"""HTTP schemas for the M2.7B-5 human candidate review API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CandidateStatus = Literal["PENDING", "ACCEPTED", "REJECTED", "SUPERSEDED"]
ReviewAction = Literal["ACCEPT", "REJECT"]
EvidenceCategory = Literal["publication-supported", "name-only"]
AmbiguityFilter = Literal["ambiguous", "unique"]


class ReviewDecisionRequest(BaseModel):
    """Only values the authenticated reviewer is allowed to control."""

    model_config = ConfigDict(extra="forbid")

    observation_id: uuid.UUID
    candidate_version: int = Field(..., ge=1)
    action: ReviewAction
    reason: str | None = Field(default=None, max_length=4000)


class ReviewLecturerSummary(BaseModel):
    id: uuid.UUID
    full_name: str


class ReviewAuthorSummary(BaseModel):
    id: uuid.UUID
    scopus_id: str
    preferred_name: str


class ReviewQueueItem(BaseModel):
    candidate_id: uuid.UUID
    candidate_status: CandidateStatus
    candidate_version: int
    current_observation_id: uuid.UUID
    lecturer: ReviewLecturerSummary
    scopus_author: ReviewAuthorSummary
    name_evidence_count: int
    publication_evidence_count: int
    publication_support_count: int
    candidate_count_for_lecturer: int
    is_ambiguous: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    page: int
    page_size: int


class ReviewObservationResponse(BaseModel):
    observation_id: uuid.UUID
    generation_run_id: uuid.UUID
    generation_run_rule_set_version: str
    observed_at: datetime
    observation_hash: str


class ReviewNameEvidenceResponse(BaseModel):
    evidence_id: uuid.UUID
    evidence_kind: Literal["NAME"]
    rule_id: str
    rule_version: str
    lecturer_source_value: str | None = None
    lecturer_comparison_value: str | None = None
    scopus_surface_type: str | None = None
    scopus_surface_value: str | None = None
    scopus_comparison_value: str | None = None
    source_refs: list[Any] = Field(default_factory=list)
    evidence_fingerprint: str


class ReviewPublicationEvidenceResponse(BaseModel):
    evidence_id: uuid.UUID
    evidence_kind: Literal["PUBLICATION"]
    rule_id: str
    rule_version: str
    reconciliation: Literal["DOI_EXACT", "TITLE_EXACT"] | None = None
    known_publication_id: uuid.UUID | None = None
    lecturer_source_snapshot_id: uuid.UUID | None = None
    canonical_publication_id: uuid.UUID | None = None
    title: str | None = None
    doi: str | None = None
    eid: str | None = None
    candidate_scopus_author_id: uuid.UUID | None = None
    source_refs: list[Any] = Field(default_factory=list)
    evidence_fingerprint: str


class ReviewOtherCandidateSummary(BaseModel):
    candidate_id: uuid.UUID
    candidate_status: CandidateStatus
    candidate_version: int
    scopus_author: ReviewAuthorSummary


class ReviewLecturerDetail(ReviewLecturerSummary):
    repository_profile_url: str | None = None
    academic_degree: str | None = None
    academic_rank: str | None = None


class ReviewAuthorDetail(ReviewAuthorSummary):
    name_variants: list[str] = Field(default_factory=list)


class ReviewAmbiguityContext(BaseModel):
    candidate_count_for_lecturer: int
    is_ambiguous: bool
    other_candidates: list[ReviewOtherCandidateSummary] = Field(default_factory=list)


class ReviewCandidateDetailResponse(BaseModel):
    candidate_id: uuid.UUID
    candidate_status: CandidateStatus
    candidate_version: int
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime
    lecturer: ReviewLecturerDetail
    scopus_author: ReviewAuthorDetail
    current_observation: ReviewObservationResponse
    name_evidence: list[ReviewNameEvidenceResponse] = Field(default_factory=list)
    publication_evidence: list[ReviewPublicationEvidenceResponse] = Field(
        default_factory=list
    )
    ambiguity: ReviewAmbiguityContext


class ReviewDecisionResponse(BaseModel):
    review_id: uuid.UUID
    candidate_id: uuid.UUID
    observation_id: uuid.UUID
    action: ReviewAction
    candidate_status: Literal["ACCEPTED", "REJECTED"]
    candidate_version: int
    resulting_identity_id: uuid.UUID | None = None
    idempotent: bool
