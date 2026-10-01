"""SQLAlchemy models — M1.1 (frozen contract).

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

We intentionally do NOT re-export model classes from this package to
avoid duplicate registration under SQLAlchemy 2.x. Import each model
from its defining submodule if you need the class symbol.

The M1.1 milestone requires ``Base.metadata`` to see all 15 tables
when ``app.models`` is imported, so each per-table module is imported
here for its side effect of registering the model with ``Base``.
This is the M1.1 "model package registration" step.
"""

from app.models.base import Base

# M1.1 model package registration — import each module for its
# registration side effect. The five modules map to the 15 physical
# tables defined by the M1.0-B contract.
from app.models import (  # noqa: F401  (registration side effect)
    governance,
    identity,
    master_lecturer,
    publication,
    scopus_raw,
)

__all__ = ["Base"]
