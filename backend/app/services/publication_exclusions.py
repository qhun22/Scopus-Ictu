"""ADMIN-governed per-lecturer publication exclusions (G09) and the shared read filter.

``not_excluded`` is the single predicate every lecturer-facing list, export and count must
apply, so a paper withdrawn from one lecturer disappears everywhere consistently while the
canonical publication, the Scopus author and the approved identity stay untouched.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.governance import User
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, PublicationAuthor
from app.models.publication_exclusion import LecturerPublicationExclusionEvent as Event

AUDIT_EXCLUDED = "LECTURER_PUBLICATION_EXCLUDED"
AUDIT_RESTORED = "LECTURER_PUBLICATION_RESTORED"
MAX_REASON_LENGTH = 4000


def not_excluded(lecturer_id_column, publication_id_column):
    """SQL predicate: the pair's latest exclusion event is not EXCLUDE (no event = included)."""

    latest = (
        select(Event.action)
        .where(Event.lecturer_id == lecturer_id_column,
               Event.publication_id == publication_id_column)
        .order_by(Event.seq.desc())
        .limit(1)
        .scalar_subquery()
    )
    return func.coalesce(latest, "INCLUDE") != "EXCLUDE"


class PublicationExclusionError(Exception):
    def __init__(self, code: str, status_code: int, message: str) -> None:
        super().__init__(message)
        self.code, self.status_code, self.message = code, status_code, message


@dataclass(frozen=True, slots=True)
class ExclusionRecord:
    lecturer_id: uuid.UUID
    publication_id: uuid.UUID
    action: str
    reason: str
    acted_by_user_id: uuid.UUID
    created_at: datetime


def _record(event: Event) -> ExclusionRecord:
    return ExclusionRecord(event.lecturer_id, event.publication_id, event.action,
                           event.reason, event.acted_by_user_id, event.created_at)


class PublicationExclusionService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def exclude(self, lecturer_id: uuid.UUID, publication_id: uuid.UUID,
                admin_user_id: uuid.UUID, reason: str) -> ExclusionRecord:
        return self._append("EXCLUDE", lecturer_id, publication_id, admin_user_id, reason)

    def restore(self, lecturer_id: uuid.UUID, publication_id: uuid.UUID,
                admin_user_id: uuid.UUID, reason: str) -> ExclusionRecord:
        return self._append("INCLUDE", lecturer_id, publication_id, admin_user_id, reason)

    def list_excluded(self, lecturer_id: uuid.UUID) -> list[ExclusionRecord]:
        rows = self._session.scalars(
            select(Event).where(Event.lecturer_id == lecturer_id).order_by(Event.seq.asc())
        ).all()
        latest: dict[uuid.UUID, Event] = {}
        for row in rows:
            latest[row.publication_id] = row
        return [_record(e) for e in latest.values() if e.action == "EXCLUDE"]

    def _latest_action(self, lecturer_id, publication_id) -> str | None:
        return self._session.scalar(
            select(Event.action)
            .where(Event.lecturer_id == lecturer_id, Event.publication_id == publication_id)
            .order_by(Event.seq.desc()).limit(1))

    def _append(self, action: str, lecturer_id: uuid.UUID, publication_id: uuid.UUID,
                admin_user_id: uuid.UUID, reason: str) -> ExclusionRecord:
        admin = self._session.get(User, admin_user_id)
        if admin is None or not admin.is_active or admin.role != "ADMIN":
            raise PublicationExclusionError("FORBIDDEN", 403, "Only an active ADMIN may do this.")
        text_reason = (reason or "").strip()
        if not text_reason or len(text_reason) > MAX_REASON_LENGTH or any(
                ord(c) < 32 and c not in "\n\t" for c in text_reason):
            raise PublicationExclusionError(
                "EXCLUSION_REASON_REQUIRED", 422, "A real, non-blank reason is required.")
        # Lock the lecturer row so two admins cannot interleave decisions for one lecturer.
        lecturer = self._session.get(Lecturer, lecturer_id, with_for_update=True)
        if lecturer is None or self._session.get(Publication, publication_id) is None:
            raise PublicationExclusionError("NOT_FOUND", 404, "Lecturer or publication not found.")
        state = self._latest_action(lecturer_id, publication_id)
        if action == "EXCLUDE":
            if state == "EXCLUDE":
                raise PublicationExclusionError("ALREADY_EXCLUDED", 409, "Already excluded.")
            linked = self._session.scalar(
                select(func.count()).select_from(PublicationAuthor)
                .join(LecturerScopusIdentity,
                      LecturerScopusIdentity.scopus_author_id == PublicationAuthor.scopus_author_id)
                .where(PublicationAuthor.publication_id == publication_id,
                       LecturerScopusIdentity.lecturer_id == lecturer_id,
                       LecturerScopusIdentity.status == "APPROVED"))
            if not linked:
                raise PublicationExclusionError(
                    "PUBLICATION_NOT_LINKED", 409,
                    "The lecturer has no approved Scopus ID on this publication.")
        elif state != "EXCLUDE":
            raise PublicationExclusionError("NOT_EXCLUDED", 409, "The pair is not excluded.")

        event = Event(lecturer_id=lecturer_id, publication_id=publication_id, action=action,
                      reason=text_reason, acted_by_user_id=admin.id,
                      created_at=datetime.now(UTC))
        self._session.add(event)
        self._session.add(AuditEvent(
            id=uuid.uuid4(), entity_type="lecturer_publication_exclusion",
            entity_id=lecturer_id, action=AUDIT_EXCLUDED if action == "EXCLUDE" else AUDIT_RESTORED,
            actor_type="USER", actor_user_id=admin.id, actor_service=None,
            before_state={"state": state or "INCLUDE"},
            after_state={"state": "EXCLUDE" if action == "EXCLUDE" else "INCLUDE"},
            reason=text_reason, event_metadata={"publication_id": str(publication_id)},
            created_at=datetime.now(UTC)))
        self._session.commit()
        return _record(event)
