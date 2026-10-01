"""Scopus import schemas — M0 scaffold."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScopusImportBase(BaseModel):
    """M0 stub. TODO(M1): filename, uploaded_by, status, row_total, etc."""

    pass


class ScopusImportCreate(ScopusImportBase):
    """M0 stub."""

    pass


class ScopusImportResponse(ScopusImportBase):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uploaded_at: datetime | None = None


class ImportStatusResponse(BaseModel):
    """M0 stub. TODO(M1): import_id, current_stage, progress_pct, errors."""

    import_id: int
    current_stage: str
    progress_pct: int = 0
    errors: list[str] = []