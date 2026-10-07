"""Set-based, read-only queries for canonical publications."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import (
    Publication,
    PublicationAuthor,
    PublicationRawSource,
    ScopusAuthor,
)
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.schemas.publication_api import (
    PublicationAuthorRead,
    PublicationDetailResponse,
    PublicationListItem,
    PublicationListResponse,
    PublicationLecturerLinkRead,
    PublicationProvenanceRead,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _trim_optional(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _escaped_substring(value: str) -> str:
    """Escape LIKE control characters while preserving literal substring search."""

    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _publication_filters(
    *,
    q: str | None,
    year: int | None,
    document_type: str | None,
    publication_stage: str | None,
    open_access_status: str | None,
) -> list[object]:
    conditions: list[object] = []
    trimmed_q = _trim_optional(q)
    if trimmed_q is not None:
        pattern = _escaped_substring(trimmed_q)
        conditions.append(
            or_(
                Publication.title.ilike(pattern, escape="\\"),
                Publication.eid.ilike(pattern, escape="\\"),
                Publication.doi.ilike(pattern, escape="\\"),
                Publication.source_title.ilike(pattern, escape="\\"),
            )
        )

    if year is not None:
        conditions.append(Publication.year == year)

    for column, value in (
        (Publication.document_type, document_type),
        (Publication.publication_stage, publication_stage),
        (Publication.open_access_status, open_access_status),
    ):
        trimmed = _trim_optional(value)
        if trimmed is not None:
            conditions.append(column == trimmed)

    return conditions


def _list_statement(
    *,
    q: str | None,
    year: int | None,
    document_type: str | None,
    publication_stage: str | None,
    open_access_status: str | None,
):
    return select(Publication).where(
        *_publication_filters(
            q=q,
            year=year,
            document_type=document_type,
            publication_stage=publication_stage,
            open_access_status=open_access_status,
        )
    )


def list_publications(
    session: Session,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    q: str | None = None,
    year: int | None = None,
    document_type: str | None = None,
    publication_stage: str | None = None,
    open_access_status: str | None = None,
) -> PublicationListResponse:
    """Return a deterministic page of canonical publications without writes."""

    statement = _list_statement(
        q=q,
        year=year,
        document_type=document_type,
        publication_stage=publication_stage,
        open_access_status=open_access_status,
    )
    total = session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ) or 0

    rows = session.scalars(
        statement.order_by(
            Publication.year.desc().nullslast(),
            Publication.eid.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PublicationListResponse(
        items=[
            PublicationListItem(
                publication_id=row.id,
                eid=row.eid,
                doi=row.doi,
                title=row.title,
                source_title=row.source_title,
                year=row.year,
                cited_by_count=row.cited_by_count,
                document_type=row.document_type,
                publication_stage=row.publication_stage,
                open_access_status=row.open_access_status,
            )
            for row in rows
        ],
        total=int(total),
        page=page,
        page_size=page_size,
    )


def _author_rows(
    session: Session, publication_id: uuid.UUID
) -> Sequence[tuple[int, str, str]]:
    return session.execute(
        select(
            PublicationAuthor.author_order,
            ScopusAuthor.scopus_id,
            ScopusAuthor.preferred_name,
        )
        .join(ScopusAuthor, ScopusAuthor.id == PublicationAuthor.scopus_author_id)
        .where(PublicationAuthor.publication_id == publication_id)
        .order_by(
            PublicationAuthor.author_order.asc(),
            ScopusAuthor.scopus_id.asc(),
        )
    ).all()


def _approved_lecturer_link_rows(
    session: Session, publication_id: uuid.UUID
) -> Sequence[tuple[int, str, str, str | None, str | None, str | None, str | None]]:
    return session.execute(
        select(
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
            PublicationAuthor.publication_id == publication_id,
            LecturerScopusIdentity.status == "APPROVED",
        )
        .order_by(
            PublicationAuthor.author_order.asc(),
            ScopusAuthor.scopus_id.asc(),
            Lecturer.full_name.asc(),
        )
    ).all()


def _provenance_rows(
    session: Session, publication_id: uuid.UUID
) -> Sequence[tuple[str, str, int, datetime]]:
    return session.execute(
        select(
            ScopusImport.file_name,
            ScopusImport.file_sha256,
            RawScopusRecord.row_number,
            ScopusImport.created_at,
        )
        .join(RawScopusRecord, RawScopusRecord.import_id == ScopusImport.id)
        .join(
            PublicationRawSource,
            PublicationRawSource.raw_record_id == RawScopusRecord.id,
        )
        .where(PublicationRawSource.publication_id == publication_id)
        .order_by(
            ScopusImport.created_at.asc(),
            ScopusImport.id.asc(),
            RawScopusRecord.row_number.asc(),
            RawScopusRecord.id.asc(),
        )
    ).all()


def get_publication_detail(
    session: Session, *, eid: str
) -> PublicationDetailResponse | None:
    """Return canonical metadata and safe, set-based detail relationships."""

    publication = session.scalar(select(Publication).where(Publication.eid == eid))
    if publication is None:
        return None

    authors = [
        PublicationAuthorRead(
            author_order=author_order,
            scopus_id=scopus_id,
            preferred_name=preferred_name,
        )
        for author_order, scopus_id, preferred_name in _author_rows(
            session, publication.id
        )
    ]
    lecturer_links = [
        PublicationLecturerLinkRead(
            author_order=author_order,
            scopus_id=scopus_id,
            full_name=full_name,
            staff_code=staff_code,
            department=department,
            faculty=faculty,
            orcid=orcid,
        )
        for (
            author_order,
            scopus_id,
            full_name,
            staff_code,
            department,
            faculty,
            orcid,
        ) in _approved_lecturer_link_rows(session, publication.id)
    ]
    provenance = [
        PublicationProvenanceRead(
            file_name=file_name,
            file_sha256=file_sha256,
            row_number=row_number,
            imported_at=imported_at,
        )
        for file_name, file_sha256, row_number, imported_at in _provenance_rows(
            session, publication.id
        )
    ]

    return PublicationDetailResponse(
        publication_id=publication.id,
        eid=publication.eid,
        doi=publication.doi,
        title=publication.title,
        source_title=publication.source_title,
        year=publication.year,
        volume=publication.volume,
        issue=publication.issue,
        art_no=publication.art_no,
        page_start=publication.page_start,
        page_end=publication.page_end,
        cited_by_count=publication.cited_by_count,
        document_type=publication.document_type,
        publication_stage=publication.publication_stage,
        open_access_status=publication.open_access_status,
        authors=authors,
        approved_lecturer_links=lecturer_links,
        provenance=provenance,
    )


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "get_publication_detail",
    "list_publications",
]
