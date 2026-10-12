"""Online affiliation enrichment job (Priority 1, additive).

A background job the ADMIN starts to fetch public OpenAlex/Crossref/ORCID
metadata for the DOIs of publications already imported from Scopus CSV, and
write it as a bundle on disk in the exact shape ``affiliation_sources.py``
already reads (``openalex_works.jsonl``, ``crossref_works.jsonl``,
``orcid_external_ids.json``).  Nothing here writes to
``publication_author_affiliation*`` tables directly — the existing
preview/apply workflow (``affiliation_workflow.py``) does that, pointed at
the job's own bundle directory instead of the fixed offline one.

One row per job; progress is derived from ``processed_dois``/``total_dois``
(no derived timestamp columns, same pattern as ``ScopusImport``).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

AFFILIATION_ENRICHMENT_STATUSES = ("RECEIVED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")
AFFILIATION_ENRICHMENT_ACTIVE_STATUSES = ("RECEIVED", "RUNNING")


class AffiliationEnrichmentJob(Base):
    """Header + progress + result summary of one online enrichment run."""

    __tablename__ = "affiliation_enrichment_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'RECEIVED'"))
    total_dois: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    processed_dois: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    openalex_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    crossref_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    orcid_fetched: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    bundle_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_summary: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint(
            "total_dois >= 0 AND processed_dois >= 0 AND processed_dois <= total_dois",
            name="progress_counts",
        ),
        CheckConstraint(
            "status IN ('RECEIVED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name="status",
        ),
        CheckConstraint(
            "error_summary IS NULL OR jsonb_typeof(error_summary) = 'object'",
            name="error_summary_object",
        ),
        Index("ix_affiliation_enrichment_jobs_status", "status"),
        Index("ix_affiliation_enrichment_jobs_requested_by", "requested_by_user_id"),
    )

    __mapper_args__ = {"version_id_col": version}


__all__ = [
    "AFFILIATION_ENRICHMENT_ACTIVE_STATUSES",
    "AFFILIATION_ENRICHMENT_STATUSES",
    "AffiliationEnrichmentJob",
]
