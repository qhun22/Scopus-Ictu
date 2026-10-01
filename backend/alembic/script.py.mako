"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

M0 NOTE: real revisions live in M1. This template is the canonical scaffold.
"""

from __future__ import annotations

# TODO(M1): replace with real revision imports.
# from alembic import op
# import sqlalchemy as sa
# ${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """M0 stub. TODO(M1): apply schema changes."""
    raise NotImplementedError("M0 has no real migrations.")


def downgrade() -> None:
    """M0 stub. TODO(M1): revert schema changes."""
    raise NotImplementedError("M0 has no real migrations.")