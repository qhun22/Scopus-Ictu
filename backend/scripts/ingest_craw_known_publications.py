"""Ingest ICTU-Craw lecturer<->publication links as known-publication evidence.

Converts the frozen Craw artifacts (``lecturers.json``, ``publications.json``,
``lecturer_publication_links.json``) into ``CrawLecturerSource`` objects and
hands them to the existing ``KnownPublicationIngestionService``.  It does not
match lecturers by name (the service maps by profile URL), never touches the
``lecturers`` table, Scopus canonical data, candidates or identities, and a
known publication is *not* a confirmation of any Scopus Author ID.

Only lecturers that appear in ``lecturer_publication_links.json`` are
ingested; every attribution is a link that exists in that file.

Usage (from ``backend/``; DB_* environment variables as for the app)::

    python -m scripts.ingest_craw_known_publications --dry-run \\
        --craw-dir <Craw/output/full> --expected-database <db> --expected-port <port>
    python -m scripts.ingest_craw_known_publications --apply \\
        --craw-dir <Craw/output/full> --expected-database <db> --expected-port <port> \\
        --manifest <path-outside-repo>.json

Exit codes: 0 ok, 2 refused by a guard / unresolved source data, 5 failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.services.lecturer_dataset.known_publication_ingestion import (
    CrawLecturerSource,
    CrawPublicationAttribution,
    KnownPublicationIngestionService,
)
from scripts.generate_matching_candidates import (
    EXIT_OK,
    EXIT_PERSIST_FAILED,
    CliRefused,
    make_read_only_engine,
    validate_manifest_path,
    validate_target_url,
    verify_server_identity,
)

CRAW_FILES = ("lecturers.json", "publications.json", "lecturer_publication_links.json")
_YEAR_RE = re.compile(r"\d{4}")


@dataclass(slots=True)
class CrawInput:
    sources: list[CrawLecturerSource]
    stats: dict[str, Any]
    problems: list[dict[str, str]] = field(default_factory=list)
    file_sha256: dict[str, str] = field(default_factory=dict)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _year(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and _YEAR_RE.fullmatch(value.strip()):
        return int(value.strip())
    return None


def build_sources(craw_dir: Path) -> CrawInput:
    """Pure conversion of the three Craw artifacts; no database access."""
    sha = {name: hashlib.sha256((craw_dir / name).read_bytes()).hexdigest() for name in CRAW_FILES}
    lecturers = {row["source_id"]: row for row in _load(craw_dir / "lecturers.json")}
    publications = {row["source_id"]: row for row in _load(craw_dir / "publications.json")}
    links = _load(craw_dir / "lecturer_publication_links.json")

    problems: list[dict[str, str]] = []
    per_lecturer: dict[str, list[dict]] = {}
    for link in links:
        lid, pid = link.get("lecturer_source_id"), link.get("target_source_id")
        if lid not in lecturers:
            problems.append({"code": "LINK_UNKNOWN_LECTURER", "lecturer_source_id": str(lid), "target_source_id": str(pid)})
            continue
        if pid not in publications:
            problems.append({"code": "LINK_UNKNOWN_PUBLICATION", "lecturer_source_id": str(lid), "target_source_id": str(pid)})
            continue
        per_lecturer.setdefault(lid, []).append(link)

    sources: list[CrawLecturerSource] = []
    year_unparsed = 0
    for lid in sorted(per_lecturer):
        record = lecturers[lid]
        attributions = []
        for link in per_lecturer[lid]:
            pub = publications[link["target_source_id"]]
            year = _year(pub.get("year"))
            if pub.get("year") not in (None, "") and year is None:
                year_unparsed += 1
            attributions.append(
                CrawPublicationAttribution(
                    source_publication_url=link["target_source_id"],
                    title_raw=pub.get("title"),
                    doi_raw=pub.get("doi") or None,
                    published_year=year,
                )
            )
        payload = dict(record)
        # Link-level provenance is kept verbatim inside the immutable snapshot payload.
        payload["_known_publication_links"] = {
            "source_files": sha,
            "links": per_lecturer[lid],
        }
        sources.append(CrawLecturerSource(lid, str(record.get("full_name") or ""), payload, tuple(attributions)))

    pairs = Counter((l["lecturer_source_id"], l["target_source_id"]) for rows in per_lecturer.values() for l in rows)
    stats = {
        "craw_lecturers": len(lecturers),
        "craw_publications": len(publications),
        "craw_links": len(links),
        "links_resolved": sum(len(v) for v in per_lecturer.values()),
        "links_unresolved": len(problems),
        "lecturers_with_links": len(per_lecturer),
        "distinct_publications_linked": len({l["target_source_id"] for rows in per_lecturer.values() for l in rows}),
        "duplicate_link_pairs": sum(1 for n in pairs.values() if n > 1),
        "link_relationship_sources": dict(Counter(l.get("relationship_source") for rows in per_lecturer.values() for l in rows)),
        "attributions_with_doi": sum(1 for s in sources for a in s.publication_attributions if a.doi_raw),
        "attributions_without_year": sum(1 for s in sources for a in s.publication_attributions if a.published_year is None),
        "year_unparsed": year_unparsed,
    }
    return CrawInput(sources, stats, problems, sha)


def preview_summary(preview) -> dict[str, Any]:
    keys = (
        "source_lecturer_count", "source_publication_attribution_count", "mapped_lecturer_count",
        "unmapped_lecturer_count", "ambiguous_lecturer_count", "snapshots_to_create",
        "snapshots_already_present", "known_publications_to_create", "known_publications_already_present",
        "source_duplicates_within_snapshot", "invalid_records", "conflicts",
        "source_urls_collapsed_into_existing_record",
    )
    out = {k: getattr(preview, k) for k in keys}
    out["error_codes"] = dict(Counter(e.code for e in preview.errors))
    return out


def table_counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        names = [r[0] for r in conn.execute(text("select tablename from pg_tables where schemaname='public' order by 1"))]
        out = {n: conn.execute(text(f'select count(*) from "{n}"')).scalar_one() for n in names}
        conn.rollback()
    return out


def run_preview(reader: Engine, data: CrawInput):
    with Session(reader) as session:
        if session.execute(text("show transaction_read_only")).scalar_one() != "on":
            raise CliRefused("reader session is not read-only")
        preview = KnownPublicationIngestionService().preview(session, data.sources)
        session.rollback()
    return preview


def blocking_problems(data: CrawInput, preview) -> list[str]:
    out = []
    if data.problems:
        out.append(f"{len(data.problems)} Craw links do not resolve to a lecturer/publication record")
    if preview.unmapped_lecturer_count:
        out.append(f"{preview.unmapped_lecturer_count} lecturers are unmapped")
    if preview.ambiguous_lecturer_count:
        out.append(f"{preview.ambiguous_lecturer_count} lecturers are ambiguous")
    if preview.invalid_records:
        out.append(f"{preview.invalid_records} invalid records")
    if preview.conflicts:
        out.append(f"{preview.conflicts} conflicts")
    return out


def apply_ingestion(reader: Engine, writer: Engine, data: CrawInput, manifest_path: Path, database: str) -> dict[str, Any]:
    preview = run_preview(reader, data)
    problems = blocking_problems(data, preview)
    if problems:
        raise CliRefused("; ".join(problems))
    before = table_counts(reader)
    manifest = {
        "schema_version": 1, "database": database, "created_at": datetime.now(UTC).isoformat(), "status": "PLANNED",
        "source_files": data.file_sha256, "stats": data.stats, "preview": preview_summary(preview), "result": None,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    session = Session(writer)  # fresh session; the service commits/rolls back itself
    try:
        result = KnownPublicationIngestionService().apply(session, data.sources)
    except Exception as exc:
        manifest.update(status="FAILED", result={"error": type(exc).__name__})
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        raise
    finally:
        session.close()
    after = table_counts(reader)
    delta = {k: after[k] - before[k] for k in after if after[k] != before[k]}
    summary = {
        "snapshots_created": result.snapshots_created, "snapshots_reused": result.snapshots_reused,
        "known_publications_created": result.known_publications_created, "known_publications_reused": result.known_publications_reused,
        "source_duplicates_collapsed": result.source_duplicates_collapsed,
        "source_urls_collapsed": result.source_urls_collapsed, "invalid_records": result.invalid_records,
        "unmapped": len(result.unmapped_lecturers), "table_deltas": delta,
    }
    manifest.update(status="COMPLETED", result=summary)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.ingest_craw_known_publications")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    p.add_argument("--craw-dir", type=Path, required=True)
    p.add_argument("--expected-database", required=True)
    p.add_argument("--expected-port", type=int, default=None)
    p.add_argument("--manifest", type=Path, default=None)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from app.core.config import settings

        url = URL.create("postgresql+psycopg2", username=settings.db_user, password=settings.db_password,
                         host=settings.db_host, port=settings.db_port, database=settings.db_name)
        validate_target_url(url, args.expected_database, args.expected_port)
        manifest_path = validate_manifest_path(args.manifest) if args.manifest else None
        if args.apply and manifest_path is None:
            raise CliRefused("--apply requires --manifest (stored outside the repository)")
        data = build_sources(args.craw_dir)
        reader = make_read_only_engine(url)
        ident = verify_server_identity(reader, args.expected_database, args.expected_port)
        print(f"target: database={ident['database']} port={ident['port']} addr={ident['address']}")
        if args.dry_run:
            before = table_counts(reader)
            preview = run_preview(reader, data)
            print(json.dumps({"mode": "dry-run", "craw": data.stats, "unresolved_links": data.problems[:10],
                              "preview": preview_summary(preview), "blocking": blocking_problems(data, preview),
                              "tables_unchanged": table_counts(reader) == before}, sort_keys=True))
            return EXIT_OK
        writer = create_engine(url, pool_pre_ping=True)
        try:
            verify_server_identity(writer, args.expected_database, args.expected_port)
            summary = apply_ingestion(reader, writer, data, manifest_path, args.expected_database)
        finally:
            writer.dispose()
        print(json.dumps({"mode": "apply", "result": summary}, sort_keys=True))
        return EXIT_OK
    except CliRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}", file=sys.stderr)
        return EXIT_PERSIST_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
