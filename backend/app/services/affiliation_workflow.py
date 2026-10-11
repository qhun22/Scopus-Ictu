"""ADMIN workflow for author-affiliation reconciliation (view source -> preview -> apply).

The workflow is a thin, auditable layer over existing pieces:

* the source bundle and its recomputation        -> ``affiliation_sources``
* the idempotent, fail-closed database writer      -> ``AffiliationImportService``

It never reads a path supplied by a request: the bundle directory comes from
the server setting ``AFFILIATION_SOURCE_DIR``.  Scopus author slots are rebuilt
from the raw CSV rows already stored by the Scopus import, so the workflow
needs neither the CSV file on disk nor any lecturer data.

``preview`` is read-only.  ``apply`` re-runs the preview inside its own
transaction, refuses when the result no longer equals the fingerprint the ADMIN
confirmed, serialises concurrent runs with a transaction-level advisory lock
and writes one audit event atomically with the data.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.affiliation import (
    Organization,
    PublicationAuthorAffiliation,
    PublicationAuthorAffiliationResolution,
)
from app.models.governance import AuditEvent
from app.models.publication import Publication, PublicationAuthor, PublicationRawSource
from app.models.scopus_raw import RawScopusRecord
from app.services.affiliation_import import AffiliationImportService
from app.services.affiliation_sources import (
    BuiltInput,
    BundleStatus,
    build_inputs,
    inspect_bundle,
)
from app.services.matching.candidate_persistence import canonical_json

APPLIED_ACTION = "AFFILIATION_IMPORT_APPLIED"
FAILED_ACTION = "AFFILIATION_IMPORT_FAILED"
_LOCK_KEY = 0x41464631  # "AFF1"
NEEDED_COLUMNS = ("EID", "DOI", "Author(s) ID", "Author full names")


class AffiliationWorkflowError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


def configured_bundle_dir() -> Path | None:
    raw = getattr(settings, "affiliation_source_dir", None)
    return Path(raw) if raw else None


@dataclass(slots=True)
class Preview:
    fingerprint: str
    bundle: BundleStatus
    stats: dict[str, Any]
    report: dict[str, Any]
    source_mismatches: int
    publications: int
    to_insert: int
    can_apply: bool
    blocked_reason: str | None


def load_scopus_rows(db: Session) -> list[dict[str, str]]:
    """One row per publication: the stored raw CSV cells the alignment needs."""

    rows = db.execute(
        select(Publication.eid, RawScopusRecord.raw_payload, RawScopusRecord.created_at)
        .join(PublicationRawSource, PublicationRawSource.publication_id == Publication.id)
        .join(RawScopusRecord, RawScopusRecord.id == PublicationRawSource.raw_record_id)
        .order_by(Publication.eid.asc(), RawScopusRecord.created_at.desc(), RawScopusRecord.id.desc())
    ).all()
    out: dict[str, dict[str, str]] = {}
    for eid, payload, _created in rows:
        if eid in out:
            continue  # newest raw row per publication wins
        payload = payload or {}
        out[eid] = {
            "EID": eid,
            **{c: str(payload.get(c) or "") for c in NEEDED_COLUMNS if c != "EID"},
        }
    return list(out.values())


def _rows_digest(rows: list[dict[str, str]]) -> str:
    return hashlib.sha256(canonical_json(sorted(rows, key=lambda r: r["EID"])).encode("utf-8")).hexdigest()


def _compute(
    db: Session, directory: Path | None, *, keep_transaction: bool = False
) -> tuple[Preview, BuiltInput | None]:
    """Build the preview.  ``keep_transaction`` leaves the transaction (and its advisory lock) open."""

    bundle = inspect_bundle(directory)
    rows = load_scopus_rows(db)
    base = dict(bundle=bundle, publications=len(rows))
    if not bundle.ready or not rows:
        reason = "NO_PUBLICATIONS" if bundle.ready else (bundle.problems[0] if bundle.problems else "BUNDLE_NOT_READY")
        return Preview("", stats={}, report={}, source_mismatches=0, to_insert=0, can_apply=False,
                       blocked_reason=reason, **base), None
    built = build_inputs(directory, rows, require_expected=False)  # type: ignore[arg-type]
    report_dict = AffiliationImportService().preview(db, built.inputs).as_dict()
    if not keep_transaction:
        db.rollback()  # preview is read-only; end the read transaction
    fingerprint = hashlib.sha256(
        canonical_json(
            {"bundle": built.file_sha256, "rows": _rows_digest(rows), "stats": built.stats,
             "report": report_dict, "mismatches": len(built.mismatches)}
        ).encode("utf-8")
    ).hexdigest()
    to_insert = int(report_dict["resolutions_to_insert"])
    blocked = "SOURCE_MISMATCH" if built.mismatches else ("NOTHING_TO_APPLY" if to_insert == 0 else None)
    return (
        Preview(fingerprint, stats=built.stats, report=report_dict, source_mismatches=len(built.mismatches),
                to_insert=to_insert, can_apply=blocked is None, blocked_reason=blocked, **base),
        built,
    )


def preview(db: Session, directory: Path | None = None) -> Preview:
    return _compute(db, directory if directory is not None else configured_bundle_dir())[0]


def apply(
    db: Session,
    *,
    fingerprint: str,
    actor_user_id: uuid.UUID,
    directory: Path | None = None,
) -> dict[str, Any]:
    directory = directory if directory is not None else configured_bundle_dir()
    run_id = uuid.uuid4()
    got = db.execute(text("select pg_try_advisory_xact_lock(:k)"), {"k": _LOCK_KEY}).scalar_one()
    if not got:
        db.rollback()
        raise AffiliationWorkflowError(
            "AFFILIATION_APPLY_IN_PROGRESS", "Một lượt áp dụng đơn vị khác đang chạy.", 409
        )
    try:
        result, built = _compute(db, directory, keep_transaction=True)
        if not result.can_apply or built is None:
            db.rollback()
            raise AffiliationWorkflowError(
                result.blocked_reason or "NOTHING_TO_APPLY", "Không có gì để áp dụng hoặc nguồn chưa sẵn sàng.", 409
            )
        if result.fingerprint != fingerprint:
            db.rollback()
            raise AffiliationWorkflowError(
                "PREVIEW_STALE", "Dữ liệu hoặc nguồn đã thay đổi kể từ lần xem trước. Hãy xem trước lại.", 409
            )
        db.add(
            AuditEvent(
                entity_type="affiliation_import",
                entity_id=run_id,
                action=APPLIED_ACTION,
                actor_type="USER",
                actor_user_id=actor_user_id,
                event_metadata={
                    "fingerprint": result.fingerprint,
                    "bundle_sha256": built.file_sha256,
                    "input": built.stats,
                    "result": result.report,
                },
            )
        )
        applied = AffiliationImportService().apply(db, built.inputs)  # commits data + audit atomically
    except AffiliationWorkflowError:
        raise
    except Exception as exc:
        db.rollback()
        db.add(
            AuditEvent(
                entity_type="affiliation_import",
                entity_id=run_id,
                action=FAILED_ACTION,
                actor_type="USER",
                actor_user_id=actor_user_id,
                event_metadata={"fingerprint": fingerprint, "error": type(exc).__name__},
            )
        )
        db.commit()
        raise AffiliationWorkflowError(
            "AFFILIATION_APPLY_FAILED", "Áp dụng đơn vị thất bại; không có dữ liệu nào được ghi.", 500
        ) from exc
    return {"run_id": str(run_id), "fingerprint": fingerprint, "result": applied.as_dict()}


def database_summary(db: Session) -> dict[str, Any]:
    by_status = {
        f"{src}/{status}": int(n)
        for src, status, n in db.execute(
            select(
                PublicationAuthorAffiliationResolution.source_system,
                PublicationAuthorAffiliationResolution.link_status,
                func.count(),
            ).group_by(
                PublicationAuthorAffiliationResolution.source_system,
                PublicationAuthorAffiliationResolution.link_status,
            )
        ).all()
    }
    last = db.execute(
        select(AuditEvent.action, AuditEvent.created_at, AuditEvent.event_metadata)
        .where(AuditEvent.action.in_((APPLIED_ACTION, FAILED_ACTION)))
        .order_by(AuditEvent.created_at.desc())
        .limit(1)
    ).first()
    return {
        "publications": int(db.scalar(select(func.count()).select_from(Publication)) or 0),
        "author_positions": int(db.scalar(select(func.count()).select_from(PublicationAuthor)) or 0),
        "organizations": int(db.scalar(select(func.count()).select_from(Organization)) or 0),
        "resolutions_by_source_and_status": by_status,
        "affiliation_entries": int(db.scalar(select(func.count()).select_from(PublicationAuthorAffiliation)) or 0),
        "last_run": None
        if last is None
        else {"action": last[0], "at": last[1].isoformat(), "fingerprint": (last[2] or {}).get("fingerprint")},
    }


__all__ = [
    "APPLIED_ACTION",
    "AffiliationWorkflowError",
    "FAILED_ACTION",
    "Preview",
    "apply",
    "configured_bundle_dir",
    "database_summary",
    "load_scopus_rows",
    "preview",
]
