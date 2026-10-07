"""Integration contract tests for GET /api/v1/reviews/history — C2-A3F.

Run focused:
    python -c "from dotenv import load_dotenv; load_dotenv('.env', override=False); import pytest, sys; sys.exit(pytest.main(['tests/integration/test_review_history_api.py', '-v']))"

Run full backend:
    python -c "from dotenv import load_dotenv; load_dotenv('.env', override=False); import pytest, sys; sys.exit(pytest.main(['tests/', '-v', '--tb=short']))"
"""

from __future__ import annotations

import hashlib
import json
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
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateObservation,
    LecturerScopusCandidateReview,
)
from app.models.governance import AuditEvent, User
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
        "lecturer_id",
        "scopus_author_id",
        "source_refs",
    }
)


# ---------------------------------------------------------------------------
# Schema isolation / session fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for C2-A3 integration tests")
    database = make_url(url).database
    if database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("C2-A3 tests must never target an acceptance database")

    schema = f"test_c2_a3_hist_{uuid.uuid4().hex}"
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
    def _make(role: str = "ADMIN", display_name: str | None = None) -> User:
        u = User(
            id=uuid.uuid4(),
            email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@a3.test",
            password_hash="x",
            display_name=display_name or f"{role} User {uuid.uuid4().hex[:4]}",
            role=role,
            is_active=True,
        )
        db_session.add(u)
        db_session.flush()
        return u

    return _make


@pytest.fixture
def admin_client(db_session: Session, client: TestClient, make_user):
    admin = make_user("ADMIN", "Admin Test User")
    app.dependency_overrides[get_current_user] = lambda: admin
    yield client, admin
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def reviewer_client(db_session: Session, client: TestClient, make_user):
    reviewer = make_user("REVIEWER", "Reviewer Test User")
    app.dependency_overrides[get_current_user] = lambda: reviewer
    yield client, reviewer
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _make_run(db: Session) -> CandidateGenerationRun:
    run = CandidateGenerationRun(
        id=uuid.uuid4(),
        rule_set_id="test-rule",
        rule_set_version="1.0",
        source_state={"seed": "test"},
        status="COMPLETED",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.flush()
    return run


def _make_obs(
    db: Session, candidate_id: uuid.UUID, run: CandidateGenerationRun
) -> LecturerScopusCandidateObservation:
    snapshot = {"candidate_status": "PENDING"}
    obs_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    obs = LecturerScopusCandidateObservation(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        generation_run_id=run.id,
        observed_at=datetime.now(timezone.utc),
        candidate_snapshot=snapshot,
        observation_hash=obs_hash,
    )
    db.add(obs)
    db.flush()
    return obs


_UNIQUE_STAFF_CODE = object()  # sentinel: auto-generate a unique staff code

def _make_candidate_pair(
    db: Session,
    *,
    staff_code: str | None | object = _UNIQUE_STAFF_CODE,
    lecturer_name: str | None = None,
    scopus_name: str | None = None,
) -> tuple[Lecturer, ScopusAuthor, LecturerScopusCandidate]:
    uid = uuid.uuid4().hex[:6]
    _lecturer_name = lecturer_name or f"Nguyen Van {uid}"
    _scopus_name = scopus_name or f"Nguyen Van {uid}"
    _staff_code: str | None = f"SC-{uid}" if staff_code is _UNIQUE_STAFF_CODE else staff_code  # type: ignore[assignment]
    lecturer = Lecturer(
        id=uuid.uuid4(),
        full_name=_lecturer_name,
        full_name_normalized=_lecturer_name.lower(),
        staff_code=_staff_code,
        email=f"lec-{uid}@ictu.edu.vn",
    )
    db.add(lecturer)
    db.flush()

    author = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id=f"5{uuid.uuid4().hex[:7]}",
        preferred_name=_scopus_name,
    )
    db.add(author)
    db.flush()

    candidate = LecturerScopusCandidate(
        id=uuid.uuid4(),
        lecturer_id=lecturer.id,
        scopus_author_id=author.id,
        status="PENDING",
    )
    db.add(candidate)
    db.flush()
    return lecturer, author, candidate


def _make_review(
    db: Session,
    *,
    candidate: LecturerScopusCandidate,
    obs: LecturerScopusCandidateObservation,
    reviewer: User,
    action: str,
    from_status: str,
    to_status: str,
    reason: str | None = None,
    review_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> LecturerScopusCandidateReview:
    r = LecturerScopusCandidateReview(
        id=review_id or uuid.uuid4(),
        candidate_id=candidate.id,
        observation_id=obs.id,
        reviewer_user_id=reviewer.id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        candidate_version=1,
        reason=reason,
        evidence_snapshot={},
    )
    if created_at is not None:
        r.created_at = created_at
    db.add(r)
    db.flush()
    return r


# ---------------------------------------------------------------------------
# A. Auth enforcement
# ---------------------------------------------------------------------------


class TestAuthEnforcement:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(HISTORY_URL)
        assert resp.status_code == 401

    def test_lecturer_returns_403(self, client: TestClient):
        # In-memory LECTURER — never flushed, so FK constraint never fires.
        fake = User(
            id=uuid.uuid4(),
            email="lecturer@test.local",
            password_hash="x",
            display_name="Lecturer User",
            role="LECTURER",
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: fake
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
# B. DTO contract — exact key set, no forbidden keys
# ---------------------------------------------------------------------------


class TestDtoContract:
    def _seed_one_accept(self, db: Session, reviewer: User):
        lecturer, author, candidate = _make_candidate_pair(db)
        run = _make_run(db)
        obs = _make_obs(db, candidate.id, run)
        _make_review(
            db,
            candidate=candidate,
            obs=obs,
            reviewer=reviewer,
            action="ACCEPT",
            from_status="PENDING",
            to_status="ACCEPTED",
        )

    def test_item_keys_exactly_safe_set(self, db_session: Session, admin_client):
        c, admin = admin_client
        self._seed_one_accept(db_session, admin)
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert frozenset(items[0].keys()) == _SAFE_DTO_KEYS

    def test_no_forbidden_keys_exposed(self, db_session: Session, admin_client):
        c, admin = admin_client
        self._seed_one_accept(db_session, admin)
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        exposed = frozenset(resp.json()["items"][0].keys()) & _FORBIDDEN_KEYS
        assert not exposed, f"Forbidden keys exposed: {exposed}"


# ---------------------------------------------------------------------------
# C. JOIN projection — assert actual seeded values come back
# ---------------------------------------------------------------------------


class TestJoinProjection:
    def test_projected_fields_match_seeded_values(
        self, db_session: Session, admin_client
    ):
        c, admin = admin_client
        lecturer, author, candidate = _make_candidate_pair(
            db_session,
            staff_code="STAFF-123",
            lecturer_name="Trần Văn B",
            scopus_name="Tran Van B",
        )
        reviewer = User(
            id=uuid.uuid4(),
            email=f"rev-{uuid.uuid4().hex[:6]}@test.local",
            password_hash="x",
            display_name="Specific Reviewer Name",
            role="REVIEWER",
            is_active=True,
        )
        db_session.add(reviewer)
        db_session.flush()
        run = _make_run(db_session)
        obs = _make_obs(db_session, candidate.id, run)
        _make_review(
            db_session,
            candidate=candidate,
            obs=obs,
            reviewer=reviewer,
            action="REJECT",
            from_status="PENDING",
            to_status="REJECTED",
            reason="test reason",
        )
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        item = items[0]
        assert item["reviewer_display_name"] == "Specific Reviewer Name"
        assert item["lecturer_full_name"] == "Trần Văn B"
        assert item["lecturer_staff_code"] == "STAFF-123"
        assert item["scopus_author_preferred_name"] == "Tran Van B"
        assert item["scopus_author_scopus_id"] == author.scopus_id
        assert item["reason"] == "test reason"

    def test_null_staff_code_is_null(self, db_session: Session, admin_client):
        c, admin = admin_client
        lecturer, author, candidate = _make_candidate_pair(
            db_session, staff_code=None
        )
        run = _make_run(db_session)
        obs = _make_obs(db_session, candidate.id, run)
        _make_review(
            db_session,
            candidate=candidate,
            obs=obs,
            reviewer=admin,
            action="ACCEPT",
            from_status="PENDING",
            to_status="ACCEPTED",
        )
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        assert resp.json()["items"][0]["lecturer_staff_code"] is None


# ---------------------------------------------------------------------------
# D. Action rows — real ACCEPT / REJECT / REOPEN data
# ---------------------------------------------------------------------------


class TestActionRows:
    def _seed_accept(self, db: Session, reviewer: User):
        lecturer, author, candidate = _make_candidate_pair(db)
        run = _make_run(db)
        obs = _make_obs(db, candidate.id, run)
        return _make_review(
            db,
            candidate=candidate,
            obs=obs,
            reviewer=reviewer,
            action="ACCEPT",
            from_status="PENDING",
            to_status="ACCEPTED",
        )

    def _seed_reject(self, db: Session, reviewer: User):
        lecturer, author, candidate = _make_candidate_pair(db)
        run = _make_run(db)
        obs = _make_obs(db, candidate.id, run)
        return _make_review(
            db,
            candidate=candidate,
            obs=obs,
            reviewer=reviewer,
            action="REJECT",
            from_status="PENDING",
            to_status="REJECTED",
            reason="Does not match",
        )

    def _seed_reopen(self, db: Session, reviewer: User):
        """Insert REOPEN row directly — no mutation API involved."""
        lecturer, author, candidate = _make_candidate_pair(db)
        run = _make_run(db)
        obs = _make_obs(db, candidate.id, run)
        return _make_review(
            db,
            candidate=candidate,
            obs=obs,
            reviewer=reviewer,
            action="REOPEN",
            from_status="REJECTED",
            to_status="PENDING",
            reason="Needs re-review",
        )

    def test_accept_row_returned_by_filter(self, db_session: Session, admin_client):
        c, admin = admin_client
        self._seed_accept(db_session, admin)
        resp = c.get(HISTORY_URL, params={"action": "ACCEPT"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["action"] == "ACCEPT"
        assert items[0]["from_status"] == "PENDING"
        assert items[0]["to_status"] == "ACCEPTED"
        assert items[0]["reason"] is None

    def test_reject_row_returned_by_filter(self, db_session: Session, admin_client):
        c, admin = admin_client
        self._seed_reject(db_session, admin)
        resp = c.get(HISTORY_URL, params={"action": "REJECT"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["action"] == "REJECT"
        assert items[0]["from_status"] == "PENDING"
        assert items[0]["to_status"] == "REJECTED"
        assert items[0]["reason"] == "Does not match"

    def test_reopen_row_returned_by_filter(self, db_session: Session, admin_client):
        c, admin = admin_client
        self._seed_reopen(db_session, admin)
        resp = c.get(HISTORY_URL, params={"action": "REOPEN"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["action"] == "REOPEN"
        assert items[0]["from_status"] == "REJECTED"
        assert items[0]["to_status"] == "PENDING"
        assert items[0]["reason"] == "Needs re-review"

    def test_all_three_actions_returned_without_filter(
        self, db_session: Session, admin_client
    ):
        c, admin = admin_client
        self._seed_accept(db_session, admin)
        self._seed_reject(db_session, admin)
        self._seed_reopen(db_session, admin)
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        assert resp.json()["total"] == 3
        actions = {item["action"] for item in resp.json()["items"]}
        assert actions == {"ACCEPT", "REJECT", "REOPEN"}

    def test_filter_excludes_other_actions(self, db_session: Session, admin_client):
        c, admin = admin_client
        self._seed_accept(db_session, admin)
        self._seed_reject(db_session, admin)
        resp = c.get(HISTORY_URL, params={"action": "ACCEPT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["action"] == "ACCEPT"

    def test_invalid_action_returns_422(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL, params={"action": "INVALID"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# E. Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    def _seed_n_reviews(self, db: Session, reviewer: User, n: int):
        run = _make_run(db)
        for i in range(n):
            lec, auth, cand = _make_candidate_pair(
                db, lecturer_name=f"Lecturer {i}", scopus_name=f"Author {i}"
            )
            obs = _make_obs(db, cand.id, run)
            _make_review(
                db,
                candidate=cand,
                obs=obs,
                reviewer=reviewer,
                action="ACCEPT",
                from_status="PENDING",
                to_status="ACCEPTED",
            )

    def test_default_page_size_20(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["page_size"] == 20
        assert body["page"] == 1

    def test_page_size_over_100_returns_422(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL, params={"page_size": 101})
        assert resp.status_code == 422

    def test_page_0_returns_422(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL, params={"page": 0})
        assert resp.status_code == 422

    def test_total_independent_of_page(self, db_session: Session, admin_client):
        c, admin = admin_client
        self._seed_n_reviews(db_session, admin, 5)
        resp1 = c.get(HISTORY_URL, params={"page": 1, "page_size": 2})
        resp2 = c.get(HISTORY_URL, params={"page": 2, "page_size": 2})
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["total"] == 5
        assert resp2.json()["total"] == 5

    def test_page_2_returns_different_items(self, db_session: Session, admin_client):
        c, admin = admin_client
        self._seed_n_reviews(db_session, admin, 5)
        resp1 = c.get(HISTORY_URL, params={"page": 1, "page_size": 3})
        resp2 = c.get(HISTORY_URL, params={"page": 2, "page_size": 3})
        ids1 = {item["id"] for item in resp1.json()["items"]}
        ids2 = {item["id"] for item in resp2.json()["items"]}
        assert ids1.isdisjoint(ids2), "Page 1 and page 2 must not share items"
        assert len(ids2) == 2  # 5 total, 3 on page 1, 2 on page 2

    def test_empty_response_structure(self, admin_client):
        c, _ = admin_client
        resp = c.get(HISTORY_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []
        assert "page" in body
        assert "page_size" in body


# ---------------------------------------------------------------------------
# F. Date range filtering
# ---------------------------------------------------------------------------


class TestDateRangeFiltering:
    def _seed_at(
        self, db: Session, reviewer: User, ts: datetime, action: str = "ACCEPT"
    ) -> LecturerScopusCandidateReview:
        lecturer, author, candidate = _make_candidate_pair(db)
        run = _make_run(db)
        obs = _make_obs(db, candidate.id, run)
        return _make_review(
            db,
            candidate=candidate,
            obs=obs,
            reviewer=reviewer,
            action=action,
            from_status="PENDING",
            to_status="ACCEPTED" if action == "ACCEPT" else "REJECTED",
            reason=None if action == "ACCEPT" else "no",
            created_at=ts,
        )

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

    def test_invalid_date_range_code_at_top_level(self, admin_client):
        c, _ = admin_client
        resp = c.get(
            HISTORY_URL,
            params={
                "date_from": "2025-12-31T00:00:00Z",
                "date_to": "2025-01-01T00:00:00Z",
            },
        )
        body = resp.json()
        assert "code" in body, "code must be at top level of response body"
        assert body["code"] == "INVALID_DATE_RANGE"
        assert "detail" in body

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

    def test_date_from_inclusive(self, db_session: Session, admin_client):
        c, admin = admin_client
        ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        self._seed_at(db_session, admin, ts)
        resp = c.get(HISTORY_URL, params={"date_from": ts.isoformat()})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_date_to_inclusive(self, db_session: Session, admin_client):
        c, admin = admin_client
        ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        self._seed_at(db_session, admin, ts)
        resp = c.get(HISTORY_URL, params={"date_to": ts.isoformat()})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_combined_range_excludes_outside_rows(
        self, db_session: Session, admin_client
    ):
        c, admin = admin_client
        ts_inside = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        ts_before = datetime(2025, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
        ts_after = datetime(2025, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        self._seed_at(db_session, admin, ts_inside)
        self._seed_at(db_session, admin, ts_before)
        self._seed_at(db_session, admin, ts_after)
        resp = c.get(
            HISTORY_URL,
            params={
                "date_from": "2025-06-01T00:00:00Z",
                "date_to": "2025-06-30T23:59:59Z",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# G. Read-only safety — no rows created by GET
# ---------------------------------------------------------------------------


class TestReadOnlySafety:
    def test_get_creates_zero_review_rows(self, db_session: Session, admin_client):
        c, admin = admin_client
        # Seed one row to give the endpoint something to return
        lecturer, author, candidate = _make_candidate_pair(db_session)
        run = _make_run(db_session)
        obs = _make_obs(db_session, candidate.id, run)
        _make_review(
            db_session,
            candidate=candidate,
            obs=obs,
            reviewer=admin,
            action="ACCEPT",
            from_status="PENDING",
            to_status="ACCEPTED",
        )
        from sqlalchemy import select, func

        count_before = db_session.execute(
            select(func.count()).select_from(LecturerScopusCandidateReview)
        ).scalar_one()

        c.get(HISTORY_URL)

        count_after = db_session.execute(
            select(func.count()).select_from(LecturerScopusCandidateReview)
        ).scalar_one()
        assert count_after == count_before, (
            f"GET /history must not create review rows: before={count_before}, after={count_after}"
        )

    def test_get_creates_zero_audit_rows(self, db_session: Session, admin_client):
        c, _ = admin_client
        from sqlalchemy import select, func

        count_before = db_session.execute(
            select(func.count()).select_from(AuditEvent)
        ).scalar_one()

        c.get(HISTORY_URL)

        count_after = db_session.execute(
            select(func.count()).select_from(AuditEvent)
        ).scalar_one()
        assert count_after == count_before, (
            f"GET /history must not create audit rows: before={count_before}, after={count_after}"
        )


# ---------------------------------------------------------------------------
# H. DB failure contract
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

    def test_db_error_response_redacts_sensitive_text(self, admin_client):
        c, _ = admin_client
        from sqlalchemy.exc import OperationalError

        sensitive = "password=secret host=db"
        with patch(
            "app.api.v1.endpoints.reviews.list_review_history",
            side_effect=OperationalError(sensitive, {}, Exception(sensitive)),
        ):
            resp = c.get(HISTORY_URL)
        assert resp.status_code == 503
        raw = resp.text
        assert "password=secret" not in raw
        assert "host=db" not in raw


# ---------------------------------------------------------------------------
# I. Deterministic ordering tiebreak
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_created_at_desc(self, db_session: Session, admin_client):
        c, admin = admin_client
        t1 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        lec1, auth1, cand1 = _make_candidate_pair(
            db_session, lecturer_name="Lec1", scopus_name="Auth1"
        )
        lec2, auth2, cand2 = _make_candidate_pair(
            db_session, lecturer_name="Lec2", scopus_name="Auth2"
        )
        run = _make_run(db_session)
        obs1 = _make_obs(db_session, cand1.id, run)
        obs2 = _make_obs(db_session, cand2.id, run)
        r1 = _make_review(
            db_session,
            candidate=cand1,
            obs=obs1,
            reviewer=admin,
            action="ACCEPT",
            from_status="PENDING",
            to_status="ACCEPTED",
            created_at=t1,
        )
        r2 = _make_review(
            db_session,
            candidate=cand2,
            obs=obs2,
            reviewer=admin,
            action="ACCEPT",
            from_status="PENDING",
            to_status="ACCEPTED",
            created_at=t2,
        )
        resp = c.get(HISTORY_URL, params={"page_size": 100})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert ids.index(str(r2.id)) < ids.index(str(r1.id)), (
            "Later created_at should sort first (DESC)"
        )

    def test_id_desc_tiebreak_same_created_at(self, db_session: Session, admin_client):
        c, admin = admin_client
        fixed_ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        id_low = uuid.UUID("10000000-0000-0000-0000-000000000001")
        id_high = uuid.UUID("90000000-0000-0000-0000-000000000002")

        lec1, auth1, cand1 = _make_candidate_pair(
            db_session, lecturer_name="TbLec1", scopus_name="TbAuth1"
        )
        lec2, auth2, cand2 = _make_candidate_pair(
            db_session, lecturer_name="TbLec2", scopus_name="TbAuth2"
        )
        run = _make_run(db_session)
        obs1 = _make_obs(db_session, cand1.id, run)
        obs2 = _make_obs(db_session, cand2.id, run)
        _make_review(
            db_session,
            candidate=cand1,
            obs=obs1,
            reviewer=admin,
            action="ACCEPT",
            from_status="PENDING",
            to_status="ACCEPTED",
            review_id=id_low,
            created_at=fixed_ts,
        )
        _make_review(
            db_session,
            candidate=cand2,
            obs=obs2,
            reviewer=admin,
            action="ACCEPT",
            from_status="PENDING",
            to_status="ACCEPTED",
            review_id=id_high,
            created_at=fixed_ts,
        )
        resp = c.get(HISTORY_URL, params={"page_size": 100})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(id_high) in ids and str(id_low) in ids
        assert ids.index(str(id_high)) < ids.index(str(id_low)), (
            "id_high must sort before id_low when created_at is equal (id DESC)"
        )
