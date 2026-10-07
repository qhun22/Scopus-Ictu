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

_SAFE_DTO_KEYS = frozenset(
    {
        "id",
        "entity_type",
        "action",
        "actor_type",
        "actor_display_name",
        "actor_service",
        "reason",
        "created_at",
    }
)

_FORBIDDEN_KEYS = frozenset(
    {
        "password_hash",
        "auth_version",
        "entity_id",
        "actor_user_id",
        "before_state",
        "after_state",
        "event_metadata",
        "metadata",
        "request_id",
        "correlation_id",
        "ip_address",
        "user_agent",
    }
)


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
def make_user(db_session: Session):
    def _make(role: str = "ADMIN", is_active: bool = True) -> User:
        u = User(
            id=uuid.uuid4(),
            email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@a1.test",
            password_hash="x",
            display_name=f"{role} User",
            role=role,
            is_active=is_active,
        )
        db_session.add(u)
        db_session.flush()
        return u

    return _make


@pytest.fixture
def admin_client(db_session: Session, client: TestClient, make_user):
    admin = make_user("ADMIN")

    app.dependency_overrides[get_current_user] = lambda: admin
    yield client, admin
    app.dependency_overrides.pop(get_current_user, None)


def _user_event(
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


def _system_event(
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
# Auth enforcement
# ---------------------------------------------------------------------------


class TestAuthEnforcement:
    def test_unauthenticated_returns_401(self, client: TestClient):
        resp = client.get(AUDIT_URL)
        assert resp.status_code == 401

    def test_reviewer_returns_403(self, db_session: Session, client: TestClient, make_user):
        reviewer = make_user("REVIEWER")
        app.dependency_overrides[get_current_user] = lambda: reviewer
        try:
            resp = client.get(AUDIT_URL)
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_lecturer_returns_403(
        self, db_session: Session, client: TestClient
    ):
        """An in-memory LECTURER user triggers 403 via require_role without DB write."""
        lecturer = User(
            id=uuid.uuid4(),
            email="lecturer@test.local",
            password_hash="x",
            display_name="Lecturer User",
            role="LECTURER",
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: lecturer
        try:
            resp = client.get(AUDIT_URL)
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Empty result
# ---------------------------------------------------------------------------


class TestEmptyResult:
    def test_empty_list_envelope(self, admin_client):
        client, _ = admin_client
        resp = client.get(AUDIT_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1
        assert body["page_size"] == 50


# ---------------------------------------------------------------------------
# Safe DTO — exact key contract
# ---------------------------------------------------------------------------


class TestSafeDTO:
    def test_item_has_exactly_safe_keys(self, db_session: Session, admin_client, make_user):
        client, admin = admin_client
        _user_event(db_session, admin)

        resp = client.get(AUDIT_URL)
        assert resp.status_code == 200
        item = resp.json()["items"][0]

        assert set(item.keys()) == _SAFE_DTO_KEYS

    def test_forbidden_fields_absent(self, db_session: Session, admin_client, make_user):
        client, admin = admin_client
        _user_event(db_session, admin)

        resp = client.get(AUDIT_URL)
        item = resp.json()["items"][0]

        for key in _FORBIDDEN_KEYS:
            assert key not in item, f"Sensitive field '{key}' leaked in DTO"

    def test_user_actor_display_name_populated(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        _user_event(db_session, admin)

        item = client.get(AUDIT_URL).json()["items"][0]
        assert item["actor_display_name"] == admin.display_name
        assert item["actor_service"] is None
        assert item["actor_type"] == "USER"

    def test_system_actor_service_populated(self, db_session: Session, admin_client):
        client, _ = admin_client
        _system_event(db_session)

        item = client.get(AUDIT_URL).json()["items"][0]
        assert item["actor_service"] == "scopus-importer"
        assert item["actor_display_name"] is None
        assert item["actor_type"] == "SYSTEM"

    def test_reason_null_when_not_set(self, db_session: Session, admin_client, make_user):
        client, admin = admin_client
        _user_event(db_session, admin, reason=None)

        item = client.get(AUDIT_URL).json()["items"][0]
        assert item["reason"] is None

    def test_reason_present_when_set(self, db_session: Session, admin_client, make_user):
        client, admin = admin_client
        _user_event(db_session, admin, reason="manual correction")

        item = client.get(AUDIT_URL).json()["items"][0]
        assert item["reason"] == "manual correction"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    def test_default_page_size(self, db_session: Session, admin_client, make_user):
        client, admin = admin_client
        for _ in range(3):
            _user_event(db_session, admin)

        body = client.get(AUDIT_URL).json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert body["page"] == 1
        assert body["page_size"] == 50

    def test_custom_page_size(self, db_session: Session, admin_client, make_user):
        client, admin = admin_client
        for _ in range(5):
            _user_event(db_session, admin)

        body = client.get(AUDIT_URL, params={"page_size": 2}).json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["page_size"] == 2

    def test_page_2(self, db_session: Session, admin_client, make_user):
        client, admin = admin_client
        for _ in range(5):
            _user_event(db_session, admin)

        body = client.get(AUDIT_URL, params={"page": 2, "page_size": 3}).json()
        assert len(body["items"]) == 2
        assert body["page"] == 2

    def test_page_size_above_100_rejected(self, admin_client):
        client, _ = admin_client
        resp = client.get(AUDIT_URL, params={"page_size": 101})
        assert resp.status_code == 422

    def test_ordering_created_at_desc(self, db_session: Session, admin_client, make_user):
        client, admin = admin_client
        now = datetime.now(UTC)
        ev1 = _user_event(db_session, admin, action="PUBLISHED", created_at=now - timedelta(minutes=2))
        ev2 = _user_event(db_session, admin, action="REVOKED", created_at=now - timedelta(minutes=1))
        ev3 = _user_event(db_session, admin, action="APPROVED", created_at=now)

        items = client.get(AUDIT_URL).json()["items"]
        assert items[0]["id"] == str(ev3.id)
        assert items[1]["id"] == str(ev2.id)
        assert items[2]["id"] == str(ev1.id)

    def test_ordering_id_tiebreak_desc(self, db_session: Session, admin_client, make_user):
        """Two events with the same created_at must sort by id DESC (larger UUID first)."""
        client, admin = admin_client
        fixed_ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        # Choose UUIDs where the lexicographic ordering is predictable
        id_low = uuid.UUID("10000000-0000-0000-0000-000000000001")
        id_high = uuid.UUID("90000000-0000-0000-0000-000000000002")

        ev_low = AuditEvent(
            id=id_low,
            entity_type="publication",
            entity_id=uuid.uuid4(),
            action="PUBLISHED",
            actor_type="USER",
            actor_user_id=admin.id,
            actor_service=None,
            reason=None,
        )
        ev_low.created_at = fixed_ts
        db_session.add(ev_low)

        ev_high = AuditEvent(
            id=id_high,
            entity_type="publication",
            entity_id=uuid.uuid4(),
            action="APPROVED",
            actor_type="USER",
            actor_user_id=admin.id,
            actor_service=None,
            reason=None,
        )
        ev_high.created_at = fixed_ts
        db_session.add(ev_high)
        db_session.flush()

        items = client.get(AUDIT_URL).json()["items"]
        assert items[0]["id"] == str(id_high)
        assert items[1]["id"] == str(id_low)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_filter_by_action_exact(self, db_session: Session, admin_client, make_user):
        client, admin = admin_client
        ev = _user_event(db_session, admin, action="PUBLISHED")
        _user_event(db_session, admin, action="REVOKED")

        body = client.get(AUDIT_URL, params={"action": "PUBLISHED"}).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_action_leading_trailing_whitespace_trimmed(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        ev = _user_event(db_session, admin, action="PUBLISHED")
        _user_event(db_session, admin, action="REVOKED")

        body = client.get(AUDIT_URL, params={"action": "  PUBLISHED  "}).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_action_whitespace_only_omits_filter(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        _user_event(db_session, admin, action="PUBLISHED")
        _user_event(db_session, admin, action="REVOKED")

        body = client.get(AUDIT_URL, params={"action": "   "}).json()
        assert body["total"] == 2

    def test_filter_entity_type_exact(self, db_session: Session, admin_client, make_user):
        client, admin = admin_client
        ev = _user_event(db_session, admin, entity_type="publication")
        _system_event(db_session, entity_type="scopus_import")

        body = client.get(AUDIT_URL, params={"entity_type": "publication"}).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_entity_type_whitespace_trimmed(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        ev = _user_event(db_session, admin, entity_type="publication")
        _system_event(db_session, entity_type="scopus_import")

        body = client.get(AUDIT_URL, params={"entity_type": "  publication  "}).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_entity_type_whitespace_only_omits_filter(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        _user_event(db_session, admin, entity_type="publication")
        _system_event(db_session, entity_type="scopus_import")

        body = client.get(AUDIT_URL, params={"entity_type": "  "}).json()
        assert body["total"] == 2

    def test_filter_by_actor_type_user(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        ev = _user_event(db_session, admin)
        _system_event(db_session)

        body = client.get(AUDIT_URL, params={"actor_type": "USER"}).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_by_actor_type_system(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        _user_event(db_session, admin)
        ev = _system_event(db_session)

        body = client.get(AUDIT_URL, params={"actor_type": "SYSTEM"}).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_actor_type_invalid_returns_422(self, admin_client):
        client, _ = admin_client
        resp = client.get(AUDIT_URL, params={"actor_type": "INVALID"})
        assert resp.status_code == 422

    def test_filter_date_from_inclusive(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
        ev = _user_event(db_session, admin, created_at=ts)

        body = client.get(AUDIT_URL, params={"date_from": ts.isoformat()}).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_date_to_inclusive(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
        ev = _user_event(db_session, admin, created_at=ts)

        body = client.get(AUDIT_URL, params={"date_to": ts.isoformat()}).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(ev.id)

    def test_filter_combined_date_range(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        now = datetime.now(UTC)
        old = _user_event(db_session, admin, created_at=now - timedelta(days=10))
        mid = _user_event(db_session, admin, created_at=now - timedelta(days=5))
        recent = _user_event(db_session, admin, created_at=now)

        d_from = (now - timedelta(days=7)).isoformat()
        d_to = (now - timedelta(days=3)).isoformat()
        body = client.get(
            AUDIT_URL, params={"date_from": d_from, "date_to": d_to}
        ).json()
        ids = {i["id"] for i in body["items"]}
        assert str(mid.id) in ids
        assert str(old.id) not in ids
        assert str(recent.id) not in ids

    def test_date_range_inverted_returns_422_top_level_code(self, admin_client):
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
        body = resp.json()
        assert body["code"] == "INVALID_DATE_RANGE"
        assert "detail" in body


# ---------------------------------------------------------------------------
# Actor resolution
# ---------------------------------------------------------------------------


class TestActorResolution:
    def test_active_user_display_name_resolved(
        self, db_session: Session, admin_client, make_user
    ):
        client, admin = admin_client
        _user_event(db_session, admin)

        item = client.get(AUDIT_URL).json()["items"][0]
        assert item["actor_display_name"] == admin.display_name

    def test_inactive_user_display_name_still_resolved(
        self, db_session: Session, admin_client, make_user
    ):
        """Inactive users must still resolve via LEFT JOIN."""
        client, _ = admin_client
        inactive = make_user("REVIEWER", is_active=False)
        inactive.display_name = "Inactive Person"
        db_session.flush()
        _user_event(db_session, inactive)

        body = client.get(AUDIT_URL, params={"actor_type": "USER"}).json()
        names = [i["actor_display_name"] for i in body["items"]]
        assert "Inactive Person" in names


# ---------------------------------------------------------------------------
# DB failure contract
# ---------------------------------------------------------------------------


class TestDBFailure:
    def test_db_failure_returns_503_top_level_code(self, admin_client):
        client, _ = admin_client

        from sqlalchemy.exc import OperationalError

        with patch(
            "app.api.v1.endpoints.audits.list_audits",
            side_effect=OperationalError("conn", None, Exception("db down")),
        ):
            resp = client.get(AUDIT_URL)

        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == "DATABASE_UNAVAILABLE"
        assert "detail" in body

    def test_db_failure_no_sensitive_exception_string(self, admin_client):
        client, _ = admin_client

        from sqlalchemy.exc import OperationalError

        with patch(
            "app.api.v1.endpoints.audits.list_audits",
            side_effect=OperationalError(
                "conn", None, Exception("password=secret host=db")
            ),
        ):
            resp = client.get(AUDIT_URL)

        body_text = resp.text
        assert "password=secret" not in body_text
        assert "host=db" not in body_text

    def test_read_does_not_create_audit_rows(
        self, db_session: Session, admin_client, make_user
    ):
        """GET /audits must never write any AuditEvent rows."""
        from sqlalchemy import func, select

        client, admin = admin_client
        _user_event(db_session, admin)

        before = db_session.execute(
            select(func.count()).select_from(AuditEvent)
        ).scalar_one()

        client.get(AUDIT_URL)

        after = db_session.execute(
            select(func.count()).select_from(AuditEvent)
        ).scalar_one()

        assert after == before


# ---------------------------------------------------------------------------
# No /ping endpoint
# ---------------------------------------------------------------------------


class TestNoPingEndpoint:
    def test_ping_endpoint_removed(self, admin_client):
        client, _ = admin_client
        resp = client.get(f"{AUDIT_URL}/ping")
        assert resp.status_code == 404
