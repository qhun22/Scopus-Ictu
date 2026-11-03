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

import json
import os
import tempfile

import pytest
from sqlalchemy import create_engine

from tests.db_safety_guard import (
    ALLOWED_TEST_DATABASE_NAMES,
    ClusterManifest,
    FORBIDDEN_DATABASE_NAMES,
    FORBIDDEN_PORTS,
    EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS,
    DatabaseSafetyRefused,
    _check_cluster_identity,
    _check_host_address,
    _check_connection_claims,
    _check_name,
    _ci_container_network_allowed,
    _load_manifest,
    _path_has_prefix,
    _path_under_testroot,
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
        ("postgresql+psycopg2://test_user@localhost:55432/test_db", 5432, "test_user"),
        ("postgresql+psycopg2://other_user@localhost:55432/test_db", 55432, "test_user"),
        ("postgresql+psycopg2://test_user@example.com:55432/test_db", 55432, "test_user"),
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


# --------------------------------------------------------------------------- manifest / path helpers
_TESTROOT_STR = "D:/DataFolder/ProjectIctu/DoAn/_ScopusIctu_Test"
_VALID_DATA_DIR_PREFIX = f"{_TESTROOT_STR}/Hun1/0211/021126-203934-postgres-regression/pgdata"
_VALID_DB = "scopus_ictu_test_pytest_20261011"
_VALID_SYSID = 7703568449941442872


def test_path_under_testroot_accepts_subpath() -> None:
    assert _path_under_testroot(f"{_TESTROOT_STR}/some/subdir") is True


def test_path_under_testroot_rejects_sibling() -> None:
    assert _path_under_testroot("D:/DataFolder/ProjectIctu/DoAn/Scopus-Ictu") is False


def test_path_under_testroot_rejects_parent() -> None:
    assert _path_under_testroot("D:/DataFolder/ProjectIctu/DoAn") is False


def test_path_under_testroot_accepts_backslash_variant() -> None:
    # Windows paths with backslashes must be treated identically.
    assert _path_under_testroot(_TESTROOT_STR.replace("/", "\\") + "\\subdir") is True


def test_path_has_prefix_exact_match() -> None:
    assert _path_has_prefix(_VALID_DATA_DIR_PREFIX + "/pg_wal", _VALID_DATA_DIR_PREFIX) is True


def test_path_has_prefix_rejects_shorter_data_dir() -> None:
    assert _path_has_prefix(_TESTROOT_STR, _VALID_DATA_DIR_PREFIX) is False


def test_path_has_prefix_case_insensitive() -> None:
    assert _path_has_prefix(_VALID_DATA_DIR_PREFIX.upper(), _VALID_DATA_DIR_PREFIX.lower()) is True


# --------------------------------------------------------------------------- _load_manifest() env-var tests
# NOTE: tests that manipulate TEST_CLUSTER_MANIFEST via monkeypatch are kept in
# a standalone script (TestRoot/Hun1/0211/021126-235000-reset-integration-test/
# scripts/run_manifest_env_tests.py) because conftest's pytest_runtest_teardown
# hook runs BEFORE monkeypatch restores env vars, causing the guard to re-read
# the modified value and refuse. Those env-var tests are not DB tests and use
# no real connections; the script runs them with --noconftest legitimately.
# The tests below exercise ClusterManifest / _check_cluster_identity logic
# directly (no env-var manipulation) and run fine through conftest.


# --------------------------------------------------------------------------- _check_cluster_identity with manifest
def test_manifest_cluster_identity_accepted_when_all_match() -> None:
    m = ClusterManifest(
        database=_VALID_DB,
        port=5490,
        system_identifier=_VALID_SYSID,
        data_dir_prefix=_VALID_DATA_DIR_PREFIX,
    )
    _check_cluster_identity(_VALID_DB, _VALID_SYSID, manifest=m, data_dir=_VALID_DATA_DIR_PREFIX + "/PG_VERSION")


def test_manifest_cluster_identity_refused_wrong_database() -> None:
    m = ClusterManifest(
        database=_VALID_DB,
        port=5490,
        system_identifier=_VALID_SYSID,
        data_dir_prefix=_VALID_DATA_DIR_PREFIX,
    )
    with pytest.raises(DatabaseSafetyRefused, match="manifest is for database"):
        _check_cluster_identity("scopus_ictu_test_pytest_20261013", _VALID_SYSID, manifest=m, data_dir=_VALID_DATA_DIR_PREFIX)


def test_manifest_cluster_identity_refused_wrong_system_identifier() -> None:
    m = ClusterManifest(
        database=_VALID_DB,
        port=5490,
        system_identifier=_VALID_SYSID,
        data_dir_prefix=_VALID_DATA_DIR_PREFIX,
    )
    with pytest.raises(DatabaseSafetyRefused, match="system_identifier does not match"):
        _check_cluster_identity(_VALID_DB, _VALID_SYSID + 1, manifest=m, data_dir=_VALID_DATA_DIR_PREFIX)


def test_manifest_cluster_identity_refused_data_dir_outside_prefix() -> None:
    m = ClusterManifest(
        database=_VALID_DB,
        port=5490,
        system_identifier=_VALID_SYSID,
        data_dir_prefix=_VALID_DATA_DIR_PREFIX,
    )
    other_dir = f"{_TESTROOT_STR}/Hun1/0211/021126-999999-other-cluster/pgdata"
    with pytest.raises(DatabaseSafetyRefused, match="data_dir_prefix"):
        _check_cluster_identity(_VALID_DB, _VALID_SYSID, manifest=m, data_dir=other_dir)


def test_manifest_cluster_identity_refused_missing_data_dir() -> None:
    m = ClusterManifest(
        database=_VALID_DB,
        port=5490,
        system_identifier=_VALID_SYSID,
        data_dir_prefix=_VALID_DATA_DIR_PREFIX,
    )
    with pytest.raises(DatabaseSafetyRefused, match="data_directory could not be retrieved"):
        _check_cluster_identity(_VALID_DB, _VALID_SYSID, manifest=m, data_dir=None)


# --------------------------------------------------------------------------- _load_manifest() env-var tests via monkeypatch.context()
# Each test manipulates TEST_CLUSTER_MANIFEST inside a monkeypatch.context()
# block.  The env var is restored when the with-block exits — INSIDE the test
# body, BEFORE conftest's pytest_runtest_teardown hook calls
# verify_destructive_test_target().  This is safe: the hook sees the original
# TEST_CLUSTER_MANIFEST value and the guard accepts the registered cluster.
# (The standalone script run_manifest_env_tests.py remains as a reference and
# can be run without conftest; the canonical pytest path is here.)


def test_load_manifest_returns_none_when_env_var_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as m:
        m.delenv("TEST_CLUSTER_MANIFEST", raising=False)
        assert _load_manifest() is None


def test_load_manifest_raises_when_file_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as m:
        m.setenv("TEST_CLUSTER_MANIFEST", "/nonexistent/path/manifest.json")
        with pytest.raises(DatabaseSafetyRefused, match="not a readable file"):
            _load_manifest()


def test_load_manifest_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not-json-at-all")
        fname = f.name
    try:
        with monkeypatch.context() as m:
            m.setenv("TEST_CLUSTER_MANIFEST", fname)
            with pytest.raises(DatabaseSafetyRefused, match="could not read or parse"):
                _load_manifest()
    finally:
        os.unlink(fname)


def test_load_manifest_raises_when_required_field_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"database": _VALID_DB, "port": 5490}, f)
        fname = f.name
    try:
        with monkeypatch.context() as m:
            m.setenv("TEST_CLUSTER_MANIFEST", fname)
            with pytest.raises(DatabaseSafetyRefused, match="missing required field"):
                _load_manifest()
    finally:
        os.unlink(fname)


def test_load_manifest_raises_when_data_dir_prefix_outside_testroot(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "database": _VALID_DB,
        "port": 5490,
        "system_identifier": _VALID_SYSID,
        "data_dir_prefix": "C:/SomeOtherPath/pgdata",
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        fname = f.name
    try:
        with monkeypatch.context() as m:
            m.setenv("TEST_CLUSTER_MANIFEST", fname)
            with pytest.raises(DatabaseSafetyRefused, match="not under TestRoot"):
                _load_manifest()
    finally:
        os.unlink(fname)


def test_load_manifest_returns_correct_dataclass_for_valid_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "database": _VALID_DB,
        "port": 5490,
        "system_identifier": _VALID_SYSID,
        "data_dir_prefix": _VALID_DATA_DIR_PREFIX,
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        fname = f.name
    try:
        with monkeypatch.context() as m:
            m.setenv("TEST_CLUSTER_MANIFEST", fname)
            m_obj = _load_manifest()
            assert m_obj is not None
            assert m_obj.database == _VALID_DB
            assert m_obj.port == 5490
            assert m_obj.system_identifier == _VALID_SYSID
            assert m_obj.data_dir_prefix == _VALID_DATA_DIR_PREFIX
    finally:
        os.unlink(fname)


def test_check_cluster_identity_no_manifest_wrong_sysid_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without manifest, uses hardcoded table; _VALID_SYSID doesn't match hardcoded entry."""
    with monkeypatch.context() as m:
        m.delenv("TEST_CLUSTER_MANIFEST", raising=False)
        m.delenv("DB_SAFETY_GUARD_CI_CONTAINER_NETWORK", raising=False)
        m.delenv("GITHUB_ACTIONS", raising=False)
        with pytest.raises(DatabaseSafetyRefused):
            _check_cluster_identity(_VALID_DB, _VALID_SYSID)
