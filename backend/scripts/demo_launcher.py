"""Điều phối khởi động / dừng phần mềm Scopus-Ictu (gọi từ file BAT ở gốc repository).

Một lần nhấp đúp BAT => PostgreSQL demo sẵn sàng => Backend sẵn sàng => Frontend sẵn sàng => mở trình duyệt.

An toàn:
* Chỉ dùng mã nguồn của repository chứa tệp này (kiểm tra đường dẫn module ``app``).
* Chỉ cluster PostgreSQL demo (data directory của thư mục runtime, cổng 55432). Không bao giờ chạm cổng 5432.
* Chạy lần thứ hai không nhân đôi tiến trình: cổng đang do tiến trình CỦA DEMO giữ thì dùng lại.
* Cổng do tiến trình lạ giữ => DỪNG và báo lỗi, không kill tiến trình đó.
* Không chứa mật khẩu/DSN: cấu hình đọc từ thư mục secrets NGOÀI Git của thư mục runtime.
* Không tự chạy migration; chỉ kiểm tra Alembic head.

Lệnh: ``start [--no-browser]``, ``stop [--keep-db]``, ``status``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOAN = REPO.parent
RUNTIME = Path(os.environ.get("SCOPUS_DEMO_RUNTIME", DOAN / "_postgres_demo_14_10"))
VENV_PYTHON = Path(os.environ.get("SCOPUS_DEMO_PYTHON", DOAN / "_venv_backend_demo_py312" / "Scripts" / "python.exe"))
LOG_DIR = Path(os.environ.get("SCOPUS_DEMO_LOGS", DOAN / "_quan_ly_do_an" / "logs" / "demo"))
ENV_FILE = RUNTIME / "secrets" / "backend_app.env"
PG_BIN = Path(os.environ.get("SCOPUS_DEMO_PG_BIN", r"C:\Program Files\PostgreSQL\17\bin"))
EXPECTED_DB = os.environ.get("SCOPUS_DEMO_DB", "scopus_ictu_app")
PG_PORT, BACKEND_PORT, FRONTEND_PORT = 55432, 8001, 5173
FORBIDDEN_PORTS = {5432}
WEB_URL = f"http://127.0.0.1:{FRONTEND_PORT}"

_DETACHED = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW


class LauncherError(Exception):
    """Lỗi người dùng có thể đọc được; BAT sẽ dừng lại và giữ cửa sổ."""


# ----------------------------------------------------------------------------- hàm thuần (có test)
def parse_listeners(netstat_text: str) -> dict[int, int]:
    """port -> pid của tiến trình đang LISTENING (IPv4/IPv6)."""
    out: dict[int, int] = {}
    for line in netstat_text.splitlines():
        m = re.match(r"^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$", line)
        if m:
            out.setdefault(int(m.group(1)), int(m.group(2)))
    return out


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.rstrip("\r\n")
    return values


def validate_config(values: dict[str, str], expected_db: str = EXPECTED_DB) -> list[str]:
    errors = []
    if values.get("DB_HOST") != "127.0.0.1":
        errors.append("DB_HOST phai la 127.0.0.1")
    if values.get("DB_PORT") != str(PG_PORT) or int(values.get("DB_PORT", "0") or 0) in FORBIDDEN_PORTS:
        errors.append(f"DB_PORT phai la {PG_PORT} (cong 5432 bi cam)")
    if values.get("DB_NAME") != expected_db:
        errors.append(f"DB_NAME phai la {expected_db}")
    if (values.get("ENVIRONMENT") or "").lower() != "local":
        errors.append("ENVIRONMENT phai la local")
    for key in ("DB_USER", "DB_PASSWORD", "SECRET_KEY"):
        if not values.get(key):
            errors.append(f"thieu {key} trong tep cau hinh (ngoai Git)")
    return errors


def descends_from(pid: int, root_pid: int, table: dict[int, int]) -> bool:
    """pid có phải root_pid hoặc hậu duệ của nó (pid -> ppid)."""
    seen = set()
    while pid and pid not in seen:
        if pid == root_pid:
            return True
        seen.add(pid)
        pid = table.get(pid, 0)
    return False


def port_owner(listener_pid: int | None, owned_root_pids: list[int], table: dict[int, int]) -> str:
    """'free' | 'ours' | 'foreign'."""
    if listener_pid is None:
        return "free"
    return "ours" if any(descends_from(listener_pid, root, table) for root in owned_root_pids if root) else "foreign"


# ----------------------------------------------------------------------------- hệ thống
def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / "launcher.log").open("a", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n")


def say(tag: str, message: str) -> None:
    print(f"[{tag}] {message}", flush=True)
    log(f"{tag} {message}")


def listeners() -> dict[int, int]:
    return parse_listeners(subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, errors="replace").stdout)


def process_parents() -> dict[int, int]:
    ps = ("Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId | ConvertTo-Json -Compress")
    raw = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True, text=True, errors="replace").stdout
    try:
        rows = json.loads(raw)
    except ValueError:
        return {}
    return {int(r["ProcessId"]): int(r["ParentProcessId"]) for r in rows}


def pid_alive(pid: int) -> bool:
    return bool(pid) and str(pid) in subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, errors="replace").stdout


def pidfile(name: str) -> Path:
    return LOG_DIR / f"{name}.pid"


def read_pid(name: str) -> int:
    try:
        return int(pidfile(name).read_text().strip())
    except (OSError, ValueError):
        return 0


def postmaster_pid() -> int:
    try:
        return int((RUNTIME / "data" / "postmaster.pid").read_text(encoding="utf-8").splitlines()[0])
    except (OSError, ValueError, IndexError):
        return 0


def http_status(url: str, timeout: float = 3.0) -> int:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def wait_for(url: str, ok: set[int], seconds: int) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if http_status(url) in ok:
            return True
        time.sleep(1)
    return False


def kill_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


# ----------------------------------------------------------------------------- các bước
def check_environment() -> dict[str, str]:
    for label, path in (("thu muc runtime", RUNTIME), ("Python 3.12 venv", VENV_PYTHON), ("backend", REPO / "backend" / "app"),
                        ("vite", REPO / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"), ("pg_ctl", PG_BIN / "pg_ctl.exe")):
        if not path.exists():
            raise LauncherError(f"Khong tim thay {label}: {path}")
    if not ENV_FILE.exists():
        raise LauncherError(f"Khong tim thay tep cau hinh demo (ngoai Git): {ENV_FILE}")
    if not shutil.which("node"):
        raise LauncherError("Khong tim thay Node.js (lenh 'node') trong PATH")
    values = read_env_file(ENV_FILE)
    errors = validate_config(values)
    if errors:
        raise LauncherError("Cau hinh demo khong hop le: " + "; ".join(errors))
    return values


def ensure_postgres() -> None:
    owner = listeners().get(PG_PORT)
    if owner is not None:
        if owner == postmaster_pid():
            say("OK", f"PostgreSQL demo dang chay (cong {PG_PORT}, PID {owner}).")
            return
        raise LauncherError(f"Cong {PG_PORT} dang duoc tien trinh khac (PID {owner}) su dung, khong phai cluster demo. Khong tu dong dung.")
    say("..", f"Khoi dong PostgreSQL demo (data directory: {RUNTIME / 'data'}) ...")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(PG_BIN / "pg_ctl.exe"), "start", "-D", str(RUNTIME / "data"), "-l", str(RUNTIME / "logs" / "postgres.log"), "-w", "-t", "90"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    owner = listeners().get(PG_PORT)
    if result.returncode != 0 or owner is None or owner != postmaster_pid():
        raise LauncherError(f"Khong khoi dong duoc PostgreSQL demo. Xem {RUNTIME / 'logs' / 'postgres.log'}")
    say("OK", f"PostgreSQL demo da san sang (cong {PG_PORT}, PID {owner}).")


def check_database(values: dict[str, str]) -> None:
    import psycopg2  # noqa: PLC0415 - chỉ cần khi khởi động

    try:
        conn = psycopg2.connect(host="127.0.0.1", port=PG_PORT, dbname=values["DB_NAME"], user=values["DB_USER"],
                                password=values["DB_PASSWORD"], sslmode="disable", connect_timeout=8)
    except Exception as exc:
        raise LauncherError(f"Khong ket noi duoc database demo: {type(exc).__name__}") from exc
    try:
        cur = conn.cursor()
        cur.execute("select current_database(), inet_server_port(), host(inet_server_addr())")
        db, port, addr = cur.fetchone()
        if (db, port) != (values["DB_NAME"], PG_PORT) or addr not in ("127.0.0.1", "::1"):
            raise LauncherError(f"May chu bao database/cong khac mong doi: {db}/{port}/{addr}")
        cur.execute("select version_num from alembic_version")
        current = cur.fetchone()[0]
        cur.execute("select count(*) from lecturers")
        lecturers = cur.fetchone()[0]
    finally:
        conn.close()
    from alembic.config import Config  # noqa: PLC0415
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    cfg = Config(str(REPO / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO / "backend" / "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    if [current] != heads:
        raise LauncherError(f"Alembic cua database la {current} nhung ma nguon can {heads}. Launcher KHONG tu migrate; can xu ly thu cong.")
    say("OK", f"Database dung: {db} @ {addr}:{port}, Alembic head {current}, {lecturers} ho so giang vien.")


def backend_env(values: dict[str, str]) -> dict[str, str]:
    env = {k: os.environ[k] for k in ("SystemRoot", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "COMSPEC") if k in os.environ}
    env.update(values)
    env["PATH"] = r"C:\Windows\system32;C:\Windows"
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = str(REPO / "backend")
    raw, snap = RUNTIME / "api_data" / "app" / "raw_scopus", RUNTIME / "api_data" / "app" / "snapshots"
    raw.mkdir(parents=True, exist_ok=True)
    snap.mkdir(parents=True, exist_ok=True)
    env["SCOPUS_RAW_DIR"], env["DSPACE_SNAPSHOT_PATH"] = str(raw) + os.sep, str(snap) + os.sep
    return env


def service_state(name: str, port: int) -> tuple[str, int | None]:
    pid = listeners().get(port)
    if pid is None:
        return "free", None
    return port_owner(pid, [read_pid(name)], process_parents()), pid


def ensure_backend(values: dict[str, str]) -> None:
    state, pid = service_state("backend", BACKEND_PORT)
    if state == "foreign":
        raise LauncherError(f"Cong backend {BACKEND_PORT} dang duoc tien trinh khac (PID {pid}) su dung. Khong tu dong dung.")
    if state == "ours":
        say("OK", f"Backend demo dang chay (cong {BACKEND_PORT}, PID {pid}).")
    else:
        env = backend_env(values)
        probe = subprocess.run([str(VENV_PYTHON), "-c", "import app; print(app.__file__)"], cwd=REPO / "backend", env=env, capture_output=True, text=True)
        loaded = Path(probe.stdout.strip()) if probe.stdout.strip() else None
        if loaded is None or loaded.resolve() != (REPO / "backend" / "app" / "__init__.py").resolve():
            raise LauncherError(f"Module 'app' khong duoc import tu {REPO / 'backend'} (hien tai: {loaded}). Khong khoi dong.")
        say("..", f"Khoi dong Backend tu {REPO / 'backend'} ...")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (LOG_DIR / "backend.log").open("ab") as out:
            proc = subprocess.Popen([str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
                                    cwd=REPO / "backend", env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, creationflags=_DETACHED)
        pidfile("backend").write_text(str(proc.pid))
    if not wait_for(f"http://127.0.0.1:{BACKEND_PORT}/health", {200}, 60):
        raise LauncherError(f"Backend khong tra loi /health trong 60 giay. Xem {LOG_DIR / 'backend.log'}")
    say("OK", f"Backend san sang: http://127.0.0.1:{BACKEND_PORT}/docs (nguon: {REPO / 'backend'}).")


def ensure_frontend() -> None:
    state, pid = service_state("frontend", FRONTEND_PORT)
    if state == "foreign":
        raise LauncherError(f"Cong frontend {FRONTEND_PORT} dang duoc tien trinh khac (PID {pid}) su dung. Khong tu dong dung.")
    if state == "ours":
        say("OK", f"Frontend demo dang chay (cong {FRONTEND_PORT}, PID {pid}).")
    else:
        env = dict(os.environ)
        env["VITE_API_PROXY_TARGET"] = f"http://127.0.0.1:{BACKEND_PORT}"
        say("..", f"Khoi dong Frontend tu {REPO / 'frontend'} ...")
        with (LOG_DIR / "frontend.log").open("ab") as out:
            proc = subprocess.Popen([shutil.which("node"), str(REPO / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"),
                                     "--host", "127.0.0.1", "--port", str(FRONTEND_PORT), "--strictPort"],
                                    cwd=REPO / "frontend", env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, creationflags=_DETACHED)
        pidfile("frontend").write_text(str(proc.pid))
    if not wait_for(WEB_URL + "/", {200}, 60):
        raise LauncherError(f"Frontend khong tra loi trong 60 giay. Xem {LOG_DIR / 'frontend.log'}")
    if http_status(f"{WEB_URL}/api/v1/auth/me") not in (200, 401):
        raise LauncherError("Frontend chay nhung khong chuyen tiep duoc /api sang Backend (proxy).")
    say("OK", f"Frontend san sang: {WEB_URL} (nguon: {REPO / 'frontend'}).")


# ----------------------------------------------------------------------------- lệnh
def cmd_start(args: argparse.Namespace) -> int:
    started: list[str] = []
    try:
        say("..", f"Ma nguon: {REPO}")
        values = check_environment()
        ensure_postgres()
        check_database(values)
        for name, port in (("backend", BACKEND_PORT), ("frontend", FRONTEND_PORT)):
            if service_state(name, port)[0] == "free":
                started.append(name)
        ensure_backend(values)
        ensure_frontend()
    except LauncherError as exc:
        say("LOI", str(exc))
        for name in started:  # chỉ dọn thứ do lần chạy này khởi động
            pid = read_pid(name)
            if pid:
                kill_tree(pid)
        return 1
    if not args.no_browser:
        if webbrowser.open(WEB_URL):
            say("OK", f"Da mo trinh duyet: {WEB_URL}")
        else:
            say("CHU Y", f"Khong tu mo duoc trinh duyet. Hay mo thu cong: {WEB_URL}")
    print(f"\nPHAN MEM SAN SANG: {WEB_URL}\nSwagger: http://127.0.0.1:{BACKEND_PORT}/docs\nNhat ky: {LOG_DIR}", flush=True)
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    process_table = process_parents()
    for name, port in (("frontend", FRONTEND_PORT), ("backend", BACKEND_PORT)):
        pid = listeners().get(port)
        if pid is None:
            say("OK", f"{name}: khong chay.")
        elif port_owner(pid, [read_pid(name)], process_table) == "ours":
            kill_tree(read_pid(name) or pid)
            kill_tree(pid)
            pidfile(name).unlink(missing_ok=True)
            say("OK", f"Da dung {name} (cong {port}).")
        else:
            say("BO QUA", f"{name}: cong {port} do tien trinh khac (PID {pid}) giu - khong dung.")
    if args.keep_db:
        say("OK", "Giu PostgreSQL demo dang chay.")
        return 0
    owner = listeners().get(PG_PORT)
    if owner is None:
        say("OK", "PostgreSQL demo: khong chay.")
    elif owner == postmaster_pid():
        subprocess.run([str(PG_BIN / "pg_ctl.exe"), "stop", "-D", str(RUNTIME / "data"), "-m", "fast", "-w"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        say("OK", "Da dung PostgreSQL demo (chi cluster demo).")
    else:
        say("BO QUA", f"Cong {PG_PORT} do tien trinh khac (PID {owner}) giu - khong dung.")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    table = process_parents()
    for name, port in (("backend", BACKEND_PORT), ("frontend", FRONTEND_PORT)):
        pid = listeners().get(port)
        print(f"{name:9} cong {port}: " + ("trong" if pid is None else f"PID {pid} ({port_owner(pid, [read_pid(name)], table)})"))
    owner = listeners().get(PG_PORT)
    print(f"postgres  cong {PG_PORT}: " + ("trong" if owner is None else f"PID {owner} ({'cluster demo' if owner == postmaster_pid() else 'KHONG phai cluster demo'})"))
    print(f"health    : backend={http_status(f'http://127.0.0.1:{BACKEND_PORT}/health')} frontend={http_status(WEB_URL + '/')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--no-browser", action="store_true")
    start.set_defaults(func=cmd_start)
    stop = sub.add_parser("stop")
    stop.add_argument("--keep-db", action="store_true")
    stop.set_defaults(func=cmd_stop)
    sub.add_parser("status").set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
