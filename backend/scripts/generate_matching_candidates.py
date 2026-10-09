"""Generate and persist PENDING lecturer <-> Scopus author candidates (M2.7B).

Thin, fail-closed operator CLI around the existing matching services:

    CandidateGenerator.generate_all()
      -> PublicationEvidenceEnricher.enrich()
      -> build_source_state()
      -> GenerationRunSpec
      -> CandidatePersistenceService.persist_generation()

It never changes matching rules, never writes candidates with hand-made SQL,
never creates identities or reviews, and is never started by the web app.

Connection settings come from the usual ``DB_*`` environment variables (see
``app.core.config``); nothing is hard-coded and no secret is printed.

Usage (from ``backend/``)::

    # 1. read-only preview (default transaction_read_only=on, nothing is written)
    python -m scripts.generate_matching_candidates --dry-run \\
        --expected-database <db> --expected-port <port>

    # 2. persist PENDING candidates; the manifest (OUTSIDE the repository)
    #    records run_id + source-state fingerprint so a retry is idempotent
    python -m scripts.generate_matching_candidates --apply \\
        --expected-database <db> --expected-port <port> \\
        --manifest <path-outside-repo>.json [--run-id <uuid>] \\
        [--expected-candidates N]

Exit codes: 0 ok, 2 refused by a safety guard, 3 source data changed,
4 generation-run conflict / abnormal run state, 5 persistence failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
    LecturerScopusCandidateReview,
)
from app.models.identity import LecturerScopusIdentity
from app.services.matching.candidate_generator import CandidateGenerator
from app.services.matching.candidate_persistence import (
    CandidatePersistenceService,
    GenerationRunConflict,
    GenerationRunSpec,
    GenerationRunStateError,
    build_source_state,
    canonical_json,
    sha256_json,
)
from app.services.matching.candidate_types import EnrichedLecturerScopusCandidate
from app.services.matching.publication_evidence_enricher import PublicationEvidenceEnricher

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_SOURCE_CHANGED = 3
EXIT_RUN_CONFLICT = 4
EXIT_PERSIST_FAILED = 5

FORBIDDEN_PORTS = frozenset({5432})
# Same databases the test suite refuses to touch.
FORBIDDEN_DATABASES = frozenset({"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA_VERSION = 1


class CliRefused(Exception):
    """A safety guard refused the operation (exit code 2)."""

    exit_code = EXIT_REFUSED


class SourceChanged(CliRefused):
    exit_code = EXIT_SOURCE_CHANGED


class RunRefused(CliRefused):
    exit_code = EXIT_RUN_CONFLICT


@dataclass(frozen=True, slots=True)
class Plan:
    candidates: tuple[EnrichedLecturerScopusCandidate, ...]
    source_state: dict[str, Any]
    conflicts: int

    @property
    def pairs_sha256(self) -> str:
        return sha256_json(
            sorted([str(c.lecturer_id), str(c.scopus_author_id)] for c in self.candidates)
        )

    @property
    def source_state_sha256(self) -> str:
        return sha256_json(self.source_state)


# ── guards ────────────────────────────────────────────────────────────────────
def validate_target_url(
    url: URL, expected_database: str, expected_port: int | None = None
) -> None:
    """Pure URL guard: loopback only, never 5432, database name must match."""
    if not expected_database:
        raise CliRefused("--expected-database is required")
    if url.database != expected_database:
        raise CliRefused("configured database does not match --expected-database")
    if url.database in FORBIDDEN_DATABASES:
        raise CliRefused("target database is protected (acceptance/forensic)")
    port = url.port or 5432
    if port in FORBIDDEN_PORTS:
        raise CliRefused(f"port {port} is forbidden for this tool")
    if expected_port is not None and port != expected_port:
        raise CliRefused("configured port does not match --expected-port")
    if (url.host or "") not in LOOPBACK_HOSTS:
        raise CliRefused("only a loopback database host is allowed")


def verify_server_identity(
    engine: Engine, expected_database: str, expected_port: int | None
) -> dict[str, Any]:
    """Ask the server who it is, on a throw-away connection (no Session)."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "select current_database(), inet_server_port(), "
                "host(inet_server_addr()), current_user, "
                "current_setting('server_version_num')::int"
            )
        ).one()
        conn.rollback()
    database, port, addr, user, version = row
    if database != expected_database:
        raise CliRefused("server reports a different database than --expected-database")
    if port in FORBIDDEN_PORTS:
        raise CliRefused(f"server port {port} is forbidden for this tool")
    if expected_port is not None and port != expected_port:
        raise CliRefused("server port does not match --expected-port")
    if addr not in {"127.0.0.1", "::1"}:
        raise CliRefused("server is not bound to loopback")
    return {"database": database, "port": port, "address": addr, "user": user, "pg_version": version}


def validate_manifest_path(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise CliRefused("manifest must be stored outside the Git repository")
    if resolved.suffix.lower() != ".json":
        raise CliRefused("manifest must be a .json file")
    return resolved


# ── read side ────────────────────────────────────────────────────────────────
def make_read_only_engine(url: URL) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": "-c default_transaction_read_only=on"},
    )


def build_plan(reader_engine: Engine) -> Plan:
    """Generate + enrich + fingerprint inside ONE read-only transaction."""
    with Session(reader_engine) as session:
        if session.execute(text("show transaction_read_only")).scalar_one() != "on":
            raise CliRefused("reader session is not read-only")
        candidates = CandidateGenerator(session).generate_all()
        enriched = PublicationEvidenceEnricher(session).enrich(candidates)
        source_state = build_source_state(session)
        session.rollback()  # end the read transaction before anything else happens
    return Plan(tuple(enriched.candidates), source_state, len(enriched.conflicts))


def inspect_runs(reader_engine: Engine, run_id: uuid.UUID | None) -> dict[str, Any]:
    with Session(reader_engine) as session:
        total = session.scalar(select(func.count(CandidateGenerationRun.id))) or 0
        completed = (
            session.scalar(
                select(func.count(CandidateGenerationRun.id)).where(
                    CandidateGenerationRun.status == "COMPLETED"
                )
            )
            or 0
        )
        status = (
            session.scalar(
                select(CandidateGenerationRun.status).where(CandidateGenerationRun.id == run_id)
            )
            if run_id
            else None
        )
        session.rollback()
    return {"runs_total": total, "runs_completed": completed, "requested_run_status": status}


def table_counts(reader_engine: Engine) -> dict[str, Any]:
    """Aggregate counts only (no personal data)."""
    with Session(reader_engine) as session:
        by_status = dict(
            session.execute(
                select(LecturerScopusCandidate.status, func.count()).group_by(
                    LecturerScopusCandidate.status
                )
            ).all()
        )
        identity_by_status = dict(
            session.execute(
                select(LecturerScopusIdentity.status, func.count()).group_by(
                    LecturerScopusIdentity.status
                )
            ).all()
        )
        out = {
            "generation_runs": session.scalar(select(func.count(CandidateGenerationRun.id))),
            "candidate_roots": session.scalar(select(func.count(LecturerScopusCandidate.id))),
            "observations": session.scalar(
                select(func.count(LecturerScopusCandidateObservation.id))
            ),
            "evidence": session.scalar(select(func.count(LecturerScopusCandidateEvidence.id))),
            "reviews": session.scalar(select(func.count(LecturerScopusCandidateReview.id))),
            "candidates_by_status": by_status,
            "identities_by_status": identity_by_status,
        }
        session.rollback()
    return out


def summarize_plan(plan: Plan) -> dict[str, Any]:
    lecturers = {c.lecturer_id for c in plan.candidates}
    authors = {c.scopus_author_id for c in plan.candidates}
    return {
        "candidates": len(plan.candidates),
        "lecturers": len(lecturers),
        "scopus_authors": len(authors),
        "name_evidence": sum(len(c.name_evidence) for c in plan.candidates),
        "publication_evidence": sum(len(c.publication_evidence) for c in plan.candidates),
        "publication_conflicts": plan.conflicts,
        "source_state_sha256": plan.source_state_sha256,
        "pairs_sha256": plan.pairs_sha256,
        "inputs": {k: v["count"] for k, v in plan.source_state["inputs"].items()},
    }


# ── manifest ─────────────────────────────────────────────────────────────────
def _write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _manifest_for(run_id: uuid.UUID, database: str, plan: Plan) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": str(run_id),
        "database": database,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "PLANNED",
        "candidate_count": len(plan.candidates),
        "pairs_sha256": plan.pairs_sha256,
        "source_state_sha256": plan.source_state_sha256,
        "source_state": plan.source_state,
        "result": None,
        "error": None,
    }


def load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION or "run_id" not in data:
        raise CliRefused("manifest has an unsupported format")
    return data


# ── apply ────────────────────────────────────────────────────────────────────
def apply_generation(
    reader_engine: Engine,
    writer_engine: Engine,
    *,
    database: str,
    manifest_path: Path,
    run_id: uuid.UUID | None = None,
    expected_candidates: int | None = None,
    allow_new_run: bool = False,
    resume_running: bool = False,
) -> dict[str, Any]:
    plan = build_plan(reader_engine)
    manifest = load_manifest(manifest_path)

    if manifest is not None:
        if manifest["database"] != database:
            raise CliRefused("manifest belongs to a different database")
        manifest_run = uuid.UUID(manifest["run_id"])
        if run_id is not None and run_id != manifest_run:
            raise CliRefused("--run-id differs from the run_id recorded in the manifest")
        run_id = manifest_run
        if manifest["source_state"] != plan.source_state or manifest["pairs_sha256"] != plan.pairs_sha256:
            raise SourceChanged(
                "source data changed since this run_id was planned; the run_id must not be "
                "reused with different metadata - keep the manifest as evidence and plan a "
                "new run with a new manifest"
            )
    else:
        if expected_candidates is not None and len(plan.candidates) != expected_candidates:
            raise CliRefused(
                f"expected {expected_candidates} candidates but generated {len(plan.candidates)}"
            )
        runs = inspect_runs(reader_engine, run_id)
        if runs["runs_completed"] and not allow_new_run:
            raise RunRefused(
                "a COMPLETED generation run already exists; pass the original manifest/--run-id "
                "to replay it, or --allow-new-run to deliberately start another run"
            )
        run_id = run_id or uuid.uuid4()
        manifest = _manifest_for(run_id, database, plan)
        _write_manifest(manifest_path, manifest)  # recoverable BEFORE touching the DB

    if expected_candidates is not None and len(plan.candidates) != expected_candidates:
        raise CliRefused(
            f"expected {expected_candidates} candidates but generated {len(plan.candidates)}"
        )

    status = inspect_runs(reader_engine, run_id)["requested_run_status"]
    if status == "RUNNING" and not resume_running:
        raise RunRefused(
            "generation run is RUNNING (possibly another process or an interrupted one); "
            "refusing to continue without --resume-running"
        )
    if status not in (None, "RUNNING", "FAILED", "COMPLETED"):
        raise RunRefused(f"generation run has an abnormal status: {status}")

    # Re-verify immediately before writing: the world must be exactly what was planned.
    recheck = build_plan(reader_engine)
    if recheck.source_state != plan.source_state or recheck.pairs_sha256 != plan.pairs_sha256:
        raise SourceChanged("source data changed between generation and apply")

    spec = GenerationRunSpec(run_id=run_id, source_state=plan.source_state)
    # A brand-new Session with NO prior statements: CandidatePersistenceService opens its
    # own transactions with session.begin(), which fails if autobegin already happened.
    writer = Session(writer_engine)
    try:
        result = CandidatePersistenceService(writer).persist_generation(spec, plan.candidates)
    except (GenerationRunConflict, GenerationRunStateError) as exc:
        manifest.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        _write_manifest(manifest_path, manifest)
        raise RunRefused(f"{type(exc).__name__}: {exc}") from exc
    except Exception as exc:
        manifest.update(status="FAILED", error=f"{type(exc).__name__}")
        _write_manifest(manifest_path, manifest)
        raise
    finally:
        writer.close()

    # Persistence must not have altered any generator input.
    after = build_plan(reader_engine)
    inputs_unchanged = after.source_state == plan.source_state
    summary = {
        "run_id": str(result.run_id),
        "run_status": result.run_status,
        "candidate_roots": result.candidate_roots,
        "observations": result.observations,
        "evidence": result.evidence,
        "idempotent_replay": result.idempotent_replay,
        "inputs_unchanged_after_apply": inputs_unchanged,
    }
    manifest.update(status=result.run_status if inputs_unchanged else "INPUTS_CHANGED", result=summary, error=None)
    _write_manifest(manifest_path, manifest)
    if not inputs_unchanged:
        raise SourceChanged("generator inputs differ after persistence")
    return summary


# ── entry point ──────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m scripts.generate_matching_candidates",
        description="Generate lecturer<->Scopus candidates (dry-run) or persist them as PENDING (apply).",
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="read-only; writes nothing to the database")
    mode.add_argument("--apply", action="store_true", help="persist PENDING candidates")
    p.add_argument("--expected-database", required=True, help="database name that must match for any run")
    p.add_argument("--expected-port", type=int, default=None, help="server port that must match (5432 is always refused)")
    p.add_argument("--run-id", type=uuid.UUID, default=None, help="stable generation run UUID (replay/resume)")
    p.add_argument("--manifest", type=Path, default=None, help="JSON manifest OUTSIDE the repo (required for --apply)")
    p.add_argument("--expected-candidates", type=int, default=None, help="refuse unless exactly N candidates are generated")
    p.add_argument("--allow-new-run", action="store_true", help="allow a new run although a COMPLETED run exists")
    p.add_argument("--resume-running", action="store_true", help="continue a run stuck in RUNNING")
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
            before = table_counts(reader)
            plan = build_plan(reader)
            out = {"mode": "dry-run", "plan": summarize_plan(plan), "runs": inspect_runs(reader, args.run_id), "tables": before}
            if manifest_path and (m := load_manifest(manifest_path)):
                out["matches_manifest"] = (
                    m["source_state"] == plan.source_state and m["pairs_sha256"] == plan.pairs_sha256
                )
                out["manifest_run_id"] = m["run_id"]
            out["tables_unchanged"] = table_counts(reader) == before
            print(canonical_json(out))
            return EXIT_OK

        writer = create_engine(url, pool_pre_ping=True)
        try:
            verify_server_identity(writer, args.expected_database, args.expected_port)
            summary = apply_generation(
                reader,
                writer,
                database=args.expected_database,
                manifest_path=manifest_path,
                run_id=args.run_id,
                expected_candidates=args.expected_candidates,
                allow_new_run=args.allow_new_run,
                resume_running=args.resume_running,
            )
        finally:
            writer.dispose()
        print(canonical_json({"mode": "apply", "result": summary, "tables": table_counts(reader)}))
        return EXIT_OK
    except CliRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:  # fail closed, keep evidence (manifest) and never echo secrets
        print(f"FAILED: {type(exc).__name__}", file=sys.stderr)
        return EXIT_PERSIST_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
