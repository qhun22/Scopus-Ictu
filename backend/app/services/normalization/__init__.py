"""Normalizers — M0 scaffold.

Normalizers perform deterministic normalization. No I/O, no DB access.
"""

from app.services.normalization.doi_normalizer import DoiNormalizer
from app.services.normalization.name_normalizer import NameNormalizer
from app.services.normalization.orcid_normalizer import OrcidNormalizer
from app.services.normalization.scopus_normalizer import (
    NormalizationCounters,
    NormalizationResult,
    Normalizer,
    ProvenanceConflict,
    create_publication_from_raw,
    is_eid_valid,
    is_publication_eid_unique_violation,
    is_unrelated_integrity_error,
    link_provenance,
    normalize_batch,
    normalize_eid,
    normalize_import,
    normalize_single_raw,
)
from app.services.normalization.text_normalizer import TextNormalizer
from app.services.normalization.title_normalizer import TitleNormalizer

__all__ = [
    "DoiNormalizer",
    "NameNormalizer",
    "NormalizationCounters",
    "NormalizationResult",
    "Normalizer",
    "OrcidNormalizer",
    "ProvenanceConflict",
    "TextNormalizer",
    "TitleNormalizer",
    "create_publication_from_raw",
    "is_eid_valid",
    "is_publication_eid_unique_violation",
    "is_unrelated_integrity_error",
    "link_provenance",
    "normalize_batch",
    "normalize_eid",
    "normalize_import",
    "normalize_single_raw",
]