"""Add specialization, gender, date_of_birth, phone to lecturers.

Revision ID: e1a2b3c4d5f6
Revises: d3f7a1c9e2b4
Create Date: 2026-10-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e1a2b3c4d5f6"
down_revision = ("d3f7a1c9e2b4", "a9c2e4f71b30")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lecturers",
        sa.Column("specialization", sa.String(200), nullable=True),
    )
    op.add_column(
        "lecturers",
        sa.Column("gender", sa.String(10), nullable=True),
    )
    op.add_column(
        "lecturers",
        sa.Column("date_of_birth", sa.Date(), nullable=True),
    )
    op.add_column(
        "lecturers",
        sa.Column("phone", sa.String(20), nullable=True),
    )
    op.create_check_constraint(
        "ck_lecturers_gender",
        "lecturers",
        "gender IS NULL OR gender IN ('Nam', 'Nữ', 'Khác')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_lecturers_gender", "lecturers", type_="check")
    op.drop_column("lecturers", "phone")
    op.drop_column("lecturers", "date_of_birth")
    op.drop_column("lecturers", "gender")
    op.drop_column("lecturers", "specialization")
