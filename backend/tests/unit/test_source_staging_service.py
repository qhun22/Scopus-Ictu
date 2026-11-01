"""Gate E.3 / P2-B2 — staging persistence service on an in-memory SQLite mirror.

The service runs unmodified against SQLite copies of *all* application tables (PostgreSQL types
mapped to generic ones; unique constraints and staging-internal FKs kept; PostgreSQL CHECKs,
partial indexes and advisory locks not reproduced) plus the two staging views created from the
model SQL. Synthetic data only. No application or PostgreSQL database is touched.
"""

from __future__ import annotations

import copy
import json
import uuid

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.models import Base
from app.models import source_staging as staging
from app.models.governance import AuditEvent
from app.services.source_claims import adapters, parser
from app.services.source_claims.analysis import PresenceStatus as P
from app.services.source_staging import service as service_module
from app.services.source_staging.service import (
    Actor,
    SourceStagingService,
    StagingError,
    ingest_outcome,
)
from tests.source_staging_fixtures import (
    ORCID_A,
    STAGING,
    harvest,
    lecturer,
    make_sqlite_engine,
    multi_row,
    multi_snapshot,
    sid,
    tables_snapshot,
)
from tests.source_staging_fixtures import encode as _encode

SYSTEM = Actor(service="e3-p2b2-tests")


@pytest.fixture
def engine():
    eng = make_sqlite_engine()
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    with Session(engine, autoflush=False) as session:
        yield session


def svc(session, actor=SYSTEM):
    return SourceStagingService(session, actor)


def count(session, table: str) -> int:
    return session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def counts(session) -> dict[str, int]:
    return {t: count(session, t) for t in staging.STAGING_TABLES}


def observations(session):
    return session.execute(text(
        "SELECT capture_id, claim_id, claim_type, value_normalized, subject_key, "
        "identity_rules_version FROM source_claim_observations")).all()


def assert_no_duplicate_observations(session):
    rows = session.execute(text(
        "SELECT capture_id, claim_id FROM source_claim_observations")).all()
    assert len(rows) == len(set(rows))


@pytest.fixture
def active(db):
    service = svc(db)
    assert service.activate_rule_set(reason="bootstrap").outcome == "ACTIVATED"
    return service


# ---------------------------------------------------------------------------
# 1-4: first import, identical replay, reordering, new capture
# ---------------------------------------------------------------------------

def test_first_import_creates_every_layer_and_is_observable(db, active):
    result = active.ingest_harvest(**harvest([lecturer(1, orcid=ORCID_A), lecturer(2)]))
    assert result.outcome == "CREATED"
    assert dict(result.layers) == {"content": True, "capture": True, "artifact": True,
                                   "analysis": True}
    assert (result.record_count, result.claim_count, result.completeness) == (2, 3, "COMPLETE")
    assert counts(db) == {"source_rule_sets": 1, "source_contents": 1, "source_captures": 1,
                          "source_artifacts": 1, "source_analyses": 1, "source_records": 2,
                          "source_claims": 3}
    assert len(observations(db)) == 3
    actions = db.execute(select(AuditEvent.action, AuditEvent.actor_service)).all()
    assert sorted(actions) == [("SOURCE_ARTIFACT_INGESTED", "e3-p2b2-tests"),
                               ("SOURCE_RULE_SET_ACTIVATED", "e3-p2b2-tests")]


def test_identical_replay_writes_nothing_but_an_audit_event(db, active):
    files = harvest([lecturer(1), lecturer(2)])
    active.ingest_harvest(**files)
    before = counts(db)
    again = active.ingest_harvest(**files)
    assert again.outcome == "ALREADY_INGESTED" and not any(dict(again.layers).values())
    assert counts(db) == before
    assert count(db, "audit_events") == 3


def test_reordered_json_keys_are_the_same_content_seen_in_a_new_capture(db, active):
    items = [lecturer(1, orcid=ORCID_A), lecturer(2)]
    first = active.ingest_harvest(**harvest(items))
    reordered = active.ingest_harvest(**harvest(
        items, encoder=lambda v: _encode(json.loads(json.dumps(v),
                                                   object_pairs_hook=lambda p: dict(reversed(p))))))
    assert reordered.outcome == "REUSED"          # new upstream bytes => new capture only
    assert reordered.content_id == first.content_id and reordered.capture_id != first.capture_id
    assert count(db, "source_analyses") == 1
    assert len(observations(db)) == 2 * first.claim_count
    assert_no_duplicate_observations(db)


def test_reordered_rows_are_new_content_with_identical_record_hashes(db, active):
    first = active.ingest_harvest(**harvest([lecturer(1), lecturer(2)]))
    second = active.ingest_harvest(**harvest([lecturer(2), lecturer(1)]))
    assert second.outcome == "CREATED" and second.content_id != first.content_id
    hashes = db.execute(text("SELECT analysis_id, record_hash FROM source_records")).all()
    by_analysis = {}
    for analysis_id, record_hash in hashes:
        by_analysis.setdefault(analysis_id, set()).add(record_hash)
    assert len(by_analysis) == 2 and len({frozenset(v) for v in by_analysis.values()}) == 1


def test_same_content_new_capture_is_reused(db, active):
    first = active.ingest_harvest(**harvest([lecturer(1)]))
    later = active.ingest_harvest(**harvest([lecturer(1)], completed="2026-11-03T09:00:00Z"))
    assert later.outcome == "REUSED"
    assert (later.content_id, later.analysis_id) == (first.content_id, first.analysis_id)
    assert counts(db)["source_captures"] == 2 and counts(db)["source_analyses"] == 1
    assert {row[0] for row in observations(db)} == {first.capture_id.hex, later.capture_id.hex}


# ---------------------------------------------------------------------------
# 5, 12: rule versions and activation
# ---------------------------------------------------------------------------

def test_ingest_requires_an_active_rule_set_matching_the_code(db, monkeypatch):
    with pytest.raises(StagingError) as raised:
        svc(db).ingest_harvest(**harvest([lecturer(1)]))
    assert raised.value.code == "NO_ACTIVE_RULE_SET"
    svc(db).activate_rule_set()
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    with pytest.raises(StagingError) as raised:
        svc(db).ingest_harvest(**harvest([lecturer(1)]))
    assert raised.value.code == "RULE_SET_MISMATCH"
    assert counts(db)["source_contents"] == 0


def test_new_rule_version_reanalyses_existing_artifacts_before_activation(db, active,
                                                                         monkeypatch):
    files = harvest([lecturer(1, orcid=ORCID_A), lecturer(2, orcid=ORCID_A)])
    first = active.ingest_harvest(**files)
    artifacts_before = db.execute(text("SELECT * FROM source_artifacts")).all()
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    activation = svc(db).activate_rule_set(reason="rules v2")
    assert (activation.outcome, activation.analyses_created) == ("ACTIVATED", 1)
    assert (activation.artifacts_covered, activation.captures_covered) == (1, 1)
    assert db.execute(text("SELECT * FROM source_artifacts")).all() == artifacts_before
    assert {row[5] for row in observations(db)} == {"2"}
    assert len(observations(db)) == first.claim_count
    history = db.execute(text("SELECT identity_rules_version, is_active_rule_set, selection_rank "
                              "FROM source_capture_analyses ORDER BY selection_rank")).all()
    assert [tuple(r) for r in history] == [("2", 1, 1), ("1", 0, 2)]
    assert count(db, "source_claims") == 2 * first.claim_count       # old analysis kept
    assert svc(db).ingest_harvest(**files).outcome == "ALREADY_INGESTED"
    assert svc(db).activate_rule_set().outcome == "ALREADY_ACTIVE"


def test_activation_fails_closed_on_an_artifact_that_cannot_be_reanalysed(db, active,
                                                                         monkeypatch):
    active.ingest_harvest(**harvest([lecturer(1)]))
    # Tampering a value (PostgreSQL's content-hash CHECK would already refuse this UPDATE).
    db.execute(text("UPDATE source_contents SET content_json = "
                    "REPLACE(content_json, 'Synthetic Lecturer 1', 'Tampered Lecturer 1')"))
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    before = counts(db)
    with pytest.raises(StagingError) as raised:
        svc(db).activate_rule_set()
    assert raised.value.code == "STORED_ARTIFACT_CORRUPT"
    assert counts(db) == before and svc(db).active_rule_set() == ("1", "1")
    assert {row[5] for row in observations(db)} == {"1"}     # view still on the old rules


def test_an_incomplete_analysis_can_never_become_active(db, active, monkeypatch):
    result = active.ingest_harvest(**harvest([lecturer(1), lecturer(2)]))
    db.execute(text(
        "INSERT INTO source_analyses (id, content_id, contract_version, identity_rules_version, "
        "normalization_version, parser_build, artifact_issues, declared_counts, record_count, "
        "claim_count) VALUES (:id, :content, '1.0', '2', '1', 'crashed', '[]', '{}', 2, 2)"),
        {"id": uuid.uuid4().hex, "content": result.content_id.hex})
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    with pytest.raises(StagingError) as raised:
        svc(db).activate_rule_set()
    assert raised.value.code == "ANALYSIS_INCOMPLETE"
    assert svc(db).active_rule_set() == ("1", "1")
    assert {row[5] for row in observations(db)} == {"1"}


def test_two_contract_versions_of_one_capture_are_observed_once(db, active):
    """No adapter emits 1.1 yet; a re-versioned canonical artifact simulates one."""
    artifact = adapters.guide_tables_artifact(
        json.loads(tables_snapshot([["X", sid(1), "1"]])["snapshot_bytes"]),
        snapshot_sha256="a" * 64, completeness="COMPLETE")
    for version in ("1.0", "1.1"):
        versioned = copy.deepcopy(artifact)
        versioned["contract_version"] = version
        active._ingest(adapters.artifact_bytes(versioned), None)
    assert counts(db)["source_captures"] == 1 and counts(db)["source_artifacts"] == 2
    assert len(observations(db)) == 1
    assert_no_duplicate_observations(db)


# ---------------------------------------------------------------------------
# 6-8: shared IDs, duplicate ORCIDs, invalid rows
# ---------------------------------------------------------------------------

def test_claims_sharing_one_scopus_id_are_all_preserved(db, active):
    active.ingest_guide_snapshot(**tables_snapshot([["X", sid(1), "1"]], [["Y", sid(1), "2"]]),
                                 completeness="COMPLETE")
    active.ingest_guide_snapshot(**multi_snapshot([multi_row(1, [sid(5)]),
                                                   multi_row(2, [sid(5)])]),
                                 completeness="PARTIAL")
    by_value = db.execute(text(
        "SELECT claim_type, subject_key FROM source_claim_observations "
        "WHERE value_normalized IN (:a, :b) ORDER BY claim_type, subject_key"),
        {"a": sid(1), "b": sid(5)}).all()
    assert [tuple(r) for r in by_value] == [
        ("SCOPUS_ID_AMBIGUOUS", None), ("SCOPUS_ID_OWNED", "gv1@example.invalid"),
        ("SCOPUS_ID_OWNED", "gv2@example.invalid"), ("SCOPUS_ID_UNASSIGNED", None)]


def test_duplicate_orcid_claims_are_all_preserved(db, active):
    active.ingest_harvest(**harvest([lecturer(1, orcid=ORCID_A), lecturer(2, orcid=ORCID_A)]))
    rows = db.execute(text("SELECT record_id FROM source_claims "
                           "WHERE claim_type = 'ORCID_DECLARED' AND value_normalized = :o"),
                      {"o": ORCID_A}).all()
    assert len(rows) == 2 and len({r[0] for r in rows}) == 2


def test_invalid_source_rows_are_retained(db, active):
    active.ingest_guide_snapshot(**tables_snapshot([], [["Z", "57-BAD", "1"]]),
                                 completeness="COMPLETE")
    record = db.execute(text("SELECT validation_status, raw FROM source_records")).one()
    assert record[0] == "INVALID" and json.loads(record[1]) == ["Z", "57-BAD", "1"]
    claim = db.execute(text("SELECT value_raw, value_normalized, value_valid "
                            "FROM source_claims")).one()
    assert tuple(claim) == ("57-BAD", None, 0)


# ---------------------------------------------------------------------------
# 9-11: PARTIAL, withdrawal, reclassification, identities untouched
# ---------------------------------------------------------------------------

def test_withdrawal_and_reclassification_between_complete_captures(db, active):
    before = active.ingest_guide_snapshot(
        **tables_snapshot([["X", sid(1), "1"]], [["Y", sid(2), "1"]]), completeness="COMPLETE")
    after = active.ingest_guide_snapshot(
        **tables_snapshot([], [["X", sid(1), "1"]], ts="2026-11-29T00:00:00Z"),
        completeness="COMPLETE")
    report = active.compare_captures(before.capture_id, after.capture_id).report
    status = {e.key: e.status for e in report.entries if e.dimension == "SCOPUS_ID"}
    assert report.comparable
    assert status == {sid(1): P.RECLASSIFIED, sid(2): P.WITHDRAWN}


def test_partial_capture_never_withdraws(db, active):
    before = active.ingest_guide_snapshot(
        **tables_snapshot([], [["Y", sid(2), "1"], ["Z", sid(3), "1"]]), completeness="COMPLETE")
    after = active.ingest_guide_snapshot(
        **tables_snapshot([], [["Y", sid(2), "1"]], ts="2026-11-29T00:00:00Z"),
        completeness="PARTIAL")
    stored = db.execute(text("SELECT completeness FROM source_captures WHERE id = :i"),
                        {"i": after.capture_id.hex}).scalar_one()
    assert stored == "PARTIAL"
    report = active.compare_captures(before.capture_id, after.capture_id).report
    assert not report.comparable and report.by_status(P.WITHDRAWN) == ()
    assert {e.key: e.status for e in report.entries}[sid(3)] is P.NOT_OBSERVED


def test_harvest_with_a_lecturer_failure_is_partial_and_never_withdraws(db, active):
    before = active.ingest_harvest(**harvest([lecturer(1), lecturer(2)]))
    after = active.ingest_harvest(**harvest([lecturer(1)], completed="2026-11-03T09:00:00Z",
                                            failures=("lecturer",)))
    assert after.completeness == "PARTIAL"
    report = active.compare_captures(before.capture_id, after.capture_id).report
    assert report.by_status(P.WITHDRAWN) == ()


def test_a_failed_replay_is_refused_before_any_write(db, active):
    files = harvest([lecturer(1)])
    replay = json.loads(files["replay_bytes"])
    replay["a_equals_b_equals_c"] = False
    with pytest.raises(StagingError) as raised:
        active.ingest_harvest(**{**files, "replay_bytes": _encode(replay)})
    assert raised.value.code == "SOURCE_REJECTED_REPLAY_NOT_PASSED"
    assert counts(db)["source_contents"] == 0


def test_different_projection_versions_are_not_comparable(db, active):
    before = active.ingest_guide_snapshot(**tables_snapshot([], [["Y", sid(2), "1"]]),
                                          completeness="COMPLETE")
    after = active.ingest_guide_snapshot(**tables_snapshot([], [], ts="2026-11-29T00:00:00Z"),
                                         completeness="COMPLETE")
    db.execute(text("UPDATE source_captures SET projection_version = 'OTHER_PROJECTION' "
                    "WHERE id = :i"), {"i": after.capture_id.hex})   # simulates another producer
    report = active.compare_captures(before.capture_id, after.capture_id).report
    assert "PROJECTION_DIFFERS" in report.reasons and report.by_status(P.WITHDRAWN) == ()


def test_reviewer_approved_identities_and_all_non_staging_tables_are_untouched(db, active,
                                                                              monkeypatch):
    identity = {"id": uuid.uuid4().hex, "lecturer_id": uuid.uuid4().hex,
                "scopus_author_id": uuid.uuid4().hex, "status": "APPROVED", "version": 3,
                "created_at": "2026-01-01 00:00:00", "updated_at": "2026-01-01 00:00:00"}
    db.execute(text("INSERT INTO lecturer_scopus_identities (id, lecturer_id, scopus_author_id, "
                    "status, version, created_at, updated_at) VALUES (:id, :lecturer_id, "
                    ":scopus_author_id, :status, :version, :created_at, :updated_at)"), identity)
    others = [t for t in Base.metadata.tables if t not in STAGING and t != "audit_events"]
    before = {t: db.execute(text(f"SELECT * FROM {t}")).all() for t in others}

    first = active.ingest_guide_snapshot(**tables_snapshot([["X", sid(1), "1"]]),
                                         completeness="COMPLETE")
    gone = active.ingest_guide_snapshot(**tables_snapshot([], ts="2026-11-29T00:00:00Z"),
                                        completeness="COMPLETE")
    assert active.compare_captures(first.capture_id, gone.capture_id).report.by_status(P.WITHDRAWN)
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    svc(db).activate_rule_set()

    assert {t: db.execute(text(f"SELECT * FROM {t}")).all() for t in others} == before


def test_the_service_only_inserts_into_staging_and_audit_tables(engine, db, active, monkeypatch):
    statements = []
    event.listen(engine, "before_cursor_execute",
                 lambda conn, cursor, stmt, params, ctx, many: statements.append(stmt))
    active.ingest_harvest(**harvest([lecturer(1, orcid=ORCID_A)]))
    active.ingest_guide_snapshot(**tables_snapshot([["X", sid(1), "1"]]), completeness="COMPLETE")
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    svc(db).activate_rule_set()
    writes = [s.split()[0:3] for s in statements
              if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
    assert writes and all(w[0].upper() == "INSERT" for w in writes)   # append-only
    targets = {w[2] for w in writes}
    assert targets <= STAGING | {"audit_events"}


# ---------------------------------------------------------------------------
# 13-14: transactions, rollback, races
# ---------------------------------------------------------------------------

def test_failure_rolls_back_only_the_failing_ingest(db, active, monkeypatch):
    kept = active.ingest_harvest(**harvest([lecturer(1)]))
    before = counts(db)
    original = service_module.SourceStagingService._insert_children

    def explode(self, analysis_id, snap):
        original(self, analysis_id, snap)
        raise RuntimeError("injected failure after children were written")

    monkeypatch.setattr(service_module.SourceStagingService, "_insert_children", explode)
    with pytest.raises(RuntimeError):
        active.ingest_guide_snapshot(**tables_snapshot([["X", sid(1), "1"]]),
                                     completeness="COMPLETE")
    assert counts(db) == before                      # nothing of the failed ingest remains
    db.commit()                                      # the caller's transaction is still usable
    assert db.execute(text("SELECT COUNT(*) FROM source_artifacts WHERE id = :i"),
                      {"i": kept.artifact_id.hex}).scalar_one() == 1
    assert count(db, "audit_events") == 2            # activation + the kept ingest only


def test_unexpected_integrity_errors_fail_closed(db, active, monkeypatch):
    def duplicate_position(self, analysis_id, snap):
        row = {"id": uuid.uuid4(), "analysis_id": analysis_id, "record_kind": "PROFILE",
               "source_position": 1, "record_hash": "a" * 64, "record_key": "k",
               "key_method": "CONTENT_V1", "key_strength": "WEAK", "raw": {}, "normalized": {},
               "validation_status": "VALID", "issues": []}
        from sqlalchemy import insert
        self.session.execute(insert(service_module.SourceRecord), [row, {**row,
                                                                         "id": uuid.uuid4()}])

    monkeypatch.setattr(service_module.SourceStagingService, "_insert_children",
                        duplicate_position)
    before = counts(db)
    with pytest.raises(StagingError) as raised:
        active.ingest_harvest(**harvest([lecturer(1)]))
    assert raised.value.code == "INTEGRITY_VIOLATION"
    assert counts(db) == before


def test_rows_committed_by_another_transaction_are_reused_not_duplicated(tmp_path):
    engine = make_sqlite_engine(f"sqlite:///{tmp_path / 'race.db'}")
    files = harvest([lecturer(1, orcid=ORCID_A)])
    with Session(engine) as setup:
        svc(setup).activate_rule_set()
        setup.commit()
    with Session(engine) as first, Session(engine) as second:
        winner = svc(first).ingest_harvest(**files)
        first.commit()
        loser = svc(second).ingest_harvest(**files)  # every insert conflicts with committed rows
        second.commit()
    assert (winner.outcome, loser.outcome) == ("CREATED", "ALREADY_INGESTED")
    assert loser.artifact_id == winner.artifact_id and loser.analysis_id == winner.analysis_id
    with Session(engine) as check:
        assert counts(check)["source_claims"] == winner.claim_count
    engine.dispose()


def test_a_concurrently_created_but_incomplete_analysis_is_refused(db, active, monkeypatch):
    original = service_module.SourceStagingService._insert_ignore

    def lose_the_race(self, model, values):
        if model is service_module.SourceAnalysis:      # another writer inserted it first ...
            original(self, model, values)                # ... without its records and claims
            return False
        return original(self, model, values)

    monkeypatch.setattr(service_module.SourceStagingService, "_insert_ignore", lose_the_race)
    with pytest.raises(StagingError) as raised:
        active.ingest_harvest(**harvest([lecturer(1)]))
    assert raised.value.code == "ANALYSIS_INCOMPLETE"
    assert counts(db)["source_analyses"] == 0


# ---------------------------------------------------------------------------
# Input validation and helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("change", "code"), [
    ({"snapshot_sha256": "f" * 64}, "BYTES_SHA256_MISMATCH"),
    ({"layout": "OTHER"}, "LAYOUT_INVALID"),
    ({"completeness": "MOSTLY"}, "SOURCE_REJECTED_COMPLETENESS_INVALID"),
])
def test_guide_snapshot_inputs_are_validated(db, active, change, code):
    args = {**tables_snapshot([["X", sid(1), "1"]]), "completeness": "COMPLETE", **change}
    with pytest.raises(StagingError) as raised:
        active.ingest_guide_snapshot(**args)
    assert raised.value.code == code
    assert counts(db)["source_contents"] == 0


def test_harvest_bytes_must_match_the_declared_sha(db, active):
    files = harvest([lecturer(1)])
    with pytest.raises(StagingError) as raised:
        active.ingest_harvest(**{**files, "lecturers_sha256": "f" * 64})
    assert raised.value.code == "SOURCE_REJECTED_BYTES_SHA256_MISMATCH"


@pytest.mark.parametrize("actor", [dict(), dict(user_id=uuid.uuid4(), service="x"),
                                   dict(service="  ")])
def test_actor_follows_the_audit_invariant(actor):
    with pytest.raises(StagingError):
        Actor(**actor)


def test_user_actor_is_recorded(db, engine):
    user = uuid.uuid4()
    service = SourceStagingService(db, Actor(user_id=user))
    service.activate_rule_set()
    service.ingest_guide_snapshot(**tables_snapshot([["X", sid(1), "1"]]), completeness="COMPLETE")
    rows = db.execute(select(AuditEvent.actor_type, AuditEvent.actor_user_id,
                             AuditEvent.actor_service)).all()
    assert {tuple(r) for r in rows} == {("USER", user, None)}
    assert db.execute(text("SELECT ingested_by FROM source_artifacts")).scalar_one() == user.hex


# ---------------------------------------------------------------------------
# B2-R1: audit events reference the real affected rows
# ---------------------------------------------------------------------------

def _activation_audits(session):
    return session.execute(select(AuditEvent.entity_type, AuditEvent.entity_id,
                                  AuditEvent.event_metadata)
                           .where(AuditEvent.action == "SOURCE_RULE_SET_ACTIVATED")).all()


def test_b2_r1_activation_audit_references_the_persisted_rule_set_row(db, monkeypatch):
    svc(db).activate_rule_set(reason="bootstrap")
    ingested = svc(db).ingest_harvest(**harvest([lecturer(1)]))
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    svc(db).activate_rule_set(reason="rules v2")

    rows = {row.id: (row.identity_rules_version, row.normalization_version, row.reason)
            for row in db.execute(select(staging.SourceRuleSet)).scalars()}
    audits = _activation_audits(db)
    assert len(rows) == len(audits) == 2
    for entity_type, entity_id, metadata in audits:
        assert entity_type == "source_rule_set"
        assert entity_id in rows                      # the exact persisted row, not a new UUID
        assert rows[entity_id] == (metadata["identity_rules_version"],
                                   metadata["normalization_version"], metadata["reason"])
    assert {e for _, e, _ in audits} == set(rows)
    ingest_audit = db.execute(select(AuditEvent.entity_id).where(
        AuditEvent.action == "SOURCE_ARTIFACT_INGESTED")).scalar_one()
    assert ingest_audit == ingested.artifact_id


def test_b2_r1_failure_after_the_rule_set_insert_leaves_no_row_and_no_audit(db, active,
                                                                         monkeypatch):
    """The rule-set row is written before coverage is proven; a failure there must undo it."""
    active.ingest_harvest(**harvest([lecturer(1)]))
    rule_sets, audits = count(db, "source_rule_sets"), count(db, "audit_events")
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")

    def fail_coverage(self, target):
        assert count(self.session, "source_rule_sets") == rule_sets + 1   # row was inserted
        raise StagingError("ACTIVATION_INCOMPLETE", "injected")

    monkeypatch.setattr(service_module.SourceStagingService, "_coverage", fail_coverage)
    with pytest.raises(StagingError) as raised:
        svc(db).activate_rule_set()
    assert raised.value.code == "ACTIVATION_INCOMPLETE"
    assert count(db, "source_rule_sets") == rule_sets
    assert count(db, "audit_events") == audits
    assert len(_activation_audits(db)) == 1           # only the bootstrap activation
    assert svc(db).active_rule_set() == ("1", "1")


def test_b2_r1_failed_reanalysis_leaves_no_activation_audit(db, active, monkeypatch):
    active.ingest_harvest(**harvest([lecturer(1)]))
    db.execute(text("UPDATE source_contents SET content_json = "
                    "REPLACE(content_json, 'Synthetic Lecturer 1', 'Tampered Lecturer 1')"))
    audits = count(db, "audit_events")
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    with pytest.raises(StagingError):
        svc(db).activate_rule_set()
    assert count(db, "audit_events") == audits and len(_activation_audits(db)) == 1


def test_b2_r1_already_active_writes_no_row_and_no_audit(db, active):
    rule_sets, audits = count(db, "source_rule_sets"), count(db, "audit_events")
    assert svc(db).activate_rule_set().outcome == "ALREADY_ACTIVE"
    assert (count(db, "source_rule_sets"), count(db, "audit_events")) == (rule_sets, audits)


def test_ingest_outcome_names_the_first_new_layer():
    layers = dict.fromkeys(("content", "capture", "artifact", "analysis"), False)
    assert ingest_outcome(layers) == "ALREADY_INGESTED"
    for layer, outcome in (("analysis", "REANALYSED"), ("artifact", "ARTIFACT_ADDED"),
                           ("capture", "REUSED"), ("content", "CREATED")):
        layers[layer] = True
        assert ingest_outcome(layers) == outcome
