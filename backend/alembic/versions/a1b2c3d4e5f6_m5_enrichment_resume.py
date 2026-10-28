"""Add doi_list and resumed_from_job_id to affiliation_enrichment_jobs for resume support.

Revision ID: a1b2c3d4e5f6
Revises: f6a1b2c3d4e5
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "a1b2c3d4e5f6"
down_revision = "c7f2a9b1d3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "affiliation_enrichment_jobs",
        sa.Column("doi_list", JSONB(none_as_null=True), nullable=True),
    )
    op.add_column(
        "affiliation_enrichment_jobs",
        sa.Column("resumed_from_job_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "doi_list_array",
        "affiliation_enrichment_jobs",
        "doi_list IS NULL OR jsonb_typeof(doi_list) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint("doi_list_array", "affiliation_enrichment_jobs", type_="check")
    op.drop_column("affiliation_enrichment_jobs", "resumed_from_job_id")
    op.drop_column("affiliation_enrichment_jobs", "doi_list")
