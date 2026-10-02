"""Public contracts for persistent user notifications."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


NotificationType = Literal[
    "PROFILE_UPDATED",
    "ROLE_CHANGED",
    "ACCOUNT_LOCKED",
    "ACCOUNT_UNLOCKED",
    "PASSWORD_RESET",
]


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    metadata: dict = Field(default_factory=dict)
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None


class NotificationReadResponse(BaseModel):
    id: uuid.UUID
    is_read: Literal[True]
    read_at: datetime
