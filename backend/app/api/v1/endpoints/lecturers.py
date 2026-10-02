"""Lecturer and linked user-account management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_session
from app.core.exceptions import APIError
from app.core.security import password_hasher
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.schemas.lecturer import (
    LecturerCreate,
    LecturerDeleteResponse,
    LecturerResponse,
    LecturerUpdate,
)
from app.schemas.user import UserAdminResponse, UserAdminUpdate
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


@router.get(
    "",
    response_model=list[LecturerUserResponse],
    summary="List all lecturers and users in the system",
)
def list_lecturers_and_users(
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_session),
) -> list[LecturerUserResponse]:
    """Return all accounts merged with lecturer master data."""
    try:
        users = db.query(User).order_by(User.created_at.asc()).all()
        lecturer_map = {item.id: item for item in db.query(Lecturer).all()}
        result = []
        for user in users:
            lecturer = lecturer_map.get(user.lecturer_id) if user.lecturer_id else None
            result.append(
                LecturerUserResponse(
                    id=user.id,
                    email=user.email,
                    display_name=user.display_name,
                    role=user.role,
                    lecturer_id=user.lecturer_id,
                    staff_code=lecturer.staff_code if lecturer else None,
                    academic_rank=lecturer.academic_rank if lecturer else None,
                    academic_degree=lecturer.academic_degree if lecturer else None,
                    position=lecturer.position if lecturer else None,
                    department=lecturer.department if lecturer else None,
                    faculty=lecturer.faculty if lecturer else None,
                    orcid=lecturer.orcid if lecturer else None,
                    is_active=user.is_active,
                    version=user.version,
                )
            )
        return result
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể truy vấn danh sách giảng viên.",
        ) from exc


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
    lecturer, account = _find_lecturer_and_user(db, lecturer_id)
    if not lecturer and not account:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin giảng viên / người dùng.")

    if account is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản liên kết.",
            code="USER_NOT_FOUND",
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
    """Delete the linked account and lecturer record."""
    lecturer, account = _find_lecturer_and_user(db, lecturer_id)
    if account and account.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa chính tài khoản đang đăng nhập.",
        )
    try:
        if account:
            db.delete(account)
        if lecturer:
            db.delete(lecturer)
        db.commit()
        return LecturerDeleteResponse(message="Xóa giảng viên / người dùng thành công.")
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Không thể xóa giảng viên vì còn dữ liệu liên quan trong hệ thống.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Không thể xóa giảng viên.") from exc


@router.get("/ping", summary="Lecturers healthcheck")
def ping() -> dict[str, str]:
    return {"status": "lecturers-ready", "milestone": "M2.3"}
