"""Identity matching — M0 scaffold.

Evidence strength order (canonical):
  1. Approved Scopus ID
  2. ORCID exact
  3. DOI / publication overlap
  4. Name + confirmed co-author evidence
  5. Fuzzy name
"""

from app.services.matching.candidate_generator import CandidateGenerator
from app.services.matching.engine import MatchingEngine
from app.services.matching.scoring import ScoreCalculator, ScoreResult

__all__ = [
    "MatchingEngine",
    "CandidateGenerator",
    "ScoreCalculator",
    "ScoreResult",
]