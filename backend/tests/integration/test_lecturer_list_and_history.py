"""Integration tests for M2.5 / M2.5A integration:
- Lecturer master list & account linkage
- Unified import history (Scopus CSV + Lecturer JSON)
- Lecturer import result semantics (410 records, outcome invariants, duplicate warnings)
- Safe delete Scopus import (downstream safety, role check, audit logging)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
import app.api.v1.endpoints.imports as imports_endpoint
from app.models.audit import AuditEvent
from app.models.governance import User
from app.models.lecturer import Lecturer
from app.models.scopus_import import ScopusImport
from app.services import scopus_import_service


def _create_user(*, role: str = "ADMIN", lecturer_id: uuid.UUID | None = None, display_name: str = "Admin User") -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.lower()}@test.invalid",
        password_hash="x",
        display_name=display_name,
        role=role,
        lecturer_id=lecturer_id,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _create_lecturer(*, full_name: str, email: str | None = None, staff_code: str | None = None) -> Lecturer:
    return Lecturer(
        id=uuid.uuid4(),
        full_name=full_name,
        full_name_normalized=full_name.lower(),
        institutional_email=email,
        staff_code=staff_code,
        academic_degree="Thạc sĩ",
        academic_rank="GVC",
        position="Giảng viên",
        faculty="Khoa CNTT",
        department="Bộ môn KHMT",
        orcid=None,
        is_active=True,
        version=1,
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


# =============================================================================
# 1. LECTURER MASTER LIST & ACCOUNT LINKAGE TESTS
# =============================================================================


def test_lecturer_list_returns_master_lecturers_with_accounts(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    lec1 = _create_lecturer(full_name="Nguyễn Văn A", email="nva@ictu.edu.vn", staff_code="CB01")
    lec2 = _create_lecturer(full_name="Trần Thị B", email="ttb@ictu.edu.vn", staff_code="CB02")
    user_for_lec1 = _create_user(role="LECTURER", lecturer_id=lec1.id, display_name="Nguyễn Văn A")

    # Keep the account version intentionally different from the lecturer version:
    # account actions must use the version of the User aggregate.
    user_for_lec1.version = 7

    # Mock db queries for Lecturer and User
    def mock_query(model: Any) -> MagicMock:
        chain = MagicMock()
        if model == Lecturer:
            chain.filter.return_value = chain
            chain.scalar.return_value = 2
            chain.all.return_value = [lec1, lec2]
            chain.offset.return_value = chain
            chain.limit.return_value = chain
            chain.order_by.return_value = chain
        elif model == User:
            chain.filter.return_value = chain
            chain.all.return_value = [user_for_lec1, admin]
        return chain

    mock_db.query.side_effect = mock_query
    mock_db.scalar.side_effect = [2, 1, 0]

    response = client.get("/api/v1/lecturers")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Lec 1 has linked account
    item1 = next(item for item in data["items"] if item["id"] == str(lec1.id))
    assert item1["full_name"] == "Nguyễn Văn A"
    assert item1["account"] is not None
    assert item1["account"]["email"] == user_for_lec1.email
    assert item1["account"]["role"] == "LECTURER"
    assert item1["account"]["version"] == 7
    assert item1["version"] == lec1.version

    # Lec 2 has NO linked account
    item2 = next(item for item in data["items"] if item["id"] == str(lec2.id))
    assert item2["full_name"] == "Trần Thị B"
    assert item2["account"] is None


def test_system_user_without_lecturer_id_does_not_appear_on_lecturers_list(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    admin = _create_user(role="ADMIN", lecturer_id=None)
    app.dependency_overrides[get_current_user] = lambda: admin

    lec = _create_lecturer(full_name="Lê Văn C", email="lvc@ictu.edu.vn")

    def mock_query(model: Any) -> MagicMock:
        chain = MagicMock()
        if model == Lecturer:
            chain.filter.return_value = chain
            chain.scalar.return_value = 1
            chain.all.return_value = [lec]
            chain.offset.return_value = chain
            chain.limit.return_value = chain
            chain.order_by.return_value = chain
        elif model == User:
            # _get_lecturer_stats queries: db.query(User).filter(User.lecturer_id.is_not(None))
            # The mock chain (.filter.return_value = chain) means:
            #   mock_db.query(User).filter(...).all() → chain.all() → [admin]
            # but chain.all.return_value = [] (no linked users in this test)
            chain.filter.return_value = chain
            chain.all.return_value = [admin]
        return chain

    mock_db.query.side_effect = mock_query
    # _get_lecturer_stats calls db.scalar(...) which must return int, not MagicMock
    mock_db.scalar.return_value = 1

    response = client.get("/api/v1/lecturers")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(lec.id)
    # Admin is not returned as a lecturer
    assert not any(item["id"] == str(admin.id) for item in items)


def test_lecturer_stats_reflects_master_data(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    lec1 = _create_lecturer(full_name="Lec 1")
    lec2 = _create_lecturer(full_name="Lec 2")
    user_active = _create_user(role="LECTURER", lecturer_id=lec1.id)

    def mock_query(model: Any) -> MagicMock:
        chain = MagicMock()
        if model == Lecturer:
            chain.filter.return_value = chain
            chain.scalar.return_value = 2
            chain.all.return_value = [lec1, lec2]
            chain.offset.return_value = chain
            chain.limit.return_value = chain
            chain.order_by.return_value = chain
        elif model == User:
            chain.filter.return_value = chain
            chain.all.return_value = [user_active]
        return chain

    mock_db.query.side_effect = mock_query
    # _get_lecturer_stats calls db.scalar() three times sequentially:
    # 1. count(Lecturer.id) -> total_lecturers (expects 2)
    # 2. count(User.active) -> linked_active (expects 1)
    # 3. count(User.locked) -> linked_locked (expects 0)
    mock_db.scalar.side_effect = [2, 1, 0]

    response = client.get("/api/v1/lecturers")
    assert response.status_code == 200
    stats = response.json().get("stats")
    assert stats is not None
    assert stats["total_lecturers"] == 2
    assert stats["account_linked"] == 1
    assert stats["account_not_linked"] == 1
    assert stats["account_locked"] == 0


# =============================================================================
# 2. UNIFIED IMPORT HISTORY TESTS
# =============================================================================


def test_unified_import_history_combines_scopus_and_lecturer_json(
    client: TestClient,
    mock_db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _create_user(role="ADMIN", display_name="Admin User")
    app.dependency_overrides[get_current_user] = lambda: admin

    now = datetime.now(UTC)
    scopus_job = ScopusImport(
        id=uuid.uuid4(),
        file_name="scopus_publications.csv",
        status="STAGED",
        total_records=50,
        valid_records=50,
        invalid_records=0,
        version=1,
        created_at=now,
        updated_at=now,
    )

    audit_ev = AuditEvent(
        id=uuid.uuid4(),
        entity_type="lecturer_dataset",
        entity_id=uuid.uuid4(),
        action="LECTURER_DATASET_IMPORTED",
        actor_user_id=admin.id,
        event_metadata={
            "filename": "ictu_lecturers.json",
            "total": 410,
            "created": 401,
            "updated": 9,
            "unchanged": 0,
            "conflicts": 0,
            "warnings": 9,
        },
        created_at=now,
    )
    # Required by _actor_names: scopus import actor lookup
    scopus_started_audit = AuditEvent(
        id=uuid.uuid4(),
        entity_type="scopus_imports",
        entity_id=scopus_job.id,
        action="SCOPUS_IMPORT_STARTED",
        actor_user_id=admin.id,
        event_metadata={},
        created_at=now,
    )

    # Track AuditEvent calls separately to return the correct mock per call.
    # Sequence in list_imports:
    #   call 1: _actor_names AuditEvent → [scopus_started_audit]
    #   call 2: lecturer_audits          → [audit_ev]
    #   call 3: rolled_back_audits        → []
    #   call 4: hidden_history_audits    → []
    _audit_call_count = [0]

    def mock_query(model: Any) -> MagicMock:
        chain = MagicMock()
        if model == ScopusImport:
            chain.order_by.return_value = chain
            chain.all.return_value = [scopus_job]
            chain.filter.return_value = chain
            chain.limit.return_value = chain
        elif model == AuditEvent:
            _audit_call_count[0] += 1
            call_n = _audit_call_count[0]
            chain.filter.return_value = chain
            chain.order_by.return_value = chain
            chain.limit.return_value = chain
            if call_n == 1:
                # _actor_names: SCOPUS_IMPORT_STARTED audit
                chain.all.return_value = [scopus_started_audit]
            elif call_n == 2:
                # lecturer_audits
                chain.all.return_value = [audit_ev]
            else:
                chain.all.return_value = []
        elif model == User:
            chain.filter.return_value = chain
            chain.all.side_effect = lambda: [admin]
            chain.first.return_value = admin
        return chain

    mock_db.query.side_effect = mock_query

    response = client.get("/api/v1/imports")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2

    # Check Scopus item
    scopus_item = next(item for item in data["items"] if item["type"] == "SCOPUS")
    assert scopus_item["file_name"] == "scopus_publications.csv"
    assert scopus_item["total_records"] == 50
    assert scopus_item["performed_by"] == "Admin User"
    assert scopus_item["can_delete"] is True

    # Check Lecturer item
    lecturer_item = next(item for item in data["items"] if item["type"] == "LECTURERS")
    assert lecturer_item["file_name"] == "ictu_lecturers.json"
    assert lecturer_item["total_records"] == 410
    assert lecturer_item["imported_records"] == 410
    assert lecturer_item["lecturer_summary"]["warnings"] == 9
    assert lecturer_item["can_delete"] is False


def test_unified_import_stats_reflects_both_sources(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    now = datetime.now(UTC)
    scopus_job = ScopusImport(
        id=uuid.uuid4(),
        file_name="scopus.csv",
        status="APPLIED",
        total_records=20,
        valid_records=20,
        invalid_records=0,
        version=1,
        created_at=now,
        updated_at=now,
    )
    audit_ev = AuditEvent(
        id=uuid.uuid4(),
        entity_type="lecturer_dataset",
        entity_id=uuid.uuid4(),
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={"filename": "lecturers.json", "total": 10, "created": 10},
        created_at=now,
    )

    # Track AuditEvent calls separately to return the correct mock per call.
    # Sequence in list_imports:
    #   call 1: _actor_names AuditEvent → []
    #   call 2: lecturer_audits          → [audit_ev]
    #   call 3: rolled_back_audits        → []
    #   call 4: hidden_history_audits    → []
    _audit_call_count = [0]

    def mock_query(model: Any) -> MagicMock:
        chain = MagicMock()
        if model == ScopusImport:
            chain.order_by.return_value = chain
            chain.all.return_value = [scopus_job]
            chain.filter.return_value = chain
            chain.limit.return_value = chain
        elif model == AuditEvent:
            _audit_call_count[0] += 1
            call_n = _audit_call_count[0]
            chain.filter.return_value = chain
            chain.order_by.return_value = chain
            chain.limit.return_value = chain
            # lecturer_audits = 2nd AuditEvent call
            chain.all.return_value = [audit_ev] if call_n == 2 else []
        elif model == User:
            chain.filter.return_value = chain
            chain.all.side_effect = lambda: [admin]
            chain.first.return_value = admin
        return chain

    mock_db.query.side_effect = mock_query

    response = client.get("/api/v1/imports/history")
    assert response.status_code == 200
    stats = response.json().get("stats")
    assert stats is not None
    assert stats["total_imports"] == 2
    assert stats["success_count"] == 2
    assert stats["processing_count"] == 0
    assert stats["failed_count"] == 0


# =============================================================================
# 3. SAFE DELETE IMPORT TESTS
# =============================================================================


def test_delete_scopus_import_non_admin_forbidden(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    lecturer_user = _create_user(role="LECTURER")
    app.dependency_overrides[get_current_user] = lambda: lecturer_user

    import_id = uuid.uuid4()
    response = client.delete(f"/api/v1/imports/{import_id}")
    assert response.status_code == 403


def test_delete_scopus_import_in_use_rejected_with_409(
    client: TestClient,
    mock_db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    import_id = uuid.uuid4()
    monkeypatch.setattr(
        scopus_import_service,
        "delete_scopus_import",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            scopus_import_service.ImportInUseError("Import is referenced downstream")
        ),
    )

    response = client.delete(f"/api/v1/imports/{import_id}")
    assert response.status_code == 409
    assert response.json()["code"] == "IMPORT_IN_USE"


def test_delete_scopus_import_safe_success(
    client: TestClient,
    mock_db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    import_id = uuid.uuid4()
    called = []

    def mock_delete(*_args, **_kwargs):
        called.append(True)
        return True

    # Patch in both the endpoint module (where it's referenced) and the
    # service module.  Without patching in imports_endpoint, the reference
    # captured at import-time in that module still points to the real function.
    monkeypatch.setattr(imports_endpoint, "delete_scopus_import", mock_delete)
    monkeypatch.setattr(scopus_import_service, "delete_scopus_import", mock_delete)

    response = client.delete(f"/api/v1/imports/{import_id}")
    assert response.status_code == 200, response.json()
    assert response.json()["deleted"] is True
    assert called == [True]


def test_delete_lecturer_import_success(
    client: TestClient,
    mock_db: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    import_id = uuid.uuid4()
    called = []

    def mock_delete(*_args, **_kwargs):
        called.append(True)
        return True

    monkeypatch.setattr(imports_endpoint, "delete_scopus_import", mock_delete)
    monkeypatch.setattr(scopus_import_service, "delete_scopus_import", mock_delete)

    response = client.delete(f"/api/v1/imports/{import_id}")
    assert response.status_code == 200, response.json()
    assert response.json()["deleted"] is True
    assert called == [True]


# =============================================================================
# 4. SORTING & ACADEMIC RANK/DEGREE TESTS
# =============================================================================


def test_lecturer_sorting_abnormal_and_academic_priority(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    # 1. GS normal
    lec_gs = _create_lecturer(full_name="GS. Phạm Văn A")
    lec_gs.academic_rank = "GS"
    lec_gs.academic_degree = "TS"

    # 2. PGS normal
    lec_pgs = _create_lecturer(full_name="PGS. Lê Văn B")
    lec_pgs.academic_rank = "PGS"
    lec_pgs.academic_degree = "TS"

    # 3. TS normal
    lec_ts = _create_lecturer(full_name="TS. Hoàng Văn C")
    lec_ts.academic_rank = None
    lec_ts.academic_degree = "TS"

    # 4. ThS normal
    lec_ths = _create_lecturer(full_name="ThS. Vũ Thị D")
    lec_ths.academic_rank = None
    lec_ths.academic_degree = "ThS"

    # 5. Cử nhân with LOCKED account -> Priority 1 (above all normal)
    lec_locked = _create_lecturer(full_name="CN. Đỗ Văn E")
    lec_locked.academic_rank = None
    lec_locked.academic_degree = "Cử nhân"
    user_locked = _create_user(role="LECTURER", lecturer_id=lec_locked.id)
    user_locked.is_active = False

    # 6 & 7. Duplicate candidates -> Priority 0 (above locked and normal)
    lec_warn1 = _create_lecturer(full_name="ĐH. Nguyễn Văn F", email="f1@ictu.edu.vn")
    lec_warn1.academic_degree = "ĐH"
    lec_warn2 = _create_lecturer(full_name="ThS. Nguyễn Văn F", email="f2@ictu.edu.vn")
    lec_warn2.academic_degree = "ThS"

    all_lecturers = [lec_gs, lec_pgs, lec_ts, lec_ths, lec_locked, lec_warn1, lec_warn2]

    def mock_query(model: Any) -> MagicMock:
        chain = MagicMock()
        if model == Lecturer:
            chain.all.return_value = all_lecturers
        elif model == User:
            chain.filter.return_value = chain
            chain.all.return_value = [user_locked, admin]
        return chain

    mock_db.query.side_effect = mock_query
    # _get_lecturer_stats calls db.scalar(...) which must return int, not MagicMock
    mock_db.scalar.return_value = 7

    # Also mock execute for select(Lecturer.id, ...)
    mock_db.execute.return_value.all.return_value = [
        (l.id, l.full_name, l.full_name_normalized) for l in all_lecturers
    ]

    response = client.get("/api/v1/lecturers?page=1&page_size=20")
    assert response.status_code == 200
    items = response.json()["items"]
    ids_in_order = [item["id"] for item in items]

    # Verify priority:
    # First items must be the duplicate warnings (lec_warn1, lec_warn2)
    assert ids_in_order[0] in (str(lec_warn1.id), str(lec_warn2.id))
    assert ids_in_order[1] in (str(lec_warn1.id), str(lec_warn2.id))

    # Next must be the locked account
    assert ids_in_order[2] == str(lec_locked.id)

    # Next must follow academic hierarchy: GS -> PGS -> TS -> ThS
    assert ids_in_order[3] == str(lec_gs.id)
    assert ids_in_order[4] == str(lec_pgs.id)
    assert ids_in_order[5] == str(lec_ts.id)
    assert ids_in_order[6] == str(lec_ths.id)


# =============================================================================
# 5. JSON EXPORT & SECURITY EXCLUSION TESTS
# =============================================================================


def test_export_lecturers_json_admin_success(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    lec = _create_lecturer(
        full_name="GS. TS. Nguyễn Văn A",
        email="nva@ictu.edu.vn",
        staff_code="CB001",
    )
    lec.academic_rank = "GS"
    lec.academic_degree = "TS"
    lec.faculty = "Khoa CNTT"
    lec.department = "Khoa học máy tính"

    mock_db.execute.return_value.scalars.return_value.all.return_value = [lec]

    response = client.get("/api/v1/lecturers/export")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert "attachment; filename=" in response.headers["content-disposition"]

    data = response.json()
    assert "dataset" in data
    assert data["dataset"]["schema_version"] == "1.0"
    assert data["dataset"]["record_count"] == 1
    assert len(data["lecturers"]) == 1

    item = data["lecturers"][0]
    assert item["full_name"] == "GS. TS. Nguyễn Văn A"
    assert item["institutional_email"] == "nva@ictu.edu.vn"
    assert item["staff_code"] == "CB001"
    assert item["academic_rank"] == "GS"
    assert item["academic_degree"] == "TS"

    # Security check: User account and auth fields MUST NOT exist
    assert "password_hash" not in item
    assert "auth_version" not in item
    assert "user_id" not in item
    assert "role" not in item
    assert "jwt" not in item

    # Round-trip check with dataset parser
    from app.services.lecturer_dataset.parser import parse_and_validate
    envelope = parse_and_validate(response.content, filename="test_export.json")
    assert envelope["dataset"]["schema_version"] == "1.0"
    assert len(envelope["lecturers"]) == 1


def test_export_lecturers_json_forbidden_for_non_admin(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    lecturer_user = _create_user(role="LECTURER")
    app.dependency_overrides[get_current_user] = lambda: lecturer_user

    response = client.get("/api/v1/lecturers/export")
    assert response.status_code == 403


# =============================================================================
# 6. SAFE DELETE & DEPENDENCY PROTECTION TESTS
# =============================================================================


def test_delete_lecturer_blocked_when_linked_to_user_account(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    lec = _create_lecturer(full_name="Nguyễn Văn A")
    user = _create_user(role="LECTURER", lecturer_id=lec.id)

    def mock_query(model: Any) -> MagicMock:
        chain = MagicMock()
        if model == Lecturer:
            chain.filter.return_value.first.return_value = lec
        elif model == User:
            chain.filter.return_value.first.return_value = user
        return chain

    mock_db.query.side_effect = mock_query

    response = client.delete(f"/api/v1/lecturers/{lec.id}")
    assert response.status_code == 409
    assert response.json()["code"] == "LECTURER_IN_USE"
    assert "tài khoản người dùng" in response.json()["detail"]
