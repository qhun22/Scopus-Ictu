"""User-submitted issue reports (additive): the feedback loop from readers of
the data back to the people who maintain it.

Any logged-in user (lecturer, reviewer, admin) can report something they
noticed looking wrong -- most commonly "this publication's unit looks wrong"
or "this author link points to the wrong lecturer". A report is a plain
statement of what the user observed and never changes any data by itself:
it carries no confidence, no evidence requirement, and writes nothing to
``publication_author_affiliation*`` or the candidate/identity tables. An
ADMIN or REVIEWER reads the queue and, if they agree, makes the actual
correction through the existing affiliation-override
(``PublicationAuthorAffiliationOverride``) or candidate-review workflow --
this table is only the intake queue, never a second confidence channel.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

FEEDBACK_CATEGORY_VALUES = ("WRONG_AFFILIATION", "WRONG_AUTHOR_LINK", "OTHER")
FEEDBACK_STATUS_VALUES = ("OPEN", "RESOLVED", "DISMISSED")


class FeedbackReport(Base):
    __tablename__ = "feedback_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_feedback_reporter"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional pointer to the publication the report is about; a plain EID
    # string (not a foreign key) so a report about a mistyped/missing EID
    # the reporter copied by hand never fails to save for that reason alone.
    publication_eid: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'OPEN'"))
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_feedback_resolved_by"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('WRONG_AFFILIATION', 'WRONG_AUTHOR_LINK', 'OTHER')", name="category"
        ),
        CheckConstraint("status IN ('OPEN', 'RESOLVED', 'DISMISSED')", name="status"),
        CheckConstraint(
            "(status = 'OPEN' AND resolved_at IS NULL AND resolved_by_user_id IS NULL) OR "
            "(status != 'OPEN' AND resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)",
            name="resolved_state_consistent",
        ),
        CheckConstraint("btrim(message) <> ''", name="message_not_blank"),
        Index("ix_feedback_status_created_at", "status", "created_at"),
    )


__all__ = ["FEEDBACK_CATEGORY_VALUES", "FEEDBACK_STATUS_VALUES", "FeedbackReport"]
