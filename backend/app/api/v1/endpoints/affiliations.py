"""ADMIN workflow for author-affiliation reconciliation: overview -> preview -> apply.

The source bundle directory is fixed by server configuration; no request field
names a file or directory.  See ``app.services.affiliation_workflow``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
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


class ApplyResponse(BaseModel):
    run_id: str
    fingerprint: str
    result: dict[str, Any]


def _file(item: BundleFile) -> BundleFileRead:
    return BundleFileRead(name=item.name, required=item.required, present=item.present,
                          size_bytes=item.size_bytes, sha256=item.sha256)


def _bundle(status: BundleStatus) -> BundleStatusRead:
    directory = workflow.configured_bundle_dir()
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
def preview(_admin: AdminUser, db: DatabaseSession) -> PreviewResponse:
    try:
        result = workflow.preview(db)
    except SQLAlchemyError as exc:
        raise _db_error(exc) from exc
    return PreviewResponse(
        fingerprint=result.fingerprint,
        can_apply=result.can_apply,
        blocked_reason=result.blocked_reason,
        publications=result.publications,
        source=_bundle(result.bundle),
        input=result.stats,
        report=result.report,
        source_mismatches=result.source_mismatches,
        resolutions_to_insert=result.to_insert,
    )


@router.post("/apply", response_model=ApplyResponse, summary="Apply a previously previewed reconciliation")
def apply(body: ApplyRequest, admin: AdminUser, db: DatabaseSession) -> ApplyResponse:
    if not body.confirm:
        raise APIError(status_code=422, detail="Cần xác nhận rõ ràng trước khi áp dụng.", code="CONFIRMATION_REQUIRED")
    try:
        outcome = workflow.apply(db, fingerprint=body.fingerprint, actor_user_id=admin.id)
    except workflow.AffiliationWorkflowError as exc:
        raise APIError(status_code=exc.status_code, detail=exc.message, code=exc.code) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _db_error(exc) from exc
    return ApplyResponse(**outcome)
