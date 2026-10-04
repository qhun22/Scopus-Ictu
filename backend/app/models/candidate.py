"""Durable pre-identity candidate persistence models.

These tables deliberately sit before the identity layer.  A candidate root is
an observed lecturer/Scopus-author pair; it is never an identity decision.
Observations, evidence, and future reviews are immutable history children.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CandidateGenerationRun(Base):
    """Mutable lifecycle root for one deterministic generation execution."""

    __tablename__ = "candidate_generation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    rule_set_id: Mapped[str] = mapped_column(Text, nullable=False)
    rule_set_version: Mapped[str] = mapped_column(Text, nullable=False)
    source_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'RUNNING'")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
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
        CheckConstraint("btrim(rule_set_id) <> ''", name="rule_set_id_not_empty"),
        CheckConstraint(
            "btrim(rule_set_version) <> ''", name="rule_set_version_not_empty"
        ),
        CheckConstraint("jsonb_typeof(source_state) = 'object'", name="source_state_object"),
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')", name="status"
        ),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint(
            "(status = 'RUNNING' AND completed_at IS NULL) OR "
            "(status IN ('COMPLETED', 'FAILED') AND completed_at IS NOT NULL)",
            name="completion_consistency",
        ),
        Index("ix_candidate_generation_runs_status_created", "status", "created_at"),
    )

    __mapper_args__ = {"version_id_col": version}


class LecturerScopusCandidate(Base):
    """Stable pre-identity candidate root for one lecturer/author pair."""

    __tablename__ = "lecturer_scopus_candidates"

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
        String(20), nullable=False, server_default=text("'PENDING'")
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
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
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'SUPERSEDED')",
            name="status",
        ),
        CheckConstraint("version >= 1", name="version"),
        UniqueConstraint(
            "lecturer_id",
            "scopus_author_id",
            name="uq_lecturer_scopus_candidates_pair",
        ),
        Index("ix_lecturer_scopus_candidates_lecturer", "lecturer_id"),
        Index("ix_lecturer_scopus_candidates_scopus_author", "scopus_author_id"),
        Index(
            "ix_lecturer_scopus_candidates_status_updated",
            "status",
            "updated_at",
        ),
    )

    __mapper_args__ = {"version_id_col": version}


class LecturerScopusCandidateObservation(Base):
    """Immutable observation of a candidate in one generation run."""

    __tablename__ = "lecturer_scopus_candidate_observations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturer_scopus_candidates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    generation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_generation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    candidate_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    observation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(candidate_snapshot) = 'object'",
            name="candidate_snapshot_object",
        ),
        CheckConstraint(
            "observation_hash ~ '^[0-9a-f]{64}$'", name="observation_hash"
        ),
        UniqueConstraint(
            "candidate_id",
            "generation_run_id",
            name="uq_candidate_observations_candidate_run",
        ),
        Index("ix_candidate_observations_candidate", "candidate_id", "created_at"),
        Index("ix_candidate_observations_run", "generation_run_id"),
    )


class LecturerScopusCandidateEvidence(Base):
    """Immutable evidence descriptor attached to one observation."""

    __tablename__ = "lecturer_scopus_candidate_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturer_scopus_candidate_observations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSONB, nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "evidence_kind IN ('NAME', 'PUBLICATION')", name="evidence_kind"
        ),
        CheckConstraint("btrim(rule_id) <> ''", name="rule_id_not_empty"),
        CheckConstraint("btrim(rule_version) <> ''", name="rule_version_not_empty"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
        CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'", name="source_refs_array"
        ),
        CheckConstraint(
            "evidence_fingerprint ~ '^[0-9a-f]{64}$'",
            name="evidence_fingerprint",
        ),
        UniqueConstraint(
            "observation_id",
            "rule_id",
            "rule_version",
            "evidence_fingerprint",
            name="uq_candidate_evidence_descriptor",
        ),
        Index("ix_candidate_evidence_observation", "observation_id", "created_at"),
    )


class LecturerScopusCandidateReview(Base):
    """Append-only future review history for a candidate root."""

    __tablename__ = "lecturer_scopus_candidate_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturer_scopus_candidates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturer_scopus_candidate_observations.id", ondelete="RESTRICT"),
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
    candidate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    resulting_identity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lecturer_scopus_identities.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('ACCEPT', 'REJECT', 'REOPEN')", name="action"
        ),
        CheckConstraint(
            "from_status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'SUPERSEDED')",
            name="from_status",
        ),
        CheckConstraint(
            "to_status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'SUPERSEDED')",
            name="to_status",
        ),
        CheckConstraint("candidate_version >= 1", name="candidate_version"),
        CheckConstraint(
            "jsonb_typeof(evidence_snapshot) = 'object'",
            name="evidence_snapshot_object",
        ),
        CheckConstraint(
            "action = 'ACCEPT' OR (reason IS NOT NULL AND btrim(reason) <> '')",
            name="reason_required",
        ),
        CheckConstraint(
            "(action = 'ACCEPT' AND from_status = 'PENDING' AND to_status = 'ACCEPTED') "
            "OR (action = 'REJECT' AND from_status = 'PENDING' AND to_status = 'REJECTED') "
            "OR (action = 'REOPEN' AND from_status IN "
            "('ACCEPTED', 'REJECTED', 'SUPERSEDED') AND to_status = 'PENDING')",
            name="transitions",
        ),
        Index(
            "ix_candidate_reviews_candidate_created",
            "candidate_id",
            "created_at",
        ),
        Index("ix_candidate_reviews_observation", "observation_id"),
        Index("ix_candidate_reviews_reviewer", "reviewer_user_id"),
    )
