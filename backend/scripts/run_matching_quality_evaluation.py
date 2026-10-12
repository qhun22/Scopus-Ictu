"""CLI: verified matching-quality evaluation (C3-A3).

Subcommands:

  prepare-cohort  Write the official primary cohort (SHA256_SEED_RANK_V1,
                  seed C3-A3-ICTU-PRIMARY-2026-V1, size 50).  Uses only the
                  official lecturer dataset; no database, no candidate data.

  compute-fingerprint
                  Compute the evaluation-input fingerprint of the approved
                  evaluation database (scopus_c3_eval_v1) in one
                  REPEATABLE READ READ ONLY snapshot.  Needs no pinned value.

  evaluate        Verify the frozen A2 review package, the human-confirmed
                  reference copy, dataset/cohort/rule/code provenance, the
                  pinned input fingerprint (refused while UNPINNED), then run
                  the frozen A1 evaluator READ-ONLY against the approved
                  evaluation database only, and write a safe result JSON.

Exit codes: 0 success, 1 verification/environment/database error,
2 usage/file/import error.  Raw database errors, the database URL and the
database name are never printed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_COHORT_PATH = REPO_ROOT / "data" / "matching" / "evaluation" / "primary_cohort_source_ids.txt"

_PACKAGE_FILES = ("candidate_review.csv", "reference_labeling_sheet.csv", "review_manifest.json")


def _emit_error(message: str) -> None:
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verified matching-quality evaluation (C3-A3).")
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare-cohort", help="Write the official primary cohort file.")
    prep.add_argument("--lecturer-dataset", required=True)
    prep.add_argument("--out", required=True)
    prep.add_argument("--overwrite", action="store_true")

    fp = sub.add_parser("compute-fingerprint", help="Compute the evaluation-input fingerprint.")
    fp.add_argument("--json-out", default=None)
    fp.add_argument("--overwrite", action="store_true")

    ev = sub.add_parser("evaluate", help="Run the verified official evaluation.")
    ev.add_argument("--review-dir", required=True)
    ev.add_argument("--reference-confirmed", required=True)
    ev.add_argument("--lecturer-dataset", required=True)
    ev.add_argument("--source-id-file", required=True)
    ev.add_argument("--json-out", required=True)
    ev.add_argument("--overwrite", action="store_true")
    return parser


def _prepare_cohort(args: argparse.Namespace) -> int:
    from app.services.matching.verified_evaluation import (
        VerificationError,
        render_cohort_file,
        select_primary_cohort,
        verify_frozen_official_dataset,
    )

    dataset_path = Path(args.lecturer_dataset)
    out = Path(args.out)
    if not dataset_path.is_file():
        _emit_error(f"Lecturer dataset not found: {dataset_path}")
        return 2
    if out.exists() and not args.overwrite:
        _emit_error(f"Refusing to overwrite existing cohort file: {out}")
        return 1
    try:
        dataset_bytes = dataset_path.read_bytes()
        verify_frozen_official_dataset(dataset_bytes)
        cohort = select_primary_cohort(dataset_bytes)
    except VerificationError as exc:
        _emit_error(str(exc))
        return 1
    content = render_cohort_file(cohort)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(content)

    from app.services.matching.verified_evaluation import sha256_hex

    print(json.dumps({"selected_count": len(cohort), "source_id_file_sha256": sha256_hex(content)}))
    return 0


def _approved_engine(settings, ve):
    """Configuration-level gates; returns an engine or None after emitting an error."""
    if settings.environment.lower() == "prod":
        _emit_error("Refused: environment=prod.")
        return None
    if not ve.is_approved_database(settings.database_url):
        _emit_error("Configured database is not the approved C3 evaluation database.")
        return None
    from sqlalchemy import create_engine

    return create_engine(settings.database_url)


def _compute_fingerprint(args: argparse.Namespace) -> int:
    from app.core.config import settings
    from app.services.matching import verified_evaluation as ve

    json_out = Path(args.json_out) if args.json_out else None
    if json_out is not None and json_out.exists() and not args.overwrite:
        _emit_error(f"Refusing to overwrite existing file: {json_out.name}")
        return 1
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    engine = _approved_engine(settings, ve)
    if engine is None:
        return 1
    try:
        with Session(engine) as session:
            try:
                session.execute(text(ve.READ_ONLY_SNAPSHOT_SQL))
            except Exception:
                _emit_error("Could not establish a read-only snapshot transaction. Refusing to continue.")
                return 1
            ve.verify_connected_database(session)
            fingerprint = ve.compute_input_fingerprint(session)
    except ve.VerificationError as exc:
        _emit_error(f"Verification failed: {exc}")
        return 1
    except SQLAlchemyError:
        _emit_error("Database fingerprint computation failed safely.")
        return 1
    finally:
        engine.dispose()

    payload = {"database_identity_verified": True, **fingerprint.as_dict()}
    text_out = json.dumps(payload, ensure_ascii=False, indent=2)
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(text_out + "\n", encoding="utf-8")
    print(text_out)
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    from app.core.config import settings
    from app.services.matching import verified_evaluation as ve

    review_dir = Path(args.review_dir)
    paths = {name: review_dir / name for name in _PACKAGE_FILES}
    confirmed_path = Path(args.reference_confirmed)
    dataset_path = Path(args.lecturer_dataset)
    source_path = Path(args.source_id_file)
    json_out = Path(args.json_out)

    for path in (*paths.values(), confirmed_path, dataset_path, source_path, COMMITTED_COHORT_PATH):
        if not path.is_file():
            _emit_error(f"Required input not found: {path.name}")
            return 2
    if json_out.exists() and not args.overwrite:
        _emit_error(f"Refusing to overwrite existing result: {json_out.name}")
        return 1

    # Each file is read exactly once; the same bytes feed every gate below.
    candidate_review_bytes = paths["candidate_review.csv"].read_bytes()
    labeling_sheet_bytes = paths["reference_labeling_sheet.csv"].read_bytes()
    dataset_bytes = dataset_path.read_bytes()
    source_id_file_bytes = source_path.read_bytes()

    # --- every offline provenance gate runs before any database connection ---
    try:
        verified = ve.verify_offline_inputs(
            candidate_review_bytes=candidate_review_bytes,
            labeling_sheet_bytes=labeling_sheet_bytes,
            manifest_bytes=paths["review_manifest.json"].read_bytes(),
            confirmed_bytes=confirmed_path.read_bytes(),
            dataset_bytes=dataset_bytes,
            dataset_path=dataset_path,
            source_id_file_bytes=source_id_file_bytes,
            committed_cohort_bytes=COMMITTED_COHORT_PATH.read_bytes(),
            repo_root=REPO_ROOT,
        )
    except ve.VerificationError as exc:
        _emit_error(f"Verification failed: {exc}")
        return 1

    # --- pinned input fingerprint (refused while UNPINNED, before any DB) ----
    try:
        ve.require_pinned_fingerprint()
    except ve.VerificationError as exc:
        _emit_error(f"Verification failed: {exc}")
        return 1

    # --- database gates -------------------------------------------------------
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    engine = _approved_engine(settings, ve)
    if engine is None:
        return 1
    try:
        with Session(engine) as session:
            try:
                session.execute(text(ve.READ_ONLY_SNAPSHOT_SQL))
            except Exception:
                _emit_error("Could not establish a read-only snapshot transaction. Refusing to continue.")
                return 1
            # One REPEATABLE READ snapshot for identity, fingerprint, re-render and evaluation.
            ve.verify_connected_database(session)
            fingerprint = ve.compute_input_fingerprint(session)
            ve.verify_input_fingerprint(fingerprint)
            rerender = ve.verify_package_rerender(
                session,
                manifest=verified.manifest,
                candidate_review_bytes=candidate_review_bytes,
                labeling_sheet_bytes=labeling_sheet_bytes,
                dataset_bytes=dataset_bytes,
                source_id_file_bytes=source_id_file_bytes,
            )
            evaluation = ve.run_frozen_a1_evaluation(verified.records, session)
    except ve.VerificationError as exc:
        _emit_error(f"Verification failed: {exc}")
        return 1
    except SQLAlchemyError:
        _emit_error("Database evaluation failed safely.")
        return 1
    finally:
        engine.dispose()

    result = ve.build_result(verified, evaluation, datetime.now(timezone.utc), fingerprint, rerender)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": json_out.name, "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "prepare-cohort":
            return _prepare_cohort(args)
        if args.command == "compute-fingerprint":
            return _compute_fingerprint(args)
        return _evaluate(args)
    except ImportError as exc:
        _emit_error(f"Import failed: {exc}. Run from repo root with backend/ on PYTHONPATH.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
