"""Versioned self-service profile updates, independent of review decisions."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import APIError
from app.models.governance import AuditEvent, User
from app.models.master_lecturer import Lecturer
from app.schemas.lecturer_profile_update import LecturerProfileUpdate
from app.schemas.lecturer_scopus_projection import LecturerProfileRead
from app.services.lecturer_scopus_projection import LecturerScopusProjectionService


def _invalid(code: str, detail: str, status: int = 422) -> APIError:
    return APIError(status_code=status, code=code, detail=detail)


def _normalize_changes(payload: LecturerProfileUpdate) -> dict:
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})
    if changes.get("orcid"):
        identifier = (
            re.sub(r"^https?://(?:www\.)?orcid\.org/", "", changes["orcid"], flags=re.IGNORECASE)
            .rstrip("/")
            .upper()
        )
        if not re.fullmatch(r"[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]", identifier):
            raise _invalid("INVALID_ORCID", "ORCID không đúng định dạng.")
        changes["orcid"] = identifier
    if changes.get("repository_profile_url"):
        value = changes["repository_profile_url"]
        try:
            url = urlsplit(value)
            valid = (
                url.scheme in {"http", "https"}
                and bool(url.hostname)
                and not url.username
                and not url.password
                and "\\" not in value
                and not any(character.isspace() for character in value)
            )
            _ = url.port
        except ValueError:
            valid = False
        if not valid:
            raise _invalid("INVALID_PROFILE_URL", "Liên kết hồ sơ phải là URL HTTP hoặc HTTPS.")
    if changes.get("date_of_birth") and changes["date_of_birth"] > datetime.now(UTC).date():
        raise _invalid("INVALID_BIRTH_DATE", "Ngày sinh không được nằm trong tương lai.")
    return changes


def _snapshot(changes: dict) -> dict:
    return {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in changes.items()
    }


def update_my_profile(
    session: Session,
    *,
    actor: User,
    payload: LecturerProfileUpdate,
) -> LecturerProfileRead:
    """The authenticated actor selects the target; payload never accepts a lecturer ID."""
    if actor.role != "LECTURER" or not actor.is_active:
        raise _invalid("FORBIDDEN", "Bạn không có quyền cập nhật hồ sơ này.", 403)
    if actor.lecturer_id is None:
        raise _invalid("LECTURER_NOT_LINKED", "Tài khoản chưa được liên kết với giảng viên.", 403)
    changes = _normalize_changes(payload)
    try:
        lecturer = session.get(
            Lecturer,
            actor.lecturer_id,
            with_for_update=True,
            populate_existing=True,
        )
        if lecturer is None:
            raise _invalid("LECTURER_NOT_FOUND", "Không tìm thấy hồ sơ giảng viên.", 404)
        if lecturer.version != payload.version:
            raise _invalid(
                "VERSION_CONFLICT",
                "Hồ sơ đã thay đổi. Vui lòng tải lại trước khi lưu.",
                409,
            )
        changes = {key: value for key, value in changes.items() if getattr(lecturer, key) != value}
        for field, code, detail in (
            ("orcid", "ORCID_ALREADY_EXISTS", "ORCID đã được sử dụng cho hồ sơ khác."),
            (
                "repository_profile_url",
                "PROFILE_URL_ALREADY_EXISTS",
                "Liên kết hồ sơ đã được sử dụng cho giảng viên khác.",
            ),
        ):
            if (
                changes.get(field)
                and session.scalar(
                    select(Lecturer.id).where(
                        getattr(Lecturer, field) == changes[field],
                        Lecturer.id != lecturer.id,
                    )
                )
                is not None
            ):
                raise _invalid(code, detail, 409)
        before = {key: getattr(lecturer, key) for key in changes}
        if changes:
            for field, value in changes.items():
                setattr(lecturer, field, value)
            now = datetime.now(UTC)
            lecturer.updated_at = now
            session.add(
                AuditEvent(
                    id=uuid.uuid4(),
                    entity_type="lecturer",
                    entity_id=lecturer.id,
                    action="LECTURER_PROFILE_SELF_UPDATED",
                    actor_type="USER",
                    actor_user_id=actor.id,
                    actor_service=None,
                    before_state=_snapshot(before),
                    after_state=_snapshot(changes),
                    reason="Giảng viên tự cập nhật thông tin cá nhân.",
                    event_metadata={"source": "LECTURER_SELF_EDIT", "fields": sorted(changes)},
                    created_at=now,
                )
            )
            session.flush()
        result = LecturerScopusProjectionService(session).get_lecturer_profile(lecturer.id)
        if result is None:
            raise _invalid("LECTURER_NOT_FOUND", "Không tìm thấy hồ sơ giảng viên.", 404)
        if changes:
            session.commit()
        return result
    except APIError:
        session.rollback()
        raise
    except StaleDataError as exc:
        session.rollback()
        raise _invalid("VERSION_CONFLICT", "Hồ sơ đã thay đổi. Vui lòng tải lại.", 409) from exc
    except IntegrityError as exc:
        session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == "uq_lecturers_orcid":
            raise _invalid(
                "ORCID_ALREADY_EXISTS",
                "ORCID đã được sử dụng cho hồ sơ khác.",
                409,
            ) from exc
        raise _invalid(
            "PROFILE_UPDATE_CONFLICT",
            "Không thể lưu do dữ liệu bị xung đột.",
            409,
        ) from exc
    except SQLAlchemyError as exc:
        session.rollback()
        raise _invalid(
            "PROFILE_UPDATE_FAILED",
            "Không thể lưu hồ sơ. Vui lòng thử lại.",
            503,
        ) from exc
