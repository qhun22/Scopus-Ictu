"""Identity resolution & human review models — M1.1 (frozen contract).

Tables (M1.0-B):
    11. lecturer_scopus_identities  (Mutable Human-Governed Aggregate Root)
    12. identity_evidence           (Append-only)
    13. mapping_reviews              (Append-only)

This module is a strict 1:1 translation of the M1.0-B contracts and the
M1C-03 vocabulary decisions. The audit actor invariant lives in
audit_events, not here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


# ---------------------------------------------------------------------------
# 11. lecturer_scopus_identities — Mutable Human-Governed Aggregate Root
# ---------------------------------------------------------------------------
class LecturerScopusIdentity(Base):
    """Approved lecturer ↔ Scopus author mapping.

    M1.0-B §11. Optimistic locking per M1.0-A09. Status / recommendation
    vocabularies per M1C-03. The ``recommendation`` triplet
    (recommendation, recommendation_algorithm_version, recommended_at)
    must be all-NULL or all-NOT-NULL.
    """

    __tablename__ = "lecturer_scopus_identities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    lecturer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scopus_author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scopus_authors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'CANDIDATE'")
    )
    recommendation: Mapped[str | None] = mapped_column(String(30), nullable=True)
    recommendation_algorithm_version: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    recommended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
        # CHECK (version >= 1) — FC-01: ck_lecturer_scopus_identities_version
        CheckConstraint("version >= 1", name="version"),
        # CHECK (status IN ('CANDIDATE','APPROVED','REJECTED','REVOKED')) — M1C-03.
        # FC-01: ck_lecturer_scopus_identities_status
        CheckConstraint(
            "status IN ('CANDIDATE', 'APPROVED', 'REJECTED', 'REVOKED')",
            name="status",
        ),
        # CHECK (recommendation IS NULL OR
        #        recommendation IN ('MATCH','NO_MATCH','MANUAL_VERIFY')) — M1C-03.
        # FC-01: ck_lecturer_scopus_identities_recommendation
        CheckConstraint(
            "recommendation IS NULL OR "
            "recommendation IN ('MATCH', 'NO_MATCH', 'MANUAL_VERIFY')",
            name="recommendation",
        ),
        # All-NULL or all-NOT-NULL triplet.
        # FC-01: ck_lecturer_scopus_identities_recommendation_consistency
        CheckConstraint(
            "(recommendation IS NULL AND "
            " recommendation_algorithm_version IS NULL AND "
            " recommended_at IS NULL) "
            "OR "
            "(recommendation IS NOT NULL AND "
            " recommendation_algorithm_version IS NOT NULL AND "
            " recommended_at IS NOT NULL)",
            name="recommendation_consistency",
        ),
        # C4-03
        UniqueConstraint(
            "lecturer_id",
            "scopus_author_id",
            name="uq_lecturer_scopus_identities_pair",
        ),
        # C4-04: a Scopus author can be APPROVED for at most one lecturer.
        # Partial unique index — explicit name.
        Index(
            "uq_identities_scopus_author_approved",
            "scopus_author_id",
            unique=True,
            postgresql_where=text("status = 'APPROVED'"),
        ),
        Index("ix_identities_scopus_author_id", "scopus_author_id"),
        Index("ix_identities_status_updated", "status", "updated_at"),
    )

    __mapper_args__ = {"version_id_col": version}


# ---------------------------------------------------------------------------
# 12. identity_evidence — Append-only
# ---------------------------------------------------------------------------
class IdentityEvidence(Base):
    """Evidence supporting an identity decision.

    M1.0-B §12. Append-only per M1.0-A08. The numeric confidence score
    is normalized to [0.0, 1.0] (C4-09). Fingerprint regex per M1C-04.
    """

    __tablename__ = "identity_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturer_scopus_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(100), nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSONB, nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0) — C4-09.
        # FC-01: ck_identity_evidence_confidence_score
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="confidence_score",
        ),
        # CHECK (direction IN ('SUPPORTS','CONTRADICTS')) — M1C-03.
        # FC-01: ck_identity_evidence_direction
        CheckConstraint(
            "direction IN ('SUPPORTS', 'CONTRADICTS')", name="direction"
        ),
        # CHECK (evidence_type IN (... 7 literals ...)) — M1C-03.
        # FC-01: ck_identity_evidence_evidence_type
        CheckConstraint(
            "evidence_type IN ("
            "'APPROVED_ID', 'ORCID_EXACT', 'DOI_EXACT', "
            "'PUBLICATION_OVERLAP', 'COAUTHOR_CONFIRMED', "
            "'NAME_SIMILARITY', 'AFFILIATION_MATCH')",
            name="evidence_type",
        ),
        # CHECK (evidence_fingerprint ~ '^[0-9a-f]{64}$') — M1C-04.
        # FC-01: ck_identity_evidence_fingerprint
        CheckConstraint(
            "evidence_fingerprint ~ '^[0-9a-f]{64}$'", name="fingerprint"
        ),
        # CHECK (jsonb_typeof(features) = 'object') — M1.0-A12.
        # FC-01: ck_identity_evidence_features_object
        CheckConstraint(
            "jsonb_typeof(features) = 'object'", name="features_object"
        ),
        # CHECK (jsonb_typeof(source_refs) = 'array') — M1.0-A12.
        # FC-01: ck_identity_evidence_source_refs_array
        CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'", name="source_refs_array"
        ),
        # C4-12: dedup constraint over the meaningful columns.
        UniqueConstraint(
            "identity_id",
            "evidence_type",
            "algorithm_version",
            "evidence_fingerprint",
            name="uq_identity_evidence_dedup",
        ),
        Index("ix_identity_evidence_created_at", "created_at"),
    )


# ---------------------------------------------------------------------------
# 13. mapping_reviews — Append-only
# ---------------------------------------------------------------------------
class MappingReview(Base):
    """Review workflow record for a mapping.

    M1.0-B §13. Append-only per M1.0-A08. State transitions are
    enforced at the DB level (C4-15); the compensates_review_id
    semantics are enforced at the DB level too (C4-16).
    """

    __tablename__ = "mapping_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturer_scopus_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    compensates_review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mapping_reviews.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        # CHECK (action IN ('APPROVE','REJECT','REVOKE','REOPEN')) — M1C-03.
        # FC-01: ck_mapping_reviews_action
        CheckConstraint(
            "action IN ('APPROVE', 'REJECT', 'REVOKE', 'REOPEN')",
            name="action",
        ),
        # CHECK (jsonb_typeof(evidence_snapshot) = 'object') — M1.0-A12.
        # FC-01: ck_mapping_reviews_evidence_snapshot_object
        CheckConstraint(
            "jsonb_typeof(evidence_snapshot) = 'object'",
            name="evidence_snapshot_object",
        ),
        # CHECK (action-driven from_status -> to_status transitions) — C4-15.
        # FC-01: ck_mapping_reviews_transitions
        CheckConstraint(
            "(action = 'APPROVE' AND from_status = 'CANDIDATE' AND to_status = 'APPROVED') "
            "OR "
            "(action = 'REJECT'  AND from_status = 'CANDIDATE' AND to_status = 'REJECTED') "
            "OR "
            "(action = 'REVOKE'  AND from_status = 'APPROVED'  AND to_status = 'REVOKED') "
            "OR "
            "(action = 'REOPEN'  AND from_status IN ('REJECTED', 'REVOKED') "
            "                    AND to_status = 'CANDIDATE')",
            name="transitions",
        ),
        # CHECK (action = 'APPROVE' OR reason required) — C4-17.
        # FC-01: ck_mapping_reviews_reason_required
        CheckConstraint(
            "action = 'APPROVE' OR (reason IS NOT NULL AND btrim(reason) <> '')",
            name="reason_required",
        ),
        # CHECK (compensates_review_id presence driven by action) — C4-16.
        # FC-01: ck_mapping_reviews_compensates
        CheckConstraint(
            "(action IN ('APPROVE', 'REJECT') AND compensates_review_id IS NULL) "
            "OR "
            "(action IN ('REVOKE', 'REOPEN') AND compensates_review_id IS NOT NULL)",
            name="compensates",
        ),
        Index("ix_mapping_reviews_identity_id", "identity_id"),
        Index("ix_mapping_reviews_reviewer", "reviewer_user_id"),
        Index(
            "ix_mapping_reviews_compensates",
            "compensates_review_id",
            postgresql_where=text("compensates_review_id IS NOT NULL"),
        ),
    )
