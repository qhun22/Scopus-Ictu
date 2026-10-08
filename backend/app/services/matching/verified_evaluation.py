"""Verified matching-quality evaluation — C3-A3.

Orchestration and provenance layer around the frozen C3-A1 evaluator.  It
verifies that the human-reviewed C3-A2 package, the official lecturer
dataset, the precommitted primary cohort, the rule-set metadata, and the
matching source code are exactly what produced the review context, then
delegates ALL metric semantics to ``app.services.matching.evaluation``.

No ranking, scoring, thresholds, or tuning.  No database writes.  This module
never writes to the human-confirmed reference file.
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import io
import json
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.matching import evaluation as a1
from app.services.matching import review_package as rp
from app.services.matching.candidate_persistence import (
    CANDIDATE_RULE_SET_ID,
    CANDIDATE_RULE_SET_VERSION,
    GENERATION_RULE_SET_ID,
    GENERATION_RULE_SET_VERSION,
    PUBLICATION_RULE_SET_ID,
    PUBLICATION_RULE_SET_VERSION,
)
from app.services.matching.review_package import (
    LABELING_SHEET_COLUMNS,
    MANIFEST_FIELDS,
    ReviewPackageError,
    parse_official_lecturers,
)

# ---------------------------------------------------------------------------
# Frozen audit anchors
# ---------------------------------------------------------------------------

FROZEN_A1_SHA = "e502e71fd33eeb93af1fde726b5b1cc5cf0b87f2"
FROZEN_A2_SHA = "a1e761c21622280845fd9f4958493d4acfe86dde"

FROZEN_MATCHING_BLOBS: tuple[tuple[str, str], ...] = (
    ("backend/app/services/matching/candidate_generator.py", "2e98f87d9d2f6b2709c4fd0aa061c7da8046d556"),
    (
        "backend/app/services/matching/publication_evidence_enricher.py",
        "0c855f9834e271b765ceac57f6c7578ab89ab475",
    ),
    ("backend/app/services/matching/candidate_types.py", "57f1a5a7e74fdcbe063fb111b19fd609ccab629a"),
)

COHORT_ALGORITHM = "SHA256_SEED_RANK_V1"
COHORT_SEED = "C3-A3-ICTU-PRIMARY-2026-V1"
COHORT_SIZE = 50

# The frozen Phase-1 official lecturer dataset.  Exactly two byte forms are
# accepted (Git autocrlf): repository LF content and the Windows CRLF checkout.
PHASE1_OFFICIAL_DATASET_SHA256_LF = "9428e0a2b009ecff1043b4dc796ed69a0fc64054594b0fb40ffa27bbed4ec82e"
PHASE1_OFFICIAL_DATASET_SHA256_CRLF = "ac4ed2d3f3c5fc7e73912ac9386b5710f4e015bbd7028e5b48a656dae3d4c3d4"
PHASE1_ACCEPTED_DATASET_SHA256: tuple[str, ...] = (
    PHASE1_OFFICIAL_DATASET_SHA256_LF,
    PHASE1_OFFICIAL_DATASET_SHA256_CRLF,
)

APPROVED_DATABASE_NAME = "scopus_c3_eval_v1"
# Explicitly named for clarity; every name other than the approved one is refused.
REJECTED_DATABASE_NAMES: tuple[str, ...] = ("scopus_m12_test", "scopus_ictu_acceptance_v2")
RESULT_SCHEMA_VERSION = "1.0"

# Evaluation-input fingerprint.  None == UNPINNED: official evaluation refused.
FINGERPRINT_SCHEMA_VERSION = 1
EXPECTED_INPUT_FINGERPRINT_SHA256: str | None = None

# Columns actually read by CandidateGenerator, PublicationEvidenceEnricher and
# lecturer resolution.  Names are listed sorted; every table's PK is "id".
FINGERPRINT_CONTENT_COLUMNS: dict[str, tuple[str, ...]] = {
    "lecturer_known_publications": ("doi_normalized", "id", "lecturer_id", "snapshot_id", "title_normalized"),
    "lecturer_source_snapshots": ("id", "lecturer_id"),
    "lecturers": ("full_name", "id", "repository_profile_url"),
    "publication_authors": ("id", "publication_id", "scopus_author_id"),
    "publications": ("doi", "eid", "id", "title", "title_normalized"),
    "scopus_author_name_variants": ("id", "scopus_author_id", "variant_name", "variant_type"),
    "scopus_authors": ("id", "preferred_name", "scopus_id"),
}
# Structural (primary-key set) only: raw payloads are never hashed.
FINGERPRINT_KEY_TABLES: tuple[str, ...] = ("raw_scopus_records", "scopus_imports")

LABEL_COLUMNS: tuple[str, ...] = (
    "decision",
    "expected_scopus_id",
    "confirmation_source",
    "confirmed_at",
    "notes",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BLOB_RE = re.compile(r"^[0-9a-f]{40}$")
_COUNT_FIELDS = (
    "selected_lecturer_count",
    "lecturers_with_candidates",
    "lecturers_without_candidates",
    "candidate_pair_count",
    "ambiguous_lecturer_count",
    "publication_conflict_count",
)
_SHA_FIELDS = (
    "official_lecturer_dataset_sha256",
    "candidate_review_sha256",
    "reference_labeling_sheet_sha256",
)
_TEXT_FIELDS = (
    "schema_version",
    "generated_at",
    "candidate_rule_set_id",
    "candidate_rule_set_version",
    "publication_rule_set_id",
    "publication_rule_set_version",
    "generation_rule_set_id",
    "generation_rule_set_version",
)


class VerificationError(Exception):
    """A provenance/integrity gate failed.  Message is safe to display."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Frozen Phase-1 official dataset
# ---------------------------------------------------------------------------


def verify_frozen_official_dataset(
    dataset_bytes: bytes, accepted: Iterable[str] | None = None
) -> str:
    """SHA-256 of the exact bytes must be one of the frozen Phase-1 hashes."""
    accepted_set = frozenset(PHASE1_ACCEPTED_DATASET_SHA256 if accepted is None else accepted)
    digest = sha256_hex(dataset_bytes)
    if digest not in accepted_set:
        raise VerificationError(
            "Official lecturer dataset is not the frozen C3-A3 Phase-1 snapshot."
        )
    return digest


# ---------------------------------------------------------------------------
# Primary cohort (selection depends ONLY on official source IDs)
# ---------------------------------------------------------------------------


def select_primary_cohort(
    dataset_bytes: bytes,
    *,
    seed: str = COHORT_SEED,
    size: int = COHORT_SIZE,
) -> tuple[str, ...]:
    """SHA256_SEED_RANK_V1: rank source IDs by SHA256(seed || 0x00 || id)."""
    try:
        official = parse_official_lecturers(dataset_bytes)
    except ReviewPackageError as exc:
        raise VerificationError(str(exc)) from None
    if len(official) < size:
        raise VerificationError(
            f"Official dataset has {len(official)} lecturers; cohort requires {size}."
        )
    seed_bytes = seed.encode("utf-8")

    def rank(source_id: str) -> tuple[str, str]:
        digest = hashlib.sha256(seed_bytes + b"\x00" + source_id.encode("utf-8")).hexdigest()
        return digest, source_id

    ranked = sorted((lecturer.source_id for lecturer in official), key=rank)
    return tuple(sorted(ranked[:size]))


def render_cohort_file(source_ids: Sequence[str]) -> bytes:
    return ("\n".join(source_ids) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# A2 manifest / package / dataset / cohort gates
# ---------------------------------------------------------------------------


def parse_review_manifest(manifest_bytes: bytes) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise VerificationError("review_manifest.json is not valid UTF-8 JSON.") from None
    if not isinstance(manifest, dict):
        raise VerificationError("review_manifest.json must be a JSON object.")

    missing = sorted(set(MANIFEST_FIELDS) - set(manifest))
    unknown = sorted(set(manifest) - set(MANIFEST_FIELDS))
    if missing:
        raise VerificationError(f"review_manifest.json missing fields: {missing}")
    if unknown:
        raise VerificationError(f"review_manifest.json has unknown fields: {unknown}")

    for name in _TEXT_FIELDS:
        if not isinstance(manifest[name], str) or not manifest[name]:
            raise VerificationError(f"review_manifest.json field {name} must be a non-empty string.")
    for name in _SHA_FIELDS:
        if not isinstance(manifest[name], str) or not _SHA256_RE.match(manifest[name]):
            raise VerificationError(f"review_manifest.json field {name} must be a SHA-256 hex digest.")
    source_sha = manifest["source_id_file_sha256"]
    if source_sha is not None and (not isinstance(source_sha, str) or not _SHA256_RE.match(source_sha)):
        raise VerificationError("review_manifest.json field source_id_file_sha256 is malformed.")
    for name in _COUNT_FIELDS:
        value = manifest[name]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise VerificationError(f"review_manifest.json field {name} must be a non-negative integer.")
    return manifest


def verify_package_hashes(
    manifest: Mapping[str, Any], candidate_review_bytes: bytes, labeling_sheet_bytes: bytes
) -> None:
    if sha256_hex(candidate_review_bytes) != manifest["candidate_review_sha256"]:
        raise VerificationError("candidate_review.csv does not match the review manifest hash.")
    if sha256_hex(labeling_sheet_bytes) != manifest["reference_labeling_sheet_sha256"]:
        raise VerificationError("reference_labeling_sheet.csv does not match the review manifest hash.")


def verify_dataset_and_cohort(
    manifest: Mapping[str, Any],
    dataset_bytes: bytes,
    source_id_file_bytes: bytes,
    committed_cohort_bytes: bytes,
) -> tuple[str, ...]:
    """Bind manifest, dataset, supplied cohort, committed cohort, and selection."""
    verify_frozen_official_dataset(dataset_bytes)
    if sha256_hex(dataset_bytes) != manifest["official_lecturer_dataset_sha256"]:
        raise VerificationError("Official lecturer dataset does not match the review manifest hash.")
    if manifest["source_id_file_sha256"] is None:
        raise VerificationError("Review package was not built from the primary cohort source-id file.")
    supplied_sha = sha256_hex(source_id_file_bytes)
    if supplied_sha != manifest["source_id_file_sha256"]:
        raise VerificationError("Source-id file does not match the review manifest hash.")
    if supplied_sha != sha256_hex(committed_cohort_bytes):
        raise VerificationError("Source-id file is not the committed primary cohort file.")
    if manifest["selected_lecturer_count"] != COHORT_SIZE:
        raise VerificationError(f"Review package must select exactly {COHORT_SIZE} lecturers.")

    cohort = select_primary_cohort(dataset_bytes)
    # Compared by lines, not bytes: Git autocrlf may check the file out as CRLF.
    # Byte identity is still enforced above against the manifest and committed copy.
    try:
        supplied_lines = tuple(source_id_file_bytes.decode("utf-8").splitlines())
    except UnicodeDecodeError:
        raise VerificationError("Source-id file is not valid UTF-8.") from None
    if supplied_lines != cohort:
        raise VerificationError("Source-id file is not the official SHA256_SEED_RANK_V1 primary cohort.")
    return cohort


def verify_rule_provenance(
    manifest: Mapping[str, Any],
    expected: Mapping[str, str] | None = None,
) -> dict[str, str]:
    expected = dict(expected) if expected is not None else current_rule_provenance()
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise VerificationError(f"Rule provenance mismatch for {key}; refusing a different experiment.")
    return expected


def current_rule_provenance() -> dict[str, str]:
    return {
        "candidate_rule_set_id": CANDIDATE_RULE_SET_ID,
        "candidate_rule_set_version": CANDIDATE_RULE_SET_VERSION,
        "publication_rule_set_id": PUBLICATION_RULE_SET_ID,
        "publication_rule_set_version": PUBLICATION_RULE_SET_VERSION,
        "generation_rule_set_id": GENERATION_RULE_SET_ID,
        "generation_rule_set_version": GENERATION_RULE_SET_VERSION,
    }


# ---------------------------------------------------------------------------
# Frozen matching-code gate (detects committed AND uncommitted changes)
# ---------------------------------------------------------------------------

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def _git(runner: Runner, repo_root: Path, *args: str) -> str:
    try:
        completed = runner(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        raise VerificationError("Git is unavailable; cannot verify frozen matching code.") from None
    output = (completed.stdout or "").strip()
    if completed.returncode != 0 or not _BLOB_RE.match(output):
        raise VerificationError("Git could not verify frozen matching code blobs.")
    return output


def verify_frozen_code(
    repo_root: Path,
    *,
    runner: Runner = subprocess.run,
    anchors: Iterable[tuple[str, str]] = FROZEN_MATCHING_BLOBS,
    frozen_sha: str = FROZEN_A2_SHA,
) -> tuple[dict[str, str], ...]:
    provenance: list[dict[str, str]] = []
    for path, expected in anchors:
        frozen = _git(runner, repo_root, "rev-parse", f"{frozen_sha}:{path}")
        if frozen != expected:
            raise VerificationError(f"Frozen blob anchor mismatch for {path}.")
        current = _git(runner, repo_root, "hash-object", "--", path)
        if current != expected:
            raise VerificationError(f"Matching code changed since the frozen review context: {path}.")
        provenance.append(
            {"path": path, "expected_frozen_blob_sha": expected, "current_blob_sha": current}
        )
    return tuple(provenance)


# ---------------------------------------------------------------------------
# Labeling sheets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Identity:
    email: str
    full_name: str


def _read_sheet(text: str, label: str) -> list[dict[str, str]]:
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise VerificationError(f"{label} is empty.") from None
    if tuple(h.strip() for h in header) != LABELING_SHEET_COLUMNS:
        raise VerificationError(f"{label} does not have the exact A1 8-column schema.")
    rows: list[dict[str, str]] = []
    for line in reader:
        if not any(cell.strip() for cell in line):
            continue
        if len(line) != len(LABELING_SHEET_COLUMNS):
            raise VerificationError(f"{label} has a row with the wrong number of columns.")
        rows.append(dict(zip(LABELING_SHEET_COLUMNS, line)))
    return rows


def _identity_index(rows: Sequence[Mapping[str, str]], label: str) -> dict[str, _Identity]:
    if len(rows) != COHORT_SIZE:
        raise VerificationError(f"{label} must have exactly {COHORT_SIZE} rows; found {len(rows)}.")
    index: dict[str, _Identity] = {}
    for row in rows:
        source_id = row["lecturer_source_id"].strip()
        if not source_id:
            raise VerificationError(f"{label} has an empty lecturer_source_id.")
        if source_id in index:
            raise VerificationError(f"{label} has a duplicate lecturer_source_id.")
        index[source_id] = _Identity(
            email=row["institutional_email"].strip().casefold(),
            full_name=row["lecturer_full_name"].strip(),
        )
    return index


def verify_blank_sheet(sheet_bytes: bytes, cohort: Iterable[str]) -> dict[str, _Identity]:
    try:
        text = sheet_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise VerificationError("reference_labeling_sheet.csv is not valid UTF-8.") from None
    rows = _read_sheet(text, "reference_labeling_sheet.csv")
    index = _identity_index(rows, "reference_labeling_sheet.csv")
    for row in rows:
        if any(row[column].strip() for column in LABEL_COLUMNS):
            raise VerificationError("Original reference_labeling_sheet.csv has been edited (labels not blank).")
    if set(index) != set(cohort):
        raise VerificationError("Original labeling sheet does not cover exactly the primary cohort.")
    return index


def decode_confirmed(confirmed_bytes: bytes) -> str:
    try:
        return confirmed_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise VerificationError("reference_confirmed.csv is not valid UTF-8.") from None


def verify_confirmed_identity(blank_index: Mapping[str, _Identity], confirmed_text: str) -> None:
    """Only the five label columns may change; row order may differ."""
    rows = _read_sheet(confirmed_text, "reference_confirmed.csv")
    confirmed = _identity_index(rows, "reference_confirmed.csv")
    if set(confirmed) != set(blank_index):
        raise VerificationError("reference_confirmed.csv lecturer set differs from the original sheet.")
    for source_id, original in blank_index.items():
        if confirmed[source_id] != original:
            raise VerificationError(
                f"Identity columns changed in reference_confirmed.csv for {source_id!r}."
            )


def parse_confirmed_labels(confirmed_text: str, dataset_path: Path) -> tuple[a1.ReferenceRecord, ...]:
    """Every cohort row must carry a complete, valid human decision (A1 rules)."""
    try:
        records = a1.parse_reference_csv(confirmed_text)
        a1.validate_against_lecturer_dataset(records, dataset_path)
    except a1.ReferenceValidationError as exc:
        issues = "; ".join(
            f"row {i.row_number}: {i.field}: {i.message}" for i in exc.issues[:20]
        )
        raise VerificationError(f"Human labels incomplete or invalid ({exc.message}) {issues}") from None
    if len(records) != COHORT_SIZE:
        raise VerificationError(f"Expected {COHORT_SIZE} complete labels; found {len(records)}.")
    return records


# ---------------------------------------------------------------------------
# Offline verification bundle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifiedInputs:
    manifest: dict[str, Any]
    cohort: tuple[str, ...]
    records: tuple[a1.ReferenceRecord, ...]
    rule_provenance: dict[str, str]
    code_provenance: tuple[dict[str, str], ...]
    hashes: dict[str, str]


def verify_offline_inputs(
    *,
    candidate_review_bytes: bytes,
    labeling_sheet_bytes: bytes,
    manifest_bytes: bytes,
    confirmed_bytes: bytes,
    dataset_bytes: bytes,
    dataset_path: Path,
    source_id_file_bytes: bytes,
    committed_cohort_bytes: bytes,
    repo_root: Path,
    runner: Runner = subprocess.run,
) -> VerifiedInputs:
    """All pre-database gates, in the official order."""
    manifest = parse_review_manifest(manifest_bytes)
    verify_package_hashes(manifest, candidate_review_bytes, labeling_sheet_bytes)
    cohort = verify_dataset_and_cohort(manifest, dataset_bytes, source_id_file_bytes, committed_cohort_bytes)
    code_provenance = verify_frozen_code(repo_root, runner=runner)
    rule_provenance = verify_rule_provenance(manifest)
    blank_index = verify_blank_sheet(labeling_sheet_bytes, cohort)
    confirmed_text = decode_confirmed(confirmed_bytes)
    verify_confirmed_identity(blank_index, confirmed_text)
    records = parse_confirmed_labels(confirmed_text, dataset_path)
    return VerifiedInputs(
        manifest=manifest,
        cohort=cohort,
        records=records,
        rule_provenance=rule_provenance,
        code_provenance=code_provenance,
        hashes={
            "review_manifest_sha256": sha256_hex(manifest_bytes),
            "candidate_review_sha256": sha256_hex(candidate_review_bytes),
            "reference_labeling_sheet_sha256": sha256_hex(labeling_sheet_bytes),
            "reference_confirmed_sha256": sha256_hex(confirmed_bytes),
            "official_lecturer_dataset_sha256": sha256_hex(dataset_bytes),
            "source_id_file_sha256": sha256_hex(source_id_file_bytes),
        },
    )


# ---------------------------------------------------------------------------
# Database gate and frozen A1 evaluation path
# ---------------------------------------------------------------------------


def is_approved_database(database_url: str) -> bool:
    """Configuration-level check (settings URL).  Not sufficient on its own."""
    from sqlalchemy.engine import make_url

    try:
        name = make_url(database_url).database
    except Exception:
        return False
    return name == APPROVED_DATABASE_NAME and name not in REJECTED_DATABASE_NAMES


READ_ONLY_SNAPSHOT_SQL = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"


def verify_connected_database(session: Any) -> None:
    """Connection-level check: the server's current_database() must match."""
    from sqlalchemy import text

    actual = session.execute(text("SELECT current_database()")).scalar_one()
    if actual != APPROVED_DATABASE_NAME or actual in REJECTED_DATABASE_NAMES:
        raise VerificationError("Connected database is not the approved C3 evaluation database.")


# ---------------------------------------------------------------------------
# Evaluation-input fingerprint (schema_version 1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TableFingerprint:
    table: str
    hash_kind: str  # "content" | "primary_key"
    columns: tuple[str, ...]
    row_count: int
    sha256: str


@dataclass(frozen=True)
class InputFingerprint:
    schema_version: int
    sha256: str
    tables: tuple[TableFingerprint, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "sha256": self.sha256,
            "tables": [
                {
                    "table": t.table,
                    "hash_kind": t.hash_kind,
                    "columns": list(t.columns),
                    "row_count": t.row_count,
                    "sha256": t.sha256,
                }
                for t in self.tables
            ],
        }


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _canonical_scalar(value: Any) -> Any:
    from uuid import UUID

    if value is None or isinstance(value, str):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise VerificationError(f"Unsupported value type in fingerprint input: {type(value).__name__}")


def _content_digest(table: str, columns: tuple[str, ...], rows: Iterable[Mapping[str, Any]]) -> TableFingerprint:
    canonical_rows: list[dict[str, Any]] = []
    for row in rows:
        missing = set(columns) - set(row)
        if missing:
            raise VerificationError(f"Fingerprint input for {table} is missing columns {sorted(missing)}.")
        canonical_rows.append({column: _canonical_scalar(row[column]) for column in columns})
    canonical_rows.sort(key=lambda r: r["id"])
    ids = [r["id"] for r in canonical_rows]
    if len(ids) != len(set(ids)) or any(not isinstance(i, str) for i in ids):
        raise VerificationError(f"Fingerprint input for {table} has duplicate or invalid primary keys.")
    return TableFingerprint(
        table, "content", columns, len(canonical_rows), sha256_hex(canonical_json_bytes(canonical_rows))
    )


def _key_digest(table: str, keys: Iterable[Any]) -> TableFingerprint:
    canonical_keys = sorted(_canonical_scalar(k) for k in keys)
    if len(canonical_keys) != len(set(canonical_keys)) or any(not isinstance(k, str) for k in canonical_keys):
        raise VerificationError(f"Fingerprint input for {table} has duplicate or invalid primary keys.")
    return TableFingerprint(
        table, "primary_key", ("id",), len(canonical_keys), sha256_hex(canonical_json_bytes(canonical_keys))
    )


def fingerprint_from_rows(
    content_rows: Mapping[str, Iterable[Mapping[str, Any]]],
    key_rows: Mapping[str, Iterable[Any]],
    *,
    schema_version: int = FINGERPRINT_SCHEMA_VERSION,
) -> InputFingerprint:
    """Pure fingerprint over already-loaded values (order of input irrelevant)."""
    if set(content_rows) != set(FINGERPRINT_CONTENT_COLUMNS) or set(key_rows) != set(FINGERPRINT_KEY_TABLES):
        raise VerificationError("Fingerprint input does not cover exactly the contracted tables.")
    tables = [
        _content_digest(table, FINGERPRINT_CONTENT_COLUMNS[table], content_rows[table])
        for table in FINGERPRINT_CONTENT_COLUMNS
    ] + [_key_digest(table, key_rows[table]) for table in FINGERPRINT_KEY_TABLES]
    tables.sort(key=lambda t: t.table)
    final_object = {
        "schema_version": schema_version,
        "tables": [
            {
                "table": t.table,
                "hash_kind": t.hash_kind,
                "columns": list(t.columns),
                "row_count": t.row_count,
                "sha256": t.sha256,
            }
            for t in tables
        ],
    }
    return InputFingerprint(schema_version, sha256_hex(canonical_json_bytes(final_object)), tuple(tables))


def _fingerprint_models() -> dict[str, Any]:
    from app.models.master_lecturer import Lecturer, LecturerKnownPublication, LecturerSourceSnapshot
    from app.models.publication import Publication, PublicationAuthor, ScopusAuthor, ScopusAuthorNameVariant
    from app.models.scopus_raw import RawScopusRecord, ScopusImport

    return {
        "lecturer_known_publications": LecturerKnownPublication,
        "lecturer_source_snapshots": LecturerSourceSnapshot,
        "lecturers": Lecturer,
        "publication_authors": PublicationAuthor,
        "publications": Publication,
        "scopus_author_name_variants": ScopusAuthorNameVariant,
        "scopus_authors": ScopusAuthor,
        "raw_scopus_records": RawScopusRecord,
        "scopus_imports": ScopusImport,
    }


def compute_input_fingerprint(session: Any) -> InputFingerprint:
    """SELECT-only load of the contracted columns, then the pure fingerprint.

    Call inside a REPEATABLE READ READ ONLY transaction so all tables come from
    one snapshot.  Raw payload columns are never selected.
    """
    from sqlalchemy import select

    models = _fingerprint_models()
    content_rows: dict[str, list[dict[str, Any]]] = {}
    for table, columns in FINGERPRINT_CONTENT_COLUMNS.items():
        model = models[table]
        if model.__tablename__ != table:
            raise VerificationError(f"Fingerprint model mapping mismatch for {table}.")
        result = session.execute(select(*(getattr(model, c) for c in columns)))
        content_rows[table] = [dict(row) for row in result.mappings().all()]
    key_rows: dict[str, list[Any]] = {}
    for table in FINGERPRINT_KEY_TABLES:
        model = models[table]
        if model.__tablename__ != table:
            raise VerificationError(f"Fingerprint model mapping mismatch for {table}.")
        key_rows[table] = list(session.execute(select(model.id)).scalars().all())
    return fingerprint_from_rows(content_rows, key_rows)


def require_pinned_fingerprint(expected: str | None = None) -> str:
    """Official evaluation is refused while the expected fingerprint is UNPINNED."""
    value = EXPECTED_INPUT_FINGERPRINT_SHA256 if expected is None else expected
    if value is None:
        raise VerificationError("Expected input fingerprint is UNPINNED; official evaluation refused.")
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        raise VerificationError("Expected input fingerprint is malformed; official evaluation refused.")
    return value


_RERENDER_GENERATED_AT = datetime(1970, 1, 1, tzinfo=timezone.utc)


def verify_package_rerender(
    session: Any,
    *,
    manifest: Mapping[str, Any],
    candidate_review_bytes: bytes,
    labeling_sheet_bytes: bytes,
    dataset_bytes: bytes,
    source_id_file_bytes: bytes,
) -> dict[str, Any]:
    """Prove the review package was produced from THIS database snapshot.

    Re-runs the frozen A2 pipeline (same functions the A2 builder CLI calls)
    with inputs taken only from the verified dataset/cohort bytes and the
    given session, then requires byte-equality of both CSVs and equality of
    every manifest field except ``generated_at``.  Package candidate data is
    never used to build the expected bytes.
    """
    # Hashes are recomputed from the supplied files, never trusted as declared.
    verify_package_hashes(manifest, candidate_review_bytes, labeling_sheet_bytes)
    try:
        official = rp.parse_official_lecturers(dataset_bytes)
        selected = rp.select_lecturers(official, rp.parse_source_id_file(source_id_file_bytes))
        canonical_ids = rp.resolve_canonical_lecturers_from_db(selected, session)
        enriched, conflicts = rp.generate_review_inputs(canonical_ids, session)
        rerendered = rp.build_review_package(
            selected=selected,
            canonical_ids=canonical_ids,
            enriched_candidates=enriched,
            conflicts=conflicts,
            official_dataset_bytes=dataset_bytes,
            source_id_file_bytes=source_id_file_bytes,
            rule_set_id=CANDIDATE_RULE_SET_ID,
            rule_set_version=CANDIDATE_RULE_SET_VERSION,
            generated_at=_RERENDER_GENERATED_AT,
        )
    except ReviewPackageError as exc:
        raise VerificationError(f"Review package re-render failed: {exc}") from None

    if rerendered.candidate_review_csv != candidate_review_bytes:
        raise VerificationError("candidate_review.csv is not byte-equal to the re-render from the database snapshot.")
    if rerendered.reference_labeling_sheet_csv != labeling_sheet_bytes:
        raise VerificationError(
            "reference_labeling_sheet.csv is not byte-equal to the re-render from the database snapshot."
        )
    differing = sorted(
        key
        for key in set(rerendered.manifest) | set(manifest)
        if key != "generated_at" and rerendered.manifest.get(key) != manifest.get(key)
    )
    if differing:
        raise VerificationError(f"review_manifest.json does not match the re-render for fields: {differing}")
    return {
        "verified": True,
        "candidate_review_sha256": sha256_hex(candidate_review_bytes),
        "reference_labeling_sheet_sha256": sha256_hex(labeling_sheet_bytes),
        "compared_manifest_fields": sorted(k for k in rerendered.manifest if k != "generated_at"),
    }


def verify_input_fingerprint(actual: InputFingerprint, expected: str | None = None) -> None:
    pinned = require_pinned_fingerprint(expected)
    if actual.schema_version != FINGERPRINT_SCHEMA_VERSION or actual.sha256 != pinned:
        raise VerificationError("Evaluation database fingerprint does not match the pinned fingerprint.")


def run_frozen_a1_evaluation(
    records: tuple[a1.ReferenceRecord, ...], session: Any
) -> a1.CandidateRetrievalEvaluation:
    resolved, errors = a1.resolve_lecturers_from_db(records, session)
    if errors:
        raise VerificationError(
            f"{len(errors)} cohort lecturer(s) could not be resolved to exactly one canonical row."
        )
    corpus = a1.load_scopus_corpus_ids(session)
    pairs = a1.generate_pairs_from_current_production(resolved, session)
    try:
        return a1.evaluate_candidate_retrieval(
            reference_records=records,
            resolved_lecturers=resolved,
            scopus_corpus_ids=corpus,
            generated_pairs_by_lecturer_db_id=pairs,
        )
    except a1.EvaluationInputError:
        raise VerificationError("Frozen A1 evaluator rejected incomplete lecturer resolution.") from None


# ---------------------------------------------------------------------------
# Safe result
# ---------------------------------------------------------------------------

_CASE_FIELDS: tuple[str, ...] = (
    "lecturer_source_id",
    "institutional_email",
    "lecturer_full_name",
    "decision",
    "expected_scopus_id",
    "target_in_scopus_corpus",
    "generated_candidate_count",
    "generated_scopus_ids",
    "match_found",
    "expected_candidate_rule_ids",
    "expected_candidate_has_publication_evidence",
)


def _safe_case(case: a1.ReferenceCaseResult) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in _CASE_FIELDS:
        value = getattr(case, name)
        out[name] = list(value) if isinstance(value, tuple) else value
    return out


def build_result(
    verified: VerifiedInputs,
    evaluation: a1.CandidateRetrievalEvaluation,
    evaluated_at: datetime,
    input_fingerprint: InputFingerprint | None = None,
    package_rerender: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = {
        field.name: getattr(evaluation.metrics, field.name)
        for field in dataclasses.fields(evaluation.metrics)
    }
    match_count = sum(1 for r in verified.records if r.decision.decision == "MATCH")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "evaluated_at": evaluated_at.isoformat(),
        "frozen_a1_sha": FROZEN_A1_SHA,
        "frozen_a2_sha": FROZEN_A2_SHA,
        **verified.hashes,
        "cohort_selection": {
            "algorithm": COHORT_ALGORITHM,
            "seed": COHORT_SEED,
            "requested_size": COHORT_SIZE,
            "selected_count": len(verified.cohort),
        },
        "rule_provenance": dict(verified.rule_provenance),
        "code_provenance": [dict(item) for item in verified.code_provenance],
        "input_fingerprint": input_fingerprint.as_dict() if input_fingerprint is not None else None,
        "review_package_rerender": dict(package_rerender) if package_rerender is not None else None,
        "reference_row_count": len(verified.records),
        "reference_match_count": match_count,
        "reference_no_match_count": len(verified.records) - match_count,
        "metrics": metrics,
        "cases": [_safe_case(case) for case in evaluation.cases],
    }


__all__ = [
    "APPROVED_DATABASE_NAME",
    "EXPECTED_INPUT_FINGERPRINT_SHA256",
    "FINGERPRINT_CONTENT_COLUMNS",
    "FINGERPRINT_KEY_TABLES",
    "FINGERPRINT_SCHEMA_VERSION",
    "InputFingerprint",
    "READ_ONLY_SNAPSHOT_SQL",
    "REJECTED_DATABASE_NAMES",
    "TableFingerprint",
    "canonical_json_bytes",
    "compute_input_fingerprint",
    "fingerprint_from_rows",
    "require_pinned_fingerprint",
    "verify_connected_database",
    "verify_input_fingerprint",
    "verify_package_rerender",
    "COHORT_ALGORITHM",
    "COHORT_SEED",
    "COHORT_SIZE",
    "FROZEN_A1_SHA",
    "FROZEN_A2_SHA",
    "FROZEN_MATCHING_BLOBS",
    "PHASE1_ACCEPTED_DATASET_SHA256",
    "PHASE1_OFFICIAL_DATASET_SHA256_CRLF",
    "PHASE1_OFFICIAL_DATASET_SHA256_LF",
    "VerificationError",
    "VerifiedInputs",
    "build_result",
    "current_rule_provenance",
    "decode_confirmed",
    "is_approved_database",
    "parse_confirmed_labels",
    "parse_review_manifest",
    "render_cohort_file",
    "run_frozen_a1_evaluation",
    "select_primary_cohort",
    "sha256_hex",
    "verify_blank_sheet",
    "verify_confirmed_identity",
    "verify_dataset_and_cohort",
    "verify_frozen_code",
    "verify_frozen_official_dataset",
    "verify_offline_inputs",
    "verify_package_hashes",
    "verify_rule_provenance",
]
