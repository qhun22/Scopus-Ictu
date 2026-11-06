"""User-submitted issue reports (feedback intake queue).

Additive. One new table; no existing table is altered. A report never writes
to publication_author_affiliation* or any identity/candidate table on its
own -- it is read by an ADMIN/REVIEWER, who makes any actual correction
through the existing affiliation-override or candidate-review workflow.

Revision ID: b7d3f91a6c84, revises f2b8c3d19a47. Not applied to any database
by this change.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7d3f91a6c84"
down_revision: str | None = "f2b8c3d19a47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "feedback_reports"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("reporter_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("publication_eid", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'OPEN'")),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("category IN ('WRONG_AFFILIATION', 'WRONG_AUTHOR_LINK', 'OTHER')",
                           name=op.f(f"ck_{T}_category")),
        sa.CheckConstraint("status IN ('OPEN', 'RESOLVED', 'DISMISSED')",
                           name=op.f(f"ck_{T}_status")),
        sa.CheckConstraint(
            "(status = 'OPEN' AND resolved_at IS NULL AND resolved_by_user_id IS NULL) OR "
            "(status != 'OPEN' AND resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)",
            name=op.f(f"ck_{T}_resolved_state_consistent"),
        ),
        sa.CheckConstraint("btrim(message) <> ''", name=op.f(f"ck_{T}_message_not_blank")),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="RESTRICT",
                                name=op.f(f"fk_{T}_reporter_user_id")),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="RESTRICT",
                                name=op.f(f"fk_{T}_resolved_by_user_id")),
    )
    op.create_index(op.f(f"ix_{T}_status_created_at"), T, ["status", "created_at"])


def downgrade() -> None:
    op.drop_index(op.f(f"ix_{T}_status_created_at"), table_name=T)
    op.drop_table(T)
