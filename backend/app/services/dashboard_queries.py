"""Read-only aggregation layer for the dashboard summary API — C2-A4.

All queries are read-only; no writes are performed here.
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.affiliation import PublicationAuthorAffiliationResolution
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor
from app.models.scopus_raw import ScopusImport
from app.schemas.dashboard import (
    AffiliationCoverageResponse,
    DashboardChartsResponse,
    DashboardSummaryResponse,
    LatestScopusImportSummary,
    PublicationsByDocumentTypeItem,
    PublicationsByYearItem,
)
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


_LINK_STATUS_RANK = case(
    (PublicationAuthorAffiliationResolution.link_status == "VERIFIED", 3),
    (PublicationAuthorAffiliationResolution.link_status == "CORROBORATED", 2),
    (PublicationAuthorAffiliationResolution.link_status == "UNRESOLVED", 1),
    else_=0,
)


def get_dashboard_charts(session: Session) -> DashboardChartsResponse:
    """Read-only aggregates backing the Overview charts.

    publications_by_year / by_document_type count distinct Publication rows
    (not author positions). affiliation_coverage counts author *positions*
    (publication_authors rows), one row per position regardless of how many
    affiliation resolutions (sources) it has — matching the brief's
    requirement that a position with several organizations is still counted
    once.
    """

    year_rows = session.execute(
        select(Publication.year, func.count())
        .where(Publication.year.is_not(None))
        .group_by(Publication.year)
        .order_by(Publication.year.asc())
    ).all()
    publications_by_year = [
        PublicationsByYearItem(year=year, count=count) for year, count in year_rows
    ]
    publications_total_with_year = sum(item.count for item in publications_by_year)
    publications_total_without_year = session.execute(
        select(func.count()).select_from(Publication).where(Publication.year.is_(None))
    ).scalar_one()

    doc_type_rows = session.execute(
        select(
            func.coalesce(Publication.document_type, "UNSPECIFIED"),
            func.count(),
        )
        .group_by(func.coalesce(Publication.document_type, "UNSPECIFIED"))
        .order_by(func.count().desc())
    ).all()
    publications_by_document_type = [
        PublicationsByDocumentTypeItem(document_type=doc_type, count=count)
        for doc_type, count in doc_type_rows
    ]

    total_author_positions = session.execute(
        select(func.count()).select_from(PublicationAuthor)
    ).scalar_one()

    # For each publication_author_id, take its single best (highest-ranked)
    # resolution status — avoids double counting a position that has rows
    # from more than one source_system.
    best_status_subq = (
        select(
            PublicationAuthorAffiliationResolution.publication_author_id,
            func.max(_LINK_STATUS_RANK).label("best_rank"),
        )
        .group_by(PublicationAuthorAffiliationResolution.publication_author_id)
        .subquery()
    )
    by_status_rank_rows = session.execute(
        select(best_status_subq.c.best_rank, func.count())
        .group_by(best_status_subq.c.best_rank)
    ).all()
    rank_to_status = {3: "VERIFIED", 2: "CORROBORATED", 1: "UNRESOLVED"}
    by_link_status: dict[str, int] = {"VERIFIED": 0, "CORROBORATED": 0, "UNRESOLVED": 0}
    for rank, count in by_status_rank_rows:
        status_name = rank_to_status.get(rank)
        if status_name:
            by_link_status[status_name] = count

    positions_resolved = session.execute(
        select(func.count()).select_from(best_status_subq)
    ).scalar_one()

    # "Has affiliation" = best resolution is VERIFIED or CORROBORATED AND at
    # least one of its affiliation rows is actually present (not an ABSENT
    # outcome). A position whose only resolutions are UNRESOLVED, or whose
    # trusted resolution reports affiliation_presence='ABSENT', counts as
    # without-affiliation.
    positions_with_affiliation = session.execute(
        select(func.count(func.distinct(PublicationAuthorAffiliationResolution.publication_author_id)))
        .where(
            PublicationAuthorAffiliationResolution.link_status.in_(("VERIFIED", "CORROBORATED")),
            PublicationAuthorAffiliationResolution.affiliation_presence == "PRESENT",
        )
    ).scalar_one()
    positions_without_affiliation = total_author_positions - positions_with_affiliation

    return DashboardChartsResponse(
        publications_total_with_year=publications_total_with_year,
        publications_total_without_year=publications_total_without_year,
        publications_by_year=publications_by_year,
        publications_by_document_type=publications_by_document_type,
        affiliation_coverage=AffiliationCoverageResponse(
            total_author_positions=total_author_positions,
            positions_with_affiliation=positions_with_affiliation,
            positions_without_affiliation=positions_without_affiliation,
            by_link_status=by_link_status,
        ),
    )
