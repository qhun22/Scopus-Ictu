"""HTTP schemas for the M2.7B-5 human candidate review API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class MergeGuideLecturer(BaseModel):
    lecturer_id: uuid.UUID
    scopus_ids: list[str]
    primary_scopus_id: str | None = None


class MergeGuideResponse(BaseModel):
    """The ICTU merge guide restricted to the asked lecturers. A hint only: nothing is decided."""

    available: bool
    source_url: str | None = None
    retrieved_at: str | None = None
    items: list[MergeGuideLecturer] = []


class ReviewGroupItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: uuid.UUID
    observation_id: uuid.UUID
    candidate_version: int = Field(..., ge=1)


class ReviewGroupAcceptRequest(BaseModel):
    """Accept every proposed Scopus ID of one lecturer together. One shared reason is required."""

    model_config = ConfigDict(extra="forbid")

    items: list[ReviewGroupItem] = Field(..., min_length=2, max_length=10)
    reason: str = Field(..., min_length=1, max_length=4000)
    primary_candidate_id: uuid.UUID | None = None


class ReviewGroupAcceptedItem(BaseModel):
    candidate_id: uuid.UUID
    review_id: uuid.UUID
    resulting_identity_id: uuid.UUID
    candidate_version: int


class ReviewGroupAcceptResponse(BaseModel):
    lecturer_id: uuid.UUID
    accepted: list[ReviewGroupAcceptedItem]
    primary_identity_id: uuid.UUID | None = None


class ReviewRevocationRequest(BaseModel):
    """ADMIN-only compensation of an earlier ACCEPT. The reason is mandatory."""

    model_config = ConfigDict(extra="forbid")

    candidate_version: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=4000)


class ReviewRevocationResponse(BaseModel):
    review_id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_status: Literal["PENDING"]
    candidate_version: int
    revoked_identity_id: uuid.UUID
    identity_status: Literal["REVOKED"]


class ReviewLecturerSummary(BaseModel):
    id: uuid.UUID
    full_name: str


class ReviewAuthorSummary(BaseModel):
    id: uuid.UUID
    scopus_id: str
    preferred_name: str


class ReviewFit(BaseModel):
    """Degree of fit with its grounds. A read-only aid, never a decision or a probability."""

    level: Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]
    reasons: list[str] = Field(default_factory=list)
    ictu_affiliation_papers: int = 0


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
    # Read-only warning: the same Scopus Author ID is proposed for >1 lecturer.
    candidate_count_for_scopus_author: int = 1
    is_shared_scopus_author: bool = False
    fit: ReviewFit | None = None
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime


ReviewQueueState = Literal[
    "NO_LECTURERS",
    "NO_CANDIDATE_RUN",
    "RUN_WITHOUT_CANDIDATES",
    "HAS_CANDIDATES",
]


class ReviewContextResponse(BaseModel):
    """Why the queue is (or is not) empty - read-only, no candidate data."""

    state: ReviewQueueState
    lecturers_total: int
    publications_total: int
    scopus_authors_total: int
    completed_generation_runs: int
    candidates_by_status: dict[str, int]


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


SourceClaimState = Literal["CURRENT", "WITHDRAWN", "NOT_OBSERVED", "AMBIGUOUS", "INVALID"]


class ReviewSourceClaimTrace(BaseModel):
    """Allowlisted provenance only: no raw row, claim key, e-mail or arbitrary JSON."""

    model_config = ConfigDict(extra="forbid")

    capture_id: uuid.UUID
    analysis_id: uuid.UUID
    artifact_id: uuid.UUID
    content_id: uuid.UUID
    claim_id: uuid.UUID
    record_id: uuid.UUID
    contract_version: str = Field(min_length=1, max_length=20, pattern=r"^1\.[0-9]+$")
    identity_rules_version: str = Field(min_length=1, max_length=100,
                                       pattern=r"^[A-Za-z0-9._/+:-]+$")
    normalization_version: str = Field(min_length=1, max_length=100,
                                      pattern=r"^[A-Za-z0-9._/+:-]+$")
    captured_at: datetime
    completeness: Literal["COMPLETE", "PARTIAL"]
    selection_status: Literal["ACTIVE_PROJECTION", "HISTORICAL_ONLY"]


class ReviewSourceClaimHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: uuid.UUID
    observation_id: uuid.UUID
    generation_run_id: uuid.UUID
    rule_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z0-9_]+$")
    rule_version: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._/+:-]+$")
    recorded_state: SourceClaimState


class ReviewSourceClaimEvidenceResponse(BaseModel):
    """Future read contract. Presence and declaration weight never authorize a decision."""

    model_config = ConfigDict(extra="forbid")

    evidence_kind: Literal["SOURCE_CLAIM"] = "SOURCE_CLAIM"
    source_tier: Literal["INSTITUTION_DECLARED"] = "INSTITUTION_DECLARED"
    evidence_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_system: Literal["ICTU_REPO_SCOPUS_GUIDE", "ICTU_REPO_PROFILES"]
    scope_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    scopus_id: str = Field(pattern=r"^[0-9]+$")
    subject_resolution: Literal["RESOLVED_SOURCE_ID", "RESOLVED_EMAIL"] | None
    recorded_subject_resolutions: list[Literal["RESOLVED_SOURCE_ID", "RESOLVED_EMAIL"]]
    selection_status: Literal["ACTIVE_PROJECTION", "HISTORICAL_ONLY"]
    current_state: SourceClaimState | Literal["STALE"]
    current_weight: Literal[0, 1]
    is_primary_claimed: bool | None
    listed: bool | None
    temporal_ambiguity: bool
    recorded_states: list[SourceClaimState]
    recorded_conflict_codes: list[str]
    history: list[ReviewSourceClaimHistory] = Field(min_length=1)
    source_refs: list[ReviewSourceClaimTrace] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_authority(self):
        historical = self.selection_status == "HISTORICAL_ONLY"
        if historical != (self.current_state == "STALE"):
            raise ValueError("Historical selection must be stale")
        if self.current_weight != int(self.current_state == "CURRENT"):
            raise ValueError("Only CURRENT declarations have usable declaration weight")
        if self.temporal_ambiguity != (self.current_state == "AMBIGUOUS"):
            raise ValueError("Temporal ambiguity cannot be authoritative")
        if self.current_state == "CURRENT":
            if self.listed is not True:
                raise ValueError("CURRENT declaration must be listed")
        elif self.is_primary_claimed is not None or self.listed is not None:
            raise ValueError("Non-current flags cannot be presented as current facts")
        if historical and any(r.selection_status == "ACTIVE_PROJECTION" for r in self.source_refs):
            raise ValueError("Stale evidence has no active provenance")
        return self


class ReviewSourceClaimProjectionResponse(BaseModel):
    """Offline contract only; no route or reviewer workflow activation in B2-A."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: uuid.UUID
    candidate_status: CandidateStatus
    reviewer_active: Literal[False] = False
    decision_enabled: Literal[False] = False
    release_gate: Literal["E3-P3-B2_REQUIRED"] = "E3-P3-B2_REQUIRED"
    items: list[ReviewSourceClaimEvidenceResponse] = Field(default_factory=list)


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
    candidate_count_for_scopus_author: int = 1
    is_shared_scopus_author: bool = False
    other_candidates: list[ReviewOtherCandidateSummary] = Field(default_factory=list)


ReasonTrigger = Literal[
    "NAME_EVIDENCE_ONLY",
    "SHARED_SCOPUS_AUTHOR",
    "MULTIPLE_CANDIDATES_FOR_LECTURER",
]


class ReviewDecisionPolicy(BaseModel):
    """Server-computed reason requirements (D-2). Informational for clients;
    the decision endpoint re-checks them and is the final authority."""

    accept_reason_required: bool = False
    accept_reason_triggers: list[ReasonTrigger] = Field(default_factory=list)
    reject_reason_required: bool = True


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
    review_policy: ReviewDecisionPolicy = Field(default_factory=ReviewDecisionPolicy)
    fit: ReviewFit | None = None


class ReviewDecisionResponse(BaseModel):
    review_id: uuid.UUID
    candidate_id: uuid.UUID
    observation_id: uuid.UUID
    action: ReviewAction
    candidate_status: Literal["ACCEPTED", "REJECTED"]
    candidate_version: int
    resulting_identity_id: uuid.UUID | None = None
    idempotent: bool
