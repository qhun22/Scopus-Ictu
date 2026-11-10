"""Self-service ownership, allowlist, audit and optimistic-concurrency regression tests."""

import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.dependencies import get_current_user
from app.api.v1.endpoints.lecturer_scopus import router
from app.core.database import get_session
from app.core.exceptions import APIError, api_error_handler
from app.models.governance import AuditEvent, User
from app.models.master_lecturer import Lecturer
from app.schemas.lecturer_profile_update import LecturerProfileUpdate
from app.services.lecturer_profile_service import update_my_profile


@pytest.fixture
def context():
    lecturer = Lecturer(
        id=uuid.uuid4(),
        full_name="Synthetic Lecturer",
        full_name_normalized="synthetic lecturer",
        email="lecturer@example.invalid",
        version=7,
        academic_degree="Old degree",
        phone="0123456789",
        date_of_birth=date(1990, 1, 1),
    )
    actor = User(id=uuid.uuid4(), role="LECTURER", is_active=True, lecturer_id=lecturer.id)
    session = MagicMock(spec=Session)
    session.get.return_value = lecturer
    session.scalar.return_value = None
    return session, actor, lecturer


def test_update_is_own_profile_and_audits_only_changed_fields(context):
    session, actor, lecturer = context
    result = update_my_profile(
        session,
        actor=actor,
        payload=LecturerProfileUpdate(
            version=7,
            academic_degree="  New degree  ",
            phone=None,
            date_of_birth="1991-02-03",
        ),
    )
    assert result.lecturer_id == actor.lecturer_id
    assert result.academic_degree == "New degree"
    assert lecturer.phone is None
    session.get.assert_any_call(
        Lecturer,
        actor.lecturer_id,
        with_for_update=True,
        populate_existing=True,
    )
    audit = session.add.call_args.args[0]
    assert isinstance(audit, AuditEvent)
    assert audit.actor_user_id == actor.id
    assert audit.entity_id == lecturer.id
    assert audit.action == "LECTURER_PROFILE_SELF_UPDATED"
    assert audit.before_state["date_of_birth"] == "1990-01-01"
    assert audit.after_state == {
        "academic_degree": "New degree",
        "phone": None,
        "date_of_birth": "1991-02-03",
    }
    assert audit.event_metadata["source"] == "LECTURER_SELF_EDIT"
    session.commit.assert_called_once()


@pytest.mark.parametrize(
    "field,value",
    [
        ("lecturer_id", str(uuid.uuid4())),
        ("id", str(uuid.uuid4())),
        ("role", "ADMIN"),
        ("email", "other@example.invalid"),
        ("full_name", "Other Person"),
        ("faculty", "Other unit"),
        ("department", "Other department"),
        ("staff_code", "123"),
        ("is_primary", True),
        ("status", "APPROVED"),
        ("scopus_id", "11111111111"),
    ],
)
def test_locked_fields_are_not_accepted(field, value):
    with pytest.raises(ValidationError):
        LecturerProfileUpdate.model_validate({"version": 7, field: value})


@pytest.mark.parametrize(
    "role,active,linked,code",
    [
        ("ADMIN", True, True, "FORBIDDEN"),
        ("REVIEWER", True, True, "FORBIDDEN"),
        ("LECTURER", False, True, "FORBIDDEN"),
        ("LECTURER", True, False, "LECTURER_NOT_LINKED"),
    ],
)
def test_service_rejects_unlinked_inactive_and_wrong_roles(context, role, active, linked, code):
    session, actor, _ = context
    actor.role, actor.is_active = role, active
    if not linked:
        actor.lecturer_id = None
    with pytest.raises(APIError) as exc:
        update_my_profile(session, actor=actor, payload=LecturerProfileUpdate(version=7))
    assert exc.value.code == code
    session.get.assert_not_called()


def test_stale_version_cannot_overwrite(context):
    session, actor, lecturer = context
    with pytest.raises(APIError) as exc:
        update_my_profile(
            session,
            actor=actor,
            payload=LecturerProfileUpdate(
                version=6,
                academic_degree="Overwrite",
            ),
        )
    assert exc.value.code == "VERSION_CONFLICT"
    assert lecturer.academic_degree == "Old degree"
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("orcid", "invalid", "INVALID_ORCID"),
        ("repository_profile_url", "javascript:alert(1)", "INVALID_PROFILE_URL"),
        ("repository_profile_url", "https://user:password@example.invalid", "INVALID_PROFILE_URL"),
        (
            "date_of_birth",
            (datetime.now(UTC).date() + timedelta(days=1)).isoformat(),
            "INVALID_BIRTH_DATE",
        ),
    ],
)
def test_invalid_values_are_rejected_before_loading_profile(context, field, value, code):
    session, actor, _ = context
    with pytest.raises(APIError) as exc:
        update_my_profile(
            session,
            actor=actor,
            payload=LecturerProfileUpdate.model_validate(
                {"version": 7, field: value},
            ),
        )
    assert exc.value.code == code
    session.get.assert_not_called()


def test_orcid_url_is_normalized_and_duplicates_rejected(context):
    session, actor, lecturer = context
    payload = LecturerProfileUpdate(version=7, orcid="https://orcid.org/0000-0000-0000-000x/")
    update_my_profile(session, actor=actor, payload=payload)
    assert lecturer.orcid == "0000-0000-0000-000X"
    lecturer.orcid = None
    session.scalar.return_value = uuid.uuid4()
    with pytest.raises(APIError) as exc:
        update_my_profile(session, actor=actor, payload=payload)
    assert exc.value.code == "ORCID_ALREADY_EXISTS"
    assert lecturer.orcid is None


def test_noop_does_not_create_audit_or_increment_version(context):
    session, actor, _ = context
    update_my_profile(
        session,
        actor=actor,
        payload=LecturerProfileUpdate(
            version=7,
            academic_degree="Old degree",
        ),
    )
    session.add.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "error,code",
    [
        (StaleDataError("synthetic conflict"), "VERSION_CONFLICT"),
        (IntegrityError("synthetic", {}, Exception("synthetic")), "PROFILE_UPDATE_CONFLICT"),
        (SQLAlchemyError("synthetic failure"), "PROFILE_UPDATE_FAILED"),
    ],
)
def test_failed_write_rolls_back(context, error, code):
    session, actor, _ = context
    session.flush.side_effect = error
    with pytest.raises(APIError) as exc:
        update_my_profile(
            session, actor=actor, payload=LecturerProfileUpdate(version=7, phone=None)
        )
    assert exc.value.code == code
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_http_ownership_and_extra_fields(context):
    session, actor, _ = context
    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)
    app.include_router(router, prefix="/api/v1/lecturers")
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/lecturers/me/profile",
            json={
                "version": 7,
                "lecturer_id": str(uuid.uuid4()),
                "phone": "123",
            },
        )
        assert response.status_code == 422
        session.get.assert_not_called()
        response = client.patch(
            "/api/v1/lecturers/me/profile",
            json={
                "version": 7,
                "phone": "123",
            },
        )
        assert response.status_code == 200
        assert response.json()["lecturer_id"] == str(actor.lecturer_id)
        actor.role = "ADMIN"
        assert client.patch("/api/v1/lecturers/me/profile", json={"version": 7}).status_code == 403
