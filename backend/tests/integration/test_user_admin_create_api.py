"""Priority 3: ADMIN creates a LECTURER/REVIEWER account with zero lecturer
profiles in the database (no JSON import needed), isolated schema per test.

The endpoint must never accept role=ADMIN (so one ADMIN can never mint
another ADMIN through it), never accept a lecturer_id or Scopus Author ID,
and never leak the password/hash in its response or in the audit trail.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.core.security import password_hasher
from app.main import app
from app.models.base import Base
from app.models.governance import AuditEvent, User

NOW = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    if make_url(url).database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("never target an acceptance database")
    schema = f"test_t3_user_create_{uuid.uuid4().hex}"
    admin_engine = create_engine(url, future=True)
    with admin_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, future=True, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _user(role: str) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.lower()}-{uuid.uuid4().hex[:6]}@usercreate.test",
        password_hash="x",
        display_name=role,
        role=role,
        lecturer_id=None,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def as_role(db: Session):
    def _as(role: str) -> User:
        user = _user(role)
        db.add(user)
        db.commit()
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _as


def _payload(**overrides: object) -> dict:
    base = {
        "email": f"lecturer.b.{uuid.uuid4().hex[:8]}@ictu.edu.vn",
        "display_name": "Giảng viên B",
        "password": "MatKhauManh123!",
        "role": "LECTURER",
    }
    base.update(overrides)
    return base


def test_admin_creates_lecturer_account_with_no_lecturer_profile(client: TestClient, as_role, db: Session) -> None:
    as_role("ADMIN")
    body = _payload(role="LECTURER")

    resp = client.post("/api/v1/users", json=body)

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["role"] == "LECTURER"
    assert data["lecturer_id"] is None
    assert data["email"] == body["email"]
    assert "password" not in data
    assert "password_hash" not in data

    row = db.query(User).filter(User.email == body["email"]).one()
    assert row.lecturer_id is None
    assert row.role == "LECTURER"
    assert row.password_hash != body["password"]
    assert password_hasher.verify(body["password"], row.password_hash)


def test_admin_creates_reviewer_account(client: TestClient, as_role) -> None:
    as_role("ADMIN")
    resp = client.post("/api/v1/users", json=_payload(role="REVIEWER"))
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "REVIEWER"


def test_cannot_create_admin_role_through_this_endpoint(client: TestClient, as_role) -> None:
    as_role("ADMIN")
    resp = client.post("/api/v1/users", json=_payload(role="ADMIN"))
    assert resp.status_code == 422


def test_duplicate_email_case_insensitive_is_rejected(client: TestClient, as_role) -> None:
    as_role("ADMIN")
    email = f"dup.{uuid.uuid4().hex[:8]}@ictu.edu.vn"
    first = client.post("/api/v1/users", json=_payload(email=email))
    assert first.status_code == 201, first.text

    second = client.post("/api/v1/users", json=_payload(email=email.upper()))
    assert second.status_code == 409
    assert second.json()["code"] == "EMAIL_ALREADY_EXISTS"


def test_lecturer_cannot_create_accounts(client: TestClient, as_role) -> None:
    as_role("LECTURER")
    resp = client.post("/api/v1/users", json=_payload())
    assert resp.status_code == 403


def test_reviewer_cannot_create_accounts(client: TestClient, as_role) -> None:
    as_role("REVIEWER")
    resp = client.post("/api/v1/users", json=_payload())
    assert resp.status_code == 403


def test_password_too_short_rejected(client: TestClient, as_role) -> None:
    as_role("ADMIN")
    resp = client.post("/api/v1/users", json=_payload(password="short"))
    assert resp.status_code == 422


def test_blank_display_name_rejected(client: TestClient, as_role) -> None:
    as_role("ADMIN")
    resp = client.post("/api/v1/users", json=_payload(display_name="   "))
    assert resp.status_code == 422


def test_audit_event_created_without_leaking_password(client: TestClient, as_role, db: Session) -> None:
    admin = as_role("ADMIN")
    body = _payload()
    resp = client.post("/api/v1/users", json=body)
    assert resp.status_code == 201, resp.text
    user_id = uuid.UUID(resp.json()["id"])

    events = db.scalars(
        select(AuditEvent).where(AuditEvent.entity_type == "users", AuditEvent.entity_id == user_id)
    ).all()
    assert len(events) == 1
    event = events[0]
    assert event.action == "USER_CREATED"
    assert event.actor_user_id == admin.id
    dumped = str(event.after_state)
    assert body["password"] not in dumped
    assert "password" not in event.after_state
    assert "password_hash" not in event.after_state


def test_cannot_set_lecturer_id_through_create_payload(client: TestClient, as_role) -> None:
    as_role("ADMIN")
    fake_lecturer_id = str(uuid.uuid4())
    resp = client.post("/api/v1/users", json={**_payload(), "lecturer_id": fake_lecturer_id})
    # extra="forbid" on the request model must reject unknown fields outright.
    assert resp.status_code == 422


def test_anonymous_cannot_create_accounts(client: TestClient) -> None:
    resp = client.post("/api/v1/users", json=_payload())
    assert resp.status_code == 401
