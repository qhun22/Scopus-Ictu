"""Governance & auditing models — M1.1 (frozen contract).

Tables (M1.0-B):
    14. users          (Mutable Governance Aggregate Root, versioned)
    15. audit_events   (Append-only)

This module is a strict 1:1 translation of the M1.0-B contracts and the
M1.0-A07 / M1.0-A08 / M1.0-A09 / M1.0-A12 / M1C-03 cross-cluster
decisions.

Per the original M1.1 directive §5 / §26 / §27 / §28:

    * No password hashing is performed in the ORM model.
    * No __repr__ exposes ``password_hash`` or any other secret.
    * The audit ``before_state`` / ``after_state`` payload is a generic
      JSONB column; the model itself does not provide convenience
      serializers that would ever produce a User object containing
      ``password_hash``.

The physical DB column ``audit_events.metadata`` keeps its exact name.
Per the resume directive §5 and the freeze record's reserved-name
clarification, the Python attribute is aliased to ``event_metadata``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


# ---------------------------------------------------------------------------
# 14. users — Mutable Governance Aggregate Root, versioned
# ---------------------------------------------------------------------------
class User(Base):
    """Application user (governance).

    M1.0-B §14. Optimistic locking per M1.0-A09. ``is_active`` is a
    business-domain flag (M1.0-A07), not a generic soft delete.
    ``password_hash`` is sensitive (C5-08) and is never exposed by
    the model's repr / equality / serialization machinery.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    lecturer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # CHECK (version >= 1) — FC-01: ck_users_version
        CheckConstraint("version >= 1", name="version"),
        # CHECK (btrim(email) <> '') — FC-01: ck_users_email_not_empty
        CheckConstraint("btrim(email) <> ''", name="email_not_empty"),
        # CHECK (btrim(display_name) <> '') — FC-01: ck_users_display_name_not_empty
        CheckConstraint(
            "btrim(display_name) <> ''", name="display_name_not_empty"
        ),
        # CHECK (role IN ('ADMIN','REVIEWER','LECTURER')) — M1C-03.
        # FC-01: ck_users_role
        CheckConstraint(
            "role IN ('ADMIN', 'REVIEWER', 'LECTURER')", name="role"
        ),
        # CHECK (role <> 'LECTURER' OR lecturer_id IS NOT NULL) — C5-04.
        # FC-01: ck_users_lecturer_account_required
        CheckConstraint(
            "role <> 'LECTURER' OR lecturer_id IS NOT NULL",
            name="lecturer_account_required",
        ),
        # C5-02: case-insensitive unique email.
        Index(
            "uq_users_email_ci",
            text("lower(email)"),
            unique=True,
        ),
        # C5-05: at most one user account per lecturer.
        Index(
            "uq_users_lecturer",
            "lecturer_id",
            unique=True,
            postgresql_where=text("lecturer_id IS NOT NULL"),
        ),
    )

    __mapper_args__ = {"version_id_col": version}


# ---------------------------------------------------------------------------
# 15. audit_events — Append-only
# ---------------------------------------------------------------------------
class AuditEvent(Base):
    """Append-only audit event (ADR-003).

    M1.0-B §15. Append-only per M1.0-A08. The actor invariant is
    enforced at the DB level (C5-13).
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    actor_service: Mapped[str | None] = mapped_column(String(100), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[IPv4Address | IPv6Address | None] = mapped_column(
        INET, nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The physical DB column is exactly `metadata`. The Python attribute
    # is aliased to ``event_metadata`` to avoid colliding with
    # ``DeclarativeBase.metadata``. The DB column is NOT renamed.
    event_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # CHECK (actor_type IN ('USER','SYSTEM')) — M1C-03.
        # FC-01: ck_audit_events_actor_type
        CheckConstraint(
            "actor_type IN ('USER', 'SYSTEM')", name="actor_type"
        ),
        # CHECK (entity_type ~ '^[a-z][a-z0-9_]*$')
        # FC-01: ck_audit_events_entity_type_format
        CheckConstraint(
            "entity_type ~ '^[a-z][a-z0-9_]*$'", name="entity_type_format"
        ),
        # CHECK (action ~ '^[A-Z][A-Z0-9_]*$')
        # FC-01: ck_audit_events_action_format
        CheckConstraint(
            "action ~ '^[A-Z][A-Z0-9_]*$'", name="action_format"
        ),
        # CHECK (actor invariant) — C5-13.
        # FC-01: ck_audit_events_actor_invariant
        CheckConstraint(
            "(actor_type = 'USER' AND actor_user_id IS NOT NULL "
            "                       AND actor_service IS NULL) "
            "OR "
            "(actor_type = 'SYSTEM' AND actor_user_id IS NULL "
            "                         AND actor_service IS NOT NULL "
            "                         AND btrim(actor_service) <> '')",
            name="actor_invariant",
        ),
        # CHECK (before_state IS NULL OR jsonb_typeof(before_state) = 'object')
        # FC-01: ck_audit_events_before_state_object
        CheckConstraint(
            "before_state IS NULL OR jsonb_typeof(before_state) = 'object'",
            name="before_state_object",
        ),
        # CHECK (after_state IS NULL OR jsonb_typeof(after_state) = 'object')
        # FC-01: ck_audit_events_after_state_object
        CheckConstraint(
            "after_state IS NULL OR jsonb_typeof(after_state) = 'object'",
            name="after_state_object",
        ),
        # CHECK (metadata IS NULL OR jsonb_typeof(metadata) = 'object')
        # FC-01: ck_audit_events_metadata_object
        CheckConstraint(
            "metadata IS NULL OR jsonb_typeof(metadata) = 'object'",
            name="metadata_object",
        ),
        Index(
            "ix_audit_events_entity",
            "entity_type",
            "entity_id",
            "created_at",
        ),
        Index("ix_audit_events_actor", "actor_user_id", "created_at"),
        Index("ix_audit_events_created", "created_at"),
        Index(
            "ix_audit_events_correlation",
            "correlation_id",
            postgresql_where=text("correlation_id IS NOT NULL"),
        ),
    )
