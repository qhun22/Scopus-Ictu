"""Read-only dashboard summary endpoint — C2-A4."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard_queries import get_dashboard_summary

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_session)]
AdminUser = Annotated[User, Depends(require_role("ADMIN"))]


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Tổng hợp số liệu bảng điều khiển (chỉ ADMIN)",
)
def dashboard_summary(
    _user: AdminUser,
    db: DatabaseSession,
) -> DashboardSummaryResponse:
    try:
        return get_dashboard_summary(db)
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=503,
            detail="Dữ liệu bảng điều khiển tạm thời không khả dụng.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


__all__ = ["router"]
