"""Allow duplicate lecturer emails to be retained for admin reconciliation.

Revision ID: c3f0b9a18d42
Revises: a7d9c4e2f601
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3f0b9a18d42"
down_revision: Union[str, None] = "a7d9c4e2f601"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_lecturers_email_ci", table_name="lecturers")
    op.create_index(
        "ix_lecturers_email_ci",
        "lecturers",
        [sa.text("lower(email)")],
        unique=False,
        postgresql_where=sa.text("email IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_lecturers_email_ci", table_name="lecturers")
    op.create_index(
        "uq_lecturers_email_ci",
        "lecturers",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
