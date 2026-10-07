"""Set-based, read-only grouped queries for the global search API.

Each result group is one independent ``SELECT`` with its own ``LIMIT``. There
are no aggregate counts and no per-row follow-up queries, so the whole endpoint
costs at most three statements regardless of how many rows match.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, ScopusAuthor
from app.schemas.search_api import (
    LecturerSearchItem,
    PublicationSearchItem,
    ScopusAuthorSearchItem,
    SearchResponse,
)

DEFAULT_LIMIT = 5
MAX_LIMIT = 20
MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 255

# Defensive in-service clamp. The endpoint already validates the range, but a
# direct service caller must not be able to request an unbounded result set.
_EFFECTIVE_MIN_LIMIT = 1


def _escaped_substring(value: str) -> str:
    """Escape LIKE control characters while preserving literal substring search."""

    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _search_lecturers(
    session: Session, pattern: str, limit: int
) -> list[LecturerSearchItem]:
    rows = session.scalars(
        select(Lecturer)
        .where(
            Lecturer.is_active.is_(True),
            or_(
                Lecturer.full_name_normalized.ilike(pattern, escape="\\"),
                Lecturer.staff_code.ilike(pattern, escape="\\"),
                Lecturer.orcid.ilike(pattern, escape="\\"),
            ),
        )
        .order_by(
            Lecturer.full_name_normalized.asc(),
            Lecturer.staff_code.asc().nullslast(),
            Lecturer.id.asc(),
        )
        .limit(limit)
    ).all()

    return [
        LecturerSearchItem(
            full_name=row.full_name,
            staff_code=row.staff_code,
            department=row.department,
            faculty=row.faculty,
            orcid=row.orcid,
        )
        for row in rows
    ]


def _search_publications(
    session: Session, pattern: str, limit: int
) -> list[PublicationSearchItem]:
    rows = session.scalars(
        select(Publication)
        .where(
            or_(
                Publication.title.ilike(pattern, escape="\\"),
                Publication.eid.ilike(pattern, escape="\\"),
                Publication.doi.ilike(pattern, escape="\\"),
                Publication.source_title.ilike(pattern, escape="\\"),
            )
        )
        .order_by(
            Publication.year.desc().nullslast(),
            Publication.eid.asc(),
        )
        .limit(limit)
    ).all()

    return [
        PublicationSearchItem(
            eid=row.eid,
            title=row.title,
            year=row.year,
            source_title=row.source_title,
            cited_by_count=row.cited_by_count,
            document_type=row.document_type,
        )
        for row in rows
    ]


def _search_scopus_authors(
    session: Session, pattern: str, limit: int
) -> list[ScopusAuthorSearchItem]:
    rows = session.scalars(
        select(ScopusAuthor)
        .where(
            or_(
                ScopusAuthor.preferred_name.ilike(pattern, escape="\\"),
                ScopusAuthor.scopus_id.ilike(pattern, escape="\\"),
            )
        )
        .order_by(
            ScopusAuthor.preferred_name.asc(),
            ScopusAuthor.scopus_id.asc(),
        )
        .limit(limit)
    ).all()

    return [
        ScopusAuthorSearchItem(
            scopus_id=row.scopus_id,
            preferred_name=row.preferred_name,
        )
        for row in rows
    ]


def global_search(session: Session, *, q: str, limit: int = DEFAULT_LIMIT) -> SearchResponse:
    """Return grouped, deterministic discovery hits for an already-trimmed query."""

    trimmed_q = q.strip()
    bounded_limit = max(_EFFECTIVE_MIN_LIMIT, min(limit, MAX_LIMIT))
    pattern = _escaped_substring(trimmed_q)

    return SearchResponse(
        q=trimmed_q,
        limit=bounded_limit,
        lecturers=_search_lecturers(session, pattern, bounded_limit),
        publications=_search_publications(session, pattern, bounded_limit),
        scopus_authors=_search_scopus_authors(session, pattern, bounded_limit),
    )


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_QUERY_LENGTH",
    "MIN_QUERY_LENGTH",
    "global_search",
]