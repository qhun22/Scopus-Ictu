"""Matching rules — M0 scaffold.

Evidence strength order (canonical):
  1. Approved Scopus ID
  2. ORCID exact
  3. DOI / publication overlap
  4. Name + confirmed co-author evidence
  5. Fuzzy name
"""

from app.services.matching.rules.approved_id_rule import ApprovedIdRule
from app.services.matching.rules.base_rule import BaseRule
from app.services.matching.rules.coauthor_rule import CoauthorRule
from app.services.matching.rules.fuzzy_name_rule import FuzzyNameRule
from app.services.matching.rules.orcid_rule import OrcidRule
from app.services.matching.rules.publication_overlap_rule import PublicationOverlapRule

__all__ = [
    "BaseRule",
    "ApprovedIdRule",
    "OrcidRule",
    "PublicationOverlapRule",
    "CoauthorRule",
    "FuzzyNameRule",
]