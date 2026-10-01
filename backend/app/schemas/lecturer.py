"""Lecturer schemas — M0 scaffold."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.common import TimestampMixin


class LecturerBase(BaseModel):
    """M0 stub. TODO(M1): full_name, email, employee_id, faculty, etc."""

    pass


class LecturerCreate(LecturerBase):
    """M0 stub."""

    pass


class LecturerUpdate(BaseModel):
    """M0 stub."""

    pass


class LecturerResponse(LecturerBase, TimestampMixin):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class LecturerSourceSnapshotResponse(BaseModel):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class LecturerKnownPublicationResponse(BaseModel):
    """M0 stub."""

    model_config = ConfigDict(from_attributes=True)

    id: int