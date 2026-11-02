"""Primary ("main") Scopus ID label per lecturer, plus the "most publications" suggestion.

Display label only. It never merges identities and never changes which publications a
lecturer has; the label history is append-only and every change is audited.
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
from app.models.lecturer_primary_scopus import LecturerPrimaryScopusEvent as Event
from app.models.master_lecturer import Lecturer
from app.models.publication import PublicationAuthor, ScopusAuthor
from app.services.publication_exclusions import not_excluded

AUDIT_SET = "LECTURER_PRIMARY_SCOPUS_ID_SET"
AUDIT_CLEARED = "LECTURER_PRIMARY_SCOPUS_ID_CLEARED"
ALLOWED_ROLES = ("ADMIN", "REVIEWER")
MAX_REASON_LENGTH = 4000


class PrimaryIdentityError(Exception):
    def __init__(self, code: str, status_code: int, message: str) -> None:
        super().__init__(message)
        self.code, self.status_code, self.message = code, status_code, message


@dataclass(frozen=True, slots=True)
class PrimaryView:
    """What to show for one lecturer."""

    primary_identity_id: uuid.UUID | None       # explicit, human-chosen
    suggested_identity_id: uuid.UUID | None     # most distinct publications; only when no explicit
    publication_counts: dict[uuid.UUID, int]    # per approved identity (distinct publications)


def approved_identity_publication_counts(
    session: Session, lecturer_id: uuid.UUID
) -> dict[uuid.UUID, int]:
    """Distinct publications per APPROVED identity of the lecturer (withdrawn papers excluded)."""

    rows = session.execute(
        select(LecturerScopusIdentity.id,
               func.count(func.distinct(PublicationAuthor.publication_id)))
        .outerjoin(PublicationAuthor,
                   PublicationAuthor.scopus_author_id == LecturerScopusIdentity.scopus_author_id)
        .where(LecturerScopusIdentity.lecturer_id == lecturer_id,
               LecturerScopusIdentity.status == "APPROVED",
               (PublicationAuthor.publication_id.is_(None))
               | not_excluded(LecturerScopusIdentity.lecturer_id, PublicationAuthor.publication_id))
        .group_by(LecturerScopusIdentity.id)
    ).all()
    return {identity_id: int(count) for identity_id, count in rows}


def _scopus_id_order(session: Session, identity_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    rows = session.execute(
        select(LecturerScopusIdentity.id, ScopusAuthor.scopus_id)
        .join(ScopusAuthor, ScopusAuthor.id == LecturerScopusIdentity.scopus_author_id)
        .where(LecturerScopusIdentity.id.in_(identity_ids))).all()
    return {i: s for i, s in rows}


def explicit_primary(session: Session, lecturer_id: uuid.UUID) -> uuid.UUID | None:
    """The latest SET, if it is the latest event and its identity is still valid."""

    last = session.scalars(
        select(Event).where(Event.lecturer_id == lecturer_id).order_by(Event.seq.desc()).limit(1)
    ).first()
    if last is None or last.action != "SET" or last.identity_id is None:
        return None
    identity = session.get(LecturerScopusIdentity, last.identity_id)
    if (identity is None or identity.status != "APPROVED"
            or identity.lecturer_id != lecturer_id):
        return None                              # revoked or moved: the label lapses
    return identity.id


def primary_view(session: Session, lecturer_id: uuid.UUID) -> PrimaryView:
    counts = approved_identity_publication_counts(session, lecturer_id)
    primary = explicit_primary(session, lecturer_id)
    suggested = None
    if primary is None and len(counts) >= 2:
        order = _scopus_id_order(session, list(counts))
        # Most publications first; ties broken by the lowest Scopus ID so it is deterministic.
        suggested = min(counts, key=lambda i: (-counts[i], order.get(i, "")))
    return PrimaryView(primary, suggested, counts)


class PrimaryIdentityService:
    def __init__(self, session: Session, *, auto_commit: bool = True) -> None:
        self._session = session
        self._auto_commit = auto_commit

    def set_primary(self, lecturer_id: uuid.UUID, identity_id: uuid.UUID,
                    user_id: uuid.UUID, reason: str) -> PrimaryView:
        return self._append("SET", lecturer_id, identity_id, user_id, reason)

    def clear_primary(self, lecturer_id: uuid.UUID, user_id: uuid.UUID,
                      reason: str) -> PrimaryView:
        return self._append("CLEAR", lecturer_id, None, user_id, reason)

    def _append(self, action: str, lecturer_id: uuid.UUID, identity_id: uuid.UUID | None,
                user_id: uuid.UUID, reason: str) -> PrimaryView:
        user = self._session.get(User, user_id)
        if user is None or not user.is_active or user.role not in ALLOWED_ROLES:
            raise PrimaryIdentityError(
                "FORBIDDEN", 403, "Only an active ADMIN or REVIEWER may choose the main ID.")
        text_reason = (reason or "").strip()
        if (not text_reason or len(text_reason) > MAX_REASON_LENGTH
                or any(ord(c) < 32 and c not in "\n\t" for c in text_reason)):
            raise PrimaryIdentityError(
                "PRIMARY_REASON_REQUIRED", 422, "A real, non-blank reason is required.")
        # Serialize per lecturer so two reviewers cannot interleave choices.
        lecturer = self._session.get(Lecturer, lecturer_id, with_for_update=True)
        if lecturer is None:
            raise PrimaryIdentityError("NOT_FOUND", 404, "Lecturer not found.")
        current = explicit_primary(self._session, lecturer_id)
        if action == "SET":
            identity = self._session.get(LecturerScopusIdentity, identity_id)
            if (identity is None or identity.lecturer_id != lecturer_id
                    or identity.status != "APPROVED"):
                raise PrimaryIdentityError(
                    "IDENTITY_NOT_APPROVED_FOR_LECTURER", 409,
                    "Only an APPROVED Scopus identity of this lecturer can be the main ID.")
            if current == identity_id:
                raise PrimaryIdentityError("ALREADY_PRIMARY", 409, "Already the main ID.")
        elif current is None:
            raise PrimaryIdentityError("NO_PRIMARY", 409, "The lecturer has no main ID chosen.")

        self._session.add(Event(lecturer_id=lecturer_id, identity_id=identity_id, action=action,
                                reason=text_reason, acted_by_user_id=user.id,
                                created_at=datetime.now(UTC)))
        self._session.add(AuditEvent(
            id=uuid.uuid4(), entity_type="lecturer_primary_scopus_identity",
            entity_id=lecturer_id, action=AUDIT_SET if action == "SET" else AUDIT_CLEARED,
            actor_type="USER", actor_user_id=user.id, actor_service=None,
            before_state={"primary_identity_id": str(current) if current else None},
            after_state={"primary_identity_id": str(identity_id) if identity_id else None},
            reason=text_reason, event_metadata={"lecturer_id": str(lecturer_id)},
            created_at=datetime.now(UTC)))
        if self._auto_commit:
            self._session.commit()
        else:
            self._session.flush()
        return primary_view(self._session, lecturer_id)
