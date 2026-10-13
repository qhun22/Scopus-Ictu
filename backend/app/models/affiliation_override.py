"""ADMIN manual affiliation overrides (Priority 2/NO-JSON closure, additive).

An override is a human-entered statement that ONE publication author
position belongs to ONE organization, layered ON TOP of the automated
resolutions in ``affiliation.py`` — it never writes to
``publication_author_affiliation*``, never edits Scopus raw data, and never
deletes a prior automated resolution.

A publication author position may have MULTIPLE independent overrides
(e.g. a dual appointment) — each row is one unit statement with its own
lifecycle. ``status`` distinguishes *adding* a unit (ACTIVE) from
*revoking* it (REVOKED): revoking sets ``status``/``revoked_at``/
``revoked_by_user_id`` on that one row only and never deletes it, so the
audit trail and the row itself remain queryable. A partial unique index
blocks two ACTIVE rows with the same (position, unit text) — see
Alembic revision c7f2a9b1d3e5 — so revoking then re-adding the identical
text is allowed, but duplicating an already-active statement is not.

The full before/after history of every change is also in ``AuditEvent``
(entity_type ``publication_author_affiliation_override``, entity_id = this
row's id). ``version`` is an explicit, client-supplied optimistic lock
(same pattern as ``candidate_review_service``), so two ADMINs editing the
same row concurrently get a clear conflict instead of a silent overwrite.

An override's ``confidence`` is deliberately restricted to the same
"not independently verified" family the automated pipeline uses
(CORROBORATED / UNRESOLVED) — see the CHECK constraint. An ADMIN confirming
a record is evidence a human looked at it, not a new identity-verification
channel; it can never become VERIFIED through this table.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

OVERRIDE_CONFIDENCE_VALUES = ("CORROBORATED", "UNRESOLVED")
OVERRIDE_STATUS_VALUES = ("ACTIVE", "REVOKED")


class PublicationAuthorAffiliationOverride(Base):
    __tablename__ = "publication_author_affiliation_overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    publication_author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publication_authors.id", ondelete="CASCADE", name="fk_paao_publication_author_id"),
        nullable=False,
    )
    # Human-entered unit text (verbatim, as the ADMIN typed it / copied from the evidence).
    affiliation_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVE'"))
    # Free-text reason the automated pipeline left this UNRESOLVED or in conflict
    # (why a human needed to step in) — distinct from AuditEvent.reason, which is
    # the ADMIN's OWN stated reason for this specific edit.
    evidence_url: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT", name="fk_paao_created_by"), nullable=False
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT", name="fk_paao_updated_by"), nullable=False
    )
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT", name="fk_paao_revoked_by"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("confidence IN ('CORROBORATED', 'UNRESOLVED')", name="confidence"),
        CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="status"),
        CheckConstraint(
            "(status = 'ACTIVE' AND revoked_at IS NULL AND revoked_by_user_id IS NULL) OR "
            "(status = 'REVOKED' AND revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL)",
            name="revoked_state_consistent",
        ),
        CheckConstraint("btrim(affiliation_text) <> ''", name="affiliation_text_not_blank"),
        CheckConstraint("btrim(evidence_url) <> ''", name="evidence_url_not_blank"),
        CheckConstraint("btrim(reason) <> ''", name="reason_not_blank"),
        CheckConstraint("version >= 1", name="version"),
        Index("ix_paao_updated_at", "updated_at"),
        Index("ix_paao_publication_author_id", "publication_author_id"),
        # Partial unique index: blocks two ACTIVE rows with the same
        # (publication_author_id, affiliation_text) — duplicate protection
        # that still allows revoke-then-re-add of the identical text. Also
        # created verbatim (as raw SQL) by Alembic revision c7f2a9b1d3e5;
        # declared here too so Base.metadata.create_all() (used by isolated
        # test schemas) enforces the same constraint without running Alembic.
        Index(
            "uq_paao_active_position_text",
            "publication_author_id",
            "affiliation_text",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )


__all__ = ["OVERRIDE_CONFIDENCE_VALUES", "OVERRIDE_STATUS_VALUES", "PublicationAuthorAffiliationOverride"]
