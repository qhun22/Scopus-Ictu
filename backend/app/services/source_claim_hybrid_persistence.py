"""Append-only persistence for hybrid SOURCE_CLAIM proposals, approvals and revocations.

What this service may do: record that a human proposed something, that a second human
approved an institutional exception, or that an earlier event was revoked or superseded.

What it may **not** do, and has no code path for: accept a candidate, create or change a
``LecturerScopusIdentity``, write ``IdentityEvidence``, record a candidate or mapping
review, or finalize anything. There is no finalization table. ``submit`` still refuses
with ``SOURCE_CLAIM_WORKFLOW_INACTIVE``, so persisting history can never become an
acceptance by accident.

Trust rules every public method obeys:

* The snapshot written is the one **this** service just re-prepared from the database and
  the authorities. A caller-held receipt is only ever compared, never stored.
* Authorization is re-read at the action boundary, for every human involved, inside the
  same transaction as the write.
* The idempotency key is derived from the trusted snapshot, never supplied by a caller, so
  a retry resolves to the row already recorded and a tampered snapshot cannot reuse a key.
* The caller owns its transaction. Every write runs in its own SAVEPOINT; this module
  never commits, never rolls back the outer transaction and keeps no state outside the DB.
"""

from __future__ import annotations

import json
import uuid
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.models.governance import AuditEvent
from app.models.source_claim_hybrid import (
    EVIDENCE_KIND,
    SOURCE_TIER,
    HybridDecisionContext,
    HybridDecisionEvent,
    HybridExceptionApproval,
    HybridInstitutionalProvenance,
    HybridPolicyDocument,
    HybridReviewerProposal,
    HybridRevocation,
)
from app.services.matching.candidate_persistence import canonical_json, sha256_json
from app.services.source_claim_hybrid import (
    POLICY_DIGEST,
    POLICY_ENCODER,
    POLICY_FAMILY,
    POLICY_ID,
    POLICY_VERSION,
    RISK_ACKNOWLEDGMENT,
    AuthorityRequest,
    Grant,
    HybridSourceClaimCompatibility,
    ReviewBranch,
    SourceAuthenticityState,
    policy_document,
    verify_receipt,
)

# Namespace of the per-candidate advisory lock. Migration d0b14a77c8e2 hard-codes the same
# value (LOCK_NAMESPACE) so its triggers serialize with this service; a PG test pins both.
_LOCK_KEY = zlib.crc32(b"scopus-ictu:source-claim-hybrid") & 0x7FFFFFFF
_ENTITY = "sc_hybrid_event"
PROPOSE = "PROPOSE"
APPROVE_EXCEPTION = "APPROVE_EXCEPTION"
REVOCATION_KINDS = ("REVOKE", "SUPERSEDE")
# Only these may be compensated or serve as a replacement. A REVOKE or SUPERSEDE is final:
# revoking a revocation (or superseding one) is refused as an ambiguous transition.
COMPENSABLE_KINDS = (PROPOSE, APPROVE_EXCEPTION)
AUDIT_ACTIONS = {
    PROPOSE: "SOURCE_CLAIM_HYBRID_PROPOSAL_RECORDED",
    APPROVE_EXCEPTION: "SOURCE_CLAIM_HYBRID_EXCEPTION_APPROVAL_RECORDED",
    "REVOKE": "SOURCE_CLAIM_HYBRID_EVENT_REVOKED",
    "SUPERSEDE": "SOURCE_CLAIM_HYBRID_EVENT_SUPERSEDED",
}


@dataclass(frozen=True, slots=True)
class AppendResult:
    """What was recorded, or what was already there. Never a decision outcome."""

    outcome: str                  # APPENDED | ALREADY_RECORDED
    event_kind: str
    event_id: uuid.UUID
    stream_seq: int
    operation_key: str
    snapshot_hash: str
    envelope_hash: str
    final_acceptance: bool = False
    workflow_active: bool = False


def _refuse(code: str, status: int = 409, **data: Any) -> APIError:
    return APIError(status_code=status, code=code,
                    detail="The hybrid SOURCE_CLAIM history cannot record this action.",
                    data=data or None)


def _require(condition: object, code: str = "HYBRID_PERSISTENCE_SNAPSHOT_INVALID") -> None:
    if not condition:
        raise _refuse(code)


def _moment(value: object) -> datetime:
    _require(isinstance(value, datetime) and value.utcoffset() is not None,
             "HYBRID_TIMESTAMP_INVALID")
    return value.astimezone(UTC)                     # type: ignore[union-attr]


def _operation_key(kind: str, snapshot_hash: str) -> str:
    """Server-derived idempotency key: the action and the exact trusted snapshot.

    A caller cannot choose it, so two different snapshots can never share a key and the
    same snapshot replayed can never produce a second event.
    """
    return sha256_json({"kind": kind, "policy_digest": POLICY_DIGEST,
                        "snapshot_hash": snapshot_hash})


def _common_snapshot_invariants(snapshot: object) -> dict:
    _require(isinstance(snapshot, dict))
    value: dict = snapshot                           # type: ignore[assignment]
    _require(value.get("policy_id") == POLICY_ID
             and value.get("policy_version") == POLICY_VERSION
             and value.get("policy_family") == POLICY_FAMILY
             and value.get("policy_digest") == POLICY_DIGEST,
             "HYBRID_POLICY_VERSION_MISMATCH")
    # A snapshot that claims any kind of finality is refused outright: history records
    # proposals, not acceptances, and this gate activates no workflow.
    _require(value.get("final_acceptance") is False and value.get("workflow_active") is False
             and value.get("decision_enabled") is False)
    return value


class HybridDecisionJournal:
    """Append-only writer over the ``sc_hybrid_*`` relations."""

    def __init__(self, session: Session, *, authority=None,
                 compatibility: HybridSourceClaimCompatibility | None = None) -> None:
        self.session = session
        self.compat = compatibility if compatibility is not None else (
            HybridSourceClaimCompatibility(session, authority=authority))

    # -- public API ---------------------------------------------------------

    def record_proposal(self, actor, command, *, proposed_at,
                        receipt=None) -> AppendResult:
        """Re-prepare, then append one reviewer proposal for one revalidated context."""
        trusted = self.compat.prepare_proposal(actor, command, proposed_at=proposed_at)
        if receipt is not None:
            verify_receipt(receipt, trusted)
        snapshot = _common_snapshot_invariants(json.loads(trusted.snapshot_json))
        _require(snapshot.get("outcome") == "OFFLINE_PROPOSAL_PREPARED"
                 and snapshot.get("approver") is None and snapshot.get("approved_at") is None)
        branch = snapshot["branch"]
        _require(branch in tuple(ReviewBranch), "HYBRID_BRANCH_PRECEDENCE")
        _require(snapshot["conflict_evaluation"]["eligibility"]["required_branch"] == branch,
                 "HYBRID_BRANCH_PRECEDENCE")
        _require((snapshot.get("risk_acknowledgment") == RISK_ACKNOWLEDGMENT)
                 == (branch == ReviewBranch.INSTITUTIONAL_EXCEPTION))
        reviewer = snapshot["reviewer"]
        _require(reviewer["human_principal_id"] is not None
                 and reviewer["user_id"] == str(actor.user_id)
                 and reviewer["auth_version"] == actor.auth_version,
                 "HYBRID_HUMAN_AUTHORIZATION_REQUIRED")
        key = _operation_key(PROPOSE, trusted.snapshot_hash)
        candidate_id = uuid.UUID(snapshot["source_context"]["candidate"]["id"])
        with self._savepoint():
            recorded = self._recorded(key, PROPOSE, trusted.snapshot_hash)
            if recorded is not None:
                return recorded
            self._lock(candidate_id)
            recorded = self._recorded(key, PROPOSE, trusted.snapshot_hash)
            if recorded is not None:            # an identical request committed while we waited
                return recorded
            # Many historical proposals are fine; one effective proposal per candidate is not
            # negotiable. A replacement first needs a validated REVOKE/SUPERSEDE of the old one.
            active = self._effective_proposal(candidate_id)
            if active is not None:
                raise _refuse("HYBRID_ACTIVE_PROPOSAL_EXISTS", proposal_id=str(active))
            context_id = self._write_context(snapshot, trusted.snapshot_hash)
            event = self._append(PROPOSE, candidate_id, context_id, trusted, key,
                                 actor_user_id=uuid.UUID(reviewer["user_id"]),
                                 actor_principal_id=uuid.UUID(reviewer["human_principal_id"]),
                                 actor_auth_version=reviewer["auth_version"],
                                 action_at=_moment(proposed_at),
                                 metadata={"branch": branch, "context_id": str(context_id)})
            self.session.execute(insert(HybridReviewerProposal).values(
                proposal_id=event.event_id, context_id=context_id, candidate_id=candidate_id,
                candidate_version=snapshot["source_context"]["candidate"]["version"],
                policy_digest=POLICY_DIGEST, branch=branch,
                assurance_basis=snapshot["assurance_basis"],
                reviewer_user_id=uuid.UUID(reviewer["user_id"]),
                reviewer_principal_id=uuid.UUID(reviewer["human_principal_id"]),
                reviewer_auth_version=reviewer["auth_version"], reason=snapshot["reason"],
                risk_acknowledgment=snapshot.get("risk_acknowledgment")))
            return event

    def record_exception_approval(self, reviewer_actor, approver_actor, command, proposal, *,
                                  proposed_at, approved_at, receipt=None) -> AppendResult:
        """Append the second human's approval of an already recorded exception proposal.

        Both humans are re-authorized by the hybrid boundary in this transaction, and the
        proposal must already exist in history: an approval cannot invent its own subject.
        """
        trusted = self.compat.prepare_exception_approval(
            reviewer_actor, approver_actor, command, proposal,
            proposed_at=proposed_at, approved_at=approved_at)
        if receipt is not None:
            verify_receipt(receipt, trusted)
        snapshot = _common_snapshot_invariants(json.loads(trusted.snapshot_json))
        _require(snapshot.get("outcome") == "OFFLINE_APPROVAL_VALIDATED"
                 and snapshot["branch"] == ReviewBranch.INSTITUTIONAL_EXCEPTION
                 and snapshot.get("proposal_digest"))
        reviewer, approver = snapshot["reviewer"], snapshot["approver"]
        _require(approver is not None and approver["human_principal_id"] is not None
                 and approver["user_id"] == str(approver_actor.user_id)
                 and approver["auth_version"] == approver_actor.auth_version,
                 "HYBRID_HUMAN_AUTHORIZATION_REQUIRED")
        _require(approver["user_id"] != reviewer["user_id"]
                 and approver["human_principal_id"] != reviewer["human_principal_id"],
                 "HYBRID_SELF_APPROVAL_FORBIDDEN")
        key = _operation_key(APPROVE_EXCEPTION, trusted.snapshot_hash)
        with self._savepoint():
            recorded = self._recorded(key, APPROVE_EXCEPTION, trusted.snapshot_hash)
            if recorded is not None:
                return recorded
            row = self._proposal_of(snapshot["proposal_digest"])
            self._lock(row.candidate_id)
            recorded = self._recorded(key, APPROVE_EXCEPTION, trusted.snapshot_hash)
            if recorded is not None:            # an identical request committed while we waited
                return recorded
            # The approval is bound to that proposal's exact branch and reviewer, so an
            # approval prepared for one candidate cannot be attached to another.
            _require(row.branch == snapshot["branch"]
                     and str(row.reviewer_user_id) == reviewer["user_id"]
                     and str(row.reviewer_principal_id) == reviewer["human_principal_id"],
                     "HYBRID_APPROVAL_NOT_APPLICABLE")
            # The authoritative lifecycle is read under the stream lock: a revoked or
            # superseded proposal can never be approved.
            _require(not self._is_compensated(row.proposal_id), "HYBRID_PROPOSAL_NOT_EFFECTIVE")
            event = self._append(
                APPROVE_EXCEPTION, row.candidate_id, row.context_id, trusted, key,
                actor_user_id=uuid.UUID(approver["user_id"]),
                actor_principal_id=uuid.UUID(approver["human_principal_id"]),
                actor_auth_version=approver["auth_version"], action_at=_moment(approved_at),
                metadata={"proposal_id": str(row.proposal_id)})
            self.session.execute(insert(HybridExceptionApproval).values(
                approval_id=event.event_id, proposal_id=row.proposal_id,
                context_id=row.context_id, branch=row.branch,
                reviewer_user_id=row.reviewer_user_id,
                reviewer_principal_id=row.reviewer_principal_id,
                approver_user_id=uuid.UUID(approver["user_id"]),
                approver_principal_id=uuid.UUID(approver["human_principal_id"]),
                approver_auth_version=approver["auth_version"],
                proposal_digest=snapshot["proposal_digest"]))
            return event

    def record_revocation(self, initiator_actor, authorizer_actor, *, target_event_id,
                          revocation_kind, reason, decided_at,
                          replacement_event_id=None) -> AppendResult:
        """Append a REVOKE or SUPERSEDE of an earlier event; nothing is ever updated.

        Dual control applies here too, re-checked against the current authorities, and
        the target's own context is what scopes that check — not caller input.
        """
        _require(revocation_kind in REVOCATION_KINDS, "HYBRID_REVOCATION_INVALID")
        _require((replacement_event_id is not None) == (revocation_kind == "SUPERSEDE"),
                 "HYBRID_REVOCATION_INVALID")
        _require(isinstance(reason, str) and bool(reason.strip()) and len(reason) <= 4000
                 and not any(ord(c) < 32 or ord(c) == 127 for c in reason),
                 "HYBRID_REASON_INVALID")
        moment = _moment(decided_at)
        with self._savepoint():
            target = self.session.get(HybridDecisionEvent, target_event_id)
            _require(target is not None, "HYBRID_REVOCATION_TARGET_NOT_FOUND")
            context = self.session.get(HybridDecisionContext, target.context_id)
            _require(context is not None, "HYBRID_REVOCATION_TARGET_NOT_FOUND")
            # Event kinds are immutable, so the transition table can be checked up front.
            _require(target.event_kind in COMPENSABLE_KINDS, "HYBRID_REVOCATION_TARGET_INVALID")
            replacement = None
            if replacement_event_id is not None:
                replacement = self.session.get(HybridDecisionEvent, replacement_event_id)
                _require(replacement is not None
                         and replacement.event_id != target.event_id
                         and replacement.stream_candidate_id == target.stream_candidate_id
                         and replacement.event_kind in COMPENSABLE_KINDS
                         and replacement.stream_seq > target.stream_seq,
                         "HYBRID_REVOCATION_INVALID")
            initiator, authorizer = self._dual_control(
                context, (initiator_actor, authorizer_actor))
            snapshot = {
                "schema_version": 1, "policy_id": POLICY_ID, "policy_version": POLICY_VERSION,
                "policy_family": POLICY_FAMILY, "policy_digest": POLICY_DIGEST,
                "kind": revocation_kind, "decided_at": moment.isoformat(),
                "target_event_id": str(target.event_id),
                "target_event_kind": target.event_kind,
                "target_envelope_hash": target.envelope_hash,
                "replacement_event_id": (None if replacement is None
                                         else str(replacement.event_id)),
                "context_digest": context.context_digest, "reason": reason.strip(),
                "initiator": _principal(initiator), "authorizer": _principal(authorizer),
                "final_acceptance": False, "workflow_active": False, "decision_enabled": False,
            }
            trusted = _Receipt(canonical_json(snapshot), sha256_json(snapshot))
            key = _operation_key(revocation_kind, trusted.snapshot_hash)
            # The stream lock comes first, so both checks below see every committed writer.
            # Idempotency first: an identical retry resolves to the recorded event. Only
            # then is a *different* compensation of an already-compensated target refused.
            self._lock(target.stream_candidate_id)
            recorded = self._recorded(key, revocation_kind, trusted.snapshot_hash)
            if recorded is not None:
                return recorded
            _require(self.session.scalar(select(HybridRevocation.revocation_id).where(
                HybridRevocation.target_event_id == target.event_id)) is None,
                "HYBRID_EVENT_ALREADY_REVOKED")
            # A replacement that was itself compensated is no longer a valid replacement.
            _require(replacement is None or not self._is_compensated(replacement.event_id),
                     "HYBRID_REVOCATION_INVALID")
            event = self._append(
                revocation_kind, target.stream_candidate_id, context.id, trusted, key,
                actor_user_id=initiator.user_id,
                actor_principal_id=initiator.human_principal_id,
                actor_auth_version=initiator.auth_version, action_at=moment,
                metadata={"target_event_id": str(target.event_id)})
            self.session.execute(insert(HybridRevocation).values(
                revocation_id=event.event_id, target_event_id=target.event_id,
                revocation_kind=revocation_kind,
                replacement_event_id=None if replacement is None else replacement.event_id,
                initiator_user_id=initiator.user_id,
                initiator_principal_id=initiator.human_principal_id,
                authorizer_user_id=authorizer.user_id,
                authorizer_principal_id=authorizer.human_principal_id,
                reason=reason.strip()))
            return event

    def submit(self, *args, **kwargs):
        """Recording history never unlocks acceptance; this stays permanently closed."""
        raise _refuse("SOURCE_CLAIM_WORKFLOW_INACTIVE")

    # -- internals ---------------------------------------------------------

    @property
    def _dialect(self) -> str:
        return self.session.get_bind().dialect.name

    def _savepoint(self):
        """Flush pending caller work first, so a prior failure is not absorbed here."""
        self.session.flush()
        return _Savepoint(self.session)

    def _lock(self, candidate_id: uuid.UUID) -> None:
        """Serialize appends to one candidate's stream (PostgreSQL); SQLite serializes."""
        if self._dialect == "postgresql":
            # hashtext() of the uuid text is what the database triggers compute too.
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(:ns, hashtext(:candidate))"),
                {"ns": _LOCK_KEY, "candidate": str(candidate_id)})

    def _is_compensated(self, event_id: uuid.UUID) -> bool:
        return self.session.scalar(select(HybridRevocation.revocation_id).where(
            HybridRevocation.target_event_id == event_id)) is not None

    def _effective_proposal(self, candidate_id: uuid.UUID) -> uuid.UUID | None:
        """A proposal of this candidate that no REVOKE/SUPERSEDE has compensated."""
        return self.session.scalar(select(HybridReviewerProposal.proposal_id).where(
            HybridReviewerProposal.candidate_id == candidate_id,
            HybridReviewerProposal.proposal_id.not_in(
                select(HybridRevocation.target_event_id))).limit(1))

    def _dual_control(self, context, actors):
        """Fresh authorization of two distinct humans, scoped to the stored context."""
        provenance = self.session.scalars(select(HybridInstitutionalProvenance).where(
            HybridInstitutionalProvenance.context_id == context.id)).all()
        _require(bool(provenance), "HYBRID_PROVENANCE_MISSING")
        # The authority scope is the stored *source* context hash: exactly the scope the
        # proposal was authorized under, so a compensation cannot widen it.
        request = AuthorityRequest(
            context.source_context_hash, context.candidate_id, context.candidate_version,
            context.lecturer_id, context.scopus_author_id,
            tuple(sorted({p.claimed_scopus_id for p in provenance})),
            tuple(sorted({p.artifact_id for p in provenance}, key=str)),
            tuple(dict.fromkeys(a.user_id for a in actors)))
        with self.session.no_autoflush:
            with Session(bind=self.session.connection(), autoflush=False,
                         join_transaction_mode="create_savepoint") as view:
                _, humans = self.compat.authorize_principals(
                    view, actors, request, grant=Grant.APPROVE_EXCEPTION)
                return humans

    def _recorded(self, key: str, kind: str, snapshot_hash: str) -> AppendResult | None:
        """Resolve a retry to the row already recorded, or refuse a key collision."""
        event = self.session.scalar(select(HybridDecisionEvent).where(
            HybridDecisionEvent.operation_key == key))
        if event is None:
            return None
        if event.event_kind != kind or event.snapshot_hash != snapshot_hash:
            raise _refuse("HYBRID_OPERATION_REPLAY_CONFLICT", event_id=str(event.event_id))
        return AppendResult("ALREADY_RECORDED", event.event_kind, event.event_id,
                            event.stream_seq, key, event.snapshot_hash, event.envelope_hash)

    def _proposal_of(self, proposal_digest: str) -> HybridReviewerProposal:
        context_id = self.session.scalar(select(HybridDecisionContext.id).where(
            HybridDecisionContext.context_digest == proposal_digest))
        row = None if context_id is None else self.session.scalar(
            select(HybridReviewerProposal).where(
                HybridReviewerProposal.context_id == context_id))
        if row is None:
            raise _refuse("HYBRID_PROPOSAL_NOT_RECORDED")
        return row

    def _write_context(self, snapshot: dict, context_digest: str) -> uuid.UUID:
        """Insert the context and its institutional provenance; both are immutable."""
        source = snapshot["source_context"]
        candidate, reviewer = source["candidate"], snapshot["reviewer"]
        self._insert_ignore(HybridPolicyDocument, dict(
            policy_digest=POLICY_DIGEST, policy_family=POLICY_FAMILY, policy_id=POLICY_ID,
            policy_revision=POLICY_VERSION, encoder_version=POLICY_ENCODER,
            policy_json=canonical_json(policy_document())))
        context_id = uuid.uuid4()
        self.session.execute(insert(HybridDecisionContext).values(
            id=context_id, context_digest=context_digest, policy_digest=POLICY_DIGEST,
            candidate_id=uuid.UUID(candidate["id"]), candidate_version=candidate["version"],
            lecturer_id=uuid.UUID(candidate["lecturer_id"]),
            scopus_author_id=uuid.UUID(candidate["scopus_author_id"]),
            observation_id=uuid.UUID(source["observation"]["id"]),
            generation_run_id=uuid.UUID(source["generation"]["id"]),
            reviewer_user_id=uuid.UUID(reviewer["user_id"]),
            reviewer_auth_version=reviewer["auth_version"],
            source_context_hash=snapshot["source_context_hash"],
            trusted_evidence_hash=source["trusted_evidence_hash"],
            authority_revision_digest=snapshot["authority_revision_digest"]))
        entries = snapshot["institutional_provenance"]
        _require(bool(entries), "HYBRID_PROVENANCE_MISSING")
        for item in entries:
            verification = item.get("verification")
            _require(item["evidence_kind"] == EVIDENCE_KIND
                     and item["source_tier"] == SOURCE_TIER)
            # A revoked institutional source is refused upstream and is not storable.
            _require(verification is None
                     or verification["state"] != SourceAuthenticityState.REVOKED,
                     "HYBRID_SOURCE_REVOKED")
            self.session.execute(insert(HybridInstitutionalProvenance).values(
                context_id=context_id, artifact_id=uuid.UUID(item["artifact_id"]),
                analysis_id=uuid.UUID(item["analysis_id"]),
                record_id=uuid.UUID(item["source_record_id"]),
                claim_id=uuid.UUID(item["claim_id"]),
                capture_id=uuid.UUID(item["capture_id"]),
                source_system=item["source_system"], source_tier=SOURCE_TIER,
                evidence_kind=EVIDENCE_KIND, independently_verified=False,
                claimed_scopus_id=item["claimed_scopus_id"],
                captured_at=item["captured_at"],
                artifact_digest=item["immutable_snapshot_digest"],
                record_digest=item["source_record_digest"],
                issuance_state=None if verification is None else verification["state"],
                issuance_verification_id=(
                    None if verification is None
                    else uuid.UUID(verification["verification_id"])),
                issuance_verification_digest=(
                    None if verification is None else verification["verification_digest"]),
                issuance_verification_method=(
                    None if verification is None else verification["verification_method"])))
        return context_id

    def _append(self, kind: str, candidate_id: uuid.UUID, context_id: uuid.UUID, trusted,
                operation_key: str, *, actor_user_id, actor_principal_id, actor_auth_version,
                action_at: datetime, metadata: dict) -> AppendResult:
        """Append one hash-chained event to this candidate's stream."""
        head = self.session.scalars(select(HybridDecisionEvent).where(
            HybridDecisionEvent.stream_candidate_id == candidate_id).order_by(
            HybridDecisionEvent.stream_seq.desc()).limit(1)).first()
        stream_seq = 1 if head is None else head.stream_seq + 1
        event_id, audit_id = uuid.uuid4(), uuid.uuid4()
        envelope = {
            "schema_version": 1, "event_kind": kind, "event_id": str(event_id),
            "stream_candidate_id": str(candidate_id), "stream_seq": stream_seq,
            "previous_event_id": None if head is None else str(head.event_id),
            "previous_event_hash": None if head is None else head.envelope_hash,
            "policy_digest": POLICY_DIGEST, "context_id": str(context_id),
            "operation_key": operation_key, "snapshot_hash": trusted.snapshot_hash,
            "actor": {"type": "USER", "user_id": str(actor_user_id),
                      "human_principal_id": str(actor_principal_id),
                      "auth_version": actor_auth_version},
            "action_at": action_at.isoformat(),
        }
        envelope_json, envelope_hash = canonical_json(envelope), sha256_json(envelope)
        self.session.execute(insert(AuditEvent).values(
            id=audit_id, entity_type=_ENTITY, entity_id=event_id, action=AUDIT_ACTIONS[kind],
            actor_type="USER", actor_user_id=actor_user_id, actor_service=None,
            event_metadata={**metadata, "operation_key": operation_key,
                            "envelope_hash": envelope_hash, "final_acceptance": False}))
        self.session.execute(insert(HybridDecisionEvent).values(
            event_id=event_id, stream_candidate_id=candidate_id, stream_seq=stream_seq,
            previous_event_id=None if head is None else head.event_id,
            previous_event_hash=None if head is None else head.envelope_hash,
            previous_stream_seq=None if head is None else head.stream_seq,
            event_kind=kind, context_id=context_id, policy_digest=POLICY_DIGEST,
            actor_type="USER", actor_user_id=actor_user_id, actor_service=None,
            actor_principal_id=actor_principal_id, actor_auth_version=actor_auth_version,
            operation_key=operation_key, snapshot_hash=trusted.snapshot_hash,
            snapshot_json=trusted.snapshot_json, envelope_hash=envelope_hash,
            envelope_json=envelope_json, audit_event_id=audit_id, action_at=action_at))
        return AppendResult("APPENDED", kind, event_id, stream_seq, operation_key,
                            trusted.snapshot_hash, envelope_hash)

    def _insert_ignore(self, model, values: dict) -> bool:
        dialect_insert = postgresql.insert if self._dialect == "postgresql" else sqlite.insert
        stmt = dialect_insert(model.__table__).values(**values).on_conflict_do_nothing()
        return self.session.execute(stmt).rowcount == 1


@dataclass(frozen=True, slots=True)
class _Receipt:
    """Same shape as a prepared hybrid receipt, for internally generated snapshots."""

    snapshot_json: str
    snapshot_hash: str


def _principal(human) -> dict:
    return {"user_id": str(human.user_id), "human_principal_id": str(human.human_principal_id),
            "auth_version": human.auth_version, "attestation_id": str(human.attestation_id),
            "revision_digest": human.revision_digest}


class _Savepoint:
    """``begin_nested()`` that reports an unexpected constraint violation as a refusal."""

    def __init__(self, session: Session) -> None:
        self.session, self.tx = session, None

    def __enter__(self):
        self.tx = self.session.begin_nested()
        return self.tx

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.tx.commit()
            return False
        self.tx.rollback()
        if isinstance(exc, IntegrityError):
            raise _refuse("HYBRID_HISTORY_INTEGRITY_VIOLATION",
                          constraint=type(exc.orig).__name__) from exc
        return False
