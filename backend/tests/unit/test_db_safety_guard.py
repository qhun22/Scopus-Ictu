"""Unit tests for the centralized destructive-test database safety guard.

Pure name/port/address logic is tested without a live database (the server
round-trip itself is proven separately by every integration test that
depends on ISOLATION_ENGINE successfully passing the guard at collection
time — a passing test suite run IS the "accepts a valid target" proof).
This file focuses on the parts that must reject, with no live connection
required, plus one live test proving the guard refuses a wrong-but-
reachable target before any destructive statement runs.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine

from tests.db_safety_guard import (
    ALLOWED_TEST_DATABASE_NAMES,
    FORBIDDEN_DATABASE_NAMES,
    FORBIDDEN_PORTS,
    EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS,
    DatabaseSafetyRefused,
    _check_host_address,
    _check_connection_claims,
    _check_name,
    _ci_container_network_allowed,
)


# --------------------------------------------------------------------------- name checks
def test_allowed_name_passes() -> None:
    for name in ALLOWED_TEST_DATABASE_NAMES:
        _check_name(name)  # must not raise


@pytest.mark.parametrize("name", sorted(FORBIDDEN_DATABASE_NAMES))
def test_forbidden_names_are_refused(name: str) -> None:
    with pytest.raises(DatabaseSafetyRefused):
        _check_name(name)


def test_app_db_name_is_refused_even_if_hypothetically_allowlisted() -> None:
    """Defense in depth: FORBIDDEN_DATABASE_NAMES is checked independently of
    (and before) the allowlist, so even a careless allowlist edit could not
    let the real App DB through."""

    assert "scopus_ictu_app" not in ALLOWED_TEST_DATABASE_NAMES  # sanity: it never should be
    with pytest.raises(DatabaseSafetyRefused):
        _check_name("scopus_ictu_app")


def test_teacher_db_name_is_refused() -> None:
    with pytest.raises(DatabaseSafetyRefused):
        _check_name("scopus_ictu_demo_teacher_20261014")


def test_unknown_name_is_refused_not_silently_allowed() -> None:
    """A name containing 'test' is NOT sufficient — only an exact allowlist
    match is accepted."""

    with pytest.raises(DatabaseSafetyRefused):
        _check_name("some_random_test_database_nobody_reviewed")


def test_none_database_name_is_refused() -> None:
    with pytest.raises(DatabaseSafetyRefused):
        _check_name(None)


def test_forbidden_database_is_refused_before_opening_a_connection() -> None:
    """Misconfigured App/E2E targets stop before even connecting, so no
    fixture cleanup SQL can be reached."""

    engine = create_engine("postgresql+psycopg2://test_user:secret@localhost:55432/scopus_ictu_app")
    engine.connect = lambda: pytest.fail("guard must refuse before connecting")  # type: ignore[method-assign]
    from tests.db_safety_guard import verify_destructive_test_target

    with pytest.raises(DatabaseSafetyRefused):
        verify_destructive_test_target(engine)


@pytest.mark.parametrize(
    ("url", "server_port", "server_user"),
    [
        ("postgresql://test_user@localhost:55432/test_db", 5432, "test_user"),
        ("postgresql://other_user@localhost:55432/test_db", 55432, "test_user"),
        ("postgresql://test_user@example.com:55432/test_db", 55432, "test_user"),
    ],
)
def test_connection_claim_mismatch_is_refused(url: str, server_port: int, server_user: str) -> None:
    engine = create_engine(url)
    with pytest.raises(DatabaseSafetyRefused):
        _check_connection_claims(engine, port=server_port, user=server_user)


# --------------------------------------------------------------------------- port checks
def test_production_port_is_in_forbidden_set() -> None:
    assert 5432 in FORBIDDEN_PORTS


def test_local_database_requires_its_verified_cluster_identifier() -> None:
    from tests.db_safety_guard import _check_cluster_identity

    for database, system_identifier in EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS.items():
        _check_cluster_identity(database, system_identifier)
        with pytest.raises(DatabaseSafetyRefused):
            _check_cluster_identity(database, system_identifier + 1)


# --------------------------------------------------------------------------- host/address checks
def test_loopback_address_passes() -> None:
    _check_host_address("127.0.0.1")  # must not raise
    _check_host_address("::1")  # must not raise


def test_non_loopback_address_refused_without_ci_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DB_SAFETY_GUARD_CI_CONTAINER_NETWORK", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(DatabaseSafetyRefused):
        _check_host_address("172.17.0.5")


def test_non_loopback_address_refused_even_with_partial_ci_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    """All three signals (flag + ENVIRONMENT=test + GITHUB_ACTIONS=true) are
    required together — no single one is trusted alone."""

    monkeypatch.setenv("DB_SAFETY_GUARD_CI_CONTAINER_NETWORK", "1")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    with pytest.raises(DatabaseSafetyRefused):
        _check_host_address("172.17.0.5")


def test_docker_bridge_address_allowed_only_with_full_ci_signal_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_SAFETY_GUARD_CI_CONTAINER_NETWORK", "1")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("ENVIRONMENT", "test")
    _check_host_address("172.17.0.5")  # must not raise


def test_ci_container_network_flag_ignored_outside_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_SAFETY_GUARD_CI_CONTAINER_NETWORK", "1")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("ENVIRONMENT", "local")
    assert _ci_container_network_allowed() is False


# --------------------------------------------------------------------------- live server round-trip
def test_live_guard_refuses_a_reachable_but_forbidden_database() -> None:
    """The decisive proof: point the guard at a real, reachable PostgreSQL
    server whose current_database() is a forbidden/unknown name, and confirm
    it is refused BEFORE any destructive statement could run. Uses the same
    TEST_DATABASE_URL the rest of the suite already proved is allowlisted,
    but connects to the sibling 'postgres' maintenance database instead —
    reachable, but not on the allowlist — to exercise the live round-trip
    without needing a second real forbidden database available in CI."""

    base_url = os.environ.get("TEST_DATABASE_URL")
    if not base_url:
        pytest.skip("TEST_DATABASE_URL is required")
    from sqlalchemy.engine import make_url

    url = make_url(base_url).set(database="postgres")
    try:
        engine = create_engine(url, pool_pre_ping=True, future=True)
        with engine.connect():
            pass
    except Exception:
        pytest.skip("sibling 'postgres' maintenance database not reachable in this environment")

    from tests.db_safety_guard import assert_safe_for_destructive_test

    with pytest.raises(DatabaseSafetyRefused):
        assert_safe_for_destructive_test(engine)
    engine.dispose()
