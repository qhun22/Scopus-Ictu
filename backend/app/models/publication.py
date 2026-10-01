"""Canonical publication models — M0 scaffolds.

Tables (from Architecture v1.1):
  6.  publications
  7.  publication_raw_sources
  8.  scopus_authors
  9.  scopus_author_name_variants
  10. publication_authors

See master_lecturer.py for the rationale behind M0's inert base.
"""

from __future__ import annotations

_SENTINEL_BASE = object


class Publication(_SENTINEL_BASE):
    """Canonical publication (Scopus) — M0 skeleton.

    Canonical external identity = EID (see ADR-001).
    TODO(M1): eid, doi, title, year, journal, raw_metadata, etc.
    """

    __tablename__ = "publications"


class PublicationRawSource(_SENTINEL_BASE):
    """Provenance join: canonical publication ↔ raw Scopus row (M0 skeleton).

    A single canonical publication may have multiple raw source rows
    across imports (see ADR-001).
    TODO(M1): publication_id FK, raw_scopus_record_id FK, captured_at, etc.
    """

    __tablename__ = "publication_raw_sources"


class ScopusAuthor(_SENTINEL_BASE):
    """Scopus author record (canonical) — M0 skeleton.

    TODO(M1): scopus_author_id, current_name, orcid, etc.
    """

    __tablename__ = "scopus_authors"


class ScopusAuthorNameVariant(_SENTINEL_BASE):
    """All known name variants for a Scopus author — M0 skeleton.

    TODO(M1): scopus_author_id FK, variant_name, language, etc.
    """

    __tablename__ = "scopus_author_name_variants"


class PublicationAuthor(_SENTINEL_BASE):
    """Publication ↔ Scopus author join — M0 skeleton.

    TODO(M1): publication_id FK, scopus_author_id FK, position, etc.
    """

    __tablename__ = "publication_authors"