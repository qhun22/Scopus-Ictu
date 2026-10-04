"""Author endpoints — M2.6B.

Provides:
- POST /normalize-import/{import_id}  — run author normalization
- GET  /authors                     — list/search authors
- GET  /authors/stats               — global canonical aggregates
- GET  /authors/{author_id}         — author detail with variants
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.models.publication import (
    PublicationAuthor,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.models.scopus_raw import ScopusImport
from app.schemas.scopus_author import (
    AuthorListItemResponse,
    AuthorListResponse,
    AuthorNormalizationResponse,
    NormalizationCountersResponse,
    NormalizationErrorEntry,
    ScopusAuthorDetailResponse,
    ScopusAuthorNameVariantResponse,
)
from app.services.normalization.scopus_author_normalizer import (
    is_import_eligible_for_author_normalization,
    normalize_authors_for_import,
)

router = APIRouter()
AdminUser = Annotated[User, Depends(require_role("ADMIN"))]
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post(
    "/normalize-import/{import_id}",
    response_model=AuthorNormalizationResponse,
    summary="Run author normalization for an APPLIED Scopus import (M2.6B)",
)
def normalize_authors_endpoint(
    import_id: uuid.UUID,
    admin: AdminUser,
    db: DatabaseSession,
) -> AuthorNormalizationResponse:
    """Admin-only: normalize authors for a Scopus import whose publication normalization is complete.

    Prerequisites:
    - Import is a Scopus import (not Lecturer).
    - Import status is APPLIED.
    - M2.6A publication normalization has been run.

    Idempotent: re-running produces EXISTING counters without duplicates.
    On failure the import remains APPLIED (never reverts to STAGED).
    """
    item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
    if item is None:
        raise APIError(
            status_code=404,
            detail="Không tìm thấy phiên nhập dữ liệu.",
            code="IMPORT_NOT_FOUND",
        )

    eligible, reason = is_import_eligible_for_author_normalization(item)
    if not eligible:
        raise APIError(
            status_code=409,
            detail=reason or "Phiên nhập không đủ điều kiện chuẩn hóa tác giả.",
            code="IMPORT_NOT_ELIGIBLE_FOR_AUTHOR_NORMALIZATION",
            data={"status": item.status},
        )

    try:
        counters = normalize_authors_for_import(db, import_id)
        db.refresh(item)
        # Return the import's updated normalization_summary
        author_summary = (
            item.normalization_summary.get("authors")
            if isinstance(item.normalization_summary, dict)
            else None
        )
        if author_summary is None:
            raise APIError(
                status_code=500,
                detail="Chuẩn hóa tác giả đã chạy nhưng không tìm thấy kết quả.",
                code="AUTHOR_NORMALIZATION_FAILED",
            )
        # Errors are persisted alongside the counters in the import summary.
        # AuthorNormalizationCounters intentionally contains only numeric
        # counters, so reading ``counters.errors`` here raises AttributeError
        # after an otherwise successful normalization (including idempotent
        # reruns) and gets converted into a misleading generic 500.
        persisted_errors = author_summary.get("errors", [])
        error_entries = [
            NormalizationErrorEntry(
                row_number=err.row_number,
                code=err.code,
                message=err.message,
            )
            for err in (
                NormalizationErrorEntry.model_validate(error)
                for error in persisted_errors
            )
        ]
        return AuthorNormalizationResponse(
            import_id=import_id,
            status=author_summary.get("status", "COMPLETED"),
            counters=NormalizationCountersResponse(
                raw_records_processed=counters.raw_records_processed,
                raw_records_failed=counters.raw_records_failed,
                author_occurrences=counters.author_occurrences,
                unique_authors_seen=counters.unique_authors_seen,
                authors_created=counters.authors_created,
                authors_existing=counters.authors_existing,
                publication_author_links_created=counters.publication_author_links_created,
                publication_author_links_existing=counters.publication_author_links_existing,
                variants_created=counters.variants_created,
                variants_existing=counters.variants_existing,
                conflicts=counters.conflicts,
            ),
            errors=error_entries,
        )
    except APIError:
        # Preserve deliberate, already-classified public errors.
        raise
    except ValueError as exc:
        raise APIError(
            status_code=409,
            detail=str(exc),
            code="AUTHOR_NORMALIZATION_NOT_ELIGIBLE",
        )
    except Exception:
        raise APIError(
            status_code=500,
            detail="Chuẩn hóa tác giả không thành công.",
            code="AUTHOR_NORMALIZATION_ERROR",
        )


@router.get("/stats", response_model=dict)
def author_stats(_admin: AdminUser, db: DatabaseSession) -> dict:
    """Admin-only: global canonical aggregates for the Authors tab KPIs."""
    total_authors = db.query(func.count(ScopusAuthor.id)).scalar() or 0
    total_links = db.query(func.count(PublicationAuthor.id)).scalar() or 0
    total_variants = db.query(func.count(ScopusAuthorNameVariant.id)).scalar() or 0
    return {
        "total_authors": int(total_authors),
        "publication_author_links": int(total_links),
        "name_variants": int(total_variants),
    }


@router.get("", response_model=AuthorListResponse)
def list_authors(
    _admin: AdminUser,
    db: DatabaseSession,
    q: Annotated[str | None, Query(description="Search by name or Scopus ID")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuthorListResponse:
    """Admin-only: list and search Scopus authors."""
    base_q = db.query(ScopusAuthor)

    if q:
        q_stripped = q.strip()
        base_q = base_q.filter(
            or_(
                ScopusAuthor.scopus_id.ilike(f"%{q_stripped}%"),
                ScopusAuthor.preferred_name.ilike(f"%{q_stripped}%"),
            )
        )

    total = base_q.count()

    offset = (page - 1) * page_size
    authors = (
        base_q.order_by(ScopusAuthor.preferred_name)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = []
    for author in authors:
        pub_count = (
            db.query(func.count(PublicationAuthor.id))
            .filter(PublicationAuthor.scopus_author_id == author.id)
            .scalar()
            or 0
        )
        var_count = (
            db.query(func.count(ScopusAuthorNameVariant.id))
            .filter(ScopusAuthorNameVariant.scopus_author_id == author.id)
            .scalar()
            or 0
        )
        items.append(
            AuthorListItemResponse(
                id=author.id,
                scopus_id=author.scopus_id,
                preferred_name=author.preferred_name,
                publication_count=int(pub_count),
                variant_count=int(var_count),
            )
        )

    return AuthorListResponse(
        items=items,
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.get("/{author_id}", response_model=ScopusAuthorDetailResponse)
def author_detail(
    author_id: uuid.UUID,
    _admin: AdminUser,
    db: DatabaseSession,
) -> ScopusAuthorDetailResponse:
    """Admin-only: get author detail with name variants."""
    author = db.query(ScopusAuthor).filter(ScopusAuthor.id == author_id).first()
    if author is None:
        raise APIError(
            status_code=404,
            detail="Không tìm thấy tác giả.",
            code="AUTHOR_NOT_FOUND",
        )

    variants = (
        db.query(ScopusAuthorNameVariant)
        .filter(ScopusAuthorNameVariant.scopus_author_id == author.id)
        .order_by(ScopusAuthorNameVariant.created_at)
        .all()
    )
    pub_count = (
        db.query(func.count(PublicationAuthor.id))
        .filter(PublicationAuthor.scopus_author_id == author.id)
        .scalar()
        or 0
    )

    return ScopusAuthorDetailResponse(
        id=author.id,
        scopus_id=author.scopus_id,
        preferred_name=author.preferred_name,
        created_at=author.created_at,
        updated_at=author.updated_at,
        variants=[
            ScopusAuthorNameVariantResponse(
                id=v.id,
                variant_type=v.variant_type,
                variant_name=v.variant_name,
                variant_name_normalized=v.variant_name_normalized,
                created_at=v.created_at,
            )
            for v in variants
        ],
        publication_count=int(pub_count),
    )
