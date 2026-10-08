"""Source-snapshot dump orchestrator for the C3 evaluation database (C3-A3 P1).

Binds the evaluation-input fingerprint v1 to a ``pg_dump`` archive of the
nine contracted tables.  An exported snapshot only lives while the exporting
transaction is open, so ONE orchestrator call:

1. opens ``REPEATABLE READ READ ONLY`` as the first statement,
2. verifies the live database is the allowlisted source and the Alembic
   revision is the contracted one,
3. computes the fingerprint with the committed ``compute_input_fingerprint``,
4. exports the snapshot with ``pg_export_snapshot()``,
5. runs ``pg_dump --snapshot`` for exactly the nine tables and checks the
   archive ToC,
6. only then ends the transaction.

A fingerprint is reported as bound to an archive only if every step
succeeded.  On any failure the transaction is rolled back, the partial
archive is deleted, and nothing is published.

This module is separate from ``evaluate``: it accepts only the source
database, never the evaluation database, and has no path to the evaluator.
It never writes to the database and takes no explicit locks (``pg_dump``'s
ACCESS SHARE locks block DDL only; acceptance writes continue).

Credentials reach ``pg_dump`` only through the child process environment
(``PGUSER``/``PGPASSWORD``/...), never through argv.  Subprocess output is
never surfaced, so hosts and passwords cannot leak through error messages.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.matching import verified_evaluation as ve

SOURCE_DATABASE_NAME = "scopus_ictu_acceptance_v2"
EXPECTED_ALEMBIC_REVISION = "d3f7a1c9e2b4"
METADATA_SCHEMA_VERSION = 1

# Exactly the tables covered by fingerprint v1, in sorted order.
DUMP_TABLES: tuple[str, ...] = tuple(sorted((*ve.FINGERPRINT_CONTENT_COLUMNS, *ve.FINGERPRINT_KEY_TABLES)))
DUMP_SCHEMA = "public"

# FK edges among the nine tables (child -> parents), from models and Alembic.
TABLE_PARENTS: dict[str, tuple[str, ...]] = {
    "lecturer_known_publications": ("lecturer_source_snapshots",),
    "lecturer_source_snapshots": ("lecturers",),
    "lecturers": (),
    "publication_authors": ("publications", "scopus_authors"),
    "publications": (),
    "raw_scopus_records": ("scopus_imports",),
    "scopus_author_name_variants": ("raw_scopus_records", "scopus_authors"),
    "scopus_authors": (),
    "scopus_imports": (),
}

PG_DUMP_LOCK_WAIT_TIMEOUT = "30s"
PG_DUMP_TIMEOUT_SECONDS = 3600
PG_RESTORE_LIST_TIMEOUT_SECONDS = 120

# Header entries pg_restore --list may show for a data-only archive.
_ALLOWED_NON_DATA_TOC_TYPES: frozenset[str] = frozenset({"ENCODING", "STDSTRINGS", "SEARCHPATH"})
_SNAPSHOT_ID_RE = re.compile(r"^[0-9A-Fa-f]+-[0-9A-Fa-f]+(-[0-9]+)?$")
_TOC_LINE_RE = re.compile(r"^\s*\d+;\s+\d+\s+\d+\s+(?P<rest>.+?)\s*$")

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class SourceDumpError(Exception):
    """A source-dump gate or step failed.  Message is safe to display."""


# ---------------------------------------------------------------------------
# Database identity
# ---------------------------------------------------------------------------


def is_source_database(database_url: str) -> bool:
    """Configuration-level allowlist: only the acceptance source database."""
    from sqlalchemy.engine import make_url

    try:
        name = make_url(database_url).database
    except Exception:
        return False
    return name == SOURCE_DATABASE_NAME


def verify_connected_source(session: Any) -> None:
    from sqlalchemy import text

    actual = session.execute(text("SELECT current_database()")).scalar_one()
    if actual != SOURCE_DATABASE_NAME:
        raise SourceDumpError("Connected database is not the allowlisted source database.")


def verify_alembic_revision(session: Any, expected: str = EXPECTED_ALEMBIC_REVISION) -> str:
    from sqlalchemy import text

    revisions = list(session.execute(text("SELECT version_num FROM alembic_version")).scalars().all())
    if revisions != [expected]:
        raise SourceDumpError("Source Alembic revision is not the contracted revision.")
    return expected


def export_snapshot(session: Any) -> str:
    from sqlalchemy import text

    snapshot_id = session.execute(text("SELECT pg_export_snapshot()")).scalar_one()
    if not isinstance(snapshot_id, str) or not _SNAPSHOT_ID_RE.match(snapshot_id):
        raise SourceDumpError("pg_export_snapshot() returned a malformed snapshot id.")
    return snapshot_id


# ---------------------------------------------------------------------------
# pg_dump / pg_restore invocation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConnectionParams:
    host: str
    port: int
    user: str
    password: str
    database: str

    def __repr__(self) -> str:  # never render credentials
        return "ConnectionParams(<redacted>)"


def child_environment(base: Mapping[str, str], params: ConnectionParams | None) -> dict[str, str]:
    """Inherited environment minus every PG* variable, plus our own if given."""
    env = {k: v for k, v in base.items() if not k.upper().startswith("PG")}
    if params is not None:
        env.update(
            {
                "PGHOST": params.host,
                "PGPORT": str(params.port),
                "PGUSER": params.user,
                "PGPASSWORD": params.password,
                "PGDATABASE": params.database,
            }
        )
    return env


def build_pg_dump_argv(pg_dump: str, snapshot_id: str, archive_path: Path) -> list[str]:
    if not _SNAPSHOT_ID_RE.match(snapshot_id):
        raise SourceDumpError("Refusing a malformed snapshot id.")
    return [
        pg_dump,
        "--format=custom",
        "--data-only",
        "--no-password",
        "--strict-names",
        f"--lock-wait-timeout={PG_DUMP_LOCK_WAIT_TIMEOUT}",
        f"--snapshot={snapshot_id}",
        f"--file={archive_path}",
        *(f"--table={DUMP_SCHEMA}.{table}" for table in DUMP_TABLES),
    ]


def _run(runner: Runner, argv: Sequence[str], env: Mapping[str, str], timeout: int, what: str) -> str:
    try:
        completed = runner(
            list(argv),
            env=dict(env),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise SourceDumpError(f"{what} timed out.") from None
    except (OSError, subprocess.SubprocessError):
        raise SourceDumpError(f"{what} could not be started.") from None
    if completed.returncode != 0:
        raise SourceDumpError(f"{what} failed with exit code {completed.returncode}.")
    return completed.stdout or ""


# ---------------------------------------------------------------------------
# Archive ToC
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TocCheck:
    data_tables: tuple[str, ...]  # in archive order
    parent_before_child: bool


def parse_toc_entries(listing: str) -> list[tuple[str, str, str]]:
    """``pg_restore --list`` -> [(entry_type, schema, name)] in archive order."""
    entries: list[tuple[str, str, str]] = []
    for line in listing.splitlines():
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        match = _TOC_LINE_RE.match(line)
        if match is None:
            raise SourceDumpError("Archive ToC has an unparseable entry.")
        rest = match.group("rest")
        if rest.startswith("TABLE DATA "):
            parts = rest[len("TABLE DATA ") :].split()
            if len(parts) < 2:
                raise SourceDumpError("Archive ToC has a malformed TABLE DATA entry.")
            entries.append(("TABLE DATA", parts[0], parts[1]))
        else:
            entries.append((rest.split()[0], "", ""))
    return entries


def is_parent_before_child(order: Sequence[str]) -> bool:
    position = {table: i for i, table in enumerate(order)}
    return all(
        position[parent] < position[child]
        for child, parents in TABLE_PARENTS.items()
        for parent in parents
        if child in position and parent in position
    )


def check_archive_toc(listing: str) -> TocCheck:
    """Exactly nine TABLE DATA entries for the contracted tables, nothing else.

    Wrong order is reported, not refused: restore uses ``pg_restore -L`` only
    when ``parent_before_child`` is False.
    """
    data: list[str] = []
    for entry_type, schema, name in parse_toc_entries(listing):
        if entry_type == "TABLE DATA":
            if schema != DUMP_SCHEMA or name not in DUMP_TABLES:
                raise SourceDumpError("Archive ToC contains a table outside the contracted nine.")
            data.append(name)
        elif entry_type not in _ALLOWED_NON_DATA_TOC_TYPES:
            raise SourceDumpError(f"Archive ToC contains a non-data entry of type {entry_type}.")
    if len(data) != len(set(data)) or sorted(data) != list(DUMP_TABLES):
        raise SourceDumpError("Archive ToC does not contain exactly the nine contracted TABLE DATA entries.")
    return TocCheck(tuple(data), is_parent_before_child(data))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceDumpResult:
    fingerprint: ve.InputFingerprint
    alembic_revision: str
    snapshot_id: str
    archive_sha256: str
    toc: TocCheck

    def metadata(self, archive_name: str) -> dict[str, Any]:
        """Operational metadata.  ``input_fingerprint`` is fingerprint v1, unchanged."""
        return {
            "metadata_schema_version": METADATA_SCHEMA_VERSION,
            "source_database_identity_verified": True,
            "alembic_revision": self.alembic_revision,
            "snapshot_id": self.snapshot_id,
            "archive_file": archive_name,
            "archive_sha256": self.archive_sha256,
            "archive_data_tables_in_order": list(self.toc.data_tables),
            "archive_parent_before_child": self.toc.parent_before_child,
            "table_row_counts": {t.table: t.row_count for t in self.fingerprint.tables},
            "input_fingerprint": self.fingerprint.as_dict(),
        }


def partial_path_for(archive_path: Path) -> Path:
    return archive_path.with_name(archive_path.name + ".partial")


def _remove_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def dump_source_snapshot(
    session: Any,
    *,
    params: ConnectionParams,
    archive_path: Path,
    pg_dump: str = "pg_dump",
    pg_restore: str = "pg_restore",
    runner: Runner = subprocess.run,
    base_env: Mapping[str, str] | None = None,
    compute_fingerprint: Callable[[Any], ve.InputFingerprint] | None = None,
) -> SourceDumpResult:
    """Fingerprint + snapshot export + pg_dump inside ONE open transaction.

    ``session`` must be fresh (no statement executed yet).  The archive is
    written to ``<archive>.partial`` and renamed to ``archive_path`` only
    after pg_dump, the ToC check and the SHA-256 all succeeded and the
    transaction was closed.  Any failure rolls back and deletes the partial.
    """
    from sqlalchemy import text

    if archive_path.exists():
        raise SourceDumpError(f"Refusing to overwrite existing archive: {archive_path.name}")
    partial = partial_path_for(archive_path)
    if partial.exists():
        raise SourceDumpError(f"Refusing to continue: stale partial archive exists: {partial.name}")
    fingerprint_fn = compute_fingerprint if compute_fingerprint is not None else ve.compute_input_fingerprint
    inherited = os.environ if base_env is None else base_env

    try:
        try:
            session.execute(text(ve.READ_ONLY_SNAPSHOT_SQL))
        except Exception:
            raise SourceDumpError("Could not establish a read-only snapshot transaction.") from None
        verify_connected_source(session)
        revision = verify_alembic_revision(session)
        fingerprint = fingerprint_fn(session)
        snapshot_id = export_snapshot(session)

        # The exporting transaction is still open here; pg_dump attaches to it.
        _run(
            runner,
            build_pg_dump_argv(pg_dump, snapshot_id, partial),
            child_environment(inherited, params),
            PG_DUMP_TIMEOUT_SECONDS,
            "pg_dump",
        )
        if not partial.is_file():
            raise SourceDumpError("pg_dump reported success but wrote no archive.")
        listing = _run(
            runner,
            [pg_restore, "--list", str(partial)],
            child_environment(inherited, None),
            PG_RESTORE_LIST_TIMEOUT_SECONDS,
            "pg_restore --list",
        )
        toc = check_archive_toc(listing)
        archive_sha256 = sha256_file(partial)
    except BaseException:
        _safe_rollback(session)
        _remove_quietly(partial)
        raise

    # Read-only transaction: nothing to commit.  Ending it releases the snapshot.
    try:
        session.rollback()
    except Exception:
        _remove_quietly(partial)
        raise SourceDumpError("Could not close the source snapshot transaction cleanly.") from None
    try:
        os.replace(partial, archive_path)
    except OSError:
        _remove_quietly(partial)
        raise SourceDumpError("Could not move the verified archive into place.") from None
    return SourceDumpResult(fingerprint, revision, snapshot_id, archive_sha256, toc)


def _safe_rollback(session: Any) -> None:
    try:
        session.rollback()
    except Exception:
        pass


__all__ = [
    "ConnectionParams",
    "DUMP_SCHEMA",
    "DUMP_TABLES",
    "EXPECTED_ALEMBIC_REVISION",
    "SOURCE_DATABASE_NAME",
    "SourceDumpError",
    "SourceDumpResult",
    "TABLE_PARENTS",
    "TocCheck",
    "build_pg_dump_argv",
    "check_archive_toc",
    "child_environment",
    "dump_source_snapshot",
    "is_parent_before_child",
    "is_source_database",
    "parse_toc_entries",
    "partial_path_for",
    "verify_alembic_revision",
    "verify_connected_source",
]
