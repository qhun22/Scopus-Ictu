"""Lecturer repository — M0 scaffold."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.master_lecturer import Lecturer, LecturerKnownPublication, LecturerSourceSnapshot
from app.repositories.base_repository import BaseRepository


class LecturerRepository(BaseRepository[Lecturer]):
    """M0 stub. TODO(M1): lecturer-specific lookups (by email, employee_id, etc.)."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Lecturer)


class LecturerSourceSnapshotRepository(BaseRepository[LecturerSourceSnapshot]):
    """M0 stub. TODO(M1): snapshot-specific lookups (by source_kind)."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, LecturerSourceSnapshot)


class LecturerKnownPublicationRepository(BaseRepository[LecturerKnownPublication]):
    """M0 stub. TODO(M1): known-publication lookups."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, LecturerKnownPublication)