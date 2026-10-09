"""Task 09: read-only warning when one Scopus Author ID is proposed for several lecturers."""

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
from app.services.matching.candidate_persistence import (
    CandidatePersistenceService,
    GenerationRunSpec,
)
from app.services.matching.candidate_types import CandidateEvidence, EnrichedLecturerScopusCandidate

SOURCE_STATE = {
    "schema_version": 1,
    "rules": {
        "candidate_generator": {"rule_set_id": "c", "rule_set_version": "M2.7A-2", "rule_ids": []},
        "publication_enrichment": {"rule_set_id": "p", "rule_set_version": "M2.7A-5", "rule_ids": []},
    },
    "inputs": {},
}


def _candidate(lecturer: Lecturer, author: ScopusAuthor) -> EnrichedLecturerScopusCandidate:
    evidence = CandidateEvidence(
        rule_id="RULE_EXACT_N0",
        lecturer_source_value=lecturer.full_name,
        lecturer_comparison_value=lecturer.full_name_normalized,
        scopus_surface_type="PREFERRED_NAME",
        scopus_surface_value=author.preferred_name,
        scopus_comparison_value=author.preferred_name.lower(),
    )
    return EnrichedLecturerScopusCandidate(
        lecturer_id=lecturer.id,
        scopus_author_id=author.id,
        scopus_id=author.scopus_id,
        preferred_name=author.preferred_name,
        evidence=(evidence,),
        publication_evidence=(),
    )


@pytest.fixture
def seeded(isolated_db_engine):
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL database available.")
    Base.metadata.create_all(bind=isolated_db_engine)
    with Session(isolated_db_engine) as s:
        for table in (
            "lecturer_scopus_candidate_reviews", "identity_evidence", "lecturer_scopus_identities",
            "lecturer_scopus_candidate_evidence", "lecturer_scopus_candidate_observations",
            "lecturer_scopus_candidates", "candidate_generation_runs", "scopus_authors", "lecturers",
        ):
            s.execute(text(f"TRUNCATE {table} CASCADE"))
        a = Lecturer(full_name="Nguyen Van A", full_name_normalized="nguyen van a")
        b = Lecturer(full_name="Nguyen Van B", full_name_normalized="nguyen van b")
        c = Lecturer(full_name="Tran Thi C", full_name_normalized="tran thi c")
        shared = ScopusAuthor(scopus_id="10000000001", preferred_name="Nguyen V")
        solo = ScopusAuthor(scopus_id="10000000002", preferred_name="Tran Thi C")
        s.add_all([a, b, c, shared, solo])
        s.commit()
        pairs = [(a, shared), (b, shared), (c, solo)]
        candidates = [_candidate(lecturer, author) for lecturer, author in pairs]
        ids = {"shared_a": a.id, "shared_b": b.id, "solo": c.id}
    with Session(isolated_db_engine) as writer:
        CandidatePersistenceService(writer).persist_generation(
            GenerationRunSpec(run_id=uuid.uuid4(), source_state=SOURCE_STATE), candidates
        )
    now = datetime.now(UTC)
    admin = User(id=uuid.uuid4(), email="admin@review.test", password_hash="x", display_name="Admin", role="ADMIN",
                 is_active=True, version=1, auth_version=1, created_at=now, updated_at=now)

    def _session():
        with Session(isolated_db_engine) as session:
            yield session

    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_session] = _session
    with TestClient(app) as client:
        yield client, ids
    app.dependency_overrides.clear()


def test_queue_flags_shared_scopus_author_without_changing_is_ambiguous(seeded) -> None:
    client, ids = seeded
    body = client.get("/api/v1/reviews/candidates?status=PENDING&page_size=100").json()
    by_lecturer = {i["lecturer"]["id"]: i for i in body["items"]}
    shared_a, shared_b, solo = (by_lecturer[str(ids[k])] for k in ("shared_a", "shared_b", "solo"))
    for item in (shared_a, shared_b):
        assert item["candidate_count_for_scopus_author"] == 2 and item["is_shared_scopus_author"] is True
    assert solo["candidate_count_for_scopus_author"] == 1 and solo["is_shared_scopus_author"] is False
    # is_ambiguous keeps its original meaning: >1 candidate for the SAME LECTURER only.
    assert all(i["is_ambiguous"] is False and i["candidate_count_for_lecturer"] == 1 for i in body["items"])
    assert body["total"] == 3
    # existing ambiguity filter is unaffected by the new flag
    assert client.get("/api/v1/reviews/candidates?ambiguity=ambiguous").json()["total"] == 0
    assert client.get("/api/v1/reviews/candidates?ambiguity=unique").json()["total"] == 3


def test_detail_exposes_shared_scopus_author_warning(seeded) -> None:
    client, ids = seeded
    items = client.get("/api/v1/reviews/candidates?page_size=100").json()["items"]
    shared = next(i for i in items if i["lecturer"]["id"] == str(ids["shared_a"]))
    solo = next(i for i in items if i["lecturer"]["id"] == str(ids["solo"]))
    d = client.get(f"/api/v1/reviews/candidates/{shared['candidate_id']}").json()["ambiguity"]
    assert d["candidate_count_for_scopus_author"] == 2 and d["is_shared_scopus_author"] is True
    assert d["is_ambiguous"] is False and d["candidate_count_for_lecturer"] == 1
    d = client.get(f"/api/v1/reviews/candidates/{solo['candidate_id']}").json()["ambiguity"]
    assert d["candidate_count_for_scopus_author"] == 1 and d["is_shared_scopus_author"] is False
