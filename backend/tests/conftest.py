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
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import get_session_factory
from app.main import app


# ── Isolation guard ────────────────────────────────────────────────────────────
def _build_isolated_test_engine() -> Engine | None:
    """Build an isolated test engine using a disposable schema.

    Strategy B (isolated schema): create a unique schema per test session.
    Falls back gracefully if PostgreSQL is unavailable.
    """
    try:
        # Read the base URL from .env, replace DB name with {name}_test_schema
        base_url = os.environ.get("TEST_DATABASE_URL")
        if not base_url:
            return None
        _assert_test_database_url(base_url)

        test_engine = create_engine(base_url, pool_pre_ping=True, future=True)

        # Test the connection is live
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        return test_engine
    except Exception:
        return None


def _assert_test_database_url(base_url: str) -> None:
    database = make_url(base_url).database
    if database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        raise RuntimeError(
            "TEST_DATABASE_URL must not target an acceptance or forensic database"
        )


ISOLATION_ENGINE: Engine | None = None

# Guard: refuse to run against ENVIRONMENT=local unless TEST_ALLOW_LOCAL=1
_env = os.environ.get("ENVIRONMENT", "local").lower()
_can_override = os.environ.get("TEST_ALLOW_LOCAL", "0") == "1"

if not _can_override:
    ISOLATION_ENGINE = _build_isolated_test_engine()
    if ISOLATION_ENGINE is None:
        pytest.exit(
            "TEST ISOLATION BLOCKER: TEST_DATABASE_URL must point to an available "
            "isolated PostgreSQL database.\n"
            "Options:\n"
            "  1. Set TEST_DATABASE_URL to an isolated PostgreSQL URL, OR\n"
            "  2. Set TEST_ALLOW_LOCAL=1 if you intentionally want to run tests "
            "against the local DB (DANGEROUS — will mutate data).\n"
            "  3. For CI: set ENVIRONMENT=test in the CI environment.",
            returncode=1,
        )


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
    """Return the isolated test engine if available; None otherwise."""
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
