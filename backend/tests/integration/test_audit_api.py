"""Integration contract tests for the C2-A1 audit read API."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.base import Base
from app.models.governance import AuditEvent, User

AUDIT_URL = "/api/v1/audits"


# ---------------------------------------------------------------------------
# Schema / session / client / auth fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for C2-A1 integration tests")
    database = make_url(url).database
    if database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("C2-A1 tests must never target an acceptance database")

    schema = f"test_c2_a1_audit_api_{uuid.uuid4().hex}"
    admin_engine = create_engine(url, pool_pre_ping=True, future=True)
    with admin_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def authenticate(db_session: Session):
    def _auth(role: str) -> User:
        u = User(
            id=uuid.uuid4(),
            email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@a1.test",
            password_hash="x",
            display_name=f"{role} User",
            role=role,
            is_active=True,
        )
        db_session.add(u)
        db_session.flush()
        return u

    return _auth


@pytest.fixture
def admin_client(db_session: Session, client: TestClient, authenticate):
    admin = authenticate("ADMIN")

    def _override():
        return admin

    app.dependency_overrides[get_current_user] = _override
    yield client, admin
    app.dependency_overrides.pop(get_current_user, None)


def _make_user_event(
    session: Session,
    actor: User,
    entity_type: str = "publication",
    action: str = "PUBLISHED",
    reason: str | None = None,
    created_at: datetime | None = None,
) -> AuditEvent:
    ev = AuditEvent(
        id=uuid.uuid4(),
        entity_type=entity_type,
        entity_id=uuid.uuid4(),
        action=action,
        actor_type="USER",
        actor_user_id=actor.id,
        actor_service=None,
        reason=reason,
    )
    if created_at is not None:
        ev.created_at = created_at
    session.add(ev)
    session.flush()
    return ev


def _make_system_event(
    session: Session,
    entity_type: str = "scopus_import",
    action: str = "IMPORT_STARTED",
    created_at: datetime | None = None,
) -> AuditEvent:
    ev = AuditEvent(
        id=uuid.uuid4(),
        entity_type=entity_type,
        entity_id=uuid.uuid4(),
        action=action,
        actor_type="SYSTEM",
        actor_user_id=None,
        actor_service="scopus-importer",
        reason=None,
    )
    if created_at is not None:
        ev.created_at = created_at
    session.add(ev)
    session.flush()
    return ev


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthEnforcement:
    def test_unauthenticated_returns_401(self, client: TestClient):
        resp = client.get(AUDIT_URL)
        assert resp.status_code == 401

    def test_reviewer_returns_403(
        self, db_session: Session, client: TestClient, authenticate
    ):
        reviewer = authenticate("REVIEWER")
        app.dependency_overrides[get_current_user] = lambda: reviewer
        try:
            resp = client.get(AUDIT_URL)
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_lecturer_returns_403(
        self, db_session: Session, client: TestClient, authenticate
    ):
        # LECTURER role requires lecturer_id — use REVIEWER trick with role override
        user = User(
            id=uuid.uuid4(),
            email=f"lec-{uuid.uuid4().hex[:8]}@a1.test",
            password_hash="x",
            display_name="Lecturer User",
            role="REVIEWER",
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()
        # Manually override role in-memory to simulate LECTURER without FK constraint
        user.role = "LECTURER"
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            resp = client.get(AUDIT_URL)
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestEmptyResult:
    def test_empty_list(self, admin_client):
        client, _ = admin_client
        resp = client.get(AUDIT_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1
        assert body["page_size"] == 50


class TestSafeDTO:
    def test_response_fields_safe(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        _make_user_event(db_session, admin, reason="test reason")

        resp = client.get(AUDIT_URL)
        assert resp.status_code == 200
        item = resp.json()["items"][0]

        # Safe fields present
        assert "id" in item
        assert "entity_type" in item
        assert "action" in item
        assert "actor_type" in item
        assert "actor_display_name" in item
        assert "actor_service" in item
        assert "reason" in item
        assert "created_at" in item

        # Sensitive fields absent
        for forbidden in (
            "entity_id",
            "actor_user_id",
            "before_state",
            "after_state",
            "event_metadata",
            "metadata",
            "ip_address",
            "user_agent",
            "request_id",
            "correlation_id",
        ):
            assert forbidden not in item, f"Sensitive field '{forbidden}' leaked in DTO"

    def test_user_actor_display_name_populated(
        self, db_session: Session, admin_client, authenticate
    ):
        client, admin = admin_client
        _make_user_event(db_session, admin)

        resp = client.get(AUDIT_URL)
        item = resp.json()["items"][0]
        assert item["actor_display_name"] == admin.display_name
        assert item["actor_service"] is None
        assert item["actor_type"] == "USER"

    def test_system_actor_service_populated(self, db_session: Session, admin_client):
        client, _ = admin_client
        _make_system_event(db_session)

        resp = client.get(AUDIT_URL)
        item = resp.json()["items"][0]
        assert item["actor_service"] == "scopus-importer"
        assert item["actor_display_name"] is None
        assert item["actor_type"] == "SYSTEM"

    def test_reason_null_when_not_set(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        _make_user_event(db_session, admin, reason=None)

        resp = client.get(AUDIT_URL)
        item = resp.json()["items"][0]
        assert item["reason"] is None


class TestPagination:
    def test_default_page_size(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        for _ in range(3):
            _make_user_event(db_session, admin)

        resp = client.get(AUDIT_URL)
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert body["page"] == 1
        assert body["page_size"] == 50

    def test_custom_page_size(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        for _ in range(5):
            _make_user_event(db_session, admin)

        resp = client.get(AUDIT_URL, params={"page_size": 2})
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["page_size"] == 2

    def test_page_2(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        for _ in range(5):
            _make_user_event(db_session, admin)

        resp = client.get(AUDIT_URL, params={"page": 2, "page_size": 3})
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["page"] == 2

    def test_page_size_capped_at_100(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        resp = client.get(AUDIT_URL, params={"page_size": 200})
        # page_size > 100 should be rejected by FastAPI Query validation
        assert resp.status_code == 422

    def test_ordering_created_at_desc(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        now = datetime.now(UTC)
        ev1 = _make_user_event(
            db_session, admin, action="PUBLISHED", created_at=now - timedelta(minutes=2)
        )
        ev2 = _make_user_event(
            db_session, admin, action="REVOKED", created_at=now - timedelta(minutes=1)
        )
        ev3 = _make_user_event(
            db_session, admin, action="APPROVED", created_at=now
        )

        resp = client.get(AUDIT_URL)
        items = resp.json()["items"]
        assert items[0]["id"] == str(ev3.id)
        assert items[1]["id"] == str(ev2.id)
        assert items[2]["id"] == str(ev1.id)


class TestFilters:
    def test_filter_by_action(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        ev = _make_user_event(db_session, admin, action="PUBLISHED")
        _make_user_event(db_session, admin, action="REVOKED")

        resp = client.get(AUDIT_URL, params={"action": "PUBLISHED"})
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_by_entity_type(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        ev = _make_user_event(db_session, admin, entity_type="publication")
        _make_system_event(db_session, entity_type="scopus_import")

        resp = client.get(AUDIT_URL, params={"entity_type": "publication"})
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_by_actor_type_user(
        self, db_session: Session, admin_client, authenticate
    ):
        client, admin = admin_client
        ev = _make_user_event(db_session, admin)
        _make_system_event(db_session)

        resp = client.get(AUDIT_URL, params={"actor_type": "USER"})
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_by_actor_type_system(
        self, db_session: Session, admin_client, authenticate
    ):
        client, admin = admin_client
        _make_user_event(db_session, admin)
        ev = _make_system_event(db_session)

        resp = client.get(AUDIT_URL, params={"actor_type": "SYSTEM"})
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_actor_type_invalid(self, admin_client):
        client, _ = admin_client
        resp = client.get(AUDIT_URL, params={"actor_type": "INVALID"})
        assert resp.status_code == 422

    def test_filter_date_from(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        now = datetime.now(UTC)
        old = _make_user_event(
            db_session, admin, created_at=now - timedelta(days=2)
        )
        recent = _make_user_event(db_session, admin, created_at=now)

        cutoff = (now - timedelta(days=1)).isoformat()
        resp = client.get(AUDIT_URL, params={"date_from": cutoff})
        body = resp.json()
        ids = [i["id"] for i in body["items"]]
        assert str(recent.id) in ids
        assert str(old.id) not in ids

    def test_filter_date_to(self, db_session: Session, admin_client, authenticate):
        client, admin = admin_client
        now = datetime.now(UTC)
        old = _make_user_event(
            db_session, admin, created_at=now - timedelta(days=2)
        )
        recent = _make_user_event(db_session, admin, created_at=now)

        cutoff = (now - timedelta(days=1)).isoformat()
        resp = client.get(AUDIT_URL, params={"date_to": cutoff})
        body = resp.json()
        ids = [i["id"] for i in body["items"]]
        assert str(old.id) in ids
        assert str(recent.id) not in ids

    def test_date_range_inverted_returns_422(self, admin_client):
        client, _ = admin_client
        now = datetime.now(UTC)
        resp = client.get(
            AUDIT_URL,
            params={
                "date_from": now.isoformat(),
                "date_to": (now - timedelta(days=1)).isoformat(),
            },
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["code"] == "INVALID_DATE_RANGE"


class TestActorResolution:
    def test_actor_display_name_resolves_for_inactive_user(
        self, db_session: Session, admin_client, authenticate
    ):
        """Inactive users must still resolve display_name via LEFT JOIN."""
        client, _ = admin_client
        inactive = User(
            id=uuid.uuid4(),
            email=f"inactive-{uuid.uuid4().hex[:8]}@a1.test",
            password_hash="x",
            display_name="Inactive Person",
            role="REVIEWER",
            is_active=False,
        )
        db_session.add(inactive)
        db_session.flush()
        _make_user_event(db_session, inactive)

        resp = client.get(AUDIT_URL, params={"actor_type": "USER"})
        item = resp.json()["items"][0]
        assert item["actor_display_name"] == "Inactive Person"


class TestDBFailure:
    def test_db_failure_returns_503(self, admin_client):
        client, _ = admin_client

        from sqlalchemy.exc import OperationalError

        with patch(
            "app.api.v1.endpoints.audits.list_audits",
            side_effect=OperationalError("conn", None, Exception("db down")),
        ):
            resp = client.get(AUDIT_URL)

        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert detail["code"] == "DATABASE_UNAVAILABLE"

    def test_db_failure_does_not_create_audit_rows(
        self, db_session: Session, admin_client, authenticate
    ):
        """Reading audits must never write AuditEvent rows."""
        client, admin = admin_client
        _make_user_event(db_session, admin)

        before = db_session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(
                __import__("sqlalchemy", fromlist=["func"]).func.count()
            ).select_from(AuditEvent)
        ).scalar_one()

        client.get(AUDIT_URL)

        after = db_session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(
                __import__("sqlalchemy", fromlist=["func"]).func.count()
            ).select_from(AuditEvent)
        ).scalar_one()

        assert after == before


class TestNoPingEndpoint:
    def test_ping_endpoint_removed(self, admin_client):
        client, _ = admin_client
        resp = client.get(f"{AUDIT_URL}/ping")
        assert resp.status_code == 404
