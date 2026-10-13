"""ADMIN manual affiliation review: list what needs attention, manage overrides.

An override NEVER touches ``publication_author_affiliation_resolutions`` /
``publication_author_affiliations`` (the automated pipeline's tables) or the
raw Scopus payload — it only writes
``publication_author_affiliation_overrides``, layered on top. Confidence is
restricted to CORROBORATED/UNRESOLVED (see the model docstring): an ADMIN
confirming a record is evidence a human looked at it, never a new
identity-verification channel, so it can never become VERIFIED here.

A publication author position may carry several independent ACTIVE
overrides at once (dual appointment, etc). Each row has its own lifecycle:
``add_override`` creates a new ACTIVE row (does not touch any other row on
the same position); ``update_override`` edits exactly the one row named by
its id; ``revoke_override`` marks that one row REVOKED (status + who/when)
without deleting it, so the audit trail and the row itself stay queryable
— this is how "revoke" is distinguished from "replace" (update_override)
or "add another unit" (add_override): three distinct operations, each
scoped to a single row.

Concurrency: ``SELECT ... FOR UPDATE`` serializes two ADMINs editing the
same row, plus an explicit client-supplied ``version`` check (same pattern
as ``candidate_review_service``) so a stale edit is refused with a clear
error instead of silently overwriting a concurrent one. The partial unique
index ``uq_paao_active_position_text`` (migration c7f2a9b1d3e5) blocks two
ACTIVE rows on the same position with identical unit text, surfaced here as
``DUPLICATE_ACTIVE_OVERRIDE``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.affiliation import PublicationAuthorAffiliationResolution
from app.models.affiliation_override import OVERRIDE_CONFIDENCE_VALUES, PublicationAuthorAffiliationOverride
from app.models.governance import AuditEvent
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor

ENTITY_TYPE = "publication_author_affiliation_override"
CREATED_ACTION = "AFFILIATION_OVERRIDE_CREATED"
UPDATED_ACTION = "AFFILIATION_OVERRIDE_UPDATED"
REVOKED_ACTION = "AFFILIATION_OVERRIDE_REVOKED"


class AffiliationOverrideError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


class PublicationAuthorNotFound(AffiliationOverrideError):
    def __init__(self) -> None:
        super().__init__("PUBLICATION_AUTHOR_NOT_FOUND", "Không tìm thấy vị trí tác giả này.", 404)


class StaleOverrideVersion(AffiliationOverrideError):
    def __init__(self, current_version: int) -> None:
        super().__init__(
            "STALE_OVERRIDE_VERSION",
            f"Dữ liệu đã bị thay đổi bởi người khác (phiên bản hiện tại: {current_version}). Hãy tải lại.",
            409,
        )
        self.current_version = current_version


class OverrideNotFound(AffiliationOverrideError):
    def __init__(self) -> None:
        super().__init__("OVERRIDE_NOT_FOUND", "Không tìm thấy hiệu chỉnh này.", 404)


class OverrideAlreadyRevoked(AffiliationOverrideError):
    def __init__(self) -> None:
        super().__init__("OVERRIDE_ALREADY_REVOKED", "Hiệu chỉnh này đã bị thu hồi trước đó.", 409)


class DuplicateActiveOverride(AffiliationOverrideError):
    def __init__(self) -> None:
        super().__init__(
            "DUPLICATE_ACTIVE_OVERRIDE",
            "Đơn vị này đã được ghi nhận đang hoạt động cho vị trí tác giả này.",
            409,
        )


@dataclass(slots=True)
class AddOverrideCommand:
    publication_author_id: uuid.UUID
    affiliation_text: str
    confidence: str
    evidence_url: str
    reason: str
    actor_user_id: uuid.UUID


@dataclass(slots=True)
class UpdateOverrideCommand:
    override_id: uuid.UUID
    affiliation_text: str
    confidence: str
    evidence_url: str
    reason: str
    actor_user_id: uuid.UUID
    expected_version: int


@dataclass(slots=True)
class NeedsReviewItem:
    publication_author_id: uuid.UUID
    eid: str
    title: str
    author_order: int
    scopus_id: str
    preferred_name: str
    reason_kind: str  # UNRESOLVED | CONFLICTING_SOURCES | LOW_CONFIDENCE
    resolution_summaries: list[dict]
    has_override: bool
    # ALL overrides (active and revoked) for this position, newest first —
    # so the ADMIN review UI can show the full list and pre-fill edit forms
    # without a second round-trip.
    overrides: list[PublicationAuthorAffiliationOverride]


def _validate_text(affiliation_text: str, confidence: str, evidence_url: str, reason: str) -> None:
    if confidence not in OVERRIDE_CONFIDENCE_VALUES:
        raise AffiliationOverrideError(
            "INVALID_CONFIDENCE", f"Mức tin cậy phải là một trong: {', '.join(OVERRIDE_CONFIDENCE_VALUES)}.", 422
        )
    if not affiliation_text.strip():
        raise AffiliationOverrideError("MISSING_AFFILIATION_TEXT", "Cần nhập tên đơn vị.", 422)
    if not evidence_url.strip():
        raise AffiliationOverrideError("MISSING_EVIDENCE", "Cần dẫn nguồn chứng cứ (URL hoặc tài liệu).", 422)
    if not reason.strip():
        raise AffiliationOverrideError("MISSING_REASON", "Cần ghi lý do thao tác.", 422)


def list_overrides_for_author(db: Session, publication_author_id: uuid.UUID) -> list[PublicationAuthorAffiliationOverride]:
    return list(
        db.scalars(
            select(PublicationAuthorAffiliationOverride)
            .where(PublicationAuthorAffiliationOverride.publication_author_id == publication_author_id)
            .order_by(PublicationAuthorAffiliationOverride.created_at.desc())
        ).all()
    )


def add_override(db: Session, cmd: AddOverrideCommand) -> PublicationAuthorAffiliationOverride:
    """Add a new ACTIVE unit statement for this position. Does not touch any
    other override already on the same position — this is how "this author
    also belongs to a second organization" is expressed, distinct from
    editing or revoking an existing one."""

    _validate_text(cmd.affiliation_text, cmd.confidence, cmd.evidence_url, cmd.reason)
    author = db.get(PublicationAuthor, cmd.publication_author_id)
    if author is None:
        raise PublicationAuthorNotFound

    row = PublicationAuthorAffiliationOverride(
        publication_author_id=cmd.publication_author_id,
        affiliation_text=cmd.affiliation_text.strip(),
        confidence=cmd.confidence,
        status="ACTIVE",
        evidence_url=cmd.evidence_url.strip(),
        reason=cmd.reason.strip(),
        created_by_user_id=cmd.actor_user_id,
        updated_by_user_id=cmd.actor_user_id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        if "uq_paao_active_position_text" in str(exc.orig):
            raise DuplicateActiveOverride from exc
        raise
    db.add(
        AuditEvent(
            entity_type=ENTITY_TYPE,
            entity_id=row.id,
            action=CREATED_ACTION,
            actor_type="USER",
            actor_user_id=cmd.actor_user_id,
            before_state=None,
            after_state={
                "affiliation_text": row.affiliation_text,
                "confidence": row.confidence,
                "evidence_url": row.evidence_url,
                "status": row.status,
            },
            reason=cmd.reason.strip(),
            event_metadata={"publication_author_id": str(cmd.publication_author_id), "version": row.version},
        )
    )
    db.commit()
    db.refresh(row)
    return row


def update_override(db: Session, cmd: UpdateOverrideCommand) -> PublicationAuthorAffiliationOverride:
    """Edit exactly the one override named by ``override_id``. Other
    overrides on the same position are never read or modified."""

    _validate_text(cmd.affiliation_text, cmd.confidence, cmd.evidence_url, cmd.reason)
    existing = db.scalar(
        select(PublicationAuthorAffiliationOverride)
        .where(PublicationAuthorAffiliationOverride.id == cmd.override_id)
        .with_for_update()
    )
    if existing is None:
        raise OverrideNotFound
    if existing.version != cmd.expected_version:
        db.rollback()
        raise StaleOverrideVersion(existing.version)
    if existing.status == "REVOKED":
        db.rollback()
        raise OverrideAlreadyRevoked

    before = {
        "affiliation_text": existing.affiliation_text,
        "confidence": existing.confidence,
        "evidence_url": existing.evidence_url,
        "reason": existing.reason,
        "status": existing.status,
    }
    existing.affiliation_text = cmd.affiliation_text.strip()
    existing.confidence = cmd.confidence
    existing.evidence_url = cmd.evidence_url.strip()
    existing.reason = cmd.reason.strip()
    existing.updated_by_user_id = cmd.actor_user_id
    existing.version = existing.version + 1
    existing.updated_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            entity_type=ENTITY_TYPE,
            entity_id=existing.id,
            action=UPDATED_ACTION,
            actor_type="USER",
            actor_user_id=cmd.actor_user_id,
            before_state=before,
            after_state={
                "affiliation_text": existing.affiliation_text,
                "confidence": existing.confidence,
                "evidence_url": existing.evidence_url,
                "reason": existing.reason,
                "status": existing.status,
            },
            reason=cmd.reason.strip(),
            event_metadata={"publication_author_id": str(existing.publication_author_id), "version": existing.version},
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_paao_active_position_text" in str(exc.orig):
            raise DuplicateActiveOverride from exc
        raise
    db.refresh(existing)
    return existing


def revoke_override(
    db: Session, *, override_id: uuid.UUID, expected_version: int, reason: str, actor_user_id: uuid.UUID
) -> PublicationAuthorAffiliationOverride:
    """Mark one override REVOKED. The row is kept (not deleted) so the
    audit trail and the statement itself remain visible as history; other
    overrides on the same position are unaffected."""

    if not reason.strip():
        raise AffiliationOverrideError("MISSING_REASON", "Cần ghi lý do thu hồi.", 422)
    existing = db.scalar(
        select(PublicationAuthorAffiliationOverride)
        .where(PublicationAuthorAffiliationOverride.id == override_id)
        .with_for_update()
    )
    if existing is None:
        raise OverrideNotFound
    if existing.version != expected_version:
        db.rollback()
        raise StaleOverrideVersion(existing.version)
    if existing.status == "REVOKED":
        db.rollback()
        raise OverrideAlreadyRevoked

    before = {"status": existing.status, "affiliation_text": existing.affiliation_text}
    now = datetime.now(UTC)
    existing.status = "REVOKED"
    existing.revoked_by_user_id = actor_user_id
    existing.revoked_at = now
    existing.updated_by_user_id = actor_user_id
    existing.version = existing.version + 1
    existing.updated_at = now
    db.add(
        AuditEvent(
            entity_type=ENTITY_TYPE,
            entity_id=existing.id,
            action=REVOKED_ACTION,
            actor_type="USER",
            actor_user_id=actor_user_id,
            before_state=before,
            after_state={"status": existing.status, "affiliation_text": existing.affiliation_text},
            reason=reason.strip(),
            event_metadata={"publication_author_id": str(existing.publication_author_id), "version": existing.version},
        )
    )
    db.commit()
    db.refresh(existing)
    return existing


_UNRESOLVED_REASONS_AS_CONFLICT = frozenset({"ID_CONFLICT", "ID_AMBIGUOUS", "POSITION_CLAIMED_BY_OTHER_ID"})


def list_needs_review(db: Session, *, limit: int = 100, offset: int = 0) -> tuple[list[NeedsReviewItem], int]:
    """Publication-author positions that are UNRESOLVED, have conflicting
    sources (different link_status per source, or a conflict-type reason),
    or are CORROBORATED only (reconciled but not independently verified)."""

    rows = db.execute(
        select(
            PublicationAuthor.id,
            Publication.eid,
            Publication.title,
            PublicationAuthor.author_order,
            ScopusAuthor.scopus_id,
            ScopusAuthor.preferred_name,
        )
        .join(Publication, Publication.id == PublicationAuthor.publication_id)
        .join(ScopusAuthor, ScopusAuthor.id == PublicationAuthor.scopus_author_id)
        .order_by(Publication.eid.asc(), PublicationAuthor.author_order.asc())
    ).all()

    res_by_author: dict[uuid.UUID, list[PublicationAuthorAffiliationResolution]] = {}
    for res in db.scalars(select(PublicationAuthorAffiliationResolution)).all():
        res_by_author.setdefault(res.publication_author_id, []).append(res)

    overrides_by_author: dict[uuid.UUID, list[PublicationAuthorAffiliationOverride]] = {}
    for o in db.scalars(
        select(PublicationAuthorAffiliationOverride).order_by(PublicationAuthorAffiliationOverride.created_at.desc())
    ).all():
        overrides_by_author.setdefault(o.publication_author_id, []).append(o)

    items: list[NeedsReviewItem] = []
    for author_id, eid, title, author_order, scopus_id, preferred_name in rows:
        resolutions = res_by_author.get(author_id, [])
        if not resolutions:
            continue  # NOT_RECONCILED — nothing was ever attempted, out of scope here
        statuses = {r.link_status for r in resolutions}
        reasons = {r.unresolved_reason for r in resolutions if r.unresolved_reason}
        if statuses == {"VERIFIED"}:
            continue  # already independently verified by identifier, nothing to review
        if "VERIFIED" in statuses and len(statuses) > 1:
            kind = "CONFLICTING_SOURCES"
        elif reasons & _UNRESOLVED_REASONS_AS_CONFLICT:
            kind = "CONFLICTING_SOURCES"
        elif statuses == {"UNRESOLVED"}:
            kind = "UNRESOLVED"
        else:
            kind = "LOW_CONFIDENCE"  # CORROBORATED (possibly mixed with UNRESOLVED), no VERIFIED
        overrides = overrides_by_author.get(author_id, [])
        items.append(
            NeedsReviewItem(
                publication_author_id=author_id,
                eid=eid,
                title=title,
                author_order=author_order,
                scopus_id=scopus_id,
                preferred_name=preferred_name,
                reason_kind=kind,
                resolution_summaries=[
                    {
                        "source_system": r.source_system,
                        "link_status": r.link_status,
                        "unresolved_reason": r.unresolved_reason,
                    }
                    for r in sorted(resolutions, key=lambda r: r.source_system)
                ],
                has_override=any(o.status == "ACTIVE" for o in overrides),
                overrides=overrides,
            )
        )
    total = len(items)
    return items[offset : offset + limit], total


__all__ = [
    "AddOverrideCommand",
    "AffiliationOverrideError",
    "CREATED_ACTION",
    "DuplicateActiveOverride",
    "ENTITY_TYPE",
    "NeedsReviewItem",
    "OverrideAlreadyRevoked",
    "OverrideNotFound",
    "PublicationAuthorNotFound",
    "REVOKED_ACTION",
    "StaleOverrideVersion",
    "UPDATED_ACTION",
    "UpdateOverrideCommand",
    "add_override",
    "list_needs_review",
    "list_overrides_for_author",
    "revoke_override",
    "update_override",
]
