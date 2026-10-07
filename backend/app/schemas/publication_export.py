"""Typed export schemas for the canonical publication export API — A4."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class PublicationExportAuthor(BaseModel):
    author_order: int
    scopus_id: str
    preferred_name: str


class PublicationExportLecturerLink(BaseModel):
    author_order: int
    scopus_id: str
    full_name: str
    staff_code: str | None
    department: str | None
    faculty: str | None
    orcid: str | None


class PublicationExportItem(BaseModel):
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
    authors: list[PublicationExportAuthor]
    approved_lecturer_links: list[PublicationExportLecturerLink]


class PublicationExportDataset(BaseModel):
    name: str
    schema_version: str
    export_id: UUID
    exported_at: str
    record_count: int
    filters_applied: dict[str, Any]
    source: str


class PublicationExportResponse(BaseModel):
    dataset: PublicationExportDataset
    publications: list[PublicationExportItem]
