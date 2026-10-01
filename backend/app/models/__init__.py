"""SQLAlchemy models — M0 scaffold.

All 15 physical tables (13 domain + 2 governance) live in per-table modules:

  app.models.master_lecturer      Lecturer, LecturerSourceSnapshot,
                                  LecturerKnownPublication
  app.models.scopus_raw           ScopusImport, RawScopusRecord
  app.models.publication          Publication, PublicationRawSource,
                                  ScopusAuthor, ScopusAuthorNameVariant,
                                  PublicationAuthor
  app.models.identity             LecturerScopusIdentity, IdentityEvidence,
                                  MappingReview
  app.models.governance           User, AuditEvent

We intentionally do NOT re-export models from this package to avoid
duplicate registration under SQLAlchemy 2.x. Import each model from its
defining submodule.

Concrete column definitions, constraints, and relationships belong to M1.
"""

from app.models.base import Base

__all__ = ["Base"]