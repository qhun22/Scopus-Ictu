"""Add publication_author_affiliation_overrides for Priority 2 manual review.

Revision ID: b5e8d2f1a4c7
Revises: a3b7c9d1e2f4
Create Date: 2026-10-12

Additive table only. An ADMIN-entered affiliation statement, layered on top
of the automated resolutions in publication_author_affiliation_resolutions /
publication_author_affiliations — neither existing table is altered, and
Scopus raw data / prior automated evidence is never modified.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b5e8d2f1a4c7"
down_revision = "a3b7c9d1e2f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publication_author_affiliation_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("publication_author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("affiliation_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("evidence_url", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("confidence IN ('CORROBORATED', 'UNRESOLVED')", name=op.f("ck_publication_author_affiliation_overrides_confidence")),
        sa.CheckConstraint("btrim(affiliation_text) <> ''", name=op.f("ck_publication_author_affiliation_overrides_affiliation_text_not_blank")),
        sa.CheckConstraint("btrim(evidence_url) <> ''", name=op.f("ck_publication_author_affiliation_overrides_evidence_url_not_blank")),
        sa.CheckConstraint("btrim(reason) <> ''", name=op.f("ck_publication_author_affiliation_overrides_reason_not_blank")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_publication_author_affiliation_overrides_version")),
        sa.ForeignKeyConstraint(
            ["publication_author_id"], ["publication_authors.id"],
            ondelete="CASCADE", name=op.f("fk_paao_publication_author_id"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            ondelete="RESTRICT", name=op.f("fk_paao_created_by"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"],
            ondelete="RESTRICT", name=op.f("fk_paao_updated_by"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_publication_author_affiliation_overrides")),
        sa.UniqueConstraint("publication_author_id", name=op.f("uq_paao_publication_author_id")),
    )
    op.create_index(
        "ix_paao_updated_at", "publication_author_affiliation_overrides", ["updated_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_paao_updated_at", table_name="publication_author_affiliation_overrides")
    op.drop_table("publication_author_affiliation_overrides")
