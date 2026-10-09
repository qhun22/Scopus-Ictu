"""Task 15: các hàm thuần của bộ điều phối khởi động demo và nội dung file BAT (không chạy tiến trình thật)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts import demo_launcher as dl

NETSTAT = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:5432           0.0.0.0:0              LISTENING       7928
  TCP    127.0.0.1:55432        0.0.0.0:0              LISTENING       10248
  TCP    127.0.0.1:8001         0.0.0.0:0              LISTENING       500
  TCP    [::]:5432              [::]:0                 LISTENING       7928
  TCP    127.0.0.1:8001         127.0.0.1:52000        ESTABLISHED     500
  TCP    127.0.0.1:5173         0.0.0.0:0              LISTENING       600
"""

GOOD = {
    "DB_HOST": "127.0.0.1", "DB_PORT": "55432", "DB_NAME": dl.EXPECTED_DB, "ENVIRONMENT": "local",
    "DB_USER": "u", "DB_PASSWORD": "synthetic", "SECRET_KEY": "synthetic-secret",
}


def test_parse_listeners_only_listening_ports() -> None:
    assert dl.parse_listeners(NETSTAT) == {5432: 7928, 55432: 10248, 8001: 500, 5173: 600}


def test_descends_from_walks_parent_chain_and_stops_on_cycles() -> None:
    table = {30: 20, 20: 10, 10: 1, 1: 0, 50: 60, 60: 50}
    assert dl.descends_from(30, 10, table) and dl.descends_from(10, 10, table)
    assert not dl.descends_from(30, 99, table)
    assert not dl.descends_from(50, 99, table)  # cycle must not hang


def test_port_owner_never_claims_a_foreign_listener() -> None:
    table = {500: 400, 400: 1, 700: 1}
    assert dl.port_owner(None, [400], table) == "free"
    assert dl.port_owner(500, [400], table) == "ours"      # venv launcher child of the recorded pid
    assert dl.port_owner(700, [400], table) == "foreign"   # unrelated process
    assert dl.port_owner(500, [0], table) == "foreign"      # no pidfile => not ours
    assert dl.port_owner(500, [], table) == "foreign"


def test_validate_config_accepts_only_the_demo_setup() -> None:
    assert dl.validate_config(GOOD) == []
    assert dl.validate_config({**GOOD, "DB_PORT": "5432"})
    assert dl.validate_config({**GOOD, "DB_HOST": "10.0.0.5"})
    assert dl.validate_config({**GOOD, "DB_NAME": "scopus_ictu_acceptance_v2"})
    assert dl.validate_config({**GOOD, "ENVIRONMENT": "prod"})
    assert dl.validate_config({k: v for k, v in GOOD.items() if k != "DB_PASSWORD"})
    assert dl.validate_config({**GOOD, "SECRET_KEY": ""})


def test_read_env_file_ignores_comments_and_keeps_values(tmp_path) -> None:
    f = tmp_path / "x.env"
    f.write_text("# comment\nDB_USER=u\nDB_PASSWORD=a=b=c\n\nEMPTY=\n", encoding="utf-8")
    assert dl.read_env_file(f) == {"DB_USER": "u", "DB_PASSWORD": "a=b=c", "EMPTY": ""}


def test_forbidden_port_constant_is_the_windows_service_port() -> None:
    assert dl.FORBIDDEN_PORTS == {5432} and dl.PG_PORT == 55432 and dl.PG_PORT not in dl.FORBIDDEN_PORTS


def test_the_bat_is_one_entry_point_without_secrets_or_absolute_paths() -> None:
    bat = (dl.REPO / "scopus-ictu-qhun22.bat").read_text(encoding="ascii")
    assert "demo_launcher.py" in bat and '"%PYTHON%" "%LAUNCHER%" start' in bat and re.search(r"/i \"%~1\"==\"stop\"", bat)
    assert not re.search(r"[A-Za-z]:\\", bat)  # no hard-coded drive paths: everything is derived from %~dp0
    assert not re.search(r"password\s*=|secret_key|postgresql://", bat, re.I)
    assert "--reload" not in bat and "5432" not in bat


def test_launcher_source_has_no_credentials_and_no_5432_connection() -> None:
    src = Path(dl.__file__).read_text(encoding="utf-8")
    assert not re.search(r"(password|secret)\s*=\s*[\"'][^\"']+[\"']", src, re.I)
    assert "5432" in src and "FORBIDDEN_PORTS" in src and "connect(" in src and "port=PG_PORT" in src
