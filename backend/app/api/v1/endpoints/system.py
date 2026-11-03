"""System administration endpoints — destructive operations, ADMIN only."""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_role
from app.core.config import settings
from app.core.exceptions import APIError
from app.models.governance import User

router = APIRouter()

_CONFIRM_PHRASE = "ICTU"
_logger = logging.getLogger(__name__)

# Reset chỉ được phép trên môi trường local/dev (ENVIRONMENT=local hoặc dev).
# Mọi môi trường khác (prod, staging, không xác định) bị từ chối trước bất kỳ thao tác SQL nào.
_RESET_ALLOWED_ENVIRONMENTS = frozenset({"local", "dev"})

# Append-only history tables refuse TRUNCATE through these guard triggers (migrations
# d0b14a77c8e2 and e4a1b7c92d10). The reset is the one deliberate, ADMIN-confirmed wipe of
# everything, and TRUNCATE ... CASCADE reaches those tables through their foreign keys.
_TRUNCATE_GUARDS = ("sc_hybrid_forbid_truncate", "lpee_forbid_truncate", "lpse_forbid_truncate")


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _truncate_guards(db: Session) -> list[tuple[str, str]]:
    """(table, trigger) pairs of TRUNCATE guards present in the current schema."""

    rows = db.execute(text(
        "SELECT c.relname, t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE NOT t.tgisinternal AND t.tgname = ANY(:names) "
        "AND c.relnamespace = CAST(current_schema() AS regnamespace)"
    ), {"names": list(_TRUNCATE_GUARDS)}).all()
    return [(r[0], r[1]) for r in rows]



@router.post("/reset", status_code=200)
def reset_system(
    confirmation: Annotated[Optional[str], Body(embed=True)] = None,
    db: Session = Depends(get_db_session),
    _actor: User = Depends(require_role("ADMIN")),
) -> dict:
    """Wipe all application data, keeping only ADMIN accounts.

    The caller must send ``{"confirmation": "ICTU"}`` in the request body.
    This operation is irreversible.

    Only available when ``ENVIRONMENT`` is ``local`` or ``dev``.  All other
    environments (``prod``, ``staging``, or unknown values) receive 410 before
    any database access.

    After a successful reset, all existing sessions — including the caller's —
    are invalidated (``auth_version`` is incremented on restored ADMIN accounts).
    The frontend must redirect to the login page on ``SESSION_REVOKED``.
    """
    # Auth check (require_role) has already run at this point.
    # Reject before any SQL when not running in a local/dev environment.
    if settings.environment.lower() not in _RESET_ALLOWED_ENVIRONMENTS:
        raise APIError(
            status_code=410,
            detail=(
                f"Thao tác reset hệ thống không được phép trên môi trường "
                f"'{settings.environment}'. Chỉ khả dụng khi ENVIRONMENT=local hoặc dev."
            ),
            code="SYSTEM_RESET_DISABLED",
        )

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

        # 1b. Lift the TRUNCATE guards of append-only history tables for THIS transaction only;
        #     they are re-armed below, and a failure rolls the whole transaction back.
        guards = _truncate_guards(db)
        for table, trigger in guards:
            db.execute(text(f"ALTER TABLE {_quote(table)} DISABLE TRIGGER {_quote(trigger)}"))

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

        for table, trigger in guards:
            db.execute(text(
                f"ALTER TABLE {_quote(table)} ENABLE ALWAYS TRIGGER {_quote(trigger)}"))

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
