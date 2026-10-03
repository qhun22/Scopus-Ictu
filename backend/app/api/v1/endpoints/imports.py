"""Administrator-only Scopus import lifecycle endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User
from app.schemas.scopus_import import (
    ScopusImportConfigResponse,
    ScopusImportListResponse,
    ScopusImportResponse,
)
from app.services.scopus_import_service import (
    DuplicateImportConfirmationRequired,
    ImportAlreadyFinished,
    ImportAlreadyProcessing,
    ImportStorageError,
    archive_import_history,
    cancel_import,
    create_import_job,
    delete_scopus_import,
    get_import,
    get_import_stats,
    is_import_eligible_for_normalization,
    list_imports,
    normalize_existing_import,
    process_import_job,
    restore_import_history,
    rollback_lecturer_import,
    validate_upload_filename,
)
from app.schemas.scopus_import import NormalizationResponse

router = APIRouter()
AdminUser = Annotated[User, Depends(require_role("ADMIN"))]
DatabaseSession = Annotated[Session, Depends(get_session)]
READ_CHUNK_BYTES = 1024 * 1024


@router.get("/config", response_model=ScopusImportConfigResponse)
def import_config(_admin: AdminUser) -> ScopusImportConfigResponse:
    return ScopusImportConfigResponse(max_bytes=settings.scopus_import_max_bytes)


@router.post(
    "/scopus",
    response_model=ScopusImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a durable raw Scopus CSV import job",
)
async def upload_scopus_import(
    admin: AdminUser,
    db: DatabaseSession,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile | None, File()] = None,
    allow_duplicate: Annotated[bool, Query()] = False,
) -> ScopusImportResponse:
    if file is None:
        raise APIError(
            status_code=422, detail="Vui lòng chọn tệp CSV cần nhập.", code="INVALID_IMPORT_FILE"
        )

    try:
        try:
            filename = validate_upload_filename(file.filename)
        except ValueError as exc:
            code = str(exc)
            if code == "UNSUPPORTED_IMPORT_FORMAT":
                raise APIError(
                    status_code=422,
                    detail="Định dạng tệp không được hỗ trợ. Vui lòng chọn tệp CSV.",
                    code=code,
                ) from exc
            raise APIError(
                status_code=422, detail="Tên tệp tải lên không hợp lệ.", code="INVALID_IMPORT_FILE"
            ) from exc

        content = await _read_bounded(file, settings.scopus_import_max_bytes)
        if not content:
            raise APIError(
                status_code=422, detail="Tệp tải lên không có dữ liệu.", code="EMPTY_IMPORT_FILE"
            )
        try:
            result = create_import_job(
                db,
                filename=filename,
                content=content,
                actor=admin,
                allow_duplicate=allow_duplicate,
            )
        except ImportAlreadyProcessing as exc:
            raise APIError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tệp này đang được xử lý trong một phiên nhập khác.",
                code="IMPORT_ALREADY_PROCESSING",
                data={"existing_import_id": str(exc.existing_import_id)},
            ) from exc
        except DuplicateImportConfirmationRequired as exc:
            raise APIError(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Nội dung tệp này đã được nhập trước đó. "
                    "Hãy xác nhận nếu vẫn muốn nhập lại."
                ),
                code="DUPLICATE_IMPORT_CONFIRMATION_REQUIRED",
                data={
                    "duplicate_of_import_id": str(exc.import_id),
                    "duplicate_imported_at": exc.imported_at.isoformat(),
                    "duplicate_filename": exc.filename,
                },
            ) from exc
        except ImportStorageError as exc:
            raise APIError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Không thể tạo phiên nhập dữ liệu.",
                code="IMPORT_FAILED",
            ) from exc

        background_tasks.add_task(process_import_job, result.id, content, admin.id)
        return result
    finally:
        await file.close()


@router.get("", response_model=ScopusImportListResponse)
@router.get("/history", response_model=ScopusImportListResponse)
def import_history(
    _admin: AdminUser,
    db: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    include_archived: Annotated[bool, Query()] = False,
) -> ScopusImportListResponse:
    try:
        items = list_imports(db, limit=limit, include_archived=include_archived)
        stats = get_import_stats(items)
        return ScopusImportListResponse(items=items, stats=stats)
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tải lịch sử nhập dữ liệu.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


@router.post("/{import_id}/archive", response_model=ScopusImportResponse)
def archive_import_endpoint(
    import_id: uuid.UUID,
    admin: AdminUser,
    db: DatabaseSession,
) -> ScopusImportResponse:
    """Admin-only: hide a Scopus import from the default history list.

    Does NOT delete the ScopusImport, raw rows, or any provenance. Uses
    an append-only AuditEvent so the action is fully reversible.
    """
    try:
        result = archive_import_history(db, import_id, admin)
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể ẩn đợt nhập khỏi lịch sử.",
            code="DATABASE_UNAVAILABLE",
        ) from exc
    if result is None:
        raise APIError(
            status_code=404,
            detail="Không tìm thấy đợt nhập dữ liệu.",
            code="IMPORT_NOT_FOUND",
        )
    return result


@router.post("/{import_id}/restore-history", response_model=ScopusImportResponse)
def restore_import_endpoint(
    import_id: uuid.UUID,
    admin: AdminUser,
    db: DatabaseSession,
) -> ScopusImportResponse:
    """Admin-only: restore a previously hidden Scopus import to history."""
    try:
        result = restore_import_history(db, import_id, admin)
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể khôi phục hiển thị đợt nhập.",
            code="DATABASE_UNAVAILABLE",
        ) from exc
    if result is None:
        raise APIError(
            status_code=404,
            detail="Không tìm thấy đợt nhập dữ liệu.",
            code="IMPORT_NOT_FOUND",
        )
    return result


@router.delete("/{import_id}")
def delete_import_endpoint(
    import_id: uuid.UUID,
    admin: AdminUser,
    db: DatabaseSession,
) -> dict[str, str | bool]:
    """Admin-only safe delete of a terminal Scopus import or Lecturer JSON import."""
    try:
        deleted = delete_scopus_import(db, import_id, admin)
    except APIError:
        raise
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể xóa đợt nhập dữ liệu.",
            code="DATABASE_UNAVAILABLE",
        ) from exc
    if not deleted:
        raise APIError(
            status_code=404,
            detail="Không tìm thấy đợt nhập dữ liệu.",
            code="IMPORT_NOT_FOUND",
        )
    return {"message": "Đã xóa đợt nhập thành công.", "id": str(import_id), "deleted": True}


@router.post("/{import_id}/rollback")
def rollback_import_endpoint(
    import_id: uuid.UUID,
    admin: AdminUser,
    db: DatabaseSession,
) -> dict[str, Any]:
    """Admin-only rollback of a lecturer dataset import."""
    try:
        rolled_back = rollback_lecturer_import(db, import_id, admin)
    except APIError:
        raise
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể hoàn tác đợt nhập dữ liệu.",
            code="DATABASE_UNAVAILABLE",
        ) from exc
    if not rolled_back:
        raise APIError(
            status_code=404,
            detail="Không tìm thấy đợt nhập dữ liệu cần hoàn tác.",
            code="LECTURER_IMPORT_NOT_FOUND",
        )
    return {
        "message": "Đã hoàn tác đợt nhập thành công.",
        "id": str(import_id),
        "rolled_back": True,
    }


@router.post("/{import_id}/cancel", response_model=ScopusImportResponse)
def cancel_import_endpoint(
    import_id: uuid.UUID,
    admin: AdminUser,
    db: DatabaseSession,
) -> ScopusImportResponse:
    try:
        item = cancel_import(db, import_id, admin)
    except ImportAlreadyFinished as exc:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phiên nhập đã kết thúc nên không thể hủy.",
            code="IMPORT_ALREADY_FINISHED",
            data={"status": exc.status},
        ) from exc
    except (SQLAlchemyError, ImportStorageError) as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể hủy phiên nhập dữ liệu.",
            code="DATABASE_UNAVAILABLE",
        ) from exc
    if item is None:
        raise APIError(
            status_code=404, detail="Không tìm thấy phiên nhập dữ liệu.", code="IMPORT_NOT_FOUND"
        )
    return item


@router.get("/{import_id}", response_model=ScopusImportResponse)
def import_detail(
    import_id: uuid.UUID,
    _admin: AdminUser,
    db: DatabaseSession,
) -> ScopusImportResponse:
    try:
        item = get_import(db, import_id)
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tải chi tiết phiên nhập dữ liệu.",
            code="DATABASE_UNAVAILABLE",
        ) from exc
    if item is None:
        raise APIError(
            status_code=404, detail="Không tìm thấy phiên nhập dữ liệu.", code="IMPORT_NOT_FOUND"
        )
    return item


@router.post(
    "/{import_id}/normalize",
    response_model=ScopusImportResponse,
    summary="Normalize raw Scopus records for a completed import (M2.6A)",
)
def normalize_import_endpoint(
    import_id: uuid.UUID,
    admin: AdminUser,
    db: DatabaseSession,
) -> ScopusImportResponse:
    """Admin-only: re-normalize or complete normalization for a STAGED Scopus import.

    Idempotent: running again on an already-normalized import produces
    EXISTING_UNCHANGED counters without creating duplicates.
    """
    try:
        counters = normalize_existing_import(db, import_id, actor=admin)
        item = get_import(db, import_id)
        if item is None:
            raise APIError(
                status_code=404,
                detail="Không tìm thấy phiên nhập dữ liệu.",
                code="IMPORT_NOT_FOUND",
            )
        return item
    except APIError:
        raise
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể chuẩn hóa phiên nhập dữ liệu.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


async def _read_bounded(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await file.read(READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise APIError(
                    status_code=413,
                    detail="Tệp vượt quá dung lượng cho phép.",
                    code="IMPORT_FILE_TOO_LARGE",
                )
            chunks.append(chunk)
    except APIError:
        raise
    except (OSError, RuntimeError) as exc:
        raise APIError(
            status_code=422, detail="Không thể đọc tệp tải lên.", code="INVALID_IMPORT_FILE"
        ) from exc
    return b"".join(chunks)
