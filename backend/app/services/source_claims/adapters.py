"""Pure adapters from real ICTU source captures to the E3-P1 artifact contract (Gate E.3 / P2-A).

Standard library only. Inputs are already-decoded JSON values; the caller reads the files and
passes the SHA-256 of the exact bytes it read. Nothing here opens files, touches a database or
the network, and nothing here decides identity: adapters only reshape a capture into the
``ictu-source-claims`` envelope that ``parser.parse_artifact`` validates.

Upstream formats handled:
- Craw harvest ``lecturers.json`` with ``harvest_manifest.json`` and ``crawl_report.json``
  -> ``ICTU_REPO_PROFILES``.
- Scopus-guide page snapshots taken in the browser -> ``ICTU_REPO_SCOPUS_GUIDE``:
  a *tables* snapshot (header row + rows per page section: AMBIGUOUS / UNASSIGNED) and a
  *rows* snapshot (MULTI_ID rows captured without their header).

Content versus capture: only what the source asserts goes into ``content`` (and so into the
content hash). Retrieval times, snapshot hashes, harvester diagnostics and adapter versions go
into ``capture``. Personal fields that identity resolution does not need (birth date, gender,
phone) are not copied at all; their labels and counts are reported in ``capture.excluded``.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from typing import Any

from app.services.source_claims.canonical import canonical_json, normalize_source_id
from app.services.source_claims.contract import (
    CONTRACT_NAME,
    CONTRACT_VERSION,
    ColumnRole,
    Completeness,
    ParsedSnapshot,
    SourceSystem,
    TableKind,
)

ADAPTER_VERSION = "ictu-source-adapters/1"
PROFILE_PROJECTION_VERSION = "ICTU_REPO_PROFILES_PROJECTION_V1"
GUIDE_PROJECTION_VERSION = "ICTU_REPO_SCOPUS_GUIDE_PROJECTION_V1"

# --- lecturers.json field classes (verified against the real harvest, see E3P2A_SOURCE_MAPPING) --
# Kept verbatim in content. ``institutional_email`` is renamed to the contract field ``email``.
PROFILE_CONTENT_FIELDS = (
    "source_id", "profile_url", "full_name", "source_display_name", "orcid", "orcid_url",
    "google_scholar_url", "academic_degree", "academic_rank", "position", "faculty",
    "department", "specialisation", "is_active", "public_publication_links", "counts",
)
PROFILE_EMAIL_SOURCE_FIELD = "institutional_email"
# Raw page labels kept verbatim in content (other labels are excluded and only counted).
PROFILE_SOURCE_FIELD_LABELS = ("Họ và tên", "Email", "ORCID", "Học vị", "Học hàm",
                               "Google Scholar")
# Observation metadata: moved to capture, never hashed into content.
PROFILE_CAPTURE_FIELDS = ("provenance", "discovery_source", "observed_labels",
                          "preserved_labels", "lost_labels")
# Harvester-derived copies of content fields; the parser normalizes on its own.
PROFILE_DERIVED_FIELDS = ("normalized", "source")
# Personal data not needed for identity resolution; dropped and counted.
PROFILE_EXCLUDED_FIELDS = ("extra_fields",)
_KNOWN_PROFILE_FIELDS = frozenset(
    PROFILE_CONTENT_FIELDS + (PROFILE_EMAIL_SOURCE_FIELD, "source_fields")
    + PROFILE_CAPTURE_FIELDS + PROFILE_DERIVED_FIELDS + PROFILE_EXCLUDED_FIELDS
)
# Harvester vocabulary (Craw ``ictu_harvester/full_harvest.py``, read 2026-10-29):
# - ``manifest.status`` is written as COMPLETE, or as COMPLETE_WITH_SOURCE_FAILURES when any entity
#   failed. A run whose offline semantic replay differs ends BLOCKED, but that word is only
#   returned by the CLI. The manifest is written *before* the replay check, so a BLOCKED run can
#   leave a manifest saying COMPLETE; ``semantic_replay.json`` is the success evidence.
# - ``source_entity_failures[].entity_type`` is "lecturer", "<kind>" or "<kind>_listing".
#   Only "lecturer" failures affect the profile listing.
HARVEST_SUCCESS_STATUSES = frozenset({"COMPLETE", "COMPLETE_WITH_SOURCE_FAILURES"})
_LECTURER_ENTITY_TYPES = frozenset({"lecturer"})

# --- Scopus-guide page ---------------------------------------------------------------------
_TABLE_KIND_MARKERS = {TableKind.AMBIGUOUS: "nhập nhằng",
                       TableKind.UNASSIGNED: "chưa xác định"}
_GUIDE_HEADER_ROLES = {"tên trên scopus": ColumnRole.SCOPUS_NAME,
                       "scopus id": ColumnRole.SCOPUS_ID,
                       "số bài": ColumnRole.DECLARED_PUB_COUNT}
# The rows snapshot captured no header row; the layout is the one Gate D.1 transcribed.
MULTI_ID_LAYOUT = (ColumnRole.NAME, ColumnRole.EMAIL, ColumnRole.DECLARED_ID_COUNT,
                   ColumnRole.DECLARED_PUB_COUNT, ColumnRole.PRIMARY_SCOPUS_ID,
                   ColumnRole.SCOPUS_ID_LIST)
_DECLARED_KEY_BY_TABLE = {TableKind.MULTI_ID: "MULTI_ID_LECTURERS",
                          TableKind.AMBIGUOUS: "AMBIGUOUS_IDS",
                          TableKind.UNASSIGNED: "UNASSIGNED_IDS"}
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class AdapterError(ValueError):
    """The upstream capture cannot be mapped to the contract; nothing is produced."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise AdapterError(code, message)


def _sha256(value: Any, name: str) -> str:
    _require(isinstance(value, str) and bool(_SHA256_RE.fullmatch(value)),
             "UPSTREAM_SHA256_INVALID", f"{name} must be 64 lower-case hex characters")
    return value


def _origin_url(value: Any, field: str) -> str:
    """Artifact origins must be real http(s) URLs with a host; opaque IDs are not accepted."""
    _require(isinstance(value, str) and re.match(r"^https?://", value.strip(), re.I) is not None
             and normalize_source_id(value).valid,
             "ORIGIN_URL_INVALID", f"{field} must be an http(s) URL with a host")
    return value


def _completeness(value: Any) -> str:
    try:
        return Completeness(value).value
    except ValueError as exc:
        raise AdapterError("COMPLETENESS_INVALID", f"got {value!r}") from exc


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().casefold()


def _envelope(source_system: SourceSystem, capture: dict, content: dict) -> dict:
    artifact = {"contract": CONTRACT_NAME, "contract_version": CONTRACT_VERSION,
                "source_system": source_system.value, "capture": capture, "content": content}
    try:
        canonical_json(artifact)
    except ValueError as exc:
        raise AdapterError("NON_CANONICAL_VALUE", str(exc)) from exc
    return artifact


def artifact_bytes(artifact: dict) -> bytes:
    """Deterministic bytes to store; ``parser.parse_artifact_bytes`` hashes exactly these."""
    return canonical_json(artifact).encode("utf-8")


# ---------------------------------------------------------------------------
# Staging identity (pure): one definition shared by the schema proposal and its tests
# ---------------------------------------------------------------------------

def reconstruct_artifact_bytes(*, source_system: str, contract_version: str, capture_json: str,
                               content_json: str) -> bytes:
    """Canonical artifact bytes from stored parts. ``contract_version`` is part of the bytes, so
    it must be stored per artifact: content and capture alone do not determine the artifact."""
    return artifact_bytes({"contract": CONTRACT_NAME, "contract_version": contract_version,
                           "source_system": source_system, "capture": json.loads(capture_json),
                           "content": json.loads(content_json)})


def staging_keys(snapshot: ParsedSnapshot) -> dict[str, tuple[str, ...]]:
    """Natural keys of the three staging layers for a snapshot parsed from canonical bytes.

    - content:  what the source asserts (reused across captures and contract versions);
    - capture:  one observation of that content (reused across contract versions);
    - artifact: the exact canonical envelope, contract version included.
    """
    _require(snapshot.artifact_bytes_sha256 is not None, "ARTIFACT_BYTES_REQUIRED",
             "parse the artifact with parse_artifact_bytes to obtain its byte identity")
    rebuilt = reconstruct_artifact_bytes(
        source_system=snapshot.source_system.value, contract_version=snapshot.contract_version,
        capture_json=snapshot.capture.capture_json, content_json=snapshot.content_json)
    _require(hashlib.sha256(rebuilt).hexdigest() == snapshot.artifact_bytes_sha256,
             "ARTIFACT_NOT_CANONICAL",
             "artifact bytes are not canonical; store adapters.artifact_bytes(artifact) instead")
    system = snapshot.source_system.value
    return {
        "content": (system, snapshot.content_hash),
        "capture": (system, snapshot.content_hash, snapshot.capture.capture_hash),
        "artifact": (snapshot.artifact_bytes_sha256,),
    }


# ---------------------------------------------------------------------------
# ICTU_REPO_PROFILES from the Craw harvest
# ---------------------------------------------------------------------------

def _project_profile(item: dict, position: int, excluded: Counter, checks: dict) -> dict:
    unknown = sorted(set(item) - _KNOWN_PROFILE_FIELDS)
    _require(not unknown, "UNMAPPED_PROFILE_FIELD",
             f"profile #{position} has unclassified fields {unknown}")
    profile = {key: item[key] for key in PROFILE_CONTENT_FIELDS if key in item}
    if PROFILE_EMAIL_SOURCE_FIELD in item:
        profile["email"] = item[PROFILE_EMAIL_SOURCE_FIELD]
    for key in PROFILE_EXCLUDED_FIELDS:
        if key in item:
            excluded[f"field:{key}"] += 1
    labels = item.get("source_fields")
    if isinstance(labels, dict):
        profile["source_fields"] = {k: v for k, v in labels.items()
                                    if k in PROFILE_SOURCE_FIELD_LABELS}
        for label in labels:
            if label not in PROFILE_SOURCE_FIELD_LABELS:
                excluded[f"source_field_label:{label}"] += 1
        _cross_check(profile, labels, position, checks)
    elif labels is not None:
        profile["source_fields"] = labels  # malformed: kept verbatim for the parser to flag
    return profile


def _cross_check(profile: dict, labels: dict, position: int, checks: dict) -> None:
    """Harvester-extracted values must be traceable to the raw page text."""
    def text(value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    pairs = (("ORCID", profile.get("orcid"), lambda e, r: e in r),
             ("Email", profile.get("email"), lambda e, r: _fold(e) == _fold(r)),
             ("Họ và tên", profile.get("full_name"), lambda e, r: _fold(e) == _fold(r)))
    for label, extracted, agrees in pairs:
        raw = text(labels.get(label))
        value = text(extracted)
        if (raw is None) != (value is None) or (raw and value and not agrees(value, raw)):
            checks.setdefault(f"{label}_NOT_IN_SOURCE_TEXT", []).append(position)


def _replay_verified(semantic_replay: Any, manifest: dict, upstream_name: str) -> bool:
    """The run passed its own offline replay *and* that replay is of this lecturers file."""
    if not isinstance(semantic_replay, dict):
        return False
    if semantic_replay.get("a_equals_b_equals_c") is not True:
        return False
    file_hashes = semantic_replay.get("file_hashes")
    expected = (manifest.get("semantic_file_hashes") or {}).get(upstream_name)
    if not isinstance(file_hashes, dict) or not isinstance(expected, str) or not file_hashes:
        return False
    return all(isinstance(run, dict) and run.get(upstream_name) == expected
               for run in file_hashes.values())


def _profiles_completeness(lecturers: list, manifest: dict, crawl_report: dict | None,
                           semantic_replay: Any, upstream_name: str):
    """COMPLETE only on positive evidence; anything missing, unknown or inconsistent is PARTIAL."""
    failures = (crawl_report or {}).get("source_entity_failures")
    failure_types = sorted({str(f.get("entity_type")) for f in failures or []
                            if isinstance(f, dict)})
    status = manifest.get("status")
    basis = {
        "profiles_in_file": len(lecturers),
        "source_card_count": manifest.get("source_card_count"),
        "lecturer_count": manifest.get("lecturer_count"),
        "crawl_report_present": crawl_report is not None,
        "source_drift_detected": manifest.get("source_drift_detected"),
        "entity_failure_types": failure_types,
        "manifest_status": status,
        "semantic_replay_verified": _replay_verified(semantic_replay, manifest, upstream_name),
    }
    status_consistent = isinstance(failures, list) and (
        (status == "COMPLETE" and not failures)
        or (status == "COMPLETE_WITH_SOURCE_FAILURES" and bool(failures)))
    complete = (crawl_report is not None
                and status in HARVEST_SUCCESS_STATUSES
                and status_consistent
                and basis["semantic_replay_verified"]
                and basis["source_card_count"] == len(lecturers)
                and basis["lecturer_count"] == len(lecturers)
                and basis["source_drift_detected"] is False
                and not _LECTURER_ENTITY_TYPES & set(failure_types))
    return (Completeness.COMPLETE if complete else Completeness.PARTIAL).value, basis


def profiles_artifact(
    lecturers: Any, manifest: Any, crawl_report: Any = None, semantic_replay: Any = None, *,
    lecturers_sha256: str, upstream_name: str = "lecturers.json",
) -> dict:
    """Map one Craw harvest to an ICTU_REPO_PROFILES artifact.

    Every list item becomes exactly one profile in source order, including profiles without
    publications and malformed items (kept verbatim for the parser to flag). Completeness is
    COMPLETE only when the harvest proves the listing was fully read: a success status that
    agrees with the failure list, a passed semantic replay of this very file, matching counts,
    no drift and no lecturer failure. Anything else, including a missing report, is PARTIAL.
    """
    _require(isinstance(lecturers, list), "LECTURERS_NOT_LIST", "lecturers.json must be a list")
    _require(isinstance(manifest, dict), "MANIFEST_INVALID", "harvest manifest must be an object")
    _require(crawl_report is None or isinstance(crawl_report, dict), "CRAWL_REPORT_INVALID",
             "crawl report must be an object")
    card_count = manifest.get("source_card_count")
    _require(isinstance(card_count, int) and not isinstance(card_count, bool) and card_count >= 0,
             "MANIFEST_INVALID", "manifest.source_card_count must be a non-negative integer")
    completed_at = manifest.get("harvest_completed_at")
    _require(isinstance(completed_at, str), "MANIFEST_INVALID",
             "manifest.harvest_completed_at is required")
    origin = _origin_url(manifest.get("source_base_url"), "manifest.source_base_url")

    excluded: Counter = Counter()
    checks: dict[str, list[int]] = {}
    profiles, observations = [], []
    for position, item in enumerate(lecturers, start=1):
        if not isinstance(item, dict):
            profiles.append(item)
            continue
        profiles.append(_project_profile(item, position, excluded, checks))
        observation = {"position": position, "source_id": item.get("source_id")}
        observation.update({key: item[key] for key in PROFILE_CAPTURE_FIELDS if key in item})
        observations.append(observation)

    _require(semantic_replay is None or isinstance(semantic_replay, dict),
             "SEMANTIC_REPLAY_INVALID", "semantic replay report must be an object")
    completeness, basis = _profiles_completeness(lecturers, manifest, crawl_report,
                                                 semantic_replay, upstream_name)
    retrieved = sorted(o["provenance"]["retrieved_at"] for o in observations
                       if isinstance(o.get("provenance"), dict)
                       and isinstance(o["provenance"].get("retrieved_at"), str))
    capture = {
        "captured_at": completed_at,
        "completeness": completeness,
        "completeness_basis": basis,
        "adapter": {"version": ADAPTER_VERSION, "projection": PROFILE_PROJECTION_VERSION},
        "upstream": {
            "file": upstream_name,
            "bytes_sha256": _sha256(lecturers_sha256, "lecturers_sha256"),
            "manifest_semantic_sha256": (manifest.get("semantic_file_hashes") or {}).get(
                upstream_name),
            "harvest_started_at": manifest.get("harvest_started_at"),
            "harvest_completed_at": completed_at,
            "harvester_version": manifest.get("parser_version"),
            "harvest_status": manifest.get("status"),
            "semantic_replay_combined_sha256": (semantic_replay or {}).get("combined_hash"),
            "retrieved_at_min": retrieved[0] if retrieved else None,
            "retrieved_at_max": retrieved[-1] if retrieved else None,
        },
        "excluded": dict(sorted(excluded.items())),
        "checks": {key: value for key, value in sorted(checks.items())},
        "observations": observations,
    }
    content = {"source_url": origin, "declared_counts": {"PROFILES": card_count},
               "profiles": profiles}
    return _envelope(SourceSystem.ICTU_REPO_PROFILES, capture, content)


# ---------------------------------------------------------------------------
# ICTU_REPO_SCOPUS_GUIDE from browser snapshots
# ---------------------------------------------------------------------------

def _declared(declared_counts: Any, tables: set[TableKind]) -> dict[str, Any]:
    if declared_counts is None:
        return {}
    _require(isinstance(declared_counts, dict), "DECLARED_COUNTS_INVALID",
             "declared_counts must be an object")
    allowed = {_DECLARED_KEY_BY_TABLE[kind] for kind in tables}
    stray = sorted(set(declared_counts) - allowed)
    _require(not stray, "DECLARED_COUNT_FOR_ABSENT_TABLE",
             f"{stray} describe tables this capture does not contain")
    return dict(declared_counts)


def _snapshot_common(snapshot: Any, snapshot_sha256: str) -> tuple[str, str]:
    _require(isinstance(snapshot, dict), "SNAPSHOT_INVALID", "snapshot must be an object")
    _sha256(snapshot_sha256, "snapshot_sha256")
    ts = snapshot.get("ts")
    _require(isinstance(ts, str), "SNAPSHOT_INVALID", "snapshot.ts is required")
    return ts, _origin_url(snapshot.get("url"), "snapshot.url")


def _table_kind(heading: Any, ti: Any) -> TableKind:
    _require(isinstance(heading, str), "TABLE_KIND_UNRESOLVED", f"table {ti} has no heading")
    folded = _fold(heading)
    kinds = [kind for kind, marker in _TABLE_KIND_MARKERS.items() if marker in folded]
    _require(len(kinds) == 1, "TABLE_KIND_UNRESOLVED",
             f"table {ti} heading matches {len(kinds)} table kinds")
    return kinds[0]


def guide_tables_artifact(
    snapshot: Any, *, snapshot_sha256: str, completeness: str, declared_counts: Any = None,
    upstream_name: str | None = None,
) -> dict:
    """Map a tables snapshot (one header row per table) to an ICTU_REPO_SCOPUS_GUIDE artifact.

    Table kind comes from the published section heading; column roles come from the published
    header text (unknown headers become OTHER). Data rows are copied verbatim.
    ``declared_counts`` must describe only tables in this capture.
    """
    ts, origin = _snapshot_common(snapshot, snapshot_sha256)
    raw_tables = snapshot.get("tables")
    _require(isinstance(raw_tables, list) and bool(raw_tables), "TABLES_MISSING",
             "snapshot.tables must be a non-empty list")
    headings = snapshot.get("section_headings")
    _require(isinstance(headings, dict), "SECTION_HEADINGS_MISSING",
             "snapshot.section_headings is required to identify tables")
    tables: dict[str, Any] = {}
    for table in raw_tables:
        _require(isinstance(table, dict) and isinstance(table.get("rows"), list),
                 "TABLE_INVALID", "each table needs a rows list")
        ti = table.get("ti")
        heading = headings.get(str(ti))
        kind = _table_kind(heading, ti)
        _require(kind.value not in tables, "TABLE_KIND_DUPLICATED", f"{kind.value} twice")
        rows = table["rows"]
        header = rows[0] if rows else None
        _require(isinstance(header, list) and all(isinstance(c, str) for c in header),
                 "HEADER_ROW_MISSING", f"table {ti} has no header row")
        roles = [_GUIDE_HEADER_ROLES.get(_fold(cell), ColumnRole.OTHER) for cell in header]
        _require(ColumnRole.SCOPUS_ID in roles, "HEADER_ROW_MISSING",
                 f"table {ti} header has no Scopus ID column")
        tables[kind.value] = {
            "heading": heading,
            "columns": [{"header": cell, "role": role.value}
                        for cell, role in zip(header, roles, strict=True)],
            "rows": rows[1:],
        }
    content: dict[str, Any] = {"source_url": origin, "tables": tables}
    summary = snapshot.get("page_summary_text")
    declared = _declared(declared_counts, {TableKind(name) for name in tables})
    if summary is not None or declared:
        content["page_summary"] = {"text": summary, "declared_counts": declared}
    capture = {
        "captured_at": ts,
        "completeness": _completeness(completeness),
        "adapter": {"version": ADAPTER_VERSION, "projection": GUIDE_PROJECTION_VERSION},
        "upstream": {"file": upstream_name, "bytes_sha256": snapshot_sha256,
                     "in_browser_sha256": snapshot.get("sha256"),
                     "capture_note": snapshot.get("capture_note"),
                     "n_tables_total": snapshot.get("n_tables_total"),
                     "table_ids": [t.get("ti") for t in raw_tables]},
    }
    return _envelope(SourceSystem.ICTU_REPO_SCOPUS_GUIDE, capture, content)


def guide_multi_id_artifact(
    snapshot: Any, *, snapshot_sha256: str, completeness: str, declared_counts: Any = None,
    upstream_name: str | None = None,
) -> dict:
    """Map a MULTI_ID rows snapshot (no header row captured) to an ICTU_REPO_SCOPUS_GUIDE artifact.

    Column roles follow ``MULTI_ID_LAYOUT``; headers and the table heading are empty strings
    because the published text was not captured. The snapshot's own row count must match.
    """
    ts, origin = _snapshot_common(snapshot, snapshot_sha256)
    rows = snapshot.get("rows")
    _require(isinstance(rows, list), "ROWS_MISSING", "snapshot.rows must be a list")
    stated = snapshot.get("multi_id_rows")
    _require(stated is None or stated == len(rows), "SNAPSHOT_ROW_COUNT_MISMATCH",
             f"snapshot states {stated} rows but holds {len(rows)}")
    content: dict[str, Any] = {
        "source_url": origin,
        "tables": {TableKind.MULTI_ID.value: {
            "heading": "",
            "columns": [{"header": "", "role": role.value} for role in MULTI_ID_LAYOUT],
            "rows": rows,
        }},
    }
    declared = _declared(declared_counts, {TableKind.MULTI_ID})
    if declared:
        content["page_summary"] = {"text": None, "declared_counts": declared}
    capture = {
        "captured_at": ts,
        "completeness": _completeness(completeness),
        "adapter": {"version": ADAPTER_VERSION, "projection": GUIDE_PROJECTION_VERSION},
        "upstream": {"file": upstream_name, "bytes_sha256": snapshot_sha256,
                     "in_browser_rows_sha256": snapshot.get("rows_sha256"),
                     "capture_note": snapshot.get("capture_note"),
                     "page_title": snapshot.get("title"),
                     "page_total_tr": snapshot.get("total_tr"),
                     "header_captured": False},
    }
    return _envelope(SourceSystem.ICTU_REPO_SCOPUS_GUIDE, capture, content)
