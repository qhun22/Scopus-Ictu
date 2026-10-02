"""Custom exception types — M0 scaffold.

These are declared so services and API endpoints have a stable namespace.
Implementations come in M1+.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


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


class APIError(HTTPException):
    """HTTP error with a stable, flat machine-readable error code."""

    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        code: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    """Render the public error envelope used by API clients."""

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers=exc.headers,
    )
