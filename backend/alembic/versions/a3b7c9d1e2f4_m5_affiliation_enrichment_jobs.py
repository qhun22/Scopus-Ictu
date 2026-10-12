"""Add affiliation_enrichment_jobs for Priority 1 online affiliation collection.

Revision ID: a3b7c9d1e2f4
Revises: f6a1b2c3d4e5
Create Date: 2026-10-12

Additive table only. ADMIN triggers an online enrichment run (OpenAlex /
Crossref / ORCID) that writes a per-job bundle on disk; this table tracks its
progress and lets the preview/apply workflow find the resulting bundle
directory. No existing table is altered.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a3b7c9d1e2f4"
down_revision = "f6a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affiliation_enrichment_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'RECEIVED'"), nullable=False),
        sa.Column("total_dois", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("processed_dois", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("openalex_found", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("crossref_found", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("orcid_fetched", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("bundle_dir", sa.Text(), nullable=True),
        sa.Column("error_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_affiliation_enrichment_jobs_version")),
        sa.CheckConstraint(
            "total_dois >= 0 AND processed_dois >= 0 AND processed_dois <= total_dois",
            name=op.f("ck_affiliation_enrichment_jobs_progress_counts"),
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name=op.f("ck_affiliation_enrichment_jobs_status"),
        ),
        sa.CheckConstraint(
            "error_summary IS NULL OR jsonb_typeof(error_summary) = 'object'",
            name=op.f("ck_affiliation_enrichment_jobs_error_summary_object"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_affiliation_enrichment_jobs")),
    )
    op.create_index(
        "ix_affiliation_enrichment_jobs_status", "affiliation_enrichment_jobs", ["status"]
    )
    op.create_index(
        "ix_affiliation_enrichment_jobs_requested_by",
        "affiliation_enrichment_jobs",
        ["requested_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_affiliation_enrichment_jobs_requested_by", table_name="affiliation_enrichment_jobs")
    op.drop_index("ix_affiliation_enrichment_jobs_status", table_name="affiliation_enrichment_jobs")
    op.drop_table("affiliation_enrichment_jobs")
