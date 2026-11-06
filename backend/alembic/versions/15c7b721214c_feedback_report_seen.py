"""Per-user, per-report "last seen" marker for the feedback intake queue.

Additive. One new table; no existing table is altered. Separate from
``feedback_read_states`` (which only drives the global "Bao loi" nav dot):
this one lets the UI show an unread indicator on the specific report that
changed, by comparing each report's latest relevant activity against the
viewer's own last-seen time for that one report (defaulting to epoch if the
viewer never opened it).

Revision ID: 15c7b721214c, revises d4e7c3a98f12. Not applied to any database
by this change.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "15c7b721214c"
down_revision: str | None = "d4e7c3a98f12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "feedback_report_seen"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE",
                                name=op.f(f"fk_{T}_user_id")),
        sa.ForeignKeyConstraint(["report_id"], ["feedback_reports.id"], ondelete="CASCADE",
                                name=op.f(f"fk_{T}_report_id")),
    )


def downgrade() -> None:
    op.drop_table(T)
