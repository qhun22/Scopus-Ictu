"""Cookie-based authentication endpoints with revocable JWT sessions."""

from __future__ import annotations

import math
import secrets
from datetime import timedelta
from typing import Annotated
from urllib.parse import urlencode, urlsplit

import httpx2 as httpx
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    COOKIE_NAME,
    get_current_user,
    require_role,
    set_access_token_cookie,
)
from app.core.config import settings
from app.core.database import get_session
from app.core.display_names import repair_display_name
from app.core.exceptions import APIError
from app.core.login_throttle import login_throttle
from app.core.security import password_hasher, token_service
from app.models.governance import AuditEvent, User, UserNotification
from app.models.master_lecturer import Lecturer
from app.schemas.auth import LoginRequest, MessageResponse, UserResponse

router = APIRouter()

GOOGLE_STATE_COOKIE = "google_oauth_state"
GOOGLE_STATE_TTL_MINUTES = 5
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _normalize_display_name(name: str | None, role: str) -> str | None:
    return repair_display_name(name, role)


def _public_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=_normalize_display_name(user.display_name, user.role),
        role=user.role,
        lecturer_id=user.lecturer_id,
        avatar_url=user.avatar_url,
    )


def _invalid_credentials() -> APIError:
    return APIError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email hoặc mật khẩu không đúng.",
        code="INVALID_CREDENTIALS",
    )


def _too_many_login_attempts(retry_after: int) -> APIError:
    minutes = max(1, math.ceil(retry_after / 60))
    return APIError(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau {minutes} phút.",
        code="TOO_MANY_LOGIN_ATTEMPTS",
        headers={"Retry-After": str(retry_after)},
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

    # Checked before the database and the password hash, so a guessing run costs almost nothing.
    retry_after = login_throttle.retry_after(email)
    if retry_after:
        raise _too_many_login_attempts(retry_after)

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
        # Counted like a wrong password so the limit does not reveal which emails exist.
        login_throttle.record_failure(email)
        raise _invalid_credentials()

    if not password_hasher.verify(login_data.password, user.password_hash):
        login_throttle.record_failure(email)
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

    login_throttle.clear(email)

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
    set_access_token_cookie(response, token)
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


def _google_not_configured() -> APIError:
    return APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Đăng nhập bằng Google chưa được cấu hình trên máy chủ.",
        code="GOOGLE_OAUTH_NOT_CONFIGURED",
    )


def _resolve_oauth_origin(request: Request) -> str | None:
    """Pick the caller's front-end origin, validated against the allow-list.

    The browser reaches this endpoint through the SPA's own proxy (same origin as the
    login page), so the reverse proxy never forwards the original Host to this process.
    The front end passes its own ``window.location.origin`` as the ``origin`` query
    param; ``Referer`` is kept as a fallback for callers that omit it (browsers that
    strip Referer by policy, or a bookmarked/typed link to this endpoint). Either way
    the candidate is only trusted once it matches ``GOOGLE_OAUTH_ALLOWED_ORIGINS``
    exactly, so this never becomes an open redirect.
    """
    allowed = settings.google_oauth_allowed_origins_list

    candidate = request.query_params.get("origin")
    if candidate and candidate.rstrip("/") in allowed:
        return candidate.rstrip("/")

    referer = request.headers.get("referer")
    if referer:
        try:
            parts = urlsplit(referer)
            origin = f"{parts.scheme}://{parts.netloc}"
        except ValueError:
            origin = None
        if origin and origin in allowed:
            return origin

    return None


def _set_google_state_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=GOOGLE_STATE_COOKIE,
        value=token,
        max_age=GOOGLE_STATE_TTL_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=settings.environment.lower() == "prod",
        path="/api/v1/auth/google",
    )


def _clear_google_state_cookie(response: Response) -> None:
    response.delete_cookie(
        key=GOOGLE_STATE_COOKIE,
        path="/api/v1/auth/google",
        httponly=True,
        samesite="lax",
        secure=settings.environment.lower() == "prod",
    )


@router.get("/google/login", summary="Start Google Sign-In")
def google_login(request: Request) -> RedirectResponse:
    """Redirect the browser to Google's consent screen (authorization code flow)."""

    if not settings.google_client_id or not settings.google_client_secret:
        raise _google_not_configured()

    origin = _resolve_oauth_origin(request)
    if origin is None:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không xác định được nguồn gốc yêu cầu đăng nhập Google.",
            code="GOOGLE_OAUTH_ORIGIN_NOT_ALLOWED",
        )

    nonce = secrets.token_urlsafe(24)
    state_token = token_service.create_access_token(
        data={"purpose": "google_oauth", "nonce": nonce, "origin": origin},
        expires_delta=timedelta(minutes=GOOGLE_STATE_TTL_MINUTES),
    )

    redirect_uri = f"{origin}/api/v1/auth/google/callback"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": nonce,
        "access_type": "online",
        "prompt": "select_account",
    }
    redirect = RedirectResponse(
        f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}", status_code=status.HTTP_302_FOUND
    )
    _set_google_state_cookie(redirect, state_token)
    return redirect


def _google_error_redirect(code: str) -> RedirectResponse:
    # Relative URL: resolved by the browser against this same origin, so no
    # need to re-derive the front-end origin for this leg of the flow.
    redirect = RedirectResponse(f"/login?google_error={code}", status_code=status.HTTP_302_FOUND)
    _clear_google_state_cookie(redirect)
    return redirect


def _find_or_create_google_user(
    db: Session, email: str, avatar_url: str | None
) -> tuple[User | None, str | None]:
    """Look up the user by email, or provision one for an existing LECTURER record.

    Google login never creates a brand-new identity on its own — ICTU has both students
    and lecturers on the same @ictu.edu.vn domain, and only lecturers already present in
    the (ADMIN-imported) ``lecturers`` table may sign in this way. So the only two ways
    in are: (1) an email that already has a ``User`` row (password-based or a prior
    Google login), or (2) an email that matches exactly one not-yet-linked ``Lecturer``
    row, which provisions the login on the spot. Anything else — a student's email, or
    any other @ictu.edu.vn address with no matching lecturer record — is rejected.

    ``avatar_url`` (Google's "picture" claim) is refreshed on the matched/created user
    on every successful login — it only ever reflects the most recent Google login, and
    only Google Sign-In ever writes it; a password-only account's is always None.

    Runs off the event loop (see ``run_in_threadpool`` at the call site) since the
    session here is a synchronous SQLAlchemy ``Session``, not an async one.

    Returns ``(user, None)`` on success, or ``(None, error_code)`` on rejection/failure.
    """
    user = db.query(User).filter(func.lower(User.email) == func.lower(email)).first()
    if user is not None:
        changed = False
        if avatar_url and user.avatar_url != avatar_url:
            user.avatar_url = avatar_url
            changed = True
        if not user.google_linked:
            user.google_linked = True
            changed = True
        if changed:
            db.commit()
            db.refresh(user)
        return user, None

    linked_lecturer_ids = {
        row[0]
        for row in db.query(User.lecturer_id).filter(User.lecturer_id.is_not(None)).all()
    }
    candidate_lecturers = (
        db.query(Lecturer).filter(func.lower(Lecturer.email) == func.lower(email)).all()
    )
    eligible_lecturers = [
        lecturer for lecturer in candidate_lecturers if lecturer.id not in linked_lecturer_ids
    ]
    if len(eligible_lecturers) != 1:
        # No lecturer record for this email (student, or anyone outside the imported
        # dataset), or an unresolvable ambiguity (several lecturers share the email) —
        # either way, provisioning an account here would be a guess. Refuse instead.
        return None, "not_lecturer"
    lecturer = eligible_lecturers[0]

    try:
        user = User(
            email=email,
            password_hash=password_hasher.hash(secrets.token_urlsafe(32)),
            display_name=_normalize_display_name(lecturer.full_name, "LECTURER"),
            role="LECTURER",
            lecturer_id=lecturer.id,
            avatar_url=avatar_url,
            has_password=False,
            google_linked=True,
        )
        db.add(user)
        db.flush()
        db.add(AuditEvent(
            entity_type="user",
            entity_id=user.id,
            action="USER_PROVISIONED_GOOGLE",
            actor_type="SYSTEM",
            actor_service="google_oauth",
            after_state={
                "email": email,
                "role": "LECTURER",
                "lecturer_id": str(lecturer.id),
            },
        ))
        db.commit()
        db.refresh(user)
        return user, None
    except IntegrityError:
        db.rollback()
        # Lost a create race to a concurrent login — the row now exists; fetch and return it.
        user = db.query(User).filter(func.lower(User.email) == func.lower(email)).first()
        return (user, None) if user is not None else (None, "conflict")


@router.get("/google/callback", summary="Google Sign-In callback")
async def google_callback(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
) -> RedirectResponse:
    """Exchange the authorization code, verify identity, and issue a session cookie."""

    if not settings.google_client_id or not settings.google_client_secret:
        raise _google_not_configured()

    state_cookie = request.cookies.get(GOOGLE_STATE_COOKIE)
    state_param = request.query_params.get("state")
    payload = token_service.verify_access_token(state_cookie) if state_cookie else None
    if (
        not payload
        or payload.get("purpose") != "google_oauth"
        or not state_param
        or payload.get("nonce") != state_param
    ):
        return _google_error_redirect("state")

    origin = payload.get("origin")
    if not isinstance(origin, str) or origin not in settings.google_oauth_allowed_origins_list:
        return _google_error_redirect("state")

    if request.query_params.get("error"):
        return _google_error_redirect("denied")

    code = request.query_params.get("code")
    if not code:
        return _google_error_redirect("missing_code")

    redirect_uri = f"{origin}/api/v1/auth/google/callback"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                return _google_error_redirect("token_exchange")
            access_token = (token_resp.json() or {}).get("access_token")
            if not access_token:
                return _google_error_redirect("token_exchange")

            userinfo_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_resp.status_code != 200:
                return _google_error_redirect("userinfo")
            userinfo = userinfo_resp.json() or {}
    except httpx.HTTPError:
        return _google_error_redirect("network")

    email = (userinfo.get("email") or "").strip()
    email_verified = userinfo.get("email_verified")
    if not email or email_verified not in (True, "true"):
        return _google_error_redirect("email_unverified")

    allowed_domain = settings.google_allowed_email_domain.strip().lower().lstrip("@")
    if allowed_domain and not email.lower().endswith(f"@{allowed_domain}"):
        return _google_error_redirect("domain")

    picture = (userinfo.get("picture") or "").strip()
    avatar_url = picture if picture.startswith(("http://", "https://")) else None

    try:
        user, error_code = await run_in_threadpool(
            _find_or_create_google_user, db, email, avatar_url
        )
    except SQLAlchemyError:
        return _google_error_redirect("database")
    if user is None:
        return _google_error_redirect(error_code or "conflict")

    if not user.is_active:
        return _google_error_redirect("locked")

    token = token_service.create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "av": int(user.auth_version or 1),
        }
    )
    redirect = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    _clear_google_state_cookie(redirect)
    set_access_token_cookie(redirect, token)
    return redirect


__all__ = ["get_current_user", "router"]
