"""Read-only M2.8 projection queries for lecturer Scopus data.

This module deliberately has no authorization or mutation responsibilities.
It projects already-persisted approved identities and canonical publications.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import (
    Publication,
    PublicationAuthor,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.schemas.lecturer_scopus_projection import (
    ApprovedIdentitySummaryRead,
    IdentityEvidenceSummaryRead,
    LecturerProfileRead,
    LecturerPublicationAggregatesRead,
    LecturerPublicationRead,
    PaginatedLecturerPublicationsRead,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class LecturerScopusProjectionService:
    """Query-only access to approved lecturer Scopus projections."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_lecturer_profile(
        self, lecturer_id: uuid.UUID
    ) -> LecturerProfileRead | None:
        """Return model-backed lecturer profile fields, if the lecturer exists."""

        lecturer = self._session.get(Lecturer, lecturer_id)
        if lecturer is None:
            return None

        return LecturerProfileRead(
            lecturer_id=lecturer.id,
            full_name=lecturer.full_name,
            staff_code=lecturer.staff_code,
            email=lecturer.email,
            academic_rank=lecturer.academic_rank,
            academic_degree=lecturer.academic_degree,
            position=lecturer.position,
            department=lecturer.department,
            faculty=lecturer.faculty,
            repository_profile_url=lecturer.repository_profile_url,
            orcid=lecturer.orcid,
        )

    def get_approved_identity_summaries(
        self, lecturer_id: uuid.UUID
    ) -> list[ApprovedIdentitySummaryRead]:
        """Return every approved identity and safe evidence summaries."""

        identity_rows = self._session.execute(
            select(LecturerScopusIdentity, ScopusAuthor)
            .join(
                ScopusAuthor,
                ScopusAuthor.id == LecturerScopusIdentity.scopus_author_id,
            )
            .where(
                LecturerScopusIdentity.lecturer_id == lecturer_id,
                LecturerScopusIdentity.status == "APPROVED",
            )
            .order_by(
                ScopusAuthor.scopus_id.asc(),
                LecturerScopusIdentity.id.asc(),
            )
        ).all()

        if not identity_rows:
            return []

        identity_ids = [identity.id for identity, _author in identity_rows]
        author_ids = [identity.scopus_author_id for identity, _author in identity_rows]

        variant_rows = self._session.execute(
            select(
                ScopusAuthorNameVariant.scopus_author_id,
                ScopusAuthorNameVariant.variant_name,
                ScopusAuthorNameVariant.id,
            )
            .where(ScopusAuthorNameVariant.scopus_author_id.in_(author_ids))
            .order_by(
                ScopusAuthorNameVariant.scopus_author_id.asc(),
                ScopusAuthorNameVariant.variant_name.asc(),
                ScopusAuthorNameVariant.id.asc(),
            )
        ).all()
        variants_by_author: dict[uuid.UUID, list[str]] = defaultdict(list)
        for author_id, variant_name, _variant_id in variant_rows:
            if variant_name not in variants_by_author[author_id]:
                variants_by_author[author_id].append(variant_name)

        evidence_rows = self._session.execute(
            select(
                IdentityEvidence.identity_id,
                IdentityEvidence.evidence_type,
                IdentityEvidence.direction,
                IdentityEvidence.created_at,
                IdentityEvidence.id,
            )
            .where(IdentityEvidence.identity_id.in_(identity_ids))
            .order_by(
                IdentityEvidence.identity_id.asc(),
                IdentityEvidence.evidence_type.asc(),
                IdentityEvidence.direction.asc(),
                IdentityEvidence.created_at.asc(),
                IdentityEvidence.id.asc(),
            )
        ).all()
        evidence_by_identity: dict[uuid.UUID, list[IdentityEvidenceSummaryRead]] = defaultdict(list)
        for identity_id, evidence_type, direction, created_at, _evidence_id in evidence_rows:
            evidence_by_identity[identity_id].append(
                IdentityEvidenceSummaryRead(
                    evidence_type=evidence_type,
                    direction=direction,
                    created_at=created_at,
                )
            )

        return [
            ApprovedIdentitySummaryRead(
                identity_id=identity.id,
                status=identity.status,
                scopus_author_id=identity.scopus_author_id,
                scopus_id=author.scopus_id,
                preferred_name=author.preferred_name,
                name_variants=variants_by_author[identity.scopus_author_id],
                evidence=evidence_by_identity[identity.id],
                created_at=identity.created_at,
                updated_at=identity.updated_at,
            )
            for identity, author in identity_rows
        ]

    def get_lecturer_publications(
        self,
        lecturer_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedLecturerPublicationsRead:
        """Return a distinct, deterministically ordered publication page."""

        self._validate_pagination(page, page_size)
        publication_set = self._publication_set(lecturer_id)
        total = self._session.scalar(
            select(func.count()).select_from(publication_set)
        ) or 0

        page_rows = self._session.execute(
            select(
                Publication.id,
                Publication.year,
                Publication.eid,
            )
            .join(
                PublicationAuthor,
                PublicationAuthor.publication_id == Publication.id,
            )
            .join(
                LecturerScopusIdentity,
                LecturerScopusIdentity.scopus_author_id
                == PublicationAuthor.scopus_author_id,
            )
            .where(
                LecturerScopusIdentity.lecturer_id == lecturer_id,
                LecturerScopusIdentity.status == "APPROVED",
            )
            .distinct()
            .order_by(
                Publication.year.desc().nulls_last(),
                Publication.eid.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        publication_ids = [row.id for row in page_rows]
        if not publication_ids:
            return PaginatedLecturerPublicationsRead(
                items=[], total=int(total), page=page, page_size=page_size
            )

        publication_rows = self._session.execute(
            select(Publication, PublicationAuthor.author_order)
            .join(
                PublicationAuthor,
                PublicationAuthor.publication_id == Publication.id,
            )
            .join(
                LecturerScopusIdentity,
                LecturerScopusIdentity.scopus_author_id
                == PublicationAuthor.scopus_author_id,
            )
            .where(
                Publication.id.in_(publication_ids),
                LecturerScopusIdentity.lecturer_id == lecturer_id,
                LecturerScopusIdentity.status == "APPROVED",
            )
            .order_by(Publication.id.asc(), PublicationAuthor.author_order.asc())
        ).all()

        publication_by_id: dict[uuid.UUID, Publication] = {}
        author_orders_by_publication: dict[uuid.UUID, set[int]] = defaultdict(set)
        for publication, author_order in publication_rows:
            publication_by_id[publication.id] = publication
            author_orders_by_publication[publication.id].add(author_order)

        items = [
            LecturerPublicationRead(
                publication_id=publication_by_id[publication_id].id,
                eid=publication_by_id[publication_id].eid,
                doi=publication_by_id[publication_id].doi,
                title=publication_by_id[publication_id].title,
                source_title=publication_by_id[publication_id].source_title,
                year=publication_by_id[publication_id].year,
                cited_by_count=publication_by_id[publication_id].cited_by_count,
                document_type=publication_by_id[publication_id].document_type,
                publication_stage=publication_by_id[publication_id].publication_stage,
                open_access_status=publication_by_id[publication_id].open_access_status,
                linked_author_orders=sorted(author_orders_by_publication[publication_id]),
            )
            for publication_id in publication_ids
        ]
        return PaginatedLecturerPublicationsRead(
            items=items,
            total=int(total),
            page=page,
            page_size=page_size,
        )

    def get_lecturer_publication_aggregates(
        self, lecturer_id: uuid.UUID
    ) -> LecturerPublicationAggregatesRead:
        """Return aggregates over the full distinct publication set."""

        publication_set = self._publication_set(lecturer_id)
        aggregate_row = self._session.execute(
            select(
                func.count().label("total_publications"),
                func.coalesce(func.sum(publication_set.c.cited_by_count), 0).label(
                    "known_citation_sum"
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (publication_set.c.cited_by_count.is_(None), 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("citation_unknown_publication_count"),
                func.coalesce(
                    func.sum(
                        case((publication_set.c.year.is_(None), 1), else_=0)
                    ),
                    0,
                ).label("unknown_year_count"),
            )
            .select_from(publication_set)
        ).one()

        year_rows = self._session.execute(
            select(publication_set.c.year, func.count().label("count"))
            .select_from(publication_set)
            .where(publication_set.c.year.is_not(None))
            .group_by(publication_set.c.year)
            .order_by(publication_set.c.year.asc())
        ).all()

        approved_identity_count = self._session.scalar(
            select(func.count(LecturerScopusIdentity.id)).where(
                LecturerScopusIdentity.lecturer_id == lecturer_id,
                LecturerScopusIdentity.status == "APPROVED",
            )
        ) or 0

        return LecturerPublicationAggregatesRead(
            total_publications=int(aggregate_row.total_publications),
            publication_count_by_year={int(year): int(count) for year, count in year_rows},
            unknown_year_count=int(aggregate_row.unknown_year_count),
            known_citation_sum=int(aggregate_row.known_citation_sum),
            citation_unknown_publication_count=int(
                aggregate_row.citation_unknown_publication_count
            ),
            approved_identity_count=int(approved_identity_count),
        )

    def _publication_set(self, lecturer_id: uuid.UUID):
        """Return the distinct canonical publication set for approved identities."""

        return (
            select(
                Publication.id.label("publication_id"),
                Publication.eid.label("eid"),
                Publication.year.label("year"),
                Publication.cited_by_count.label("cited_by_count"),
            )
            .join(
                PublicationAuthor,
                PublicationAuthor.publication_id == Publication.id,
            )
            .join(
                LecturerScopusIdentity,
                LecturerScopusIdentity.scopus_author_id
                == PublicationAuthor.scopus_author_id,
            )
            .where(
                LecturerScopusIdentity.lecturer_id == lecturer_id,
                LecturerScopusIdentity.status == "APPROVED",
            )
            .distinct()
            .subquery("lecturer_scopus_publications")
        )

    @staticmethod
    def _validate_pagination(page: int, page_size: int) -> None:
        if page < 1:
            raise ValueError("page must be at least 1")
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")


__all__ = ["LecturerScopusProjectionService"]
