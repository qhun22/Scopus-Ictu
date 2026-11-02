"""Primary Scopus ID label per lecturer: append-only event history.

Additive. Creates one table plus a guard trigger that refuses UPDATE, DELETE and TRUNCATE
(an owner or superuser can still disable it; this is not immutability against them). No
existing table is altered and the label never merges or changes any identity.

Revision ID: f2b8c3d19a47, revises e4a1b7c92d10. Not applied to any database by this change.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2b8c3d19a47"
down_revision: str | None = "e4a1b7c92d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "lecturer_primary_scopus_events"

FORBID = """
CREATE FUNCTION lpse_forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION USING
        MESSAGE = 'lecturer_primary_scopus_events is append-only: ' || TG_OP || ' is refused',
        ERRCODE = 'integrity_constraint_violation';
END
$$
"""


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("lecturer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("acted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("action IN ('SET', 'CLEAR')", name=op.f(f"ck_{T}_action")),
        sa.CheckConstraint("btrim(reason) <> ''", name=op.f(f"ck_{T}_reason_not_empty")),
        sa.CheckConstraint("(action = 'SET') = (identity_id IS NOT NULL)",
                           name=op.f(f"ck_{T}_identity_matches_action")),
        sa.ForeignKeyConstraint(["lecturer_id"], ["lecturers.id"], ondelete="RESTRICT",
                                name=op.f("fk_lpse_lecturer_id")),
        sa.ForeignKeyConstraint(["identity_id"], ["lecturer_scopus_identities.id"],
                                ondelete="RESTRICT", name=op.f("fk_lpse_identity_id")),
        sa.ForeignKeyConstraint(["acted_by_user_id"], ["users.id"], ondelete="RESTRICT",
                                name=op.f("fk_lpse_acted_by_user_id")),
    )
    op.create_index("ix_lpse_lecturer_seq", T, ["lecturer_id", "seq"])
    op.execute(FORBID)
    op.execute(f"CREATE TRIGGER lpse_forbid_update_delete BEFORE UPDATE OR DELETE ON {T} "
               "FOR EACH ROW EXECUTE FUNCTION lpse_forbid_mutation()")
    op.execute(f"CREATE TRIGGER lpse_forbid_truncate BEFORE TRUNCATE ON {T} "
               "FOR EACH STATEMENT EXECUTE FUNCTION lpse_forbid_mutation()")
    op.execute(f"ALTER TABLE {T} ENABLE ALWAYS TRIGGER lpse_forbid_update_delete")
    op.execute(f"ALTER TABLE {T} ENABLE ALWAYS TRIGGER lpse_forbid_truncate")


def downgrade() -> None:
    # Dropping the table would destroy the label history; fail closed if any row exists.
    op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {T}) THEN "
               f"RAISE EXCEPTION 'refusing to drop {T}: history is append-only'; "
               "END IF; END $$;")
    op.drop_table(T)
    op.execute("DROP FUNCTION lpse_forbid_mutation()")
