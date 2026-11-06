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
from app.models.feedback import FeedbackComment, FeedbackReport
from app.models.governance import User
from app.schemas.feedback_api import (
    CreateFeedbackCommentRequest,
    CreateFeedbackReportRequest,
    FeedbackCommentListResponse,
    FeedbackCommentRead,
    FeedbackReportListResponse,
    FeedbackReportRead,
    FeedbackUnreadResponse,
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


def _read(
    report: FeedbackReport, reporter: User | None, comment_count: int = 0
) -> FeedbackReportRead:
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
        comment_count=comment_count,
    )


def _comment_read(comment: FeedbackComment, author: User | None) -> FeedbackCommentRead:
    return FeedbackCommentRead(
        id=comment.id,
        report_id=comment.report_id,
        author_user_id=comment.author_user_id,
        author_name=feedback_service.reporter_display_name(author),
        is_staff_author=bool(author and author.role in feedback_service.STAFF_ROLES),
        message=comment.message,
        created_at=comment.created_at,
    )


@router.get(
    "/unread",
    response_model=FeedbackUnreadResponse,
    summary="Whether the current user has unseen feedback activity (any logged-in role)",
)
def get_unread(current_user: CurrentUser, db: DatabaseSession) -> FeedbackUnreadResponse:
    try:
        unread = feedback_service.has_unread(db, current_user)
    except SQLAlchemyError as exc:
        raise _db_error("Không thể kiểm tra thông báo báo lỗi.") from exc
    return FeedbackUnreadResponse(has_unread=unread)


@router.post(
    "/mark-seen",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark the feedback queue as seen by the current user (any logged-in role)",
)
def mark_seen(current_user: CurrentUser, db: DatabaseSession) -> None:
    try:
        feedback_service.mark_seen(db, current_user.id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error("Không thể cập nhật trạng thái đã xem.") from exc


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
        counts = feedback_service.comment_counts(db, [row.id for row in rows])
    except feedback_service.FeedbackError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        raise _db_error("Không thể tải danh sách báo cáo.") from exc
    return FeedbackReportListResponse(
        items=[
            _read(row, reporters.get(row.reporter_user_id), counts.get(row.id, 0))
            for row in rows
        ],
        total=total,
        open_count=open_count,
    )


@router.get(
    "/reports/mine",
    response_model=FeedbackReportListResponse,
    summary="List my own issue reports (any logged-in role)",
)
def list_my_reports(
    current_user: CurrentUser,
    db: DatabaseSession,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FeedbackReportListResponse:
    try:
        rows, total, open_count = feedback_service.list_reports(
            db,
            status=status_filter,
            reporter_user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
        counts = feedback_service.comment_counts(db, [row.id for row in rows])
    except feedback_service.FeedbackError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        raise _db_error("Không thể tải danh sách báo cáo của bạn.") from exc
    return FeedbackReportListResponse(
        items=[_read(row, current_user, counts.get(row.id, 0)) for row in rows],
        total=total,
        open_count=open_count,
    )


@router.get(
    "/reports/{report_id}",
    response_model=FeedbackReportRead,
    summary="Get one issue report (the reporter, or ADMIN/REVIEWER)",
)
def get_report(
    report_id: uuid.UUID, current_user: CurrentUser, db: DatabaseSession
) -> FeedbackReportRead:
    try:
        report = feedback_service.get_report(db, report_id)
        feedback_service.ensure_can_view_report(report, current_user)
        reporter = (
            current_user
            if report.reporter_user_id == current_user.id
            else db.get(User, report.reporter_user_id)
        )
        counts = feedback_service.comment_counts(db, [report.id])
    except feedback_service.FeedbackError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        raise _db_error("Không thể tải báo cáo.") from exc
    return _read(report, reporter, counts.get(report.id, 0))


@router.get(
    "/reports/{report_id}/comments",
    response_model=FeedbackCommentListResponse,
    summary="List the comment thread on a report (the reporter, or ADMIN/REVIEWER)",
)
def list_comments(
    report_id: uuid.UUID, current_user: CurrentUser, db: DatabaseSession
) -> FeedbackCommentListResponse:
    try:
        comments = feedback_service.list_comments(db, report_id, current_user)
        author_ids = {c.author_user_id for c in comments}
        authors = {
            u.id: u for u in db.query(User).filter(User.id.in_(author_ids)).all()
        } if author_ids else {}
    except feedback_service.FeedbackError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        raise _db_error("Không thể tải nội dung trao đổi.") from exc
    return FeedbackCommentListResponse(
        items=[_comment_read(c, authors.get(c.author_user_id)) for c in comments]
    )


@router.post(
    "/reports/{report_id}/comments",
    response_model=FeedbackCommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Reply on a report's thread (the reporter, or ADMIN/REVIEWER)",
)
def add_comment(
    report_id: uuid.UUID,
    body: CreateFeedbackCommentRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> FeedbackCommentRead:
    try:
        comment = feedback_service.add_comment(
            db,
            feedback_service.AddCommentCommand(
                report_id=report_id, author=current_user, message=body.message
            ),
        )
    except feedback_service.FeedbackError as exc:
        db.rollback()
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error("Không thể gửi trao đổi.") from exc
    return _comment_read(comment, current_user)


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
