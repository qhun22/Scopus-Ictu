"""M2.4 account session revocation and persistent user notifications.

Revision ID: a7d9c4e2f601
Revises: e5b3cf21c1d12b64
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a7d9c4e2f601"
down_revision: Union[str, None] = "e5b3cf21c1d12b64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.create_check_constraint(
        op.f("ck_users_auth_version"),
        "users",
        "auth_version >= 1",
    )

    op.create_table(
        "user_notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "notification_type IN ("
            "'PROFILE_UPDATED', 'ROLE_CHANGED', 'ACCOUNT_LOCKED', "
            "'ACCOUNT_UNLOCKED', 'PASSWORD_RESET'"
            ")",
            name=op.f("ck_user_notifications_notification_type"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object'",
            name=op.f("ck_user_notifications_metadata_object"),
        ),
        sa.CheckConstraint(
            "(is_read = FALSE AND read_at IS NULL) OR "
            "(is_read = TRUE AND read_at IS NOT NULL)",
            name=op.f("ck_user_notifications_read_consistency"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_notifications_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_notifications")),
    )
    op.create_index(
        op.f("ix_user_notifications_user_id"),
        "user_notifications",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_notifications_created_at"),
        "user_notifications",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_notifications_unread_lookup",
        "user_notifications",
        ["user_id", "is_read", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("user_notifications")
    op.drop_constraint(op.f("ck_users_auth_version"), "users", type_="check")
    op.drop_column("users", "auth_version")
