"""Primary ("main") Scopus ID label per lecturer — append-only event history.

A lecturer may hold several APPROVED Scopus identities side by side (business rule BR-01).
This table records which one a human chose to show as the main ID. It is a **display
label only**: it never merges identities, never changes a publication set and never
touches ``lecturer_scopus_identities`` (a frozen contract), so it cannot create or confirm
a link by itself.

The effective primary of a lecturer is the latest event if it is a ``SET`` whose identity is
still APPROVED and still belongs to that lecturer; otherwise there is none.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

PRIMARY_ACTIONS = ("SET", "CLEAR")

# BIGINT identity on PostgreSQL; a rowid alias on SQLite so offline tests can append.
_SEQ = BigInteger().with_variant(Integer, "sqlite")


class LecturerPrimaryScopusEvent(Base):
    __tablename__ = "lecturer_primary_scopus_events"

    seq: Mapped[int] = mapped_column(_SEQ, primary_key=True, autoincrement=True)
    lecturer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturers.id", ondelete="RESTRICT", name="fk_lpse_lecturer_id"),
        nullable=False)
    identity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturer_scopus_identities.id", ondelete="RESTRICT",
                   name="fk_lpse_identity_id"),
        nullable=True)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    acted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_lpse_acted_by_user_id"),
        nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("action IN ('SET', 'CLEAR')", name="action"),
        CheckConstraint("btrim(reason) <> ''", name="reason_not_empty"),
        # SET names an identity; CLEAR names none.
        CheckConstraint("(action = 'SET') = (identity_id IS NOT NULL)",
                        name="identity_matches_action"),
        Index("ix_lpse_lecturer_seq", "lecturer_id", "seq"),
    )
