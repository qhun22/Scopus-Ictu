"""Pydantic schemas — M0 scaffold."""

from app.schemas.audit import AuditEventResponse
from app.schemas.auth import LoginRequest, TokenPayload
from app.schemas.common import PageResponse, PaginationParams, TimestampMixin
from app.schemas.identity_review import (
    CandidateWithEvidenceResponse,
    IdentityEvidenceResponse,
    LecturerScopusIdentityCreate,
    LecturerScopusIdentityResponse,
    MappingReviewCreate,
    MappingReviewResponse,
)
from app.schemas.lecturer_scopus_projection import (
    ApprovedIdentitySummaryRead,
    IdentityEvidenceSummaryRead,
    LecturerProfileRead,
    LecturerPublicationAggregatesRead,
    LecturerPublicationRead,
    PaginatedLecturerPublicationsRead,
)
from app.schemas.lecturer_scopus_api import LecturerPublicationsAPIResponse
from app.schemas.review_api import (
    ReviewCandidateDetailResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
)
from app.schemas.lecturer import (
    LecturerCreate,
    LecturerKnownPublicationResponse,
    LecturerResponse,
    LecturerSourceSnapshotResponse,
    LecturerUpdate,
)
from app.schemas.publication import (
    PublicationCreate,
    PublicationResponse,
    ScopusAuthorCreate,
    ScopusAuthorResponse,
)
from app.schemas.publication_api import (
    PublicationAuthorRead,
    PublicationDetailResponse,
    PublicationListItem,
    PublicationListResponse,
    PublicationLecturerLinkRead,
    PublicationProvenanceRead,
)
from app.schemas.scopus_import import (
    ImportStatus,
    ScopusImportConfigResponse,
    ImportStatusResponse,
    ScopusImportBase,
    ScopusImportCreate,
    ScopusImportListResponse,
    ScopusImportResponse,
)

__all__ = [
    # common
    "TimestampMixin",
    "PaginationParams",
    "PageResponse",
    # auth
    "TokenPayload",
    "LoginRequest",
    # lecturer
    "LecturerBase",
    "LecturerCreate",
    "LecturerUpdate",
    "LecturerResponse",
    "LecturerSourceSnapshotResponse",
    "LecturerKnownPublicationResponse",
    # scopus_import
    "ImportStatus",
    "ImportStatusResponse",
    "ScopusImportConfigResponse",
    "ScopusImportListResponse",
    "ScopusImportBase",
    "ScopusImportCreate",
    "ScopusImportResponse",
    # publication
    "PublicationBase",
    "PublicationCreate",
    "PublicationResponse",
    "ScopusAuthorBase",
    "ScopusAuthorCreate",
    "ScopusAuthorResponse",
    "PublicationAuthorResponse",
    "PublicationAuthorRead",
    "PublicationDetailResponse",
    "PublicationListItem",
    "PublicationListResponse",
    "PublicationLecturerLinkRead",
    "PublicationProvenanceRead",
    # scopus_author
    "ScopusAuthorNameVariantResponse",
    # identity_review
    "LecturerScopusIdentityBase",
    "LecturerScopusIdentityCreate",
    "LecturerScopusIdentityResponse",
    "IdentityEvidenceBase",
    "IdentityEvidenceResponse",
    "MappingReviewBase",
    "MappingReviewCreate",
    "MappingReviewResponse",
    "LecturerProfileRead",
    "IdentityEvidenceSummaryRead",
    "ApprovedIdentitySummaryRead",
    "LecturerPublicationRead",
    "PaginatedLecturerPublicationsRead",
    "LecturerPublicationAggregatesRead",
    "LecturerPublicationsAPIResponse",
    "CandidateWithEvidenceResponse",
    "ReviewCandidateDetailResponse",
    "ReviewDecisionRequest",
    "ReviewDecisionResponse",
    "ReviewQueueItem",
    "ReviewQueueResponse",
    # audit
    "AuditEventResponse",
]
