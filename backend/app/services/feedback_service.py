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

from app.models.feedback import FEEDBACK_CATEGORY_VALUES, FEEDBACK_STATUS_VALUES, FeedbackReport
from app.models.governance import AuditEvent, User

CREATED_ACTION = "FEEDBACK_REPORT_CREATED"
RESOLVED_ACTION = "FEEDBACK_REPORT_RESOLVED"


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
    db: Session, *, status: str | None = None, limit: int = 100, offset: int = 0
) -> tuple[list[FeedbackReport], int, int]:
    query = select(FeedbackReport)
    if status is not None:
        if status not in FEEDBACK_STATUS_VALUES:
            allowed = ", ".join(FEEDBACK_STATUS_VALUES)
            raise FeedbackError("INVALID_STATUS", f"Trạng thái phải là một trong: {allowed}.")
        query = query.where(FeedbackReport.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    open_count = db.scalar(
        select(func.count()).select_from(FeedbackReport).where(FeedbackReport.status == "OPEN")
    ) or 0
    rows = db.scalars(
        query.order_by(FeedbackReport.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(rows), int(total), int(open_count)


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


def reporter_display_name(user: User | None) -> str:
    if user is None:
        return "—"
    return user.display_name or user.email
