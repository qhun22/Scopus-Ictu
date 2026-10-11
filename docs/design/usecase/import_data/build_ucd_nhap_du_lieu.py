#!/usr/bin/env python3
"""Dựng Use Case Diagram "Phân hệ Nhập dữ liệu" (A4 dọc) từ MỘT đặc tả duy nhất.

Từ cùng danh sách nút + quan hệ, script sinh:
  - render/UCD-NHAP-DU-LIEU.svg : hình vector có tọa độ kiểm soát (dùng để in A4 dọc)
  - UCD-NHAP-DU-LIEU.puml  : nguồn PlantUML cùng tập quan hệ (chỉnh sửa/đối chiếu ngữ nghĩa)

PlantUML tự bố cục ra hình ngang (đã thử), nên bản in dùng SVG này. Sửa nội dung
ở phần SPEC bên dưới rồi chạy lại: python build_ucd_nhap_du_lieu.py
"""
from __future__ import annotations

import math
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent

# ----------------------------------------------------------------------------- SPEC
RX, RY = 110, 36                      # bán kính ellipse Use Case
W, H = 770, 780                       # khung vẽ (px)
BOX = dict(x=150, y=24, w=610, h=646)  # ranh giới hệ thống
ACTOR_X, TRUNK_X = 58, 126

# id -> (cx, cy, các dòng nhãn, in nghiêng = UC trừu tượng)
NODES = {
    "P":   (600, 212, ["Nhập dữ liệu", "từ tệp"], True),
    "N1":  (270, 150, ["Nhập tệp CSV", "công bố Scopus"], False),
    "N2":  (270, 274, ["Nhập tệp JSON", "danh sách giảng viên"], False),
    "C":   (600, 100, ["Xử lý cảnh báo", "tệp trùng"], False),
    "D":   (600, 324, ["Hủy tiến trình nhập"], False),
    "E":   (600, 436, ["Hoàn tác đợt nhập", "giảng viên"], False),
    "N7":  (270, 410, ["Xem lịch sử", "các đợt nhập"], False),
    "N8":  (270, 504, ["Xem chi tiết", "đợt nhập"], False),
    "N10": (270, 598, ["Xóa đợt nhập"], False),
    "N9":  (600, 598, ["Ẩn đợt nhập", "khỏi lịch sử"], False),
}
ASSOC = ["N1", "N2", "N7", "N8", "N10"]          # ADMIN — UC
GEN = [("N1", "P"), ("N2", "P")]                 # con -> cha
EXTEND = [                                       # (UC mở rộng, UC cơ sở, vị trí nhãn)
    ("C", "P", (612, 160, "start")),
    ("D", "P", (612, 272, "start")),
    ("E", "N2", (424, 326, "middle")),
    ("N9", "N10", (435, 588, "middle")),
]
FONT = "'Segoe UI', Arial, sans-serif"
LABEL_PX, EDGE_PX, LEGEND_PX = 16, 14, 14


# ----------------------------------------------------------------------------- hình học
def boundary(c, toward):
    """Điểm trên biên ellipse tâm c, theo hướng tới `toward`."""
    dx, dy = toward[0] - c[0], toward[1] - c[1]
    t = 1.0 / math.sqrt((dx / RX) ** 2 + (dy / RY) ** 2)
    return c[0] + dx * t, c[1] + dy * t


def center(n):
    return NODES[n][0], NODES[n][1]


def seg(a, b):
    ca, cb = center(a), center(b)
    return boundary(ca, cb), boundary(cb, ca)


def open_arrow(p, frm, size=12, spread=24):
    ang = math.atan2(p[1] - frm[1], p[0] - frm[0])
    pts = []
    for s in (+1, -1):
        a = ang + math.pi + s * math.radians(spread)
        pts.append((p[0] + size * math.cos(a), p[1] + size * math.sin(a)))
    return f"{pts[0][0]:.1f},{pts[0][1]:.1f} {p[0]:.1f},{p[1]:.1f} {pts[1][0]:.1f},{pts[1][1]:.1f}"


def hollow_triangle(p, frm, size=14, spread=26):
    ang = math.atan2(p[1] - frm[1], p[0] - frm[0])
    pts = []
    for s in (+1, -1):
        a = ang + math.pi + s * math.radians(spread)
        pts.append((p[0] + size * math.cos(a), p[1] + size * math.sin(a)))
    return f"{p[0]:.1f},{p[1]:.1f} {pts[0][0]:.1f},{pts[0][1]:.1f} {pts[1][0]:.1f},{pts[1][1]:.1f}"


# ----------------------------------------------------------------------------- SVG
def build_svg() -> str:
    o: list[str] = []
    o.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'font-family="{FONT}" role="img" aria-label="Use Case Diagram - Phan he Nhap du lieu">'
    )
    o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

    # ranh giới hệ thống
    b = BOX
    o.append(f'<rect x="{b["x"]}" y="{b["y"]}" width="{b["w"]}" height="{b["h"]}" fill="none" stroke="#111" stroke-width="1.8"/>')
    o.append(
        f'<text x="{b["x"] + b["w"] / 2}" y="{b["y"] + 24}" text-anchor="middle" font-size="{LABEL_PX}" '
        f'font-weight="700" fill="#111">Hệ thống Scopus–ICTU — Phân hệ Nhập dữ liệu</text>'
    )

    # associations: actor -> bus -> trái ellipse
    ys = [NODES[n][1] for n in ASSOC]
    ay = (min(ys) + max(ys)) / 2
    o.append(f'<g stroke="#111" stroke-width="1.6" fill="none">')
    o.append(f'<line x1="{ACTOR_X + 18}" y1="{ay}" x2="{TRUNK_X}" y2="{ay}"/>')
    o.append(f'<line x1="{TRUNK_X}" y1="{min(ys)}" x2="{TRUNK_X}" y2="{max(ys)}"/>')
    for n in ASSOC:
        cx, cy = center(n)
        o.append(f'<line x1="{TRUNK_X}" y1="{cy}" x2="{cx - RX}" y2="{cy}"/>')
    o.append("</g>")

    # generalization (đường liền + tam giác rỗng ở UC cha)
    for child, parent in GEN:
        s, e = seg(child, parent)
        o.append(f'<line x1="{s[0]:.1f}" y1="{s[1]:.1f}" x2="{e[0]:.1f}" y2="{e[1]:.1f}" stroke="#111" stroke-width="1.6"/>')
        o.append(f'<polygon points="{hollow_triangle(e, s)}" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/>')

    # extend (nét đứt, mũi tên mở về UC cơ sở)
    for src, dst, (lx, ly, anchor) in EXTEND:
        s, e = seg(src, dst)
        o.append(f'<line x1="{s[0]:.1f}" y1="{s[1]:.1f}" x2="{e[0]:.1f}" y2="{e[1]:.1f}" stroke="#111" stroke-width="1.5" stroke-dasharray="7 5"/>')
        o.append(f'<polyline points="{open_arrow(e, s)}" fill="none" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/>')
        o.append(f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="{EDGE_PX}" fill="#111">«extend»</text>')

    # use case ellipses
    for nid, (cx, cy, lines, italic) in NODES.items():
        o.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{RX}" ry="{RY}" fill="#fff" stroke="#111" stroke-width="1.8"/>')
        n = len(lines)
        first = cy - (n - 1) * 9 + 5.5
        style = ' font-style="italic"' if italic else ""
        o.append(f'<text text-anchor="middle" font-size="{LABEL_PX}" fill="#111"{style}>')
        for i, t in enumerate(lines):
            o.append(f'<tspan x="{cx}" y="{first + i * 18:.1f}">{escape(t)}</tspan>')
        o.append("</text>")

    # actor
    ax, ahead = ACTOR_X, ay - 44
    o.append('<g stroke="#111" stroke-width="1.8" fill="none">')
    o.append(f'<circle cx="{ax}" cy="{ahead}" r="11" fill="#fff"/>')
    o.append(f'<line x1="{ax}" y1="{ahead + 11}" x2="{ax}" y2="{ahead + 44}"/>')
    o.append(f'<line x1="{ax - 18}" y1="{ahead + 24}" x2="{ax + 18}" y2="{ahead + 24}"/>')
    o.append(f'<line x1="{ax}" y1="{ahead + 44}" x2="{ax - 15}" y2="{ahead + 68}"/>')
    o.append(f'<line x1="{ax}" y1="{ahead + 44}" x2="{ax + 15}" y2="{ahead + 68}"/>')
    o.append("</g>")
    o.append(f'<text text-anchor="middle" font-size="{LABEL_PX}" font-weight="700" fill="#111">')
    o.append(f'<tspan x="{ax}" y="{ahead + 90}">Quản trị viên</tspan><tspan x="{ax}" y="{ahead + 108}">(ADMIN)</tspan></text>')

    # chú giải
    ly = b["y"] + b["h"] + 34
    lx = b["x"]
    o.append(f'<text x="{lx}" y="{ly}" font-size="{LEGEND_PX}" font-weight="700" fill="#111">Chú giải</text>')
    row1, row2 = ly + 28, ly + 58
    o.append(f'<line x1="{lx}" y1="{row1 - 5}" x2="{lx + 46}" y2="{row1 - 5}" stroke="#111" stroke-width="1.6"/>')
    o.append(f'<text x="{lx + 56}" y="{row1}" font-size="{LEGEND_PX}" fill="#111">Association (ADMIN thực hiện UC)</text>')
    o.append(f'<line x1="{lx}" y1="{row2 - 5}" x2="{lx + 46}" y2="{row2 - 5}" stroke="#111" stroke-width="1.5" stroke-dasharray="7 5"/>')
    o.append(f'<polyline points="{open_arrow((lx + 46, row2 - 5), (lx, row2 - 5))}" fill="none" stroke="#111" stroke-width="1.5"/>')
    o.append(f'<text x="{lx + 56}" y="{row2}" font-size="{LEGEND_PX}" fill="#111">«extend»: từ UC mở rộng đến UC cơ sở</text>')
    cx2 = lx + 322
    o.append(f'<line x1="{cx2}" y1="{row1 - 5}" x2="{cx2 + 46}" y2="{row1 - 5}" stroke="#111" stroke-width="1.6"/>')
    o.append(f'<polygon points="{hollow_triangle((cx2 + 46, row1 - 5), (cx2, row1 - 5))}" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/>')
    o.append(f'<text x="{cx2 + 56}" y="{row1}" font-size="{LEGEND_PX}" fill="#111">Generalization: UC con → UC cha</text>')
    o.append(f'<text x="{cx2}" y="{row2}" font-size="{LEGEND_PX}" font-style="italic" fill="#111">Chữ nghiêng</text>')
    o.append(f'<text x="{cx2 + 92}" y="{row2}" font-size="{LEGEND_PX}" fill="#111">= UC trừu tượng</text>')
    o.append("</svg>")
    return "\n".join(o)


# ----------------------------------------------------------------------------- PlantUML
def build_puml() -> str:
    L = [
        "@startuml UCD-NHAP-DU-LIEU",
        "' Sinh tự động bởi build_ucd_nhap_du_lieu.py cùng tập quan hệ với UCD-NHAP-DU-LIEU.svg.",
        "' PlantUML tự bố cục (ra hình ngang); bản in A4 dọc dùng SVG có tọa độ kiểm soát.",
        "left to right direction",
        "skinparam dpi 120",
        'skinparam defaultFontName "Segoe UI"',
        "skinparam defaultFontSize 14",
        "skinparam shadowing false",
        "skinparam usecase {",
        "  BackgroundColor white",
        "  BorderColor black",
        "}",
        "skinparam actor {",
        "  BackgroundColor white",
        "  BorderColor black",
        "}",
        "skinparam ArrowColor black",
        "title Use Case — Phân hệ Nhập dữ liệu (Scopus–ICTU)",
        'actor "Quản trị viên\\n(ADMIN)" as ADMIN',
        'rectangle "Hệ thống Scopus–ICTU — Phân hệ Nhập dữ liệu" {',
    ]
    for nid, (_, _, lines, italic) in NODES.items():
        label = "\\n".join(lines)
        if italic:
            label = "<i>" + label.replace("\\n", "</i>\\n<i>") + "</i>"
        L.append(f'  usecase "{label}" as {nid}')
    L.append("}")
    for n in ASSOC:
        L.append(f"ADMIN -- {n}")
    for child, parent in GEN:
        L.append(f"{parent} <|-- {child}")
    for src, dst, _ in EXTEND:
        L.append(f"{dst} <.. {src} : <<extend>>")
    L.append("@enduml")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    (OUT / "render").mkdir(exist_ok=True)
    (OUT / "render" / "UCD-NHAP-DU-LIEU.svg").write_text(build_svg(), encoding="utf-8")
    (OUT / "UCD-NHAP-DU-LIEU.puml").write_text(build_puml(), encoding="utf-8")
    print("OK:", OUT / "render" / "UCD-NHAP-DU-LIEU.svg", OUT / "UCD-NHAP-DU-LIEU.puml")
