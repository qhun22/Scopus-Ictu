"""M2.7B-2 durable pre-identity candidate persistence.

This migration adds only the candidate-generation, observation, evidence, and
future-review history tables.  It does not alter identity tables or create any
identity rows.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b27c9d1e4f60"
down_revision: Union[str, None] = "f4c8b1a2e9d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
NOW = sa.text("now()")
GEN_RANDOM_UUID = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.create_table(
        "candidate_generation_runs",
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("rule_set_id", sa.Text(), nullable=False),
        sa.Column("rule_set_version", sa.Text(), nullable=False),
        sa.Column("source_state", JSONB, nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'RUNNING'"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint(
            "btrim(rule_set_id) <> ''",
            name=op.f("ck_candidate_generation_runs_rule_set_id_not_empty"),
        ),
        sa.CheckConstraint(
            "btrim(rule_set_version) <> ''",
            name=op.f("ck_candidate_generation_runs_rule_set_version_not_empty"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_state) = 'object'",
            name=op.f("ck_candidate_generation_runs_source_state_object"),
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name=op.f("ck_candidate_generation_runs_status"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_candidate_generation_runs_version"),
        ),
        sa.CheckConstraint(
            "(status = 'RUNNING' AND completed_at IS NULL) OR "
            "(status IN ('COMPLETED', 'FAILED') AND completed_at IS NOT NULL)",
            name=op.f("ck_candidate_generation_runs_completion_consistency"),
        ),
    )
    op.create_index(
        "ix_candidate_generation_runs_status_created",
        "candidate_generation_runs",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "lecturer_scopus_candidates",
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("lecturer_id", UUID, nullable=False),
        sa.Column("scopus_author_id", UUID, nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["lecturer_id"],
            ["lecturers.id"],
            name=op.f("fk_lecturer_scopus_candidates_lecturer_id_lecturers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["scopus_author_id"],
            ["scopus_authors.id"],
            name=op.f("fk_lecturer_scopus_candidates_scopus_author_id_scopus_authors"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'SUPERSEDED')",
            name=op.f("ck_lecturer_scopus_candidates_status"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_lecturer_scopus_candidates_version"),
        ),
        sa.UniqueConstraint(
            "lecturer_id",
            "scopus_author_id",
            name="uq_lecturer_scopus_candidates_pair",
        ),
    )
    op.create_index(
        "ix_lecturer_scopus_candidates_lecturer",
        "lecturer_scopus_candidates",
        ["lecturer_id"],
        unique=False,
    )
    op.create_index(
        "ix_lecturer_scopus_candidates_scopus_author",
        "lecturer_scopus_candidates",
        ["scopus_author_id"],
        unique=False,
    )
    op.create_index(
        "ix_lecturer_scopus_candidates_status_updated",
        "lecturer_scopus_candidates",
        ["status", "updated_at"],
        unique=False,
    )

    op.create_table(
        "lecturer_scopus_candidate_observations",
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("candidate_id", UUID, nullable=False),
        sa.Column("generation_run_id", UUID, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candidate_snapshot", JSONB, nullable=False),
        sa.Column("observation_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["lecturer_scopus_candidates.id"],
            name=op.f("fk_lecturer_scopus_candidate_observations_candidate_id_lecturer_scopus_candidates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["generation_run_id"],
            ["candidate_generation_runs.id"],
            name=op.f("fk_lecturer_scopus_candidate_observations_generation_run_id_candidate_generation_runs"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(candidate_snapshot) = 'object'",
            name=op.f("ck_lecturer_scopus_candidate_observations_candidate_snapshot_object"),
        ),
        sa.CheckConstraint(
            "observation_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_lecturer_scopus_candidate_observations_observation_hash"),
        ),
        sa.UniqueConstraint(
            "candidate_id",
            "generation_run_id",
            name="uq_candidate_observations_candidate_run",
        ),
    )
    op.create_index(
        "ix_candidate_observations_candidate",
        "lecturer_scopus_candidate_observations",
        ["candidate_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_observations_run",
        "lecturer_scopus_candidate_observations",
        ["generation_run_id"],
        unique=False,
    )

    op.create_table(
        "lecturer_scopus_candidate_evidence",
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("observation_id", UUID, nullable=False),
        sa.Column("evidence_kind", sa.String(length=30), nullable=False),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("rule_version", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("source_refs", JSONB, nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["lecturer_scopus_candidate_observations.id"],
            name=op.f("fk_lecturer_scopus_candidate_evidence_observation_id_lecturer_scopus_candidate_observations"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "evidence_kind IN ('NAME', 'PUBLICATION')",
            name=op.f("ck_lecturer_scopus_candidate_evidence_evidence_kind"),
        ),
        sa.CheckConstraint(
            "btrim(rule_id) <> ''",
            name=op.f("ck_lecturer_scopus_candidate_evidence_rule_id_not_empty"),
        ),
        sa.CheckConstraint(
            "btrim(rule_version) <> ''",
            name=op.f("ck_lecturer_scopus_candidate_evidence_rule_version_not_empty"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name=op.f("ck_lecturer_scopus_candidate_evidence_payload_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'",
            name=op.f("ck_lecturer_scopus_candidate_evidence_source_refs_array"),
        ),
        sa.CheckConstraint(
            "evidence_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_lecturer_scopus_candidate_evidence_evidence_fingerprint"),
        ),
        sa.UniqueConstraint(
            "observation_id",
            "rule_id",
            "rule_version",
            "evidence_fingerprint",
            name="uq_candidate_evidence_descriptor",
        ),
    )
    op.create_index(
        "ix_candidate_evidence_observation",
        "lecturer_scopus_candidate_evidence",
        ["observation_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "lecturer_scopus_candidate_reviews",
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("candidate_id", UUID, nullable=False),
        sa.Column("observation_id", UUID, nullable=False),
        sa.Column("reviewer_user_id", UUID, nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=False),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("candidate_version", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_snapshot", JSONB, nullable=False),
        sa.Column("resulting_identity_id", UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["lecturer_scopus_candidates.id"],
            name=op.f("fk_lecturer_scopus_candidate_reviews_candidate_id_lecturer_scopus_candidates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["lecturer_scopus_candidate_observations.id"],
            name=op.f("fk_lecturer_scopus_candidate_reviews_observation_id_lecturer_scopus_candidate_observations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"],
            ["users.id"],
            name=op.f("fk_lecturer_scopus_candidate_reviews_reviewer_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resulting_identity_id"],
            ["lecturer_scopus_identities.id"],
            name=op.f("fk_lecturer_scopus_candidate_reviews_resulting_identity_id_lecturer_scopus_identities"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "action IN ('ACCEPT', 'REJECT', 'REOPEN')",
            name=op.f("ck_lecturer_scopus_candidate_reviews_action"),
        ),
        sa.CheckConstraint(
            "from_status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'SUPERSEDED')",
            name=op.f("ck_lecturer_scopus_candidate_reviews_from_status"),
        ),
        sa.CheckConstraint(
            "to_status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'SUPERSEDED')",
            name=op.f("ck_lecturer_scopus_candidate_reviews_to_status"),
        ),
        sa.CheckConstraint(
            "candidate_version >= 1",
            name=op.f("ck_lecturer_scopus_candidate_reviews_candidate_version"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_snapshot) = 'object'",
            name=op.f("ck_lecturer_scopus_candidate_reviews_evidence_snapshot_object"),
        ),
        sa.CheckConstraint(
            "action = 'ACCEPT' OR (reason IS NOT NULL AND btrim(reason) <> '')",
            name=op.f("ck_lecturer_scopus_candidate_reviews_reason_required"),
        ),
        sa.CheckConstraint(
            "(action = 'ACCEPT' AND from_status = 'PENDING' AND to_status = 'ACCEPTED') "
            "OR (action = 'REJECT' AND from_status = 'PENDING' AND to_status = 'REJECTED') "
            "OR (action = 'REOPEN' AND from_status IN "
            "('ACCEPTED', 'REJECTED', 'SUPERSEDED') AND to_status = 'PENDING')",
            name=op.f("ck_lecturer_scopus_candidate_reviews_transitions"),
        ),
    )
    op.create_index(
        "ix_candidate_reviews_candidate_created",
        "lecturer_scopus_candidate_reviews",
        ["candidate_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_reviews_observation",
        "lecturer_scopus_candidate_reviews",
        ["observation_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_reviews_reviewer",
        "lecturer_scopus_candidate_reviews",
        ["reviewer_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_reviews_reviewer", table_name="lecturer_scopus_candidate_reviews")
    op.drop_index("ix_candidate_reviews_observation", table_name="lecturer_scopus_candidate_reviews")
    op.drop_index("ix_candidate_reviews_candidate_created", table_name="lecturer_scopus_candidate_reviews")
    op.drop_table("lecturer_scopus_candidate_reviews")

    op.drop_index("ix_candidate_evidence_observation", table_name="lecturer_scopus_candidate_evidence")
    op.drop_table("lecturer_scopus_candidate_evidence")

    op.drop_index("ix_candidate_observations_run", table_name="lecturer_scopus_candidate_observations")
    op.drop_index("ix_candidate_observations_candidate", table_name="lecturer_scopus_candidate_observations")
    op.drop_table("lecturer_scopus_candidate_observations")

    op.drop_index("ix_lecturer_scopus_candidates_status_updated", table_name="lecturer_scopus_candidates")
    op.drop_index("ix_lecturer_scopus_candidates_scopus_author", table_name="lecturer_scopus_candidates")
    op.drop_index("ix_lecturer_scopus_candidates_lecturer", table_name="lecturer_scopus_candidates")
    op.drop_table("lecturer_scopus_candidates")

    op.drop_index("ix_candidate_generation_runs_status_created", table_name="candidate_generation_runs")
    op.drop_table("candidate_generation_runs")
