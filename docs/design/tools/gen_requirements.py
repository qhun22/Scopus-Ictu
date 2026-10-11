"""Sinh requirements/01_FR_NFR.md và .csv từ tools/fr_nfr_data.py và kiểm tên test có thật.

    python -X utf8 gen_requirements.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fr_nfr_data import FR, NFR  # noqa: E402

DESIGN = Path(__file__).resolve().parents[1]
REPO = DESIGN.parents[1]
TESTS = REPO / "backend" / "tests"

# --- kiểm tên test có thật (hàm hoặc tên tệp)
funcs, files = set(), set()
for p in TESTS.rglob("test_*.py"):
    files.add(p.stem)
    funcs.update(re.findall(r"^\s*(?:async\s+)?def (test_\w+)", p.read_text(encoding="utf8"), re.M))
missing = []
for r in FR + NFR:
    for name in re.findall(r"\btest_[a-z0-9_]+\b", r["tests"]):
        if name not in funcs and name not in files:
            # cho phép dạng rút gọn "test_01…03", "test_a2_t10…t13": phần trước dấu … là tiền tố hàm
            if any(f.startswith(name) for f in funcs):
                continue
            missing.append((r["id"], name))
if missing:
    print("TÊN TEST KHÔNG TỒN TẠI:", missing)
    sys.exit(1)

GROUPS = {"XT": "Xác thực, phân quyền, giám sát", "G1": "Nhóm 1 — Nhập dữ liệu", "G2": "Nhóm 2 — Quản lý hồ sơ tác giả/giảng viên",
          "G3": "Nhóm 3 — Quản lý công bố", "G4": "Nhóm 4 — Chuẩn hóa, đối soát và phê duyệt", "G5": "Nhóm 5 — Tìm kiếm, thống kê, xuất dữ liệu"}


def cell(s):
    return s.replace("|", "\\|").replace("\n", " ")


L = ["# Đặc tả yêu cầu chức năng (FR) và phi chức năng (NFR)\n",
     "> **Sinh tự động** từ `tools/fr_nfr_data.py` bởi `tools/gen_requirements.py`; mọi tên test pytest trong cột \"Bằng chứng test\" đã được kiểm là có thật trong `backend/tests`. "
     "Mã yêu cầu **ổn định** (không đánh số lại); thêm yêu cầu mới thì dùng số kế tiếp.\n",
     "> **Đây là bản nháp đề xuất của sinh viên.** Tiêu chí nghiệm thu chưa được GVHD xác nhận (GAP-12). Trạng thái chỉ dùng bốn giá trị: **ĐÃ TRIỂN KHAI · MỘT PHẦN · CHƯA TRIỂN KHAI · CHƯA KIỂM CHỨNG**. "
     "\"Bằng chứng test\" chỉ nêu test tự động; số liệu 797 test PASS và kết quả E2E trình duyệt là **THEO BÁO CÁO TRƯỚC** (Task 16–17), Task 19 không chạy lại.\n"]
n_fr = len(FR)
by = {}
for r in FR:
    by[r["status"]] = by.get(r["status"], 0) + 1
nby = {}
for r in NFR:
    nby[r["status"]] = nby.get(r["status"], 0) + 1
L.append("## Tổng hợp\n")
L.append("| Loại | Tổng | ĐÃ TRIỂN KHAI | MỘT PHẦN | CHƯA TRIỂN KHAI | CHƯA KIỂM CHỨNG |")
L.append("|---|--:|--:|--:|--:|--:|")
L.append(f"| FR | {n_fr} | {by.get('ĐÃ TRIỂN KHAI', 0)} | {by.get('MỘT PHẦN', 0)} | {by.get('CHƯA TRIỂN KHAI', 0)} | {by.get('CHƯA KIỂM CHỨNG', 0)} |")
L.append(f"| NFR | {len(NFR)} | {nby.get('ĐÃ TRIỂN KHAI', 0)} | {nby.get('MỘT PHẦN', 0)} | {nby.get('CHƯA TRIỂN KHAI', 0)} | {nby.get('CHƯA KIỂM CHỨNG', 0)} |")
L.append("")
L.append("**Yêu cầu của đề cương chưa có FR tương ứng vì CHƯA triển khai** (xem `gap/GAP_DE_CUONG_VS_CODE.md`): so sánh trước/sau chuẩn hóa (GAP-05), đánh giá trên tập đối chiếu GVHD (GAP-06), hoàn tác quyết định duyệt (GAP-07), "
         "mức độ phù hợp (GAP-04), xuất CSV/Excel (GAP-09). Không đưa các mục này vào bảng FR như thể đã làm.\n")

HDR = "| ID | Mô tả | Actor | Đầu vào → Đầu ra | Điều kiện nghiệm thu | Trạng thái | Mã nguồn / API | Bằng chứng test | Giới hạn hiện tại |"
SEP = "|---|---|---|---|---|---|---|---|---|"
L.append("# 1. Yêu cầu chức năng (FR)\n")
for g, gname in GROUPS.items():
    rows = [r for r in FR if r["group"] == g]
    if not rows:
        continue
    L.append(f"## {gname}\n")
    L.append(HDR)
    L.append(SEP)
    for r in rows:
        io = f"**Vào:** {r['inp']}<br>**Ra:** {r['out']}"
        L.append(f"| **{r['id']}** {r['title']} ({r['uc']}) | {cell(r['desc'])} | {r['actor']} | {cell(io)} | {cell(r['accept'])} | **{r['status']}** | {cell(r['code'])} | {cell(r['tests'])} | {cell(r['limit'])} |")
    L.append("")
L.append("# 2. Yêu cầu phi chức năng (NFR)\n")
L.append(HDR)
L.append(SEP)
for r in NFR:
    io = f"**Vào:** {r['inp']}<br>**Ra:** {r['out']}"
    L.append(f"| **{r['id']}** {r['title']} | {cell(r['desc'])} | {r['actor']} | {cell(io)} | {cell(r['accept'])} | **{r['status']}** | {cell(r['code'])} | {cell(r['tests'])} | {cell(r['limit'])} |")
L.append("")
(DESIGN / "requirements" / "01_FR_NFR.md").write_text("\n".join(L) + "\n", encoding="utf8")
with open(DESIGN / "requirements" / "01_FR_NFR.csv", "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "loai", "nhom", "ten", "mo_ta", "actor", "dau_vao", "dau_ra", "dieu_kien_nghiem_thu", "trang_thai", "ma_nguon_api", "bang_chung_test", "gioi_han", "uc"])
    for r in FR:
        w.writerow([r["id"], "FR", r["group"], r["title"], r["desc"], r["actor"], r["inp"], r["out"], r["accept"], r["status"], r["code"], r["tests"], r["limit"], r["uc"]])
    for r in NFR:
        w.writerow([r["id"], "NFR", "", r["title"], r["desc"], r["actor"], r["inp"], r["out"], r["accept"], r["status"], r["code"], r["tests"], r["limit"], ""])
print(f"OK: {len(FR)} FR, {len(NFR)} NFR; tên test đã kiểm ({len(funcs)} hàm test, {len(files)} tệp)")
