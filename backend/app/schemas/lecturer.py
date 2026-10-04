"""Request and response schemas for lecturer account management."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import TimestampMixin
class LecturerBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=3, max_length=255)
    # staff_code is OPTIONAL. A blank/omitted value is stored as NULL.
    # Uniqueness is enforced at the DB level (partial unique index).
    staff_code: str | None = Field(default=None, max_length=50)
    role: str = Field(default="LECTURER", min_length=1, max_length=20)
    academic_degree: str | None = Field(default=None, max_length=50)
    department: str | None = Field(default=None, max_length=150)


class LecturerCreate(LecturerBase):
    password: str = Field(..., min_length=8, max_length=256)


class LecturerUpdate(BaseModel):
    version: int = Field(..., ge=1)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    # Update semantics:
    #   * omitted  -> field unchanged
    #   * None     -> clear field to NULL
    #   * ""       -> clear field to NULL
    #   * non-empty -> trim, validate uniqueness against OTHER lecturer IDs
    staff_code: str | None = Field(default=None, max_length=50)
    role: str | None = Field(default=None, min_length=1, max_length=20)
    academic_rank: str | None = Field(default=None, max_length=50)
    academic_degree: str | None = Field(default=None, max_length=50)
    position: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=150)
    faculty: str | None = Field(default=None, max_length=150)
    orcid: str | None = Field(default=None, max_length=19)
    grant_account: bool = False
    password: str | None = Field(default=None, min_length=8, max_length=256)


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


# ---------------------------------------------------------------------------
# M2.5A — ICTU lecturer dataset import pipeline
# ---------------------------------------------------------------------------
class LecturerDatasetConflict(BaseModel):
    """Single conflict surfaced by the preview/import endpoints."""

    record_full_name: str
    matched_by: str
    existing_id: str
    existing_full_name: str
    existing_email: str | None = None


class LecturerDatasetMetadata(BaseModel):
    """Subset of the dataset envelope returned to the client."""

    name: str | None = None
    schema_version: str
    institution: str | None = None
    source: str | None = None
    source_url: str | None = None
    source_system: str | None = None
    generated_at: str | None = None
    parser_version: str | None = None
    record_count: int


class LecturerPreviewResponse(BaseModel):
    """Read-only diff between an uploaded dataset and the database."""

    dataset: LecturerDatasetMetadata
    summary: dict
    conflicts: list[LecturerDatasetConflict]
    filename: str
    parser_version: str


class LecturerImportResponse(BaseModel):
    """Result of an atomic import."""

    dataset: LecturerDatasetMetadata
    summary: dict
    conflicts: list[LecturerDatasetConflict]
    snapshot_ids: list[str]
    filename: str
    parser_version: str


class LecturerAccount(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    is_active: bool
    version: int


class LecturerStats(BaseModel):
    total_lecturers: int
    account_linked: int
    account_not_linked: int
    account_locked: int
    warning_count: int = 0


class LecturerListItem(BaseModel):
    """One row in the server-side lecturer listing."""

    id: uuid.UUID
    full_name: str
    full_name_normalized: str
    staff_code: str | None = None
    institutional_email: str | None = None
    academic_degree: str | None = None
    academic_rank: str | None = None
    position: str | None = None
    faculty: str | None = None
    department: str | None = None
    orcid: str | None = None
    profile_url: str | None = None
    is_active: bool = True
    has_user_account: bool = False
    has_warning: bool = False
    warning_reason: str | None = None
    account: LecturerAccount | None = None
    version: int
    created_at: str | None = None
    updated_at: str | None = None


class LecturerListResponse(BaseModel):
    items: list[LecturerListItem]
    total: int
    page: int
    page_size: int
    stats: LecturerStats | None = None
