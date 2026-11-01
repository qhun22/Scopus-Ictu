"""Shared synthetic builders for the E3-P2-B2 staging tests (unit SQLite mirror and PostgreSQL).

Synthetic values only: ``example.invalid`` domains, fake 570000000xx Scopus IDs and ORCID's own
documentation iD. The structures copy the real Craw harvest and guide snapshots.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import (
    JSON,
    Column,
    Computed,
    ForeignKeyConstraint,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    create_engine,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models import source_staging as staging
from app.services.source_claims.provenance import MANIFEST_NAME, harvest_semantic_hash

REPO = "https://repository.example.invalid"
GUIDE = f"{REPO}/huong-dan-gop-tai-khoan-scopus/"
ORCID_A = "0000-0002-1825-0097"
STAGING = set(staging.STAGING_TABLES)
PASSES = ("A_cached_write", "B_cached_replay", "C_offline_replay")
HEADER = ["Tên trên Scopus", "Scopus ID", "Số bài"]


def sid(n: int) -> str:
    return str(57000000000 + n)


# ---------------------------------------------------------------------------
# SQLite mirror of the application schema (unit tests only)
# ---------------------------------------------------------------------------

def _default(column):
    default = column.server_default
    if default is None or not hasattr(default, "arg"):
        return None
    sql = str(getattr(default.arg, "text", default.arg))
    if sql == "now()":
        return text("CURRENT_TIMESTAMP")
    if "gen_random_uuid" in sql or "::" in sql or "(" in sql:
        return None
    return text(sql)


def _mirror(metadata: MetaData) -> MetaData:
    """Every table with generic types, its UNIQUE constraints and staging-internal FKs; no
    PostgreSQL CHECKs, partial indexes or FKs into non-staging tables."""
    mirror = MetaData()
    for table in metadata.sorted_tables:
        columns = []
        for col in table.columns:
            ctype = col.type
            if isinstance(ctype, JSONB):
                ctype = JSON()
            elif isinstance(ctype, INET):
                ctype = String(64)
            elif type(ctype).__name__ == "UUID":
                ctype = Uuid()
            extra = [Computed(col.computed.sqltext, persisted=True)] if col.computed else []
            columns.append(Column(col.name, ctype, *extra, primary_key=col.primary_key,
                                  nullable=col.nullable or col.identity is not None,
                                  server_default=None if col.computed else _default(col)))
        constraints = [UniqueConstraint(*[c.name for c in uq.columns])
                       for uq in table.constraints if isinstance(uq, UniqueConstraint)]
        if table.name in STAGING:
            constraints += [
                ForeignKeyConstraint([c.name for c in fk.columns],
                                     [f"{fk.referred_table.name}.{e.column.name}"
                                      for e in fk.elements])
                for fk in table.constraints
                if isinstance(fk, ForeignKeyConstraint) and fk.referred_table.name in STAGING]
        Table(table.name, mirror, *columns, *constraints)
    return mirror


def make_sqlite_engine(url: str = "sqlite://"):
    kwargs = {"poolclass": StaticPool} if url == "sqlite://" else {}
    engine = create_engine(url, connect_args={"check_same_thread": False}, **kwargs)

    @event.listens_for(engine, "connect")
    def _connect(dbapi_connection, _record):
        dbapi_connection.isolation_level = None   # let SQLAlchemy own BEGIN/SAVEPOINT
        dbapi_connection.execute("PRAGMA foreign_keys = ON")

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    _mirror(Base.metadata).create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(   # stands in for PostgreSQL's GENERATED ALWAYS AS IDENTITY
            "CREATE TRIGGER source_rule_sets_identity AFTER INSERT ON source_rule_sets "
            "WHEN NEW.sequence_no IS NULL BEGIN UPDATE source_rule_sets SET sequence_no = "
            "(SELECT COALESCE(MAX(sequence_no), 0) + 1 FROM source_rule_sets) "
            "WHERE id = NEW.id; END")
        conn.exec_driver_sql(f"CREATE VIEW {staging.SOURCE_CAPTURE_ANALYSES_VIEW} AS "
                             f"{staging.SOURCE_CAPTURE_ANALYSES_SQL}")
        conn.exec_driver_sql(f"CREATE VIEW {staging.SOURCE_CLAIM_OBSERVATIONS_VIEW} AS "
                             f"{staging.SOURCE_CLAIM_OBSERVATIONS_SQL}")
    return engine


# ---------------------------------------------------------------------------
# Synthetic sources shaped like the real Craw harvest and guide snapshots
# ---------------------------------------------------------------------------

def lecturer(n, *, orcid=None, name=None, email=None):
    url = f"{REPO}/giang-vien/synthetic-{n}/"
    name, email = name or f"Synthetic Lecturer {n}", email or f"lecturer{n}@example.invalid"
    labels = {"Họ và tên": name, "Email": email}
    if orcid:
        labels["ORCID"] = f"{orcid} ↗"
    return {"source_id": url, "profile_url": url, "full_name": name,
            "institutional_email": email, "orcid": orcid, "public_publication_links": [],
            "counts": {"article_count": 0}, "source_fields": labels,
            "provenance": {"source_url": url, "retrieved_at": "2026-10-03T18:44:10Z"}}


def encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _combined(file_hashes):
    return hashlib.sha256(json.dumps(file_hashes, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def harvest(items, *, completed="2026-10-03T21:31:10Z", failures=(), encoder=encode):
    """Files exactly as the harvester writes them, including the three-pass semantic replay."""
    crawl = {"source_entity_failures": [{"entity_type": t} for t in failures]}
    manifest = {"harvest_started_at": "2026-10-03T20:05:14Z", "harvest_completed_at": completed,
                "source_base_url": REPO, "parser_version": "synthetic",
                "source_card_count": len(items), "lecturer_count": len(items),
                "status": "COMPLETE_WITH_SOURCE_FAILURES" if failures else "COMPLETE",
                "source_drift_detected": False,
                "semantic_file_hashes": {"lecturers.json": harvest_semantic_hash(items),
                                         "crawl_report.json": harvest_semantic_hash(crawl)}}
    files = {"lecturers.json": harvest_semantic_hash(items),
             "crawl_report.json": harvest_semantic_hash(crawl),
             MANIFEST_NAME: harvest_semantic_hash(manifest)}
    runs = {run: dict(files) for run in PASSES}
    combined = {run: _combined(h) for run, h in runs.items()}
    replay = {"file_hashes": runs, "combined_hashes": combined,
              "combined_hash": combined[PASSES[0]], "a_equals_b_equals_c": True,
              "differing_files": []}
    lecturers_bytes = encoder(items)
    return {"lecturers_bytes": lecturers_bytes,
            "lecturers_sha256": hashlib.sha256(lecturers_bytes).hexdigest(),
            "manifest_bytes": encode(manifest), "replay_bytes": encode(replay),
            "crawl_report_bytes": encode(crawl)}


def tables_snapshot(ambiguous=(), unassigned=(), *, ts="2026-10-29T01:37:29Z"):
    snapshot = {"ts": ts, "url": GUIDE, "n_tables_total": 3,
                "section_headings": {"1": "Scopus ID nhập nhằng — synthetic",
                                     "2": "Scopus ID chưa xác định chủ sở hữu — synthetic"},
                "tables": [{"ti": 1, "rows": [HEADER, *map(list, ambiguous)]},
                           {"ti": 2, "rows": [HEADER, *map(list, unassigned)]}]}
    data = encode(snapshot)
    return {"snapshot_bytes": data, "snapshot_sha256": hashlib.sha256(data).hexdigest(),
            "layout": "TABLES"}


def multi_snapshot(rows, *, ts="2026-10-29T00:32:28Z"):
    data = encode({"ts": ts, "url": GUIDE, "multi_id_rows": len(rows), "rows": rows})
    return {"snapshot_bytes": data, "snapshot_sha256": hashlib.sha256(data).hexdigest(),
            "layout": "MULTI_ID"}


def multi_row(n, ids, primary=None):
    return [f"GV {n}", f"gv{n}@example.invalid", str(len(ids)), "1", primary or ids[0],
            "; ".join(ids)]
