"""Typed read schemas for the Completion-1 A3 global search API.

Every DTO is intentionally lightweight and exposes only the canonical external
identifiers (EID, Scopus ID, staff code). Internal UUID primary keys, raw
provenance, source rows, and contact PII are never projected.
"""

from __future__ import annotations

from pydantic import BaseModel


class LecturerSearchItem(BaseModel):
    """Safe, lightweight lecturer discovery hit."""

    full_name: str
    staff_code: str | None
    department: str | None
    faculty: str | None
    orcid: str | None


class PublicationSearchItem(BaseModel):
    """Safe, lightweight publication discovery hit."""

    eid: str
    title: str
    year: int | None
    source_title: str | None
    cited_by_count: int | None
    document_type: str | None


class ScopusAuthorSearchItem(BaseModel):
    """Safe, lightweight Scopus author discovery hit."""

    scopus_id: str
    preferred_name: str


class SearchResponse(BaseModel):
    """Grouped global search results."""

    q: str
    limit: int
    lecturers: list[LecturerSearchItem]
    publications: list[PublicationSearchItem]
    scopus_authors: list[ScopusAuthorSearchItem]