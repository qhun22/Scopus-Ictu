"""Centralized guard: verify a database connection is safe for DESTRUCTIVE
pytest fixtures (TRUNCATE / bulk DELETE / schema DROP) before they run.

Root cause this exists to prevent (see docs/qa/NO_JSON_SAFETY_AND_JOB_RECOVERY.md):
a handful of integration tests bind straight to ``TEST_DATABASE_URL``'s
``public`` schema (via ``isolated_db_engine`` in conftest.py) and then
``TRUNCATE ... CASCADE`` a fixed table list — including ``users`` in one
case — with no per-test isolation and no teardown. The *old* check in
``_assert_test_database_url`` only blocked two literal "forensic" database
names and ran once at import time; it never re-verified before each
destructive statement, never checked what *server* (host/port/cluster) was
on the other end, and had no notion of "App DB" or "teacher DB" at all. A
developer who pointed ``TEST_DATABASE_URL`` at the manual-E2E database by
mistake (or at the real App DB) got no resistance — exactly what happened
in a prior session.

Design, in order of what each layer catches:

1. ``ALLOWED_TEST_DATABASE_NAMES`` — an explicit allowlist. A database must
   be named EXACTLY one of these to ever be eligible for destructive
   fixtures. No "contains 'test'" / "contains 'demo'" pattern matching:
   the whole point is that a name is not evidence, only an exact match
   against a list a human curated is.
2. ``FORBIDDEN_DATABASE_NAMES`` — a hard-coded blocklist of the real App DB
   and teacher DB names, checked independently of (and before) the
   allowlist. Defense in depth: even if the allowlist were ever edited
   carelessly to include one of these, this list still refuses them.
3. ``FORBIDDEN_PORTS`` — refuses PostgreSQL's default port (5432), which on
   this project's machines is the production/local-service port, never a
   disposable test cluster.
4. A live round-trip to the server itself (``current_database()``,
   ``inet_server_port()``, ``host(inet_server_addr())``,
   ``current_user``, and — the strongest signal — ``pg_control_system()``'s
   ``system_identifier``) cross-checked against what the connection URL
   *claims*. A URL can lie about which database it points to only if DNS/
   connection routing is also compromised; the server's own answers cannot.
5. Every check raises ``DatabaseSafetyRefused`` (fail CLOSED) on ANY
   ambiguity: missing env var, unreachable server, name not on the
   allowlist, name on the blocklist, forbidden port, or a mismatch between
   what the URL says and what the server reports. There is no fallback
   path that proceeds when verification could not be completed.

This module is imported only by tests/conftest.py and test files that use
destructive fixtures — it has no production code path and is never
imported by ``app.*``. It intentionally does NOT read ``ENVIRONMENT`` as a
trust signal (the old guard did, and "ENVIRONMENT=test" is just an env var
a developer can set on any machine, including one pointed at a real
database) and does NOT expose any environment-variable override that
widens the allowlist at runtime — the allowlist is a Python literal in
this file, edited (and reviewed) like any other code change.
"""

from __future__ import annotations

import ipaddress
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

# ── Manifest-based cluster registration ─────────────────────────────────────
# The env var TEST_CLUSTER_MANIFEST points to a JSON file that registers a
# specific, disposable test cluster *for this test process only*. The manifest
# approach avoids editing the EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS table
# for every new cluster while keeping the guard's fail-closed guarantee.
#
# The manifest must be placed under TestRoot (verified), which anchors it to a
# local disposable cluster directory. The manifest's system_identifier is
# checked against the live server's pg_control_system().system_identifier;
# the live data_directory is checked against the manifest's data_dir_prefix.
#
# When TEST_CLUSTER_MANIFEST is absent: the existing EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS
# table is used (unchanged behaviour for CI and the original registered cluster).
# When present and valid: manifest values override the system_identifier check.
# When present but invalid (missing/bad JSON/wrong paths): fail closed.

_TEST_CLUSTER_MANIFEST_ENV = "TEST_CLUSTER_MANIFEST"

# Root under which all disposable test clusters must live. The manifest's
# data_dir_prefix must be under this directory (case-insensitive on Windows).
# NEVER change this to a path that contains the application or teacher database.
_TESTROOT = Path("D:/DataFolder/ProjectIctu/DoAn/_ScopusIctu_Test")


@dataclass(frozen=True, slots=True)
class ClusterManifest:
    """Identity of a disposable test cluster registered for a specific test run."""

    database: str
    port: int
    system_identifier: int
    data_dir_prefix: str  # path under _TESTROOT; live data_dir must start with this


def _path_under_testroot(p: str) -> bool:
    """True when p (or any prefix-equal path) is under _TESTROOT (case-insensitive)."""
    def _parts(s: str):
        return [x.lower() for x in PurePosixPath(s.replace("\\", "/")).parts]

    root_parts = _parts(str(_TESTROOT))
    candidate_parts = _parts(p)
    return (
        len(candidate_parts) >= len(root_parts)
        and candidate_parts[: len(root_parts)] == root_parts
    )


def _path_has_prefix(data_dir: str, prefix: str) -> bool:
    """True when data_dir starts with prefix (case-insensitive, cross-OS)."""
    def _parts(s: str):
        return [x.lower() for x in PurePosixPath(s.replace("\\", "/")).parts]

    p = _parts(prefix)
    d = _parts(data_dir)
    return len(d) >= len(p) and d[: len(p)] == p


def _load_manifest() -> ClusterManifest | None:
    """Read and validate the cluster manifest from TEST_CLUSTER_MANIFEST, if set.

    Returns None when the env var is absent.
    Raises DatabaseSafetyRefused on any validation failure (fail closed).
    """
    path_str = os.environ.get(_TEST_CLUSTER_MANIFEST_ENV)
    if not path_str:
        return None

    try:
        manifest_path = Path(path_str)
        if not manifest_path.is_file():
            raise DatabaseSafetyRefused(
                f"Refusing destructive test fixture: TEST_CLUSTER_MANIFEST "
                f"'{path_str}' is not a readable file."
            )
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except DatabaseSafetyRefused:
        raise
    except Exception as exc:
        raise DatabaseSafetyRefused(
            f"Refusing destructive test fixture: could not read or parse "
            f"TEST_CLUSTER_MANIFEST '{path_str}': {exc}"
        ) from exc

    # Validate required fields
    required = ("database", "port", "system_identifier", "data_dir_prefix")
    missing = [k for k in required if k not in raw]
    if missing:
        raise DatabaseSafetyRefused(
            f"Refusing destructive test fixture: TEST_CLUSTER_MANIFEST missing "
            f"required field(s): {missing}"
        )

    data_dir_prefix = str(raw["data_dir_prefix"])
    if not _path_under_testroot(data_dir_prefix):
        raise DatabaseSafetyRefused(
            f"Refusing destructive test fixture: manifest data_dir_prefix "
            f"'{data_dir_prefix}' is not under TestRoot ({_TESTROOT}). "
            "Only clusters with data directories under TestRoot may be registered."
        )

    try:
        return ClusterManifest(
            database=str(raw["database"]),
            port=int(raw["port"]),
            system_identifier=int(raw["system_identifier"]),
            data_dir_prefix=data_dir_prefix,
        )
    except (ValueError, TypeError) as exc:
        raise DatabaseSafetyRefused(
            f"Refusing destructive test fixture: TEST_CLUSTER_MANIFEST has "
            f"invalid field values: {exc}"
        ) from exc

# ── Layer 1: explicit allowlist ──────────────────────────────────────────
# Every name here must be a disposable database created specifically to be
# torn down by pytest fixtures (TRUNCATE/DELETE/DROP). Nothing else may be
# added without deciding, by hand, that the named database is expendable.
ALLOWED_TEST_DATABASE_NAMES = frozenset(
    {
        # CI: a fresh postgres:16 service container, destroyed with the
        # job — see .github/workflows/ci.yml.
        "test_db",
        # Local disposable pytest-only databases (never used for manual
        # UI/E2E testing — see ALLOWED_TEST_DATABASE_NAMES docstring and
        # docs/qa/NO_JSON_SAFETY_AND_JOB_RECOVERY.md for the naming
        # convention: *_test_pytest_* is pytest-only by construction).
        "scopus_ictu_test_pytest_20261011",
        "scopus_ictu_test_pytest_20261013",
    }
)

# The local disposable pytest databases above are hosted by the one verified
# PostgreSQL cluster recorded in the NO-JSON acceptance evidence. CI gets a
# fresh service cluster on every run, so `test_db` is accepted only when the
# full GitHub Actions container-network signal set is present.
EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS = {
    "scopus_ictu_test_pytest_20261011": 7694238084633166136,
    "scopus_ictu_test_pytest_20261013": 7694238084633166136,
}

# ── Layer 2: hard blocklist, independent of the allowlist above ─────────
FORBIDDEN_DATABASE_NAMES = frozenset(
    {
        "scopus_ictu_app",  # the real App DB (Task 20B)
        "scopus_ictu_demo_teacher_20261014",  # teacher DB, read-only source of record
        "scopus_ictu_acceptance_v2",  # prior forensic/acceptance DB
        "scopus_ictu_ui_clean",  # prior forensic/acceptance DB
        # Any *_e2e_* / *_nojson_test_* database is a manual-E2E fixture,
        # never a pytest target, regardless of what TEST_DATABASE_URL says.
        "scopus_ictu_nojson_test_20261013",
        "scopus_ictu_e2e_nojson_20261013",
        "scopus_ictu_test_nojson_20261011",
        "scopus_ictu_test_p3_20261013",
    }
)

FORBIDDEN_PORTS = frozenset({5432})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
LOOPBACK_ADDRS = frozenset({"127.0.0.1", "::1"})

# Same narrowly-scoped CI container-network allowance used by
# scripts/generate_matching_candidates.py — GitHub Actions' postgres
# service container reports its Docker bridge address, not a loopback
# literal, even though the job connects via "localhost". This still
# requires ENVIRONMENT=test; it is never honored on a developer machine.
_CI_CONTAINER_NETWORK_FLAG = "DB_SAFETY_GUARD_CI_CONTAINER_NETWORK"
_DOCKER_BRIDGE_NETWORK = ipaddress.ip_network("172.16.0.0/12")


class DatabaseSafetyRefused(Exception):
    """A destructive pytest fixture tried to run against an unsafe target."""


@dataclass(frozen=True, slots=True)
class VerifiedTestTarget:
    database: str
    port: int
    address: str
    user: str
    system_identifier: int


def _redacted_url_summary(raw_url: str) -> str:
    """A diagnostic string safe to put in an exception message: never the
    password, never the full URL (which embeds the password)."""

    try:
        url = make_url(raw_url)
    except Exception:
        return "<unparseable TEST_DATABASE_URL>"
    return f"{url.drivername}://{url.username}@{url.host}:{url.port}/{url.database}"


def _check_name(database: str | None) -> None:
    name = database or ""
    if name in FORBIDDEN_DATABASE_NAMES:
        raise DatabaseSafetyRefused(
            f"Refusing destructive test fixture: database '{name}' is on the "
            "hard-coded protected list (App DB / teacher DB / prior forensic "
            "DB / known manual-E2E DB). This can never be overridden."
        )
    if name not in ALLOWED_TEST_DATABASE_NAMES:
        raise DatabaseSafetyRefused(
            f"Refusing destructive test fixture: database '{name}' is not on "
            "the explicit pytest allowlist (db_safety_guard.ALLOWED_TEST_DATABASE_NAMES). "
            "Containing 'test' or 'demo' in the name is not sufficient — add the "
            "exact name to the allowlist only after confirming it is a disposable, "
            "pytest-only database, never used for manual UI/E2E testing."
        )


def _ci_container_network_allowed() -> bool:
    environment = os.environ.get("ENVIRONMENT", "local").lower()
    return (
        os.environ.get(_CI_CONTAINER_NETWORK_FLAG) == "1"
        and environment == "test"
        and os.environ.get("GITHUB_ACTIONS") == "true"
    )


def _check_host_address(addr: str) -> None:
    if addr in LOOPBACK_ADDRS:
        return
    if _ci_container_network_allowed():
        try:
            if ipaddress.ip_address(addr) in _DOCKER_BRIDGE_NETWORK:
                return
        except ValueError:
            pass
    raise DatabaseSafetyRefused(
        f"Refusing destructive test fixture: server address '{addr}' is not "
        "loopback and the CI container-network allowance does not apply."
    )


def _check_connection_claims(engine: Engine, *, port: int, user: str) -> None:
    """Cross-check URL claims against the identity reported by PostgreSQL."""

    claimed_host = (engine.url.host or "").casefold()
    if claimed_host not in LOOPBACK_HOSTS:
        raise DatabaseSafetyRefused(
            "Refusing destructive test fixture: TEST_DATABASE_URL must use a "
            "loopback host outside the explicitly enabled GitHub Actions service network."
        )
    if engine.url.port != port:
        raise DatabaseSafetyRefused(
            f"Refusing destructive test fixture: URL port {engine.url.port} does not "
            f"match PostgreSQL server port {port}."
        )
    if engine.url.username != user:
        raise DatabaseSafetyRefused(
            "Refusing destructive test fixture: URL username does not match "
            "the connected PostgreSQL role."
        )


def _check_cluster_identity(
    database: str,
    system_identifier: int,
    *,
    manifest: "ClusterManifest | None" = None,
    data_dir: str | None = None,
) -> None:
    # Manifest path: explicit cluster registration for this test run.
    if manifest is not None:
        if manifest.database != database:
            raise DatabaseSafetyRefused(
                f"Refusing destructive test fixture: manifest is for database "
                f"'{manifest.database}' but connected database is '{database}'."
            )
        if manifest.system_identifier != system_identifier:
            raise DatabaseSafetyRefused(
                "Refusing destructive test fixture: PostgreSQL cluster "
                "system_identifier does not match the manifest. "
                f"Manifest expects {manifest.system_identifier}; "
                f"server reports {system_identifier}."
            )
        if data_dir is None:
            raise DatabaseSafetyRefused(
                "Refusing destructive test fixture: manifest requires data_dir "
                "verification but data_directory could not be retrieved."
            )
        if not _path_has_prefix(data_dir, manifest.data_dir_prefix):
            raise DatabaseSafetyRefused(
                f"Refusing destructive test fixture: server data_directory "
                f"'{data_dir}' does not start with manifest data_dir_prefix "
                f"'{manifest.data_dir_prefix}'. "
                "This cluster is not the one registered in the manifest."
            )
        return

    # Default path: hardcoded expected system_identifiers per database name.
    expected = EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS.get(database)
    if expected is not None:
        if system_identifier != expected:
            raise DatabaseSafetyRefused(
                "Refusing destructive test fixture: PostgreSQL cluster identity "
                "does not match the verified local pytest cluster."
            )
        return
    if database == "test_db" and _ci_container_network_allowed():
        return
    raise DatabaseSafetyRefused(
        "Refusing destructive test fixture: no approved PostgreSQL cluster "
        "identity is configured for this target. "
        "Use TEST_CLUSTER_MANIFEST to register a new disposable test cluster."
    )


def verify_destructive_test_target(engine: Engine) -> VerifiedTestTarget:
    """Round-trip the live server and confirm it is safe for destructive
    pytest fixtures. Raises DatabaseSafetyRefused on ANY ambiguity —
    missing config, unreachable server, name not allowlisted, name on the
    blocklist, forbidden port, or any URL/server mismatch. Never returns a
    partial or best-effort result; callers must treat a raised exception
    as "do not run the destructive statement."

    The database name is checked against the URL BEFORE opening any
    connection: a forbidden name (App DB, teacher DB, ...) is refused
    without ever establishing a session against that server, not merely
    before any destructive statement on it.

    When TEST_CLUSTER_MANIFEST is set, the manifest's system_identifier and
    data_dir_prefix are used for cluster identity verification instead of the
    hardcoded EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS table. A manifest
    that fails validation causes an immediate DatabaseSafetyRefused.
    """

    # Load manifest early (before connecting) so a bad manifest file fails
    # closed without ever touching the server.
    manifest = _load_manifest()

    _check_name(engine.url.database)

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "select current_database(), inet_server_port(), "
                    "coalesce(host(inet_server_addr()), '127.0.0.1'), current_user, "
                    "(select system_identifier from pg_control_system()), "
                    "current_setting('data_directory')"
                )
            ).one()
            conn.rollback()
    except DatabaseSafetyRefused:
        raise
    except Exception as exc:
        raise DatabaseSafetyRefused(
            "Refusing destructive test fixture: could not verify server identity "
            f"({type(exc).__name__}). Fail closed — no cleanup was attempted."
        ) from exc

    database, port, addr, user, system_identifier, data_dir = row

    _check_name(database)

    if port in FORBIDDEN_PORTS:
        raise DatabaseSafetyRefused(
            f"Refusing destructive test fixture: server port {port} is forbidden "
            "(production/local-service port, never a disposable test cluster)."
        )

    _check_host_address(str(addr))
    _check_connection_claims(engine, port=port, user=user)
    if not isinstance(system_identifier, int) or system_identifier <= 0:
        raise DatabaseSafetyRefused(
            "Refusing destructive test fixture: PostgreSQL cluster identity "
            "could not be verified."
        )
    _check_cluster_identity(
        database,
        system_identifier,
        manifest=manifest,
        data_dir=str(data_dir) if data_dir else None,
    )

    return VerifiedTestTarget(
        database=database,
        port=port,
        address=str(addr),
        user=user,
        system_identifier=system_identifier,
    )


def assert_safe_for_destructive_test(engine: Engine) -> VerifiedTestTarget:
    """Call this immediately before any TRUNCATE / bulk DELETE / schema DROP
    in a test fixture. Re-verifies the live server every time it is called
    — it does not trust a result cached from an earlier call in the same
    test session, because the whole point is that configuration can be
    wrong in ways a one-time check at import time would miss."""

    return verify_destructive_test_target(engine)


__all__ = [
    "ALLOWED_TEST_DATABASE_NAMES",
    "FORBIDDEN_DATABASE_NAMES",
    "FORBIDDEN_PORTS",
    "EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS",
    "ClusterManifest",
    "DatabaseSafetyRefused",
    "VerifiedTestTarget",
    "_load_manifest",
    "_path_has_prefix",
    "_path_under_testroot",
    "assert_safe_for_destructive_test",
    "verify_destructive_test_target",
]
