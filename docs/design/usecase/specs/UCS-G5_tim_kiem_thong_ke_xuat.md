# Đặc tả Use Case — Nhóm 5: Tìm kiếm, thống kê và xuất dữ liệu

> Khớp "UC chính (e) Tìm kiếm, thống kê và xuất dữ liệu" của đề cương. Sơ đồ: `diagrams/UCD-5_tim_kiem_thong_ke_xuat`. **Lưu ý trung thực:** thống kê hiện chỉ là bộ chỉ số đếm; xuất dữ liệu **chỉ JSON** (không CSV/Excel) — xem GAP-08, GAP-09. Đối chiếu mã: `search.py`, `search_queries.py`, `dashboard.py`, `dashboard_queries.py`, `publications.py` (export), `publication_export.py`, `lecturers.py` (export), `lecturer_dataset/exporter.py`.

---

## UC-14 — Tra cứu tổng hợp

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-14 |
| **Mục tiêu** | Tìm nhanh trong ba nhóm dữ liệu — giảng viên, công bố, tác giả Scopus — bằng một ô tìm kiếm; tên tiếng Việt không phân biệt dấu/hoa thường |
| **Actor chính / phụ** | Chính: **ADMIN, REVIEWER**. Không dành cho LECTURER |
| **Điều kiện trước** | Đăng nhập ADMIN hoặc REVIEWER |
| **Luồng chính** | 1. Người dùng vào **Tra cứu** (`/search`) và nhập từ khóa.<br>2. Hệ thống (`GET /search?q=&limit=`) cắt khoảng trắng, kiểm độ dài (≥ 2 ký tự), tìm theo chuỗi con (ký tự đặc biệt của LIKE được khớp nguyên văn) và gấp dấu tiếng Việt (`text_folding`), trả kết quả theo nhóm (mặc định 5, tối đa 20 mỗi nhóm).<br>3. Người dùng mở một kết quả để sang màn chi tiết tương ứng |
| **Luồng thay thế** | A1. Không có kết quả → thông báo rỗng.<br>A2. "Luong", "luong", "Lương" cho cùng kết quả (không phân biệt dấu) |
| **Luồng lỗi** | E1. Từ khóa quá ngắn → 422 `SEARCH_QUERY_TOO_SHORT`; quá dài → 422 `SEARCH_QUERY_TOO_LONG`.<br>E2. LECTURER → 403; chưa đăng nhập → 401.<br>E3. Lỗi DB → 503 |
| **Điều kiện sau** | Chỉ đọc |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | ADMIN, REVIEWER |
| **API / UI thực tế** | `GET /api/v1/search`; UI `/search` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Tìm không dấu chỉ áp dụng cho tra cứu/danh sách; **không** ảnh hưởng luật đối sánh |
| **Test case tương ứng** | `test_search_api` (19 ca); `unit/test_search_routes_contract`; `unit/test_text_folding` |

---

## UC-04 — Xem thống kê tổng quan (dashboard)

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-04 |
| **Mục tiêu** | Cho quản trị nắm nhanh tình trạng dữ liệu và công việc tồn đọng |
| **Actor chính / phụ** | Chính: **ADMIN** |
| **Điều kiện trước** | Đăng nhập ADMIN |
| **Luồng chính** | 1. ADMIN vào **Tổng quan** (`/dashboard`).<br>2. Hệ thống (`GET /dashboard/summary`) trả: tổng công bố; tổng/đang hoạt động giảng viên; tổng tác giả Scopus; số danh tính theo trạng thái (CANDIDATE/APPROVED/REJECTED/REVOKED); số ứng viên chờ duyệt; đợt nhập Scopus gần nhất (tệp, trạng thái, số bản ghi); các hành động audit gần đây |
| **Luồng thay thế** | A1. Chưa có dữ liệu → các chỉ số bằng 0, đợt nhập gần nhất rỗng |
| **Luồng lỗi** | E1. Không phải ADMIN → 403; chưa đăng nhập → 401.<br>E2. Lỗi DB → 503 |
| **Điều kiện sau** | Chỉ đọc |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | `GET /api/v1/dashboard/summary`; UI `/dashboard` (và Trang chủ `/home` có khung biểu đồ giữ chỗ) |
| **Trạng thái triển khai** | **MỘT PHẦN**: chỉ các chỉ số đếm; **không có** thống kê theo năm/loại tài liệu/khoa/nguồn; biểu đồ Trang chủ là giữ chỗ ("Đang phát triển") — GAP-08 |
| **Test case tương ứng** | `test_dashboard_api` (34 ca). E2E: ảnh 02 (Task 16; đối soát API/DB: 660 công bố/411 hồ sơ/1.207 tác giả/40 chờ duyệt) |

---

## UC-15 — Xuất dữ liệu công bố ra JSON

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-15 |
| **Mục tiêu** | Xuất tập công bố chuẩn hóa (theo bộ lọc) ra tệp JSON có cấu trúc để hệ thống khác dùng lại |
| **Actor chính / phụ** | Chính: **ADMIN** |
| **Điều kiện trước** | Đăng nhập ADMIN; có công bố |
| **Luồng chính** | 1. ADMIN vào **Công bố** (`/publications`), đặt bộ lọc (từ khóa, năm, loại, giai đoạn, truy cập mở) và bấm **Xuất JSON**.<br>2. Hệ thống (`GET /publications/export`) truy vấn theo cùng bộ lọc của danh sách (không phân trang) bằng các truy vấn theo lô.<br>3. Hệ thống **ghi audit `PUBLICATION_DATASET_EXPORTED` và commit trước**, rồi trả tệp UTF-8: `dataset` (tên, `schema_version` `1.0`, `export_id`, `exported_at`, `record_count`, `filters_applied`, `source`) + `publications` (kèm tác giả và liên kết giảng viên đã duyệt) |
| **Luồng thay thế** | A1. Không bộ lọc → xuất toàn bộ |
| **Luồng lỗi** | E1. Ghi audit thất bại → **503, không giao tệp**.<br>E2. Lỗi DB → 503.<br>E3. REVIEWER/LECTURER → 403 (chỉ ADMIN) |
| **Điều kiện sau** | Có tệp JSON và một sự kiện audit (số bản ghi, định dạng, bộ lọc) |
| **Dữ liệu thay đổi** | `audit_events` (một dòng) |
| **Quyền truy cập** | **ADMIN** (REVIEWER xem được công bố nhưng không xuất) |
| **API / UI thực tế** | `GET /api/v1/publications/export`; UI `/publications` (nút Xuất JSON) |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API), chỉ JSON**. **Không có CSV/Excel** (sơ đồ UC cũ trong `DoAn.docx` nêu Excel/CSV/JSON — chỉ JSON là thật); trường nguồn xuất bản đang là `Scopus` (GAP-02) |
| **Test case tương ứng** | `test_publication_export_api` (44 ca). Lưu ý vận hành: **không bấm Xuất JSON trên teacher DB** vì sinh audit (quy ước demo) |

---

## UC-09 — Xuất hồ sơ giảng viên ra JSON

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-09 |
| **Mục tiêu** | Xuất bộ hồ sơ giảng viên ICTU ra JSON theo đúng schema nhập (round-trip) |
| **Actor chính / phụ** | Chính: **ADMIN** |
| **Điều kiện trước** | Đăng nhập ADMIN |
| **Luồng chính** | 1. ADMIN vào **Giảng viên** (`/lecturers`) và bấm **Xuất JSON**.<br>2. Hệ thống (`GET /lecturers/export`) dựng bộ dữ liệu từ các định danh nguồn đã xác thực, ghi audit `LECTURER_DATASET_EXPORTED` và trả tệp JSON nhập lại được (UC-08) |
| **Luồng thay thế** | — |
| **Luồng lỗi** | E1. Không phải ADMIN → 403.<br>E2. Lỗi DB → 503 |
| **Điều kiện sau** | Có tệp JSON và audit |
| **Dữ liệu thay đổi** | `audit_events` |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | `GET /api/v1/lecturers/export`; UI `/lecturers` (nút Xuất JSON); dịch vụ `lecturer_dataset/exporter.py` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API), chỉ JSON**. Giới hạn: không khôi phục `tel` và Google Scholar (không có cột DB) |
| **Test case tương ứng** | `test_lecturer_json_roundtrip`. E2E: §6.3 (nút kích hoạt export + audit; nội dung tệp kiểm bằng API) |
