"""G09: append-only per-lecturer publication exclusion events.

Additive. Creates one table and a guard trigger that refuses UPDATE, DELETE and TRUNCATE
(an owner or superuser can still disable it; this is not immutability against them).
No existing table is altered.

Revision ID: e4a1b7c92d10, revises d0b14a77c8e2. Not applied to any database by this change.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e4a1b7c92d10"
down_revision: str | None = "d0b14a77c8e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "lecturer_publication_exclusion_events"

FORBID = """
CREATE FUNCTION lpee_forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION USING
        MESSAGE = 'lecturer_publication_exclusion_events is append-only: ' || TG_OP
                  || ' is refused',
        ERRCODE = 'integrity_constraint_violation';
END
$$
"""


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("lecturer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("acted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("action IN ('EXCLUDE', 'INCLUDE')", name=op.f(f"ck_{T}_action")),
        sa.CheckConstraint("btrim(reason) <> ''", name=op.f(f"ck_{T}_reason_not_empty")),
        sa.ForeignKeyConstraint(["lecturer_id"], ["lecturers.id"], ondelete="RESTRICT",
                                name=op.f("fk_lpee_lecturer_id")),
        sa.ForeignKeyConstraint(["publication_id"], ["publications.id"], ondelete="RESTRICT",
                                name=op.f("fk_lpee_publication_id")),
        sa.ForeignKeyConstraint(["acted_by_user_id"], ["users.id"], ondelete="RESTRICT",
                                name=op.f("fk_lpee_acted_by_user_id")),
    )
    op.create_index("ix_lpee_pair_seq", T, ["lecturer_id", "publication_id", "seq"])
    op.execute(FORBID)
    op.execute(f"CREATE TRIGGER lpee_forbid_update_delete BEFORE UPDATE OR DELETE ON {T} "
               "FOR EACH ROW EXECUTE FUNCTION lpee_forbid_mutation()")
    op.execute(f"CREATE TRIGGER lpee_forbid_truncate BEFORE TRUNCATE ON {T} "
               "FOR EACH STATEMENT EXECUTE FUNCTION lpee_forbid_mutation()")
    op.execute(f"ALTER TABLE {T} ENABLE ALWAYS TRIGGER lpee_forbid_update_delete")
    op.execute(f"ALTER TABLE {T} ENABLE ALWAYS TRIGGER lpee_forbid_truncate")


def downgrade() -> None:
    # Dropping the table would destroy exclusion history; fail closed if any row exists.
    op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {T}) THEN "
               f"RAISE EXCEPTION 'refusing to drop {T}: history is append-only'; "
               "END IF; END $$;")
    op.drop_table(T)
    op.execute("DROP FUNCTION lpee_forbid_mutation()")
