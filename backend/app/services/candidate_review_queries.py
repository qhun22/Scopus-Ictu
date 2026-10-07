"""Shared read queries for the M2.7B candidate review boundary.

The current-observation rule is deliberately defined next to the reviewed
service and reused by the API read side.  A completed run is authoritative;
running and failed runs are never reviewable.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateObservation,
)


def latest_completed_observations_subquery():
    """Return one deterministic latest COMPLETED observation per candidate."""

    ranked = (
        select(
            LecturerScopusCandidateObservation.id.label("observation_id"),
            LecturerScopusCandidateObservation.candidate_id.label("candidate_id"),
            LecturerScopusCandidateObservation.generation_run_id.label(
                "generation_run_id"
            ),
            LecturerScopusCandidateObservation.observed_at.label("observed_at"),
            LecturerScopusCandidateObservation.observation_hash.label(
                "observation_hash"
            ),
            LecturerScopusCandidateObservation.created_at.label(
                "observation_created_at"
            ),
            CandidateGenerationRun.rule_set_version.label("rule_set_version"),
            CandidateGenerationRun.completed_at.label("run_completed_at"),
            CandidateGenerationRun.created_at.label("run_created_at"),
            func.row_number()
            .over(
                partition_by=LecturerScopusCandidateObservation.candidate_id,
                order_by=(
                    CandidateGenerationRun.completed_at.desc(),
                    CandidateGenerationRun.created_at.desc(),
                    CandidateGenerationRun.id.desc(),
                ),
            )
            .label("observation_rank"),
        )
        .join(
            CandidateGenerationRun,
            CandidateGenerationRun.id
            == LecturerScopusCandidateObservation.generation_run_id,
        )
        .where(CandidateGenerationRun.status == "COMPLETED")
        .subquery("latest_completed_observations")
    )
    return ranked


def current_reviewable_candidates_subquery(candidate_status: str):
    """Return a subquery of candidates that have a current COMPLETED observation.

    Shared semantic boundary for both the review queue and the dashboard
    pending-review count so the two cannot silently drift.
    """
    latest = latest_completed_observations_subquery()
    return (
        select(
            LecturerScopusCandidate.id.label("candidate_id"),
            latest.c.observation_id.label("current_observation_id"),
        )
        .select_from(LecturerScopusCandidate)
        .join(
            latest,
            (latest.c.candidate_id == LecturerScopusCandidate.id)
            & (latest.c.observation_rank == 1),
        )
        .where(LecturerScopusCandidate.status == candidate_status)
        .subquery("current_reviewable_candidates")
    )


def current_reviewable_observation(
    session: Session, candidate_id: uuid.UUID
) -> LecturerScopusCandidateObservation:
    """Resolve a candidate's current observation using the B4 service rule."""

    latest_run_id = session.scalar(
        select(LecturerScopusCandidateObservation.generation_run_id)
        .join(
            CandidateGenerationRun,
            CandidateGenerationRun.id
            == LecturerScopusCandidateObservation.generation_run_id,
        )
        .where(
            LecturerScopusCandidateObservation.candidate_id == candidate_id,
            CandidateGenerationRun.status == "COMPLETED",
        )
        .order_by(
            CandidateGenerationRun.completed_at.desc(),
            CandidateGenerationRun.created_at.desc(),
            CandidateGenerationRun.id.desc(),
        )
        .limit(1)
    )
    if latest_run_id is None:
        from app.services.candidate_review_service import ObservationNotFoundError

        raise ObservationNotFoundError(
            f"No observation from a COMPLETED generation run for candidate {candidate_id}"
        )

    observation = session.scalar(
        select(LecturerScopusCandidateObservation).where(
            LecturerScopusCandidateObservation.candidate_id == candidate_id,
            LecturerScopusCandidateObservation.generation_run_id == latest_run_id,
        )
    )
    if observation is None:
        from app.services.candidate_review_service import ObservationNotFoundError

        raise ObservationNotFoundError(
            f"Observation for candidate {candidate_id} in latest run {latest_run_id} not found"
        )
    return observation


__all__ = [
    "current_reviewable_candidates_subquery",
    "current_reviewable_observation",
    "latest_completed_observations_subquery",
]
