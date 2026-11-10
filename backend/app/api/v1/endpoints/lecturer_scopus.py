"""Authorized lecturer Scopus projections and self-service profile updates."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.schemas.lecturer import LecturerScopusImportItem
from app.schemas.lecturer_profile_update import LecturerProfileUpdate
from app.schemas.lecturer_scopus_api import LecturerPublicationsAPIResponse
from app.schemas.lecturer_scopus_projection import (
    ApprovedIdentitySummaryRead,
    LecturerProfileRead,
)
from app.services.lecturer_dataset.scopus_references import pending_scopus_imports
from app.services.lecturer_profile_service import update_my_profile
from app.services.lecturer_scopus_projection import LecturerScopusProjectionService
from app.services.matching.manual_candidate import (
    ManualCandidateError,
    assign_scopus_identity,
    revoke_scopus_identity,
)
from app.services.primary_scopus_identity import (
    PrimaryIdentityError,
    PrimaryIdentityService,
)

router = APIRouter()

DatabaseSession = Annotated[Session, Depends(get_session)]
LecturerUser = Annotated[User, Depends(require_role("LECTURER"))]
AdminUser = Annotated[User, Depends(require_role("ADMIN"))]
StaffUser = Annotated[User, Depends(require_role("ADMIN", "REVIEWER"))]
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


@router.get("/scopus-import-review", response_model=list[LecturerScopusImportItem])
def get_pending_scopus_imports(
    _staff: StaffUser,
    db: DatabaseSession,
    lecturer_id: uuid.UUID | None = None,
) -> list[dict]:
    """Retained IDs pending human review, also available after page refresh."""
    return _read(lambda: pending_scopus_imports(db, lecturer_id))


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


@router.patch("/me/profile", response_model=LecturerProfileRead)
def patch_my_profile(
    payload: LecturerProfileUpdate,
    current_user: LecturerUser,
    db: DatabaseSession,
) -> LecturerProfileRead:
    return update_my_profile(db, actor=current_user, payload=payload)


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
    _staff: StaffUser,
    db: DatabaseSession,
) -> list[ApprovedIdentitySummaryRead]:
    service = LecturerScopusProjectionService(db)
    _read(lambda: _admin_profile(service, lecturer_id))
    return _read(lambda: service.get_approved_identity_summaries(lecturer_id))


class AssignScopusIdentityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scopus_id: str = Field(..., min_length=1, max_length=50)
    # Required: cites where the reviewer got this (e.g. the lecturer's ORCID
    # page, their own Scopus profile) -- recorded as the review's reason.
    reason: str = Field(..., min_length=1, max_length=4000)
    create_author_if_missing: bool = Field(
        default=False,
        description="Manual assignment may register an author ID before publications are imported.",
    )


class AssignScopusIdentityResponse(BaseModel):
    identity_id: uuid.UUID
    scopus_id: str
    scopus_preferred_name: str
    already_approved: bool


@router.post(
    "/{lecturer_id}/scopus/identities",
    response_model=AssignScopusIdentityResponse,
    summary="Assign one Scopus author ID to a lecturer directly from the lecturer profile screen",
)
def assign_identity(
    lecturer_id: uuid.UUID,
    request: AssignScopusIdentityRequest,
    staff: StaffUser,
    db: DatabaseSession,
) -> AssignScopusIdentityResponse:
    """Thin wrapper over the normal review boundary: still goes through
    ``CandidateReviewService.accept_candidate()`` (creating/reusing a PENDING
    candidate with the reviewer's reason as evidence first), so the usual D-2
    evidence/reason rules and audit trail apply -- see
    ``services.matching.manual_candidate.assign_scopus_identity``. This only
    collapses "Thêm cặp thủ công" + "Duyệt đối sánh" into one request for a
    reviewer who already holds external evidence (ORCID, the lecturer's own
    publication list, …)."""
    try:
        result = assign_scopus_identity(
            db,
            lecturer_id=lecturer_id,
            scopus_id=request.scopus_id,
            reason=request.reason,
            reviewer=staff,
            create_author_if_missing=request.create_author_if_missing,
        )
    except ManualCandidateError as exc:
        db.rollback()
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể gán ID Scopus.",
            code="DATABASE_UNAVAILABLE",
        ) from exc
    return AssignScopusIdentityResponse(
        identity_id=result.identity_id,
        scopus_id=result.scopus_id,
        scopus_preferred_name=result.scopus_preferred_name,
        already_approved=result.already_approved,
    )


class RevokeScopusIdentityResponse(BaseModel):
    identity_id: uuid.UUID
    scopus_id: str


@router.delete(
    "/{lecturer_id}/scopus/identities/{identity_id}",
    response_model=RevokeScopusIdentityResponse,
    summary="Undo (revoke) a Scopus ID already assigned to a lecturer -- e.g. added by mistake",
)
def revoke_identity(
    lecturer_id: uuid.UUID,
    identity_id: uuid.UUID,
    admin: AdminUser,
    db: DatabaseSession,
    reason: Annotated[str, Query(min_length=1, max_length=4000)],
) -> RevokeScopusIdentityResponse:
    """ADMIN-only (same rule ``CandidateReviewService.revoke_identity()`` already
    enforces): appends a compensating review (G10) rather than deleting
    anything -- the candidate goes back to PENDING, so this pair can be
    re-decided later. See ``services.matching.manual_candidate.revoke_scopus_identity``.
    ``reason`` is a query param (not a JSON body) so the client's plain
    DELETE-with-no-body helper can be reused."""
    try:
        result = revoke_scopus_identity(
            db,
            lecturer_id=lecturer_id,
            identity_id=identity_id,
            reason=reason,
            admin=admin,
        )
    except ManualCandidateError as exc:
        db.rollback()
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể bỏ ID Scopus.",
            code="DATABASE_UNAVAILABLE",
        ) from exc
    return RevokeScopusIdentityResponse(identity_id=result.identity_id, scopus_id=result.scopus_id)


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


class PrimaryIdentityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_id: uuid.UUID
    reason: str = Field(..., min_length=1, max_length=4000)


class ClearPrimaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=4000)


class PrimaryIdentityResponse(BaseModel):
    lecturer_id: uuid.UUID
    primary_identity_id: uuid.UUID | None
    suggested_identity_id: uuid.UUID | None


def _primary_change(db: Session, lecturer_id: uuid.UUID, call) -> PrimaryIdentityResponse:
    try:
        view = call()
    except PrimaryIdentityError as exc:
        db.rollback()
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="The change conflicted with the persisted state.",
            code="PRIMARY_ID_PERSISTENCE_CONFLICT",
        ) from exc
    return PrimaryIdentityResponse(
        lecturer_id=lecturer_id,
        primary_identity_id=view.primary_identity_id,
        suggested_identity_id=view.suggested_identity_id,
    )


@router.post(
    "/{lecturer_id}/scopus/primary-identity",
    response_model=PrimaryIdentityResponse,
    summary="Choose one approved Scopus ID as the lecturer's main ID (display label only)",
)
def set_primary_identity(
    lecturer_id: uuid.UUID,
    request: PrimaryIdentityRequest,
    staff: StaffUser,
    db: DatabaseSession,
) -> PrimaryIdentityResponse:
    service = PrimaryIdentityService(db)
    return _primary_change(db, lecturer_id, lambda: service.set_primary(
        lecturer_id, request.identity_id, staff.id, request.reason))


@router.post(
    "/{lecturer_id}/scopus/primary-identity/clear",
    response_model=PrimaryIdentityResponse,
    summary="Remove the lecturer's chosen main Scopus ID label",
)
def clear_primary_identity(
    lecturer_id: uuid.UUID,
    request: ClearPrimaryRequest,
    staff: StaffUser,
    db: DatabaseSession,
) -> PrimaryIdentityResponse:
    service = PrimaryIdentityService(db)
    return _primary_change(db, lecturer_id, lambda: service.clear_primary(
        lecturer_id, staff.id, request.reason))


__all__ = ["router"]
