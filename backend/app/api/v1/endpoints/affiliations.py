"""ADMIN workflow for author-affiliation reconciliation: overview -> preview -> apply.

The source bundle directory is fixed by server configuration; no request field
names a file or directory.  See ``app.services.affiliation_workflow``.

Preview/apply can target either the fixed offline bundle (default) or the
bundle an online enrichment job already wrote — selected by ``job_id``, never
by a path: the server resolves ``job_id`` to the directory it itself
recorded in ``affiliation_enrichment_jobs.bundle_dir``.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.services import affiliation_enrichment_service as enrichment
from app.services import affiliation_override_service as override_service
from app.services import affiliation_workflow as workflow
from app.services.affiliation_sources import BundleFile, BundleStatus, inspect_bundle

router = APIRouter()
AdminUser = Annotated[User, Depends(require_role("ADMIN"))]
DatabaseSession = Annotated[Session, Depends(get_session)]


class BundleFileRead(BaseModel):
    name: str
    required: bool
    present: bool
    size_bytes: int | None = None
    sha256: str | None = None


class BundleStatusRead(BaseModel):
    configured: bool
    ready: bool
    directory_label: str | None = None
    files: list[BundleFileRead] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)
    openalex_works: int | None = None
    crossref_works: int | None = None
    orcid_records: int | None = None
    orcid_with_scopus_id: int | None = None
    retrieved_from: str | None = None
    retrieved_to: str | None = None
    cross_check_available: bool = False


class OverviewResponse(BaseModel):
    source: BundleStatusRead
    database: dict[str, Any]


class PreviewResponse(BaseModel):
    fingerprint: str
    can_apply: bool
    blocked_reason: str | None
    publications: int
    source: BundleStatusRead
    input: dict[str, Any]
    report: dict[str, Any]
    source_mismatches: int
    resolutions_to_insert: int


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(min_length=64, max_length=64)
    confirm: bool
    job_id: uuid.UUID | None = None


class ApplyResponse(BaseModel):
    run_id: str
    fingerprint: str
    result: dict[str, Any]


class EnrichmentJobRead(BaseModel):
    id: uuid.UUID
    status: str
    total_dois: int
    processed_dois: int
    openalex_found: int
    crossref_found: int
    orcid_fetched: int
    bundle_dir: str | None
    error_summary: dict[str, Any] | None
    created_at: str
    updated_at: str


def _job_read(job: enrichment.AffiliationEnrichmentJob) -> EnrichmentJobRead:
    return EnrichmentJobRead(
        id=job.id,
        status=job.status,
        total_dois=job.total_dois,
        processed_dois=job.processed_dois,
        openalex_found=job.openalex_found,
        crossref_found=job.crossref_found,
        orcid_fetched=job.orcid_fetched,
        bundle_dir=job.bundle_dir,
        error_summary=job.error_summary,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
    )


def _resolve_directory(db: Session, job_id: uuid.UUID | None) -> Path | None:
    """``None`` -> the fixed offline bundle. A job id -> that job's own bundle,
    never a client-supplied path."""

    if job_id is None:
        return workflow.configured_bundle_dir()
    job = enrichment.get_job(db, job_id)
    if job is None or job.status != "COMPLETED" or not job.bundle_dir:
        raise APIError(
            status_code=404,
            detail="Không tìm thấy kết quả thu thập trực tuyến đã hoàn tất cho mã này.",
            code="ENRICHMENT_JOB_NOT_READY",
        )
    return Path(job.bundle_dir)


def _file(item: BundleFile) -> BundleFileRead:
    return BundleFileRead(name=item.name, required=item.required, present=item.present,
                          size_bytes=item.size_bytes, sha256=item.sha256)


def _bundle(status: BundleStatus, directory: Path | None = None) -> BundleStatusRead:
    directory = directory if directory is not None else workflow.configured_bundle_dir()
    return BundleStatusRead(
        configured=status.configured,
        ready=status.ready,
        directory_label=directory.name if directory else None,
        files=[_file(f) for f in status.files],
        problems=list(status.problems),
        openalex_works=status.openalex_works,
        crossref_works=status.crossref_works,
        orcid_records=status.orcid_records,
        orcid_with_scopus_id=status.orcid_with_scopus_id,
        retrieved_from=status.retrieved_from,
        retrieved_to=status.retrieved_to,
        cross_check_available=status.cross_check_available,
    )




def _db_error(exc: SQLAlchemyError) -> APIError:
    return APIError(status_code=503, detail="Không thể truy vấn dữ liệu đơn vị tác giả.", code="DATABASE_UNAVAILABLE")


@router.get("/overview", response_model=OverviewResponse, summary="Source bundle status and stored affiliation counts")
def overview(_admin: AdminUser, db: DatabaseSession) -> OverviewResponse:
    try:
        return OverviewResponse(
            source=_bundle(inspect_bundle(workflow.configured_bundle_dir())),
            database=workflow.database_summary(db),
        )
    except SQLAlchemyError as exc:
        raise _db_error(exc) from exc


@router.post("/preview", response_model=PreviewResponse, summary="Read-only preview of what would be written")
def preview(
    _admin: AdminUser, db: DatabaseSession, job_id: uuid.UUID | None = None
) -> PreviewResponse:
    directory = _resolve_directory(db, job_id)
    try:
        result = workflow.preview(db, directory)
    except SQLAlchemyError as exc:
        raise _db_error(exc) from exc
    return PreviewResponse(
        fingerprint=result.fingerprint,
        can_apply=result.can_apply,
        blocked_reason=result.blocked_reason,
        publications=result.publications,
        source=_bundle(result.bundle, directory),
        input=result.stats,
        report=result.report,
        source_mismatches=result.source_mismatches,
        resolutions_to_insert=result.to_insert,
    )


@router.post("/apply", response_model=ApplyResponse, summary="Apply a previously previewed reconciliation")
def apply(body: ApplyRequest, admin: AdminUser, db: DatabaseSession) -> ApplyResponse:
    if not body.confirm:
        raise APIError(status_code=422, detail="Cần xác nhận rõ ràng trước khi áp dụng.", code="CONFIRMATION_REQUIRED")
    directory = _resolve_directory(db, body.job_id)
    try:
        outcome = workflow.apply(db, fingerprint=body.fingerprint, actor_user_id=admin.id, directory=directory)
    except workflow.AffiliationWorkflowError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error(exc) from exc
    return ApplyResponse(**outcome)


@router.post(
    "/enrichment/online",
    response_model=EnrichmentJobRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="ADMIN-triggered background job: fetch OpenAlex/Crossref/ORCID for all stored publication DOIs",
)
def start_online_enrichment(
    admin: AdminUser, db: DatabaseSession, background_tasks: BackgroundTasks
) -> EnrichmentJobRead:
    try:
        job = enrichment.start_job(db, admin)
    except enrichment.AffiliationEnrichmentError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error(exc) from exc
    background_tasks.add_task(enrichment.process_enrichment_job, job.id)
    return _job_read(job)


@router.get(
    "/enrichment/online/{job_id}",
    response_model=EnrichmentJobRead,
    summary="Poll the status/progress of an online enrichment job",
)
def get_online_enrichment(job_id: uuid.UUID, _admin: AdminUser, db: DatabaseSession) -> EnrichmentJobRead:
    job = enrichment.get_job(db, job_id)
    if job is None:
        raise APIError(status_code=404, detail="Không tìm thấy lượt thu thập này.", code="ENRICHMENT_JOB_NOT_FOUND")
    return _job_read(job)


@router.post(
    "/enrichment/online/{job_id}/cancel",
    response_model=EnrichmentJobRead,
    summary="Cooperatively cancel a running online enrichment job",
)
def cancel_online_enrichment(job_id: uuid.UUID, admin: AdminUser, db: DatabaseSession) -> EnrichmentJobRead:
    try:
        job = enrichment.cancel_job(db, job_id, admin)
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error(exc) from exc
    if job is None:
        raise APIError(status_code=404, detail="Không tìm thấy lượt thu thập này.", code="ENRICHMENT_JOB_NOT_FOUND")
    return _job_read(job)


# --------------------------------------------------------------------------- manual review (Priority 2 / NO-JSON closure)
class NeedsReviewItemRead(BaseModel):
    publication_author_id: uuid.UUID
    eid: str
    title: str
    author_order: int
    scopus_id: str
    preferred_name: str
    reason_kind: str
    resolution_summaries: list[dict[str, Any]]
    has_override: bool
    # ALL overrides for this position — active and revoked, newest first.
    overrides: list["OverrideRead"] = Field(default_factory=list)


class NeedsReviewListResponse(BaseModel):
    items: list[NeedsReviewItemRead]
    total: int


class OverrideRead(BaseModel):
    id: uuid.UUID
    publication_author_id: uuid.UUID
    affiliation_text: str
    confidence: str
    status: str
    evidence_url: str
    reason: str
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    revoked_by_user_id: uuid.UUID | None
    revoked_at: str | None
    version: int
    created_at: str
    updated_at: str


class AddOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_author_id: uuid.UUID
    affiliation_text: str = Field(min_length=1, max_length=2000)
    confidence: str
    evidence_url: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)


class UpdateOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affiliation_text: str = Field(min_length=1, max_length=2000)
    confidence: str
    evidence_url: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)
    expected_version: int


class RevokeOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2000)
    expected_version: int


def _override_read(row: override_service.PublicationAuthorAffiliationOverride) -> OverrideRead:
    return OverrideRead(
        id=row.id,
        publication_author_id=row.publication_author_id,
        affiliation_text=row.affiliation_text,
        confidence=row.confidence,
        status=row.status,
        evidence_url=row.evidence_url,
        reason=row.reason,
        created_by_user_id=row.created_by_user_id,
        updated_by_user_id=row.updated_by_user_id,
        revoked_by_user_id=row.revoked_by_user_id,
        revoked_at=row.revoked_at.isoformat() if row.revoked_at else None,
        version=row.version,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


@router.get(
    "/needs-review",
    response_model=NeedsReviewListResponse,
    summary="Author positions that are UNRESOLVED, conflicting, or only CORROBORATED",
)
def needs_review(
    _admin: AdminUser, db: DatabaseSession, limit: Annotated[int, Field(ge=1, le=500)] = 100, offset: int = 0
) -> NeedsReviewListResponse:
    try:
        items, total = override_service.list_needs_review(db, limit=limit, offset=offset)
    except SQLAlchemyError as exc:
        raise _db_error(exc) from exc
    return NeedsReviewListResponse(
        items=[
            NeedsReviewItemRead(
                publication_author_id=i.publication_author_id,
                eid=i.eid,
                title=i.title,
                author_order=i.author_order,
                scopus_id=i.scopus_id,
                preferred_name=i.preferred_name,
                reason_kind=i.reason_kind,
                resolution_summaries=i.resolution_summaries,
                has_override=i.has_override,
                overrides=[_override_read(o) for o in i.overrides],
            )
            for i in items
        ],
        total=total,
    )


@router.post(
    "/overrides",
    response_model=OverrideRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new active unit statement for one author position (does not touch other overrides on it)",
)
def add_override(body: AddOverrideRequest, admin: AdminUser, db: DatabaseSession) -> OverrideRead:
    try:
        row = override_service.add_override(
            db,
            override_service.AddOverrideCommand(
                publication_author_id=body.publication_author_id,
                affiliation_text=body.affiliation_text,
                confidence=body.confidence,
                evidence_url=body.evidence_url,
                reason=body.reason,
                actor_user_id=admin.id,
            ),
        )
    except override_service.AffiliationOverrideError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error(exc) from exc
    return _override_read(row)


@router.put(
    "/overrides/{override_id}",
    response_model=OverrideRead,
    summary="Edit exactly one override by its own id (other overrides on the same position are unaffected)",
)
def put_override(override_id: uuid.UUID, body: UpdateOverrideRequest, admin: AdminUser, db: DatabaseSession) -> OverrideRead:
    try:
        row = override_service.update_override(
            db,
            override_service.UpdateOverrideCommand(
                override_id=override_id,
                affiliation_text=body.affiliation_text,
                confidence=body.confidence,
                evidence_url=body.evidence_url,
                reason=body.reason,
                actor_user_id=admin.id,
                expected_version=body.expected_version,
            ),
        )
    except override_service.AffiliationOverrideError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error(exc) from exc
    return _override_read(row)


@router.post(
    "/overrides/{override_id}/revoke",
    response_model=OverrideRead,
    summary="Revoke one override (kept, not deleted, for audit) without affecting other overrides on the position",
)
def revoke_override_endpoint(
    override_id: uuid.UUID, body: RevokeOverrideRequest, admin: AdminUser, db: DatabaseSession
) -> OverrideRead:
    try:
        row = override_service.revoke_override(
            db,
            override_id=override_id,
            expected_version=body.expected_version,
            reason=body.reason,
            actor_user_id=admin.id,
        )
    except override_service.AffiliationOverrideError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error(exc) from exc
    return _override_read(row)
