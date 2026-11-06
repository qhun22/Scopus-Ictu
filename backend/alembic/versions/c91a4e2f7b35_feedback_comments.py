"""Feedback report comment thread (two-way reply between reporter and staff).

Additive. One new table; no existing table is altered. A comment never
writes to publication_author_affiliation* or any identity/candidate table --
it is purely the back-and-forth conversation on a feedback_reports row
("what exactly did you mean"), written by either the original reporter or an
ADMIN/REVIEWER.

Revision ID: c91a4e2f7b35, revises b7d3f91a6c84. Not applied to any database
by this change.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c91a4e2f7b35"
down_revision: str | None = "b7d3f91a6c84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "feedback_comments"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("btrim(message) <> ''", name=op.f(f"ck_{T}_message_not_blank")),
        sa.ForeignKeyConstraint(["report_id"], ["feedback_reports.id"], ondelete="CASCADE",
                                name=op.f(f"fk_{T}_report_id")),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="RESTRICT",
                                name=op.f(f"fk_{T}_author_user_id")),
    )
    op.create_index(op.f(f"ix_{T}_report_created_at"), T, ["report_id", "created_at"])


def downgrade() -> None:
    op.drop_index(op.f(f"ix_{T}_report_created_at"), table_name=T)
    op.drop_table(T)
