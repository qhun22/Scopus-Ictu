"""Public API contracts for raw Scopus CSV imports."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


NormalizationSummary = Literal[
    "canonical_new",
    "canonical_existing",
    "canonical_metadata_changed",
    "canonical_failed",
    "canonical_processed",
    "canonical_intra_duplicate",
]


class NormalizationData(BaseModel):
    """Normalization counters for a completed Scopus import (M2.6A)."""

    status: Literal["NORMALIZING", "COMPLETED", "CANCELLED", "FAILED"] = "COMPLETED"
    total_records: int = 0
    progress_percent: int = Field(default=0, ge=0, le=100)
    canonical_new: int = 0
    canonical_existing: int = 0
    canonical_metadata_changed: int = 0
    canonical_failed: int = 0
    canonical_processed: int = 0
    canonical_intra_duplicate: int = 0

ImportStatus = Literal[
    "RECEIVED",
    "PARSING",
    "VALIDATED",
    "STAGED",
    "APPLIED",
    "FAILED",
    "CANCELLED",
    "IMPORTED",
]

ImportType = Literal["SCOPUS", "LECTURERS"]


class ScopusImportBase(BaseModel):
    pass


class ScopusImportCreate(ScopusImportBase):
    pass


class ScopusImportResponse(BaseModel):
    id: uuid.UUID
    type: ImportType = "SCOPUS"
    file_name: str
    status: str
    total_records: int
    imported_records: int
    failed_records: int
    processed_records: int
    progress_percent: int = Field(ge=0, le=100)
    duplicate_candidates: int = 0
    row_errors: list[dict] = Field(default_factory=list)
    error_summary: dict | None = None
    normalization: NormalizationData | None = None
    version: int = 1
    created_at: datetime
    updated_at: datetime
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float
    is_terminal: bool
    performed_by: str | None = None
    # Legacy alias kept for backwards compatibility; computed from `usage`.
    # For Scopus imports: `can_delete = is_terminal AND NOT in_use`.
    # For lecturer imports: `can_delete` is unrelated to usage.
    can_delete: bool = False
    # New M2.6A follow-up fields:
    in_use: bool = False
    archived: bool = False
    usage: dict = Field(default_factory=lambda: {
        "publication_source_links": 0,
        "author_variant_links": 0,
    })
    scopus_summary: dict | None = None
    lecturer_summary: dict | None = None
    # M2.6B: nested author normalization counters
    normalization_summary: dict | None = None


class UnifiedImportStats(BaseModel):
    total_imports: int
    success_count: int
    processing_count: int
    failed_count: int


class ScopusImportListResponse(BaseModel):
    items: list[ScopusImportResponse]
    stats: UnifiedImportStats | None = None


class ScopusImportConfigResponse(BaseModel):
    supported_extensions: list[str] = Field(default_factory=lambda: [".csv"])
    max_bytes: int


class ImportStatusResponse(BaseModel):
    current_stage: str
    progress_pct: int = 0
    errors: list[str] = Field(default_factory=list)


class NormalizationResponse(BaseModel):
    """Response returned after normalizing a Scopus import."""

    import_id: uuid.UUID
    canonical_new: int
    canonical_existing: int
    canonical_metadata_changed: int
    canonical_failed: int
    canonical_processed: int
    canonical_intra_duplicate: int


__all__ = [
    "ImportStatus",
    "ImportStatusResponse",
    "ImportType",
    "NormalizationData",
    "NormalizationResponse",
    "ScopusImportConfigResponse",
    "ScopusImportBase",
    "ScopusImportCreate",
    "ScopusImportListResponse",
    "ScopusImportResponse",
    "UnifiedImportStats",
]
