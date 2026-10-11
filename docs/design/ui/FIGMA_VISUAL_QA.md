# Figma Visual QA — Scopus–ICTU · Task 20B

**Ngày:** 10/10/2026  
**File Figma:** JL6qaElA0zehVEVhURJiIC  
**Trạng thái Visual QA:** PARTIAL — rate limit Figma MCP Starter; frame màn hình chưa tạo được; VQA so sánh Figma↔ảnh thật chưa thực hiện được.

---

## Trạng thái tổng quan

| Hạng mục | Trạng thái |
|---|---|
| Ảnh chụp giao diện thật | ✅ 101 bản ghi |
| Variables (121) | ✅ Đã tạo + đã verify get_variable_defs |
| Text styles (19) | ✅ Đã tạo |
| Effect styles (6) | ✅ Đã tạo |
| Section 00 Cover (Page 1) | ⚠️ PARTIAL — script gặp rate limit trước khi commit |
| Section 01 Foundations (Page 1) | ⚠️ PARTIAL |
| Section 02 Components (Page 1) | ❌ Chưa tạo |
| Section 03–06 Screens (Page 2) | ❌ Chưa tạo |
| Prototype reactions | ❌ Chưa tạo |
| VQA so sánh frame↔ảnh thật | ❌ Chưa thực hiện |

---

## Phương pháp VQA đã lên kế hoạch

1. `get_screenshot(nodeId)` từng frame màn hình Figma
2. Đặt cạnh nhau: ảnh chụp thật (1440×900) + frame Figma render (PIL, py3.14)
3. Xuất ra `_quan_ly_do_an/evidence/task20b/vqa/` (ngoài Git)
4. Ghi nhận khác biệt vào bảng dưới

---

## Danh sách ảnh chụp thật (nguồn tham chiếu VQA)

| Screen ID | File ảnh | Viewport | Trạng thái | DB |
|---|---|---|---|---|
| S01 — Login default | S01_login_default_1440x900.png | 1440×900 | AS-IS | ui20b |
| S01a — Login validation | S01_login_validation_1440x900.png | 1440×900 | AS-IS | ui20b |
| S01b — Login sai mật khẩu | S01_login_wrongpw_1440x900.png | 1440×900 | AS-IS (401 thật) | ui20b |
| S01c — Login loading | S01_login_loading_1440x900.png | 1440×900 | AS-IS (intercept) | ui20b |
| S19 — Home ADMIN | A_home_1440x900.png | 1440×900 | AS-IS | ui20b |
| S05 — Dashboard | A_dashboard_1440x900.png | 1440×900 | AS-IS | ui20b |
| S04 — Imports default | A_imports_1440x900.png | 1440×900 | AS-IS | ui20b |
| S04a — CSV selected | A_imports_csv_selected_1440x900.png | 1440×900 | AS-IS | ui20b |
| S04b — JSON wrong type | A_imports_json_wrongtype_1440x900.png | 1440×900 | AS-IS | ui20b |
| S04c — JSON reading | A_imports_json_reading_1440x900.png | 1440×900 | AS-IS | ui20b |
| S04d — JSON selected | A_imports_json_selected_1440x900.png | 1440×900 | AS-IS | ui20b |
| S04e — JSON preview | A_imports_json_preview_1440x900.png | 1440×900 | AS-IS | ui20b |
| S04f — JSON parse error | A_imports_json_previewerror_1440x900.png | 1440×900 | AS-IS | ui20b |
| S04g — Detail modal | A_imports_detail_modal_1440x900.png | 1440×900 | AS-IS | ui20b |
| S06 — Lecturers | A_lecturers_1440x900.png | 1440×900 | AS-IS | ui20b |
| S07 — Lecturer detail modal | A_lecturers_detail_modal_1440x900.png | 1440×900 | AS-IS | ui20b |
| S07a — Lecturer account tab | A_lecturers_detail_account_1440x900.png | 1440×900 | AS-IS | ui20b |
| S07b — Add lecturer modal | A_lecturers_add_modal_1440x900.png | 1440×900 | AS-IS | ui20b |
| S02 — Publications | A_publications_1440x900.png | 1440×900 | AS-IS | ui20b |
| S03 — Pub detail | A_pubdetail_1440x900.png | 1440×900 | AS-IS | ui20b |
| S03err — Pub 404 | A_pubdetail_404_1440x900.png | 1440×900 | AS-IS (404 thật) | ui20b |
| S09 — Reviews REVIEWER | R_reviews_1440x900.png | 1440×900 | AS-IS | ui20b |
| S09 — Reviews ADMIN | A_reviews_1440x900.png | 1440×900 | AS-IS | ui20b |
| S09a — Reviews empty filter | R_reviews_empty_filter_1440x900.png | 1440×900 | AS-IS | ui20b |
| S09b — Reviews loading | A_reviews_loading_1440x900.png | 1440×900 | AS-IS (intercept) | ui20b |
| S09c — Reviews 503 | A_reviews_error_1440x900.png | 1440×900 | AS-IS (intercept) | ui20b |
| S10 — Candidate detail | R_reviews_detail_1440x900.png | 1440×900 | AS-IS | ui20b |
| S10a — Candidate bottom | R_reviews_detail_bottom_1440x900.png | 1440×900 | AS-IS | ui20b |
| S11 — ACCEPT confirm | R_accept_confirm_1440x900.png | 1440×900 | AS-IS | ui20b |
| S11a — ACCEPT done | R_accept_done_1440x900.png | 1440×900 | AS-IS | ui20b |
| S11b — 409 conflict | R_conflict_409_1440x900.png | 1440×900 | AS-IS (409 thật) | ui20b |
| S12 — REJECT empty | R_reject_empty_1440x900.png | 1440×900 | AS-IS | ui20b |
| S12a — REJECT filled | R_reject_filled_1440x900.png | 1440×900 | AS-IS | ui20b |
| S12b — REJECT done | R_reject_done_1440x900.png | 1440×900 | AS-IS | ui20b |
| S13 — Review history ADMIN | A_reviewhistory_data_1440x900.png | 1440×900 | AS-IS | ui20b |
| S13 — Review history REVIEWER | R_reviewhistory_data_1440x900.png | 1440×900 | AS-IS | ui20b |
| S13a — RH empty | R_reviewhistory_empty_1440x900.png | 1440×900 | AS-IS | ui20b |
| S13b — RH loading | A_reviewhistory_loading_1440x900.png | 1440×900 | AS-IS (intercept) | ui20b |
| S13c — RH 503 | A_reviewhistory_error_1440x900.png | 1440×900 | AS-IS (intercept) | ui20b |
| S14 — Audit logs | A_auditlogs_1440x900.png | 1440×900 | AS-IS | ui20b |
| S14a — AL empty | A_auditlogs_empty_1440x900.png | 1440×900 | AS-IS | ui20b |
| S14b — AL loading | A_auditlogs_loading_1440x900.png | 1440×900 | AS-IS (intercept) | ui20b |
| S14c — AL 503 | A_auditlogs_error_1440x900.png | 1440×900 | AS-IS (intercept) | ui20b |
| S15 — Tasks placeholder | A_tasks_1440x900.png | 1440×900 | AS-IS | ui20b |
| S19a — Home REVIEWER | R_home_1440x900.png | 1440×900 | AS-IS | ui20b |
| S19b — Home LECTURER | L_home_1440x900.png | 1440×900 | AS-IS | ui20b |
| S16 — Profile | L_profile_1440x900.png | 1440×900 | AS-IS | ui20b |
| S17 — Identity | L_identity_1440x900.png | 1440×900 | AS-IS | ui20b |
| S18 — My-pubs | L_mypubs_1440x900.png | 1440×900 | AS-IS | ui20b |
| S19 RBAC — REVIEWER blocked | R_blocked_dashboard_1440x900.png | 1440×900 | AS-IS | ui20b |
| S19 RBAC — LECTURER blocked | L_blocked_reviews_1440x900.png | 1440×900 | AS-IS | ui20b |
| S99 — Header user menu | A_header_menu_1440x900.png | 1440×900 | AS-IS | ui20b |

---

## Các vấn đề đã phát hiện (không cần VQA frame–ảnh)

| Mã | Mức | Màn | Mô tả |
|---|---|---|---|
| GAP-a | HIGH | S04 /imports | Cột "Thao tác" bị cắt tại 1440px; bảng tràn ngang |
| GAP-b | MEDIUM | S10/S11/S12 | Modal ACCEPT/REJECT dùng AntD: màu primary #1677FF ≠ #3A5FC3; font không phải Saira |
| GAP-c | MEDIUM | S12a | Bộ đếm "62/4000" của textarea chồng lên vùng nút footer trong dialog REJECT |
| GAP-d | LOW | S02 /publications | Nút "Chi tiết" xuống dòng thứ 2 tại 1440 |
| GAP-e | LOW | S03 /publications/:eid | Header hiển thị "Hệ thống" thay vì tiêu đề trang |
| GAP-f | LOW | nhiều trang | shadow-xs/2xs/backdrop-blur-xs không hoạt động TW 3.4 → card phẳng |
| GAP-g | LOW | nhiều trang | font-black 900 không tải → synth |
| GAP-h | LOW | S16/S17/S18 | LECTURER pages: container khác (thêm padding, nhãn KPI viết hoa, rounded-2xl) |
| GAP-i | LOW | S14 /audit-logs | Nút filter xuống dòng 2; placeholder bị cắt "VD: PUBLICATION_DAT" |
| GAP-j | LOW | S13 /review-history | Hiển thị mã ACCEPT/REJECT; PENDING→ACCEPTED thay vì nhãn tiếng Việt |
| GAP-k | LOW | S05 /dashboard | "Trạng thái định danh": Ứng viên 0, Chờ duyệt 40 — cần kiểm tra logic |
| GAP-l | LOW | S19 /home | Thẻ "Đối sánh cần xử lý — Chưa có dữ liệu"; lối tắt "Tác vụ/Người dùng" |
| GAP-m | INFO | S06/S07 | Bảng giảng viên chứa tên/email thật ICTU → Figma chỉ dùng dữ liệu minh họa |
| GAP-n | INFO | Legacy v0 | 9 frame legacy không khớp UI thật: thiếu cột, sidebar khác, tên người thật |

---

## Kế hoạch VQA sau khi có frame Figma

```bash
# Script PIL so sánh (chạy sau khi tạo frame trên Figma)
python _quan_ly_do_an/tools/task20b/vqa_compare.py \
  --figma-node <nodeId> \
  --real-screenshot _quan_ly_do_an/evidence/task20b/screenshots/A_reviews_1440x900.png \
  --out _quan_ly_do_an/evidence/task20b/vqa/S09_compare.png
```

> Tệp `vqa_compare.py` chưa tạo — P2 task sau khi rate limit hết hạn.
