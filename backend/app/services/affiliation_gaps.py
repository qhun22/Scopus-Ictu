"""Author positions that have no affiliation to show ("chưa giải quyết được") — week-7 API.

Read-only and computed in Python from ``affiliation_export.load_positions`` so the list obeys the
same unit rules as the export file: every position is in exactly one of two groups, "has at
least one unit" or "gap with exactly one reason". A position the ADMIN typed a unit for counts
as having a unit; one the ADMIN only marked UNRESOLVED stays a gap.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.publication import Publication
from app.schemas.affiliation_override_api import override_to_read
from app.schemas.publication_export import (
    AffiliationGapItem,
    AffiliationGapListResponse,
    AffiliationGapSummary,
    SourceOutcomeRead,
)
from app.services.affiliation_export import (
    GAPS_CSV_COLUMNS,
    Position,
    csv_bytes,
    gaps_csv_rows,
    load_positions,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(slots=True)
class _Gap:
    publication: Publication
    author_count: int
    position: Position


def _collect(
    session: Session, *, year: int | None, eid: str | None, ictu_only: bool
) -> tuple[list[_Gap], int]:
    """All gap positions in scope (publication order, then author order) and the number of
    positions in scope. ``ictu_only`` keeps positions with an APPROVED, non-excluded lecturer."""

    query = select(Publication)
    if year is not None:
        query = query.where(Publication.year == year)
    if eid is not None and eid.strip():
        query = query.where(Publication.eid == eid.strip())
    pubs = session.scalars(
        query.order_by(Publication.year.desc().nullslast(), Publication.eid.asc())
    ).all()
    positions_by_pub = load_positions(session, [p.id for p in pubs])

    gaps: list[_Gap] = []
    scope_positions = 0
    for pub in pubs:
        positions = positions_by_pub.get(pub.id, [])
        for pos in positions:
            if ictu_only and not pos.ictu_lecturers:
                continue
            scope_positions += 1
            if pos.decision.gap_reason is not None:
                gaps.append(_Gap(pub, len(positions), pos))
    return gaps, scope_positions


def _item(gap: _Gap) -> AffiliationGapItem:
    pub, pos, d = gap.publication, gap.position, gap.position.decision
    return AffiliationGapItem(
        publication_author_id=pos.publication_author_id,
        eid=pub.eid,
        doi=pub.doi,
        title=pub.title,
        year=pub.year,
        author_count=gap.author_count,
        author_order=pos.author_order,
        scopus_id=pos.scopus_id,
        author_name=pos.author_name,
        affiliation_status=d.affiliation_status,
        reason=d.gap_reason or "UNKNOWN",
        by_source=[
            SourceOutcomeRead(source=s.source, link_status=s.link_status, reason=s.reason)
            for s in d.by_source
        ],
        admin_reviewed=d.admin_reviewed,
        ictu_lecturer=" | ".join(pos.ictu_lecturers) or None,
        overrides=[override_to_read(o) for o in pos.overrides],
    )


def list_gaps(
    session: Session,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    year: int | None = None,
    eid: str | None = None,
    reason: str | None = None,
    ictu_only: bool = False,
) -> AffiliationGapListResponse:
    """One page of gap positions. ``summary`` ignores ``reason`` so the counts beside a
    reason filter do not change when a reason is chosen; ``total`` honours it."""

    gaps, scope_positions = _collect(session, year=year, eid=eid, ictu_only=ictu_only)
    summary = AffiliationGapSummary(
        total_positions=scope_positions,
        total_gaps=len(gaps),
        publications_with_gaps=len({g.publication.id for g in gaps}),
        by_reason=dict(Counter(g.position.decision.gap_reason for g in gaps)),
    )
    shown = [g for g in gaps if reason is None or g.position.decision.gap_reason == reason]
    start = (page - 1) * page_size
    return AffiliationGapListResponse(
        items=[_item(g) for g in shown[start : start + page_size]],
        total=len(shown),
        page=page,
        page_size=page_size,
        summary=summary,
    )


def gaps_csv(
    session: Session,
    *,
    year: int | None = None,
    eid: str | None = None,
    reason: str | None = None,
    ictu_only: bool = False,
) -> tuple[bytes, int]:
    """Return (csv_bytes, row_count): every gap in scope, no pagination."""

    gaps, _ = _collect(session, year=year, eid=eid, ictu_only=ictu_only)
    shown = [g for g in gaps if reason is None or g.position.decision.gap_reason == reason]
    rows = gaps_csv_rows([(g.publication, g.author_count, g.position) for g in shown])
    return csv_bytes(GAPS_CSV_COLUMNS, rows), len(rows)

