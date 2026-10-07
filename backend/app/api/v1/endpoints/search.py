"""Role-protected global search API — Completion-1 A3."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.schemas.search_api import SearchResponse
from app.services.search_queries import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MAX_QUERY_LENGTH,
    MIN_QUERY_LENGTH,
    global_search,
)

router = APIRouter()
SearchReader = Annotated[User, Depends(require_role("ADMIN", "REVIEWER"))]
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("", response_model=SearchResponse)
def global_search_endpoint(
    _reader: SearchReader,
    db: DatabaseSession,
    q: Annotated[str, Query(max_length=MAX_QUERY_LENGTH)],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> SearchResponse:
    """Search lecturers, publications, and Scopus authors by literal substring.

    Query terms are trimmed before semantic validation, so a blank or
    single-character term rejects with 422 instead of matching everything.
    LIKE control characters (``%``, ``_``, ``\\``) are matched literally.
    """

    trimmed_q = q.strip()
    if len(trimmed_q) < MIN_QUERY_LENGTH:
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Từ khóa tìm kiếm phải có ít nhất {MIN_QUERY_LENGTH} ký tự.",
            code="SEARCH_QUERY_TOO_SHORT",
        )

    try:
        return global_search(db, q=trimmed_q, limit=limit)
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể truy vấn dữ liệu tra cứu.",
            code="DATABASE_UNAVAILABLE",
        ) from exc