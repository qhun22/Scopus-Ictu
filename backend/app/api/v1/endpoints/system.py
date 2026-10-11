"""System administration endpoints — destructive operations, ADMIN only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_role
from app.core.exceptions import APIError
from app.models.affiliation import (
    Organization,
    PublicationAuthorAffiliationResolution,
    PublicationAuthorAffiliation,
)
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
    LecturerScopusCandidateReview,
)
from app.models.governance import AuditEvent, User, UserNotification
from app.models.identity import (
    LecturerScopusIdentity,
    IdentityEvidence,
    MappingReview,
)
from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)
from app.models.publication import (
    Publication,
    PublicationAuthor,
    PublicationRawSource,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.models.scopus_raw import ScopusImport, RawScopusRecord

router = APIRouter()

_CONFIRM_PHRASE = "ICTU"


@router.post("/reset", status_code=200)
def reset_system(
    confirmation: Annotated[str, Body(embed=True)],
    db: Session = Depends(get_db_session),
    _actor: User = Depends(require_role("ADMIN")),
) -> dict:
    """Wipe all application data, keeping only ADMIN accounts.

    The caller must send ``{"confirmation": "ICTU"}`` in the request body.
    This operation is irreversible.
    """
    if confirmation != _CONFIRM_PHRASE:
        raise APIError(
            status_code=422,
            detail=f'Xác nhận không đúng. Vui lòng nhập "{_CONFIRM_PHRASE}" để tiếp tục.',
            code="RESET_CONFIRMATION_MISMATCH",
        )

    try:
        # Delete in FK-safe order (leaves before roots)

        # 1. Affiliation children
        db.query(PublicationAuthorAffiliation).delete(synchronize_session=False)
        db.query(PublicationAuthorAffiliationResolution).delete(synchronize_session=False)
        db.query(Organization).delete(synchronize_session=False)

        # 2. Candidate cascade
        db.query(LecturerScopusCandidateEvidence).delete(synchronize_session=False)
        db.query(LecturerScopusCandidateReview).delete(synchronize_session=False)
        db.query(LecturerScopusCandidateObservation).delete(synchronize_session=False)
        db.query(LecturerScopusCandidate).delete(synchronize_session=False)
        db.query(CandidateGenerationRun).delete(synchronize_session=False)

        # 3. Identity cascade
        db.query(IdentityEvidence).delete(synchronize_session=False)
        db.query(MappingReview).delete(synchronize_session=False)
        db.query(LecturerScopusIdentity).delete(synchronize_session=False)

        # 4. Publications cascade
        db.query(PublicationAuthor).delete(synchronize_session=False)
        db.query(PublicationRawSource).delete(synchronize_session=False)
        db.query(Publication).delete(synchronize_session=False)
        db.query(ScopusAuthorNameVariant).delete(synchronize_session=False)
        db.query(ScopusAuthor).delete(synchronize_session=False)

        # 5. Raw Scopus imports
        db.query(RawScopusRecord).delete(synchronize_session=False)
        db.query(ScopusImport).delete(synchronize_session=False)

        # 6. Lecturer cascade
        db.query(LecturerKnownPublication).delete(synchronize_session=False)
        db.query(LecturerSourceSnapshot).delete(synchronize_session=False)

        # 7. LECTURER-role users + their notifications (before lecturers)
        lecturer_user_ids = [
            row.id
            for row in db.query(User.id).filter(User.role == "LECTURER").all()
        ]
        if lecturer_user_ids:
            db.query(UserNotification).filter(
                UserNotification.user_id.in_(lecturer_user_ids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.role == "LECTURER").delete(
                synchronize_session=False
            )

        db.query(Lecturer).delete(synchronize_session=False)

        # 8. Audit events (append-only log — clear entirely)
        db.query(AuditEvent).delete(synchronize_session=False)

        # 9. Remaining notifications for non-LECTURER users
        db.query(UserNotification).delete(synchronize_session=False)

        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=500,
            detail="Không thể reset hệ thống do lỗi cơ sở dữ liệu.",
            code="SYSTEM_RESET_FAILED",
        ) from exc

    return {"status": "ok", "message": "Hệ thống đã được reset thành công."}
