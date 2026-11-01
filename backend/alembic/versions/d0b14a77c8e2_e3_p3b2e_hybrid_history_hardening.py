"""E3-P3-B2-E targeted hardening of the hybrid SOURCE_CLAIM history (additive).

Revises c99a03e55ff3 without rewriting it. c99a03e55ff3 is an untracked source file that
this repository never applied to a database, but nothing proves that no developer database
has run it, so the hardening is a new additive revision that is correct on both paths.

What it adds, finding by finding:

* F1  BEFORE UPDATE/DELETE row triggers and a BEFORE TRUNCATE trigger on all seven
      ``sc_hybrid_*`` relations (ENABLE ALWAYS, so ``session_replication_role = replica``
      does not skip them). They stop every role that is not the table owner or a
      superuser. An owner or superuser can still ``ALTER TABLE ... DISABLE TRIGGER``:
      that is a privileged-administrator bypass, not something this migration prevents.
* F4/F5  ``previous_stream_seq`` plus a composite FK, so a predecessor's id, hash,
      stream and sequence number must all describe one and the same event.
* F6  event -> context composite FK, so an event's candidate stream and policy digest
      equal its context's.
* F3/F7/F8  BEFORE INSERT lifecycle triggers on proposals, approvals and revocations. They
      take the same per-candidate advisory lock as the service, so a writer that does not
      use the service is serialized with it.

No finalization relation is added and no table is altered other than the one new column
on ``sc_hybrid_events``. Source only: this gate applied it to no application database.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d0b14a77c8e2"
down_revision: str | None = "c99a03e55ff3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVENTS = "sc_hybrid_events"
CONTEXTS = "sc_hybrid_contexts"
PROPOSALS = "sc_hybrid_proposals"
APPROVALS = "sc_hybrid_approvals"
REVOCATIONS = "sc_hybrid_revocations"
TABLES = ("sc_hybrid_policies", CONTEXTS, "sc_hybrid_provenance", EVENTS, PROPOSALS,
          APPROVALS, REVOCATIONS)

# zlib.crc32(b"scopus-ictu:source-claim-hybrid") & 0x7FFFFFFF. The service takes
# pg_advisory_xact_lock(LOCK_NAMESPACE, hashtext(<candidate uuid text>)); the triggers take
# the very same lock, and a PostgreSQL test pins both constants and both derivations.
LOCK_NAMESPACE = 1835032549

FORBID_MUTATION = """
CREATE FUNCTION sc_hybrid_forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION USING
        MESSAGE = 'sc_hybrid history is append-only: ' || TG_OP || ' on ' || TG_TABLE_NAME
                  || ' is refused',
        ERRCODE = 'integrity_constraint_violation';
END
$$
"""

LOCK_STREAM = f"""
CREATE FUNCTION sc_hybrid_lock_stream(candidate uuid) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    -- The lifecycle checks read other transactions' committed rows after the lock is
    -- granted. That is only sound when every statement takes a fresh snapshot.
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION USING
            MESSAGE = 'sc_hybrid lifecycle rules require READ COMMITTED isolation',
            ERRCODE = 'check_violation';
    END IF;
    PERFORM pg_advisory_xact_lock({LOCK_NAMESPACE}, hashtext(candidate::text));
END
$$
"""

CHECK_PROPOSAL = """
CREATE FUNCTION sc_hybrid_check_proposal() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    ev record;
BEGIN
    SELECT e.event_kind, e.context_id, e.stream_candidate_id, e.policy_digest INTO ev
      FROM sc_hybrid_events e WHERE e.event_id = NEW.proposal_id;
    IF NOT FOUND THEN
        RETURN NEW;                       -- the foreign key reports the missing event
    END IF;
    IF ev.event_kind <> 'PROPOSE' OR ev.context_id <> NEW.context_id
       OR ev.stream_candidate_id <> NEW.candidate_id
       OR ev.policy_digest <> NEW.policy_digest THEN
        RAISE EXCEPTION USING
            MESSAGE = 'sc_hybrid proposal must describe its own PROPOSE event',
            ERRCODE = 'check_violation';
    END IF;
    PERFORM sc_hybrid_lock_stream(NEW.candidate_id);
    -- Many historical proposals are allowed; only one may be effective. A proposal stops
    -- being effective once a REVOKE or SUPERSEDE targets it.
    IF EXISTS (
        SELECT 1 FROM sc_hybrid_proposals p
         WHERE p.candidate_id = NEW.candidate_id AND p.proposal_id <> NEW.proposal_id
           AND NOT EXISTS (SELECT 1 FROM sc_hybrid_revocations r
                            WHERE r.target_event_id = p.proposal_id)) THEN
        RAISE EXCEPTION USING
            MESSAGE = 'sc_hybrid candidate already has an effective proposal',
            ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

CHECK_APPROVAL = """
CREATE FUNCTION sc_hybrid_check_approval() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    ev record;
    pe record;
BEGIN
    SELECT e.event_kind, e.context_id, e.stream_candidate_id, e.stream_seq INTO ev
      FROM sc_hybrid_events e WHERE e.event_id = NEW.approval_id;
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;
    SELECT e.event_kind, e.stream_candidate_id, e.stream_seq INTO pe
      FROM sc_hybrid_events e WHERE e.event_id = NEW.proposal_id;
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;
    IF ev.event_kind <> 'APPROVE_EXCEPTION' OR pe.event_kind <> 'PROPOSE'
       OR ev.stream_candidate_id <> pe.stream_candidate_id
       OR ev.context_id <> NEW.context_id OR ev.stream_seq <= pe.stream_seq THEN
        RAISE EXCEPTION USING
            MESSAGE = 'sc_hybrid approval must be a later APPROVE_EXCEPTION of a PROPOSE '
                      || 'in the same stream and context',
            ERRCODE = 'check_violation';
    END IF;
    PERFORM sc_hybrid_lock_stream(pe.stream_candidate_id);
    IF EXISTS (SELECT 1 FROM sc_hybrid_revocations r
                WHERE r.target_event_id = NEW.proposal_id) THEN
        RAISE EXCEPTION USING
            MESSAGE = 'sc_hybrid proposal was revoked or superseded and cannot be approved',
            ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

CHECK_REVOCATION = """
CREATE FUNCTION sc_hybrid_check_revocation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    ev record;
    tgt record;
    rep record;
BEGIN
    SELECT e.event_kind, e.stream_candidate_id, e.stream_seq INTO ev
      FROM sc_hybrid_events e WHERE e.event_id = NEW.revocation_id;
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;
    SELECT e.event_kind, e.stream_candidate_id, e.stream_seq INTO tgt
      FROM sc_hybrid_events e WHERE e.event_id = NEW.target_event_id;
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;
    -- Only a proposal or an approval can be compensated; a REVOKE or SUPERSEDE is final.
    IF ev.event_kind <> NEW.revocation_kind
       OR ev.stream_candidate_id <> tgt.stream_candidate_id
       OR ev.stream_seq <= tgt.stream_seq
       OR tgt.event_kind NOT IN ('PROPOSE', 'APPROVE_EXCEPTION') THEN
        RAISE EXCEPTION USING
            MESSAGE = 'sc_hybrid revocation must be a later REVOKE or SUPERSEDE of a '
                      || 'PROPOSE or APPROVE_EXCEPTION in the same stream',
            ERRCODE = 'check_violation';
    END IF;
    PERFORM sc_hybrid_lock_stream(tgt.stream_candidate_id);
    IF NEW.replacement_event_id IS NOT NULL THEN
        SELECT e.event_kind, e.stream_candidate_id, e.stream_seq INTO rep
          FROM sc_hybrid_events e WHERE e.event_id = NEW.replacement_event_id;
        IF NOT FOUND THEN
            RETURN NEW;
        END IF;
        IF rep.event_kind NOT IN ('PROPOSE', 'APPROVE_EXCEPTION')
           OR rep.stream_candidate_id <> tgt.stream_candidate_id
           OR rep.stream_seq <= tgt.stream_seq OR rep.stream_seq >= ev.stream_seq
           OR EXISTS (SELECT 1 FROM sc_hybrid_revocations r
                       WHERE r.target_event_id = NEW.replacement_event_id) THEN
            RAISE EXCEPTION USING
                MESSAGE = 'sc_hybrid replacement must be an effective PROPOSE or '
                          || 'APPROVE_EXCEPTION recorded after the target',
                ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$$
"""

LIFECYCLE = (
    (PROPOSALS, "sc_hybrid_check_proposal"),
    (APPROVALS, "sc_hybrid_check_approval"),
    (REVOCATIONS, "sc_hybrid_check_revocation"),
)


def _ck(table: str, name: str, sql: str) -> None:
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, sql)


def upgrade() -> None:
    # F4/F5: the predecessor's stream position becomes a stored, constrained fact. The
    # backfill runs before any trigger exists and is a pure function of existing columns.
    op.add_column(EVENTS, sa.Column("previous_stream_seq", sa.Integer(), nullable=True))
    op.execute("UPDATE sc_hybrid_events SET previous_stream_seq = stream_seq - 1 "
               "WHERE previous_event_id IS NOT NULL")
    _ck(EVENTS, "previous_stream_seq",
        "(previous_stream_seq IS NULL) = (previous_event_id IS NULL) "
        "AND (previous_stream_seq IS NULL OR previous_stream_seq = stream_seq - 1)")
    op.create_unique_constraint("uq_sc_hybrid_events_chain_link", EVENTS,
                                ["stream_candidate_id", "stream_seq", "event_id",
                                 "envelope_hash"])
    op.create_foreign_key(
        op.f("fk_sc_hybrid_events_chain_link"), EVENTS, EVENTS,
        ["stream_candidate_id", "previous_stream_seq", "previous_event_id",
         "previous_event_hash"],
        ["stream_candidate_id", "stream_seq", "event_id", "envelope_hash"],
        ondelete="RESTRICT")

    # F6: an event's stream and policy are its context's candidate and policy.
    op.create_unique_constraint("uq_sc_hybrid_contexts_candidate_policy", CONTEXTS,
                                ["id", "candidate_id", "policy_digest"])
    op.create_foreign_key(
        op.f("fk_sc_hybrid_events_context_candidate_policy"), EVENTS, CONTEXTS,
        ["context_id", "stream_candidate_id", "policy_digest"],
        ["id", "candidate_id", "policy_digest"], ondelete="RESTRICT")

    # F3/F7/F8 lifecycle triggers, then F1 last so the backfill above was never blocked.
    op.execute(LOCK_STREAM)
    for table, function in LIFECYCLE:
        op.execute({"sc_hybrid_check_proposal": CHECK_PROPOSAL,
                    "sc_hybrid_check_approval": CHECK_APPROVAL,
                    "sc_hybrid_check_revocation": CHECK_REVOCATION}[function])
        op.execute(f"CREATE TRIGGER sc_hybrid_lifecycle_check BEFORE INSERT ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION {function}()")
        op.execute(f"ALTER TABLE {table} ENABLE ALWAYS TRIGGER sc_hybrid_lifecycle_check")

    op.execute(FORBID_MUTATION)
    for table in TABLES:
        op.execute(f"CREATE TRIGGER sc_hybrid_forbid_update_delete "
                   f"BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION sc_hybrid_forbid_mutation()")
        op.execute(f"CREATE TRIGGER sc_hybrid_forbid_truncate BEFORE TRUNCATE ON {table} "
                   "FOR EACH STATEMENT EXECUTE FUNCTION sc_hybrid_forbid_mutation()")
        op.execute(f"ALTER TABLE {table} ENABLE ALWAYS TRIGGER sc_hybrid_forbid_update_delete")
        op.execute(f"ALTER TABLE {table} ENABLE ALWAYS TRIGGER sc_hybrid_forbid_truncate")


def downgrade() -> None:
    # Structural rollback of the hardening only; recorded history is untouched.
    for table in TABLES:
        op.execute(f"DROP TRIGGER sc_hybrid_forbid_truncate ON {table}")
        op.execute(f"DROP TRIGGER sc_hybrid_forbid_update_delete ON {table}")
    op.execute("DROP FUNCTION sc_hybrid_forbid_mutation()")
    for table, function in LIFECYCLE:
        op.execute(f"DROP TRIGGER sc_hybrid_lifecycle_check ON {table}")
        op.execute(f"DROP FUNCTION {function}()")
    op.execute("DROP FUNCTION sc_hybrid_lock_stream(uuid)")
    op.drop_constraint(op.f("fk_sc_hybrid_events_context_candidate_policy"), EVENTS,
                       type_="foreignkey")
    op.drop_constraint("uq_sc_hybrid_contexts_candidate_policy", CONTEXTS, type_="unique")
    op.drop_constraint(op.f("fk_sc_hybrid_events_chain_link"), EVENTS, type_="foreignkey")
    op.drop_constraint("uq_sc_hybrid_events_chain_link", EVENTS, type_="unique")
    op.drop_constraint(op.f("ck_sc_hybrid_events_previous_stream_seq"), EVENTS, type_="check")
    op.drop_column(EVENTS, "previous_stream_seq")
