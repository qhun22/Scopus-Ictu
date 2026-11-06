"""User feedback-report intake queue: any logged-in user files a report
(most commonly "this unit looks wrong" or "this author link looks wrong");
ADMIN/REVIEWER reads the queue and marks it resolved or dismissed. Filing or
resolving a report never itself changes publication, affiliation or identity
data -- see app.services.feedback_service.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.feedback import FeedbackReport
from app.models.governance import User
from app.schemas.feedback_api import (
    CreateFeedbackReportRequest,
    FeedbackReportListResponse,
    FeedbackReportRead,
    ResolveFeedbackReportRequest,
)
from app.services import feedback_service

router = APIRouter()

CurrentUser = Annotated[User, Depends(get_current_user)]
StaffUser = Annotated[User, Depends(require_role("ADMIN", "REVIEWER"))]
DatabaseSession = Annotated[Session, Depends(get_session)]


def _db_error(detail: str) -> APIError:
    return APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail, code="DATABASE_UNAVAILABLE"
    )


def _read(report: FeedbackReport, reporter: User | None) -> FeedbackReportRead:
    return FeedbackReportRead(
        id=report.id,
        reporter_user_id=report.reporter_user_id,
        reporter_name=feedback_service.reporter_display_name(reporter),
        category=report.category,
        publication_eid=report.publication_eid,
        message=report.message,
        status=report.status,
        admin_note=report.admin_note,
        resolved_by_user_id=report.resolved_by_user_id,
        resolved_at=report.resolved_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.post(
    "/reports",
    response_model=FeedbackReportRead,
    status_code=status.HTTP_201_CREATED,
    summary="File a new issue report (any logged-in role)",
)
def create_report(
    body: CreateFeedbackReportRequest, current_user: CurrentUser, db: DatabaseSession
) -> FeedbackReportRead:
    try:
        report = feedback_service.create_report(
            db,
            feedback_service.CreateReportCommand(
                reporter_user_id=current_user.id,
                category=body.category,
                publication_eid=body.publication_eid,
                message=body.message,
            ),
        )
    except feedback_service.FeedbackError as exc:
        db.rollback()
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error("Không thể gửi báo cáo.") from exc
    return _read(report, current_user)


@router.get(
    "/reports",
    response_model=FeedbackReportListResponse,
    summary="List issue reports (ADMIN/REVIEWER)",
)
def list_reports(
    _staff: StaffUser,
    db: DatabaseSession,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FeedbackReportListResponse:
    try:
        rows, total, open_count = feedback_service.list_reports(
            db, status=status_filter, limit=limit, offset=offset
        )
        reporter_ids = {row.reporter_user_id for row in rows}
        reporters = {
            u.id: u for u in db.query(User).filter(User.id.in_(reporter_ids)).all()
        } if reporter_ids else {}
    except feedback_service.FeedbackError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        raise _db_error("Không thể tải danh sách báo cáo.") from exc
    return FeedbackReportListResponse(
        items=[_read(row, reporters.get(row.reporter_user_id)) for row in rows],
        total=total,
        open_count=open_count,
    )


@router.post(
    "/reports/{report_id}/resolve",
    response_model=FeedbackReportRead,
    summary="Mark a report RESOLVED or DISMISSED (ADMIN/REVIEWER)",
)
def resolve_report(
    report_id: uuid.UUID,
    body: ResolveFeedbackReportRequest,
    staff: StaffUser,
    db: DatabaseSession,
) -> FeedbackReportRead:
    try:
        report = feedback_service.resolve_report(
            db,
            feedback_service.ResolveReportCommand(
                report_id=report_id,
                actor_user_id=staff.id,
                status=body.status,
                admin_note=body.admin_note,
            ),
        )
        reporter = db.get(User, report.reporter_user_id)
    except feedback_service.FeedbackError as exc:
        db.rollback()
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error("Không thể cập nhật báo cáo.") from exc
    return _read(report, reporter)
