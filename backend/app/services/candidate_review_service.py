"""Human candidate review service — M2.7B-4.

Provides ACCEPT and REJECT operations for pre-identity lecturer/Scopus-author
candidates.  This service is the authoritative boundary between the candidate
generation layer and the identity resolution layer.

Key invariants enforced here:
  - Candidate review is the only path from PENDING to ACCEPTED/REJECTED.
  - LecturerScopusIdentity is created only on explicit ACCEPT.
  - Human review is NEVER recorded as IdentityEvidence.
  - confidence_score is always NULL for candidate-derived evidence.
  - Decision-time evidence snapshot is built server-side from immutable DB rows.
  - Concurrent races are handled atomically with SELECT FOR UPDATE + DB uniqueness.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
    LecturerScopusCandidateReview,
)
from app.models.governance import User
from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.models.publication import ScopusAuthor
from app.services.candidate_review_queries import current_reviewable_observation


# ---------------------------------------------------------------------------
# Typed command objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AcceptCandidateCommand:
    """Command to accept one candidate."""

    candidate_id: uuid.UUID
    observation_id: uuid.UUID
    candidate_version: int
    reviewer_user_id: uuid.UUID
    reason: str | None = None  # optional for ACCEPT per existing schema


@dataclass(frozen=True, slots=True)
class RejectCandidateCommand:
    """Command to reject one candidate."""

    candidate_id: uuid.UUID
    observation_id: uuid.UUID
    candidate_version: int
    reviewer_user_id: uuid.UUID
    reason: str  # required for REJECT per schema CHECK constraint


# ---------------------------------------------------------------------------
# Typed result objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ReviewResult:
    """Shared fields for both ACCEPT and REJECT outcomes."""

    review_id: uuid.UUID
    candidate_id: uuid.UUID
    observation_id: uuid.UUID
    action: str  # 'ACCEPT' or 'REJECT'
    candidate_status: str  # 'ACCEPTED' or 'REJECTED'
    candidate_version: int
    idempotent: bool


@dataclass(frozen=True, slots=True)
class AcceptResult(ReviewResult):
    """Result of a candidate ACCEPT operation."""

    resulting_identity_id: uuid.UUID

    # evidence promotion audit
    name_evidence_promoted: int = 0
    publication_evidence_promoted: int = 0


@dataclass(frozen=True, slots=True)
class RejectResult(ReviewResult):
    """Result of a candidate REJECT operation."""

    resulting_identity_id: None = field(default=None, compare=False)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class CandidateReviewError(Exception):
    """Base class for all review service domain errors."""

    code: str = "INTERNAL_ERROR"
    message: str = "An internal error occurred."

    def __init__(self, message: str | None = None) -> None:
        if message:
            self.message = message
        super().__init__(f"[{self.code}] {self.message}")


class CandidateNotFoundError(CandidateReviewError):
    """No candidate exists for the given ID."""

    code = "CANDIDATE_NOT_FOUND"


class ObservationNotFoundError(CandidateReviewError):
    """No observation exists for the given ID."""

    code = "OBSERVATION_NOT_FOUND"


class ObservationCandidateMismatchError(CandidateReviewError):
    """The observation does not belong to the specified candidate."""

    code = "OBSERVATION_CANDIDATE_MISMATCH"


class StaleCandidateObservationError(CandidateReviewError):
    """The submitted observation is not the current reviewable observation."""

    code = "STALE_CANDIDATE_OBSERVATION"


class StaleCandidateVersionError(CandidateReviewError):
    """The submitted candidate version does not match the current DB version."""

    code = "STALE_CANDIDATE_VERSION"


class CandidateAlreadyDecidedError(CandidateReviewError):
    """The candidate has already received a terminal decision."""

    code = "CANDIDATE_ALREADY_DECIDED_CONFLICT"
    existing_action: str = ""
    existing_review_id: uuid.UUID | None = None


class ReviewerNotFoundError(CandidateReviewError):
    """No user exists for the given reviewer ID."""

    code = "REVIEWER_NOT_FOUND"


class ReviewerNotAuthorizedError(CandidateReviewError):
    """The reviewer does not hold a permitted role (ADMIN or REVIEWER)."""

    code = "REVIEWER_NOT_AUTHORIZED"
    reviewer_role: str = ""


class ScopusAuthorAlreadyApprovedError(CandidateReviewError):
    """The Scopus author is already APPROVED for another lecturer."""

    code = "SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER"
    existing_lecturer_id: uuid.UUID | None = None


class PreexistingIdentityConflictError(CandidateReviewError):
    """An exact identity already exists with no matching CandidateReview provenance."""

    code = "PREEXISTING_IDENTITY_PROVENANCE_CONFLICT"
    existing_identity_id: uuid.UUID | None = None


class InvalidReviewReasonError(CandidateReviewError):
    """The review reason is blank or missing when required."""

    code = "INVALID_REVIEW_REASON"


class EvidencePromotionUnsupportedError(CandidateReviewError):
    """Candidate evidence kind cannot be mapped to IdentityEvidence."""

    code = "EVIDENCE_PROMOTION_UNSUPPORTED"
    unsupported_evidence_kind: str = ""


# ---------------------------------------------------------------------------
# Evidence type mapping
# ---------------------------------------------------------------------------

# Mapping from candidate evidence.kind to IdentityEvidence.evidence_type.
# The direction is always 'SUPPORTS' for candidate-derived evidence.
# confidence_score is always NULL (no machine-derived score in M2.7 evidence).
#
# PUBLICATION evidence: prefer DOI_EXACT when reconciliation=='DOI_EXACT',
# otherwise fall back to 'PUBLICATION_OVERLAP' (the closest available type
# that represents known-publication co-authorship evidence).

CANDIDATE_TO_IDENTITY_EVIDENCE_TYPE: dict[str, str] = {
    "NAME": "NAME_SIMILARITY",
    "PUBLICATION": "DOI_EXACT",  # overridden per evidence payload below
}


def _map_publication_evidence_type(reconciliation: str) -> str:
    """Select the best IdentityEvidence.evidence_type for publication evidence."""
    if reconciliation == "DOI_EXACT":
        return "DOI_EXACT"
    # TITLE_EXACT is not in the vocabulary; use PUBLICATION_OVERLAP.
    return "PUBLICATION_OVERLAP"


# ---------------------------------------------------------------------------
# Audit action constants
# ---------------------------------------------------------------------------

AUDIT_ACTION_CANDIDATE_ACCEPTED = "CANDIDATE_ACCEPTED"
AUDIT_ACTION_CANDIDATE_REJECTED = "CANDIDATE_REJECTED"
AUDIT_ACTION_IDENTITY_CREATED = "IDENTITY_CREATED_FROM_CANDIDATE"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class CandidateReviewService:
    """Human review boundary for lecturer/Scopus-author candidates.

    This service implements the M2.7B-4 review contract:
      - Authorizes reviewer roles.
      - Validates current observation and version.
      - Implements idempotent ACQUIRE and REJECT.
      - Creates identity + evidence on ACCEPT.
      - Creates CandidateReview history.
      - Records audit events.
      - Fails closed on all race conditions.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------

    def accept_candidate(self, cmd: AcceptCandidateCommand) -> AcceptResult:
        """Accept a pending candidate and create the approved identity.

        Implements the full ACCEPT transaction as defined in §22 of M2.7B-4.
        Returns AcceptResult on success, raises a domain error on any failure.
        """
        return self._accept(cmd)

    def reject_candidate(self, cmd: RejectCandidateCommand) -> RejectResult:
        """Reject a pending candidate.

        Implements the full REJECT transaction as defined in §23 of M2.7B-4.
        Returns RejectResult on success, raises a domain error on any failure.
        """
        return self._reject(cmd)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_and_lock_candidate(
        self, candidate_id: uuid.UUID
    ) -> LecturerScopusCandidate:
        """Load a candidate with SELECT FOR UPDATE to serialize concurrent reviews."""
        row = self._session.get(
            LecturerScopusCandidate,
            candidate_id,
            with_for_update=True,
        )
        if row is None:
            raise CandidateNotFoundError(
                f"No candidate with id={candidate_id}"
            )
        return row

    def _load_observation(
        self, observation_id: uuid.UUID
    ) -> LecturerScopusCandidateObservation:
        """Load an observation (no lock — read-only)."""
        row = self._session.get(
            LecturerScopusCandidateObservation,
            observation_id,
        )
        if row is None:
            raise ObservationNotFoundError(
                f"No observation with id={observation_id}"
            )
        return row

    def _load_observation_evidence(
        self, observation_id: uuid.UUID
    ) -> tuple[LecturerScopusCandidateEvidence, ...]:
        """Load all evidence descriptors for one observation, ordered."""
        rows = self._session.scalars(
            select(LecturerScopusCandidateEvidence)
            .where(
                LecturerScopusCandidateEvidence.observation_id == observation_id
            )
            .order_by(
                LecturerScopusCandidateEvidence.evidence_kind,
                LecturerScopusCandidateEvidence.rule_id,
                LecturerScopusCandidateEvidence.evidence_fingerprint,
            )
        ).all()
        return tuple(rows)

    def _resolve_current_reviewable_observation(
        self, candidate_id: uuid.UUID
    ) -> LecturerScopusCandidateObservation:
        """Return the latest COMPLETED generation run's observation for a candidate.

        Rule: select the single observation belonging to the most recent
        CandidateGenerationRun with status='COMPLETED' that has an observation
        for the given candidate.  RUNNING and FAILED generations are excluded.

        This is deterministic because:
          - a candidate belongs to exactly one observation per generation run
            (unique constraint on candidate_id + generation_run_id).
          - generation runs are immutable once COMPLETED.
          - completed_at reflects run completion, with created_at and id as
            deterministic tie-breakers. UUID id is only a stable tie-breaker
            for equal timestamps, not a chronological signal.
        """
        return current_reviewable_observation(self._session, candidate_id)

    def _authorize_reviewer(
        self, user_id: uuid.UUID
    ) -> User:
        """Authorize a reviewer by user ID.

        Raises ReviewerNotFoundError if the user does not exist.
        Raises ReviewerNotAuthorizedError if the user is not ADMIN or REVIEWER
        or is inactive.
        """
        user = self._session.get(User, user_id)
        if user is None:
            raise ReviewerNotFoundError(f"No user with id={user_id}")
        if not user.is_active:
            raise ReviewerNotAuthorizedError(
                f"User {user_id} is inactive"
            )
        if user.role not in ("ADMIN", "REVIEWER"):
            raise ReviewerNotAuthorizedError(
                f"User {user_id} has role {user.role!r}; "
                f"only ADMIN and REVIEWER are permitted"
            )
        return user

    def _check_identity_conflicts(
        self,
        lecturer_id: uuid.UUID,
        scopus_author_id: uuid.UUID,
    ) -> None:
        """Fail closed if the identity cannot be created due to cardinality violations.

        Case A: no conflict → allowed.
        Case B: lecturer already has APPROVED identities → allowed (one lecturer
                may have multiple APPROVED Scopus authors).
        Case C: Scopus author already APPROVED for another lecturer → BLOCKED.
        Case D: exact identity already exists → checked by idempotency in _accept.
        Case E: exact identity exists from other provenance → BLOCKED.
        """
        # Lock the author row so concurrent reviews for the same author
        # serialize even when no APPROVED identity row exists yet.
        self._session.get(
            ScopusAuthor,
            scopus_author_id,
            with_for_update=True,
        )

        # Case C: is this Scopus author already APPROVED for a different lecturer?
        existing = self._session.scalar(
            select(LecturerScopusIdentity)
            .where(
                LecturerScopusIdentity.scopus_author_id == scopus_author_id,
                LecturerScopusIdentity.status == "APPROVED",
            )
            .with_for_update()
        )
        if existing is not None and existing.lecturer_id != lecturer_id:
            raise ScopusAuthorAlreadyApprovedError(
                f"Scopus author {scopus_author_id} is already APPROVED "
                f"for lecturer {existing.lecturer_id}"
            )

    def _build_evidence_snapshot(
        self,
        candidate_id: uuid.UUID,
        lecturer_id: uuid.UUID,
        scopus_author_id: uuid.UUID,
        observation_id: uuid.UUID,
        observation_hash: str,
        generation_run_id: uuid.UUID,
        generation_run_version: str,
        evidence_rows: tuple[LecturerScopusCandidateEvidence, ...],
    ) -> dict:
        """Build the deterministic, server-side decision-time evidence snapshot.

        This JSON structure is immutable and stored in CandidateReview.evidence_snapshot.
        It contains enough information to reconstruct the decision context without
        depending on current database state.
        """
        evidence_descriptors = []
        for ev in evidence_rows:
            # Extract reconciliation from payload for PUBLICATION evidence
            reconciliation = None
            if ev.evidence_kind == "PUBLICATION":
                reconciliation = ev.payload.get("reconciliation")

            evidence_descriptors.append({
                "evidence_kind": ev.evidence_kind,
                "rule_id": ev.rule_id,
                "rule_version": ev.rule_version,
                "evidence_fingerprint": ev.evidence_fingerprint,
                "payload": dict(ev.payload),
                "source_refs": list(ev.source_refs),
                # Include reconciliation for PUBLICATION evidence for clarity
                **(
                    {"reconciliation": reconciliation}
                    if reconciliation
                    else {}
                ),
            })

        return {
            "schema_version": 1,
            "candidate_id": str(candidate_id),
            "lecturer_id": str(lecturer_id),
            "scopus_author_id": str(scopus_author_id),
            "observation_id": str(observation_id),
            "observation_hash": observation_hash,
            "generation_run_id": str(generation_run_id),
            "generation_run_rule_set_version": generation_run_version,
            "evidence_count": len(evidence_descriptors),
            "evidence": evidence_descriptors,
        }

    def _promote_candidate_evidence_to_identity(
        self,
        identity_id: uuid.UUID,
        evidence_rows: tuple[LecturerScopusCandidateEvidence, ...],
        generation_run_version: str,
    ) -> tuple[int, int]:
        """Promote candidate evidence to IdentityEvidence records.

        Returns (name_evidence_count, publication_evidence_count).
        confidence_score is always NULL (M2.7 evidence has no machine score).
        source_refs are preserved exactly as stored in the candidate observation.
        The evidence_fingerprint is copied to maintain traceability.
        """
        name_count = 0
        pub_count = 0
        for ev in evidence_rows:
            if ev.evidence_kind == "NAME":
                identity_evidence_type = "NAME_SIMILARITY"
                name_count += 1
            elif ev.evidence_kind == "PUBLICATION":
                reconciliation = ev.payload.get("reconciliation")
                identity_evidence_type = _map_publication_evidence_type(
                    reconciliation or "TITLE_EXACT"
                )
                pub_count += 1
            else:
                raise EvidencePromotionUnsupportedError(
                    f"Candidate evidence kind {ev.evidence_kind!r} "
                    f"is not supported for promotion"
                )

            identity_evidence = IdentityEvidence(
                id=uuid.uuid4(),
                identity_id=identity_id,
                evidence_type=identity_evidence_type,
                direction="SUPPORTS",
                confidence_score=None,  # never fabricated from human review
                algorithm_version=generation_run_version,
                features=dict(ev.payload),
                source_refs=list(ev.source_refs),
                evidence_fingerprint=ev.evidence_fingerprint,
            )
            self._session.add(identity_evidence)

        return name_count, pub_count

    def _record_audit_events(
        self,
        *,
        reviewer_user_id: uuid.UUID,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        event_metadata: dict,
        before_state: dict | None = None,
        after_state: dict | None = None,
        reason: str | None = None,
    ) -> None:
        """Append audit events within the current transaction.

        Actor is always USER (the human reviewer).
        The event is committed as part of the review transaction.
        """
        audit = AuditEvent(
            id=uuid.uuid4(),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_type="USER",
            actor_user_id=reviewer_user_id,
            actor_service=None,
            before_state=before_state,
            after_state=after_state,
            reason=reason,
            event_metadata=event_metadata,
            created_at=datetime.now(UTC),
        )
        self._session.add(audit)

    # ------------------------------------------------------------------
    # ACCEPT implementation
    # ------------------------------------------------------------------

    def _accept(self, cmd: AcceptCandidateCommand) -> AcceptResult:
        now = datetime.now(UTC)

        # 1. Authorize reviewer
        reviewer = self._authorize_reviewer(cmd.reviewer_user_id)

        # 2. Load and lock candidate (serializes concurrent reviews)
        candidate = self._load_and_lock_candidate(cmd.candidate_id)

        # 3. Detect exact idempotent prior decision
        existing_review = self._session.scalar(
            select(LecturerScopusCandidateReview)
            .where(
                LecturerScopusCandidateReview.candidate_id == cmd.candidate_id,
                LecturerScopusCandidateReview.observation_id == cmd.observation_id,
                LecturerScopusCandidateReview.action == "ACCEPT",
            )
        )
        if existing_review is not None:
            # Idempotent success — the exact same review was already accepted.
            # Verify the identity still exists and matches.
            if (
                existing_review.resulting_identity_id is not None
            ):
                identity = self._session.get(
                    LecturerScopusIdentity,
                    existing_review.resulting_identity_id,
                )
                if identity is not None and identity.status == "APPROVED":
                    return AcceptResult(
                        review_id=existing_review.id,
                        candidate_id=cmd.candidate_id,
                        observation_id=cmd.observation_id,
                        action="ACCEPT",
                        candidate_status="ACCEPTED",
                        candidate_version=candidate.version,
                        idempotent=True,
                        resulting_identity_id=existing_review.resulting_identity_id,
                    )
            # If identity was deleted or revoked, treat as conflict
            raise CandidateAlreadyDecidedError(
                f"Candidate {cmd.candidate_id} already decided "
                f"(review={existing_review.id})"
            )

        # 4. Validate current candidate state
        if candidate.status != "PENDING":
            raise CandidateAlreadyDecidedError(
                f"Candidate {cmd.candidate_id} has status {candidate.status!r}; "
                f"only PENDING candidates may be accepted"
            )

        # 5. Validate candidate_version (optimistic locking)
        if candidate.version != cmd.candidate_version:
            raise StaleCandidateVersionError(
                f"Submitted version {cmd.candidate_version} does not match "
                f"current version {candidate.version}"
            )

        # 6. Validate observation belongs to this candidate
        observation = self._load_observation(cmd.observation_id)
        if observation.candidate_id != cmd.candidate_id:
            raise ObservationCandidateMismatchError(
                f"Observation {cmd.observation_id} does not belong to "
                f"candidate {cmd.candidate_id}"
            )

        # 7. Validate observation is current/reviewable
        current_obs = self._resolve_current_reviewable_observation(cmd.candidate_id)
        if observation.id != current_obs.id:
            raise StaleCandidateObservationError(
                f"Submitted observation {cmd.observation_id} is not the "
                f"current reviewable observation {current_obs.id}"
            )

        # 8. Load immutable observation evidence
        evidence_rows = self._load_observation_evidence(cmd.observation_id)

        # Load generation run for version info
        run = self._session.get(CandidateGenerationRun, observation.generation_run_id)
        run_version = run.rule_set_version if run else "unknown"

        # 9. Validate identity conflicts (cardinality)
        self._check_identity_conflicts(
            candidate.lecturer_id,
            candidate.scopus_author_id,
        )

        # 10. Check for preexisting exact identity with no matching review
        # Case E: if exact identity exists with no CandidateReview provenance,
        # fail closed (do not falsely attribute it to this review).
        preexisting_identity = self._session.scalar(
            select(LecturerScopusIdentity)
            .where(
                LecturerScopusIdentity.lecturer_id == candidate.lecturer_id,
                LecturerScopusIdentity.scopus_author_id == candidate.scopus_author_id,
            )
        )
        if preexisting_identity is not None:
            # Check if there's a matching CandidateReview
            review_for_identity = self._session.scalar(
                select(LecturerScopusCandidateReview)
                .where(
                    LecturerScopusCandidateReview.candidate_id == cmd.candidate_id,
                    LecturerScopusCandidateReview.resulting_identity_id
                    == preexisting_identity.id,
                )
            )
            if review_for_identity is None:
                raise PreexistingIdentityConflictError(
                    f"Exact identity {preexisting_identity.id} already exists "
                    f"but has no CandidateReview provenance from this candidate. "
                    f"Cannot falsely attribute to this review."
                )

        # Build evidence snapshot BEFORE creating the identity (decision-time)
        snapshot = self._build_evidence_snapshot(
            candidate_id=candidate.id,
            lecturer_id=candidate.lecturer_id,
            scopus_author_id=candidate.scopus_author_id,
            observation_id=observation.id,
            observation_hash=observation.observation_hash,
            generation_run_id=observation.generation_run_id,
            generation_run_version=run_version,
            evidence_rows=evidence_rows,
        )

        # Captures for audit
        candidate_before = {
            "id": str(candidate.id),
            "status": candidate.status,
            "version": candidate.version,
        }

        # 11. Create LecturerScopusIdentity (APPROVED)
        identity = LecturerScopusIdentity(
            id=uuid.uuid4(),
            lecturer_id=candidate.lecturer_id,
            scopus_author_id=candidate.scopus_author_id,
            status="APPROVED",
            version=1,
            created_at=now,
            updated_at=now,
        )
        self._session.add(identity)
        self._session.flush()  # get the identity.id

        identity_after = {
            "id": str(identity.id),
            "status": identity.status,
            "lecturer_id": str(identity.lecturer_id),
            "scopus_author_id": str(identity.scopus_author_id),
        }

        # 12. Promote candidate evidence to IdentityEvidence
        name_count, pub_count = self._promote_candidate_evidence_to_identity(
            identity_id=identity.id,
            evidence_rows=evidence_rows,
            generation_run_version=run_version,
        )

        # 13. Create CandidateReview (references the resulting identity)
        review = LecturerScopusCandidateReview(
            id=uuid.uuid4(),
            candidate_id=candidate.id,
            observation_id=observation.id,
            reviewer_user_id=reviewer.id,
            action="ACCEPT",
            from_status="PENDING",
            to_status="ACCEPTED",
            candidate_version=candidate.version,
            reason=cmd.reason,
            evidence_snapshot=snapshot,
            resulting_identity_id=identity.id,
            created_at=now,
        )
        self._session.add(review)

        # 14. Transition candidate to ACCEPTED
        candidate.status = "ACCEPTED"
        # 15. Increment version (optimistic locking)
        candidate.version = candidate.version + 1
        candidate.updated_at = now

        candidate_after = {
            "id": str(candidate.id),
            "status": candidate.status,
            "version": candidate.version,
        }

        # 16. Create AuditEvents
        self._record_audit_events(
            reviewer_user_id=reviewer.id,
            action=AUDIT_ACTION_CANDIDATE_ACCEPTED,
            entity_type="lecturer_scopus_candidate",
            entity_id=candidate.id,
            event_metadata={
                "candidate_id": str(candidate.id),
                "observation_id": str(observation.id),
                "review_id": str(review.id),
                "resulting_identity_id": str(identity.id),
                "evidence_count": len(evidence_rows),
                "idempotent": False,
            },
            before_state=candidate_before,
            after_state=candidate_after,
            reason=cmd.reason,
        )
        self._record_audit_events(
            reviewer_user_id=reviewer.id,
            action=AUDIT_ACTION_IDENTITY_CREATED,
            entity_type="lecturer_scopus_identity",
            entity_id=identity.id,
            event_metadata={
                "identity_id": str(identity.id),
                "candidate_id": str(candidate.id),
                "review_id": str(review.id),
                "lecturer_id": str(candidate.lecturer_id),
                "scopus_author_id": str(candidate.scopus_author_id),
            },
            before_state=None,
            after_state=identity_after,
        )

        # 17. Commit once
        self._session.commit()

        return AcceptResult(
            review_id=review.id,
            candidate_id=candidate.id,
            observation_id=observation.id,
            action="ACCEPT",
            candidate_status="ACCEPTED",
            candidate_version=candidate.version,
            idempotent=False,
            resulting_identity_id=identity.id,
            name_evidence_promoted=name_count,
            publication_evidence_promoted=pub_count,
        )

    # ------------------------------------------------------------------
    # REJECT implementation
    # ------------------------------------------------------------------

    def _reject(self, cmd: RejectCandidateCommand) -> RejectResult:
        now = datetime.now(UTC)

        # 1. Authorize reviewer
        reviewer = self._authorize_reviewer(cmd.reviewer_user_id)

        # 2. Validate reason required
        if not cmd.reason or not cmd.reason.strip():
            raise InvalidReviewReasonError(
                "A non-blank reason is required for REJECT"
            )

        # 3. Load and lock candidate
        candidate = self._load_and_lock_candidate(cmd.candidate_id)

        # 4. Detect exact idempotent prior decision
        existing_review = self._session.scalar(
            select(LecturerScopusCandidateReview)
            .where(
                LecturerScopusCandidateReview.candidate_id == cmd.candidate_id,
                LecturerScopusCandidateReview.observation_id == cmd.observation_id,
                LecturerScopusCandidateReview.action == "REJECT",
            )
        )
        if existing_review is not None:
            return RejectResult(
                review_id=existing_review.id,
                candidate_id=cmd.candidate_id,
                observation_id=cmd.observation_id,
                action="REJECT",
                candidate_status="REJECTED",
                candidate_version=candidate.version,
                idempotent=True,
            )

        # 5. Validate current candidate state
        if candidate.status != "PENDING":
            raise CandidateAlreadyDecidedError(
                f"Candidate {cmd.candidate_id} has status {candidate.status!r}; "
                f"only PENDING candidates may be rejected"
            )

        # 6. Validate candidate_version
        if candidate.version != cmd.candidate_version:
            raise StaleCandidateVersionError(
                f"Submitted version {cmd.candidate_version} does not match "
                f"current version {candidate.version}"
            )

        # 7. Validate observation
        observation = self._load_observation(cmd.observation_id)
        if observation.candidate_id != cmd.candidate_id:
            raise ObservationCandidateMismatchError(
                f"Observation {cmd.observation_id} does not belong to "
                f"candidate {cmd.candidate_id}"
            )

        # 8. Validate observation is current
        current_obs = self._resolve_current_reviewable_observation(
            cmd.candidate_id
        )
        if observation.id != current_obs.id:
            raise StaleCandidateObservationError(
                f"Submitted observation {cmd.observation_id} is not the "
                f"current reviewable observation {current_obs.id}"
            )

        # 9. Load evidence
        evidence_rows = self._load_observation_evidence(cmd.observation_id)

        run = self._session.get(CandidateGenerationRun, observation.generation_run_id)
        run_version = run.rule_set_version if run else "unknown"

        # Build snapshot
        snapshot = self._build_evidence_snapshot(
            candidate_id=candidate.id,
            lecturer_id=candidate.lecturer_id,
            scopus_author_id=candidate.scopus_author_id,
            observation_id=observation.id,
            observation_hash=observation.observation_hash,
            generation_run_id=observation.generation_run_id,
            generation_run_version=run_version,
            evidence_rows=evidence_rows,
        )

        candidate_before = {
            "id": str(candidate.id),
            "status": candidate.status,
            "version": candidate.version,
        }

        # 10. Create CandidateReview (NO identity, NO IdentityEvidence)
        review = LecturerScopusCandidateReview(
            id=uuid.uuid4(),
            candidate_id=candidate.id,
            observation_id=observation.id,
            reviewer_user_id=reviewer.id,
            action="REJECT",
            from_status="PENDING",
            to_status="REJECTED",
            candidate_version=candidate.version,
            reason=cmd.reason.strip(),
            evidence_snapshot=snapshot,
            resulting_identity_id=None,
            created_at=now,
        )
        self._session.add(review)

        # 11. Transition candidate
        candidate.status = "REJECTED"
        candidate.version = candidate.version + 1
        candidate.updated_at = now

        candidate_after = {
            "id": str(candidate.id),
            "status": candidate.status,
            "version": candidate.version,
        }

        # 12. Create AuditEvent
        self._record_audit_events(
            reviewer_user_id=reviewer.id,
            action=AUDIT_ACTION_CANDIDATE_REJECTED,
            entity_type="lecturer_scopus_candidate",
            entity_id=candidate.id,
            event_metadata={
                "candidate_id": str(candidate.id),
                "observation_id": str(observation.id),
                "review_id": str(review.id),
                "evidence_count": len(evidence_rows),
                "idempotent": False,
            },
            before_state=candidate_before,
            after_state=candidate_after,
            reason=cmd.reason,
        )

        # 13. Commit once
        self._session.commit()

        return RejectResult(
            review_id=review.id,
            candidate_id=candidate.id,
            observation_id=cmd.observation_id,
            action="REJECT",
            candidate_status="REJECTED",
            candidate_version=candidate.version,
            idempotent=False,
        )


__all__ = [
    "AcceptCandidateCommand",
    "AcceptResult",
    "AUDIT_ACTION_CANDIDATE_ACCEPTED",
    "AUDIT_ACTION_CANDIDATE_REJECTED",
    "AUDIT_ACTION_IDENTITY_CREATED",
    "CandidateAlreadyDecidedError",
    "CandidateNotFoundError",
    "CandidateReviewError",
    "CandidateReviewService",
    "CANDIDATE_TO_IDENTITY_EVIDENCE_TYPE",
    "EvidencePromotionUnsupportedError",
    "InvalidReviewReasonError",
    "ObservationCandidateMismatchError",
    "ObservationNotFoundError",
    "PreexistingIdentityConflictError",
    "RejectCandidateCommand",
    "RejectResult",
    "ReviewResult",
    "ReviewerNotAuthorizedError",
    "ReviewerNotFoundError",
    "ScopusAuthorAlreadyApprovedError",
    "StaleCandidateObservationError",
    "StaleCandidateVersionError",
]
