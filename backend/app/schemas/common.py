"""Common schema primitives — M0 scaffold."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TimestampMixin(BaseModel):
    """Mixin for created_at / updated_at timestamps."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime | None = None
    updated_at: datetime | None = None


class PaginationParams(BaseModel):
    """M0 pagination params (stub)."""

    page: int = 1
    page_size: int = 50


class PageResponse(BaseModel):
    """M0 generic paginated response (stub)."""

    items: list[Any] = []
    total: int = 0
    page: int = 1
    page_size: int = 50