"""Custom exception types — M0 scaffold.

These are declared so services and API endpoints have a stable namespace.
Implementations come in M1+.
"""

from __future__ import annotations


class ScopusIctuError(Exception):
    """Base exception for the application."""

    pass


class NotFoundError(ScopusIctuError):
    """Raised when a requested resource does not exist."""

    pass


class ValidationError(ScopusIctuError):
    """Raised when input data fails validation."""

    pass


class IntegrityError(ScopusIctuError):
    """Raised when a DB constraint is violated."""

    pass


class ImportPipelineError(ScopusIctuError):
    """Raised when the Scopus import pipeline encounters an error."""

    pass


class MatchingError(ScopusIctuError):
    """Raised when the matching engine encounters an error."""

    pass


class AuditError(ScopusIctuError):
    """Raised when an audit write fails."""

    pass


class DSpaceSnapshotError(ScopusIctuError):
    """Raised when an ICTU DSpace snapshot operation fails."""

    pass