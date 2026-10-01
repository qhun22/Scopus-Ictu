"""Integration tests for auth flow endpoints (M2.2).

Tests:
4. login success ADMIN
5. login success LECTURER
6. unknown email -> 401
7. wrong password -> 401
8. inactive user -> 403
9. authenticated /me -> 200
10. anonymous /me -> 401
11. logout clears auth
12. /me after logout -> 401
13. password_hash never appears in responses
14. email login case-insensitive
15. authentication cookie has expected security attributes
"""

from __future__ import annotations

import uuid
from typing import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_session
from app.core.security import password_hasher
from app.main import app
from app.models.governance import User


class MockUserQuery:
    def __init__(self, users: list[User]) -> None:
        self._users = users

    def filter(self, *criterion) -> MockUserQuery:
        # In mock tests, criterion execution or simple evaluation is handled
        return self

    def first(self) -> User | None:
        if self._users:
            return self._users[0]
        return None


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    return db


@pytest.fixture
def client(mock_db: MagicMock) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: mock_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_login_success_admin(client: TestClient, mock_db: MagicMock) -> None:
    admin_id = uuid.uuid4()
    admin_user = User(
        id=admin_id,
        email="admin@gmail.com",
        password_hash=password_hasher.hash("AdminSecret123"),
        display_name="Quản trị viên",
        role="ADMIN",
        lecturer_id=None,
        is_active=True,
    )
    mock_db.query.return_value.filter.return_value.first.return_value = admin_user

    # 4. login success ADMIN & 14. case-insensitive email
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "  ADMIN@GMAIL.COM  ", "password": "AdminSecret123"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(admin_id)
    assert data["email"] == "admin@gmail.com"
    assert data["display_name"] == "Quản trị viên"
    assert data["role"] == "ADMIN"
    assert data["lecturer_id"] is None

    # 13. password_hash never appears in responses
    assert "password_hash" not in data
    assert "password" not in data

    # 15. authentication cookie has expected security attributes
    assert "access_token" in response.cookies
    cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie_header
    assert "Path=/" in cookie_header


def test_login_success_lecturer(client: TestClient, mock_db: MagicMock) -> None:
    lecturer_user_id = uuid.uuid4()
    lecturer_profile_id = uuid.uuid4()
    lecturer_user = User(
        id=lecturer_user_id,
        email="user@gmail.com",
        password_hash=password_hasher.hash("UserSecret123"),
        display_name="Người dùng",
        role="LECTURER",
        lecturer_id=lecturer_profile_id,
        is_active=True,
    )
    mock_db.query.return_value.filter.return_value.first.return_value = lecturer_user

    # 5. login success LECTURER
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@gmail.com", "password": "UserSecret123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "LECTURER"
    assert data["lecturer_id"] == str(lecturer_profile_id)


def test_login_unknown_email(client: TestClient, mock_db: MagicMock) -> None:
    # 6. unknown email -> 401
    mock_db.query.return_value.filter.return_value.first.return_value = None

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@gmail.com", "password": "AnyPassword"},
    )
    assert response.status_code == 401
    assert "Email hoặc mật khẩu không chính xác" in response.json()["detail"]


def test_login_wrong_password(client: TestClient, mock_db: MagicMock) -> None:
    # 7. wrong password -> 401
    user = User(
        id=uuid.uuid4(),
        email="admin@gmail.com",
        password_hash=password_hasher.hash("CorrectPassword"),
        display_name="Quản trị viên",
        role="ADMIN",
        is_active=True,
    )
    mock_db.query.return_value.filter.return_value.first.return_value = user

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@gmail.com", "password": "WrongPassword"},
    )
    assert response.status_code == 401
    assert "Email hoặc mật khẩu không chính xác" in response.json()["detail"]


def test_login_inactive_user(client: TestClient, mock_db: MagicMock) -> None:
    # 8. inactive user -> 403
    user = User(
        id=uuid.uuid4(),
        email="inactive@gmail.com",
        password_hash=password_hasher.hash("ValidPassword"),
        display_name="Inactive User",
        role="LECTURER",
        lecturer_id=uuid.uuid4(),
        is_active=False,
    )
    mock_db.query.return_value.filter.return_value.first.return_value = user

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@gmail.com", "password": "ValidPassword"},
    )
    assert response.status_code == 403
    assert "vô hiệu hóa" in response.json()["detail"]


def test_me_and_logout_flow(client: TestClient, mock_db: MagicMock) -> None:
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="admin@gmail.com",
        password_hash=password_hasher.hash("Secret123"),
        display_name="Quản trị viên",
        role="ADMIN",
        lecturer_id=None,
        is_active=True,
    )
    mock_db.query.return_value.filter.return_value.first.return_value = user

    # 10. anonymous /me -> 401
    anon_response = client.get("/api/v1/auth/me")
    assert anon_response.status_code == 401

    # Login to get cookie
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@gmail.com", "password": "Secret123"},
    )
    assert login_response.status_code == 200

    # 9. authenticated /me -> 200
    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "admin@gmail.com"
    assert "password_hash" not in me_response.json()

    # 11. logout clears auth
    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200

    # 12. /me after logout -> 401
    post_logout_me = client.get("/api/v1/auth/me")
    assert post_logout_me.status_code == 401
