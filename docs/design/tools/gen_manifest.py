"""Sinh docs/design/MANIFEST.json: danh sách tệp + SHA-256 + nguồn + phiên bản công cụ.

    python -X utf8 gen_manifest.py
Chạy SAU CÙNG (sau render và check_consistency) để băm đúng bản cuối.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
REPO = DESIGN.parents[1]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf8").stdout.strip()
    except Exception:
        return ""


def category(p: Path) -> str:
    rel = p.relative_to(DESIGN).as_posix()
    if "/render/" in rel:
        return "render (SVG/PNG xuất từ nguồn)"
    if rel.startswith("tools/"):
        return "tool"
    ext = p.suffix.lower()
    return {".puml": "nguồn sơ đồ PlantUML", ".bpmn": "nguồn BPMN 2.0", ".dbml": "nguồn ERD DBML", ".md": "tài liệu",
            ".csv": "bảng dữ liệu", ".json": "dữ liệu/nguồn máy đọc"}.get(ext, "khác")


snap = json.load(open(DESIGN / "database/source/schema_snapshot.json", encoding="utf8"))
files = []
for p in sorted(DESIGN.rglob("*")):
    if p.is_file() and p.name != "MANIFEST.json" and "__pycache__" not in p.parts:
        files.append(dict(path=p.relative_to(DESIGN).as_posix(), bytes=p.stat().st_size, sha256=sha256(p), category=category(p)))
by_cat: dict[str, int] = {}
for f in files:
    by_cat[f["category"]] = by_cat.get(f["category"], 0) + 1
puml = [f for f in files if f["path"].endswith(".puml")]
manifest = dict(
    name="Bộ tài sản phân tích–thiết kế Scopus–ICTU (Task 19)",
    version="1.0",
    generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    repository_head=git("rev-parse", "--short", "HEAD"),
    working_tree_note="Tệp trong docs/design và docs/planning là tệp mới/chưa commit tại thời điểm sinh manifest",
    schema_source=dict(database=snap["meta"]["database"], postgres=snap["meta"]["postgres_version"],
                       alembic_version=snap["meta"]["alembic_version"], extracted_at=snap["meta"]["extracted_at"], mode=snap["meta"]["mode"]),
    counts=dict(files=len(files), by_category=by_cat, plantuml_sources=len(puml), tables=len(snap["tables"]),
                foreign_keys=sum(len(t["fks"]) for t in snap["tables"].values())),
    tools=dict(
        plantuml=dict(version="1.2026.8", sha256="5e1ecfa8ecd32c90b03bbf3b1eb6f020943f98ab0fcf4032be31a0002ee2c462",
                      source="https://github.com/plantuml/plantuml/releases/tag/v1.2026.8 (SHA-256 khớp digest do GitHub công bố)"),
        graphviz=dict(version="16.1.0", sha256="733e49626c492242eb8dca30ea627b6ead20710e207998c7933b4909d92d6abc",
                      source="https://gitlab.com/graphviz/graphviz/-/releases (SHA-256 khớp tệp .sha256 do dự án công bố)"),
        bpmn_js=dict(version="17.11.1", use="kiểm tra nhập .bpmn (unpkg) — 0 cảnh báo, 82 phần tử"),
        dbml_core=dict(use="kiểm cú pháp .dbml — 24 bảng, 30 quan hệ"),
        browser="Microsoft Edge headless (xuất PNG từ SVG tự dựng)"),
    files=files,
)
(DESIGN / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf8")
print("OK:", len(files), "tệp;", by_cat)
