"""Pytest fixtures and configuration — M0 scaffold."""

from __future__ import annotations

import pytest

from app.main import app


@pytest.fixture(autouse=True)
def disable_runtime_recovery_during_tests():
    """Unit/API mocks must never recover jobs from a developer database."""

    previous = app.state.import_recovery_enabled
    app.state.import_recovery_enabled = False
    try:
        yield
    finally:
        app.state.import_recovery_enabled = previous
