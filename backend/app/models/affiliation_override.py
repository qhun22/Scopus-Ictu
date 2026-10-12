"""ADMIN manual affiliation overrides (Priority 2, additive).

An override is a human-entered statement about ONE publication author
position's affiliation, layered ON TOP of the automated resolutions in
``affiliation.py`` — it never writes to ``publication_author_affiliation*``,
never edits Scopus raw data, and never deletes a prior automated resolution.

Exactly one row per ``publication_author_id`` (the "current" override); the
full before/after history of every change is in ``AuditEvent`` (entity_type
``publication_author_affiliation_override``, entity_id = this row's id),
not duplicated here. ``version`` is an explicit, client-supplied optimistic
lock (same pattern as ``candidate_review_service``), so two ADMINs editing
the same position concurrently get a clear conflict instead of a silent
overwrite.

An override's ``confidence`` is deliberately restricted to the same
"not independently verified" family the automated pipeline uses
(CORROBORATED / UNRESOLVED) — see the CHECK constraint. An ADMIN confirming
a record is evidence a human looked at it, not a new identity-verification
channel; it can never become VERIFIED through this table.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

OVERRIDE_CONFIDENCE_VALUES = ("CORROBORATED", "UNRESOLVED")


class PublicationAuthorAffiliationOverride(Base):
    __tablename__ = "publication_author_affiliation_overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    publication_author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publication_authors.id", ondelete="CASCADE", name="fk_paao_publication_author_id"),
        nullable=False,
        unique=True,
    )
    # Human-entered unit text (verbatim, as the ADMIN typed it / copied from the evidence).
    affiliation_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
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
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("publication_author_id", name="uq_paao_publication_author_id"),
        CheckConstraint("confidence IN ('CORROBORATED', 'UNRESOLVED')", name="confidence"),
        CheckConstraint("btrim(affiliation_text) <> ''", name="affiliation_text_not_blank"),
        CheckConstraint("btrim(evidence_url) <> ''", name="evidence_url_not_blank"),
        CheckConstraint("btrim(reason) <> ''", name="reason_not_blank"),
        CheckConstraint("version >= 1", name="version"),
        Index("ix_paao_updated_at", "updated_at"),
    )


__all__ = ["OVERRIDE_CONFIDENCE_VALUES", "PublicationAuthorAffiliationOverride"]
