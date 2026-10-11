"""Render tất cả sơ đồ PlantUML (.puml) trong docs/design ra SVG + PNG cạnh tệp nguồn.

    python -X utf8 render.py [--jar <đường dẫn plantuml.jar>] [đường dẫn lọc con]

* Graphviz (dot.exe) mặc định nằm ở thư mục `tools/graphviz` trong `_quan_ly_do_an` (xem SOURCE.txt); thiếu thì dùng bố cục smetana.
* Mặc định tìm jar ở `D:\\DataFolder\\ProjectIctu\\DoAn\\_quan_ly_do_an\\tools\\plantuml\\plantuml-1.2026.8.jar`
  (xem SOURCE.txt cạnh jar để biết nguồn và SHA-256). Cần Java.
* Xuất `<tên>.svg` và `<tên>.png` vào thư mục `render/` bên cạnh mỗi thư mục chứa `.puml`.
* Trả về mã lỗi khác 0 nếu bất kỳ sơ đồ nào lỗi cú pháp.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
TOOLS = Path(r"D:\DataFolder\ProjectIctu\DoAn\_quan_ly_do_an\tools")
DEFAULT_JAR = TOOLS / "plantuml" / "plantuml-1.2026.8.jar"
DEFAULT_DOT = TOOLS / "graphviz" / "Graphviz-16.1.0-win64" / "bin" / "dot.exe"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", default=str(DEFAULT_JAR))
    ap.add_argument("--dot", default=str(DEFAULT_DOT), help="đường dẫn dot.exe (Graphviz); thiếu thì dùng bố cục smetana tích hợp (kém đẹp hơn)")
    ap.add_argument("subpath", nargs="?", default="")
    a = ap.parse_args()
    root = DESIGN / a.subpath if a.subpath else DESIGN
    files = sorted(p for p in root.rglob("*.puml") if "render" not in p.parts)
    bad = 0
    env = dict(os.environ)
    extra = []
    if Path(a.dot).exists():
        env["GRAPHVIZ_DOT"] = a.dot
    else:
        extra = ["-Playout=smetana"]
        print("CẢNH BÁO: không thấy Graphviz dot — dùng smetana")
    for f in files:
        out = f.parent / "render"
        out.mkdir(exist_ok=True)
        for fmt in ("svg", "png"):
            r = subprocess.run(["java", "-Djava.awt.headless=true", "-DPLANTUML_LIMIT_SIZE=16384", "-jar", a.jar, f"-t{fmt}", "-charset", "UTF-8",
                                "-o", str(out), *extra, str(f)], capture_output=True, text=True, encoding="utf8", env=env)
            if r.returncode != 0 or "Error" in (r.stdout + r.stderr) or "Syntax" in (r.stdout + r.stderr):
                bad += 1
                print("LỖI", f.name, fmt, (r.stdout + r.stderr)[:400])
        print("ok", f.relative_to(DESIGN))
    print(f"{len(files)} sơ đồ, {bad} lỗi")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
