"""E3-P3-B2-D hybrid history on real PostgreSQL. NOT executed until a PG target exists.

Requires TEST_DATABASE_URL pointing to an allowlisted disposable database; the conftest
guard (tests/db_safety_guard.py) re-verifies the target and there is no bypass. Each test
works in its own schema: the real B2-D migration DDL creates the seven ``sc_hybrid_*``
relations, the surrounding tables come from the models, and the schema is dropped after.

This file is what proves the parts SQLite cannot: real CHECK constraints, real foreign
keys, and append concurrency under the per-stream advisory lock. All authority
attestations are SYNTHETIC; no production decision is executed and submit stays inactive.
"""

from __future__ import annotations

import importlib.util
import threading
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import APIError
from app.models.base import Base
from app.models.candidate import (
    LecturerScopusCandidate,
    LecturerScopusCandidateObservation,
)
from app.models.governance import User
from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.models.source_claim_hybrid import HYBRID_TABLES
from app.models.source_staging import (
    SOURCE_CAPTURE_ANALYSES_SQL,
    SOURCE_CAPTURE_ANALYSES_VIEW,
    SOURCE_CLAIM_OBSERVATIONS_SQL,
    SOURCE_CLAIM_OBSERVATIONS_VIEW,
    SourceArtifact,
)
from app.services.matching.source_claim_candidate_persistence import (
    SourceClaimCandidateWriter,
)
from app.services.source_claim_decision_boundary import (
    ReviewerContext,
    SourceClaimAcceptContext,
)
from app.services.source_claim_hybrid import (
    RISK_ACKNOWLEDGMENT,
    AuthorityFacts,
    Grant,
    HumanAuthority,
    HybridCommand,
    HybridSourceClaimCompatibility,
    ReviewBranch,
    SourceAuthenticity,
    SourceAuthenticityState,
)
from app.services.source_claim_hybrid_persistence import HybridDecisionJournal
from app.services.source_staging.service import Actor, SourceStagingService
from tests.db_safety_guard import assert_safe_for_destructive_test
from tests.source_staging_fixtures import REPO, multi_row, multi_snapshot, sid

MIGRATION = (Path(__file__).resolve().parents[2] / "alembic" / "versions"
             / "c99a03e55ff3_e3_p3b2d_source_claim_hybrid_history.py")
HARDENING = MIGRATION.with_name("d0b14a77c8e2_e3_p3b2e_hybrid_history_hardening.py")
ACTOR = Actor(service="e3-p3b2d-pg-tests")
AT = datetime(2026, 10, 30, 10, tzinfo=UTC)
LATER = AT + timedelta(minutes=5)
RUN = uuid.UUID(int=500)


def uid(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


class SyntheticAuthority:
    """TEST-ONLY authority. Authenticates nothing; exists to reach the write path."""

    def __init__(self, facts: AuthorityFacts) -> None:
        self.facts = facts

    def load(self, view, context_digest):
        return self.facts


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _migration_module():
    return _load(MIGRATION, "e3_p3b2d_pg")


def _hardening_module():
    return _load(HARDENING, "e3_p3b2e_pg")


@pytest.fixture
def pg(isolated_db_engine: Engine | None) -> Generator[sessionmaker, None, None]:
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL test database available.")
    schema = f"e3p3b2d_{uuid.uuid4().hex}"
    with isolated_db_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(isolated_db_engine.url, future=True, pool_pre_ping=True,
                           connect_args={"options": f"-csearch_path={schema} "
                                                    "-cstatement_timeout=30000 "
                                                    "-clock_timeout=30s"})
    try:
        others = [t for n, t in Base.metadata.tables.items() if n not in HYBRID_TABLES]
        Base.metadata.create_all(bind=engine, tables=others)
        with engine.begin() as conn:
            # create_all builds tables only; the staging views live in migration a77e01c33ee1.
            # Same SQL text (a unit test pins model == migration), needed by activate_rule_set().
            conn.exec_driver_sql(f"CREATE VIEW {SOURCE_CAPTURE_ANALYSES_VIEW} AS "
                                 f"{SOURCE_CAPTURE_ANALYSES_SQL}")
            conn.exec_driver_sql(f"CREATE VIEW {SOURCE_CLAIM_OBSERVATIONS_VIEW} AS "
                                 f"{SOURCE_CLAIM_OBSERVATIONS_SQL}")
        with engine.begin() as conn:
            # Same wiring as alembic/env.py: target_metadata carries the naming convention.
            context = MigrationContext.configure(conn, opts={"target_metadata": Base.metadata})
            with Operations.context(context):
                _migration_module().upgrade()        # the real B2-D DDL and CHECKs
                _hardening_module().upgrade()        # B2-E hardening: triggers, composite keys
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()
        assert_safe_for_destructive_test(isolated_db_engine)
        with isolated_db_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def world(pg: sessionmaker):
    """Synthetic lecturers, authors, users, one staged declaration and its candidates."""
    with pg() as db:
        SourceStagingService(db, ACTOR).activate_rule_set()
        for n in (1, 2, 3):
            db.add(Lecturer(
                id=uid(n), full_name=f"Unrelated lecturer name {n}",
                full_name_normalized=f"unrelated lecturer name {n}",
                email=f"gv{n}@example.invalid", version=1,
                repository_profile_url=f"{REPO}/giang-vien/synthetic-{n}/"))
            db.add(ScopusAuthor(id=uid(100 + n), scopus_id=sid(n),
                                preferred_name=f"Completely different author {n}"))
        for n, role in ((750, "REVIEWER"), (751, "REVIEWER")):
            db.add(User(id=uid(n), email=f"reviewer{n}@example.invalid",
                        password_hash="synthetic", display_name=f"Synthetic human {n}",
                        role=role, is_active=True, version=1, auth_version=1))
        db.commit()
    with pg() as db:
        SourceStagingService(db, ACTOR).ingest_guide_snapshot(
            **multi_snapshot([multi_row(1, [sid(1)])], ts="2026-10-29T00:00:00Z"),
            completeness="COMPLETE")
        SourceClaimCandidateWriter(db).persist_generation(RUN)
        db.commit()
    return pg


def _command(db: Session) -> HybridCommand:
    candidate = db.scalar(select(LecturerScopusCandidate).where(
        LecturerScopusCandidate.lecturer_id == uid(1),
        LecturerScopusCandidate.scopus_author_id == uid(101)))
    observation = db.scalar(select(LecturerScopusCandidateObservation).where(
        LecturerScopusCandidateObservation.candidate_id == candidate.id,
        LecturerScopusCandidateObservation.generation_run_id == RUN))
    source = SourceClaimAcceptContext(
        candidate.id, observation.id, candidate.version,
        "Synthetic declaration reviewed; no identity approval")
    return HybridCommand(source, ReviewBranch.INSTITUTIONAL_EXCEPTION,
                         risk_acknowledgment=RISK_ACKNOWLEDGMENT)


def _journal(db: Session, command: HybridCommand):
    """Build the boundary and a SYNTHETIC authority bound to this exact context."""
    from app.services.source_claim_decision_boundary import SourceClaimDecisionBoundary

    actor, approver = ReviewerContext(uid(750), 1), ReviewerContext(uid(751), 1)
    base = SourceClaimDecisionBoundary(db).prepare(actor, command.source)
    humans = tuple(HumanAuthority(
        uid(750 + n), uid(900 + n), 1, True,
        (Grant.PROPOSE_EXCEPTION, Grant.APPROVE_EXCEPTION), uid(800 + n), "2" * 64)
        for n in (0, 1))
    authenticity = tuple(SourceAuthenticity(
        a.id, a.artifact_bytes_sha256, "ICTU", SourceAuthenticityState.CURRENT,
        uid(810 + n), "3" * 64, "FORMALLY_VERIFIED_ISSUANCE_V1")
        for n, a in enumerate(db.scalars(select(SourceArtifact)).all()))
    authority = SyntheticAuthority(
        AuthorityFacts(base.snapshot_hash, "4" * 64, (), humans, authenticity))
    boundary = HybridSourceClaimCompatibility(db, authority=authority)
    return HybridDecisionJournal(db, compatibility=boundary), boundary, actor, approver


def _count(db: Session, table: str) -> int:
    return db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


# ---------------------------------------------------------------------------
# Round trip under real constraints
# ---------------------------------------------------------------------------

def test_pg_proposal_and_approval_round_trip(world):
    with world() as db:
        command = _command(db)
        journal, boundary, actor, approver = _journal(db, command)
        proposal = journal.record_proposal(actor, command, proposed_at=AT)
        draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
        approval = journal.record_exception_approval(
            actor, approver, command, draft, proposed_at=AT, approved_at=LATER)
        db.commit()
        assert (proposal.outcome, proposal.stream_seq) == ("APPENDED", 1)
        assert (approval.outcome, approval.stream_seq) == ("APPENDED", 2)
    with world() as db:
        assert _count(db, "sc_hybrid_events") == 2
        assert _count(db, "sc_hybrid_proposals") == 1
        assert _count(db, "sc_hybrid_approvals") == 1
        assert _count(db, "sc_hybrid_provenance") >= 1
        # Still no acceptance anywhere.
        assert db.scalars(select(LecturerScopusIdentity)).all() == []
        assert db.scalars(select(IdentityEvidence)).all() == []


def test_pg_replay_of_the_same_proposal_is_idempotent(world):
    with world() as db:
        command = _command(db)
        journal, _, actor, _ = _journal(db, command)
        first = journal.record_proposal(actor, command, proposed_at=AT)
        again = journal.record_proposal(actor, command, proposed_at=AT)
        db.commit()
    assert again.outcome == "ALREADY_RECORDED" and again.event_id == first.event_id
    with world() as db:
        assert _count(db, "sc_hybrid_events") == 1


# ---------------------------------------------------------------------------
# Constraints that only PostgreSQL enforces
# ---------------------------------------------------------------------------

def _recorded_proposal(world):
    with world() as db:
        command = _command(db)
        journal, _, actor, _ = _journal(db, command)
        result = journal.record_proposal(actor, command, proposed_at=AT)
        db.commit()
        return result


@pytest.mark.parametrize(("statement", "why"), [
    ("UPDATE sc_hybrid_provenance SET independently_verified = TRUE",
     "an institutional declaration can never be marked independently verified"),
    ("UPDATE sc_hybrid_events SET snapshot_json = snapshot_json || ' '",
     "the stored snapshot must keep matching its hash"),
    ("UPDATE sc_hybrid_events SET envelope_json = envelope_json || ' '",
     "the chained envelope must keep matching its hash"),
    ("UPDATE sc_hybrid_events SET actor_type = 'SYSTEM'",
     "no automated actor may hold a decision event"),
    ("UPDATE sc_hybrid_events SET actor_principal_id = NULL",
     "a decision event always names the human behind the account"),
    ("UPDATE sc_hybrid_provenance SET source_tier = 'INDEPENDENT'",
     "the source tier of a declaration is fixed"),
    ("UPDATE sc_hybrid_provenance SET issuance_state = 'REVOKED'",
     "a revoked issuance is not storable"),
])
def test_pg_checks_refuse_tampering_with_recorded_history(world, statement, why):
    """The CHECKs hold on their own: the append-only triggers are switched off (owner-level
    bypass, rolled back with the transaction) so the constraint itself is what refuses."""
    _recorded_proposal(world)
    with world() as db:
        _bypass_append_only(db)
        with pytest.raises(IntegrityError):
            db.execute(text(statement))
            db.flush()
        db.rollback()
        assert _count(db, "sc_hybrid_events") == 1, why


def test_pg_unique_refuses_a_chain_fork(world):
    proposal = _recorded_proposal(world)
    with world() as db:
        row = db.execute(text(
            "SELECT stream_candidate_id, context_id, policy_digest, actor_user_id, "
            "actor_principal_id, snapshot_json, snapshot_hash, envelope_json, "
            "envelope_hash, operation_key FROM sc_hybrid_events")).mappings().one()
        with pytest.raises(IntegrityError):
            # A second event claiming the same predecessor would branch the history.
            db.execute(text(
                "INSERT INTO sc_hybrid_events (event_id, stream_candidate_id, stream_seq, "
                "previous_stream_seq, previous_event_id, previous_event_hash, event_kind, "
                "context_id, "
                "policy_digest, actor_type, actor_user_id, actor_principal_id, "
                "actor_auth_version, operation_key, snapshot_hash, snapshot_json, "
                "envelope_hash, envelope_json, action_at) VALUES "
                "(gen_random_uuid(), :stream, 2, 1, :previous, :previous_hash, 'REVOKE', "
                ":context, :policy, 'USER', :user_id, :principal, 1, :key, :hash, "
                ":json, :envelope_hash, :envelope, now())"),
                {"stream": row["stream_candidate_id"], "previous": proposal.event_id,
                 "previous_hash": row["envelope_hash"], "context": row["context_id"],
                 "policy": row["policy_digest"], "user_id": row["actor_user_id"],
                 "principal": row["actor_principal_id"], "key": row["operation_key"],
                 "hash": row["snapshot_hash"], "json": row["snapshot_json"],
                 "envelope_hash": row["envelope_hash"], "envelope": row["envelope_json"]})
            db.flush()
        db.rollback()


def test_pg_unique_refuses_a_second_approval_of_one_proposal(world):
    with world() as db:
        command = _command(db)
        journal, boundary, actor, approver = _journal(db, command)
        journal.record_proposal(actor, command, proposed_at=AT)
        draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
        journal.record_exception_approval(
            actor, approver, command, draft, proposed_at=AT, approved_at=LATER)
        db.commit()
    with world() as db:
        command = _command(db)
        journal, boundary, actor, approver = _journal(db, command)
        draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
        with pytest.raises(APIError) as exc:
            journal.record_exception_approval(
                actor, approver, command, draft, proposed_at=AT,
                approved_at=LATER + timedelta(minutes=1))
        assert exc.value.code == "HYBRID_HISTORY_INTEGRITY_VIOLATION"
        db.rollback()
        assert _count(db, "sc_hybrid_approvals") == 1


def test_pg_check_refuses_an_approval_by_the_reviewers_own_human(world):
    with world() as db:
        command = _command(db)
        journal, _, actor, _ = _journal(db, command)
        journal.record_proposal(actor, command, proposed_at=AT)
        db.commit()
    with world() as db:
        row = db.execute(text(
            "SELECT proposal_id, context_id, branch, reviewer_user_id, "
            "reviewer_principal_id FROM sc_hybrid_proposals")).mappings().one()
        _bypass_lifecycle(db, "sc_hybrid_approvals")        # the CHECK must refuse on its own
        with pytest.raises(IntegrityError, match="distinct_"):
            db.execute(text(
                "INSERT INTO sc_hybrid_approvals (approval_id, proposal_id, context_id, "
                "branch, reviewer_user_id, reviewer_principal_id, approver_user_id, "
                "approver_principal_id, approver_auth_version, proposal_digest) VALUES "
                "(:proposal, :proposal, :context, :branch, :reviewer, :principal, "
                ":reviewer, :principal, 1, :digest)"),
                {**row, "proposal": row["proposal_id"], "context": row["context_id"],
                 "branch": row["branch"], "reviewer": row["reviewer_user_id"],
                 "principal": row["reviewer_principal_id"], "digest": "a" * 64})
            db.flush()
        db.rollback()


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

def test_pg_concurrent_identical_proposals_record_exactly_one_event(world):
    results, errors, barrier = [], [], threading.Barrier(2)

    def worker():
        try:
            with world() as db:
                command = _command(db)
                journal, _, actor, _ = _journal(db, command)
                barrier.wait(timeout=20)
                results.append(journal.record_proposal(
                    actor, command, proposed_at=AT).outcome)
                db.commit()
        except Exception as exc:                 # reported by the assertions below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    # Either the loser sees the recorded row, or it is refused: never two events.
    assert len(results) + len(errors) == 2
    with world() as db:
        assert _count(db, "sc_hybrid_events") == 1
        assert _count(db, "sc_hybrid_proposals") == 1


def test_pg_downgrade_refuses_to_drop_recorded_history(world):
    _recorded_proposal(world)
    with world() as db:
        with pytest.raises(DatabaseError):           # the RAISE EXCEPTION guard fires
            with Operations.context(MigrationContext.configure(db.connection())):
                _migration_module().downgrade()
        db.rollback()
        assert _count(db, "sc_hybrid_events") == 1


# ===========================================================================
# E3-P3-B2-E: the parts the first 14 tests do not exercise
# ===========================================================================

def _recorded_pair(world):
    """Proposal and approval committed; returns both AppendResults."""
    with world() as db:
        command = _command(db)
        journal, boundary, actor, approver = _journal(db, command)
        proposal = journal.record_proposal(actor, command, proposed_at=AT)
        draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
        approval = journal.record_exception_approval(
            actor, approver, command, draft, proposed_at=AT, approved_at=LATER)
        db.commit()
        return proposal, approval


def test_pg_catalog_constraints_match_the_models(world):
    """The migration's real PostgreSQL constraints equal the models', name for name."""
    with world() as db:
        schema = db.execute(text("SELECT current_schema()")).scalar_one()
        rows = db.execute(text(
            "SELECT cls.relname, con.conname, con.contype FROM pg_constraint con "
            "JOIN pg_class cls ON cls.oid = con.conrelid "
            "JOIN pg_namespace ns ON ns.oid = cls.relnamespace "
            "WHERE ns.nspname = :schema AND cls.relname LIKE 'sc\\_hybrid\\_%' "
            "AND con.contype IN ('p', 'u', 'f', 'c')"), {"schema": schema}).all()
    live = {(table, name, kind) for table, name, kind in rows}
    kinds = {"PrimaryKeyConstraint": "p", "UniqueConstraint": "u",
             "ForeignKeyConstraint": "f", "CheckConstraint": "c"}
    expected = set()
    for name in HYBRID_TABLES:
        for constraint in Base.metadata.tables[name].constraints:
            kind = kinds.get(type(constraint).__name__)
            if kind and constraint.name:
                expected.add((name, str(constraint.name), kind))
    assert expected, "model constraint names are resolved by the naming convention"
    assert live - expected == set() and expected - live == set()
    assert {kind for _, _, kind in live} == {"p", "u", "f", "c"}


@pytest.mark.parametrize("run", range(4))
def test_pg_concurrent_identical_proposals_give_one_append_and_one_replay(world, run):
    """Strict form of the concurrency test: the loser must resolve to the recorded event."""
    results, errors, barrier = [], [], threading.Barrier(2)

    def worker():
        try:
            with world() as db:
                command = _command(db)
                journal, _, actor, _ = _journal(db, command)
                barrier.wait(timeout=20)
                results.append(journal.record_proposal(actor, command, proposed_at=AT).outcome)
                db.commit()
        except Exception as exc:                 # reported by the assertions below
            errors.append(getattr(exc, "code", type(exc).__name__))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert errors == [] and sorted(results) == ["ALREADY_RECORDED", "APPENDED"], (results, errors)
    with world() as db:
        assert (_count(db, "sc_hybrid_events"), _count(db, "sc_hybrid_proposals")) == (1, 1)


def test_pg_advisory_lock_makes_a_second_writer_wait_for_the_first_commit(world):
    outcome, errors = [], []
    first = world()
    command = _command(first)
    journal, _, actor, _ = _journal(first, command)
    held = journal.record_proposal(actor, command, proposed_at=AT)      # lock held, uncommitted
    assert held.outcome == "APPENDED"

    def second():
        try:
            with world() as db:
                cmd = _command(db)
                other, _, act, _ = _journal(db, cmd)
                outcome.append(other.record_proposal(act, cmd, proposed_at=AT).outcome)
                db.commit()
        except Exception as exc:
            errors.append(getattr(exc, "code", type(exc).__name__))

    thread = threading.Thread(target=second)
    thread.start()
    waiting = 0
    with world() as probe:
        for _ in range(100):                                            # up to ~10 s
            waiting = probe.execute(text(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted"
            )).scalar_one()
            if waiting:
                break
            threading.Event().wait(0.1)
    assert waiting == 1 and outcome == [] and errors == []              # blocked, not finished
    first.commit()
    first.close()
    thread.join(timeout=30)
    assert errors == [] and outcome == ["ALREADY_RECORDED"], (outcome, errors)


def test_pg_failed_write_rolls_back_only_its_own_savepoint(world):
    _recorded_pair(world)
    with world() as db:
        db.add(User(id=uid(777), email="caller.write@example.invalid", password_hash="synthetic",
                    display_name="Caller earlier write", role="REVIEWER", is_active=True,
                    version=1, auth_version=1))
        db.flush()                                                      # caller's earlier work
        command = _command(db)
        journal, boundary, actor, approver = _journal(db, command)
        draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
        with pytest.raises(APIError) as exc:                            # UNIQUE: one approval
            journal.record_exception_approval(
                actor, approver, command, draft, proposed_at=AT,
                approved_at=LATER + timedelta(minutes=1))
        assert exc.value.code == "HYBRID_HISTORY_INTEGRITY_VIOLATION"
        # No rollback() by the caller: the session is still usable and keeps its own write.
        assert db.execute(text("SELECT count(*) FROM users WHERE email = "
                               "'caller.write@example.invalid'")).scalar_one() == 1
        assert (_count(db, "sc_hybrid_events"), _count(db, "sc_hybrid_approvals")) == (2, 1)
        db.commit()
    with world() as db:
        assert db.execute(text("SELECT count(*) FROM users WHERE email = "
                               "'caller.write@example.invalid'")).scalar_one() == 1
        assert (_count(db, "sc_hybrid_events"), _count(db, "sc_hybrid_approvals")) == (2, 1)


def test_pg_database_refuses_reusing_a_context_for_another_candidate(world):
    _recorded_proposal(world)
    with world() as db:
        other = LecturerScopusCandidate(lecturer_id=uid(2), scopus_author_id=uid(102))
        db.add(other)
        db.flush()
        _bypass_append_only(db)                         # the composite FK must refuse on its own
        with pytest.raises(IntegrityError) as exc:
            db.execute(text("UPDATE sc_hybrid_proposals SET candidate_id = :other"),
                       {"other": other.id})
            db.flush()
        diag = getattr(exc.value.orig, "diag", None)
        assert diag is not None and "context_pair" in (diag.constraint_name or "")
        db.rollback()


@pytest.mark.parametrize("kind", ["REVOKE", "SUPERSEDE"])
def test_pg_revoke_and_supersede_append_history_and_refuse_double_compensation(world, kind):
    proposal, approval = _recorded_pair(world)
    target = approval.event_id if kind == "REVOKE" else proposal.event_id
    replacement = None if kind == "REVOKE" else approval.event_id
    decided = LATER + timedelta(minutes=10)
    with world() as db:
        command = _command(db)
        journal, _, actor, approver = _journal(db, command)
        first = journal.record_revocation(
            actor, approver, target_event_id=target, revocation_kind=kind,
            reason="Synthetic compensation", decided_at=decided, replacement_event_id=replacement)
        again = journal.record_revocation(
            actor, approver, target_event_id=target, revocation_kind=kind,
            reason="Synthetic compensation", decided_at=decided, replacement_event_id=replacement)
        db.commit()
        assert (first.outcome, first.stream_seq) == ("APPENDED", 3)
        assert again.outcome == "ALREADY_RECORDED" and again.event_id == first.event_id
    with world() as db:
        command = _command(db)
        journal, _, actor, approver = _journal(db, command)
        with pytest.raises(APIError) as exc:                            # a different reason
            journal.record_revocation(
                actor, approver, target_event_id=target, revocation_kind=kind,
                reason="A second, different compensation", decided_at=decided,
                replacement_event_id=replacement)
        assert exc.value.code == "HYBRID_EVENT_ALREADY_REVOKED"
        db.rollback()
        events = db.execute(text(
            "SELECT event_id, previous_event_id, previous_event_hash, envelope_hash "
            "FROM sc_hybrid_events ORDER BY stream_seq")).all()
        assert len(events) == 3 and _count(db, "sc_hybrid_revocations") == 1
        for before, after in zip(events, events[1:], strict=False):      # the chain is intact
            assert (after.previous_event_id, after.previous_event_hash) == (
                before.event_id, before.envelope_hash)
        assert db.scalars(select(LecturerScopusIdentity)).all() == []


def test_pg_submit_stays_inactive_and_writes_no_identity(world):
    with world() as db:
        command = _command(db)
        journal, _, _, _ = _journal(db, command)
        with pytest.raises(APIError) as exc:
            journal.submit(command)
        assert exc.value.code == "SOURCE_CLAIM_WORKFLOW_INACTIVE"
        assert db.scalars(select(LecturerScopusIdentity)).all() == []
        assert db.scalars(select(IdentityEvidence)).all() == []
        assert _count(db, "sc_hybrid_events") == 0


# ===========================================================================
# E3-P3-B2-E targeted security hardening (migration d0b14a77c8e2)
# ===========================================================================

def _bypass_append_only(db: Session) -> None:
    """Owner-level bypass, scoped to this transaction (DDL rolls back with it).

    Used only to prove that the CHECK/FK/UNIQUE constraints still hold on their own, and to
    document the residual risk: an owner or superuser can do exactly this."""
    for table in HYBRID_TABLES:
        db.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER sc_hybrid_forbid_update_delete"))


def _bypass_lifecycle(db: Session, table: str) -> None:
    db.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER sc_hybrid_lifecycle_check"))


def _recorded_history(world):
    """Proposal (1), approval (2) and a REVOKE of the approval (3) committed."""
    with world() as db:
        command = _command(db)
        journal, boundary, actor, approver = _journal(db, command)
        proposal = journal.record_proposal(actor, command, proposed_at=AT)
        draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
        approval = journal.record_exception_approval(
            actor, approver, command, draft, proposed_at=AT, approved_at=LATER)
        revocation = journal.record_revocation(
            approver, actor, target_event_id=approval.event_id, revocation_kind="REVOKE",
            reason="Synthetic compensation", decided_at=LATER + timedelta(minutes=10))
        db.commit()
        return proposal, approval, revocation


def _root(db: Session):
    return db.execute(text(
        "SELECT event_id, envelope_hash, stream_candidate_id, context_id, policy_digest, "
        "actor_user_id, actor_principal_id, snapshot_hash, snapshot_json "
        "FROM sc_hybrid_events WHERE stream_seq = 1 AND envelope_json NOT LIKE 'raw-%'"
    )).mappings().one()


def _raw_context(db: Session, base_context_id, *, candidate_id=None):
    row = dict(db.execute(text("SELECT * FROM sc_hybrid_contexts WHERE id = :id"),
                          {"id": base_context_id}).mappings().one())
    row["id"] = uuid.uuid4()
    row["context_digest"] = db.execute(text(
        "SELECT encode(sha256(convert_to(:v, 'UTF8')), 'hex')"), {"v": str(row["id"])}).scalar_one()
    if candidate_id is not None:
        row["candidate_id"] = candidate_id
    columns = ", ".join(row)
    db.execute(text(f"INSERT INTO sc_hybrid_contexts ({columns}) "
                    f"VALUES ({', '.join(':' + c for c in row)})"), row)
    return row["id"]


def _raw_policy(db: Session) -> str:
    tag = uuid.uuid4().hex
    return db.execute(text(
        "INSERT INTO sc_hybrid_policies (policy_digest, policy_family, policy_id, "
        "policy_revision, encoder_version, policy_json) VALUES "
        "(encode(sha256(convert_to(:j, 'UTF8')), 'hex'), :f, 'raw', 1, 'raw', :j) "
        "RETURNING policy_digest"), {"j": f"raw-policy-{tag}", "f": f"raw-{tag}"}).scalar_one()


def _raw_event(db: Session, *, kind="PROPOSE", stream, seq, context, previous=None,
               policy=None, previous_seq="derive"):
    """Insert one event row directly. ``previous`` is (event_id, envelope_hash, seq)."""
    base = _root(db)
    event_id = uuid.uuid4()
    p_id, p_hash, p_seq = previous or (None, None, None)
    if previous_seq != "derive":
        p_seq = previous_seq
    envelope = f"raw-envelope-{event_id}"
    hashed = db.execute(text(
        "INSERT INTO sc_hybrid_events (event_id, stream_candidate_id, stream_seq, "
        "previous_stream_seq, previous_event_id, previous_event_hash, event_kind, context_id, "
        "policy_digest, actor_type, actor_user_id, actor_principal_id, actor_auth_version, "
        "operation_key, snapshot_hash, snapshot_json, envelope_hash, envelope_json, action_at) "
        "VALUES (:id, :stream, :seq, :pseq, :pid, :phash, :kind, :context, :policy, 'USER', "
        ":user_id, :principal, 1, encode(sha256(convert_to(:key, 'UTF8')), 'hex'), :shash, "
        ":sjson, encode(sha256(convert_to(:env, 'UTF8')), 'hex'), :env, now()) "
        "RETURNING envelope_hash"),
        {"id": event_id, "stream": stream, "seq": seq, "pseq": p_seq, "pid": p_id,
         "phash": p_hash, "kind": kind, "context": context,
         "policy": policy or base["policy_digest"], "user_id": base["actor_user_id"],
         "principal": base["actor_principal_id"], "key": f"raw-key-{event_id}",
         "shash": base["snapshot_hash"], "sjson": base["snapshot_json"],
         "env": envelope}).scalar_one()
    return event_id, hashed, seq


def _raw_proposal(db: Session, event_id, context_id, candidate_id):
    base = dict(db.execute(text("SELECT * FROM sc_hybrid_proposals LIMIT 1")).mappings().one())
    base.update(proposal_id=event_id, context_id=context_id, candidate_id=candidate_id)
    columns = ", ".join(base)
    db.execute(text(f"INSERT INTO sc_hybrid_proposals ({columns}) "
                    f"VALUES ({', '.join(':' + c for c in base)})"), base)


def _raw_approval(db: Session, event_id, proposal_id):
    proposal = db.execute(text(
        "SELECT context_id, branch, reviewer_user_id, reviewer_principal_id "
        "FROM sc_hybrid_proposals WHERE proposal_id = :p"), {"p": proposal_id}).mappings().one()
    db.execute(text(
        "INSERT INTO sc_hybrid_approvals (approval_id, proposal_id, context_id, branch, "
        "reviewer_user_id, reviewer_principal_id, approver_user_id, approver_principal_id, "
        "approver_auth_version, proposal_digest) VALUES (:e, :p, :c, :b, :ru, :rp, :au, :ap, 1, "
        ":d)"), {"e": event_id, "p": proposal_id, "c": proposal["context_id"],
                 "b": proposal["branch"], "ru": proposal["reviewer_user_id"],
                 "rp": proposal["reviewer_principal_id"], "au": uid(751), "ap": uid(901),
                 "d": "a" * 64})


def _raw_revocation(db: Session, event_id, target, kind="REVOKE", replacement=None):
    db.execute(text(
        "INSERT INTO sc_hybrid_revocations (revocation_id, target_event_id, revocation_kind, "
        "replacement_event_id, initiator_user_id, initiator_principal_id, authorizer_user_id, "
        "authorizer_principal_id, reason) VALUES (:e, :t, :k, :r, :iu, :ip, :au, :ap, 'raw')"),
        {"e": event_id, "t": target, "k": kind, "r": replacement, "iu": uid(751),
         "ip": uid(901), "au": uid(750), "ap": uid(900)})


def _refused(db: Session, match: str):
    """Context for one statement that must fail without poisoning the transaction."""
    class _Ctx:
        def __enter__(self):
            self.raises = pytest.raises(DatabaseError, match=match)
            self.nested = db.begin_nested()
            self.raises.__enter__()

        def __exit__(self, *exc):
            handled = self.raises.__exit__(*exc)
            self.nested.rollback()
            return handled
    return _Ctx()


# -- F1: database-level append-only ------------------------------------------

_TOUCH = {"sc_hybrid_events": "recorded_at"}


@pytest.mark.parametrize("table", HYBRID_TABLES)
def test_pg_triggers_refuse_update_delete_and_truncate_even_for_the_owner(world, table):
    _recorded_history(world)
    column = _TOUCH.get(table, "created_at")
    with world() as db:
        assert _count(db, table) >= 1, "every relation has a row to protect"
        for statement in (f"UPDATE {table} SET {column} = {column}", f"DELETE FROM {table}",
                          f"TRUNCATE {table} CASCADE"):
            with _refused(db, "append-only"):
                db.execute(text(statement))
        # ENABLE ALWAYS: even session_replication_role = replica (superuser) does not skip it.
        db.execute(text("SET LOCAL session_replication_role = replica"))
        with _refused(db, "append-only"):
            db.execute(text(f"UPDATE {table} SET {column} = {column}"))
        db.rollback()
        assert _count(db, table) >= 1


def test_pg_non_owner_role_cannot_mutate_history_or_switch_the_guards_off(world):
    """A representative non-superuser, non-owner role holding every table privilege."""
    _recorded_history(world)
    role = f"sc_hybrid_probe_{uuid.uuid4().hex[:12]}"
    with world() as db:
        schema = db.execute(text("SELECT current_schema()")).scalar_one()
        db.execute(text(f"CREATE ROLE {role} NOLOGIN"))
        db.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO {role}'))
        db.execute(text(f'GRANT ALL ON ALL TABLES IN SCHEMA "{schema}" TO {role}'))
        db.commit()
    try:
        with world() as db:
            db.execute(text(f"SET ROLE {role}"))
            assert db.execute(text(
                "SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar_one() is False
            for table in HYBRID_TABLES:
                column = _TOUCH.get(table, "created_at")
                for statement in (f"UPDATE {table} SET {column} = {column}",
                                  f"DELETE FROM {table}", f"TRUNCATE {table} CASCADE"):
                    with _refused(db, "append-only"):
                        db.execute(text(statement))
            # It cannot disable the triggers (not the owner) or skip them via replication mode.
            with _refused(db, "must be owner"):
                db.execute(text(
                    "ALTER TABLE sc_hybrid_events DISABLE TRIGGER sc_hybrid_forbid_update_delete"))
            with _refused(db, "permission denied"):
                db.execute(text("SET session_replication_role = replica"))
            db.rollback()
    finally:
        with world() as db:
            db.execute(text(f"DROP OWNED BY {role}"))
            db.execute(text(f"DROP ROLE {role}"))
            db.commit()
    with world() as db:                       # nothing was removed or changed
        assert (_count(db, "sc_hybrid_events"), _count(db, "sc_hybrid_revocations")) == (3, 1)


def test_pg_owner_can_still_disable_the_guard_and_that_is_the_documented_limit(world):
    """Not a promise of immutability: an owner or superuser may ALTER TABLE ... DISABLE TRIGGER."""
    _recorded_history(world)
    with world() as db:
        _bypass_append_only(db)
        assert db.execute(text("DELETE FROM sc_hybrid_revocations")).rowcount == 1
        db.rollback()                                          # nothing is kept
        assert _count(db, "sc_hybrid_revocations") == 1


def test_pg_trigger_inventory_replaces_the_old_no_enforcement_characterization(world):
    with world() as db:
        schema = db.execute(text("SELECT current_schema()")).scalar_one()
        rows = db.execute(text(
            "SELECT c.relname, t.tgname, t.tgenabled FROM pg_trigger t "
            "JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = :s AND c.relname LIKE 'sc\\_hybrid\\_%' AND NOT t.tgisinternal"),
            {"s": schema}).all()
        rules = db.execute(text(
            "SELECT count(*) FROM pg_rules WHERE schemaname = :s "
            "AND tablename LIKE 'sc\\_hybrid\\_%'"), {"s": schema}).scalar_one()
    live = {(table, name): enabled for table, name, enabled in rows}
    expected = {(t, n): "A" for t in HYBRID_TABLES
                for n in ("sc_hybrid_forbid_update_delete", "sc_hybrid_forbid_truncate")}
    expected.update({(t, "sc_hybrid_lifecycle_check"): "A" for t in (
        "sc_hybrid_proposals", "sc_hybrid_approvals", "sc_hybrid_revocations")})
    assert live == expected and rules == 0       # 'A' = ENABLE ALWAYS


# -- F4/F5: the chain is one line inside one stream ---------------------------

def test_pg_chain_link_pins_predecessor_id_hash_stream_and_position(world):
    _recorded_proposal(world)
    with world() as db:
        root = _root(db)
        stream, context = root["stream_candidate_id"], root["context_id"]
        prev = (root["event_id"], root["envelope_hash"], 1)
        other = LecturerScopusCandidate(lecturer_id=uid(2), scopus_author_id=uid(102))
        db.add(other)
        db.flush()
        other_context = _raw_context(db, context, candidate_id=other.id)
        other_root = _raw_event(db, stream=other.id, seq=1, context=other_context)

        wrong_hash = (root["event_id"], "f" * 64, 1)
        with _refused(db, "fk_sc_hybrid_events_chain_link"):
            _raw_event(db, stream=stream, seq=2, context=context, previous=wrong_hash)
        with _refused(db, "fk_sc_hybrid_events_"):
            _raw_event(db, stream=stream, seq=2, context=context,
                       previous=(uuid.uuid4(), root["envelope_hash"], 1))
        with _refused(db, "ck_sc_hybrid_events_previous_stream_seq"):      # skipped position
            _raw_event(db, stream=stream, seq=3, context=context, previous=prev)
        with _refused(db, "fk_sc_hybrid_events_chain_link"):               # lied position
            _raw_event(db, stream=stream, seq=3, context=context,
                       previous=(root["event_id"], root["envelope_hash"], 2))
        with _refused(db, "fk_sc_hybrid_events_chain_link"):               # graft: stream 1 -> 2
            _raw_event(db, stream=stream, seq=2, context=context, previous=other_root)
        with _refused(db, "fk_sc_hybrid_events_chain_link"):               # graft: stream 2 -> 1
            _raw_event(db, stream=other.id, seq=2, context=other_context, previous=prev)
        _raw_event(db, stream=stream, seq=2, context=context, previous=prev)   # honest link
        assert _count(db, "sc_hybrid_events") == 3
        db.rollback()


# -- F6: an event's context belongs to the event's candidate and policy -------

def test_pg_event_context_must_match_the_event_candidate_and_policy(world):
    _recorded_proposal(world)
    with world() as db:
        root = _root(db)
        stream, context = root["stream_candidate_id"], root["context_id"]
        other = LecturerScopusCandidate(lecturer_id=uid(2), scopus_author_id=uid(102))
        db.add(other)
        db.flush()
        policy = _raw_policy(db)
        with _refused(db, "fk_sc_hybrid_events_context_candidate_policy"):   # other candidate
            _raw_event(db, stream=other.id, seq=1, context=context)
        with _refused(db, "fk_sc_hybrid_events_context_candidate_policy"):   # other policy
            _raw_event(db, stream=stream, seq=2, context=context, policy=policy,
                       previous=(root["event_id"], root["envelope_hash"], 1))
        _raw_event(db, stream=stream, seq=2, context=context,
                   previous=(root["event_id"], root["envelope_hash"], 1))      # consistent
        db.rollback()


# -- F3: no approval of a revoked or superseded proposal ----------------------

def test_pg_service_refuses_approving_a_revoked_proposal(world):
    with world() as db:
        command = _command(db)
        journal, boundary, actor, approver = _journal(db, command)
        proposal = journal.record_proposal(actor, command, proposed_at=AT)
        journal.record_revocation(approver, actor, target_event_id=proposal.event_id,
                                  revocation_kind="REVOKE", reason="Synthetic withdrawal",
                                  decided_at=LATER)
        db.commit()
    with world() as db:
        command = _command(db)
        journal, boundary, actor, approver = _journal(db, command)
        draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
        with pytest.raises(APIError) as exc:
            journal.record_exception_approval(
                actor, approver, command, draft, proposed_at=AT,
                approved_at=LATER + timedelta(minutes=20))
        assert exc.value.code == "HYBRID_PROPOSAL_NOT_EFFECTIVE"
        db.rollback()
        assert (_count(db, "sc_hybrid_events"), _count(db, "sc_hybrid_approvals")) == (2, 0)


def test_pg_database_refuses_approving_a_revoked_proposal_written_directly(world):
    with world() as db:
        command = _command(db)
        journal, _, actor, approver = _journal(db, command)
        proposal = journal.record_proposal(actor, command, proposed_at=AT)
        revoked = journal.record_revocation(
            approver, actor, target_event_id=proposal.event_id, revocation_kind="REVOKE",
            reason="Synthetic withdrawal", decided_at=LATER)
        db.commit()
    with world() as db:
        root = _root(db)
        stream, context = root["stream_candidate_id"], root["context_id"]
        event = _raw_event(db, kind="APPROVE_EXCEPTION", stream=stream, seq=3, context=context,
                           previous=(revoked.event_id, revoked.envelope_hash, 2))
        with _refused(db, "revoked or superseded"):
            _raw_approval(db, event[0], proposal.event_id)
        db.rollback()


# -- F7: exact compensation transitions ---------------------------------------

def test_pg_database_enforces_the_revocation_transition_table(world):
    proposal, approval, revoked = _recorded_history(world)       # P(1) A(2) REVOKE-of-A(3)
    with world() as db:
        root = _root(db)
        stream, context = root["stream_candidate_id"], root["context_id"]
        head = (revoked.event_id, revoked.envelope_hash, 3)
        revoke_4 = _raw_event(db, kind="REVOKE", stream=stream, seq=4, context=context,
                              previous=head)
        with _refused(db, "PROPOSE or APPROVE_EXCEPTION in the same stream"):
            _raw_revocation(db, revoke_4[0], revoked.event_id)               # revoke a REVOKE
        db.rollback()
    with world() as db:
        root = _root(db)
        stream, context = root["stream_candidate_id"], root["context_id"]
        head = (revoked.event_id, revoked.envelope_hash, 3)
        supersede_4 = _raw_event(db, kind="SUPERSEDE", stream=stream, seq=4, context=context,
                                 previous=head)
        with _refused(db, "replacement must be an effective"):
            _raw_revocation(db, supersede_4[0], proposal.event_id, "SUPERSEDE",
                            revoked.event_id)                       # replacement is a REVOKE
        with _refused(db, "replacement must be an effective"):
            _raw_revocation(db, supersede_4[0], proposal.event_id, "SUPERSEDE",
                            approval.event_id)                               # replacement revoked
        with _refused(db, "PROPOSE or APPROVE_EXCEPTION in the same stream"):
            _raw_revocation(db, supersede_4[0], proposal.event_id, "REVOKE")  # kind mismatch
        db.rollback()


# -- F8: one effective proposal per candidate ---------------------------------

def test_pg_service_allows_a_second_proposal_only_after_a_validated_revoke(world):
    with world() as db:
        command = _command(db)
        journal, _, actor, approver = _journal(db, command)
        first = journal.record_proposal(actor, command, proposed_at=AT)
        with pytest.raises(APIError) as exc:
            journal.record_proposal(actor, command, proposed_at=AT + timedelta(minutes=1))
        assert exc.value.code == "HYBRID_ACTIVE_PROPOSAL_EXISTS"
        journal.record_revocation(approver, actor, target_event_id=first.event_id,
                                  revocation_kind="REVOKE", reason="Replace the proposal",
                                  decided_at=LATER)
        second = journal.record_proposal(actor, command, proposed_at=AT + timedelta(minutes=1))
        db.commit()
        assert (second.outcome, second.stream_seq) == ("APPENDED", 3)
    with world() as db:
        assert _count(db, "sc_hybrid_proposals") == 2          # history keeps both


def test_pg_database_refuses_a_second_effective_proposal_written_directly(world):
    first = _recorded_proposal(world)
    with world() as db:
        root = _root(db)
        stream = root["stream_candidate_id"]
        context = _raw_context(db, root["context_id"])
        event = _raw_event(db, stream=stream, seq=2, context=context,
                           previous=(first.event_id, first.envelope_hash, 1))
        with _refused(db, "already has an effective proposal"):
            _raw_proposal(db, event[0], context, stream)
        db.rollback()


@pytest.mark.parametrize("run", range(3))
def test_pg_concurrent_distinct_proposals_leave_exactly_one_effective(world, run):
    outcomes, errors, barrier = [], [], threading.Barrier(2)

    def worker(minutes):
        try:
            with world() as db:
                command = _command(db)
                journal, _, actor, _ = _journal(db, command)
                barrier.wait(timeout=20)
                outcomes.append(journal.record_proposal(
                    actor, command, proposed_at=AT + timedelta(minutes=minutes)).outcome)
                db.commit()
        except Exception as exc:                      # classified by the assertions below
            errors.append(getattr(exc, "code", type(exc).__name__))

    threads = [threading.Thread(target=worker, args=(m,)) for m in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert outcomes == ["APPENDED"] and errors == ["HYBRID_ACTIVE_PROPOSAL_EXISTS"], (
        outcomes, errors)
    with world() as db:
        assert (_count(db, "sc_hybrid_events"), _count(db, "sc_hybrid_proposals")) == (1, 1)


# -- one lock for the service and the database triggers -----------------------

def test_pg_service_and_triggers_share_one_per_candidate_advisory_lock(world):
    from app.services import source_claim_hybrid_persistence as service

    assert service._LOCK_KEY == _hardening_module().LOCK_NAMESPACE
    first = world()
    command = _command(first)
    journal, _, actor, _ = _journal(first, command)
    journal.record_proposal(actor, command, proposed_at=AT)         # holds the stream lock
    candidate = first.execute(text("SELECT stream_candidate_id FROM sc_hybrid_events")
                              ).scalar_one()
    done, errors = [], []

    def trigger_side():
        try:
            with world() as db:
                db.execute(text("SELECT sc_hybrid_lock_stream(:c)"), {"c": candidate})
                done.append(True)
                db.rollback()
        except Exception as exc:
            errors.append(type(exc).__name__)

    with world() as probe:
        free = probe.execute(text(
            "SELECT pg_try_advisory_xact_lock(:ns, hashtext(CAST(:c AS text)))"),
            {"ns": service._LOCK_KEY, "c": str(candidate)}).scalar_one()
        assert free is False                      # the service's key is the database's key
        probe.rollback()
    thread = threading.Thread(target=trigger_side)
    thread.start()
    waiting = 0
    with world() as probe:
        for _ in range(100):
            waiting = probe.execute(text(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted"
            )).scalar_one()
            if waiting:
                break
            threading.Event().wait(0.1)
    assert waiting == 1 and done == [] and errors == []
    first.commit()
    first.close()
    thread.join(timeout=30)
    assert done == [True] and errors == []


def test_pg_lifecycle_rules_refuse_a_snapshot_isolation_level(world):
    _recorded_proposal(world)
    with world() as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        candidate = db.execute(text("SELECT stream_candidate_id FROM sc_hybrid_events")
                               ).scalar_one()
        with _refused(db, "require READ COMMITTED"):
            db.execute(text("SELECT sc_hybrid_lock_stream(:c)"), {"c": candidate})
        db.rollback()


# -- F2: the idempotency re-check exists in all three write paths -------------

def _race(world, action):
    outcomes, errors, barrier = [], [], threading.Barrier(2)

    def worker():
        try:
            with world() as db:
                barrier.wait(timeout=20)
                outcomes.append(action(db))
                db.commit()
        except Exception as exc:
            errors.append(getattr(exc, "code", type(exc).__name__))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    return sorted(outcomes), errors


@pytest.mark.parametrize("run", range(2))
def test_pg_concurrent_identical_approvals_give_one_append_and_one_replay(world, run):
    _recorded_proposal(world)

    def approve_once(db):
        command = _command(db)
        journal, boundary, actor, approver = _journal(db, command)
        draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
        return journal.record_exception_approval(
            actor, approver, command, draft, proposed_at=AT, approved_at=LATER).outcome

    assert _race(world, approve_once) == (["ALREADY_RECORDED", "APPENDED"], [])
    with world() as db:
        assert (_count(db, "sc_hybrid_events"), _count(db, "sc_hybrid_approvals")) == (2, 1)


@pytest.mark.parametrize("run", range(2))
def test_pg_concurrent_identical_revocations_give_one_append_and_one_replay(world, run):
    _, approval = _recorded_pair(world)

    def revoke_once(db):
        command = _command(db)
        journal, _, actor, approver = _journal(db, command)
        return journal.record_revocation(
            approver, actor, target_event_id=approval.event_id, revocation_kind="REVOKE",
            reason="Synthetic compensation", decided_at=LATER + timedelta(minutes=10)).outcome

    assert _race(world, revoke_once) == (["ALREADY_RECORDED", "APPENDED"], [])
    with world() as db:
        assert (_count(db, "sc_hybrid_events"), _count(db, "sc_hybrid_revocations")) == (3, 1)


# -- the migration on a database that already holds history -------------------

def test_pg_hardening_upgrade_backfills_and_revalidates_existing_history(world):
    _recorded_history(world)
    with world() as db:
        ctx = MigrationContext.configure(db.connection(), opts={"target_metadata": Base.metadata})
        with Operations.context(ctx):
            _hardening_module().downgrade()               # the schema as c99a03e55ff3 left it
        assert db.execute(text(
            "SELECT count(*) FROM information_schema.columns WHERE table_name = 'sc_hybrid_events'"
            " AND column_name = 'previous_stream_seq' AND table_schema = current_schema()"
        )).scalar_one() == 0
        with Operations.context(ctx):
            _hardening_module().upgrade()                 # backfill, then validate, then guard
        seqs = db.execute(text("SELECT stream_seq, previous_stream_seq FROM sc_hybrid_events "
                               "ORDER BY stream_seq")).all()
        assert seqs == [(1, None), (2, 1), (3, 2)]
        with _refused(db, "append-only"):
            db.execute(text("DELETE FROM sc_hybrid_revocations"))
        db.rollback()


# -- the service under a least-privilege application role ---------------------

def test_pg_service_runs_as_a_non_owner_role_that_cannot_rewrite_history(world):
    """Append works with plain table DML grants; rewriting the same history does not.

    Representative role only: real application roles are provisioned outside this repository.
    """
    role = f"sc_hybrid_app_{uuid.uuid4().hex[:12]}"
    with world() as db:
        schema = db.execute(text("SELECT current_schema()")).scalar_one()
        db.execute(text(f"CREATE ROLE {role} NOLOGIN"))
        db.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO {role}'))
        db.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA '
                        f'"{schema}" TO {role}'))
        db.commit()
    try:
        with world() as db:
            db.execute(text(f"SET LOCAL ROLE {role}"))
            command = _command(db)
            journal, boundary, actor, approver = _journal(db, command)
            proposal = journal.record_proposal(actor, command, proposed_at=AT)
            draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
            approval = journal.record_exception_approval(
                actor, approver, command, draft, proposed_at=AT, approved_at=LATER)
            revoked = journal.record_revocation(
                approver, actor, target_event_id=approval.event_id, revocation_kind="REVOKE",
                reason="Synthetic compensation", decided_at=LATER + timedelta(minutes=10))
            assert [proposal.stream_seq, approval.stream_seq, revoked.stream_seq] == [1, 2, 3]
            assert db.execute(text("SELECT current_user")).scalar_one() == role
            assert db.execute(text(
                "SELECT rolsuper OR EXISTS (SELECT 1 FROM pg_class c WHERE c.relname = "
                "'sc_hybrid_events' AND c.relowner = r.oid) FROM pg_roles r "
                "WHERE r.rolname = current_user")).scalar_one() is False
            for statement in ("UPDATE sc_hybrid_events SET recorded_at = recorded_at",
                              "DELETE FROM sc_hybrid_revocations"):
                with _refused(db, "append-only"):
                    db.execute(text(statement))
            db.commit()
    finally:
        with world() as db:
            db.execute(text(f"DROP OWNED BY {role}"))
            db.execute(text(f"DROP ROLE {role}"))
            db.commit()
    with world() as db:
        assert (_count(db, "sc_hybrid_events"), _count(db, "sc_hybrid_revocations")) == (3, 1)
