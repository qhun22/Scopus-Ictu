"""Audit schemas — M0 scaffold.

ADR-003: audit is append-only.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None = None
    action: str
    entity_type: str | None = None
    entity_id: int | None = None
    payload: dict | None = None
    occurred_at: datetime | None = None