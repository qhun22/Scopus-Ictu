# Screen Inventory — Scopus–ICTU · Task 20B

**Ngày lập:** 10/10/2026  
**DB kiểm thử:** scopus_ictu_test_ui20b_20261010 (cụm demo 127.0.0.1:55432)  
**Ảnh chụp tại:** `_quan_ly_do_an/evidence/task20b/screenshots/`  
**Tổng ảnh chụp:** 101 bản ghi (một số ID bị chụp lại lần 2 trên DB ui20b ghi đè lần 1 ui20a)

---

## Nhóm PI 2.3 — 6 nhóm bắt buộc

### PI2.3-1 — Danh sách

| Screen ID | Tên | Route | Role | Viewport | Trạng thái | File ảnh | Figma (Legacy v0) | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| S02 | Danh sách công bố | /publications | ADMIN | 1440×900 | AS-IS | A_publications_1440x900.png | FG-05 (partial) | GAP-02: source_title = "Scopus" tất cả dòng |
| S06 | Danh sách giảng viên | /lecturers | ADMIN | 1440×900 | AS-IS | A_lecturers_1440x900.png | — | Chứa tên/email thật → Figma chỉ dùng dữ liệu minh họa |

### PI2.3-2 — Chi tiết

| Screen ID | Tên | Route | Role | Viewport | Trạng thái | File ảnh | Figma (Legacy v0) | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| S03 | Chi tiết công bố | /publications/:eid | ADMIN | 1440×900 | AS-IS | A_pubdetail_1440x900.png | FG-06 (partial) | Tiêu đề Header hiển thị "Hệ thống" thay vì tên trang (GAP-e) |
| S07 | Chi tiết giảng viên | /lecturers (modal) | ADMIN | 1440×900 | AS-IS | A_lecturers_detail_modal_1440x900.png | — | Modal AntD; tab Thông tin / Tài khoản |

### PI2.3-3 — Nhập dữ liệu

| Screen ID | Tên | Route | Role | Viewport | Trạng thái | File ảnh | Figma (Legacy v0) | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| S04 | Nhập dữ liệu — mặc định | /imports | ADMIN | 1440×900 | AS-IS | A_imports_1440x900.png | FG-03 (partial) | — |
| S04a | Nhập CSV — đã chọn file | /imports | ADMIN | 1440×900 | AS-IS | A_imports_csv_selected_1440x900.png | — | Cột "Thao tác" bị cắt ở 1440 (GAP-a) |
| S04b | Nhập JSON — sai định dạng | /imports | ADMIN | 1440×900 | AS-IS | A_imports_json_wrongtype_1440x900.png | — | — |
| S04c | Nhập JSON — đang đọc | /imports | ADMIN | 1440×900 | AS-IS | A_imports_json_reading_1440x900.png | — | — |
| S04d | Nhập JSON — đã chọn | /imports | ADMIN | 1440×900 | AS-IS | A_imports_json_selected_1440x900.png | — | — |
| S04e | Nhập JSON — kết quả kiểm tra | /imports | ADMIN | 1440×900 | AS-IS | A_imports_json_preview_1440x900.png | — | 410 mới / 352 cập nhật / 58 không đổi |
| S04f | Nhập JSON — lỗi cú pháp | /imports | ADMIN | 1440×900 | AS-IS | A_imports_json_previewerror_1440x900.png | — | — |
| S04g | Chi tiết đợt nhập | /imports (modal) | ADMIN | 1440×900 | AS-IS | A_imports_detail_modal_1440x900.png | — | — |

### PI2.3-4 — So sánh trước/sau chuẩn hóa (PROPOSED)

| Screen ID | Tên | Route | Role | Viewport | Trạng thái | Figma node | Ghi chú |
|---|---|---|---|---|---|---|---|
| S20 | So sánh chuẩn hóa | /publications/:eid/normalization (ĐỀ XUẤT) | ADMIN | 1440×900 | PROPOSED / NOT IMPLEMENTED | FG-04 (Legacy v0) | API đề xuất: GET /api/v1/publications/{eid}/normalization-comparison; chưa có route; bảng 4 cột |

> ⚠️ S20 CHƯA TRIỂN KHAI. Không có ảnh chụp giao diện thật. Frame S20 trong Legacy v0 là minh họa. Xem đặc tả chi tiết tại `docs/design/figma_handoff/FIGMA_HANDOFF_TASK20.md`.

### PI2.3-5 — Hàng đợi phê duyệt

| Screen ID | Tên | Route | Role | Viewport | Trạng thái | File ảnh | Figma (Legacy v0) | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| S09 | Hàng đợi duyệt | /reviews | REVIEWER | 1440×900 | AS-IS | R_reviews_1440x900.png | FG-01 (partial) | — |
| S09a | Hàng đợi — trống (filter REJECTED) | /reviews | REVIEWER | 1440×900 | AS-IS | R_reviews_empty_filter_1440x900.png | — | — |
| S09b | Hàng đợi — đang tải | /reviews | ADMIN | 1440×900 | AS-IS | A_reviews_loading_1440x900.png | — | intercept hold |
| S09c | Hàng đợi — lỗi 503 | /reviews | ADMIN | 1440×900 | AS-IS | A_reviews_error_1440x900.png | — | — |
| S10 | Chi tiết ứng viên | /reviews (modal) | REVIEWER | 1440×900 | AS-IS | R_reviews_detail_1440x900.png | FG-02 (partial) | Modal AntD; phần A–E |
| S10a | Chi tiết — phần E + nút | /reviews (modal) | REVIEWER | 1440×900 | AS-IS | R_reviews_detail_bottom_1440x900.png | — | Scroll bottom |
| S11 | Dialog xác nhận ACCEPT | /reviews (dialog) | REVIEWER | 1440×900 | AS-IS | R_accept_confirm_1440x900.png | FG-07 (partial) | — |
| S11a | ACCEPT — thành công (toast) | /reviews | REVIEWER | 1440×900 | AS-IS | R_accept_done_1440x900.png | — | — |
| S11b | ACCEPT — lỗi 409 conflict | /reviews (dialog) | REVIEWER | 1440×900 | AS-IS | R_conflict_409_1440x900.png | — | Thật: SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER |
| S12 | Dialog REJECT — trống | /reviews (dialog) | REVIEWER | 1440×900 | AS-IS | R_reject_empty_1440x900.png | — | Nút REJECT bị khóa khi chưa nhập lý do |
| S12a | Dialog REJECT — có nội dung | /reviews (dialog) | REVIEWER | 1440×900 | AS-IS | R_reject_filled_1440x900.png | — | Bộ đếm "62 / 4000" bị chồng lên nút (GAP-c) |
| S12b | REJECT — thành công (toast) | /reviews | REVIEWER | 1440×900 | AS-IS | R_reject_done_1440x900.png | — | — |

### PI2.3-6 — Thống kê

| Screen ID | Tên | Route | Role | Viewport | Trạng thái | File ảnh | Figma (Legacy v0) | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| S05 | Dashboard / Tổng quan | /dashboard | ADMIN | 1440×900 | AS-IS | A_dashboard_1440x900.png | FG-08 (partial) | Không làm biểu đồ giả; chỉ số đếm có nguồn |

---

## Nhóm B — Trang ưu tiên (đồng bộ với /imports Task 20A/R2)

| Screen ID | Tên | Route | Role | File ảnh | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|
| S13 | Lịch sử review | /review-history | ADMIN | A_reviewhistory_data_1440x900.png | AS-IS | — |
| S13a | Lịch sử review — trống | /review-history | REVIEWER | R_reviewhistory_empty_1440x900.png | AS-IS | — |
| S13b | Lịch sử review — đang tải | /review-history | ADMIN | A_reviewhistory_loading_1440x900.png | AS-IS | intercept hold |
| S13c | Lịch sử review — lỗi 503 | /review-history | ADMIN | A_reviewhistory_error_1440x900.png | AS-IS | — |
| S14 | Nhật ký hệ thống | /audit-logs | ADMIN | A_auditlogs_1440x900.png | AS-IS | — |
| S14a | Nhật ký — trống | /audit-logs | ADMIN | A_auditlogs_empty_1440x900.png | AS-IS | Lọc hành động không tồn tại |
| S14b | Nhật ký — đang tải | /audit-logs | ADMIN | A_auditlogs_loading_1440x900.png | AS-IS | — |
| S14c | Nhật ký — lỗi 503 | /audit-logs | ADMIN | A_auditlogs_error_1440x900.png | AS-IS | — |
| S15 | Tác vụ (placeholder) | /tasks | ADMIN | A_tasks_1440x900.png | AS-IS / PLACEHOLDER | "Chức năng đang phát triển" |

---

## Nhóm C — Màn hình giảng viên & quản trị

| Screen ID | Tên | Route | Role | File ảnh | Trạng thái |
|---|---|---|---|---|---|
| S16 | Hồ sơ giảng viên | /profile | LECTURER | L_profile_1440x900.png | AS-IS |
| S17 | Liên kết Scopus (danh tính) | /identity | LECTURER | L_identity_1440x900.png | AS-IS |
| S18 | Công bố của tôi | /my-publications | LECTURER | L_mypubs_1440x900.png | AS-IS |

---

## Các màn hình khác

| Screen ID | Tên | Route | File ảnh | Ghi chú |
|---|---|---|---|---|
| S01 | Đăng nhập — mặc định | /login | S01_login_default_1440x900.png | — |
| S01a | Đăng nhập — validation | /login | S01_login_validation_1440x900.png | — |
| S01b | Đăng nhập — sai mật khẩu | /login | S01_login_wrongpw_1440x900.png | 401 thật từ backend |
| S01c | Đăng nhập — đang xử lý | /login | S01_login_loading_1440x900.png | intercept hold |
| S19 | Trang chủ (ADMIN) | /home | A_home_1440x900.png | — |
| S19a | Trang chủ (REVIEWER) | /home | R_home_1440x900.png | — |
| S19b | Trang chủ (LECTURER) | /home | L_home_1440x900.png | — |
| S21 | Chuẩn hóa dữ liệu | /normalization | A_normalization_1440x900.png | — |

---

## Viewport bổ sung

| File ảnh | Màn | Viewport | Ghi chú |
|---|---|---|---|
| S01_login_default_1366x768.png | S01 | 1366×768 | — |
| A_imports_1366x768.png | S04 | 1366×768 | GAP-a rõ hơn |
| A_reviews_1366x768.png | S09 | 1366×768 | — |
| A_imports_1920x1080.png | S04 | 1920×1080 | — |
| A_reviews_1920x1080.png | S09 | 1920×1080 | — |
| A_reviews_mobile_390x844.png | S09 | 390×844 | Responsive kiểm tra |
| A_home_mobile_390x844.png | S19 | 390×844 | — |
| L_mypubs_mobile_390x844.png | S18 | 390×844 | — |

---

## Tóm tắt

- **Tổng màn hình đã kiểm kê:** ~40 (bao gồm các trạng thái loading/error/empty/modal)
- **6 nhóm PI 2.3:** ✅ Đủ (S20 là PROPOSED)
- **4 trang ưu tiên:** ✅ /reviews, /review-history, /audit-logs, /tasks
- **3 vai trò:** ✅ ADMIN / REVIEWER / LECTURER (có ảnh RBAC block)
- **Chụp ảnh thật từ DB kiểm thử:** ✅ 101 bản ghi
- **Frame Figma:** Giới hạn Starter 3 page; 9 frame Legacy v0 đã giữ
