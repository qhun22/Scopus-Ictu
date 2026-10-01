"""Scoring — M0 HIGH-RISK STUB.

Allowed in M0:
  - DTOs
  - signatures
  - result types
Prohibited in M0:
  - weights
  - thresholds
  - formulas
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceKind(str, Enum):
    """Canonical evidence kinds (see ADR-004 ordering)."""

    APPROVED_SCOPUS_ID = "approved_scopus_id"
    ORCID_EXACT = "orcid_exact"
    DOI_OR_PUBLICATION_OVERLAP = "doi_or_publication_overlap"
    NAME_PLUS_COAUTHOR = "name_plus_coauthor"
    FUZZY_NAME = "fuzzy_name"


@dataclass(frozen=True)
class ScoreResult:
    """M0 stub. TODO(M1): numeric score + matched evidence kinds + strength rank."""

    evidence_kinds: list[EvidenceKind]


class ScoreCalculator:
    """M0 stub. TODO(M1): combine evidence into a deterministic ordering."""

    def score(self, context) -> ScoreResult:
        raise NotImplementedError("ScoreCalculator.score not implemented in M0.")