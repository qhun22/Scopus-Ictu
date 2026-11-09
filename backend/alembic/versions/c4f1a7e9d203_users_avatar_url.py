"""Add ``users.avatar_url``.

Nullable, set from the Google "picture" claim on Google Sign-In and refreshed
on every such login; NULL for password-only accounts, which keep the existing
initials-placeholder avatar in the UI. Schema-only, no data to backfill.

Revision ID: c4f1a7e9d203, revises b3d91f4c7a20.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4f1a7e9d203"
down_revision: str | None = "b3d91f4c7a20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
