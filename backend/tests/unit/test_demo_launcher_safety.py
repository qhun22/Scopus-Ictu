"""PROMPT 10 / PA-1: launcher safety — start never migrates, migrate is guarded, health checks fail fast.

All process / database access is replaced by fakes; nothing real is started, dumped or migrated here.
The real-database migrate path is covered by tests/integration/test_demo_launcher_migrate.py.
"""

from __future__ import annotations

import argparse
import io
import time
from contextlib import redirect_stdout
from types import SimpleNamespace

import pytest

from scripts import demo_launcher as dl

APP = "scopus_ictu_app"
TEACHER = "scopus_ictu_demo_teacher_20261014"
VALUES = {"DB_HOST": "127.0.0.1", "DB_PORT": "55432", "DB_NAME": APP, "ENVIRONMENT": "local",
          "DB_USER": "u", "DB_PASSWORD": "synthetic-pw-123", "SECRET_KEY": "synthetic-secret-456"}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(dl, "RUNTIME", tmp_path / "runtime")
    dl._SECRETS.clear()
    yield
    dl._SECRETS.clear()


class Calls(list):
    def mark(self, name):
        return lambda *a, **k: self.append(name)


def _wire_migrate(monkeypatch, *, db=APP, current="old", heads=("new",), backup_fails=False):
    calls = Calls()
    state = {"current": current}
    monkeypatch.setattr(dl, "check_environment", lambda: {**VALUES, "DB_NAME": db})
    monkeypatch.setattr(dl, "ensure_postgres", calls.mark("ensure_postgres"))
    monkeypatch.setattr(dl, "alembic_heads", lambda: list(heads))

    def query(values):
        calls.append("query")
        return values["DB_NAME"], 55432, "127.0.0.1", state["current"], 410

    def backup(values):
        calls.append("backup")
        if backup_fails:
            raise dl.LauncherError("Sao luu that bai (ma loi 1) - KHONG migrate.")
        return dl.RUNTIME / "x.dump"

    def migrate(values):
        calls.append("migrate")
        state["current"] = heads[0]

    monkeypatch.setattr(dl, "query_database", query)
    monkeypatch.setattr(dl, "backup_database", backup)
    monkeypatch.setattr(dl, "run_migration", migrate)
    return calls


# --------------------------------------------------------------------------- pure helpers
def test_pure_helpers() -> None:
    assert dl.needs_migration("a", ["a"]) is False
    assert dl.needs_migration("a", ["b"]) is True
    assert dl.needs_migration("", ["b"]) is True
    assert dl.needs_migration("a", ["a", "b"]) is True  # multiple heads is never "up to date"
    assert dl.migration_block_reason(TEACHER) and dl.migration_block_reason(APP) is None
    assert dl.confirmation_matches(f"  {APP} ", APP)
    assert not dl.confirmation_matches(APP.upper(), APP)
    assert not dl.confirmation_matches("scopus_ictu", APP)
    assert not dl.confirmation_matches(None, APP)
    assert dl.redact("pw synthetic-pw-123 and key synthetic-secret-456", {"synthetic-pw-123", "synthetic-secret-456"}) == "pw *** and key ***"


# --------------------------------------------------------------------------- START
def test_start_check_with_matching_revision_passes(monkeypatch) -> None:
    calls = _wire_migrate(monkeypatch, current="new", heads=("new",))
    dl.check_database(VALUES)
    assert "migrate" not in calls and "backup" not in calls


def test_start_check_with_mismatched_revision_refuses_and_never_migrates(monkeypatch) -> None:
    calls = _wire_migrate(monkeypatch, current="old", heads=("new",))
    with pytest.raises(dl.LauncherError, match="Khong tu migrate khi khoi dong"):
        dl.check_database(VALUES)
    assert "migrate" not in calls and "backup" not in calls


def test_cmd_start_stops_before_any_service_when_revision_mismatches(monkeypatch) -> None:
    calls = _wire_migrate(monkeypatch, current="old", heads=("new",))
    monkeypatch.setattr(dl, "ensure_backend", calls.mark("backend"))
    monkeypatch.setattr(dl, "ensure_frontend", calls.mark("frontend"))
    monkeypatch.setattr(dl, "service_state", lambda name, port: ("free", None))
    assert dl.cmd_start(argparse.Namespace(no_browser=True)) == 1
    assert "backend" not in calls and "frontend" not in calls and "migrate" not in calls


# --------------------------------------------------------------------------- MIGRATE
def test_migrate_when_already_at_head_does_not_backup_or_migrate(monkeypatch) -> None:
    calls = _wire_migrate(monkeypatch, current="new", heads=("new",))
    assert dl.cmd_migrate(argparse.Namespace(confirm=None)) == 0
    assert "backup" not in calls and "migrate" not in calls


def test_migrate_refuses_protected_teacher_db_before_touching_anything(monkeypatch) -> None:
    calls = _wire_migrate(monkeypatch, db=TEACHER)
    assert dl.cmd_migrate(argparse.Namespace(confirm=TEACHER)) == 1
    assert calls == []  # not even postgres / query


def test_migrate_requires_exact_confirmation(monkeypatch) -> None:
    calls = _wire_migrate(monkeypatch)
    assert dl.cmd_migrate(argparse.Namespace(confirm="scopus_ictu")) == 1
    assert "backup" not in calls and "migrate" not in calls
    monkeypatch.setattr("builtins.input", lambda prompt: "wrong")
    assert dl.cmd_migrate(argparse.Namespace(confirm=None)) == 1
    assert "backup" not in calls and "migrate" not in calls


def test_migrate_stops_when_backup_fails(monkeypatch) -> None:
    calls = _wire_migrate(monkeypatch, backup_fails=True)
    assert dl.cmd_migrate(argparse.Namespace(confirm=APP)) == 1
    assert "backup" in calls and "migrate" not in calls


def test_migrate_happy_path_order(monkeypatch) -> None:
    calls = _wire_migrate(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt: APP)
    assert dl.cmd_migrate(argparse.Namespace(confirm=None)) == 0
    assert [c for c in calls if c in ("backup", "migrate")] == ["backup", "migrate"]
    assert calls.index("backup") > calls.index("query")


def test_backup_failure_removes_partial_dump_and_raises(monkeypatch) -> None:
    def fake_run(cmd, env=None, capture_output=None):
        out = dl.Path(cmd[cmd.index("-f") + 1])
        out.write_bytes(b"partial")
        assert "PGPASSWORD" in env and VALUES["DB_PASSWORD"] not in " ".join(cmd)  # secret not on the command line
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(dl.subprocess, "run", fake_run)
    with pytest.raises(dl.LauncherError, match="KHONG migrate"):
        dl.backup_database(VALUES)
    assert not list((dl.RUNTIME / "backups").glob("*.dump"))


def test_backup_reports_missing_pg_dump_as_launcher_error(monkeypatch) -> None:
    monkeypatch.setattr(dl, "PG_BIN", dl.Path("Z:/does/not/exist"))
    with pytest.raises(dl.LauncherError, match="pg_dump"):
        dl.backup_database(VALUES)


def test_backup_success_writes_checksum_and_warns_restore_is_unverified(monkeypatch) -> None:
    def fake_run(cmd, env=None, capture_output=None):
        dl.Path(cmd[cmd.index("-f") + 1]).write_bytes(b"PGDMP fake")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(dl.subprocess, "run", fake_run)
    buf = io.StringIO()
    with redirect_stdout(buf):
        out = dl.backup_database(VALUES)
    assert out.exists() and out.with_name(out.name + ".sha256").exists()
    assert "CHUA kiem chung restore" in buf.getvalue()


# --------------------------------------------------------------------------- health checks
class _DeadProc:
    pid, returncode = 4242, 3

    def poll(self):
        return self.returncode


def test_backend_that_exits_is_reported_quickly(monkeypatch) -> None:
    monkeypatch.setattr(dl, "service_state", lambda name, port: ("free", None))
    app_init = str((dl.REPO / "backend" / "app" / "__init__.py").resolve())
    monkeypatch.setattr(dl.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=app_init + "\n", returncode=0))
    monkeypatch.setattr(dl.subprocess, "Popen", lambda *a, **k: _DeadProc())
    monkeypatch.setattr(dl, "http_status", lambda url, timeout=3.0: 0)
    t0 = time.time()
    with pytest.raises(dl.LauncherError, match="da dung"):
        dl.ensure_backend(VALUES)
    assert time.time() - t0 < 5  # not the 60 s timeout


def test_frontend_is_not_reported_ready_when_backend_api_is_not_served(monkeypatch) -> None:
    monkeypatch.setattr(dl, "service_state", lambda name, port: ("ours", 600))
    monkeypatch.setattr(dl, "http_status", lambda url, timeout=3.0: 502 if "/api/" in url else 200)
    with pytest.raises(dl.LauncherError, match="proxy"):
        dl.ensure_frontend()


def test_secrets_are_redacted_on_screen_and_in_the_log(monkeypatch) -> None:
    dl._SECRETS.update({VALUES["DB_PASSWORD"], VALUES["SECRET_KEY"]})
    buf = io.StringIO()
    with redirect_stdout(buf):
        dl.say("LOI", f"connection failed for password {VALUES['DB_PASSWORD']} key {VALUES['SECRET_KEY']}")
    log_text = (dl.LOG_DIR / "launcher.log").read_text(encoding="utf-8")
    for text in (buf.getvalue(), log_text):
        assert VALUES["DB_PASSWORD"] not in text and VALUES["SECRET_KEY"] not in text and "***" in text
