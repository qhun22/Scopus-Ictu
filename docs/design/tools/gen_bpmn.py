"""Sinh BPMN 2.0 (.bpmn có BPMNDI) và SVG từ một mô hình quy trình khai báo ngay trong tệp này.

    python -X utf8 gen_bpmn.py
Ghi: process/BPMN-1_quy_trinh_thuc_te.bpmn  (mở/chỉnh được bằng bpmn.io / Camunda Modeler)
     process/render/BPMN-1_quy_trinh_thuc_te.svg  (PNG xuất bằng render_svg_png.py)

Quy trình mô tả ĐÚNG phần mềm hiện có. KHÔNG có bước tự động phê duyệt danh tính: hệ thống chỉ đề xuất; APPROVED chỉ sau ACCEPT của người (ADR-004).
"""
from __future__ import annotations

import html
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
OUT = DESIGN / "process"

# ------------------------------------------------------------------ hình học
COL_W = 180
X0 = 150            # tâm cột 0
LANE_X = 20         # mép trái pool
LABEL_W = 34        # độ rộng nhãn làn
TASK_W, TASK_H = 164, 76
GW = 46
EV = 34
TOP = 50            # chừa tiêu đề pool
LANES = [  # (id, tên, chiều cao)
    ("lane_adm", "ADMIN\n(Quản trị viên)", 170),
    ("lane_sys", "Hệ thống\n(API/dịch vụ — tự động)", 250),
    ("lane_cli", "Kỹ thuật viên\n(script CLI)", 130),
    ("lane_rev", "REVIEWER / ADMIN\n(người duyệt)", 230),
    ("lane_lec", "LECTURER\n(Giảng viên)", 130),
]
LANE_Y = {}
y = TOP
for lid, _, h in LANES:
    LANE_Y[lid] = (y, h)
    y += h
POOL_H = y - TOP
SUB = {"u": -55, "l": 60, "m": 0, "ru": -45, "rl": 65}


LABEL_POS = {"G3": "bl", "G4": "tl"}   # vị trí nhãn cổng (mặc định: dưới)


def label_xy(n):
    pos = LABEL_POS.get(n["id"], "b")
    if pos == "bl":
        return n["cx"] - 30, n["cy"] + n["h"] / 2 + 14, "end"
    if pos == "tl":
        return n["cx"], n["cy"] - n["h"] / 2 - 22, "middle"
    return n["cx"], n["cy"] + n["h"] / 2 + 17, "middle"


def lane_cy(lane, sub="m"):
    top, h = LANE_Y[lane]
    return top + h / 2 + SUB.get(sub, 0)


# ------------------------------------------------------------------ nút
# id, loại, làn, cột, hàng con, nhãn, ghi chú
N = [
    ("S0", "start", "lane_adm", 0, "m", "Có dữ liệu nguồn\n(CSV Scopus / JSON GV)"),
    ("A1", "userTask", "lane_adm", 1, "m", "Tải tệp lên\n(UC-08 JSON / UC-10 CSV)"),
    ("S1", "serviceTask", "lane_sys", 2, "m", "Kiểm tra tệp: định dạng,\ncột EID, SHA-256 trùng,\nlỗi từng dòng; JSON: xem trước"),
    ("G1", "xor", "lane_sys", 3, "m", "Hợp lệ\nvà không trùng?"),
    ("AE", "userTask", "lane_adm", 3, "m", "Đọc lỗi theo dòng:\nsửa tệp hoặc xác nhận\nnhập trùng"),
    ("S2", "serviceTask", "lane_sys", 4, "m", "Lưu dữ liệu THÔ: JSON →\nlecturers + snapshot;\nCSV → scopus_imports,\nraw_scopus_records; audit"),
    ("G2", "xor", "lane_sys", 5, "m", "Là CSV\nScopus?"),
    ("E1", "end", "lane_sys", 6, "m", "Hồ sơ giảng viên\nđã lưu"),
    ("A3", "userTask", "lane_adm", 6, "m", "Chạy chuẩn hóa công bố\nvà bóc tách tác giả\n(UC-11, UC-12)"),
    ("S3", "serviceTask", "lane_sys", 7, "m", "Chuẩn hóa: EID chống trùng\n→ công bố + nguồn gốc;\ntác giả + vị trí tác giả"),
    ("C1", "scriptTask", "lane_cli", 8, "m", "Nạp bằng chứng ngoài:\ncông bố đã biết (Craw),\nđơn vị (OpenAlex/Crossref)"),
    ("C2", "scriptTask", "lane_cli", 9, "m", "Sinh ứng viên: 4 luật tên\n+ bằng chứng công bố;\nlưu PENDING, idempotent"),
    ("R1", "userTask", "lane_rev", 10, "ru", "Xem hàng đợi và\nbằng chứng ứng viên\n(UC-17)"),
    ("G3", "xor", "lane_rev", 11, "ru", "Quyết định\ncủa người duyệt?"),
    ("EP", "end", "lane_rev", 11, "rl", "Giữ PENDING\n(không ghi gì)"),
    ("S4", "serviceTask", "lane_sys", 12, "u", "Kiểm tra: ứng viên PENDING,\nphiên bản hiện hành,\nScopus ID chưa APPROVED"),
    ("S6", "serviceTask", "lane_sys", 12, "l", "Kiểm tra lý do bắt buộc;\nghi review REJECT\n+ audit"),
    ("G4", "xor", "lane_sys", 13, "u", "Hợp lệ?"),
    ("ER", "endError", "lane_rev", 13, "rl", "Dừng: HTTP 409\n(xung đột/dữ liệu cũ)"),
    ("S5", "serviceTask", "lane_sys", 14, "u", "Ghi review ACCEPT,\ndanh tính APPROVED,\nbằng chứng danh tính, audit"),
    ("GP", "and", "lane_sys", 15, "u", ""),
    ("R2", "userTask", "lane_rev", 15, "ru", "Truy vết: xem lịch sử\nreview, nhật ký\n(UC-19, UC-07)"),
    ("L1", "userTask", "lane_lec", 16, "m", "Xem liên kết Scopus\nvà công bố của tôi\n(UC-21, UC-22)"),
    ("E2", "end", "lane_rev", 17, "ru", "Đã truy vết"),
    ("E3", "end", "lane_lec", 17, "m", "Giảng viên\nkhai thác kết quả"),
]
NODES = {}
for nid, kind, lane, col, sub, label in N:
    cx = X0 + COL_W * col
    cy = lane_cy(lane, sub)
    if kind in ("userTask", "serviceTask", "scriptTask"):
        w, h = TASK_W, TASK_H
    elif kind in ("xor", "and"):
        w = h = GW
    else:
        w = h = EV
    NODES[nid] = dict(id=nid, kind=kind, lane=lane, label=label, cx=cx, cy=cy, w=w, h=h)

# ------------------------------------------------------------------ luồng
# (id, từ, tới, nhãn, đường đi: danh sách điểm trung gian dạng ('x',node)/('y',node)/số, hoặc None cho đường thẳng)
def L(n, side):  # điểm trên cạnh nút
    d = NODES[n]
    return {"l": (d["cx"] - d["w"] / 2, d["cy"]), "r": (d["cx"] + d["w"] / 2, d["cy"]),
            "t": (d["cx"], d["cy"] - d["h"] / 2), "b": (d["cx"], d["cy"] + d["h"] / 2)}[side]


def X(n):
    return NODES[n]["cx"]


def Y(n):
    return NODES[n]["cy"]


FLOWS = []


def flow(fid, a, b, sa, sb, via=(), name=""):
    pts = [L(a, sa)] + list(via) + [L(b, sb)]
    FLOWS.append(dict(id=fid, src=a, dst=b, pts=pts, name=name))


flow("f1", "S0", "A1", "r", "l")
flow("f2", "A1", "S1", "r", "t", via=[(X("S1"), Y("A1"))])
flow("f3", "S1", "G1", "r", "l")
flow("f4", "G1", "AE", "t", "b", name="Không")
flow("f5", "AE", "A1", "t", "t", via=[(X("AE"), Y("AE") - 62), (X("A1"), Y("AE") - 62)], name="Làm lại")
flow("f6", "G1", "S2", "r", "l", name="Có")
flow("f7", "S2", "G2", "r", "l")
flow("f8", "G2", "A3", "t", "l", via=[(X("G2"), Y("A3"))], name="CSV")
flow("f9", "G2", "E1", "r", "l", name="JSON")
flow("f10", "A3", "S3", "r", "t", via=[(X("S3"), Y("A3"))])
flow("f11", "S3", "C1", "r", "t", via=[(X("C1"), Y("S3"))])
flow("f12", "C1", "C2", "r", "l")
flow("f13", "C2", "R1", "r", "t", via=[(X("R1"), Y("C2"))])
flow("f14", "R1", "G3", "r", "l")
flow("f15", "G3", "S4", "t", "l", via=[(X("G3"), Y("S4"))], name="ACCEPT")
flow("f16", "G3", "S6", "r", "b", via=[(X("S6"), Y("G3"))], name="REJECT (lý do bắt buộc)")
flow("f17", "G3", "EP", "b", "t", name="Giữ PENDING")
flow("f18", "S4", "G4", "r", "l")
flow("f19", "G4", "S5", "r", "l", name="Có")
flow("f20", "G4", "ER", "b", "t", via=[], name="Không")
flow("f21", "S5", "GP", "r", "l")
flow("f22", "GP", "R2", "b", "t")
flow("f23", "GP", "L1", "r", "t", via=[(X("L1"), Y("GP"))])
flow("f24", "S6", "R2", "r", "l", via=[(X("S6") + 120, Y("S6")), (X("S6") + 120, Y("R2"))])
flow("f25", "R2", "E2", "r", "l")
flow("f26", "L1", "E3", "r", "l")

ANNOT = [
    dict(id="T1", x=X("S2") - 70, y=LANE_Y["lane_sys"][0] + LANE_Y["lane_sys"][1] - 62, w=330, h=52,
         text="Dữ liệu thô bất biến: raw_scopus_records.raw_payload và lecturer_source_snapshots không bị sửa khi chuẩn hóa.", attach="S2"),
    dict(id="T2", x=X("C1") - 90, y=LANE_Y["lane_rev"][0] + 24, w=400, h=70,
         text="KHÔNG có bước tự động phê duyệt: hệ thống chỉ ĐỀ XUẤT ứng viên; danh tính APPROVED chỉ được tạo sau ACCEPT của người (ADR-004, test_no_mapping_review_written).", attach="C2"),
]

TITLE = "BPMN-1 — Quy trình nghiệp vụ thực tế của Scopus–ICTU (nhập → kiểm tra → dữ liệu thô → chuẩn hóa → bằng chứng → đề xuất → người duyệt → truy vết)"
WIDTH = X0 + COL_W * 17 + 120
HEIGHT = TOP + POOL_H + 20


# ------------------------------------------------------------------ BPMN XML
def esc(s):
    return html.escape(s, quote=True).replace("\n", "&#10;")


def bpmn_xml():
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<!-- Sinh bởi docs/design/tools/gen_bpmn.py. Mở bằng https://demo.bpmn.io hoặc Camunda Modeler để chỉnh sửa. -->',
         '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
         'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
         'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="Definitions_ScopusIctu" targetNamespace="http://scopus-ictu/bpmn">',
         '  <bpmn:collaboration id="Collab_1">',
         '    <bpmn:participant id="Pool_1" name="Hệ thống Scopus–ICTU" processRef="Process_1" />',
         '  </bpmn:collaboration>',
         '  <bpmn:process id="Process_1" name="Quy trình nghiệp vụ thực tế" isExecutable="false">',
         '    <bpmn:laneSet id="LaneSet_1">']
    for lid, lname, _ in LANES:
        o.append(f'      <bpmn:lane id="{lid}" name="{esc(lname)}">')
        for n in NODES.values():
            if n["lane"] == lid:
                o.append(f'        <bpmn:flowNodeRef>{n["id"]}</bpmn:flowNodeRef>')
        o.append("      </bpmn:lane>")
    o.append("    </bpmn:laneSet>")
    out_of = {}
    in_of = {}
    for f in FLOWS:
        out_of.setdefault(f["src"], []).append(f["id"])
        in_of.setdefault(f["dst"], []).append(f["id"])
    for n in NODES.values():
        tag = {"start": "startEvent", "end": "endEvent", "endError": "endEvent", "xor": "exclusiveGateway", "and": "parallelGateway"}.get(n["kind"], n["kind"])
        attrs = f'id="{n["id"]}" name="{esc(n["label"])}"'
        io = "".join(f"\n      <bpmn:incoming>{i}</bpmn:incoming>" for i in in_of.get(n["id"], [])) + \
             "".join(f"\n      <bpmn:outgoing>{i}</bpmn:outgoing>" for i in out_of.get(n["id"], []))
        extra = ""
        if n["kind"] == "endError":
            extra = '\n      <bpmn:errorEventDefinition id="ErrDef_1" />'
        o.append(f"    <bpmn:{tag} {attrs}>{io}{extra}\n    </bpmn:{tag}>")
    for f in FLOWS:
        nm = f' name="{esc(f["name"])}"' if f["name"] else ""
        o.append(f'    <bpmn:sequenceFlow id="{f["id"]}"{nm} sourceRef="{f["src"]}" targetRef="{f["dst"]}" />')
    for a in ANNOT:
        o.append(f'    <bpmn:textAnnotation id="{a["id"]}"><bpmn:text>{esc(a["text"])}</bpmn:text></bpmn:textAnnotation>')
        o.append(f'    <bpmn:association id="As_{a["id"]}" sourceRef="{a["attach"]}" targetRef="{a["id"]}" />')
    o.append("  </bpmn:process>")
    o.append('  <bpmndi:BPMNDiagram id="Diagram_1">')
    o.append('    <bpmndi:BPMNPlane id="Plane_1" bpmnElement="Collab_1">')
    o.append(f'      <bpmndi:BPMNShape id="Pool_1_di" bpmnElement="Pool_1" isHorizontal="true"><dc:Bounds x="{LANE_X}" y="{TOP}" width="{WIDTH - LANE_X - 10}" height="{POOL_H}" /></bpmndi:BPMNShape>')
    for lid, _, h in LANES:
        ly, lh = LANE_Y[lid]
        o.append(f'      <bpmndi:BPMNShape id="{lid}_di" bpmnElement="{lid}" isHorizontal="true"><dc:Bounds x="{LANE_X + LABEL_W - 4}" y="{ly}" width="{WIDTH - LANE_X - LABEL_W - 6}" height="{lh}" /></bpmndi:BPMNShape>')
    for n in NODES.values():
        x, y = n["cx"] - n["w"] / 2, n["cy"] - n["h"] / 2
        extra = ' isMarkerVisible="true"' if n["kind"] == "xor" else ""
        o.append(f'      <bpmndi:BPMNShape id="{n["id"]}_di" bpmnElement="{n["id"]}"{extra}><dc:Bounds x="{x:g}" y="{y:g}" width="{n["w"]}" height="{n["h"]}" />')
        if n["kind"] in ("start", "end", "endError", "xor", "and") and n["label"]:
            lw = 120
            lx, ly2, anc = label_xy(n) if n["kind"] in ("xor", "and") else (n["cx"], n["cy"] + n["h"] / 2 + 17, "middle")
            bx = lx - lw if anc == "end" else lx - lw / 2
            o.append(f'        <bpmndi:BPMNLabel><dc:Bounds x="{bx:g}" y="{ly2 - 13:g}" width="{lw}" height="30" /></bpmndi:BPMNLabel>')
        o.append("      </bpmndi:BPMNShape>")
    for a in ANNOT:
        o.append(f'      <bpmndi:BPMNShape id="{a["id"]}_di" bpmnElement="{a["id"]}"><dc:Bounds x="{a["x"]:g}" y="{a["y"]:g}" width="{a["w"]}" height="{a["h"]}" /></bpmndi:BPMNShape>')
    for f in FLOWS:
        o.append(f'      <bpmndi:BPMNEdge id="{f["id"]}_di" bpmnElement="{f["id"]}">')
        for (px, py) in f["pts"]:
            o.append(f'        <di:waypoint x="{px:g}" y="{py:g}" />')
        if f["name"]:
            mx, my = f["pts"][0]
            o.append(f'        <bpmndi:BPMNLabel><dc:Bounds x="{mx + 4:g}" y="{my - 18:g}" width="80" height="14" /></bpmndi:BPMNLabel>')
        o.append("      </bpmndi:BPMNEdge>")
    for a in ANNOT:
        n = NODES[a["attach"]]
        o.append(f'      <bpmndi:BPMNEdge id="As_{a["id"]}_di" bpmnElement="As_{a["id"]}"><di:waypoint x="{n["cx"]:g}" y="{n["cy"] + n["h"] / 2:g}" /><di:waypoint x="{a["x"] + a["w"] / 2:g}" y="{a["y"]:g}" /></bpmndi:BPMNEdge>')
    o.append("    </bpmndi:BPMNPlane>")
    o.append("  </bpmndi:BPMNDiagram>")
    o.append("</bpmn:definitions>")
    return "\n".join(o) + "\n"


# ------------------------------------------------------------------ SVG
def wrap_lines(text):
    return text.split("\n")


def svg_text(cx, cy, label, size=12.5, weight="normal", fill="#1B2631", anchor="middle", lh=15):
    lines = wrap_lines(label)
    y0 = cy - lh * (len(lines) - 1) / 2 + size * 0.35
    out = [f'<text x="{cx:g}" y="{y0:g}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{fill}">']
    for i, ln in enumerate(lines):
        out.append(f'<tspan x="{cx:g}" dy="{0 if i == 0 else lh}">{html.escape(ln)}</tspan>')
    out.append("</text>")
    return "".join(out)


def svg():
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" font-family="Segoe UI, Arial, sans-serif">',
         '<defs><marker id="ar" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10 z" fill="#2C3E50"/></marker></defs>',
         f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#FFFFFF"/>',
         f'<text x="{WIDTH / 2:g}" y="30" text-anchor="middle" font-size="17" font-weight="bold" fill="#17202A">{html.escape(TITLE)}</text>']
    pw = WIDTH - LANE_X - 10
    o.append(f'<rect x="{LANE_X}" y="{TOP}" width="{pw}" height="{POOL_H}" fill="none" stroke="#2C3E50" stroke-width="1.6"/>')
    fills = ["#FEF5E7", "#EBF5FB", "#EAFAF1", "#F5EEF8", "#FDEDEC"]
    for k, (lid, lname, _) in enumerate(LANES):
        ly, lh = LANE_Y[lid]
        o.append(f'<rect x="{LANE_X}" y="{ly}" width="{pw}" height="{lh}" fill="{fills[k]}" fill-opacity="0.55" stroke="#2C3E50" stroke-width="1"/>')
        o.append(f'<rect x="{LANE_X}" y="{ly}" width="{LABEL_W}" height="{lh}" fill="{fills[k]}" stroke="#2C3E50" stroke-width="1"/>')
        cx, cy = LANE_X + LABEL_W / 2, ly + lh / 2
        lines = lname.split("\n")
        t = [f'<text transform="translate({cx:g},{cy:g}) rotate(-90)" text-anchor="middle" font-size="12.5" font-weight="bold" fill="#17202A">']
        for i, ln in enumerate(lines):
            t.append(f'<tspan x="0" dy="{0 if i == 0 else 15}">{html.escape(ln)}</tspan>')
        t.append("</text>")
        o.append("".join(t).replace('translate(', f'translate(', 1))
    # luồng
    for f in FLOWS:
        pts = " ".join(f"{x:g},{y:g}" for x, y in f["pts"])
        o.append(f'<polyline points="{pts}" fill="none" stroke="#2C3E50" stroke-width="1.6" marker-end="url(#ar)"/>')
    # nhãn luồng
    for f in FLOWS:
        if not f["name"]:
            continue
        (x1, y1), (x2, y2) = f["pts"][0], f["pts"][1]
        if abs(x2 - x1) >= abs(y2 - y1):
            lx, ly, anc = (x1 + 6, y1 - 6, "start")
        else:
            lx, ly, anc = (x1 + 6, y1 + (-8 if y2 < y1 else 16), "start")
        o.append(f'<text x="{lx:g}" y="{ly:g}" font-size="11" font-weight="bold" fill="#7B241C" text-anchor="{anc}">{html.escape(f["name"])}</text>')
    # nút
    for n in NODES.values():
        cx, cy, w, h = n["cx"], n["cy"], n["w"], n["h"]
        k = n["kind"]
        if k in ("userTask", "serviceTask", "scriptTask"):
            fill = {"userTask": "#FFFFFF", "serviceTask": "#D6EAF8", "scriptTask": "#E8DAEF"}[k]
            o.append(f'<rect x="{cx - w / 2:g}" y="{cy - h / 2:g}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="#1F3A5F" stroke-width="1.8"/>')
            mark = {"userTask": "👤", "serviceTask": "⚙", "scriptTask": "▤"}[k]
            o.append(f'<text x="{cx - w / 2 + 7:g}" y="{cy - h / 2 + 15:g}" font-size="11" fill="#1F3A5F">{mark}</text>')
            o.append(svg_text(cx, cy + 4, n["label"], size=11, lh=14))
        elif k in ("xor", "and"):
            pts = f"{cx:g},{cy - h / 2:g} {cx + w / 2:g},{cy:g} {cx:g},{cy + h / 2:g} {cx - w / 2:g},{cy:g}"
            o.append(f'<polygon points="{pts}" fill="#FEF9E7" stroke="#7D6608" stroke-width="1.8"/>')
            if k == "xor":
                o.append(f'<path d="M{cx - 9:g},{cy - 9:g} L{cx + 9:g},{cy + 9:g} M{cx + 9:g},{cy - 9:g} L{cx - 9:g},{cy + 9:g}" stroke="#7D6608" stroke-width="2.4"/>')
            else:
                o.append(f'<path d="M{cx - 11:g},{cy:g} L{cx + 11:g},{cy:g} M{cx:g},{cy - 11:g} L{cx:g},{cy + 11:g}" stroke="#7D6608" stroke-width="2.4"/>')
            if n["label"]:
                lx, ly2, anc = label_xy(n)
                o.append(svg_text(lx, ly2, n["label"], size=11, lh=13, anchor=anc))
        elif k == "start":
            o.append(f'<circle cx="{cx:g}" cy="{cy:g}" r="{w / 2}" fill="#E9F7EF" stroke="#1E8449" stroke-width="2"/>')
            o.append(svg_text(cx, cy + h / 2 + 22, n["label"], size=11, lh=13))
        else:
            stroke = "#922B21"
            o.append(f'<circle cx="{cx:g}" cy="{cy:g}" r="{w / 2}" fill="#FDEDEC" stroke="{stroke}" stroke-width="3.6"/>')
            if k == "endError":
                o.append(f'<path d="M{cx - 7:g},{cy + 7:g} L{cx - 3:g},{cy - 7:g} L{cx + 3:g},{cy + 2:g} L{cx + 7:g},{cy - 8:g}" fill="none" stroke="{stroke}" stroke-width="2"/>')
            o.append(svg_text(cx, cy + h / 2 + 20, n["label"], size=11, lh=13))
    # chú thích
    for a in ANNOT:
        x, y, w, h = a["x"], a["y"], a["w"], a["h"]
        o.append(f'<path d="M{x + 12:g},{y:g} L{x:g},{y:g} L{x:g},{y + h:g} L{x + 12:g},{y + h:g}" fill="none" stroke="#566573" stroke-width="1.4"/>')
        n = NODES[a["attach"]]
        o.append(f'<line x1="{n["cx"]:g}" y1="{n["cy"] + n["h"] / 2:g}" x2="{x + w / 2:g}" y2="{y:g}" stroke="#566573" stroke-dasharray="4 3"/>')
        words, lines, cur = a["text"].split(" "), [], ""
        for w_ in words:
            if len(cur) + len(w_) + 1 > int(w / 6.3):
                lines.append(cur)
                cur = w_
            else:
                cur = (cur + " " + w_).strip()
        lines.append(cur)
        o.append(svg_text(x + 10, y + h / 2, "\n".join(lines), size=11, anchor="start", lh=13, fill="#2E4053"))
    # chú giải
    ly = HEIGHT - 12
    o.append(f'<text x="{LANE_X + 8}" y="{ly}" font-size="11" fill="#566573">Chú giải: 👤 nhiệm vụ của người · ⚙ nhiệm vụ dịch vụ tự động · ▤ script CLI · ◇✕ cổng loại trừ · ◇+ cổng song song · vòng đậm = sự kiện kết thúc · nguồn: gen_bpmn.py (mô hình trong tệp)</text>')
    o.append("</svg>")
    return "\n".join(o) + "\n"


if __name__ == "__main__":
    (OUT / "render").mkdir(parents=True, exist_ok=True)
    (OUT / "BPMN-1_quy_trinh_thuc_te.bpmn").write_text(bpmn_xml(), encoding="utf8")
    (OUT / "render" / "BPMN-1_quy_trinh_thuc_te.svg").write_text(svg(), encoding="utf8")
    print("OK:", len(NODES), "nút,", len(FLOWS), "luồng; kích thước", WIDTH, "x", HEIGHT)
