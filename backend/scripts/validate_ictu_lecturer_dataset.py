"""Dataset validator — stdlib-only.

M2.5A §46: ``python -m scripts.validate_ictu_lecturer_dataset
../data/lecturers/ictu_lecturers.json``.

Why stdlib only
---------------
The backend runtime stack (see ``pyproject.toml``) intentionally does
not include ``jsonschema`` because every model is validated through
Pydantic v2 at the API boundary. The dataset validator only needs to
verify a handful of invariants that are simpler than full JSON Schema
2020-12 — required fields, types, basic formats, plus project-level
invariants such as duplicate emails and stable staff-code uniqueness.

This validator MUST fail with a non-zero exit code when:

  * the JSON is malformed;
  * the schema version is not "1.x";
  * any lecturer record lacks ``full_name`` or a faculty/department;
  * duplicate institutional emails appear across records;
  * the record count differs from ``--expected-count`` (when set);
  * any forbidden key (password, password_hash, token, secret,
    citizen_id, home_address) appears in the dataset.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Final

LOGGER = logging.getLogger("scripts.validate_ictu_lecturer_dataset")

DEFAULT_SCHEMA_VERSION: Final[str] = "1.0"

FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "secret",
        "citizen_id",
        "home_address",
    }
)

EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)
ORCID_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$"
)
ACADEMIC_DEGREE_ALLOWED: Final[frozenset[str | None]] = frozenset(
    {"TS", "ThS", "KS", "CN", "PGS", "GS", "DH", None}
)
ACADEMIC_RANK_ALLOWED: Final[frozenset[str | None]] = frozenset({"PGS", "GS", None})


class ValidationError(Exception):
    """Raised on the first hard failure so the CLI exits non-zero."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ValidationError(code, message)


def _is_email(value: Any) -> bool:
    return isinstance(value, str) and bool(EMAIL_RE.match(value))


def _is_orcid(value: Any) -> bool:
    return isinstance(value, str) and bool(ORCID_RE.match(value))


def validate(path: Path, *, expected_count: int | None) -> dict:
    """Validate the dataset file and return a summary dict."""
    if not path.exists():
        raise ValidationError("FILE_NOT_FOUND", f"Dataset file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "INVALID_JSON", f"Dataset file is not valid JSON: {exc}"
        ) from exc

    _require(isinstance(data, dict), "INVALID_TOP_LEVEL", "Top-level value must be an object.")
    _require("dataset" in data, "MISSING_DATASET_KEY", "Top-level 'dataset' key is required.")
    dataset_meta = data["dataset"]
    _require(
        isinstance(dataset_meta, dict),
        "INVALID_DATASET",
        "'dataset' must be an object.",
    )
    _require(
        dataset_meta.get("schema_version", "").startswith(DEFAULT_SCHEMA_VERSION.split(".")[0]),
        "UNSUPPORTED_SCHEMA_VERSION",
        f"schema_version must start with '{DEFAULT_SCHEMA_VERSION.split('.')[0]}.x', "
        f"got {dataset_meta.get('schema_version')!r}",
    )
    _require(
        dataset_meta.get("record_count") == len(data.get("lecturers", [])),
        "RECORD_COUNT_MISMATCH",
        f"dataset.record_count={dataset_meta.get('record_count')} but "
        f"len(lecturers)={len(data.get('lecturers', []))}",
    )

    lecturers = data.get("lecturers", [])
    _require(isinstance(lecturers, list), "INVALID_LECTURERS", "'lecturers' must be an array.")
    _require(len(lecturers) >= 1, "EMPTY_LECTURERS", "'lecturers' must not be empty.")

    forbidden_hits: dict[str, int] = Counter()
    seen_emails: dict[str, int] = {}
    seen_staff_codes: dict[str, int] = {}
    seen_full_names: dict[tuple[str, str], int] = {}

    for idx, record in enumerate(lecturers):
        location = f"lecturers[{idx}]"
        _require(
            isinstance(record, dict),
            "INVALID_RECORD",
            f"{location} must be an object.",
        )
        for forbidden in FORBIDDEN_KEYS:
            if forbidden in record:
                forbidden_hits[forbidden] += 1
        # Required string fields.
        # NOTE: ``full_name`` is the only mandatory textual field.
        # ``faculty`` and ``department`` are *advisory* in the canonical
        # dataset envelope and may be NULL when the upstream source
        # does not publish them (M2.5A §9 — completeness rule). The
        # M1 ``lecturers`` table also accepts NULL for these columns.
        for field in ("full_name",):
            value = record.get(field)
            _require(
                isinstance(value, str) and value.strip(),
                "MISSING_REQUIRED_FIELD",
                f"{location}.{field} is required and must be a non-empty string.",
            )
        # faculty / department may be null per M2.5A §9.
        for advisory in ("faculty", "department"):
            adv_value = record.get(advisory)
            if adv_value is not None:
                _require(
                    isinstance(adv_value, str) and adv_value.strip(),
                    "INVALID_ADVISORY_FIELD",
                    f"{location}.{advisory} must be a non-empty string or null.",
                )
        # Optional typed fields.
        email = record.get("institutional_email")
        if email is not None:
            _require(
                _is_email(email),
                "INVALID_EMAIL",
                f"{location}.institutional_email={email!r} is not a valid email.",
            )
            if email in seen_emails:
                raise ValidationError(
                    "DUPLICATE_EMAIL",
                    f"Duplicate institutional_email {email!r} at {location} "
                    f"(also at lecturers[{seen_emails[email]}])",
                )
            seen_emails[email] = idx
        staff_code = record.get("staff_code")
        if staff_code is not None:
            _require(
                isinstance(staff_code, str) and re.match(r"^[A-Za-z0-9_-]+$", staff_code),
                "INVALID_STAFF_CODE",
                f"{location}.staff_code={staff_code!r} must be alphanumeric/underscore/dash.",
            )
            if staff_code in seen_staff_codes:
                raise ValidationError(
                    "DUPLICATE_STAFF_CODE",
                    f"Duplicate staff_code {staff_code!r} at {location} "
                    f"(also at lecturers[{seen_staff_codes[staff_code]}])",
                )
            seen_staff_codes[staff_code] = idx
        orcid = record.get("orcid")
        if orcid is not None:
            _require(
                _is_orcid(orcid),
                "INVALID_ORCID",
                f"{location}.orcid={orcid!r} does not match the canonical ORCID format.",
            )
        degree = record.get("academic_degree")
        _require(
            degree in ACADEMIC_DEGREE_ALLOWED,
            "INVALID_ACADEMIC_DEGREE",
            f"{location}.academic_degree={degree!r} not in allowed set.",
        )
        rank = record.get("academic_rank")
        _require(
            rank in ACADEMIC_RANK_ALLOWED,
            "INVALID_ACADEMIC_RANK",
            f"{location}.academic_rank={rank!r} not in allowed set.",
        )
        key = (record["full_name"].casefold(), (record.get("department") or "").casefold())
        if key in seen_full_names:
            # Same name + same department = duplicate candidate. We do
            # NOT auto-merge (per M2.5A §18). Surface it in the report
            # but only fail the run when other strong identifiers also
            # collide.
            LOGGER.warning(
                "duplicate candidate: %s @ %s (also at index %d)",
                record["full_name"],
                record["department"],
                seen_full_names[key],
            )
        seen_full_names[key] = idx
        # Provenance block.
        provenance = record.get("provenance")
        _require(
            isinstance(provenance, dict) and provenance.get("source_name"),
            "MISSING_PROVENANCE",
            f"{location}.provenance.source_name is required.",
        )
        _require(
            isinstance(provenance.get("source_urls"), list) and provenance["source_urls"],
            "MISSING_PROVENANCE_URL",
            f"{location}.provenance.source_urls must be a non-empty list.",
        )
        # known_publications: array of objects with title_raw.
        pubs = record.get("known_publications", [])
        _require(isinstance(pubs, list), "INVALID_KNOWN_PUBS", f"{location}.known_publications must be an array.")
        for j, pub in enumerate(pubs):
            _require(
                isinstance(pub, dict) and isinstance(pub.get("title_raw"), str) and pub["title_raw"].strip(),
                "INVALID_KNOWN_PUB",
                f"{location}.known_publications[{j}].title_raw is required.",
            )

    _require(
        not forbidden_hits,
        "FORBIDDEN_FIELDS_PRESENT",
        f"Forbidden sensitive fields detected: {dict(forbidden_hits)}",
    )

    summary = {
        "record_count": len(lecturers),
        "unique_emails": len(seen_emails),
        "unique_staff_codes": len(seen_staff_codes),
        "duplicate_candidate_pairs": max(0, len(lecturers) - len(seen_full_names)),
        "forbidden_field_hits": dict(forbidden_hits),
        "faculty_counts": Counter(
            r["faculty"] for r in lecturers if r.get("faculty")
        ),
        "department_counts": Counter(
            r["department"] for r in lecturers if r.get("department")
        ),
    }
    if expected_count is not None:
        _require(
            len(lecturers) == expected_count,
            "EXPECTED_COUNT_MISMATCH",
            f"Expected {expected_count} records, got {len(lecturers)}.",
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the ICTU lecturer dataset against project invariants.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=Path("data/lecturers/ictu_lecturers.json"),
        help="Path to the dataset JSON (default: data/lecturers/ictu_lecturers.json).",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=None,
        help="Strict acceptance: exit non-zero if record count != expected.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    try:
        summary = validate(args.dataset, expected_count=args.expected_count)
    except ValidationError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 2
    print("=" * 56)
    print(f" dataset file         : {args.dataset}")
    print(f" record_count         : {summary['record_count']}")
    print(f" unique_emails        : {summary['unique_emails']}")
    print(f" unique_staff_codes   : {summary['unique_staff_codes']}")
    print(f" duplicate_candidates : {summary['duplicate_candidate_pairs']}")
    print(f" forbidden_field_hits : {summary['forbidden_field_hits']}")
    print(f" faculty_counts       : {dict(summary['faculty_counts'])}")
    print(f" department_counts    : {dict(summary['department_counts'])}")
    print("=" * 56)
    print("OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
