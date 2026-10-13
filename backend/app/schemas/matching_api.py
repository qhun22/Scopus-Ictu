"""Response/request shapes for ADMIN candidate generation and Craw ingestion."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class GenerationRunResponse(BaseModel):
    run_id: uuid.UUID
    run_status: str
    candidate_roots: int
    observations: int
    evidence: int
    idempotent_replay: bool
    name_candidates: int
    craw_assisted_candidates: int
    craw_unattributed: int
    publication_conflicts: int


class CrawPreviewResponse(BaseModel):
    fingerprint: str
    can_apply: bool
    blocked_reason: str | None
    stats: dict[str, Any]
    preview: dict[str, Any]
    blocking: list[str]


class CrawApplyRequest(BaseModel):
    fingerprint: str
    confirm: bool = False


class CrawApplyResponse(BaseModel):
    run_id: str
    fingerprint: str
    result: dict[str, Any]
