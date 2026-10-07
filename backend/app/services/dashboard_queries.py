"""Read-only aggregation layer for the dashboard summary API — C2-A4.

All queries are read-only; no writes are performed here.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, ScopusAuthor
from app.models.scopus_raw import ScopusImport
from app.schemas.dashboard import DashboardSummaryResponse, LatestScopusImportSummary
from app.services.audit_queries import list_audits
from app.services.candidate_review_queries import current_reviewable_candidates_subquery

_ALL_IDENTITY_STATUSES = ("CANDIDATE", "APPROVED", "REJECTED", "REVOKED")


def get_dashboard_summary(session: Session) -> DashboardSummaryResponse:
    total_publications = session.execute(
        select(func.count()).select_from(Publication)
    ).scalar_one()

    total_lecturers = session.execute(
        select(func.count()).select_from(Lecturer)
    ).scalar_one()

    active_lecturers = session.execute(
        select(func.count()).select_from(Lecturer).where(Lecturer.is_active.is_(True))
    ).scalar_one()

    total_scopus_authors = session.execute(
        select(func.count()).select_from(ScopusAuthor)
    ).scalar_one()

    identity_rows = session.execute(
        select(
            LecturerScopusIdentity.status,
            func.count(LecturerScopusIdentity.id).label("cnt"),
        ).group_by(LecturerScopusIdentity.status)
    ).all()
    identity_counts: dict = {s: 0 for s in _ALL_IDENTITY_STATUSES}
    for row in identity_rows:
        if row.status in identity_counts:
            identity_counts[row.status] = row.cnt

    reviewable = current_reviewable_candidates_subquery("PENDING")
    pending_review_count = session.execute(
        select(func.count()).select_from(reviewable)
    ).scalar_one()

    import_row = session.execute(
        select(ScopusImport)
        .order_by(ScopusImport.created_at.desc(), ScopusImport.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    latest_scopus_import = (
        LatestScopusImportSummary.model_validate(import_row) if import_row else None
    )

    recent_audit_actions = list_audits(session, page=1, page_size=5).items

    return DashboardSummaryResponse(
        total_publications=total_publications,
        total_lecturers=total_lecturers,
        active_lecturers=active_lecturers,
        total_scopus_authors=total_scopus_authors,
        identity_counts=identity_counts,
        pending_review_count=pending_review_count,
        latest_scopus_import=latest_scopus_import,
        recent_audit_actions=recent_audit_actions,
    )
