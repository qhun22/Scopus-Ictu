"""Authorized HTTP boundary for lecturer Scopus read projections."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.schemas.lecturer_scopus_api import LecturerPublicationsAPIResponse
from app.schemas.lecturer_scopus_projection import (
    ApprovedIdentitySummaryRead,
    LecturerProfileRead,
    PaginatedLecturerPublicationsRead,
)
from app.services.lecturer_scopus_projection import LecturerScopusProjectionService

router = APIRouter()

DatabaseSession = Annotated[Session, Depends(get_session)]
LecturerUser = Annotated[User, Depends(require_role("LECTURER"))]
AdminUser = Annotated[User, Depends(require_role("ADMIN"))]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]

T = TypeVar("T")


def _read(call: Callable[[], T]) -> T:
    """Translate only database failures into the repository API error shape."""

    try:
        return call()
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể truy vấn dữ liệu hồ sơ Scopus.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


def _linked_lecturer_id(current_user: User) -> uuid.UUID:
    lecturer_id = current_user.lecturer_id
    if lecturer_id is None:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản giảng viên chưa được liên kết với hồ sơ giảng viên.",
            code="LECTURER_NOT_LINKED",
        )
    return lecturer_id


def _lecturer_not_found() -> APIError:
    return APIError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Không tìm thấy hồ sơ giảng viên.",
        code="LECTURER_NOT_FOUND",
    )


def _publications_response(
    service: LecturerScopusProjectionService,
    lecturer_id: uuid.UUID,
    page: int,
    page_size: int,
) -> LecturerPublicationsAPIResponse:
    page_result = service.get_lecturer_publications(
        lecturer_id,
        page=page,
        page_size=page_size,
    )
    aggregates = service.get_lecturer_publication_aggregates(lecturer_id)
    return LecturerPublicationsAPIResponse(
        items=page_result.items,
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
        aggregates=aggregates,
    )


def _admin_profile(
    service: LecturerScopusProjectionService, lecturer_id: uuid.UUID
) -> LecturerProfileRead:
    profile = service.get_lecturer_profile(lecturer_id)
    if profile is None:
        raise _lecturer_not_found()
    return profile


# Static /me routes intentionally precede the explicit administrator routes.
@router.get("/me/profile", response_model=LecturerProfileRead)
def get_my_profile(
    current_user: LecturerUser,
    db: DatabaseSession,
) -> LecturerProfileRead:
    lecturer_id = _linked_lecturer_id(current_user)
    service = LecturerScopusProjectionService(db)
    profile = _read(lambda: service.get_lecturer_profile(lecturer_id))
    if profile is None:
        raise _lecturer_not_found()
    return profile


@router.get(
    "/me/identities",
    response_model=list[ApprovedIdentitySummaryRead],
)
def get_my_identities(
    current_user: LecturerUser,
    db: DatabaseSession,
) -> list[ApprovedIdentitySummaryRead]:
    lecturer_id = _linked_lecturer_id(current_user)
    service = LecturerScopusProjectionService(db)
    return _read(lambda: service.get_approved_identity_summaries(lecturer_id))


@router.get(
    "/me/publications",
    response_model=LecturerPublicationsAPIResponse,
)
def get_my_publications(
    current_user: LecturerUser,
    db: DatabaseSession,
    page: Page = 1,
    page_size: PageSize = 20,
) -> LecturerPublicationsAPIResponse:
    lecturer_id = _linked_lecturer_id(current_user)
    service = LecturerScopusProjectionService(db)
    return _read(
        lambda: _publications_response(service, lecturer_id, page, page_size)
    )


@router.get(
    "/{lecturer_id}/scopus/profile",
    response_model=LecturerProfileRead,
)
def get_admin_profile(
    lecturer_id: uuid.UUID,
    _admin: AdminUser,
    db: DatabaseSession,
) -> LecturerProfileRead:
    service = LecturerScopusProjectionService(db)
    return _read(lambda: _admin_profile(service, lecturer_id))


@router.get(
    "/{lecturer_id}/scopus/identities",
    response_model=list[ApprovedIdentitySummaryRead],
)
def get_admin_identities(
    lecturer_id: uuid.UUID,
    _admin: AdminUser,
    db: DatabaseSession,
) -> list[ApprovedIdentitySummaryRead]:
    service = LecturerScopusProjectionService(db)
    _read(lambda: _admin_profile(service, lecturer_id))
    return _read(lambda: service.get_approved_identity_summaries(lecturer_id))


@router.get(
    "/{lecturer_id}/scopus/publications",
    response_model=LecturerPublicationsAPIResponse,
)
def get_admin_publications(
    lecturer_id: uuid.UUID,
    _admin: AdminUser,
    db: DatabaseSession,
    page: Page = 1,
    page_size: PageSize = 20,
) -> LecturerPublicationsAPIResponse:
    service = LecturerScopusProjectionService(db)
    _read(lambda: _admin_profile(service, lecturer_id))
    return _read(
        lambda: _publications_response(service, lecturer_id, page, page_size)
    )


__all__ = ["router"]
