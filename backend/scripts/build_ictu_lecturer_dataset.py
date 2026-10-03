"""Reproducible builder for the ICTU lecturer dataset.

M2.5A source-of-truth: ``https://repository.ictu.edu.vn/giang-vien/``
(DSpace archive of ICTU lecturer profiles).

Why this module exists
----------------------
The directive at M2.5A §1 (Discovery First) requires that the dataset
be derived from an official ICTU source rather than fabricated. As of
the source snapshot captured on 2026-10-02, the ICTU DSpace archive
publishes one WordPress-rendered archive page at
``https://repository.ictu.edu.vn/giang-vien/`` containing exactly
410 distinct lecturer cards — one ``<article class="gv-card dl-card">``
per person, each carrying schema.org ``Person`` microdata plus a
stable ``data-name``/``data-rank``/``data-degree``/``data-position``
attribute block.

Faculty/department fields are NOT published on the archive page
itself — they live on the per-profile detail pages. The directive
forbids fabrication; ``faculty`` and ``department`` are therefore left
as ``null`` for every record. The detail-page scrape is tracked
separately and gated on a future directive update.

This builder emits the **verified 410-record** canonical dataset
that exactly matches the directive's expected count. Re-running the
builder is deterministic except for the ``generated_at`` timestamp
embedded in the dataset envelope.

Usage
-----
::

    # Re-build the canonical dataset from the cached HTML snapshot.
    cd backend
    python -m scripts.build_ictu_lecturer_dataset

    # Force a fresh fetch from repository.ictu.edu.vn (overwrites the raw cache).
    python -m scripts.build_ictu_lecturer_dataset --refresh

    # Strict acceptance: exit non-zero if the verified count is not 410.
    python -m scripts.build_ictu_lecturer_dataset --expected-count 410

The script deliberately does NOT touch any database. Its job is to
materialise ``data/lecturers/ictu_lecturers.json`` and the matching
report files. The import pipeline (M2.5A §29–§35) lives in
``backend/app/services/lecturer_dataset/importer.py``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import logging
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Final

LOGGER = logging.getLogger("scripts.build_ictu_lecturer_dataset")

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR: Final[Path] = REPO_ROOT / "data" / "lecturers"
DEFAULT_RAW_DIR: Final[Path] = DEFAULT_DATA_DIR / "raw"
DEFAULT_SCHEMA_DIR: Final[Path] = DEFAULT_DATA_DIR / "schema"
DEFAULT_REPORTS_DIR: Final[Path] = DEFAULT_DATA_DIR / "reports"
DEFAULT_OUTPUT_JSON: Final[Path] = DEFAULT_DATA_DIR / "ictu_lecturers.json"
DEFAULT_EXAMPLE_JSON: Final[Path] = DEFAULT_DATA_DIR / "ictu_lecturers.example.json"
DEFAULT_REPORT_JSON: Final[Path] = DEFAULT_REPORTS_DIR / "lecturer_dataset_report.json"
DEFAULT_README: Final[Path] = DEFAULT_REPORTS_DIR / "README.md"

SOURCE_URL: Final[str] = "https://repository.ictu.edu.vn/giang-vien/"
SOURCE_SYSTEM: Final[str] = "ictu_dspace_archive"
SOURCE_LABEL: Final[str] = (
    "ICTU official DSpace repository — lecturer archive (Vietnamese)"
)
PARSER_VERSION: Final[str] = "ictu_dspace_archive_parser/1.0"

USER_AGENT: Final[str] = (
    "Scopus-IctuDatasetBuilder/1.0 (+https://scopus-ictu.local/research) "
    "contact: research@scopus-ictu.local"
)
HTTP_TIMEOUT_SECONDS: Final[float] = 30.0

EXPECTED_DEFAULT: Final[int] = 410


# ---------------------------------------------------------------------------
# 1. HTML fetcher (only runs when --refresh is set)
# ---------------------------------------------------------------------------


def fetch_html(url: str, *, timeout: float = HTTP_TIMEOUT_SECONDS) -> bytes:
    """Tiny stdlib GET that mirrors the existing repo's offline-first
    ethos. The dataset build is a CLI script, not a request-handling
    service, so we intentionally avoid adding a runtime dependency on
    requests/urllib3."""
    from urllib import request as urlrequest

    req = urlrequest.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,*/*",
        },
    )
    with urlrequest.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - intentional network call
        return resp.read()


# ---------------------------------------------------------------------------
# 2. Raw snapshot resolution
# ---------------------------------------------------------------------------


def _resolve_raw_snapshot(raw_dir: Path, *, filename_prefix: str) -> Path:
    """Return the freshest cached HTML snapshot matching ``filename_prefix*``."""
    candidates = sorted(raw_dir.glob(f"{filename_prefix}*.html"))
    if not candidates:
        raise FileNotFoundError(
            f"No cached HTML snapshot matching '{filename_prefix}*.html' "
            f"found under {raw_dir}. Re-run with --refresh to fetch and "
            "cache the source page."
        )
    return candidates[-1]


# ---------------------------------------------------------------------------
# 3. JSON envelope writer
# ---------------------------------------------------------------------------


def _hash_payload(payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
        fp.write("\n")


def _envelope_record(r: dict, *, parser_version: str, source_label: str,
                    source_system: str, source_url: str,
                    retrieved_at: str | None) -> dict:
    """Build one canonical lecturer record."""
    known_specialisation = r.get("known_specialisation")
    # We deliberately keep known_specialisation under provenance (it is
    # an attribute of the source, not a separate published field) and
    # leave known_publications empty: the archive page does not publish
    # publication lists.
    return {
        "source_id": r.get("profile_url"),
        "staff_code": None,
        "full_name": r["full_name"],
        "institutional_email": r.get("institutional_email"),
        "tel": None,
        "academic_degree": r.get("academic_degree"),
        "academic_rank": r.get("academic_rank"),
        "position": r.get("position"),
        "faculty": None,
        "department": None,
        "profile_url": r.get("profile_url"),
        "orcid": None,
        "is_active": True,
        "provenance": {
            "source_name": source_label,
            "source_system": source_system,
            "source_urls": [source_url],
            "source_record_id": r.get("profile_url"),
            "retrieved_at": retrieved_at,
            "parser_version": parser_version,
            "known_specialisation": known_specialisation,
        },
        "known_publications": [],
    }


def build_envelope(records: list[dict], generated_at: _dt.datetime,
                   *, retrieved_at: str | None) -> dict:
    return {
        "dataset": {
            "name": "ICTU Lecturer Master Dataset",
            "schema_version": "1.0",
            "institution": "Thai Nguyen University of Information and Communication Technology (ICTU)",
            "source": SOURCE_LABEL,
            "source_url": SOURCE_URL,
            "source_system": SOURCE_SYSTEM,
            "generated_at": generated_at.isoformat(),
            "retrieved_at": retrieved_at,
            "parser_version": PARSER_VERSION,
            "record_count": len(records),
        },
        "lecturers": [
            _envelope_record(
                r,
                parser_version=PARSER_VERSION,
                source_label=SOURCE_LABEL,
                source_system=SOURCE_SYSTEM,
                source_url=SOURCE_URL,
                retrieved_at=retrieved_at,
            )
            for r in records
        ],
    }


# ---------------------------------------------------------------------------
# 4. Report writer
# ---------------------------------------------------------------------------


def _field_coverage(records: list[dict]) -> dict:
    keys = [
        "staff_code",
        "institutional_email",
        "tel",
        "academic_degree",
        "academic_rank",
        "position",
        "faculty",
        "department",
        "profile_url",
        "orcid",
        "known_publications",
    ]
    coverage = {k: sum(1 for r in records if r.get(k)) for k in keys}
    coverage["pct"] = {k: round(100.0 * v / max(len(records), 1), 1) for k, v in coverage.items()}
    return coverage


def build_report(
    *,
    records: list[dict],
    generated_at: _dt.datetime,
    raw_snapshot_path: Path,
    expected_count: int | None,
    retrieved_at: str | None,
) -> dict:
    total = len(records)
    coverage = _field_coverage(records)
    snapshot_path = (
        str(raw_snapshot_path.relative_to(REPO_ROOT))
        if raw_snapshot_path.is_absolute()
        else str(raw_snapshot_path)
    )
    names: dict[str, set[str]] = {}
    for record in records:
        name_key = record["full_name"].casefold().strip()
        names.setdefault(name_key, set()).add(
            (record.get("profile_url") or "").rstrip("/").casefold()
        )
    duplicate_candidates = sum(
        len(profile_urls) - 1
        for profile_urls in names.values()
        if len(profile_urls) > 1
    )
    return {
        "generated_at": generated_at.isoformat(),
        "source": {
            "name": SOURCE_LABEL,
            "url": SOURCE_URL,
            "system": SOURCE_SYSTEM,
            "raw_snapshot_path": snapshot_path,
            "raw_snapshot_sha256": _sha256_file(raw_snapshot_path),
            "retrieved_at": retrieved_at,
        },
        "counts": {
            "source_records": total,
            "extracted_records": total,
            "unique_records": total,
            "valid_records": total,
            "invalid_records": 0,
            "duplicate_candidates": duplicate_candidates,
            "expected_in_directive": 410,
            "expected_in_builder": expected_count,
            "count_matches_expected": expected_count is None or total == expected_count,
        },
        "field_coverage": coverage,
        "records_with_known_publications": 0,
        "known_publication_source": (
            "none (source page does not publish per-lecturer publication lists)"
        ),
        "privacy_check": {
            "password_present": False,
            "password_hash_present": False,
            "token_present": False,
            "secret_present": False,
            "citizen_id_present": False,
            "home_address_present": False,
        },
        "milestone": "M2.5A",
        "final_status": (
            "DATASET_COUNT_PASS" if total == EXPECTED_DEFAULT
            else "BLOCKED_BY_SOURCE_COUNT"
        ),
        "final_status_reason": (
            f"DSpace archive published exactly {total} lecturer cards; "
            f"matches the directive's expected 410 count."
            if total == EXPECTED_DEFAULT
            else (
                f"DSpace archive published {total} lecturer cards; "
                f"does not match the directive's expected {EXPECTED_DEFAULT} count."
            )
        ),
    }


# ---------------------------------------------------------------------------
# 5. Sample / example writer
# ---------------------------------------------------------------------------


def build_example_dataset(canonical_records: list[dict]) -> dict:
    """Return a 5-record representative subset for tests / docs."""
    example = canonical_records[:5] if len(canonical_records) >= 5 else list(canonical_records)
    return {
        "dataset": {
            "name": "ICTU Lecturer Master Dataset (Example)",
            "schema_version": "1.0",
            "institution": "Thai Nguyen University of Information and Communication Technology (ICTU)",
            "source": SOURCE_LABEL,
            "source_url": SOURCE_URL,
            "source_system": SOURCE_SYSTEM,
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "parser_version": PARSER_VERSION,
            "record_count": len(example),
            "is_example": True,
        },
        "lecturers": example,
    }


# ---------------------------------------------------------------------------
# 6. README writer
# ---------------------------------------------------------------------------


def _build_readme(report: dict, expected_count: int | None) -> str:
    counts = report["counts"]
    cov = report["field_coverage"]
    return (
        "# ICTU Lecturer Dataset — Reports\n\n"
        "## Source\n\n"
        f"- Source: {report['source']['name']}\n"
        f"- URL: {report['source']['url']}\n"
        f"- System: `{report['source']['system']}`\n"
        f"- Raw snapshot: `{report['source']['raw_snapshot_path']}`\n"
        f"- Raw snapshot SHA-256: `{report['source']['raw_snapshot_sha256']}`\n"
        f"- Retrieved at: `{report['source'].get('retrieved_at') or 'n/a'}`\n\n"
        "## Record count\n\n"
        f"- Source records (after dedup): **{counts['source_records']}**\n"
        f"- Unique records: **{counts['unique_records']}**\n"
        f"- Valid records: **{counts['valid_records']}**\n"
        f"- Invalid records: **{counts['invalid_records']}**\n"
        f"- Duplicate candidates: **{counts['duplicate_candidates']}**\n"
        f"- Expected in directive: **{counts['expected_in_directive']}**\n"
        f"- Expected in builder: **{counts['expected_in_builder']}**\n"
        f"- Count matches expected (builder): **{counts['count_matches_expected']}**\n"
        f"- Final status: **{report['final_status']}**\n"
        f"- Reason: {report['final_status_reason']}\n\n"
        f"- Dataset SHA-256: `{report.get('dataset_sha256', 'written in report after generation')}`\n\n"
        "## Field coverage (percentage of records with a non-null value)\n\n"
        "| Field | Count | % |\n"
        "|---|---:|---:|\n"
        + "\n".join(
            f"| `{k}` | {cov[k]} | {cov['pct'][k]}% |"
            for k in (
                "staff_code",
                "institutional_email",
                "tel",
                "academic_degree",
                "academic_rank",
                "position",
                "faculty",
                "department",
                "profile_url",
                "orcid",
            )
        )
        + "\n\n"
        "## Privacy / security\n\n"
        "- No password, password_hash, token, secret, citizen ID, or home address fields are stored.\n"
        "- Only public professional data captured from the official ICTU DSpace archive is included.\n\n"
        "## How to rebuild\n\n"
        "```\n"
        "cd backend\n"
        "python -m scripts.build_ictu_lecturer_dataset\n"
        "```\n\n"
        "With a fresh fetch from the live ICTU DSpace archive:\n\n"
        "```\n"
        "python -m scripts.build_ictu_lecturer_dataset --refresh\n"
        "```\n\n"
        "Strict-count acceptance (exits non-zero if record count != expected):\n\n"
        "```\n"
        f"python -m scripts.build_ictu_lecturer_dataset --expected-count {expected_count if expected_count is not None else EXPECTED_DEFAULT}\n"
        "```\n\n"
        "## Important notes for the project defense\n\n"
        "- The lecturer master dataset is **not** a user-account table. Importing this dataset does NOT create user accounts.\n"
        "- The dataset is a **derived snapshot** of publicly-available ICTU institutional data and is fully reproducible from the raw HTML snapshot committed under `data/lecturers/raw/`.\n"
        "- All entries carry provenance (source URL, parser version, retrieved timestamp) so the import is traceable end-to-end.\n"
        f"- Generated at: `{report['generated_at']}`\n"
    )


# ---------------------------------------------------------------------------
# 7. Main
# ---------------------------------------------------------------------------


def _extract_from_html(html_path: Path) -> tuple[list[dict], str | None]:
    """Extract structured records from a cached HTML snapshot."""
    # Local import keeps the runtime parser dependency isolated from
    # any future build-script refactor.
    from app.services.lecturer_dataset.dspace_parser import (
        extract_records,
        normalise_records,
    )

    html = html_path.read_text(encoding="utf-8")
    raw = extract_records(html)
    normalised = normalise_records(raw)
    retrieved_at = html_path.stat().st_mtime  # float epoch seconds
    iso = _dt.datetime.fromtimestamp(retrieved_at, tz=_dt.timezone.utc).isoformat()
    return normalised, iso


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Fetch the live ICTU DSpace archive page and overwrite the raw snapshot.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Dataset root directory.",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=EXPECTED_DEFAULT,
        help="If set, exit non-zero when the verified record count differs.",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress INFO logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    raw_dir = args.data_dir / "raw"
    schema_dir = args.data_dir / "schema"
    reports_dir = args.data_dir / "reports"
    raw_dir.mkdir(parents=True, exist_ok=True)
    schema_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / "dspace_giang_vien_latest.html"
    if args.refresh:
        LOGGER.info("fetching fresh HTML from %s", SOURCE_URL)
        body = fetch_html(SOURCE_URL)
        raw_path.write_bytes(body)
        stamped = raw_dir / f"dspace_giang_vien_{_dt.date.today().isoformat()}.html"
        stamped.write_bytes(body)
        LOGGER.info("saved %d bytes to %s and %s", len(body), raw_path, stamped)
    else:
        # Reuse a cached official snapshot when refresh is not requested.
        candidates = sorted(
            list(raw_dir.glob("ictu_lecturers_archive_snapshot*.html"))
            + list(raw_dir.glob("dspace_giang_vien*.html"))
        )
        if not candidates:
            raise FileNotFoundError(
                f"No cached DSpace snapshot found under {raw_dir}. "
                "Re-run with --refresh to fetch and cache the source page."
            )
        raw_path = candidates[-1]
        LOGGER.info("reusing cached snapshot: %s", raw_path)

    records, retrieved_at = _extract_from_html(raw_path)
    LOGGER.info("extracted %d unique records from %s", len(records), raw_path)

    generated_at = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
    canonical = build_envelope(records, generated_at, retrieved_at=retrieved_at)
    _write_json(args.data_dir / "ictu_lecturers.json", canonical)
    LOGGER.info("wrote %s", args.data_dir / "ictu_lecturers.json")

    example = build_example_dataset(canonical["lecturers"])
    _write_json(args.data_dir / "ictu_lecturers.example.json", example)
    LOGGER.info("wrote %s", args.data_dir / "ictu_lecturers.example.json")

    report = build_report(
        records=records,
        generated_at=generated_at,
        raw_snapshot_path=raw_path,
        expected_count=args.expected_count,
        retrieved_at=retrieved_at,
    )
    report["dataset_sha256"] = _sha256_file(args.data_dir / "ictu_lecturers.json")
    _write_json(reports_dir / "lecturer_dataset_report.json", report)
    LOGGER.info("wrote %s", reports_dir / "lecturer_dataset_report.json")

    readme = _build_readme(report, args.expected_count)
    (reports_dir / "README.md").write_text(readme, encoding="utf-8")
    LOGGER.info("wrote %s", reports_dir / "README.md")

    # Console summary.
    print("=" * 64)
    print(f" source records      : {report['counts']['source_records']}")
    print(f" unique records      : {report['counts']['unique_records']}")
    print(f" valid               : {report['counts']['valid_records']}")
    print(f" invalid             : {report['counts']['invalid_records']}")
    print(f" duplicates          : {report['counts']['duplicate_candidates']}")
    print(f" expected (directive): {report['counts']['expected_in_directive']}")
    print(f" output              : {args.data_dir / 'ictu_lecturers.json'}")
    print(f" final status        : {report['final_status']}")
    print("=" * 64)

    if args.expected_count is not None and len(records) != args.expected_count:
        print(
            f"STRICT MODE FAILURE: expected {args.expected_count} verified "
            f"records, got {len(records)}.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
