"""Safe read-only DTO for review history — C2-A3."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ReviewHistoryStatus = Literal["PENDING", "ACCEPTED", "REJECTED", "SUPERSEDED"]


class ReviewHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: Literal["ACCEPT", "REJECT", "REOPEN"]
    from_status: ReviewHistoryStatus
    to_status: ReviewHistoryStatus
    reason: str | None
    created_at: datetime
    # Non-null: DB enforces reviewer_user_id NOT NULL + FK RESTRICT + display_name NOT NULL
    reviewer_display_name: str
    # Non-null: DB enforces lecturer_id NOT NULL + full_name NOT NULL
    lecturer_full_name: str
    lecturer_staff_code: str | None
    # Non-null: DB enforces scopus_author_id NOT NULL + scopus_id/preferred_name NOT NULL
    scopus_author_scopus_id: str
    scopus_author_preferred_name: str


class ReviewHistoryResponse(BaseModel):
    items: list[ReviewHistoryItem]
    total: int
    page: int
    page_size: int
