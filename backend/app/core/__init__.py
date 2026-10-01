"""Core module — M0 scaffold.

Provides: config, database, security, exceptions, logging.
"""

from app.core.config import Settings, settings
from app.core.exceptions import (
    ScopusIctuError,
    NotFoundError,
    ValidationError,
    IntegrityError,
    ImportPipelineError,
    MatchingError,
    AuditError,
    DSpaceSnapshotError,
)
from app.core.logging import setup_logging, logger

__all__ = [
    "Settings",
    "settings",
    "ScopusIctuError",
    "NotFoundError",
    "ValidationError",
    "IntegrityError",
    "ImportPipelineError",
    "MatchingError",
    "AuditError",
    "DSpaceSnapshotError",
    "setup_logging",
    "logger",
]