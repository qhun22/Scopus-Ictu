"""Integration tests for M2.5A lecturer import API (preview + import + idempotency).

These tests use a ``MagicMock`` DB session so they run offline. The
existing scopus CSV import integration test
(``test_scopus_import_api.py``) follows the same mocking style and is
the closest precedent.

Authentication is bypassed by overriding ``get_current_user`` on the
FastAPI app so the tests stay focused on the import pipeline's own
logic.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.governance import User


FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "ictu_lecturers_fixture.json"
)


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fixture_bytes() -> bytes:
    return FIXTURE_PATH.read_bytes()


def _create_user(*, role: str = "ADMIN", lecturer_id: uuid.UUID | None = None) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.lower()}@test.invalid",
        password_hash="x",
        display_name=f"Test {role.title()}",
        role=role,
        lecturer_id=lecturer_id,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=None,
        updated_at=None,
    )


def _install_role_override(role: str) -> None:
    """Override the FastAPI ``get_current_user`` dependency to return
    a deterministic User with the requested role. Works for both
    successful-auth tests and authorization-failure tests (the
    ``LECTURER``/``REVIEWER`` cases flow into ``require_role`` and
    are correctly rejected with ``403 FORBIDDEN``).
    """
    user = _create_user(role=role)
    app.dependency_overrides[get_current_user] = lambda: user


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(mock_db: MagicMock) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: mock_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _configure_db_with(mock_db: MagicMock, *, lecturers: list | None = None) -> None:
    """Configure the MagicMock ``db.query(Lecturer)`` chain so the
    preview/import service sees the supplied list of Lecturer-like
    objects."""
    lecturers = lecturers or []

    def query(model: Any) -> MagicMock:
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.all.return_value = lecturers
        chain.first.return_value = lecturers[0] if lecturers else None
        chain.scalar.return_value = len(lecturers)
        chain.scalars.return_value.all.return_value = lecturers
        chain.offset.return_value = chain
        chain.limit.return_value = chain
        chain.order_by.return_value = chain
        chain.distinct.return_value = chain
        return chain

    mock_db.query.side_effect = query
    # Also needed by _get_lecturer_stats which calls db.scalar() directly
    mock_db.scalar.return_value = len(lecturers)


# ---------------------------------------------------------------------------
# Authorisation
# ---------------------------------------------------------------------------

def test_preview_requires_admin_role(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="LECTURER")
    response = client.post(
        "/api/v1/lecturers/import/preview",
        files={"file": ("fixture.json", _fixture_bytes(), "application/json")},
    )
    assert response.status_code == 403, response.text
    assert response.json().get("code") == "FORBIDDEN"


def test_import_requires_admin_role(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="REVIEWER")
    response = client.post(
        "/api/v1/lecturers/import",
        files={"file": ("fixture.json", _fixture_bytes(), "application/json")},
    )
    assert response.status_code == 403
    assert response.json().get("code") == "FORBIDDEN"


def test_import_requires_authentication(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    response = client.post(
        "/api/v1/lecturers/import",
        files={"file": ("fixture.json", _fixture_bytes(), "application/json")},
    )
    assert response.status_code == 401
    assert response.json().get("code") == "SESSION_REVOKED"


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def test_preview_counts_match_fixture(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="ADMIN")
    response = client.post(
        "/api/v1/lecturers/import/preview",
        files={"file": ("fixture.json", _fixture_bytes(), "application/json")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["total"] == 5
    assert body["summary"]["create"] == 5
    assert body["summary"]["update"] == 0
    assert body["summary"]["unchanged"] == 0
    assert body["filename"] == "fixture.json"
    assert body["dataset"]["schema_version"] == "1.0"


def test_preview_accepts_dh_academic_degree(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="ADMIN")
    payload = _load_fixture()
    payload["lecturers"][0]["academic_degree"] = "DH"
    raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response = client.post(
        "/api/v1/lecturers/import/preview",
        files={"file": ("ictu_lecturers.json", raw_bytes, "application/json")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["total"] == len(payload["lecturers"])



def test_preview_does_not_mutate_db(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="ADMIN")
    response = client.post(
        "/api/v1/lecturers/import/preview",
        files={"file": ("fixture.json", _fixture_bytes(), "application/json")},
    )
    assert response.status_code == 200
    # Critical: preview must never call db.add or db.commit.
    assert mock_db.add.call_count == 0
    assert mock_db.commit.call_count == 0


def test_preview_rejects_unsupported_extension(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="ADMIN")
    response = client.post(
        "/api/v1/lecturers/import/preview",
        files={"file": ("fixture.csv", _fixture_bytes(), "text/csv")},
    )
    assert response.status_code == 422
    assert response.json().get("code") == "UNSUPPORTED_IMPORT_FORMAT"


def test_preview_rejects_invalid_schema(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="ADMIN")
    payload = _load_fixture()
    payload["dataset"]["schema_version"] = "99.0"
    bad = json.dumps(payload).encode("utf-8")
    response = client.post(
        "/api/v1/lecturers/import/preview",
        files={"file": ("fixture.json", bad, "application/json")},
    )
    assert response.status_code == 422
    assert response.json().get("code") == "UNSUPPORTED_DATASET_SCHEMA"


# ---------------------------------------------------------------------------
# Import — idempotency
# ---------------------------------------------------------------------------

def test_import_creates_records_then_idempotent(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="ADMIN")
    response = client.post(
        "/api/v1/lecturers/import",
        files={"file": ("fixture.json", _fixture_bytes(), "application/json")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["summary"]["total"] == 5
    assert body["summary"]["created"] == 5
    assert body["summary"]["updated"] == 0
    assert body["summary"]["unchanged"] == 0
    assert len(body["snapshot_ids"]) == 5
    assert len(body["conflicts"]) == 0  # fixture is deterministic, no soft matches
    assert mock_db.add.called
    assert mock_db.commit.called


def test_import_rejects_invalid_json(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="ADMIN")
    response = client.post(
        "/api/v1/lecturers/import",
        files={"file": ("bad.json", b"{not-json", "application/json")},
    )
    assert response.status_code == 422
    assert response.json().get("code") == "INVALID_LECTURER_DATASET"


def test_import_rejects_duplicate_emails(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="ADMIN")
    payload = _load_fixture()
    payload["lecturers"][1]["institutional_email"] = payload["lecturers"][0]["institutional_email"]
    response = client.post(
        "/api/v1/lecturers/import",
        files={"file": ("fixture.json", json.dumps(payload).encode("utf-8"), "application/json")},
    )
    assert response.status_code == 422
    assert response.json().get("code") == "DUPLICATE_LECTURER_IDENTITY"
    assert mock_db.commit.call_count == 0


# ---------------------------------------------------------------------------
# Lecturer master listing
# ---------------------------------------------------------------------------

def test_list_master_requires_admin(client: TestClient, mock_db: MagicMock) -> None:
    _configure_db_with(mock_db)
    _install_role_override(role="LECTURER")
    response = client.get("/api/v1/lecturers/master")
    assert response.status_code == 403
    assert response.json().get("code") == "FORBIDDEN"


def test_list_master_returns_pagination_envelope(client: TestClient, mock_db: MagicMock) -> None:
    fake_lecturers = [
        MagicMock(
            id=uuid.uuid4(),
            full_name=f"Test Lecturer {i}",
            full_name_normalized=f"test lecturer {i}",
            staff_code=f"ICTU-T-{i:03d}",
            email=f"test.{i}@example.invalid",
            repository_profile_url=f"https://repository.ictu.edu.vn/lecturer/{i}",
            academic_degree="ThS",
            academic_rank=None,
            position="Lecturer",
            faculty="Faculty of Information Technology",
            department="Department of Computer Science",
            orcid=None,
            is_active=True,
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        for i in range(3)
    ]
    _configure_db_with(mock_db, lecturers=fake_lecturers)
    _install_role_override(role="ADMIN")
    response = client.get("/api/v1/lecturers/master?page=1&page_size=10")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "items" in body and "total" in body
    assert body["page"] == 1
    assert body["page_size"] == 10
