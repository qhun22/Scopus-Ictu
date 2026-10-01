"""Raw Scopus ingestion models — M0 scaffolds.

Tables (from Architecture v1.1):
  4.  scopus_imports
  5.  raw_scopus_records

See master_lecturer.py for the rationale behind M0's inert base.
"""

from __future__ import annotations

_SENTINEL_BASE = object


class ScopusImport(_SENTINEL_BASE):
    """Header for a single Scopus CSV import batch — M0 skeleton.

    TODO(M1): filename, uploaded_by, imported_at, status, row counts.
    """

    __tablename__ = "scopus_imports"


class RawScopusRecord(_SENTINEL_BASE):
    """One raw Scopus row from a CSV import — M0 skeleton.

    Canonical identity is NOT decided here. EID lives on publications.
    TODO(M1): import_id FK, raw_payload, source_row_no, etc.
    """

    __tablename__ = "raw_scopus_records"