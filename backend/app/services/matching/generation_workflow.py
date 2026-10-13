"""ADMIN workflow for running candidate generation from the web app.

Thin orchestration over the same services the operator CLI
(``scripts/generate_matching_candidates.py``) already uses — this module
exists because that CLI is explicitly never started by the web app (it
takes a database connection string and filesystem manifest path as
command-line arguments, which a request must never supply). The request
here carries no parameters at all beyond the confirming POST itself; the
service decides everything else, exactly like ``AffiliationWorkflowApply``.

Pipeline, one read-write transaction:

    CandidateGenerator.generate_all()              (name-matching candidates)
      -> PublicationEvidenceEnricher.enrich()       (adds Craw evidence to
                                                      candidates already found)
      -> discover_craw_assisted_candidates()        (NEW pairs anchored by
                                                      author position + weak
                                                      name correspondence —
                                                      see craw_assisted_discovery.py)
      -> CandidatePersistenceService.persist_generation()

A generation run_id is minted by this workflow, never accepted from the
request, so a caller cannot replay or collide with another run's id.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master_lecturer import Lecturer, LecturerKnownPublication, LecturerSourceSnapshot
from app.models.publication import (
    Publication,
    PublicationAuthor,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.services.matching.candidate_generator import CandidateGenerator
from app.services.matching.candidate_persistence import (
    CandidatePersistenceService,
    GenerationRunConflict,
    GenerationRunSpec,
    GenerationRunStateError,
    build_source_state,
)
from app.services.matching.candidate_types import EnrichedLecturerScopusCandidate
from app.services.matching.craw_assisted_discovery import discover_craw_assisted_candidates
from app.services.matching.publication_evidence_enricher import PublicationEvidenceEnricher


class GenerationWorkflowError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


@dataclass(frozen=True, slots=True)
class GenerationRunSummary:
    run_id: uuid.UUID
    run_status: str
    candidate_roots: int
    observations: int
    evidence: int
    idempotent_replay: bool
    name_candidates: int
    craw_assisted_candidates: int
    craw_unattributed: int
    publication_conflicts: int


def _load_all(
    session: Session,
) -> tuple[
    list[Lecturer],
    list[ScopusAuthor],
    list[ScopusAuthorNameVariant],
    list[LecturerKnownPublication],
    list[LecturerSourceSnapshot],
    list[Publication],
    list[PublicationAuthor],
]:
    lecturers = list(session.scalars(select(Lecturer).order_by(Lecturer.id)))
    authors = list(session.scalars(select(ScopusAuthor).order_by(ScopusAuthor.id)))
    variants = list(
        session.scalars(select(ScopusAuthorNameVariant).order_by(ScopusAuthorNameVariant.id))
    )
    known_publications = list(
        session.scalars(select(LecturerKnownPublication).order_by(LecturerKnownPublication.id))
    )
    snapshots = list(
        session.scalars(select(LecturerSourceSnapshot).order_by(LecturerSourceSnapshot.id))
    )
    publications = list(session.scalars(select(Publication).order_by(Publication.id)))
    publication_authors = list(
        session.scalars(select(PublicationAuthor).order_by(PublicationAuthor.id))
    )
    return (
        lecturers,
        authors,
        variants,
        known_publications,
        snapshots,
        publications,
        publication_authors,
    )


def build_candidates(
    session: Session,
) -> tuple[tuple[EnrichedLecturerScopusCandidate, ...], dict[str, Any], int, int]:
    """Run the full generation + enrichment + Craw-assisted discovery pass.

    Returns (candidates, source_state, publication_conflicts, craw_unattributed_count).
    """

    (
        lecturers,
        authors,
        variants,
        known_publications,
        snapshots,
        publications,
        publication_authors,
    ) = _load_all(session)

    name_candidates = CandidateGenerator(session).generate_all()
    enrichment = PublicationEvidenceEnricher(session).enrich(name_candidates)

    existing_pairs = {(c.lecturer_id, c.scopus_author_id) for c in enrichment.candidates}
    craw_discovery = discover_craw_assisted_candidates(
        existing_pairs,
        known_publications,
        snapshots,
        publications,
        publication_authors,
        authors,
        variants,
        lecturers,
    )

    all_candidates = tuple(enrichment.candidates) + craw_discovery.discovered
    source_state = build_source_state(session)
    total_conflicts = len(enrichment.conflicts) + len(craw_discovery.conflicts)
    return all_candidates, source_state, total_conflicts, len(craw_discovery.unattributed)


def run_generation(session: Session) -> GenerationRunSummary:
    """Generate and persist candidates for one ADMIN-triggered run.

    No application-level lock serializes concurrent runs here: two clicks
    racing each other mint two different run_ids and simply produce two
    COMPLETED ``CandidateGenerationRun`` rows over the same source data —
    ``CandidatePersistenceService`` already makes that safe without any
    help from this module, via ``ON CONFLICT DO NOTHING`` on the candidate
    root (lecturer_id, scopus_author_id) unique constraint and
    ``with_for_update()`` row locks on the root and on each observation
    while writing, exactly as it already needs to be for two REVIEWERs or
    a retried CLI run. Adding a session-scoped advisory lock here was tried
    and reverted: it is not safe to hold across the ``session.commit()``
    this function needs between generation and persistence, because that
    commit can hand the ORM Session a different pooled connection for its
    next statement — the lock stays with the old connection, silently
    orphaned, while this function wrongly believes it still holds it.
    """

    candidates, source_state, publication_conflicts, craw_unattributed = build_candidates(session)
    session.commit()  # end the read phase; persist_generation begins its own transaction

    run_id = uuid.uuid4()
    spec = GenerationRunSpec(run_id=run_id, source_state=source_state, started_at=datetime.now(UTC))
    try:
        result = CandidatePersistenceService(session).persist_generation(spec, candidates)
    except (GenerationRunConflict, GenerationRunStateError) as exc:
        raise GenerationWorkflowError(
            "GENERATION_RUN_CONFLICT", str(exc), status_code=409
        ) from exc

    name_count = sum(1 for c in candidates if c.name_evidence)
    craw_assisted_count = sum(1 for c in candidates if not c.name_evidence)
    return GenerationRunSummary(
        run_id=result.run_id,
        run_status=result.run_status,
        candidate_roots=result.candidate_roots,
        observations=result.observations,
        evidence=result.evidence,
        idempotent_replay=result.idempotent_replay,
        name_candidates=name_count,
        craw_assisted_candidates=craw_assisted_count,
        craw_unattributed=craw_unattributed,
        publication_conflicts=publication_conflicts,
    )


__all__ = [
    "GenerationRunSummary",
    "GenerationWorkflowError",
    "build_candidates",
    "run_generation",
]
