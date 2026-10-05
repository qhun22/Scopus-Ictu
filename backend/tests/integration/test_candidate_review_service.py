"""Integration tests for M2.7B-4 candidate review service.

These tests use the isolated PostgreSQL test database (scopus_m12_test) and
create all required schema/rows via SQLAlchemy ORM.  Each test starts from a
clean schema state for the relevant tables.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit import AuditEvent
from app.models.base import Base
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
from app.services.candidate_review_service import (
    AcceptCandidateCommand,
    AcceptResult,
    CandidateAlreadyDecidedError,
    CandidateNotFoundError,
    CandidateReviewService,
    EvidencePromotionUnsupportedError,
    InvalidReviewReasonError,
    ObservationCandidateMismatchError,
    ObservationNotFoundError,
    PreexistingIdentityConflictError,
    RejectCandidateCommand,
    ReviewerNotAuthorizedError,
    ReviewerNotFoundError,
    ScopusAuthorAlreadyApprovedError,
    StaleCandidateObservationError,
    StaleCandidateVersionError,
)


# ---------------------------------------------------------------------------
# Engine / session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def review_engine() -> Engine:
    """Provide an isolated test engine for the review tests."""
    import os
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL must point to an isolated PostgreSQL database")
    engine = create_engine(url, pool_pre_ping=True, future=True)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session_factory(review_engine: Engine) -> sessionmaker:
    """Return a sessionmaker bound to the review engine."""
    return sessionmaker(
        autocommit=False, autoflush=False, bind=review_engine
    )


@pytest.fixture
def review_session(
    session_factory: sessionmaker,
) -> Generator[Session, None, None]:
    """Yield a session with all relevant tables truncated."""
    session = session_factory()
    try:
        # Truncate in dependency order.  Use TRUNCATE ... CASCADE to safely
        # handle cross-table FK references (user_notifications, etc).
        from sqlalchemy import text as _text
        for model in (
            LecturerScopusCandidateReview,
            IdentityEvidence,
            LecturerScopusIdentity,
            LecturerScopusCandidateEvidence,
            LecturerScopusCandidateObservation,
            LecturerScopusCandidate,
            AuditEvent,
            CandidateGenerationRun,
            "user_notifications",
            User,
            ScopusAuthor,
            Lecturer,
        ):
            if isinstance(model, str):
                session.execute(_text(f"TRUNCATE {model} CASCADE"))
            else:
                session.execute(_text(
                    f"TRUNCATE {model.__table__.name} CASCADE"
                ))
        session.commit()
        yield session
    finally:
        session.rollback()
        for model in (
            LecturerScopusCandidateReview,
            IdentityEvidence,
            LecturerScopusIdentity,
            LecturerScopusCandidateEvidence,
            LecturerScopusCandidateObservation,
            LecturerScopusCandidate,
            AuditEvent,
            CandidateGenerationRun,
            "user_notifications",
            User,
            ScopusAuthor,
            Lecturer,
        ):
            if isinstance(model, str):
                session.execute(_text(f"TRUNCATE {model} CASCADE"))
            else:
                session.execute(_text(
                    f"TRUNCATE {model.__table__.name} CASCADE"
                ))
        session.commit()
        session.close()


# ---------------------------------------------------------------------------
# Fixtures for users, lecturers, authors, candidates
# ---------------------------------------------------------------------------

def _make_user(
    session: Session,
    *,
    role: str = "REVIEWER",
    is_active: bool = True,
    lecturer_id: uuid.UUID | None = None,
) -> User:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"user-{uid.hex[:8]}@test.local",
        password_hash="x" * 40,  # placeholder, never used in review tests
        display_name=f"Test {role} {uid.hex[:6]}",
        role=role,
        lecturer_id=lecturer_id,
        is_active=is_active,
        version=1,
        auth_version=1,
    )
    session.add(user)
    session.flush()
    return user


def _make_lecturer(session: Session, *, full_name: str = "TS. Test Lecturer") -> Lecturer:
    lect = Lecturer(
        full_name=full_name,
        full_name_normalized=full_name.lower(),
    )
    session.add(lect)
    session.flush()
    return lect


def _make_author(
    session: Session, *, preferred_name: str = "Test Author"
) -> ScopusAuthor:
    scopus_id = f"{uuid.uuid4().int % 10**11:011d}"
    author = ScopusAuthor(
        scopus_id=scopus_id,
        preferred_name=preferred_name,
    )
    session.add(author)
    session.flush()
    return author


def _make_run(
    session: Session,
    *,
    status: str = "COMPLETED",
    rule_set_version: str = "M2.7A-2+M2.7A-5",
    started_at: datetime | None = None,
    run_id: uuid.UUID | None = None,
) -> CandidateGenerationRun:
    rid = run_id or uuid.uuid4()
    if started_at is None:
        started_at = datetime.now(UTC)
    run = CandidateGenerationRun(
        id=rid,
        rule_set_id="M2.7A_CANDIDATE_EVIDENCE",
        rule_set_version=rule_set_version,
        source_state={"schema_version": 1, "rules": {}, "inputs": {}},
        started_at=started_at,
        completed_at=(
            datetime.now(UTC) if status in ("COMPLETED", "FAILED") else None
        ),
        status=status,
        version=1,
    )
    session.add(run)
    session.flush()
    return run


def _run_concurrently(
    session_factory: sessionmaker,
    commands: tuple[tuple[str, AcceptCandidateCommand | RejectCandidateCommand], ...],
) -> list[tuple[str, object | BaseException]]:
    """Run review commands in independent sessions at the same barrier."""
    barrier = threading.Barrier(len(commands))
    outcomes: list[tuple[str, object | BaseException]] = []
    outcomes_lock = threading.Lock()

    def worker(
        action: str, command: AcceptCandidateCommand | RejectCandidateCommand
    ) -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=10)
            service = CandidateReviewService(session)
            result = (
                service.accept_candidate(command)
                if action == "ACCEPT"
                else service.reject_candidate(command)
            )
            outcome: object | BaseException = result
        except BaseException as exc:  # capture each independent transaction outcome
            outcome = exc
        finally:
            session.close()
        with outcomes_lock:
            outcomes.append((action, outcome))

    threads = [
        threading.Thread(target=worker, args=command, daemon=True)
        for command in commands
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive(), "concurrent review worker did not finish"
    assert len(outcomes) == len(commands)
    return outcomes


def _make_candidate(
    session: Session,
    *,
    lecturer: Lecturer,
    author: ScopusAuthor,
) -> LecturerScopusCandidate:
    cand = LecturerScopusCandidate(
        lecturer_id=lecturer.id,
        scopus_author_id=author.id,
        status="PENDING",
    )
    session.add(cand)
    session.flush()
    return cand


def _make_observation(
    session: Session,
    *,
    candidate: LecturerScopusCandidate,
    run: CandidateGenerationRun,
    evidence: list[dict[str, Any]] | None = None,
) -> LecturerScopusCandidateObservation:
    """Create an observation with the given evidence list.

    Each evidence dict must have: kind, rule_id, rule_version, payload,
    source_refs, and a derived evidence_fingerprint.
    """
    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "candidate_id": str(candidate.id),
        "lecturer_id": str(candidate.lecturer_id),
        "scopus_author_id": str(candidate.scopus_author_id),
        "evidence": evidence or [],
    }
    snapshot_json = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    observation_hash = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()

    obs = LecturerScopusCandidateObservation(
        candidate_id=candidate.id,
        generation_run_id=run.id,
        observed_at=datetime.now(UTC),
        candidate_snapshot=snapshot,
        observation_hash=observation_hash,
    )
    session.add(obs)
    session.flush()

    if evidence:
        for ev in evidence:
            payload = ev.get("payload", {})
            source_refs = ev.get("source_refs", [])
            fingerprint_seed = {
                "evidence_kind": ev["kind"],
                "rule_id": ev["rule_id"],
                "rule_version": ev["rule_version"],
                "payload": payload,
                "source_refs": source_refs,
            }
            fingerprint = hashlib.sha256(
                json.dumps(
                    fingerprint_seed, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            ce = LecturerScopusCandidateEvidence(
                observation_id=obs.id,
                evidence_kind=ev["kind"],
                rule_id=ev["rule_id"],
                rule_version=ev["rule_version"],
                payload=payload,
                source_refs=source_refs,
                evidence_fingerprint=fingerprint,
            )
            session.add(ce)
        session.flush()
    return obs


def _name_evidence(reconciliation: str = "NAME_EXACT") -> dict[str, Any]:
    return {
        "kind": "NAME",
        "rule_id": "RULE_EXACT_N0",
        "rule_version": "M2.7A-2",
        "payload": {
            "lecturer_source_value": "TS. Test Lecturer",
            "lecturer_comparison_value": "ts. test lecturer",
            "scopus_surface_type": "PREFERRED_NAME",
            "scopus_surface_value": "Test Author",
            "scopus_comparison_value": "test author",
        },
        "source_refs": [],
    }


def _publication_evidence(
    *, reconciliation: str = "DOI_EXACT", canonical_publication_id: uuid.UUID | None = None
) -> dict[str, Any]:
    return {
        "kind": "PUBLICATION",
        "rule_id": "RULE_KNOWN_PUBLICATION_DOI_EXACT",
        "rule_version": "M2.7A-5",
        "payload": {
            "lecturer_id": "00000000-0000-0000-0000-000000000000",
            "candidate_scopus_author_id": "00000000-0000-0000-0000-000000000000",
            "known_publication_doi_normalized": "10.1000/example",
            "known_publication_title_normalized": "an example",
            "canonical_publication_eid": "2-s2.0-123",
            "canonical_publication_doi": "10.1000/example",
            "canonical_publication_title": "An example",
            "reconciliation": reconciliation,
        },
        "source_refs": [
            {
                "kind": "lecturer_known_publication",
                "id": str(uuid.uuid4()),
            },
            {
                "kind": "lecturer_source_snapshot",
                "id": str(uuid.uuid4()),
            },
            {
                "kind": "publication",
                "id": str(canonical_publication_id or uuid.uuid4()),
            },
        ],
    }


# ---------------------------------------------------------------------------
# Pre-built fixture: completed generation with one PENDING candidate
# ---------------------------------------------------------------------------

@pytest.fixture
def ready_fixture(review_session: Session) -> dict[str, Any]:
    """Build a complete, reviewable candidate setup."""
    lecturer = _make_lecturer(review_session)
    author = _make_author(review_session)
    run = _make_run(review_session, status="COMPLETED")
    candidate = _make_candidate(
        review_session, lecturer=lecturer, author=author
    )
    obs = _make_observation(
        review_session,
        candidate=candidate,
        run=run,
        evidence=[_name_evidence(), _publication_evidence()],
    )
    review_session.commit()

    reviewer = _make_user(review_session, role="REVIEWER")

    return {
        "lecturer_id": lecturer.id,
        "author_id": author.id,
        "candidate": candidate,
        "observation": obs,
        "run": run,
        "reviewer": reviewer,
    }


# ---------------------------------------------------------------------------
# 29. ACCEPT HAPPY PATH
# ---------------------------------------------------------------------------

def test_accept_happy_path(ready_fixture: dict[str, Any], review_session: Session) -> None:
    """ACCEPT a pending candidate with name + publication evidence."""
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    # Pre-conditions
    assert cand.status == "PENDING"
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")) == 0
    assert review_session.scalar(text("SELECT count(*) FROM identity_evidence")) == 0
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_candidate_reviews")) == 0
    assert review_session.scalar(text("SELECT count(*) FROM audit_events")) == 0
    assert review_session.scalar(text("SELECT count(*) FROM mapping_reviews")) == 0

    service = CandidateReviewService(review_session)
    result = service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
        )
    )

    # Result checks
    assert result.action == "ACCEPT"
    assert result.idempotent is False
    assert result.candidate_status == "ACCEPTED"
    assert result.candidate_version == cand.version  # cand was bumped in-place
    assert result.resulting_identity_id is not None
    assert result.name_evidence_promoted == 1
    assert result.publication_evidence_promoted == 1

    # DB state checks
    new_cand = review_session.get(LecturerScopusCandidate, cand.id)
    assert new_cand is not None and new_cand.status == "ACCEPTED"

    identity = review_session.get(LecturerScopusIdentity, result.resulting_identity_id)
    assert identity is not None
    assert identity.status == "APPROVED"
    assert identity.lecturer_id == cand.lecturer_id
    assert identity.scopus_author_id == cand.scopus_author_id

    # IdentityEvidence: name + publication
    iev = review_session.scalars(
        select(IdentityEvidence).where(IdentityEvidence.identity_id == identity.id)
    ).all()
    assert len(iev) == 2
    for e in iev:
        assert e.confidence_score is None  # never fabricated
        assert e.direction == "SUPPORTS"
    types = {e.evidence_type for e in iev}
    assert types == {"NAME_SIMILARITY", "DOI_EXACT"}

    # CandidateReview
    reviews = review_session.scalars(
        select(LecturerScopusCandidateReview).where(
            LecturerScopusCandidateReview.candidate_id == cand.id
        )
    ).all()
    assert len(reviews) == 1
    r = reviews[0]
    assert r.action == "ACCEPT"
    assert r.from_status == "PENDING"
    assert r.to_status == "ACCEPTED"
    assert r.reviewer_user_id == reviewer.id
    assert r.resulting_identity_id == identity.id
    assert r.observation_id == obs.id
    assert r.candidate_version == 1
    assert r.evidence_snapshot["candidate_id"] == str(cand.id)
    assert r.evidence_snapshot["observation_id"] == str(obs.id)

    # Audit events
    audit_actions = [
        row[0] for row in review_session.execute(
            text("SELECT action FROM audit_events WHERE entity_type = 'lecturer_scopus_candidate' OR entity_type = 'lecturer_scopus_identity' ORDER BY created_at")
        )
    ]
    assert "CANDIDATE_ACCEPTED" in audit_actions
    assert "IDENTITY_CREATED_FROM_CANDIDATE" in audit_actions

    # No MappingReview
    assert review_session.scalar(text("SELECT count(*) FROM mapping_reviews")) == 0


# ---------------------------------------------------------------------------
# 30. REJECT HAPPY PATH
# ---------------------------------------------------------------------------

def test_reject_happy_path(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    result = service.reject_candidate(
        RejectCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
            reason="Insufficient evidence",
        )
    )

    assert result.action == "REJECT"
    assert result.idempotent is False
    assert result.candidate_status == "REJECTED"
    assert result.candidate_version == cand.version  # bumped in-place
    assert result.resulting_identity_id is None

    new_cand = review_session.get(LecturerScopusCandidate, cand.id)
    assert new_cand is not None and new_cand.status == "REJECTED"

    # 0 identities, 0 IdentityEvidence, 0 MappingReview
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")) == 0
    assert review_session.scalar(text("SELECT count(*) FROM identity_evidence")) == 0
    assert review_session.scalar(text("SELECT count(*) FROM mapping_reviews")) == 0

    # 1 review
    reviews = review_session.scalars(
        select(LecturerScopusCandidateReview).where(
            LecturerScopusCandidateReview.candidate_id == cand.id
        )
    ).all()
    assert len(reviews) == 1
    r = reviews[0]
    assert r.action == "REJECT"
    assert r.to_status == "REJECTED"
    assert r.reason == "Insufficient evidence"
    assert r.evidence_snapshot["candidate_id"] == str(cand.id)
    assert r.resulting_identity_id is None

    # 1 audit event
    assert review_session.scalar(text("SELECT count(*) FROM audit_events")) == 1
    ae = review_session.scalar(select(AuditEvent))
    assert ae is not None
    assert ae.action == "CANDIDATE_REJECTED"
    assert ae.actor_type == "USER"
    assert ae.actor_user_id == reviewer.id


# ---------------------------------------------------------------------------
# 31. SAME ACCEPT RETRY (idempotent)
# ---------------------------------------------------------------------------

def test_accept_retry_is_idempotent(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    first = service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
        )
    )
    second = service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=first.candidate_version,
            reviewer_user_id=reviewer.id,
        )
    )
    assert second.idempotent is True
    assert second.resulting_identity_id == first.resulting_identity_id
    assert second.review_id == first.review_id

    # No duplicate rows
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_candidate_reviews")) == 1
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")) == 1
    assert review_session.scalar(text("SELECT count(*) FROM identity_evidence")) == 2  # 1 name + 1 publication
    assert review_session.scalar(text("SELECT count(*) FROM audit_events")) == 2  # 1 candidate + 1 identity


# ---------------------------------------------------------------------------
# 32. SAME REJECT RETRY (idempotent)
# ---------------------------------------------------------------------------

def test_reject_retry_is_idempotent(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    first = service.reject_candidate(
        RejectCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
            reason="not enough",
        )
    )
    second = service.reject_candidate(
        RejectCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=first.candidate_version,
            reviewer_user_id=reviewer.id,
            reason="not enough",
        )
    )
    assert second.idempotent is True
    assert second.review_id == first.review_id
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_candidate_reviews")) == 1
    assert review_session.scalar(text("SELECT count(*) FROM audit_events")) == 1


# ---------------------------------------------------------------------------
# 33. OPPOSITE DECISION CONFLICT
# ---------------------------------------------------------------------------

def test_accept_then_reject_conflicts(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
        )
    )
    with pytest.raises(CandidateAlreadyDecidedError):
        service.reject_candidate(
            RejectCandidateCommand(
                candidate_id=cand.id,
                observation_id=obs.id,
                candidate_version=2,
                reviewer_user_id=reviewer.id,
                reason="trying to flip",
            )
        )
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_candidate_reviews")) == 1


def test_reject_then_accept_conflicts(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    service.reject_candidate(
        RejectCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
            reason="no",
        )
    )
    with pytest.raises(CandidateAlreadyDecidedError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand.id,
                observation_id=obs.id,
                candidate_version=2,
                reviewer_user_id=reviewer.id,
            )
        )


# ---------------------------------------------------------------------------
# 34. STALE VERSION
# ---------------------------------------------------------------------------

def test_stale_version_fails_closed(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    # Bump candidate version legitimately
    cand.version = 2
    review_session.commit()

    service = CandidateReviewService(review_session)
    with pytest.raises(StaleCandidateVersionError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand.id,
                observation_id=obs.id,
                candidate_version=1,  # stale
                reviewer_user_id=reviewer.id,
            )
        )
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_candidate_reviews")) == 0


# ---------------------------------------------------------------------------
# 35. STALE OBSERVATION
# ---------------------------------------------------------------------------

def test_stale_observation_fails_closed(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    old_obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    # Create a newer completed generation with a newer observation
    new_run = _make_run(review_session, status="COMPLETED")
    new_obs = _make_observation(
        review_session,
        candidate=cand,
        run=new_run,
        evidence=[_name_evidence()],
    )
    review_session.commit()

    service = CandidateReviewService(review_session)
    with pytest.raises(StaleCandidateObservationError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand.id,
                observation_id=old_obs.id,  # stale
                candidate_version=cand.version,
                reviewer_user_id=reviewer.id,
            )
        )
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_candidate_reviews")) == 0


# ---------------------------------------------------------------------------
# 36. OBSERVATION OWNERSHIP
# ---------------------------------------------------------------------------

def test_observation_candidate_mismatch(
    ready_fixture: dict[str, Any], review_session: Session
) -> None:
    cand = ready_fixture["candidate"]
    reviewer = ready_fixture["reviewer"]

    # Build a separate candidate with its own observation
    other_lecturer = _make_lecturer(review_session, full_name="Other")
    other_author = _make_author(review_session, preferred_name="Other Author")
    other_cand = _make_candidate(
        review_session, lecturer=other_lecturer, author=other_author
    )
    other_run = _make_run(review_session, status="COMPLETED")
    other_obs = _make_observation(
        review_session,
        candidate=other_cand,
        run=other_run,
        evidence=[_name_evidence()],
    )
    review_session.commit()

    service = CandidateReviewService(review_session)
    with pytest.raises(ObservationCandidateMismatchError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand.id,
                observation_id=other_obs.id,  # belongs to other candidate
                candidate_version=cand.version,
                reviewer_user_id=reviewer.id,
            )
        )


# ---------------------------------------------------------------------------
# 37. UNAUTHORIZED REVIEWER
# ---------------------------------------------------------------------------

def test_lecturer_role_rejected(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]

    lecturer_user = _make_user(review_session, role="LECTURER", lecturer_id=ready_fixture["lecturer_id"])
    review_session.commit()

    service = CandidateReviewService(review_session)
    with pytest.raises(ReviewerNotAuthorizedError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand.id,
                observation_id=obs.id,
                candidate_version=cand.version,
                reviewer_user_id=lecturer_user.id,
            )
        )
    with pytest.raises(ReviewerNotAuthorizedError):
        service.reject_candidate(
            RejectCandidateCommand(
                candidate_id=cand.id,
                observation_id=obs.id,
                candidate_version=cand.version,
                reviewer_user_id=lecturer_user.id,
                reason="no",
            )
        )


def test_unknown_user_rejected(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    service = CandidateReviewService(review_session)
    with pytest.raises(ReviewerNotFoundError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand.id,
                observation_id=obs.id,
                candidate_version=cand.version,
                reviewer_user_id=uuid.uuid4(),
            )
        )


def test_inactive_user_rejected(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    inactive = _make_user(review_session, role="REVIEWER", is_active=False)
    review_session.commit()

    service = CandidateReviewService(review_session)
    with pytest.raises(ReviewerNotAuthorizedError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand.id,
                observation_id=obs.id,
                candidate_version=cand.version,
                reviewer_user_id=inactive.id,
            )
        )


def test_admin_role_accepted(ready_fixture: dict[str, Any], review_session: Session) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]

    admin = _make_user(review_session, role="ADMIN")
    review_session.commit()

    service = CandidateReviewService(review_session)
    result = service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=admin.id,
        )
    )
    assert result.action == "ACCEPT"
    assert result.idempotent is False


# ---------------------------------------------------------------------------
# 38. MULTIPLE APPROVED AUTHORS FOR SAME LECTURER
# ---------------------------------------------------------------------------

def test_lecturer_can_have_multiple_approved_authors(
    ready_fixture: dict[str, Any], review_session: Session
) -> None:
    """A lecturer may have multiple APPROVED Scopus-author mappings."""
    cand_a = ready_fixture["candidate"]
    obs_a = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]
    lecturer_id = ready_fixture["lecturer_id"]

    # Build second candidate for same lecturer, different author
    author_b = _make_author(review_session, preferred_name="Second Author")
    cand_b = _make_candidate(
        review_session,
        lecturer=review_session.get(Lecturer, lecturer_id),
        author=author_b,
    )
    run_b = _make_run(review_session, status="COMPLETED")
    obs_b = _make_observation(
        review_session,
        candidate=cand_b,
        run=run_b,
        evidence=[_name_evidence()],
    )
    review_session.commit()

    service = CandidateReviewService(review_session)
    r_a = service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand_a.id,
            observation_id=obs_a.id,
            candidate_version=cand_a.version,
            reviewer_user_id=reviewer.id,
        )
    )
    r_b = service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand_b.id,
            observation_id=obs_b.id,
            candidate_version=cand_b.version,
            reviewer_user_id=reviewer.id,
        )
    )

    # Both succeed
    assert r_a.action == "ACCEPT" and r_a.idempotent is False
    assert r_b.action == "ACCEPT" and r_b.idempotent is False
    assert r_a.resulting_identity_id != r_b.resulting_identity_id

    # Both identities are APPROVED for the same lecturer
    identities = review_session.scalars(
        select(LecturerScopusIdentity).where(
            LecturerScopusIdentity.lecturer_id == lecturer_id,
            LecturerScopusIdentity.status == "APPROVED",
        )
    ).all()
    assert len(identities) == 2


# ---------------------------------------------------------------------------
# 39. SAME SCOPUS AUTHOR / DIFFERENT LECTURERS (rejected)
# ---------------------------------------------------------------------------

def test_same_author_different_lecturer_rejected(
    ready_fixture: dict[str, Any], review_session: Session
) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]
    author_id = ready_fixture["author_id"]

    # Accept the first candidate
    service = CandidateReviewService(review_session)
    service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
        )
    )

    # Build second candidate: same author, different lecturer
    other_lecturer = _make_lecturer(review_session, full_name="Other")
    cand2 = _make_candidate(
        review_session,
        lecturer=other_lecturer,
        author=review_session.get(ScopusAuthor, author_id),
    )
    run2 = _make_run(review_session, status="COMPLETED")
    obs2 = _make_observation(
        review_session,
        candidate=cand2,
        run=run2,
        evidence=[_name_evidence()],
    )
    review_session.commit()

    with pytest.raises(ScopusAuthorAlreadyApprovedError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand2.id,
                observation_id=obs2.id,
                candidate_version=cand2.version,
                reviewer_user_id=reviewer.id,
            )
        )


# ---------------------------------------------------------------------------
# 42. PREEXISTING EXACT IDENTITY (Case E)
# ---------------------------------------------------------------------------

def test_preexisting_identity_provenance_conflict(
    ready_fixture: dict[str, Any], review_session: Session
) -> None:
    """A pre-existing identity with no matching review must fail closed."""
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    # Seed a pre-existing identity for the same (lecturer, author) pair
    # without creating a CandidateReview
    existing = LecturerScopusIdentity(
        lecturer_id=cand.lecturer_id,
        scopus_author_id=cand.scopus_author_id,
        status="APPROVED",
    )
    review_session.add(existing)
    review_session.commit()

    service = CandidateReviewService(review_session)
    with pytest.raises(PreexistingIdentityConflictError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand.id,
                observation_id=obs.id,
                candidate_version=cand.version,
                reviewer_user_id=reviewer.id,
            )
        )


# ---------------------------------------------------------------------------
# 43. EVIDENCE PROMOTION
# ---------------------------------------------------------------------------

def test_evidence_promotion_count_and_confidence(
    ready_fixture: dict[str, Any], review_session: Session
) -> None:
    """Each CandidateEvidence row produces one IdentityEvidence, confidence=NULL."""
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    result = service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
        )
    )

    identity = review_session.get(LecturerScopusIdentity, result.resulting_identity_id)
    assert identity is not None

    promoted = review_session.scalars(
        select(IdentityEvidence).where(IdentityEvidence.identity_id == identity.id)
    ).all()
    # 1 name + 1 publication = 2
    assert len(promoted) == 2
    for e in promoted:
        assert e.confidence_score is None  # never fabricated
        assert e.direction == "SUPPORTS"
        # The evidence_fingerprint is preserved from the candidate
        assert len(e.evidence_fingerprint) == 64

    # The candidate evidence IDs are still present
    cev = review_session.scalars(
        select(LecturerScopusCandidateEvidence).where(
            LecturerScopusCandidateEvidence.observation_id == obs.id
        )
    ).all()
    assert len(cev) == 2


# ---------------------------------------------------------------------------
# 44. DECISION SNAPSHOT IMMUTABILITY
# ---------------------------------------------------------------------------

def test_decision_snapshot_immutable_after_subsequent_changes(
    ready_fixture: dict[str, Any], review_session: Session
) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    result = service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
        )
    )

    review_row = review_session.get(LecturerScopusCandidateReview, result.review_id)
    assert review_row is not None
    original_snapshot = dict(review_row.evidence_snapshot)

    # Now add a new generation with different evidence
    new_run = _make_run(review_session, status="COMPLETED")
    new_obs = _make_observation(
        review_session,
        candidate=cand,
        run=new_run,
        evidence=[
            {
                "kind": "NAME",
                "rule_id": "RULE_TITLE_STRIPPED_N0",
                "rule_version": "M2.7A-3",
                "payload": {"lecturer_source_value": "X"},
                "source_refs": [],
            }
        ],
    )
    review_session.commit()

    # The original review's snapshot must be unchanged
    review_session.expire_all()
    review_row2 = review_session.get(LecturerScopusCandidateReview, result.review_id)
    assert review_row2 is not None
    assert review_row2.evidence_snapshot == original_snapshot
    assert review_row2.evidence_snapshot["observation_id"] == str(obs.id)


# ---------------------------------------------------------------------------
# 45. FAILURE ROLLBACK (incomplete commit)
# ---------------------------------------------------------------------------

def test_failure_rollback_no_partial_writes(
    ready_fixture: dict[str, Any], review_session: Session, monkeypatch
) -> None:
    """A failure mid-transaction must leave the DB unchanged."""
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    pre_state = {
        "identities": review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")),
        "evidence": review_session.scalar(text("SELECT count(*) FROM identity_evidence")),
        "reviews": review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_candidate_reviews")),
        "audit": review_session.scalar(text("SELECT count(*) FROM audit_events")),
    }
    assert pre_state["identities"] == 0
    assert pre_state["reviews"] == 0

    # Monkey-patch to fail after the identity is created
    from app.services import candidate_review_service
    original_promote = candidate_review_service.CandidateReviewService._promote_candidate_evidence_to_identity

    def broken_promote(*args, **kwargs):
        raise RuntimeError("Simulated failure during evidence promotion")

    monkeypatch.setattr(
        candidate_review_service.CandidateReviewService,
        "_promote_candidate_evidence_to_identity",
        broken_promote,
    )

    service = candidate_review_service.CandidateReviewService(review_session)
    with pytest.raises(RuntimeError, match="Simulated failure"):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand.id,
                observation_id=obs.id,
                candidate_version=cand.version,
                reviewer_user_id=reviewer.id,
            )
        )

    # The service relies on a single commit; on any failure the exception
    # bubbles up and the surrounding transaction must be rolled back to
    # leave the DB unchanged.
    review_session.rollback()
    review_session.expire_all()
    post_state = {
        "identities": review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")),
        "evidence": review_session.scalar(text("SELECT count(*) FROM identity_evidence")),
        "reviews": review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_candidate_reviews")),
        "audit": review_session.scalar(text("SELECT count(*) FROM audit_events")),
    }
    assert post_state == pre_state
    # Candidate must remain PENDING
    refreshed_cand = review_session.get(LecturerScopusCandidate, cand.id)
    assert refreshed_cand is not None
    assert refreshed_cand.status == "PENDING"


# ---------------------------------------------------------------------------
# 46. NO SCORING
# ---------------------------------------------------------------------------

def test_no_scoring_artifact_in_evidence_promotion(
    ready_fixture: dict[str, Any], review_session: Session
) -> None:
    """No confidence value is ever assigned by the review service."""
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    result = service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
        )
    )
    iev = review_session.scalars(
        select(IdentityEvidence).where(IdentityEvidence.identity_id == result.resulting_identity_id)
    ).all()
    for e in iev:
        assert e.confidence_score is None


# ---------------------------------------------------------------------------
# 47. NO MAPPING REVIEW WRITES
# ---------------------------------------------------------------------------

def test_no_mapping_review_written(
    ready_fixture: dict[str, Any], review_session: Session
) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    service.accept_candidate(
        AcceptCandidateCommand(
            candidate_id=cand.id,
            observation_id=obs.id,
            candidate_version=cand.version,
            reviewer_user_id=reviewer.id,
        )
    )
    assert review_session.scalar(text("SELECT count(*) FROM mapping_reviews")) == 0

    # Also test REJECT
    # Reject a fresh candidate
    other_lecturer = _make_lecturer(review_session, full_name="Another")
    other_author = _make_author(review_session, preferred_name="Another Author")
    other_cand = _make_candidate(
        review_session,
        lecturer=other_lecturer,
        author=other_author,
    )
    other_run = _make_run(review_session, status="COMPLETED")
    other_obs = _make_observation(
        review_session,
        candidate=other_cand,
        run=other_run,
        evidence=[_name_evidence()],
    )
    review_session.commit()

    service.reject_candidate(
        RejectCandidateCommand(
            candidate_id=other_cand.id,
            observation_id=other_obs.id,
            candidate_version=other_cand.version,
            reviewer_user_id=reviewer.id,
            reason="no good",
        )
    )
    assert review_session.scalar(text("SELECT count(*) FROM mapping_reviews")) == 0


# ---------------------------------------------------------------------------
# 24. REASON CONTRACT
# ---------------------------------------------------------------------------

def test_reject_blank_reason_rejected(
    ready_fixture: dict[str, Any], review_session: Session
) -> None:
    cand = ready_fixture["candidate"]
    obs = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    with pytest.raises(InvalidReviewReasonError):
        service.reject_candidate(
            RejectCandidateCommand(
                candidate_id=cand.id,
                observation_id=obs.id,
                candidate_version=cand.version,
                reviewer_user_id=reviewer.id,
                reason="   ",
            )
        )


# ---------------------------------------------------------------------------
# CANDIDATE NOT FOUND
# ---------------------------------------------------------------------------

def test_unknown_candidate_rejected(ready_fixture: dict[str, Any], review_session: Session) -> None:
    reviewer = ready_fixture["reviewer"]
    obs = ready_fixture["observation"]

    service = CandidateReviewService(review_session)
    with pytest.raises(CandidateNotFoundError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=uuid.uuid4(),
                observation_id=obs.id,
                candidate_version=1,
                reviewer_user_id=reviewer.id,
            )
        )


def test_unknown_observation_rejected(
    ready_fixture: dict[str, Any], review_session: Session
) -> None:
    cand = ready_fixture["candidate"]
    reviewer = ready_fixture["reviewer"]

    service = CandidateReviewService(review_session)
    with pytest.raises(ObservationNotFoundError):
        service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=cand.id,
                observation_id=uuid.uuid4(),
                candidate_version=1,
                reviewer_user_id=reviewer.id,
            )
        )


# ---------------------------------------------------------------------------
# Run-time checks for stable imports
# ---------------------------------------------------------------------------

def test_service_class_is_exported() -> None:
    from app.services import candidate_review_service
    assert hasattr(candidate_review_service, "CandidateReviewService")
    assert hasattr(candidate_review_service, "AcceptCandidateCommand")
    assert hasattr(candidate_review_service, "RejectCandidateCommand")


# ---------------------------------------------------------------------------
# 48. DETERMINISTIC CURRENT OBSERVATION
# ---------------------------------------------------------------------------

def test_current_observation_is_deterministic_for_tied_completed_runs(
    review_session: Session,
) -> None:
    """Equal completion timestamps use created_at/id tie-breakers deterministically."""
    lecturer = _make_lecturer(review_session)
    author = _make_author(review_session)
    candidate = _make_candidate(review_session, lecturer=lecturer, author=author)
    fixed_time = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
    lower_run_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    higher_run_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    completed_a = _make_run(
        review_session, status="COMPLETED", run_id=lower_run_id
    )
    completed_b = _make_run(
        review_session, status="COMPLETED", run_id=higher_run_id
    )
    running = _make_run(review_session, status="RUNNING")
    failed = _make_run(review_session, status="FAILED")
    for run in (completed_a, completed_b):
        run.started_at = fixed_time
        run.created_at = fixed_time
        run.completed_at = fixed_time
    running.started_at = fixed_time.replace(hour=12)
    running.created_at = fixed_time.replace(hour=12)
    failed.started_at = fixed_time.replace(hour=13)
    failed.created_at = fixed_time.replace(hour=13)
    failed.completed_at = fixed_time.replace(hour=14)

    obs_a = _make_observation(
        review_session, candidate=candidate, run=completed_a, evidence=[_name_evidence()]
    )
    obs_b = _make_observation(
        review_session, candidate=candidate, run=completed_b, evidence=[_name_evidence()]
    )
    _make_observation(review_session, candidate=candidate, run=running)
    _make_observation(review_session, candidate=candidate, run=failed)
    review_session.commit()

    expected = obs_b
    service = CandidateReviewService(review_session)
    selected = [
        service._resolve_current_reviewable_observation(candidate.id).id
        for _ in range(5)
    ]
    assert selected == [expected.id] * 5


# ---------------------------------------------------------------------------
# 49. REAL CONCURRENCY — SAME SCOPUS AUTHOR
# ---------------------------------------------------------------------------

def test_concurrent_accept_same_author_has_one_winner(
    review_session: Session, session_factory: sessionmaker
) -> None:
    reviewer = _make_user(review_session)
    lecturer_a = _make_lecturer(review_session, full_name="Lecturer A")
    lecturer_b = _make_lecturer(review_session, full_name="Lecturer B")
    author = _make_author(review_session, preferred_name="Shared Author")

    candidates: list[tuple[LecturerScopusCandidate, LecturerScopusCandidateObservation]] = []
    for lecturer in (lecturer_a, lecturer_b):
        candidate = _make_candidate(review_session, lecturer=lecturer, author=author)
        run = _make_run(review_session, status="COMPLETED")
        observation = _make_observation(
            review_session, candidate=candidate, run=run, evidence=[_name_evidence()]
        )
        candidates.append((candidate, observation))
    review_session.commit()

    commands = tuple(
        (
            "ACCEPT",
            AcceptCandidateCommand(
                candidate_id=candidate.id,
                observation_id=observation.id,
                candidate_version=candidate.version,
                reviewer_user_id=reviewer.id,
            ),
        )
        for candidate, observation in candidates
    )
    outcomes = _run_concurrently(session_factory, commands)

    successes = [outcome for _, outcome in outcomes if isinstance(outcome, AcceptResult)]
    errors = [outcome for _, outcome in outcomes if isinstance(outcome, BaseException)]
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ScopusAuthorAlreadyApprovedError)
    assert not isinstance(errors[0], IntegrityError)

    check = session_factory()
    try:
        assert check.scalar(text(
            "SELECT count(*) FROM lecturer_scopus_identities "
            "WHERE scopus_author_id = :author_id AND status = 'APPROVED'"
        ), {"author_id": author.id}) == 1
    finally:
        check.close()


# ---------------------------------------------------------------------------
# 50. REAL CONCURRENCY — SAME CANDIDATE
# ---------------------------------------------------------------------------

def test_concurrent_accept_same_candidate_has_no_duplicates(
    ready_fixture: dict[str, Any],
    review_session: Session,
    session_factory: sessionmaker,
) -> None:
    candidate = ready_fixture["candidate"]
    observation = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]
    review_session.commit()
    command = AcceptCandidateCommand(
        candidate_id=candidate.id,
        observation_id=observation.id,
        candidate_version=candidate.version,
        reviewer_user_id=reviewer.id,
    )

    outcomes = _run_concurrently(
        session_factory,
        (("ACCEPT", command), ("ACCEPT", command)),
    )

    successes = [outcome for _, outcome in outcomes if isinstance(outcome, AcceptResult)]
    errors = [outcome for _, outcome in outcomes if isinstance(outcome, BaseException)]
    assert len(successes) in {1, 2}, outcomes
    if len(successes) == 2:
        assert sum(result.idempotent for result in successes) == 1
    else:
        assert len(errors) == 1
        assert isinstance(errors[0], CandidateAlreadyDecidedError)
        assert not isinstance(errors[0], IntegrityError)

    check = session_factory()
    try:
        assert check.scalar(text("SELECT count(*) FROM lecturer_scopus_candidate_reviews")) == 1
        assert check.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")) == 1
        assert check.scalar(text("SELECT count(*) FROM identity_evidence")) == 2
        assert check.get(LecturerScopusCandidate, candidate.id).status == "ACCEPTED"
    finally:
        check.close()


# ---------------------------------------------------------------------------
# 51. REAL CONCURRENCY — OPPOSITE DECISIONS
# ---------------------------------------------------------------------------

def test_concurrent_opposite_decisions_have_one_terminal_winner(
    ready_fixture: dict[str, Any],
    review_session: Session,
    session_factory: sessionmaker,
) -> None:
    candidate = ready_fixture["candidate"]
    observation = ready_fixture["observation"]
    reviewer = ready_fixture["reviewer"]
    review_session.commit()
    accept = AcceptCandidateCommand(
        candidate_id=candidate.id,
        observation_id=observation.id,
        candidate_version=candidate.version,
        reviewer_user_id=reviewer.id,
    )
    reject = RejectCandidateCommand(
        candidate_id=candidate.id,
        observation_id=observation.id,
        candidate_version=candidate.version,
        reviewer_user_id=reviewer.id,
        reason="Concurrent reject test",
    )

    outcomes = _run_concurrently(
        session_factory,
        (("ACCEPT", accept), ("REJECT", reject)),
    )

    successes = [outcome for _, outcome in outcomes if not isinstance(outcome, BaseException)]
    errors = [outcome for _, outcome in outcomes if isinstance(outcome, BaseException)]
    assert len(successes) == 1, outcomes
    assert len(errors) == 1
    assert isinstance(errors[0], CandidateAlreadyDecidedError)
    assert not isinstance(errors[0], IntegrityError)

    check = session_factory()
    try:
        durable_action = check.scalar(text(
            "SELECT action FROM lecturer_scopus_candidate_reviews"
        ))
        durable_status = check.get(LecturerScopusCandidate, candidate.id).status
        assert durable_action in {"ACCEPT", "REJECT"}
        assert durable_status in {"ACCEPTED", "REJECTED"}
        assert check.scalar(text("SELECT count(*) FROM lecturer_scopus_candidate_reviews")) == 1
        if durable_action == "ACCEPT":
            assert check.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")) == 1
            assert check.scalar(text("SELECT count(*) FROM identity_evidence")) == 2
        else:
            assert check.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")) == 0
            assert check.scalar(text("SELECT count(*) FROM identity_evidence")) == 0
    finally:
        check.close()
