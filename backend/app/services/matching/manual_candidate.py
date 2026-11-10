"""ADMIN-proposed single candidate pair, for a lecturer/Scopus author the
deterministic name rules in ``candidate_generator.py`` fail to pair up.

This never creates an identity or bypasses review: it only reaches the same
PENDING state a generated candidate reaches, through the same
``CandidatePersistenceService`` the bulk generator already uses, so every
append-only/idempotency guarantee that service already gives still applies.
The only new thing is the evidence shape: a single NAME-kind row tagged
``RULE_MANUAL_ADMIN`` carrying the ADMIN's note instead of a rule-computed
comparison value. D-2's reason policy still treats it as name-only evidence,
so ACCEPT still requires an explicit reason.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.candidate import (
    LecturerScopusCandidate as LecturerScopusCandidateRow,
)
from app.models.candidate import (
    LecturerScopusCandidateReview,
)
from app.models.governance import AuditEvent, User
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.services.candidate_review_queries import current_reviewable_observation
from app.services.candidate_review_service import (
    AcceptCandidateCommand,
    CandidateNotAcceptedError,
    CandidateNotFoundError,
    CandidateReviewError,
    CandidateReviewService,
    InvalidReviewReasonError,
    ObservationNotFoundError,
    PreexistingIdentityConflictError,
    ReviewerNotAuthorizedError,
    ReviewerNotFoundError,
    RevocationReasonRequiredError,
    RevokeIdentityCommand,
    ScopusAuthorAlreadyApprovedError,
    StaleCandidateObservationError,
    StaleCandidateVersionError,
)
from app.services.matching.candidate_persistence import (
    CandidatePersistenceService,
    GenerationRunConflict,
    GenerationRunSpec,
    GenerationRunStateError,
    build_source_state,
)
from app.services.matching.candidate_types import (
    CandidateEvidence,
    EnrichedLecturerScopusCandidate,
)

# Mirrors reviews.py's ``_domain_error_response`` status mapping for the
# subset of domain errors reachable from this single-candidate accept flow.
_REVIEW_ERROR_STATUS: dict[type[CandidateReviewError], int] = {
    CandidateNotFoundError: 404,
    ObservationNotFoundError: 404,
    StaleCandidateObservationError: 409,
    StaleCandidateVersionError: 409,
    ReviewerNotFoundError: 403,
    ReviewerNotAuthorizedError: 403,
    ScopusAuthorAlreadyApprovedError: 409,
    PreexistingIdentityConflictError: 409,
    InvalidReviewReasonError: 422,
    CandidateNotAcceptedError: 409,
    RevocationReasonRequiredError: 422,
}


class ManualCandidateError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


@dataclass(frozen=True, slots=True)
class ManualCandidateResult:
    candidate_id: uuid.UUID
    run_id: uuid.UUID
    lecturer_full_name: str
    scopus_id: str
    scopus_preferred_name: str
    idempotent_replay: bool


def create_manual_candidate(
    session: Session,
    *,
    lecturer_id: uuid.UUID,
    scopus_id: str,
    note: str,
    reviewer_email: str,
) -> ManualCandidateResult:
    """Propose one lecturer/Scopus-author pair by hand, as a PENDING candidate.

    Raises ``ManualCandidateError`` (never a bare SQLAlchemy/ValueError) for
    every caller-fixable problem: unknown lecturer, unknown/unimported Scopus
    author, or a pair that already has a candidate root (in ANY status —
    re-proposing an existing pair is never silently accepted here).
    """

    note = note.strip()
    if not note:
        raise ManualCandidateError(
            "MANUAL_CANDIDATE_NOTE_REQUIRED",
            "Cần ghi lý do/căn cứ khi thêm cặp đối sánh thủ công.",
            status_code=422,
        )

    lecturer = session.get(Lecturer, lecturer_id)
    if lecturer is None:
        raise ManualCandidateError(
            "LECTURER_NOT_FOUND", "Không tìm thấy giảng viên này.", status_code=404
        )

    scopus_id = scopus_id.strip()
    author = session.scalar(select(ScopusAuthor).where(ScopusAuthor.scopus_id == scopus_id))
    if author is None:
        raise ManualCandidateError(
            "SCOPUS_AUTHOR_NOT_FOUND",
            "Không tìm thấy tác giả Scopus với ID này trong hệ thống. "
            "Tác giả phải đã được bóc tách (Dữ liệu tác giả) trước khi có thể đối sánh.",
            status_code=404,
        )

    existing = session.scalar(
        select(LecturerScopusCandidateRow).where(
            LecturerScopusCandidateRow.lecturer_id == lecturer_id,
            LecturerScopusCandidateRow.scopus_author_id == author.id,
        )
    )
    if existing is not None:
        raise ManualCandidateError(
            "MANUAL_CANDIDATE_ALREADY_EXISTS",
            f"Cặp giảng viên/tác giả Scopus này đã có ứng viên đối sánh "
            f"(trạng thái: {existing.status}). Xem trong danh sách Duyệt đối sánh.",
            status_code=409,
        )

    candidate = EnrichedLecturerScopusCandidate(
        lecturer_id=lecturer_id,
        scopus_author_id=author.id,
        scopus_id=author.scopus_id,
        preferred_name=author.preferred_name,
        evidence=(
            CandidateEvidence(
                rule_id="RULE_MANUAL_ADMIN",
                lecturer_source_value=lecturer.full_name,
                lecturer_comparison_value=note,
                scopus_surface_type="PREFERRED_NAME",
                scopus_surface_value=author.preferred_name,
                scopus_comparison_value=f"proposed_by:{reviewer_email}",
            ),
        ),
        publication_evidence=(),
    )

    source_state = build_source_state(session)
    run_id = uuid.uuid4()
    spec = GenerationRunSpec(run_id=run_id, source_state=source_state, started_at=datetime.now(UTC))
    # The reads above (session.get/scalar, build_source_state) auto-begin a
    # transaction on first use; persist_generation opens its own transaction
    # via `with self._session.begin():` and raises InvalidRequestError if one
    # is already open. End the read phase first, exactly as the bulk
    # generator (generation_workflow.run_generation) already does.
    session.commit()
    try:
        result = CandidatePersistenceService(session).persist_generation(spec, (candidate,))
    except (GenerationRunConflict, GenerationRunStateError) as exc:
        raise ManualCandidateError("MANUAL_CANDIDATE_PERSIST_CONFLICT", str(exc)) from exc

    root = session.scalar(
        select(LecturerScopusCandidateRow).where(
            LecturerScopusCandidateRow.lecturer_id == lecturer_id,
            LecturerScopusCandidateRow.scopus_author_id == author.id,
        )
    )
    if root is None:
        raise ManualCandidateError(
            "MANUAL_CANDIDATE_PERSIST_CONFLICT",
            "Không thể tạo ứng viên đối sánh (lỗi không xác định sau khi ghi).",
        )

    return ManualCandidateResult(
        candidate_id=root.id,
        run_id=result.run_id,
        lecturer_full_name=lecturer.full_name,
        scopus_id=author.scopus_id,
        scopus_preferred_name=author.preferred_name,
        idempotent_replay=result.idempotent_replay,
    )


@dataclass(frozen=True, slots=True)
class AssignScopusIdentityResult:
    identity_id: uuid.UUID
    scopus_id: str
    scopus_preferred_name: str
    already_approved: bool


def _register_author_reference(
    session: Session, *, scopus_id: str, reviewer: User, reason: str,
) -> ScopusAuthor:
    """Record a reviewer-supplied ID, without inventing a name or publications.

    Registration is not identity approval. The caller still goes through the
    normal candidate review boundary, with the reviewer's explicit reason.
    """
    if not reviewer.is_active or reviewer.role not in {"ADMIN", "REVIEWER"}:
        raise ManualCandidateError(
            "FORBIDDEN", "Không có quyền ghi nhận ID tác giả.", status_code=403,
        )
    if not reason or len(reason) > 4000 or any(ord(c) < 32 and c not in "\n\t" for c in reason):
        raise ManualCandidateError(
            "INVALID_REVIEW_REASON", "Cần nhập căn cứ xác minh hợp lệ.", status_code=422,
        )
    if not scopus_id.isascii() or not scopus_id.isdigit() or len(scopus_id) > 50:
        raise ManualCandidateError(
            "INVALID_SCOPUS_ID", "Scopus Author ID phải là dãy chữ số.", status_code=422,
        )

    # The import normalizer also uses the ID itself when a name is unavailable.
    author = ScopusAuthor(id=uuid.uuid4(), scopus_id=scopus_id, preferred_name=scopus_id)
    try:
        with session.begin_nested():
            session.add(author)
            session.flush()
    except IntegrityError as exc:
        # A concurrent import/reviewer may have registered this unique ID first.
        sqlstate = getattr(exc.orig, "pgcode", None) or getattr(exc.orig, "sqlstate", None)
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if (sqlstate, constraint) != ("23505", "uq_scopus_authors_scopus_id"):
            raise
        existing = session.scalar(select(ScopusAuthor).where(ScopusAuthor.scopus_id == scopus_id))
        if existing is None:
            raise
        return existing

    session.add(AuditEvent(
        id=uuid.uuid4(),
        entity_type="scopus_author",
        entity_id=author.id,
        action="SCOPUS_AUTHOR_REFERENCE_CREATED",
        actor_type="USER",
        actor_user_id=reviewer.id,
        before_state=None,
        after_state={"scopus_id": scopus_id, "preferred_name": scopus_id},
        reason=reason,
        event_metadata={"source": "manual_profile_assignment", "name_available": False},
        created_at=datetime.now(UTC),
    ))
    session.flush()
    return author


def assign_scopus_identity(
    session: Session,
    *,
    lecturer_id: uuid.UUID,
    scopus_id: str,
    reason: str,
    reviewer: User,
    create_author_if_missing: bool = False,
) -> AssignScopusIdentityResult:
    """Record, from the lecturer profile screen, that a given Scopus author IS this
    lecturer -- the ADMIN already holds evidence (e.g. ORCID, the lecturer's own
    publication list) and wants it recorded without a separate trip to "Duyet doi
    sanh". This still goes through the same review boundary as any other pair:
    it creates (or reuses) a PENDING candidate carrying the ADMIN's note as
    RULE_MANUAL_ADMIN evidence, then accepts it through
    ``CandidateReviewService.accept_candidate()`` -- the only path that may create
    a ``LecturerScopusIdentity``. Nothing here bypasses review; it only collapses
    two already-existing steps into one request. The profile editor can explicitly
    opt in to registering a missing author ID; this creates no publications and
    does not approve an identity by itself.
    """

    scopus_id = scopus_id.strip()
    reason = reason.strip()
    lecturer = session.get(Lecturer, lecturer_id)
    if lecturer is None:
        raise ManualCandidateError(
            "LECTURER_NOT_FOUND", "Không tìm thấy giảng viên này.", status_code=404
        )

    author = session.scalar(select(ScopusAuthor).where(ScopusAuthor.scopus_id == scopus_id))
    if author is None and create_author_if_missing:
        author = _register_author_reference(
            session, scopus_id=scopus_id, reviewer=reviewer, reason=reason,
        )
    if author is None:
        raise ManualCandidateError(
            "SCOPUS_AUTHOR_NOT_FOUND",
            "Không tìm thấy tác giả Scopus với ID này trong hệ thống. "
            "Tác giả phải đã được bóc tách (Dữ liệu tác giả) trước khi có thể gán.",
            status_code=404,
        )

    existing_identity = session.scalar(
        select(LecturerScopusIdentity).where(
            LecturerScopusIdentity.lecturer_id == lecturer_id,
            LecturerScopusIdentity.scopus_author_id == author.id,
        )
    )
    if existing_identity is not None and existing_identity.status == "APPROVED":
        return AssignScopusIdentityResult(
            identity_id=existing_identity.id,
            scopus_id=author.scopus_id,
            scopus_preferred_name=author.preferred_name,
            already_approved=True,
        )
    if existing_identity is not None:
        raise ManualCandidateError(
            "SCOPUS_IDENTITY_CONFLICT",
            f"Cặp này đã có trong hệ thống với trạng thái {existing_identity.status}. "
            "Xem và xử lý trong Duyệt đối sánh.",
            status_code=409,
        )

    candidate = session.scalar(
        select(LecturerScopusCandidateRow).where(
            LecturerScopusCandidateRow.lecturer_id == lecturer_id,
            LecturerScopusCandidateRow.scopus_author_id == author.id,
        )
    )
    if candidate is None:
        created = create_manual_candidate(
            session,
            lecturer_id=lecturer_id,
            scopus_id=scopus_id,
            note=reason,
            reviewer_email=reviewer.email,
        )
        candidate = session.get(LecturerScopusCandidateRow, created.candidate_id)
    elif candidate.status == "ACCEPTED":
        # Already accepted -- e.g. a retried/concurrent request (import retry
        # racing a manual assign, or a fresh generation run changing which
        # observation counts as "current"). accept_candidate()'s own
        # idempotent-replay check only matches an exact observation_id, so a
        # later observation would otherwise fall through to a raw
        # CandidateAlreadyDecidedError. Look the real outcome up instead.
        accept_review = session.scalar(
            select(LecturerScopusCandidateReview)
            .where(
                LecturerScopusCandidateReview.candidate_id == candidate.id,
                LecturerScopusCandidateReview.action == "ACCEPT",
            )
            .order_by(LecturerScopusCandidateReview.created_at.desc())
            .limit(1)
        )
        identity = (
            session.get(LecturerScopusIdentity, accept_review.resulting_identity_id)
            if accept_review is not None and accept_review.resulting_identity_id is not None
            else None
        )
        same_lecturer = identity is not None and identity.lecturer_id == lecturer_id
        if identity is not None and identity.status == "APPROVED" and same_lecturer:
            return AssignScopusIdentityResult(
                identity_id=identity.id,
                scopus_id=author.scopus_id,
                scopus_preferred_name=author.preferred_name,
                already_approved=True,
            )
        raise ManualCandidateError(
            "SCOPUS_IDENTITY_CONFLICT",
            f"Cặp này đã có ứng viên đối sánh với trạng thái {candidate.status}. "
            "Xem và xử lý trong Duyệt đối sánh.",
            status_code=409,
        )
    elif candidate.status != "PENDING":
        raise ManualCandidateError(
            "SCOPUS_IDENTITY_CONFLICT",
            f"Cặp này đã có ứng viên đối sánh với trạng thái {candidate.status}. "
            "Xem và xử lý trong Duyệt đối sánh.",
            status_code=409,
        )

    observation = current_reviewable_observation(session, candidate.id)
    service = CandidateReviewService(session)
    try:
        result = service.accept_candidate(
            AcceptCandidateCommand(
                candidate_id=candidate.id,
                observation_id=observation.id,
                candidate_version=candidate.version,
                reviewer_user_id=reviewer.id,
                reason=reason,
            )
        )
    except CandidateReviewError as exc:
        status_code = _REVIEW_ERROR_STATUS.get(type(exc), 409)
        raise ManualCandidateError(exc.code, exc.message, status_code=status_code) from exc

    return AssignScopusIdentityResult(
        identity_id=result.resulting_identity_id,
        scopus_id=author.scopus_id,
        scopus_preferred_name=author.preferred_name,
        already_approved=False,
    )


@dataclass(frozen=True, slots=True)
class RevokeScopusIdentityResult:
    identity_id: uuid.UUID
    scopus_id: str


def revoke_scopus_identity(
    session: Session,
    *,
    lecturer_id: uuid.UUID,
    identity_id: uuid.UUID,
    reason: str,
    admin: User,
) -> RevokeScopusIdentityResult:
    """Undo a mistaken "Gán ID Scopus" (or any other ACCEPT): the ADMIN-facing
    counterpart of ``assign_scopus_identity``, for the "x" button next to an
    already-saved row in the lecturer-profile Scopus ID list.

    Still goes through ``CandidateReviewService.revoke_identity()`` -- the one
    path allowed to move an identity out of APPROVED -- appending a
    compensating review (G10) rather than deleting anything. The candidate
    goes back to PENDING, so the pair can be re-decided later if it turns out
    to be right after all.
    """

    identity = session.get(LecturerScopusIdentity, identity_id)
    if identity is None or identity.lecturer_id != lecturer_id:
        raise ManualCandidateError(
            "SCOPUS_IDENTITY_NOT_FOUND",
            "Không tìm thấy ID Scopus này cho giảng viên.",
            status_code=404,
        )
    if identity.status != "APPROVED":
        raise ManualCandidateError(
            "SCOPUS_IDENTITY_NOT_APPROVED",
            f"ID này đang ở trạng thái {identity.status}, không thể bỏ.",
            status_code=409,
        )

    accept_review = session.scalar(
        select(LecturerScopusCandidateReview)
        .where(
            LecturerScopusCandidateReview.resulting_identity_id == identity_id,
            LecturerScopusCandidateReview.action == "ACCEPT",
        )
        .order_by(LecturerScopusCandidateReview.created_at.desc())
        .limit(1)
    )
    if accept_review is None:
        raise ManualCandidateError(
            "SCOPUS_IDENTITY_NOT_FOUND",
            "Không tìm thấy quyết định duyệt gốc của ID Scopus này.",
            status_code=404,
        )
    candidate = session.get(LecturerScopusCandidateRow, accept_review.candidate_id)
    if candidate is None:
        raise ManualCandidateError(
            "SCOPUS_IDENTITY_NOT_FOUND",
            "Không tìm thấy ứng viên đối sánh gốc của ID Scopus này.",
            status_code=404,
        )
    scopus_id = session.scalar(
        select(ScopusAuthor.scopus_id).where(ScopusAuthor.id == identity.scopus_author_id)
    ) or ""

    service = CandidateReviewService(session)
    try:
        result = service.revoke_identity(
            RevokeIdentityCommand(
                candidate_id=candidate.id,
                candidate_version=candidate.version,
                admin_user_id=admin.id,
                reason=reason,
            )
        )
    except CandidateReviewError as exc:
        status_code = _REVIEW_ERROR_STATUS.get(type(exc), 409)
        raise ManualCandidateError(exc.code, exc.message, status_code=status_code) from exc

    return RevokeScopusIdentityResult(
        identity_id=result.resulting_identity_id,
        scopus_id=scopus_id,
    )


__all__ = [
    "ManualCandidateError",
    "ManualCandidateResult",
    "create_manual_candidate",
    "AssignScopusIdentityResult",
    "assign_scopus_identity",
    "RevokeScopusIdentityResult",
    "revoke_scopus_identity",
]
