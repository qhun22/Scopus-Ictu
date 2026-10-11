"""`/reviews/context`: which precondition of the review queue is missing (isolated schema per test)."""

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
from app.models.candidate import CandidateGenerationRun
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.services.matching.candidate_persistence import CandidatePersistenceService, GenerationRunSpec
from app.services.matching.candidate_types import CandidateEvidence, EnrichedLecturerScopusCandidate

SOURCE_STATE = {
    "schema_version": 1,
    "rules": {
        "candidate_generator": {"rule_set_id": "c", "rule_set_version": "M2.7A-2", "rule_ids": []},
        "publication_enrichment": {"rule_set_id": "p", "rule_set_version": "M2.7A-5", "rule_ids": []},
    },
    "inputs": {},
}


@pytest.fixture
def db() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    if make_url(url).database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("never target an acceptance database")
    schema = f"test_rev_ctx_{uuid.uuid4().hex}"
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
def client(db: Session) -> Generator[TestClient, None, None]:
    now = datetime.now(UTC)
    reviewer = User(id=uuid.uuid4(), email="r@ctx.test", password_hash="x", display_name="R", role="REVIEWER",
                    is_active=True, version=1, auth_version=1, created_at=now, updated_at=now)
    app.dependency_overrides[get_current_user] = lambda: reviewer
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _context(client: TestClient) -> dict:
    response = client.get("/api/v1/reviews/context")
    assert response.status_code == 200, response.text
    return response.json()


def test_state_walks_through_the_four_reasons(client: TestClient, db: Session) -> None:
    body = _context(client)
    assert body["state"] == "NO_LECTURERS" and body["lecturers_total"] == 0
    assert body["candidates_by_status"] == {"PENDING": 0, "ACCEPTED": 0, "REJECTED": 0, "SUPERSEDED": 0}

    lecturer = Lecturer(full_name="Nguyen Van A", full_name_normalized="nguyen van a")
    author = ScopusAuthor(scopus_id="10000000001", preferred_name="Nguyen Van A")
    db.add_all([lecturer, author])
    db.commit()
    body = _context(client)
    assert body["state"] == "NO_CANDIDATE_RUN" and body["lecturers_total"] == 1 and body["scopus_authors_total"] == 1

    # A completed run that found nothing.
    with Session(db.get_bind()) as writer:
        CandidatePersistenceService(writer).persist_generation(
            GenerationRunSpec(run_id=uuid.uuid4(), source_state=SOURCE_STATE), []
        )
    assert db.query(CandidateGenerationRun).filter_by(status="COMPLETED").count() == 1
    body = _context(client)
    assert body["state"] == "RUN_WITHOUT_CANDIDATES" and body["completed_generation_runs"] == 1

    evidence = CandidateEvidence(
        rule_id="RULE_EXACT_N0", lecturer_source_value=lecturer.full_name,
        lecturer_comparison_value=lecturer.full_name_normalized,
        scopus_surface_type="PREFERRED_NAME", scopus_surface_value=author.preferred_name,
        scopus_comparison_value=author.preferred_name.lower(),
    )
    candidate = EnrichedLecturerScopusCandidate(
        lecturer_id=lecturer.id, scopus_author_id=author.id, scopus_id=author.scopus_id,
        preferred_name=author.preferred_name, evidence=(evidence,), publication_evidence=(),
    )
    with Session(db.get_bind()) as writer:
        CandidatePersistenceService(writer).persist_generation(
            GenerationRunSpec(run_id=uuid.uuid4(), source_state=SOURCE_STATE), [candidate]
        )
    body = _context(client)
    assert body["state"] == "HAS_CANDIDATES" and body["candidates_by_status"]["PENDING"] == 1


def test_context_is_reviewer_or_admin_only(client: TestClient) -> None:
    now = datetime.now(UTC)
    lecturer = User(id=uuid.uuid4(), email="l@ctx.test", password_hash="x", display_name="L", role="LECTURER",
                    lecturer_id=None, is_active=True, version=1, auth_version=1, created_at=now, updated_at=now)
    app.dependency_overrides[get_current_user] = lambda: lecturer
    assert client.get("/api/v1/reviews/context").status_code == 403
