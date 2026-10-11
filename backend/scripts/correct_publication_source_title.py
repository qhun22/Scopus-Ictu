"""Correct ``publications.source_title`` rows that hold the data-provider name.

Defect: the normalizer used to read the CSV column ``Source`` (the data provider,
always "Scopus") instead of ``Source title`` (the journal / proceedings / book
series).  Existing canonical rows are never overwritten by re-normalization
(``EXISTING_METADATA_CHANGED``), so already-stored rows need this one-off,
audited correction.

A row is corrected ONLY when every condition holds:

1. ``publications.source_title`` equals the defective value (default ``Scopus``)
   AND equals the raw ``Source`` value, i.e. it is the mapping defect and not a
   manual edit;
2. the publication has exactly one ``publication_raw_sources`` row and that raw
   record is linked to exactly one publication (1:1 provenance);
3. the raw record is VALID and belongs to a ``scopus_imports`` row in status
   APPLIED;
4. the raw ``Source title`` is non-blank (a blank value is never replaced by the
   provider name - the system's missing-data policy is NULL);
5. the raw EID (``eid_raw`` and the payload ``EID``) matches the publication EID.

It writes ``source_title`` and ``updated_at`` and lets the ORM version column
(``version_id_col``) increment ``version``; one SYSTEM audit event per source
import records the correction (no raw payload, no secrets).  Nothing else is
touched and no schema change is needed.  Re-running is a no-op.

Usage (from ``backend/``; DB_* environment variables as for the app)::

    python -m scripts.correct_publication_source_title --dry-run \\
        --expected-database <db> --expected-port <port>
    python -m scripts.correct_publication_source_title --apply \\
        --expected-database <db> --expected-port <port> \\
        --manifest <path-outside-repo>.json [--expected-updates N]

Exit codes: 0 ok / nothing to do, 2 refused by a guard, 3 source data changed,
5 failure (the transaction is rolled back; nothing is written).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.models.governance import AuditEvent
from app.models.publication import Publication
from app.services.matching.candidate_persistence import sha256_json
from app.services.normalization.scopus_normalizer import normalize_eid
from scripts.generate_matching_candidates import (
    EXIT_OK,
    EXIT_PERSIST_FAILED,
    CliRefused,
    SourceChanged,
    make_read_only_engine,
    validate_manifest_path,
    validate_target_url,
    verify_server_identity,
)

TOOL = "correct_publication_source_title/1"
WRONG_VALUE = "Scopus"
MANIFEST_SCHEMA_VERSION = 1

# Audit identity: a SYSTEM actor needs actor_service (CHECK ck_audit_events_actor_invariant);
# entity_type / action follow the formats enforced by the audit_events CHECK constraints.
AUDIT_ENTITY_TYPE = "scopus_imports"
AUDIT_ACTION = "SCOPUS_SOURCE_TITLE_CORRECTED"
AUDIT_ACTOR_SERVICE = "source_title_correction_cli"

# Skip reasons (stable codes, reported in the summary).
R_NOT_WRONG_VALUE = "NOT_WRONG_VALUE"
R_ALREADY_CORRECT = "ALREADY_CORRECT"
R_NO_RAW_SOURCE = "NO_RAW_SOURCE"
R_PROVENANCE_NOT_1TO1 = "PROVENANCE_NOT_1TO1"
R_IMPORT_NOT_APPLIED = "IMPORT_NOT_APPLIED"
R_RAW_NOT_VALID = "RAW_NOT_VALID"
R_EID_MISMATCH = "EID_MISMATCH"
R_STORED_NOT_PROVIDER_VALUE = "STORED_VALUE_NOT_PROVIDER_VALUE"
R_SOURCE_TITLE_MISSING = "RAW_SOURCE_TITLE_MISSING"
R_NO_CHANGE = "NO_CHANGE"


class VerificationFailed(Exception):
    """A post-update integrity check failed inside the transaction (rolled back)."""


# ── pure planning ─────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class SourceRow:
    """One publication joined with its raw provenance (read side)."""

    publication_id: uuid.UUID
    eid: str
    version: int
    current_source_title: str | None
    raw_record_id: uuid.UUID
    raw_eid: str | None
    payload_eid: str | None
    raw_validation_status: str | None
    import_id: uuid.UUID
    import_status: str | None
    raw_source: str | None
    raw_source_title: str | None
    publication_raw_link_count: int
    raw_record_link_count: int


@dataclass(frozen=True, slots=True)
class Correction:
    publication_id: uuid.UUID
    eid: str
    version: int
    old: str
    new: str
    import_id: uuid.UUID


@dataclass(slots=True)
class Plan:
    wrong_value: str
    wrong_total: int
    corrections: tuple[Correction, ...]
    skipped: Counter = field(default_factory=Counter)

    @property
    def fingerprint(self) -> str:
        return sha256_json(
            sorted([c.eid, c.old, c.new, str(c.import_id), c.version] for c in self.corrections)
        )

    def by_import(self) -> dict[str, int]:
        return dict(Counter(str(c.import_id) for c in self.corrections))

    def new_value_counts(self) -> Counter:
        return Counter(c.new for c in self.corrections)


def classify(row: SourceRow, wrong_value: str = WRONG_VALUE) -> tuple[str | None, str | None]:
    """Return ``(new_source_title, None)`` when correctable, else ``(None, reason)``."""
    current = (row.current_source_title or "").strip()
    new = (row.raw_source_title or "").strip()
    if current != wrong_value:
        return None, (R_ALREADY_CORRECT if new and current == new else R_NOT_WRONG_VALUE)
    if row.publication_raw_link_count != 1 or row.raw_record_link_count != 1:
        return None, R_PROVENANCE_NOT_1TO1
    if row.import_status != "APPLIED":
        return None, R_IMPORT_NOT_APPLIED
    if row.raw_validation_status != "VALID":
        return None, R_RAW_NOT_VALID
    if normalize_eid(row.raw_eid) != row.eid or (
        row.payload_eid is not None and normalize_eid(row.payload_eid) != row.eid
    ):
        return None, R_EID_MISMATCH
    if (row.raw_source or "").strip() != current:
        return None, R_STORED_NOT_PROVIDER_VALUE
    if not new:
        return None, R_SOURCE_TITLE_MISSING
    if new == current:
        return None, R_NO_CHANGE
    return new, None


def build_plan(rows: Sequence[SourceRow], wrong_total: int, wrong_value: str = WRONG_VALUE) -> Plan:
    plan = Plan(wrong_value=wrong_value, wrong_total=wrong_total, corrections=())
    seen: dict[uuid.UUID, int] = Counter()
    for row in rows:
        seen[row.publication_id] += 1
    corrections: list[Correction] = []
    reported_multi: set[uuid.UUID] = set()
    for row in sorted(rows, key=lambda r: (r.eid, str(r.raw_record_id))):
        if seen[row.publication_id] > 1:
            if row.publication_id not in reported_multi:
                reported_multi.add(row.publication_id)
                plan.skipped[R_PROVENANCE_NOT_1TO1] += 1
            continue
        new, reason = classify(row, wrong_value)
        if new is None:
            plan.skipped[reason or R_NOT_WRONG_VALUE] += 1
            continue
        corrections.append(
            Correction(row.publication_id, row.eid, row.version, row.current_source_title or "", new, row.import_id)
        )
    plan.corrections = tuple(corrections)
    plan.skipped[R_NO_RAW_SOURCE] += max(wrong_total - len(seen), 0)
    if not plan.skipped[R_NO_RAW_SOURCE]:
        del plan.skipped[R_NO_RAW_SOURCE]
    return plan


# ── database reads (also used inside the write transaction) ───────────────────
_ROWS_SQL = text(
    """
    SELECT p.id, p.eid, p.version, p.source_title,
           r.id, r.eid_raw, r.raw_payload ->> 'EID', r.validation_status,
           i.id, i.status,
           r.raw_payload ->> 'Source', r.raw_payload ->> 'Source title',
           (SELECT count(*) FROM publication_raw_sources s2 WHERE s2.publication_id = p.id),
           (SELECT count(*) FROM publication_raw_sources s3 WHERE s3.raw_record_id = r.id)
      FROM publications p
      JOIN publication_raw_sources s ON s.publication_id = p.id
      JOIN raw_scopus_records r ON r.id = s.raw_record_id
      JOIN scopus_imports i ON i.id = r.import_id
     WHERE p.source_title = :wrong
     ORDER BY p.eid, r.id
    """
)

# Every business column except the ones this tool is allowed to change.
_FINGERPRINT_SQL = text(
    """
    SELECT id, eid, doi, title, title_normalized, year, volume, issue, art_no, page_start,
           page_end, cited_by_count, document_type, publication_stage, open_access_status,
           created_at
      FROM publications ORDER BY id
    """
)


def load_plan(session: Session, wrong_value: str = WRONG_VALUE) -> Plan:
    rows = [SourceRow(*row) for row in session.execute(_ROWS_SQL, {"wrong": wrong_value}).all()]
    wrong_total = session.execute(
        text("SELECT count(*) FROM publications WHERE source_title = :wrong"), {"wrong": wrong_value}
    ).scalar_one()
    return build_plan(rows, wrong_total, wrong_value)


def untouched_columns_fingerprint(session: Session) -> str:
    return sha256_json([[str(v) for v in row] for row in session.execute(_FINGERPRINT_SQL).all()])


def table_counts(session: Session) -> dict[str, int]:
    names = [r[0] for r in session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1"))]
    return {n: session.execute(text(f'SELECT count(*) FROM "{n}"')).scalar_one() for n in names}


def source_title_profile(session: Session) -> dict[str, Any]:
    distinct = session.execute(text("SELECT count(DISTINCT source_title) FROM publications")).scalar_one()
    top = session.execute(
        text("SELECT source_title, count(*) FROM publications GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 3")
    ).all()
    versions = dict(session.execute(text("SELECT version, count(*) FROM publications GROUP BY 1 ORDER BY 1")).all())
    return {
        "distinct_source_titles": distinct,
        "top": [[t, n] for t, n in top],
        "versions": {str(k): v for k, v in versions.items()},
    }


# ── summary / dry-run ─────────────────────────────────────────────────────────
def summarize(plan: Plan) -> dict[str, Any]:
    new_counts = plan.new_value_counts()
    return {
        "wrong_value": plan.wrong_value,
        "publications_with_wrong_value": plan.wrong_total,
        "eligible": len(plan.corrections),
        "skipped": dict(plan.skipped),
        "by_import": plan.by_import(),
        "distinct_new_source_titles": len(new_counts),
        "projected_top": [[t, n] for t, n in new_counts.most_common(3)],
        "sample": [
            {"eid": c.eid, "old": c.old, "new": c.new, "version": f"{c.version}->{c.version + 1}"}
            for c in plan.corrections[:5]
        ],
        "plan_sha256": plan.fingerprint,
    }


# ── apply ─────────────────────────────────────────────────────────────────────
def _write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _audit_event(import_id: str, count: int, plan: Plan, distinct_new: int) -> AuditEvent:
    return AuditEvent(
        entity_type=AUDIT_ENTITY_TYPE,
        entity_id=uuid.UUID(import_id),
        action=AUDIT_ACTION,
        actor_type="SYSTEM",
        actor_user_id=None,
        actor_service=AUDIT_ACTOR_SERVICE,
        before_state={"field": "publications.source_title", "value": plan.wrong_value, "publications": count},
        after_state={"field": "publications.source_title", "value": "Source title", "publications": count,
                     "distinct_source_titles_in_run": distinct_new},
        reason="Correct source_title mapped from CSV column 'Source' (data provider) instead of 'Source title'.",
        event_metadata={
            "import_id": import_id,
            "tool": TOOL,
            "publications_updated": count,
            "plan_sha256": plan.fingerprint,
            "from_column": "Source",
            "to_column": "Source title",
        },
    )


def apply_corrections(
    reader: Engine,
    writer: Engine,
    *,
    database: str,
    manifest_path: Path,
    expected_updates: int | None = None,
    wrong_value: str = WRONG_VALUE,
) -> dict[str, Any]:
    with Session(reader) as session:
        plan = load_plan(session, wrong_value)
        session.rollback()
    if not plan.corrections:
        return {"status": "NOOP", "reason": "no publication matches the correction rule", **summarize(plan)}
    if manifest_path.exists():
        raise CliRefused(
            "manifest already exists; a manifest from an earlier plan must not be reused "
            "(keep it as evidence and use a new path)"
        )
    if expected_updates is not None and len(plan.corrections) != expected_updates:
        raise CliRefused(f"expected {expected_updates} updates but the rule selects {len(plan.corrections)}")

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "tool": TOOL,
        "database": database,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "PLANNED",
        "plan": summarize(plan),
        "result": None,
        "error": None,
    }
    _write_manifest(manifest_path, manifest)  # recoverable evidence BEFORE touching the DB

    now = datetime.now(UTC)
    try:
        with Session(writer) as session:  # fresh session: one atomic transaction
            # Lock every candidate row, then re-plan inside the transaction: the world must be
            # exactly what was planned.
            session.execute(
                text("SELECT id FROM publications WHERE source_title = :w ORDER BY id FOR UPDATE"),
                {"w": wrong_value},
            )
            replan = load_plan(session, wrong_value)
            if replan.fingerprint != plan.fingerprint:
                raise SourceChanged("source data changed between planning and the locked re-check")

            fingerprint_before = untouched_columns_fingerprint(session)
            counts_before = table_counts(session)
            profile_before = source_title_profile(session)

            publications = {
                p.id: p
                for p in session.scalars(
                    select(Publication).where(Publication.id.in_([c.publication_id for c in plan.corrections]))
                )
            }
            if len(publications) != len(plan.corrections):
                raise SourceChanged("a planned publication no longer exists")
            for c in plan.corrections:
                pub = publications[c.publication_id]
                if pub.source_title != c.old or pub.version != c.version:
                    raise SourceChanged("a planned publication changed")
                pub.source_title = c.new
                pub.updated_at = now
            session.flush()  # UPDATE ... WHERE version = <old>; the ORM bumps version (version_id_col)

            per_import = plan.by_import()
            for import_id, count in sorted(per_import.items()):
                session.add(_audit_event(import_id, count, plan, len(plan.new_value_counts())))
            session.flush()

            # ── in-transaction verification: any failure rolls everything back ──
            problems: list[str] = []
            for c in plan.corrections:
                pub = publications[c.publication_id]
                if pub.version != c.version + 1:
                    problems.append("version not incremented by exactly 1")
                    break
            db_rows = {
                r[0]: (r[1], r[2], r[3])
                for r in session.execute(
                    text("SELECT id, source_title, version, updated_at FROM publications WHERE id = ANY(:ids)"),
                    {"ids": [c.publication_id for c in plan.corrections]},
                ).all()
            }
            for c in plan.corrections:
                title, version, updated_at = db_rows[c.publication_id]
                if title != c.new or version != c.version + 1 or updated_at != now:
                    problems.append("stored row does not match the plan")
                    break
            if untouched_columns_fingerprint(session) != fingerprint_before:
                problems.append("a business column other than source_title changed")
            counts_after = table_counts(session)
            expected_counts = dict(counts_before)
            expected_counts["audit_events"] = counts_before["audit_events"] + len(per_import)
            if counts_after != expected_counts:
                problems.append("row counts differ from the expected result")
            remaining = session.execute(
                text("SELECT count(*) FROM publications WHERE source_title = :w"), {"w": wrong_value}
            ).scalar_one()
            if remaining != plan.wrong_total - len(plan.corrections):
                problems.append("unexpected number of rows still holding the defective value")
            if problems:
                raise VerificationFailed("; ".join(sorted(set(problems))))
            profile_after = source_title_profile(session)
            session.commit()
    except Exception as exc:
        manifest.update(status="FAILED", error=f"{type(exc).__name__}: {exc}" if isinstance(exc, (CliRefused, VerificationFailed)) else type(exc).__name__)
        _write_manifest(manifest_path, manifest)
        raise

    result = {
        "status": "COMPLETED",
        "updated": len(plan.corrections),
        "audit_events_written": len(per_import),
        "profile_before": profile_before,
        "profile_after": profile_after,
        "table_deltas": {k: counts_after[k] - counts_before[k] for k in counts_after if counts_after[k] != counts_before[k]},
        "business_columns_unchanged": True,
    }
    manifest.update(status="COMPLETED", result=result, error=None)
    _write_manifest(manifest_path, manifest)
    return result


# ── entry point ───────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m scripts.correct_publication_source_title",
        description="Correct publications.source_title rows that hold the data-provider name.",
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="read-only; writes nothing")
    mode.add_argument("--apply", action="store_true", help="apply the correction in one transaction")
    p.add_argument("--expected-database", required=True)
    p.add_argument("--expected-port", type=int, default=None, help="5432 is always refused")
    p.add_argument("--manifest", type=Path, default=None, help="JSON manifest OUTSIDE the repo (required for --apply)")
    p.add_argument("--expected-updates", type=int, default=None, help="refuse unless exactly N rows are selected")
    p.add_argument("--wrong-value", default=WRONG_VALUE, help="defective value to correct (default: Scopus)")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from app.core.config import settings

        url = URL.create(
            drivername="postgresql+psycopg2",
            username=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
        )
        validate_target_url(url, args.expected_database, args.expected_port)
        manifest_path = validate_manifest_path(args.manifest) if args.manifest else None
        if args.apply and manifest_path is None:
            raise CliRefused("--apply requires --manifest (stored outside the repository)")

        reader = make_read_only_engine(url)
        identity = verify_server_identity(reader, args.expected_database, args.expected_port)
        print(f"target: database={identity['database']} port={identity['port']} addr={identity['address']} user={identity['user']}")

        if args.dry_run:
            with Session(reader) as session:
                if session.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
                    raise CliRefused("reader session is not read-only")
                before_counts = table_counts(session)
                profile_before = source_title_profile(session)
                plan = load_plan(session, args.wrong_value)
                unchanged = table_counts(session) == before_counts
                session.rollback()
            out = {"mode": "dry-run", "plan": summarize(plan), "before": profile_before, "tables_unchanged": unchanged}
            print(json.dumps(out, ensure_ascii=False, sort_keys=True))
            return EXIT_OK

        writer = create_engine(url, pool_pre_ping=True)
        try:
            verify_server_identity(writer, args.expected_database, args.expected_port)
            result = apply_corrections(
                reader,
                writer,
                database=args.expected_database,
                manifest_path=manifest_path,
                expected_updates=args.expected_updates,
                wrong_value=args.wrong_value,
            )
        finally:
            writer.dispose()
        print(json.dumps({"mode": "apply", "result": result}, ensure_ascii=False, sort_keys=True, default=str))
        return EXIT_OK
    except CliRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return exc.exit_code
    except VerificationFailed as exc:
        print(f"FAILED: verification: {exc}", file=sys.stderr)
        return EXIT_PERSIST_FAILED
    except Exception as exc:  # fail closed; the transaction was rolled back and no secret is echoed
        print(f"FAILED: {type(exc).__name__}", file=sys.stderr)
        return EXIT_PERSIST_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
