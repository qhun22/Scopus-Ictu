"""Allow a LECTURER account that is not yet linked to a lecturer profile.

Revision ID: f6a1b2c3d4e5
Revises: e1a2b3c4d5f6
Create Date: 2026-10-11

Before this revision ``ck_users_lecturer_account_required`` forced every
LECTURER account to reference a ``lecturers`` row, so no LECTURER could exist
without the ICTU lecturer JSON.  The constraint is dropped; the account stays
valid (role CHECK, unique e-mail, auth_version...) and the application keeps
treating an unlinked LECTURER as read-only: it never receives a Scopus identity
implicitly and the ``/lecturers/me/*`` endpoints answer ``LECTURER_NOT_LINKED``.

``downgrade`` re-creates the constraint and refuses to run while unlinked
LECTURER accounts exist (it would otherwise fail halfway or silently delete
accounts).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2c3d4e5"
down_revision = "e1a2b3c4d5f6"
branch_labels = None
depends_on = None

_CONSTRAINT = "ck_users_lecturer_account_required"


def upgrade() -> None:
    op.drop_constraint(op.f(_CONSTRAINT), "users", type_="check")


def downgrade() -> None:
    bind = op.get_bind()
    unlinked = bind.execute(
        sa.text("SELECT count(*) FROM users WHERE role = 'LECTURER' AND lecturer_id IS NULL")
    ).scalar_one()
    if unlinked:
        raise RuntimeError(
            f"Cannot restore {_CONSTRAINT}: {unlinked} LECTURER account(s) have no lecturer profile."
        )
    op.create_check_constraint(
        op.f(_CONSTRAINT),
        "users",
        "role <> 'LECTURER' OR lecturer_id IS NOT NULL",
    )
