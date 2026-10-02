"""Request and response schemas for lecturer account management."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import TimestampMixin


class LecturerBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=3, max_length=255)
    staff_code: str = Field(..., min_length=1, max_length=50)
    role: str = Field(default="LECTURER", min_length=1, max_length=20)
    academic_degree: str | None = Field(default=None, max_length=50)
    department: str | None = Field(default=None, max_length=150)


class LecturerCreate(LecturerBase):
    password: str = Field(..., min_length=8, max_length=256)


class LecturerUpdate(BaseModel):
    version: int = Field(..., ge=1)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    staff_code: str | None = Field(default=None, min_length=1, max_length=50)
    role: str | None = Field(default=None, min_length=1, max_length=20)
    academic_rank: str | None = Field(default=None, max_length=50)
    academic_degree: str | None = Field(default=None, max_length=50)
    position: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=150)
    faculty: str | None = Field(default=None, max_length=150)
    orcid: str | None = Field(default=None, max_length=19)


class LecturerResponse(LecturerBase, TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool = True


class LecturerDeleteResponse(BaseModel):
    message: str


class LecturerSourceSnapshotResponse(BaseModel):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class LecturerKnownPublicationResponse(BaseModel):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int
