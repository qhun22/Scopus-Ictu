"""Typed export schemas for the canonical publication export API — A4.

schema_version 1.1 (week 7) only ADDS fields to 1.0: ``author_count`` per publication and
``affiliation_status`` / ``gap_reason`` / ``affiliations`` per author.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.affiliation_override_api import OverrideRead

EXPORT_SCHEMA_VERSION = "1.1"


class PublicationExportOrganization(BaseModel):
    name: str
    country: str | None = None


class PublicationExportAffiliation(BaseModel):
    """One unit of one author on one publication, with its own confidence and source."""

    text: str | None
    organizations: list[PublicationExportOrganization] = Field(default_factory=list)
    # VERIFIED / CORROBORATED: the external source's statement, labelled by how sure the
    # author-to-source link is. MANUAL_REVIEW: typed by an ADMIN, never counted as verified.
    confidence: str
    source: str  # openalex | crossref | admin
    evidence_url: str | None


class PublicationExportAuthor(BaseModel):
    author_order: int
    scopus_id: str
    preferred_name: str
    affiliation_status: str = "NOT_RECONCILED"
    # Set exactly when ``affiliations`` is empty.
    gap_reason: str | None = None
    affiliations: list[PublicationExportAffiliation] = Field(default_factory=list)


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
    author_count: int = 0
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


# ----------------------------------------------------------------------------- gaps list
class SourceOutcomeRead(BaseModel):
    source: str
    link_status: str
    reason: str | None


class AffiliationGapItem(BaseModel):
    # Internal id so the UI can reach the override form; deliberately NOT part of the export file.
    publication_author_id: UUID
    eid: str
    doi: str | None
    title: str
    year: int | None
    author_count: int
    author_order: int
    scopus_id: str
    author_name: str
    affiliation_status: str
    reason: str
    by_source: list[SourceOutcomeRead]
    admin_reviewed: bool
    ictu_lecturer: str | None
    # Every override of the position, ACTIVE and REVOKED, newest first. JSON only.
    overrides: list[OverrideRead] = Field(default_factory=list)


class AffiliationGapSummary(BaseModel):
    total_positions: int
    total_gaps: int
    publications_with_gaps: int
    by_reason: dict[str, int]


class AffiliationGapListResponse(BaseModel):
    items: list[AffiliationGapItem]
    total: int
    page: int
    page_size: int
    summary: AffiliationGapSummary
