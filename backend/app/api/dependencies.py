"""Shared authentication and authorization dependencies."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import APIError
from app.core.security import token_service
from app.models.governance import User, UserNotification

COOKIE_NAME = "access_token"
SESSION_RENEWAL_WINDOW_SECONDS = max(
    60,
    min(15 * 60, settings.access_token_expire_minutes * 60 // 4),
)

get_db_session = get_session


def get_token_from_request(request: Request) -> str | None:
    """Extract a session token from the HttpOnly cookie or Bearer header."""

    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip() or None
    return None


def _session_error(detail: str = "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.") -> APIError:
    return APIError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        code="SESSION_REVOKED",
    )


def set_access_token_cookie(response: Response, token: str) -> None:
    """Write the authentication cookie with one consistent policy."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.environment.lower() == "prod",
        path="/",
    )


def _renew_session_if_needed(
    response: Response,
    user: User,
    payload: dict,
) -> None:
    """Keep an actively used session alive without weakening revocation checks."""
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or isinstance(expires_at, bool):
        return

    now_timestamp = int(datetime.now(UTC).timestamp())
    if expires_at - now_timestamp > SESSION_RENEWAL_WINDOW_SECONDS:
        return

    renewed_token = token_service.create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "av": int(user.auth_version or 1),
        }
    )
    set_access_token_cookie(response, renewed_token)


def get_current_user(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_session)],
) -> User:
    """Validate JWT identity, active status, and security-session version."""

    token = get_token_from_request(request)
    if not token:
        raise _session_error("Chưa đăng nhập hoặc phiên làm việc đã hết hạn.")

    payload = token_service.verify_access_token(token)
    if not payload or "sub" not in payload:
        raise _session_error()

    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (TypeError, ValueError) as exc:
        raise _session_error() from exc

    try:
        user = db.query(User).filter(User.id == user_id).first()
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể truy vấn cơ sở dữ liệu.",
            code="DATABASE_UNAVAILABLE",
        ) from exc

    if user is None:
        raise _session_error("Người dùng không tồn tại hoặc phiên đã bị thu hồi.")

    if not user.is_active:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đang bị khóa.",
            code="ACCOUNT_LOCKED",
        )

    token_auth_version = payload.get("av")
    if not isinstance(token_auth_version, int) or isinstance(token_auth_version, bool):
        raise _session_error("Phiên đăng nhập cũ không còn hiệu lực. Vui lòng đăng nhập lại.")

    user_auth_version = int(user.auth_version or 1)
    if token_auth_version != user_auth_version:
        issued_at = payload.get("iat")
        try:
            query = db.query(UserNotification).filter(
                UserNotification.user_id == user.id,
                UserNotification.notification_type.in_(
                    ("PASSWORD_RESET", "ACCOUNT_LOCKED")
                ),
            )
            if isinstance(issued_at, int) and not isinstance(issued_at, bool):
                query = query.filter(
                    UserNotification.created_at
                    >= datetime.fromtimestamp(issued_at, tz=UTC)
                )
            latest_security_notification = query.order_by(
                UserNotification.created_at.desc()
            ).first()
        except SQLAlchemyError as exc:
            raise APIError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể xác minh phiên đăng nhập.",
                code="DATABASE_UNAVAILABLE",
            ) from exc

        if (
            latest_security_notification is not None
            and latest_security_notification.notification_type == "PASSWORD_RESET"
        ):
            raise APIError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Thông tin đăng nhập đã thay đổi.",
                code="PASSWORD_RESET_BY_ADMIN",
            )
        raise _session_error("Phiên đăng nhập đã thay đổi. Vui lòng đăng nhập lại.")

    _renew_session_if_needed(response, user, payload)
    return user


def require_role(*allowed_roles: str) -> Callable[..., User]:
    """Build a dependency that authorizes only the supplied server-side roles."""

    allowed = frozenset(role.upper() for role in allowed_roles)

    def dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role.upper() not in allowed:
            raise APIError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền thực hiện thao tác này.",
                code="FORBIDDEN",
            )
        return current_user

    return dependency


__all__ = [
    "COOKIE_NAME",
    "get_current_user",
    "get_db_session",
    "get_session",
    "get_token_from_request",
    "require_role",
    "set_access_token_cookie",
]
