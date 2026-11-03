"""System reset endpoint and append-only guard trigger tests.

Contract (env-based policy, vòng 5):

1. Non-local/non-dev environment → 410 SYSTEM_RESET_DISABLED before any SQL.
2. Unknown/staging/prod environment → same 410 before any SQL.
3. Local env + wrong/missing confirmation → 422 RESET_CONFIRMATION_MISMATCH, no SQL.
4. Local env + ADMIN + correct confirmation → SQL path reached (mocked to avoid wipe).
5. Append-only guard: BEFORE TRUNCATE trigger blocks direct TRUNCATE on history tables,
   independent of endpoint state (requires real isolated DB).

Role enforcement is handled by the ``require_role("ADMIN")`` FastAPI dependency and is
NOT tested here via direct call (the dependency is bypassed in unit tests).
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.system import reset_system
from app.core.exceptions import APIError
from app.models.base import Base
from app.models.governance import User
from app.models.publication_exclusion import LecturerPublicationExclusionEvent
from tests.db_safety_guard import assert_safe_for_destructive_test

MIGRATION = (Path(__file__).resolve().parents[2] / "alembic" / "versions"
             / "e4a1b7c92d10_g09_lecturer_publication_exclusions.py")


# ---------------------------------------------------------------------------
# Shared fixture for append-only guard tests (requires real isolated DB)
# ---------------------------------------------------------------------------

@pytest.fixture
def schema_session(isolated_db_engine):
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL test database available.")
    schema = f"reset_{uuid.uuid4().hex}"
    with isolated_db_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(isolated_db_engine.url, future=True, connect_args={
        "options": f"-csearch_path={schema} -cstatement_timeout=30000"})
    try:
        Base.metadata.create_all(bind=engine, tables=[
            t for n, t in Base.metadata.tables.items()
            if n != LecturerPublicationExclusionEvent.__tablename__])
        spec = importlib.util.spec_from_file_location("reset_mig", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(
                    conn, opts={"target_metadata": Base.metadata})):
                module.upgrade()
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()
        assert_safe_for_destructive_test(isolated_db_engine)
        with isolated_db_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def _seed(db):
    admin_id, user_id, lecturer_id, pub_id = (uuid.uuid4() for _ in range(4))
    for uid, role in ((admin_id, "ADMIN"), (user_id, "REVIEWER")):
        db.add(User(id=uid, email=f"{uid.hex}@test.local", password_hash="x" * 40,
                    display_name=role, role=role, is_active=True, version=1, auth_version=1))
    db.execute(text("INSERT INTO lecturers (id, full_name, full_name_normalized, version) "
                    "VALUES (:i, 'L', 'l', 1)"), {"i": lecturer_id})
    db.execute(text("INSERT INTO publications (id, eid, title, title_normalized) "
                    "VALUES (:i, 'EID-RESET', 't', 't')"), {"i": pub_id})
    db.flush()
    db.execute(text(
        "INSERT INTO lecturer_publication_exclusion_events (lecturer_id, publication_id, "
        "action, reason, acted_by_user_id) VALUES (:l, :p, 'EXCLUDE', 'r', :u)"),
        {"l": lecturer_id, "p": pub_id, "u": admin_id})
    db.commit()
    return admin_id


# ---------------------------------------------------------------------------
# Mock-based endpoint tests (no real DB, no data wipe)
# ---------------------------------------------------------------------------

def test_reset_disabled_on_prod_environment():
    """Môi trường prod phải trả 410 SYSTEM_RESET_DISABLED trước bất kỳ SQL nào."""
    mock_db = MagicMock()
    mock_actor = MagicMock()
    with patch("app.api.v1.endpoints.system.settings") as mock_settings:
        mock_settings.environment = "prod"
        with pytest.raises(APIError) as exc_info:
            reset_system(confirmation="ICTU", db=mock_db, _actor=mock_actor)
    err = exc_info.value
    assert err.status_code == 410
    assert err.code == "SYSTEM_RESET_DISABLED"
    mock_db.execute.assert_not_called()
    mock_db.commit.assert_not_called()


def test_reset_disabled_on_unknown_environment():
    """Môi trường không xác định (ví dụ staging) phải trả 410 trước SQL."""
    mock_db = MagicMock()
    mock_actor = MagicMock()
    with patch("app.api.v1.endpoints.system.settings") as mock_settings:
        mock_settings.environment = "staging"
        with pytest.raises(APIError) as exc_info:
            reset_system(confirmation="ICTU", db=mock_db, _actor=mock_actor)
    err = exc_info.value
    assert err.status_code == 410
    assert err.code == "SYSTEM_RESET_DISABLED"
    mock_db.execute.assert_not_called()


def test_reset_wrong_confirmation_rejected():
    """Xác nhận sai phải trả 422 RESET_CONFIRMATION_MISMATCH, không thực hiện SQL."""
    mock_db = MagicMock()
    mock_actor = MagicMock()
    with patch("app.api.v1.endpoints.system.settings") as mock_settings:
        mock_settings.environment = "local"
        with pytest.raises(APIError) as exc_info:
            reset_system(confirmation="WRONG", db=mock_db, _actor=mock_actor)
    err = exc_info.value
    assert err.status_code == 422
    assert err.code == "RESET_CONFIRMATION_MISMATCH"
    mock_db.execute.assert_not_called()
    mock_db.commit.assert_not_called()


def test_reset_missing_confirmation_rejected():
    """Không có xác nhận phải trả 422, không thực hiện SQL."""
    mock_db = MagicMock()
    mock_actor = MagicMock()
    with patch("app.api.v1.endpoints.system.settings") as mock_settings:
        mock_settings.environment = "local"
        with pytest.raises(APIError) as exc_info:
            reset_system(confirmation=None, db=mock_db, _actor=mock_actor)
    err = exc_info.value
    assert err.status_code == 422
    assert err.code == "RESET_CONFIRMATION_MISMATCH"
    mock_db.execute.assert_not_called()


def test_reset_local_admin_correct_confirmation_reaches_sql():
    """Local env + xác nhận đúng → đường SQL được kích hoạt (mock DB, không xóa dữ liệu thật).

    Bài kiểm thử này xác nhận rằng khi điều kiện hợp lệ, hàm reset_system()
    thực sự gọi db.execute() — tức là vượt qua kiểm tra môi trường và xác nhận.
    DB được mock hoàn toàn để tránh xóa dữ liệu đang dùng.
    """
    mock_db = MagicMock()
    mock_actor = MagicMock()
    # Mock DB trả về: không có ADMIN (snapshot rỗng) và không có guard triggers.
    mock_db.execute.return_value.fetchall.return_value = []   # admins snapshot
    mock_db.execute.return_value.all.return_value = []        # truncate guards

    with patch("app.api.v1.endpoints.system.settings") as mock_settings:
        mock_settings.environment = "local"
        result = reset_system(confirmation="ICTU", db=mock_db, _actor=mock_actor)

    assert result == {"status": "ok", "message": "Hệ thống đã được reset thành công."}
    mock_db.execute.assert_called()
    mock_db.commit.assert_called_once()


def test_reset_dev_environment_also_allowed():
    """Môi trường dev cũng được phép (cùng chính sách với local)."""
    mock_db = MagicMock()
    mock_actor = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_db.execute.return_value.all.return_value = []

    with patch("app.api.v1.endpoints.system.settings") as mock_settings:
        mock_settings.environment = "dev"
        result = reset_system(confirmation="ICTU", db=mock_db, _actor=mock_actor)

    assert result["status"] == "ok"
    mock_db.execute.assert_called()


# ---------------------------------------------------------------------------
# Real PostgreSQL test — append-only guard (requires isolated DB)
# ---------------------------------------------------------------------------

def test_append_only_guard_blocks_direct_truncate(schema_session):
    """BEFORE TRUNCATE trigger phải từ chối TRUNCATE trực tiếp trên bảng lịch sử.

    Bài kiểm thử này độc lập với chính sách môi trường — guard hoạt động bất kể
    endpoint có được phép hay không.
    """
    with schema_session() as db:
        _seed(db)
        with pytest.raises(DatabaseError, match="append-only"):
            db.execute(text("TRUNCATE lecturer_publication_exclusion_events"))
        db.rollback()


# ---------------------------------------------------------------------------
# Real PostgreSQL tests — full Reset flow (requires isolated DB, public schema)
# ---------------------------------------------------------------------------

def _disable_guards_truncate_reenable(session, tables: str) -> None:
    """Disable TRUNCATE guards, truncate the given tables, then re-arm.

    Used by public_schema_session fixture to achieve a clean state without
    the append-only triggers blocking the cleanup truncate.
    """
    from app.api.v1.endpoints.system import _truncate_guards, _quote
    guards = _truncate_guards(session)
    for table, trigger in guards:
        session.execute(text(f"ALTER TABLE {_quote(table)} DISABLE TRIGGER {_quote(trigger)}"))
    session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    for table, trigger in guards:
        session.execute(text(
            f"ALTER TABLE {_quote(table)} ENABLE ALWAYS TRIGGER {_quote(trigger)}"))
    session.commit()


@pytest.fixture
def public_schema_session(isolated_db_engine):
    """Session bound to the public schema of the isolated test DB for full-reset tests.

    Fixture timeline (trigger state evidence):
    1. SETUP (before yield): disable TRUNCATE guards → TRUNCATE users CASCADE →
       re-enable guards as ENABLE ALWAYS → commit.  Test body starts with triggers ARMED.
    2. TEST BODY: triggers remain ENABLE ALWAYS throughout; no DDL on triggers in this phase.
    3. TEARDOWN (after yield): session.close() only — no trigger manipulation.

    Transactional DDL guarantee: if _disable_guards_truncate_reenable raises before the
    re-enable+commit step, the transaction rolls back and PostgreSQL restores trigger state
    automatically.  Cleanup failure cannot leave triggers disabled.
    """
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL test database available.")
    SessionLocal = sessionmaker(bind=isolated_db_engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    assert_safe_for_destructive_test(isolated_db_engine)
    _disable_guards_truncate_reenable(session, "users")
    try:
        yield session
    finally:
        session.close()


def test_reset_real_db_admin_preserved_auth_version_incremented(public_schema_session):
    """Full Reset flow: ADMIN preserved with auth_version+1, REVIEWER removed."""
    db = public_schema_session
    mock_actor = MagicMock()

    admin_id = uuid.uuid4()
    reviewer_id = uuid.uuid4()
    orig_auth_version = 3

    db.add(User(
        id=admin_id, email=f"{admin_id.hex}@test.local",
        password_hash="x" * 60, display_name="Admin Test",
        role="ADMIN", is_active=True, version=1, auth_version=orig_auth_version,
    ))
    db.add(User(
        id=reviewer_id, email=f"{reviewer_id.hex}@test.local",
        password_hash="x" * 60, display_name="Reviewer Test",
        role="REVIEWER", is_active=True, version=1, auth_version=1,
    ))
    db.commit()

    with patch("app.api.v1.endpoints.system.settings") as mock_settings:
        mock_settings.environment = "local"
        result = reset_system(confirmation="ICTU", db=db, _actor=mock_actor)

    assert result == {"status": "ok", "message": "Hệ thống đã được reset thành công."}

    users_after = db.execute(text("SELECT role, auth_version FROM users ORDER BY role")).fetchall()
    roles_after = [r[0] for r in users_after]
    assert roles_after == ["ADMIN"], f"Expected only ADMIN, got: {roles_after}"
    assert users_after[0][1] == orig_auth_version + 1, (
        f"auth_version should be {orig_auth_version + 1}, got {users_after[0][1]}"
    )


def test_reset_real_db_triggers_re_armed_after_reset(public_schema_session):
    """After a successful reset, append-only TRUNCATE triggers are still active."""
    db = public_schema_session
    mock_actor = MagicMock()

    db.add(User(
        id=uuid.uuid4(), email="admin2@test.local",
        password_hash="x" * 60, display_name="Admin2",
        role="ADMIN", is_active=True, version=1, auth_version=1,
    ))
    db.commit()

    with patch("app.api.v1.endpoints.system.settings") as mock_settings:
        mock_settings.environment = "local"
        reset_system(confirmation="ICTU", db=db, _actor=mock_actor)

    # Evidence: trigger is ENABLE ALWAYS ('A' in pg_trigger.tgenabled) after reset.
    # reset_system() re-arms triggers before db.commit(), so the session sees them
    # as ENABLE ALWAYS here — NOT from the fixture setup phase.
    trigger_row = db.execute(text(
        "SELECT tgenabled FROM pg_trigger t "
        "JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE t.tgname = 'lpee_forbid_truncate' "
        "AND c.relnamespace = CAST(current_schema() AS regnamespace)"
    )).fetchone()
    assert trigger_row is not None, "lpee_forbid_truncate not found after reset"
    assert trigger_row[0] == "A", f"Expected ENABLE ALWAYS ('A'), got {trigger_row[0]!r}"

    # Trigger must still refuse direct TRUNCATE after reset.
    with pytest.raises(DatabaseError, match="append-only"):
        db.execute(text("TRUNCATE lecturer_publication_exclusion_events"))
    db.rollback()


def test_reset_real_db_no_admin_reset_still_succeeds(public_schema_session):
    """Reset with no ADMIN in the DB completes without error (nothing to restore)."""
    db = public_schema_session
    mock_actor = MagicMock()
    # No users seeded; public_schema_session already cleaned users.

    with patch("app.api.v1.endpoints.system.settings") as mock_settings:
        mock_settings.environment = "local"
        result = reset_system(confirmation="ICTU", db=db, _actor=mock_actor)

    assert result["status"] == "ok"
    count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
    assert count == 0
