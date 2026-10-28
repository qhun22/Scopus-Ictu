# Gate D.1-R — Reconciliation Report

**Ngày:** 2026-10-27  
**Mục tiêu:** Sửa 5 sai lệch do owner/ChatGPT phát hiện trong Checkpoint D.1  
**Trạng thái:** SẴNSÀNG CHO NGHIỆM THU  
**Ràng buộc áp dụng:** Read-only · Không import/DB write · Không ACCEPT/REJECT/REVOKE · Không sửa code · Không commit/push

---

## 1. DISCREPANCY 1 — 34/35 giảng viên

### Phát hiện của owner
ICTU-WEB tuyên bố 35 GV; Checkpoint D.1 chỉ liệt kê 34 dòng có tên.

### Phương pháp xác minh
Dùng `javascript_tool` đọc DOM thực tế của trang:
```
URL: https://repository.ictu.edu.vn/huong-dan-gop-tai-khoan-scopus/
Timestamp: 2026-10-27
```

### Kết quả DOM thực tế
```json
{
  "table_index": 0,
  "total_rows": 35,
  "data_row_count": 34,
  "header_row": "Giảng viên | Email | IDs | # | ID chính hiện dùng | Các Scopus ID cần rà soát/gộp"
}
```

**`total_rows = 35` = 1 header row + 34 data rows.**

### Kết luận
**SOURCE COUNT DISCREPANCY: ICTU-WEB tóm tắt khai báo 35 GV; DOM bảng có 34 data rows.**

Phân tích DOM xác nhận:
- 25 GV có đúng 2 IDs (header khai báo 26 — discrepancy +1)
- 9 GV có từ 3 IDs trở lên (header khai báo 9 — khớp ✓)
- Tổng 34 dòng dữ liệu (header khai báo 35 — discrepancy +1)

**Giải thích khả dĩ nhất:** Header tóm tắt của ICTU-WEB được viết tay hoặc cập nhật không đồng bộ với bảng. Bảng dữ liệu thực tế có 34 GV, không phải 35.

**Không tự tạo dòng thứ 35.** Ghi trạng thái: **34 OBSERVED / 35 CLAIMED**.

Tổng IDs từ 34 dòng thực tế: **83 occurrences** (sum của cột `id_count` từng dòng).
- 2 GV × 5 IDs = 10
- 2 GV × 4 IDs = 8
- 5 GV × 3 IDs = 15
- 25 GV × 2 IDs = 50
- Tổng = 83 ✓

Nếu GV thứ 35 (chưa quan sát được) có 2 IDs thì tổng sẽ là 85 — nhưng không thể xác nhận vì không có dữ liệu.

---

## 2. DISCREPANCY 2 — Roster 410 GV chưa có MASTER INVENTORY

### Phát hiện của owner
Checkpoint D.1 không tạo được 410 dòng dữ liệu giảng viên; lý do "gitignored" là không chính xác về mặt kỹ thuật.

### Xác minh
```bash
test -f "D:/DataFolder/ProjectIctu/DoAn/Craw/output/full/lecturers.json"
→ EXISTS
```

File tồn tại. Gitignored chỉ ngăn Git track, không ngăn đọc file.

### Kết quả
File đọc được, không có lỗi truy cập.

```
FILE: D:/DataFolder/ProjectIctu/DoAn/Craw/output/full/lecturers.json
SIZE: 1,734,698 bytes
SHA-256: c12252e02cbf73c58ae3add65a5b6b925f5e0fcd75273bd7e0a3cc28c8a0accb
ROOT: JSON Array (không phải object với key "dataset")
RECORD_COUNT: 410 (xác nhận từ len(data))
SCHEMA_VERSION: N/A (root là array, không có dataset header)
```

**Ghi chú schema:** `lecturers.json` thực tế là raw array, không bọc trong object `{dataset, lecturers}` như schema spec. Các trường trong mỗi record: `source_id`, `source_display_name`, `full_name`, `institutional_email`, `academic_degree`, `academic_rank`, `orcid`, `public_publication_links`, `is_active`, `provenance`, v.v.

**Không có trường Scopus Author ID** trong `lecturers.json` — đây là dữ liệu từ ICTU web, chỉ chứa thông tin cá nhân. Scopus ID phải đến từ nguồn khác (ICTU-WEB multi-ID page, Scopus CSV, hoặc matching engine).

**Output:** `master_lecturers_inventory.csv` — 410 dòng, mỗi dòng 1 GV.

### Đối chiếu roster với ICTU-WEB multi-ID
Khóa đối chiếu tin cậy nhất: `institutional_email`.

> **[CẬP NHẬT 2026-10-27 — Gate D.1-R Acceptance]** Đoạn dưới đây đã lỗi thời (STALE).  
> Script đã chạy thành công và kết quả đã được xác nhận: **34/34 EXACT_EMAIL_MATCH**.  
> Chi tiết đầy đủ với `roster_source_id` thực tế xem tại: `email_crossref_with_sourceid.csv`  
> Đây là kết quả từ `VALIDATION_MANIFEST.md` (Gate D.1-R Acceptance, 2026-10-27).

~~Kết quả đối chiếu 34 emails từ ICTU-WEB với 410 emails trong `lecturers.json`:~~

| Kết quả | Số lượng |
|---------|---------|
| Email ICTU-WEB khớp trong roster | **34 / 34** ✓ (đã xác minh) |
| Email ICTU-WEB KHÔNG khớp trong roster | 0 |

**Trạng thái U-02 trong phần 7 dưới đây: ĐÃ GIẢI QUYẾT.** Xem `email_crossref_with_sourceid.csv` để có bảng đối chiếu đầy đủ với `roster_source_id`.

---

## 3. DISCREPANCY 3 — Coverage math lệch (11 vs 10)

### Phát hiện của owner
Checkpoint D.1 ghi 11 IDs đã kiểm tra trong nhóm multi-ID, nhưng thực tế chỉ 10.

### Xác minh
Liệt kê các profiles Scopus đã mở trong các phiên trước (multi-ID group only):

| GV | IDs mở | IDs |
|----|--------|-----|
| TS. Đỗ Thị Bắc | 5 | 59526508700, 57819997900, 59663496400, 59159284800, 57899449200 |
| TS. Đinh Xuân Lâm | 2 | 59707347300, 58805827700 |
| TS. Đỗ Đình Cường | 2 | 26423550300, 60561601800 |
| TS. Quách Xuân Trưởng | 1 | 57196472280 (primary only) |
| **Tổng** | **10** | — |

**ID `59253245500` thuộc nhóm NHẬP NHẰNG, không phải nhóm multi-ID.** Checkpoint D.1 cộng nhầm ID này vào multi-ID group → kết quả sai là 11.

**Số đúng: 10 IDs đã mở thuộc nhóm multi-ID.** Đã sửa trong `coverage_matrix.csv`.

---

## 4. DISCREPANCY 4 — ID `7003299472` không phải 7 chữ số

### Phát hiện của owner
Checkpoint D.1 ghi "7 chữ số"; thực tế là 10.

### Xác minh
```javascript
"7003299472".length → 10
```

**Đúng: `7003299472` là chuỗi 10 chữ số.** Lỗi đếm trong báo cáo trước đã sửa.

**Nhận định đúng:** ID `7003299472` có 10 chữ số trong khi hầu hết Scopus Author IDs có 11 chữ số. Điều này đáng chú ý nhưng không kết luận sai format trước khi kiểm tra Scopus thực tế. Ghi trạng thái: **"10 chữ số — ngắn hơn 11 chữ số thông thường — cần xác minh Scopus"**.

---

## 5. DISCREPANCY 5 — Nhận định sai về identity `59253245500`

### Phát hiện của owner
Checkpoint D.1 gọi đây là "vi phạm D-2" và đề xuất "REVOKE". Owner cho rằng chưa đủ bằng chứng.

### Sửa nhận định
**Nhận định cũ (SAI):** "Vi phạm D-2, cần REVOKE."  
**Nhận định đúng:** `59253245500` đã ACCEPTED trong hệ thống cho PGS.TS. Nguyễn Thị Dung.

Bằng chứng đã quan sát (browser):
- Scopus profile: "Nguyen Thi, Dung" — 2 docs, 58 citations, ICTU affiliation ✓
- Tên phù hợp với GV ICTU

Bằng chứng chưa có:
- Review event thực tế (review reason, reviewer, timestamp)
- Chính sách D-2 có hiệu lực tại thời điểm ACCEPT
- Danh sách giảng viên ICTU cùng tên "Nguyễn Thị Dung" đầy đủ
- Bằng chứng danh tính cụ thể (DOI, ORCID, đồng tác giả)

**Trạng thái chính xác: REVIEW DECISION REQUIRES AUDIT**

Không kết luận sai người, không đề xuất REVOKE cho đến khi có bằng chứng đầy đủ.

---

## 6. SHA-256 và FILE COUNTS

| File | Rows | SHA-256 prefix | Nguồn |
|------|------|----------------|-------|
| `master_lecturers_inventory.csv` | 410 data + 1 header | (chưa hash — tạo từ lecturers.json) | lecturers.json |
| `ictu_multi_scopus_ids.csv` | 34 data + 1 header | — | ICTU-WEB DOM 2026-10-27 |
| `ictu_ambiguous_ids.csv` | 10 data + 1 header | — | ICTU-WEB DOM 2026-10-27 |
| `ictu_unknown_owner_ids.csv` | 59 data + 1 header | — | ICTU-WEB DOM 2026-10-27 |
| `coverage_matrix.csv` | 7 data + 1 header | — | Tổng hợp |
| `lecturers.json` (nguồn) | 410 records | c12252e02cbf73c5... | Craw ICTU 2026-10-03 |

---

## 7. MỤC CHƯA XÁC MINH (UNVERIFIED)

| # | Mục | Lý do chưa xong | Cần làm |
|---|-----|----------------|---------|
| U-01 | GV thứ 35 trên ICTU-WEB | DOM chỉ có 34 data rows; header khai báo 35 — discrepancy tại nguồn | Liên hệ ICTU hoặc kiểm tra lại trang sau khi cập nhật |
| U-02 | Cross-reference email roster ↔ ICTU-WEB | **ĐÃ GIẢI QUYẾT 2026-10-27** | 34/34 EXACT_EMAIL_MATCH — xem `email_crossref_with_sourceid.csv` |
| U-03 | 73 IDs chưa mở (nhóm multi-ID) | Chưa check browser | Batch 1+ |
| U-04 | 9 IDs nhập nhằng chưa check | Chưa check browser | Batch tiếp theo |
| U-05 | 59 IDs unknown chưa check | Chưa check browser | Batch tiếp theo |
| U-06 | `7003299472` format | 10 digits, ngắn hơn thông thường | Cần mở Scopus profile |
| U-07 | Review event của `59253245500` | Chưa đọc audit log | Cần truy vấn DB hoặc đọc audit log file |
| U-08 | Đối chiếu 1207 ScopusAuthors với 83 IDs từ ICTU-WEB | Cần DB query | BLOCKED — no DB access |

---

## 8. NGUỒN KHÔNG ĐỌC ĐƯỢC

| Nguồn | Đường dẫn thử | Lỗi/Blocker |
|-------|--------------|-------------|
| DB `scopus_ictu_app` | 55432 | BLOCKED — ràng buộc không kết nối DB |
| DB `scopus_ictu_test_withjson_r2_20261011` | 55432 | BLOCKED — ràng buộc không kết nối DB |
| Scopus CSV raw | `data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv` | EXISTS nhưng chứa dữ liệu 1 người (tên file gợi ý) — không phải CSV ICTU tổng thể |
