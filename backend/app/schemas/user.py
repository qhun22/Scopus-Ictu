"""Typed contracts for administrator-managed user accounts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


UserRole = Literal["ADMIN", "REVIEWER", "LECTURER"]
# An ADMIN creating a new account through this endpoint may only grant these
# two roles — never ADMIN — so one admin can never mint another admin by
# calling the account-creation API (see user_admin_service.create_user).
CreatableUserRole = Literal["REVIEWER", "LECTURER"]


class UserAdminCreate(BaseModel):
    """ADMIN-only account creation. No lecturer profile is required or created:
    ``lecturer_id`` is never accepted here, so an account may exist strictly
    read-only until a JSON import later links it (see migration f6a1b2c3d4e5)."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=256)
    role: CreatableUserRole


class UserAdminUpdate(BaseModel):
    """Optimistically versioned profile/account update."""

    version: int = Field(..., ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    role: UserRole | None = None
    staff_code: str | None = Field(default=None, max_length=50)
    academic_rank: str | None = Field(default=None, max_length=50)
    academic_degree: str | None = Field(default=None, max_length=50)
    position: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=150)
    faculty: str | None = Field(default=None, max_length=150)
    orcid: str | None = Field(default=None, max_length=19)


class VersionedUserAction(BaseModel):
    version: int = Field(..., ge=1)


class PasswordResetRequest(VersionedUserAction):
    new_password: str = Field(..., min_length=8, max_length=256)


class UserAdminResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: UserRole
    lecturer_id: uuid.UUID | None = None
    staff_code: str | None = None
    academic_rank: str | None = None
    academic_degree: str | None = None
    position: str | None = None
    department: str | None = None
    faculty: str | None = None
    orcid: str | None = None
    specialization: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    phone: str | None = None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    has_warning: bool = False
    warning_reason: str | None = None


class PasswordResetResponse(BaseModel):
    message: str
    user_id: uuid.UUID
    version: int
