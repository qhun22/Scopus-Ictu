"""ADMIN-triggered background job: fetch public affiliation metadata online.

Follows the same shape as ``scopus_import_service.process_import_job``: the
job runs after the HTTP response (FastAPI ``BackgroundTasks``), each step
opens its own short-lived session, and every step re-checks the job is still
ACTIVE before continuing — so a concurrent cancel is cooperative, not a
forced kill.

The job writes its bundle under
``<AFFILIATION_ONLINE_CACHE_DIR>/<job_id>/`` — never the ADMIN's fixed
offline ``AFFILIATION_SOURCE_DIR`` — so an online run can never silently
overwrite or be confused with a manually curated offline bundle. The
existing preview/apply workflow (``affiliation_workflow.py``) is then called
by the caller with that directory to actually write affiliation data; this
module never touches ``publication_author_affiliation*`` tables.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import settings
from app.core.database import get_session_factory
from app.models.affiliation_enrichment import (
    AFFILIATION_ENRICHMENT_ACTIVE_STATUSES,
    AffiliationEnrichmentJob,
)
from app.models.governance import AuditEvent, User
from app.services.affiliation_online_fetch import (
    AffiliationFetchCancelled,
    FetchProgress,
    normalize_doi,
    run_enrichment,
)
from app.services.affiliation_workflow import load_scopus_rows

STARTED_ACTION = "AFFILIATION_ONLINE_FETCH_STARTED"
COMPLETED_ACTION = "AFFILIATION_ONLINE_FETCH_COMPLETED"
FAILED_ACTION = "AFFILIATION_ONLINE_FETCH_FAILED"
CANCELLED_ACTION = "AFFILIATION_ONLINE_FETCH_CANCELLED"
# Transaction-level advisory lock serializing "is a job already active?" with
# the insert of a new one — without it two concurrent trigger requests can
# both pass the SELECT check before either commits (TOCTOU), starting two
# jobs at once. "AFF2" distinguishes it from affiliation_workflow's "AFF1".
_START_LOCK_KEY = 0x41464632


class AffiliationEnrichmentError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


class NoPublicationsToEnrich(AffiliationEnrichmentError):
    def __init__(self) -> None:
        super().__init__(
            "NO_PUBLICATIONS", "Chưa có công bố nào trong hệ thống để thu thập đơn vị.", 409
        )


class EnrichmentAlreadyRunning(AffiliationEnrichmentError):
    def __init__(self) -> None:
        super().__init__(
            "ENRICHMENT_ALREADY_RUNNING", "Một lượt thu thập đơn vị trực tuyến khác đang chạy.", 409
        )


class OnlineCacheNotConfigured(AffiliationEnrichmentError):
    def __init__(self) -> None:
        super().__init__(
            "ONLINE_CACHE_NOT_CONFIGURED",
            "Chưa cấu hình thư mục lưu kết quả thu thập trực tuyến (AFFILIATION_ONLINE_CACHE_DIR).",
            409,
        )


def cache_root() -> Path | None:
    raw = getattr(settings, "affiliation_online_cache_dir", None)
    return Path(raw) if raw else None


def _dois_to_enrich(db: Session) -> list[str]:
    rows = load_scopus_rows(db)
    seen: dict[str, None] = {}
    for row in rows:
        doi = normalize_doi(row.get("DOI"))
        if doi:
            seen.setdefault(doi, None)
    return list(seen)[: settings.affiliation_online_max_dois_per_run]


def start_job(db: Session, actor: User) -> AffiliationEnrichmentJob:
    root = cache_root()
    if root is None:
        raise OnlineCacheNotConfigured
    got = db.execute(text("select pg_try_advisory_xact_lock(:k)"), {"k": _START_LOCK_KEY}).scalar_one()
    if not got:
        db.rollback()
        raise EnrichmentAlreadyRunning
    already_active = db.execute(
        select(AffiliationEnrichmentJob.id).where(
            AffiliationEnrichmentJob.status.in_(AFFILIATION_ENRICHMENT_ACTIVE_STATUSES)
        )
    ).first()
    if already_active is not None:
        db.rollback()
        raise EnrichmentAlreadyRunning
    dois = _dois_to_enrich(db)
    if not dois:
        db.rollback()
        raise NoPublicationsToEnrich
    job = AffiliationEnrichmentJob(requested_by_user_id=actor.id, total_dois=len(dois))
    db.add(job)
    db.flush()
    db.add(
        AuditEvent(
            entity_type="affiliation_enrichment_job",
            entity_id=job.id,
            action=STARTED_ACTION,
            actor_type="USER",
            actor_user_id=actor.id,
            event_metadata={"total_dois": len(dois)},
        )
    )
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: uuid.UUID) -> AffiliationEnrichmentJob | None:
    return db.query(AffiliationEnrichmentJob).filter(AffiliationEnrichmentJob.id == job_id).first()


def cancel_job(db: Session, job_id: uuid.UUID, actor: User) -> AffiliationEnrichmentJob | None:
    for retry in range(2):
        item = get_job(db, job_id)
        if item is None:
            return None
        if item.status not in AFFILIATION_ENRICHMENT_ACTIVE_STATUSES:
            return item
        item.status = "CANCELLED"
        item.updated_at = datetime.now(UTC)
        db.add(
            AuditEvent(
                entity_type="affiliation_enrichment_job",
                entity_id=item.id,
                action=CANCELLED_ACTION,
                actor_type="USER",
                actor_user_id=actor.id,
                event_metadata={"processed_dois": item.processed_dois, "total_dois": item.total_dois},
            )
        )
        try:
            db.commit()
            return item
        except StaleDataError:
            db.rollback()
            if retry == 0:
                continue
            raise
        except SQLAlchemyError:
            db.rollback()
            raise
    return None


def _dois_for_job(job_id: uuid.UUID) -> tuple[list[str], Path] | None:
    with get_session_factory()() as db:
        item = get_job(db, job_id)
        if item is None or item.status not in AFFILIATION_ENRICHMENT_ACTIVE_STATUSES:
            return None
        item.status = "RUNNING"
        item.updated_at = datetime.now(UTC)
        db.commit()
    root = cache_root()
    if root is None:
        return None
    bundle_dir = root / str(job_id)
    with get_session_factory()() as db:
        dois = _dois_to_enrich(db)
    return dois, bundle_dir


def _is_active(job_id: uuid.UUID) -> bool:
    with get_session_factory()() as db:
        item = get_job(db, job_id)
        return item is not None and item.status in AFFILIATION_ENRICHMENT_ACTIVE_STATUSES


def _save_progress(job_id: uuid.UUID, progress: FetchProgress) -> None:
    with get_session_factory()() as db:
        item = get_job(db, job_id)
        if item is None or item.status not in AFFILIATION_ENRICHMENT_ACTIVE_STATUSES:
            return
        item.processed_dois = progress.done
        item.openalex_found = progress.openalex_found
        item.crossref_found = progress.crossref_found
        item.orcid_fetched = progress.orcid_fetched
        item.updated_at = datetime.now(UTC)
        try:
            db.commit()
        except StaleDataError:
            db.rollback()


def _finish(job_id: uuid.UUID, bundle_dir: Path) -> None:
    with get_session_factory()() as db:
        item = get_job(db, job_id)
        if item is None or item.status not in AFFILIATION_ENRICHMENT_ACTIVE_STATUSES:
            return
        item.status = "COMPLETED"
        item.bundle_dir = str(bundle_dir)
        item.updated_at = datetime.now(UTC)
        db.add(
            AuditEvent(
                entity_type="affiliation_enrichment_job",
                entity_id=item.id,
                action=COMPLETED_ACTION,
                actor_type="SYSTEM",
                actor_user_id=None,
                actor_service="affiliation_enrichment_worker",
                event_metadata={
                    "total_dois": item.total_dois,
                    "openalex_found": item.openalex_found,
                    "crossref_found": item.crossref_found,
                    "orcid_fetched": item.orcid_fetched,
                },
            )
        )
        db.commit()


def _fail(job_id: uuid.UUID, code: str, message: str) -> None:
    with get_session_factory()() as db:
        item = get_job(db, job_id)
        if item is None or item.status not in AFFILIATION_ENRICHMENT_ACTIVE_STATUSES:
            return
        item.status = "FAILED"
        item.error_summary = {"code": code, "message": message}
        item.updated_at = datetime.now(UTC)
        db.add(
            AuditEvent(
                entity_type="affiliation_enrichment_job",
                entity_id=item.id,
                action=FAILED_ACTION,
                actor_type="SYSTEM",
                actor_user_id=None,
                actor_service="affiliation_enrichment_worker",
                event_metadata={"code": code},
            )
        )
        db.commit()


def process_enrichment_job(job_id: uuid.UUID) -> None:
    """Run after the response. Mirrors ``process_import_job``'s per-step session pattern."""

    setup = _dois_for_job(job_id)
    if setup is None:
        return
    dois, bundle_dir = setup

    async def progress_cb(progress: FetchProgress) -> None:
        _save_progress(job_id, progress)

    def should_continue() -> bool:
        return _is_active(job_id)

    try:
        asyncio.run(
            run_enrichment(bundle_dir, dois, progress_cb=progress_cb, should_continue=should_continue)
        )
        _finish(job_id, bundle_dir)
    except AffiliationFetchCancelled:
        pass  # status already CANCELLED by the caller; nothing more to record
    except Exception:
        _fail(job_id, "ENRICHMENT_PROCESSING_FAILED", "Không thể hoàn tất thu thập dữ liệu trực tuyến.")


__all__ = [
    "AffiliationEnrichmentError",
    "COMPLETED_ACTION",
    "CANCELLED_ACTION",
    "EnrichmentAlreadyRunning",
    "FAILED_ACTION",
    "NoPublicationsToEnrich",
    "OnlineCacheNotConfigured",
    "STARTED_ACTION",
    "cache_root",
    "cancel_job",
    "get_job",
    "process_enrichment_job",
    "start_job",
]
