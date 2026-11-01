"""E3-P2-B1 source-claim staging tables and observation views.

Adds pre-identity staging only: no FK to lecturers, Scopus authors, candidates, reviews or
identities, and no data. Revision ID: a77e01c33ee1, revises a1b2c3d4e5f6.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a77e01c33ee1"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
NOW = sa.text("now()")
GEN_RANDOM_UUID = sa.text("gen_random_uuid()")
HEX64 = "~ '^[0-9a-f]{64}$'"
CONTRACT_VERSION = "contract_version ~ '^1\\.[0-9]+$'"

# Identical to app.models.source_staging (a unit test asserts equality).
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


def _ck(table: str, name: str, sql: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def _created(name: str = "created_at") -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=NOW)


def upgrade() -> None:
    t = "source_rule_sets"
    op.create_table(
        t,
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("sequence_no", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("identity_rules_version", sa.String(length=20), nullable=False),
        sa.Column("normalization_version", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("activated_by", UUID, nullable=True),
        _created("activated_at"),
        sa.ForeignKeyConstraint(["activated_by"], ["users.id"],
                                name=op.f("fk_source_rule_sets_activated_by_users"),
                                ondelete="RESTRICT"),
        _ck(t, "identity_rules_version_not_empty", "btrim(identity_rules_version) <> ''"),
        _ck(t, "normalization_version_not_empty", "btrim(normalization_version) <> ''"),
        sa.UniqueConstraint("sequence_no", name="uq_source_rule_sets_sequence_no"),
    )

    t = "source_contents"
    op.create_table(
        t,
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("source_system", sa.String(length=50), nullable=False),
        sa.Column("contract_major", sa.SmallInteger(), nullable=False),
        sa.Column("scope_key", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        _created(),
        _ck(t, "source_system",
            "source_system IN ('ICTU_REPO_SCOPUS_GUIDE', 'ICTU_REPO_PROFILES')"),
        _ck(t, "contract_major", "contract_major = 1"),
        _ck(t, "scope_key", f"scope_key {HEX64}"),
        _ck(t, "content_hash", f"content_hash {HEX64}"),
        _ck(t, "content_hash_matches",
            "content_hash = encode(sha256(convert_to(content_json, 'UTF8')), 'hex')"),
        sa.UniqueConstraint("source_system", "content_hash", name="uq_source_contents_system_hash"),
        sa.UniqueConstraint("id", "source_system", name="uq_source_contents_id_system"),
    )
    op.create_index("ix_source_contents_system_scope", t, ["source_system", "scope_key"])

    t = "source_captures"
    op.create_table(
        t,
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("content_id", UUID, nullable=False),
        sa.Column("source_system", sa.String(length=50), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completeness", sa.String(length=10), nullable=False),
        sa.Column("capture_hash", sa.String(length=64), nullable=False),
        sa.Column("capture_json", sa.Text(), nullable=False),
        sa.Column("adapter_version", sa.String(length=100), nullable=False),
        sa.Column("projection_version", sa.String(length=100), nullable=False),
        sa.Column("upstream_name", sa.Text(), nullable=True),
        sa.Column("upstream_bytes_sha256", sa.String(length=64), nullable=False),
        _created(),
        sa.ForeignKeyConstraint(["content_id", "source_system"],
                                ["source_contents.id", "source_contents.source_system"],
                                name="fk_source_captures_content_system", ondelete="RESTRICT"),
        _ck(t, "completeness", "completeness IN ('COMPLETE', 'PARTIAL')"),
        _ck(t, "capture_hash", f"capture_hash {HEX64}"),
        _ck(t, "capture_hash_matches",
            "capture_hash = encode(sha256(convert_to(capture_json, 'UTF8')), 'hex')"),
        _ck(t, "upstream_bytes_sha256", f"upstream_bytes_sha256 {HEX64}"),
        _ck(t, "adapter_version_not_empty", "btrim(adapter_version) <> ''"),
        _ck(t, "projection_version_not_empty", "btrim(projection_version) <> ''"),
        sa.UniqueConstraint("content_id", "capture_hash",
                            name="uq_source_captures_content_capture"),
        sa.UniqueConstraint("id", "content_id", name="uq_source_captures_id_content"),
    )
    op.create_index("ix_source_captures_system_captured", t, ["source_system", "captured_at"])
    op.create_index("ix_source_captures_content", t, ["content_id"])

    t = "source_artifacts"
    op.create_table(
        t,
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("content_id", UUID, nullable=False),
        sa.Column("capture_id", UUID, nullable=False),
        sa.Column("contract_version", sa.String(length=20), nullable=False),
        sa.Column("artifact_bytes_sha256", sa.String(length=64), nullable=False),
        sa.Column("received_bytes_sha256", sa.String(length=64), nullable=True),
        sa.Column("upstream_storage_ref", sa.Text(), nullable=True),
        sa.Column("ingested_by", UUID, nullable=True),
        _created("ingested_at"),
        sa.ForeignKeyConstraint(["capture_id", "content_id"],
                                ["source_captures.id", "source_captures.content_id"],
                                name="fk_source_artifacts_capture_content", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ingested_by"], ["users.id"],
                                name=op.f("fk_source_artifacts_ingested_by_users"),
                                ondelete="RESTRICT"),
        _ck(t, "contract_version", CONTRACT_VERSION),
        _ck(t, "artifact_bytes_sha256", f"artifact_bytes_sha256 {HEX64}"),
        _ck(t, "received_bytes_sha256",
            f"received_bytes_sha256 IS NULL OR received_bytes_sha256 {HEX64}"),
        sa.UniqueConstraint("artifact_bytes_sha256",
                            name="uq_source_artifacts_artifact_bytes_sha256"),
        sa.UniqueConstraint("capture_id", "contract_version",
                            name="uq_source_artifacts_capture_version"),
    )
    op.create_index("ix_source_artifacts_content_version", t, ["content_id", "contract_version"])

    t = "source_analyses"
    op.create_table(
        t,
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("content_id", UUID, nullable=False),
        sa.Column("contract_version", sa.String(length=20), nullable=False),
        sa.Column("identity_rules_version", sa.String(length=20), nullable=False),
        sa.Column("normalization_version", sa.String(length=20), nullable=False),
        sa.Column("parser_build", sa.String(length=100), nullable=False),
        sa.Column("artifact_issues", JSONB, nullable=False),
        sa.Column("declared_counts", JSONB, nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("claim_count", sa.Integer(), nullable=False),
        _created(),
        sa.ForeignKeyConstraint(["content_id"], ["source_contents.id"],
                                name=op.f("fk_source_analyses_content_id_source_contents"),
                                ondelete="RESTRICT"),
        _ck(t, "contract_version", CONTRACT_VERSION),
        _ck(t, "identity_rules_version_not_empty", "btrim(identity_rules_version) <> ''"),
        _ck(t, "normalization_version_not_empty", "btrim(normalization_version) <> ''"),
        _ck(t, "parser_build_not_empty", "btrim(parser_build) <> ''"),
        _ck(t, "artifact_issues_array", "jsonb_typeof(artifact_issues) = 'array'"),
        _ck(t, "declared_counts_object", "jsonb_typeof(declared_counts) = 'object'"),
        _ck(t, "counts", "record_count >= 0 AND claim_count >= 0"),
        sa.UniqueConstraint("content_id", "contract_version", "identity_rules_version",
                            "normalization_version", name="uq_source_analyses_content_rules"),
    )
    op.create_index("ix_source_analyses_rules", t,
                    ["identity_rules_version", "normalization_version"])

    t = "source_records"
    op.create_table(
        t,
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("analysis_id", UUID, nullable=False),
        sa.Column("record_kind", sa.String(length=30), nullable=False),
        sa.Column("source_position", sa.Integer(), nullable=False),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
        sa.Column("record_key", sa.Text(), nullable=False),
        sa.Column("key_method", sa.String(length=30), nullable=False),
        sa.Column("key_strength", sa.String(length=10), nullable=False),
        sa.Column("raw", JSONB, nullable=False),
        sa.Column("normalized", JSONB, nullable=False),
        sa.Column("validation_status", sa.String(length=10), nullable=False),
        sa.Column("issues", JSONB, nullable=False),
        _created(),
        sa.ForeignKeyConstraint(["analysis_id"], ["source_analyses.id"],
                                name=op.f("fk_source_records_analysis_id_source_analyses"),
                                ondelete="RESTRICT"),
        _ck(t, "record_kind", "record_kind IN ('PROFILE', 'MULTI_ID_ROW', 'AMBIGUOUS_ID_ROW', "
                              "'UNASSIGNED_ID_ROW')"),
        _ck(t, "source_position", "source_position >= 1"),
        _ck(t, "record_hash", f"record_hash {HEX64}"),
        _ck(t, "record_key_not_empty", "btrim(record_key) <> ''"),
        _ck(t, "key_method_strength",
            "(key_method = 'PROFILE_SOURCE_ID_V1' AND key_strength = 'STRONG') OR "
            "(key_method = 'EMAIL_V1' AND key_strength = 'MEDIUM') OR "
            "(key_method = 'SCOPUS_ID_V1' AND key_strength = 'STRONG') OR "
            "(key_method = 'CONTENT_V1' AND key_strength = 'WEAK')"),
        _ck(t, "validation_status", "validation_status IN ('VALID', 'WARNING', 'INVALID')"),
        _ck(t, "normalized_object", "jsonb_typeof(normalized) = 'object'"),
        _ck(t, "issues_array", "jsonb_typeof(issues) = 'array'"),
        sa.UniqueConstraint("analysis_id", "record_kind", "source_position",
                            name="uq_source_records_position"),
        sa.UniqueConstraint("id", "analysis_id", name="uq_source_records_id_analysis"),
    )
    op.create_index("ix_source_records_key", t, ["analysis_id", "record_kind", "record_key"])
    op.create_index("ix_source_records_record_hash", t, ["record_hash"])
    op.create_index("ix_source_records_method_key", t, ["key_method", "record_key"])

    t = "source_claims"
    op.create_table(
        t,
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("analysis_id", UUID, nullable=False),
        sa.Column("record_id", UUID, nullable=False),
        sa.Column("claim_type", sa.String(length=30), nullable=False),
        sa.Column("subject_key", sa.Text(), nullable=True),
        sa.Column("value_raw", sa.Text(), nullable=True),
        sa.Column("value_normalized", sa.Text(), nullable=True),
        sa.Column("value_method", sa.String(length=60), nullable=False),
        sa.Column("value_valid", sa.Boolean(),
                  sa.Computed("value_normalized IS NOT NULL", persisted=True), nullable=False),
        sa.Column("claim_key", sa.Text(), nullable=False),
        sa.Column("flags", JSONB, nullable=False),
        _created(),
        sa.ForeignKeyConstraint(["record_id", "analysis_id"],
                                ["source_records.id", "source_records.analysis_id"],
                                name="fk_source_claims_record_analysis", ondelete="RESTRICT"),
        _ck(t, "claim_type", "claim_type IN ('SCOPUS_ID_OWNED', 'SCOPUS_ID_AMBIGUOUS', "
                             "'SCOPUS_ID_UNASSIGNED', 'ORCID_DECLARED', 'EMAIL_DECLARED')"),
        _ck(t, "subject_iff_owned",
            "(subject_key IS NULL) = (claim_type IN ('SCOPUS_ID_AMBIGUOUS', "
            "'SCOPUS_ID_UNASSIGNED'))"),
        _ck(t, "claim_key_prefix", "left(claim_key, length(claim_type) + 1) = claim_type || '|'"),
        _ck(t, "value_method_not_empty", "btrim(value_method) <> ''"),
        _ck(t, "flags_object", "jsonb_typeof(flags) = 'object'"),
        sa.UniqueConstraint("record_id", "claim_key", name="uq_source_claims_record_claim_key"),
    )
    op.create_index("ix_source_claims_type_value", t, ["claim_type", "value_normalized"])
    op.create_index("ix_source_claims_analysis_key", t, ["analysis_id", "claim_key"])
    op.create_index("ix_source_claims_subject", t, ["subject_key"])

    op.execute(f"CREATE VIEW source_capture_analyses AS\n{SOURCE_CAPTURE_ANALYSES_SQL}")
    op.execute(f"CREATE VIEW source_claim_observations AS\n{SOURCE_CLAIM_OBSERVATIONS_SQL}")


def downgrade() -> None:
    op.execute("DROP VIEW source_claim_observations")
    op.execute("DROP VIEW source_capture_analyses")
    for table, indexes in (
        ("source_claims", ("ix_source_claims_subject", "ix_source_claims_analysis_key",
                           "ix_source_claims_type_value")),
        ("source_records", ("ix_source_records_method_key", "ix_source_records_record_hash",
                            "ix_source_records_key")),
        ("source_analyses", ("ix_source_analyses_rules",)),
        ("source_artifacts", ("ix_source_artifacts_content_version",)),
        ("source_captures", ("ix_source_captures_content", "ix_source_captures_system_captured")),
        ("source_contents", ("ix_source_contents_system_scope",)),
        ("source_rule_sets", ()),
    ):
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
