"""Scopus import repository — M0 scaffold."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.repositories.base_repository import BaseRepository


class ScopusImportRepository(BaseRepository[ScopusImport]):
    """M0 stub. TODO(M1): import batch lookups."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ScopusImport)


class RawScopusRecordRepository(BaseRepository[RawScopusRecord]):
    """M0 stub. TODO(M1): raw-record lookups by import_id and source_row_no."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, RawScopusRecord)