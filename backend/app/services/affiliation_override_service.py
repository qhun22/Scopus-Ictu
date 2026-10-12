"""ADMIN manual affiliation review: list what needs attention, upsert an override.

An override NEVER touches ``publication_author_affiliation_resolutions`` /
``publication_author_affiliations`` (the automated pipeline's tables) or the
raw Scopus payload — it only writes
``publication_author_affiliation_overrides``, layered on top. Confidence is
restricted to CORROBORATED/UNRESOLVED (see the model docstring): an ADMIN
confirming a record is evidence a human looked at it, never a new
identity-verification channel, so it can never become VERIFIED here.

Concurrency: ``SELECT ... FOR UPDATE`` serializes two ADMINs editing the same
position, plus an explicit client-supplied ``version`` check (same pattern as
``candidate_review_service``) so a stale edit is refused with a clear error
instead of silently overwriting a concurrent one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.affiliation import PublicationAuthorAffiliationResolution
from app.models.affiliation_override import OVERRIDE_CONFIDENCE_VALUES, PublicationAuthorAffiliationOverride
from app.models.governance import AuditEvent
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor

ENTITY_TYPE = "publication_author_affiliation_override"
CREATED_ACTION = "AFFILIATION_OVERRIDE_CREATED"
UPDATED_ACTION = "AFFILIATION_OVERRIDE_UPDATED"
DELETED_ACTION = "AFFILIATION_OVERRIDE_DELETED"


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


@dataclass(slots=True)
class UpsertOverrideCommand:
    publication_author_id: uuid.UUID
    affiliation_text: str
    confidence: str
    evidence_url: str
    reason: str
    actor_user_id: uuid.UUID
    expected_version: int | None  # None = creating a new override


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
    # The full current override, if any — so the ADMIN review UI can
    # pre-fill the edit form (and know the version to send back) without a
    # second round-trip.
    override: PublicationAuthorAffiliationOverride | None = None


def _validate(cmd: UpsertOverrideCommand) -> None:
    if cmd.confidence not in OVERRIDE_CONFIDENCE_VALUES:
        raise AffiliationOverrideError(
            "INVALID_CONFIDENCE", f"Mức tin cậy phải là một trong: {', '.join(OVERRIDE_CONFIDENCE_VALUES)}.", 422
        )
    if not cmd.affiliation_text.strip():
        raise AffiliationOverrideError("MISSING_AFFILIATION_TEXT", "Cần nhập tên đơn vị.", 422)
    if not cmd.evidence_url.strip():
        raise AffiliationOverrideError("MISSING_EVIDENCE", "Cần dẫn nguồn chứng cứ (URL hoặc tài liệu).", 422)
    if not cmd.reason.strip():
        raise AffiliationOverrideError("MISSING_REASON", "Cần ghi lý do thao tác.", 422)


def upsert_override(db: Session, cmd: UpsertOverrideCommand) -> PublicationAuthorAffiliationOverride:
    _validate(cmd)
    author = db.get(PublicationAuthor, cmd.publication_author_id)
    if author is None:
        raise PublicationAuthorNotFound

    existing = db.scalar(
        select(PublicationAuthorAffiliationOverride)
        .where(PublicationAuthorAffiliationOverride.publication_author_id == cmd.publication_author_id)
        .with_for_update()
    )

    if existing is None:
        if cmd.expected_version is not None:
            raise OverrideNotFound
        row = PublicationAuthorAffiliationOverride(
            publication_author_id=cmd.publication_author_id,
            affiliation_text=cmd.affiliation_text.strip(),
            confidence=cmd.confidence,
            evidence_url=cmd.evidence_url.strip(),
            reason=cmd.reason.strip(),
            created_by_user_id=cmd.actor_user_id,
            updated_by_user_id=cmd.actor_user_id,
        )
        db.add(row)
        db.flush()
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
                },
                reason=cmd.reason.strip(),
                event_metadata={"publication_author_id": str(cmd.publication_author_id), "version": row.version},
            )
        )
        db.commit()
        db.refresh(row)
        return row

    if cmd.expected_version is None or existing.version != cmd.expected_version:
        db.rollback()
        raise StaleOverrideVersion(existing.version)

    before = {
        "affiliation_text": existing.affiliation_text,
        "confidence": existing.confidence,
        "evidence_url": existing.evidence_url,
        "reason": existing.reason,
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
            },
            reason=cmd.reason.strip(),
            event_metadata={"publication_author_id": str(cmd.publication_author_id), "version": existing.version},
        )
    )
    db.commit()
    db.refresh(existing)
    return existing


def delete_override(
    db: Session, *, publication_author_id: uuid.UUID, expected_version: int, actor_user_id: uuid.UUID
) -> None:
    existing = db.scalar(
        select(PublicationAuthorAffiliationOverride)
        .where(PublicationAuthorAffiliationOverride.publication_author_id == publication_author_id)
        .with_for_update()
    )
    if existing is None:
        raise OverrideNotFound
    if existing.version != expected_version:
        db.rollback()
        raise StaleOverrideVersion(existing.version)
    before = {
        "affiliation_text": existing.affiliation_text,
        "confidence": existing.confidence,
        "evidence_url": existing.evidence_url,
        "reason": existing.reason,
    }
    override_id = existing.id
    db.delete(existing)
    db.add(
        AuditEvent(
            entity_type=ENTITY_TYPE,
            entity_id=override_id,
            action=DELETED_ACTION,
            actor_type="USER",
            actor_user_id=actor_user_id,
            before_state=before,
            after_state=None,
            event_metadata={"publication_author_id": str(publication_author_id)},
        )
    )
    db.commit()


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

    overrides_by_author: dict[uuid.UUID, PublicationAuthorAffiliationOverride] = {
        o.publication_author_id: o for o in db.scalars(select(PublicationAuthorAffiliationOverride)).all()
    }

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
                has_override=author_id in overrides_by_author,
                override=overrides_by_author.get(author_id),
            )
        )
    total = len(items)
    return items[offset : offset + limit], total


__all__ = [
    "AffiliationOverrideError",
    "CREATED_ACTION",
    "DELETED_ACTION",
    "ENTITY_TYPE",
    "NeedsReviewItem",
    "OverrideNotFound",
    "PublicationAuthorNotFound",
    "StaleOverrideVersion",
    "UPDATED_ACTION",
    "UpsertOverrideCommand",
    "delete_override",
    "list_needs_review",
    "upsert_override",
]
