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
    "CandidateWithEvidenceResponse",
    # audit
    "AuditEventResponse",
]
