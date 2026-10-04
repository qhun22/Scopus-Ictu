"""Identity matching — M0 scaffold.

Evidence strength order (canonical):
  1. Approved Scopus ID
  2. ORCID exact
  3. DOI / publication overlap
  4. Name + confirmed co-author evidence
  5. Fuzzy name
"""

from app.services.matching.candidate_generator import (
    OBSERVED_TITLE_PREFIXES,
    CandidateGenerator,
    generate_candidates,
    normalize_comma_equivalence,
    normalize_name_n0,
    normalize_name_n2,
    strip_observed_title_prefix,
)
from app.services.matching.candidate_types import CandidateEvidence, LecturerScopusCandidate
from app.services.matching.engine import MatchingEngine
from app.services.matching.scoring import ScoreCalculator, ScoreResult

__all__ = [
    "MatchingEngine",
    "CandidateGenerator",
    "CandidateEvidence",
    "LecturerScopusCandidate",
    "OBSERVED_TITLE_PREFIXES",
    "generate_candidates",
    "normalize_name_n0",
    "normalize_name_n2",
    "normalize_comma_equivalence",
    "strip_observed_title_prefix",
    "ScoreCalculator",
    "ScoreResult",
]
