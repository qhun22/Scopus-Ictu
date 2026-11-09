"""Add ``users.has_password`` and ``users.google_linked``.

Both track real login-method facts so the UI can stop hard-coding "Email" as
the login method: ``has_password`` is false only for an account whose
``password_hash`` is an unusable random placeholder (auto-provisioned by
Google Sign-In, never set by an ADMIN); ``google_linked`` is true once that
account has signed in with Google at least once. Either, both, or (for very
old rows) neither can be true at once — password and Google sign-in are
independent, coexisting login paths into the same account.

Backfill: every existing row predates Google Sign-In, so ``has_password``
defaults true (matches reality — every one has an ADMIN-set password) and
``google_linked`` defaults false (matches reality — none has used Google
yet) for all of them; new server defaults then carry forward correctly.

Revision ID: e8b2c6a94f17, revises c4f1a7e9d203.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8b2c6a94f17"
down_revision: str | None = "c4f1a7e9d203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "has_password", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "google_linked", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "google_linked")
    op.drop_column("users", "has_password")
