"""P3-B1 on SQLAlchemy + isolated SQLite memory; no application DB or migrations."""

from __future__ import annotations

import copy
import importlib.util
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import CheckConstraint, Column, Integer, MetaData, String, Table, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
)
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.models.source_staging import SourceAnalysis, SourceRecord, SourceRuleSet
from app.services.candidate_review_queries import (
    current_reviewable_candidates_subquery,
    current_reviewable_observation,
)
from app.services.candidate_review_service import (
    CANDIDATE_TO_IDENTITY_EVIDENCE_TYPE,
    ObservationNotFoundError,
)
from app.services.matching.candidate_generator import generate_candidates
from app.services.matching.candidate_persistence import GenerationRunConflict
from app.services.matching.source_claim_candidate_persistence import SourceClaimCandidateWriter
from app.services.review_reason_policy import accept_reason_policy
from app.services.source_claim_matching import bridge
from app.services.source_claims import adapters, parser
from app.services.source_staging.service import Actor, SourceStagingService
from tests.source_staging_fixtures import (
    ORCID_A,
    REPO,
    harvest,
    lecturer,
    make_sqlite_engine,
    multi_row,
    multi_snapshot,
    sid,
)


def uid(n):
    return uuid.UUID(int=n)


@pytest.fixture
def world():
    engine = make_sqlite_engine()
    with Session(engine, autoflush=False) as db:
        staging = SourceStagingService(db, Actor(service="synthetic-p3b1"))
        staging.activate_rule_set()
        for n in range(1, 4):
            db.add(Lecturer(
                id=uid(n), full_name=f"Unrelated lecturer name {n}",
                full_name_normalized=f"unrelated lecturer name {n}",
                email=f"gv{n}@example.invalid", version=1,
                repository_profile_url=f"{REPO}/giang-vien/synthetic-{n}/",
            ))
            db.add(ScopusAuthor(id=uid(100 + n), scopus_id=sid(n),
                                preferred_name=f"Completely different author {n}"))
        db.commit()
        yield db, staging, SourceClaimCandidateWriter(db)
    engine.dispose()


def guide(world, rows=None, *, ts="2026-10-29T00:00:00Z", completeness="COMPLETE"):
    _, staging, _ = world
    return staging.ingest_guide_snapshot(
        **multi_snapshot(rows if rows is not None else [multi_row(1, [sid(1)])], ts=ts),
        completeness=completeness,
    )


def write(world, run=500):
    return world[2].persist_generation(uid(run))


def evidence(world):
    return world[0].scalars(select(LecturerScopusCandidateEvidence)).all()


def projection(world):
    return world[2].current_evidence()


def weight(world):
    return sum(e["payload"]["current_weight"] for e in projection(world))


def test_source_only_candidate_is_pending_and_inactive_for_reviewers(world):
    db, _, _ = world
    assert generate_candidates(
        db.scalars(select(Lecturer)).all(), db.scalars(select(ScopusAuthor)).all(), [],
    ) == ()
    guide(world)
    result = write(world)
    root = db.scalar(select(LecturerScopusCandidate))
    assert result.status == "STAGED" and result.evidence == 1
    assert root.status == "PENDING"
    ev, = evidence(world)
    assert ev.evidence_kind == "SOURCE_CLAIM"
    assert ev.payload["source_tier"] == "INSTITUTION_DECLARED"
    assert ev.source_refs[0]["claim_id"] and ev.source_refs[0]["artifact_id"]
    assert ev.source_refs[0]["record_raw"]
    assert weight(world) == 1
    with pytest.raises(ObservationNotFoundError):
        current_reviewable_observation(db, root.id)
    assert db.execute(select(current_reviewable_candidates_subquery("PENDING"))).all() == []
    assert "SOURCE_CLAIM" not in CANDIDATE_TO_IDENTITY_EVIDENCE_TYPE
    assert "NAME_EVIDENCE_ONLY" in accept_reason_policy(
        db, lecturer_id=root.lecturer_id, scopus_author_id=root.scopus_author_id,
        evidence_kinds=[ev.evidence_kind],
    ).triggers


def test_duplicate_run_replay_checks_everything_and_writes_nothing(world):
    db, _, _ = world
    guide(world)
    first = write(world)
    db.commit()
    ids = [e.id for e in evidence(world)]
    again = write(world)
    assert not first.idempotent_replay and again.idempotent_replay
    assert [e.id for e in evidence(world)] == ids
    assert len(db.scalars(select(CandidateGenerationRun)).all()) == 1


def test_repeated_captures_keep_provenance_without_weight_inflation(world):
    guide(world)
    write(world)
    guide(world, ts="2026-10-30T00:00:00Z")
    assert projection(world) == ()  # Old persisted run is stale, not CURRENT.
    write(world, 501)
    assert len(evidence(world)) == 2
    assert len({e.evidence_fingerprint for e in evidence(world)}) == 1
    ev, = projection(world)
    assert len(ev["source_refs"]) == 2 and weight(world) == 1
    write(world, 502)
    assert len(projection(world)) == 1 and weight(world) == 1


def test_contract_variation_preserves_logical_fingerprint(world):
    guide(world)
    write(world)
    _, staging, _ = world
    snapshot = multi_snapshot([multi_row(1, [sid(1)])], ts="2026-10-29T00:00:00Z")
    artifact = adapters.guide_multi_id_artifact(
        json.loads(snapshot["snapshot_bytes"]), snapshot_sha256=snapshot["snapshot_sha256"],
        completeness="COMPLETE",
    )
    artifact["contract_version"] = "1.1"
    staging._ingest(adapters.artifact_bytes(artifact), None)
    write(world, 501)
    assert len({e.evidence_fingerprint for e in evidence(world)}) == 1
    assert weight(world) == 1
    assert projection(world)[0]["source_refs"][0]["contract_version"] == "1.1"


def test_rule_reanalysis_uses_active_analysis_and_not_stored_inactive_rows(world, monkeypatch):
    db, staging, _ = world
    guide(world)
    write(world)
    old_ids = {a.id for a in db.scalars(select(SourceAnalysis))}
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "1.1")
    monkeypatch.setattr(bridge, "BRIDGE_RULE_VERSION", "test-bridge-2")
    staging.activate_rule_set()
    assert projection(world) == ()
    write(world, 501)
    assert len({e.evidence_fingerprint for e in evidence(world)}) == 1
    assert weight(world) == 1
    active_ref = projection(world)[0]["source_refs"][0]
    assert active_ref["analysis_id"] not in {str(i) for i in old_ids}
    assert active_ref["identity_rules_version"] == "1.1"


def test_withdrawal_zeroes_current_weight_but_retains_history(world):
    guide(world)
    write(world)
    old_id = evidence(world)[0].id
    guide(world, rows=[], ts="2026-10-30T00:00:00Z")
    assert weight(world) == 0
    write(world, 501)
    ev, = projection(world)
    assert ev["payload"]["current_state"] == "WITHDRAWN"
    assert weight(world) == 0 and len(evidence(world)) == 2
    assert world[0].get(LecturerScopusCandidateEvidence, old_id).payload["current_weight"] == 1
    # The old row is history; summing historical payload weights is forbidden.


@pytest.mark.parametrize(("time", "completeness", "state"), [
    ("2026-10-30T00:00:00Z", "PARTIAL", "NOT_OBSERVED"),
    ("2026-10-29T00:00:00Z", "COMPLETE", "AMBIGUOUS"),
    ("2026-10-29T07:00:00+07:00", "COMPLETE", "AMBIGUOUS"),
])
def test_partial_and_equal_instant_absence_never_withdraw(world, time, completeness, state):
    guide(world)
    write(world)
    guide(world, rows=[], ts=time, completeness=completeness)
    write(world, 501)
    assert projection(world)[0]["payload"]["current_state"] == state
    assert weight(world) == 0


def test_same_time_flag_conflicts_are_not_scoring_facts(world):
    guide(world, [multi_row(1, [sid(1), sid(2)])], ts="2026-10-28T00:00:00Z")
    write(world)
    guide(world, [multi_row(1, [sid(1), sid(2)], primary=sid(1))])
    guide(world, [multi_row(1, [sid(1), sid(2)], primary=sid(2))])
    write(world, 501)
    assert len(projection(world)) == 2
    assert weight(world) == 0
    assert all(e["payload"]["is_primary_claimed"] is None for e in projection(world))


def test_multi_ids_and_competing_ownership_stay_separate(world):
    guide(world, [multi_row(1, [sid(1), sid(2)]), multi_row(2, [sid(1)])])
    write(world)
    assert len(evidence(world)) == 3
    assert len(world[0].scalars(select(LecturerScopusCandidate)).all()) == 3
    state = world[0].get(CandidateGenerationRun, uid(500)).source_state
    pairs = state["bridge"]["pairs"]
    assert sum("SCOPUS_ID_DECLARED_FOR_SEVERAL_LECTURERS" in p["reasons"] for p in pairs) == 2


def test_duplicate_orcid_claims_remain_visible_without_orcid_exact_evidence(world):
    _, staging, _ = world
    guide(world, [multi_row(1, [sid(1)]), multi_row(2, [sid(2)])])
    staging.ingest_harvest(**harvest([lecturer(1, orcid=ORCID_A), lecturer(2, orcid=ORCID_A)]))
    write(world)
    state = world[0].get(CandidateGenerationRun, uid(500)).source_state
    orcids = [o for o in state["source_observations"] if o["claim_type"] == "ORCID_DECLARED"]
    assert len(orcids) == 2 and orcids[0]["record_id"] != orcids[1]["record_id"]
    assert any(f["code"] == "ORCID_DECLARED_BY_MULTIPLE_RECORDS"
               for f in state["bridge"]["findings"])
    assert {e.evidence_kind for e in evidence(world)} == {"SOURCE_CLAIM"}


@pytest.mark.parametrize("status", ["REJECTED", "SUPERSEDED", "ACCEPTED"])
def test_existing_candidate_reviewer_state_is_never_reopened(world, status):
    db, _, _ = world
    root = LecturerScopusCandidate(id=uid(700), lecturer_id=uid(1), scopus_author_id=uid(101),
                                   status=status, version=8)
    db.add(root)
    db.flush()
    before = (root.status, root.version, root.first_seen_at, root.last_seen_at)
    guide(world)
    write(world)
    db.refresh(root)
    assert (root.status, root.version, root.first_seen_at, root.last_seen_at) == before
    assert len(evidence(world)) == 1


@pytest.mark.parametrize("status", ["REVOKED", "REJECTED"])
def test_negative_identity_is_untouched_and_does_not_spawn_a_new_pending_pair(world, status):
    db, _, _ = world
    row = LecturerScopusIdentity(id=uid(800), lecturer_id=uid(1), scopus_author_id=uid(101),
                                status=status, version=4)
    db.add(row)
    db.flush()
    before = row.status, row.version
    guide(world)
    result = write(world)
    db.refresh(row)
    assert (row.status, row.version) == before
    assert result.candidates == 0
    assert db.scalars(select(LecturerScopusCandidate)).all() == []
    assert len(db.get(CandidateGenerationRun, uid(500)).source_state["bridge"]["evidence"]) == 1


@pytest.mark.parametrize("field", [
    "evidence_kind", "rule_id", "rule_version", "payload", "source_refs", "evidence_fingerprint",
])
def test_replay_rejects_tampered_evidence_not_just_fingerprint(world, field):
    guide(world)
    write(world)
    row = evidence(world)[0]
    value = getattr(row, field)
    setattr(row, field, {"tampered": True} if field == "payload" else
            [{"capture_id": str(uid(99))}] if field == "source_refs" else
            "NAME" if field == "evidence_kind" else "tampered")
    world[0].flush()
    with pytest.raises(GenerationRunConflict):
        write(world)
    assert getattr(row, field) != value


@pytest.mark.parametrize("field", ["candidate_snapshot", "observation_hash", "observed_at"])
def test_replay_rejects_tampered_observation(world, field):
    guide(world)
    write(world)
    row = world[0].scalar(select(LecturerScopusCandidateObservation))
    setattr(row, field, {"bad": True} if field == "candidate_snapshot" else
            datetime(2000, 1, 1, tzinfo=UTC) if field == "observed_at" else "a" * 64)
    world[0].flush()
    with pytest.raises(GenerationRunConflict):
        write(world)


def test_failure_is_atomic_retains_callers_writes_and_retry_works(world):
    db, _, _ = world
    guide(world)
    # A valid earlier pending caller write is flushed before our savepoint.
    caller = ScopusAuthor(id=uid(999), scopus_id=sid(999), preferred_name="caller-owned")
    db.add(caller)

    def fail_on_evidence(mapper, connection, target):
        raise IntegrityError("synthetic", {}, RuntimeError("unexpected CHECK"))

    event.listen(LecturerScopusCandidateEvidence, "before_insert", fail_on_evidence)
    try:
        with pytest.raises(IntegrityError):
            write(world)
    finally:
        event.remove(LecturerScopusCandidateEvidence, "before_insert", fail_on_evidence)
    assert db.in_transaction() and db.get(ScopusAuthor, caller.id) is caller
    assert db.scalars(select(CandidateGenerationRun)).all() == []
    assert db.scalars(select(LecturerScopusCandidateObservation)).all() == []
    assert db.scalars(select(LecturerScopusCandidate)).all() == []
    assert evidence(world) == []
    assert write(world).evidence == 1
    db.rollback()  # Owner can roll back both its work and our successful retry.
    assert db.get(ScopusAuthor, uid(999)) is None
    assert db.get(CandidateGenerationRun, uid(500)) is None


def test_pending_invalid_caller_state_fails_before_our_savepoint(world):
    db, _, _ = world
    guide(world)
    db.add(ScopusAuthor(id=uid(999), scopus_id=None, preferred_name="invalid"))
    with pytest.raises(IntegrityError):
        write(world)
    assert not db.is_active  # Caller must recover its own invalid transaction.
    db.rollback()


def test_json_payloads_are_detached_from_prepared_aliases(world, monkeypatch):
    guide(world)
    writer = world[2]
    original = writer._prepare
    captured = []

    def remember():
        prepared = original()
        captured.append(prepared)
        return prepared

    monkeypatch.setattr(writer, "_prepare", remember)
    write(world)
    state, items = captured[0]
    before = copy.deepcopy(evidence(world)[0].payload)
    state["bridge"]["findings"].append({"bad": True})
    items[0]["evidence"][0]["payload"]["current_weight"] = 999
    items[0]["evidence"][0]["source_refs"][0]["claim_id"] = "bad"
    assert evidence(world)[0].payload == before
    assert evidence(world)[0].source_refs[0]["claim_id"] != "bad"


def test_missing_active_analysis_fails_closed(world):
    db, _, _ = world
    guide(world)
    db.add(SourceRuleSet(id=uid(777), identity_rules_version="missing",
                         normalization_version="missing"))
    db.flush()
    with pytest.raises(GenerationRunConflict, match="active analysis"):
        write(world)


def test_catalog_miss_stays_a_finding_without_inventing_an_author(world):
    guide(world, [multi_row(1, [sid(99)])])
    result = write(world)
    assert result.candidates == 0 and evidence(world) == []
    findings = world[0].get(CandidateGenerationRun, uid(500)).source_state["bridge"]["findings"]
    assert any(f["code"] == "SCOPUS_AUTHOR_NOT_IN_CATALOG" for f in findings)
    assert world[0].scalar(select(ScopusAuthor).where(ScopusAuthor.scopus_id == sid(99))) is None


def test_initial_ambiguous_flags_do_not_create_pending_pairs(world):
    guide(world, [multi_row(1, [sid(1), sid(2)], primary=sid(1))])
    guide(world, [multi_row(1, [sid(1), sid(2)], primary=sid(2))])
    assert write(world).candidates == 0
    assert projection(world) == ()
    state = world[0].get(CandidateGenerationRun, uid(500)).source_state
    assert len(state["bridge"]["evidence"]) == 2
    assert any(f["code"] == "CAPTURE_ORDER_AMBIGUOUS" for f in state["bridge"]["findings"])


@pytest.mark.parametrize("target", ["run_source_refs", "run_input_hash", "missing_evidence"])
def test_replay_rejects_tampered_run_provenance_and_missing_descriptors(world, target):
    db, _, _ = world
    guide(world)
    write(world)
    run = db.get(CandidateGenerationRun, uid(500))
    if target == "missing_evidence":
        db.delete(evidence(world)[0])
    else:
        state = copy.deepcopy(run.source_state)
        if target == "run_source_refs":
            state["source_observations"][0]["artifact_id"] = str(uid(999))
        else:
            state["input_hash"] = "a" * 64
        run.source_state = state
    db.flush()
    with pytest.raises(GenerationRunConflict):
        write(world)


def test_prior_successful_generation_and_caller_write_survive_later_failure(world):
    db, _, _ = world
    guide(world)
    write(world)
    first_evidence = evidence(world)[0].id
    caller = ScopusAuthor(id=uid(999), scopus_id=sid(999), preferred_name="earlier caller write")
    db.add(caller)

    def fail(mapper, connection, target):
        raise RuntimeError("synthetic late failure")

    event.listen(LecturerScopusCandidateEvidence, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="late failure"):
            write(world, 501)
    finally:
        event.remove(LecturerScopusCandidateEvidence, "before_insert", fail)
    assert db.get(CandidateGenerationRun, uid(500)).status == "STAGED"
    assert db.get(CandidateGenerationRun, uid(501)) is None
    assert db.get(ScopusAuthor, uid(999)) is caller
    assert [e.id for e in evidence(world)] == [first_evidence]
    assert write(world, 501).evidence == 1


def test_invalid_record_does_not_gain_weight(world):
    db, _, _ = world
    guide(world)
    record = db.scalar(select(SourceRecord))
    record.validation_status = "INVALID"  # Synthetic representation of a retained invalid row.
    db.flush()
    assert write(world).candidates == 0
    assert weight(world) == 0


def test_existing_completed_name_observation_is_not_replaced_by_staged_source(world):
    db, _, _ = world
    guide(world)
    write(world)
    root = db.scalar(select(LecturerScopusCandidate))
    now = datetime.now(UTC)
    run = CandidateGenerationRun(
        id=uid(600), rule_set_id="existing-name-run", rule_set_version="1",
        source_state={}, status="COMPLETED", started_at=now, completed_at=now,
    )
    db.add(run)
    db.flush()
    obs = LecturerScopusCandidateObservation(
        id=uid(601), candidate_id=root.id, generation_run_id=run.id, observed_at=now,
        candidate_snapshot={}, observation_hash="a" * 64,
    )
    db.add(obs)
    db.flush()
    write(world, 501)
    assert current_reviewable_observation(db, root.id).id == obs.id


def test_model_checks_and_migration_source_agree_without_executing_migrations(world):
    path = (Path(__file__).parents[2]
            / "alembic/versions/b88f02d44ff2_source_claim_candidate_evidence.py")
    spec = importlib.util.spec_from_file_location("p3b1_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    creates = []
    module.op = SimpleNamespace(
        f=lambda s: s, drop_constraint=lambda *a, **k: None,
        create_check_constraint=lambda name, table, expr: creates.append((name, table, expr)),
    )
    module.upgrade()  # Recording fake operations only; no SQL/Alembic environment.
    assert (module.revision, module.down_revision) == ("b88f02d44ff2", "a77e01c33ee1")
    for name, table_name, expression in creates:
        model = (CandidateGenerationRun if table_name == "candidate_generation_runs"
                 else LecturerScopusCandidateEvidence)
        target = next(c for c in model.__table__.constraints
                      if isinstance(c, CheckConstraint) and c.name == name)
        # Order of IN literals is semantically irrelevant.
        assert set(expression.replace("(", " ").replace(")", " ").split()) == set(
            str(target.sqltext).replace("(", " ").replace(")", " ").split())
    # Execute the evidence vocabulary CHECK on a real SQLite table. Other PG
    # CHECKs, JSONB semantics and locks are not reproduced by the shared mirror.
    metadata = MetaData()
    table = Table("p3b1_evidence_contract", metadata,
                  Column("id", Integer, primary_key=True), Column("evidence_kind", String),
                  CheckConstraint("evidence_kind IN ('NAME', 'PUBLICATION', 'SOURCE_CLAIM')"))
    metadata.create_all(world[0].get_bind())
    with world[0].get_bind().begin() as conn:
        conn.execute(table.insert().values(evidence_kind="SOURCE_CLAIM"))
        with pytest.raises(IntegrityError):
            conn.execute(table.insert().values(evidence_kind="ORCID_EXACT"))
