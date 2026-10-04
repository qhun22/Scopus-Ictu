"""SQLAlchemy models — M1.1 (frozen contract).

All physical tables live in per-table modules:

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

The model package imports each module for its side effect of registering all
current tables with ``Base``. Candidate persistence remains separate from the
identity model so importing these models cannot imply identity creation.
"""

from app.models.base import Base

# M1.1 model package registration — import each module for its
# registration side effect. Candidate persistence is an additive pre-identity
# module alongside the frozen M1 tables.
from app.models import (  # noqa: F401  (registration side effect)
    candidate,
    governance,
    identity,
    master_lecturer,
    publication,
    scopus_raw,
)

__all__ = ["Base"]
