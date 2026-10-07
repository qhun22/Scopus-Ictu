"""Audit read queries — C2-A1.

Provides a single paginated list function used by the audit endpoint.
No writes are performed here; audit is append-only (ADR-003).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.governance import AuditEvent, User
from app.schemas.audit import AuditListItem, AuditListResponse

_MAX_PAGE_SIZE = 100
_DEFAULT_PAGE_SIZE = 50


def _normalize_str_filter(value: str | None) -> str | None:
    """Trim whitespace; return None if empty or None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def list_audits(
    session: Session,
    *,
    page: int = 1,
    page_size: int = _DEFAULT_PAGE_SIZE,
    action: str | None = None,
    entity_type: str | None = None,
    actor_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditListResponse:
    """Return a paginated, filtered list of audit events.

    action and entity_type are trimmed; empty-after-trim treated as absent.
    Actor LEFT JOIN: inactive users still resolve display_name because
    the FK is RESTRICT (no deleted users exist in the system).
    """
    page_size = min(page_size, _MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

    action = _normalize_str_filter(action)
    entity_type = _normalize_str_filter(entity_type)

    filters = _build_filters(action, entity_type, actor_type, date_from, date_to)

    total: int = session.execute(
        select(func.count()).select_from(AuditEvent).where(*filters)
    ).scalar_one()

    rows = session.execute(
        select(
            AuditEvent.id,
            AuditEvent.entity_type,
            AuditEvent.action,
            AuditEvent.actor_type,
            User.display_name.label("actor_display_name"),
            AuditEvent.actor_service,
            AuditEvent.reason,
            AuditEvent.created_at,
        )
        .outerjoin(User, AuditEvent.actor_user_id == User.id)
        .where(*filters)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .offset(offset)
        .limit(page_size)
    ).all()

    items = [
        AuditListItem(
            id=row.id,
            entity_type=row.entity_type,
            action=row.action,
            actor_type=row.actor_type,
            actor_display_name=row.actor_display_name,
            actor_service=row.actor_service,
            reason=row.reason,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return AuditListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


def _build_filters(
    action: str | None,
    entity_type: str | None,
    actor_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list:
    filters = []
    if action is not None:
        filters.append(AuditEvent.action == action)
    if entity_type is not None:
        filters.append(AuditEvent.entity_type == entity_type)
    if actor_type is not None:
        filters.append(AuditEvent.actor_type == actor_type)
    if date_from is not None:
        filters.append(AuditEvent.created_at >= date_from)
    if date_to is not None:
        filters.append(AuditEvent.created_at <= date_to)
    return filters
