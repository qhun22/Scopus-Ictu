"""Cookie-based authentication endpoints with revocable JWT sessions."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import COOKIE_NAME, get_current_user, require_role
from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import APIError
from app.core.security import password_hasher, token_service
from app.models.governance import User, UserNotification
from app.schemas.auth import LoginRequest, MessageResponse, UserResponse


router = APIRouter()


def _public_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        lecturer_id=user.lecturer_id,
    )


def _invalid_credentials() -> APIError:
    return APIError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email hoặc mật khẩu không đúng.",
        code="INVALID_CREDENTIALS",
    )


@router.post("/login", response_model=UserResponse, summary="Login")
def login(
    login_data: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_session)],
) -> UserResponse:
    """Authenticate credentials and issue a JWT containing ``sub`` and ``av``."""

    email = login_data.email.strip()
    if not email or not login_data.password:
        raise _invalid_credentials()

    try:
        user = (
            db.query(User)
            .filter(func.lower(User.email) == func.lower(email))
            .first()
        )
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể kết nối cơ sở dữ liệu.",
            code="DATABASE_UNAVAILABLE",
        ) from exc

    if user is None:
        raise _invalid_credentials()

    if not password_hasher.verify(login_data.password, user.password_hash):
        try:
            has_pending_password_reset = (
                db.query(UserNotification)
                .filter(
                    UserNotification.user_id == user.id,
                    UserNotification.notification_type == "PASSWORD_RESET",
                    UserNotification.is_read.is_(False),
                )
                .first()
                is not None
            )
        except SQLAlchemyError as exc:
            raise APIError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể xác minh thông tin đăng nhập.",
                code="DATABASE_UNAVAILABLE",
            ) from exc
        if has_pending_password_reset:
            raise APIError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Thông tin đăng nhập đã được quản trị viên thay đổi.",
                code="PASSWORD_RESET_BY_ADMIN",
            )
        raise _invalid_credentials()

    if not user.is_active:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đang bị khóa.",
            code="ACCOUNT_LOCKED",
        )

    token = token_service.create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "av": int(user.auth_version or 1),
        }
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.environment.lower() == "prod",
        path="/",
    )
    return _public_user(user)


@router.get("/me", response_model=UserResponse, summary="Current user")
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return _public_user(current_user)


@router.post("/logout", response_model=MessageResponse, summary="Logout")
def logout(response: Response) -> MessageResponse:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.environment.lower() == "prod",
    )
    return MessageResponse(message="Đăng xuất thành công.")


@router.get(
    "/users",
    response_model=list[UserResponse],
    summary="Deprecated admin user list alias",
    deprecated=True,
)
def list_users_legacy(
    _current_user: Annotated[User, Depends(require_role("ADMIN"))],
    db: Annotated[Session, Depends(get_session)],
) -> list[UserResponse]:
    """Keep the former URL safe while clients migrate to ``/users``."""

    try:
        return [_public_user(user) for user in db.query(User).order_by(User.created_at).all()]
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể truy vấn danh sách người dùng.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


__all__ = ["get_current_user", "router"]
