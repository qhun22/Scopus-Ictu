"""Master-data lecturer models — M1.1 (frozen contract).

Tables (M1.0-B):
    1.  lecturers                       (Mutable Aggregate Root, versioned)
    2.  lecturer_source_snapshots       (Append-only, M1C-01 parent candidate key)
    3.  lecturer_known_publications     (Append-only, M1C-01 composite FK child)

This module is a strict 1:1 translation of the M1.0-B contracts and the
M1C-01 / M1C-04 cross-cluster decisions. No schema redesign, no
inferred fields, no invented indexes.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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


# ---------------------------------------------------------------------------
# 1. lecturers — Mutable Aggregate Root, versioned
# ---------------------------------------------------------------------------
class Lecturer(Base):
    """Canonical lecturer master record.

    M1.0-B §1. Optimistic locking per M1.0-A09.
    """

    __tablename__ = "lecturers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    staff_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    academic_rank: Mapped[str | None] = mapped_column(String(50), nullable=True)
    academic_degree: Mapped[str | None] = mapped_column(String(50), nullable=True)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    faculty: Mapped[str | None] = mapped_column(String(150), nullable=True)
    repository_profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    repository_profile_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    orcid: Mapped[str | None] = mapped_column(String(19), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("TRUE")
    )
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
        # CHECK (version >= 1) — FC-01: ck_lecturers_version
        CheckConstraint("version >= 1", name="version"),
        # CHECK (orcid IS NULL OR orcid ~ '^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$')
        # FC-01: ck_lecturers_orcid_format
        CheckConstraint(
            "orcid IS NULL OR orcid ~ '^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$'",
            name="orcid_format",
        ),
        # Partial unique indexes — explicit names (not auto-template).
        Index(
            "uq_lecturers_staff_code",
            "staff_code",
            unique=True,
            postgresql_where=text("staff_code IS NOT NULL"),
        ),
        Index(
            "uq_lecturers_email_ci",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index(
            "uq_lecturers_orcid",
            "orcid",
            unique=True,
            postgresql_where=text("orcid IS NOT NULL"),
        ),
        Index("ix_lecturers_full_name_normalized", "full_name_normalized"),
    )

    __mapper_args__ = {"version_id_col": version}


# ---------------------------------------------------------------------------
# 2. lecturer_source_snapshots — Append-only, M1C-01 parent candidate key
# ---------------------------------------------------------------------------
class LecturerSourceSnapshot(Base):
    """Per-source snapshot of a lecturer (provenance).

    M1.0-B §2. Append-only per M1.0-A08 (no updated_at). The composite
    candidate key (id, lecturer_id) referenced by the composite FK on
    ``lecturer_known_publications`` is implemented as a table-level
    UNIQUE constraint — M1C-01.
    """

    __tablename__ = "lecturer_source_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    lecturer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Single-column FK to lecturers(id) ON DELETE RESTRICT.
    # M1.0-A10 default ON DELETE RESTRICT.
    __table_args__ = (
        # CHECK (validation_status IN ('VALID','INVALID')) — M1C-03.
        # FC-01: ck_lecturer_source_snapshots_validation_status
        CheckConstraint(
            "validation_status IN ('VALID', 'INVALID')",
            name="validation_status",
        ),
        # CHECK (snapshot_hash ~ '^[0-9a-f]{64}$') — M1C-04.
        # FC-01: ck_lecturer_source_snapshots_snapshot_hash
        CheckConstraint("snapshot_hash ~ '^[0-9a-f]{64}$'", name="snapshot_hash"),
        # CHECK (jsonb_typeof(raw_payload) = 'object') — M1.0-A12.
        # FC-01: ck_lecturer_source_snapshots_raw_payload_object
        CheckConstraint(
            "jsonb_typeof(raw_payload) = 'object'", name="raw_payload_object"
        ),
        # CHECK (validation_errors IS NULL OR jsonb_typeof(validation_errors) = 'array')
        # FC-02: ck_lecturer_source_snapshots_validation_errors_array
        CheckConstraint(
            "validation_errors IS NULL OR jsonb_typeof(validation_errors) = 'array'",
            name="validation_errors_array",
        ),
        # M1C-01 parent candidate key — explicit name (not auto-template).
        UniqueConstraint(
            "id",
            "lecturer_id",
            name="uq_lecturer_source_snapshots_id_lecturer",
        ),
        # Single-column FK declared as table-level because the composite
        # FK on the child table references (id, lecturer_id) and we want
        # lecturer_id to be a real column with its own FK semantics.
        ForeignKeyConstraint(
            ["lecturer_id"],
            ["lecturers.id"],
            name="fk_lecturer_source_snapshots_lecturer_id_lecturers",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_lecturer_source_snapshots_lecturer_id", "lecturer_id"
        ),
        Index(
            "ix_snapshots_source_lookup",
            "source_system",
            "source_url",
            "fetched_at",
        ),
    )


# ---------------------------------------------------------------------------
# 3. lecturer_known_publications — Append-only, M1C-01 composite FK child
# ---------------------------------------------------------------------------
class LecturerKnownPublication(Base):
    """Known publication attribution per lecturer per snapshot.

    M1.0-B §3. The composite FK (snapshot_id, lecturer_id) ->
    lecturer_source_snapshots(id, lecturer_id) enforces the
    cross-lecturer integrity invariant defined in M1C-01. The
    independent query-path index ix_lecturer_known_publications_lecturer_id
    remains because PostgreSQL does not auto-create child-side indexes
    for composite FKs (M1C-01 PostgreSQL indexing rule).
    """

    __tablename__ = "lecturer_known_publications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    lecturer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    title_raw: Mapped[str] = mapped_column(Text, nullable=False)
    title_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    doi_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doi_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_title_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # CHECK (published_year IS NULL OR published_year BETWEEN 1000 AND 9999)
        # FC-01: ck_lecturer_known_publications_published_year
        CheckConstraint(
            "published_year IS NULL OR published_year BETWEEN 1000 AND 9999",
            name="published_year",
        ),
        # M1C-01 composite FK. Explicit name.
        ForeignKeyConstraint(
            ["snapshot_id", "lecturer_id"],
            ["lecturer_source_snapshots.id", "lecturer_source_snapshots.lecturer_id"],
            name="fk_lecturer_known_publications_snapshot_lecturer",
            ondelete="RESTRICT",
        ),
        # M1C-01 dedicated child-side index on lecturer_id (independent
        # of the composite FK). FKs do not auto-create child indexes.
        Index(
            "ix_lecturer_known_publications_lecturer_id", "lecturer_id"
        ),
        Index(
            "ix_lecturer_known_publications_snapshot_id", "snapshot_id"
        ),
        Index(
            "ix_known_pubs_lecturer_year",
            "lecturer_id",
            "published_year",
        ),
        Index(
            "ix_lecturer_known_publications_doi",
            "doi_normalized",
            postgresql_where=text("doi_normalized IS NOT NULL"),
        ),
    )
