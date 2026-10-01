"""Canonical publication & author models — M1.1 (frozen contract).

Tables (M1.0-B):
    6.  publications                   (Mutable Canonical Root, versioned)
    7.  publication_raw_sources        (Provenance Association)
    8.  scopus_authors                 (Mutable Derived Canonical Entity)
    9.  scopus_author_name_variants    (Additive Provenance Child)
    10. publication_authors            (Derived Canonical Association)

This module is a strict 1:1 translation of the M1.0-B contracts. The
canonical external identity is EID on ``publications`` (M1.0-A13).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
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


# ---------------------------------------------------------------------------
# 6. publications — Mutable Canonical Root, versioned
# ---------------------------------------------------------------------------
class Publication(Base):
    """Canonical publication (Scopus).

    M1.0-B §6. EID is the canonical external identity (M1.0-A13,
    ADR-001). Optimistic locking per M1.0-A09. ``cited_by_count`` is
    nullable and a NULL is semantically distinct from 0 (C3-03).
    """

    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    eid: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        # M1.0-A13: eid must be UNIQUE at the table level. Declared
        # explicitly so the physical name is uq_publications_eid and
        # the constraint is obvious to a reader.
        unique=True,
    )
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume: Mapped[str | None] = mapped_column(Text, nullable=True)
    issue: Mapped[str | None] = mapped_column(Text, nullable=True)
    art_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_start: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_end: Mapped[str | None] = mapped_column(Text, nullable=True)
    cited_by_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    publication_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    open_access_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # CHECK (btrim(eid) <> '') — FC-01: ck_publications_eid_not_empty
        CheckConstraint("btrim(eid) <> ''", name="eid_not_empty"),
        # CHECK (version >= 1) — FC-01: ck_publications_version
        CheckConstraint("version >= 1", name="version"),
        # CHECK (year IS NULL OR year BETWEEN 1000 AND 9999)
        # FC-01: ck_publications_year_range
        CheckConstraint(
            "year IS NULL OR year BETWEEN 1000 AND 9999", name="year_range"
        ),
        # CHECK (cited_by_count IS NULL OR cited_by_count >= 0) — C3-03.
        # FC-01: ck_publications_cited_by_count
        CheckConstraint(
            "cited_by_count IS NULL OR cited_by_count >= 0",
            name="cited_by_count",
        ),
        # C3-02: partial index on doi (NOT unique).
        Index("ix_publications_doi", "doi", postgresql_where=text("doi IS NOT NULL")),
        Index("ix_publications_year", "year"),
    )

    __mapper_args__ = {"version_id_col": version}


# ---------------------------------------------------------------------------
# 7. publication_raw_sources — Provenance Association
# ---------------------------------------------------------------------------
class PublicationRawSource(Base):
    """Provenance join: canonical publication ↔ raw Scopus row.

    M1.0-B §7. C3-05 enforces one canonical publication per raw record.
    The two FKs are declared as inline ForeignKey so the physical
    constraint names are produced by the naming-convention template.
    """

    __tablename__ = "publication_raw_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    raw_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_scopus_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # C3-05: one raw record maps to at most one canonical publication.
        UniqueConstraint(
            "raw_record_id", name="uq_publication_raw_sources_raw_record_id"
        ),
        Index(
            "ix_publication_raw_sources_publication_id", "publication_id"
        ),
        # publication_raw_sources has no CHECK constraints (FC-01 NONE).
    )


# ---------------------------------------------------------------------------
# 8. scopus_authors — Mutable Derived Canonical Entity
# ---------------------------------------------------------------------------
class ScopusAuthor(Base):
    """Scopus author record (canonical).

    M1.0-B §8. scopus_id is the external identifier (C3-06, unique).
    """

    __tablename__ = "scopus_authors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    scopus_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    preferred_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # CHECK (btrim(scopus_id) <> '') — FC-01: ck_scopus_authors_scopus_id_not_empty
        CheckConstraint("btrim(scopus_id) <> ''", name="scopus_id_not_empty"),
    )


# ---------------------------------------------------------------------------
# 9. scopus_author_name_variants — Additive Provenance Child
# ---------------------------------------------------------------------------
class ScopusAuthorNameVariant(Base):
    """All known name variants for a Scopus author.

    M1.0-B §9. variant_type vocabulary per M1C-03.
    """

    __tablename__ = "scopus_author_name_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    scopus_author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scopus_authors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    variant_type: Mapped[str] = mapped_column(String(30), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name_normalized: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    first_seen_raw_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_scopus_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # CHECK (variant_type IN ('AUTHOR_DISPLAY','AUTHOR_FULL_NAME')) — M1C-03.
        # FC-01: ck_scopus_author_name_variants_variant_type
        CheckConstraint(
            "variant_type IN ('AUTHOR_DISPLAY', 'AUTHOR_FULL_NAME')",
            name="variant_type",
        ),
        UniqueConstraint(
            "scopus_author_id",
            "variant_type",
            "variant_name",
            name="uq_author_name_variants",
        ),
        Index(
            "ix_author_name_variants_normalized", "variant_name_normalized"
        ),
        Index(
            "ix_author_name_variants_raw_source", "first_seen_raw_record_id"
        ),
    )


# ---------------------------------------------------------------------------
# 10. publication_authors — Derived Canonical Association
# ---------------------------------------------------------------------------
class PublicationAuthor(Base):
    """Publication ↔ Scopus author join.

    M1.0-B §10. publication_id -> publications(id) ON DELETE CASCADE
    per M1.0-A11 (composition child). scopus_author_id -> scopus_authors(id)
    ON DELETE RESTRICT per M1.0-A10.
    """

    __tablename__ = "publication_authors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
    )
    scopus_author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scopus_authors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    author_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # CHECK (author_order >= 1) — FC-01: ck_publication_authors_author_order
        CheckConstraint("author_order >= 1", name="author_order"),
        # C3-11: unique (publication_id, author_order)
        UniqueConstraint(
            "publication_id",
            "author_order",
            name="uq_publication_authors_order",
        ),
        # C3-12: unique (publication_id, scopus_author_id)
        UniqueConstraint(
            "publication_id",
            "scopus_author_id",
            name="uq_publication_authors_author",
        ),
        Index(
            "ix_publication_authors_scopus_author_id", "scopus_author_id"
        ),
    )
