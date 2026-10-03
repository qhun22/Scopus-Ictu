"""M2.6A normalization summary — additive JSONB column for scopus_imports.

Does NOT modify M1 initial migration.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f4c8b1a2e9d7"
down_revision: Union[str, None] = "c3f0b9a18d42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive: adds a nullable JSONB column for normalization counters.
    # Does NOT touch error_summary — raw validation errors remain preserved.
    # CHECK constraint mirrors the error_summary shape guard (FC-02).
    op.add_column(
        "scopus_imports",
        sa.Column(
            "normalization_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("NULL"),
        ),
    )
    op.create_check_constraint(
        "ck_scopus_imports_normalization_summary_object",
        "scopus_imports",
        "normalization_summary IS NULL OR jsonb_typeof(normalization_summary) = 'object'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_scopus_imports_normalization_summary_object",
        "scopus_imports",
        type_="check",
    )
    op.drop_column("scopus_imports", "normalization_summary")
