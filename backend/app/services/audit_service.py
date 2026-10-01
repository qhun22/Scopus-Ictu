"""Audit service — M0 scaffold.

Single writer for audit_events. Append-only per ADR-003.
"""

from __future__ import annotations


class AuditService:
    """M0 stub. TODO(M1): build and append AuditEvent rows for business actions."""

    def record(
        self,
        *,
        actor_user_id: int | None,
        action: str,
        entity_type: str | None,
        entity_id: int | None,
        payload: dict | None = None,
    ) -> None:
        """Record an audit event (M0 stub)."""
        raise NotImplementedError("AuditService.record not implemented in M0.")