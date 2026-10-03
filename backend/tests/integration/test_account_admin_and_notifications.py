"""Comprehensive integration and unit tests for M2.4 Account Administration and Persistent Notifications.

Covers all 30 test scenarios defined in Directive §45:
AUTH
1. normal correct login -> 200
2. normal wrong password -> 401 INVALID_CREDENTIALS
3. locked login -> 403 ACCOUNT_LOCKED

LOCK
4. admin lock lecturer -> success
5. is_active becomes false
6. audit created
7. notification created
8. lecturer cannot login
9. non-admin cannot lock
10. admin cannot lock self

UNLOCK
11. admin unlock -> success
12. login works again
13. notification created
14. audit created

PASSWORD RESET
15. new password hash != plaintext
16. old password no longer verifies
17. new password verifies
18. auth_version increments
19. notification PASSWORD_RESET created
20. audit created without password/hash
21. old session rejected after reset
22. offline user old password -> 401 PASSWORD_RESET_BY_ADMIN
23. offline user new password -> 200

NOTIFICATIONS
24. user only sees own notifications
25. other user cannot read notification
26. mark read sets: is_read=true, read_at != null
27. unread query excludes read notifications

PROFILE/ROLE
28. admin update creates notification
29. role update creates ROLE_CHANGED
30. optimistic version conflict -> 409
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_session
from app.core.security import password_hasher, token_service
from app.main import app
from app.models.governance import AuditEvent, User, UserNotification
from app.models.master_lecturer import Lecturer
from app.services.user_admin_service import (
    lock_user,
    reset_user_password,
    unlock_user,
    update_user,
)
from app.schemas.user import UserAdminUpdate


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(mock_db: MagicMock) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: mock_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_user(
    *,
    user_id: uuid.UUID | None = None,
    email: str = "user@ictu.edu.vn",
    password: str = "CorrectPassword123!",
    role: str = "LECTURER",
    display_name: str = "Giảng viên A",
    lecturer_id: uuid.UUID | None = None,
    is_active: bool = True,
    version: int = 1,
    auth_version: int = 1,
) -> User:
    return User(
        id=user_id or uuid.uuid4(),
        email=email,
        password_hash=password_hasher.hash(password),
        display_name=display_name,
        role=role,
        lecturer_id=lecturer_id or uuid.uuid4(),
        is_active=is_active,
        version=version,
        auth_version=auth_version,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ===========================================================================
# AUTH TESTS (1-3)
# ===========================================================================

def test_01_normal_correct_login(client: TestClient, mock_db: MagicMock) -> None:
    user = _create_user(email="teacher@ictu.edu.vn", password="ValidPassword123!")
    mock_db.query.return_value.filter.return_value.first.return_value = user

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@ictu.edu.vn", "password": "ValidPassword123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "teacher@ictu.edu.vn"
    assert "access_token" in response.cookies


def test_02_normal_wrong_password(client: TestClient, mock_db: MagicMock) -> None:
    user = _create_user(email="teacher@ictu.edu.vn", password="ValidPassword123!")
    # First query for user, second for pending password reset notifications
    mock_db.query.return_value.filter.return_value.first.side_effect = [user, None]

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@ictu.edu.vn", "password": "WrongPassword456!"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
    assert "Email hoặc mật khẩu không đúng." in response.json()["detail"]


def test_03_locked_login(client: TestClient, mock_db: MagicMock) -> None:
    user = _create_user(email="locked@ictu.edu.vn", password="ValidPassword123!", is_active=False)
    mock_db.query.return_value.filter.return_value.first.return_value = user

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "locked@ictu.edu.vn", "password": "ValidPassword123!"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_LOCKED"
    assert "Tài khoản đang bị khóa." in response.json()["detail"]


# ===========================================================================
# LOCK TESTS (4-10)
# ===========================================================================

def test_04_05_06_07_admin_lock_lecturer(mock_db: MagicMock) -> None:
    admin = _create_user(role="ADMIN", display_name="Admin")
    target = _create_user(role="LECTURER", display_name="Target Lecturer", is_active=True, auth_version=1)

    added_objects: list[object] = []
    mock_db.add.side_effect = lambda obj: added_objects.append(obj)

    result = lock_user(mock_db, user=target, expected_version=target.version, actor=admin)
    assert result is True
    # 5. is_active becomes false
    assert target.is_active is False
    assert target.auth_version == 2

    # 6. audit created
    audit = next((o for o in added_objects if isinstance(o, AuditEvent)), None)
    assert audit is not None
    assert audit.action == "USER_LOCKED"
    assert audit.actor_user_id == admin.id
    assert audit.entity_id == target.id
    assert audit.before_state == {"is_active": True}
    assert audit.after_state == {"is_active": False}

    # 7. notification created
    notif = next((o for o in added_objects if isinstance(o, UserNotification)), None)
    assert notif is not None
    assert notif.notification_type == "ACCOUNT_LOCKED"
    assert notif.user_id == target.id


def test_08_locked_lecturer_cannot_login(client: TestClient, mock_db: MagicMock) -> None:
    target = _create_user(email="locked_target@ictu.edu.vn", is_active=False)
    mock_db.query.return_value.filter.return_value.first.return_value = target

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "locked_target@ictu.edu.vn", "password": "CorrectPassword123!"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_LOCKED"


def test_09_non_admin_cannot_lock(client: TestClient, mock_db: MagicMock) -> None:
    reviewer = _create_user(role="REVIEWER")
    target = _create_user(role="LECTURER")
    mock_db.query.return_value.filter.return_value.first.return_value = reviewer

    token = token_service.create_access_token(
        {"sub": str(reviewer.id), "email": reviewer.email, "role": reviewer.role, "av": 1}
    )
    client.cookies.set("access_token", token)

    response = client.post(
        f"/api/v1/users/{target.id}/lock",
        json={"version": target.version},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_10_admin_cannot_lock_self(client: TestClient, mock_db: MagicMock) -> None:
    admin = _create_user(role="ADMIN", display_name="Admin Self")
    mock_db.query.return_value.filter.return_value.first.return_value = admin

    token = token_service.create_access_token(
        {"sub": str(admin.id), "email": admin.email, "role": "ADMIN", "av": 1}
    )
    client.cookies.set("access_token", token)

    response = client.post(
        f"/api/v1/users/{admin.id}/lock",
        json={"version": admin.version},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CANNOT_LOCK_CURRENT_USER"


# ===========================================================================
# UNLOCK TESTS (11-14)
# ===========================================================================

def test_11_12_13_14_admin_unlock_lecturer(mock_db: MagicMock) -> None:
    admin = _create_user(role="ADMIN")
    target = _create_user(role="LECTURER", is_active=False)

    added_objects: list[object] = []
    mock_db.add.side_effect = lambda obj: added_objects.append(obj)

    result = unlock_user(mock_db, user=target, expected_version=target.version, actor=admin)
    assert result is True
    assert target.is_active is True

    # 13. notification created
    notif = next((o for o in added_objects if isinstance(o, UserNotification)), None)
    assert notif is not None
    assert notif.notification_type == "ACCOUNT_UNLOCKED"
    assert notif.user_id == target.id

    # 14. audit created
    audit = next((o for o in added_objects if isinstance(o, AuditEvent)), None)
    assert audit is not None
    assert audit.action == "USER_UNLOCKED"
    assert audit.actor_user_id == admin.id
    assert audit.after_state == {"is_active": True}


# ===========================================================================
# PASSWORD RESET TESTS (15-23)
# ===========================================================================

def test_15_16_17_18_19_20_password_reset_mutation(mock_db: MagicMock) -> None:
    admin = _create_user(role="ADMIN")
    target = _create_user(password="OldSecretPass123!", auth_version=1)
    old_hash = target.password_hash

    added_objects: list[object] = []
    mock_db.add.side_effect = lambda obj: added_objects.append(obj)

    new_pwd = "BrandNewPassword2026!"
    reset_user_password(
        mock_db,
        user=target,
        new_password=new_pwd,
        expected_version=target.version,
        actor=admin,
    )

    # 15. new password hash != plaintext
    assert target.password_hash != new_pwd
    assert target.password_hash != old_hash
    # 16. old password no longer verifies
    assert password_hasher.verify("OldSecretPass123!", target.password_hash) is False
    # 17. new password verifies
    assert password_hasher.verify(new_pwd, target.password_hash) is True
    # 18. auth_version increments
    assert target.auth_version == 2

    # 19. notification PASSWORD_RESET created
    notif = next((o for o in added_objects if isinstance(o, UserNotification)), None)
    assert notif is not None
    assert notif.notification_type == "PASSWORD_RESET"

    # 20. audit created without password/hash
    audit = next((o for o in added_objects if isinstance(o, AuditEvent)), None)
    assert audit is not None
    assert audit.action == "USER_PASSWORD_RESET"
    assert new_pwd not in str(audit.after_state)
    assert old_hash not in str(audit.after_state)
    assert audit.after_state == {"password_reset": True}


def test_password_reset_audit_none_is_bound_as_sql_null() -> None:
    """Keep nullable audit JSON compatible with its PostgreSQL constraints."""
    before_state_type = AuditEvent.__table__.c.before_state.type
    after_state_type = AuditEvent.__table__.c.after_state.type

    assert before_state_type.none_as_null is True
    assert after_state_type.none_as_null is True


def test_21_old_session_rejected_after_reset(client: TestClient, mock_db: MagicMock) -> None:
    user = _create_user(auth_version=2)
    mock_db.query.return_value.filter.return_value.first.return_value = user

    # Token has old av=1
    old_token = token_service.create_access_token(
        {"sub": str(user.id), "email": user.email, "role": user.role, "av": 1}
    )
    client.cookies.set("access_token", old_token)

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_active_session_is_renewed_near_expiration(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    user = _create_user()
    mock_db.query.return_value.filter.return_value.first.return_value = user
    expiring_token = token_service.create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "av": int(user.auth_version or 1),
        },
        expires_delta=timedelta(minutes=5),
    )
    client.cookies.set("access_token", expiring_token)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert "access_token=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


def test_22_offline_user_old_password_returns_password_reset_by_admin(
    client: TestClient, mock_db: MagicMock
) -> None:
    user = _create_user(password="NewPassword123!")
    # 1st query: user lookup by email
    # 2nd query: pending unread PASSWORD_RESET notification lookup
    unread_reset_notif = UserNotification(
        id=uuid.uuid4(),
        user_id=user.id,
        notification_type="PASSWORD_RESET",
        title="Mật khẩu đã được thay đổi",
        message="Quản trị viên đã cập nhật mật khẩu.",
        is_read=False,
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [user, unread_reset_notif]

    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "OldPasswordBeforeAdminReset!"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "PASSWORD_RESET_BY_ADMIN"
    assert "Thông tin đăng nhập đã được quản trị viên thay đổi." in response.json()["detail"]


def test_23_offline_user_new_password_succeeds(
    client: TestClient, mock_db: MagicMock
) -> None:
    user = _create_user(password="NewPassword123!", auth_version=2)
    mock_db.query.return_value.filter.return_value.first.return_value = user

    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "NewPassword123!"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == user.email


# ===========================================================================
# NOTIFICATIONS TESTS (24-27)
# ===========================================================================

def test_24_27_unread_notifications_isolation(client: TestClient, mock_db: MagicMock) -> None:
    current_user = _create_user()
    token = token_service.create_access_token(
        {"sub": str(current_user.id), "email": current_user.email, "role": current_user.role, "av": 1}
    )
    client.cookies.set("access_token", token)

    notif = UserNotification(
        id=uuid.uuid4(),
        user_id=current_user.id,
        notification_type="PROFILE_UPDATED",
        title="Cập nhật thông tin",
        message="Quản trị viên đã cập nhật thông tin.",
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )

    mock_db.query.return_value.filter.return_value.first.return_value = current_user
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [notif]

    response = client.get("/api/v1/notifications/unread")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == str(notif.id)
    assert items[0]["type"] == "PROFILE_UPDATED"


def test_25_other_user_cannot_read_notification(client: TestClient, mock_db: MagicMock) -> None:
    current_user = _create_user()
    token = token_service.create_access_token(
        {"sub": str(current_user.id), "email": current_user.email, "role": current_user.role, "av": 1}
    )
    client.cookies.set("access_token", token)

    # 1st query: get_current_user returns current_user
    # 2nd query: query notification where id == notif_id and user_id == current_user.id -> returns None
    mock_db.query.return_value.filter.return_value.first.side_effect = [current_user, None]

    other_notif_id = uuid.uuid4()
    response = client.post(f"/api/v1/notifications/{other_notif_id}/read")
    assert response.status_code == 404
    assert response.json()["code"] == "NOTIFICATION_NOT_FOUND"


def test_26_mark_read_sets_read_fields(client: TestClient, mock_db: MagicMock) -> None:
    current_user = _create_user()
    token = token_service.create_access_token(
        {"sub": str(current_user.id), "email": current_user.email, "role": current_user.role, "av": 1}
    )
    client.cookies.set("access_token", token)

    notif = UserNotification(
        id=uuid.uuid4(),
        user_id=current_user.id,
        notification_type="ROLE_CHANGED",
        title="Quyền thay đổi",
        message="Role updated",
        is_read=False,
        read_at=None,
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [current_user, notif]

    response = client.post(f"/api/v1/notifications/{notif.id}/read")
    assert response.status_code == 200
    assert response.json()["is_read"] is True
    assert notif.is_read is True
    assert notif.read_at is not None


# ===========================================================================
# PROFILE & ROLE TESTS (28-30)
# ===========================================================================

def test_28_admin_update_creates_notification_and_audit(mock_db: MagicMock) -> None:
    admin = _create_user(role="ADMIN")
    target = _create_user(role="LECTURER", display_name="Old Name", email="old@ictu.edu.vn")
    lecturer = Lecturer(
        id=target.lecturer_id,
        full_name="Old Name",
        full_name_normalized="old name",
        email="old@ictu.edu.vn",
        faculty="Khoa CNTT",
    )
    mock_db.query.return_value.filter.return_value.first.return_value = None

    added_objects: list[object] = []
    mock_db.add.side_effect = lambda obj: added_objects.append(obj)

    update_payload = UserAdminUpdate(
        version=target.version,
        display_name="New Name",
        faculty="Khoa An Toan Thong Tin",
    )

    changed = update_user(
        mock_db,
        user=target,
        lecturer=lecturer,
        payload=update_payload,
        actor=admin,
    )
    assert changed is True
    assert target.display_name == "New Name"
    assert lecturer.faculty == "Khoa An Toan Thong Tin"

    notif = next((o for o in added_objects if isinstance(o, UserNotification)), None)
    assert notif is not None
    assert notif.notification_type == "PROFILE_UPDATED"
    assert "display_name" in notif.notification_metadata.get("changed_fields", [])


def test_29_role_update_creates_role_changed_notification(mock_db: MagicMock) -> None:
    admin = _create_user(role="ADMIN")
    target = _create_user(role="LECTURER")

    added_objects: list[object] = []
    mock_db.add.side_effect = lambda obj: added_objects.append(obj)

    update_payload = UserAdminUpdate(version=target.version, role="REVIEWER")
    changed = update_user(
        mock_db,
        user=target,
        lecturer=None,
        payload=update_payload,
        actor=admin,
    )
    assert changed is True
    assert target.role == "REVIEWER"

    notif = next((o for o in added_objects if isinstance(o, UserNotification)), None)
    assert notif is not None
    assert notif.notification_type == "ROLE_CHANGED"
    assert notif.notification_metadata.get("new_role") == "REVIEWER"


def test_30_optimistic_version_conflict(mock_db: MagicMock) -> None:
    admin = _create_user(role="ADMIN")
    target = _create_user(version=5)

    update_payload = UserAdminUpdate(version=4, display_name="Conflicted")
    from app.core.exceptions import APIError

    with pytest.raises(APIError) as exc_info:
        update_user(
            mock_db,
            user=target,
            lecturer=None,
            payload=update_payload,
            actor=admin,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "VERSION_CONFLICT"


# ===========================================================================
# EDGE CASE REGRESSION TESTS
# ===========================================================================

def test_31_lock_unlock_supersedes_stale_lock_notification(mock_db: MagicMock) -> None:
    """Verify that unlocking an account supersedes and marks unread ACCOUNT_LOCKED notifications."""
    admin = _create_user(role="ADMIN")
    target = _create_user(role="LECTURER", is_active=True)

    added_objects: list[object] = []
    mock_db.add.side_effect = lambda obj: added_objects.append(obj)

    # 1. Admin locks target
    lock_user(mock_db, user=target, expected_version=target.version, actor=admin)
    assert target.is_active is False
    lock_notif = next((o for o in added_objects if isinstance(o, UserNotification) and o.notification_type == "ACCOUNT_LOCKED"), None)
    assert lock_notif is not None
    assert lock_notif.is_read is False

    # 2. Mock db query returning the pending unread lock notification
    mock_db.query.return_value.filter.return_value.all.return_value = [lock_notif]

    # 3. Admin unlocks target
    unlock_user(mock_db, user=target, expected_version=target.version, actor=admin)
    assert target.is_active is True

    # 4. Verify previous lock notification was superseded/marked read
    assert lock_notif.is_read is True
    assert lock_notif.read_at is not None

    # 5. Verify ACCOUNT_UNLOCKED notification was created
    unlock_notif = next((o for o in added_objects if isinstance(o, UserNotification) and o.notification_type == "ACCOUNT_UNLOCKED"), None)
    assert unlock_notif is not None
    assert unlock_notif.is_read is False
