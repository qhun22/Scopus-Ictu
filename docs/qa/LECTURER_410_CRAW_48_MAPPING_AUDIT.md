# KIỂM TOÁN: 410 GIẢNG VIÊN ↔ CRAW 48 ↔ SCOPUS — NGUYÊN NHÂN VÀ HƯỚNG DẪN

**Ngày:** 14/10/2026  
**Git HEAD:** 58e1104 — Khóa code trước demo  
**Branch:** main  

---

## 1. MÔI TRƯỜNG KIỂM TRA

| Hạng mục | Giá trị |
|---|---|
| Git HEAD | `58e1104` |
| Working tree | Không có thay đổi code trong phiên này |
| Backend demo (đang chạy) | `127.0.0.1:8001` → DB `scopus_ictu_app` @ 55432 |
| Frontend demo (đang chạy) | `127.0.0.1:5173` |
| Backend test (không chạy) | `127.0.0.1:8199` → DB `scopus_ictu_test_withjson_r2_20261011` @ 55432 |
| Craw source dir | `D:\DataFolder\ProjectIctu\DoAn\Craw\output\full` |
| Alembic head trên DB app | `c7f2a9b1d3e5` (đúng) |
| Python venv | `D:\DataFolder\ProjectIctu\DoAn\_venv_backend_demo_py312\Scripts\python.exe` |

---

## 2. NGUỒN DỮ LIỆU THỰC TẾ

### A. Bộ JSON 410 giảng viên

- **File:** `D:\DataFolder\ProjectIctu\DoAn\Craw\output\full\lecturers.json`
- **Tổng số hồ sơ:** 410
- **Trường `source_id`:** URL hồ sơ ICTU, ví dụ `https://repository.ictu.edu.vn/giang-vien/bui-anh-tu/`
- **Bảng lưu trong DB:** `lecturers` (trường `repository_profile_url`)
- **Import thế nào:** ADMIN → Nhập dữ liệu → Nhập giảng viên (file JSON hoặc qua UI)
- **Import lại có tạo trùng không:** Không — service dùng upsert theo `source_id`
- **Trạng thái trên DB demo (`scopus_ictu_app`):** **0 giảng viên** — chưa import JSON

### B. Bộ Craw ICTU (lecturer_publication_links)

- **File chính:** `D:\DataFolder\ProjectIctu\DoAn\Craw\output\full\lecturer_publication_links.json`
- **Tổng links:** 328
- **Giảng viên duy nhất có link:** **48** (trong số 410 người có trong `lecturers.json`)
- **Tổng giảng viên trong Craw:** 410 (từ `lecturers.json`)
- **Giải thích:** 48 là số giảng viên có công bố được thu thập từ trang ICTU; 362 người còn lại có hồ sơ nhưng không có công bố Craw
- **Bản chụp mới (`target_source_id`):** 155 công bố Craw duy nhất (328 links đến 155 công bố)

### C. Bộ Scopus CSV 660 công bố

- **Bảng:** `publications` (660 rows), `publication_authors` (2751 rows), `scopus_authors` (1207 rows)
- **Affiliation đã xử lý:** `publication_author_affiliations` (1709 rows)
- **Trạng thái trên DB demo:** đã nhập và chuẩn hóa đầy đủ

---

## 3. TẠI SAO 410 KHÁC 48?

```
410 giảng viên trong lecturers.json (toàn bộ hồ sơ ICTU)
         ↓
362 người KHÔNG có công bố nào thu thập từ ICTU repository
         ↓
 48 người CÓ ít nhất 1 công bố được Craw thu thập từ trang cá nhân ICTU
         ↓
328 links (1 giảng viên có thể có nhiều công bố)
```

**Đây KHÔNG phải là lỗi.** Craw chỉ thu thập công bố từ trang hồ sơ của giảng viên trên `repository.ictu.edu.vn`. Chỉ 48 giảng viên có liệt kê công bố trên trang đó.

---

## 4. CÁC PHÉP ĐẾM CỤ THỂ

| Chỉ số | Giá trị | Ý nghĩa |
|---|---|---|
| Hồ sơ giảng viên ICTU | **410** | Số hàng trong `lecturers.json` = số hàng trong bảng `lecturers` sau khi import JSON |
| Giảng viên có dữ liệu Craw | **48** | Số giảng viên xuất hiện trong `lecturer_publication_links.json` (có ít nhất 1 pub) |
| Links Craw | **328** | Tổng số cặp (giảng viên, công bố) trong Craw |
| Công bố Craw duy nhất | **155** | DISTINCT `target_source_id` trong links |
| Công bố Scopus CSV | **660** | Bảng `publications` sau khi import CSV |
| Tác giả Scopus đã bóc tách | **1207** | Bảng `scopus_authors` |
| Vị trí tác giả | **2751** | Bảng `publication_authors` |
| Affiliation đã xử lý | **1709** | Bảng `publication_author_affiliations` |
| Known publications (sau khi nạp Craw trên DB test) | **327** | Bảng `lecturer_known_publications` |
| Snapshots (sau nạp Craw trên DB test) | **48** | Bảng `lecturer_source_snapshots` |
| Candidates PENDING (DB test) | **149** | Bảng `lecturer_scopus_candidates` |

---

## 5. NGUYÊN NHÂN 48/48 UNMAPPED — ĐÃ TÁI HIỆN

**Nguyên nhân:** Frontend `127.0.0.1:5173` và backend `127.0.0.1:8001` đang kết nối DB `scopus_ictu_app`, trong khi bảng `lecturers` của DB này **rỗng hoàn toàn (0 hàng)**.

**Cơ chế mapping trong code:**
```python
# KnownPublicationIngestionService._build_lecturer_index()
rows = db.execute(
    select(Lecturer.id, Lecturer.repository_profile_url).where(
        Lecturer.repository_profile_url.is_not(None)
    )
).all()
by_url = {url: lid for lid, url in rows}
```

Với `lecturers` rỗng → `by_url = {}` → mọi Craw source_id đều không match → 48 `UNMAPPED_LECTURER` → 48 `invalid_records`.

**Xác minh bằng code:**
```
DB scopus_ictu_app:  lecturers=0  → preview: 48 unmapped, 48 invalid ← KHỚP với UI
DB test_withjson_r2: lecturers=410 → preview: 48 mapped, 0 unmapped   ← KHỚP với DB đầy đủ
```

**48 Craw source_ids HOÀN TOÀN KHỚP với 48 URLs trong DB test** — không có lỗi format, không có lỗi schema.

---

## 6. LÝ DO ĐÃ THẤY 39 ỨNNG VIÊN TRƯỚC ĐÂY

Người dùng đề cập thấy 39 ứng viên ở trang Duyệt đối sánh "dù chưa nhập JSON". Có hai giải thích khả dĩ:

1. **Kết nối tới DB test** — phiên đó đang kết nối `scopus_ictu_test_e2e_t15/t16/t17_20261009` (mỗi DB có 40 candidates) hoặc `scopus_ictu_test_withjson_r2_20261011` (149 candidates). Giao diện 5173/8001 thời điểm đó có thể đang trỏ sang DB test.

2. **Phiên nghiệm thu cũ** — phiên nghiệm thu dùng DB test đầy đủ (8199/5199) hiển thị 146 candidates. Có thể nhớ nhầm số từ phiên đó.

**DB `scopus_ictu_app` hiện tại: 0 candidates, 0 lecturers.** Không có candidates nào từ DB này.

---

## 7. KẾT QUẢ TRƯỚC/SAU NHẬP JSON (ĐÃ KIỂM THỬ TRÊN DB TEST)

Đây là so sánh từ DB test đầy đủ (`scopus_ictu_test_withjson_r2_20261011`) so với `scopus_ictu_app`:

| Chỉ số | Trước nhập JSON (scopus_ictu_app) | Sau nhập JSON (DB test) |
|---|---|---|
| Lecturers | 0 | 410 |
| Craw preview: mapped | 0 | 48 |
| Craw preview: unmapped | 48 | 0 |
| Craw preview: invalid | 48 | 0 |
| Sau nạp Craw: snapshots | 0 | 48 |
| Sau nạp Craw: known_pubs | 0 | 327 |
| Candidates (sau sinh) | 0 | 149 |

---

## 8. KẾT QUẢ API/UI THỰC TẾ

Đã gọi `compute_preview()` qua code Python trực tiếp (tương đương API `POST /api/v1/matching/craw/preview`):

**Trên `scopus_ictu_app` (DB demo, 0 lecturers):**
```json
{
  "can_apply": false,
  "blocked_reason": "48 lecturers are unmapped",
  "blocking": ["48 lecturers are unmapped", "48 invalid records"],
  "preview": {
    "source_lecturer_count": 48,
    "mapped_lecturer_count": 0,
    "unmapped_lecturer_count": 48,
    "invalid_records": 48,
    "error_codes": {"UNMAPPED_LECTURER": 48}
  }
}
```

**Trên `scopus_ictu_test_withjson_r2_20261011` (DB test đầy đủ, 410 lecturers):**
```json
{
  "can_apply": true,
  "blocked_reason": null,
  "blocking": [],
  "preview": {
    "source_lecturer_count": 48,
    "mapped_lecturer_count": 48,
    "unmapped_lecturer_count": 0,
    "snapshots_already_present": 48,
    "known_publications_already_present": 327,
    "invalid_records": 0,
    "error_codes": {}
  }
}
```

---

## 9. TEST PASS/FAIL/BLOCKED

| Kiểm tra | Kết quả | Ghi chú |
|---|---|---|
| Xác minh Craw dir và file tồn tại | PASS | 410 lecturers, 1907 pubs, 328 links trong Craw |
| 48 Craw source_ids khớp DB URLs (test DB) | PASS | 48/48, không có sai format |
| Preview trên DB rỗng → 48 unmapped | PASS (tái hiện đúng) | lecturers=0 → mọi URL đều unmapped |
| Preview trên DB đầy đủ → 48 mapped | PASS | lecturers=410 → 48/48 mapped |
| Không sửa code, không import vào DB demo | PASS (đúng chính sách) | |
| BROWSER E2E trực tiếp UI 5173 | BLOCKED (theo chính sách an toàn demo) | Không restart/thao tác server demo |

---

## 10. CÁC SỬA ĐỔI CODE

**Không có.** Hệ thống hoạt động đúng. Vấn đề là dữ liệu (DB demo chưa có lecturers), không phải bug.

---

## 11. HƯỚNG DẪN THAO TÁC ĐÚNG

### Nếu muốn dùng DB demo (`scopus_ictu_app`) với đầy đủ tính năng:

**Bước 1 — Nhập JSON 410 giảng viên:**
- Vào ADMIN → **Nhập dữ liệu** → tab **Giảng viên**
- Chọn file `lecturers.json` từ `D:\DataFolder\ProjectIctu\DoAn\Craw\output\full\`
- Đợi import hoàn thành → kiểm tra số lượng = 410

**Bước 2 — Xem trước Craw:**
- Vào ADMIN → **Chuẩn hóa dữ liệu** → tab **Đối sánh**
- Nhấn **Xem trước** — lúc này sẽ hiển thị: 48 mapped, 0 unmapped, 327 công bố đã biết

**Bước 3 — Xác nhận áp dụng Craw:**
- Đọc kết quả xem trước
- Tích checkbox xác nhận
- Nhấn **Xác nhận áp dụng**

**Bước 4 — Sinh ứng viên:**
- Nhấn **Chạy sinh ứng viên** (cùng tab)
- Đợi kết quả: ứng viên từ tên + ứng viên từ Craw

**Bước 5 — REVIEWER duyệt:**
- REVIEWER → **Duyệt đối sánh** → xem từng ứng viên → Xác nhận / Từ chối

### Nếu vẫn thấy 0/48 sau khi nhập JSON:

1. Kiểm tra backend đang kết nối DB nào: xem `backend/.env` → `DB_NAME`
2. Kiểm tra có đúng số lecturers chưa: ADMIN → Dashboard → số giảng viên
3. Nếu Dashboard hiện 0 giảng viên → bước nhập JSON chưa thành công

---

## 12. KẾT LUẬN

| Câu hỏi | Câu trả lời |
|---|---|
| Tại sao 48, không phải 410? | Chỉ 48/410 giảng viên có công bố được Craw thu thập từ trang ICTU |
| Tại sao 48/48 unmapped? | DB demo `scopus_ictu_app` chưa có giảng viên (0 rows) — JSON chưa import |
| Có bug code không? | Không. Code mapping đúng. Vấn đề thuần túy là thiếu dữ liệu |
| 39 candidates từ đâu? | Từ DB test cũ (e2e t15-t17 có 40 candidates), không phải DB demo hiện tại |
| Cần làm gì? | Import JSON 410 giảng viên vào DB demo → Nạp Craw → Sinh ứng viên |
