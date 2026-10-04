"""Transient canonical-publication evidence enrichment for existing candidates.

The service only reads the canonical database and enriches candidates already
returned by ``CandidateGenerator``.  It never creates candidates, persists
evidence, scores pairs, or makes an identity decision.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master_lecturer import (
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)
from app.models.publication import Publication, PublicationAuthor
from app.services.matching.candidate_types import (
    EnrichedLecturerScopusCandidate,
    LecturerScopusCandidate,
    PublicationEvidence,
    PublicationEvidenceConflict,
)

_DOI_PREFIXES: tuple[str, ...] = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


def normalize_doi_for_matching(value: str | None) -> str | None:
    """Apply the conservative DOI_N0 normalization contract."""
    if value is None or not isinstance(value, str):
        return None
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not normalized:
        return None
    for prefix in _DOI_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    normalized = unicodedata.normalize("NFKC", normalized).strip().casefold()
    return normalized or None


@dataclass(frozen=True, slots=True)
class PublicationEvidenceEnrichmentResult(Sequence[EnrichedLecturerScopusCandidate]):
    """Enriched candidates plus fail-closed reconciliation diagnostics."""

    candidates: tuple[EnrichedLecturerScopusCandidate, ...]
    conflicts: tuple[PublicationEvidenceConflict, ...]

    def __len__(self) -> int:
        return len(self.candidates)

    def __getitem__(
        self, index: int | slice
    ) -> EnrichedLecturerScopusCandidate | tuple[EnrichedLecturerScopusCandidate, ...]:
        return self.candidates[index]

    def __iter__(self):
        return iter(self.candidates)


@dataclass(frozen=True, slots=True)
class _ReconciledKnownPublication:
    known_publication: LecturerKnownPublication
    snapshot: LecturerSourceSnapshot
    publication: Publication
    rule_id: Literal[
        "RULE_KNOWN_PUBLICATION_DOI_EXACT",
        "RULE_KNOWN_PUBLICATION_TITLE_EXACT",
    ]
    reconciliation: Literal["DOI_EXACT", "TITLE_EXACT"]


def _publication_sort_key(publication: Publication) -> tuple[str, str]:
    return str(publication.eid), str(publication.id)


def _reconcile_known_publications(
    known_publications: Iterable[LecturerKnownPublication],
    snapshots_by_id: dict[UUID, LecturerSourceSnapshot],
    publications: Iterable[Publication],
) -> tuple[tuple[_ReconciledKnownPublication, ...], tuple[PublicationEvidenceConflict, ...]]:
    """Reconcile known-publication rows with conservative exact rules."""
    publication_rows = tuple(sorted(publications, key=_publication_sort_key))
    by_doi: dict[str, list[Publication]] = defaultdict(list)
    by_title: dict[str, list[Publication]] = defaultdict(list)
    for publication in publication_rows:
        canonical_doi = normalize_doi_for_matching(publication.doi)
        if canonical_doi is not None:
            by_doi[canonical_doi].append(publication)
        by_title[publication.title_normalized].append(publication)

    reconciled: list[_ReconciledKnownPublication] = []
    conflicts: list[PublicationEvidenceConflict] = []
    for known_publication in sorted(known_publications, key=lambda row: str(row.id)):
        snapshot = snapshots_by_id.get(known_publication.snapshot_id)
        if snapshot is None:
            continue
        if snapshot.lecturer_id != known_publication.lecturer_id:
            conflicts.append(
                PublicationEvidenceConflict(
                    known_publication_id=known_publication.id,
                    lecturer_id=known_publication.lecturer_id,
                    lecturer_snapshot_id=known_publication.snapshot_id,
                    reason="SNAPSHOT_LECTURER_MISMATCH",
                    doi_publication_ids=(),
                    title_publication_ids=(),
                )
            )
            continue

        doi_matches = (
            by_doi.get(normalize_doi_for_matching(known_publication.doi_normalized), [])
            if known_publication.doi_normalized
            else []
        )
        title_matches = by_title.get(known_publication.title_normalized, [])

        if len(doi_matches) > 1:
            conflicts.append(
                PublicationEvidenceConflict(
                    known_publication_id=known_publication.id,
                    lecturer_id=known_publication.lecturer_id,
                    lecturer_snapshot_id=known_publication.snapshot_id,
                    reason="DOI_AMBIGUOUS",
                    doi_publication_ids=tuple(row.id for row in doi_matches),
                    title_publication_ids=tuple(row.id for row in title_matches),
                )
            )
            continue

        if len(title_matches) > 1:
            conflicts.append(
                PublicationEvidenceConflict(
                    known_publication_id=known_publication.id,
                    lecturer_id=known_publication.lecturer_id,
                    lecturer_snapshot_id=known_publication.snapshot_id,
                    reason="TITLE_AMBIGUOUS",
                    doi_publication_ids=tuple(row.id for row in doi_matches),
                    title_publication_ids=tuple(row.id for row in title_matches),
                )
            )
            continue

        if len(doi_matches) == 1:
            publication = doi_matches[0]
            if len(title_matches) == 1 and title_matches[0].id != publication.id:
                conflicts.append(
                    PublicationEvidenceConflict(
                        known_publication_id=known_publication.id,
                        lecturer_id=known_publication.lecturer_id,
                        lecturer_snapshot_id=known_publication.snapshot_id,
                        reason="DOI_TITLE_CONFLICT",
                        doi_publication_ids=(publication.id,),
                        title_publication_ids=(title_matches[0].id,),
                    )
                )
                continue
            reconciled.append(
                _ReconciledKnownPublication(
                    known_publication=known_publication,
                    snapshot=snapshot,
                    publication=publication,
                    rule_id="RULE_KNOWN_PUBLICATION_DOI_EXACT",
                    reconciliation="DOI_EXACT",
                )
            )
            continue

        if len(title_matches) == 1:
            reconciled.append(
                _ReconciledKnownPublication(
                    known_publication=known_publication,
                    snapshot=snapshot,
                    publication=title_matches[0],
                    rule_id="RULE_KNOWN_PUBLICATION_TITLE_EXACT",
                    reconciliation="TITLE_EXACT",
                )
            )
    return tuple(reconciled), tuple(conflicts)


def enrich_candidates(
    candidates: Iterable[LecturerScopusCandidate],
    known_publications: Iterable[LecturerKnownPublication],
    snapshots: Iterable[LecturerSourceSnapshot],
    publications: Iterable[Publication],
    publication_authors: Iterable[PublicationAuthor],
) -> PublicationEvidenceEnrichmentResult:
    """Pure in-memory enrichment used by the service and focused unit tests."""
    candidate_rows = tuple(candidates)
    candidate_by_pair = {
        (candidate.lecturer_id, candidate.scopus_author_id): candidate
        for candidate in candidate_rows
    }
    snapshots_by_id = {snapshot.id: snapshot for snapshot in snapshots}
    reconciled, conflicts = _reconcile_known_publications(
        known_publications, snapshots_by_id, publications
    )

    author_ids_by_publication: dict[UUID, set[UUID]] = defaultdict(set)
    for row in publication_authors:
        author_ids_by_publication[row.publication_id].add(row.scopus_author_id)

    # One descriptor per candidate/publication.  DOI provenance wins over title
    # provenance for the same publication, then UUID order makes reruns stable.
    evidence_by_key: dict[tuple[UUID, UUID, UUID], PublicationEvidence] = {}
    rule_rank = {
        "RULE_KNOWN_PUBLICATION_DOI_EXACT": 0,
        "RULE_KNOWN_PUBLICATION_TITLE_EXACT": 1,
    }
    for item in reconciled:
        publication_author_ids = author_ids_by_publication.get(item.publication.id, set())
        for pair, _candidate in candidate_by_pair.items():
            lecturer_id, scopus_author_id = pair
            if lecturer_id != item.known_publication.lecturer_id:
                continue
            if scopus_author_id not in publication_author_ids:
                continue
            key = (lecturer_id, scopus_author_id, item.publication.id)
            descriptor = PublicationEvidence(
                rule_id=item.rule_id,
                known_publication_id=item.known_publication.id,
                lecturer_id=lecturer_id,
                lecturer_snapshot_id=item.snapshot.id,
                canonical_publication_id=item.publication.id,
                canonical_publication_eid=item.publication.eid,
                candidate_scopus_author_id=scopus_author_id,
                known_publication_doi_normalized=item.known_publication.doi_normalized,
                known_publication_title_normalized=item.known_publication.title_normalized,
                canonical_publication_doi=item.publication.doi,
                canonical_publication_title=item.publication.title,
                reconciliation=item.reconciliation,
            )
            existing = evidence_by_key.get(key)
            if existing is None or (
                rule_rank[descriptor.rule_id],
                str(descriptor.known_publication_id),
            ) < (rule_rank[existing.rule_id], str(existing.known_publication_id)):
                evidence_by_key[key] = descriptor

    result: list[EnrichedLecturerScopusCandidate] = []
    for candidate in candidate_rows:
        evidence = tuple(
            sorted(
                (
                    descriptor
                    for (lecturer_id, scopus_author_id, _), descriptor in evidence_by_key.items()
                    if lecturer_id == candidate.lecturer_id
                    and scopus_author_id == candidate.scopus_author_id
                ),
                key=lambda item: (
                    item.canonical_publication_eid,
                    str(item.canonical_publication_id),
                ),
            )
        )
        result.append(EnrichedLecturerScopusCandidate.from_candidate(candidate, evidence))

    return PublicationEvidenceEnrichmentResult(tuple(result), conflicts)


class PublicationEvidenceEnricher:
    """Read-only bulk loader for canonical publication evidence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def enrich(
        self, candidates: Iterable[LecturerScopusCandidate]
    ) -> PublicationEvidenceEnrichmentResult:
        candidate_rows = tuple(candidates)
        if not candidate_rows:
            return PublicationEvidenceEnrichmentResult((), ())

        lecturer_ids = {candidate.lecturer_id for candidate in candidate_rows}
        known_publications = list(
            self._session.scalars(
                select(LecturerKnownPublication)
                .where(LecturerKnownPublication.lecturer_id.in_(lecturer_ids))
                .order_by(LecturerKnownPublication.id)
            )
        )
        snapshot_ids = {row.snapshot_id for row in known_publications}
        snapshots = (
            list(
                self._session.scalars(
                    select(LecturerSourceSnapshot)
                    .where(LecturerSourceSnapshot.id.in_(snapshot_ids))
                    .order_by(LecturerSourceSnapshot.id)
                )
            )
            if snapshot_ids
            else []
        )
        publications = list(self._session.scalars(select(Publication).order_by(Publication.id)))
        publication_authors = list(
            self._session.scalars(select(PublicationAuthor).order_by(PublicationAuthor.id))
        )
        return enrich_candidates(
            candidate_rows,
            known_publications,
            snapshots,
            publications,
            publication_authors,
        )
