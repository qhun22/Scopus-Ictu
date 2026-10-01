"""Master-data lecturer models — M0 scaffolds.

Tables (from Architecture v1.1):
  1.  lecturers
  2.  lecturer_source_snapshots
  3.  lecturer_known_publications

M0 declares class signatures only. The classes intentionally do NOT inherit
from app.models.base.Base so that SQLAlchemy does not attempt to register
empty mapped classes (which would force invented primary-key decisions in
violation of the M0 constraint "No speculative DB constraints may be invented").
M1 will switch the parent class to `Base` and add real columns.
"""

from __future__ import annotations

_SENTINEL_BASE = object


class Lecturer(_SENTINEL_BASE):
    """Canonical lecturer master record (M0 skeleton).

    TODO(M1): `class Lecturer(Base):` + concrete columns, indexes, constraints.
    """

    __tablename__ = "lecturers"


class LecturerSourceSnapshot(_SENTINEL_BASE):
    """Per-source snapshot of a lecturer (provenance) — M0 skeleton.

    TODO(M1): concrete columns + linkage to lecturers.
    """

    __tablename__ = "lecturer_source_snapshots"


class LecturerKnownPublication(_SENTINEL_BASE):
    """Lecture-known publication link (M0 skeleton).

    TODO(M1): lecturer_id FK, publication_external_id, evidence column.
    """

    __tablename__ = "lecturer_known_publications"