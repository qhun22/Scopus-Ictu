"""Author repository — M0 scaffold."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.publication import ScopusAuthor, ScopusAuthorNameVariant
from app.repositories.base_repository import BaseRepository


class ScopusAuthorRepository(BaseRepository[ScopusAuthor]):
    """M0 stub. TODO(M1): lookup by scopus_author_id, ORCID, name."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ScopusAuthor)


class ScopusAuthorNameVariantRepository(BaseRepository[ScopusAuthorNameVariant]):
    """M0 stub. TODO(M1): variant lookups by normalized name."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ScopusAuthorNameVariant)