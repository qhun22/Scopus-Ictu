"""Gate E.3 / P2-B1 — staging schema, migration structure and observation-view semantics.

No application database. Metadata and migration checks render PostgreSQL DDL offline. The view
and ingest-lifecycle checks run the *same* view SQL on in-memory SQLite stand-in tables that copy
the real models' columns, primary keys, unique constraints and staging-internal foreign keys.
PostgreSQL CHECKs, JSONB and execution of the migration itself are not exercised here.
"""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import re
import sqlite3
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Base
from app.models import source_staging as staging
from app.services.source_claims import adapters, parser
from app.services.source_claims.contract import (
    ClaimType,
    KeyMethod,
    KeyStrength,
    RecordKind,
    SourceSystem,
    ValidationStatus,
)
from app.services.source_claims.parser import parse_artifact_bytes

BACKEND = Path(__file__).resolve().parents[2]
VERSIONS = BACKEND / "alembic" / "versions"
MIGRATION = VERSIONS / "a77e01c33ee1_e3_p2b1_source_claim_staging.py"
PG = postgresql.dialect()
TABLES = staging.STAGING_TABLES
ORCID_A = "0000-0002-1825-0097"
SHA = "a" * 64


def sid(n: int) -> str:
    return str(57000000000 + n)


# ---------------------------------------------------------------------------
# 1. Metadata: isolation, uniqueness inventory, vocabulary sync
# ---------------------------------------------------------------------------

def test_all_staging_tables_are_registered():
    assert set(TABLES) <= set(Base.metadata.tables)
    for name in TABLES:
        assert "updated_at" not in Base.metadata.tables[name].c  # append-only convention


def test_staging_has_no_foreign_key_to_identity_or_canonical_tables():
    for name in TABLES:
        for fk in Base.metadata.tables[name].foreign_keys:
            assert fk.column.table.name in set(TABLES) | {"users"}, (name, fk.target_fullname)
    for table in Base.metadata.tables.values():
        if table.name in TABLES:
            continue
        assert not any(fk.column.table.name in TABLES for fk in table.foreign_keys), table.name
    forbidden = {"lecturer_id", "scopus_author_id", "identity_id", "candidate_id", "status",
                 "decision", "reviewer_user_id", "approved"}
    for name in TABLES:
        assert not forbidden & set(Base.metadata.tables[name].c.keys()), name


def _unique_sets():
    found = set()
    for name in TABLES:
        table = Base.metadata.tables[name]
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint):
                found.add((name, tuple(c.name for c in constraint.columns)))
        for index in table.indexes:
            assert not index.unique, index.name
    return found


def test_unique_constraints_are_exactly_the_designed_ones():
    """No global UNIQUE on ORCID, name, record_key or claim_key can slip in unnoticed."""
    assert _unique_sets() == {
        ("source_rule_sets", ("sequence_no",)),
        ("source_contents", ("source_system", "content_hash")),
        ("source_contents", ("id", "source_system")),
        ("source_captures", ("content_id", "capture_hash")),
        ("source_captures", ("id", "content_id")),
        ("source_artifacts", ("artifact_bytes_sha256",)),
        ("source_artifacts", ("capture_id", "contract_version")),
        ("source_analyses", ("content_id", "contract_version", "identity_rules_version",
                             "normalization_version")),
        ("source_records", ("analysis_id", "record_kind", "source_position")),
        ("source_records", ("id", "analysis_id")),
        ("source_claims", ("record_id", "claim_key")),
    }
    artifact_columns = set(Base.metadata.tables["source_artifacts"].c.keys())
    assert "analysis_id" not in artifact_columns  # a new analysis never rewrites an artifact


def test_check_vocabularies_match_the_p1_contract():
    assert set(staging.SOURCE_SYSTEMS) == {s.value for s in SourceSystem}
    assert set(staging.RECORD_KINDS) == {k.value for k in RecordKind}
    assert set(staging.CLAIM_TYPES) == {c.value for c in ClaimType}
    assert set(staging.VALIDATION_STATUSES) == {s.value for s in ValidationStatus}
    assert {m for m, _ in staging.KEY_METHOD_STRENGTH} == {m.value for m in KeyMethod}
    assert {s for _, s in staging.KEY_METHOD_STRENGTH} == {s.value for s in KeyStrength}
    pairs = set()
    for snap in (_profiles_snapshot(), _guide_snapshot(), _multi_snapshot()):
        pairs |= {(r.record_key.method.value, r.record_key.strength.value) for r in snap.records}
        unowned = {c.claim_type.value for c in snap.claims if c.subject_key is None}
        assert unowned <= set(staging.UNOWNED_CLAIM_TYPES)
    assert pairs <= set(staging.KEY_METHOD_STRENGTH)


def test_contract_version_sql_pattern_is_the_parser_grammar():
    for version in ("1.0", "1.1", "1.10", "1.00"):
        assert re.fullmatch(staging.CONTRACT_VERSION_SQL_PATTERN[1:-1], version)
    for version in ("2.0", "1", "1.x", "1.0.1", "01.0"):
        assert not re.fullmatch(staging.CONTRACT_VERSION_SQL_PATTERN[1:-1], version)
        assert not parser._CONTRACT_VERSION_RE.fullmatch(version)


# ---------------------------------------------------------------------------
# 2. Migration structure (offline PostgreSQL rendering; no connection)
# ---------------------------------------------------------------------------

def _migration_module():
    spec = importlib.util.spec_from_file_location("e3_p2b1_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render(step: str) -> str:
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buffer, "target_metadata": Base.metadata})
    with Operations.context(context):
        getattr(_migration_module(), step)()
    return buffer.getvalue()


def _revision_graph():
    revisions, downs = {}, set()
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        rev = re.search(r'^revision(?::[^=]+)?\s*=\s*"([^"]+)"', text, re.M)
        down = re.search(r"^down_revision(?::[^=]+)?\s*=\s*(.+)$", text, re.M)
        if rev:
            revisions[rev.group(1)] = path.name
            downs.update(re.findall(r'"([0-9a-z_]+)"', down.group(1) if down else ""))
    return revisions, downs


def test_migration_is_the_single_new_head_on_top_of_the_previous_head():
    module = _migration_module()
    assert (module.revision, module.down_revision) == ("a77e01c33ee1", "a1b2c3d4e5f6")
    revisions, downs = _revision_graph()
    # Append-only chain: the head moves on with each accepted revision (now the main-ID label).
    assert set(revisions) - downs == {"f2b8c3d19a47"}
    assert "a77e01c33ee1" in downs  # Accepted staging revision is the parent, never rewritten.


def _items(create_table_sql: str) -> set[str]:
    body = create_table_sql[create_table_sql.index("(") + 1: create_table_sql.rindex(")")]
    items, depth, current = [], 0, ""
    for char in body:
        depth += char == "("
        depth -= char == ")"
        if char == "," and depth == 0:
            items.append(current)
            current = ""
        else:
            current += char
    items.append(current)
    return {" ".join(item.split()) for item in items if item.strip()}


def _blocks(sql: str, prefix: str) -> dict[str, str]:
    found = {}
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement.startswith(prefix):
            found[statement.split()[len(prefix.split())]] = statement
    return found


def test_migration_tables_match_the_models_item_by_item():
    rendered = _blocks(_render("upgrade"), "CREATE TABLE")
    assert set(rendered) == set(TABLES)
    for name in TABLES:
        model_sql = str(CreateTable(Base.metadata.tables[name]).compile(dialect=PG))
        assert _items(rendered[name]) == _items(model_sql), name


def test_migration_indexes_match_the_models():
    sql = _render("upgrade")
    rendered = {" ".join(s.split()) for s in sql.split(";") if s.strip().startswith("CREATE INDEX")}
    expected = {" ".join(str(CreateIndex(ix).compile(dialect=PG)).split())
                for name in TABLES for ix in Base.metadata.tables[name].indexes}
    assert rendered == expected


def test_migration_views_are_the_model_view_sql():
    module = _migration_module()
    assert module.SOURCE_CAPTURE_ANALYSES_SQL == staging.SOURCE_CAPTURE_ANALYSES_SQL
    assert module.SOURCE_CLAIM_OBSERVATIONS_SQL == staging.SOURCE_CLAIM_OBSERVATIONS_SQL
    sql = _render("upgrade")
    for name, body in ((staging.SOURCE_CAPTURE_ANALYSES_VIEW, staging.SOURCE_CAPTURE_ANALYSES_SQL),
                       (staging.SOURCE_CLAIM_OBSERVATIONS_VIEW,
                        staging.SOURCE_CLAIM_OBSERVATIONS_SQL)):
        assert f"CREATE VIEW {name} AS\n{body}" in sql
    assert sql.index("CREATE VIEW source_capture_analyses") < sql.index(
        "CREATE VIEW source_claim_observations")


def test_downgrade_removes_everything_upgrade_creates_in_reverse_dependency_order():
    up, down = _render("upgrade"), _render("downgrade")
    dropped_tables = re.findall(r"DROP TABLE (\w+)", down)
    assert dropped_tables == list(reversed(TABLES))
    created_indexes = set(re.findall(r"CREATE INDEX (\w+)", up))
    assert set(re.findall(r"DROP INDEX (\w+)", down)) == created_indexes
    assert re.findall(r"DROP VIEW (\w+)", down) == list(reversed(staging.STAGING_VIEWS))
    assert down.index("DROP VIEW") < down.index("DROP TABLE")
    assert "lecturer" not in up.lower().replace("lecturers.json", "")


def test_migration_ddl_carries_the_integrity_checks():
    sql = " ".join(_render("upgrade").split())
    for fragment in (
        "content_hash = encode(sha256(convert_to(content_json, 'UTF8')), 'hex')",
        "capture_hash = encode(sha256(convert_to(capture_json, 'UTF8')), 'hex')",
        "contract_version ~ '^1\\.[0-9]+$'",
        "(subject_key IS NULL) = (claim_type IN ('SCOPUS_ID_AMBIGUOUS', 'SCOPUS_ID_UNASSIGNED'))",
        "value_valid BOOLEAN GENERATED ALWAYS AS (value_normalized IS NOT NULL) STORED NOT NULL",
        "sequence_no BIGINT GENERATED ALWAYS AS IDENTITY",
        "FOREIGN KEY(capture_id, content_id) REFERENCES source_captures (id, content_id)",
        "FOREIGN KEY(record_id, analysis_id) REFERENCES source_records (id, analysis_id)",
    ):
        assert fragment in sql, fragment


# ---------------------------------------------------------------------------
# 3. Executable view semantics on SQLite stand-ins built from the real models
# ---------------------------------------------------------------------------

def _sqlite_type(column) -> str:
    return "INTEGER" if isinstance(column.type, (Integer, BigInteger, SmallInteger, Boolean)) \
        else "TEXT"


def _stand_in_ddl(name: str) -> str:
    table = Base.metadata.tables[name]
    parts = []
    for column in table.columns:
        if column.computed is not None:
            parts.append(f"{column.name} INTEGER GENERATED ALWAYS AS "
                         f"({column.computed.sqltext}) VIRTUAL")
        else:
            parts.append(f"{column.name} {_sqlite_type(column)}"
                         + (" NOT NULL" if not column.nullable else ""))
    parts.append(f"PRIMARY KEY ({', '.join(c.name for c in table.primary_key.columns)})")
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            parts.append(f"UNIQUE ({', '.join(c.name for c in constraint.columns)})")
        internal_fk = (isinstance(constraint, ForeignKeyConstraint)
                       and constraint.referred_table.name in TABLES)
        if internal_fk:
            local = ", ".join(c.name for c in constraint.columns)
            remote = ", ".join(e.column.name for e in constraint.elements)
            parts.append(f"FOREIGN KEY ({local}) REFERENCES {constraint.referred_table.name} "
                         f"({remote})")
    return f"CREATE TABLE {name} ({', '.join(parts)})"


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    for name in TABLES:
        conn.execute(_stand_in_ddl(name))
    conn.execute(f"CREATE VIEW source_capture_analyses AS {staging.SOURCE_CAPTURE_ANALYSES_SQL}")
    conn.execute(f"CREATE VIEW source_claim_observations AS "
                 f"{staging.SOURCE_CLAIM_OBSERVATIONS_SQL}")
    yield Store(conn)
    conn.close()


class Store:
    """Executable specification of the P2-B2 ingest lifecycle against the stand-in tables."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn, self.clock = conn, 0

    def tick(self) -> str:
        self.clock += 1
        return f"2026-10-29T00:00:{self.clock:02d}Z"

    def activate(self, identity: str, normalization: str) -> None:
        seq = (self.conn.execute("SELECT COALESCE(MAX(sequence_no), 0) FROM source_rule_sets")
               .fetchone()[0]) + 1
        self.conn.execute("INSERT INTO source_rule_sets (id, sequence_no, identity_rules_version, "
                          "normalization_version, activated_at) VALUES (?, ?, ?, ?, ?)",
                          (str(uuid.uuid4()), seq, identity, normalization, self.tick()))

    def _ensure(self, table: str, key: dict, values: dict) -> tuple[str, bool]:
        row = {"id": str(uuid.uuid4()), **key, **values}
        cols = ", ".join(row)
        cursor = self.conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' for _ in row)}) "
            "ON CONFLICT DO NOTHING", tuple(row.values()))
        where = " AND ".join(f"{k} = ?" for k in key)
        found = self.conn.execute(f"SELECT id FROM {table} WHERE {where}", tuple(key.values()))
        return found.fetchone()[0], cursor.rowcount == 1

    def ingest(self, data: bytes) -> tuple[str, dict[str, bool]]:
        """Each layer is checked on its own key; an existing artifact never blocks an analysis."""
        snap = parse_artifact_bytes(data)
        adapters.staging_keys(snap)
        system = snap.source_system.value
        capture = json.loads(snap.capture.capture_json)
        content_id, new_content = self._ensure(
            "source_contents", {"source_system": system, "content_hash": snap.content_hash},
            {"contract_major": 1, "scope_key": snap.scope_key, "source_url": snap.source_url,
             "content_json": snap.content_json, "created_at": self.tick()})
        capture_id, new_capture = self._ensure(
            "source_captures",
            {"content_id": content_id, "capture_hash": snap.capture.capture_hash},
            {"source_system": system, "captured_at": snap.capture.captured_at,
             "completeness": snap.completeness.value, "capture_json": snap.capture.capture_json,
             "adapter_version": capture["adapter"]["version"],
             "projection_version": capture["adapter"]["projection"],
             "upstream_name": capture["upstream"]["file"],
             "upstream_bytes_sha256": capture["upstream"]["bytes_sha256"],
             "created_at": self.tick()})
        _, new_artifact = self._ensure(
            "source_artifacts", {"artifact_bytes_sha256": snap.artifact_bytes_sha256},
            {"content_id": content_id, "capture_id": capture_id,
             "contract_version": snap.contract_version, "ingested_at": self.tick()})
        new_analysis = self._ensure_analysis(content_id, snap)
        layers = {"content": new_content, "capture": new_capture, "artifact": new_artifact,
                  "analysis": new_analysis}
        return ingest_outcome(layers), layers

    def _ensure_analysis(self, content_id: str, snap) -> bool:
        analysis_id, new = self._ensure(
            "source_analyses",
            {"content_id": content_id, "contract_version": snap.contract_version,
             "identity_rules_version": snap.identity_rules_version,
             "normalization_version": snap.normalization_version},
            {"parser_build": "test",
             "artifact_issues": json.dumps([i.to_dict() for i in snap.issues]),
             "declared_counts": json.dumps(dict(snap.declared_counts)),
             "record_count": len(snap.records), "claim_count": len(snap.claims),
             "created_at": self.tick()})
        if not new:
            return False
        record_ids = {}
        for record in snap.records:
            record_ids[record.ref] = str(uuid.uuid4())
            self.conn.execute(
                "INSERT INTO source_records (id, analysis_id, record_kind, source_position, "
                "record_hash, record_key, key_method, key_strength, raw, normalized, "
                "validation_status, issues, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record_ids[record.ref], analysis_id, record.record_kind.value,
                 record.source_position, record.record_hash, record.record_key.value,
                 record.record_key.method.value, record.record_key.strength.value, record.raw_json,
                 json.dumps({k: dict(v) for k, v in record.normalized}),
                 record.validation_status.value, json.dumps([i.to_dict() for i in record.issues]),
                 self.tick()))
        for claim in snap.claims:
            self.conn.execute(
                "INSERT INTO source_claims (id, analysis_id, record_id, claim_type, subject_key, "
                "value_raw, value_normalized, value_method, claim_key, flags, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), analysis_id, record_ids[claim.record_ref],
                 claim.claim_type.value, claim.subject_key, claim.value.raw, claim.value.normalized,
                 claim.value.method, claim.claim_key, json.dumps(dict(claim.flags)), self.tick()))
        return True

    def reanalyse_stored(self) -> int:
        """Re-parse every stored artifact from its rows (no upstream input) under current rules."""
        rows = self.conn.execute(
            "SELECT art.contract_version, cap.capture_json, con.content_json, con.source_system, "
            "con.id FROM source_artifacts art JOIN source_captures cap ON cap.id = art.capture_id "
            "JOIN source_contents con ON con.id = art.content_id").fetchall()
        created = 0
        for version, capture_json, content_json, system, content_id in rows:
            data = adapters.reconstruct_artifact_bytes(
                source_system=system, contract_version=version, capture_json=capture_json,
                content_json=content_json)
            created += self._ensure_analysis(content_id, parse_artifact_bytes(data))
        return created

    def rows(self, sql: str, *args) -> list[tuple]:
        return self.conn.execute(sql, args).fetchall()

    def count(self, table: str) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def ingest_outcome(layers: dict[str, bool]) -> str:
    if layers["content"]:
        return "CREATED"
    if layers["capture"]:
        return "REUSED"
    if layers["artifact"]:
        return "ARTIFACT_ADDED"
    if layers["analysis"]:
        return "REANALYSED"
    return "ALREADY_INGESTED"


def _profile(n, orcid=None, email=None):
    url = f"https://repository.example.invalid/giang-vien/synthetic-{n}/"
    labels = {"Họ và tên": f"Synthetic {n}", "Email": email or f"l{n}@example.invalid"}
    if orcid:
        labels["ORCID"] = f"{orcid} ↗"
    return {"source_id": url, "profile_url": url, "full_name": f"Synthetic {n}",
            "institutional_email": email or f"l{n}@example.invalid", "orcid": orcid,
            "public_publication_links": [], "source_fields": labels,
            "provenance": {"retrieved_at": "2026-10-03T18:44:10Z"}}


def _profiles_artifact(completed="2026-10-03T21:31:10Z"):
    items = [_profile(1, ORCID_A), _profile(2, ORCID_A), _profile(3)]
    manifest = {"harvest_completed_at": completed,
                "source_base_url": "https://repository.example.invalid", "source_card_count": 3,
                "lecturer_count": 3, "status": "COMPLETE", "source_drift_detected": False,
                "semantic_file_hashes": {"lecturers.json": "b" * 64}}
    replay = {"a_equals_b_equals_c": True,
              "file_hashes": {r: {"lecturers.json": "b" * 64} for r in ("A", "B", "C")}}
    return adapters.profiles_artifact(items, manifest, {"source_entity_failures": []}, replay,
                                      lecturers_sha256=SHA)


def _guide_artifact():
    header = ["Tên trên Scopus", "Scopus ID", "Số bài"]
    snapshot = {"ts": "2026-10-29T01:37:29Z",
                "url": "https://repository.example.invalid/huong-dan-gop-tai-khoan-scopus/",
                "section_headings": {"1": "Scopus ID nhập nhằng — synthetic",
                                     "2": "Scopus ID chưa xác định chủ sở hữu — synthetic"},
                "tables": [{"ti": 1, "rows": [header, ["X", sid(1), "1"]]},
                           {"ti": 2, "rows": [header, ["Y", sid(1), "2"], ["Z", "57-BAD", "1"]]}]}
    return adapters.guide_tables_artifact(snapshot, snapshot_sha256=SHA, completeness="COMPLETE")


def _multi_artifact():
    rows = [["GV 1", "gv1@example.invalid", "2", "3", sid(5), f"{sid(5)}; {sid(6)}"],
            ["GV 2", "gv2@example.invalid", "1", "1", sid(5), sid(5)]]
    snapshot = {"ts": "2026-10-29T00:32:28Z",
                "url": "https://repository.example.invalid/huong-dan-gop-tai-khoan-scopus/",
                "multi_id_rows": 2, "rows": rows}
    return adapters.guide_multi_id_artifact(snapshot, snapshot_sha256=SHA, completeness="PARTIAL")


def _bytes(artifact, version="1.0"):
    artifact = copy.deepcopy(artifact)
    artifact["contract_version"] = version
    return adapters.artifact_bytes(artifact)


def _profiles_snapshot():
    return parse_artifact_bytes(_bytes(_profiles_artifact()))


def _guide_snapshot():
    return parse_artifact_bytes(_bytes(_guide_artifact()))


def _multi_snapshot():
    return parse_artifact_bytes(_bytes(_multi_artifact()))


def _observations(db):
    return db.rows("SELECT capture_id, claim_id, analysis_id, contract_version, "
                   "identity_rules_version, claim_type, value_normalized, record_id "
                   "FROM source_claim_observations")


def _assert_no_duplicate_observations(db):
    rows = db.rows("SELECT capture_id, claim_id FROM source_claim_observations")
    assert len(rows) == len(set(rows))
    per_capture = db.rows("SELECT capture_id, COUNT(DISTINCT analysis_id) "
                          "FROM source_claim_observations GROUP BY capture_id")
    assert all(n == 1 for _, n in per_capture)


def test_two_minor_versions_share_one_capture_and_are_observed_once(db):
    db.activate("1", "1")
    assert db.ingest(_bytes(_profiles_artifact(), "1.0"))[0] == "CREATED"
    assert db.ingest(_bytes(_profiles_artifact(), "1.1"))[0] == "ARTIFACT_ADDED"
    assert [db.count(t) for t in ("source_contents", "source_captures", "source_artifacts",
                                  "source_analyses")] == [1, 1, 2, 2]
    claims_per_analysis = len(_profiles_snapshot().claims)
    observations = _observations(db)
    assert len(observations) == claims_per_analysis      # not 2 x claims
    assert {row[3] for row in observations} == {"1.1"}  # highest minor selected
    _assert_no_duplicate_observations(db)


def test_a_naive_capture_artifact_analysis_join_would_double_count(db):
    """Guards the failure mode the view exists to prevent."""
    db.activate("1", "1")
    db.ingest(_bytes(_profiles_artifact(), "1.0"))
    db.ingest(_bytes(_profiles_artifact(), "1.1"))
    naive = db.rows("SELECT cap.id, cl.claim_key FROM source_captures cap "
                    "JOIN source_artifacts art ON art.capture_id = cap.id "
                    "JOIN source_analyses an ON an.content_id = art.content_id "
                    "AND an.contract_version = art.contract_version "
                    "JOIN source_claims cl ON cl.analysis_id = an.id")
    assert len(naive) == 2 * len(_observations(db))
    assert len({tuple(r) for r in naive}) == len(_observations(db))


def test_re_ingesting_the_same_artifact_writes_nothing(db):
    db.activate("1", "1")
    data = _bytes(_profiles_artifact())
    db.ingest(data)
    before = [db.count(t) for t in TABLES]
    outcome, layers = db.ingest(data)
    assert outcome == "ALREADY_INGESTED" and not any(layers.values())
    assert [db.count(t) for t in TABLES] == before


def test_rule_version_change_reanalyses_an_existing_artifact(db, monkeypatch):
    db.activate("1", "1")
    data = _bytes(_profiles_artifact())
    db.ingest(data)
    artifacts_before = db.rows("SELECT * FROM source_artifacts ORDER BY id")
    old_analysis = db.rows("SELECT id FROM source_analyses")[0][0]

    db.activate("2", "1")
    assert _observations(db) == []          # nothing observed under rules not yet applied

    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    outcome, layers = db.ingest(data)       # same bytes: content, capture, artifact all exist
    assert outcome == "REANALYSED"
    assert layers == {"content": False, "capture": False, "artifact": False, "analysis": True}

    assert db.rows("SELECT * FROM source_artifacts ORDER BY id") == artifacts_before
    observations = _observations(db)
    assert {row[4] for row in observations} == {"2"}
    assert len(observations) == len(_profiles_snapshot().claims)
    history = db.rows("SELECT analysis_id, identity_rules_version, is_active_rule_set, "
                      "selection_rank FROM source_capture_analyses ORDER BY selection_rank")
    assert [(r[1], r[2], r[3]) for r in history] == [("2", 1, 1), ("1", 0, 2)]
    assert history[1][0] == old_analysis
    assert db.count("source_claims") == 2 * len(_profiles_snapshot().claims)  # history kept
    _assert_no_duplicate_observations(db)


def test_reanalysis_from_stored_rows_needs_no_upstream_input(db, monkeypatch):
    db.activate("1", "1")
    db.ingest(_bytes(_profiles_artifact(), "1.0"))
    db.ingest(_bytes(_profiles_artifact(), "1.1"))
    db.activate("2", "1")
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    assert db.reanalyse_stored() == 2       # one new analysis per stored contract version
    assert db.reanalyse_stored() == 0       # idempotent
    assert {row[4] for row in _observations(db)} == {"2"}
    _assert_no_duplicate_observations(db)


def test_switching_back_to_an_older_rule_set_reselects_its_analysis(db, monkeypatch):
    db.activate("1", "1")
    data = _bytes(_profiles_artifact())
    db.ingest(data)
    db.activate("2", "1")
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    db.ingest(data)
    db.activate("1", "1")                   # re-activation is a new log row, not an update
    assert {row[4] for row in _observations(db)} == {"1"}
    assert db.count("source_rule_sets") == 3


def test_recaptured_content_is_observed_per_capture(db):
    db.activate("1", "1")
    assert db.ingest(_bytes(_profiles_artifact()))[0] == "CREATED"
    assert db.ingest(_bytes(_profiles_artifact(completed="2026-11-03T09:00:00Z")))[0] == "REUSED"
    assert [db.count(t) for t in ("source_contents", "source_captures", "source_analyses")] == [
        1, 2, 1]
    observations = _observations(db)
    assert len(observations) == 2 * len(_profiles_snapshot().claims)
    assert len({row[0] for row in observations}) == 2
    _assert_no_duplicate_observations(db)


def test_duplicate_orcid_claims_are_both_observed(db):
    db.activate("1", "1")
    db.ingest(_bytes(_profiles_artifact()))
    orcid = [r for r in _observations(db) if r[5] == "ORCID_DECLARED"]
    assert [r[6] for r in orcid] == [ORCID_A, ORCID_A]
    assert len({r[7] for r in orcid}) == 2   # two distinct source records


def test_claims_sharing_one_scopus_id_are_all_kept(db):
    db.activate("1", "1")
    db.ingest(_bytes(_guide_artifact()))
    db.ingest(_bytes(_multi_artifact()))
    shared_unowned = db.rows("SELECT claim_type FROM source_claim_observations "
                             "WHERE value_normalized = ? ORDER BY claim_type", sid(1))
    assert [r[0] for r in shared_unowned] == ["SCOPUS_ID_AMBIGUOUS", "SCOPUS_ID_UNASSIGNED"]
    owners = db.rows("SELECT subject_key FROM source_claim_observations "
                     "WHERE claim_type = 'SCOPUS_ID_OWNED' AND value_normalized = ? "
                     "ORDER BY subject_key", sid(5))
    assert [r[0] for r in owners] == ["gv1@example.invalid", "gv2@example.invalid"]
    _assert_no_duplicate_observations(db)


def test_invalid_rows_and_values_are_retained(db):
    db.activate("1", "1")
    db.ingest(_bytes(_guide_artifact()))
    invalid = db.rows("SELECT raw, validation_status FROM source_records "
                      "WHERE validation_status = 'INVALID'")
    assert [(json.loads(r[0]), r[1]) for r in invalid] == [(["Z", "57-BAD", "1"], "INVALID")]
    bad = db.rows("SELECT value_raw, value_normalized, value_valid FROM source_claims "
                  "WHERE value_raw = '57-BAD'")
    assert bad == [("57-BAD", None, 0)]


def test_stand_in_foreign_keys_reject_cross_analysis_claims(db):
    db.activate("1", "1")
    db.ingest(_bytes(_profiles_artifact()))
    record_id = db.rows("SELECT id FROM source_records LIMIT 1")[0][0]
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute("INSERT INTO source_claims (id, analysis_id, record_id, claim_type, "
                        "value_method, claim_key, flags, created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()), str(uuid.uuid4()), record_id, "EMAIL_DECLARED", "m",
                         "EMAIL_DECLARED|x|y", "{}", "t"))


def test_second_artifact_for_same_capture_and_version_is_impossible(db):
    db.activate("1", "1")
    db.ingest(_bytes(_profiles_artifact()))
    capture_id, content_id = db.rows("SELECT id, content_id FROM source_captures")[0]
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute("INSERT INTO source_artifacts (id, content_id, capture_id, "
                        "contract_version, artifact_bytes_sha256, ingested_at) "
                        "VALUES (?,?,?,?,?,?)",
                        (str(uuid.uuid4()), content_id, capture_id, "1.0", "c" * 64, "t"))
