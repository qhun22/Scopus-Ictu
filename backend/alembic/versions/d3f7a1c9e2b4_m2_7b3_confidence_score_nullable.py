"""Allow absent machine-derived identity evidence confidence scores.

Revision ID: d3f7a1c9e2b4
Revises: b27c9d1e4f60
Create Date: 2026-10-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d3f7a1c9e2b4"
down_revision = "b27c9d1e4f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Permit NULL when no machine-derived score is available."""
    op.alter_column(
        "identity_evidence",
        "confidence_score",
        existing_type=sa.Numeric(precision=5, scale=4),
        existing_nullable=False,
        nullable=True,
    )


def downgrade() -> None:
    """Restore the frozen non-NULL contract."""
    op.alter_column(
        "identity_evidence",
        "confidence_score",
        existing_type=sa.Numeric(precision=5, scale=4),
        existing_nullable=True,
        nullable=False,
    )
