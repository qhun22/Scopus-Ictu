"""Additive author-level affiliation tables (organizations, resolutions, affiliations).

Adds three tables and nothing else: no existing table, column, constraint or
row is touched, and no identity / candidate data is created.  Downgrade drops
exactly these three tables (children first).

Revision ID: a9c2e4f71b30
Revises: d3f7a1c9e2b4
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a9c2e4f71b30"
down_revision: Union[str, None] = "d3f7a1c9e2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
NOW = sa.text("now()")
GEN_RANDOM_UUID = sa.text("gen_random_uuid()")
RES = "publication_author_affiliation_resolutions"
AFF = "publication_author_affiliations"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("source_org_id", sa.Text(), nullable=True),
        sa.Column("ror", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.CheckConstraint("btrim(source_system) <> ''", name=op.f("ck_organizations_source_system")),
        sa.CheckConstraint("btrim(display_name) <> ''", name=op.f("ck_organizations_display_name")),
        sa.CheckConstraint(
            "source_org_id IS NULL OR btrim(source_org_id) <> ''",
            name=op.f("ck_organizations_source_org_id"),
        ),
        sa.CheckConstraint(
            "country_code IS NULL OR country_code ~ '^[A-Z]{2}$'",
            name=op.f("ck_organizations_country_code"),
        ),
    )
    op.create_index(
        "uq_organizations_source_org",
        "organizations",
        ["source_system", "source_org_id"],
        unique=True,
        postgresql_where=sa.text("source_org_id IS NOT NULL"),
    )
    op.create_index(
        "uq_organizations_source_name",
        "organizations",
        ["source_system", "display_name"],
        unique=True,
        postgresql_where=sa.text("source_org_id IS NULL"),
    )
    op.create_index("ix_organizations_ror", "organizations", ["ror"])

    op.create_table(
        RES,
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("publication_author_id", UUID, nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("source_payload_sha256", sa.String(64), nullable=False),
        sa.Column("link_status", sa.String(20), nullable=False),
        sa.Column("link_method", sa.String(40), nullable=True),
        sa.Column("unresolved_reason", sa.String(80), nullable=True),
        sa.Column("affiliation_presence", sa.String(10), nullable=True),
        sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_doi", sa.Text(), nullable=True),
        sa.Column("source_work_id", sa.Text(), nullable=True),
        sa.Column("external_position", sa.Integer(), nullable=True),
        sa.Column("external_author_name", sa.Text(), nullable=True),
        sa.Column("external_author_orcid", sa.String(19), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("importer_version", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_" + RES)),
        sa.ForeignKeyConstraint(
            ["publication_author_id"],
            ["publication_authors.id"],
            name="fk_paar_publication_author_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("id", "link_status", name="uq_paar_id_link_status"),
        sa.UniqueConstraint(
            "publication_author_id",
            "source_system",
            "source_payload_sha256",
            name="uq_paar_author_source_payload",
        ),
        sa.CheckConstraint("btrim(source_system) <> ''", name=op.f("ck_" + RES + "_source_system")),
        sa.CheckConstraint(
            "source_payload_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_" + RES + "_payload_hash")
        ),
        sa.CheckConstraint(
            "link_status IN ('VERIFIED', 'CORROBORATED', 'UNRESOLVED')",
            name=op.f("ck_" + RES + "_link_status"),
        ),
        sa.CheckConstraint(
            "(link_status = 'VERIFIED' AND link_method IS NOT NULL "
            "AND link_method = 'ORCID_SCOPUS_ID_BRIDGE') OR "
            "(link_status = 'CORROBORATED' AND link_method IS NOT NULL "
            "AND link_method = 'POSITION_COUNT_NAME') OR "
            "(link_status = 'UNRESOLVED' AND link_method IS NULL)",
            name=op.f("ck_" + RES + "_link_method"),
        ),
        sa.CheckConstraint(
            "(link_status = 'UNRESOLVED') = (unresolved_reason IS NOT NULL) AND "
            "(unresolved_reason IS NULL OR btrim(unresolved_reason) <> '')",
            name=op.f("ck_" + RES + "_reason"),
        ),
        sa.CheckConstraint(
            "(link_status = 'UNRESOLVED' AND affiliation_presence IS NULL) OR "
            "(link_status <> 'UNRESOLVED' AND affiliation_presence IS NOT NULL "
            "AND affiliation_presence IN ('PRESENT', 'ABSENT'))",
            name=op.f("ck_" + RES + "_presence"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence) = 'object'", name=op.f("ck_" + RES + "_evidence_object")
        ),
        sa.CheckConstraint(
            "external_position IS NULL OR external_position >= 1",
            name=op.f("ck_" + RES + "_ext_position"),
        ),
        sa.CheckConstraint(
            "link_status = 'UNRESOLVED' OR external_position IS NOT NULL",
            name=op.f("ck_" + RES + "_trusted_position"),
        ),
        sa.CheckConstraint(
            "link_status <> 'VERIFIED' OR external_author_orcid IS NOT NULL",
            name=op.f("ck_" + RES + "_verified_orcid"),
        ),
        sa.CheckConstraint(
            "external_author_orcid IS NULL OR "
            "external_author_orcid ~ '^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$'",
            name=op.f("ck_" + RES + "_orcid_format"),
        ),
        sa.CheckConstraint(
            "link_status = 'UNRESOLVED' OR retrieved_at IS NOT NULL",
            name=op.f("ck_" + RES + "_retrieved_at"),
        ),
    )
    op.create_index("ix_paar_publication_author", RES, ["publication_author_id"])
    op.create_index("ix_paar_source_status", RES, ["source_system", "link_status"])

    op.create_table(
        AFF,
        sa.Column("id", UUID, primary_key=True, server_default=GEN_RANDOM_UUID),
        sa.Column("resolution_id", UUID, nullable=False),
        sa.Column("link_status", sa.String(20), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("raw_index", sa.Integer(), nullable=True),
        sa.Column("raw_affiliation_text", sa.Text(), nullable=True),
        sa.Column("organization_id", UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_" + AFF)),
        sa.ForeignKeyConstraint(
            ["resolution_id", "link_status"],
            [RES + ".id", RES + ".link_status"],
            name="fk_paa_resolution_link_status",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_paa_organization_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("resolution_id", "ord", name="uq_paa_resolution_ord"),
        sa.CheckConstraint(
            "link_status IN ('VERIFIED', 'CORROBORATED')", name=op.f("ck_" + AFF + "_link_status")
        ),
        sa.CheckConstraint("ord >= 1", name=op.f("ck_" + AFF + "_ord")),
        sa.CheckConstraint(
            "raw_affiliation_text IS NOT NULL OR organization_id IS NOT NULL",
            name=op.f("ck_" + AFF + "_content"),
        ),
        sa.CheckConstraint(
            "(raw_index IS NULL) = (raw_affiliation_text IS NULL) AND "
            "(raw_index IS NULL OR raw_index >= 1) AND "
            "(raw_affiliation_text IS NULL OR btrim(raw_affiliation_text) <> '')",
            name=op.f("ck_" + AFF + "_raw_text"),
        ),
    )
    op.create_index("ix_paa_organization_id", AFF, ["organization_id"])


def downgrade() -> None:
    op.drop_table(AFF)
    op.drop_table(RES)
    op.drop_table("organizations")
