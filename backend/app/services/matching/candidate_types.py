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
