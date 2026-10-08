"""CLI: source-snapshot dump for the C3 evaluation database (C3-A3 P1).

Single mode.  In ONE open ``REPEATABLE READ READ ONLY`` transaction on the
allowlisted source database (``scopus_ictu_acceptance_v2`` only) it verifies
the live database and Alembic revision, computes the evaluation-input
fingerprint v1, exports the snapshot, runs ``pg_dump --snapshot`` for exactly
the nine contracted tables, checks the archive ToC, and only then closes the
transaction.  There is no separate fingerprint-then-dump path, and no path to
``evaluate``.

Credentials come only from ``DB_*`` settings and reach ``pg_dump`` only via
the child process environment.  Database errors, URLs, hosts and the
database name are never printed.

On success writes the archive and a metadata JSON (Alembic revision, snapshot
id, archive SHA-256, nine row counts, fingerprint v1).  On any failure the
transaction is rolled back, the partial archive is deleted, and no metadata
is written.

Exit codes: 0 success, 1 verification/environment/database/dump error,
2 usage/file/import error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _emit_error(message: str) -> None:
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="C3 evaluation source-snapshot dump (C3-A3 P1).")
    parser.add_argument("--archive-out", required=True, help="pg_dump custom-format archive to create.")
    parser.add_argument("--metadata-out", required=True, help="Metadata JSON to create.")
    parser.add_argument("--pg-dump", default="pg_dump")
    parser.add_argument("--pg-restore", default="pg_restore")
    return parser


def run(args: argparse.Namespace) -> int:
    from app.core.config import settings
    from app.services.matching import eval_source_dump as sd
    from app.services.matching import verified_evaluation as ve

    archive = Path(args.archive_out)
    metadata_out = Path(args.metadata_out)
    for path in (archive, metadata_out, sd.partial_path_for(archive)):
        if path.exists():
            _emit_error(f"Refusing to overwrite existing file: {path.name}")
            return 1
    if not archive.parent.is_dir() or not metadata_out.parent.is_dir():
        _emit_error("Output directory does not exist.")
        return 2

    if settings.environment.lower() == "prod":
        _emit_error("Refused: environment=prod.")
        return 1
    if not sd.is_source_database(settings.database_url):
        _emit_error("Configured database is not the allowlisted source database.")
        return 1

    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    params = sd.ConnectionParams(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )
    engine = create_engine(settings.database_url)
    try:
        with Session(engine) as session:
            result = sd.dump_source_snapshot(
                session,
                params=params,
                archive_path=archive,
                pg_dump=args.pg_dump,
                pg_restore=args.pg_restore,
            )
    except (sd.SourceDumpError, ve.VerificationError) as exc:
        _emit_error(f"Source dump failed: {exc}")
        return 1
    except SQLAlchemyError:
        _emit_error("Source database access failed safely.")
        return 1
    finally:
        engine.dispose()

    payload = result.metadata(archive.name)
    text_out = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        metadata_out.write_text(text_out + "\n", encoding="utf-8")
    except OSError:
        # An archive without its metadata is not a published copy.
        archive.unlink(missing_ok=True)
        _emit_error("Could not write metadata; archive removed.")
        return 1
    print(text_out)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return run(args)
    except ImportError as exc:
        _emit_error(f"Import failed: {exc}. Run from repo root with backend/ on PYTHONPATH.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
