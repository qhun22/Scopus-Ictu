"""Source-claim contract (Gate E.3 / P1) — versions, vocabularies and value types.

Pure module: standard library only. Nothing here touches a database, the
application configuration or the network.

A *source claim* is what an ICTU source asserts. It is never an approved
identity: no type in this package carries a reviewer decision, and nothing
here maps a claim onto a lecturer or a canonical Scopus author.

Immutability: every value type is a frozen dataclass whose collections are
tuples. Raw source values are stored as canonical JSON text (``raw_json``) so
that they cannot be mutated after parsing and can be recovered exactly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

CONTRACT_NAME = "ictu-source-claims"
CONTRACT_VERSION = "1.0"
CONTRACT_MAJOR = 1
# Versions of the rules that derive keys and normalized values. Withdrawal is
# only inferred between snapshots parsed under the same versions.
IDENTITY_RULES_VERSION = "1"
NORMALIZATION_VERSION = "1"


class SourceSystem(StrEnum):
    ICTU_REPO_SCOPUS_GUIDE = "ICTU_REPO_SCOPUS_GUIDE"
    ICTU_REPO_PROFILES = "ICTU_REPO_PROFILES"


class Completeness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"


class TableKind(StrEnum):
    MULTI_ID = "MULTI_ID"
    AMBIGUOUS = "AMBIGUOUS"
    UNASSIGNED = "UNASSIGNED"


class RecordKind(StrEnum):
    PROFILE = "PROFILE"
    MULTI_ID_ROW = "MULTI_ID_ROW"
    AMBIGUOUS_ID_ROW = "AMBIGUOUS_ID_ROW"
    UNASSIGNED_ID_ROW = "UNASSIGNED_ID_ROW"


RECORD_KIND_BY_TABLE = {
    TableKind.MULTI_ID: RecordKind.MULTI_ID_ROW,
    TableKind.AMBIGUOUS: RecordKind.AMBIGUOUS_ID_ROW,
    TableKind.UNASSIGNED: RecordKind.UNASSIGNED_ID_ROW,
}


class ClaimType(StrEnum):
    SCOPUS_ID_OWNED = "SCOPUS_ID_OWNED"
    SCOPUS_ID_AMBIGUOUS = "SCOPUS_ID_AMBIGUOUS"
    SCOPUS_ID_UNASSIGNED = "SCOPUS_ID_UNASSIGNED"
    ORCID_DECLARED = "ORCID_DECLARED"
    EMAIL_DECLARED = "EMAIL_DECLARED"


SCOPUS_CLAIM_TYPES = frozenset({
    ClaimType.SCOPUS_ID_OWNED, ClaimType.SCOPUS_ID_AMBIGUOUS, ClaimType.SCOPUS_ID_UNASSIGNED,
})


class ColumnRole(StrEnum):
    """Meaning of a source table column, declared by the capture artifact."""

    NAME = "NAME"
    EMAIL = "EMAIL"
    DECLARED_ID_COUNT = "DECLARED_ID_COUNT"
    DECLARED_PUB_COUNT = "DECLARED_PUB_COUNT"
    PRIMARY_SCOPUS_ID = "PRIMARY_SCOPUS_ID"
    SCOPUS_ID_LIST = "SCOPUS_ID_LIST"
    SCOPUS_NAME = "SCOPUS_NAME"
    SCOPUS_ID = "SCOPUS_ID"
    OTHER = "OTHER"


ALLOWED_ROLES = {
    TableKind.MULTI_ID: frozenset({
        ColumnRole.NAME, ColumnRole.EMAIL, ColumnRole.DECLARED_ID_COUNT,
        ColumnRole.DECLARED_PUB_COUNT, ColumnRole.PRIMARY_SCOPUS_ID,
        ColumnRole.SCOPUS_ID_LIST, ColumnRole.OTHER,
    }),
    TableKind.AMBIGUOUS: frozenset({
        ColumnRole.SCOPUS_NAME, ColumnRole.SCOPUS_ID, ColumnRole.DECLARED_PUB_COUNT,
        ColumnRole.OTHER,
    }),
    TableKind.UNASSIGNED: frozenset({
        ColumnRole.SCOPUS_NAME, ColumnRole.SCOPUS_ID, ColumnRole.DECLARED_PUB_COUNT,
        ColumnRole.OTHER,
    }),
}
REQUIRED_ROLES = {
    TableKind.MULTI_ID: frozenset({ColumnRole.SCOPUS_ID_LIST}),
    TableKind.AMBIGUOUS: frozenset({ColumnRole.SCOPUS_ID}),
    TableKind.UNASSIGNED: frozenset({ColumnRole.SCOPUS_ID}),
}

# Declared-count keys a capture tool may report next to the raw page summary.
DECLARED_COUNT_KEYS = {
    "MULTI_ID_LECTURERS": TableKind.MULTI_ID,
    "AMBIGUOUS_IDS": TableKind.AMBIGUOUS,
    "UNASSIGNED_IDS": TableKind.UNASSIGNED,
}

# Profile fields with a defined meaning. Any other field is kept verbatim.
PROFILE_SOURCE_ID_FIELD = "source_id"
PROFILE_EMAIL_FIELD = "email"
PROFILE_ORCID_FIELD = "orcid"


class ValidationStatus(StrEnum):
    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"


class Severity(StrEnum):
    WARNING = "WARNING"
    ERROR = "ERROR"


class KeyMethod(StrEnum):
    """How a record key was derived. Names are never a key."""

    PROFILE_SOURCE_ID_V1 = "PROFILE_SOURCE_ID_V1"  # stable profile URL/handle
    EMAIL_V1 = "EMAIL_V1"                          # normalized e-mail
    SCOPUS_ID_V1 = "SCOPUS_ID_V1"                  # the row's own Scopus ID
    CONTENT_V1 = "CONTENT_V1"                      # source-scoped hash of raw content


class KeyStrength(StrEnum):
    STRONG = "STRONG"  # stable source identifier
    MEDIUM = "MEDIUM"  # e-mail: stable in practice, not guaranteed unique
    WEAK = "WEAK"      # content-derived; changes when any cell changes


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    severity: Severity
    message: str
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity.value,
                "message": self.message, "field": self.field}


@dataclass(frozen=True, slots=True)
class NormalizedValue:
    """A raw source value next to its normalized form.

    ``normalized`` is None when the raw value is invalid. ``method`` names the
    normalization so a later rule change is detectable.
    """

    raw: str | None
    normalized: str | None
    method: str
    issues: tuple[Issue, ...] = ()

    @property
    def valid(self) -> bool:
        return self.normalized is not None


@dataclass(frozen=True, slots=True)
class RecordKey:
    value: str
    method: KeyMethod
    strength: KeyStrength


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """One source row or profile, kept whole even when fields are invalid."""

    record_kind: RecordKind
    source_position: int           # 1-based position in its table / profile list
    raw_json: str                  # canonical JSON of the exact source value
    record_hash: str               # sha256 over kind + raw value (position excluded)
    record_key: RecordKey
    normalized: tuple[tuple[str, Any], ...]
    validation_status: ValidationStatus
    issues: tuple[Issue, ...]

    @property
    def raw(self) -> Any:
        return json.loads(self.raw_json)

    @property
    def ref(self) -> str:
        return f"{self.record_kind.value}#{self.source_position}"


@dataclass(frozen=True, slots=True)
class ClaimItem:
    """One atomic assertion made by one source record."""

    claim_type: ClaimType
    record_ref: str                # SourceRecord.ref
    subject_key: str | None        # owner/profile record key; None for unowned IDs
    value: NormalizedValue
    claim_key: str
    flags: tuple[tuple[str, Any], ...] = ()

    def flag(self, name: str, default: Any = None) -> Any:
        return dict(self.flags).get(name, default)


@dataclass(frozen=True, slots=True)
class CaptureMetadata:
    """How and when the content was observed. Never part of the content hash."""

    captured_at: str
    completeness: Completeness
    capture_json: str              # canonical JSON of the whole capture block
    capture_hash: str


@dataclass(frozen=True, slots=True)
class ParsedSnapshot:
    """Result of parsing one artifact. Deterministic for identical input."""

    contract_version: str
    source_system: SourceSystem
    source_url: str
    scope_key: str                 # what was captured; comparable snapshots share it
    content_json: str              # canonical JSON of the semantic source payload
    content_hash: str              # identity of the source content version
    capture: CaptureMetadata
    artifact_bytes_sha256: str | None
    declared_counts: tuple[tuple[str, int], ...]
    records: tuple[SourceRecord, ...]
    claims: tuple[ClaimItem, ...]
    issues: tuple[Issue, ...]      # artifact-level issues
    identity_rules_version: str = IDENTITY_RULES_VERSION
    normalization_version: str = NORMALIZATION_VERSION

    @property
    def content(self) -> Any:
        return json.loads(self.content_json)

    @property
    def completeness(self) -> Completeness:
        return self.capture.completeness
