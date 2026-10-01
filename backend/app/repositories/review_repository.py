"""Mapping review repository — M0 scaffold.

Review queue operations belong to M1.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.identity import MappingReview
from app.repositories.base_repository import BaseRepository


class ReviewRepository(BaseRepository[MappingReview]):
    """M0 stub. TODO(M1): pending reviews, decisions, etc."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, MappingReview)