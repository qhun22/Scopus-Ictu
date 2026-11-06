"""Service layer for the user feedback-report intake queue (additive).

Thin wrapper: validates input, writes one row plus one AuditEvent, and
lists/resolves reports. Never touches publication_author_affiliation*,
candidates or identities -- resolving a report only records that an
ADMIN/REVIEWER looked at it; any real data fix happens through the existing
affiliation-override or candidate-review workflow, started separately by
that same person after reading the report.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.feedback import (
    FEEDBACK_CATEGORY_VALUES,
    FEEDBACK_STATUS_VALUES,
    FeedbackComment,
    FeedbackReadState,
    FeedbackReport,
    FeedbackReportSeen,
)
from app.models.governance import AuditEvent, User

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

STAFF_ROLES = ("ADMIN", "REVIEWER")

CREATED_ACTION = "FEEDBACK_REPORT_CREATED"
RESOLVED_ACTION = "FEEDBACK_REPORT_RESOLVED"
COMMENT_ADDED_ACTION = "FEEDBACK_COMMENT_ADDED"


class FeedbackError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


@dataclass(frozen=True, slots=True)
class CreateReportCommand:
    reporter_user_id: uuid.UUID
    category: str
    publication_eid: str | None
    message: str


@dataclass(frozen=True, slots=True)
class ResolveReportCommand:
    report_id: uuid.UUID
    actor_user_id: uuid.UUID
    status: str
    admin_note: str | None


@dataclass(frozen=True, slots=True)
class AddCommentCommand:
    report_id: uuid.UUID
    author: User
    message: str


def create_report(db: Session, cmd: CreateReportCommand) -> FeedbackReport:
    if cmd.category not in FEEDBACK_CATEGORY_VALUES:
        allowed = ", ".join(FEEDBACK_CATEGORY_VALUES)
        raise FeedbackError("INVALID_CATEGORY", f"Loại báo cáo phải là một trong: {allowed}.")
    if not cmd.message.strip():
        raise FeedbackError("MESSAGE_REQUIRED", "Cần mô tả vấn đề.")
    report = FeedbackReport(
        id=uuid.uuid4(),
        reporter_user_id=cmd.reporter_user_id,
        category=cmd.category,
        publication_eid=(cmd.publication_eid or "").strip() or None,
        message=cmd.message.strip(),
        status="OPEN",
    )
    db.add(report)
    db.flush()
    db.add(
        AuditEvent(
            entity_type="feedback_report",
            entity_id=report.id,
            action=CREATED_ACTION,
            actor_type="USER",
            actor_user_id=cmd.reporter_user_id,
            event_metadata={
                "category": cmd.category,
                "publication_eid": report.publication_eid,
            },
        )
    )
    db.commit()
    db.refresh(report)
    return report


def list_reports(
    db: Session,
    *,
    status: str | None = None,
    reporter_user_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[FeedbackReport], int, int]:
    query = select(FeedbackReport)
    open_query = select(func.count()).select_from(FeedbackReport).where(
        FeedbackReport.status == "OPEN"
    )
    if reporter_user_id is not None:
        query = query.where(FeedbackReport.reporter_user_id == reporter_user_id)
        open_query = open_query.where(FeedbackReport.reporter_user_id == reporter_user_id)
    if status is not None:
        if status not in FEEDBACK_STATUS_VALUES:
            allowed = ", ".join(FEEDBACK_STATUS_VALUES)
            raise FeedbackError("INVALID_STATUS", f"Trạng thái phải là một trong: {allowed}.")
        query = query.where(FeedbackReport.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    open_count = db.scalar(open_query) or 0
    rows = db.scalars(
        query.order_by(FeedbackReport.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(rows), int(total), int(open_count)


def get_report(db: Session, report_id: uuid.UUID) -> FeedbackReport:
    report = db.get(FeedbackReport, report_id)
    if report is None:
        raise FeedbackError("REPORT_NOT_FOUND", "Không tìm thấy báo cáo này.", status_code=404)
    return report


def ensure_can_view_report(report: FeedbackReport, viewer: User) -> None:
    if viewer.role in STAFF_ROLES or viewer.id == report.reporter_user_id:
        return
    raise FeedbackError(
        "REPORT_ACCESS_DENIED", "Bạn không có quyền xem báo cáo này.", status_code=403
    )


def comment_counts(db: Session, report_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not report_ids:
        return {}
    rows = db.execute(
        select(FeedbackComment.report_id, func.count())
        .where(FeedbackComment.report_id.in_(report_ids))
        .group_by(FeedbackComment.report_id)
    ).all()
    return {row[0]: int(row[1]) for row in rows}


def mark_report_seen(db: Session, user_id: uuid.UUID, report_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    state = db.get(FeedbackReportSeen, (user_id, report_id))
    if state is None:
        db.add(FeedbackReportSeen(user_id=user_id, report_id=report_id, last_seen_at=now))
    else:
        state.last_seen_at = now
    db.commit()


def unread_report_ids(
    db: Session, report_ids: list[uuid.UUID], viewer: User
) -> set[uuid.UUID]:
    """Which of `report_ids` have activity `viewer` has not opened yet, so the
    UI can point at the specific report instead of only a single queue-wide
    dot. Mirrors `has_unread`'s "who counts as the other side" rule, but
    per-report: a report never opened by this viewer defaults to epoch, so it
    counts as unread as soon as it has qualifying activity.
    """
    if not report_ids:
        return set()
    seen_rows = db.execute(
        select(FeedbackReportSeen.report_id, FeedbackReportSeen.last_seen_at).where(
            FeedbackReportSeen.user_id == viewer.id,
            FeedbackReportSeen.report_id.in_(report_ids),
        )
    ).all()
    last_seen = {row[0]: row[1] for row in seen_rows}

    unread: set[uuid.UUID] = set()
    if viewer.role in STAFF_ROLES:
        rows = db.execute(
            select(FeedbackReport.id, FeedbackReport.created_at).where(
                FeedbackReport.id.in_(report_ids)
            )
        ).all()
        for report_id, created_at in rows:
            if created_at > last_seen.get(report_id, EPOCH):
                unread.add(report_id)
        reply_rows = db.execute(
            select(FeedbackComment.report_id, FeedbackComment.created_at)
            .join(User, User.id == FeedbackComment.author_user_id)
            .where(
                FeedbackComment.report_id.in_(report_ids),
                User.role.notin_(STAFF_ROLES),
            )
        ).all()
    else:
        reply_rows = db.execute(
            select(FeedbackComment.report_id, FeedbackComment.created_at)
            .join(User, User.id == FeedbackComment.author_user_id)
            .where(
                FeedbackComment.report_id.in_(report_ids),
                User.role.in_(STAFF_ROLES),
            )
        ).all()

    for report_id, created_at in reply_rows:
        if created_at > last_seen.get(report_id, EPOCH):
            unread.add(report_id)
    return unread


def resolve_report(db: Session, cmd: ResolveReportCommand) -> FeedbackReport:
    if cmd.status not in ("RESOLVED", "DISMISSED"):
        raise FeedbackError("INVALID_STATUS", "Trạng thái xử lý phải là RESOLVED hoặc DISMISSED.")
    report = db.get(FeedbackReport, cmd.report_id)
    if report is None:
        raise FeedbackError("REPORT_NOT_FOUND", "Không tìm thấy báo cáo này.", status_code=404)
    if report.status != "OPEN":
        raise FeedbackError(
            "REPORT_ALREADY_CLOSED", "Báo cáo này đã được xử lý trước đó.", status_code=409
        )
    report.status = cmd.status
    report.admin_note = (cmd.admin_note or "").strip() or None
    report.resolved_by_user_id = cmd.actor_user_id
    report.resolved_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            entity_type="feedback_report",
            entity_id=report.id,
            action=RESOLVED_ACTION,
            actor_type="USER",
            actor_user_id=cmd.actor_user_id,
            event_metadata={"status": cmd.status, "admin_note": report.admin_note},
        )
    )
    db.commit()
    db.refresh(report)
    return report


def add_comment(db: Session, cmd: AddCommentCommand) -> FeedbackComment:
    report = get_report(db, cmd.report_id)
    ensure_can_view_report(report, cmd.author)
    if not cmd.message.strip():
        raise FeedbackError("MESSAGE_REQUIRED", "Cần nhập nội dung trao đổi.")
    comment = FeedbackComment(
        id=uuid.uuid4(),
        report_id=report.id,
        author_user_id=cmd.author.id,
        message=cmd.message.strip(),
    )
    db.add(comment)
    db.flush()
    db.add(
        AuditEvent(
            entity_type="feedback_report",
            entity_id=report.id,
            action=COMMENT_ADDED_ACTION,
            actor_type="USER",
            actor_user_id=cmd.author.id,
            event_metadata={"comment_id": str(comment.id)},
        )
    )
    db.commit()
    db.refresh(comment)
    return comment


def list_comments(db: Session, report_id: uuid.UUID, viewer: User) -> list[FeedbackComment]:
    report = get_report(db, report_id)
    ensure_can_view_report(report, viewer)
    rows = db.scalars(
        select(FeedbackComment)
        .where(FeedbackComment.report_id == report_id)
        .order_by(FeedbackComment.created_at.asc())
    ).all()
    return list(rows)


def mark_seen(db: Session, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    state = db.get(FeedbackReadState, user_id)
    if state is None:
        db.add(FeedbackReadState(user_id=user_id, last_seen_at=now))
    else:
        state.last_seen_at = now
    db.commit()


def has_unread(db: Session, user: User) -> bool:
    state = db.get(FeedbackReadState, user.id)
    since = state.last_seen_at if state is not None else EPOCH

    if user.role in STAFF_ROLES:
        # Staff cares about every report: a brand-new one, or a reply from
        # the (non-staff) reporter who filed it.
        new_report = db.scalar(
            select(FeedbackReport.id).where(FeedbackReport.created_at > since).limit(1)
        )
        if new_report is not None:
            return True
        reporter_reply = db.scalar(
            select(FeedbackComment.id)
            .join(User, User.id == FeedbackComment.author_user_id)
            .where(FeedbackComment.created_at > since, User.role.notin_(STAFF_ROLES))
            .limit(1)
        )
        return reporter_reply is not None

    # A reporter only cares about staff replying on a report they filed.
    staff_reply = db.scalar(
        select(FeedbackComment.id)
        .join(FeedbackReport, FeedbackReport.id == FeedbackComment.report_id)
        .join(User, User.id == FeedbackComment.author_user_id)
        .where(
            FeedbackReport.reporter_user_id == user.id,
            FeedbackComment.created_at > since,
            User.role.in_(STAFF_ROLES),
        )
        .limit(1)
    )
    return staff_reply is not None


def reporter_display_name(user: User | None) -> str:
    if user is None:
        return "—"
    return user.display_name or user.email
