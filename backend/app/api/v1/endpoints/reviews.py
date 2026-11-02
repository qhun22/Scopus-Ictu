"""Thin REST boundary for durable M2.7B candidate human review."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from datetime import datetime

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
)
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.models.publication import (
    Publication,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.schemas.review_history_api import ReviewHistoryResponse
from app.services.review_history_queries import list_review_history
from app.schemas.review_api import (
    ReviewAmbiguityContext,
    ReviewAuthorDetail,
    ReviewAuthorSummary,
    ReviewCandidateDetailResponse,
    ReviewContextResponse,
    ReviewDecisionPolicy,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewLecturerDetail,
    ReviewLecturerSummary,
    MergeGuideLecturer,
    MergeGuideResponse,
    ReviewFit,
    ReviewGroupAcceptRequest,
    ReviewGroupAcceptResponse,
    ReviewGroupAcceptedItem,
    ReviewObservationResponse,
    ReviewRevocationRequest,
    ReviewRevocationResponse,
    ReviewOtherCandidateSummary,
    ReviewQueueItem,
    ReviewQueueResponse,
)
from app.services.candidate_review_queries import (
    current_reviewable_candidates_subquery,
    current_reviewable_observation,
    latest_completed_observations_subquery,
)
from app.services.candidate_review_service import (
    AcceptCandidateCommand,
    CandidateAlreadyDecidedError,
    CandidateNotAcceptedError,
    IdentityRevokedError,
    RevocationReasonRequiredError,
    RevokeIdentityCommand,
    CandidateNotFoundError,
    CandidateReviewError,
    CandidateReviewService,
    EvidencePromotionUnsupportedError,
    InvalidReviewReasonError,
    ObservationCandidateMismatchError,
    ObservationNotFoundError,
    PreexistingIdentityConflictError,
    RejectCandidateCommand,
    ReviewReasonRequiredForWeakEvidenceError,
    ReviewerNotAuthorizedError,
    ReviewerNotFoundError,
    ScopusAuthorAlreadyApprovedError,
    StaleCandidateObservationError,
    StaleCandidateVersionError,
)
from app.services.candidate_evidence_read import serialize_review_evidence
from app.services.candidate_group_review import (
    GroupDuplicateError,
    GroupItem,
    GroupMismatchError,
    GroupPrimaryNotInGroupError,
    GroupReasonRequiredError,
    GroupSharedAuthorError,
    GroupSizeError,
    accept_group,
)
from app.services import merge_guide
from app.services.candidate_fit import assess_fit, ictu_affiliation_paper_counts
from app.services.text_folding import contains_folded
from app.services.primary_scopus_identity import PrimaryIdentityError
from app.services.review_reason_policy import accept_reason_policy

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_session)]
ReviewerUser = Annotated[User, Depends(require_role("ADMIN", "REVIEWER"))]


def _evidence_counts_subquery():
    return (
        select(
            LecturerScopusCandidateEvidence.observation_id.label("observation_id"),
            func.count(
                case(
                    (LecturerScopusCandidateEvidence.evidence_kind == "NAME", 1)
                )
            ).label("name_evidence_count"),
            func.count(
                case(
                    (
                        LecturerScopusCandidateEvidence.evidence_kind
                        == "PUBLICATION",
                        1,
                    )
                )
            ).label("publication_evidence_count"),
        )
        .group_by(LecturerScopusCandidateEvidence.observation_id)
        .subquery("review_evidence_counts")
    )


def _candidate_ambiguity_subquery():
    return (
        select(
            LecturerScopusCandidate.lecturer_id.label("lecturer_id"),
            func.count(LecturerScopusCandidate.id).label(
                "candidate_count_for_lecturer"
            ),
        )
        .group_by(LecturerScopusCandidate.lecturer_id)
        .subquery("review_candidate_ambiguity")
    )


def _scopus_author_sharing_subquery():
    """Read-only: how many candidate roots propose the same Scopus author."""
    return (
        select(
            LecturerScopusCandidate.scopus_author_id.label("scopus_author_id"),
            func.count(LecturerScopusCandidate.id).label(
                "candidate_count_for_scopus_author"
            ),
        )
        .group_by(LecturerScopusCandidate.scopus_author_id)
        .subquery("review_scopus_author_sharing")
    )


def _queue_statement(
    *,
    candidate_status: str,
    evidence_category: str | None,
    ambiguity: str | None,
    search: str | None = None,
):
    reviewable = current_reviewable_candidates_subquery(candidate_status)
    evidence_counts = _evidence_counts_subquery()
    ambiguity_counts = _candidate_ambiguity_subquery()
    sharing_counts = _scopus_author_sharing_subquery()
    publication_count = func.coalesce(
        evidence_counts.c.publication_evidence_count, 0
    )
    statement = (
        select(
            LecturerScopusCandidate.id.label("candidate_id"),
            LecturerScopusCandidate.status.label("candidate_status"),
            LecturerScopusCandidate.version.label("candidate_version"),
            reviewable.c.current_observation_id.label("current_observation_id"),
            Lecturer.id.label("lecturer_id"),
            Lecturer.full_name.label("lecturer_full_name"),
            ScopusAuthor.id.label("scopus_author_id"),
            ScopusAuthor.scopus_id.label("scopus_id"),
            ScopusAuthor.preferred_name.label("preferred_name"),
            func.coalesce(evidence_counts.c.name_evidence_count, 0).label(
                "name_evidence_count"
            ),
            publication_count.label("publication_evidence_count"),
            publication_count.label("publication_support_count"),
            ambiguity_counts.c.candidate_count_for_lecturer.label(
                "candidate_count_for_lecturer"
            ),
            sharing_counts.c.candidate_count_for_scopus_author.label(
                "candidate_count_for_scopus_author"
            ),
            LecturerScopusCandidate.created_at.label("created_at"),
            LecturerScopusCandidate.updated_at.label("updated_at"),
            LecturerScopusCandidate.last_seen_at.label("last_seen_at"),
        )
        .select_from(LecturerScopusCandidate)
        .join(Lecturer, Lecturer.id == LecturerScopusCandidate.lecturer_id)
        .join(
            ScopusAuthor,
            ScopusAuthor.id == LecturerScopusCandidate.scopus_author_id,
        )
        .join(
            reviewable,
            reviewable.c.candidate_id == LecturerScopusCandidate.id,
        )
        .outerjoin(
            evidence_counts,
            evidence_counts.c.observation_id == reviewable.c.current_observation_id,
        )
        .join(
            ambiguity_counts,
            ambiguity_counts.c.lecturer_id == LecturerScopusCandidate.lecturer_id,
        )
        .join(
            sharing_counts,
            sharing_counts.c.scopus_author_id == LecturerScopusCandidate.scopus_author_id,
        )
    )
    # Every word must appear in the lecturer name / e-mail or the Scopus name / ID, ignoring case
    # and Vietnamese diacritics.
    for token in (search or "").split()[:8]:
        statement = statement.where(
            or_(
                contains_folded(Lecturer.full_name, token),
                contains_folded(func.coalesce(Lecturer.email, ""), token),
                contains_folded(ScopusAuthor.preferred_name, token),
                contains_folded(ScopusAuthor.scopus_id, token),
            )
        )
    if evidence_category == "publication-supported":
        statement = statement.where(publication_count > 0)
    elif evidence_category == "name-only":
        statement = statement.where(publication_count == 0)
    if ambiguity == "ambiguous":
        statement = statement.where(
            ambiguity_counts.c.candidate_count_for_lecturer > 1
        )
    elif ambiguity == "unique":
        statement = statement.where(
            ambiguity_counts.c.candidate_count_for_lecturer == 1
        )
    return statement


def _domain_error_response(exc: CandidateReviewError) -> APIError:
    status_by_type = {
        CandidateNotFoundError: 404,
        ObservationNotFoundError: 404,
        ObservationCandidateMismatchError: 409,
        StaleCandidateObservationError: 409,
        StaleCandidateVersionError: 409,
        CandidateAlreadyDecidedError: 409,
        ReviewerNotFoundError: 403,
        ReviewerNotAuthorizedError: 403,
        ScopusAuthorAlreadyApprovedError: 409,
        PreexistingIdentityConflictError: 409,
        InvalidReviewReasonError: 422,
        ReviewReasonRequiredForWeakEvidenceError: 422,
        EvidencePromotionUnsupportedError: 409,
        CandidateNotAcceptedError: 409,
        IdentityRevokedError: 409,
        RevocationReasonRequiredError: 422,
        GroupSizeError: 422,
        GroupDuplicateError: 422,
        GroupMismatchError: 422,
        GroupPrimaryNotInGroupError: 422,
        GroupReasonRequiredError: 422,
        GroupSharedAuthorError: 422,
    }
    data: dict[str, object] = {}
    if isinstance(exc, ReviewReasonRequiredForWeakEvidenceError):
        data["reason_triggers"] = list(exc.triggers)
    return APIError(
        status_code=status_by_type.get(type(exc), 409),
        detail="Review operation could not be completed.",
        code=exc.code,
        data=data,
    )


def _serialize_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _source_ref_ids(source_refs: list[Any]) -> dict[str, uuid.UUID]:
    result: dict[str, uuid.UUID] = {}
    for ref in source_refs:
        if not isinstance(ref, dict):
            continue
        ref_id = _serialize_uuid(ref.get("id"))
        kind = ref.get("kind")
        if ref_id is not None and isinstance(kind, str):
            result.setdefault(kind, ref_id)
    return result


@router.get(
    "/context",
    response_model=ReviewContextResponse,
    summary="Explain which precondition of the review queue is missing",
)
def review_context(_reviewer: ReviewerUser, db: DatabaseSession) -> ReviewContextResponse:
    """Counters that let the UI tell apart the four reasons the queue can be empty."""

    try:
        lecturers = int(db.scalar(select(func.count()).select_from(Lecturer)) or 0)
        publications = int(db.scalar(select(func.count()).select_from(Publication)) or 0)
        authors = int(db.scalar(select(func.count()).select_from(ScopusAuthor)) or 0)
        runs = int(
            db.scalar(
                select(func.count())
                .select_from(CandidateGenerationRun)
                .where(CandidateGenerationRun.status == "COMPLETED")
            )
            or 0
        )
        by_status = {
            status_name: int(count)
            for status_name, count in db.execute(
                select(LecturerScopusCandidate.status, func.count()).group_by(
                    LecturerScopusCandidate.status
                )
            ).all()
        }
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=503,
            detail="Không thể truy vấn ngữ cảnh hàng đợi duyệt.",
            code="DATABASE_UNAVAILABLE",
        ) from exc
    for key in ("PENDING", "ACCEPTED", "REJECTED", "SUPERSEDED"):
        by_status.setdefault(key, 0)
    if lecturers == 0:
        state = "NO_LECTURERS"
    elif runs == 0:
        state = "NO_CANDIDATE_RUN"
    elif sum(by_status.values()) == 0:
        state = "RUN_WITHOUT_CANDIDATES"
    else:
        state = "HAS_CANDIDATES"
    return ReviewContextResponse(
        state=state,
        lecturers_total=lecturers,
        publications_total=publications,
        scopus_authors_total=authors,
        completed_generation_runs=runs,
        candidates_by_status=by_status,
    )


@router.get(
    "/candidates",
    response_model=ReviewQueueResponse,
    summary="List deterministic human-review candidate roots",
)
def list_review_candidates(
    _reviewer: ReviewerUser,
    db: DatabaseSession,
    status: str = Query("PENDING", pattern="^(PENDING|ACCEPTED|REJECTED|SUPERSEDED)$"),
    evidence_category: str | None = Query(
        default=None, pattern="^(publication-supported|name-only)$"
    ),
    ambiguity: str | None = Query(default=None, pattern="^(ambiguous|unique)$"),
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ReviewQueueResponse:
    """Return reviewable observations without scores, ranking, or heavy evidence."""

    statement = _queue_statement(
        candidate_status=status,
        evidence_category=evidence_category,
        ambiguity=ambiguity,
        search=q,
    )
    total = db.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ) or 0
    rows = db.execute(
        statement.order_by(
            LecturerScopusCandidate.created_at.asc(),
            LecturerScopusCandidate.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    ictu_papers = ictu_affiliation_paper_counts(db, {row["scopus_author_id"] for row in rows})

    def _fit(row) -> ReviewFit:
        assessed = assess_fit(
            name_evidence_count=int(row["name_evidence_count"]),
            publication_support_count=int(row["publication_support_count"]),
            ictu_affiliation_papers=ictu_papers.get(row["scopus_author_id"], 0),
            is_shared_author=int(row["candidate_count_for_scopus_author"]) > 1,
            is_ambiguous_lecturer=int(row["candidate_count_for_lecturer"]) > 1,
        )
        return ReviewFit(
            level=assessed.level,
            reasons=list(assessed.reasons),
            ictu_affiliation_papers=assessed.ictu_affiliation_papers,
        )

    items = [
        ReviewQueueItem(
            candidate_id=row["candidate_id"],
            candidate_status=row["candidate_status"],
            candidate_version=row["candidate_version"],
            current_observation_id=row["current_observation_id"],
            lecturer=ReviewLecturerSummary(
                id=row["lecturer_id"], full_name=row["lecturer_full_name"]
            ),
            scopus_author=ReviewAuthorSummary(
                id=row["scopus_author_id"],
                scopus_id=row["scopus_id"],
                preferred_name=row["preferred_name"],
            ),
            name_evidence_count=int(row["name_evidence_count"]),
            publication_evidence_count=int(row["publication_evidence_count"]),
            publication_support_count=int(row["publication_support_count"]),
            candidate_count_for_lecturer=int(row["candidate_count_for_lecturer"]),
            is_ambiguous=int(row["candidate_count_for_lecturer"]) > 1,
            candidate_count_for_scopus_author=int(row["candidate_count_for_scopus_author"]),
            is_shared_scopus_author=int(row["candidate_count_for_scopus_author"]) > 1,
            fit=_fit(row),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_seen_at=row["last_seen_at"],
        )
        for row in rows
    ]
    return ReviewQueueResponse(items=items, total=int(total), page=page, page_size=page_size)


def _detail_fit(
    db: Session,
    *,
    author_id: uuid.UUID,
    name_evidence_count: int,
    publication_support_count: int,
    is_shared_author: bool,
    is_ambiguous_lecturer: bool,
) -> ReviewFit:
    assessed = assess_fit(
        name_evidence_count=name_evidence_count,
        publication_support_count=publication_support_count,
        ictu_affiliation_papers=ictu_affiliation_paper_counts(db, {author_id}).get(author_id, 0),
        is_shared_author=is_shared_author,
        is_ambiguous_lecturer=is_ambiguous_lecturer,
    )
    return ReviewFit(
        level=assessed.level,
        reasons=list(assessed.reasons),
        ictu_affiliation_papers=assessed.ictu_affiliation_papers,
    )


@router.get(
    "/candidates/{candidate_id}",
    response_model=ReviewCandidateDetailResponse,
    summary="Get the current human-review context for one candidate",
)
def review_candidate_detail(
    candidate_id: uuid.UUID,
    _reviewer: ReviewerUser,
    db: DatabaseSession,
) -> ReviewCandidateDetailResponse:
    candidate_row = db.execute(
        select(LecturerScopusCandidate, Lecturer, ScopusAuthor)
        .join(Lecturer, Lecturer.id == LecturerScopusCandidate.lecturer_id)
        .join(ScopusAuthor, ScopusAuthor.id == LecturerScopusCandidate.scopus_author_id)
        .where(LecturerScopusCandidate.id == candidate_id)
    ).first()
    if candidate_row is None:
        raise APIError(
            status_code=404,
            detail="Candidate was not found.",
            code="CANDIDATE_NOT_FOUND",
        )
    candidate, lecturer, author = candidate_row
    try:
        observation = current_reviewable_observation(db, candidate_id)
    except ObservationNotFoundError as exc:
        db.rollback()
        raise APIError(
            status_code=409,
            detail="Candidate has no current reviewable completed observation.",
            code="CANDIDATE_NOT_REVIEWABLE",
        ) from exc
    run = db.get(CandidateGenerationRun, observation.generation_run_id)
    if run is None:
        raise APIError(
            status_code=409,
            detail="Candidate generation context is not reviewable.",
            code="CANDIDATE_NOT_REVIEWABLE",
        )

    evidence_rows = db.scalars(
        select(LecturerScopusCandidateEvidence)
        .where(LecturerScopusCandidateEvidence.observation_id == observation.id)
        .order_by(
            LecturerScopusCandidateEvidence.evidence_kind,
            LecturerScopusCandidateEvidence.rule_id,
            LecturerScopusCandidateEvidence.evidence_fingerprint,
        )
    ).all()
    variants = db.scalars(
        select(ScopusAuthorNameVariant)
        .where(ScopusAuthorNameVariant.scopus_author_id == author.id)
        .order_by(ScopusAuthorNameVariant.variant_name, ScopusAuthorNameVariant.id)
    ).all()
    other_candidates = db.execute(
        select(
            LecturerScopusCandidate.id.label("candidate_id"),
            LecturerScopusCandidate.status.label("candidate_status"),
            LecturerScopusCandidate.version.label("candidate_version"),
            ScopusAuthor.id.label("author_id"),
            ScopusAuthor.scopus_id,
            ScopusAuthor.preferred_name,
        )
        .join(ScopusAuthor, ScopusAuthor.id == LecturerScopusCandidate.scopus_author_id)
        .where(
            LecturerScopusCandidate.lecturer_id == lecturer.id,
            LecturerScopusCandidate.id != candidate.id,
        )
        .order_by(LecturerScopusCandidate.created_at, LecturerScopusCandidate.id)
    ).mappings().all()

    publication_ids = {
        ref_id
        for ev in evidence_rows
        if ev.evidence_kind == "PUBLICATION"
        for ref_kind, ref_id in _source_ref_ids(list(ev.source_refs or [])).items()
        if ref_kind == "publication"
    }
    publications = {}
    if publication_ids:
        publications = {
            publication.id: publication
            for publication in db.scalars(
                select(Publication).where(Publication.id.in_(publication_ids))
            ).all()
        }

    name_evidence, publication_evidence = serialize_review_evidence(evidence_rows, publications)

    candidate_count = len(other_candidates) + 1
    reason_policy = accept_reason_policy(
        db,
        lecturer_id=lecturer.id,
        scopus_author_id=author.id,
        evidence_kinds=(ev.evidence_kind for ev in evidence_rows),
    )
    author_candidate_count = int(
        db.scalar(
            select(func.count(LecturerScopusCandidate.id)).where(
                LecturerScopusCandidate.scopus_author_id == author.id
            )
        )
        or 0
    )
    return ReviewCandidateDetailResponse(
        candidate_id=candidate.id,
        candidate_status=candidate.status,
        candidate_version=candidate.version,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
        last_seen_at=candidate.last_seen_at,
        lecturer=ReviewLecturerDetail(
            id=lecturer.id,
            full_name=lecturer.full_name,
            repository_profile_url=lecturer.repository_profile_url,
            academic_degree=lecturer.academic_degree,
            academic_rank=lecturer.academic_rank,
        ),
        scopus_author=ReviewAuthorDetail(
            id=author.id,
            scopus_id=author.scopus_id,
            preferred_name=author.preferred_name,
            name_variants=[variant.variant_name for variant in variants],
        ),
        current_observation=ReviewObservationResponse(
            observation_id=observation.id,
            generation_run_id=observation.generation_run_id,
            generation_run_rule_set_version=run.rule_set_version,
            observed_at=observation.observed_at,
            observation_hash=observation.observation_hash,
        ),
        name_evidence=name_evidence,
        publication_evidence=publication_evidence,
        ambiguity=ReviewAmbiguityContext(
            candidate_count_for_lecturer=candidate_count,
            is_ambiguous=candidate_count > 1,
            candidate_count_for_scopus_author=author_candidate_count,
            is_shared_scopus_author=author_candidate_count > 1,
            other_candidates=[
                ReviewOtherCandidateSummary(
                    candidate_id=row["candidate_id"],
                    candidate_status=row["candidate_status"],
                    candidate_version=row["candidate_version"],
                    scopus_author=ReviewAuthorSummary(
                        id=row["author_id"],
                        scopus_id=row["scopus_id"],
                        preferred_name=row["preferred_name"],
                    ),
                )
                for row in other_candidates
            ],
        ),
        review_policy=ReviewDecisionPolicy(
            accept_reason_required=reason_policy.required,
            accept_reason_triggers=list(reason_policy.triggers),
        ),
        fit=_detail_fit(
            db,
            author_id=author.id,
            name_evidence_count=len(name_evidence),
            publication_support_count=len(publication_evidence),
            is_shared_author=author_candidate_count > 1,
            is_ambiguous_lecturer=candidate_count > 1,
        ),
    )


@router.post(
    "/candidates/{candidate_id}/reviews",
    response_model=ReviewDecisionResponse,
    summary="Accept or reject one candidate through CandidateReviewService",
)
def decide_review_candidate(
    candidate_id: uuid.UUID,
    request: ReviewDecisionRequest,
    reviewer: ReviewerUser,
    db: DatabaseSession,
) -> ReviewDecisionResponse:
    """Authenticate, delegate, and translate the reviewed domain result."""

    service = CandidateReviewService(db)
    try:
        if request.action == "ACCEPT":
            result = service.accept_candidate(
                AcceptCandidateCommand(
                    candidate_id=candidate_id,
                    observation_id=request.observation_id,
                    candidate_version=request.candidate_version,
                    reviewer_user_id=reviewer.id,
                    reason=request.reason,
                )
            )
        else:
            result = service.reject_candidate(
                RejectCandidateCommand(
                    candidate_id=candidate_id,
                    observation_id=request.observation_id,
                    candidate_version=request.candidate_version,
                    reviewer_user_id=reviewer.id,
                    reason=request.reason or "",
                )
            )
    except CandidateReviewError as exc:
        db.rollback()
        raise _domain_error_response(exc) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=409,
            detail="Review operation conflicted with current persisted state.",
            code="REVIEW_PERSISTENCE_CONFLICT",
        ) from exc

    return ReviewDecisionResponse(
        review_id=result.review_id,
        candidate_id=result.candidate_id,
        observation_id=result.observation_id,
        action=result.action,
        candidate_status=result.candidate_status,
        candidate_version=result.candidate_version,
        resulting_identity_id=result.resulting_identity_id,
        idempotent=result.idempotent,
    )


AdminUser = Annotated[User, Depends(require_role("ADMIN"))]


@router.get(
    "/merge-guide",
    response_model=MergeGuideResponse,
    summary="ICTU merge-guide hint (IDs and main ID) for the listed lecturers; decides nothing",
)
def get_merge_guide(
    _reviewer: ReviewerUser,
    db: DatabaseSession,
    lecturer_ids: Annotated[list[uuid.UUID], Query(max_length=200)],
) -> MergeGuideResponse:
    guide = merge_guide.load_merge_guide()
    if guide is None:
        return MergeGuideResponse(available=False)
    found = merge_guide.guides_for_lecturers(db, guide, set(lecturer_ids))
    return MergeGuideResponse(
        available=True,
        source_url=guide.source_url,
        retrieved_at=guide.retrieved_at,
        items=[
            MergeGuideLecturer(
                lecturer_id=g.lecturer_id,
                scopus_ids=list(g.scopus_ids),
                primary_scopus_id=g.primary_scopus_id,
            )
            for g in found
        ],
    )


@router.post(
    "/lecturers/{lecturer_id}/group-accept",
    response_model=ReviewGroupAcceptResponse,
    summary="Accept all proposed Scopus IDs of one lecturer in one transaction",
)
def group_accept_lecturer_candidates(
    lecturer_id: uuid.UUID,
    request: ReviewGroupAcceptRequest,
    reviewer: ReviewerUser,
    db: DatabaseSession,
) -> ReviewGroupAcceptResponse:
    """Each member keeps every single-decision rule; the group commits or rolls back as one."""

    try:
        result = accept_group(
            db,
            lecturer_id=lecturer_id,
            items=[GroupItem(i.candidate_id, i.observation_id, i.candidate_version)
                   for i in request.items],
            reviewer_user_id=reviewer.id,
            reason=request.reason,
            primary_candidate_id=request.primary_candidate_id,
        )
    except CandidateReviewError as exc:
        db.rollback()
        raise _domain_error_response(exc) from exc
    except PrimaryIdentityError as exc:
        db.rollback()
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=409,
            detail="Group review conflicted with current persisted state.",
            code="REVIEW_PERSISTENCE_CONFLICT",
        ) from exc
    return ReviewGroupAcceptResponse(
        lecturer_id=result.lecturer_id,
        accepted=[ReviewGroupAcceptedItem(
            candidate_id=r.candidate_id, review_id=r.review_id,
            resulting_identity_id=r.resulting_identity_id,
            candidate_version=r.candidate_version) for r in result.results],
        primary_identity_id=result.primary_identity_id,
    )


@router.post(
    "/candidates/{candidate_id}/revocation",
    response_model=ReviewRevocationResponse,
    summary="ADMIN revokes an approved identity (append-only compensation)",
)
def revoke_review_candidate(
    candidate_id: uuid.UUID,
    request: ReviewRevocationRequest,
    admin: AdminUser,
    db: DatabaseSession,
) -> ReviewRevocationResponse:
    """Re-check ADMIN and delegate; history is appended, never edited."""

    try:
        result = CandidateReviewService(db).revoke_identity(
            RevokeIdentityCommand(
                candidate_id=candidate_id,
                candidate_version=request.candidate_version,
                admin_user_id=admin.id,
                reason=request.reason,
            )
        )
    except CandidateReviewError as exc:
        db.rollback()
        raise _domain_error_response(exc) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=409,
            detail="Revocation conflicted with current persisted state.",
            code="REVIEW_PERSISTENCE_CONFLICT",
        ) from exc
    return ReviewRevocationResponse(
        review_id=result.review_id,
        candidate_id=result.candidate_id,
        candidate_status="PENDING",
        candidate_version=result.candidate_version,
        revoked_identity_id=result.resulting_identity_id,
        identity_status="REVOKED",
    )


HistoryUser = Annotated[User, Depends(require_role("ADMIN", "REVIEWER"))]


@router.get(
    "/history",
    response_model=ReviewHistoryResponse,
    summary="List review history (read-only, append-only source of truth)",
)
def list_review_history_endpoint(
    _user: HistoryUser,
    db: DatabaseSession,
    action: Literal["ACCEPT", "REJECT", "REOPEN"] | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ReviewHistoryResponse:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise APIError(
            status_code=422,
            detail="date_from must be earlier than or equal to date_to.",
            code="INVALID_DATE_RANGE",
        )
    try:
        return list_review_history(
            db,
            page=page,
            page_size=page_size,
            action=action,
            date_from=date_from,
            date_to=date_to,
        )
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=503,
            detail="Review history is temporarily unavailable.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


__all__ = ["router"]
