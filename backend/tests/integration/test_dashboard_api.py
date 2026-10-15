"""Integration contract tests for GET /api/v1/dashboard/summary — C2-A4.

Run focused:
    python -c "from dotenv import load_dotenv; load_dotenv('.env', override=False); import pytest, sys; sys.exit(pytest.main(['tests/integration/test_dashboard_api.py', '-v']))"
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
from app.models.affiliation import PublicationAuthorAffiliationResolution
from app.models.base import Base
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateObservation,
    LecturerScopusCandidateReview,
)
from app.models.governance import AuditEvent, User
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor
from app.models.scopus_raw import ScopusImport

DASHBOARD_URL = "/api/v1/dashboard/summary"
CHARTS_URL = "/api/v1/dashboard/charts"

_SAFE_IMPORT_KEYS = frozenset(
    {
        "file_name",
        "status",
        "total_records",
        "valid_records",
        "invalid_records",
        "created_at",
        "updated_at",
    }
)
_FORBIDDEN_IMPORT_KEYS = frozenset(
    {"id", "file_sha256", "error_summary", "normalization_summary", "imported_at"}
)

_SAFE_AUDIT_KEYS = frozenset(
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
_FORBIDDEN_AUDIT_KEYS = frozenset(
    {
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
        "password_hash",
        "auth_version",
    }
)


# ---------------------------------------------------------------------------
# Schema isolation / session fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for C2-A4 integration tests")
    database = make_url(url).database
    if database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("C2-A4 tests must never target an acceptance database")

    schema = f"test_c2_a4_dash_{uuid.uuid4().hex}"
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
            email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@dash.test",
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
    admin = make_user("ADMIN", "Admin Dash User")
    app.dependency_overrides[get_current_user] = lambda: admin
    yield client, admin
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

_SHA256_ZERO = "a" * 64


def _make_import(
    db: Session,
    *,
    file_name: str | None = None,
    status: str = "APPLIED",
    created_at: datetime | None = None,
) -> ScopusImport:
    uid = uuid.uuid4().hex[:6]
    imp = ScopusImport(
        id=uuid.uuid4(),
        file_name=file_name or f"scopus_{uid}.csv",
        file_sha256=hashlib.sha256(uid.encode()).hexdigest(),
        total_records=10,
        valid_records=8,
        invalid_records=2,
        status=status,
    )
    if created_at is not None:
        imp.created_at = created_at
    db.add(imp)
    db.flush()
    return imp


def _make_lecturer(
    db: Session, *, is_active: bool = True, name: str | None = None
) -> Lecturer:
    uid = uuid.uuid4().hex[:6]
    lec = Lecturer(
        id=uuid.uuid4(),
        full_name=name or f"Lecturer {uid}",
        full_name_normalized=(name or f"lecturer {uid}").lower(),
        staff_code=f"SC-{uid}",
        email=f"lec-{uid}@ictu.edu.vn",
        is_active=is_active,
    )
    db.add(lec)
    db.flush()
    return lec


def _make_scopus_author(db: Session) -> ScopusAuthor:
    uid = uuid.uuid4().hex[:6]
    a = ScopusAuthor(
        id=uuid.uuid4(),
        scopus_id=f"7{uid}",
        preferred_name=f"Author {uid}",
    )
    db.add(a)
    db.flush()
    return a


def _make_publication(
    db: Session, *, year: int | None = None, document_type: str | None = None
) -> Publication:
    uid = uuid.uuid4().hex[:6]
    p = Publication(
        id=uuid.uuid4(),
        eid=f"2-s2.0-{uid}",
        title=f"Publication {uid}",
        title_normalized=f"publication {uid}",
        source_title=f"Journal {uid}",
        year=year,
        document_type=document_type,
    )
    db.add(p)
    db.flush()
    return p


def _make_publication_author(
    db: Session, publication: Publication, author: ScopusAuthor, *, author_order: int = 1
) -> PublicationAuthor:
    pa = PublicationAuthor(
        id=uuid.uuid4(),
        publication_id=publication.id,
        scopus_author_id=author.id,
        author_order=author_order,
    )
    db.add(pa)
    db.flush()
    return pa


def _make_affiliation_resolution(
    db: Session,
    publication_author: PublicationAuthor,
    *,
    link_status: str = "CORROBORATED",
    affiliation_presence: str | None = "PRESENT",
    source_system: str = "openalex",
) -> PublicationAuthorAffiliationResolution:
    is_unresolved = link_status == "UNRESOLVED"
    res = PublicationAuthorAffiliationResolution(
        id=uuid.uuid4(),
        publication_author_id=publication_author.id,
        source_system=source_system,
        source_payload_sha256="a" * 64,
        link_status=link_status,
        link_method=None if is_unresolved else (
            "ORCID_SCOPUS_ID_BRIDGE" if link_status == "VERIFIED" else "POSITION_COUNT_NAME"
        ),
        unresolved_reason="NOT_FOUND" if is_unresolved else None,
        affiliation_presence=None if is_unresolved else affiliation_presence,
        evidence={},
        external_position=None if is_unresolved else 1,
        external_author_orcid=(
            "0000-0001-2345-6789" if link_status == "VERIFIED" else None
        ),
        retrieved_at=None if is_unresolved else datetime.now(timezone.utc),
        importer_version="test-1.0",
    )
    db.add(res)
    db.flush()
    return res


def _make_identity(
    db: Session, lecturer: Lecturer, author: ScopusAuthor, status: str = "CANDIDATE"
) -> LecturerScopusIdentity:
    identity = LecturerScopusIdentity(
        id=uuid.uuid4(),
        lecturer_id=lecturer.id,
        scopus_author_id=author.id,
        status=status,
    )
    db.add(identity)
    db.flush()
    return identity


def _make_run(db: Session, status: str = "COMPLETED") -> CandidateGenerationRun:
    run = CandidateGenerationRun(
        id=uuid.uuid4(),
        rule_set_id="test-rule",
        rule_set_version="1.0",
        source_state={"seed": "test"},
        status=status,
    )
    # DB check: (RUNNING AND completed_at IS NULL) OR (COMPLETED|FAILED AND completed_at IS NOT NULL)
    if status in ("COMPLETED", "FAILED"):
        run.completed_at = datetime.now(timezone.utc)
    db.add(run)
    db.flush()
    return run


def _make_obs(
    db: Session,
    candidate_id: uuid.UUID,
    run: CandidateGenerationRun,
) -> LecturerScopusCandidateObservation:
    snap = {"candidate_status": "PENDING"}
    obs_hash = hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest()
    obs = LecturerScopusCandidateObservation(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        generation_run_id=run.id,
        observed_at=datetime.now(timezone.utc),
        candidate_snapshot=snap,
        observation_hash=obs_hash,
    )
    db.add(obs)
    db.flush()
    return obs


def _make_candidate(
    db: Session,
    lecturer: Lecturer,
    author: ScopusAuthor,
    status: str = "PENDING",
) -> LecturerScopusCandidate:
    cand = LecturerScopusCandidate(
        id=uuid.uuid4(),
        lecturer_id=lecturer.id,
        scopus_author_id=author.id,
        status=status,
    )
    db.add(cand)
    db.flush()
    return cand


def _make_audit_event(
    db: Session,
    actor: User | None = None,
    *,
    entity_type: str = "publication",
    action: str = "CREATED",
    actor_type: str = "USER",
    created_at: datetime | None = None,
) -> AuditEvent:
    ev = AuditEvent(
        id=uuid.uuid4(),
        entity_type=entity_type,
        entity_id=uuid.uuid4(),
        action=action,
        actor_type=actor_type,
        actor_user_id=actor.id if actor else None,
        actor_service="test-service" if actor_type == "SYSTEM" else None,
        reason=None,
    )
    if created_at is not None:
        ev.created_at = created_at
    db.add(ev)
    db.flush()
    return ev


# ---------------------------------------------------------------------------
# A. Auth enforcement
# ---------------------------------------------------------------------------


class TestAuthEnforcement:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(DASHBOARD_URL)
        assert resp.status_code == 401

    def test_reviewer_returns_403(self, client: TestClient, make_user):
        reviewer = make_user("REVIEWER")
        app.dependency_overrides[get_current_user] = lambda: reviewer
        try:
            resp = client.get(DASHBOARD_URL)
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_lecturer_returns_403(self, client: TestClient):
        fake = User(
            id=uuid.uuid4(),
            email="lecturer@dash.test",
            password_hash="x",
            display_name="Lecturer User",
            role="LECTURER",
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: fake
        try:
            resp = client.get(DASHBOARD_URL)
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_admin_returns_200(self, admin_client):
        c, _ = admin_client
        resp = c.get(DASHBOARD_URL)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# B. Empty database contract
# ---------------------------------------------------------------------------


class TestEmptyDatabaseContract:
    def test_all_zero_counts_and_empty_collections(self, admin_client):
        c, _ = admin_client
        resp = c.get(DASHBOARD_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_publications"] == 0
        assert body["total_lecturers"] == 0
        assert body["active_lecturers"] == 0
        assert body["total_scopus_authors"] == 0
        assert body["identity_counts"] == {
            "CANDIDATE": 0,
            "APPROVED": 0,
            "REJECTED": 0,
            "REVOKED": 0,
        }
        assert body["pending_review_count"] == 0
        assert body["latest_scopus_import"] is None
        assert body["recent_audit_actions"] == []


# ---------------------------------------------------------------------------
# C. Core counts
# ---------------------------------------------------------------------------


class TestCoreCounts:
    def test_publication_count(self, db_session: Session, admin_client):
        c, _ = admin_client
        _make_publication(db_session)
        _make_publication(db_session)
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["total_publications"] == 2

    def test_lecturer_total_and_active(self, db_session: Session, admin_client):
        c, _ = admin_client
        _make_lecturer(db_session, is_active=True)
        _make_lecturer(db_session, is_active=True)
        _make_lecturer(db_session, is_active=False)
        resp = c.get(DASHBOARD_URL)
        body = resp.json()
        assert body["total_lecturers"] == 3
        assert body["active_lecturers"] == 2

    def test_inactive_lecturer_not_in_active_count(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        _make_lecturer(db_session, is_active=False)
        resp = c.get(DASHBOARD_URL)
        body = resp.json()
        assert body["total_lecturers"] == 1
        assert body["active_lecturers"] == 0

    def test_scopus_author_count(self, db_session: Session, admin_client):
        c, _ = admin_client
        _make_scopus_author(db_session)
        _make_scopus_author(db_session)
        _make_scopus_author(db_session)
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["total_scopus_authors"] == 3


# ---------------------------------------------------------------------------
# D. Identity counts
# ---------------------------------------------------------------------------


class TestIdentityCounts:
    def test_all_four_statuses_present_even_when_zero(
        self, admin_client
    ):
        c, _ = admin_client
        resp = c.get(DASHBOARD_URL)
        counts = resp.json()["identity_counts"]
        assert set(counts.keys()) == {"CANDIDATE", "APPROVED", "REJECTED", "REVOKED"}

    def test_identity_counts_exact(self, db_session: Session, admin_client):
        c, admin = admin_client
        # Need distinct (lecturer, scopus_author) pairs per identity
        # APPROVED: only one per scopus_author
        lec1 = _make_lecturer(db_session)
        lec2 = _make_lecturer(db_session)
        lec3 = _make_lecturer(db_session)
        lec4 = _make_lecturer(db_session)
        a1 = _make_scopus_author(db_session)
        a2 = _make_scopus_author(db_session)
        a3 = _make_scopus_author(db_session)
        a4 = _make_scopus_author(db_session)
        _make_identity(db_session, lec1, a1, "CANDIDATE")
        _make_identity(db_session, lec2, a2, "APPROVED")
        _make_identity(db_session, lec3, a3, "REJECTED")
        _make_identity(db_session, lec4, a4, "REVOKED")
        resp = c.get(DASHBOARD_URL)
        counts = resp.json()["identity_counts"]
        assert counts["CANDIDATE"] == 1
        assert counts["APPROVED"] == 1
        assert counts["REJECTED"] == 1
        assert counts["REVOKED"] == 1

    def test_missing_statuses_appear_as_zero(self, db_session: Session, admin_client):
        c, _ = admin_client
        lec = _make_lecturer(db_session)
        auth = _make_scopus_author(db_session)
        _make_identity(db_session, lec, auth, "CANDIDATE")
        resp = c.get(DASHBOARD_URL)
        counts = resp.json()["identity_counts"]
        assert counts["CANDIDATE"] == 1
        assert counts["APPROVED"] == 0
        assert counts["REJECTED"] == 0
        assert counts["REVOKED"] == 0


# ---------------------------------------------------------------------------
# E. Pending review semantics
# ---------------------------------------------------------------------------


class TestPendingReviewSemantics:
    def test_pending_with_no_observation_not_counted(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        lec = _make_lecturer(db_session)
        auth = _make_scopus_author(db_session)
        _make_candidate(db_session, lec, auth, "PENDING")
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["pending_review_count"] == 0

    def test_pending_with_running_run_observation_not_counted(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        lec = _make_lecturer(db_session)
        auth = _make_scopus_author(db_session)
        cand = _make_candidate(db_session, lec, auth, "PENDING")
        run = _make_run(db_session, status="RUNNING")
        _make_obs(db_session, cand.id, run)
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["pending_review_count"] == 0

    def test_pending_with_failed_run_observation_not_counted(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        lec = _make_lecturer(db_session)
        auth = _make_scopus_author(db_session)
        cand = _make_candidate(db_session, lec, auth, "PENDING")
        run = _make_run(db_session, status="FAILED")
        _make_obs(db_session, cand.id, run)
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["pending_review_count"] == 0

    def test_pending_with_completed_run_observation_is_counted(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        lec = _make_lecturer(db_session)
        auth = _make_scopus_author(db_session)
        cand = _make_candidate(db_session, lec, auth, "PENDING")
        run = _make_run(db_session, status="COMPLETED")
        _make_obs(db_session, cand.id, run)
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["pending_review_count"] == 1

    def test_accepted_candidate_not_counted(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        lec = _make_lecturer(db_session)
        auth = _make_scopus_author(db_session)
        cand = _make_candidate(db_session, lec, auth, "ACCEPTED")
        run = _make_run(db_session, status="COMPLETED")
        _make_obs(db_session, cand.id, run)
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["pending_review_count"] == 0

    def test_multiple_completed_observations_candidate_counted_once(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        lec = _make_lecturer(db_session)
        auth = _make_scopus_author(db_session)
        cand = _make_candidate(db_session, lec, auth, "PENDING")
        run1 = _make_run(db_session, status="COMPLETED")
        run2 = _make_run(db_session, status="COMPLETED")
        _make_obs(db_session, cand.id, run1)
        _make_obs(db_session, cand.id, run2)
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["pending_review_count"] == 1


# ---------------------------------------------------------------------------
# F. Queue / dashboard parity
# ---------------------------------------------------------------------------


class TestQueueDashboardParity:
    def test_pending_review_count_matches_queue_total(
        self, db_session: Session, admin_client
    ):
        c, admin = admin_client
        # Seed 3 valid reviewable candidates + 1 not reviewable
        run = _make_run(db_session, status="COMPLETED")
        for _ in range(3):
            lec = _make_lecturer(db_session)
            auth = _make_scopus_author(db_session)
            cand = _make_candidate(db_session, lec, auth, "PENDING")
            _make_obs(db_session, cand.id, run)
        # This one has no observation — not counted
        lec_x = _make_lecturer(db_session)
        auth_x = _make_scopus_author(db_session)
        _make_candidate(db_session, lec_x, auth_x, "PENDING")

        dash_resp = c.get(DASHBOARD_URL)
        queue_resp = c.get("/api/v1/reviews/candidates", params={"status": "PENDING"})
        assert dash_resp.status_code == 200
        assert queue_resp.status_code == 200
        assert (
            dash_resp.json()["pending_review_count"] == queue_resp.json()["total"]
        ), "Dashboard pending_review_count must equal review queue total"


# ---------------------------------------------------------------------------
# G. Latest scopus import
# ---------------------------------------------------------------------------


class TestLatestScopusImport:
    def test_no_import_returns_null(self, admin_client):
        c, _ = admin_client
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["latest_scopus_import"] is None

    def test_latest_chosen_by_created_at_desc(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        t_old = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t_new = datetime(2025, 6, 1, tzinfo=timezone.utc)
        _make_import(db_session, file_name="old.csv", created_at=t_old)
        _make_import(db_session, file_name="new.csv", created_at=t_new)
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["latest_scopus_import"]["file_name"] == "new.csv"

    def test_latest_import_exact_allowed_keys(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        _make_import(db_session)
        resp = c.get(DASHBOARD_URL)
        imp = resp.json()["latest_scopus_import"]
        assert imp is not None
        assert frozenset(imp.keys()) == _SAFE_IMPORT_KEYS

    def test_latest_import_no_forbidden_keys(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        _make_import(db_session)
        resp = c.get(DASHBOARD_URL)
        imp = resp.json()["latest_scopus_import"]
        exposed = frozenset(imp.keys()) & _FORBIDDEN_IMPORT_KEYS
        assert not exposed, f"Forbidden import keys exposed: {exposed}"

    def test_id_desc_tiebreak_same_created_at(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        id_low = uuid.UUID("10000000-0000-0000-0000-000000000001")
        id_high = uuid.UUID("90000000-0000-0000-0000-000000000002")
        imp_low = ScopusImport(
            id=id_low,
            file_name="low.csv",
            file_sha256=hashlib.sha256(b"low").hexdigest(),
            total_records=0,
            valid_records=0,
            invalid_records=0,
            status="APPLIED",
        )
        imp_low.created_at = ts
        imp_high = ScopusImport(
            id=id_high,
            file_name="high.csv",
            file_sha256=hashlib.sha256(b"high").hexdigest(),
            total_records=0,
            valid_records=0,
            invalid_records=0,
            status="APPLIED",
        )
        imp_high.created_at = ts
        db_session.add(imp_low)
        db_session.add(imp_high)
        db_session.flush()
        resp = c.get(DASHBOARD_URL)
        assert resp.json()["latest_scopus_import"]["file_name"] == "high.csv"


# ---------------------------------------------------------------------------
# H. Recent audit actions
# ---------------------------------------------------------------------------


class TestRecentAuditActions:
    def test_empty_recent_audit_returns_empty_list(self, admin_client):
        c, _ = admin_client
        assert c.get(DASHBOARD_URL).json()["recent_audit_actions"] == []

    def test_recent_audit_max_5(self, db_session: Session, admin_client):
        c, admin = admin_client
        for i in range(8):
            _make_audit_event(db_session, admin)
        resp = c.get(DASHBOARD_URL)
        assert len(resp.json()["recent_audit_actions"]) == 5

    def test_recent_audit_ordered_created_at_desc(
        self, db_session: Session, admin_client
    ):
        c, admin = admin_client
        ts_old = datetime(2025, 1, 1, tzinfo=timezone.utc)
        ts_new = datetime(2025, 12, 1, tzinfo=timezone.utc)
        ev_old = _make_audit_event(db_session, admin, created_at=ts_old)
        ev_new = _make_audit_event(db_session, admin, created_at=ts_new)
        items = c.get(DASHBOARD_URL).json()["recent_audit_actions"]
        ids = [item["id"] for item in items]
        assert ids.index(str(ev_new.id)) < ids.index(str(ev_old.id))

    def test_recent_audit_exact_safe_keys(self, db_session: Session, admin_client):
        c, admin = admin_client
        _make_audit_event(db_session, admin)
        items = c.get(DASHBOARD_URL).json()["recent_audit_actions"]
        assert len(items) == 1
        assert frozenset(items[0].keys()) == _SAFE_AUDIT_KEYS

    def test_recent_audit_no_forbidden_keys(self, db_session: Session, admin_client):
        c, admin = admin_client
        _make_audit_event(db_session, admin)
        items = c.get(DASHBOARD_URL).json()["recent_audit_actions"]
        exposed = frozenset(items[0].keys()) & _FORBIDDEN_AUDIT_KEYS
        assert not exposed, f"Forbidden audit keys exposed: {exposed}"

    def test_recent_audit_includes_system_actor(
        self, db_session: Session, admin_client
    ):
        c, admin = admin_client
        _make_audit_event(
            db_session, None, actor_type="SYSTEM", entity_type="import", action="START"
        )
        items = c.get(DASHBOARD_URL).json()["recent_audit_actions"]
        assert any(item["actor_type"] == "SYSTEM" for item in items)


# ---------------------------------------------------------------------------
# I. Read-only safety
# ---------------------------------------------------------------------------


class TestReadOnlySafety:
    def test_get_creates_zero_audit_rows(self, db_session: Session, admin_client):
        c, _ = admin_client
        from sqlalchemy import select, func

        before = db_session.execute(
            select(func.count()).select_from(AuditEvent)
        ).scalar_one()
        c.get(DASHBOARD_URL)
        after = db_session.execute(
            select(func.count()).select_from(AuditEvent)
        ).scalar_one()
        assert after == before, (
            f"GET dashboard must not create audit rows: before={before}, after={after}"
        )

    def test_get_creates_zero_review_rows(self, db_session: Session, admin_client):
        c, _ = admin_client
        from sqlalchemy import select, func

        before = db_session.execute(
            select(func.count()).select_from(LecturerScopusCandidateReview)
        ).scalar_one()
        c.get(DASHBOARD_URL)
        after = db_session.execute(
            select(func.count()).select_from(LecturerScopusCandidateReview)
        ).scalar_one()
        assert after == before


# ---------------------------------------------------------------------------
# J. DB failure contract
# ---------------------------------------------------------------------------


class TestDatabaseFailure:
    def test_db_failure_returns_503_with_code(self, admin_client):
        c, _ = admin_client
        from sqlalchemy.exc import OperationalError

        with patch(
            "app.api.v1.endpoints.dashboard.get_dashboard_summary",
            side_effect=OperationalError("conn", {}, Exception("down")),
        ):
            resp = c.get(DASHBOARD_URL)
        assert resp.status_code == 503
        assert resp.json().get("code") == "DATABASE_UNAVAILABLE"

    def test_db_error_redacts_sensitive_text(self, admin_client):
        c, _ = admin_client
        from sqlalchemy.exc import OperationalError

        sensitive = "password=secret host=db"
        with patch(
            "app.api.v1.endpoints.dashboard.get_dashboard_summary",
            side_effect=OperationalError(sensitive, {}, Exception(sensitive)),
        ):
            resp = c.get(DASHBOARD_URL)
        assert resp.status_code == 503
        assert "password=secret" not in resp.text
        assert "host=db" not in resp.text


# ---------------------------------------------------------------------------
# K. GET /api/v1/dashboard/charts — RBAC
# ---------------------------------------------------------------------------


class TestChartsAuthEnforcement:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(CHARTS_URL)
        assert resp.status_code == 401

    def test_reviewer_returns_403(self, client: TestClient, make_user):
        reviewer = make_user("REVIEWER")
        app.dependency_overrides[get_current_user] = lambda: reviewer
        try:
            resp = client.get(CHARTS_URL)
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_lecturer_returns_403(self, client: TestClient):
        fake = User(
            id=uuid.uuid4(),
            email="lecturer-charts@dash.test",
            password_hash="x",
            display_name="Lecturer User",
            role="LECTURER",
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: fake
        try:
            resp = client.get(CHARTS_URL)
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_admin_returns_200(self, admin_client):
        c, _ = admin_client
        resp = c.get(CHARTS_URL)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# L. Empty database contract — charts
# ---------------------------------------------------------------------------


class TestChartsEmptyDatabase:
    def test_empty_db_returns_zero_and_empty_lists(self, admin_client):
        c, _ = admin_client
        resp = c.get(CHARTS_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["publications_total_with_year"] == 0
        assert body["publications_total_without_year"] == 0
        assert body["publications_by_year"] == []
        assert body["publications_by_document_type"] == []
        cov = body["affiliation_coverage"]
        assert cov["total_author_positions"] == 0
        assert cov["positions_with_affiliation"] == 0
        assert cov["positions_without_affiliation"] == 0
        assert cov["by_link_status"] == {
            "VERIFIED": 0,
            "CORROBORATED": 0,
            "UNRESOLVED": 0,
        }


# ---------------------------------------------------------------------------
# M. publications_by_year
# ---------------------------------------------------------------------------


class TestChartsPublicationsByYear:
    def test_groups_by_year_ascending(self, db_session: Session, admin_client):
        c, _ = admin_client
        _make_publication(db_session, year=2024)
        _make_publication(db_session, year=2022)
        _make_publication(db_session, year=2024)
        _make_publication(db_session, year=2023)
        resp = c.get(CHARTS_URL)
        items = resp.json()["publications_by_year"]
        assert [i["year"] for i in items] == [2022, 2023, 2024]
        assert {i["year"]: i["count"] for i in items} == {2022: 1, 2023: 1, 2024: 2}

    def test_null_year_excluded_from_by_year_but_counted_separately(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        _make_publication(db_session, year=2024)
        _make_publication(db_session, year=None)
        _make_publication(db_session, year=None)
        resp = c.get(CHARTS_URL)
        body = resp.json()
        assert body["publications_total_with_year"] == 1
        assert body["publications_total_without_year"] == 2
        assert all(i["year"] is not None for i in body["publications_by_year"])

    def test_future_year_in_source_data_is_not_filtered(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        _make_publication(db_session, year=2099)
        resp = c.get(CHARTS_URL)
        items = resp.json()["publications_by_year"]
        assert {i["year"]: i["count"] for i in items} == {2099: 1}

    def test_sum_of_groups_matches_total_publications_count(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        _make_publication(db_session, year=2020)
        _make_publication(db_session, year=2021)
        _make_publication(db_session, year=2021)
        resp = c.get(CHARTS_URL)
        body = resp.json()
        total_from_groups = sum(i["count"] for i in body["publications_by_year"])
        assert total_from_groups == body["publications_total_with_year"] == 3


# ---------------------------------------------------------------------------
# N. publications_by_document_type
# ---------------------------------------------------------------------------


class TestChartsPublicationsByDocumentType:
    def test_groups_by_document_type(self, db_session: Session, admin_client):
        c, _ = admin_client
        _make_publication(db_session, document_type="Article")
        _make_publication(db_session, document_type="Article")
        _make_publication(db_session, document_type="Conference Paper")
        resp = c.get(CHARTS_URL)
        items = resp.json()["publications_by_document_type"]
        by_type = {i["document_type"]: i["count"] for i in items}
        assert by_type["Article"] == 2
        assert by_type["Conference Paper"] == 1

    def test_null_document_type_grouped_as_unspecified(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        _make_publication(db_session, document_type=None)
        _make_publication(db_session, document_type=None)
        resp = c.get(CHARTS_URL)
        items = resp.json()["publications_by_document_type"]
        by_type = {i["document_type"]: i["count"] for i in items}
        assert by_type["UNSPECIFIED"] == 2

    def test_does_not_invent_document_types_not_in_db(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        _make_publication(db_session, document_type="Review")
        resp = c.get(CHARTS_URL)
        items = resp.json()["publications_by_document_type"]
        types_present = {i["document_type"] for i in items}
        assert types_present == {"Review"}


# ---------------------------------------------------------------------------
# O. affiliation_coverage — author *positions*, not unique authors
# ---------------------------------------------------------------------------


class TestChartsAffiliationCoverage:
    def test_total_author_positions_counts_rows_not_unique_authors(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        author = _make_scopus_author(db_session)
        pub1 = _make_publication(db_session)
        pub2 = _make_publication(db_session)
        # Same Scopus author appears at a position on two different publications
        _make_publication_author(db_session, pub1, author, author_order=1)
        _make_publication_author(db_session, pub2, author, author_order=2)
        resp = c.get(CHARTS_URL)
        cov = resp.json()["affiliation_coverage"]
        assert cov["total_author_positions"] == 2

    def test_position_with_resolution_but_absent_affiliation_counts_as_without(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        author = _make_scopus_author(db_session)
        pub = _make_publication(db_session)
        pa = _make_publication_author(db_session, pub, author)
        _make_affiliation_resolution(
            db_session, pa, link_status="CORROBORATED", affiliation_presence="ABSENT"
        )
        resp = c.get(CHARTS_URL)
        cov = resp.json()["affiliation_coverage"]
        assert cov["total_author_positions"] == 1
        assert cov["positions_with_affiliation"] == 0
        assert cov["positions_without_affiliation"] == 1

    def test_position_with_present_affiliation_counts_as_with(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        author = _make_scopus_author(db_session)
        pub = _make_publication(db_session)
        pa = _make_publication_author(db_session, pub, author)
        _make_affiliation_resolution(
            db_session, pa, link_status="CORROBORATED", affiliation_presence="PRESENT"
        )
        resp = c.get(CHARTS_URL)
        cov = resp.json()["affiliation_coverage"]
        assert cov["positions_with_affiliation"] == 1
        assert cov["positions_without_affiliation"] == 0

    def test_unresolved_position_counts_as_without_affiliation(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        author = _make_scopus_author(db_session)
        pub = _make_publication(db_session)
        pa = _make_publication_author(db_session, pub, author)
        _make_affiliation_resolution(db_session, pa, link_status="UNRESOLVED")
        resp = c.get(CHARTS_URL)
        cov = resp.json()["affiliation_coverage"]
        assert cov["positions_with_affiliation"] == 0
        assert cov["positions_without_affiliation"] == 1
        assert cov["by_link_status"]["UNRESOLVED"] == 1

    def test_position_never_attempted_counts_as_without_affiliation(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        author = _make_scopus_author(db_session)
        pub = _make_publication(db_session)
        _make_publication_author(db_session, pub, author)  # no resolution at all
        resp = c.get(CHARTS_URL)
        cov = resp.json()["affiliation_coverage"]
        assert cov["total_author_positions"] == 1
        assert cov["positions_with_affiliation"] == 0
        assert cov["positions_without_affiliation"] == 1
        assert sum(cov["by_link_status"].values()) == 0

    def test_position_counted_once_despite_multiple_source_resolutions(
        self, db_session: Session, admin_client
    ):
        """A position with resolutions from two source systems (e.g. OpenAlex
        AND Crossref) must still count once in with/without totals."""
        c, _ = admin_client
        author = _make_scopus_author(db_session)
        pub = _make_publication(db_session)
        pa = _make_publication_author(db_session, pub, author)
        _make_affiliation_resolution(
            db_session, pa, link_status="UNRESOLVED", source_system="crossref"
        )
        _make_affiliation_resolution(
            db_session,
            pa,
            link_status="CORROBORATED",
            affiliation_presence="PRESENT",
            source_system="openalex",
        )
        resp = c.get(CHARTS_URL)
        cov = resp.json()["affiliation_coverage"]
        assert cov["total_author_positions"] == 1
        assert cov["positions_with_affiliation"] == 1
        assert cov["positions_without_affiliation"] == 0
        # Best status wins: CORROBORATED (rank 2) beats UNRESOLVED (rank 1)
        assert cov["by_link_status"]["CORROBORATED"] == 1
        assert cov["by_link_status"]["UNRESOLVED"] == 0

    def test_verified_outranks_corroborated_for_same_position(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        author = _make_scopus_author(db_session)
        pub = _make_publication(db_session)
        pa = _make_publication_author(db_session, pub, author)
        _make_affiliation_resolution(
            db_session,
            pa,
            link_status="CORROBORATED",
            affiliation_presence="PRESENT",
            source_system="openalex",
        )
        _make_affiliation_resolution(
            db_session,
            pa,
            link_status="VERIFIED",
            affiliation_presence="PRESENT",
            source_system="orcid",
        )
        resp = c.get(CHARTS_URL)
        cov = resp.json()["affiliation_coverage"]
        assert cov["by_link_status"]["VERIFIED"] == 1
        assert cov["by_link_status"]["CORROBORATED"] == 0

    def test_without_affiliation_equals_total_minus_with(
        self, db_session: Session, admin_client
    ):
        c, _ = admin_client
        author = _make_scopus_author(db_session)
        pub = _make_publication(db_session)
        pa1 = _make_publication_author(db_session, pub, author, author_order=1)
        author2 = _make_scopus_author(db_session)
        pa2 = _make_publication_author(db_session, pub, author2, author_order=2)
        _make_affiliation_resolution(
            db_session, pa1, link_status="CORROBORATED", affiliation_presence="PRESENT"
        )
        # pa2 has no resolution at all
        resp = c.get(CHARTS_URL)
        cov = resp.json()["affiliation_coverage"]
        assert cov["total_author_positions"] == 2
        assert (
            cov["positions_with_affiliation"] + cov["positions_without_affiliation"]
            == cov["total_author_positions"]
        )


# ---------------------------------------------------------------------------
# P. Charts read-only safety
# ---------------------------------------------------------------------------


class TestChartsReadOnlySafety:
    def test_get_creates_zero_rows(self, db_session: Session, admin_client):
        c, _ = admin_client
        from sqlalchemy import select, func

        before = db_session.execute(
            select(func.count()).select_from(Publication)
        ).scalar_one()
        c.get(CHARTS_URL)
        after = db_session.execute(
            select(func.count()).select_from(Publication)
        ).scalar_one()
        assert after == before


# ---------------------------------------------------------------------------
# Q. Charts DB failure contract
# ---------------------------------------------------------------------------


class TestChartsDatabaseFailure:
    def test_db_failure_returns_503_with_code(self, admin_client):
        c, _ = admin_client
        from sqlalchemy.exc import OperationalError

        with patch(
            "app.api.v1.endpoints.dashboard.get_dashboard_charts",
            side_effect=OperationalError("conn", {}, Exception("down")),
        ):
            resp = c.get(CHARTS_URL)
        assert resp.status_code == 503
        assert resp.json().get("code") == "DATABASE_UNAVAILABLE"
