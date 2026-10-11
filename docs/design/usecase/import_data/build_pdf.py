#!/usr/bin/env python3
"""Ghép SVG vector + tiêu đề + ghi chú vào MỘT trang A4 dọc (210x297 mm) rồi in PDF bằng Chrome headless."""
from __future__ import annotations

import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
svg = (HERE / "render" / "UCD-NHAP-DU-LIEU.svg").read_text(encoding="utf-8")
svg = svg.replace('width="770" height="780"', 'style="width:180mm;height:auto;display:block"', 1)

html = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><title>UCD Nhập dữ liệu — Scopus–ICTU</title>
<style>
  @page {{ size: 210mm 297mm; margin: 0; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #fff; color: #111; font-family: 'Segoe UI', Arial, sans-serif; }}
  .page {{ width: 210mm; height: 297mm; padding: 14mm 15mm 12mm; overflow: hidden; }}
  h1 {{ font-size: 15pt; line-height: 1.25; }}
  .sub {{ font-size: 10pt; margin-top: 1.2mm; color: #222; }}
  .fig {{ margin-top: 3mm; }}
  .notes {{ margin-top: 3mm; font-size: 10pt; line-height: 1.38; }}
  .notes h2 {{ font-size: 10.5pt; margin-bottom: 1mm; }}
  .notes ol {{ padding-left: 5mm; }}
  .notes li {{ margin-bottom: 0.8mm; }}
  .foot {{ margin-top: 2.5mm; font-size: 9pt; color: #333; border-top: 0.3mm solid #999; padding-top: 1.5mm; }}
</style></head><body><div class="page">
  <h1>Sơ đồ Use Case — Phân hệ Nhập dữ liệu</h1>
  <div class="sub">Đồ án Scopus–ICTU · Hiện trạng (AS-IS) theo mã nguồn ngày 11/10/2026 · Actor duy nhất: Quản trị viên (ADMIN)</div>
  <div class="fig">{svg}</div>
  <div class="notes"><h2>Ghi chú đọc sơ đồ</h2><ol>
    <li><b>Quyền:</b> chỉ ADMIN nhập dữ liệu — mọi API <code>/imports…</code> và <code>/lecturers/import…</code> đều yêu cầu vai trò ADMIN; REVIEWER và LECTURER nhận 403.</li>
    <li><b>Hai luồng khác nhau:</b> CSV Scopus lưu <i>dữ liệu thô</i> ngay khi tải lên; JSON giảng viên được <i>xem trước (không ghi CSDL)</i> rồi mới nhập. «Nhập dữ liệu từ tệp» là UC trừu tượng gom hành vi chung (cảnh báo trùng, hủy tiến trình).</li>
    <li><b>«extend» có điều kiện:</b> tệp trùng nội dung; hủy khi chưa hoàn tất; hoàn tác sau khi đã nhập giảng viên; ẩn khỏi lịch sử khi đợt đang được sử dụng nên không xóa được.</li>
    <li><b>Ngoài phạm vi sơ đồ:</b> Chuẩn hóa dữ liệu, script nạp Craw/OpenAlex (CLI), Đặt lại hệ thống. «Xóa đợt nhập» không phải xóa toàn bộ dữ liệu đã nhập.</li>
  </ol></div>
  <div class="foot">Truy vết Actor/UC/API/FR: <code>docs/design/usecase/import_data/UCD-NHAP-DU-LIEU_BAO_CAO_KIEM_DINH.md</code></div>
</div></body></html>"""

(HERE / "UCD-NHAP-DU-LIEU_print.html").write_text(html, encoding="utf-8")
pdf = HERE / "UCD-NHAP-DU-LIEU.pdf"
cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
       f"--print-to-pdf={pdf}", (HERE / "UCD-NHAP-DU-LIEU_print.html").as_uri()]
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "", "->", pdf)
try:  # PNG xem trước: render từ chính tệp PDF (tùy chọn, cần pypdfium2)
    import pypdfium2 as pdfium
    pdfium.PdfDocument(str(pdf))[0].render(scale=2.2).to_pil().save(HERE / "render" / "UCD-NHAP-DU-LIEU.png")
    print("PNG xem trước: render/UCD-NHAP-DU-LIEU.png")
except ImportError:
    print("Bỏ qua PNG xem trước (không có pypdfium2).")
sys.exit(0 if pdf.exists() else 1)
