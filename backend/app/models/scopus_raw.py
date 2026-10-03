"""Raw Scopus ingestion models — M1.1 (frozen contract).

Tables (M1.0-B):
    4.  scopus_imports       (Mutable Workflow Aggregate Root, versioned)
    5.  raw_scopus_records   (Append-only)

This module is a strict 1:1 translation of the M1.0-B contracts and the
M1C-02 / M1C-03 / M1C-04 cross-cluster decisions.

Note on M1.0-A14: ``raw_scopus_records.eid_raw`` is explicitly **not**
unique at the table level. The contract intentionally does not declare
a UQ or unique index on this column.
"""

from __future__ import annotations

import uuid
from datetime import datetime

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


# ---------------------------------------------------------------------------
# 4. scopus_imports — Mutable Workflow Aggregate Root, versioned
# ---------------------------------------------------------------------------
class ScopusImport(Base):
    """Header for a single Scopus CSV import batch.

    M1.0-B §4. Optimistic locking per M1.0-A09. Status vocabulary per
    M1C-02 (7 literals; PROCESSING forbidden).
    """

    __tablename__ = "scopus_imports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    total_records: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    valid_records: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    invalid_records: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'RECEIVED'"),
    )
    error_summary: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
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
        # CHECK (version >= 1) — FC-01: ck_scopus_imports_version
        CheckConstraint("version >= 1", name="version"),
        # CHECK (total_records >= 0 AND valid_records >= 0
        #        AND invalid_records >= 0) — FC-01: ck_scopus_imports_record_counts
        CheckConstraint(
            "total_records >= 0 AND valid_records >= 0 AND invalid_records >= 0",
            name="record_counts",
        ),
        # CHECK (file_sha256 ~ '^[0-9a-f]{64}$') — M1C-04.
        # FC-01: ck_scopus_imports_file_sha256
        CheckConstraint("file_sha256 ~ '^[0-9a-f]{64}$'", name="file_sha256"),
        # CHECK (status IN (... 7 literals ...)) — M1C-02.
        # FC-01: ck_scopus_imports_status
        CheckConstraint(
            "status IN ('RECEIVED', 'PARSING', 'VALIDATED', 'STAGED', "
            "'APPLIED', 'FAILED', 'CANCELLED')",
            name="status",
        ),
        # CHECK (error_summary IS NULL OR jsonb_typeof(error_summary) = 'object')
        # FC-02: ck_scopus_imports_error_summary_object
        CheckConstraint(
            "error_summary IS NULL OR jsonb_typeof(error_summary) = 'object'",
            name="error_summary_object",
        ),
        Index("ix_scopus_imports_file_sha256", "file_sha256"),
        Index("ix_scopus_imports_status", "status"),
    )

    __mapper_args__ = {"version_id_col": version}


# ---------------------------------------------------------------------------
# 5. raw_scopus_records — Append-only
# ---------------------------------------------------------------------------
class RawScopusRecord(Base):
    """One raw Scopus row from a CSV import.

    M1.0-B §5. Append-only per M1.0-A08 (no updated_at). The 22 raw
    Scopus values are stored verbatim inside ``raw_payload``; ``row_hash``
    is the SHA-256 over their canonical JSON-array representation per
    M1C-04.
    """

    __tablename__ = "raw_scopus_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scopus_imports.id", ondelete="RESTRICT"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    eid_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_errors: Mapped[list | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # CHECK (row_number >= 1) — FC-01: ck_raw_scopus_records_row_number
        CheckConstraint("row_number >= 1", name="row_number"),
        # CHECK (validation_status IN ('VALID','INVALID')) — M1C-03.
        # FC-01: ck_raw_scopus_records_validation_status
        CheckConstraint(
            "validation_status IN ('VALID', 'INVALID')",
            name="validation_status",
        ),
        # CHECK (row_hash ~ '^[0-9a-f]{64}$') — M1C-04.
        # FC-01: ck_raw_scopus_records_row_hash
        CheckConstraint("row_hash ~ '^[0-9a-f]{64}$'", name="row_hash"),
        # CHECK (jsonb_typeof(raw_payload) = 'object') — M1.0-A12.
        # FC-01: ck_raw_scopus_records_raw_payload_object
        CheckConstraint(
            "jsonb_typeof(raw_payload) = 'object'", name="raw_payload_object"
        ),
        # CHECK (validation_errors IS NULL OR jsonb_typeof(validation_errors) = 'array')
        # FC-02: ck_raw_scopus_records_validation_errors_array
        CheckConstraint(
            "validation_errors IS NULL OR jsonb_typeof(validation_errors) = 'array'",
            name="validation_errors_array",
        ),
        # C3-04: import_id FK already declared inline above (RESTRICT).
        # Composite uniqueness of (import_id, row_number) per M1.0-B §5.
        UniqueConstraint(
            "import_id",
            "row_number",
            name="uq_raw_scopus_records_import_row",
        ),
        # M1.0-A14: eid_raw is explicitly NOT unique. Partial indexes only.
        Index(
            "ix_raw_scopus_records_eid_raw",
            "eid_raw",
            postgresql_where=text("eid_raw IS NOT NULL"),
        ),
        Index(
            "ix_raw_scopus_records_doi_raw",
            "doi_raw",
            postgresql_where=text("doi_raw IS NOT NULL"),
        ),
    )
