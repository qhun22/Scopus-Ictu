"""ADMIN workflow for ingesting ICTU-Craw known-publication evidence from
the web app (preview -> apply), mirroring ``affiliation_workflow.py``.

The Craw source directory is never accepted from a request — it comes from
the server setting ``CRAW_SOURCE_DIR`` (same pattern as
``AFFILIATION_SOURCE_DIR``). This module only reads the three frozen Craw
artifact files and hands them to the existing, already-reviewed
``KnownPublicationIngestionService``; it does not duplicate that service's
mapping/dedup logic, and it does not touch ``lecturers``, Scopus canonical
data, candidates, or identities — only ``lecturer_source_snapshots`` and
``lecturer_known_publications``, exactly as that service already documents.

The JSON-parsing step (``build_sources``) is imported from the operator CLI
(``scripts/ingest_craw_known_publications.py``) rather than duplicated, so
there is exactly one implementation of the Craw-artifact-to-service-input
conversion shared by the CLI and this API workflow.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.governance import AuditEvent
from app.services.matching.candidate_persistence import canonical_json
from scripts.ingest_craw_known_publications import (
    CrawInput,
    blocking_problems,
    build_sources,
    preview_summary,
)
from app.services.lecturer_dataset.known_publication_ingestion import (
    KnownPublicationIngestionService,
)

APPLIED_ACTION = "CRAW_INGESTION_APPLIED"
FAILED_ACTION = "CRAW_INGESTION_FAILED"
_LOCK_KEY = 0x43524157  # "CRAW"


class CrawIngestionWorkflowError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


def configured_craw_dir() -> Path | None:
    raw = getattr(settings, "craw_source_dir", None)
    return Path(raw) if raw else None


@dataclass(slots=True)
class CrawPreview:
    fingerprint: str
    stats: dict[str, Any]
    preview: dict[str, Any]
    blocking: list[str]
    can_apply: bool
    blocked_reason: str | None


def _load_source(directory: Path | None) -> tuple[CrawInput | None, str | None]:
    directory = directory if directory is not None else configured_craw_dir()
    if directory is None:
        return None, "CRAW_SOURCE_NOT_CONFIGURED"
    if not directory.is_dir():
        return None, "CRAW_SOURCE_DIR_MISSING"
    try:
        return build_sources(directory), None
    except (FileNotFoundError, OSError):
        return None, "CRAW_SOURCE_FILES_MISSING"


def compute_preview(db: Session, directory: Path | None = None) -> CrawPreview:
    data, blocked_reason = _load_source(directory)
    if data is None:
        return CrawPreview("", {}, {}, [blocked_reason or "CRAW_SOURCE_NOT_CONFIGURED"], False, blocked_reason)

    # Call the service directly on the request's own Session. The CLI's
    # read-only-transaction check is a safety belt appropriate for a script
    # that opens its own throwaway connection with operator-supplied
    # credentials; it is not needed here, since this Session is already
    # scoped to one RBAC-gated request and nothing is written until apply().
    ingestion_preview = KnownPublicationIngestionService().preview(db, data.sources)
    summary = preview_summary(ingestion_preview)
    blocking = blocking_problems(data, ingestion_preview)
    fingerprint = hashlib.sha256(
        canonical_json({"files": data.file_sha256, "stats": data.stats, "preview": summary}).encode("utf-8")
    ).hexdigest()
    return CrawPreview(fingerprint, data.stats, summary, blocking, not blocking, blocking[0] if blocking else None)


def apply_ingestion(
    db: Session,
    *,
    fingerprint: str,
    actor_user_id: uuid.UUID,
    directory: Path | None = None,
) -> dict[str, Any]:
    directory = directory if directory is not None else configured_craw_dir()
    run_id = uuid.uuid4()
    got = db.execute(text("select pg_try_advisory_xact_lock(:k)"), {"k": _LOCK_KEY}).scalar_one()
    if not got:
        db.rollback()
        raise CrawIngestionWorkflowError(
            "CRAW_APPLY_IN_PROGRESS", "Một lượt nạp Craw khác đang chạy.", 409
        )

    result = compute_preview(db, directory)
    if not result.can_apply:
        db.rollback()
        raise CrawIngestionWorkflowError(
            result.blocked_reason or "NOTHING_TO_APPLY",
            "Không có gì để áp dụng hoặc nguồn Craw chưa sẵn sàng.",
            409,
        )
    if result.fingerprint != fingerprint:
        db.rollback()
        raise CrawIngestionWorkflowError(
            "PREVIEW_STALE", "Dữ liệu Craw đã thay đổi kể từ lần xem trước. Hãy xem trước lại.", 409
        )

    data, _ = _load_source(directory)
    assert data is not None  # compute_preview already confirmed can_apply

    try:
        apply_result = KnownPublicationIngestionService().apply(db, data.sources)
    except Exception as exc:
        db.rollback()
        db.add(
            AuditEvent(
                entity_type="craw_ingestion",
                entity_id=run_id,
                action=FAILED_ACTION,
                actor_type="USER",
                actor_user_id=actor_user_id,
                event_metadata={"fingerprint": fingerprint, "error": type(exc).__name__},
            )
        )
        db.commit()
        raise CrawIngestionWorkflowError(
            "CRAW_APPLY_FAILED", "Nạp Craw thất bại; không có dữ liệu nào được ghi.", 500
        ) from exc

    summary = {
        "snapshots_created": apply_result.snapshots_created,
        "snapshots_reused": apply_result.snapshots_reused,
        "known_publications_created": apply_result.known_publications_created,
        "known_publications_reused": apply_result.known_publications_reused,
        "source_duplicates_collapsed": apply_result.source_duplicates_collapsed,
        "source_urls_collapsed": apply_result.source_urls_collapsed,
        "invalid_records": apply_result.invalid_records,
        "unmapped": len(apply_result.unmapped_lecturers),
    }
    # apply() already committed the data write; this audit event is a
    # separate, immediately-following transaction (never both-or-neither
    # with the data), which is acceptable here because the event only
    # records a fact about a write that has already durably happened.
    db.add(
        AuditEvent(
            entity_type="craw_ingestion",
            entity_id=run_id,
            action=APPLIED_ACTION,
            actor_type="USER",
            actor_user_id=actor_user_id,
            event_metadata={"fingerprint": fingerprint, "result": summary},
        )
    )
    db.commit()
    return {"run_id": str(run_id), "fingerprint": fingerprint, "result": summary}


__all__ = [
    "APPLIED_ACTION",
    "CrawIngestionWorkflowError",
    "CrawPreview",
    "FAILED_ACTION",
    "apply_ingestion",
    "compute_preview",
    "configured_craw_dir",
]
