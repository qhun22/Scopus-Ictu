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
from sqlalchemy.orm import Session

from app.models.candidate import LecturerScopusCandidate as LecturerScopusCandidateRow
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
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


__all__ = ["ManualCandidateError", "ManualCandidateResult", "create_manual_candidate"]
