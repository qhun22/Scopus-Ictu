"""Safe read-only DTO for review history — C2-A3."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReviewHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: Literal["ACCEPT", "REJECT", "REOPEN"]
    from_status: str
    to_status: str
    reason: str | None
    created_at: datetime
    reviewer_display_name: str | None
    lecturer_full_name: str | None
    lecturer_staff_code: str | None
    scopus_author_scopus_id: str | None
    scopus_author_preferred_name: str | None


class ReviewHistoryResponse(BaseModel):
    items: list[ReviewHistoryItem]
    total: int
    page: int
    page_size: int
