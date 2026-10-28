"""System administration endpoints — destructive operations, ADMIN only."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_role
from app.core.exceptions import APIError
from app.models.governance import User

router = APIRouter()

_CONFIRM_PHRASE = "ICTU"
_logger = logging.getLogger(__name__)



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
        # 1. Snapshot ADMIN accounts to restore after the wipe.
        admins = db.execute(text(
            "SELECT id, email, password_hash, display_name, is_active, version, "
            "created_at, updated_at, auth_version FROM users WHERE role = 'ADMIN'"
        )).fetchall()

        # 2. TRUNCATE CASCADE everything including users — simplest way to clear
        #    the entire FK graph without manually resolving dependency order.
        db.execute(text(
            "TRUNCATE users, audit_events, user_notifications, "
            "lecturer_scopus_candidate_reviews, mapping_reviews, "
            "publication_author_affiliation_overrides, "
            "publication_author_affiliations, "
            "publication_author_affiliation_resolutions, "
            "organizations, affiliation_enrichment_jobs, "
            "lecturer_scopus_candidate_evidence, "
            "lecturer_scopus_candidate_observations, "
            "lecturer_scopus_candidates, candidate_generation_runs, "
            "identity_evidence, lecturer_scopus_identities, "
            "publication_authors, publication_raw_sources, "
            "publications, scopus_author_name_variants, scopus_authors, "
            "raw_scopus_records, scopus_imports, "
            "lecturer_known_publications, lecturer_source_snapshots, "
            "lecturers RESTART IDENTITY CASCADE"
        ))

        # 3. Restore ADMIN accounts.
        for row in admins:
            db.execute(text(
                "INSERT INTO users (id, email, password_hash, display_name, role, "
                "lecturer_id, is_active, version, created_at, updated_at, auth_version) "
                "VALUES (:id, :email, :password_hash, :display_name, 'ADMIN', "
                "NULL, :is_active, :version, :created_at, :updated_at, :auth_version)"
            ), {
                "id": row.id, "email": row.email,
                "password_hash": row.password_hash,
                "display_name": row.display_name,
                "is_active": row.is_active, "version": row.version,
                "created_at": row.created_at, "updated_at": row.updated_at,
                "auth_version": row.auth_version + 1,
            })

        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()
        _logger.error("SYSTEM_RESET_FAILED: %s", exc, exc_info=True)
        raise APIError(
            status_code=500,
            detail=f"Không thể reset hệ thống do lỗi cơ sở dữ liệu: {exc}",
            code="SYSTEM_RESET_FAILED",
        ) from exc

    return {"status": "ok", "message": "Hệ thống đã được reset thành công."}
