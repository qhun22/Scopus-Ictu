"""Publication repository — M0 scaffold."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.publication import (
    Publication,
    PublicationAuthor,
    PublicationRawSource,
)
from app.repositories.base_repository import BaseRepository


class PublicationRepository(BaseRepository[Publication]):
    """M0 stub. TODO(M1): lookup by EID (canonical identity)."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Publication)


class PublicationRawSourceRepository(BaseRepository[PublicationRawSource]):
    """M0 stub. TODO(M1): provenance lookups."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, PublicationRawSource)


class PublicationAuthorRepository(BaseRepository[PublicationAuthor]):
    """M0 stub. TODO(M1): author-position lookups."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, PublicationAuthor)