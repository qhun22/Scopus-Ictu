"""Pydantic schemas — M0 scaffold."""

from app.schemas.audit import AuditEventResponse
from app.schemas.auth import LoginRequest, LoginResponse, TokenPayload
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
    ImportStatusResponse,
    ScopusImportCreate,
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
    "LoginResponse",
    # lecturer
    "LecturerBase",
    "LecturerCreate",
    "LecturerUpdate",
    "LecturerResponse",
    "LecturerSourceSnapshotResponse",
    "LecturerKnownPublicationResponse",
    # scopus_import
    "ScopusImportBase",
    "ScopusImportCreate",
    "ScopusImportResponse",
    "ImportStatusResponse",
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