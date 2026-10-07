"""Integration contract tests for GET /api/v1/reviews/history — C2-A3.

Run with:
    python -c "from dotenv import load_dotenv; load_dotenv('.env', override=False); import pytest, sys; sys.exit(pytest.main(['tests/integration/test_review_history_api.py', '-v']))"
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
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
from app.models.candidate import LecturerScopusCandidate, LecturerScopusCandidateReview
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor

HISTORY_URL = "/api/v1/reviews/history"

_SAFE_DTO_KEYS = frozenset(
    {
        "id",
        "action",
        "from_status",
        "to_status",
        "reason",
        "created_at",
        "reviewer_display_name",
        "lecturer_full_name",
        "lecturer_staff_code",
        "scopus_author_scopus_id",
        "scopus_author_preferred_name",
    }
)

_FORBIDDEN_KEYS = frozenset(
    {
        "candidate_id",
        "observation_id",
        "reviewer_user_id",
        "candidate_version",
        "resulting_identity_id",
        "evidence_snapshot",
        "generation_run_id",
    }
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for C2-A3 integration tests")
    database = make_url(url).database
    if database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("C2-A3 tests must never target an acceptance database")

    schema = f"test_c2_a3_review_hist_{uuid.uuid4().hex}"
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
            email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@a3.test",
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


@pytest.fixture
def reviewer_client(db_session: Session, client: TestClient, make_user):
    reviewer = make_user("REVIEWER")
    app.dependency_overrides[get_current_user] = lambda: reviewer
    yield client, reviewer
    app.dependency_overrides.pop(get_current_user, None)


def _make_seed_data(db_session: Session, reviewer: User):
    """Insert one Lecturer, ScopusAuthor, Candidate, and Review row."""
    lecturer = Lecturer(
        id=uuid.uuid4(),
        full_name="Nguyễn Văn A",
        full_name_normalized="nguyen van a",
        staff_code="NVA001",
        email="nva@ictu.edu.vn",
    )
    db_session.add(lecturer)
    db_session.flush()

    author = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id=f"5{uuid.uuid4().hex[:7]}",
        preferred_name="Nguyen Van A",
    )
    db_session.add(author)
    db_session.flush()

    candidate = LecturerScopusCandidate(
        id=uuid.uuid4(),
        lecturer_id=lecturer.id,
        scopus_author_id=author.id,
        status="ACCEPTED",
    )
    db_session.add(candidate)
    db_session.flush()

    # Find or create a minimal observation for FK constraint
    # LecturerScopusCandidateReview requires observation_id (FK RESTRICT).
    # We need a generation run + observation first.
    from app.models.candidate import (
        CandidateGenerationRun,
        LecturerScopusCandidateObservation,
    )
    import hashlib, json

    run = CandidateGenerationRun(
        id=uuid.uuid4(),
        rule_set_id="test-rule",
        rule_set_version="1.0",
        source_state={"seed": "test"},
        status="COMPLETED",
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    db_session.flush()

    snapshot = {"candidate_status": "PENDING"}
    obs_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    obs = LecturerScopusCandidateObservation(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        generation_run_id=run.id,
        observed_at=datetime.now(timezone.utc),
        candidate_snapshot=snapshot,
        observation_hash=obs_hash,
    )
    db_session.add(obs)
    db_session.flush()

    review = LecturerScopusCandidateReview(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        observation_id=obs.id,
        reviewer_user_id=reviewer.id,
        action="ACCEPT",
        from_status="PENDING",
        to_status="ACCEPTED",
        candidate_version=1,
        reason=None,
        evidence_snapshot={},
    )
    db_session.add(review)
    db_session.flush()
    return review, lecturer, author, candidate


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


class TestAuthEnforcement:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(HISTORY_URL)
        assert resp.status_code == 401

    def test_lecturer_returns_403(self, client: TestClient):
        # Use an in-memory User with LECTURER role — never flushed, so the
        # lecturer_id FK constraint never fires.
        fake_lecturer = User(
            id=uuid.uuid4(),
            email="lecturer@test.local",
            password_hash="x",
            display_name="Lecturer User",
            role="LECTURER",
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: fake_lecturer
        try:
            resp = client.get(HISTORY_URL)
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_admin_returns_200(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200

    def test_reviewer_returns_200(self, reviewer_client):
        c, _ = reviewer_client
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# DTO contract
# ---------------------------------------------------------------------------


class TestDtoContract:
    def test_item_keys_are_exactly_safe_set(self, db_session: Session, admin_client):
        c, admin = admin_client
        _make_seed_data(db_session, admin)
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        actual_keys = frozenset(items[0].keys())
        assert actual_keys == _SAFE_DTO_KEYS

    def test_no_forbidden_keys_exposed(self, db_session: Session, admin_client):
        c, admin = admin_client
        _make_seed_data(db_session, admin)
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        items = resp.json()["items"]
        actual_keys = frozenset(items[0].keys())
        exposed = actual_keys & _FORBIDDEN_KEYS
        assert not exposed, f"Forbidden keys exposed: {exposed}"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    def test_default_page_size_is_20(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["page_size"] == 20
        assert body["page"] == 1

    def test_page_size_max_100_enforced(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL, params={"page_size": 9999})
        assert resp.status_code == 422

    def test_invalid_page_0_returns_422(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL, params={"page": 0})
        assert resp.status_code == 422

    def test_empty_response_structure(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert body["total"] == 0
        assert body["items"] == []


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_invalid_action_returns_422(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL, params={"action": "INVALID"})
        assert resp.status_code == 422

    def test_accept_action_filter(self, db_session: Session, admin_client):
        c, admin = admin_client
        _make_seed_data(db_session, admin)
        resp = c.get(HISTORY_URL, params={"action": "ACCEPT"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["action"] == "ACCEPT"

    def test_reject_filter_returns_empty_when_no_rejects(self, db_session: Session, admin_client):
        c, admin = admin_client
        _make_seed_data(db_session, admin)
        resp = c.get(HISTORY_URL, params={"action": "REJECT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# Date range validation
# ---------------------------------------------------------------------------


class TestDateRangeValidation:
    def test_date_from_after_date_to_returns_422(self, admin_client):
        c, _ = admin_client
        resp = c.get(
            HISTORY_URL,
            params={
                "date_from": "2025-12-31T00:00:00Z",
                "date_to": "2025-01-01T00:00:00Z",
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body.get("code") == "INVALID_DATE_RANGE"

    def test_date_from_equal_to_date_to_is_valid(self, admin_client):
        c, _ = admin_client
        resp = c.get(
            HISTORY_URL,
            params={
                "date_from": "2025-06-01T00:00:00Z",
                "date_to": "2025-06-01T00:00:00Z",
            },
        )
        assert resp.status_code == 200

    def test_date_inclusive_boundary(self, db_session: Session, admin_client):
        c, admin = admin_client
        review, _, _, _ = _make_seed_data(db_session, admin)
        ts = review.created_at.isoformat()
        resp = c.get(HISTORY_URL, params={"date_from": ts, "date_to": ts})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# DB failure contract
# ---------------------------------------------------------------------------


class TestDatabaseFailure:
    def test_db_failure_returns_503_with_code(self, admin_client):
        c, _ = admin_client
        from sqlalchemy.exc import OperationalError

        with patch(
            "app.api.v1.endpoints.reviews.list_review_history",
            side_effect=OperationalError("conn", {}, Exception("down")),
        ):
            resp = c.get(HISTORY_URL)
        assert resp.status_code == 503
        body = resp.json()
        assert body.get("code") == "DATABASE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Deterministic ordering tiebreak
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_id_desc_tiebreak_when_same_created_at(self, db_session: Session, admin_client):
        c, admin = admin_client

        # Create shared FK objects
        lecturer = Lecturer(
            id=uuid.uuid4(),
            full_name="Tiebreak Lecturer",
            full_name_normalized="tiebreak lecturer",
            email="tb@ictu.edu.vn",
        )
        db_session.add(lecturer)

        author = ScopusAuthor(
            id=uuid.uuid4(),
            scopus_id=f"9{uuid.uuid4().hex[:7]}",
            preferred_name="Tiebreak Author",
        )
        db_session.add(author)
        db_session.flush()

        candidate = LecturerScopusCandidate(
            id=uuid.uuid4(),
            lecturer_id=lecturer.id,
            scopus_author_id=author.id,
            status="REJECTED",
        )
        db_session.add(candidate)
        db_session.flush()

        from app.models.candidate import (
            CandidateGenerationRun,
            LecturerScopusCandidateObservation,
        )
        import hashlib, json

        run = CandidateGenerationRun(
            id=uuid.uuid4(),
            rule_set_id="tb-rule",
            rule_set_version="1.0",
            source_state={"seed": "tb"},
            status="COMPLETED",
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(run)
        db_session.flush()

        snapshot = {"candidate_status": "PENDING"}
        obs_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        obs = LecturerScopusCandidateObservation(
            id=uuid.uuid4(),
            candidate_id=candidate.id,
            generation_run_id=run.id,
            observed_at=datetime.now(timezone.utc),
            candidate_snapshot=snapshot,
            observation_hash=obs_hash,
        )
        db_session.add(obs)
        db_session.flush()

        fixed_ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        id_low = uuid.UUID("10000000-0000-0000-0000-000000000001")
        id_high = uuid.UUID("90000000-0000-0000-0000-000000000002")

        for rev_id in [id_low, id_high]:
            r = LecturerScopusCandidateReview(
                id=rev_id,
                candidate_id=candidate.id,
                observation_id=obs.id,
                reviewer_user_id=admin.id,
                action="REJECT",
                from_status="PENDING",
                to_status="REJECTED",
                candidate_version=1,
                reason="tiebreak test",
                evidence_snapshot={},
            )
            r.created_at = fixed_ts
            db_session.add(r)
        db_session.flush()

        resp = c.get(HISTORY_URL, params={"page_size": 100})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(id_high) in ids and str(id_low) in ids
        assert ids.index(str(id_high)) < ids.index(str(id_low)), (
            "id_high should sort before id_low when created_at equal (id DESC)"
        )
