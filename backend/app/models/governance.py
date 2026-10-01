"""Governance models — M0 scaffolds.

Tables (from Architecture v1.1):
  14. users
  15. audit_events

See master_lecturer.py for the rationale behind M0's inert base.
"""

from __future__ import annotations

_SENTINEL_BASE = object


class User(_SENTINEL_BASE):
    """Application user (M0 skeleton).

    TODO(M1): email, hashed_password, role, is_active, created_at, etc.
    """

    __tablename__ = "users"


class AuditEvent(_SENTINEL_BASE):
    """Append-only audit event (see ADR-003) — M0 skeleton.

    TODO(M1): actor_user_id, action, entity_type, entity_id, payload,
    occurred_at, prev_hash, hash — append-only constraints.
    """

    __tablename__ = "audit_events"