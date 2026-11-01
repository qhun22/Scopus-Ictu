"""Parse frozen ICTU source artifacts into records and claims (Gate E.3 / P1).

Pure module: standard library only. Input is an artifact envelope::

    {"contract": "ictu-source-claims", "contract_version": "1.0",
     "source_system": "ICTU_REPO_SCOPUS_GUIDE" | "ICTU_REPO_PROFILES",
     "capture": {"captured_at": "<ISO-8601 with offset>",
                 "completeness": "COMPLETE" | "PARTIAL", ...free metadata},
     "content": {...semantic source payload...}}

Hash boundaries (see contract.ParsedSnapshot):
- ``content_hash`` covers ``content`` only — the source assertion itself.
  ``capture`` (time, tool, completeness, notes) never changes it.
- ``artifact_bytes_sha256`` is the exact-bytes hash, available only through
  ``parse_artifact_bytes``. A parsed dict cannot prove byte-exact content:
  whitespace and key order of the original file are not recoverable from it.
- ``record_hash`` covers one record's raw value, not its position.

Envelope violations raise ``ArtifactError``. Problems inside a row or profile
never drop it: they become issues on a kept record.
"""

from __future__ import annotations

import copy as _copy
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app.services.source_claims.canonical import (
    NonCanonicalValueError,
    canonical_json,
    normalize_email,
    normalize_name,
    normalize_orcid,
    normalize_scopus_id,
    normalize_source_id,
    parse_count,
    sha256_json,
    sha256_text,
    split_scopus_id_list,
)
from app.services.source_claims.contract import (
    ALLOWED_ROLES,
    CONTRACT_MAJOR,
    CONTRACT_NAME,
    DECLARED_COUNT_KEYS,
    IDENTITY_RULES_VERSION,
    NORMALIZATION_VERSION,
    PROFILE_EMAIL_FIELD,
    PROFILE_ORCID_FIELD,
    PROFILE_SOURCE_ID_FIELD,
    RECORD_KIND_BY_TABLE,
    REQUIRED_ROLES,
    CaptureMetadata,
    ClaimItem,
    ClaimType,
    ColumnRole,
    Completeness,
    Issue,
    KeyMethod,
    KeyStrength,
    NormalizedValue,
    ParsedSnapshot,
    RecordKey,
    RecordKind,
    Severity,
    SourceRecord,
    SourceSystem,
    TableKind,
    ValidationStatus,
)

PROFILES_DECLARED_KEY = "PROFILES"

# Full-string match; the JSON Schema expresses the same language as
# ^1\.[0-9]+(?![\s\S]) so that no validator accepts a trailing newline.
_CONTRACT_VERSION_RE = re.compile(rf"{CONTRACT_MAJOR}\.[0-9]+")


def _frozen_map(data: dict) -> _FrozenMap:
    obj = dict.__new__(_FrozenMap)
    for k, v in data.items():
        dict.__setitem__(obj, k, v)  # bypass the rejecting __setitem__
    return obj


class _FrozenMap(dict):
    """Read-only dict for SourceRecord.normalized evidence (R2).

    Inherits from dict so equality, read access and JSON encoding work normally.
    Mutations raise TypeError. Construct with _FrozenMap._make(data).
    """

    __slots__ = ()

    @classmethod
    def _make(cls, data: dict) -> _FrozenMap:
        return _frozen_map(data)

    def __reduce__(self):
        # Pickle would otherwise rebuild through __setitem__ (rejected).
        return (_frozen_map, (dict(self),))

    def __ior__(self, other):
        raise TypeError(f"'{type(self).__name__}' does not support in-place update")

    def __setitem__(self, key, value) -> None:
        raise TypeError(f"'{type(self).__name__}' does not support item assignment")

    def __delitem__(self, key) -> None:
        raise TypeError(f"'{type(self).__name__}' does not support item deletion")

    def clear(self) -> None:  # type: ignore[override]
        raise TypeError(f"'{type(self).__name__}' does not support clear")

    def pop(self, *args):  # type: ignore[override]
        raise TypeError(f"'{type(self).__name__}' does not support pop")

    def popitem(self):  # type: ignore[override]
        raise TypeError(f"'{type(self).__name__}' does not support popitem")

    def setdefault(self, *args, **kwargs):  # type: ignore[override]
        raise TypeError(f"'{type(self).__name__}' does not support setdefault")

    def update(self, *args, **kwargs) -> None:  # type: ignore[override]
        raise TypeError(f"'{type(self).__name__}' does not support update")

    def __deepcopy__(self, memo: dict) -> _FrozenMap:
        return _frozen_map({k: _copy.deepcopy(v, memo) for k, v in self.items()})

    def __copy__(self) -> _FrozenMap:
        return _frozen_map(dict(self))


class ArtifactError(ValueError):
    """The artifact envelope violates the contract; nothing can be parsed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def parse_artifact_bytes(data: bytes) -> ParsedSnapshot:
    """Parse artifact file bytes; also records the exact-bytes SHA-256.

    Duplicate object keys and floats are rejected: either would silently lose
    or alter source content during JSON decoding.
    """
    import hashlib

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [key for key, _ in pairs]
        duplicated = sorted(key for key, count in Counter(keys).items() if count > 1)
        if duplicated:
            raise ArtifactError("DUPLICATE_JSON_KEY", f"duplicate keys {duplicated}")
        return dict(pairs)

    def reject_float(text: str) -> Any:
        raise ArtifactError("FLOAT_NOT_ALLOWED", f"float literal {text!r}")

    try:
        artifact = json.loads(
            data.decode("utf-8"), object_pairs_hook=reject_duplicates, parse_float=reject_float,
        )
    except UnicodeDecodeError as exc:
        raise ArtifactError("NOT_UTF8", str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise ArtifactError("NOT_JSON", str(exc)) from exc
    return parse_artifact(artifact, artifact_bytes_sha256=hashlib.sha256(data).hexdigest())


def parse_artifact(
    artifact: Any, *, artifact_bytes_sha256: str | None = None,
) -> ParsedSnapshot:
    if not isinstance(artifact, dict):
        raise ArtifactError("ARTIFACT_NOT_OBJECT", "artifact must be a JSON object")
    try:
        canonical_json(artifact)
    except NonCanonicalValueError as exc:
        raise ArtifactError("NON_CANONICAL_VALUE", str(exc)) from exc
    unknown = sorted(set(artifact) - {"contract", "contract_version", "source_system",
                                      "capture", "content"})
    if unknown:
        raise ArtifactError("UNKNOWN_ENVELOPE_FIELD", f"unexpected fields {unknown}")
    if artifact.get("contract") != CONTRACT_NAME:
        raise ArtifactError("WRONG_CONTRACT", f"contract must be {CONTRACT_NAME!r}")
    version = artifact.get("contract_version")
    if not isinstance(version, str) or not _CONTRACT_VERSION_RE.fullmatch(version):
        raise ArtifactError("UNSUPPORTED_CONTRACT_VERSION", f"got {version!r}")
    try:
        source_system = SourceSystem(artifact.get("source_system"))
    except ValueError as exc:
        raise ArtifactError("UNKNOWN_SOURCE_SYSTEM", str(exc)) from exc
    capture = _parse_capture(artifact.get("capture"))
    content = artifact.get("content")
    if not isinstance(content, dict):
        raise ArtifactError("CONTENT_NOT_OBJECT", "content must be an object")
    source_url = content.get("source_url")
    if not isinstance(source_url, str) or not source_url.strip():
        raise ArtifactError("SOURCE_URL_MISSING", "content.source_url is required")
    _url_norm = normalize_source_id(source_url)
    if not _url_norm.valid:
        raise ArtifactError("SOURCE_URL_MALFORMED",
                            f"content.source_url cannot be normalized: {source_url!r}")

    if source_system is SourceSystem.ICTU_REPO_SCOPUS_GUIDE:
        records, claims, issues, declared, scope_parts = _parse_guide(content)
    else:
        records, claims, issues, declared, scope_parts = _parse_profiles(content)

    scope_key = sha256_json({
        "contract_major": CONTRACT_MAJOR,
        "source_system": source_system.value,
        "source_url": _url_norm.normalized,
        "parts": sorted(scope_parts),
    })
    content_json = canonical_json(content)
    return ParsedSnapshot(
        contract_version=version,
        source_system=source_system,
        source_url=source_url,
        scope_key=scope_key,
        content_json=content_json,
        content_hash=sha256_text(content_json),
        capture=capture,
        artifact_bytes_sha256=artifact_bytes_sha256,
        declared_counts=tuple(sorted(declared.items())),
        records=records,
        claims=claims,
        issues=issues,
        identity_rules_version=IDENTITY_RULES_VERSION,
        normalization_version=NORMALIZATION_VERSION,
    )


# ---------------------------------------------------------------------------
# Envelope parts
# ---------------------------------------------------------------------------

def _parse_capture(capture: Any) -> CaptureMetadata:
    if not isinstance(capture, dict):
        raise ArtifactError("CAPTURE_NOT_OBJECT", "capture must be an object")
    captured_at = capture.get("captured_at")
    if not isinstance(captured_at, str):
        raise ArtifactError("CAPTURED_AT_MISSING", "capture.captured_at is required")
    try:
        moment = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactError("CAPTURED_AT_INVALID", captured_at) from exc
    if moment.tzinfo is None:
        raise ArtifactError("CAPTURED_AT_NO_OFFSET", "captured_at needs a UTC offset")
    try:
        completeness = Completeness(capture.get("completeness"))
    except ValueError as exc:
        raise ArtifactError("COMPLETENESS_INVALID", str(exc)) from exc
    capture_json = canonical_json(capture)
    return CaptureMetadata(captured_at, completeness, capture_json, sha256_text(capture_json))


def _declared_counts(raw: Any, allowed: set[str]) -> tuple[dict[str, int], list[Issue]]:
    if raw is None:
        return {}, []
    if not isinstance(raw, dict):
        raise ArtifactError("DECLARED_COUNTS_NOT_OBJECT", "declared_counts must be an object")
    declared: dict[str, int] = {}
    issues: list[Issue] = []
    for key, value in raw.items():
        if key not in allowed:
            raise ArtifactError("UNKNOWN_DECLARED_COUNT", key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            issues.append(Issue("DECLARED_COUNT_INVALID", Severity.WARNING,
                                f"Declared count {key} is not a non-negative integer.", key))
            continue
        declared[key] = value
    return declared, issues


def _count_issues(declared: dict[str, int], actual: dict[str, int]) -> list[Issue]:
    """The source's own count assertion is kept; a mismatch is reported, never fixed."""
    issues = []
    for key, value in sorted(declared.items()):
        if key in actual and actual[key] != value:
            issues.append(Issue(
                "SOURCE_COUNT_MISMATCH", Severity.WARNING,
                f"Source declares {key}={value} but its detailed listing has {actual[key]}.",
                key,
            ))
    return issues


# ---------------------------------------------------------------------------
# Record helpers
# ---------------------------------------------------------------------------

def _status(issues: list[Issue]) -> ValidationStatus:
    if any(issue.severity is Severity.ERROR for issue in issues):
        return ValidationStatus.INVALID
    if issues:
        return ValidationStatus.WARNING
    return ValidationStatus.VALID


def _content_key(record_hash: str) -> RecordKey:
    return RecordKey(f"content:{record_hash}", KeyMethod.CONTENT_V1, KeyStrength.WEAK)


def _value_key(value: NormalizedValue) -> str:
    if value.normalized is not None:
        return value.normalized
    return "raw-sha256:" + sha256_text(value.raw or "")


def _claim_key(claim_type: ClaimType, subject: str | None, value: NormalizedValue) -> str:
    return f"{claim_type.value}|{subject or '-'}|{_value_key(value)}"


def _normalized_pairs(values: dict[str, NormalizedValue]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(
        (name, _FrozenMap._make(
            {"raw": value.raw, "normalized": value.normalized, "method": value.method}
        ))
        for name, value in values.items()
    ))


class _Draft:
    """Mutable working state for one record before keys are de-duplicated."""

    def __init__(self, kind: RecordKind, position: int, raw: Any) -> None:
        self.kind, self.position, self.raw = kind, position, raw
        self.raw_json = canonical_json(raw)
        self.record_hash = sha256_json({"record_kind": kind.value, "raw": raw})
        self.values: dict[str, NormalizedValue] = {}
        self.issues: list[Issue] = []
        self.key: RecordKey = _content_key(self.record_hash)
        self.claims: list[tuple[ClaimType, NormalizedValue, dict[str, Any], bool]] = []

    @property
    def ref(self) -> str:
        return f"{self.kind.value}#{self.position}"

    def keep(self, name: str, value: NormalizedValue) -> NormalizedValue:
        self.values[name] = value
        self.issues.extend(value.issues)
        return value


def _finalize(drafts: list[_Draft]) -> tuple[tuple[SourceRecord, ...], tuple[ClaimItem, ...]]:
    """Flag duplicate keys on every record that shares them; never merge or drop."""
    groups: dict[tuple[RecordKind, str], list[_Draft]] = defaultdict(list)
    for draft in drafts:
        groups[(draft.kind, draft.key.value)].append(draft)
    for (_, key), members in groups.items():
        if len(members) > 1:
            refs = ", ".join(member.ref for member in members)
            code = ("DUPLICATE_SOURCE_ROW" if key.startswith("content:")
                    else "DUPLICATE_RECORD_KEY")
            for member in members:
                member.issues.append(Issue(
                    code, Severity.WARNING,
                    f"Record key shared by {refs}; records are kept separately.", None,
                ))
    records, claims = [], []
    for draft in drafts:
        records.append(SourceRecord(
            record_kind=draft.kind,
            source_position=draft.position,
            raw_json=draft.raw_json,
            record_hash=draft.record_hash,
            record_key=draft.key,
            normalized=_normalized_pairs(draft.values),
            validation_status=_status(draft.issues),
            issues=tuple(draft.issues),
        ))
        for claim_type, value, flags, owned in draft.claims:
            subject = draft.key.value if owned else None
            flags = {**flags, "subject_key_strength": draft.key.strength.value} if owned else flags
            claims.append(ClaimItem(
                claim_type=claim_type,
                record_ref=draft.ref,
                subject_key=subject,
                value=value,
                claim_key=_claim_key(claim_type, subject, value),
                flags=tuple(sorted(flags.items())),
            ))
    return tuple(records), tuple(claims)


# ---------------------------------------------------------------------------
# ICTU_REPO_SCOPUS_GUIDE
# ---------------------------------------------------------------------------

def _columns(kind: TableKind, table: dict[str, Any]) -> dict[ColumnRole, int]:
    columns = table.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ArtifactError("COLUMNS_MISSING", f"{kind.value}.columns must be a non-empty list")
    roles: dict[ColumnRole, int] = {}
    for index, column in enumerate(columns):
        if not isinstance(column, dict) or not isinstance(column.get("header"), str):
            raise ArtifactError("COLUMN_INVALID", f"{kind.value}.columns[{index}]")
        try:
            role = ColumnRole(column.get("role"))
        except ValueError as exc:
            raise ArtifactError("COLUMN_ROLE_UNKNOWN", f"{kind.value}.columns[{index}]") from exc
        if role not in ALLOWED_ROLES[kind]:
            raise ArtifactError("COLUMN_ROLE_NOT_ALLOWED", f"{role.value} in {kind.value}")
        if role is not ColumnRole.OTHER:
            if role in roles:
                raise ArtifactError("COLUMN_ROLE_DUPLICATED", f"{role.value} in {kind.value}")
            roles[role] = index
    missing = REQUIRED_ROLES[kind] - set(roles)
    if missing:
        raise ArtifactError("COLUMN_ROLE_REQUIRED",
                            f"{kind.value} lacks {sorted(r.value for r in missing)}")
    return roles


def _cell(row: list[Any], roles: dict[ColumnRole, int], role: ColumnRole) -> Any:
    index = roles.get(role)
    if index is None or index >= len(row):
        return None
    return row[index]


def _optional(
    draft: _Draft, name: str, row: list[Any], roles: dict[ColumnRole, int],
    role: ColumnRole, normalizer,
) -> NormalizedValue | None:
    """Normalize a cell only when the table declares that column."""
    if role not in roles:
        return None
    return draft.keep(name, normalizer(_cell(row, roles, role), role.value))


def _multi_id_row(draft: _Draft, row: list[Any], roles: dict[ColumnRole, int]) -> None:
    _optional(draft, "name", row, roles, ColumnRole.NAME, normalize_name)
    email = _optional(draft, "email", row, roles, ColumnRole.EMAIL, normalize_email)
    declared_ids = _optional(draft, "declared_id_count", row, roles,
                             ColumnRole.DECLARED_ID_COUNT, parse_count)
    declared_pubs = _optional(draft, "declared_pub_count", row, roles,
                              ColumnRole.DECLARED_PUB_COUNT, parse_count)
    if email is not None and email.valid:
        draft.key = RecordKey(email.normalized, KeyMethod.EMAIL_V1, KeyStrength.MEDIUM)
    if email is not None and email.raw is not None and email.raw.strip():
        draft.claims.append((ClaimType.EMAIL_DECLARED, email, {}, True))

    listed: dict[str, NormalizedValue] = {}
    for token in split_scopus_id_list(_cell(row, roles, ColumnRole.SCOPUS_ID_LIST)):
        value = normalize_scopus_id(token, "SCOPUS_ID_LIST")
        draft.issues.extend(value.issues)
        key = _value_key(value)
        if key in listed:
            draft.issues.append(Issue("DUPLICATE_ID_IN_ROW", Severity.WARNING,
                                      f"Scopus ID {token!r} listed more than once.",
                                      "SCOPUS_ID_LIST"))
            continue
        listed[key] = value
    if not listed:
        draft.issues.append(Issue("NO_SCOPUS_ID_LISTED", Severity.ERROR,
                                  "Row lists no Scopus ID.", "SCOPUS_ID_LIST"))

    primary_raw = _cell(row, roles, ColumnRole.PRIMARY_SCOPUS_ID)
    primary = None
    if primary_raw is not None and str(primary_raw).strip():
        primary = draft.keep("primary_scopus_id",
                             normalize_scopus_id(primary_raw, "PRIMARY_SCOPUS_ID"))
    primary_key = _value_key(primary) if primary is not None else None
    if primary is not None and primary_key not in listed:
        draft.issues.append(Issue("PRIMARY_NOT_IN_LIST", Severity.WARNING,
                                  "Source primary ID is not in the row's ID list.",
                                  "PRIMARY_SCOPUS_ID"))

    valid_ids = sum(1 for value in listed.values() if value.valid)
    declared_id_count = (int(declared_ids.normalized)
                         if declared_ids is not None and declared_ids.valid else None)
    if declared_id_count is not None and declared_id_count != valid_ids:
        draft.issues.append(Issue(
            "ID_COUNT_MISMATCH", Severity.WARNING,
            f"Row declares {declared_ids.normalized} IDs but lists {valid_ids} valid IDs.",
            "DECLARED_ID_COUNT"))

    shared = {"declared_pub_count_raw": declared_pubs.raw if declared_pubs else None}
    for key, value in listed.items():
        draft.claims.append((ClaimType.SCOPUS_ID_OWNED, value, {
            **shared, "listed": True, "is_primary_claimed": key == primary_key,
        }, True))
    if primary is not None and primary_key not in listed:
        draft.claims.append((ClaimType.SCOPUS_ID_OWNED, primary, {
            **shared, "listed": False, "is_primary_claimed": True,
        }, True))


def _unowned_id_row(
    draft: _Draft, row: list[Any], roles: dict[ColumnRole, int], claim_type: ClaimType,
) -> None:
    scopus_name = _optional(draft, "scopus_name", row, roles, ColumnRole.SCOPUS_NAME,
                            normalize_name)
    declared_pubs = _optional(draft, "declared_pub_count", row, roles,
                              ColumnRole.DECLARED_PUB_COUNT, parse_count)
    scopus_id = draft.keep("scopus_id", normalize_scopus_id(
        _cell(row, roles, ColumnRole.SCOPUS_ID), "SCOPUS_ID"))
    if scopus_id.valid:
        draft.key = RecordKey(scopus_id.normalized, KeyMethod.SCOPUS_ID_V1, KeyStrength.STRONG)
    # Never attributed to anyone: the claim has no subject.
    draft.claims.append((claim_type, scopus_id, {
        "declared_pub_count_raw": declared_pubs.raw if declared_pubs else None,
        "scopus_name_raw": scopus_name.raw if scopus_name else None,
    }, False))


_UNOWNED_CLAIM = {
    TableKind.AMBIGUOUS: ClaimType.SCOPUS_ID_AMBIGUOUS,
    TableKind.UNASSIGNED: ClaimType.SCOPUS_ID_UNASSIGNED,
}


def _parse_guide(content: dict[str, Any]):
    unknown = sorted(set(content) - {"source_url", "page_summary", "tables"})
    if unknown:
        raise ArtifactError("UNKNOWN_CONTENT_FIELD", f"unexpected fields {unknown}")
    tables = content.get("tables")
    if not isinstance(tables, dict) or not tables:
        raise ArtifactError("TABLES_MISSING", "content.tables must be a non-empty object")
    issues: list[Issue] = []
    summary = content.get("page_summary")
    declared: dict[str, int] = {}
    if summary is not None:
        if not isinstance(summary, dict):
            raise ArtifactError("PAGE_SUMMARY_NOT_OBJECT", "page_summary must be an object")
        declared, count_issues = _declared_counts(
            summary.get("declared_counts"), set(DECLARED_COUNT_KEYS))
        issues.extend(count_issues)

    drafts: list[_Draft] = []
    actual: dict[str, int] = {}
    for name in sorted(tables):
        try:
            kind = TableKind(name)
        except ValueError as exc:
            raise ArtifactError("UNKNOWN_TABLE", name) from exc
        table = tables[name]
        if not isinstance(table, dict) or not isinstance(table.get("rows"), list):
            raise ArtifactError("TABLE_INVALID", f"{name} needs a rows list")
        roles = _columns(kind, table)
        width = len(table["columns"])
        record_kind = RECORD_KIND_BY_TABLE[kind]
        for position, row in enumerate(table["rows"], start=1):
            draft = _Draft(record_kind, position, row)
            if not isinstance(row, list):
                draft.issues.append(Issue("ROW_NOT_LIST", Severity.ERROR,
                                          "Row is not a list of cells.", None))
                drafts.append(draft)
                continue
            if len(row) != width:
                draft.issues.append(Issue(
                    "ROW_CELL_COUNT_MISMATCH", Severity.ERROR,
                    f"Row has {len(row)} cells; the table declares {width} columns.", None))
            if kind is TableKind.MULTI_ID:
                _multi_id_row(draft, row, roles)
            else:
                _unowned_id_row(draft, row, roles, _UNOWNED_CLAIM[kind])
            drafts.append(draft)
        declared_key = next(k for k, v in DECLARED_COUNT_KEYS.items() if v is kind)
        actual[declared_key] = len(table["rows"])

    issues.extend(_count_issues(declared, actual))
    records, claims = _finalize(drafts)
    return records, claims, tuple(issues), declared, [f"table:{name}" for name in tables]


# ---------------------------------------------------------------------------
# ICTU_REPO_PROFILES
# ---------------------------------------------------------------------------

def _profile(draft: _Draft, profile: dict[str, Any]) -> None:
    draft.keep("name", normalize_name(profile.get("full_name"), "full_name"))
    source_id = None
    if profile.get(PROFILE_SOURCE_ID_FIELD) is not None:
        source_id = draft.keep("source_id", normalize_source_id(
            profile.get(PROFILE_SOURCE_ID_FIELD), PROFILE_SOURCE_ID_FIELD))
    email = None
    if profile.get(PROFILE_EMAIL_FIELD) not in (None, ""):
        email = draft.keep("email", normalize_email(
            profile.get(PROFILE_EMAIL_FIELD), PROFILE_EMAIL_FIELD))
        draft.claims.append((ClaimType.EMAIL_DECLARED, email, {}, True))
    if profile.get(PROFILE_ORCID_FIELD) not in (None, ""):
        orcid = draft.keep("orcid", normalize_orcid(
            profile.get(PROFILE_ORCID_FIELD), PROFILE_ORCID_FIELD))
        draft.claims.append((ClaimType.ORCID_DECLARED, orcid, {}, True))

    if source_id is not None and source_id.valid:
        draft.key = RecordKey(source_id.normalized, KeyMethod.PROFILE_SOURCE_ID_V1,
                              KeyStrength.STRONG)
    elif email is not None and email.valid:
        draft.key = RecordKey(email.normalized, KeyMethod.EMAIL_V1, KeyStrength.MEDIUM)


def _parse_profiles(content: dict[str, Any]):
    unknown = sorted(set(content) - {"source_url", "declared_counts", "profiles"})
    if unknown:
        raise ArtifactError("UNKNOWN_CONTENT_FIELD", f"unexpected fields {unknown}")
    profiles = content.get("profiles")
    if not isinstance(profiles, list):
        raise ArtifactError("PROFILES_MISSING", "content.profiles must be a list")
    declared, issues = _declared_counts(content.get("declared_counts"), {PROFILES_DECLARED_KEY})
    drafts = []
    for position, profile in enumerate(profiles, start=1):
        draft = _Draft(RecordKind.PROFILE, position, profile)
        if isinstance(profile, dict):
            _profile(draft, profile)
        else:
            draft.issues.append(Issue("PROFILE_NOT_OBJECT", Severity.ERROR,
                                      "Profile is not an object.", None))
        drafts.append(draft)
    issues.extend(_count_issues(declared, {PROFILES_DECLARED_KEY: len(profiles)}))
    records, claims = _finalize(drafts)
    return records, claims, tuple(issues), declared, ["profiles"]
