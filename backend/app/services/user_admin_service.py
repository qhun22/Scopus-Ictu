"""Atomic administrator mutations for versioned user accounts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.core.security import password_hasher
from app.models.governance import AuditEvent, User, UserNotification
from app.models.master_lecturer import Lecturer
from app.schemas.user import UserAdminResponse, UserAdminUpdate


PROFILE_NOTIFICATION = (
    "Thông tin tài khoản đã được cập nhật",
    "Quản trị viên vừa cập nhật thông tin tài khoản của bạn.",
)
ROLE_NOTIFICATION = (
    "Quyền tài khoản đã thay đổi",
    "Quản trị viên vừa cập nhật vai trò của tài khoản.",
)
LOCK_NOTIFICATION = (
    "Tài khoản đã bị khóa",
    "Tài khoản của bạn đã bị quản trị viên khóa. Vui lòng liên hệ quản trị viên để được hỗ trợ.",
)
UNLOCK_NOTIFICATION = (
    "Tài khoản đã được mở khóa",
    "Quản trị viên đã mở khóa tài khoản của bạn.",
)
PASSWORD_RESET_NOTIFICATION = (
    "Mật khẩu đã được thay đổi",
    "Quản trị viên đã cập nhật mật khẩu tài khoản của bạn. "
    "Vui lòng liên hệ quản trị viên để nhận thông tin đăng nhập mới.",
)

LECTURER_FIELDS = (
    "staff_code",
    "academic_rank",
    "academic_degree",
    "position",
    "department",
    "faculty",
    "orcid",
)


def get_user_and_lecturer(
    db: Session, user_id: uuid.UUID
) -> tuple[User, Lecturer | None]:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản người dùng.",
            code="USER_NOT_FOUND",
        )
    lecturer = None
    if user.lecturer_id is not None:
        lecturer = db.query(Lecturer).filter(Lecturer.id == user.lecturer_id).first()
    return user, lecturer


def ensure_expected_version(user: User, expected_version: int) -> None:
    if user.version != expected_version:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dữ liệu người dùng đã thay đổi. Vui lòng tải lại.",
            code="VERSION_CONFLICT",
        )


def to_admin_response(user: User, lecturer: Lecturer | None) -> UserAdminResponse:
    return UserAdminResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        lecturer_id=user.lecturer_id,
        staff_code=lecturer.staff_code if lecturer else None,
        academic_rank=lecturer.academic_rank if lecturer else None,
        academic_degree=lecturer.academic_degree if lecturer else None,
        position=lecturer.position if lecturer else None,
        department=lecturer.department if lecturer else None,
        faculty=lecturer.faculty if lecturer else None,
        orcid=lecturer.orcid if lecturer else None,
        is_active=user.is_active,
        version=user.version,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _safe_snapshot(user: User, lecturer: Lecturer | None) -> dict[str, object]:
    return {
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "lecturer_id": str(user.lecturer_id) if user.lecturer_id else None,
        "is_active": user.is_active,
        **{
            field: getattr(lecturer, field) if lecturer is not None else None
            for field in LECTURER_FIELDS
        },
    }


def _add_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_type: str,
    title: str,
    message: str,
    metadata: dict | None = None,
) -> None:
    db.add(
        UserNotification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            notification_metadata=metadata or {},
            is_read=False,
        )
    )


def _add_audit(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
    action: str,
    before_state: dict | None,
    after_state: dict | None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            entity_type="users",
            entity_id=target_user_id,
            action=action,
            actor_type="USER",
            actor_user_id=actor_user_id,
            actor_service=None,
            before_state=before_state,
            after_state=after_state,
            event_metadata=metadata or {},
        )
    )


def _clean_nullable(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def update_user(
    db: Session,
    *,
    user: User,
    lecturer: Lecturer | None,
    payload: UserAdminUpdate,
    actor: User,
) -> bool:
    """Apply a profile/role update and append notifications/audits in one unit."""

    ensure_expected_version(user, payload.version)
    fields = payload.model_fields_set - {"version"}
    if not fields:
        return False

    before = _safe_snapshot(user, lecturer)
    changed_profile_fields: list[str] = []
    role_changed = False

    if "email" in fields:
        if payload.email is None or not payload.email.strip():
            raise APIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Email không được để trống.",
                code="INVALID_USER_UPDATE",
            )
        email = payload.email.strip()
        duplicate = (
            db.query(User)
            .filter(func.lower(User.email) == email.lower(), User.id != user.id)
            .first()
        )
        if duplicate is not None:
            raise APIError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email đã được sử dụng bởi tài khoản khác.",
                code="EMAIL_ALREADY_EXISTS",
            )
        if user.email != email:
            user.email = email
            if lecturer is not None:
                lecturer.email = email
            changed_profile_fields.append("email")

    if "display_name" in fields:
        if payload.display_name is None or not payload.display_name.strip():
            raise APIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Họ và tên không được để trống.",
                code="INVALID_USER_UPDATE",
            )
        display_name = " ".join(payload.display_name.split())
        if user.display_name != display_name:
            user.display_name = display_name
            if lecturer is not None:
                lecturer.full_name = display_name
                lecturer.full_name_normalized = display_name.casefold()
            changed_profile_fields.append("display_name")

    requested_lecturer_fields = fields.intersection(LECTURER_FIELDS)
    if requested_lecturer_fields and lecturer is None:
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tài khoản này không có hồ sơ giảng viên để cập nhật.",
            code="LECTURER_PROFILE_REQUIRED",
        )

    if lecturer is not None:
        for field in LECTURER_FIELDS:
            if field not in fields:
                continue
            value = _clean_nullable(getattr(payload, field))
            if field == "staff_code" and value is not None:
                duplicate_staff_code = (
                    db.query(Lecturer)
                    .filter(Lecturer.staff_code == value, Lecturer.id != lecturer.id)
                    .first()
                )
                if duplicate_staff_code is not None:
                    raise APIError(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Mã cán bộ đã được sử dụng.",
                        code="STAFF_CODE_ALREADY_EXISTS",
                    )
            if getattr(lecturer, field) != value:
                setattr(lecturer, field, value)
                changed_profile_fields.append(field)

    if "role" in fields:
        if payload.role is None:
            raise APIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vai trò không được để trống.",
                code="INVALID_USER_UPDATE",
            )
        if payload.role == "LECTURER" and user.lecturer_id is None:
            raise APIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vai trò LECTURER yêu cầu hồ sơ giảng viên.",
                code="LECTURER_PROFILE_REQUIRED",
            )
        if user.role != payload.role:
            user.role = payload.role
            role_changed = True

    if not changed_profile_fields and not role_changed:
        return False

    user.updated_at = datetime.now(timezone.utc)
    after = _safe_snapshot(user, lecturer)

    if changed_profile_fields:
        safe_fields = sorted(set(changed_profile_fields))
        _add_notification(
            db,
            user_id=user.id,
            notification_type="PROFILE_UPDATED",
            title=PROFILE_NOTIFICATION[0],
            message=PROFILE_NOTIFICATION[1],
            metadata={"changed_fields": safe_fields},
        )
        _add_audit(
            db,
            actor_user_id=actor.id,
            target_user_id=user.id,
            action="USER_UPDATED",
            before_state={field: before[field] for field in safe_fields},
            after_state={field: after[field] for field in safe_fields},
            metadata={"changed_fields": safe_fields},
        )

    if role_changed:
        _add_notification(
            db,
            user_id=user.id,
            notification_type="ROLE_CHANGED",
            title=ROLE_NOTIFICATION[0],
            message=ROLE_NOTIFICATION[1],
            metadata={"new_role": user.role},
        )
        _add_audit(
            db,
            actor_user_id=actor.id,
            target_user_id=user.id,
            action="USER_ROLE_CHANGED",
            before_state={"role": before["role"]},
            after_state={"role": user.role},
            metadata={"new_role": user.role},
        )
    return True


def lock_user(
    db: Session,
    *,
    user: User,
    expected_version: int,
    actor: User,
) -> bool:
    ensure_expected_version(user, expected_version)
    if user.id == actor.id:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể khóa tài khoản đang sử dụng.",
            code="CANNOT_LOCK_CURRENT_USER",
        )
    if not user.is_active:
        return False

    user.is_active = False
    user.auth_version = int(user.auth_version or 1) + 1
    user.updated_at = datetime.now(timezone.utc)
    _add_notification(
        db,
        user_id=user.id,
        notification_type="ACCOUNT_LOCKED",
        title=LOCK_NOTIFICATION[0],
        message=LOCK_NOTIFICATION[1],
    )
    _add_audit(
        db,
        actor_user_id=actor.id,
        target_user_id=user.id,
        action="USER_LOCKED",
        before_state={"is_active": True},
        after_state={"is_active": False},
    )
    return True


def unlock_user(
    db: Session,
    *,
    user: User,
    expected_version: int,
    actor: User,
) -> bool:
    ensure_expected_version(user, expected_version)
    if user.is_active:
        return False

    user.is_active = True
    now = datetime.now(timezone.utc)
    user.updated_at = now

    # Supersede/mark any unread ACCOUNT_LOCKED notifications for this user
    unread_lock_notifications = (
        db.query(UserNotification)
        .filter(
            UserNotification.user_id == user.id,
            UserNotification.notification_type == "ACCOUNT_LOCKED",
            UserNotification.is_read.is_(False),
        )
        .all()
    )
    for lock_notif in unread_lock_notifications:
        lock_notif.is_read = True
        lock_notif.read_at = now

    _add_notification(
        db,
        user_id=user.id,
        notification_type="ACCOUNT_UNLOCKED",
        title=UNLOCK_NOTIFICATION[0],
        message=UNLOCK_NOTIFICATION[1],
    )
    _add_audit(
        db,
        actor_user_id=actor.id,
        target_user_id=user.id,
        action="USER_UNLOCKED",
        before_state={"is_active": False},
        after_state={"is_active": True},
    )
    return True


def reset_user_password(
    db: Session,
    *,
    user: User,
    new_password: str,
    expected_version: int,
    actor: User,
) -> None:
    ensure_expected_version(user, expected_version)
    if user.id == actor.id:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể đặt lại mật khẩu quản trị viên đang sử dụng từ màn hình này.",
            code="CANNOT_RESET_CURRENT_USER",
        )

    new_hash = password_hasher.hash(new_password)
    user.password_hash = new_hash
    user.auth_version = int(user.auth_version or 1) + 1
    user.updated_at = datetime.now(timezone.utc)
    _add_notification(
        db,
        user_id=user.id,
        notification_type="PASSWORD_RESET",
        title=PASSWORD_RESET_NOTIFICATION[0],
        message=PASSWORD_RESET_NOTIFICATION[1],
    )
    _add_audit(
        db,
        actor_user_id=actor.id,
        target_user_id=user.id,
        action="USER_PASSWORD_RESET",
        before_state=None,
        after_state={"password_reset": True},
    )
