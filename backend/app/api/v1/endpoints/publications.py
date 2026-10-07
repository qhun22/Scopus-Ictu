"""Role-protected canonical publication read API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.schemas.publication_api import PublicationDetailResponse, PublicationListResponse
from app.services.publication_queries import get_publication_detail, list_publications

router = APIRouter()
PublicationReader = Annotated[User, Depends(require_role("ADMIN", "REVIEWER"))]
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
