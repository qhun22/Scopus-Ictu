"""Identity / evidence repository — M0 scaffold.

ADR-004: identity and evidence are separate.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.identity import (
    IdentityEvidence,
    LecturerScopusIdentity,
    MappingReview,
)
from app.repositories.base_repository import BaseRepository


class LecturerScopusIdentityRepository(BaseRepository[LecturerScopusIdentity]):
    """M0 stub. TODO(M1): approved-identity lookups."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, LecturerScopusIdentity)


class IdentityEvidenceRepository(BaseRepository[IdentityEvidence]):
    """M0 stub. TODO(M1): evidence-by-identity lookups."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, IdentityEvidence)


class MappingReviewRepository(BaseRepository[MappingReview]):
    """M0 stub. TODO(M1): review-queue lookups."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, MappingReview)