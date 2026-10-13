"""Pytest fixtures and configuration — M0 scaffold.

Test database isolation contract (Phase 6):
- pytest must NEVER mutate the normal development database (backend/.env / scopus_m12_test).
- All tests run with ENVIRONMENT=test, using either:
  A. A dedicated disposable PostgreSQL test database  OR
  B. An isolated PostgreSQL schema with independent search_path.
- The guard fails closed if isolation cannot be established.
- Integration tests use MagicMock sessions (already safe).
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import get_session_factory
from app.main import app
from tests.db_safety_guard import (
    DatabaseSafetyRefused,
    assert_safe_for_destructive_test,
)


# ── Isolation guard ────────────────────────────────────────────────────────────
# db_safety_guard.assert_safe_for_destructive_test() is the single source of
# truth for "is this database safe to TRUNCATE/DELETE/DROP against" — see
# that module's docstring for the full rationale. There is deliberately NO
# environment-variable escape hatch here (the old TEST_ALLOW_LOCAL=1 flag
# bypassed isolation entirely and has been removed): every destructive
# fixture re-verifies the live server through that one function, every time,
# and a missing/unreachable/unverifiable target fails closed.
def _build_isolated_test_engine() -> Engine | None:
    """Build the shared engine for destructive-fixture tests, pre-verified
    against the explicit pytest allowlist. Returns None (never raises) if
    TEST_DATABASE_URL is absent or the server is unreachable; the caller
    turns that into a hard pytest.exit so a silent `None` can never let a
    destructive fixture quietly skip verification and proceed anyway."""

    base_url = os.environ.get("TEST_DATABASE_URL")
    if not base_url:
        return None
    try:
        test_engine = create_engine(base_url, pool_pre_ping=True, future=True)
        assert_safe_for_destructive_test(test_engine)
        return test_engine
    except DatabaseSafetyRefused:
        raise
    except Exception:
        return None


ISOLATION_ENGINE: Engine | None = None

try:
    ISOLATION_ENGINE = _build_isolated_test_engine()
except DatabaseSafetyRefused as exc:
    pytest.exit(f"DATABASE SAFETY GUARD REFUSED: {exc}", returncode=1)

if ISOLATION_ENGINE is None:
    pytest.exit(
        "TEST ISOLATION BLOCKER: TEST_DATABASE_URL must point to an available, "
        "allowlisted PostgreSQL test database (see tests/db_safety_guard.py). "
        "There is no override — add the exact database name to "
        "ALLOWED_TEST_DATABASE_NAMES only after confirming it is disposable "
        "and never used for manual UI/E2E testing.",
        returncode=1,
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Re-verify the live target before any per-test or module fixture runs.

    A wrong TEST_DATABASE_URL therefore aborts before fixtures can create or
    drop schemas, truncate tables, or execute cleanup. Fixtures using the
    shared engine still re-check immediately before their own cleanup too.
    """

    try:
        assert_safe_for_destructive_test(ISOLATION_ENGINE)
    except DatabaseSafetyRefused as exc:
        pytest.fail(f"DATABASE SAFETY GUARD REFUSED: {exc}", pytrace=False)


def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:
    """Re-verify before function-scoped fixture finalizers perform cleanup."""

    try:
        assert_safe_for_destructive_test(ISOLATION_ENGINE)
    except DatabaseSafetyRefused as exc:
        pytest.fail(f"DATABASE SAFETY GUARD REFUSED BEFORE FIXTURE CLEANUP: {exc}", pytrace=False)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def disable_runtime_recovery_during_tests():
    """Unit/API mocks must never recover jobs from a developer database."""
    previous = app.state.import_recovery_enabled
    app.state.import_recovery_enabled = False
    try:
        yield
    finally:
        app.state.import_recovery_enabled = previous


@pytest.fixture
def isolated_db_engine() -> Engine | None:
    """Return the isolated test engine, RE-VERIFIED against the destructive-
    test safety guard on every single use (not just once at import time) —
    a test using this fixture is trusted to TRUNCATE/DELETE against it."""

    if ISOLATION_ENGINE is None:
        return None
    try:
        assert_safe_for_destructive_test(ISOLATION_ENGINE)
    except DatabaseSafetyRefused as exc:
        pytest.fail(f"DATABASE SAFETY GUARD REFUSED: {exc}", pytrace=False)
    return ISOLATION_ENGINE


@pytest.fixture
def isolated_session(isolated_db_engine: Engine | None) -> Generator[Session, None, None]:
    """Yield an isolated test session scoped to one test function."""
    if isolated_db_engine is None:
        pytest.skip("No isolated test database available.")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=isolated_db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
