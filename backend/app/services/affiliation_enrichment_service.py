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
import hashlib
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import settings
from app.core.database import get_engine, get_session_factory
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
_pending_worker_leases: dict[uuid.UUID, Connection] = {}
_pending_worker_leases_lock = threading.Lock()


def _job_lock_key(job_id: uuid.UUID) -> int:
    """Map a UUID to PostgreSQL's signed 64-bit advisory-lock key space."""

    digest = hashlib.blake2b(job_id.bytes, digest_size=8, person=b"aff-enrich").digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


def _acquire_worker_lease(job_id: uuid.UUID, engine: Engine) -> Connection | None:
    """Hold a session advisory lock for the full lifetime of one worker."""

    connection = engine.connect()
    try:
        acquired = connection.execute(
            text("select pg_try_advisory_lock(:lock_key)"),
            {"lock_key": _job_lock_key(job_id)},
        ).scalar_one()
        connection.commit()
        if acquired:
            return connection
        connection.close()
        return None
    except Exception:
        connection.close()
        raise


def _release_worker_lease(job_id: uuid.UUID, connection: Connection) -> None:
    try:
        connection.execute(
            text("select pg_advisory_unlock(:lock_key)"),
            {"lock_key": _job_lock_key(job_id)},
        )
        connection.commit()
    finally:
        connection.close()


def _take_pending_worker_lease(job_id: uuid.UUID) -> Connection | None:
    with _pending_worker_leases_lock:
        return _pending_worker_leases.pop(job_id, None)


def _release_pending_worker_lease(job_id: uuid.UUID) -> None:
    lease = _take_pending_worker_lease(job_id)
    if lease is not None:
        _release_worker_lease(job_id, lease)


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


def start_job(
    db: Session, actor: User, *, reserve_worker_lease: bool = False
) -> AffiliationEnrichmentJob:
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
    job = AffiliationEnrichmentJob(requested_by_user_id=actor.id, total_dois=len(dois), doi_list=dois)
    db.add(job)
    db.flush()
    worker_lease = None
    if reserve_worker_lease:
        worker_lease = _acquire_worker_lease(job.id, db.get_bind())
        if worker_lease is None:
            db.rollback()
            raise EnrichmentAlreadyRunning
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
    try:
        db.commit()
        db.refresh(job)
    except Exception:
        db.rollback()
        if worker_lease is not None:
            _release_worker_lease(job.id, worker_lease)
        raise
    if worker_lease is not None:
        with _pending_worker_leases_lock:
            _pending_worker_leases[job.id] = worker_lease
    return job


def get_job(db: Session, job_id: uuid.UUID) -> AffiliationEnrichmentJob | None:
    return db.query(AffiliationEnrichmentJob).filter(AffiliationEnrichmentJob.id == job_id).first()


def get_latest_job(db: Session) -> AffiliationEnrichmentJob | None:
    """Most recently created job, regardless of status — lets the ADMIN UI
    find and display the right job after a reload/tab switch without
    remembering its id client-side, and without starting a new one just
    because the page reloaded."""

    return (
        db.query(AffiliationEnrichmentJob)
        .order_by(AffiliationEnrichmentJob.created_at.desc())
        .first()
    )


def recover_interrupted_enrichment_jobs() -> int:
    """Fail active jobs whose in-process background task disappeared when the
    server restarted — same pattern as
    ``scopus_import_service.recover_interrupted_imports``. A RECEIVED/RUNNING
    row left over from a prior process is never silently resumed (there is
    no mechanism to re-attach to the old asyncio task, and claiming otherwise
    without implementing and testing real resumption would be a false
    promise to the ADMIN); it is explicitly marked FAILED with a reason the
    UI can show, so the ADMIN sees a clear, actionable state instead of a
    progress bar that never moves again."""

    with get_session_factory()() as db:
        items = db.query(AffiliationEnrichmentJob).filter(
            AffiliationEnrichmentJob.status.in_(AFFILIATION_ENRICHMENT_ACTIVE_STATUSES)
        ).with_for_update(skip_locked=True).all()
        now = datetime.now(UTC)
        recovered = 0
        for item in items:
            # A live worker in this or another API process holds the matching
            # session-level advisory lock. The transaction lock prevents a
            # worker from claiming the same job while it is being marked.
            owns_lease = db.execute(
                text("select pg_try_advisory_xact_lock(:lock_key)"),
                {"lock_key": _job_lock_key(item.id)},
            ).scalar_one()
            if not owns_lease:
                continue
            item.status = "FAILED"
            item.error_summary = {
                "code": "ENRICHMENT_INTERRUPTED",
                "message": "Tiến trình thu thập đơn vị trực tuyến bị gián đoạn khi dịch vụ khởi động lại.",
            }
            item.updated_at = now
            db.add(
                AuditEvent(
                    entity_type="affiliation_enrichment_job",
                    entity_id=item.id,
                    action=FAILED_ACTION,
                    actor_type="SYSTEM",
                    actor_user_id=None,
                    actor_service="affiliation_enrichment_worker",
                    event_metadata={"code": "ENRICHMENT_INTERRUPTED"},
                )
            )
            recovered += 1
        if recovered:
            db.commit()
        else:
            db.rollback()
        return recovered


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


class EnrichmentNotResumable(AffiliationEnrichmentError):
    def __init__(self, reason: str = "") -> None:
        super().__init__(
            "ENRICHMENT_NOT_RESUMABLE",
            f"Lượt thu thập này không thể tiếp tục: {reason}" if reason else "Lượt thu thập này không thể tiếp tục.",
            409,
        )


def resume_job(
    db: Session, prior_job_id: uuid.UUID, actor: User, *, reserve_worker_lease: bool = False
) -> AffiliationEnrichmentJob:
    """Create a new job that continues from where a FAILED/CANCELLED job left off.

    The new job reuses the ``doi_list`` from the prior job, skipping the first
    ``processed_dois`` entries so only the unfinished tail is fetched again.
    """
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

    prior = db.query(AffiliationEnrichmentJob).filter(AffiliationEnrichmentJob.id == prior_job_id).first()
    if prior is None:
        db.rollback()
        raise EnrichmentNotResumable("Không tìm thấy lượt thu thập gốc.")
    if prior.status not in ("FAILED", "CANCELLED"):
        db.rollback()
        raise EnrichmentNotResumable(f"Trạng thái hiện tại là {prior.status}, chỉ có thể tiếp tục từ FAILED hoặc CANCELLED.")
    if not prior.doi_list:
        db.rollback()
        raise EnrichmentNotResumable("Lượt gốc không lưu danh sách DOI (có thể được tạo trước khi tính năng này ra mắt).")

    skip = prior.processed_dois or 0
    remaining_dois = list(prior.doi_list)[skip:]
    if not remaining_dois:
        db.rollback()
        raise EnrichmentNotResumable("Tất cả DOI đã được xử lý, không còn gì để tiếp tục.")

    job = AffiliationEnrichmentJob(
        requested_by_user_id=actor.id,
        total_dois=len(remaining_dois),
        doi_list=remaining_dois,
        resumed_from_job_id=prior_job_id,
    )
    db.add(job)
    db.flush()

    worker_lease = None
    if reserve_worker_lease:
        worker_lease = _acquire_worker_lease(job.id, db.get_bind())
        if worker_lease is None:
            db.rollback()
            raise EnrichmentAlreadyRunning

    db.add(
        AuditEvent(
            entity_type="affiliation_enrichment_job",
            entity_id=job.id,
            action=STARTED_ACTION,
            actor_type="USER",
            actor_user_id=actor.id,
            event_metadata={
                "total_dois": len(remaining_dois),
                "skipped_dois": skip,
                "resumed_from_job_id": str(prior_job_id),
            },
        )
    )
    try:
        db.commit()
        db.refresh(job)
    except Exception:
        db.rollback()
        if worker_lease is not None:
            _release_worker_lease(job.id, worker_lease)
        raise

    if worker_lease is not None:
        with _pending_worker_leases_lock:
            _pending_worker_leases[job.id] = worker_lease
    return job


def _dois_for_job(job_id: uuid.UUID) -> tuple[list[str], Path] | None:
    with get_session_factory()() as db:
        item = get_job(db, job_id)
        if item is None or item.status not in AFFILIATION_ENRICHMENT_ACTIVE_STATUSES:
            return None
        # Use the stored doi_list if available (resume path or normal start with stored list).
        # Fall back to a fresh query only for legacy jobs created before this column existed.
        stored_dois = list(item.doi_list) if item.doi_list else None
        item.status = "RUNNING"
        item.updated_at = datetime.now(UTC)
        db.commit()
    root = cache_root()
    if root is None:
        return None
    bundle_dir = root / str(job_id)
    if stored_dois is not None:
        return stored_dois, bundle_dir
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
    """Run after the response while holding a lease visible to every process."""

    lease = _take_pending_worker_lease(job_id)
    if lease is None:
        lease = _acquire_worker_lease(job_id, get_engine())
    if lease is None:
        return  # A worker in another process already owns this job.
    try:
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
    finally:
        _release_worker_lease(job_id, lease)


__all__ = [
    "AffiliationEnrichmentError",
    "COMPLETED_ACTION",
    "CANCELLED_ACTION",
    "EnrichmentAlreadyRunning",
    "EnrichmentNotResumable",
    "FAILED_ACTION",
    "NoPublicationsToEnrich",
    "OnlineCacheNotConfigured",
    "STARTED_ACTION",
    "cache_root",
    "cancel_job",
    "get_job",
    "get_latest_job",
    "process_enrichment_job",
    "recover_interrupted_enrichment_jobs",
    "resume_job",
    "start_job",
]
