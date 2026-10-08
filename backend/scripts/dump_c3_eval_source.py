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
transaction is rolled back, all owned partial/staging files are deleted, and
no metadata is written.

**R4**: archive and metadata output paths are rejected if they resolve to the
same filesystem object (checked via ``Path.resolve`` and ``os.stat`` inode
comparison for symlinks).  This check runs before any session is opened.

**R5**: metadata is written atomically via a staging tempfile (flush+fsync)
and promoted with ``os.link`` (exclusive no-clobber).  If metadata promotion
fails after archive promotion, the archive is also removed.

**R6**: archive promotion uses ``os.link`` (exclusive no-clobber).

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

    # R4: reject same-path before opening any session.
    if sd._same_path(archive, metadata_out):
        _emit_error("archive-out and metadata-out must not refer to the same path.")
        return 1

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
    result = None
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

    if result is None:
        _emit_error("Source dump did not complete.")
        return 1

    # R5: write metadata via staging tempfile, promote with os.link (no-clobber).
    import os

    payload = result.metadata(archive.name)
    content = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    # Verify archive is still present before publishing metadata.
    if not archive.is_file():
        _emit_error("Archive disappeared before metadata could be written.")
        return 1

    meta_staging = None
    try:
        meta_staging = sd.write_metadata_atomic(content, metadata_out)
        sd.exclusive_promote(meta_staging, metadata_out)
        meta_staging = None  # successfully promoted; no longer needs cleanup
    except sd.SourceDumpError as exc:
        _emit_error(f"Metadata publication failed: {exc}")
        # Archive was promoted; remove it since metadata was not published.
        cleanup = sd.cleanup_owned_artifacts([archive])
        if cleanup.incomplete:
            _emit_error(f"Archive cleanup also incomplete — {cleanup.summary()}.")
        return 1
    except OSError:
        _emit_error("Metadata write failed.")
        cleanup = sd.cleanup_owned_artifacts([archive])
        if cleanup.incomplete:
            _emit_error(f"Archive cleanup also incomplete — {cleanup.summary()}.")
        return 1
    finally:
        if meta_staging is not None:
            sd.cleanup_owned_artifacts([meta_staging])

    print(json.dumps(payload, ensure_ascii=False, indent=2))
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
