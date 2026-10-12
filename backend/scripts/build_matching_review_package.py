"""CLI: build the deterministic human matching review package (C3-A2).

Usage:
    python backend/scripts/build_matching_review_package.py \\
        --lecturer-dataset data/lecturers/ictu_lecturers.json \\
        --output-dir <directory> \\
        [--source-id-file <path>] [--overwrite]

Writes exactly three files into --output-dir:
    candidate_review.csv
    reference_labeling_sheet.csv
    review_manifest.json

The package is advisory review material.  It creates NO ground truth: the
labeling sheet is blank apart from identity/display columns.

READ-ONLY database access via app.core.config.settings.database_url (never
printed).  Refuses to run when settings.environment is "prod".  Fails closed
when SET TRANSACTION READ ONLY cannot be established.  Raw database exception
details are never emitted.

Exit codes:
    0  success
    1  validation, environment, overwrite or database error
    2  usage / file / import error
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PACKAGE_FILES = (
    "candidate_review.csv",
    "reference_labeling_sheet.csv",
    "review_manifest.json",
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build the human matching review package (no ground truth).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--lecturer-dataset", required=True, help="Official ICTU lecturer JSON.")
    p.add_argument("--output-dir", required=True, help="Directory for the three package files.")
    p.add_argument("--source-id-file", default=None, help="Optional lecturer_source_id subset file.")
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the three package files if they already exist.",
    )
    return p


def _emit_error(message: str) -> None:
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    dataset_path = Path(args.lecturer_dataset)
    output_dir = Path(args.output_dir)
    selection_path = Path(args.source_id_file) if args.source_id_file else None

    if not dataset_path.is_file():
        _emit_error(f"Lecturer dataset not found: {dataset_path}")
        return 2
    if selection_path is not None and not selection_path.is_file():
        _emit_error(f"Source-id file not found: {selection_path}")
        return 2

    try:
        from app.core.config import settings
        from app.services.matching.candidate_persistence import (
            CANDIDATE_RULE_SET_ID,
            CANDIDATE_RULE_SET_VERSION,
        )
        from app.services.matching.review_package import (
            ReviewPackageError,
            build_review_package,
            generate_review_inputs,
            parse_official_lecturers,
            parse_source_id_file,
            resolve_canonical_lecturers_from_db,
            select_lecturers,
        )
    except ImportError as exc:
        _emit_error(f"Import failed: {exc}. Run from repo root with backend/ on PYTHONPATH.")
        return 2

    # --- inputs: official dataset + deterministic selection ------------------
    dataset_bytes = dataset_path.read_bytes()
    selection_bytes = selection_path.read_bytes() if selection_path is not None else None
    try:
        official = parse_official_lecturers(dataset_bytes)
        requested = parse_source_id_file(selection_bytes) if selection_bytes is not None else None
        selected = select_lecturers(official, requested)
    except ReviewPackageError as exc:
        _emit_error(str(exc))
        return 1

    # --- output safety: never silently overwrite human review work -----------
    targets = [output_dir / name for name in _PACKAGE_FILES]
    existing = [t.name for t in targets if t.exists()]
    if existing and not args.overwrite:
        _emit_error(f"Refusing to overwrite existing package files: {existing}")
        return 1

    # --- environment guard ---------------------------------------------------
    if settings.environment.lower() == "prod":
        _emit_error("Review package builder refused: environment=prod.")
        return 1

    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy.orm import Session
    except ImportError as exc:
        _emit_error(f"SQLAlchemy import failed: {exc}")
        return 2

    engine = create_engine(settings.database_url)
    generated_at = datetime.now(timezone.utc)

    try:
        with Session(engine) as session:
            try:
                session.execute(text("SET TRANSACTION READ ONLY"))
            except Exception:
                _emit_error(
                    "Could not establish a read-only database transaction. "
                    "Refusing to continue."
                )
                return 1

            canonical_ids = resolve_canonical_lecturers_from_db(selected, session)
            enriched, conflicts = generate_review_inputs(canonical_ids, session)

        package = build_review_package(
            selected=selected,
            canonical_ids=canonical_ids,
            enriched_candidates=enriched,
            conflicts=conflicts,
            official_dataset_bytes=dataset_bytes,
            source_id_file_bytes=selection_bytes,
            rule_set_id=CANDIDATE_RULE_SET_ID,
            rule_set_version=CANDIDATE_RULE_SET_VERSION,
            generated_at=generated_at,
        )
    except ReviewPackageError as exc:
        _emit_error(str(exc))
        return 1
    except SQLAlchemyError:
        _emit_error("Database review-package generation failed safely.")
        return 1
    finally:
        engine.dispose()

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "candidate_review.csv").write_bytes(package.candidate_review_csv)
    (output_dir / "reference_labeling_sheet.csv").write_bytes(package.reference_labeling_sheet_csv)
    (output_dir / "review_manifest.json").write_bytes(package.manifest_json)

    print(json.dumps(package.manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
