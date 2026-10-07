"""CLI: evaluate candidate-retrieval quality against a reference CSV.

Usage:
    python backend/scripts/evaluate_matching_reference.py \\
        --reference <path/to/reference.csv> \\
        --lecturer-dataset data/lecturers/ictu_lecturers.json \\
        [--json-out <path/to/output.json>]

Performs READ-ONLY queries against the application database.
No rows are inserted or updated.

DB connection is loaded from the existing application settings
(app.core.config.settings.database_url).  No credentials are hardcoded
or emitted.

Refuses to run when settings.environment == "prod".

The read-only transaction guard is fail-closed: if PostgreSQL rejects
SET TRANSACTION READ ONLY, the script exits with a non-zero code rather
than continuing with possible write access.

Exit codes:
    0  success
    1  validation, environment, or evaluation error
    2  usage / file / import error
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Evaluate candidate-retrieval quality against a reference CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--reference", required=True, help="Path to the reference CSV file.")
    p.add_argument(
        "--lecturer-dataset",
        required=True,
        help="Path to the official ICTU lecturer JSON dataset.",
    )
    p.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write the JSON output. Defaults to stdout.",
    )
    return p


def _dataclass_to_dict(obj: object) -> object:
    """Recursively convert dataclasses and frozensets to JSON-serialisable types."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dataclass_to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_dataclass_to_dict(i) for i in obj]
    if isinstance(obj, frozenset):
        return sorted(_dataclass_to_dict(i) for i in obj)
    if isinstance(obj, UUID):
        return str(obj)
    return obj


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    reference_path = Path(args.reference)
    dataset_path = Path(args.lecturer_dataset)

    if not reference_path.exists():
        _emit_error(f"Reference file not found: {reference_path}", args.json_out)
        return 2
    if not dataset_path.exists():
        _emit_error(f"Lecturer dataset not found: {dataset_path}", args.json_out)
        return 2

    try:
        from app.core.config import settings
        from app.services.matching.candidate_persistence import (
            CANDIDATE_RULE_SET_ID,
            CANDIDATE_RULE_SET_VERSION,
        )
        from app.services.matching.evaluation import (
            EvaluationInputError,
            ReferenceValidationError,
            evaluate_candidate_retrieval,
            generate_pairs_from_current_production,
            load_scopus_corpus_ids,
            parse_reference_csv,
            resolve_lecturers_from_db,
            validate_against_lecturer_dataset,
        )
    except ImportError as exc:
        _emit_error(
            f"Import failed: {exc}. Run from repo root with backend/ on PYTHONPATH.",
            args.json_out,
        )
        return 2

    # --- Guard: refuse to run in production environment --------------------
    if settings.environment.lower() == "prod":
        _emit_error(
            "Evaluation CLI refused: environment=prod. "
            "Run only against non-production databases.",
            args.json_out,
        )
        return 1

    # --- Step 1: validate reference CSV ------------------------------------
    try:
        ref_bytes = reference_path.read_bytes()
        records = parse_reference_csv(ref_bytes)
    except ReferenceValidationError as exc:
        _emit_error(str(exc), args.json_out)
        return 1
    except UnicodeDecodeError as exc:
        _emit_error(f"Encoding error in reference CSV: {exc}", args.json_out)
        return 1

    # --- Step 2: cross-check against lecturer dataset ----------------------
    try:
        validate_against_lecturer_dataset(records, dataset_path)
    except ReferenceValidationError as exc:
        _emit_error(str(exc), args.json_out)
        return 1

    # --- Step 3: connect to DB using application settings ------------------
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import Session
    except ImportError as exc:
        _emit_error(f"SQLAlchemy import failed: {exc}", args.json_out)
        return 2

    # Use settings.database_url — never print the URL
    engine = create_engine(settings.database_url)

    ref_sha256 = hashlib.sha256(ref_bytes).hexdigest()
    evaluated_at = datetime.now(timezone.utc).isoformat()

    try:
        with Session(engine) as session:
            # Fail-closed read-only transaction guard.
            # If PostgreSQL refuses, exit immediately — do NOT continue.
            try:
                session.execute(text("SET TRANSACTION READ ONLY"))
            except Exception as exc:
                _emit_error(
                    f"Could not establish read-only transaction: {exc}. Refusing to continue.",
                    args.json_out,
                )
                return 1

            resolved_lecturers, resolve_errors = resolve_lecturers_from_db(records, session)
            if resolve_errors:
                _emit_error(
                    "Lecturer resolution errors:\n" + "\n".join(resolve_errors),
                    args.json_out,
                )
                return 1

            scopus_corpus_ids = load_scopus_corpus_ids(session)

            # Audit correction: use current production CandidateGenerator,
            # NOT persisted LecturerScopusCandidate (PENDING status).
            generated_pairs = generate_pairs_from_current_production(
                resolved_lecturers, session
            )

        evaluation = evaluate_candidate_retrieval(
            reference_records=records,
            resolved_lecturers=resolved_lecturers,
            scopus_corpus_ids=scopus_corpus_ids,
            generated_pairs_by_lecturer_db_id=generated_pairs,
        )
    except EvaluationInputError as exc:
        _emit_error(str(exc), args.json_out)
        return 1
    finally:
        engine.dispose()

    # --- Step 4: emit deterministic JSON output ----------------------------
    output = {
        "schema_version": "1.0",
        "evaluated_at": evaluated_at,
        "reference_dataset_sha256": ref_sha256,
        "candidate_rule_set_id": CANDIDATE_RULE_SET_ID,
        "candidate_rule_set_version": CANDIDATE_RULE_SET_VERSION,
        "metrics": _dataclass_to_dict(evaluation.metrics),
        "cases": _dataclass_to_dict(evaluation.cases),
    }

    output_json = json.dumps(output, ensure_ascii=False, indent=2)

    if args.json_out:
        Path(args.json_out).write_text(output_json, encoding="utf-8")
        print(f"Evaluation written to: {args.json_out}")
    else:
        print(output_json)

    return 0


def _emit_error(message: str, json_out: str | None) -> None:
    payload = json.dumps({"error": message}, ensure_ascii=False)
    if json_out:
        Path(json_out).write_text(payload, encoding="utf-8")
    print(payload, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
