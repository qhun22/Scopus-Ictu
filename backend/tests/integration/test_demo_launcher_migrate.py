"""PROMPT 10 / PA-1: real START check and MIGRATE against an isolated, allowlisted TEST database.

Target: scopus_ictu_test_pytest_20261011 on the demo cluster (127.0.0.1:55432), verified by
tests/db_safety_guard before its schema is reset. Never the demo, App or teacher database.
Credentials come from TEST_DATABASE_URL and are passed only in memory / subprocess environment.
"""

from __future__ import annotations

import argparse
import os
import subprocess

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from scripts import demo_launcher as dl
from tests.db_safety_guard import assert_safe_for_destructive_test

TEST_DB = "scopus_ictu_test_pytest_20261011"


def _revision(engine) -> str:
    with engine.connect() as c:
        return c.execute(text("select version_num from alembic_version")).scalar_one()


def _alembic(values: dict[str, str], *args: str) -> None:
    res = subprocess.run([str(dl.VENV_PYTHON), "-m", "alembic", *args], cwd=dl.REPO / "backend",
                         env=dl.backend_env(values), capture_output=True, text=True)
    assert res.returncode == 0, dl.redact(res.stderr[-2000:], {values["DB_PASSWORD"]})


@pytest.fixture
def target(tmp_path, monkeypatch):
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        pytest.skip("TEST_DATABASE_URL is required")
    url = make_url(base).set(database=TEST_DB)
    assert url.host == "127.0.0.1" and url.port == dl.PG_PORT
    engine = create_engine(url, pool_pre_ping=True, future=True)
    assert_safe_for_destructive_test(engine)  # allowlisted disposable DB on the expected cluster
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    values = {"DB_HOST": "127.0.0.1", "DB_PORT": str(dl.PG_PORT), "DB_NAME": TEST_DB, "ENVIRONMENT": "local",
              "DB_USER": url.username, "DB_PASSWORD": url.password, "SECRET_KEY": "test-only-launcher-secret-key"}
    assert dl.validate_config(values, expected_db=TEST_DB) == []
    monkeypatch.setattr(dl, "RUNTIME", tmp_path / "runtime")
    monkeypatch.setattr(dl, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(dl, "check_environment", lambda: (dl._SECRETS.update({values["DB_PASSWORD"], values["SECRET_KEY"]}), values)[1])
    monkeypatch.setattr(dl, "ensure_postgres", lambda: None)  # the cluster is already running; never start/stop it here
    head = dl.alembic_heads()[0]
    previous = __import__("alembic.script", fromlist=["ScriptDirectory"]).ScriptDirectory.from_config(
        _cfg()).get_revision(head).down_revision
    _alembic(values, "upgrade", previous)
    try:
        yield engine, values, head, previous
    finally:
        for dump in (tmp_path / "runtime" / "backups").glob("*.dump"):
            dump.unlink()  # keep the evidence directory small; checksums were asserted
        engine.dispose()
        dl._SECRETS.clear()


def _cfg():
    from alembic.config import Config

    cfg = Config(str(dl.REPO / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(dl.REPO / "backend" / "alembic"))
    return cfg


def test_start_refuses_a_lagging_revision_then_migrate_upgrades_with_backup(target) -> None:
    engine, values, head, previous = target
    assert _revision(engine) == previous

    # START check on the real database: refuses and does not migrate
    with pytest.raises(dl.LauncherError, match="Khong tu migrate khi khoi dong"):
        dl.check_database(values)
    assert _revision(engine) == previous

    # MIGRATE: backup first, then upgrade to head
    assert dl.cmd_migrate(argparse.Namespace(confirm=TEST_DB)) == 0
    assert _revision(engine) == head
    dumps = list((dl.RUNTIME / "backups").glob(f"{TEST_DB}_pre_migrate_*.dump"))
    assert len(dumps) == 1 and dumps[0].stat().st_size > 0
    sidecar = dumps[0].with_name(dumps[0].name + ".sha256").read_text(encoding="ascii")
    import hashlib
    assert sidecar.split()[0] == hashlib.sha256(dumps[0].read_bytes()).hexdigest()

    # START check now passes
    dl.check_database(values)

    # MIGRATE again: already at head -> no second backup, nothing changes
    assert dl.cmd_migrate(argparse.Namespace(confirm=TEST_DB)) == 0
    assert len(list((dl.RUNTIME / "backups").glob("*.dump"))) == 1
    assert _revision(engine) == head

    # nothing secret on screen-log
    log = (dl.LOG_DIR / "launcher.log").read_text(encoding="utf-8")
    assert values["DB_PASSWORD"] not in log and "CHUA kiem chung restore" in log


def test_real_backup_failure_stops_before_migrating(target, monkeypatch) -> None:
    engine, values, head, previous = target
    monkeypatch.setattr(dl, "PG_BIN", dl.Path(dl.RUNTIME / "no_pg_bin_here"))
    assert dl.cmd_migrate(argparse.Namespace(confirm=TEST_DB)) == 1
    assert _revision(engine) == previous  # not migrated


def test_wrong_confirmation_changes_nothing(target) -> None:
    engine, values, head, previous = target
    assert dl.cmd_migrate(argparse.Namespace(confirm="scopus_ictu_app")) == 1
    assert _revision(engine) == previous
    assert not list((dl.RUNTIME / "backups").glob("*.dump")) if (dl.RUNTIME / "backups").exists() else True


def test_protected_teacher_db_is_refused_without_connecting(target, monkeypatch) -> None:
    engine, values, head, previous = target
    teacher = {**values, "DB_NAME": "scopus_ictu_demo_teacher_20261014"}
    monkeypatch.setattr(dl, "check_environment", lambda: teacher)
    touched = []
    monkeypatch.setattr(dl, "query_database", lambda v: touched.append(v["DB_NAME"]))
    monkeypatch.setattr(dl, "backup_database", lambda v: touched.append("backup"))
    monkeypatch.setattr(dl, "run_migration", lambda v: touched.append("migrate"))
    assert dl.cmd_migrate(argparse.Namespace(confirm="scopus_ictu_demo_teacher_20261014")) == 1
    assert touched == []
