"""CLI: validate a matching reference CSV against the official lecturer dataset.

Usage:
    python backend/scripts/validate_matching_reference.py \\
        --reference <path/to/reference.csv> \\
        --lecturer-dataset data/lecturers/ictu_lecturers.json

Exit codes:
    0  valid
    1  validation error (input-validation, not unexpected crash)
    2  usage/file error

No database connection required.
No secrets emitted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate a matching reference CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--reference", required=True, help="Path to the reference CSV file.")
    p.add_argument(
        "--lecturer-dataset",
        required=True,
        help="Path to the official ICTU lecturer JSON dataset.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    reference_path = Path(args.reference)
    dataset_path = Path(args.lecturer_dataset)

    if not reference_path.exists():
        print(
            json.dumps(
                {
                    "validation_status": "ERROR",
                    "error": f"Reference file not found: {reference_path}",
                }
            )
        )
        return 2

    if not dataset_path.exists():
        print(
            json.dumps(
                {
                    "validation_status": "ERROR",
                    "error": f"Lecturer dataset not found: {dataset_path}",
                }
            )
        )
        return 2

    # Import evaluation module (relative to repo root — assumes backend/ on sys.path
    # or script run from repo root with PYTHONPATH set appropriately)
    try:
        from app.services.matching.evaluation import (
            ReferenceValidationError,
            parse_reference_csv,
            validate_against_lecturer_dataset,
        )
    except ImportError as exc:
        print(
            json.dumps(
                {
                    "validation_status": "ERROR",
                    "error": f"Import failed: {exc}. Run from repo root with backend/ on PYTHONPATH.",
                }
            )
        )
        return 2

    # Parse
    try:
        content = reference_path.read_bytes()
        records = parse_reference_csv(content)
    except ReferenceValidationError as exc:
        summary = {
            "validation_status": "INVALID",
            "error": exc.message,
            "issues": [
                {
                    "row": issue.row_number,
                    "field": issue.field,
                    "message": issue.message,
                }
                for issue in exc.issues
            ],
        }
        print(json.dumps(summary, ensure_ascii=False))
        return 1
    except UnicodeDecodeError as exc:
        print(json.dumps({"validation_status": "INVALID", "error": f"Encoding error: {exc}"}))
        return 1

    # Cross-check against lecturer dataset
    try:
        validate_against_lecturer_dataset(records, dataset_path)
    except ReferenceValidationError as exc:
        summary = {
            "validation_status": "INVALID",
            "error": exc.message,
            "issues": [
                {
                    "row": issue.row_number,
                    "field": issue.field,
                    "message": issue.message,
                }
                for issue in exc.issues
            ],
        }
        print(json.dumps(summary, ensure_ascii=False))
        return 1

    match_count = sum(1 for r in records if r.decision.decision == "MATCH")
    no_match_count = len(records) - match_count

    print(
        json.dumps(
            {
                "validation_status": "VALID",
                "reference_count": len(records),
                "match_count": match_count,
                "no_match_count": no_match_count,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
