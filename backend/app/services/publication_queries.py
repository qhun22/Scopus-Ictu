"""Set-based, read-only queries for canonical publications."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.services.text_folding import fold_text, folded
from app.models.affiliation import (
    Organization,
    PublicationAuthorAffiliation,
    PublicationAuthorAffiliationResolution,
)
from app.models.affiliation_override import PublicationAuthorAffiliationOverride
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
    AffiliationOrganizationRead,
    AffiliationOverrideRead,
    AffiliationProvenanceRead,
    AffiliationResolutionRead,
    AffiliationSummaryRead,
    AuthorAffiliationRead,
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


def publication_filters(
    *,
    q: str | None,
    year: int | None,
    document_type: str | None,
    publication_stage: str | None,
    open_access_status: str | None,
    scopus_id: str | None = None,
) -> list[object]:
    conditions: list[object] = []
    trimmed_q = _trim_optional(q)
    if trimmed_q is not None:
        pattern = _escaped_substring(trimmed_q)
        conditions.append(
            or_(
                folded(Publication.title).like(fold_text(pattern), escape="\\"),
                Publication.eid.ilike(pattern, escape="\\"),
                Publication.doi.ilike(pattern, escape="\\"),
                folded(Publication.source_title).like(fold_text(pattern), escape="\\"),
            )
        )

    trimmed_scopus_id = _trim_optional(scopus_id)
    if trimmed_scopus_id is not None:
        # Publications in which this Scopus author appears (any position).
        conditions.append(
            select(PublicationAuthor.id)
            .join(ScopusAuthor, ScopusAuthor.id == PublicationAuthor.scopus_author_id)
            .where(
                PublicationAuthor.publication_id == Publication.id,
                ScopusAuthor.scopus_id == trimmed_scopus_id,
            )
            .exists()
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
    scopus_id: str | None = None,
):
    return select(Publication).where(
        *publication_filters(
            q=q,
            year=year,
            document_type=document_type,
            publication_stage=publication_stage,
            open_access_status=open_access_status,
            scopus_id=scopus_id,
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
    scopus_id: str | None = None,
) -> PublicationListResponse:
    """Return a deterministic page of canonical publications without writes."""

    statement = _list_statement(
        q=q,
        year=year,
        document_type=document_type,
        publication_stage=publication_stage,
        open_access_status=open_access_status,
        scopus_id=scopus_id,
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
) -> Sequence[tuple[uuid.UUID, int, str, str]]:
    return session.execute(
        select(
            PublicationAuthor.id,
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


def _override_rows(
    session: Session, publication_author_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, PublicationAuthorAffiliationOverride]:
    if not publication_author_ids:
        return {}
    rows = session.scalars(
        select(PublicationAuthorAffiliationOverride).where(
            PublicationAuthorAffiliationOverride.publication_author_id.in_(publication_author_ids)
        )
    ).all()
    return {r.publication_author_id: r for r in rows}


def _override_read(row: PublicationAuthorAffiliationOverride) -> AffiliationOverrideRead:
    return AffiliationOverrideRead(
        affiliation_text=row.affiliation_text,
        confidence=row.confidence,
        evidence_url=row.evidence_url,
        reason=row.reason,
        updated_at=row.updated_at,
    )


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


_STATUS_RANK = {"VERIFIED": 2, "CORROBORATED": 1, "UNRESOLVED": 0}


def _affiliation_blocks(session: Session, publication_id: uuid.UUID) -> dict[int, dict]:
    """Per author_order affiliation data, from two set-based queries.

    Affiliations are loaded separately from authors, so many affiliations can
    never duplicate, drop or reorder authors.  Only the latest resolution per
    (author position, source system) is current.
    """

    res_rows = session.execute(
        select(PublicationAuthor.author_order, PublicationAuthorAffiliationResolution)
        .join(
            PublicationAuthorAffiliationResolution,
            PublicationAuthorAffiliationResolution.publication_author_id == PublicationAuthor.id,
        )
        .where(PublicationAuthor.publication_id == publication_id)
        .order_by(
            PublicationAuthor.author_order.asc(),
            PublicationAuthorAffiliationResolution.source_system.asc(),
            PublicationAuthorAffiliationResolution.created_at.desc(),
            PublicationAuthorAffiliationResolution.id.asc(),
        )
    ).all()
    current: dict[tuple[int, str], PublicationAuthorAffiliationResolution] = {}
    for order, res in res_rows:
        current.setdefault((order, res.source_system), res)  # first row = newest
    aff_by_res: dict[uuid.UUID, list[tuple[PublicationAuthorAffiliation, Organization | None]]] = {}
    ids = [r.id for r in current.values() if r.link_status != "UNRESOLVED"]
    if ids:
        for aff, org in session.execute(
            select(PublicationAuthorAffiliation, Organization)
            .outerjoin(Organization, Organization.id == PublicationAuthorAffiliation.organization_id)
            .where(PublicationAuthorAffiliation.resolution_id.in_(ids))
            .order_by(PublicationAuthorAffiliation.resolution_id, PublicationAuthorAffiliation.ord)
        ).all():
            aff_by_res.setdefault(aff.resolution_id, []).append((aff, org))

    blocks: dict[int, dict] = {}
    for (order, _source), res in sorted(current.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        block = blocks.setdefault(order, {"resolutions": [], "affiliations": []})
        block["resolutions"].append(
            AffiliationResolutionRead(
                source_system=res.source_system,
                link_status=res.link_status,
                link_method=res.link_method,
                unresolved_reason=res.unresolved_reason,
                affiliation_presence=res.affiliation_presence,
                retrieved_at=res.retrieved_at,
                source_work_id=res.source_work_id,
            )
        )
        if res.link_status == "UNRESOLVED":
            continue
        # one item per raw string; organizations attached to the same raw string are grouped
        groups: dict[object, AuthorAffiliationRead] = {}
        for aff, org in aff_by_res.get(res.id, []):
            gkey = aff.raw_index if aff.raw_index is not None else ("org", aff.id)
            item = groups.get(gkey)
            if item is None:
                item = AuthorAffiliationRead(
                    link_status=res.link_status,
                    source_system=res.source_system,
                    raw_affiliation_text=aff.raw_affiliation_text,
                    organizations=[],
                    retrieved_at=res.retrieved_at,
                    provenance=AffiliationProvenanceRead(
                        link_method=res.link_method,
                        source_work_id=res.source_work_id,
                        source_doi=res.source_doi,
                        external_position=res.external_position,
                        external_author_name=res.external_author_name,
                        evidence=res.evidence or {},
                    ),
                )
                groups[gkey] = item
            if org is not None:
                item.organizations.append(
                    AffiliationOrganizationRead(
                        source_system=org.source_system,
                        source_org_id=org.source_org_id,
                        ror=org.ror,
                        display_name=org.display_name,
                        country_code=org.country_code,
                    )
                )
        block["affiliations"].extend(groups.values())
    for block in blocks.values():
        block["affiliations"].sort(key=lambda a: (-_STATUS_RANK[a.link_status], a.source_system))
    return blocks


def _apply_affiliations(
    authors: list[PublicationAuthorRead], blocks: dict[int, dict]
) -> AffiliationSummaryRead:
    counts = {"vw": 0, "vo": 0, "cw": 0, "co": 0, "un": 0, "nr": 0}
    for author in authors:
        block = blocks.get(author.author_order)
        if not block:
            counts["nr"] += 1
            continue
        resolutions = block["resolutions"]
        best = max(resolutions, key=lambda r: _STATUS_RANK[r.link_status]).link_status
        trusted = [r for r in resolutions if r.link_status != "UNRESOLVED"]
        best_has = any(r.link_status == best and r.affiliation_presence == "PRESENT" for r in resolutions)
        author.affiliation_status = best
        author.affiliation_resolutions = resolutions
        author.affiliations = block["affiliations"]
        if trusted:
            author.source_has_affiliation = any(r.affiliation_presence == "PRESENT" for r in trusted)
        if best == "VERIFIED":
            counts["vw" if best_has else "vo"] += 1
        elif best == "CORROBORATED":
            counts["cw" if best_has else "co"] += 1
        else:
            counts["un"] += 1
    n = len(authors)
    return AffiliationSummaryRead(
        authors=n,
        verified_with_affiliation=counts["vw"],
        verified_without_affiliation=counts["vo"],
        corroborated_with_affiliation=counts["cw"],
        corroborated_without_affiliation=counts["co"],
        unresolved=counts["un"],
        not_reconciled=counts["nr"],
        all_authors_verified_with_affiliation=n > 0 and counts["vw"] == n,
        all_authors_verified_or_corroborated_with_affiliation=n > 0 and counts["vw"] + counts["cw"] == n,
    )


def get_publication_detail(
    session: Session, *, eid: str
) -> PublicationDetailResponse | None:
    """Return canonical metadata and safe, set-based detail relationships."""

    publication = session.scalar(select(Publication).where(Publication.eid == eid))
    if publication is None:
        return None

    author_rows = _author_rows(session, publication.id)
    overrides = _override_rows(session, [row[0] for row in author_rows])
    authors = [
        PublicationAuthorRead(
            author_order=author_order,
            scopus_id=scopus_id,
            preferred_name=preferred_name,
            affiliation_override=_override_read(overrides[publication_author_id])
            if publication_author_id in overrides
            else None,
        )
        for publication_author_id, author_order, scopus_id, preferred_name in author_rows
    ]
    affiliation_summary = _apply_affiliations(authors, _affiliation_blocks(session, publication.id))
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
        affiliation_summary=affiliation_summary,
        approved_lecturer_links=lecturer_links,
        provenance=provenance,
    )


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "get_publication_detail",
    "list_publications",
    "publication_filters",
]
