"""D-2: when an ACCEPT review decision must carry a reason.

Computed only from persisted rows (current observation evidence and candidate
counts), never from flags sent by a client.

Competition is counted over candidates that are still in force — PENDING and
ACCEPTED (an ACCEPTED candidate is exactly an approved identity link; the state
machine has no other path to ACCEPTED). REJECTED and SUPERSEDED candidates are
history and do not make a decision ambiguous. A Scopus author already ACCEPTED
for another lecturer is rejected earlier as an identity conflict (409). The
read-only ambiguity context in the review queue still shows all candidates.

A reason never changes the evidence level of the resulting identity: it is
stored on the review and audit rows only, not as IdentityEvidence.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.candidate import LecturerScopusCandidate

# Candidate states that still compete for the same lecturer / Scopus author.
ACTIVE_CANDIDATE_STATUSES = ("PENDING", "ACCEPTED")

# Only name-match evidence; no publication evidence in the current observation.
TRIGGER_NAME_EVIDENCE_ONLY = "NAME_EVIDENCE_ONLY"
# The same Scopus Author ID is proposed for more than one lecturer.
TRIGGER_SHARED_SCOPUS_AUTHOR = "SHARED_SCOPUS_AUTHOR"
# The lecturer has more than one Scopus-author candidate to tell apart.
TRIGGER_MULTIPLE_CANDIDATES_FOR_LECTURER = "MULTIPLE_CANDIDATES_FOR_LECTURER"

ACCEPT_REASON_TRIGGERS = (
    TRIGGER_NAME_EVIDENCE_ONLY,
    TRIGGER_SHARED_SCOPUS_AUTHOR,
    TRIGGER_MULTIPLE_CANDIDATES_FOR_LECTURER,
)


@dataclass(frozen=True, slots=True)
class AcceptReasonPolicy:
    triggers: tuple[str, ...]

    @property
    def required(self) -> bool:
        return bool(self.triggers)


def accept_reason_policy(
    session: Session,
    *,
    lecturer_id: uuid.UUID,
    scopus_author_id: uuid.UUID,
    evidence_kinds: Iterable[str],
) -> AcceptReasonPolicy:
    """Return which weak-evidence conditions apply to accepting this pair."""

    triggers: list[str] = []
    if "PUBLICATION" not in set(evidence_kinds):
        triggers.append(TRIGGER_NAME_EVIDENCE_ONLY)
    author_candidates = session.scalar(
        select(func.count(LecturerScopusCandidate.id)).where(
            LecturerScopusCandidate.scopus_author_id == scopus_author_id,
            LecturerScopusCandidate.status.in_(ACTIVE_CANDIDATE_STATUSES),
        )
    ) or 0
    if author_candidates > 1:
        triggers.append(TRIGGER_SHARED_SCOPUS_AUTHOR)
    lecturer_candidates = session.scalar(
        select(func.count(LecturerScopusCandidate.id)).where(
            LecturerScopusCandidate.lecturer_id == lecturer_id,
            LecturerScopusCandidate.status.in_(ACTIVE_CANDIDATE_STATUSES),
        )
    ) or 0
    if lecturer_candidates > 1:
        triggers.append(TRIGGER_MULTIPLE_CANDIDATES_FOR_LECTURER)
    return AcceptReasonPolicy(triggers=tuple(triggers))


def normalize_reason(reason: str | None) -> str | None:
    """Strip surrounding whitespace; a reason with no real content is no reason."""

    if reason is None:
        return None
    stripped = reason.strip()
    return stripped or None


__all__ = [
    "ACCEPT_REASON_TRIGGERS",
    "ACTIVE_CANDIDATE_STATUSES",
    "AcceptReasonPolicy",
    "TRIGGER_MULTIPLE_CANDIDATES_FOR_LECTURER",
    "TRIGGER_NAME_EVIDENCE_ONLY",
    "TRIGGER_SHARED_SCOPUS_AUTHOR",
    "accept_reason_policy",
    "normalize_reason",
]
