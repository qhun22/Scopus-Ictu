"""Scopus author schemas — M2.6B."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScopusAuthorBase(BaseModel):
    """Shared fields for ScopusAuthor."""

    model_config = ConfigDict(from_attributes=True)


class ScopusAuthorResponse(ScopusAuthorBase):
    """Response schema for a single Scopus author (M2.6B)."""

    id: UUID
    scopus_id: str
    preferred_name: str
    created_at: datetime
    updated_at: datetime


class ScopusAuthorNameVariantResponse(BaseModel):
    """Response schema for a name variant (M2.6B)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_type: str  # "AUTHOR_DISPLAY" or "AUTHOR_FULL_NAME"
    variant_name: str
    variant_name_normalized: str
    created_at: datetime


class ScopusAuthorDetailResponse(ScopusAuthorResponse):
    """Extended response with name variants."""

    variants: list[ScopusAuthorNameVariantResponse] = Field(default_factory=list)
    publication_count: int = 0


class AuthorListItemResponse(BaseModel):
    """Lightweight list item for author search results."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scopus_id: str
    preferred_name: str
    publication_count: int = 0
    variant_count: int = 0


class AuthorListResponse(BaseModel):
    """Paginated author list response."""

    items: list[AuthorListItemResponse]
    total: int
    page: int
    page_size: int


class NormalizationCountersResponse(BaseModel):
    """Counters from an author normalization run."""

    raw_records_processed: int
    raw_records_failed: int
    author_occurrences: int
    unique_authors_seen: int
    authors_created: int
    authors_existing: int
    publication_author_links_created: int
    publication_author_links_existing: int
    variants_created: int
    variants_existing: int
    conflicts: int


class NormalizationErrorEntry(BaseModel):
    """Structured row-level error from author normalization."""

    row_number: int
    code: str
    message: str


class AuthorNormalizationResponse(BaseModel):
    """Response returned after author normalization (M2.6B)."""

    import_id: UUID
    status: str  # COMPLETED | FAILED | NORMALIZING
    counters: NormalizationCountersResponse
    errors: list[NormalizationErrorEntry] = Field(default_factory=list)
