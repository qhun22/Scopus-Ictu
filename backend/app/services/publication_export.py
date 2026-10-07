"""Set-based, read-only export query for the canonical publication export API — A4.

Uses batched IN() queries — one per relationship — to avoid N+1 against the
publication list.  All queries are read-only (no writes here; the AuditEvent
commit belongs to the endpoint).
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor
from app.schemas.publication_export import (
    PublicationExportAuthor,
    PublicationExportItem,
    PublicationExportLecturerLink,
)
from app.services.publication_queries import publication_filters


def _build_filters_applied(
    *,
    q: str | None,
    year: int | None,
    document_type: str | None,
    publication_stage: str | None,
    open_access_status: str | None,
) -> dict:
    """Return a dict of only the non-empty normalized filters supplied."""
    result: dict = {}
    if q is not None:
        normalized = q.strip()
        if normalized:
            result["q"] = normalized
    if year is not None:
        result["year"] = year
    if document_type is not None:
        v = document_type.strip()
        if v:
            result["document_type"] = v
    if publication_stage is not None:
        v = publication_stage.strip()
        if v:
            result["publication_stage"] = v
    if open_access_status is not None:
        v = open_access_status.strip()
        if v:
            result["open_access_status"] = v
    return result


def _batch_authors(
    session: Session, publication_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[PublicationExportAuthor]]:
    if not publication_ids:
        return {}
    rows = session.execute(
        select(
            PublicationAuthor.publication_id,
            PublicationAuthor.author_order,
            ScopusAuthor.scopus_id,
            ScopusAuthor.preferred_name,
        )
        .join(ScopusAuthor, ScopusAuthor.id == PublicationAuthor.scopus_author_id)
        .where(PublicationAuthor.publication_id.in_(publication_ids))
        .order_by(
            PublicationAuthor.publication_id.asc(),
            PublicationAuthor.author_order.asc(),
            ScopusAuthor.scopus_id.asc(),
        )
    ).all()

    result: dict[uuid.UUID, list[PublicationExportAuthor]] = defaultdict(list)
    for pub_id, author_order, scopus_id, preferred_name in rows:
        result[pub_id].append(
            PublicationExportAuthor(
                author_order=author_order,
                scopus_id=scopus_id,
                preferred_name=preferred_name,
            )
        )
    return result


def _batch_lecturer_links(
    session: Session, publication_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[PublicationExportLecturerLink]]:
    if not publication_ids:
        return {}
    rows = session.execute(
        select(
            PublicationAuthor.publication_id,
            PublicationAuthor.author_order,
            ScopusAuthor.scopus_id,
            Lecturer.full_name,
            Lecturer.staff_code,
            Lecturer.department,
            Lecturer.faculty,
            Lecturer.orcid,
        )
        .join(ScopusAuthor, ScopusAuthor.id == PublicationAuthor.scopus_author_id)
        .join(
            LecturerScopusIdentity,
            LecturerScopusIdentity.scopus_author_id == ScopusAuthor.id,
        )
        .join(Lecturer, Lecturer.id == LecturerScopusIdentity.lecturer_id)
        .where(
            PublicationAuthor.publication_id.in_(publication_ids),
            LecturerScopusIdentity.status == "APPROVED",
        )
        .order_by(
            PublicationAuthor.publication_id.asc(),
            PublicationAuthor.author_order.asc(),
            ScopusAuthor.scopus_id.asc(),
            Lecturer.full_name.asc(),
            Lecturer.id.asc(),
        )
    ).all()

    result: dict[uuid.UUID, list[PublicationExportLecturerLink]] = defaultdict(list)
    for pub_id, author_order, scopus_id, full_name, staff_code, department, faculty, orcid in rows:
        result[pub_id].append(
            PublicationExportLecturerLink(
                author_order=author_order,
                scopus_id=scopus_id,
                full_name=full_name,
                staff_code=staff_code,
                department=department,
                faculty=faculty,
                orcid=orcid,
            )
        )
    return result


def export_publications(
    session: Session,
    *,
    q: str | None = None,
    year: int | None = None,
    document_type: str | None = None,
    publication_stage: str | None = None,
    open_access_status: str | None = None,
) -> tuple[list[PublicationExportItem], dict]:
    """Return (items, filters_applied) for the export endpoint.

    Queries are read-only.  The AuditEvent commit is the caller's responsibility.
    Raises SQLAlchemyError on DB failure — the caller wraps this in a 503.
    """

    filters_applied = _build_filters_applied(
        q=q,
        year=year,
        document_type=document_type,
        publication_stage=publication_stage,
        open_access_status=open_access_status,
    )

    pubs = session.scalars(
        select(Publication)
        .where(
            *publication_filters(
                q=q,
                year=year,
                document_type=document_type,
                publication_stage=publication_stage,
                open_access_status=open_access_status,
            )
        )
        .order_by(
            Publication.year.desc().nullslast(),
            Publication.eid.asc(),
        )
    ).all()

    pub_ids = [p.id for p in pubs]
    authors_by_pub = _batch_authors(session, pub_ids)
    links_by_pub = _batch_lecturer_links(session, pub_ids)

    items = [
        PublicationExportItem(
            eid=p.eid,
            doi=p.doi,
            title=p.title,
            source_title=p.source_title,
            year=p.year,
            volume=p.volume,
            issue=p.issue,
            art_no=p.art_no,
            page_start=p.page_start,
            page_end=p.page_end,
            cited_by_count=p.cited_by_count,
            document_type=p.document_type,
            publication_stage=p.publication_stage,
            open_access_status=p.open_access_status,
            authors=authors_by_pub.get(p.id, []),
            approved_lecturer_links=links_by_pub.get(p.id, []),
        )
        for p in pubs
    ]

    return items, filters_applied
