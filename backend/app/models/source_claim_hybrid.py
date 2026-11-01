"""Hybrid SOURCE_CLAIM authority/decision persistence (Gate E.3 / P3-B2-D): append-only.

Every row here is insert-only. There is deliberately **no finalization table**: these
relations record reviewer proposals, dual-control institutional-exception approvals and
revocation/supersession events only. Nothing in this module can change a candidate's
status, create an identity, promote IdentityEvidence or record a MappingReview, so
persisting a row is never an acceptance. SOURCE_CLAIM production submit stays inactive.

Frozen contracts are untouched: no existing table, constraint or index is altered, and
no composite key is added to a frozen table. Human principals and capability grants live
in external registries that this repository does not own, so those columns are plain
UUIDs validated by the append boundary — not foreign keys into an invented local registry.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.source_staging import SOURCE_SYSTEMS

_ID = dict(primary_key=True, server_default=text("gen_random_uuid()"))
_NOW = text("now()")

EVENT_KINDS = ("PROPOSE", "APPROVE_EXCEPTION", "REVOKE", "SUPERSEDE")
BRANCHES = ("STANDARD_INDEPENDENT", "INSTITUTIONAL_EXCEPTION")
ASSURANCE_BASES = ("INDEPENDENT_VERIFIED", "INSTITUTIONAL_EXCEPTION")
REVOCATION_KINDS = ("REVOKE", "SUPERSEDE")
# A recorded institutional source is CURRENT or UNVERIFIED; REVOKED is refused upstream
# and is intentionally not storable, so history can never claim a revoked issuance.
ISSUANCE_STATES = ("CURRENT", "UNVERIFIED")
SOURCE_TIER = "INSTITUTION_DECLARED"
EVIDENCE_KIND = "SOURCE_CLAIM"

# The same SQL idioms the staging schema uses, restated locally so this module adds no
# dependency on another model module's internals.


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _hex(column: str) -> str:
    return f"{column} ~ '^[0-9a-f]{{64}}$'"


def _json_sha(json_column: str, hash_column: str) -> str:
    return f"{hash_column} = encode(sha256(convert_to({json_column}, 'UTF8')), 'hex')"


def _not_blank(column: str) -> str:
    return f"btrim({column}) <> ''"


def _both_or_neither(*columns: str) -> str:
    first, rest = columns[0], columns[1:]
    return " AND ".join(f"({first} IS NULL) = ({other} IS NULL)" for other in rest)


class HybridPolicyDocument(Base):
    """One immutable policy revision; ``policy_digest`` is the hash of the exact bytes.

    Activation is not a mutable flag: a decision event binds the digest it was taken
    under, so replaying old history never silently adopts newer policy semantics.
    """

    __tablename__ = "sc_hybrid_policies"

    policy_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_family: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    encoder_version: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        CheckConstraint(_hex("policy_digest"), name="policy_digest"),
        CheckConstraint(_json_sha("policy_json", "policy_digest"), name="policy_digest_matches"),
        CheckConstraint(_not_blank("policy_family"), name="policy_family_not_empty"),
        CheckConstraint(_not_blank("policy_id"), name="policy_id_not_empty"),
        CheckConstraint(_not_blank("encoder_version"), name="encoder_version_not_empty"),
        CheckConstraint("policy_revision >= 1", name="policy_revision"),
        UniqueConstraint("policy_family", "policy_revision",
                         name="uq_sc_hybrid_policies_family_revision"),
    )


class HybridDecisionContext(Base):
    """The exact revalidated pair/source/policy context a decision event was taken on.

    ``context_digest`` is the trusted proposal snapshot hash produced by the offline
    hybrid boundary; it binds candidate, version, reviewer, policy revision, source
    descriptors and authority revision together, so no field can be swapped afterwards.
    """

    __tablename__ = "sc_hybrid_contexts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_ID)
    context_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(
        String(64), ForeignKey("sc_hybrid_policies.policy_digest", ondelete="RESTRICT"),
        nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lecturer_scopus_candidates.id", ondelete="RESTRICT"),
        nullable=False)
    candidate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    lecturer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lecturers.id", ondelete="RESTRICT"), nullable=False)
    scopus_author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopus_authors.id", ondelete="RESTRICT"), nullable=False)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturer_scopus_candidate_observations.id", ondelete="RESTRICT",
                   name="fk_sc_hybrid_contexts_observation_id"), nullable=False)
    generation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_generation_runs.id", ondelete="RESTRICT",
                                       name="fk_sc_hybrid_contexts_generation_run_id"),
        nullable=False)
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewer_auth_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    trusted_evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    authority_revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        CheckConstraint(_hex("context_digest"), name="context_digest"),
        CheckConstraint(_hex("source_context_hash"), name="source_context_hash"),
        CheckConstraint(_hex("trusted_evidence_hash"), name="trusted_evidence_hash"),
        CheckConstraint(_hex("authority_revision_digest"), name="authority_revision_digest"),
        CheckConstraint("candidate_version >= 1", name="candidate_version"),
        CheckConstraint("reviewer_auth_version >= 1", name="reviewer_auth_version"),
        UniqueConstraint("context_digest", name="uq_sc_hybrid_contexts_context_digest"),
        # Composite target so a child row cannot silently point at another pair, version
        # or policy revision than the context it claims.
        UniqueConstraint("id", "candidate_id", "candidate_version", "policy_digest",
                         name="uq_sc_hybrid_contexts_pair_policy"),
        # Target of the event -> context FK: an event's stream and policy are its context's.
        UniqueConstraint("id", "candidate_id", "policy_digest",
                         name="uq_sc_hybrid_contexts_candidate_policy"),
        Index("ix_sc_hybrid_contexts_candidate", "candidate_id", "created_at"),
    )


class HybridInstitutionalProvenance(Base):
    """Immutable institutional lineage selected for one context; never verified evidence.

    ``independently_verified`` is CHECK-pinned to FALSE: the database itself refuses to
    hold an institutional declaration that claims independent verification.
    """

    __tablename__ = "sc_hybrid_provenance"

    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_hybrid_contexts.id", ondelete="RESTRICT"),
        primary_key=True)
    # No foreign key into the staging tables, on purpose. The accepted E3-P2-B1 contract
    # is that staging is pre-identity and nothing downstream points into it, and that
    # contract is not reopened here. The append boundary revalidates the full lineage
    # (artifact ↔ capture ↔ content, record ↔ analysis ↔ claim, claim value and
    # validation status) against the live staging rows before inserting, and the digests
    # below pin the exact bytes, so a drifted row no longer matches what was recorded.
    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    capture_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_tier: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    independently_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE"))
    claimed_scopus_id: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    issuance_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    issuance_verification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    issuance_verification_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issuance_verification_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        CheckConstraint(_in("source_system", SOURCE_SYSTEMS), name="source_system"),
        CheckConstraint(f"source_tier = '{SOURCE_TIER}'", name="source_tier"),
        CheckConstraint(f"evidence_kind = '{EVIDENCE_KIND}'", name="evidence_kind"),
        CheckConstraint("independently_verified = FALSE", name="never_independent"),
        CheckConstraint(_not_blank("claimed_scopus_id"), name="claimed_scopus_id_not_empty"),
        CheckConstraint(_not_blank("captured_at"), name="captured_at_not_empty"),
        CheckConstraint(_hex("artifact_digest"), name="artifact_digest"),
        CheckConstraint(_hex("record_digest"), name="record_digest"),
        CheckConstraint(f"issuance_state IS NULL OR {_in('issuance_state', ISSUANCE_STATES)}",
                        name="issuance_state"),
        CheckConstraint(f"issuance_verification_digest IS NULL "
                        f"OR {_hex('issuance_verification_digest')}",
                        name="issuance_verification_digest"),
        # An issuance attestation is recorded whole or not at all.
        CheckConstraint(_both_or_neither("issuance_state", "issuance_verification_id",
                                        "issuance_verification_digest",
                                        "issuance_verification_method"),
                        name="issuance_attestation_complete"),
        Index("ix_sc_hybrid_provenance_claim", "claim_id"),
    )


class HybridDecisionEvent(Base):
    """Append-only hash-chained decision history, one stream per candidate.

    ``UNIQUE(previous_event_id)`` makes the chain a line, not a tree: a second event
    cannot be grafted onto an already-extended predecessor. ``UNIQUE(operation_key)``
    is the idempotency key, derived by the append boundary from the trusted snapshot —
    never supplied by a caller — so a retry cannot become a second decision and a
    tampered snapshot cannot reuse an existing key.
    """

    __tablename__ = "sc_hybrid_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_ID)
    stream_candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lecturer_scopus_candidates.id", ondelete="RESTRICT",
                                       name="fk_sc_hybrid_events_stream_candidate_id"),
        nullable=False)
    stream_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_hybrid_events.event_id", ondelete="RESTRICT"),
        nullable=True)
    previous_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Always ``stream_seq - 1`` when there is a predecessor; stored so a composite FK can pin
    # the predecessor's stream, position, id and hash to one event (migration d0b14a77c8e2).
    previous_stream_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_hybrid_contexts.id", ondelete="RESTRICT"),
        nullable=False)
    policy_digest: Mapped[str] = mapped_column(
        String(64), ForeignKey("sc_hybrid_policies.policy_digest", ondelete="RESTRICT"),
        nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    actor_service: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # The human behind the account, as resolved by the external principal registry.
    actor_principal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_auth_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    envelope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    envelope_json: Mapped[str] = mapped_column(Text, nullable=False)
    audit_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_events.id", ondelete="RESTRICT"), nullable=True)
    action_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        CheckConstraint(_in("event_kind", EVENT_KINDS), name="event_kind"),
        CheckConstraint("stream_seq >= 1", name="stream_seq"),
        # The chain head is the only event without a predecessor.
        CheckConstraint("(stream_seq = 1) = (previous_event_id IS NULL)",
                        name="chain_head_consistency"),
        CheckConstraint(_both_or_neither("previous_event_id", "previous_event_hash"),
                        name="previous_pair"),
        CheckConstraint(f"previous_event_hash IS NULL OR {_hex('previous_event_hash')}",
                        name="previous_event_hash"),
        CheckConstraint("previous_event_id IS NULL OR previous_event_id <> event_id",
                        name="no_self_predecessor"),
        CheckConstraint(
            "(previous_stream_seq IS NULL) = (previous_event_id IS NULL) "
            "AND (previous_stream_seq IS NULL OR previous_stream_seq = stream_seq - 1)",
            name="previous_stream_seq"),
        CheckConstraint(_hex("operation_key"), name="operation_key"),
        CheckConstraint(_hex("snapshot_hash"), name="snapshot_hash"),
        CheckConstraint(_hex("envelope_hash"), name="envelope_hash"),
        CheckConstraint(_json_sha("snapshot_json", "snapshot_hash"), name="snapshot_hash_matches"),
        CheckConstraint(_json_sha("envelope_json", "envelope_hash"), name="envelope_hash_matches"),
        # Every kind defined here (propose, approve, revoke, supersede) is a human
        # action, so SYSTEM is not an acceptable actor for any of them. The column and
        # its vocabulary mirror the frozen audit_events actor contract.
        CheckConstraint(_in("actor_type", ("USER",)), name="human_action_required"),
        CheckConstraint(
            "actor_user_id IS NOT NULL AND actor_service IS NULL "
            "AND actor_principal_id IS NOT NULL "
            "AND actor_auth_version IS NOT NULL AND actor_auth_version >= 1",
            name="actor_invariant"),
        UniqueConstraint("stream_candidate_id", "stream_seq", name="uq_sc_hybrid_events_stream"),
        UniqueConstraint("previous_event_id", name="uq_sc_hybrid_events_previous_event_id"),
        UniqueConstraint("operation_key", name="uq_sc_hybrid_events_operation_key"),
        UniqueConstraint("envelope_hash", name="uq_sc_hybrid_events_envelope_hash"),
        # F4/F5: predecessor id + hash + position are one event of this very stream, so a
        # graft onto another stream, a wrong hash or a skipped position is refused.
        UniqueConstraint("stream_candidate_id", "stream_seq", "event_id", "envelope_hash",
                         name="uq_sc_hybrid_events_chain_link"),
        ForeignKeyConstraint(
            ["stream_candidate_id", "previous_stream_seq", "previous_event_id",
             "previous_event_hash"],
            ["sc_hybrid_events.stream_candidate_id", "sc_hybrid_events.stream_seq",
             "sc_hybrid_events.event_id", "sc_hybrid_events.envelope_hash"],
            name="fk_sc_hybrid_events_chain_link", ondelete="RESTRICT"),
        # F6: the event's candidate stream and policy are its context's.
        ForeignKeyConstraint(
            ["context_id", "stream_candidate_id", "policy_digest"],
            ["sc_hybrid_contexts.id", "sc_hybrid_contexts.candidate_id",
             "sc_hybrid_contexts.policy_digest"],
            name="fk_sc_hybrid_events_context_candidate_policy", ondelete="RESTRICT"),
        Index("ix_sc_hybrid_events_context", "context_id"),
        Index("ix_sc_hybrid_events_recorded", "recorded_at"),
    )


class HybridReviewerProposal(Base):
    """A reviewer's non-final proposal on one context. Never an acceptance.

    ``UNIQUE(context_id)`` keeps one proposal per exact revalidated context, so a replay
    of the same prepared draft can only ever resolve to the row already recorded.
    """

    __tablename__ = "sc_hybrid_proposals"

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_hybrid_events.event_id", ondelete="RESTRICT"),
        primary_key=True)
    context_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    candidate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    branch: Mapped[str] = mapped_column(String(30), nullable=False)
    assurance_basis: Mapped[str] = mapped_column(String(30), nullable=False)
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewer_principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reviewer_auth_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_acknowledgment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        ForeignKeyConstraint(
            ["context_id", "candidate_id", "candidate_version", "policy_digest"],
            ["sc_hybrid_contexts.id", "sc_hybrid_contexts.candidate_id",
             "sc_hybrid_contexts.candidate_version", "sc_hybrid_contexts.policy_digest"],
            name="fk_sc_hybrid_proposals_context_pair_policy", ondelete="RESTRICT"),
        CheckConstraint(_in("branch", BRANCHES), name="branch"),
        CheckConstraint(_in("assurance_basis", ASSURANCE_BASES), name="assurance_basis"),
        # The exception branch is the only path with a different assurance basis, and it
        # is the only branch that may carry a risk acknowledgment.
        CheckConstraint(
            "(branch = 'STANDARD_INDEPENDENT' AND assurance_basis = 'INDEPENDENT_VERIFIED'"
            " AND risk_acknowledgment IS NULL)"
            " OR (branch = 'INSTITUTIONAL_EXCEPTION'"
            " AND assurance_basis = 'INSTITUTIONAL_EXCEPTION'"
            " AND risk_acknowledgment IS NOT NULL)",
            name="branch_assurance_consistency"),
        CheckConstraint("candidate_version >= 1", name="candidate_version"),
        CheckConstraint("reviewer_auth_version >= 1", name="reviewer_auth_version"),
        CheckConstraint(_not_blank("reason"), name="reason_not_empty"),
        UniqueConstraint("context_id", name="uq_sc_hybrid_proposals_context_id"),
        # Composite target: an approval must name this proposal's exact branch and reviewer.
        UniqueConstraint("proposal_id", "context_id", "branch", "reviewer_user_id",
                         "reviewer_principal_id", name="uq_sc_hybrid_proposals_binding"),
        Index("ix_sc_hybrid_proposals_candidate", "candidate_id", "created_at"),
    )


class HybridExceptionApproval(Base):
    """Second-human approval of an institutional-exception proposal. Still not final.

    Two distinct accounts *and* two distinct human principals are required by CHECK, so
    one person holding several accounts cannot satisfy dual control. ``UNIQUE(proposal_id)``
    admits exactly one approval per proposal regardless of retries or approver identity.
    """

    __tablename__ = "sc_hybrid_approvals"

    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_hybrid_events.event_id", ondelete="RESTRICT"),
        primary_key=True)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    context_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch: Mapped[str] = mapped_column(String(30), nullable=False)
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reviewer_principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    approver_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approver_principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    approver_auth_version: Mapped[int] = mapped_column(Integer, nullable=False)
    proposal_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        ForeignKeyConstraint(
            ["proposal_id", "context_id", "branch", "reviewer_user_id", "reviewer_principal_id"],
            ["sc_hybrid_proposals.proposal_id", "sc_hybrid_proposals.context_id",
             "sc_hybrid_proposals.branch", "sc_hybrid_proposals.reviewer_user_id",
             "sc_hybrid_proposals.reviewer_principal_id"],
            name="fk_sc_hybrid_approvals_proposal_binding", ondelete="RESTRICT"),
        CheckConstraint("branch = 'INSTITUTIONAL_EXCEPTION'", name="exception_branch_only"),
        CheckConstraint("reviewer_user_id <> approver_user_id", name="distinct_accounts"),
        CheckConstraint("reviewer_principal_id <> approver_principal_id",
                        name="distinct_human_principals"),
        CheckConstraint("approver_auth_version >= 1", name="approver_auth_version"),
        CheckConstraint(_hex("proposal_digest"), name="proposal_digest"),
        UniqueConstraint("proposal_id", name="uq_sc_hybrid_approvals_proposal_id"),
        Index("ix_sc_hybrid_approvals_approver", "approver_user_id", "created_at"),
    )


class HybridRevocation(Base):
    """Revocation or supersession of an earlier event; appended, never an update.

    ``UNIQUE(target_event_id)`` gives each target exactly one terminal compensation, and
    dual control applies here too: a revocation needs a second distinct human.
    """

    __tablename__ = "sc_hybrid_revocations"

    revocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_hybrid_events.event_id", ondelete="RESTRICT"),
        primary_key=True)
    target_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_hybrid_events.event_id", ondelete="RESTRICT"),
        nullable=False)
    revocation_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    replacement_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_hybrid_events.event_id", ondelete="RESTRICT"),
        nullable=True)
    initiator_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    initiator_principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    authorizer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    authorizer_principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        CheckConstraint(_in("revocation_kind", REVOCATION_KINDS), name="revocation_kind"),
        CheckConstraint("(revocation_kind = 'SUPERSEDE') = (replacement_event_id IS NOT NULL)",
                        name="replacement_requires_supersede"),
        CheckConstraint("target_event_id <> revocation_id", name="target_is_not_self"),
        CheckConstraint("replacement_event_id IS NULL "
                        "OR replacement_event_id NOT IN (target_event_id, revocation_id)",
                        name="replacement_is_distinct"),
        CheckConstraint("initiator_user_id <> authorizer_user_id", name="distinct_accounts"),
        CheckConstraint("initiator_principal_id <> authorizer_principal_id",
                        name="distinct_human_principals"),
        CheckConstraint(_not_blank("reason"), name="reason_not_empty"),
        UniqueConstraint("target_event_id", name="uq_sc_hybrid_revocations_target_event_id"),
        Index("ix_sc_hybrid_revocations_created", "created_at"),
    )


HYBRID_TABLES = ("sc_hybrid_policies", "sc_hybrid_contexts", "sc_hybrid_provenance",
                 "sc_hybrid_events", "sc_hybrid_proposals", "sc_hybrid_approvals",
                 "sc_hybrid_revocations")
