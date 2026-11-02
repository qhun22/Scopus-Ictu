"""Back up, verify and restore the demo PostgreSQL database. Never overwrites a database.

    python -m scripts.db_backup backup                 # dump + SHA-256 + manifest, then prove it restores
    python -m scripts.db_backup backup --no-verify
    python -m scripts.db_backup verify  --dump FILE    # checksum, restore into a throw-away DB, compare rows
    python -m scripts.db_backup restore --dump FILE --into NEW_DATABASE

Safety rules (each one is a refusal, not a warning):
* the target of ``restore`` must be a NEW database name; an existing database is never touched;
* the live database names and the teacher database are refused as targets;
* only the demo cluster is used (port 5432 is refused); passwords travel via the environment only;
* a dump whose SHA-256 does not match its ``.sha256`` file is refused;
* ``verify`` restores into a database it creates itself and drops it afterwards.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2 import sql

from scripts import demo_launcher as dl

FORBIDDEN_TARGETS = frozenset({
    "scopus_ictu_app", "scopus_ictu_demo_teacher_20261014", "scopus_ictu_acceptance_v2",
    "scopus_ictu_ui_clean", "postgres", "template0", "template1",
})
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
ADMIN_USER = "demo_admin"


class BackupError(Exception):
    pass


def _app_values() -> dict[str, str]:
    values = dl.read_env_file(dl.ENV_FILE)
    problems = dl.validate_config(values)
    if problems:
        raise BackupError("Cau hinh khong hop le: " + "; ".join(problems))
    if dl.PG_PORT in dl.FORBIDDEN_PORTS:
        raise BackupError("Cong PostgreSQL bi cam.")
    return values


def _admin_password() -> str:
    path = dl.RUNTIME / "secrets" / "admin.pw"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise BackupError(f"Khong doc duoc mat khau quan tri o {path.name}: {type(exc).__name__}") from exc


def _connect(dbname: str, user: str, password: str) -> contextlib.closing:
    conn = psycopg2.connect(host="127.0.0.1", port=dl.PG_PORT, dbname=dbname, user=user, password=password)
    conn.autocommit = True
    return contextlib.closing(conn)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_target_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise BackupError("Ten database dich chi gom chu thuong, so va dau gach duoi (3-63 ky tu).")
    if name in FORBIDDEN_TARGETS:
        raise BackupError(f"'{name}' la database duoc bao ve - khong khoi phuc de len.")


def _table_counts(conn) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
        )
        names = [row[0] for row in cur.fetchall()]
        counts: dict[str, int] = {}
        for name in names:
            cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name)))
            counts[name] = cur.fetchone()[0]
    return counts


def _read_checksum_file(dump: Path) -> str | None:
    side = dump.with_name(dump.name + ".sha256")
    if not side.exists():
        return None
    return side.read_text(encoding="ascii").split()[0]


def _verify_checksum(dump: Path) -> str:
    actual = _sha256(dump)
    expected = _read_checksum_file(dump)
    if expected is None:
        raise BackupError(f"Thieu tep {dump.name}.sha256 - khong the kiem tra toan ven.")
    if actual != expected:
        raise BackupError("SHA-256 cua ban sao luu KHONG khop - tep co the bi hong hoac bi sua. Tu choi.")
    return actual


def backup() -> Path:
    values = _app_values()
    out_dir = dl.RUNTIME / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump = out_dir / f"{values['DB_NAME']}_backup_{stamp}.dump"
    env = dict(os.environ, PGPASSWORD=values["DB_PASSWORD"])
    res = subprocess.run(
        [str(dl.PG_BIN / "pg_dump.exe"), "-h", "127.0.0.1", "-p", str(dl.PG_PORT), "-U", values["DB_USER"],
         "-d", values["DB_NAME"], "-Fc", "--no-password", "-f", str(dump)],
        env=env, capture_output=True,
    )
    if res.returncode != 0 or not dump.exists() or dump.stat().st_size == 0:
        dump.unlink(missing_ok=True)
        raise BackupError(f"pg_dump that bai (ma {res.returncode}).")
    digest = _sha256(dump)
    dump.with_name(dump.name + ".sha256").write_bytes(f"{digest} *{dump.name}\n".encode("ascii"))
    with _connect(values["DB_NAME"], values["DB_USER"], values["DB_PASSWORD"]) as conn:
        counts = _table_counts(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            revision = cur.fetchone()[0]
    manifest = {
        "database": values["DB_NAME"], "created_at": datetime.now().isoformat(timespec="seconds"),
        "sha256": digest, "size_bytes": dump.stat().st_size, "alembic_revision": revision,
        "tables": len(counts), "rows": sum(counts.values()), "row_counts": counts,
        "verified_by_restore": False,
    }
    dump.with_name(dump.name + ".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] Da sao luu: {dump} ({manifest['tables']} bang, {manifest['rows']} dong, sha256 {digest[:12]}...)")
    return dump


def _restore_into(dump: Path, target: str) -> None:
    admin_pw = _admin_password()
    with _connect("postgres", ADMIN_USER, admin_pw) as admin:
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target,))
            if cur.fetchone():
                raise BackupError(f"Database '{target}' da ton tai - khong ghi de. Chon ten moi.")
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
    env = dict(os.environ, PGPASSWORD=admin_pw)
    res = subprocess.run(
        [str(dl.PG_BIN / "pg_restore.exe"), "-h", "127.0.0.1", "-p", str(dl.PG_PORT), "-U", ADMIN_USER,
         "-d", target, "--no-owner", "--no-privileges", "--exit-on-error", "--no-password", str(dump)],
        env=env, capture_output=True,
    )
    if res.returncode != 0:
        _drop(target)
        raise BackupError(f"pg_restore that bai (ma {res.returncode}); database '{target}' da duoc go bo.")


def _drop(target: str) -> None:
    _check_target_name(target)
    with _connect("postgres", ADMIN_USER, _admin_password()) as admin, admin.cursor() as cur:
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(target)))


def verify(dump: Path) -> bool:
    values = _app_values()
    digest = _verify_checksum(dump)
    manifest_path = dump.with_name(dump.name + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    target = f"restore_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _check_target_name(target)
    _restore_into(dump, target)
    try:
        with _connect(target, ADMIN_USER, _admin_password()) as conn:
            restored = _table_counts(conn)
        if manifest is not None:
            expected = manifest["row_counts"]
        else:
            with _connect(values["DB_NAME"], values["DB_USER"], values["DB_PASSWORD"]) as conn:
                expected = _table_counts(conn)
    finally:
        _drop(target)
    missing = sorted(set(expected) - set(restored))
    differing = sorted(t for t in expected if t in restored and expected[t] != restored[t])
    ok = not missing and not differing
    print(f"[{'OK' if ok else 'LOI'}] Kiem chung khoi phuc {dump.name}: sha256 {digest[:12]}..., "
          f"{len(restored)} bang, {sum(restored.values())} dong; database tam da duoc go bo.")
    if missing:
        print("  Thieu bang:", ", ".join(missing))
    if differing:
        print("  Lech so dong:", ", ".join(f"{t} ({expected[t]} -> {restored[t]})" for t in differing))
    if ok and manifest_path.exists():
        manifest["verified_by_restore"] = True
        manifest["verified_at"] = datetime.now().isoformat(timespec="seconds")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return ok


def restore(dump: Path, target: str) -> None:
    _check_target_name(target)
    _app_values()
    digest = _verify_checksum(dump)
    _restore_into(dump, target)
    with _connect(target, ADMIN_USER, _admin_password()) as conn:
        counts = _table_counts(conn)
    print(f"[OK] Da khoi phuc vao database MOI '{target}': {len(counts)} bang, {sum(counts.values())} dong "
          f"(sha256 {digest[:12]}...). Database dang chay khong bi thay doi.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--no-verify", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("--dump", required=True, type=Path)
    r = sub.add_parser("restore")
    r.add_argument("--dump", required=True, type=Path)
    r.add_argument("--into", required=True, metavar="NEW_DATABASE")
    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            dump = backup()
            if not args.no_verify and not verify(dump):
                return 1
        elif args.command == "verify":
            return 0 if verify(args.dump) else 1
        else:
            restore(args.dump, args.into)
        return 0
    except BackupError as exc:
        print(f"[LOI] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
