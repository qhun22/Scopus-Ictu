"""Paginated read-only query layer for review history — C2-A3."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.candidate import LecturerScopusCandidate, LecturerScopusCandidateReview
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.schemas.review_history_api import ReviewHistoryItem, ReviewHistoryResponse


def list_review_history(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ReviewHistoryResponse:
    page_size = min(page_size, 100)
    offset = (page - 1) * page_size

    filters = []
    if action is not None:
        filters.append(LecturerScopusCandidateReview.action == action)
    if date_from is not None:
        filters.append(LecturerScopusCandidateReview.created_at >= date_from)
    if date_to is not None:
        filters.append(LecturerScopusCandidateReview.created_at <= date_to)

    # All joins are INNER: reviewer_user_id NOT NULL FK RESTRICT, lecturer_id NOT NULL,
    # scopus_author_id NOT NULL — nulls are structurally impossible.
    base = (
        select(LecturerScopusCandidateReview)
        .join(
            LecturerScopusCandidate,
            LecturerScopusCandidateReview.candidate_id == LecturerScopusCandidate.id,
        )
        .join(Lecturer, Lecturer.id == LecturerScopusCandidate.lecturer_id)
        .join(ScopusAuthor, ScopusAuthor.id == LecturerScopusCandidate.scopus_author_id)
        .join(User, LecturerScopusCandidateReview.reviewer_user_id == User.id)
    )
    if filters:
        base = base.where(*filters)

    total = session.execute(
        select(func.count()).select_from(base.order_by(None).subquery())
    ).scalar_one()

    rows = session.execute(
        select(
            LecturerScopusCandidateReview.id,
            LecturerScopusCandidateReview.action,
            LecturerScopusCandidateReview.from_status,
            LecturerScopusCandidateReview.to_status,
            LecturerScopusCandidateReview.reason,
            LecturerScopusCandidateReview.created_at,
            User.display_name.label("reviewer_display_name"),
            Lecturer.full_name.label("lecturer_full_name"),
            Lecturer.staff_code.label("lecturer_staff_code"),
            ScopusAuthor.scopus_id.label("scopus_author_scopus_id"),
            ScopusAuthor.preferred_name.label("scopus_author_preferred_name"),
        )
        .join(
            LecturerScopusCandidate,
            LecturerScopusCandidateReview.candidate_id == LecturerScopusCandidate.id,
        )
        .join(Lecturer, Lecturer.id == LecturerScopusCandidate.lecturer_id)
        .join(ScopusAuthor, ScopusAuthor.id == LecturerScopusCandidate.scopus_author_id)
        .join(User, LecturerScopusCandidateReview.reviewer_user_id == User.id)
        .where(*filters)
        .order_by(
            LecturerScopusCandidateReview.created_at.desc(),
            LecturerScopusCandidateReview.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
    ).all()

    items = [ReviewHistoryItem(**row._mapping) for row in rows]
    return ReviewHistoryResponse(items=items, total=total, page=page, page_size=page_size)
