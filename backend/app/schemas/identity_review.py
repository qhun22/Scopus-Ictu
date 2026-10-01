"""Identity review schemas — M0 scaffold.

ADR-004: identity and evidence are separate.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import TimestampMixin


class LecturerScopusIdentityBase(BaseModel):
    """M0 stub. TODO(M1): lecturer_id, scopus_author_id, status, etc."""

    pass


class LecturerScopusIdentityCreate(LecturerScopusIdentityBase):
    """M0 stub."""

    pass


class LecturerScopusIdentityResponse(LecturerScopusIdentityBase, TimestampMixin):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class IdentityEvidenceBase(BaseModel):
    """M0 stub. TODO(M1): identity_id, evidence_kind, payload, etc."""

    pass


class IdentityEvidenceResponse(IdentityEvidenceBase):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class MappingReviewBase(BaseModel):
    """M0 stub. TODO(M1): identity_id, reviewer_id, decision, reason, etc."""

    pass


class MappingReviewCreate(MappingReviewBase):
    """M0 stub."""

    pass


class MappingReviewResponse(MappingReviewBase):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reviewed_at: datetime | None = None


class CandidateWithEvidenceResponse(BaseModel):
    """M0 stub. Matching engine output for review queue."""

    lecturer_id: int
    scopus_author_id: int
    score: float | None = None
    evidence: list[IdentityEvidenceResponse] = []