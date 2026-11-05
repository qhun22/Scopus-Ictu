"""Role-protected canonical publication read API."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_optional_current_user, require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import AuditEvent, User
from app.schemas.publication_api import (
    PublicationDetailResponse,
    PublicationFilterOptions,
    PublicationListResponse,
)
from app.schemas.publication_export import (
    EXPORT_SCHEMA_VERSION,
    AffiliationGapListResponse,
    PublicationExportDataset,
    PublicationExportResponse,
)
from app.services import normalization_compare
from app.services.affiliation_export import GAP_REASONS
from app.services.affiliation_gaps import gaps_csv, list_gaps
from app.services.publication_export import export_publications, export_publications_csv
from app.services.publication_queries import (
    get_publication_detail,
    get_publication_filter_options,
    list_publications,
)

router = APIRouter()
# Guests and authenticated users may read the public list/detail. Export stays
# ADMIN-only.
PublicationReader = Annotated[User | None, Depends(get_optional_current_user)]
PublicationAdmin = Annotated[User, Depends(require_role("ADMIN"))]
PublicationStaff = Annotated[User, Depends(require_role("ADMIN", "REVIEWER"))]
DatabaseSession = Annotated[Session, Depends(get_session)]

# Exported file names carry Vietnam time (UTC+7), the clock the users read, not UTC.
VIETNAM_TZ = timezone(timedelta(hours=7))
CSV_MEDIA_TYPE = "text/csv; charset=utf-8"
GAP_REASON_PATTERN = "^(" + "|".join(GAP_REASONS) + ")$"


def _database_unavailable(exc: SQLAlchemyError) -> APIError:
    return APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Không thể truy vấn dữ liệu công bố.",
        code="DATABASE_UNAVAILABLE",
    )


def _for_role(result: PublicationDetailResponse, reader: User | None) -> PublicationDetailResponse:
    """Withhold internal/administrative data from everyone but ADMIN.

    Authors, affiliations and their evidence stay visible to everyone.
    Approved lecturer links (another person's name, staff code, ORCID) and
    internal import provenance (file names/hashes, row numbers) are
    ADMIN-only — guests, LECTURER and REVIEWER readers all get the same
    withheld view.
    """

    if reader is not None and reader.role == "ADMIN":
        return result
    # The ADMIN's free-text reason on a manual affiliation is an internal note (it can name people):
    # the unit text, its confidence and its evidence link stay visible, the note does not.
    authors = [
        author.model_copy(update={
            "affiliation_overrides": [
                override.model_copy(update={"reason": ""})
                for override in author.affiliation_overrides
            ]
        })
        for author in result.authors
    ]
    return result.model_copy(
        update={"provenance": [], "approved_lecturer_links": [], "authors": authors}
    )


@router.get("", response_model=PublicationListResponse)
def list_publication_endpoint(
    _reader: PublicationReader,
    db: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=255)] = None,
    year: int | None = None,
    document_type: Annotated[str | None, Query(max_length=50)] = None,
    publication_stage: Annotated[str | None, Query(max_length=50)] = None,
    open_access_status: Annotated[str | None, Query(max_length=50)] = None,
    scopus_id: Annotated[str | None, Query(max_length=32, pattern=r"^\d*$")] = None,
    author_name: Annotated[str | None, Query(max_length=255)] = None,
    missing_doi: bool | None = None,
) -> PublicationListResponse:
    """List canonical publications using server-side filtering and pagination."""

    try:
        return list_publications(
            db,
            page=page,
            page_size=page_size,
            q=q,
            year=year,
            document_type=document_type,
            publication_stage=publication_stage,
            open_access_status=open_access_status,
            scopus_id=scopus_id,
            author_name=author_name,
            missing_doi=missing_doi,
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc


# /filters MUST be declared before /{eid} so FastAPI matches it as a static path.
@router.get("/filters", response_model=PublicationFilterOptions)
def list_publication_filter_options_endpoint(
    _reader: PublicationReader,
    db: DatabaseSession,
    q: Annotated[str | None, Query(max_length=255)] = None,
    year: int | None = None,
    document_type: Annotated[str | None, Query(max_length=50)] = None,
    publication_stage: Annotated[str | None, Query(max_length=50)] = None,
    open_access_status: Annotated[str | None, Query(max_length=50)] = None,
    scopus_id: Annotated[str | None, Query(max_length=32, pattern=r"^\d*$")] = None,
    author_name: Annotated[str | None, Query(max_length=255)] = None,
    missing_doi: bool | None = None,
) -> PublicationFilterOptions:
    """Year/document-type/stage/open-access values for the list page's filter
    dropdowns, each counted within whatever OTHER filters are already applied
    (same parameters as the list endpoint) — not that dropdown's own filter."""

    try:
        return get_publication_filter_options(
            db,
            q=q,
            year=year,
            document_type=document_type,
            publication_stage=publication_stage,
            open_access_status=open_access_status,
            scopus_id=scopus_id,
            author_name=author_name,
            missing_doi=missing_doi,
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc


# /export and /affiliation-gaps MUST be declared before /{eid} so FastAPI matches them as
# static paths.
def _audit_export(
    db: Session,
    admin: User,
    *,
    entity_type: str,
    action: str,
    export_id: uuid.UUID,
    metadata: dict,
) -> None:
    """Record the export and commit BEFORE the file is returned; a failed commit means 503
    and no file is delivered."""

    db.add(
        AuditEvent(
            entity_type=entity_type,
            entity_id=export_id,
            action=action,
            actor_type="USER",
            actor_user_id=admin.id,
            actor_service=None,
            before_state=None,
            after_state=None,
            event_metadata=metadata,
        )
    )
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể ghi nhật ký xuất dữ liệu công bố.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


def _attachment(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get("/export")
def export_publication_endpoint(
    admin: PublicationAdmin,
    db: DatabaseSession,
    q: Annotated[str | None, Query(max_length=255)] = None,
    year: int | None = None,
    document_type: Annotated[str | None, Query(max_length=50)] = None,
    publication_stage: Annotated[str | None, Query(max_length=50)] = None,
    open_access_status: Annotated[str | None, Query(max_length=50)] = None,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",  # noqa: A002
) -> Response:
    """Export the filtered canonical publication dataset as a UTF-8 JSON (default) or CSV file.

    Supports the same filter parameters as the list endpoint (no pagination). The CSV has one
    row per author position. Writes an AuditEvent and commits before the file bytes are
    returned; if the audit commit fails the endpoint returns 503 and no file is delivered.
    """

    export_id = uuid.uuid4()
    now = datetime.now(UTC)
    timestamp_str = now.astimezone(VIETNAM_TZ).strftime("%Y%m%d_%H%M%S")
    filters = {
        "q": q,
        "year": year,
        "document_type": document_type,
        "publication_stage": publication_stage,
        "open_access_status": open_access_status,
    }

    if format == "csv":
        try:
            content, record_count, row_count, filters_applied = export_publications_csv(
                db, **filters
            )
        except SQLAlchemyError as exc:
            raise _database_unavailable(exc) from exc
        _audit_export(
            db,
            admin,
            entity_type="publication_export",
            action="PUBLICATION_DATASET_EXPORTED",
            export_id=export_id,
            metadata={
                "record_count": record_count,
                "row_count": row_count,
                "format": "CSV",
                "schema_version": EXPORT_SCHEMA_VERSION,
                "filters_applied": filters_applied,
            },
        )
        return Response(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            headers=_attachment(f"ictu_publications_{timestamp_str}.csv"),
        )

    try:
        items, filters_applied = export_publications(db, **filters)
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc

    dataset = PublicationExportDataset(
        name="ICTU Publication Export",
        schema_version=EXPORT_SCHEMA_VERSION,
        export_id=export_id,
        exported_at=now.isoformat(),
        record_count=len(items),
        filters_applied=filters_applied,
        source="SCOPUS_ICTU_SYSTEM_EXPORT",
    )
    payload = PublicationExportResponse(dataset=dataset, publications=items)

    content = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    _audit_export(
        db,
        admin,
        entity_type="publication_export",
        action="PUBLICATION_DATASET_EXPORTED",
        export_id=export_id,
        metadata={
            "record_count": len(items),
            "format": "JSON",
            "schema_version": EXPORT_SCHEMA_VERSION,
            "filters_applied": filters_applied,
        },
    )

    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers=_attachment(f"ictu_publications_{timestamp_str}.json"),
    )


@router.get("/affiliation-gaps", response_model=AffiliationGapListResponse)
def list_affiliation_gaps_endpoint(
    _admin: PublicationAdmin,
    db: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    year: int | None = None,
    eid: Annotated[str | None, Query(max_length=64)] = None,
    reason: Annotated[str | None, Query(pattern=GAP_REASON_PATTERN)] = None,
    ictu_only: bool = False,
) -> AffiliationGapListResponse:
    """Author positions with no affiliation to show, one reason each (ADMIN, read-only)."""

    try:
        return list_gaps(
            db,
            page=page,
            page_size=page_size,
            year=year,
            eid=eid,
            reason=reason,
            ictu_only=ictu_only,
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc


@router.get("/affiliation-gaps/export")
def export_affiliation_gaps_endpoint(
    admin: PublicationAdmin,
    db: DatabaseSession,
    year: int | None = None,
    eid: Annotated[str | None, Query(max_length=64)] = None,
    reason: Annotated[str | None, Query(pattern=GAP_REASON_PATTERN)] = None,
    ictu_only: bool = False,
) -> Response:
    """The same list as a CSV (no pagination). Audited like the publication export."""

    export_id = uuid.uuid4()
    timestamp_str = datetime.now(VIETNAM_TZ).strftime("%Y%m%d_%H%M%S")
    try:
        content, row_count = gaps_csv(db, year=year, eid=eid, reason=reason, ictu_only=ictu_only)
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc
    filters_applied = {
        key: value
        for key, value in (
            ("year", year),
            ("eid", eid),
            ("reason", reason),
            ("ictu_only", True if ictu_only else None),
        )
        if value is not None
    }
    _audit_export(
        db,
        admin,
        entity_type="publication_affiliation_gaps_export",
        action="PUBLICATION_AFFILIATION_GAPS_EXPORTED",
        export_id=export_id,
        metadata={"row_count": row_count, "format": "CSV", "filters_applied": filters_applied},
    )
    return Response(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        headers=_attachment(f"ictu_affiliation_gaps_{timestamp_str}.csv"),
    )


class NormalizationCompareField(BaseModel):
    field: str
    raw: str | None
    stored: str | None
    canonical: str | None
    status: str


class NormalizationCompareSource(BaseModel):
    file_name: str
    row_number: int
    row_hash: str


class NormalizationCompareResponse(BaseModel):
    eid: str
    sources: list[NormalizationCompareSource]
    fields: list[NormalizationCompareField]


@router.get("/{eid}/normalization-compare", response_model=NormalizationCompareResponse)
def normalization_compare_endpoint(
    eid: str, _staff: PublicationStaff, db: DatabaseSession
) -> NormalizationCompareResponse:
    """Raw CSV value vs stored value vs canonical form, field by field (read-only)."""

    try:
        result = normalization_compare.build_compare(db, eid)
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc
    if result is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy công bố.",
            code="PUBLICATION_NOT_FOUND",
        )
    return NormalizationCompareResponse(
        eid=result.eid,
        sources=[
            NormalizationCompareSource(file_name=s.file_name, row_number=s.row_number, row_hash=s.row_hash)
            for s in result.sources
        ],
        fields=[
            NormalizationCompareField(
                field=f.field, raw=f.raw, stored=f.stored, canonical=f.canonical, status=f.status
            )
            for f in result.fields
        ],
    )


@router.get("/{eid}", response_model=PublicationDetailResponse)
def get_publication_endpoint(
    eid: str,
    reader: PublicationReader,
    db: DatabaseSession,
) -> PublicationDetailResponse:
    """Return one canonical publication by its unique EID."""

    try:
        result = get_publication_detail(db, eid=eid)
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc

    if result is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy công bố.",
            code="PUBLICATION_NOT_FOUND",
        )
    return _for_role(result, reader)
