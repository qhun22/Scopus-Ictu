# User Flows — Scopus–ICTU · Task 20B

**Ngày lập:** 10/10/2026  
**Trạng thái prototype Figma:** PARTIAL — rate limit MCP; flow được mô tả bằng bảng; frame trên Page 2 chưa tạo.

---

## Flow 1 — Đăng nhập & phân quyền

```
[Chưa đăng nhập] 
  → GET /login (S01)
    → Nhập email + mật khẩu
      [Validation lỗi] → Hiển thị lỗi inline (S01a)
      [Sai mật khẩu 401] → Toast "Đăng nhập thất bại" (S01b)
      [Tài khoản khóa 403] → Toast "Tài khoản đang bị khóa"
      [Đang xử lý] → Spinner trên nút (S01c)
      [Thành công]
        → ADMIN → /home (S19)
        → REVIEWER → /home (S19a)
        → LECTURER → /home (S19b)

[Phân quyền — RBAC redirect]
  REVIEWER → /dashboard → redirect /home (xác minh: R_blocked_dashboard ✅)
  LECTURER → /reviews → redirect /home (xác minh: L_blocked_reviews ✅)
```

| Bước | Màn | Trạng thái | Ảnh |
|---|---|---|---|
| 1 | S01 | Mặc định | S01_login_default_1440x900.png |
| 2 | S01a | Validation | S01_login_validation_1440x900.png |
| 3 | S01b | Sai mật khẩu | S01_login_wrongpw_1440x900.png |
| 4 | S01c | Đang tải | S01_login_loading_1440x900.png |
| 5 | S19 | ADMIN home | A_home_1440x900.png |

---

## Flow 2 — Nhập dữ liệu (Import)

```
ADMIN → /imports (S04)
  ├── Chọn file CSV Scopus
  │     → Hiển thị tên file + nút Nhập (S04a)
  │     → Cột "Thao tác" có thể bị cắt ở 1440px (GAP-a, TO-BE)
  │
  └── Chọn file JSON giảng viên
        [Sai định dạng] → Toast lỗi (S04b)
        [Đang đọc] → Spinner (S04c)
        [Đã chọn] → Hiển thị tên file (S04d)
        → Bấm "Kiểm tra dữ liệu"
          [Lỗi cú pháp JSON] → Thông báo lỗi parse (S04f)
          [Thành công] → Bảng xem trước (S04e)
                          → 410 mới / 352 cập nhật / 58 không đổi
          → Bấm "Nhập"
            → Toast thành công
            → Bảng lịch sử cập nhật
            → "Chi tiết" → Modal thông tin đợt nhập (S04g)
```

| Bước | Màn | Trạng thái | Ảnh |
|---|---|---|---|
| 1 | S04 | Mặc định | A_imports_1440x900.png |
| 2 | S04a | CSV đã chọn | A_imports_csv_selected_1440x900.png |
| 3 | S04b | JSON sai định dạng | A_imports_json_wrongtype_1440x900.png |
| 4 | S04c | JSON đang đọc | A_imports_json_reading_1440x900.png |
| 5 | S04d | JSON đã chọn | A_imports_json_selected_1440x900.png |
| 6 | S04e | Kết quả kiểm tra | A_imports_json_preview_1440x900.png |
| 7 | S04f | Lỗi cú pháp | A_imports_json_previewerror_1440x900.png |
| 8 | S04g | Modal chi tiết | A_imports_detail_modal_1440x900.png |

---

## Flow 3 — Khám phá công bố

```
ADMIN/REVIEWER → /publications (S02)
  → Tìm kiếm / lọc → kết quả lọc
  → "Chi tiết" → /publications/:eid (S03)
    → Xem thông tin: tiêu đề, tác giả, đơn vị, từ khóa, DOI, nguồn
    → source_title = "Scopus" cho tất cả dòng (GAP-02)
    → DOI hiển thị nguyên văn "DOI:..." (GAP-01)
    → Tác giả → link tác giả Scopus (nếu có)
    → Đơn vị / Affiliation
```

| Bước | Màn | Ảnh |
|---|---|---|
| 1 | S02 — Danh sách | A_publications_1440x900.png |
| 2 | S03 — Chi tiết | A_pubdetail_1440x900.png |
| 3 | S03 — 404 | A_pubdetail_404_1440x900.png |

---

## Flow 4 — Duyệt đối sánh (REVIEWER)

```
REVIEWER → /reviews (S09)
  → Danh sách ứng viên: Giảng viên ICTU / Tác giả Scopus / Trạng thái / Bằng chứng / Ngữ cảnh mơ hồ / Thao tác
  → Cảnh báo "Dùng chung" phải nổi bật (badge rose)
  → Filter: Trạng thái / Tìm tên
  → Hàng trống (filter REJECTED) (S09a)
  → [Đang tải] (S09b) / [Lỗi 503] (S09c)
  
  → Bấm "Chi tiết" ứng viên → Modal AntD (S10)
    → Phần A: thông tin giảng viên ICTU
    → Phần B: thông tin tác giả Scopus
    → Phần C: bằng chứng đối sánh
    → Phần D: ngữ cảnh mơ hồ (nếu có)
    → Phần E: các ứng viên khác dùng chung Scopus ID (S10a)
  
  ├── ACCEPT flow:
  │     → Bấm "Xác nhận đối sánh" → Dialog xác nhận (S11)
  │       → Bấm "Xác nhận ACCEPT" → Đang gửi...
  │         [Thành công] → Toast xanh (S11a) → ứng viên biến khỏi hàng đợi
  │         [409 conflict] → Thông báo lỗi conflict trong dialog (S11b)
  │           → Conflict codes: STALE_CANDIDATE_VERSION, CANDIDATE_ALREADY_DECIDED_CONFLICT,
  │             SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER (đã chụp S11b)
  
  └── REJECT flow:
        → Bấm "Từ chối" → Dialog REJECT (S12)
          → Textarea lý do (tối đa 4000 ký tự)
          → Nút REJECT bị khóa khi chưa nhập lý do (S12)
          → Nhập lý do → Nút được phép (S12a)
          → Bộ đếm "62 / 4000" chồng lên vùng nút (GAP-c, TO-BE)
          → Bấm "Xác nhận REJECT" → Toast đỏ (S12b)
```

| Bước | Màn | Ảnh |
|---|---|---|
| 1 | S09 | R_reviews_1440x900.png |
| 2 | S09a — trống | R_reviews_empty_filter_1440x900.png |
| 3 | S10 — chi tiết | R_reviews_detail_1440x900.png |
| 4 | S10a — bottom | R_reviews_detail_bottom_1440x900.png |
| 5 | S11 — confirm ACCEPT | R_accept_confirm_1440x900.png |
| 6 | S11a — done | R_accept_done_1440x900.png |
| 7 | S11b — 409 | R_conflict_409_1440x900.png |
| 8 | S12 — reject empty | R_reject_empty_1440x900.png |
| 9 | S12a — filled | R_reject_filled_1440x900.png |
| 10 | S12b — done | R_reject_done_1440x900.png |

---

## Flow 5 — LECTURER (Hồ sơ & công bố)

```
LECTURER → /home (S19b)
  → /profile (S16): thông tin cá nhân, chỉnh sửa hồ sơ
  → /identity (S17): liên kết Scopus
    → Danh sách danh tính (PENDING / APPROVED / REJECTED)
    → Seed test: 0 APPROVED (không có ảnh chụp trạng thái APPROVED — P1 optional)
  → /my-publications (S18): công bố đã được liên kết
```

| Bước | Màn | Ảnh |
|---|---|---|
| 1 | S19b — home | L_home_1440x900.png |
| 2 | S16 — profile | L_profile_1440x900.png |
| 3 | S17 — identity | L_identity_1440x900.png |
| 4 | S18 — my-pubs | L_mypubs_1440x900.png |

---

## Flow 6 — So sánh chuẩn hóa (PROPOSED / NOT IMPLEMENTED)

```
[ĐỀ XUẤT - chưa triển khai]
ADMIN → /publications/:eid (S03)
  → Bấm "Xem chuẩn hóa" (nút đề xuất)
  → GET /api/v1/publications/{eid}/normalization-comparison (API chưa có)
  → /publications/:eid/normalization (S20)
    → Bảng 4 cột:
      Trường | Giá trị gốc (raw_payload) | Giá trị chuẩn hóa | Quy tắc áp dụng
    → Badge: Giữ nguyên / Đã chuẩn hóa / Khác biệt / Thiếu
    → Bộ đếm: NEW / EXISTING_UNCHANGED / EXISTING_METADATA_CHANGED / INVALID_EID
    → Ghi chú GAP-01: DOI giữ nguyên văn
    → Ghi chú GAP-02: source_title = "Scopus"
```

> ⚠️ Flow 6 là PROPOSED — không có ảnh chụp giao diện thật. Xem đặc tả S20 tại `docs/design/figma_handoff/FIGMA_HANDOFF_TASK20.md`.

---

## Tóm tắt

| Flow | Hoàn chỉnh? | Ảnh có? | Prototype Figma? |
|---|---|---|---|
| Flow 1 — Login & RBAC | ✅ | ✅ 4 ảnh | PARTIAL (frame chưa tạo) |
| Flow 2 — Import | ✅ | ✅ 8 ảnh | PARTIAL |
| Flow 3 — Công bố | ✅ | ✅ 3 ảnh | PARTIAL |
| Flow 4 — Duyệt | ✅ | ✅ 10 ảnh | PARTIAL |
| Flow 5 — LECTURER | ✅ | ✅ 4 ảnh | PARTIAL |
| Flow 6 — S20 PROPOSED | ⚠️ Mô tả | ❌ Không có | PARTIAL |
