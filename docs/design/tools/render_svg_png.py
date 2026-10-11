"""Xuất PNG độ phân giải cao (x2) từ các SVG tự dựng (BPMN, mockup) bằng Microsoft Edge/Chrome headless.

    python -X utf8 render_svg_png.py <tệp.svg> [<tệp.svg> ...]
Tìm trình duyệt ở các đường dẫn mặc định của Windows (Edge trước, rồi Chrome). Kích thước lấy từ thuộc tính viewBox của SVG.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]


def main(paths: list[str]) -> int:
    exe = next((b for b in BROWSERS if Path(b).exists()), None)
    if not exe:
        print("Không thấy Edge/Chrome")
        return 2
    rc = 0
    for p in paths:
        svg = Path(p).resolve()
        txt = svg.read_text(encoding="utf8")
        m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', txt)
        w, h = int(float(m.group(1))), int(float(m.group(2)))
        png = svg.with_suffix(".png")
        r = subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                            f"--window-size={w},{h}", f"--screenshot={png}", svg.as_uri()], capture_output=True, text=True)
        ok = png.exists() and png.stat().st_size > 1000
        print(("ok " if ok else "LỖI ") + png.name, f"{w*2}x{h*2}px")
        rc |= 0 if ok else 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
