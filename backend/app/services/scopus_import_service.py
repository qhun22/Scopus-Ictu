"""Durable lifecycle and provenance handling for Scopus CSV imports."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query, Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import settings
from app.core.database import get_session_factory
from app.core.exceptions import APIError
from app.core.security import password_hasher, token_service
from app.models.governance import AuditEvent, User
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.schemas.scopus_import import (
    ScopusImportResponse,
)
from app.services.parser.scopus_csv_parser import ParsedScopusFile, ScopusCsvError, ScopusCsvParser

ACTIVE_STATUSES = frozenset({"RECEIVED", "PARSING", "VALIDATED"})
COMPLETED_STATUSES = frozenset({"STAGED", "APPLIED"})
TERMINAL_STATUSES = frozenset({"STAGED", "APPLIED", "FAILED", "CANCELLED"})
ALLOWED_EXTENSIONS = frozenset({".csv"})
MAX_REPORTED_ROW_ERRORS = 20
WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)


class ImportStorageError(RuntimeError):
    """A lifecycle write could not be committed safely."""


class ImportAlreadyProcessing(RuntimeError):
    def __init__(self, existing_import_id: uuid.UUID) -> None:
        self.existing_import_id = existing_import_id


class DuplicateImportConfirmationRequired(RuntimeError):
    def __init__(self, previous: ScopusImport) -> None:
        self.import_id = previous.id
        self.filename = previous.file_name
        self.imported_at = previous.created_at


class ImportAlreadyFinished(RuntimeError):
    def __init__(self, status: str) -> None:
        self.status = status


def validate_upload_filename(filename: str | None) -> str:
    if filename is None or not filename.strip():
        raise ValueError("INVALID_IMPORT_FILE")
    cleaned = filename.strip()
    path = PureWindowsPath(cleaned)
    if (
        len(cleaned) > 255
        or cleaned in {".", ".."}
        or "/" in cleaned
        or "\\" in cleaned
        or ":" in cleaned
        or any(ord(char) < 32 for char in cleaned)
        or PurePosixPath(cleaned).is_absolute()
        or path.is_absolute()
        or path.stem.upper() in WINDOWS_RESERVED_NAMES
    ):
        raise ValueError("INVALID_IMPORT_FILE")
    if path.suffix.casefold() not in ALLOWED_EXTENSIONS:
        raise ValueError("UNSUPPORTED_IMPORT_FORMAT")
    return cleaned


def create_import_job(
    db: Session,
    *,
    filename: str,
    content: bytes,
    actor: User,
    allow_duplicate: bool = False,
) -> ScopusImportResponse:
    digest = hashlib.sha256(content).hexdigest()
    now = datetime.now(UTC)
    try:
        _lock_digest(db, digest)
        active = _latest_by_hash(db, digest, ACTIVE_STATUSES)
        if active is not None:
            raise ImportAlreadyProcessing(active.id)
        previous = _latest_by_hash(db, digest, COMPLETED_STATUSES)
        if previous is not None and not allow_duplicate:
            raise DuplicateImportConfirmationRequired(previous)

        item = ScopusImport(
            id=uuid.uuid4(),
            file_name=filename,
            file_sha256=digest,
            total_records=0,
            valid_records=0,
            invalid_records=0,
            status="RECEIVED",
            error_summary=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        db.add(
            _user_audit(
                item,
                actor.id,
                "SCOPUS_IMPORT_STARTED",
                None,
                {"status": "RECEIVED"},
                {"filename": filename, "file_sha256": digest},
            )
        )
        db.commit()
        return to_import_response(item, performed_by=actor.display_name)
    except (ImportAlreadyProcessing, DuplicateImportConfirmationRequired):
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise ImportStorageError("The import job could not be created.") from exc


def process_import_job(import_id: uuid.UUID, content: bytes, actor_user_id: uuid.UUID) -> None:
    """Run after the response; each transition/batch is independently committed."""
    try:
        if not _transition_active(import_id, status="PARSING"):
            return
        parsed = ScopusCsvParser().parse_bytes(content)
        if not _save_parse_result(import_id, parsed):
            return
        records = _raw_records(import_id, parsed)
        size = settings.scopus_import_batch_size
        for offset in range(0, len(records), size):
            if not _save_batch(import_id, records[offset : offset + size]):
                return
        if not _finish_import(import_id, actor_user_id):
            return
    except ScopusCsvError as exc:
        _fail_import(import_id, exc.code, exc.detail)
    except Exception:
        _fail_import(import_id, "IMPORT_PROCESSING_FAILED", "Không thể hoàn tất xử lý tệp CSV.")


def cancel_import(db: Session, import_id: uuid.UUID, actor: User) -> ScopusImportResponse | None:
    for retry in range(2):
        item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
        if item is None:
            return None
        if item.status == "CANCELLED":
            return to_import_response(item, performed_by=actor.display_name)
        if item.status in TERMINAL_STATUSES:
            raise ImportAlreadyFinished(item.status)
        before = {"status": item.status}
        item.status = "CANCELLED"
        item.updated_at = datetime.now(UTC)
        db.add(
            _user_audit(
                item,
                actor.id,
                "SCOPUS_IMPORT_CANCELLED",
                before,
                {"status": "CANCELLED"},
                {
                    "processed_records": item.valid_records + item.invalid_records,
                    "total_records": item.total_records,
                },
            )
        )
        try:
            db.commit()
            return to_import_response(item, performed_by=actor.display_name)
        except StaleDataError:
            db.rollback()
            if retry == 0:
                continue
            raise
        except SQLAlchemyError:
            db.rollback()
            raise
    raise ImportStorageError("The cancellation could not be stored.")


def recover_interrupted_imports() -> int:
    """Fail active jobs whose in-memory upload disappeared during restart."""
    with get_session_factory()() as db:
        items = db.query(ScopusImport).filter(ScopusImport.status.in_(ACTIVE_STATUSES)).all()
        now = datetime.now(UTC)
        for item in items:
            before = {"status": item.status}
            item.status = "FAILED"
            item.updated_at = now
            item.error_summary = _with_fatal(
                item.error_summary,
                "IMPORT_INTERRUPTED",
                "Tiến trình nhập bị gián đoạn khi dịch vụ khởi động lại.",
            )
            db.add(
                _system_audit(
                    item,
                    "SCOPUS_IMPORT_FAILED",
                    before,
                    {"status": "FAILED"},
                    {"reason": "IMPORT_INTERRUPTED"},
                )
            )
        if items:
            db.commit()
        return len(items)


def _safe_dict(val: Any) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _ensure_dt(val: Any) -> datetime:
    if val is None:
        return datetime.now(UTC)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt
        except Exception:
            return datetime.now(UTC)
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=UTC)
        return val
    return datetime.now(UTC)


def list_imports(db: Session, *, limit: int = 50) -> list[ScopusImportResponse]:
    """Return unified import history including Scopus CSV and Lecturer JSON imports."""
    items = db.query(ScopusImport).order_by(ScopusImport.created_at.desc()).limit(limit).all()
    names = _actor_names(db, [item.id for item in items])
    scopus_responses = [
        to_import_response(item, performed_by=names.get(item.id, "Không xác định"))
        for item in items
    ]

    lecturer_audits = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "lecturer_dataset",
            AuditEvent.action == "LECTURER_DATASET_IMPORTED",
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    rolled_back_audits = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "lecturer_dataset",
            AuditEvent.action == "LECTURER_DATASET_ROLLED_BACK",
        )
        .all()
    )
    hidden_history_audits = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "lecturer_dataset",
            AuditEvent.action == "LECTURER_DATASET_HISTORY_DELETED",
        )
        .all()
    )
    rolled_back_ids: set[uuid.UUID] = {
        a.entity_id for a in rolled_back_audits if a.entity_id is not None
    }.union({a.id for a in rolled_back_audits if a.id is not None})
    for a in rolled_back_audits:
        meta = _safe_dict(a.event_metadata)
        if meta.get("import_id"):
            try:
                rolled_back_ids.add(uuid.UUID(str(meta["import_id"])))
            except (ValueError, TypeError):
                pass

    hidden_history_ids: set[uuid.UUID] = {
        a.entity_id for a in hidden_history_audits if a.entity_id is not None
    }
    for a in hidden_history_audits:
        meta = _safe_dict(a.event_metadata)
        if meta.get("import_id"):
            try:
                hidden_history_ids.add(uuid.UUID(str(meta["import_id"])))
            except (ValueError, TypeError):
                pass

    actor_ids = [a.actor_user_id for a in lecturer_audits if a.actor_user_id is not None]
    lecturer_actors: dict[uuid.UUID, str] = {}
    if actor_ids:
        users = db.query(User).filter(User.id.in_(set(actor_ids))).all()
        lecturer_actors = {u.id: u.display_name for u in users}

    lecturer_responses = []
    for audit in lecturer_audits:
        if audit.id in hidden_history_ids or audit.entity_id in hidden_history_ids:
            continue
        is_rolled_back = audit.id in rolled_back_ids or (
            audit.entity_id is not None and audit.entity_id in rolled_back_ids
        )
        after = _safe_dict(audit.after_state)
        meta = _safe_dict(audit.event_metadata)
        total = int(after.get("record_count") or meta.get("total") or meta.get("record_count") or 0)
        created = int(after.get("created") or meta.get("created") or 0)
        updated = int(after.get("updated") or meta.get("updated") or 0)
        unchanged = int(after.get("unchanged") or meta.get("unchanged") or 0)
        conflicts = int(after.get("conflicts") or meta.get("conflicts") or 0)
        warnings = int(after.get("warnings") or meta.get("warnings") or conflicts)
        actor_name = lecturer_actors.get(audit.actor_user_id) if audit.actor_user_id else None
        dt = _ensure_dt(audit.created_at)
        lecturer_responses.append(
            ScopusImportResponse(
                id=audit.id,
                type="LECTURERS",
                file_name=meta.get("filename", "ictu_lecturers.json"),
                status="CANCELLED" if is_rolled_back else "IMPORTED",
                total_records=total,
                imported_records=created + updated,
                failed_records=0,
                processed_records=total,
                progress_percent=100,
                duplicate_candidates=warnings,
                row_errors=[],
                error_summary=None,
                version=1,
                created_at=dt,
                updated_at=dt,
                started_at=dt,
                finished_at=dt,
                duration_seconds=0.0,
                is_terminal=True,
                performed_by=actor_name or "Không xác định",
                can_delete=is_rolled_back,
                lecturer_summary={
                    "created": created,
                    "updated": updated,
                    "unchanged": unchanged,
                    "conflicts": conflicts,
                    "warnings": warnings,
                    "dataset_name": meta.get("dataset_name"),
                    "schema_version": meta.get("dataset_schema_version", "1.0"),
                },
            )
        )

    all_imports = sorted(
        [*scopus_responses, *lecturer_responses],
        key=lambda x: _ensure_dt(x.created_at),
        reverse=True,
    )
    return all_imports[:limit]


def get_import_stats(all_items: list[ScopusImportResponse]):
    from app.schemas.scopus_import import UnifiedImportStats

    total = len(all_items)
    success = sum(
        1 for x in all_items if x.status in ("STAGED", "APPLIED", "IMPORTED")
    )
    processing = sum(
        1 for x in all_items if x.status in ("RECEIVED", "PARSING", "VALIDATED")
    )
    failed = sum(
        1 for x in all_items if x.status in ("FAILED", "CANCELLED")
    )
    return UnifiedImportStats(
        total_imports=total,
        success_count=success,
        processing_count=processing,
        failed_count=failed,
    )


def get_import(db: Session, import_id: uuid.UUID) -> ScopusImportResponse | None:
    item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
    if item is not None:
        return to_import_response(
            item,
            performed_by=_actor_names(db, [item.id]).get(item.id, "Không xác định"),
        )

    audit = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "lecturer_dataset",
            AuditEvent.action == "LECTURER_DATASET_IMPORTED",
            (AuditEvent.id == import_id) | (AuditEvent.entity_id == import_id),
        )
        .order_by(AuditEvent.created_at.desc())
        .first()
    )
    if audit is not None:
        history_deleted = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.entity_type == "lecturer_dataset",
                AuditEvent.action == "LECTURER_DATASET_HISTORY_DELETED",
                (AuditEvent.entity_id == audit.entity_id) | (AuditEvent.entity_id == audit.id),
            )
            .first()
        )
        if history_deleted is not None:
            return None

        rb_check = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.entity_type == "lecturer_dataset",
                AuditEvent.action == "LECTURER_DATASET_ROLLED_BACK",
                (AuditEvent.entity_id == audit.entity_id) | (AuditEvent.entity_id == audit.id),
            )
            .first()
        )
        is_rolled_back = rb_check is not None

        after = _safe_dict(audit.after_state)
        meta = _safe_dict(audit.event_metadata)
        total = int(after.get("record_count") or meta.get("total") or meta.get("record_count") or 0)
        created = int(after.get("created") or meta.get("created") or 0)
        updated = int(after.get("updated") or meta.get("updated") or 0)
        unchanged = int(after.get("unchanged") or meta.get("unchanged") or 0)
        conflicts = int(after.get("conflicts") or meta.get("conflicts") or 0)
        warnings = int(after.get("warnings") or meta.get("warnings") or conflicts)
        actor_name = None
        if audit.actor_user_id:
            u = db.query(User).filter(User.id == audit.actor_user_id).first()
            if u:
                actor_name = u.display_name
        dt = _ensure_dt(audit.created_at)
        return ScopusImportResponse(
            id=audit.id,
            type="LECTURERS",
            file_name=meta.get("filename", "ictu_lecturers.json"),
            status="CANCELLED" if is_rolled_back else "IMPORTED",
            total_records=total,
            imported_records=created + updated,
            failed_records=0,
            processed_records=total,
            progress_percent=100,
            duplicate_candidates=warnings,
            row_errors=[],
            error_summary=None,
            version=1,
            created_at=dt,
            updated_at=dt,
            started_at=dt,
            finished_at=dt,
            duration_seconds=0.0,
            is_terminal=True,
            performed_by=actor_name or "Không xác định",
            can_delete=is_rolled_back,
            lecturer_summary={
                "created": created,
                "updated": updated,
                "unchanged": unchanged,
                "conflicts": conflicts,
                "warnings": warnings,
                "dataset_name": meta.get("dataset_name"),
                "schema_version": meta.get("dataset_schema_version", "1.0"),
            },
        )
    return None


def delete_scopus_import(db: Session, import_id: uuid.UUID, actor: User) -> bool:
    """Delete a Scopus import, or hide a rolled-back lecturer import from history."""
    from app.core.exceptions import APIError
    from app.models.publication import PublicationRawSource, ScopusAuthorNameVariant

    item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
    if item is None:
        return delete_lecturer_import_history(db, import_id=import_id, actor=actor)

    if item.status in ACTIVE_STATUSES:
        raise APIError(
            status_code=409,
            detail="Không thể xóa đợt nhập đang trong quá trình xử lý.",
            code="IMPORT_ALREADY_PROCESSING",
        )

    # Check downstream dependencies
    in_use_pub = (
        db.query(PublicationRawSource)
        .join(RawScopusRecord, PublicationRawSource.raw_record_id == RawScopusRecord.id)
        .filter(RawScopusRecord.import_id == item.id)
        .first()
    )
    in_use_author = (
        db.query(ScopusAuthorNameVariant)
        .join(
            RawScopusRecord,
            ScopusAuthorNameVariant.first_seen_raw_record_id == RawScopusRecord.id,
        )
        .filter(RawScopusRecord.import_id == item.id)
        .first()
    )
    if in_use_pub is not None or in_use_author is not None:
        raise APIError(
            status_code=409,
            detail="Dữ liệu từ đợt nhập này đang được hệ thống sử dụng.",
            code="IMPORT_IN_USE",
        )

    # Audit deletion before destructive removal
    audit = AuditEvent(
        entity_type="scopus_imports",
        entity_id=item.id,
        action="SCOPUS_IMPORT_DELETED",
        actor_type="USER",
        actor_user_id=actor.id,
        actor_service=None,
        before_state={
            "status": item.status,
            "file_name": item.file_name,
            "file_sha256": item.file_sha256,
            "total_records": item.total_records,
            "valid_records": item.valid_records,
            "invalid_records": item.invalid_records,
        },
        after_state={"status": "DELETED"},
        event_metadata={
            "import_id": str(item.id),
            "filename": item.file_name,
            "file_sha256": item.file_sha256,
            "total_records": item.total_records,
            "valid_records": item.valid_records,
            "invalid_records": item.invalid_records,
            "deleted_by": actor.display_name,
            "deleted_at": datetime.now(UTC).isoformat(),
        },
    )
    db.add(audit)
    db.query(RawScopusRecord).filter(RawScopusRecord.import_id == item.id).delete(
        synchronize_session=False
    )
    db.delete(item)
    db.commit()
    return True


def rollback_lecturer_import(db: Session, import_id: uuid.UUID, actor: User) -> bool:
    """Rollback lecturer records without deleting the import-history entry."""
    from app.core.exceptions import APIError
    from app.services.lecturer_dataset.rollback import (
        LecturerRollbackError,
        LecturerRollbackService,
    )

    try:
        LecturerRollbackService().rollback_import(db, import_id=import_id, actor=actor)
        return True
    except LecturerRollbackError as exc:
        if exc.code == "LECTURER_IMPORT_NOT_FOUND":
            return False
        raise APIError(
            status_code=exc.status_code,
            detail=exc.message,
            code=exc.code,
            data=exc.data,
        ) from exc


def delete_lecturer_import_history(
    db: Session,
    *,
    import_id: uuid.UUID,
    actor: User,
) -> bool:
    """Hide a lecturer import from history after its data was rolled back.

    Audit events stay append-only. A deletion marker removes the entry from the
    import-history view while preserving the security audit trail.
    """
    from app.core.exceptions import APIError

    import_audit = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "lecturer_dataset",
            AuditEvent.action == "LECTURER_DATASET_IMPORTED",
            (AuditEvent.id == import_id) | (AuditEvent.entity_id == import_id),
        )
        .first()
    )
    if import_audit is None:
        return False

    history_entity_id = import_audit.entity_id or import_audit.id
    rolled_back = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "lecturer_dataset",
            AuditEvent.action == "LECTURER_DATASET_ROLLED_BACK",
            (AuditEvent.entity_id == history_entity_id)
            | (AuditEvent.entity_id == import_audit.id),
        )
        .first()
    )
    if rolled_back is None:
        raise APIError(
            status_code=409,
            detail="Bạn chưa hoàn tác đợt nhập giảng viên này.",
            code="LECTURER_IMPORT_NOT_ROLLED_BACK",
        )

    already_deleted = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "lecturer_dataset",
            AuditEvent.action == "LECTURER_DATASET_HISTORY_DELETED",
            (AuditEvent.entity_id == history_entity_id)
            | (AuditEvent.entity_id == import_audit.id),
        )
        .first()
    )
    if already_deleted is not None:
        # Treat repeated requests as success so a stale browser row can refresh
        # cleanly after the original deletion was committed.
        return True

    meta = _safe_dict(import_audit.event_metadata)
    db.add(
        AuditEvent(
            entity_type="lecturer_dataset",
            entity_id=history_entity_id,
            action="LECTURER_DATASET_HISTORY_DELETED",
            actor_type="USER",
            actor_user_id=actor.id,
            actor_service=None,
            before_state={"status": "ROLLED_BACK"},
            after_state={"status": "HISTORY_DELETED"},
            event_metadata={
                "import_id": str(import_audit.id),
                "filename": meta.get("filename", "ictu_lecturers.json"),
                "deleted_by": actor.display_name,
                "deleted_at": datetime.now(UTC).isoformat(),
            },
        )
    )
    db.commit()
    return True



def to_import_response(item: ScopusImport, *, performed_by: str | None) -> ScopusImportResponse:
    processed = item.valid_records + item.invalid_records
    progress = (
        min(100, round(processed * 100 / item.total_records))
        if item.total_records
        else (100 if item.status in COMPLETED_STATUSES else 0)
    )
    terminal = item.status in TERMINAL_STATUSES
    summary = item.error_summary or {}
    return ScopusImportResponse(
        id=item.id,
        type="SCOPUS",
        file_name=item.file_name,
        status=item.status,
        total_records=item.total_records,
        imported_records=item.valid_records,
        failed_records=item.invalid_records,
        processed_records=processed,
        progress_percent=progress,
        duplicate_candidates=int(summary.get("duplicate_candidates", 0)),
        row_errors=list(summary.get("row_errors", [])),
        error_summary=item.error_summary,
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at,
        started_at=item.created_at,
        finished_at=item.updated_at if terminal else None,
        duration_seconds=max(0.0, (item.updated_at - item.created_at).total_seconds()),
        is_terminal=terminal,
        performed_by=performed_by or "Không xác định",
        can_delete=terminal,
        scopus_summary=item.error_summary,
    )


def _latest_by_hash(db: Session, digest: str, statuses: frozenset[str]) -> ScopusImport | None:
    return (
        db.query(ScopusImport)
        .filter(ScopusImport.file_sha256 == digest, ScopusImport.status.in_(statuses))
        .order_by(ScopusImport.created_at.desc())
        .first()
    )


def _lock_digest(db: Session, digest: str) -> None:
    bind = db.get_bind()
    if getattr(getattr(bind, "dialect", None), "name", None) == "postgresql":
        key = int.from_bytes(bytes.fromhex(digest[:16]), "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def _transition_active(import_id: uuid.UUID, *, status: str) -> bool:
    with get_session_factory()() as db:
        item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
        if item is None or item.status not in ACTIVE_STATUSES:
            return False
        item.status = status
        item.updated_at = datetime.now(UTC)
        db.commit()
        return True


def _save_parse_result(import_id: uuid.UUID, parsed: ParsedScopusFile) -> bool:
    with get_session_factory()() as db:
        item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
        if item is None or item.status not in ACTIVE_STATUSES:
            return False
        item.total_records = parsed.total_records
        item.error_summary = _summary(parsed)
        item.status = "VALIDATED"
        item.updated_at = datetime.now(UTC)
        db.commit()
        return True


def _save_batch(import_id: uuid.UUID, records: list[RawScopusRecord]) -> bool:
    with get_session_factory()() as db:
        item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
        if item is None or item.status not in ACTIVE_STATUSES:
            return False
        db.add_all(records)
        item.valid_records += sum(record.validation_status == "VALID" for record in records)
        item.invalid_records += sum(record.validation_status == "INVALID" for record in records)
        item.updated_at = datetime.now(UTC)
        try:
            db.commit()
            return True
        except StaleDataError:
            db.rollback()
            return False


def _finish_import(import_id: uuid.UUID, actor_user_id: uuid.UUID) -> bool:
    with get_session_factory()() as db:
        item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
        if item is None or item.status not in ACTIVE_STATUSES:
            return False
        if item.valid_records + item.invalid_records != item.total_records:
            raise ImportStorageError("Incomplete counts cannot be marked completed.")
        before = {"status": item.status}
        item.status = "STAGED"
        item.updated_at = datetime.now(UTC)
        db.add(
            _user_audit(
                item,
                actor_user_id,
                "SCOPUS_IMPORT_COMPLETED",
                before,
                {"status": "STAGED"},
                {
                    "total_records": item.total_records,
                    "valid_records": item.valid_records,
                    "invalid_records": item.invalid_records,
                },
            )
        )
        try:
            db.commit()
            return True
        except StaleDataError:
            db.rollback()
            return False


def _fail_import(import_id: uuid.UUID, code: str, message: str) -> None:
    try:
        with get_session_factory()() as db:
            item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
            if item is None or item.status not in ACTIVE_STATUSES:
                return
            before = {"status": item.status}
            item.status = "FAILED"
            item.updated_at = datetime.now(UTC)
            item.error_summary = _with_fatal(item.error_summary, code, message)
            db.add(
                _system_audit(
                    item, "SCOPUS_IMPORT_FAILED", before, {"status": "FAILED"}, {"reason": code}
                )
            )
            db.commit()
    except SQLAlchemyError:
        return


def _summary(parsed: ParsedScopusFile) -> dict | None:
    if not parsed.row_errors and not parsed.duplicate_candidates:
        return None
    return {
        "row_error_count": len(parsed.row_errors),
        "row_errors": [
            {"row_number": error.row_number, "code": error.code, "message": error.message}
            for error in parsed.row_errors[:MAX_REPORTED_ROW_ERRORS]
        ],
        "row_errors_truncated": len(parsed.row_errors) > MAX_REPORTED_ROW_ERRORS,
        "duplicate_candidates": parsed.duplicate_candidates,
        "duplicate_row_numbers": list(parsed.duplicate_row_numbers[:MAX_REPORTED_ROW_ERRORS]),
    }


def _raw_records(import_id: uuid.UUID, parsed: ParsedScopusFile) -> list[RawScopusRecord]:
    records = [
        RawScopusRecord(
            import_id=import_id,
            row_number=row.row_number,
            row_hash=row.row_hash,
            eid_raw=row.eid_raw,
            doi_raw=row.doi_raw,
            raw_payload=row.raw_payload,
            validation_status="VALID",
            validation_errors=None,
        )
        for row in parsed.rows
    ]
    records.extend(
        RawScopusRecord(
            import_id=import_id,
            row_number=error.row_number,
            row_hash=error.row_hash,
            eid_raw=None,
            doi_raw=None,
            raw_payload={"_headers": list(parsed.headers), "_raw_values": list(error.raw_values)},
            validation_status="INVALID",
            validation_errors=[{"code": error.code, "message": error.message}],
        )
        for error in parsed.row_errors
    )
    return sorted(records, key=lambda record: record.row_number)


def _with_fatal(summary: dict | None, code: str, message: str) -> dict:
    return {**(summary or {}), "fatal_error": {"code": code, "message": message}}


def _user_audit(
    item: ScopusImport,
    actor_id: uuid.UUID,
    action: str,
    before: dict | None,
    after: dict | None,
    metadata: dict | None,
) -> AuditEvent:
    return AuditEvent(
        entity_type="scopus_imports",
        entity_id=item.id,
        action=action,
        actor_type="USER",
        actor_user_id=actor_id,
        actor_service=None,
        before_state=before,
        after_state=after,
        event_metadata={"import_id": str(item.id), **(metadata or {})},
    )


def _system_audit(
    item: ScopusImport, action: str, before: dict | None, after: dict | None, metadata: dict | None
) -> AuditEvent:
    return AuditEvent(
        entity_type="scopus_imports",
        entity_id=item.id,
        action=action,
        actor_type="SYSTEM",
        actor_user_id=None,
        actor_service="scopus_import_worker",
        before_state=before,
        after_state=after,
        event_metadata={"import_id": str(item.id), **(metadata or {})},
    )


def _actor_names(db: Session, import_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not import_ids:
        return {}
    audits = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "scopus_imports",
            AuditEvent.entity_id.in_(import_ids),
            AuditEvent.action == "SCOPUS_IMPORT_STARTED",
            AuditEvent.actor_user_id.is_not(None),
        )
        .order_by(AuditEvent.created_at.desc())
        .all()
    )
    actor_by_import: dict[uuid.UUID, uuid.UUID] = {}
    for audit in audits:
        if audit.actor_user_id is not None and audit.entity_id not in actor_by_import:
            actor_by_import[audit.entity_id] = audit.actor_user_id
    if not actor_by_import:
        return {}
    users = db.query(User).filter(User.id.in_(set(actor_by_import.values()))).all()
    names = {user.id: user.display_name for user in users}
    return {
        import_id: names[actor_id]
        for import_id, actor_id in actor_by_import.items()
        if actor_id in names
    }


__all__ = [
    "ACTIVE_STATUSES",
    "COMPLETED_STATUSES",
    "TERMINAL_STATUSES",
    "DuplicateImportConfirmationRequired",
    "ImportAlreadyFinished",
    "ImportAlreadyProcessing",
    "ImportStorageError",
    "cancel_import",
    "create_import_job",
    "delete_scopus_import",
    "eligible_raw_records",
    "get_import",
    "get_import_stats",
    "list_imports",
    "process_import_job",
    "recover_interrupted_imports",
    "rollback_lecturer_import",
    "to_import_response",
    "validate_upload_filename",
]
