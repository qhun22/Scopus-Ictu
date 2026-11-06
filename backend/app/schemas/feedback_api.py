"""Request/response shapes for the user feedback-report intake queue."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateFeedbackReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    publication_eid: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=1, max_length=4000)


class ResolveFeedbackReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    admin_note: str | None = Field(default=None, max_length=4000)


class FeedbackReportRead(BaseModel):
    id: uuid.UUID
    reporter_user_id: uuid.UUID
    reporter_name: str
    category: str
    publication_eid: str | None
    message: str
    status: str
    admin_note: str | None
    resolved_by_user_id: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    comment_count: int = 0


class FeedbackReportListResponse(BaseModel):
    items: list[FeedbackReportRead]
    total: int
    open_count: int


class CreateFeedbackCommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)


class FeedbackCommentRead(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    author_user_id: uuid.UUID
    author_name: str
    is_staff_author: bool
    message: str
    created_at: datetime


class FeedbackCommentListResponse(BaseModel):
    items: list[FeedbackCommentRead]


class FeedbackUnreadResponse(BaseModel):
    has_unread: bool
