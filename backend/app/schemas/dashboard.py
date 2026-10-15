"""Safe read-only DTOs for the dashboard summary API — C2-A4."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.audit import AuditListItem

IdentityStatus = Literal["CANDIDATE", "APPROVED", "REJECTED", "REVOKED"]

ScopusImportStatus = Literal[
    "RECEIVED",
    "PARSING",
    "VALIDATED",
    "STAGED",
    "APPLIED",
    "FAILED",
    "CANCELLED",
]


class LatestScopusImportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_name: str
    status: ScopusImportStatus
    total_records: int
    valid_records: int
    invalid_records: int
    created_at: datetime
    updated_at: datetime


class DashboardSummaryResponse(BaseModel):
    total_publications: int
    total_lecturers: int
    active_lecturers: int
    total_scopus_authors: int

    identity_counts: dict[IdentityStatus, int]

    pending_review_count: int

    latest_scopus_import: LatestScopusImportSummary | None

    recent_audit_actions: list[AuditListItem]


class PublicationsByYearItem(BaseModel):
    year: int
    count: int


class PublicationsByDocumentTypeItem(BaseModel):
    document_type: str
    count: int


class AffiliationCoverageResponse(BaseModel):
    """Coverage of author *positions* (publication_authors rows), not of
    unique Scopus authors — one position counts once even if it has
    affiliation resolutions from multiple source systems."""

    total_author_positions: int
    positions_with_affiliation: int
    positions_without_affiliation: int
    # Best (most-trusted) resolution status actually observed per position,
    # restricted to positions that have at least one resolution row.
    by_link_status: dict[str, int]


class DashboardChartsResponse(BaseModel):
    publications_total_with_year: int
    publications_total_without_year: int
    publications_by_year: list[PublicationsByYearItem]
    publications_by_document_type: list[PublicationsByDocumentTypeItem]
    affiliation_coverage: AffiliationCoverageResponse
