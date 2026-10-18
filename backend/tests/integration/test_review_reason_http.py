"""D-2 (PROMPT 09): HTTP contract for reason requirements, on real persisted candidates.

Reuses the name-evidence-only fixture from test_review_shared_author_warning
(two lecturers share one Scopus author; a third lecturer has a unique author).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.base import Base
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.services.matching.candidate_persistence import CandidatePersistenceService, GenerationRunSpec
from tests.integration.test_review_shared_author_warning import SOURCE_STATE, _candidate


@pytest.fixture
def seeded(isolated_db_engine):
    """Name-evidence-only candidates (two lecturers share one author) and a persisted REVIEWER."""
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL database available.")
    Base.metadata.create_all(bind=isolated_db_engine)
    with Session(isolated_db_engine) as s:
        for table in (
            "lecturer_scopus_candidate_reviews", "identity_evidence", "lecturer_scopus_identities",
            "lecturer_scopus_candidate_evidence", "lecturer_scopus_candidate_observations",
            "lecturer_scopus_candidates", "candidate_generation_runs", "scopus_authors", "lecturers",
            "audit_events", "user_notifications", "users",
        ):
            s.execute(text(f"TRUNCATE {table} CASCADE"))
        a = Lecturer(full_name="Nguyen Van A", full_name_normalized="nguyen van a")
        b = Lecturer(full_name="Nguyen Van B", full_name_normalized="nguyen van b")
        c = Lecturer(full_name="Tran Thi C", full_name_normalized="tran thi c")
        shared = ScopusAuthor(scopus_id="10000000001", preferred_name="Nguyen V")
        solo = ScopusAuthor(scopus_id="10000000002", preferred_name="Tran Thi C")
        now = datetime.now(UTC)
        fields = dict(id=uuid.uuid4(), email="reviewer@reason.test", password_hash="x" * 40, display_name="Reviewer",
                      role="REVIEWER", is_active=True, version=1, auth_version=1, created_at=now, updated_at=now)
        reviewer = User(**fields)  # transient copy used by the auth override
        s.add_all([a, b, c, shared, solo, User(**fields)])
        s.commit()
        candidates = [_candidate(lecturer, author) for lecturer, author in [(a, shared), (b, shared), (c, solo)]]
        ids = {"shared_a": a.id, "shared_b": b.id, "solo": c.id}
    with Session(isolated_db_engine) as writer:
        CandidatePersistenceService(writer).persist_generation(
            GenerationRunSpec(run_id=uuid.uuid4(), source_state=SOURCE_STATE), candidates
        )

    def _session():
        with Session(isolated_db_engine) as session:
            yield session

    app.dependency_overrides[get_current_user] = lambda: reviewer
    app.dependency_overrides[get_session] = _session
    with TestClient(app) as client:
        yield client, ids
    app.dependency_overrides.clear()


def _detail(client, lecturer_id: str) -> dict:
    items = client.get("/api/v1/reviews/candidates?page_size=100").json()["items"]
    item = next(i for i in items if i["lecturer"]["id"] == lecturer_id)
    return client.get(f"/api/v1/reviews/candidates/{item['candidate_id']}").json()


def _decide(client, detail: dict, action: str, reason=None):
    body = {"observation_id": detail["current_observation"]["observation_id"],
            "candidate_version": detail["candidate_version"], "action": action}
    if reason is not None:
        body["reason"] = reason
    return client.post(f"/api/v1/reviews/candidates/{detail['candidate_id']}/reviews", json=body)


def test_detail_exposes_server_computed_review_policy(seeded) -> None:
    client, ids = seeded
    solo = _detail(client, str(ids["solo"]))
    assert solo["review_policy"] == {"accept_reason_required": True, "accept_reason_triggers": ["NAME_EVIDENCE_ONLY"],
                                     "reject_reason_required": True}
    shared = _detail(client, str(ids["shared_a"]))
    assert shared["review_policy"]["accept_reason_triggers"] == ["NAME_EVIDENCE_ONLY", "SHARED_SCOPUS_AUTHOR"]


def test_accept_weak_evidence_without_reason_is_422_with_stable_envelope(seeded) -> None:
    client, ids = seeded
    detail = _detail(client, str(ids["solo"]))
    for reason in (None, "", "   "):
        response = _decide(client, detail, "ACCEPT", reason)
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] == "REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE"
        assert body["reason_triggers"] == ["NAME_EVIDENCE_ONLY"]
        assert set(body) == {"detail", "code", "reason_triggers"}
    # nothing was written: still PENDING with the same version
    again = _detail(client, str(ids["solo"]))
    assert again["candidate_status"] == "PENDING" and again["candidate_version"] == detail["candidate_version"]


def test_accept_with_reason_succeeds_and_replay_is_idempotent(seeded) -> None:
    client, ids = seeded
    detail = _detail(client, str(ids["solo"]))
    first = _decide(client, detail, "ACCEPT", "Đối chiếu trang hồ sơ ICTU")
    assert first.status_code == 200, first.text
    assert first.json()["idempotent"] is False and first.json()["candidate_status"] == "ACCEPTED"
    replay = _decide(client, detail, "ACCEPT", "Đối chiếu trang hồ sơ ICTU")
    assert replay.status_code == 200 and replay.json()["idempotent"] is True
    assert replay.json()["review_id"] == first.json()["review_id"]
    assert replay.json()["resulting_identity_id"] == first.json()["resulting_identity_id"]


def test_reject_without_reason_keeps_existing_contract(seeded) -> None:
    client, ids = seeded
    detail = _detail(client, str(ids["shared_a"]))
    response = _decide(client, detail, "REJECT", "  ")
    assert response.status_code == 422 and response.json()["code"] == "INVALID_REVIEW_REASON"
    ok = _decide(client, detail, "REJECT", "Khác đơn vị công tác")
    assert ok.status_code == 200 and ok.json()["candidate_status"] == "REJECTED"
