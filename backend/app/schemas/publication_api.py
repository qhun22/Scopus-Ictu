"""Typed read schemas for the canonical publication API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AffiliationLinkStatus = Literal["VERIFIED", "CORROBORATED", "UNRESOLVED", "NOT_RECONCILED"]


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


class AffiliationOrganizationRead(BaseModel):
    """Organization as normalized by the EXTERNAL source (never merged across sources)."""

    source_system: str
    source_org_id: str | None
    ror: str | None
    display_name: str
    country_code: str | None


class AffiliationProvenanceRead(BaseModel):
    """Safe trace of how an external authorship was tied to this Scopus author."""

    link_method: str
    source_work_id: str | None
    source_doi: str | None
    external_position: int | None
    external_author_name: str | None
    evidence: dict[str, Any] = Field(default_factory=dict)


class AuthorAffiliationRead(BaseModel):
    """One affiliation string (and its source-normalized organizations) of a trusted link.

    ``scope`` is fixed: this is the author's affiliation on THIS publication as
    stated by an external metadata source.  It is not asserted by Scopus, is not
    the repository's publication-level unit, and is not a lecturer's current unit.
    """

    link_status: Literal["VERIFIED", "CORROBORATED"]
    source_system: str
    raw_affiliation_text: str | None
    organizations: list[AffiliationOrganizationRead] = Field(default_factory=list)
    retrieved_at: datetime
    scope: Literal["AUTHOR_ON_PUBLICATION_EXTERNAL_SOURCE"] = "AUTHOR_ON_PUBLICATION_EXTERNAL_SOURCE"
    provenance: AffiliationProvenanceRead


class AffiliationResolutionRead(BaseModel):
    """Outcome of reconciling one external source with this author position."""

    source_system: str
    link_status: Literal["VERIFIED", "CORROBORATED", "UNRESOLVED"]
    link_method: str | None
    unresolved_reason: str | None
    # PRESENT / ABSENT (source lists no unit) for trusted links; null = unknown (UNRESOLVED)
    affiliation_presence: Literal["PRESENT", "ABSENT"] | None
    retrieved_at: datetime | None
    source_work_id: str | None


class PublicationAuthorRead(BaseModel):
    """Ordered, public-safe Scopus author summary."""

    author_order: int
    scopus_id: str
    preferred_name: str
    # Additive affiliation block.  NOT_RECONCILED = no reconciliation was ever run.
    affiliation_status: AffiliationLinkStatus = "NOT_RECONCILED"
    # True: a trusted source lists a unit; False: trusted source lists none; null: unknown.
    source_has_affiliation: bool | None = None
    affiliations: list[AuthorAffiliationRead] = Field(default_factory=list)
    affiliation_resolutions: list[AffiliationResolutionRead] = Field(default_factory=list)


class AffiliationSummaryRead(BaseModel):
    """Counts of author positions by affiliation confidence (mutually exclusive)."""

    authors: int
    verified_with_affiliation: int
    verified_without_affiliation: int
    corroborated_with_affiliation: int
    corroborated_without_affiliation: int
    unresolved: int
    not_reconciled: int
    # Strictest reading: every author VERIFIED and with an affiliation.
    all_authors_verified_with_affiliation: bool
    # Weaker reading: every author VERIFIED or CORROBORATED and with an affiliation.
    all_authors_verified_or_corroborated_with_affiliation: bool
    note: str = (
        "Affiliations are author-level statements of external metadata sources "
        "(OpenAlex/Crossref), not asserted by Scopus. CORROBORATED is not verified."
    )


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
    affiliation_summary: AffiliationSummaryRead | None = None
    approved_lecturer_links: list[PublicationLecturerLinkRead]
    provenance: list[PublicationProvenanceRead]
