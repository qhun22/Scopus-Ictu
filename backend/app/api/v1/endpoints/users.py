"""Administrator-only user account management endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.schemas.user import (
    PasswordResetRequest,
    PasswordResetResponse,
    UserAdminResponse,
    UserAdminUpdate,
    VersionedUserAction,
)
from app.services.user_admin_service import (
    get_user_and_lecturer,
    lock_user,
    reset_user_password,
    to_admin_response,
    unlock_user,
    update_user,
)


router = APIRouter()
AdminUser = Annotated[User, Depends(require_role("ADMIN"))]
DatabaseSession = Annotated[Session, Depends(get_session)]


def _raise_database_mutation_error(db: Session, exc: Exception) -> NoReturn:
    db.rollback()
    if isinstance(exc, StaleDataError):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dữ liệu người dùng đã thay đổi. Vui lòng tải lại.",
            code="VERSION_CONFLICT",
        ) from exc
    if isinstance(exc, IntegrityError):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dữ liệu cập nhật xung đột với dữ liệu hiện có.",
            code="USER_DATA_CONFLICT",
        ) from exc
    raise APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Không thể cập nhật tài khoản người dùng.",
        code="DATABASE_UNAVAILABLE",
    ) from exc


@router.get("", response_model=list[UserAdminResponse], summary="List user accounts")
def list_users(_admin: AdminUser, db: DatabaseSession) -> list[UserAdminResponse]:
    try:
        users = db.query(User).order_by(User.created_at.asc()).all()
        lecturer_ids = [user.lecturer_id for user in users if user.lecturer_id is not None]
        lecturers = (
            db.query(Lecturer).filter(Lecturer.id.in_(lecturer_ids)).all()
            if lecturer_ids
            else []
        )
        lecturer_map = {lecturer.id: lecturer for lecturer in lecturers}
        return [
            to_admin_response(
                user,
                lecturer_map.get(user.lecturer_id) if user.lecturer_id else None,
            )
            for user in users
        ]
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể truy vấn danh sách người dùng.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


@router.get(
    "/{user_id}",
    response_model=UserAdminResponse,
    summary="Get a user account",
)
def get_user(user_id: uuid.UUID, _admin: AdminUser, db: DatabaseSession) -> UserAdminResponse:
    try:
        user, lecturer = get_user_and_lecturer(db, user_id)
        return to_admin_response(user, lecturer)
    except APIError:
        raise
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể truy vấn tài khoản người dùng.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


@router.patch(
    "/{user_id}",
    response_model=UserAdminResponse,
    summary="Update a user profile or role",
)
def patch_user(
    user_id: uuid.UUID,
    payload: UserAdminUpdate,
    admin: AdminUser,
    db: DatabaseSession,
) -> UserAdminResponse:
    try:
        user, lecturer = get_user_and_lecturer(db, user_id)
        changed = update_user(
            db,
            user=user,
            lecturer=lecturer,
            payload=payload,
            actor=admin,
        )
        if changed:
            db.commit()
            db.refresh(user)
            if lecturer is not None:
                db.refresh(lecturer)
        return to_admin_response(user, lecturer)
    except APIError:
        db.rollback()
        raise
    except (StaleDataError, IntegrityError, SQLAlchemyError) as exc:
        _raise_database_mutation_error(db, exc)


@router.post(
    "/{user_id}/lock",
    response_model=UserAdminResponse,
    summary="Lock a user account",
)
def lock_account(
    user_id: uuid.UUID,
    payload: VersionedUserAction,
    admin: AdminUser,
    db: DatabaseSession,
) -> UserAdminResponse:
    try:
        user, lecturer = get_user_and_lecturer(db, user_id)
        if lock_user(
            db,
            user=user,
            expected_version=payload.version,
            actor=admin,
        ):
            db.commit()
            db.refresh(user)
        return to_admin_response(user, lecturer)
    except APIError:
        db.rollback()
        raise
    except (StaleDataError, IntegrityError, SQLAlchemyError) as exc:
        _raise_database_mutation_error(db, exc)


@router.post(
    "/{user_id}/unlock",
    response_model=UserAdminResponse,
    summary="Unlock a user account",
)
def unlock_account(
    user_id: uuid.UUID,
    payload: VersionedUserAction,
    admin: AdminUser,
    db: DatabaseSession,
) -> UserAdminResponse:
    try:
        user, lecturer = get_user_and_lecturer(db, user_id)
        if unlock_user(
            db,
            user=user,
            expected_version=payload.version,
            actor=admin,
        ):
            db.commit()
            db.refresh(user)
        return to_admin_response(user, lecturer)
    except APIError:
        db.rollback()
        raise
    except (StaleDataError, IntegrityError, SQLAlchemyError) as exc:
        _raise_database_mutation_error(db, exc)


@router.post(
    "/{user_id}/reset-password",
    response_model=PasswordResetResponse,
    summary="Reset a user password",
)
def reset_password(
    user_id: uuid.UUID,
    payload: PasswordResetRequest,
    admin: AdminUser,
    db: DatabaseSession,
) -> PasswordResetResponse:
    try:
        user, _lecturer = get_user_and_lecturer(db, user_id)
        reset_user_password(
            db,
            user=user,
            new_password=payload.new_password,
            expected_version=payload.version,
            actor=admin,
        )
        db.commit()
        db.refresh(user)
        return PasswordResetResponse(
            message="Đã đặt lại mật khẩu.",
            user_id=user.id,
            version=user.version,
        )
    except APIError:
        db.rollback()
        raise
    except (StaleDataError, IntegrityError, SQLAlchemyError) as exc:
        _raise_database_mutation_error(db, exc)
