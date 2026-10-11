"""Import author-level affiliation resolutions from the Task 10 survey files.

The survey directory (kept OUTSIDE Git) holds the downloaded OpenAlex /
Crossref / ORCID metadata and ``author_affiliation_links.jsonl``.  This CLI

* rebuilds every link from the RAW metadata with the committed alignment module,
* requires each JSONL row to agree with that recomputation (otherwise it
  refuses to apply: stale or tampered input),
* hands the result to ``AffiliationImportService`` (preview / apply).

It writes only the three affiliation tables; it never creates Scopus authors,
publication authors, identities or candidates.

Usage (from ``backend/``; DB_* variables as for the app)::

    python -m scripts.import_author_affiliations --dry-run --survey-dir <dir> \\
        --scopus-csv <csv> --expected-database <db> --expected-port <port>
    python -m scripts.import_author_affiliations --apply   ... --manifest <outside-repo>.json

Exit codes: 0 ok, 2 refused by a guard / input mismatch, 5 failure.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.services.affiliation_import import AffiliationImportService, EntryInput
from app.services.affiliation_sources import (
    BuiltInput,
    entries_of,
    sha256_file,
)
from app.services.affiliation_sources import build_inputs as bundle_build_inputs
from app.services.author_affiliation import AuthorAffiliationLink
from scripts.generate_matching_candidates import (
    EXIT_OK,
    EXIT_PERSIST_FAILED,
    CliRefused,
    make_read_only_engine,
    validate_manifest_path,
    validate_target_url,
    verify_server_identity,
)

SURVEY_FILES = (
    "openalex_works.jsonl",
    "crossref_works.jsonl",
    "orcid_external_ids.json",
    "author_affiliation_links.jsonl",
)


def _sha(path: Path) -> str:
    return sha256_file(path)


def _entries(link: AuthorAffiliationLink) -> tuple[EntryInput, ...]:
    return entries_of(link)


def build_inputs(survey_dir: Path, scopus_csv: Path) -> BuiltInput:
    """CLI wrapper: CSV rows from disk + the shared bundle logic (JSONL cross-check required)."""

    with scopus_csv.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    built = bundle_build_inputs(survey_dir, rows, require_expected=True, strict_cross_check=True)
    built.file_sha256["scopus_csv"] = _sha(scopus_csv)
    return built


def _identity_report(reader, database: str, port: int | None) -> dict[str, Any]:
    return verify_server_identity(reader, database, port)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.import_author_affiliations")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    p.add_argument("--survey-dir", type=Path, required=True)
    p.add_argument("--scopus-csv", type=Path, required=True)
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
        built = build_inputs(args.survey_dir, args.scopus_csv)
        reader = make_read_only_engine(url)
        ident = _identity_report(reader, args.expected_database, args.expected_port)
        print(f"target: database={ident['database']} port={ident['port']} addr={ident['address']}")
        with Session(reader) as session:
            if session.execute(text("show transaction_read_only")).scalar_one() != "on":
                raise CliRefused("reader session is not read-only")
            report = AffiliationImportService().preview(session, built.inputs)
            session.rollback()
        summary = {"input": built.stats, "source_mismatches": len(built.mismatches), "preview": report.as_dict()}
        if args.dry_run:
            print(json.dumps({"mode": "dry-run", **summary}, sort_keys=True))
            return EXIT_OK
        if built.mismatches:
            raise CliRefused(f"{len(built.mismatches)} JSONL rows disagree with the recomputation from raw metadata")
        writer = create_engine(url, pool_pre_ping=True)
        try:
            verify_server_identity(writer, args.expected_database, args.expected_port)
            with Session(writer) as session:  # fresh session, no prior statements
                applied = AffiliationImportService().apply(session, built.inputs)
        finally:
            writer.dispose()
        manifest = {"schema_version": 1, "database": args.expected_database, "source_files": built.file_sha256,
                    "input": built.stats, "result": applied.as_dict()}
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"mode": "apply", "result": applied.as_dict()}, sort_keys=True))
        return EXIT_OK
    except CliRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}", file=sys.stderr)
        return EXIT_PERSIST_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
