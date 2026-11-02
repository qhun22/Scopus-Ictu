"""Group review: accept every proposed Scopus ID of ONE lecturer in a single transaction.

A lecturer with several candidate IDs is usually one person. Instead of N separate decisions
the reviewer sees the group, gives one shared reason and may mark one ID as the main label.
Nothing here weakens the single-decision rules: each member still goes through
``CandidateReviewService.accept_candidate`` (stale version/observation checks, D-2 reason
policy, one-owner-per-author constraint). The whole group commits or rolls back together,
so a failure on any member leaves no partial approval behind.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import LecturerScopusCandidate
from app.services.candidate_review_service import (
    AcceptCandidateCommand,
    AcceptResult,
    CandidateNotFoundError,
    CandidateReviewError,
    CandidateReviewService,
    InvalidReviewReasonError,
)
from app.services.primary_scopus_identity import PrimaryIdentityService
from app.services.review_reason_policy import normalize_reason

MAX_GROUP_SIZE = 10


class GroupSizeError(CandidateReviewError):
    code = "GROUP_NEEDS_TWO_TO_TEN_CANDIDATES"


class GroupMismatchError(CandidateReviewError):
    code = "GROUP_CANDIDATE_LECTURER_MISMATCH"


class GroupDuplicateError(CandidateReviewError):
    code = "GROUP_DUPLICATE_CANDIDATE"


class GroupReasonRequiredError(InvalidReviewReasonError):
    code = "GROUP_REASON_REQUIRED"


class GroupPrimaryNotInGroupError(CandidateReviewError):
    code = "GROUP_PRIMARY_NOT_IN_GROUP"


class GroupSharedAuthorError(CandidateReviewError):
    code = "GROUP_SHARED_SCOPUS_AUTHOR"


@dataclass(frozen=True, slots=True)
class GroupItem:
    candidate_id: uuid.UUID
    observation_id: uuid.UUID
    candidate_version: int


@dataclass(frozen=True, slots=True)
class GroupAcceptResult:
    lecturer_id: uuid.UUID
    results: tuple[AcceptResult, ...]
    primary_identity_id: uuid.UUID | None


def accept_group(
    session: Session,
    *,
    lecturer_id: uuid.UUID,
    items: Sequence[GroupItem],
    reviewer_user_id: uuid.UUID,
    reason: str | None,
    primary_candidate_id: uuid.UUID | None = None,
) -> GroupAcceptResult:
    """Accept every member or none: a failure raises and leaves nothing written."""

    if not 2 <= len(items) <= MAX_GROUP_SIZE:
        raise GroupSizeError(f"A group has between 2 and {MAX_GROUP_SIZE} candidates")
    ids = [item.candidate_id for item in items]
    if len(set(ids)) != len(ids):
        raise GroupDuplicateError("The same candidate appears twice in the group")
    shared_reason = normalize_reason(reason)
    if shared_reason is None:
        raise GroupReasonRequiredError("One shared, non-blank reason is required for a group")
    if primary_candidate_id is not None and primary_candidate_id not in ids:
        raise GroupPrimaryNotInGroupError("The main ID must be one of the group's candidates")
    for candidate_id in ids:
        candidate = session.get(LecturerScopusCandidate, candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(f"No candidate with id={candidate_id}")
        if candidate.lecturer_id != lecturer_id:
            raise GroupMismatchError("Every candidate of a group must belong to the same lecturer")
        # An ID also proposed for another lecturer is ambiguous: it must be decided one by one.
        rival = session.scalars(
            select(LecturerScopusCandidate.id).where(
                LecturerScopusCandidate.scopus_author_id == candidate.scopus_author_id,
                LecturerScopusCandidate.lecturer_id != lecturer_id,
                LecturerScopusCandidate.status.in_(("PENDING", "ACCEPTED")),
            ).limit(1)
        ).first()
        if rival is not None:
            raise GroupSharedAuthorError(
                "A Scopus ID proposed for more than one lecturer must be reviewed individually"
            )

    try:
        service = CandidateReviewService(session, auto_commit=False)
        results: list[AcceptResult] = []
        for item in items:
            results.append(service.accept_candidate(AcceptCandidateCommand(
                candidate_id=item.candidate_id,
                observation_id=item.observation_id,
                candidate_version=item.candidate_version,
                reviewer_user_id=reviewer_user_id,
                reason=shared_reason,
            )))
        primary_identity_id = None
        if primary_candidate_id is not None:
            primary_identity_id = results[ids.index(primary_candidate_id)].resulting_identity_id
            PrimaryIdentityService(session, auto_commit=False).set_primary(
                lecturer_id, primary_identity_id, reviewer_user_id, shared_reason)
        session.commit()
    except BaseException:
        session.rollback()
        raise
    return GroupAcceptResult(lecturer_id, tuple(results), primary_identity_id)
