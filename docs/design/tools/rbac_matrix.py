"""Trích ma trận API ↔ vai trò từ mã FastAPI thật (không DB, không mạng).

Duyệt cây phụ thuộc (`route.dependant`) của từng route để tìm `require_role(...)` (đọc tập `allowed` trong closure)
và `get_current_user` (chỉ cần đăng nhập).  Ghi `usecase/RBAC_API_MATRIX.json/.csv`.

    python -X utf8 rbac_matrix.py --backend-dir <repo>/backend
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

for k, v in dict(DB_USER="x", DB_PASSWORD="x", DB_HOST="127.0.0.1", DB_PORT="1", DB_NAME="x",
                 SECRET_KEY="x" * 40, ENVIRONMENT="local").items():
    os.environ.setdefault(k, v)

DESIGN = Path(__file__).resolve().parents[1]


def walk(dep, found):
    call = dep.call
    if call is not None:
        qn = getattr(call, "__qualname__", "")
        if "require_role" in qn and call.__closure__:
            for cell in call.__closure__:
                v = cell.cell_contents
                if isinstance(v, frozenset):
                    found["roles"] |= set(v)
        if getattr(call, "__name__", "") == "get_current_user":
            found["auth"] = True
    for sub in dep.dependencies:
        walk(sub, found)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend-dir", required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(Path(a.backend_dir).resolve()))
    from app.main import app
    from fastapi.routing import APIRoute

    def iter_routes():
        for r in app.routes:
            if isinstance(r, APIRoute):
                yield r
            elif hasattr(r, "effective_route_contexts"):  # FastAPI >= 0.14x: router lồng nhau được bọc lười
                yield from r.effective_route_contexts()

    ops = []
    for r in iter_routes():
        found = {"roles": set(), "auth": False}
        walk(r.dependant, found)
        for m in sorted(set(r.methods) - {"HEAD", "OPTIONS"}):
            if found["roles"]:
                access = "ROLE:" + ",".join(sorted(found["roles"]))
            elif found["auth"]:
                access = "AUTHENTICATED"
            else:
                access = "PUBLIC"
            summary = getattr(r, "summary", None) or getattr(r, "name", "")
            ops.append(dict(method=m, path=r.path, summary=summary, access=access,
                            roles=sorted(found["roles"]), deprecated=bool(r.deprecated)))
    ops.sort(key=lambda o: (o["path"], o["method"]))
    (DESIGN / "usecase").mkdir(exist_ok=True)
    (DESIGN / "usecase" / "RBAC_API_MATRIX.json").write_text(json.dumps(ops, ensure_ascii=False, indent=1), encoding="utf8")
    with open(DESIGN / "usecase" / "RBAC_API_MATRIX.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["method", "path", "access", "deprecated", "summary"])
        for o in ops:
            w.writerow([o["method"], o["path"], o["access"], o["deprecated"], o["summary"]])
    from collections import Counter
    print(len(ops), "thao tác;", dict(Counter(o["access"] for o in ops)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
