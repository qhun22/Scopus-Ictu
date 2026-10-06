"""Read-only DTOs for the proposed M2.8 lecturer Scopus projection."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LecturerProfileRead(BaseModel):
    lecturer_id: uuid.UUID
    full_name: str
    staff_code: str | None = None
    email: str | None = None
    academic_rank: str | None = None
    academic_degree: str | None = None
    position: str | None = None
    department: str | None = None
    faculty: str | None = None
    repository_profile_url: str | None = None
    orcid: str | None = None


class IdentityEvidenceSummaryRead(BaseModel):
    evidence_type: str
    direction: str
    created_at: datetime


class ApprovedIdentitySummaryRead(BaseModel):
    identity_id: uuid.UUID
    status: str
    scopus_author_id: uuid.UUID
    scopus_id: str
    preferred_name: str
    name_variants: list[str] = Field(default_factory=list)
    evidence: list[IdentityEvidenceSummaryRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class LecturerPublicationRead(BaseModel):
    publication_id: uuid.UUID
    eid: str
    doi: str | None = None
    title: str
    source_title: str | None = None
    year: int | None = None
    cited_by_count: int | None = None
    document_type: str | None = None
    publication_stage: str | None = None
    open_access_status: str | None = None
    linked_author_orders: list[int] = Field(default_factory=list)


class PaginatedLecturerPublicationsRead(BaseModel):
    items: list[LecturerPublicationRead] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class LecturerPublicationAggregatesRead(BaseModel):
    total_publications: int = 0
    publication_count_by_year: dict[int, int] = Field(default_factory=dict)
    unknown_year_count: int = 0
    known_citation_sum: int = 0
    citation_unknown_publication_count: int = 0
    approved_identity_count: int = 0
