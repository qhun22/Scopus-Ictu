"""Scopus import pipeline — M0 scaffold.

Module boundaries only. Future pipeline:

  CSV Upload
    -> Raw ingestion
    -> Parsing
    -> Validation
    -> Staging
    -> Normalization
    -> Deduplication
    -> Diff Preview
    -> Candidate Generation
    -> Evidence Generation
    -> Approval Queue
    -> Apply Canonical Changes
    -> Audit

No execution logic in M0.
"""

from app.services.import_pipeline.apply_service import ApplyCanonicalChangesService
from app.services.import_pipeline.deduplicator import Deduplicator
from app.services.import_pipeline.diff_builder import DiffBuilder
from app.services.import_pipeline.normalizer import ImportNormalizer
from app.services.import_pipeline.orchestrator import ImportOrchestrator
from app.services.import_pipeline.staging_service import StagingService
from app.services.import_pipeline.validator import ImportValidator

__all__ = [
    "ImportOrchestrator",
    "ImportValidator",
    "StagingService",
    "ImportNormalizer",
    "Deduplicator",
    "DiffBuilder",
    "ApplyCanonicalChangesService",
]