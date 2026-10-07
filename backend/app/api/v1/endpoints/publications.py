"""Role-protected canonical publication read API."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import AuditEvent, User
from app.schemas.publication_api import PublicationDetailResponse, PublicationListResponse
from app.schemas.publication_export import PublicationExportDataset, PublicationExportResponse
from app.services.publication_export import export_publications
from app.services.publication_queries import get_publication_detail, list_publications

router = APIRouter()
PublicationReader = Annotated[User, Depends(require_role("ADMIN", "REVIEWER"))]
PublicationAdmin = Annotated[User, Depends(require_role("ADMIN"))]
DatabaseSession = Annotated[Session, Depends(get_session)]


def _database_unavailable(exc: SQLAlchemyError) -> APIError:
    return APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Không thể truy vấn dữ liệu công bố.",
        code="DATABASE_UNAVAILABLE",
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
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc


# /export MUST be declared before /{eid} so FastAPI matches it as a static path.
@router.get("/export")
def export_publication_endpoint(
    admin: PublicationAdmin,
    db: DatabaseSession,
    q: Annotated[str | None, Query(max_length=255)] = None,
    year: int | None = None,
    document_type: Annotated[str | None, Query(max_length=50)] = None,
    publication_stage: Annotated[str | None, Query(max_length=50)] = None,
    open_access_status: Annotated[str | None, Query(max_length=50)] = None,
) -> Response:
    """Export the filtered canonical publication dataset as a UTF-8 JSON file.

    Supports the same filter parameters as the list endpoint (no pagination).
    Writes an AuditEvent and commits before the file bytes are returned; if the
    audit commit fails the endpoint returns 503 and no file is delivered.
    """

    export_id = uuid.uuid4()
    now = datetime.now(UTC)

    try:
        items, filters_applied = export_publications(
            db,
            q=q,
            year=year,
            document_type=document_type,
            publication_stage=publication_stage,
            open_access_status=open_access_status,
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc

    dataset = PublicationExportDataset(
        name="ICTU Publication Export",
        schema_version="1.0",
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

    db.add(
        AuditEvent(
            entity_type="publication_export",
            entity_id=export_id,
            action="PUBLICATION_DATASET_EXPORTED",
            actor_type="USER",
            actor_user_id=admin.id,
            actor_service=None,
            before_state=None,
            after_state=None,
            event_metadata={
                "record_count": len(items),
                "format": "JSON",
                "schema_version": "1.0",
                "filters_applied": filters_applied,
            },
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

    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    filename = f"ictu_publications_{timestamp_str}.json"

    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{eid}", response_model=PublicationDetailResponse)
def get_publication_endpoint(
    eid: str,
    _reader: PublicationReader,
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
    return result
