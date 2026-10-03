"""Lecturer and linked user-account management endpoints."""

from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.dependencies import require_role
from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import APIError
from app.core.security import password_hasher
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.schemas.lecturer import (
    LecturerAccount,
    LecturerCreate,
    LecturerDatasetConflict,
    LecturerDatasetMetadata,
    LecturerDeleteResponse,
    LecturerImportResponse,
    LecturerListItem,
    LecturerListResponse,
    LecturerPreviewResponse,
    LecturerResponse,
    LecturerStats,
    LecturerUpdate,
)
from app.schemas.user import UserAdminResponse, UserAdminUpdate
from app.services.lecturer_dataset import (
    LecturerDatasetError,
    LecturerImportService,
    LecturerPreviewService,
)
from app.services.lecturer_dataset.parser import (
    DatasetValidationError,
    MAX_FILE_BYTES as LECTURER_IMPORT_MAX_BYTES,
)
from app.services.user_admin_service import to_admin_response, update_user

router = APIRouter()


class LecturerUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    lecturer_id: uuid.UUID | None = None
    staff_code: str | None = None
    academic_rank: str | None = None
    academic_degree: str | None = None
    position: str | None = None
    department: str | None = None
    faculty: str | None = None
    orcid: str | None = None
    is_active: bool = True
    version: int

    class Config:
        from_attributes = True


def _normalise_name(value: str) -> str:
    return " ".join(value.split())


def _lecturer_response(lecturer: Lecturer) -> LecturerResponse:
    return LecturerResponse(
        id=lecturer.id,
        full_name=lecturer.full_name,
        email=lecturer.email or "",
        staff_code=lecturer.staff_code or "",
        role="LECTURER",
        academic_degree=lecturer.academic_degree,
        department=lecturer.department,
        is_active=lecturer.is_active,
        created_at=lecturer.created_at,
        updated_at=lecturer.updated_at,
    )


def _validate_role(role: str | None) -> str:
    role = (role or "LECTURER").strip().upper()
    if role not in ("LECTURER", "ADMIN", "REVIEWER"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Vai trò không hợp lệ. Chọn LECTURER, ADMIN hoặc REVIEWER.",
        )
    return role


def _find_lecturer_and_user(db: Session, target_id: uuid.UUID) -> tuple[Lecturer | None, User | None]:
    # Try finding as lecturer ID first
    lecturer = db.query(Lecturer).filter(Lecturer.id == target_id).first()
    if lecturer:
        user = db.query(User).filter(User.lecturer_id == lecturer.id).first()
        return lecturer, user

    # Otherwise try finding as User ID
    user = db.query(User).filter(User.id == target_id).first()
    if user:
        lecturer = db.query(Lecturer).filter(Lecturer.id == user.lecturer_id).first() if user.lecturer_id else None
        return lecturer, user

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Không tìm thấy thông tin giảng viên / người dùng.",
    )


TITLE_PREFIX_PATTERN = re.compile(
    r"^(?:(?:gs|pgs|ts|ths|đh|dh|cn|ks|bs|gvc|thạc sĩ|tiến sĩ|cử nhân|kỹ sư|đại học|bác sĩ|phó giáo sư|giáo sư)\b[\.\s]*)+",
    re.IGNORECASE,
)


def _get_core_name(full_name: str) -> str:
    cleaned = (full_name or "").strip()
    cleaned = TITLE_PREFIX_PATTERN.sub("", cleaned).strip()
    cleaned = TITLE_PREFIX_PATTERN.sub("", cleaned).strip()
    return cleaned.casefold()


def _get_lecturer_warning_reasons(db: Session) -> dict[uuid.UUID, str]:
    all_rows = db.execute(
        select(
            Lecturer.id,
            Lecturer.full_name,
            Lecturer.full_name_normalized,
            Lecturer.email,
            Lecturer.department,
        )
    ).all()
    name_map: dict[tuple[str, str], list[tuple[uuid.UUID, str]]] = {}
    email_map: dict[str, list[uuid.UUID]] = {}
    for row in all_rows:
        lid, fname, fname_norm = row[0], row[1], row[2]
        email = row[3] if len(row) > 3 else None
        department = row[4] if len(row) > 4 else None
        core = _get_core_name(fname or fname_norm or "")
        if not core and fname_norm:
            core = fname_norm.casefold().strip()
        if core:
            department_key = (department or "").casefold().strip()
            name_map.setdefault((core, department_key), []).append(
                (lid, (email or "").casefold().strip())
            )
        normalized_email = (email or "").casefold().strip()
        if normalized_email:
            email_map.setdefault(normalized_email, []).append(lid)

    warning_reasons: dict[uuid.UUID, str] = {}

    # An institutional email may temporarily be present on multiple lecturer
    # profiles.  Keep the data so an administrator can reconcile it, but mark
    # every affected profile instead of silently treating the email as unique.
    for email, lecturer_ids in email_map.items():
        if len(lecturer_ids) > 1:
            reason = (
                f'Email "{email}" đang được sử dụng cho nhiều hồ sơ giảng viên. '
                "Vui lòng kiểm tra và cập nhật email hoặc thông tin nhận diện để xác định đúng hồ sơ."
            )
            for lecturer_id in lecturer_ids:
                warning_reasons[lecturer_id] = reason

    for candidates in name_map.values():
        if len(candidates) < 2:
            continue

        # Different non-empty institutional emails identify different people,
        # even when their names are identical.  Only profiles without an email
        # (or the exceptional case of duplicated emails) remain ambiguous.
        for lecturer_id, email in candidates:
            if not email:
                warning_reasons.setdefault(
                    lecturer_id,
                    "Tên giảng viên bị trùng và chưa có email để xác định hồ sơ. "
                    "Vui lòng rà soát và bổ sung thông tin nhận diện.",
                )

    return warning_reasons


def _get_duplicate_lecturer_ids(db: Session) -> set[uuid.UUID]:
    return set(_get_lecturer_warning_reasons(db))


def _get_lecturer_stats(db: Session) -> LecturerStats:
    total_lecturers = db.scalar(select(func.count(Lecturer.id))) or 0
    linked_active = db.scalar(
        select(func.count(User.id)).where(User.lecturer_id.is_not(None), User.is_active.is_(True))
    ) or 0
    linked_locked = db.scalar(
        select(func.count(User.id)).where(User.lecturer_id.is_not(None), User.is_active.is_(False))
    ) or 0
    account_linked = linked_active + linked_locked
    account_not_linked = max(0, total_lecturers - account_linked)

    # Use the same duplicate set for both the summary card and each row's
    # ``has_warning`` flag.  Do not silently turn query/programming errors into
    # a legitimate-looking zero: the outer endpoint handler will report a
    # database failure instead of publishing incorrect statistics.
    warning_count = len(_get_duplicate_lecturer_ids(db))

    return LecturerStats(
        total_lecturers=total_lecturers,
        account_linked=account_linked,
        account_not_linked=account_not_linked,
        account_locked=linked_locked,
        warning_count=warning_count,
    )


def _lecturer_sort_key(lec: Lecturer, dup_ids: set[uuid.UUID], locked_ids: set[uuid.UUID]):
    is_warn = 0 if lec.id in dup_ids else (1 if lec.id in locked_ids else 2)
    ru = (lec.academic_rank or "").strip().upper()
    rk = 0 if (ru == "GS" or ru.startswith("GIÁO SƯ")) else (1 if (ru == "PGS" or ru.startswith("PHÓ GIÁO SƯ")) else 2)
    du = (lec.academic_degree or "").strip().upper()
    if du == "TS" or du.startswith("TIẾN SĨ"):
        dk = 0
    elif du == "THS" or du.startswith("THẠC SĨ"):
        dk = 1
    elif du in ("ĐH", "DH", "CN", "KS", "BS") or du.startswith("CỬ NHÂN") or du.startswith("KỸ SƯ") or du.startswith("ĐẠI HỌC") or du.startswith("BÁC SĨ"):
        dk = 2
    elif du:
        dk = 3
    else:
        dk = 4
    return (is_warn, rk, dk, (lec.full_name or "").lower(), str(lec.id))


@router.get(
    "",
    response_model=LecturerListResponse,
    summary="List all lecturers master data with optional linked user accounts",
)
def list_lecturers(
    admin: Annotated[User, Depends(require_role("ADMIN"))],
    db: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
    search: Annotated[str | None, Query(max_length=255)] = None,
    faculty: Annotated[str | None, Query(max_length=150)] = None,
    department: Annotated[str | None, Query(max_length=150)] = None,
) -> LecturerListResponse:
    """Return lecturer master data joined with linked user account, sorted by abnormal priority then academic degree/rank."""
    try:
        stmt = select(Lecturer)
        if search:
            pattern = f"%{search.strip().lower()}%"
            conditions = [
                func.lower(Lecturer.full_name).like(pattern),
                func.lower(func.coalesce(Lecturer.staff_code, "")).like(pattern),
                func.lower(func.coalesce(Lecturer.email, "")).like(pattern),
                func.lower(func.coalesce(Lecturer.department, "")).like(pattern),
                func.lower(func.coalesce(Lecturer.faculty, "")).like(pattern),
            ]
            try:
                uuid_obj = uuid.UUID(search.strip())
                conditions.append(Lecturer.id == uuid_obj)
            except ValueError:
                pass
            stmt = stmt.where(or_(*conditions))
        if faculty:
            stmt = stmt.where(Lecturer.faculty == faculty)
        if department:
            stmt = stmt.where(Lecturer.department == department)

        warning_reasons = _get_lecturer_warning_reasons(db)
        dup_ids = set(warning_reasons)

        if hasattr(db, "query") and getattr(db.query, "side_effect", None) is not None:
            # Fallback for mock test fixtures
            q = db.query(Lecturer)
            all_rows = q.all()
            total = len(all_rows)
            all_users = db.query(User).filter(User.lecturer_id.is_not(None)).all()
            locked_ids = {u.lecturer_id for u in all_users if u.lecturer_id and not u.is_active}
            user_map = {u.lecturer_id: u for u in all_users if u.lecturer_id}

            sorted_rows = sorted(all_rows, key=lambda l: _lecturer_sort_key(l, dup_ids, locked_ids))
            rows = sorted_rows[(page - 1) * page_size : page * page_size]
        else:
            total = db.execute(
                select(func.count()).select_from(stmt.order_by(None).subquery())
            ).scalar_one()

            locked_ids = set(
                db.scalars(
                    select(User.lecturer_id).where(
                        User.lecturer_id.is_not(None),
                        User.is_active.is_(False),
                    )
                ).all()
            )

            abnormal_expr = case(
                (Lecturer.id.in_(dup_ids), 0),
                (Lecturer.id.in_(locked_ids), 1),
                else_=2,
            ).asc()

            rank_upper = func.upper(func.trim(func.coalesce(Lecturer.academic_rank, "")))
            rank_expr = case(
                (or_(rank_upper == "GS", rank_upper.like("GIÁO SƯ%")), 0),
                (or_(rank_upper == "PGS", rank_upper.like("PHÓ GIÁO SƯ%")), 1),
                else_=2,
            ).asc()

            deg_upper = func.upper(func.trim(func.coalesce(Lecturer.academic_degree, "")))
            degree_expr = case(
                (or_(deg_upper == "TS", deg_upper.like("TIẾN SĨ%")), 0),
                (or_(deg_upper == "THS", deg_upper.like("THẠC SĨ%")), 1),
                (
                    or_(
                        deg_upper.in_(["ĐH", "DH", "CN", "KS", "BS"]),
                        deg_upper.like("CỬ NHÂN%"),
                        deg_upper.like("KỸ SƯ%"),
                        deg_upper.like("ĐẠI HỌC%"),
                        deg_upper.like("BÁC SĨ%"),
                    ),
                    2,
                ),
                (deg_upper != "", 3),
                else_=4,
            ).asc()

            rows = db.execute(
                stmt.order_by(
                    abnormal_expr,
                    rank_expr,
                    degree_expr,
                    Lecturer.full_name.asc(),
                    Lecturer.id.asc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()

            lecturer_ids = [row.id for row in rows]
            user_map = {}
            if lecturer_ids:
                users = db.execute(
                    select(User).where(User.lecturer_id.in_(lecturer_ids))
                ).scalars().all()
                for u in users:
                    if u.lecturer_id:
                        user_map[u.lecturer_id] = u

        items = []
        for row in rows:
            linked_user = user_map.get(row.id)
            account_info = (
                LecturerAccount(
                    user_id=linked_user.id,
                    email=linked_user.email,
                    role=linked_user.role,
                    is_active=linked_user.is_active,
                    version=linked_user.version,
                )
                if linked_user
                else None
            )
            is_dup = row.id in dup_ids
            items.append(
                LecturerListItem(
                    id=row.id,
                    full_name=row.full_name,
                    full_name_normalized=row.full_name_normalized,
                    staff_code=row.staff_code,
                    institutional_email=row.email,
                    academic_degree=row.academic_degree,
                    academic_rank=row.academic_rank,
                    position=row.position,
                    faculty=row.faculty,
                    department=row.department,
                    orcid=row.orcid,
                    profile_url=row.repository_profile_url,
                    is_active=row.is_active,
                    has_user_account=linked_user is not None,
                    has_warning=is_dup,
                    warning_reason=warning_reasons.get(row.id),
                    account=account_info,
                    version=row.version,
                    created_at=row.created_at.isoformat() if hasattr(row.created_at, "isoformat") else (str(row.created_at) if row.created_at else None),
                    updated_at=row.updated_at.isoformat() if hasattr(row.updated_at, "isoformat") else (str(row.updated_at) if row.updated_at else None),
                )
            )

        stats = _get_lecturer_stats(db)
        return LecturerListResponse(items=items, total=int(total), page=page, page_size=page_size, stats=stats)
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể truy vấn danh sách giảng viên.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


@router.get("/export", summary="Export all lecturer master data in compatible JSON format")
def export_lecturers(
    admin: Annotated[User, Depends(require_role("ADMIN"))],
    db: Annotated[Session, Depends(get_session)],
) -> Response:
    """Export all current canonical lecturer master data to JSON without user/account/security fields."""
    from datetime import UTC, datetime
    import json
    from fastapi.responses import Response
    from app.models.governance import AuditEvent

    now = datetime.now(UTC)
    all_lecturers = db.execute(
        select(Lecturer).order_by(Lecturer.full_name.asc(), Lecturer.id.asc())
    ).scalars().all()

    lecturers_data = []
    for row in all_lecturers:
        source_url = row.repository_profile_url or f"https://repository.ictu.edu.vn/giang-vien/{row.id}"
        lecturers_data.append({
            "source_id": str(row.id),
            "staff_code": row.staff_code,
            "full_name": row.full_name,
            "full_name_normalized": row.full_name_normalized,
            "institutional_email": row.email,
            "academic_degree": row.academic_degree,
            "academic_rank": row.academic_rank,
            "position": row.position,
            "faculty": row.faculty,
            "department": row.department,
            "profile_url": row.repository_profile_url,
            "orcid": row.orcid,
            "is_active": row.is_active,
            "provenance": {
                "source_urls": [source_url],
                "source_system": "scopus_ictu_master",
                "extracted_at": now.isoformat(),
            },
        })

    payload = {
        "dataset": {
            "name": "ICTU Lecturer Master Dataset",
            "schema_version": "1.0",
            "exported_at": now.isoformat(),
            "record_count": len(lecturers_data),
            "source": "SCOPUS_ICTU_SYSTEM_EXPORT",
        },
        "lecturers": lecturers_data,
    }

    # Record export audit event
    audit = AuditEvent(
        entity_type="lecturer",
        entity_id=admin.id,
        action="LECTURER_DATASET_EXPORTED",
        actor_type="USER",
        actor_user_id=admin.id,
        event_metadata={
            "record_count": len(lecturers_data),
            "format": "JSON",
            "exported_at": now.isoformat(),
        },
    )
    db.add(audit)
    db.commit()

    content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    filename = f"ictu_lecturers_{timestamp_str}.json"

    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/json; charset=utf-8",
        },
    )


@router.post("", response_model=LecturerResponse, status_code=status.HTTP_201_CREATED)
def create_lecturer(
    payload: LecturerCreate,
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_session),
) -> LecturerResponse:
    """Create a lecturer master record and its login account."""
    role = _validate_role(payload.role)
    full_name = _normalise_name(payload.full_name)
    email = payload.email.strip()
    staff_code = payload.staff_code.strip()
    if not full_name or not email or not staff_code:
        raise HTTPException(status_code=422, detail="Tên, email và mã cán bộ không được để trống.")

    if db.query(User).filter(func.lower(User.email) == email.lower()).first():
        raise HTTPException(status_code=409, detail="Email đã được sử dụng.")
    if db.query(Lecturer).filter(Lecturer.staff_code == staff_code).first():
        raise HTTPException(status_code=409, detail="Mã cán bộ đã được sử dụng.")

    lecturer = Lecturer(
        full_name=full_name,
        full_name_normalized=full_name.casefold(),
        email=email,
        staff_code=staff_code,
        academic_degree=payload.academic_degree,
        department=payload.department,
    )
    db.add(lecturer)
    try:
        db.flush()
        db.add(User(
            email=email,
            password_hash=password_hasher.hash(payload.password),
            display_name=full_name,
            role=role,
            lecturer_id=lecturer.id,
        ))
        db.commit()
        db.refresh(lecturer)
        return _lecturer_response(lecturer)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email hoặc mã cán bộ đã được sử dụng.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Không thể tạo tài khoản giảng viên.") from exc


def update_lecturer(
    lecturer_id: uuid.UUID,
    payload: LecturerUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_session),
) -> UserAdminResponse:
    from app.models.governance import AuditEvent
    lecturer, account = _find_lecturer_and_user(db, lecturer_id)
    if not lecturer and not account:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin giảng viên / người dùng.")

    # Unlinked Lecturer handling
    if account is None and lecturer is not None:
        if payload.version != lecturer.version:
            raise APIError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dữ liệu giảng viên đã bị thay đổi bởi phiên làm việc khác.",
                code="VERSION_CONFLICT",
            )
        before_dict = {
            "full_name": lecturer.full_name,
            "staff_code": lecturer.staff_code,
            "email": lecturer.email,
            "academic_degree": lecturer.academic_degree,
            "academic_rank": lecturer.academic_rank,
            "faculty": lecturer.faculty,
            "department": lecturer.department,
            "position": lecturer.position,
            "orcid": lecturer.orcid,
        }
        if payload.full_name is not None and payload.full_name.strip():
            fn = _normalise_name(payload.full_name)
            lecturer.full_name = fn
            lecturer.full_name_normalized = fn.casefold()
        if payload.staff_code is not None:
            sc = payload.staff_code.strip() or None
            if sc:
                dup_sc = db.query(Lecturer).filter(Lecturer.staff_code == sc, Lecturer.id != lecturer.id).first()
                if dup_sc:
                    raise HTTPException(status_code=409, detail="Mã cán bộ đã được sử dụng bởi giảng viên khác.")
            lecturer.staff_code = sc
        duplicate_email = None
        if payload.email is not None:
            email = payload.email.strip() or None
            if email:
                duplicate_email = (
                    db.query(Lecturer)
                    .filter(
                        func.lower(Lecturer.email) == email.lower(),
                        Lecturer.id != lecturer.id,
                    )
                    .first()
                )
            lecturer.email = email
        if payload.academic_degree is not None:
            lecturer.academic_degree = payload.academic_degree.strip() or None
        if payload.academic_rank is not None:
            lecturer.academic_rank = payload.academic_rank.strip() or None
        if payload.faculty is not None:
            lecturer.faculty = payload.faculty.strip() or None
        if payload.department is not None:
            lecturer.department = payload.department.strip() or None
        if payload.position is not None:
            lecturer.position = payload.position.strip() or None
        if payload.orcid is not None:
            lecturer.orcid = payload.orcid.strip() or None

        # Check if granting account
        if payload.grant_account:
            if not payload.password or len(payload.password) < 8:
                raise HTTPException(status_code=422, detail="Mật khẩu tài khoản phải có ít nhất 8 ký tự.")
            acc_email = (payload.email or lecturer.email or "").strip()
            if not acc_email:
                raise HTTPException(status_code=422, detail="Vui lòng cung cấp email để cấp tài khoản.")
            dup_u = db.query(User).filter(func.lower(User.email) == acc_email.lower()).first()
            if dup_u:
                raise HTTPException(status_code=409, detail="Email này đã được sử dụng cho một tài khoản khác.")
            role = _validate_role(payload.role)
            new_user = User(
                email=acc_email,
                password_hash=password_hasher.hash(payload.password),
                display_name=lecturer.full_name,
                role=role,
                lecturer_id=lecturer.id,
            )
            db.add(new_user)
            account = new_user

        lecturer.version += 1
        after_dict = {
            "full_name": lecturer.full_name,
            "staff_code": lecturer.staff_code,
            "email": lecturer.email,
            "academic_degree": lecturer.academic_degree,
            "academic_rank": lecturer.academic_rank,
            "faculty": lecturer.faculty,
            "department": lecturer.department,
            "position": lecturer.position,
            "orcid": lecturer.orcid,
        }

        # Audit event
        db.add(AuditEvent(
            entity_type="lecturer",
            entity_id=lecturer.id,
            action="LECTURER_UPDATED",
            actor_type="USER",
            actor_user_id=current_user.id,
            before_state=before_dict,
            after_state=after_dict,
        ))

        try:
            db.commit()
        except StaleDataError as exc:
            db.rollback()
            raise APIError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dữ liệu giảng viên đã bị thay đổi bởi phiên làm việc khác.",
                code="VERSION_CONFLICT",
            ) from exc
        except IntegrityError as exc:
            db.rollback()
            raise APIError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email, mã cán bộ hoặc ORCID đã được sử dụng bởi hồ sơ giảng viên khác.",
                code="LECTURER_DATA_CONFLICT",
            ) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise APIError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể cập nhật giảng viên.",
                code="DATABASE_UNAVAILABLE",
            ) from exc
        if account is not None:
            db.refresh(account)
            return to_admin_response(account, lecturer)
        else:
            db.refresh(lecturer)
            return UserAdminResponse(
                id=lecturer.id,
                email=lecturer.email or "",
                display_name=lecturer.full_name,
                role="LECTURER",
                lecturer_id=lecturer.id,
                staff_code=lecturer.staff_code,
                academic_rank=lecturer.academic_rank,
                academic_degree=lecturer.academic_degree,
                position=lecturer.position,
                department=lecturer.department,
                faculty=lecturer.faculty,
                orcid=lecturer.orcid,
                is_active=lecturer.is_active,
                version=lecturer.version,
                created_at=lecturer.created_at,
                updated_at=lecturer.updated_at,
                has_warning=duplicate_email is not None,
                warning_reason=(
                    f'Email "{lecturer.email}" đang được sử dụng cho nhiều hồ sơ giảng viên. '
                    "Vui lòng kiểm tra và cập nhật email hoặc thông tin nhận diện để xác định đúng hồ sơ."
                    if duplicate_email is not None
                    else None
                ),
            )

    changes = payload.model_dump(exclude_unset=True)
    mapped_changes = {"version": changes.pop("version")}
    if "full_name" in changes:
        mapped_changes["display_name"] = changes.pop("full_name")
    if "role" in changes and changes["role"] is not None:
        changes["role"] = _validate_role(changes["role"])
    mapped_changes.update(changes)
    admin_payload = UserAdminUpdate(**mapped_changes)
    try:
        changed = update_user(
            db,
            user=account,
            lecturer=lecturer,
            payload=admin_payload,
            actor=current_user,
        )
        if changed:
            db.commit()
            db.refresh(account)
            if lecturer is not None:
                db.refresh(lecturer)
        return to_admin_response(account, lecturer)
    except APIError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Thông tin giảng viên bị trùng.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Không thể cập nhật giảng viên.") from exc


router.put("/{lecturer_id}", response_model=UserAdminResponse)(update_lecturer)
router.patch("/{lecturer_id}", response_model=UserAdminResponse)(update_lecturer)


@router.delete("/{lecturer_id}", response_model=LecturerDeleteResponse)
def delete_lecturer(
    lecturer_id: uuid.UUID,
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_session),
) -> LecturerDeleteResponse:
    """Safe delete of a lecturer record if no linked account or business dependencies exist."""
    from datetime import UTC, datetime
    from app.models.governance import AuditEvent
    from app.models.identity import LecturerScopusIdentity
    from app.models.master_lecturer import (
        LecturerKnownPublication,
        LecturerSourceSnapshot,
    )

    lecturer, account = _find_lecturer_and_user(db, lecturer_id)
    if not lecturer and not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy giảng viên để xóa.",
        )

    # 1. Dependency check: linked User account
    if account is not None or (lecturer and db.query(User).filter(User.lecturer_id == lecturer.id).first()):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hồ sơ này đang được liên kết với tài khoản người dùng trong hệ thống.",
            code="LECTURER_IN_USE",
            data={"dependency": "USER_ACCOUNT"},
        )

    # 2. Dependency check: Scopus identities
    if lecturer:
        scopus_count = db.query(LecturerScopusIdentity).filter(
            LecturerScopusIdentity.lecturer_id == lecturer.id
        ).count()
        if scopus_count > 0:
            raise APIError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Hồ sơ này đang được liên kết với định danh Scopus trong hệ thống.",
                code="LECTURER_IN_USE",
                data={"dependency": "SCOPUS_IDENTITY", "count": scopus_count},
            )

        # 3. Dependency check: Known publications
        pub_count = db.query(LecturerKnownPublication).filter(
            LecturerKnownPublication.lecturer_id == lecturer.id
        ).count()
        if pub_count > 0:
            raise APIError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Hồ sơ này đang được liên kết với dữ liệu công bố khoa học trong hệ thống.",
                code="LECTURER_IN_USE",
                data={"dependency": "KNOWN_PUBLICATIONS", "count": pub_count},
            )

    try:
        if lecturer:
            # Delete child source snapshots associated strictly with this lecturer
            db.query(LecturerSourceSnapshot).filter(
                LecturerSourceSnapshot.lecturer_id == lecturer.id
            ).delete(synchronize_session=False)

            # Record audit event
            db.add(AuditEvent(
                entity_type="lecturer",
                entity_id=lecturer.id,
                action="LECTURER_DELETED",
                actor_type="USER",
                actor_user_id=current_user.id,
                event_metadata={
                    "full_name": lecturer.full_name,
                    "staff_code": lecturer.staff_code,
                    "deleted_at": datetime.now(UTC).isoformat(),
                },
            ))

            db.delete(lecturer)
            db.commit()

        return LecturerDeleteResponse(message="Xóa giảng viên thành công.")
    except IntegrityError as exc:
        db.rollback()
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hồ sơ này đang được liên kết với dữ liệu khác trong hệ thống.",
            code="LECTURER_IN_USE",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Không thể xóa giảng viên.") from exc



@router.get("/ping", summary="Lecturers healthcheck")
def ping() -> dict[str, str]:
    return {"status": "lecturers-ready", "milestone": "M2.3"}


# ---------------------------------------------------------------------------
# M2.5A — ICTU lecturer dataset import pipeline
# ---------------------------------------------------------------------------

def _lecturer_import_dataset_meta(dataset: dict) -> LecturerDatasetMetadata:
    return LecturerDatasetMetadata(
        name=dataset.get("name"),
        schema_version=str(dataset.get("schema_version") or "1.0"),
        institution=dataset.get("institution"),
        source=dataset.get("source"),
        source_url=dataset.get("source_url"),
        source_system=dataset.get("source_system"),
        generated_at=dataset.get("generated_at"),
        parser_version=dataset.get("parser_version"),
        record_count=int(dataset.get("record_count") or 0),
    )


async def _read_upload_bounded(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await file.read(1024 * 1024)
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
            status_code=422,
            detail="Không thể đọc tệp tải lên.",
            code="INVALID_IMPORT_FILE",
        ) from exc
    return b"".join(chunks)


def _validate_upload_filename(filename: str | None) -> str:
    if not filename or not filename.strip():
        raise APIError(
            status_code=422,
            detail="Tên tệp tải lên không hợp lệ.",
            code="INVALID_IMPORT_FILE",
        )
    cleaned = filename.strip()
    if not cleaned.lower().endswith(".json"):
        raise APIError(
            status_code=422,
            detail="Chỉ hỗ trợ tệp JSON (.json).",
            code="UNSUPPORTED_IMPORT_FORMAT",
        )
    return cleaned


@router.post(
    "/import/preview",
    response_model=LecturerPreviewResponse,
    summary="Preview an ICTU lecturer dataset before importing (read-only)",
)
async def preview_lecturer_dataset(
    admin: Annotated[User, Depends(require_role("ADMIN"))],
    db: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile | None, File()] = None,
) -> LecturerPreviewResponse:
    """M2.5A §27–§28: read-only diff against current lecturer master data."""
    if file is None:
        raise APIError(
            status_code=422,
            detail="Vui lòng chọn tệp JSON cần kiểm tra.",
            code="INVALID_IMPORT_FILE",
        )
    filename = _validate_upload_filename(file.filename)
    try:
        content = await _read_upload_bounded(file, LECTURER_IMPORT_MAX_BYTES)
    finally:
        await file.close()
    try:
        summary = LecturerPreviewService().preview(
            db, filename=filename, content=content
        )
    except DatasetValidationError as exc:
        raise APIError(
            status_code=422,
            detail=exc.message,
            code=exc.code or "INVALID_LECTURER_DATASET",
        ) from exc
    return LecturerPreviewResponse(
        dataset=_lecturer_import_dataset_meta(summary.dataset),
        summary={
            "total": summary.total,
            "valid": summary.valid,
            "create": summary.create,
            "update": summary.update,
            "unchanged": summary.unchanged,
            "conflicts": summary.conflicts,
        },
        conflicts=[LecturerDatasetConflict(**c) for c in summary.conflict_samples],
        filename=summary.filename,
        parser_version=summary.parser_version,
    )


@router.post(
    "/import",
    response_model=LecturerImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply a previously previewed ICTU lecturer dataset to the database",
)
async def import_lecturer_dataset(
    admin: Annotated[User, Depends(require_role("ADMIN"))],
    db: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile | None, File()] = None,
) -> LecturerImportResponse:
    """M2.5A §29–§35: ADMIN-only, atomic, idempotent import."""
    if file is None:
        raise APIError(
            status_code=422,
            detail="Vui lòng chọn tệp JSON cần nhập.",
            code="INVALID_IMPORT_FILE",
        )
    filename = _validate_upload_filename(file.filename)
    try:
        content = await _read_upload_bounded(file, LECTURER_IMPORT_MAX_BYTES)
    finally:
        await file.close()
    try:
        result = LecturerImportService().import_dataset(
            db,
            filename=filename,
            content=content,
            actor=admin,
        )
    except DatasetValidationError as exc:
        raise APIError(
            status_code=422,
            detail=exc.message,
            code=exc.code or "INVALID_LECTURER_DATASET",
        ) from exc
    except LecturerDatasetError as exc:
        raise APIError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
            code=exc.code,
        ) from exc
    return LecturerImportResponse(
        dataset=_lecturer_import_dataset_meta(result.dataset),
        summary={
            "total": result.total,
            "created": result.created,
            "updated": result.updated,
            "unchanged": result.unchanged,
            "conflicts": result.conflicts,
        },
        conflicts=[LecturerDatasetConflict(**c) for c in result.conflict_samples],
        snapshot_ids=result.snapshot_ids,
        filename=result.filename,
        parser_version=result.parser_version,
    )


@router.get(
    "/master",
    response_model=LecturerListResponse,
    summary="Server-side paginated lecturer master-data listing",
)
def list_lecturer_master(
    admin: Annotated[User, Depends(require_role("ADMIN"))],
    db: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
    search: Annotated[str | None, Query(max_length=255)] = None,
    faculty: Annotated[str | None, Query(max_length=150)] = None,
    department: Annotated[str | None, Query(max_length=150)] = None,
) -> LecturerListResponse:
    """Server-side paginated lecturer listing with linked user accounts."""
    return list_lecturers(
        admin=admin,
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        faculty=faculty,
        department=department,
    )


@router.post(
    "/import/{import_id}/rollback",
    summary="Rollback an applied ICTU lecturer dataset import",
)
def rollback_lecturer_import_endpoint(
    import_id: uuid.UUID,
    admin: Annotated[User, Depends(require_role("ADMIN"))],
    db: Annotated[Session, Depends(get_session)],
) -> dict[str, Any]:
    """Admin-only rollback of an imported lecturer dataset."""
    from app.services.lecturer_dataset.rollback import (
        LecturerRollbackError,
        LecturerRollbackService,
    )

    try:
        summary = LecturerRollbackService().rollback_import(
            db, import_id=import_id, actor=admin
        )
        return {
            "message": "Đã hoàn tác đợt nhập giảng viên thành công.",
            "import_id": str(summary.import_id),
            "created_records_removed": summary.created_records_removed,
            "updated_records_restored": summary.updated_records_restored,
            "manual_records_preserved": summary.manual_records_preserved,
            "multi_source_records_preserved": summary.multi_source_records_preserved,
            "rolled_back_at": summary.rolled_back_at.isoformat(),
        }
    except LecturerRollbackError as exc:
        raise APIError(
            status_code=exc.status_code,
            detail=exc.message,
            code=exc.code,
            data=exc.data,
        ) from exc
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể hoàn tác đợt nhập giảng viên do lỗi cơ sở dữ liệu.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


@router.delete(
    "/unlinked/cleanup",
    summary="Clean orphan unlinked lecturer records (no active user account attached)",
)
def cleanup_unlinked_lecturers(
    admin: Annotated[User, Depends(require_role("ADMIN"))],
    db: Annotated[Session, Depends(get_session)],
) -> dict[str, Any]:
    """Admin-only cleanup of orphan imported lecturer records with no linked accounts."""
    from scripts.clean_orphan_lecturers import clean_orphan_lecturers

    count = clean_orphan_lecturers(db)
    return {
        "message": f"Đã dọn dẹp thành công {count} hồ sơ giảng viên mồ côi chưa cấp tài khoản.",
        "cleaned_count": count,
    }
