"""Per-user "last seen" marker for the feedback intake queue.

Additive. One new table; no existing table is altered. Used only to decide
whether to show an unread indicator on the "Bao loi" nav item -- it is not a
record of what a user actually read.

Revision ID: d4e7c3a98f12, revises c91a4e2f7b35. Not applied to any database
by this change.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4e7c3a98f12"
down_revision: str | None = "c91a4e2f7b35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "feedback_read_states"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE",
                                name=op.f(f"fk_{T}_user_id")),
    )


def downgrade() -> None:
    op.drop_table(T)
