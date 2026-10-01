"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

M1.2 NOTE: revision template restored to the canonical Alembic form so
that subsequent revisions (M1.2+, if governance approves) can be
generated with ``alembic revision --autogenerate``.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """Apply schema changes."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Revert schema changes."""
    ${downgrades if downgrades else "pass"}