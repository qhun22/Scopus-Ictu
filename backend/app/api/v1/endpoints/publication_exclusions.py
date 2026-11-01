"""ADMIN endpoints for per-lecturer publication exclusions (G09). Thin: validate, delegate."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.services.publication_exclusions import (
    ExclusionRecord,
    PublicationExclusionError,
    PublicationExclusionService,
)

router = APIRouter()
AdminUser = Annotated[User, Depends(require_role("ADMIN"))]
DatabaseSession = Annotated[Session, Depends(get_session)]


class ExclusionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lecturer_id: uuid.UUID
    publication_id: uuid.UUID
    reason: str = Field(..., min_length=1, max_length=4000)


class ExclusionResponse(BaseModel):
    lecturer_id: uuid.UUID
    publication_id: uuid.UUID
    action: str
    reason: str
    acted_by_user_id: uuid.UUID
    created_at: datetime


class ExclusionListResponse(BaseModel):
    items: list[ExclusionResponse]


def _to_response(record: ExclusionRecord) -> ExclusionResponse:
    return ExclusionResponse(
        lecturer_id=record.lecturer_id, publication_id=record.publication_id,
        action=record.action, reason=record.reason,
        acted_by_user_id=record.acted_by_user_id, created_at=record.created_at)


def _run(db: Session, call) -> ExclusionResponse:
    try:
        return _to_response(call())
    except PublicationExclusionError as exc:
        db.rollback()
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(status_code=409, detail="Exclusion conflicted with persisted state.",
                       code="EXCLUSION_PERSISTENCE_CONFLICT") from exc


@router.get("", response_model=ExclusionListResponse,
            summary="Publications currently excluded from one lecturer")
def list_exclusions(
    _admin: AdminUser, db: DatabaseSession,
    lecturer_id: Annotated[uuid.UUID, Query()],
) -> ExclusionListResponse:
    items = PublicationExclusionService(db).list_excluded(lecturer_id)
    return ExclusionListResponse(items=[_to_response(i) for i in items])


@router.post("", response_model=ExclusionResponse,
             summary="Exclude one publication from one lecturer (reason required)")
def exclude_publication(request: ExclusionRequest, admin: AdminUser,
                        db: DatabaseSession) -> ExclusionResponse:
    service = PublicationExclusionService(db)
    return _run(db, lambda: service.exclude(
        request.lecturer_id, request.publication_id, admin.id, request.reason))


@router.post("/restore", response_model=ExclusionResponse,
             summary="Restore a previously excluded publication (reason required)")
def restore_publication(request: ExclusionRequest, admin: AdminUser,
                        db: DatabaseSession) -> ExclusionResponse:
    service = PublicationExclusionService(db)
    return _run(db, lambda: service.restore(
        request.lecturer_id, request.publication_id, admin.id, request.reason))
