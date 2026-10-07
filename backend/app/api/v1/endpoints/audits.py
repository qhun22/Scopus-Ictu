"""Audit endpoints — C2-A1 (read-only, ADMIN only).

ADR-003: audit is append-only. This module provides paginated read access.
No AuditEvent rows are created here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_role
from app.core.database import get_session
from app.models.governance import User
from app.schemas.audit import AuditListResponse
from app.services.audit_queries import list_audits

router = APIRouter()

_ADMIN = Depends(require_role("ADMIN"))


@router.get(
    "",
    response_model=AuditListResponse,
    summary="List audit events (ADMIN only)",
)
def get_audit_list(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    action: Annotated[str | None, Query(max_length=64)] = None,
    entity_type: Annotated[str | None, Query(max_length=100)] = None,
    actor_type: Annotated[str | None, Query(pattern="^(USER|SYSTEM)$")] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    _current_user: User = _ADMIN,
    session: Session = Depends(get_session),
) -> AuditListResponse:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_DATE_RANGE", "message": "date_from must be <= date_to"},
        )

    try:
        return list_audits(
            session,
            page=page,
            page_size=page_size,
            action=action,
            entity_type=entity_type,
            actor_type=actor_type,
            date_from=date_from,
            date_to=date_to,
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DATABASE_UNAVAILABLE", "message": "Database unavailable"},
        )
