"""Persistence layer — M0 scaffold.

Repositories own the persistence boundary. Services MUST NOT bypass them.
"""

from app.repositories.author_repository import (
    ScopusAuthorNameVariantRepository,
    ScopusAuthorRepository,
)
from app.repositories.audit_repository import AuditRepository
from app.repositories.base_repository import BaseRepository
from app.repositories.identity_repository import (
    IdentityEvidenceRepository,
    LecturerScopusIdentityRepository,
)
from app.repositories.import_repository import (
    RawScopusRecordRepository,
    ScopusImportRepository,
)
from app.repositories.lecturer_repository import (
    LecturerKnownPublicationRepository,
    LecturerRepository,
    LecturerSourceSnapshotRepository,
)
from app.repositories.publication_repository import (
    PublicationAuthorRepository,
    PublicationRawSourceRepository,
    PublicationRepository,
)
from app.repositories.review_repository import ReviewRepository

__all__ = [
    "BaseRepository",
    # lecturer
    "LecturerRepository",
    "LecturerSourceSnapshotRepository",
    "LecturerKnownPublicationRepository",
    # scopus imports
    "ScopusImportRepository",
    "RawScopusRecordRepository",
    # publications / authors
    "PublicationRepository",
    "PublicationRawSourceRepository",
    "PublicationAuthorRepository",
    "ScopusAuthorRepository",
    "ScopusAuthorNameVariantRepository",
    # identity / review
    "LecturerScopusIdentityRepository",
    "IdentityEvidenceRepository",
    "ReviewRepository",
    # governance
    "AuditRepository",
]