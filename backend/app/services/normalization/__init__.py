"""Normalization of raw Scopus import rows into canonical publications."""

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

__all__ = [
    "NormalizationCounters",
    "NormalizationResult",
    "Normalizer",
    "ProvenanceConflict",
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