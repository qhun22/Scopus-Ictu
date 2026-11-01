"""E3-P3-B2-D hybrid SOURCE_CLAIM authority/decision history.

Adds seven append-only relations: policy revisions, revalidated decision contexts,
institutional provenance, a hash-chained decision event log, reviewer proposals,
dual-control exception approvals and revocation/supersession.

No existing table, constraint or index is altered, and no frozen contract changes. There
is deliberately **no finalization relation**: nothing here can accept a candidate, create
an identity, write IdentityEvidence or record a review, so installing this schema does
not activate the SOURCE_CLAIM workflow.

Source only. Revision ID: c99a03e55ff3, revises b88f02d44ff2. Execution requires a
separately authorized migration deployment; this gate applied it to no database.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c99a03e55ff3"
down_revision: str | None = "b88f02d44ff2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.text("now()")
GEN_RANDOM_UUID = sa.text("gen_random_uuid()")
HEX64 = "~ '^[0-9a-f]{64}$'"

POLICIES = "sc_hybrid_policies"
CONTEXTS = "sc_hybrid_contexts"
PROVENANCE = "sc_hybrid_provenance"
EVENTS = "sc_hybrid_events"
PROPOSALS = "sc_hybrid_proposals"
APPROVALS = "sc_hybrid_approvals"
REVOCATIONS = "sc_hybrid_revocations"
TABLES = (POLICIES, CONTEXTS, PROVENANCE, EVENTS, PROPOSALS, APPROVALS, REVOCATIONS)


def _ck(table: str, name: str, sql: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def _fk(table: str, column: str, target: str, *, name: str | None = None
        ) -> sa.ForeignKeyConstraint:
    referred = target.split(".")[0]
    return sa.ForeignKeyConstraint(
        [column], [target], ondelete="RESTRICT",
        name=op.f(name or f"fk_{table}_{column}_{referred}"))


def _created(name: str = "created_at") -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=NOW)


def _sha(json_column: str, hash_column: str) -> str:
    return f"{hash_column} = encode(sha256(convert_to({json_column}, 'UTF8')), 'hex')"


def upgrade() -> None:
    t = POLICIES
    op.create_table(
        t,
        sa.Column("policy_digest", sa.String(length=64), primary_key=True),
        sa.Column("policy_family", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=64), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("encoder_version", sa.String(length=32), nullable=False),
        sa.Column("policy_json", sa.Text(), nullable=False),
        _created(),
        _ck(t, "policy_digest", f"policy_digest {HEX64}"),
        _ck(t, "policy_digest_matches", _sha("policy_json", "policy_digest")),
        _ck(t, "policy_family_not_empty", "btrim(policy_family) <> ''"),
        _ck(t, "policy_id_not_empty", "btrim(policy_id) <> ''"),
        _ck(t, "encoder_version_not_empty", "btrim(encoder_version) <> ''"),
        _ck(t, "policy_revision", "policy_revision >= 1"),
        sa.UniqueConstraint("policy_family", "policy_revision",
                            name="uq_sc_hybrid_policies_family_revision"),
    )

    t = CONTEXTS
    op.create_table(
        t,
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("context_digest", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("candidate_id", UUID, nullable=False),
        sa.Column("candidate_version", sa.Integer(), nullable=False),
        sa.Column("lecturer_id", UUID, nullable=False),
        sa.Column("scopus_author_id", UUID, nullable=False),
        sa.Column("observation_id", UUID, nullable=False),
        sa.Column("generation_run_id", UUID, nullable=False),
        sa.Column("reviewer_user_id", UUID, nullable=False),
        sa.Column("reviewer_auth_version", sa.Integer(), nullable=False),
        sa.Column("source_context_hash", sa.String(length=64), nullable=False),
        sa.Column("trusted_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("authority_revision_digest", sa.String(length=64), nullable=False),
        _created(),
        _ck(t, "context_digest", f"context_digest {HEX64}"),
        _ck(t, "source_context_hash", f"source_context_hash {HEX64}"),
        _ck(t, "trusted_evidence_hash", f"trusted_evidence_hash {HEX64}"),
        _ck(t, "authority_revision_digest", f"authority_revision_digest {HEX64}"),
        _ck(t, "candidate_version", "candidate_version >= 1"),
        _ck(t, "reviewer_auth_version", "reviewer_auth_version >= 1"),
        sa.UniqueConstraint("context_digest", name="uq_sc_hybrid_contexts_context_digest"),
        # Composite target for the proposal child FK: pair, version and policy together.
        sa.UniqueConstraint("id", "candidate_id", "candidate_version", "policy_digest",
                            name="uq_sc_hybrid_contexts_pair_policy"),
        _fk(t, "policy_digest", "sc_hybrid_policies.policy_digest"),
        _fk(t, "candidate_id", "lecturer_scopus_candidates.id"),
        _fk(t, "lecturer_id", "lecturers.id"),
        _fk(t, "scopus_author_id", "scopus_authors.id"),
        _fk(t, "observation_id", "lecturer_scopus_candidate_observations.id",
            name="fk_sc_hybrid_contexts_observation_id"),
        _fk(t, "generation_run_id", "candidate_generation_runs.id",
            name="fk_sc_hybrid_contexts_generation_run_id"),
        _fk(t, "reviewer_user_id", "users.id"),
    )
    op.create_index("ix_sc_hybrid_contexts_candidate", t, ["candidate_id", "created_at"])

    t = PROVENANCE
    op.create_table(
        t,
        sa.Column("context_id", UUID, primary_key=True),
        sa.Column("artifact_id", UUID, primary_key=True),
        sa.Column("analysis_id", UUID, primary_key=True),
        sa.Column("record_id", UUID, primary_key=True),
        sa.Column("claim_id", UUID, primary_key=True),
        sa.Column("capture_id", UUID, nullable=False),
        sa.Column("source_system", sa.String(length=50), nullable=False),
        sa.Column("source_tier", sa.String(length=30), nullable=False),
        sa.Column("evidence_kind", sa.String(length=20), nullable=False),
        sa.Column("independently_verified", sa.Boolean(), nullable=False,
                  server_default=sa.text("FALSE")),
        sa.Column("claimed_scopus_id", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.String(length=40), nullable=False),
        sa.Column("artifact_digest", sa.String(length=64), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column("issuance_state", sa.String(length=20), nullable=True),
        sa.Column("issuance_verification_id", UUID, nullable=True),
        sa.Column("issuance_verification_digest", sa.String(length=64), nullable=True),
        sa.Column("issuance_verification_method", sa.String(length=64), nullable=True),
        _created(),
        _ck(t, "source_system",
            "source_system IN ('ICTU_REPO_SCOPUS_GUIDE', 'ICTU_REPO_PROFILES')"),
        _ck(t, "source_tier", "source_tier = 'INSTITUTION_DECLARED'"),
        _ck(t, "evidence_kind", "evidence_kind = 'SOURCE_CLAIM'"),
        # The database itself refuses an institutional declaration that claims to be
        # independently verified evidence.
        _ck(t, "never_independent", "independently_verified = FALSE"),
        _ck(t, "claimed_scopus_id_not_empty", "btrim(claimed_scopus_id) <> ''"),
        _ck(t, "captured_at_not_empty", "btrim(captured_at) <> ''"),
        _ck(t, "artifact_digest", f"artifact_digest {HEX64}"),
        _ck(t, "record_digest", f"record_digest {HEX64}"),
        _ck(t, "issuance_state",
            "issuance_state IS NULL OR issuance_state IN ('CURRENT', 'UNVERIFIED')"),
        _ck(t, "issuance_verification_digest",
            f"issuance_verification_digest IS NULL OR issuance_verification_digest {HEX64}"),
        _ck(t, "issuance_attestation_complete",
            "(issuance_state IS NULL) = (issuance_verification_id IS NULL) "
            "AND (issuance_state IS NULL) = (issuance_verification_digest IS NULL) "
            "AND (issuance_state IS NULL) = (issuance_verification_method IS NULL)"),
        # Deliberately no FK into the staging tables: the accepted E3-P2-B1 contract
        # keeps staging pre-identity with nothing downstream pointing into it. Lineage is
        # revalidated by the append boundary and pinned by the digests above.
        _fk(t, "context_id", "sc_hybrid_contexts.id"),
    )
    op.create_index("ix_sc_hybrid_provenance_claim", t, ["claim_id"])

    t = EVENTS
    op.create_table(
        t,
        sa.Column("event_id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("stream_candidate_id", UUID, nullable=False),
        sa.Column("stream_seq", sa.Integer(), nullable=False),
        sa.Column("previous_event_id", UUID, nullable=True),
        sa.Column("previous_event_hash", sa.String(length=64), nullable=True),
        sa.Column("event_kind", sa.String(length=30), nullable=False),
        sa.Column("context_id", UUID, nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", UUID, nullable=True),
        sa.Column("actor_service", sa.String(length=100), nullable=True),
        sa.Column("actor_principal_id", UUID, nullable=True),
        sa.Column("actor_auth_version", sa.Integer(), nullable=True),
        sa.Column("operation_key", sa.String(length=64), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("envelope_hash", sa.String(length=64), nullable=False),
        sa.Column("envelope_json", sa.Text(), nullable=False),
        sa.Column("audit_event_id", UUID, nullable=True),
        sa.Column("action_at", sa.DateTime(timezone=True), nullable=False),
        _created("recorded_at"),
        _ck(t, "event_kind",
            "event_kind IN ('PROPOSE', 'APPROVE_EXCEPTION', 'REVOKE', 'SUPERSEDE')"),
        _ck(t, "stream_seq", "stream_seq >= 1"),
        _ck(t, "chain_head_consistency", "(stream_seq = 1) = (previous_event_id IS NULL)"),
        _ck(t, "previous_pair", "(previous_event_id IS NULL) = (previous_event_hash IS NULL)"),
        _ck(t, "previous_event_hash",
            f"previous_event_hash IS NULL OR previous_event_hash {HEX64}"),
        _ck(t, "no_self_predecessor",
            "previous_event_id IS NULL OR previous_event_id <> event_id"),
        _ck(t, "operation_key", f"operation_key {HEX64}"),
        _ck(t, "snapshot_hash", f"snapshot_hash {HEX64}"),
        _ck(t, "envelope_hash", f"envelope_hash {HEX64}"),
        _ck(t, "snapshot_hash_matches", _sha("snapshot_json", "snapshot_hash")),
        _ck(t, "envelope_hash_matches", _sha("envelope_json", "envelope_hash")),
        # Proposing, approving, revoking and superseding are human actions only.
        _ck(t, "human_action_required", "actor_type IN ('USER')"),
        _ck(t, "actor_invariant",
            "actor_user_id IS NOT NULL AND actor_service IS NULL "
            "AND actor_principal_id IS NOT NULL "
            "AND actor_auth_version IS NOT NULL AND actor_auth_version >= 1"),
        sa.UniqueConstraint("stream_candidate_id", "stream_seq",
                            name="uq_sc_hybrid_events_stream"),
        # The chain is a line, not a tree: a predecessor has at most one successor.
        sa.UniqueConstraint("previous_event_id",
                            name="uq_sc_hybrid_events_previous_event_id"),
        # Idempotency key, derived by the append boundary from the trusted snapshot.
        sa.UniqueConstraint("operation_key", name="uq_sc_hybrid_events_operation_key"),
        sa.UniqueConstraint("envelope_hash", name="uq_sc_hybrid_events_envelope_hash"),
        _fk(t, "stream_candidate_id", "lecturer_scopus_candidates.id",
            name="fk_sc_hybrid_events_stream_candidate_id"),
        _fk(t, "previous_event_id", "sc_hybrid_events.event_id"),
        _fk(t, "context_id", "sc_hybrid_contexts.id"),
        _fk(t, "policy_digest", "sc_hybrid_policies.policy_digest"),
        _fk(t, "actor_user_id", "users.id"),
        _fk(t, "audit_event_id", "audit_events.id"),
    )
    op.create_index("ix_sc_hybrid_events_context", t, ["context_id"])
    op.create_index("ix_sc_hybrid_events_recorded", t, ["recorded_at"])

    t = PROPOSALS
    op.create_table(
        t,
        sa.Column("proposal_id", UUID, primary_key=True),
        sa.Column("context_id", UUID, nullable=False),
        sa.Column("candidate_id", UUID, nullable=False),
        sa.Column("candidate_version", sa.Integer(), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("branch", sa.String(length=30), nullable=False),
        sa.Column("assurance_basis", sa.String(length=30), nullable=False),
        sa.Column("reviewer_user_id", UUID, nullable=False),
        sa.Column("reviewer_principal_id", UUID, nullable=False),
        sa.Column("reviewer_auth_version", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("risk_acknowledgment", sa.Text(), nullable=True),
        _created(),
        sa.ForeignKeyConstraint(
            ["context_id", "candidate_id", "candidate_version", "policy_digest"],
            ["sc_hybrid_contexts.id", "sc_hybrid_contexts.candidate_id",
             "sc_hybrid_contexts.candidate_version", "sc_hybrid_contexts.policy_digest"],
            name=op.f("fk_sc_hybrid_proposals_context_pair_policy"), ondelete="RESTRICT"),
        _ck(t, "branch", "branch IN ('STANDARD_INDEPENDENT', 'INSTITUTIONAL_EXCEPTION')"),
        _ck(t, "assurance_basis",
            "assurance_basis IN ('INDEPENDENT_VERIFIED', 'INSTITUTIONAL_EXCEPTION')"),
        _ck(t, "branch_assurance_consistency",
            "(branch = 'STANDARD_INDEPENDENT' AND assurance_basis = 'INDEPENDENT_VERIFIED'"
            " AND risk_acknowledgment IS NULL)"
            " OR (branch = 'INSTITUTIONAL_EXCEPTION'"
            " AND assurance_basis = 'INSTITUTIONAL_EXCEPTION'"
            " AND risk_acknowledgment IS NOT NULL)"),
        _ck(t, "candidate_version", "candidate_version >= 1"),
        _ck(t, "reviewer_auth_version", "reviewer_auth_version >= 1"),
        _ck(t, "reason_not_empty", "btrim(reason) <> ''"),
        # One proposal per exact revalidated context, so a replay cannot become a second.
        sa.UniqueConstraint("context_id", name="uq_sc_hybrid_proposals_context_id"),
        sa.UniqueConstraint("proposal_id", "context_id", "branch", "reviewer_user_id",
                            "reviewer_principal_id", name="uq_sc_hybrid_proposals_binding"),
        _fk(t, "proposal_id", "sc_hybrid_events.event_id"),
        _fk(t, "reviewer_user_id", "users.id"),
    )
    op.create_index("ix_sc_hybrid_proposals_candidate", t, ["candidate_id", "created_at"])

    t = APPROVALS
    op.create_table(
        t,
        sa.Column("approval_id", UUID, primary_key=True),
        sa.Column("proposal_id", UUID, nullable=False),
        sa.Column("context_id", UUID, nullable=False),
        sa.Column("branch", sa.String(length=30), nullable=False),
        sa.Column("reviewer_user_id", UUID, nullable=False),
        sa.Column("reviewer_principal_id", UUID, nullable=False),
        sa.Column("approver_user_id", UUID, nullable=False),
        sa.Column("approver_principal_id", UUID, nullable=False),
        sa.Column("approver_auth_version", sa.Integer(), nullable=False),
        sa.Column("proposal_digest", sa.String(length=64), nullable=False),
        _created(),
        # Bound to that proposal's exact branch and reviewer, so an approval prepared for
        # one candidate cannot be reused for another.
        sa.ForeignKeyConstraint(
            ["proposal_id", "context_id", "branch", "reviewer_user_id",
             "reviewer_principal_id"],
            ["sc_hybrid_proposals.proposal_id", "sc_hybrid_proposals.context_id",
             "sc_hybrid_proposals.branch", "sc_hybrid_proposals.reviewer_user_id",
             "sc_hybrid_proposals.reviewer_principal_id"],
            name=op.f("fk_sc_hybrid_approvals_proposal_binding"), ondelete="RESTRICT"),
        _ck(t, "exception_branch_only", "branch = 'INSTITUTIONAL_EXCEPTION'"),
        _ck(t, "distinct_accounts", "reviewer_user_id <> approver_user_id"),
        # Two accounts of one person are one human, so dual control needs two principals.
        _ck(t, "distinct_human_principals",
            "reviewer_principal_id <> approver_principal_id"),
        _ck(t, "approver_auth_version", "approver_auth_version >= 1"),
        _ck(t, "proposal_digest", f"proposal_digest {HEX64}"),
        sa.UniqueConstraint("proposal_id", name="uq_sc_hybrid_approvals_proposal_id"),
        _fk(t, "approval_id", "sc_hybrid_events.event_id"),
        _fk(t, "approver_user_id", "users.id"),
    )
    op.create_index("ix_sc_hybrid_approvals_approver", t, ["approver_user_id", "created_at"])

    t = REVOCATIONS
    op.create_table(
        t,
        sa.Column("revocation_id", UUID, primary_key=True),
        sa.Column("target_event_id", UUID, nullable=False),
        sa.Column("revocation_kind", sa.String(length=20), nullable=False),
        sa.Column("replacement_event_id", UUID, nullable=True),
        sa.Column("initiator_user_id", UUID, nullable=False),
        sa.Column("initiator_principal_id", UUID, nullable=False),
        sa.Column("authorizer_user_id", UUID, nullable=False),
        sa.Column("authorizer_principal_id", UUID, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        _created(),
        _ck(t, "revocation_kind", "revocation_kind IN ('REVOKE', 'SUPERSEDE')"),
        _ck(t, "replacement_requires_supersede",
            "(revocation_kind = 'SUPERSEDE') = (replacement_event_id IS NOT NULL)"),
        _ck(t, "target_is_not_self", "target_event_id <> revocation_id"),
        _ck(t, "replacement_is_distinct",
            "replacement_event_id IS NULL "
            "OR replacement_event_id NOT IN (target_event_id, revocation_id)"),
        _ck(t, "distinct_accounts", "initiator_user_id <> authorizer_user_id"),
        _ck(t, "distinct_human_principals",
            "initiator_principal_id <> authorizer_principal_id"),
        _ck(t, "reason_not_empty", "btrim(reason) <> ''"),
        # Each target gets exactly one terminal compensation.
        sa.UniqueConstraint("target_event_id", name="uq_sc_hybrid_revocations_target_event_id"),
        _fk(t, "revocation_id", "sc_hybrid_events.event_id"),
        _fk(t, "target_event_id", "sc_hybrid_events.event_id"),
        _fk(t, "replacement_event_id", "sc_hybrid_events.event_id"),
        _fk(t, "initiator_user_id", "users.id"),
        _fk(t, "authorizer_user_id", "users.id"),
    )
    op.create_index("ix_sc_hybrid_revocations_created", t, ["created_at"])


def downgrade() -> None:
    # Dropping the history would destroy append-only decision provenance, so this is a
    # structural rollback only: it fails closed if any row exists.
    for table in reversed(TABLES):
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {table}) THEN "
            f"RAISE EXCEPTION 'refusing to drop {table}: recorded history is append-only'; "
            "END IF; END $$;")
    for table in reversed(TABLES):
        op.drop_table(table)
