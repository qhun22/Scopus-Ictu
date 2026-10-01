"""Audit repository — M0 scaffold.

ADR-003: audit is append-only. Repository MUST NOT expose update / delete.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.governance import AuditEvent


class AuditRepository:
    """Append-only audit event writer (M0 stub).

    TODO(M1): expose `append(event: AuditEvent) -> AuditEvent` and read-only
    listing helpers. Update and delete are intentionally omitted.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> AuditEvent:
        """Append a new audit event (M0 stub)."""
        raise NotImplementedError("AuditRepository.append not implemented in M0.")