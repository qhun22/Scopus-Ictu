"""D-2 (PROMPT 09): ACCEPT needs a real reason when evidence is weak or ambiguous.

Service-level tests on the isolated review database (same fixtures as
test_candidate_review_service). The weak-evidence decision is made from DB rows;
a reason never becomes IdentityEvidence.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.candidate import LecturerScopusCandidate, LecturerScopusCandidateReview
from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.services.candidate_review_service import (
    AcceptCandidateCommand,
    CandidateReviewService,
    InvalidReviewReasonError,
    RejectCandidateCommand,
    ReviewerNotAuthorizedError,
    ReviewReasonRequiredForWeakEvidenceError,
    ScopusAuthorAlreadyApprovedError,
)
from app.services.identity_evidence_basis import evidence_basis_by_identity
from tests.integration.test_candidate_review_service import (  # noqa: F401  (fixtures)
    _make_author,
    _make_candidate,
    _make_lecturer,
    _make_observation,
    _make_run,
    _make_user,
    _name_evidence,
    _publication_evidence,
    review_engine,
    review_session,
    session_factory,
)


def _setup(session: Session, pairs: list[tuple[str, str, list[dict[str, Any]]]]) -> dict[str, Any]:
    """pairs: (lecturer_key, author_key, evidence); keys are reused to share rows."""
    run = _make_run(session, status="COMPLETED")
    lecturers: dict[str, Any] = {}
    authors: dict[str, Any] = {}
    out: list[tuple[LecturerScopusCandidate, Any]] = []
    for lk, ak, evidence in pairs:
        lecturers.setdefault(lk, _make_lecturer(session, full_name=f"TS. Lecturer {lk}"))
        authors.setdefault(ak, _make_author(session, preferred_name=f"Author {ak}"))
        cand = _make_candidate(session, lecturer=lecturers[lk], author=authors[ak])
        obs = _make_observation(session, candidate=cand, run=run, evidence=evidence)
        out.append((cand, obs))
    session.commit()
    reviewer = _make_user(session, role="REVIEWER")
    session.commit()
    return {"pairs": out, "reviewer": reviewer, "lecturers": lecturers, "authors": authors}


def _accept(session: Session, cand, obs, reviewer, reason: str | None = None):
    return CandidateReviewService(session).accept_candidate(
        AcceptCandidateCommand(candidate_id=cand.id, observation_id=obs.id, candidate_version=cand.version,
                               reviewer_user_id=reviewer.id, reason=reason)
    )


def _counts(session: Session) -> tuple[int, int, int, int]:
    return tuple(
        session.scalar(select(func.count()).select_from(model)) or 0
        for model in (LecturerScopusCandidateReview, LecturerScopusIdentity, IdentityEvidence, AuditEvent)
    )


def test_strong_unique_evidence_accepts_without_reason(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_name_evidence(), _publication_evidence()])])
    cand, obs = fx["pairs"][0]
    result = _accept(review_session, cand, obs, fx["reviewer"])
    assert result.idempotent is False and result.candidate_status == "ACCEPTED"
    review = review_session.get(LecturerScopusCandidateReview, result.review_id)
    assert review.reason is None


def test_strong_evidence_whitespace_reason_is_stored_as_no_reason(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_publication_evidence()])])
    cand, obs = fx["pairs"][0]
    result = _accept(review_session, cand, obs, fx["reviewer"], reason="   \t ")
    assert review_session.get(LecturerScopusCandidateReview, result.review_id).reason is None


@pytest.mark.parametrize("reason", [None, "", "    ", "\n\t "])
def test_name_only_accept_without_real_reason_is_refused_and_writes_nothing(
    review_session: Session, reason: str | None
) -> None:
    fx = _setup(review_session, [("L1", "A1", [_name_evidence()])])
    cand, obs = fx["pairs"][0]
    before = _counts(review_session)
    with pytest.raises(ReviewReasonRequiredForWeakEvidenceError) as err:
        _accept(review_session, cand, obs, fx["reviewer"], reason=reason)
    assert err.value.code == "REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE"
    assert err.value.triggers == ("NAME_EVIDENCE_ONLY",)
    assert isinstance(err.value, InvalidReviewReasonError)  # same 422 family as before
    review_session.rollback()
    assert _counts(review_session) == before
    fresh = review_session.get(LecturerScopusCandidate, cand.id)
    review_session.refresh(fresh)
    assert fresh.status == "PENDING" and fresh.version == cand.version


def test_name_only_accept_with_reason_succeeds_and_reason_is_not_evidence(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_name_evidence()])])
    cand, obs = fx["pairs"][0]
    result = _accept(review_session, cand, obs, fx["reviewer"], reason="  Đối chiếu hồ sơ ORCID thủ công  ")
    review = review_session.get(LecturerScopusCandidateReview, result.review_id)
    assert review.reason == "Đối chiếu hồ sơ ORCID thủ công"
    types = review_session.scalars(
        select(IdentityEvidence.evidence_type).where(IdentityEvidence.identity_id == result.resulting_identity_id)
    ).all()
    assert types == ["NAME_SIMILARITY"]  # the reason did not add any evidence
    basis = evidence_basis_by_identity(review_session, [result.resulting_identity_id])[result.resulting_identity_id]
    assert basis["level"] == "NAME_ONLY" and basis["independently_verified"] is False
    audit = review_session.scalar(select(AuditEvent).where(AuditEvent.action == "CANDIDATE_ACCEPTED"))
    assert audit.reason == "Đối chiếu hồ sơ ORCID thủ công"
    assert audit.event_metadata["reason_required"] is True
    assert audit.event_metadata["reason_triggers"] == ["NAME_EVIDENCE_ONLY"]


def test_shared_scopus_author_requires_reason_even_with_publication_evidence(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_name_evidence(), _publication_evidence()]),
                                 ("L2", "A1", [_name_evidence(), _publication_evidence()])])
    cand, obs = fx["pairs"][0]
    with pytest.raises(ReviewReasonRequiredForWeakEvidenceError) as err:
        _accept(review_session, cand, obs, fx["reviewer"])
    assert err.value.triggers == ("SHARED_SCOPUS_AUTHOR",)
    review_session.rollback()
    assert _accept(review_session, cand, obs, fx["reviewer"], reason="Đúng đơn vị và đồng tác giả").idempotent is False


def test_lecturer_with_several_candidates_requires_reason(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_publication_evidence()]), ("L1", "A2", [_publication_evidence()])])
    cand, obs = fx["pairs"][0]
    with pytest.raises(ReviewReasonRequiredForWeakEvidenceError) as err:
        _accept(review_session, cand, obs, fx["reviewer"])
    assert err.value.triggers == ("MULTIPLE_CANDIDATES_FOR_LECTURER",)


def test_all_three_triggers_are_reported_together(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_name_evidence()]), ("L1", "A2", [_name_evidence()]),
                                 ("L2", "A1", [_name_evidence()])])
    cand, obs = fx["pairs"][0]
    with pytest.raises(ReviewReasonRequiredForWeakEvidenceError) as err:
        _accept(review_session, cand, obs, fx["reviewer"])
    assert err.value.triggers == ("NAME_EVIDENCE_ONLY", "SHARED_SCOPUS_AUTHOR", "MULTIPLE_CANDIDATES_FOR_LECTURER")


def test_replay_of_recorded_accept_is_idempotent_and_writes_nothing(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_name_evidence()])])
    cand, obs = fx["pairs"][0]
    version = cand.version
    first = _accept(review_session, cand, obs, fx["reviewer"], reason="Lý do thật")
    after_first = _counts(review_session)
    # Same command replayed (original version), even without the reason: contract returns the recorded result.
    replay = CandidateReviewService(review_session).accept_candidate(
        AcceptCandidateCommand(candidate_id=cand.id, observation_id=obs.id, candidate_version=version,
                               reviewer_user_id=fx["reviewer"].id, reason=None)
    )
    assert replay.idempotent is True and replay.review_id == first.review_id
    assert replay.resulting_identity_id == first.resulting_identity_id
    assert _counts(review_session) == after_first


def test_reason_does_not_bypass_scopus_author_conflict(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_publication_evidence()]), ("L2", "A1", [_publication_evidence()])])
    (c1, o1), (c2, o2) = fx["pairs"]
    _accept(review_session, c1, o1, fx["reviewer"], reason="Đã đối chiếu")
    before = _counts(review_session)
    with pytest.raises(ScopusAuthorAlreadyApprovedError):
        _accept(review_session, c2, o2, fx["reviewer"], reason="Lý do không thể vượt ràng buộc")
    review_session.rollback()
    assert _counts(review_session) == before
    approved = review_session.scalars(select(LecturerScopusIdentity).where(LecturerScopusIdentity.status == "APPROVED")).all()
    assert len(approved) == 1 and approved[0].lecturer_id == c1.lecturer_id


def test_lecturer_role_cannot_decide(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_publication_evidence()])])
    cand, obs = fx["pairs"][0]
    lecturer_user = _make_user(review_session, role="LECTURER")
    review_session.commit()
    with pytest.raises(ReviewerNotAuthorizedError):
        _accept(review_session, cand, obs, lecturer_user, reason="x")


@pytest.mark.parametrize("reason", ["", "   ", "\n"])
def test_reject_still_requires_real_reason(review_session: Session, reason: str) -> None:
    fx = _setup(review_session, [("L1", "A1", [_name_evidence()])])
    cand, obs = fx["pairs"][0]
    with pytest.raises(InvalidReviewReasonError) as err:
        CandidateReviewService(review_session).reject_candidate(
            RejectCandidateCommand(candidate_id=cand.id, observation_id=obs.id, candidate_version=cand.version,
                                   reviewer_user_id=fx["reviewer"].id, reason=reason)
        )
    assert err.value.code == "INVALID_REVIEW_REASON"


def test_reject_with_reason_succeeds_without_identity(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_name_evidence()])])
    cand, obs = fx["pairs"][0]
    result = CandidateReviewService(review_session).reject_candidate(
        RejectCandidateCommand(candidate_id=cand.id, observation_id=obs.id, candidate_version=cand.version,
                               reviewer_user_id=fx["reviewer"].id, reason="  Khác đơn vị  ")
    )
    assert result.candidate_status == "REJECTED" and result.resulting_identity_id is None
    assert review_session.get(LecturerScopusCandidateReview, result.review_id).reason == "Khác đơn vị"
    assert (review_session.scalar(select(func.count()).select_from(LecturerScopusIdentity)) or 0) == 0


# ---------------------------------------------------------------------------
# PROMPT 11: competition counts only candidates still in force (PENDING / ACCEPTED)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("sibling_status", "expect_multiple"),
    [("PENDING", True), ("ACCEPTED", True), ("REJECTED", False), ("SUPERSEDED", False)],
)
def test_lecturer_sibling_status_decides_multiple_candidates_trigger(
    review_session: Session, sibling_status: str, expect_multiple: bool
) -> None:
    fx = _setup(review_session, [("L1", "A1", [_publication_evidence()]), ("L1", "A2", [_publication_evidence()])])
    (cand, obs), (sibling, _sobs) = fx["pairs"]
    sibling.status = sibling_status
    review_session.commit()
    if expect_multiple:
        with pytest.raises(ReviewReasonRequiredForWeakEvidenceError) as err:
            _accept(review_session, cand, obs, fx["reviewer"])
        assert err.value.triggers == ("MULTIPLE_CANDIDATES_FOR_LECTURER",)
    else:
        result = _accept(review_session, cand, obs, fx["reviewer"])  # strong, unique among active -> no reason needed
        assert result.idempotent is False and result.candidate_status == "ACCEPTED"


@pytest.mark.parametrize(("other_status", "expect_shared"), [("PENDING", True), ("REJECTED", False), ("SUPERSEDED", False)])
def test_shared_author_trigger_ignores_historical_candidates(
    review_session: Session, other_status: str, expect_shared: bool
) -> None:
    fx = _setup(review_session, [("L1", "A1", [_publication_evidence()]), ("L2", "A1", [_publication_evidence()])])
    (cand, obs), (other, _oobs) = fx["pairs"]
    other.status = other_status
    review_session.commit()
    if expect_shared:
        with pytest.raises(ReviewReasonRequiredForWeakEvidenceError) as err:
            _accept(review_session, cand, obs, fx["reviewer"])
        assert err.value.triggers == ("SHARED_SCOPUS_AUTHOR",)
    else:
        assert _accept(review_session, cand, obs, fx["reviewer"]).candidate_status == "ACCEPTED"


def test_author_accepted_for_another_lecturer_is_still_a_conflict_not_a_reason_question(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_publication_evidence()]), ("L2", "A1", [_publication_evidence()])])
    (c1, o1), (c2, o2) = fx["pairs"]
    _accept(review_session, c1, o1, fx["reviewer"], reason="Đã đối chiếu")
    with pytest.raises(ScopusAuthorAlreadyApprovedError):
        _accept(review_session, c2, o2, fx["reviewer"])  # no reason given: conflict (409) wins, not 422


def test_replay_after_sibling_rejection_stays_idempotent(review_session: Session) -> None:
    fx = _setup(review_session, [("L1", "A1", [_name_evidence()]), ("L1", "A2", [_name_evidence()])])
    (cand, obs), (sibling, sobs) = fx["pairs"]
    version = cand.version
    first = _accept(review_session, cand, obs, fx["reviewer"], reason="Hai ứng viên, chọn A1 theo hồ sơ")
    CandidateReviewService(review_session).reject_candidate(
        RejectCandidateCommand(candidate_id=sibling.id, observation_id=sobs.id, candidate_version=sibling.version,
                               reviewer_user_id=fx["reviewer"].id, reason="Khác người"))
    before = _counts(review_session)
    replay = CandidateReviewService(review_session).accept_candidate(
        AcceptCandidateCommand(candidate_id=cand.id, observation_id=obs.id, candidate_version=version,
                               reviewer_user_id=fx["reviewer"].id, reason=None))
    assert replay.idempotent is True and replay.review_id == first.review_id
    assert _counts(review_session) == before
