"""User feedback-report intake queue: file a report (any logged-in role),
list/resolve it (ADMIN/REVIEWER only). Filing or resolving never itself
touches publication, affiliation or identity data.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.base import Base
from app.models.governance import User

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    if make_url(url).database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("never target an acceptance database")
    schema = f"test_feedback_{uuid.uuid4().hex}"
    admin = create_engine(url, future=True)
    with admin.begin() as conn:
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
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _user(role: str) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.lower()}-{uuid.uuid4().hex[:6]}@feedback.test",
        password_hash="x",
        display_name=f"{role.title()} Test",
        role=role,
        lecturer_id=None,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def as_role(db_session: Session):
    def _as(role: str) -> User:
        user = _user(role)
        db_session.add(user)
        db_session.commit()
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _as


def test_anonymous_cannot_file_a_report(client) -> None:
    resp = client.post(
        "/api/v1/feedback/reports",
        json={"category": "WRONG_AFFILIATION", "message": "Sai đơn vị."},
    )
    assert resp.status_code == 401


@pytest.mark.parametrize("role", ["LECTURER", "REVIEWER", "ADMIN"])
def test_any_logged_in_role_can_file_a_report(client, as_role, role) -> None:
    as_role(role)
    resp = client.post(
        "/api/v1/feedback/reports",
        json={
            "category": "WRONG_AFFILIATION",
            "publication_eid": "2-s2.0-105036738437",
            "message": "Đơn vị hiển thị không đúng, đơn vị thật là ICTU.",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "OPEN"
    assert body["publication_eid"] == "2-s2.0-105036738437"
    assert body["resolved_at"] is None


def test_invalid_category_is_rejected(client, as_role) -> None:
    as_role("LECTURER")
    resp = client.post(
        "/api/v1/feedback/reports", json={"category": "NOT_A_REAL_CATEGORY", "message": "x"}
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_CATEGORY"


def test_lecturer_cannot_list_or_resolve_reports(client, as_role) -> None:
    as_role("LECTURER")
    assert client.get("/api/v1/feedback/reports").status_code == 403
    resp = client.post(
        f"/api/v1/feedback/reports/{uuid.uuid4()}/resolve", json={"status": "RESOLVED"}
    )
    assert resp.status_code == 403


def test_admin_lists_and_resolves_a_report(client, as_role) -> None:
    lecturer = as_role("LECTURER")
    created = client.post(
        "/api/v1/feedback/reports",
        json={"category": "WRONG_AUTHOR_LINK", "message": "Bài này không phải của tôi."},
    )
    report_id = created.json()["id"]

    admin = as_role("ADMIN")
    listed = client.get("/api/v1/feedback/reports")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["open_count"] == 1
    assert body["items"][0]["reporter_name"] == lecturer.display_name

    resolved = client.post(
        f"/api/v1/feedback/reports/{report_id}/resolve",
        json={"status": "RESOLVED", "admin_note": "Đã kiểm tra, đúng như báo cáo."},
    )
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["status"] == "RESOLVED"
    assert body["admin_note"] == "Đã kiểm tra, đúng như báo cáo."
    assert body["resolved_by_user_id"] == str(admin.id)
    assert body["resolved_at"] is not None

    again = client.get("/api/v1/feedback/reports", params={"status": "OPEN"})
    assert again.json()["total"] == 0


def test_resolving_an_already_closed_report_is_refused(client, as_role) -> None:
    as_role("LECTURER")
    created = client.post(
        "/api/v1/feedback/reports", json={"category": "OTHER", "message": "x"}
    )
    report_id = created.json()["id"]

    as_role("ADMIN")
    resolve_url = f"/api/v1/feedback/reports/{report_id}/resolve"
    first = client.post(resolve_url, json={"status": "DISMISSED"})
    assert first.status_code == 200

    second = client.post(resolve_url, json={"status": "RESOLVED"})
    assert second.status_code == 409
    assert second.json()["code"] == "REPORT_ALREADY_CLOSED"
