from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.v1.endpoints.imports as imports_endpoint
from app.core.config import settings
from app.core.database import get_session
from app.core.security import password_hasher, token_service
from app.main import app
from app.models.governance import User
from app.schemas.scopus_import import ScopusImportResponse
from app.services.scopus_import_service import (
    DuplicateImportConfirmationRequired,
    ImportAlreadyProcessing,
)

CSV = b"Authors,Title,EID\nAuthor A,Synthetic paper,EID-1\n"


def import_response(status: str = "RECEIVED") -> ScopusImportResponse:
    now = datetime.now(UTC)
    return ScopusImportResponse(
        id=uuid.uuid4(), file_name="sample.csv", status=status,
        total_records=0, imported_records=0, failed_records=0, processed_records=0,
        progress_percent=0, duplicate_candidates=0, row_errors=[], error_summary=None,
        version=1, created_at=now, updated_at=now, started_at=now,
        finished_at=None, duration_seconds=0, is_terminal=False, performed_by="Synthetic ADMIN",
    )


def create_user(role: str) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.lower()}@example.test",
        password_hash=password_hasher.hash("SyntheticPassword123!"),
        display_name=f"Synthetic {role}",
        role=role,
        lecturer_id=uuid.uuid4() if role == "LECTURER" else None,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(mock_db: MagicMock) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: mock_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def authenticate(client: TestClient, mock_db: MagicMock, role: str) -> User:
    user = create_user(role)
    mock_db.query.return_value.filter.return_value.first.return_value = user
    token = token_service.create_access_token(
        {"sub": str(user.id), "email": user.email, "role": role, "av": 1}
    )
    client.cookies.set("access_token", token)
    return user


def test_delete_import_returns_boolean_deleted_flag(
    client: TestClient,
    mock_db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticate(client, mock_db, "ADMIN")
    monkeypatch.setattr(
        imports_endpoint,
        "delete_scopus_import",
        lambda *_args, **_kwargs: True,
    )

    response = client.delete(f"/api/v1/imports/{uuid.uuid4()}")

    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_admin_upload_valid_csv(
    client: TestClient,
    mock_db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticate(client, mock_db, "ADMIN")
    queued = import_response()
    monkeypatch.setattr(imports_endpoint, "create_import_job", lambda *_args, **_kwargs: queued)
    monkeypatch.setattr(imports_endpoint, "process_import_job", lambda *_args, **_kwargs: None)
    response = client.post(
        "/api/v1/imports/scopus",
        files={"file": ("sample.csv", CSV, "text/csv")},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "RECEIVED"
    assert response.json()["progress_percent"] == 0


@pytest.mark.parametrize("role", ["LECTURER", "REVIEWER"])
def test_non_admin_upload_is_forbidden(
    client: TestClient,
    mock_db: MagicMock,
    role: str,
) -> None:
    authenticate(client, mock_db, role)
    response = client.post(
        "/api/v1/imports/scopus",
        files={"file": ("sample.csv", CSV, "text/csv")},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("sample.xlsx", CSV, "UNSUPPORTED_IMPORT_FORMAT"),
        ("sample.csv", b"", "EMPTY_IMPORT_FILE"),
    ],
)
def test_invalid_uploads_return_stable_codes(
    client: TestClient,
    mock_db: MagicMock,
    filename: str,
    content: bytes,
    code: str,
) -> None:
    authenticate(client, mock_db, "ADMIN")
    response = client.post(
        "/api/v1/imports/scopus",
        files={"file": (filename, content, "application/octet-stream")},
    )
    assert response.status_code == 422
    assert response.json()["code"] == code


def test_oversized_upload_is_rejected(
    client: TestClient,
    mock_db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticate(client, mock_db, "ADMIN")
    monkeypatch.setattr(settings, "scopus_import_max_bytes", 3)
    response = client.post(
        "/api/v1/imports/scopus",
        files={"file": ("sample.csv", b"1234", "text/csv")},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "IMPORT_FILE_TOO_LARGE"


def test_active_duplicate_returns_existing_job_id(
    client: TestClient,
    mock_db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticate(client, mock_db, "ADMIN")
    existing_id = uuid.uuid4()

    def conflict(*_args: object, **_kwargs: object) -> object:
        raise ImportAlreadyProcessing(existing_id)

    monkeypatch.setattr(imports_endpoint, "create_import_job", conflict)
    response = client.post(
        "/api/v1/imports/scopus",
        files={"file": ("sample.csv", CSV, "text/csv")},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "IMPORT_ALREADY_PROCESSING"
    assert response.json()["existing_import_id"] == str(existing_id)


def test_completed_duplicate_requires_explicit_confirmation(
    client: TestClient,
    mock_db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticate(client, mock_db, "ADMIN")
    previous = SimpleNamespace(
        id=uuid.uuid4(),
        file_name="previous.csv",
        created_at=datetime.now(UTC),
    )

    def conflict(*_args: object, **_kwargs: object) -> object:
        raise DuplicateImportConfirmationRequired(previous)  # type: ignore[arg-type]

    monkeypatch.setattr(imports_endpoint, "create_import_job", conflict)
    response = client.post(
        "/api/v1/imports/scopus",
        files={"file": ("sample.csv", CSV, "text/csv")},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_IMPORT_CONFIRMATION_REQUIRED"
    assert response.json()["duplicate_of_import_id"] == str(previous.id)


def test_admin_history_empty_list(client: TestClient, mock_db: MagicMock) -> None:
    authenticate(client, mock_db, "ADMIN")
    mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    response = client.get("/api/v1/imports")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["stats"]["total_imports"] == 0


@pytest.mark.parametrize("path", ["/api/v1/imports", f"/api/v1/imports/{uuid.uuid4()}"])
def test_non_admin_history_and_detail_are_forbidden(
    client: TestClient,
    mock_db: MagicMock,
    path: str,
) -> None:
    authenticate(client, mock_db, "REVIEWER")
    response = client.get(path)
    assert response.status_code == 403


def test_unknown_import_returns_404(
    client: TestClient,
    mock_db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticate(client, mock_db, "ADMIN")
    # Patch the service function directly: get_import returns None → 404.
    import app.api.v1.endpoints.imports as imports_endpoint_module
    monkeypatch.setattr(
        imports_endpoint_module,
        "get_import",
        lambda db, import_id: None,
    )
    response = client.get(f"/api/v1/imports/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "IMPORT_NOT_FOUND"
