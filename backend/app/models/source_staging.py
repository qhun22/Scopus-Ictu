"""Source-claim staging (Gate E.3 / P2-B1): append-only, pre-identity; only external FK: users.

Artifacts never point at an analysis, so a new rule version adds an analysis without touching any
artifact row; ``source_rule_sets`` (newest row active) drives the observation view.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_ID = dict(primary_key=True, server_default=text("gen_random_uuid()"))
_NOW = text("now()")

SOURCE_SYSTEMS = ("ICTU_REPO_SCOPUS_GUIDE", "ICTU_REPO_PROFILES")
RECORD_KINDS = ("PROFILE", "MULTI_ID_ROW", "AMBIGUOUS_ID_ROW", "UNASSIGNED_ID_ROW")
CLAIM_TYPES = ("SCOPUS_ID_OWNED", "SCOPUS_ID_AMBIGUOUS", "SCOPUS_ID_UNASSIGNED",
               "ORCID_DECLARED", "EMAIL_DECLARED")
UNOWNED_CLAIM_TYPES = ("SCOPUS_ID_AMBIGUOUS", "SCOPUS_ID_UNASSIGNED")
KEY_METHOD_STRENGTH = (("PROFILE_SOURCE_ID_V1", "STRONG"), ("EMAIL_V1", "MEDIUM"),
                       ("SCOPUS_ID_V1", "STRONG"), ("CONTENT_V1", "WEAK"))
VALIDATION_STATUSES = ("VALID", "WARNING", "INVALID")
# PostgreSQL ARE: without the 'n' flag, ``$`` matches only at the end of the string, so this is
# the same language as the parser's ``re.fullmatch(r"1\.[0-9]+")``.
CONTRACT_VERSION_SQL_PATTERN = r"^1\.[0-9]+$"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _hex(column: str) -> str:
    return f"{column} ~ '^[0-9a-f]{{64}}$'"


def _json_sha(json_column: str, hash_column: str) -> str:
    return f"{hash_column} = encode(sha256(convert_to({json_column}, 'UTF8')), 'hex')"


def _not_blank(column: str) -> str:
    return f"btrim({column}) <> ''"


class SourceRuleSet(Base):
    """Append-only log of rule-version activations; the highest ``sequence_no`` is active."""

    __tablename__ = "source_rule_sets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_ID)
    sequence_no: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False)
    identity_rules_version: Mapped[str] = mapped_column(String(20), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    activated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        CheckConstraint(_not_blank("identity_rules_version"),
                        name="identity_rules_version_not_empty"),
        CheckConstraint(_not_blank("normalization_version"),
                        name="normalization_version_not_empty"),
        UniqueConstraint("sequence_no", name="uq_source_rule_sets_sequence_no"),
    )


class SourceContent(Base):
    """One immutable source assertion; ``content_json`` is the exact hashed text."""

    __tablename__ = "source_contents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_ID)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    contract_major: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        CheckConstraint(_in("source_system", SOURCE_SYSTEMS), name="source_system"),
        CheckConstraint("contract_major = 1", name="contract_major"),
        CheckConstraint(_hex("scope_key"), name="scope_key"),
        CheckConstraint(_hex("content_hash"), name="content_hash"),
        CheckConstraint(_json_sha("content_json", "content_hash"), name="content_hash_matches"),
        UniqueConstraint("source_system", "content_hash", name="uq_source_contents_system_hash"),
        UniqueConstraint("id", "source_system", name="uq_source_contents_id_system"),
        Index("ix_source_contents_system_scope", "source_system", "scope_key"),
    )


class SourceCapture(Base):
    """One observation of a content (capture time, completeness, lineage)."""

    __tablename__ = "source_captures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_ID)
    content_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completeness: Mapped[str] = mapped_column(String(10), nullable=False)
    capture_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    capture_json: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(100), nullable=False)
    projection_version: Mapped[str] = mapped_column(String(100), nullable=False)
    upstream_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    upstream_bytes_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        ForeignKeyConstraint(
            ["content_id", "source_system"],
            ["source_contents.id", "source_contents.source_system"],
            name="fk_source_captures_content_system", ondelete="RESTRICT"),
        CheckConstraint(_in("completeness", ("COMPLETE", "PARTIAL")), name="completeness"),
        CheckConstraint(_hex("capture_hash"), name="capture_hash"),
        CheckConstraint(_json_sha("capture_json", "capture_hash"), name="capture_hash_matches"),
        CheckConstraint(_hex("upstream_bytes_sha256"), name="upstream_bytes_sha256"),
        CheckConstraint(_not_blank("adapter_version"), name="adapter_version_not_empty"),
        CheckConstraint(_not_blank("projection_version"), name="projection_version_not_empty"),
        UniqueConstraint("content_id", "capture_hash", name="uq_source_captures_content_capture"),
        UniqueConstraint("id", "content_id", name="uq_source_captures_id_content"),
        Index("ix_source_captures_system_captured", "source_system", "captured_at"),
        Index("ix_source_captures_content", "content_id"),
    )


class SourceArtifact(Base):
    """One exact canonical envelope; rebuildable from capture_json + content_json + version."""

    __tablename__ = "source_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_ID)
    content_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    capture_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(20), nullable=False)
    artifact_bytes_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    received_bytes_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upstream_storage_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        ForeignKeyConstraint(
            ["capture_id", "content_id"], ["source_captures.id", "source_captures.content_id"],
            name="fk_source_artifacts_capture_content", ondelete="RESTRICT"),
        CheckConstraint(f"contract_version ~ '{CONTRACT_VERSION_SQL_PATTERN}'",
                        name="contract_version"),
        CheckConstraint(_hex("artifact_bytes_sha256"), name="artifact_bytes_sha256"),
        CheckConstraint(f"received_bytes_sha256 IS NULL OR {_hex('received_bytes_sha256')}",
                        name="received_bytes_sha256"),
        UniqueConstraint("artifact_bytes_sha256", name="uq_source_artifacts_artifact_bytes_sha256"),
        # Same capture + same version => same canonical bytes; stated explicitly so the
        # observation view's one-artifact-per-(capture, version) basis is a DB guarantee.
        UniqueConstraint("capture_id", "contract_version",
                         name="uq_source_artifacts_capture_version"),
        Index("ix_source_artifacts_content_version", "content_id", "contract_version"),
    )


class SourceAnalysis(Base):
    """One parse of a content under one contract version and one rule set."""

    __tablename__ = "source_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_ID)
    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_contents.id", ondelete="RESTRICT"), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(20), nullable=False)
    identity_rules_version: Mapped[str] = mapped_column(String(20), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(20), nullable=False)
    parser_build: Mapped[str] = mapped_column(String(100), nullable=False)
    artifact_issues: Mapped[Any] = mapped_column(JSONB, nullable=False)
    declared_counts: Mapped[Any] = mapped_column(JSONB, nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        CheckConstraint(f"contract_version ~ '{CONTRACT_VERSION_SQL_PATTERN}'",
                        name="contract_version"),
        CheckConstraint(_not_blank("identity_rules_version"),
                        name="identity_rules_version_not_empty"),
        CheckConstraint(_not_blank("normalization_version"),
                        name="normalization_version_not_empty"),
        CheckConstraint(_not_blank("parser_build"), name="parser_build_not_empty"),
        CheckConstraint("jsonb_typeof(artifact_issues) = 'array'", name="artifact_issues_array"),
        CheckConstraint("jsonb_typeof(declared_counts) = 'object'", name="declared_counts_object"),
        CheckConstraint("record_count >= 0 AND claim_count >= 0", name="counts"),
        UniqueConstraint("content_id", "contract_version", "identity_rules_version",
                         "normalization_version", name="uq_source_analyses_content_rules"),
        Index("ix_source_analyses_rules", "identity_rules_version", "normalization_version"),
    )


class SourceRecord(Base):
    """One source row or profile as parsed; duplicate keys are kept and flagged, never merged."""

    __tablename__ = "source_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_ID)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_analyses.id", ondelete="RESTRICT"), nullable=False)
    record_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_position: Mapped[int] = mapped_column(Integer, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_method: Mapped[str] = mapped_column(String(30), nullable=False)
    key_strength: Mapped[str] = mapped_column(String(10), nullable=False)
    raw: Mapped[Any] = mapped_column(JSONB, nullable=False)
    normalized: Mapped[Any] = mapped_column(JSONB, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(10), nullable=False)
    issues: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        CheckConstraint(_in("record_kind", RECORD_KINDS), name="record_kind"),
        CheckConstraint("source_position >= 1", name="source_position"),
        CheckConstraint(_hex("record_hash"), name="record_hash"),
        CheckConstraint(_not_blank("record_key"), name="record_key_not_empty"),
        CheckConstraint(" OR ".join(f"(key_method = '{m}' AND key_strength = '{s}')"
                                    for m, s in KEY_METHOD_STRENGTH), name="key_method_strength"),
        CheckConstraint(_in("validation_status", VALIDATION_STATUSES), name="validation_status"),
        CheckConstraint("jsonb_typeof(normalized) = 'object'", name="normalized_object"),
        CheckConstraint("jsonb_typeof(issues) = 'array'", name="issues_array"),
        UniqueConstraint("analysis_id", "record_kind", "source_position",
                         name="uq_source_records_position"),
        UniqueConstraint("id", "analysis_id", name="uq_source_records_id_analysis"),
        Index("ix_source_records_key", "analysis_id", "record_kind", "record_key"),
        Index("ix_source_records_record_hash", "record_hash"),
        Index("ix_source_records_method_key", "key_method", "record_key"),
    )


class SourceClaim(Base):
    """One atomic source assertion; never an identity. Shared values keep separate rows."""

    __tablename__ = "source_claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_ID)
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_method: Mapped[str] = mapped_column(String(60), nullable=False)
    value_valid: Mapped[bool] = mapped_column(
        Boolean, Computed("value_normalized IS NOT NULL", persisted=True))
    claim_key: Mapped[str] = mapped_column(Text, nullable=False)
    flags: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=_NOW)

    __table_args__ = (
        ForeignKeyConstraint(
            ["record_id", "analysis_id"], ["source_records.id", "source_records.analysis_id"],
            name="fk_source_claims_record_analysis", ondelete="RESTRICT"),
        CheckConstraint(_in("claim_type", CLAIM_TYPES), name="claim_type"),
        CheckConstraint(f"(subject_key IS NULL) = ({_in('claim_type', UNOWNED_CLAIM_TYPES)})",
                        name="subject_iff_owned"),
        CheckConstraint("left(claim_key, length(claim_type) + 1) = claim_type || '|'",
                        name="claim_key_prefix"),
        CheckConstraint(_not_blank("value_method"), name="value_method_not_empty"),
        CheckConstraint("jsonb_typeof(flags) = 'object'", name="flags_object"),
        UniqueConstraint("record_id", "claim_key", name="uq_source_claims_record_claim_key"),
        Index("ix_source_claims_type_value", "claim_type", "value_normalized"),
        Index("ix_source_claims_analysis_key", "analysis_id", "claim_key"),
        Index("ix_source_claims_subject", "subject_key"),
    )


# Portable SQL (PostgreSQL and SQLite) so the selection logic is executable in tests; the
# migration holds an identical copy. SUBSTR(..., 3) is the numeric minor: the CHECK pins major '1'.

SOURCE_CAPTURE_ANALYSES_VIEW = "source_capture_analyses"
SOURCE_CAPTURE_ANALYSES_SQL = """\
WITH active_rule_set AS (
    SELECT identity_rules_version, normalization_version
    FROM source_rule_sets
    ORDER BY sequence_no DESC
    LIMIT 1
),
candidates AS (
    SELECT
        cap.id AS capture_id,
        art.id AS artifact_id,
        an.id AS analysis_id,
        an.contract_version AS contract_version,
        an.identity_rules_version AS identity_rules_version,
        an.normalization_version AS normalization_version,
        an.created_at AS analysis_created_at,
        CASE WHEN act.identity_rules_version IS NULL THEN 0 ELSE 1 END AS is_active_rule_set
    FROM source_captures cap
    JOIN source_artifacts art ON art.capture_id = cap.id
    JOIN source_analyses an
      ON an.content_id = art.content_id
     AND an.contract_version = art.contract_version
    LEFT JOIN active_rule_set act
      ON act.identity_rules_version = an.identity_rules_version
     AND act.normalization_version = an.normalization_version
)
SELECT
    c.capture_id,
    c.artifact_id,
    c.analysis_id,
    c.contract_version,
    c.identity_rules_version,
    c.normalization_version,
    c.analysis_created_at,
    c.is_active_rule_set,
    ROW_NUMBER() OVER (
        PARTITION BY c.capture_id
        ORDER BY c.is_active_rule_set DESC,
                 CAST(SUBSTR(c.contract_version, 3) AS INTEGER) DESC,
                 c.analysis_created_at DESC,
                 c.analysis_id
    ) AS selection_rank
FROM candidates c"""

SOURCE_CLAIM_OBSERVATIONS_VIEW = "source_claim_observations"
SOURCE_CLAIM_OBSERVATIONS_SQL = """\
SELECT
    sel.capture_id,
    cap.source_system,
    cap.captured_at,
    cap.completeness,
    sel.artifact_id,
    sel.analysis_id,
    sel.contract_version,
    sel.identity_rules_version,
    sel.normalization_version,
    cl.id AS claim_id,
    cl.record_id,
    cl.claim_type,
    cl.subject_key,
    cl.value_normalized,
    cl.claim_key
FROM source_capture_analyses sel
JOIN source_captures cap ON cap.id = sel.capture_id
JOIN source_claims cl ON cl.analysis_id = sel.analysis_id
WHERE sel.selection_rank = 1
  AND sel.is_active_rule_set = 1"""

STAGING_TABLES = ("source_rule_sets", "source_contents", "source_captures", "source_artifacts",
                  "source_analyses", "source_records", "source_claims")
STAGING_VIEWS = (SOURCE_CAPTURE_ANALYSES_VIEW, SOURCE_CLAIM_OBSERVATIONS_VIEW)
