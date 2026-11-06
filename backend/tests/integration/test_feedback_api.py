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


def test_reporter_can_list_own_reports_and_see_comment_count(client, as_role) -> None:
    lecturer = as_role("LECTURER")
    created = client.post(
        "/api/v1/feedback/reports",
        json={"category": "OTHER", "message": "Thiếu dữ liệu đơn vị."},
    )
    report_id = created.json()["id"]

    mine = client.get("/api/v1/feedback/reports/mine")
    assert mine.status_code == 200
    body = mine.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == report_id
    assert body["items"][0]["comment_count"] == 0

    admin = as_role("ADMIN")
    reply = client.post(
        f"/api/v1/feedback/reports/{report_id}/comments",
        json={"message": "Bạn cho mình xin mã EID của công bố được không?"},
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["is_staff_author"] is True
    assert reply.json()["author_name"] == admin.display_name

    app.dependency_overrides[get_current_user] = lambda: lecturer
    mine_again = client.get("/api/v1/feedback/reports/mine")
    assert mine_again.json()["items"][0]["comment_count"] == 1


def test_reporter_can_reply_on_own_thread_but_not_others(client, as_role, db_session) -> None:
    as_role("LECTURER")
    created = client.post(
        "/api/v1/feedback/reports", json={"category": "OTHER", "message": "x"}
    )
    report_id = created.json()["id"]

    own_reply = client.post(
        f"/api/v1/feedback/reports/{report_id}/comments",
        json={"message": "Bổ sung: EID là 2-s2.0-105036738437."},
    )
    assert own_reply.status_code == 201, own_reply.text

    thread = client.get(f"/api/v1/feedback/reports/{report_id}/comments")
    assert thread.status_code == 200
    assert len(thread.json()["items"]) == 1
    assert thread.json()["items"][0]["is_staff_author"] is False

    other_lecturer = _user("LECTURER")
    db_session.add(other_lecturer)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: other_lecturer
    forbidden = client.get(f"/api/v1/feedback/reports/{report_id}/comments")
    assert forbidden.status_code == 403
    forbidden_reply = client.post(
        f"/api/v1/feedback/reports/{report_id}/comments", json={"message": "x"}
    )
    assert forbidden_reply.status_code == 403


def test_staff_can_view_and_reply_on_any_report(client, as_role) -> None:
    as_role("LECTURER")
    created = client.post(
        "/api/v1/feedback/reports", json={"category": "OTHER", "message": "x"}
    )
    report_id = created.json()["id"]

    reviewer = as_role("REVIEWER")
    detail = client.get(f"/api/v1/feedback/reports/{report_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == report_id

    reply = client.post(
        f"/api/v1/feedback/reports/{report_id}/comments",
        json={"message": "Đã kiểm tra, sẽ cập nhật đơn vị."},
    )
    assert reply.status_code == 201
    assert reply.json()["author_name"] == reviewer.display_name


def test_unread_flows_for_reporter_and_staff(client, as_role) -> None:
    lecturer = as_role("LECTURER")
    assert client.get("/api/v1/feedback/unread").json()["has_unread"] is False

    created = client.post(
        "/api/v1/feedback/reports", json={"category": "OTHER", "message": "x"}
    )
    report_id = created.json()["id"]
    # Filing your own report never counts as "unread" for you.
    assert client.get("/api/v1/feedback/unread").json()["has_unread"] is False

    admin = as_role("ADMIN")
    # A brand-new report is unread for staff until they mark it seen.
    assert client.get("/api/v1/feedback/unread").json()["has_unread"] is True
    assert client.post("/api/v1/feedback/mark-seen").status_code == 204
    assert client.get("/api/v1/feedback/unread").json()["has_unread"] is False

    client.post(
        f"/api/v1/feedback/reports/{report_id}/comments",
        json={"message": "Bạn cho mình thêm thông tin được không?"},
    )
    # Staff's own reply does not mark themselves unread.
    assert client.get("/api/v1/feedback/unread").json()["has_unread"] is False

    app.dependency_overrides[get_current_user] = lambda: lecturer
    # The reporter now has an unread staff reply.
    assert client.get("/api/v1/feedback/unread").json()["has_unread"] is True
    client.post(
        f"/api/v1/feedback/reports/{report_id}/comments",
        json={"message": "Mã EID là 2-s2.0-105036738437."},
    )
    assert client.post("/api/v1/feedback/mark-seen").status_code == 204
    assert client.get("/api/v1/feedback/unread").json()["has_unread"] is False

    app.dependency_overrides[get_current_user] = lambda: admin
    # Staff now has an unread reply from the (non-staff) reporter.
    assert client.get("/api/v1/feedback/unread").json()["has_unread"] is True


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
