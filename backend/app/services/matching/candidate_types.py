"""Transient candidate-domain objects for deterministic identity retrieval.

Candidates and their evidence descriptors intentionally have no persistence
mapping.  They are retrieval facts, not identity decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

RuleId = Literal[
    "RULE_EXACT_N0",
    "RULE_TITLE_STRIPPED_N0",
    "RULE_TITLE_STRIPPED_N2",
    "RULE_TITLE_STRIPPED_N2_FORMAT",
]

PublicationEvidenceRuleId = Literal[
    "RULE_KNOWN_PUBLICATION_DOI_EXACT",
    "RULE_KNOWN_PUBLICATION_TITLE_EXACT",
]

PublicationReconciliation = Literal["DOI_EXACT", "TITLE_EXACT"]

SurfaceType = Literal["PREFERRED_NAME", "AUTHOR_FULL_NAME", "AUTHOR_DISPLAY"]


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """One explainable retrieval observation for a candidate pair."""

    rule_id: RuleId
    lecturer_source_value: str
    lecturer_comparison_value: str
    scopus_surface_type: SurfaceType
    scopus_surface_value: str
    scopus_comparison_value: str


@dataclass(frozen=True, slots=True)
class LecturerScopusCandidate:
    """Transient lecturer ↔ Scopus author candidate.

    ``scopus_id`` and ``preferred_name`` are read-only display snapshots from
    the canonical author row.  The UUID pair remains the identity of this
    candidate within the current dataset.
    """

    lecturer_id: UUID
    scopus_author_id: UUID
    scopus_id: str
    preferred_name: str
    evidence: tuple[CandidateEvidence, ...]

    @property
    def candidate_count_key(self) -> tuple[str, str]:
        """Stable pair key useful to callers without adding a ranking."""
        return str(self.lecturer_id), str(self.scopus_author_id)


@dataclass(frozen=True, slots=True)
class PublicationEvidence:
    """One transient, explainable known-publication observation.

    This is deliberately separate from :class:`CandidateEvidence`: the name
    candidate remains the retrieval fact and publication evidence is an
    additive enrichment.  No score, confidence, weight, or decision is stored
    here.
    """

    rule_id: PublicationEvidenceRuleId
    known_publication_id: UUID
    lecturer_id: UUID
    lecturer_snapshot_id: UUID
    canonical_publication_id: UUID
    canonical_publication_eid: str
    candidate_scopus_author_id: UUID
    known_publication_doi_normalized: str | None
    known_publication_title_normalized: str
    canonical_publication_doi: str | None
    canonical_publication_title: str
    reconciliation: PublicationReconciliation


@dataclass(frozen=True, slots=True)
class PublicationEvidenceConflict:
    """A reconciliation ambiguity/conflict exposed without creating support."""

    known_publication_id: UUID
    lecturer_id: UUID
    lecturer_snapshot_id: UUID
    reason: Literal[
        "DOI_AMBIGUOUS",
        "DOI_TITLE_CONFLICT",
        "TITLE_AMBIGUOUS",
        "SNAPSHOT_LECTURER_MISMATCH",
    ]
    doi_publication_ids: tuple[UUID, ...]
    title_publication_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class EnrichedLecturerScopusCandidate:
    """Existing candidate plus transient canonical publication evidence."""

    lecturer_id: UUID
    scopus_author_id: UUID
    scopus_id: str
    preferred_name: str
    evidence: tuple[CandidateEvidence, ...]
    publication_evidence: tuple[PublicationEvidence, ...]

    @property
    def name_evidence(self) -> tuple[CandidateEvidence, ...]:
        """Explicit alias for the unchanged candidate-generator evidence."""
        return self.evidence

    @property
    def candidate_count_key(self) -> tuple[str, str]:
        return str(self.lecturer_id), str(self.scopus_author_id)

    @classmethod
    def from_candidate(
        cls,
        candidate: LecturerScopusCandidate,
        publication_evidence: tuple[PublicationEvidence, ...],
    ) -> EnrichedLecturerScopusCandidate:
        return cls(
            lecturer_id=candidate.lecturer_id,
            scopus_author_id=candidate.scopus_author_id,
            scopus_id=candidate.scopus_id,
            preferred_name=candidate.preferred_name,
            evidence=candidate.evidence,
            publication_evidence=publication_evidence,
        )
