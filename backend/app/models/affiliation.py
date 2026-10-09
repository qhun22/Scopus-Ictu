"""Author-level affiliation resolutions (Task 11, additive).

Three tables, none of which alters an existing table:

``organizations``
    Organizations *as asserted by one external source* (e.g. an OpenAlex
    institution).  Never merged across sources and never merged by name
    similarity; ROR / source id are attributes, not merge keys.

``publication_author_affiliation_resolutions``
    One row per (publication author position, source system, source payload
    version).  It records the *outcome of reconciling* the external author
    list with the Scopus author at that position - including outcomes where
    the source has no affiliation (``affiliation_presence = 'ABSENT'``) and
    outcomes that could not be reconciled (``UNRESOLVED`` + reason).  So
    "the source lists no unit" and "we could not reconcile" are different
    rows, and "never attempted" is the absence of rows.

``publication_author_affiliations``
    The affiliation rows of a VERIFIED / CORROBORATED resolution.  A
    composite FK ``(resolution_id, link_status)`` plus a CHECK on
    ``link_status`` makes it impossible, at database level, to attach an
    affiliation to an UNRESOLVED resolution.

Affiliation text is the *external source's* statement about the author on
that paper.  It is neither Scopus's own assertion, nor the repository's
publication-level "Đơn vị", nor a lecturer's current unit.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

LINK_STATUSES = ("VERIFIED", "CORROBORATED", "UNRESOLVED")
LINK_METHODS = {
    "VERIFIED": "ORCID_SCOPUS_ID_BRIDGE",
    "CORROBORATED": "POSITION_COUNT_NAME",
}


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_org_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ror: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("btrim(source_system) <> ''", name="source_system"),
        CheckConstraint("btrim(display_name) <> ''", name="display_name"),
        CheckConstraint(
            "source_org_id IS NULL OR btrim(source_org_id) <> ''", name="source_org_id"
        ),
        CheckConstraint(
            "country_code IS NULL OR country_code ~ '^[A-Z]{2}$'", name="country_code"
        ),
        # Identity of an organization is (source, source id); ROR is only an attribute.
        Index(
            "uq_organizations_source_org",
            "source_system",
            "source_org_id",
            unique=True,
            postgresql_where=text("source_org_id IS NOT NULL"),
        ),
        # Id-less organizations: only an exact (same source, same string) repeat is the same row.
        Index(
            "uq_organizations_source_name",
            "source_system",
            "display_name",
            unique=True,
            postgresql_where=text("source_org_id IS NULL"),
        ),
        Index("ix_organizations_ror", "ror"),
    )


class PublicationAuthorAffiliationResolution(Base):
    __tablename__ = "publication_author_affiliation_resolutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    publication_author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "publication_authors.id",
            ondelete="CASCADE",
            name="fk_paar_publication_author_id",
        ),
        nullable=False,
    )
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    # Idempotency / data version: SHA-256 of the canonical source payload used.
    source_payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    link_status: Mapped[str] = mapped_column(String(20), nullable=False)
    link_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    unresolved_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # PRESENT / ABSENT for trusted links, NULL (unknown) for UNRESOLVED.
    affiliation_presence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    source_doi: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_work_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_author_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_author_orcid: Mapped[str | None] = mapped_column(String(19), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    importer_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("id", "link_status", name="uq_paar_id_link_status"),
        UniqueConstraint(
            "publication_author_id",
            "source_system",
            "source_payload_sha256",
            name="uq_paar_author_source_payload",
        ),
        CheckConstraint("btrim(source_system) <> ''", name="source_system"),
        CheckConstraint("source_payload_sha256 ~ '^[0-9a-f]{64}$'", name="payload_hash"),
        CheckConstraint(
            "link_status IN ('VERIFIED', 'CORROBORATED', 'UNRESOLVED')", name="link_status"
        ),
        CheckConstraint(
            "(link_status = 'VERIFIED' AND link_method IS NOT NULL "
            "AND link_method = 'ORCID_SCOPUS_ID_BRIDGE') OR "
            "(link_status = 'CORROBORATED' AND link_method IS NOT NULL "
            "AND link_method = 'POSITION_COUNT_NAME') OR "
            "(link_status = 'UNRESOLVED' AND link_method IS NULL)",
            name="link_method",
        ),
        CheckConstraint(
            "(link_status = 'UNRESOLVED') = (unresolved_reason IS NOT NULL) AND "
            "(unresolved_reason IS NULL OR btrim(unresolved_reason) <> '')",
            name="reason",
        ),
        CheckConstraint(
            "(link_status = 'UNRESOLVED' AND affiliation_presence IS NULL) OR "
            "(link_status <> 'UNRESOLVED' AND affiliation_presence IS NOT NULL "
            "AND affiliation_presence IN ('PRESENT', 'ABSENT'))",
            name="presence",
        ),
        CheckConstraint("jsonb_typeof(evidence) = 'object'", name="evidence_object"),
        CheckConstraint("external_position IS NULL OR external_position >= 1", name="ext_position"),
        CheckConstraint(
            "link_status = 'UNRESOLVED' OR external_position IS NOT NULL", name="trusted_position"
        ),
        CheckConstraint(
            "link_status <> 'VERIFIED' OR external_author_orcid IS NOT NULL", name="verified_orcid"
        ),
        CheckConstraint(
            "external_author_orcid IS NULL OR "
            "external_author_orcid ~ '^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$'",
            name="orcid_format",
        ),
        CheckConstraint(
            "link_status = 'UNRESOLVED' OR retrieved_at IS NOT NULL", name="retrieved_at"
        ),
        Index("ix_paar_publication_author", "publication_author_id"),
        Index("ix_paar_source_status", "source_system", "link_status"),
    )


class PublicationAuthorAffiliation(Base):
    __tablename__ = "publication_author_affiliations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    resolution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    link_status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Position of this row inside ONE resolution (a resolution is source+payload specific).
    ord: Mapped[int] = mapped_column(Integer, nullable=False)
    # Index of the source's raw affiliation string; rows sharing it belong to one raw string.
    raw_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_affiliation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT", name="fk_paa_organization_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["resolution_id", "link_status"],
            [
                "publication_author_affiliation_resolutions.id",
                "publication_author_affiliation_resolutions.link_status",
            ],
            ondelete="CASCADE",
            name="fk_paa_resolution_link_status",
        ),
        UniqueConstraint("resolution_id", "ord", name="uq_paa_resolution_ord"),
        CheckConstraint("link_status IN ('VERIFIED', 'CORROBORATED')", name="link_status"),
        CheckConstraint("ord >= 1", name="ord"),
        CheckConstraint(
            "raw_affiliation_text IS NOT NULL OR organization_id IS NOT NULL", name="content"
        ),
        CheckConstraint(
            "(raw_index IS NULL) = (raw_affiliation_text IS NULL) AND "
            "(raw_index IS NULL OR raw_index >= 1) AND "
            "(raw_affiliation_text IS NULL OR btrim(raw_affiliation_text) <> '')",
            name="raw_text",
        ),
        Index("ix_paa_organization_id", "organization_id"),
    )


__all__ = [
    "LINK_METHODS",
    "LINK_STATUSES",
    "Organization",
    "PublicationAuthorAffiliation",
    "PublicationAuthorAffiliationResolution",
]
