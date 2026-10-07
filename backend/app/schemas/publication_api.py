"""Typed read schemas for the canonical publication API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PublicationListItem(BaseModel):
    """Safe, lightweight canonical publication list item."""

    publication_id: UUID
    eid: str
    doi: str | None
    title: str
    source_title: str | None
    year: int | None
    cited_by_count: int | None
    document_type: str | None
    publication_stage: str | None
    open_access_status: str | None


class PublicationListResponse(BaseModel):
    """Server-paginated canonical publication list."""

    items: list[PublicationListItem]
    total: int
    page: int
    page_size: int


class PublicationAuthorRead(BaseModel):
    """Ordered, public-safe Scopus author summary."""

    author_order: int
    scopus_id: str
    preferred_name: str


class PublicationLecturerLinkRead(BaseModel):
    """Approved lecturer link at a concrete publication author position."""

    author_order: int
    scopus_id: str
    full_name: str
    staff_code: str | None
    department: str | None
    faculty: str | None
    orcid: str | None


class PublicationProvenanceRead(BaseModel):
    """Human-readable provenance for one canonical publication source row."""

    file_name: str
    file_sha256: str
    row_number: int
    imported_at: datetime


class PublicationDetailResponse(BaseModel):
    """Canonical publication metadata and safe read-only relationships."""

    publication_id: UUID
    eid: str
    doi: str | None
    title: str
    source_title: str | None
    year: int | None
    volume: str | None
    issue: str | None
    art_no: str | None
    page_start: str | None
    page_end: str | None
    cited_by_count: int | None
    document_type: str | None
    publication_stage: str | None
    open_access_status: str | None
    authors: list[PublicationAuthorRead]
    approved_lecturer_links: list[PublicationLecturerLinkRead]
    provenance: list[PublicationProvenanceRead]
