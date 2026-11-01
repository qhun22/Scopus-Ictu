"""Per-lecturer publication exclusion history (Gate E.1 G09).

An approved Scopus ID attaches *all* of that author's publications to a lecturer. When a
Scopus profile mixes two people, an ADMIN needs to withdraw single papers from one
lecturer without touching the canonical publication, the Scopus author or the identity.

Append-only event log: ``EXCLUDE`` and ``INCLUDE`` (restore) rows with a mandatory reason
and actor. The effective state of a (lecturer, publication) pair is its latest event.
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

EXCLUSION_ACTIONS = ("EXCLUDE", "INCLUDE")

# BIGINT identity on PostgreSQL; a rowid alias on SQLite so offline tests can append.
_SEQ = BigInteger().with_variant(Integer, "sqlite")


class LecturerPublicationExclusionEvent(Base):
    __tablename__ = "lecturer_publication_exclusion_events"

    seq: Mapped[int] = mapped_column(_SEQ, primary_key=True, autoincrement=True)
    lecturer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturers.id", ondelete="RESTRICT", name="fk_lpee_lecturer_id"),
        nullable=False)
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="RESTRICT", name="fk_lpee_publication_id"),
        nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    acted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_lpee_acted_by_user_id"),
        nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("action IN ('EXCLUDE', 'INCLUDE')", name="action"),
        CheckConstraint("btrim(reason) <> ''", name="reason_not_empty"),
        Index("ix_lpee_pair_seq", "lecturer_id", "publication_id", "seq"),
    )
