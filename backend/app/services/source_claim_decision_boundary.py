"""Inactive SOURCE_CLAIM decision compatibility, not a new review handler.

The existing IdentityEvidence vocabulary cannot represent institutional claims.
Prepare/replay a trusted prospective ACCEPT snapshot, but always refuse execution.
No route, feature switch, promotion, identity/review/audit write or external effect.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateObservation,
    LecturerScopusCandidateReview,
)
from app.models.governance import User
from app.models.identity import LecturerScopusIdentity
from app.services.candidate_evidence_read import _historical_captures, source_claim_read_preview
from app.services.matching.candidate_persistence import (
    GenerationRunConflict,
    canonical_json,
    sha256_json,
)
from app.services.matching.source_claim_candidate_persistence import (
    RULE_SET_ID,
    RULE_SET_VERSION,
    SourceClaimCandidateWriter,
)
from app.services.review_reason_policy import accept_reason_policy, normalize_reason


@dataclass(frozen=True, slots=True)
class ReviewerContext:
    """SERVER-BOUND authenticated principal; never populate from request fields.

    A future route must derive both values from existing get_current_user /
    require_role. The offline service cannot authenticate a JWT by itself.
    """

    user_id: uuid.UUID
    auth_version: int


@dataclass(frozen=True, slots=True)
class SourceClaimAcceptContext:
    candidate_id: uuid.UUID
    observation_id: uuid.UUID
    candidate_version: int
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedSourceClaimDecision:
    """Immutable detached draft, not a recorded or authorized decision."""

    snapshot_json: str
    snapshot_hash: str


def _refuse(code: str, status: int = 409, *, triggers=()):
    return APIError(status_code=status, code=code,
                    detail="SOURCE_CLAIM decision context is unavailable or not authorized.",
                    data={"reason_triggers": list(triggers)} if triggers else None)


def _authorize(view: Session, actor: ReviewerContext) -> User:
    if (not isinstance(actor, ReviewerContext) or not isinstance(actor.user_id, uuid.UUID)
            or type(actor.auth_version) is not int or actor.auth_version < 1):
        raise _refuse("AUTHENTICATION_REQUIRED", 401)
    user = view.get(User, actor.user_id)
    if user is None or user.auth_version != actor.auth_version:
        raise _refuse("SESSION_REVOKED", 401)
    if not user.is_active:
        raise _refuse("ACCOUNT_LOCKED", 403)
    if user.role not in {"ADMIN", "REVIEWER"}:
        raise _refuse("FORBIDDEN", 403)
    return user


def _capture_history(descriptors, captures, parsed_captures):
    """Prospective decisions require COMPLETE latest comparable captures.

    Older PARTIAL captures remain history. Equal instants are a set, not ordered
    by UUID. This is eligibility validation, not another source matching engine.
    """
    scopes = {(e["payload"]["source_system"], e["payload"]["scope_key"],
               e["payload"]["projection_version"]) for e in descriptors}
    selected = []
    for scope in sorted(scopes):
        group = [c for c in captures if (
            c["source_system"], c["scope_key"], c["projection_version"]) == scope]
        if not group:
            raise _refuse("SOURCE_CLAIM_DECISION_INCOMPLETE")
        latest = max(parsed_captures[c["capture_id"]]["captured_at"] for c in group)
        frontier = [c for c in group
                    if parsed_captures[c["capture_id"]]["captured_at"] == latest]
        if any(c["completeness"] != "COMPLETE" for c in frontier):
            raise _refuse("SOURCE_CLAIM_DECISION_INCOMPLETE")
        selected.extend(group)
    return sorted(selected, key=canonical_json)


class SourceClaimDecisionBoundary:
    """Caller transaction stays owned by caller; no workflow activation path."""

    def __init__(self, session: Session):
        self.session = session

    def prepare(self, actor: ReviewerContext, command: SourceClaimAcceptContext):
        """Revalidate a prospective decision; return a deterministic inactive draft.

        A fresh identity map avoids trusting cached role/candidate/source objects.
        Bind to the caller's existing connection with an owned SAVEPOINT, not a
        new engine/outer transaction. Closing the view rolls back its savepoint
        only. Pending caller changes are deliberately NOT autoflushed or expired.
        No mutation is attempted, even for fully valid evidence.
        """
        with self.session.no_autoflush:
            with Session(bind=self.session.connection(), autoflush=False,
                         join_transaction_mode="create_savepoint") as view:
                user = _authorize(view, actor)
                return self._prepare(view, user, command)

    @staticmethod
    def _prepare(view, user, command):
        if (not isinstance(command, SourceClaimAcceptContext)
                or not isinstance(command.candidate_id, uuid.UUID)
                or not isinstance(command.observation_id, uuid.UUID)
                or type(command.candidate_version) is not int or command.candidate_version < 1
                or (command.reason is not None and (
                    not isinstance(command.reason, str) or len(command.reason) > 4000))):
            raise _refuse("SOURCE_CLAIM_DECISION_COMMAND_INVALID", 422)
        candidate = view.get(LecturerScopusCandidate, command.candidate_id)
        if candidate is None:
            raise _refuse("CANDIDATE_NOT_FOUND", 404)
        if candidate.status != "PENDING":
            raise _refuse("CANDIDATE_ALREADY_DECIDED_CONFLICT")
        if candidate.version != command.candidate_version:
            raise _refuse("STALE_CANDIDATE_VERSION")
        # There is no accepted source-decision REOPEN/idempotent-decision policy
        # yet. A PENDING flag must not erase existing human-review history.
        prior_review = view.scalar(select(LecturerScopusCandidateReview.id).where(
            LecturerScopusCandidateReview.candidate_id == candidate.id).limit(1))
        if prior_review is not None:
            raise _refuse("SOURCE_CLAIM_PRIOR_REVIEW_REQUIRES_POLICY")
        observation = view.get(LecturerScopusCandidateObservation, command.observation_id)
        if observation is None or observation.candidate_id != candidate.id:
            raise _refuse("OBSERVATION_CANDIDATE_MISMATCH")
        run = view.get(CandidateGenerationRun, observation.generation_run_id)
        if (run is None or run.status != "STAGED" or run.rule_set_id != RULE_SET_ID
                or run.rule_set_version != RULE_SET_VERSION):
            raise _refuse("SOURCE_CLAIM_DECISION_CONTEXT_UNSUPPORTED")
        parsed_captures = _historical_captures(run.source_state)
        writer = SourceClaimCandidateWriter(view)
        # Reuse B1's pure trusted preparation/replay contract; do not persist or
        # replace accepted B1/B2-A logic. Internal interface dependency is tested.
        try:
            state, items = writer._prepare()
        except GenerationRunConflict as exc:
            raise _refuse("SOURCE_CLAIM_DECISION_NOT_CURRENT") from exc
        if state != run.source_state:
            raise _refuse("STALE_SOURCE_CLAIM_DECISION_CONTEXT")
        try:
            writer._verify_run(run, state, items)
        except GenerationRunConflict as exc:
            raise _refuse("SOURCE_CLAIM_DECISION_EVIDENCE_INVALID") from exc
        item = next((i for i in items if i["pair"] == (
            candidate.lecturer_id, candidate.scopus_author_id)), None)
        if item is None or not item["evidence"]:
            raise _refuse("SOURCE_CLAIM_DECISION_NOT_CURRENT")
        descriptors = item["evidence"]
        if any(e["evidence_kind"] != "SOURCE_CLAIM"
               or e["payload"]["source_tier"] != "INSTITUTION_DECLARED"
               or e["payload"]["current_state"] != "CURRENT"
               or e["payload"]["current_weight"] != 1 for e in descriptors):
            raise _refuse("SOURCE_CLAIM_DECISION_NOT_CURRENT")
        identities = view.scalars(select(LecturerScopusIdentity).where(
            LecturerScopusIdentity.scopus_author_id == candidate.scopus_author_id)).all()
        for identity in identities:
            if identity.lecturer_id == candidate.lecturer_id:
                code = ("IDENTITY_REVIEWER_REOPEN_REQUIRED"
                        if identity.status in {"REJECTED", "REVOKED"}
                        else "PREEXISTING_IDENTITY_PROVENANCE_CONFLICT")
                raise _refuse(code)
            if identity.status == "APPROVED":
                raise _refuse("SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER")
        if item["snapshot"]["pair"]["reasons"]:
            raise _refuse("SOURCE_CLAIM_OWNERSHIP_CONFLICT")
        captures = _capture_history(descriptors, state["captures"], parsed_captures)
        policy = accept_reason_policy(
            view, lecturer_id=candidate.lecturer_id, scopus_author_id=candidate.scopus_author_id,
            evidence_kinds=["SOURCE_CLAIM"],
        )
        reason = normalize_reason(command.reason)
        if policy.required and reason is None:
            raise _refuse("REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE", 422,
                          triggers=policy.triggers)
        preview = source_claim_read_preview(view, candidate.id)
        selected_fingerprints = {e["fingerprint"] for e in descriptors}
        current_items = [i.model_dump(mode="json") for i in preview.items
                         if i.evidence_fingerprint in selected_fingerprints]
        if len(current_items) != len(selected_fingerprints) or any(
            i["current_state"] != "CURRENT" or i["current_weight"] != 1 for i in current_items
        ):
            raise _refuse("SOURCE_CLAIM_DECISION_NOT_CURRENT")
        snapshot = {
            "schema_version": 1, "boundary": "E3-P3-B2-B", "intended_action": "ACCEPT",
            "workflow_active": False, "decision_enabled": False,
            "identity_evidence_promotion": "BLOCKED_OWNER_POLICY_REQUIRED",
            "reviewer": {"id": user.id, "role": user.role, "auth_version": user.auth_version},
            "candidate": {"id": candidate.id, "status": candidate.status,
                          "version": candidate.version, "lecturer_id": candidate.lecturer_id,
                          "scopus_author_id": candidate.scopus_author_id},
            "observation": {"id": observation.id, "hash": observation.observation_hash},
            "generation": {"id": run.id, "status": run.status, "rule_set_id": run.rule_set_id,
                           "rule_set_version": run.rule_set_version,
                           "input_hash": state["input_hash"]},
            "active_rule_set": state["active_rule_set"], "capture_history": captures,
            "logical_fingerprints": sorted(selected_fingerprints),
            "trusted_evidence_hash": sha256_json(descriptors),
            "evidence": current_items,
            "review_policy": {"accept_reason_required": policy.required,
                              "reason_triggers": list(policy.triggers), "reason": reason},
        }
        return PreparedSourceClaimDecision(canonical_json(snapshot), sha256_json(snapshot))

    def verify_replay(self, actor, command, snapshot_json, snapshot_hash):
        """Client/draft hashes never authorize: compare the full fresh trusted context."""
        trusted = self.prepare(actor, command)
        try:
            value = json.loads(snapshot_json)
            matches = (isinstance(value, dict) and isinstance(snapshot_hash, str)
                       and sha256_json(value) == snapshot_hash == trusted.snapshot_hash
                       and canonical_json(value) == trusted.snapshot_json)
        except (TypeError, ValueError) as exc:
            raise _refuse("SOURCE_CLAIM_DECISION_SNAPSHOT_INVALID") from exc
        if not matches:
            raise _refuse("SOURCE_CLAIM_DECISION_SNAPSHOT_INVALID")
        return trusted

    def submit(self, actor, command, snapshot_json, snapshot_hash):
        """Permanent-in-this-gate kill switch; no configuration/client bypass."""
        self.verify_replay(actor, command, snapshot_json, snapshot_hash)
        raise _refuse("SOURCE_CLAIM_WORKFLOW_INACTIVE")
