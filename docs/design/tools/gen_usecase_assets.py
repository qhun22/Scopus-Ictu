"""Sinh sơ đồ Use Case (PlantUML) và bảng UC từ usecase/usecase_map.json.

    python -X utf8 gen_usecase_assets.py
Ghi: usecase/diagrams/UCD-*.puml, usecase/UC_INVENTORY.md, usecase/ACTOR_UC_MATRIX.md
(Đọc usecase/RBAC_API_MATRIX.json do rbac_matrix.py sinh để in vai trò thật của từng API.)
"""
from __future__ import annotations

import json
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
UC_DIR = DESIGN / "usecase"
M = json.load(open(UC_DIR / "usecase_map.json", encoding="utf8"))
RBAC = {f"{o['method']} {o['path']}": o for o in json.load(open(UC_DIR / "RBAC_API_MATRIX.json", encoding="utf8"))}
UCS = {u["id"]: u for u in M["use_cases"]}
ACTORS = M["actors"]
GROUPS = M["groups"]

HEAD = """@startuml {name}
' Nguồn: docs/design/usecase/usecase_map.json (sinh bởi tools/gen_usecase_assets.py). Không sửa tay phần sinh tự động.
left to right direction
skinparam dpi 160
skinparam defaultFontName "Segoe UI"
skinparam defaultFontSize 12
skinparam shadowing false
skinparam packageStyle rectangle
skinparam usecase {{
  BackgroundColor #EAF2F8
  BorderColor #1F618D
  FontSize 12
}}
skinparam actor {{
  BackgroundColor #FDEBD0
  BorderColor #B9770E
}}
skinparam ArrowColor #34495E
skinparam ArrowFontSize 10
"""

ACTOR_NAME = {"ADMIN": 'Quản trị viên\\n(ADMIN)', "REVIEWER": 'Phê duyệt viên\\n(REVIEWER)',
              "LECTURER": 'Giảng viên\\n(LECTURER)', "TECH": 'Kỹ thuật viên\\n«CLI — không phải vai trò»'}
STATUS_SHORT = lambda s: "CLI" if "CLI" in s else ("API" if "CHỈ API" in s else ("một phần" if "MỘT PHẦN" in s else ""))


def uc_label(u):
    note = STATUS_SHORT(u["status"])
    extra = f"\\n[{note}]" if note else ""
    return f'{u["id"]}\\n{u["name"]}{extra}'.replace('"', "'")


def wrap(text, width=26):
    out, line = [], ""
    for w in text.split(" "):
        if len(line) + len(w) + 1 > width and line:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    out.append(line)
    return "\\n".join(out)


def uc_label_wrapped(u):
    note = STATUS_SHORT(u["status"])
    s = f'{u["id"]}\\n' + wrap(u["name"].replace('"', "'"))
    if note:
        s += f"\\n[{note}]"
    return s


def sid(uc_id):
    return uc_id.replace("-", "")


def legend(extra=""):
    return ("legend bottom right\n  <b>Chú giải</b>\n  Oval = use case có thật trong mã (ID khớp UC_INVENTORY.md)\n"
            "  [CLI] chạy bằng script · [API] chỉ có API, chưa có giao diện · [một phần] triển khai chưa đầy đủ\n"
            "  Đường nét liền actor—UC = quyền truy cập đã đối chiếu với require_role (RBAC_API_MATRIX)\n" + extra +
            "endlegend\n")


def diagram(name, title, uc_ids, extra_legend="", only_actor=None):
    actors = []
    for i in uc_ids:
        for a in UCS[i]["actors"]:
            if a not in actors and (only_actor is None or a == only_actor):
                actors.append(a)
    order = ["ADMIN", "REVIEWER", "LECTURER", "TECH"]
    actors.sort(key=order.index)
    L = [HEAD.format(name=name), f"title {title}\n"]
    for a in actors:
        stereo = " <<CLI>>" if a == "TECH" else ""
        L.append(f'actor "{ACTOR_NAME[a]}" as {a}{stereo}')
    L.append("")
    by_group = {}
    for i in uc_ids:
        by_group.setdefault(UCS[i]["group"], []).append(i)
    for g, ids in by_group.items():
        L.append(f'rectangle "{GROUPS[g]}" {{')
        for i in ids:
            L.append(f'  usecase "{uc_label_wrapped(UCS[i])}" as {sid(i)}')
        L.append("}")
    L.append("")
    for i in uc_ids:
        for a in UCS[i]["actors"]:
            if only_actor is None or a == only_actor:
                L.append(f"{a} --> {sid(i)}")
    for i in uc_ids:
        u = UCS[i]
        if u.get("extends") and u["extends"] in uc_ids:
            L.append(f'{sid(i)} .> {sid(u["extends"])} : <<extend>>')
        for inc in u.get("includes", []):
            if inc in uc_ids:
                L.append(f'{sid(i)} .> {sid(inc)} : <<include>>')
    L.append(legend(extra_legend))
    L.append("@enduml")
    return "\n".join(L) + "\n"


def overview():
    """Tổng thể mức nhóm. ADMIN ở bên trái, các actor còn lại ở bên phải để giảm giao cắt."""
    order = ["G1", "G4", "G5", "XT", "G3", "G2"]
    head = HEAD.format(name="UCD-0_tong_the") + "skinparam linetype ortho\n"
    L = [head, "title UCD-0 — Use Case tổng thể theo nhóm nghiệp vụ (ba actor + script CLI)\n"]
    L.append(f'actor "{ACTOR_NAME["ADMIN"]}" as ADMIN')
    for a in ["REVIEWER", "LECTURER", "TECH"]:
        stereo = " <<CLI>>" if a == "TECH" else ""
        L.append(f'actor "{ACTOR_NAME[a]}" as {a}{stereo}')
    L.append("")
    L.append('rectangle "Hệ thống Scopus–ICTU (mức nhóm — chi tiết xem UCD-1…UCD-6)" {')
    for g in order:
        ids = [u["id"] for u in M["use_cases"] if u["group"] == g]
        L.append(f'  usecase "{wrap(GROUPS[g], 24)}\\n({", ".join(ids)})" as {g}')
    L.append("}")
    L.append("")
    for g in order:
        acts = set()
        for u in M["use_cases"]:
            if u["group"] == g:
                acts |= set(u["actors"])
        for a in ["ADMIN", "REVIEWER", "LECTURER", "TECH"]:
            if a in acts:
                L.append(f"{a} --> {g}")
    L.append(legend("  Mỗi oval = một NHÓM use case; actor nối tới nhóm nếu có ít nhất một UC trong nhóm dành cho actor đó.\n"
                    "  Quyền chi tiết từng UC xem ACTOR_UC_MATRIX.md; 5 nhóm 1–5 khớp 5 UC chính của đề cương (PI-1.3).\n"))
    L.append("@enduml")
    return "\n".join(L) + "\n"


def write_diagrams():
    d = UC_DIR / "diagrams"
    d.mkdir(exist_ok=True)
    # UCD-0: tổng quan mức nhóm, cả 3 vai trò
    (d / "UCD-0_tong_the.puml").write_text(overview(), encoding="utf8")
    for actor, tag, label in (("ADMIN", "0A", "Quản trị viên (ADMIN)"), ("REVIEWER", "0B", "Phê duyệt viên (REVIEWER)"), ("LECTURER", "0C", "Giảng viên (LECTURER)")):
        ids = [u["id"] for u in M["use_cases"] if actor in u["actors"]]
        name = f"UCD-{tag}_tong_the_{actor.lower()}"
        (d / f"{name}.puml").write_text(diagram(name, f"UCD-{tag} — Use Case tổng thể của {label}: {len(ids)} UC", ids, only_actor=actor), encoding="utf8")
    spec = [
        ("UCD-1_nhap_du_lieu", "UCD-1 — Nhóm 1: Nhập dữ liệu", "G1"),
        ("UCD-2_quan_ly_ho_so", "UCD-2 — Nhóm 2: Quản lý hồ sơ tác giả/giảng viên", "G2"),
        ("UCD-3_quan_ly_cong_bo", "UCD-3 — Nhóm 3: Quản lý công bố", "G3"),
        ("UCD-4_chuan_hoa_doi_soat_phe_duyet", "UCD-4 — Nhóm 4: Chuẩn hóa, đối soát và phê duyệt", "G4"),
        ("UCD-5_tim_kiem_thong_ke_xuat", "UCD-5 — Nhóm 5: Tìm kiếm, thống kê và xuất dữ liệu", "G5"),
        ("UCD-6_xac_thuc_giam_sat", "UCD-6 — Xác thực, thông báo, giám sát và khởi tạo", "XT"),
    ]
    for name, title, g in spec:
        ids = [u["id"] for u in M["use_cases"] if u["group"] == g]
        extra = ""
        if g == "G4":
            extra = ("  UC-18 «include» UC-17: yêu cầu duyệt bắt buộc observation_id + candidate_version lấy từ chi tiết ứng viên (ReviewDecisionRequest).\n"
                     "  UC-11 → UC-12 là THỨ TỰ tiền điều kiện (cần công bố đã chuẩn hóa), không vẽ include/extend.\n")
        if g == "G1":
            extra = "  «extend» = hành vi tùy chọn trên đợt nhập đã có (hoàn tác/hủy/lưu trữ/xóa).\n"
        (d / f"{name}.puml").write_text(diagram(name.split("_")[0] + "_" + "_".join(name.split("_")[1:]), title, ids, extra), encoding="utf8")


def roles_of(uc):
    roles = set()
    for op in uc["ops"]:
        r = RBAC[op]
        roles |= set(r["roles"]) if r["roles"] else set()
    return sorted(roles)


def access_label(op):
    r = RBAC[op]
    return {"PUBLIC": "công khai", "AUTHENTICATED": "đã đăng nhập"}.get(r["access"], "/".join(r["roles"]))


def write_tables():
    L = ["# Danh mục Use Case có thật (28)\n",
         "> **Sinh tự động** từ `usecase_map.json` + `RBAC_API_MATRIX.json` (rút từ mã FastAPI) bởi `tools/gen_usecase_assets.py`. "
         "Mọi UC có route/API/script thật; `tools/check_consistency.py` kiểm lại quyền (actor ↔ `require_role`) và route giao diện (↔ `frontend/src/App.tsx`).\n",
         "Trạng thái: **ĐÃ TRIỂN KHAI** = có đường chạy hoàn chỉnh · **MỘT PHẦN** · **CHỈ API** (chưa có UI) · **CHỈ CLI** (script, không có nút).\n"]
    for g, gname in GROUPS.items():
        ids = [u for u in M["use_cases"] if u["group"] == g]
        L.append(f"## {gname}\n")
        L.append("| UC | Tên | Actor | API (quyền thực từ mã) | Giao diện | Trạng thái | Quan hệ UML |")
        L.append("|---|---|---|---|---|---|---|")
        for u in ids:
            acts = ", ".join(u["actors"])
            ops = "<br>".join(f"`{o}` ({access_label(o)})" for o in u["ops"]) or ("script: " + ", ".join(f"`{s}`" for s in u.get("script", [])))
            ui = ", ".join(f"`{x}`" for x in u["ui"]) or "—"
            if u.get("ui_note"):
                ui += f"<br><i>{u['ui_note']}</i>"
            rel = []
            if u.get("extends"):
                rel.append(f"«extend» {u['extends']}")
            for i in u.get("includes", []):
                rel.append(f"«include» {i}")
            L.append(f"| **{u['id']}** | {u['name']} | {acts} | {ops} | {ui} | {u['status']} | {'; '.join(rel) or '—'} |")
        L.append("")
    L.append("## Không phải use case nghiệp vụ (đã loại có chủ đích)\n")
    for k, v in M["unmapped_ops_allowed"].items():
        L.append(f"- `{k}` — {v}")
    L.append("- `/tasks` (trang giữ chỗ `NOT_IMPLEMENTED`), `/users` (chuyển hướng sang `/lecturers`), `DiffViewerStub` (không được dùng).")
    (UC_DIR / "UC_INVENTORY.md").write_text("\n".join(L) + "\n", encoding="utf8")

    # Ma trận
    names = {"ADMIN": "ADMIN", "REVIEWER": "REVIEWER", "LECTURER": "LECTURER"}
    L = ["# Ma trận Actor × Use Case\n",
         "> **Sinh tự động** từ `usecase_map.json`. `●` = được phép · `–` = bị từ chối (API trả 403; giao diện ẩn menu) · `CLI` = chạy bằng script (không phải vai trò). "
         "Cột \"Khớp mã\" = kết quả đối chiếu với `require_role` thật (xem `check_consistency.py`).\n",
         "| UC | Tên | ADMIN | REVIEWER | LECTURER | Script | Quyền theo mã |",
         "|---|---|:-:|:-:|:-:|:-:|---|"]
    for u in sorted(M["use_cases"], key=lambda x: x["id"]):
        cells = ["●" if a in u["actors"] else "–" for a in ("ADMIN", "REVIEWER", "LECTURER")]
        tech = "CLI" if "TECH" in u["actors"] else "–"
        real = roles_of(u)
        real_s = "/".join(real) if real else ("mọi vai trò đã đăng nhập" if u["ops"] else "—")
        L.append(f"| {u['id']} | {u['name']} | {cells[0]} | {cells[1]} | {cells[2]} | {tech} | {real_s} |")
    L.append("")
    tot = {a: sum(1 for u in M["use_cases"] if a in u["actors"]) for a in ACTORS}
    L.append(f"**Tổng:** ADMIN {tot['ADMIN']} UC · REVIEWER {tot['REVIEWER']} UC · LECTURER {tot['LECTURER']} UC · script (CLI) {tot['TECH']} UC.")
    (UC_DIR / "ACTOR_UC_MATRIX.md").write_text("\n".join(L) + "\n", encoding="utf8")


if __name__ == "__main__":
    write_diagrams()
    write_tables()
    print("OK:", len(UCS), "use case")
