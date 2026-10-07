"""Audit schemas — safe read-only DTO (C2-A1).

ADR-003: audit is append-only; this module only exposes the safe subset
of AuditEvent fields (no entity_id, actor_user_id, before_state,
after_state, event_metadata, ip_address, user_agent, request_id,
correlation_id).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditListItem(BaseModel):
    """Safe projection of a single AuditEvent row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    action: str
    actor_type: str
    actor_display_name: str | None
    actor_service: str | None
    reason: str | None
    created_at: datetime


class AuditListResponse(BaseModel):
    """Paginated audit log envelope."""

    items: list[AuditListItem]
    total: int
    page: int
    page_size: int
