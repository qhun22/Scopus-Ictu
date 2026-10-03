"""Public API contracts for raw Scopus CSV imports."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    version: int = 1
    created_at: datetime
    updated_at: datetime
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float
    is_terminal: bool
    performed_by: str | None = None
    can_delete: bool = False
    scopus_summary: dict | None = None
    lecturer_summary: dict | None = None


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
    import_id: uuid.UUID
    current_stage: str
    progress_pct: int = 0
    errors: list[str] = Field(default_factory=list)


__all__ = [
    "ImportStatus",
    "ImportStatusResponse",
    "ScopusImportBase",
    "ScopusImportCreate",
    "ImportType",
    "ScopusImportConfigResponse",
    "ScopusImportListResponse",
    "ScopusImportResponse",
    "UnifiedImportStats",
]
