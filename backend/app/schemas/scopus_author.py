"""Scopus author schemas — M0 scaffold."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.common import TimestampMixin


class ScopusAuthorResponse(BaseModel):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class ScopusAuthorNameVariantResponse(BaseModel):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int