from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints import lecturers as lecturer_endpoints
from app.core.exceptions import APIError
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.schemas.lecturer import LecturerUpdate


def _lecturer(*, email: str) -> Lecturer:
    now = datetime.now(UTC)
    return Lecturer(
        id=uuid.uuid4(),
        full_name="Test Lecturer",
        full_name_normalized="test lecturer",
        email=email,
        staff_code="TEST-001",
        is_active=True,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _admin() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="admin@test.invalid",
        password_hash="not-used",
        display_name="Admin",
        role="ADMIN",
        is_active=True,
        version=1,
        auth_version=1,
        created_at=now,
        updated_at=now,
    )


def test_unlinked_lecturer_update_keeps_duplicate_email_as_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _lecturer(email="old@test.invalid")
    duplicate = _lecturer(email="used@test.invalid")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = duplicate
    monkeypatch.setattr(
        lecturer_endpoints,
        "_find_lecturer_and_user",
        lambda _db, _id: (target, None),
    )

    result = lecturer_endpoints.update_lecturer(
        target.id,
        LecturerUpdate(version=1, email="USED@test.invalid"),
        current_user=_admin(),
        db=db,
    )

    assert target.email == "USED@test.invalid"
    assert result.has_warning is True
    assert "đang được sử dụng cho nhiều hồ sơ" in (result.warning_reason or "")
    db.commit.assert_called_once_with()


def test_unlinked_lecturer_update_maps_commit_integrity_error_to_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _lecturer(email="old@test.invalid")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit.side_effect = IntegrityError(
        "UPDATE lecturers ...",
        {},
        Exception("duplicate key"),
    )
    monkeypatch.setattr(
        lecturer_endpoints,
        "_find_lecturer_and_user",
        lambda _db, _id: (target, None),
    )

    with pytest.raises(APIError) as exc_info:
        lecturer_endpoints.update_lecturer(
            target.id,
            LecturerUpdate(version=1, email="new@test.invalid"),
            current_user=_admin(),
            db=db,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "LECTURER_DATA_CONFLICT"
    db.rollback.assert_called_once_with()
