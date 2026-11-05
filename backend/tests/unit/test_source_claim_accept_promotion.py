"""ACCEPT of a SOURCE_CLAIM-only candidate on synthetic SQLite; no application DB."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
    LecturerScopusCandidateReview,
)
from app.models.governance import User
from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.services.candidate_evidence_read import serialize_review_evidence
from app.services.candidate_review_service import (
    AcceptCandidateCommand,
    CandidateReviewService,
    EvidencePromotionUnsupportedError,
    ReviewReasonRequiredForWeakEvidenceError,
)
from tests.source_staging_fixtures import make_sqlite_engine, sid

REASON = "Synthetic institution roster declares this pairing"
PAYLOAD = {"primary_scopus_id": sid(1)}
SOURCE_REFS = [{"kind": "synthetic_roster", "url": "https://example.invalid/roster"}]


def uid(n):
    return uuid.UUID(int=n)


@pytest.fixture
def db():
    engine = make_sqlite_engine()
    with Session(engine, autoflush=False) as session:
        now = datetime.now(UTC)
        session.add_all([
            Lecturer(id=uid(1), full_name="Synthetic lecturer",
                     full_name_normalized="synthetic lecturer",
                     email="gv1@example.invalid", version=1),
            ScopusAuthor(id=uid(2), scopus_id=sid(1), preferred_name="Different author"),
            User(id=uid(3), email="reviewer@example.invalid", password_hash="synthetic",
                 display_name="Synthetic reviewer", role="REVIEWER", is_active=True,
                 version=1, auth_version=1),
            CandidateGenerationRun(id=uid(4), rule_set_id="SYNTHETIC_ROSTER",
                                   rule_set_version="1", status="COMPLETED", source_state={},
                                   started_at=now, completed_at=now),
        ])
        session.flush()
        session.add(LecturerScopusCandidate(
            id=uid(5), lecturer_id=uid(1), scopus_author_id=uid(2), status="PENDING",
            first_seen_at=now, last_seen_at=now,
        ))
        session.flush()
        session.add(LecturerScopusCandidateObservation(
            id=uid(6), candidate_id=uid(5), generation_run_id=uid(4), observed_at=now,
            candidate_snapshot={}, observation_hash="b" * 64,
        ))
        session.flush()
        session.add(LecturerScopusCandidateEvidence(
            id=uid(7), observation_id=uid(6), evidence_kind="SOURCE_CLAIM",
            rule_id="SYNTHETIC_ROSTER", rule_version="1", payload=PAYLOAD,
            source_refs=SOURCE_REFS, evidence_fingerprint="c" * 64,
        ))
        session.commit()
        yield session
    engine.dispose()


def accept(db, *, reason):
    return CandidateReviewService(db).accept_candidate(AcceptCandidateCommand(
        candidate_id=uid(5), observation_id=uid(6), candidate_version=1,
        reviewer_user_id=uid(3), reason=reason,
    ))


def test_accept_promotes_source_claim_to_approved_id_without_counting_it_as_name(db):
    result = accept(db, reason=REASON)

    identity = db.get(LecturerScopusIdentity, result.resulting_identity_id)
    assert identity.status == "APPROVED"
    promoted, = db.scalars(select(IdentityEvidence)).all()
    assert promoted.identity_id == identity.id
    assert promoted.evidence_type == "APPROVED_ID"
    assert promoted.features == PAYLOAD
    assert promoted.source_refs == SOURCE_REFS
    assert promoted.confidence_score is None
    assert (result.name_evidence_promoted, result.publication_evidence_promoted) == (0, 0)
    assert db.get(LecturerScopusCandidate, uid(5)).status == "ACCEPTED"
    assert db.scalar(select(LecturerScopusCandidateReview)).reason == REASON


def test_d2_still_requires_a_reason_and_writes_nothing_without_one(db):
    with pytest.raises(ReviewReasonRequiredForWeakEvidenceError) as exc:
        accept(db, reason=None)

    assert "NAME_EVIDENCE_ONLY" in exc.value.triggers
    assert db.scalars(select(LecturerScopusIdentity)).all() == []
    assert db.scalars(select(IdentityEvidence)).all() == []
    assert db.get(LecturerScopusCandidate, uid(5)).status == "PENDING"


def test_reviewers_still_cannot_read_source_claim_evidence(db):
    rows = db.scalars(select(LecturerScopusCandidateEvidence)).all()

    with pytest.raises(APIError) as exc:
        serialize_review_evidence(rows, {})

    assert exc.value.code == "SOURCE_CLAIM_REVIEW_INACTIVE"


def test_other_unknown_kinds_still_fail_closed_on_promotion(db):
    with pytest.raises(EvidencePromotionUnsupportedError):
        CandidateReviewService(db)._promote_candidate_evidence_to_identity(
            uid(99), (SimpleNamespace(evidence_kind="ORCID_EXACT"),), "1",
        )
