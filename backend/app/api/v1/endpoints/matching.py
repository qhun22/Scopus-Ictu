"""ADMIN-only endpoints for running candidate generation and ingesting
ICTU-Craw known-publication evidence from the web app.

Both routes take no parameters from the request beyond an explicit
confirmation — the Craw source directory and the generation run_id are
server-side decisions (``CRAW_SOURCE_DIR`` setting, freshly minted UUID),
never request input. This mirrors the existing ``/affiliations`` preview
-> apply pattern and reuses the same already-reviewed services; no new
matching rule, scoring, or persistence logic lives in this file.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.schemas.matching_api import (
    CrawApplyRequest,
    CrawApplyResponse,
    CrawPreviewResponse,
    GenerationRunResponse,
)
from app.services.lecturer_dataset import craw_ingestion_workflow
from app.services.matching import generation_workflow

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_session)]
AdminUser = Annotated[User, Depends(require_role("ADMIN"))]


@router.get("/ping", summary="M0 healthcheck")
def ping() -> dict[str, str]:
    """Retained for existing callers; superseded by the routes below."""
    return {"status": "matching-stub", "milestone": "M0"}


def _db_error(exc: SQLAlchemyError) -> APIError:
    return APIError(status_code=503, detail="Không thể truy vấn dữ liệu đối sánh.", code="DATABASE_UNAVAILABLE")


@router.post(
    "/candidates/generate",
    response_model=GenerationRunResponse,
    summary="Run name-matching + Craw-assisted candidate generation and persist PENDING candidates",
)
def generate_candidates(_admin: AdminUser, db: DatabaseSession) -> GenerationRunResponse:
    try:
        result = generation_workflow.run_generation(db)
    except generation_workflow.GenerationWorkflowError as exc:
        db.rollback()
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error(exc) from exc
    return GenerationRunResponse(
        run_id=result.run_id,
        run_status=result.run_status,
        candidate_roots=result.candidate_roots,
        observations=result.observations,
        evidence=result.evidence,
        idempotent_replay=result.idempotent_replay,
        name_candidates=result.name_candidates,
        craw_assisted_candidates=result.craw_assisted_candidates,
        craw_unattributed=result.craw_unattributed,
        publication_conflicts=result.publication_conflicts,
    )


@router.post(
    "/craw/preview",
    response_model=CrawPreviewResponse,
    summary="Read-only preview of what Craw ingestion would write",
)
def preview_craw_ingestion(_admin: AdminUser, db: DatabaseSession) -> CrawPreviewResponse:
    try:
        result = craw_ingestion_workflow.compute_preview(db)
    except SQLAlchemyError as exc:
        raise _db_error(exc) from exc
    return CrawPreviewResponse(
        fingerprint=result.fingerprint,
        can_apply=result.can_apply,
        blocked_reason=result.blocked_reason,
        stats=result.stats,
        preview=result.preview,
        blocking=result.blocking,
    )


@router.post(
    "/craw/apply",
    response_model=CrawApplyResponse,
    summary="Apply a previously previewed Craw ingestion",
)
def apply_craw_ingestion(
    body: CrawApplyRequest, admin: AdminUser, db: DatabaseSession
) -> CrawApplyResponse:
    if not body.confirm:
        raise APIError(status_code=422, detail="Cần xác nhận rõ ràng trước khi áp dụng.", code="CONFIRMATION_REQUIRED")
    try:
        outcome = craw_ingestion_workflow.apply_ingestion(
            db, fingerprint=body.fingerprint, actor_user_id=admin.id
        )
    except craw_ingestion_workflow.CrawIngestionWorkflowError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error(exc) from exc
    return CrawApplyResponse(**outcome)
