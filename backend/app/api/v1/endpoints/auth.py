"""Authentication endpoints — M2.2 implementation.

Provides:
- POST /api/v1/auth/login: Authenticates user credentials and sets an HttpOnly JWT cookie.
- GET  /api/v1/auth/me: Returns current authenticated user profile.
- POST /api/v1/auth/logout: Clears authentication cookie and terminates session.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.security import password_hasher, token_service
from app.models.governance import User
from app.schemas.auth import LoginRequest, MessageResponse, UserResponse

router = APIRouter()

COOKIE_NAME = "access_token"


def get_token_from_request(request: Request) -> str | None:
    """Extract auth token from HttpOnly cookie or Authorization Bearer header."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    return token


def get_current_user(
    request: Request,
    db: Session = Depends(get_session),
) -> User:
    """FastAPI dependency to extract and validate the current authenticated user.
    
    Returns 401 when anonymous or token is invalid/expired without database crashing.
    """
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa đăng nhập hoặc phiên làm việc đã hết hạn.",
        )

    payload = token_service.verify_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
        )

    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã định danh người dùng trong phiên không hợp lệ.",
        )

    try:
        user = db.query(User).filter(User.id == user_id).first()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể truy vấn cơ sở dữ liệu. Vui lòng kiểm tra kết nối database.",
        ) from exc

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa.",
        )

    return user


@router.post(
    "/login",
    response_model=UserResponse,
    summary="User login with email and password",
)
def login(
    login_data: LoginRequest,
    response: Response,
    db: Session = Depends(get_session),
) -> UserResponse:
    """Authenticate user credentials, set HttpOnly session cookie, and return user profile."""
    email = login_data.email.strip()
    if not email or not login_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
        )

    try:
        user = (
            db.query(User)
            .filter(func.lower(User.email) == func.lower(email))
            .first()
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể kết nối cơ sở dữ liệu. Vui lòng kiểm tra dịch vụ PostgreSQL.",
        ) from exc

    if not user or not password_hasher.verify(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa.",
        )

    # Issue signed JWT token with string sub claim
    token = token_service.create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
        }
    )

    # Set secure HttpOnly cookie
    is_secure = settings.environment.lower() == "prod"
    max_age_seconds = settings.access_token_expire_minutes * 60

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
    )

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        lecturer_id=user.lecturer_id,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the profile of currently authenticated user."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
        lecturer_id=current_user.lecturer_id,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="User logout and session termination",
)
def logout(response: Response) -> MessageResponse:
    """Clear HttpOnly authentication cookie."""
    is_secure = settings.environment.lower() == "prod"
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=is_secure,
    )
    return MessageResponse(message="Đăng xuất thành công.")