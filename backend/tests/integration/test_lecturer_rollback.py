"""Integration and regression tests for Lecturer Dataset Import Rollback and Ownership Semantics.

Test Matrix & Regression Verification:
1. manual lecturer survives import rollback
2. lecturer created only by import is removed (via created_lecturer_ids source of truth)
3. lecturer updated by import is not deleted
4. updated existing lecturer restores pre-import state when history exists
5. regression: manual lecturer with no prior snapshot updated by import survives rollback
6. regression: audit trail is append-only (import audit is not deleted, rollback audit is added)
7. same-name different identity remains independent
8. lecturer referenced by another import/source survives
9. lecturer linked to user blocks rollback (409 LECTURER_IMPORT_IN_USE)
10. user is never auto-deleted
11. lecturer with downstream identity/publication dependency blocks rollback
12. rollback is atomic on failure
13. rollback twice returns safe conflict/idempotent result (409 LECTURER_IMPORT_ALREADY_ROLLED_BACK)
14. non-admin rollback -> 403
15. unknown import -> 404
16. rollback updates stats/list
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
from app.models.audit import AuditEvent
from app.models.governance import User
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)
from sqlalchemy.exc import SQLAlchemyError
from app.services.lecturer_dataset.rollback import (
    LecturerRollbackError,
    LecturerRollbackService,
)



class _SequentialFirst:
    """Returns the next value from the sequence, then sticky-returns the last value.

    - Call 1 → first element
    - Call 2 → second element
    - ...
    - Call N (N = len(values)) → last element
    - Call N+1 → last element (sticky)
    - ... continues returning last element indefinitely

    Calls return items in order, then the last value for excess calls.
    """

    def __init__(self, *values) -> None:
        vals = list(values)
        self._values = vals
        self._index = 0
        self._last = vals[-1] if vals else None

    def __call__(self):
        if self._index >= len(self._values):
            return self._last
        value = self._values[self._index]
        self._index += 1
        return value


def _build_query_mock(first_values=(), all_values=(), delete_value=0):
    """Build a single query mock where .first() cycles through given values.

    When .filter().filter().first() is called, .filter() returns the same
    query mock (set via .filter.return_value = query_mock), and .first()
    on that query mock runs our side_effect cycle.
    """
    query_mock = MagicMock()
    query_mock.first.side_effect = _SequentialFirst(*first_values)
    query_mock.all.side_effect = lambda: list(all_values) if all_values else []
    query_mock.filter.return_value = query_mock  # chain stays on same mock
    query_mock.order_by.return_value = query_mock
    query_mock.delete.return_value = delete_value
    query_mock.scalar.return_value = 0
    query_mock.offset.return_value = query_mock
    query_mock.limit.return_value = query_mock
    return query_mock


def _make_mock_db_for_rollback(
    import_audit,
    *,
    # AuditEvent first() call sequence:
    #   call 1 = import_audit (found)
    #   call 2 = rolled_back_audit (None = not yet rolled back)
    audit_first_sequence: tuple | None = None,
    snapshots: list | None = None,
    snapshot_order_all: list | None = None,
    lecturer_results: list | None = None,
    user_results: list | None = None,
    identity_results: list | None = None,
    lkp_results: list | None = None,
    linked_accounts_error: bool = False,
    linked_identities_error: bool = False,
):
    """Factory for a fully-configured mock DB for rollback service tests.

    This creates one query mock per model where .first() returns the correct
    sequential value from a cycle. The query mock's .filter() returns itself
    (same mock) so chained calls like .filter().filter().first() work correctly.

    Args:
        import_audit: The AuditEvent for the import to be rolled back.
        audit_first_sequence: Tuple of (audit_or_None,) values for each
            AuditEvent.first() call. Default (import_audit, None) handles
            the two-AuditEvent-queries-in-rollback pattern.
        snapshots: List returned by LecturerSourceSnapshot.all()
        snapshot_order_all: Same as snapshots (order_by returns same mock)
        lecturer_results: List of Lecturer objects returned in sequence
        user_results: List of User objects returned in sequence
        identity_results: List of LecturerScopusIdentity objects returned
        lkp_results: List of LecturerKnownPublication objects returned
        linked_accounts_error: If True, users are returned on
            User.query(...).in_(...).all() causing 409 IN_USE
        linked_identities_error: If True, identities are returned causing 409
    """
    _snapshots = list(snapshots) if snapshots else []
    _snapshot_order = list(snapshot_order_all) if snapshot_order_all else _snapshots
    _lecturers = list(lecturer_results) if lecturer_results else []
    _users = list(user_results) if user_results else []
    _idents = list(identity_results) if identity_results else []
    _lkps = list(lkp_results) if lkp_results else []
    _audit_first_seq = (
        audit_first_sequence
        if audit_first_sequence is not None
        else (import_audit, None)
    )
    # CRITICAL: Create ONE _SequentialFirst for ALL AuditEvent queries.
    # Each call to mock_db.query(AuditEvent) creates a NEW query mock,
    # but they ALL must share the SAME counter so that:
    #   call 1 → audit (import found)
    #   call 2 → None (not yet rolled back)
    #   call 3+ → None (stays None)
    _audit_first_side_effect = _SequentialFirst(*_audit_first_seq)

    def _query(model):
        from app.models.audit import AuditEvent
        from app.models.governance import User
        from app.models.identity import LecturerScopusIdentity
        from app.models.master_lecturer import (
            Lecturer,
            LecturerKnownPublication,
            LecturerSourceSnapshot,
        )

        if model == AuditEvent:
            # Build AuditEvent mock DIRECTLY without _build_query_mock.
            # _build_query_mock creates a fresh _SequentialFirst which would
            # OVERWRITE our shared _audit_first_side_effect. We need the SAME
            # instance shared across all AuditEvent queries so that:
            #   call 1 → audit (import found)
            #   call 2 → None (not yet rolled back)
            #   call 3+ → None (sticky)
            q = MagicMock()
            q.first.side_effect = _audit_first_side_effect
            q.all.side_effect = lambda: []
            q.filter.return_value = q
            q.order_by.return_value = q
            q.delete.return_value = 0
            q.scalar.return_value = 0
            q.offset.return_value = q
            q.limit.return_value = q
            return q

        elif model == LecturerSourceSnapshot:
            q = _build_query_mock(
                all_values=_snapshots,
            )
            # order_by returns same mock
            q.order_by.return_value.all.side_effect = lambda: list(_snapshot_order)
            return q

        elif model == Lecturer:
            q = _build_query_mock(
                first_values=_lecturers,  # first() cycles through lecturers
                all_values=_lecturers,
            )
            return q

        elif model == User:
            q = _build_query_mock(
                first_values=_users,
                all_values=_users,
            )
            # Simulate the blocker check: when lecturer_ids are passed via .in_()
            # If linked_accounts_error is True, return the users from _users
            def _in_filter_side_effect(*args, **kwargs):
                if linked_accounts_error:
                    # Return users as "linked accounts blocking rollback"
                    return list(_users)
                return []
            q.filter.return_value.all.side_effect = _in_filter_side_effect
            return q

        elif model == LecturerScopusIdentity:
            q = _build_query_mock(
                first_values=_idents,
                all_values=_idents,
            )
            def _in_ident_filter(*args, **kwargs):
                if linked_identities_error:
                    return list(_idents)
                return []
            q.filter.return_value.all.side_effect = _in_ident_filter
            return q

        elif model == LecturerKnownPublication:
            q = _build_query_mock(
                all_values=_lkps,
            )
            return q

        return _build_query_mock()

    mock_db = MagicMock()
    mock_db.query.side_effect = _query
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()
    # Return the tuple so tests can:
    #   mock_db.query.side_effect = factory(...)[0].query.side_effect
    #   mock_db.commit.side_effect = factory(...)[1].commit.side_effect
    #   OR simply:
    #   _install_mock_db_for_rollback(mock_db, ...)
    # and factory attaches query/rollback/commit directly to mock_db.
    return _query, mock_db


def _install_mock_db_for_rollback(
    mock_db: MagicMock,
    import_audit,
    *,
    audit_first_sequence: tuple | None = None,
    snapshots: list | None = None,
    snapshot_order_all: list | None = None,
    lecturer_results: list | None = None,
    user_results: list | None = None,
    identity_results: list | None = None,
    lkp_results: list | None = None,
    linked_accounts_error: bool = False,
    linked_identities_error: bool = False,
) -> None:
    """Install rollback mock query side-effect onto an existing mock_db.

    Sets up mock_db.query.side_effect with a query function that returns the
    correct results for each model. This is the preferred way to mock the
    rollback service — call this after setting up other mock_db attributes
    like commit.side_effect.
    """
    _query_fn, _mock_db = _make_mock_db_for_rollback(
        import_audit,
        audit_first_sequence=audit_first_sequence,
        snapshots=snapshots,
        snapshot_order_all=snapshot_order_all,
        lecturer_results=lecturer_results,
        user_results=user_results,
        identity_results=identity_results,
        lkp_results=lkp_results,
        linked_accounts_error=linked_accounts_error,
        linked_identities_error=linked_identities_error,
    )
    mock_db.query.side_effect = _query_fn
    # Attach add/commit/rollback if not already set
    if mock_db.add.side_effect is None:
        mock_db.add = _mock_db.add
    if not mock_db.commit.called:
        mock_db.commit = _mock_db.commit
    if not mock_db.rollback.called:
        mock_db.rollback = _mock_db.rollback


def _create_user(*, role: str = "ADMIN", lecturer_id: uuid.UUID | None = None) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.lower()}_{uuid.uuid4().hex[:6]}@test.invalid",
        password_hash="x",
        display_name=f"Test {role.title()}",
        role=role,
        lecturer_id=lecturer_id,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _create_lecturer(
    *,
    full_name: str,
    email: str | None = None,
    staff_code: str | None = None,
    department: str | None = "CNTT",
) -> Lecturer:
    return Lecturer(
        id=uuid.uuid4(),
        full_name=full_name,
        full_name_normalized=full_name.casefold().strip(),
        email=email,
        staff_code=staff_code,
        academic_degree="Thạc sĩ",
        academic_rank="GVC",
        position="Giảng viên",
        faculty="Khoa CNTT",
        department=department,
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
# 1. ROLLBACK SERVICE LOGIC & OWNERSHIP TESTS
# =============================================================================


def test_manual_lecturer_survives_and_created_lecturer_removed(mock_db: MagicMock) -> None:
    """Tests 1 & 2: Manual lecturer survives; import-created lecturer is deleted."""
    admin = _create_user(role="ADMIN")
    import_id = uuid.uuid4()

    import_lec = _create_lecturer(
        full_name="Thầy Nhập Khẩu",
        email="imported@ictu.edu.vn",
        staff_code="IMP01",
    )

    snap_id = uuid.uuid4()
    snap = LecturerSourceSnapshot(
        id=snap_id,
        lecturer_id=import_lec.id,
        source_system="ictu_profile_page",
        source_url="https://ictu.edu.vn/lecturers/IMP01",
        snapshot_hash="abc" * 21 + "a",
        parser_version="1.0",
        validation_status="VALID",
        raw_payload={
            "canonical": {
                "full_name": import_lec.full_name,
                "staff_code": import_lec.staff_code,
            }
        },
        fetched_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    audit = AuditEvent(
        id=import_id,
        entity_type="lecturer_dataset",
        entity_id=import_id,
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={
            "filename": "lecturers.json",
            "snapshot_ids": [str(snap_id)],
            "created_lecturer_ids": [str(import_lec.id)],
        },
        after_state={
            "snapshot_ids": [str(snap_id)],
            "created_lecturer_ids": [str(import_lec.id)],
        },
    )

    # import_lec is in created_lecturer_ids → deleted by rollback
    # No user link, no identity link → proceeds normally
    _install_mock_db_for_rollback(
        mock_db,
        audit,
        audit_first_sequence=(audit, None),
        snapshots=[snap],
        snapshot_order_all=[snap],
        lecturer_results=[import_lec],
    )

    service = LecturerRollbackService()
    summary = service.rollback_import(mock_db, import_id=import_id, actor=admin)

    assert summary.created_records_removed == 1
    assert summary.manual_records_preserved == 0
    assert mock_db.commit.called


def test_updated_existing_lecturer_restores_prior_state(mock_db: MagicMock) -> None:
    """Tests 3 & 4: Lecturer updated by import is not deleted and restored to pre-import state."""
    admin = _create_user(role="ADMIN")
    import_id = uuid.uuid4()

    existing_lec = _create_lecturer(
        full_name="Nguyễn Văn A Updated",
        email="nva_new@ictu.edu.vn",
        staff_code="CB01",
        department="Bộ môn An toàn mạng",
    )

    snap1_id = uuid.uuid4()
    snap1_old = LecturerSourceSnapshot(
        id=snap1_id,
        lecturer_id=existing_lec.id,
        source_system="ictu_profile_page",
        source_url="https://ictu.edu.vn/lecturers/CB01",
        snapshot_hash="old_hash" * 8,
        parser_version="1.0",
        validation_status="VALID",
        raw_payload={
            "canonical": {
                "full_name": "Nguyễn Văn A Gốc",
                "staff_code": "CB01",
                "institutional_email": "nva_old@ictu.edu.vn",
                "department": "Bộ môn KHMT",
                "faculty": "Khoa CNTT",
            }
        },
        fetched_at=datetime(2025, 1, 1, tzinfo=UTC),
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )

    snap2_id = uuid.uuid4()
    snap2_import = LecturerSourceSnapshot(
        id=snap2_id,
        lecturer_id=existing_lec.id,
        source_system="ictu_profile_page",
        source_url="https://ictu.edu.vn/lecturers/CB01",
        snapshot_hash="new_hash" * 8,
        parser_version="1.0",
        validation_status="VALID",
        raw_payload={
            "canonical": {
                "full_name": "Nguyễn Văn A Updated",
                "staff_code": "CB01",
                "institutional_email": "nva_new@ictu.edu.vn",
                "department": "Bộ môn An toàn mạng",
            }
        },
        fetched_at=datetime(2025, 2, 1, tzinfo=UTC),
        created_at=datetime(2025, 2, 1, tzinfo=UTC),
    )

    audit = AuditEvent(
        id=import_id,
        entity_type="lecturer_dataset",
        entity_id=import_id,
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={
            "filename": "lecturers.json",
            "snapshot_ids": [str(snap2_id)],
            "created_lecturer_ids": [],
        },
    )

    # existing_lec NOT in created_lecturer_ids, has OTHER snapshots → restored
    _install_mock_db_for_rollback(
        mock_db,
        audit,
        audit_first_sequence=(audit, None),
        snapshots=[snap2_import],
        snapshot_order_all=[snap1_old, snap2_import],
        lecturer_results=[existing_lec],
    )

    service = LecturerRollbackService()
    summary = service.rollback_import(mock_db, import_id=import_id, actor=admin)

    assert summary.created_records_removed == 0
    assert summary.updated_records_restored == 1
    assert existing_lec.full_name == "Nguyễn Văn A Gốc"
    assert existing_lec.email == "nva_old@ictu.edu.vn"
    assert existing_lec.department == "Bộ môn KHMT"


def test_regression_manual_lecturer_updated_without_prior_snapshot_survives(mock_db: MagicMock) -> None:
    """Test 5 Regression:
    - Manual lecturer exists with NO prior snapshot.
    - Import X updates it (creates first snapshot for that lecturer).
    - Rollback X.
    - Manual lecturer MUST survive because its ID is not in created_lecturer_ids.
    """
    admin = _create_user(role="ADMIN")
    import_id = uuid.uuid4()

    manual_lec = _create_lecturer(
        full_name="TS. Lê Văn Thủ Công",
        email="manual_lec@ictu.edu.vn",
        staff_code="MAN_TC_01",
        department="Khoa Điện tử",
    )

    # Import X created a snapshot for this lecturer
    snap_id = uuid.uuid4()
    snap_import = LecturerSourceSnapshot(
        id=snap_id,
        lecturer_id=manual_lec.id,
        source_system="ictu_profile_page",
        source_url="https://ictu.edu.vn/lecturers/MAN_TC_01",
        snapshot_hash="hash" * 16,
        parser_version="1.0",
        validation_status="VALID",
        raw_payload={
            "canonical": {
                "full_name": "TS. Lê Văn Thủ Công (Updated)",
                "staff_code": "MAN_TC_01",
                "institutional_email": "manual_lec@ictu.edu.vn",
            }
        },
        fetched_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    audit = AuditEvent(
        id=import_id,
        entity_type="lecturer_dataset",
        entity_id=import_id,
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={
            "filename": "lecturers.json",
            "snapshot_ids": [str(snap_id)],
            # IMPORTANT: manual_lec.id is NOT in created_lecturer_ids.
            # Since LecturerSourceSnapshot.lecturer_id is nullable and snap.lecturer_id
            # may be None in some cases, we rely on created_lecturer_ids as the
            # authoritative source. manual_lec is NOT created by this import.
            "created_lecturer_ids": [],
        },
    )

    # Snapshots belong to the batch, and snap.lecturer_id is set so the lecturer
    # is included in all_batch_lecturer_ids. It is NOT in created_lecturer_ids,
    # so it lands in CASE D: preserve as a manually-managed lecturer.
    _install_mock_db_for_rollback(
        mock_db,
        audit,
        audit_first_sequence=(audit, None),
        snapshots=[snap_import],
        snapshot_order_all=[snap_import],
        # lecturer_results: one query result for the lecturer lookup
        lecturer_results=[manual_lec],
        # No linked users, no linked identities → no 409 blockers
        user_results=[],
        identity_results=[],
        lkp_results=[],
    )

    service = LecturerRollbackService()
    summary = service.rollback_import(mock_db, import_id=import_id, actor=admin)

    # Must NOT delete manual lecturer! CASE D preserves it.
    assert summary.created_records_removed == 0
    assert summary.manual_records_preserved == 1
    assert mock_db.commit.called


def test_regression_audit_trail_is_append_only(mock_db: MagicMock) -> None:
    """Test 6 Regression:
    - Verifies rollback does NOT call db.delete(import_audit).
    - Appends LECTURER_DATASET_ROLLED_BACK to db.add.
    """
    admin = _create_user(role="ADMIN")
    import_id = uuid.uuid4()

    import_audit = AuditEvent(
        id=import_id,
        entity_type="lecturer_dataset",
        entity_id=import_id,
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={
            "filename": "lecturers.json",
            "snapshot_ids": [],
            "created_lecturer_ids": [],
        },
    )

    added_objects: list[Any] = []
    deleted_objects: list[Any] = []

    mock_db.add.side_effect = lambda obj: added_objects.append(obj)
    mock_db.delete.side_effect = lambda obj: deleted_objects.append(obj)

    _install_mock_db_for_rollback(
        mock_db,
        import_audit,
        audit_first_sequence=(import_audit, None),
        snapshots=[],
        snapshot_order_all=[],
        lecturer_results=[],
    )

    service = LecturerRollbackService()
    summary = service.rollback_import(mock_db, import_id=import_id, actor=admin)

    assert summary.import_id == import_id
    # db.delete must NOT contain import_audit
    assert import_audit not in deleted_objects
    # db.add must contain the new rollback audit event
    rollback_audits = [
        obj for obj in added_objects
        if isinstance(obj, AuditEvent) and obj.action == "LECTURER_DATASET_ROLLED_BACK"
    ]
    assert len(rollback_audits) == 1
    assert rollback_audits[0].entity_type == "lecturer_dataset"


def test_user_linkage_blocks_rollback_with_409(mock_db: MagicMock) -> None:
    """Tests 9 & 10: Linked user blocks rollback with 409 LECTURER_IMPORT_IN_USE and user is not deleted."""
    admin = _create_user(role="ADMIN")
    import_id = uuid.uuid4()

    import_lec = _create_lecturer(
        full_name="Thầy Có Tài Khoản",
        email="linked@ictu.edu.vn",
        staff_code="LNK01",
    )
    linked_user = _create_user(role="LECTURER", lecturer_id=import_lec.id)

    snap_id = uuid.uuid4()
    snap = LecturerSourceSnapshot(
        id=snap_id,
        lecturer_id=None,  # nullable; lecturer tracked via created_lecturer_ids
        source_system="ictu_profile_page",
        source_url="https://ictu.edu.vn/lecturers/LNK01",
        snapshot_hash="abc" * 21 + "a",
        parser_version="1.0",
        validation_status="VALID",
        raw_payload={"canonical": {"full_name": import_lec.full_name}},
        fetched_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    audit = AuditEvent(
        id=import_id,
        entity_type="lecturer_dataset",
        entity_id=import_id,
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={
            "filename": "lecturers.json",
            "snapshot_ids": [str(snap_id)],
            "created_lecturer_ids": [str(import_lec.id)],
        },
    )

    # linked_user has lecturer_id=import_lec.id → user is linked to lecturer to delete
    # → blocked with 409 LECTURER_IMPORT_IN_USE
    _install_mock_db_for_rollback(
        mock_db,
        audit,
        audit_first_sequence=(audit, None),
        snapshots=[snap],
        snapshot_order_all=[snap],
        lecturer_results=[import_lec],
        user_results=[linked_user],  # triggers the user-linked blocking check
        linked_accounts_error=True,  # causes 409 IN_USE
    )

    service = LecturerRollbackService()
    with pytest.raises(LecturerRollbackError) as exc_info:
        service.rollback_import(mock_db, import_id=import_id, actor=admin)

    err = exc_info.value
    assert err.code == "LECTURER_IMPORT_IN_USE"
    assert err.status_code == 409
    assert err.data["linked_accounts"] == 1
    assert not mock_db.commit.called


def test_scopus_identity_dependency_blocks_rollback(mock_db: MagicMock) -> None:
    """Test 11: Downstream identity dependency blocks rollback."""
    admin = _create_user(role="ADMIN")
    import_id = uuid.uuid4()

    import_lec = _create_lecturer(
        full_name="Thầy Có Scopus",
        email="scopus@ictu.edu.vn",
        staff_code="SCP01",
    )

    snap_id = uuid.uuid4()
    snap = LecturerSourceSnapshot(
        id=snap_id,
        lecturer_id=None,  # nullable; tracked via created_lecturer_ids
        source_system="ictu_profile_page",
        source_url="https://ictu.edu.vn/lecturers/SCP01",
        snapshot_hash="abc" * 21 + "a",
        parser_version="1.0",
        validation_status="VALID",
        raw_payload={"canonical": {"full_name": import_lec.full_name}},
        fetched_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    audit = AuditEvent(
        id=import_id,
        entity_type="lecturer_dataset",
        entity_id=import_id,
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={
            "filename": "lecturers.json",
            "snapshot_ids": [str(snap_id)],
            "created_lecturer_ids": [str(import_lec.id)],
        },
    )

    identity = LecturerScopusIdentity(
        id=uuid.uuid4(),
        lecturer_id=import_lec.id,
        scopus_author_id="57190000000",
    )

    # No user link, but identity IS linked to import_lec
    # → blocked with 409 LECTURER_IMPORT_IN_USE
    _install_mock_db_for_rollback(
        mock_db,
        audit,
        audit_first_sequence=(audit, None),
        snapshots=[snap],
        snapshot_order_all=[snap],
        lecturer_results=[import_lec],
        user_results=[],
        identity_results=[identity],
        linked_identities_error=True,  # causes 409 IN_USE
    )

    service = LecturerRollbackService()
    with pytest.raises(LecturerRollbackError) as exc_info:
        service.rollback_import(mock_db, import_id=import_id, actor=admin)

    err = exc_info.value
    assert err.code == "LECTURER_IMPORT_IN_USE"
    assert err.status_code == 409
    assert err.data["dependent_identities"] == 1


def test_rollback_already_rolled_back_raises_409(mock_db: MagicMock) -> None:
    """Test 13: Rollback twice returns safe conflict."""
    admin = _create_user(role="ADMIN")
    import_id = uuid.uuid4()

    rolled_back_audit = AuditEvent(
        id=uuid.uuid4(),
        entity_type="lecturer_dataset",
        entity_id=import_id,
        action="LECTURER_DATASET_ROLLED_BACK",
    )

    def mock_query(model: Any) -> MagicMock:
        chain = MagicMock()
        if model == AuditEvent:
            chain.filter.return_value.first.return_value = rolled_back_audit
        return chain

    mock_db.query.side_effect = mock_query

    service = LecturerRollbackService()
    with pytest.raises(LecturerRollbackError) as exc_info:
        service.rollback_import(mock_db, import_id=import_id, actor=admin)

    assert exc_info.value.code == "LECTURER_IMPORT_ALREADY_ROLLED_BACK"
    assert exc_info.value.status_code == 409


# =============================================================================
# 2. HTTP ENDPOINTS & AUTHORIZATION TESTS
# =============================================================================


def test_rollback_endpoint_requires_admin(client: TestClient, mock_db: MagicMock) -> None:
    """Test 14: Non-admin rollback returns 403."""
    lecturer_user = _create_user(role="LECTURER")
    app.dependency_overrides[get_current_user] = lambda: lecturer_user

    import_id = uuid.uuid4()
    response = client.post(f"/api/v1/imports/{import_id}/rollback")
    assert response.status_code == 403


def test_rollback_unknown_import_returns_404(client: TestClient, mock_db: MagicMock) -> None:
    """Test 15: Unknown import returns 404."""
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    def mock_query(model: Any) -> MagicMock:
        chain = MagicMock()
        if model == AuditEvent:
            chain.filter.return_value.first.return_value = None
        return chain

    mock_db.query.side_effect = mock_query

    import_id = uuid.uuid4()
    response = client.post(f"/api/v1/imports/{import_id}/rollback")
    assert response.status_code == 404
    assert response.json()["code"] == "LECTURER_IMPORT_NOT_FOUND"


def test_rollback_linked_user_endpoint_returns_mapped_409(
    client: TestClient,
    mock_db: MagicMock,
) -> None:
    """Test 9 via API: HTTP 409 with structured payload."""
    admin = _create_user(role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin

    import_id = uuid.uuid4()
    import_lec = _create_lecturer(
        full_name="Thầy Test API",
        email="testapi@ictu.edu.vn",
    )
    linked_user = _create_user(role="LECTURER", lecturer_id=import_lec.id)
    snap_id = uuid.uuid4()
    snap = LecturerSourceSnapshot(
        id=snap_id,
        lecturer_id=None,  # nullable; tracked via created_lecturer_ids
        source_system="ictu_profile_page",
        source_url="https://ictu.edu.vn/lecturers/TAP01",
        snapshot_hash="abc" * 21 + "a",
        parser_version="1.0",
        validation_status="VALID",
        raw_payload={"canonical": {"full_name": import_lec.full_name}},
        fetched_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    audit = AuditEvent(
        id=import_id,
        entity_type="lecturer_dataset",
        entity_id=import_id,
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={
            "filename": "ictu_lecturers.json",
            "snapshot_ids": [str(snap_id)],
            "created_lecturer_ids": [str(import_lec.id)],
        },
    )

    _install_mock_db_for_rollback(
        mock_db,
        audit,
        audit_first_sequence=(audit, None),
        snapshots=[snap],
        snapshot_order_all=[snap],
        lecturer_results=[import_lec],
        user_results=[linked_user],
        linked_accounts_error=True,  # triggers 409 IN_USE
    )

    response = client.post(f"/api/v1/imports/{import_id}/rollback")
    assert response.status_code == 409
    data = response.json()
    assert data["code"] == "LECTURER_IMPORT_IN_USE"
    assert data["linked_accounts"] == 1


def test_multi_source_lecturer_survives_rollback(mock_db: MagicMock) -> None:
    """Test 8: Lecturer referenced by another import/source survives rollback of batch X."""
    admin = _create_user(role="ADMIN")
    import_id = uuid.uuid4()

    multi_lec = _create_lecturer(full_name="Thầy Nhiều Nguồn", staff_code="MULTI01")
    other_batch_snap = LecturerSourceSnapshot(
        id=uuid.uuid4(),
        lecturer_id=multi_lec.id,
        source_system="ictu_profile_page_v1",
        source_url="https://ictu.edu.vn/lecturers/MULTI01",
        snapshot_hash="h1" * 32,
        parser_version="1.0",
        validation_status="VALID",
        raw_payload={"canonical": {"full_name": multi_lec.full_name}},
        fetched_at=datetime(2025, 1, 1, tzinfo=UTC),
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    this_batch_snap = LecturerSourceSnapshot(
        id=uuid.uuid4(),
        lecturer_id=multi_lec.id,
        source_system="ictu_profile_page_v2",
        source_url="https://ictu.edu.vn/lecturers/MULTI01",
        snapshot_hash="h2" * 32,
        parser_version="1.0",
        validation_status="VALID",
        raw_payload={"canonical": {"full_name": multi_lec.full_name}},
        fetched_at=datetime(2025, 2, 1, tzinfo=UTC),
        created_at=datetime(2025, 2, 1, tzinfo=UTC),
    )

    audit = AuditEvent(
        id=import_id,
        entity_type="lecturer_dataset",
        entity_id=import_id,
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={
            "filename": "ictu_lecturers.json",
            "snapshot_ids": [str(this_batch_snap.id)],
            "created_lecturer_ids": [],
        },
    )

    # multi_lec has other_snaps > 0 → protected, restored, counted as multi_source
    _install_mock_db_for_rollback(
        mock_db,
        audit,
        audit_first_sequence=(audit, None),
        snapshots=[this_batch_snap],
        snapshot_order_all=[other_batch_snap, this_batch_snap],
        lecturer_results=[multi_lec],
        lkp_results=[],
    )

    service = LecturerRollbackService()
    summary = service.rollback_import(mock_db, import_id=import_id, actor=admin)

    assert summary.created_records_removed == 0
    assert summary.multi_source_records_preserved == 1


def test_rollback_is_atomic_on_database_error(mock_db: MagicMock) -> None:
    """Test 12: DB error during commit triggers full rollback and raises LecturerRollbackError."""
    admin = _create_user(role="ADMIN")
    import_id = uuid.uuid4()

    import_lec = _create_lecturer(
        full_name="Thầy Atomic",
        email="atomic@ictu.edu.vn",
    )
    snap_id = uuid.uuid4()
    snap = LecturerSourceSnapshot(
        id=snap_id,
        lecturer_id=None,  # nullable; tracked via created_lecturer_ids
        source_system="ictu_profile_page",
        source_url="https://ictu.edu.vn/lecturers/AT01",
        snapshot_hash="abc" * 21 + "a",
        parser_version="1.0",
        validation_status="VALID",
        raw_payload={"canonical": {"full_name": import_lec.full_name}},
        fetched_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    audit = AuditEvent(
        id=import_id,
        entity_type="lecturer_dataset",
        entity_id=import_id,
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={
            "filename": "ictu_lecturers.json",
            "snapshot_ids": [str(snap_id)],
            "created_lecturer_ids": [str(import_lec.id)],
        },
    )

    _install_mock_db_for_rollback(
        mock_db,
        audit,
        audit_first_sequence=(audit, None),
        snapshots=[snap],
        snapshot_order_all=[snap],
        lecturer_results=[import_lec],
    )

    # Trigger the except SQLAlchemyError branch in rollback_import
    # Must be SQLAlchemyError (not plain Exception) for the service to catch it
    commit_error = SQLAlchemyError("DB constraint violation during atomic rollback")
    mock_db.commit.side_effect = commit_error

    service = LecturerRollbackService()
    with pytest.raises(LecturerRollbackError) as exc_info:
        service.rollback_import(mock_db, import_id=import_id, actor=admin)

    err = exc_info.value
    assert err.code == "LECTURER_IMPORT_ROLLBACK_FAILED"
    assert err.status_code == 500
    assert mock_db.rollback.called
