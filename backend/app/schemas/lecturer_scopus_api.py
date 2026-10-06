"""HTTP response schemas for the M2.8 lecturer Scopus read API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.lecturer_scopus_projection import (
    LecturerPublicationAggregatesRead,
    LecturerPublicationRead,
)


class LecturerPublicationsAPIResponse(BaseModel):
    """One publication page together with full-result aggregates."""

    items: list[LecturerPublicationRead] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    aggregates: LecturerPublicationAggregatesRead


__all__ = ["LecturerPublicationsAPIResponse"]
