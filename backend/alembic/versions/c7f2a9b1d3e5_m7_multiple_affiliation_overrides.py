"""Allow a publication author position to have multiple active affiliation overrides.

Revision ID: c7f2a9b1d3e5
Revises: b5e8d2f1a4c7
Create Date: 2026-10-13

A real author can hold a dual appointment, so one ADMIN-entered unit
statement per position is too restrictive. This drops the old
one-row-per-position unique constraint, adds status/revoked_* columns so a
unit can be revoked (kept, not deleted, for audit) instead of only
replaced or hard-deleted, and adds a partial unique index that blocks two
ACTIVE rows with the same (position, unit text) while still allowing a
revoked statement to be re-added. Fully additive: no existing table other
than publication_author_affiliation_overrides itself is touched, and no
row is deleted.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c7f2a9b1d3e5"
down_revision = "b5e8d2f1a4c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_paao_publication_author_id", "publication_author_affiliation_overrides", type_="unique")

    op.add_column(
        "publication_author_affiliation_overrides",
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'ACTIVE'")),
    )
    op.add_column(
        "publication_author_affiliation_overrides",
        sa.Column("revoked_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "publication_author_affiliation_overrides",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_paao_revoked_by"),
        "publication_author_affiliation_overrides",
        "users",
        ["revoked_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_publication_author_affiliation_overrides_status"),
        "publication_author_affiliation_overrides",
        "status IN ('ACTIVE', 'REVOKED')",
    )
    op.create_check_constraint(
        op.f("ck_publication_author_affiliation_overrides_revoked_state_consistent"),
        "publication_author_affiliation_overrides",
        "(status = 'ACTIVE' AND revoked_at IS NULL AND revoked_by_user_id IS NULL) OR "
        "(status = 'REVOKED' AND revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL)",
    )

    op.create_index(
        "ix_paao_publication_author_id", "publication_author_affiliation_overrides", ["publication_author_id"]
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_paao_active_position_text "
        "ON publication_author_affiliation_overrides (publication_author_id, affiliation_text) "
        "WHERE status = 'ACTIVE'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_paao_active_position_text")
    op.drop_index("ix_paao_publication_author_id", table_name="publication_author_affiliation_overrides")
    op.drop_constraint(
        op.f("ck_publication_author_affiliation_overrides_revoked_state_consistent"),
        "publication_author_affiliation_overrides",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_publication_author_affiliation_overrides_status"),
        "publication_author_affiliation_overrides",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_paao_revoked_by"), "publication_author_affiliation_overrides", type_="foreignkey"
    )
    op.drop_column("publication_author_affiliation_overrides", "revoked_at")
    op.drop_column("publication_author_affiliation_overrides", "revoked_by_user_id")
    op.drop_column("publication_author_affiliation_overrides", "status")

    # NOTE: downgrade cannot safely restore uq_paao_publication_author_id if
    # multiple ACTIVE overrides were created for one position under the new
    # schema — that data loss is intentional and must be handled manually.
    op.create_unique_constraint(
        "uq_paao_publication_author_id", "publication_author_affiliation_overrides", ["publication_author_id"]
    )
