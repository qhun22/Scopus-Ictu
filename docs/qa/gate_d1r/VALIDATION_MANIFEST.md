# Gate D.1-R — Validation Manifest

**Ngày tạo:** 2026-10-27  
**Mục đích:** Bàn giao 6 artifact để owner/ChatGPT kiểm tra độc lập trước khi mở Batch 1  
**Trạng thái:** READY FOR INDEPENDENT REVIEW — BATCH 1 CHƯA BẮT ĐẦU  
**Ràng buộc áp dụng:** Read-only · Không import/DB write · Không ACCEPT/REJECT/REVOKE · Không sửa code · Không commit/push

---

## 1. GIT HEAD SHA

```
Repo:   D:\DataFolder\ProjectIctu\DoAn\Scopus-Ictu
Branch: main
HEAD:   80a5e2a (Khôi phục cấu hình khởi chạy Claude dạng di động)
```

---

## 2. ARTIFACT FILE MANIFEST

| # | File | Path (relative to repo root) | Size (bytes) | SHA-256 | Data rows |
|---|------|------------------------------|--------------|---------|-----------|
| 1 | master_lecturers_inventory.csv | docs/qa/gate_d1r/master_lecturers_inventory.csv | 56,143 | `b0122bf8bc9503682c1589cdb8f5de7690ddd5811b418f457457db81e9df216b` | 410 |
| 2 | ictu_multi_scopus_ids.csv | docs/qa/gate_d1r/ictu_multi_scopus_ids.csv | 4,631 | `8e782e12c689e7563dfd88e02d8c0c8f145b3c7634029faf7759251c8ddb77c0` | 34 |
| 3 | ictu_ambiguous_ids.csv | docs/qa/gate_d1r/ictu_ambiguous_ids.csv | 1,153 | `1cbb9235e0d0ed32004b9aeaea25e1d8b2157d9b35dda978584d23c7ade91d7d` | 10 |
| 4 | ictu_unknown_owner_ids.csv | docs/qa/gate_d1r/ictu_unknown_owner_ids.csv | 4,029 | `a92311df1045c9d12b251de9326457cb831543bcb5c09081d8ad497dbc4678fc` | 59 |
| 5 | coverage_matrix.csv | docs/qa/gate_d1r/coverage_matrix.csv | 1,206 | `73303ad6b132454e8969073ad3c70a16e4bf164a3fb50d37e279486e710d3103` | 7 |
| 6 | RECONCILIATION_REPORT.md | docs/qa/gate_d1r/RECONCILIATION_REPORT.md | 9,057 | `4ce4046a3cafc3a3c596e85f163c8c1ac21c1a4eacdd0c8537712fe5098dc352` | 199 lines (non-blank) |

**Lưu ý:** `coverage_matrix.csv` có 7 data rows (không phải dòng header). `RECONCILIATION_REPORT.md` có 199 dòng nội dung (non-blank lines). SHA-256 trên là của file gốc tại thời điểm tạo ZIP Gate D.1-R; file đã được cập nhật sau đó (Gate D.1 Closeout) — xem ZIP mới để có checksum cập nhật.

---

## 3. ROSTER UNIQUENESS (master_lecturers_inventory.csv)

| Kiểm tra | Kết quả |
|----------|---------|
| Tổng số dòng dữ liệu | 410 |
| Unique source_id | 410 / 410 ✓ |
| Unique institutional_email | 410 / 410 ✓ |
| Emails trống | 0 ✓ |
| Source_id trùng lặp | 0 ✓ |
| Email trùng lặp | 0 ✓ |
| Dòng có ORCID | 372 / 410 |
| Dòng có pub_link_count > 0 | 106 / 410 |

Nguồn dữ liệu: `lecturers.json` tại `D:\DataFolder\ProjectIctu\DoAn\Craw\output\full\lecturers.json`  
SHA-256 lecturers.json: `c12252e02cbf73c58ae3add65a5b6b925f5e0fcd75273bd7e0a3cc28c8a0accb`  
Kích thước lecturers.json: 1,734,698 bytes  
Cấu trúc: JSON Array (không phải object với key `dataset`); 410 records

---

## 4. CROSS-REFERENCE: ICTU-WEB EMAILS ↔ ROSTER 410

**Phương pháp:** Khớp cột `email` trong `ictu_multi_scopus_ids.csv` với cột `institutional_email` trong `master_lecturers_inventory.csv` theo exact string match.

| Kết quả | Số lượng |
|---------|---------|
| EXACT_EMAIL_MATCH (email ICTU-WEB khớp chính xác trong roster) | **34 / 34** |
| NO_EMAIL_MATCH | 0 |
| AMBIGUOUS | 0 |

**Kết luận:** Tất cả 34 GV có nhiều Scopus ID trong ICTU-WEB đều có bản ghi chính xác trong roster 410 người. Email là khóa đối chiếu tin cậy cho mọi bước tiếp theo.

Chi tiết 34 cặp đối chiếu (email → source_id):

| Row | Email (ICTU-WEB) | Tên (ICTU-WEB) | Kết quả |
|-----|-----------------|----------------|---------|
| 1 | dtbac@ictu.edu.vn | TS. Đỗ Thị Bắc | EXACT_EMAIL_MATCH |
| 2 | lmhue@ictu.edu.vn | ThS. Lương Thị Minh Huế | EXACT_EMAIL_MATCH |
| 3 | nhminh@ictu.edu.vn | TS. Nguyễn Hải Minh | EXACT_EMAIL_MATCH |
| 4 | qxtruong@ictu.edu.vn | TS. Quách Xuân Trưởng | EXACT_EMAIL_MATCH |
| 5 | lhlinh@ictu.edu.vn | TS. Lê Hùng Linh | EXACT_EMAIL_MATCH |
| 6 | nvtao@ictu.edu.vn | TS. Nguyễn Văn Tảo | EXACT_EMAIL_MATCH |
| 7 | nhhuy@ictu.edu.vn | TS. Ngô Hữu Huy | EXACT_EMAIL_MATCH |
| 8 | pdlong@ictu.edu.vn | TS. Phạm Đức Long | EXACT_EMAIL_MATCH |
| 9 | tqquy@ictu.edu.vn | TS. Trần Quang Quý | EXACT_EMAIL_MATCH |
| 10 | dqa@ictu.edu.vn | GS.TS. Đặng Quang Á | EXACT_EMAIL_MATCH |
| 11 | nthanh@ictu.edu.vn | Nguyễn Thị Hải Anh | EXACT_EMAIL_MATCH |
| 12 | nvhuan@ictu.edu.vn | PGS.TS. Nguyễn Văn Huân | EXACT_EMAIL_MATCH |
| 13 | ptnghia@ictu.edu.vn | PGS.TS. Phùng Trung Nghĩa | EXACT_EMAIL_MATCH |
| 14 | nthang@ictu.edu.vn | TS. Nguyễn Thị Hằng | EXACT_EMAIL_MATCH |
| 15 | ntmphuong@ictu.edu.vn | TS. Nguyễn Thị Mai Phương | EXACT_EMAIL_MATCH |
| 16 | nttnhan@ictu.edu.vn | TS. Nguyễn Thị Thanh Nhàn | EXACT_EMAIL_MATCH |
| 17 | thangnt@ictu.edu.vn | TS. Nguyễn Toàn Thắng | EXACT_EMAIL_MATCH |
| 18 | ndbinh@ictu.edu.vn | TS. Nguyễn Đức Bình | EXACT_EMAIL_MATCH |
| 19 | ttxuan@ictu.edu.vn | TS. Trần Thị Xuân | EXACT_EMAIL_MATCH |
| 20 | tvkhanh@ictu.edu.vn | TS. Trần Văn Khánh | EXACT_EMAIL_MATCH |
| 21 | thnguyen@ictu.edu.vn | TS. Tô Hữu Nguyên | EXACT_EMAIL_MATCH |
| 22 | vcthang@ictu.edu.vn | TS. Vũ Chiến Thắng | EXACT_EMAIL_MATCH |
| 23 | vxnam@ictu.edu.vn | TS. Vũ Xuân Nam | EXACT_EMAIL_MATCH |
| 24 | dxlam@ictu.edu.vn | TS. Đinh Xuân Lâm | EXACT_EMAIL_MATCH |
| 25 | ddcuong@ictu.edu.vn | TS. Đỗ Đình Cường | EXACT_EMAIL_MATCH |
| 26 | lsthai@ictu.edu.vn | ThS. Lê Sơn Thái | EXACT_EMAIL_MATCH |
| 27 | nhtan@ictu.edu.vn | ThS. Nguyễn Hồng Tân | EXACT_EMAIL_MATCH |
| 28 | nkson@ictu.edu.vn | ThS. Nguyễn Kim Sơn | EXACT_EMAIL_MATCH |
| 29 | nvviet@ictu.edu.vn | ThS. Nguyễn Văn Việt | EXACT_EMAIL_MATCH |
| 30 | ptthuong@ictu.edu.vn | ThS. Phạm Thị Thương | EXACT_EMAIL_MATCH |
| 31 | vvdung@ictu.edu.vn | ThS. Vũ Việt Dũng | EXACT_EMAIL_MATCH |
| 32 | dqlong@ictu.edu.vn | ThS. Đinh Quý Long | EXACT_EMAIL_MATCH |
| 33 | dtchung@ictu.edu.vn | ThS. Đào Trần Chung | EXACT_EMAIL_MATCH |
| 34 | dhkhoi@ictu.edu.vn | ThS. Đỗ Huy Khôi | EXACT_EMAIL_MATCH |

---

## 5. SCOPUS ID COUNTS (ictu_multi_scopus_ids.csv)

| Kiểm tra | Kết quả |
|----------|---------|
| Tổng số dòng dữ liệu (GV) | 34 |
| Tổng ID occurrences (sum id_count) | 83 |
| Unique Scopus IDs | 83 / 83 ✓ |
| ID trùng lặp giữa các GV | 0 ✓ |
| id_count claimed ≠ actual parsed IDs | 0 ✓ |
| IDs chứa ký tự không phải số (scientific notation) | 0 ✓ |

Phân bố id_count:
- 2 GV × 5 IDs = 10 occurrences
- 2 GV × 4 IDs = 8 occurrences
- 5 GV × 3 IDs = 15 occurrences
- 25 GV × 2 IDs = 50 occurrences
- **Tổng = 83 ✓**

---

## 6. ICTU-WEB SOURCE COUNT DISCREPANCY (đã ghi lại)

| Nhóm | ICTU-WEB header tuyên bố | DOM bảng thực tế |
|------|--------------------------|-----------------|
| Multi-ID GV | 35 | 34 data rows |
| Ambiguous IDs | 10 | 10 data rows ✓ |
| Unknown owner IDs | 59 | 59 data rows ✓ |

**Giải thích:** ICTU-WEB header đếm 35 GV nhưng bảng HTML chỉ có 34 hàng dữ liệu (35 tr = 1 header + 34 data). Đây là discrepancy tại nguồn, không phải lỗi trích xuất.

---

## 7. BẰNG CHỨNG TRÌNH DUYỆT / DOM

| Nguồn | Phương pháp | Ngày | Ghi chú |
|-------|------------|------|---------|
| `https://repository.ictu.edu.vn/huong-dan-gop-tai-khoan-scopus/` | `javascript_tool` đọc DOM trực tiếp | 2026-10-27 | 3 bảng HTML; xác nhận total_rows=35 (1 header+34 data) cho bảng 1 |
**[QUAN TRỌNG — Cập nhật Gate D.1 Closeout 2026-10-27]**  
Các số liệu docs/citations bên dưới đánh dấu "phiên trước" là từ lịch sử session, CHƯA được tái xác minh trong phiên này. Scopus Preview trả lỗi "Unable to display author profile" cho cả 3 IDs được kiểm tra lại ngày 2026-10-27 (lỗi phía server Scopus, không phải IDs không tồn tại — page titles vẫn load được). Tất cả số liệu docs/citations từ phiên trước được ghi là **HISTORICAL — NOT RE-VERIFIED**.

| Nguồn | Phương pháp | Ngày | Kết quả phiên này (2026-10-27) | Kết quả phiên trước (HISTORICAL) |
|-------|------------|------|-------------------------------|----------------------------------|
| Scopus 59526508700 (Đỗ Thị Bắc) | Browser | 2026-10-27 | PARTIAL: page title = "Do, Thi Bac"; body = "Unable to display author profile" (Scopus server error) | HISTORICAL: docs/citations không được ghi lại chính xác — NOT RE-VERIFIED |
| Scopus 57819997900 | Browser | 2026-10-27 | PARTIAL: page title = "Do, Bac Thi" (tên đảo ngược); body = "Unable to display author profile" | HISTORICAL: NOT RE-VERIFIED |
| Scopus 57899449200 | Browser | 2026-10-27 | PARTIAL: page title = "ThiBac, Do" (tên ghép lỗi); body = "Unable to display author profile" | HISTORICAL: NOT RE-VERIFIED |
| Scopus 59707347300 (TS. Đinh Xuân Lâm) | Browser | phiên trước | Chưa kiểm tra lại phiên này | HISTORICAL: 2 docs, ICTU affiliation ✓ |
| Scopus 58805827700 (TS. Đinh Xuân Lâm alt) | Browser | phiên trước | Chưa kiểm tra lại phiên này | HISTORICAL: 1 doc, ICTU affiliation ✓ |
| Scopus 26423550300 (TS. Đỗ Đình Cường) | Browser | phiên trước | Chưa kiểm tra lại phiên này | HISTORICAL: 5 docs, ICTU affiliation ✓ |
| Scopus 60561601800 (TS. Đỗ Đình Cường alt) | Browser | phiên trước | Chưa kiểm tra lại phiên này | HISTORICAL: 3 docs, ICTU affiliation ✓ |
| Scopus 57196472280 (TS. Quách Xuân Trưởng primary) | Browser | phiên trước | Chưa kiểm tra lại phiên này | HISTORICAL: 17 docs, ORCID 0000-0003-1402-0830 ✓ |
| Scopus 59253245500 (Nguyen Thi Dung) | Browser | phiên trước | Chưa kiểm tra lại phiên này | HISTORICAL: 2 docs, 58 citations, ICTU affiliation ✓ |
| `"7003299472".length` | `javascript_tool` DOM | 2026-10-27 | = 10 (không phải 7) | — |
| ORCID 0009-0001-3939-8656 (orcid.org) | Browser | 2026-10-27 | CONFIRMED: thuộc Vi Thị Bích Ngọc, Lecturer of Chinese Language, ICTU | — |
| ICTU profile Bùi Thị Quyên | Browser | 2026-10-27 | CONFIRMED: email btquyen@ictu.edu.vn, ORCID 0009-0001-3939-8656 hiển thị trên trang (gán nhầm) | — |
| ICTU profile Vi Thị Bích Ngọc | Browser | 2026-10-27 | CONFIRMED: email ngocvtb@ictu.edu.vn, ORCID 0009-0001-3939-8656 (đúng chủ sở hữu) | — |

**IDs đã mở browser thực tế:** 10 / 83 IDs trong nhóm multi-ID (12%)  
**IDs ambiguous đã mở:** 1 / 10 (10%)  
**IDs unknown đã mở:** 0 / 59 (0%)

---

## 8. MỤC CHƯA XÁC MINH (UNVERIFIED)

| # | Mục | Trạng thái |
|---|-----|-----------|
| U-01 | GV thứ 35 trên ICTU-WEB | SOURCE COUNT DISCREPANCY — nguồn không nhất quán |
| U-02 | Chi tiết từng cặp đối chiếu email→source_id | Cross-reference summary đã xác nhận 34/34; bảng chi tiết ở Section 4 trên |
| U-03 | 73 IDs chưa mở (nhóm multi-ID, ngoài 10 đã kiểm tra) | NOT CHECKED — cần Batch 1+ |
| U-04 | 9/10 IDs ambiguous chưa check browser | NOT CHECKED — cần Batch tiếp theo |
| U-05 | 59 IDs unknown chưa check browser | NOT CHECKED — cần Batch tiếp theo |
| U-06 | `7003299472` — 10 digits thay vì 11 thông thường | Cần mở Scopus profile |
| U-07 | Review event của identity 59253245500 đã ACCEPTED | Cần audit log query (BLOCKED — no DB access) |
| U-08 | Đối chiếu 1207 ScopusAuthors ↔ 83 ICTU-WEB IDs | BLOCKED — no DB access |

---

## 9. NGUỒN DỮ LIỆU & PHƯƠNG PHÁP

| Artifact | Nguồn | Phương pháp trích xuất |
|----------|-------|----------------------|
| `master_lecturers_inventory.csv` | `lecturers.json` (Craw ICTU, 2026-10-03 approx) | Python script đọc JSON array, trích 12 trường, ghi CSV UTF-8 |
| `ictu_multi_scopus_ids.csv` | ICTU-WEB HTML table 1 | `javascript_tool` đọc DOM trực tiếp; IDs lưu dạng pipe-delimited string |
| `ictu_ambiguous_ids.csv` | ICTU-WEB HTML table 2 | `javascript_tool` đọc DOM trực tiếp |
| `ictu_unknown_owner_ids.csv` | ICTU-WEB HTML table 3 | `javascript_tool` đọc DOM trực tiếp |
| `coverage_matrix.csv` | Tổng hợp từ các nguồn trên | Viết thủ công dựa trên kết quả kiểm tra |
| `RECONCILIATION_REPORT.md` | Phân tích các discrepancy | Viết thủ công với bằng chứng DOM |

---

## 10. GIỚI HẠN & CẢNH BÁO

1. **Không có Scopus ID trong lecturers.json:** Roster 410 không chứa Scopus Author ID. Mapping GV ↔ Scopus ID chỉ có từ ICTU-WEB (34 GV multi-ID) và matching engine DB (không truy cập được trong session này).

2. **73 IDs multi-ID chưa kiểm tra browser:** Chỉ 10/83 IDs đã mở Scopus profile thực tế. Coverage = 12%.

3. **Identity 59253245500 — REVIEW DECISION REQUIRES AUDIT:** Đã ACCEPTED trong hệ thống cho PGS.TS. Nguyễn Thị Dung. Chưa đọc review event, không kết luận vi phạm hay không vi phạm D-2.

4. **GV thứ 35:** ICTU-WEB header tuyên bố 35 GV; DOM bảng có 34 data rows. Có thể GV thứ 35 đã bị xóa khỏi bảng nhưng header chưa cập nhật. Không thể xác nhận hay phủ nhận sự tồn tại của GV này.

5. **lecturers.json là dữ liệu cũ:** Snapshot từ crawler, không phải dữ liệu DB live. Một số GV có thể đã thay đổi thông tin.

6. **Không truy cập DB:** Không có cross-reference với 1207 ScopusAuthors hay 149 PENDING candidates trong DB.

---

*Manifest v1 tạo 2026-10-27 (Gate D.1-R Acceptance). Cập nhật v2 2026-10-27 (Gate D.1 Closeout): sửa line count RECONCILIATION_REPORT 141→199, phân tách bằng chứng browser phiên này / phiên trước, ghi nhận Scopus Preview lỗi server ngày kiểm tra, bổ sung bằng chứng ORCID collision từ orcid.org. Mọi số liệu docs/citations Scopus từ phiên trước được ghi là HISTORICAL và chưa được tái xác minh. Ràng buộc áp dụng: read-only, không DB write, không ACCEPT/REJECT/REVOKE.*
