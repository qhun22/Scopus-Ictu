# Đặc tả Use Case — Nhóm 3: Quản lý công bố

> Khớp "UC chính (c) Quản lý công bố" của đề cương. Sơ đồ: `diagrams/UCD-3_quan_ly_cong_bo`. Công bố là **dữ liệu chuẩn hóa chỉ đọc**: không có chức năng sửa tay công bố (thiết kế bất biến — chuẩn hóa chạy lại không ghi đè metadata đã có). Việc tạo công bố thuộc UC-11 (nhóm 4). Đối chiếu mã: `publications.py`, `publication_queries.py`, `lecturer_scopus.py`, `lecturer_scopus_projection.py`.

---

## UC-13 — Xem danh sách và chi tiết công bố

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-13 |
| **Mục tiêu** | Duyệt kho công bố chuẩn hóa; xem chi tiết một công bố gồm metadata, tác giả theo thứ tự, giảng viên đã được duyệt, nguồn gốc dòng CSV và **đơn vị công tác theo từng tác giả** |
| **Actor chính / phụ** | Chính: **ADMIN, REVIEWER**. Không dành cho LECTURER (403) |
| **Điều kiện trước** | Đăng nhập ADMIN hoặc REVIEWER; đã có công bố (UC-11) |
| **Luồng chính** | 1. Người dùng vào **Công bố** (`/publications`): danh sách phân trang (mặc định 20/trang) có bộ lọc từ khóa, năm, loại tài liệu, giai đoạn xuất bản, truy cập mở.<br>2. Chọn một công bố → `/publications/:eid` (`GET /publications/{eid}`).<br>3. Màn chi tiết hiển thị: metadata (EID, DOI, tiêu đề, năm, nguồn, trích dẫn…); **bảng tác giả** theo thứ tự kèm trạng thái đơn vị (VERIFIED / CORROBORATED / UNRESOLVED) và nguồn ngoài; giảng viên đã được duyệt liên kết; **nguồn gốc** (tên tệp, số dòng, SHA-256, thời điểm nhập) |
| **Luồng thay thế** | A1. Danh sách rỗng khi bộ lọc không khớp.<br>A2. Một bài có nhiều nguồn gốc (nhiều lần nhập): hiển thị 3 dòng đầu, "Xem thêm" |
| **Luồng lỗi** | E1. EID không tồn tại → 404.<br>E2. Tham số lọc sai → 422.<br>E3. LECTURER → 403; chưa đăng nhập → 401.<br>E4. Lỗi DB → 503 |
| **Điều kiện sau** | Chỉ đọc; không dữ liệu nào đổi |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | ADMIN, REVIEWER (`require_role("ADMIN","REVIEWER")`) |
| **API / UI thực tế** | `GET /api/v1/publications`, `GET /api/v1/publications/{eid}`; UI `/publications`, `/publications/:eid`; dịch vụ `publication_queries.py`, `author_affiliation` (hiển thị đơn vị) |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. **Lưu ý dữ liệu:** trường "Nguồn tạp chí" hiện hiển thị `Scopus` cho mọi công bố (lỗi ánh xạ — GAP-02); đơn vị theo tác giả đến từ OpenAlex/Crossref, không phải từ Scopus và không phải đơn vị hiện tại của giảng viên |
| **Test case tương ứng** | `test_publication_api` (32 ca); `test_affiliation_import_and_api`; `test_dashboard_api` (số liệu liên quan). E2E: §6.6 báo cáo Task 16 (ảnh 10–12; ví dụ EID `…105006527625` 5 tác giả/8 liên kết đơn vị) |

---

## UC-22 — Xem công bố của tôi (giảng viên)

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-22 |
| **Mục tiêu** | Giảng viên xem các công bố gắn với các tác giả Scopus **đã được duyệt APPROVED** của mình |
| **Actor chính / phụ** | Chính: **LECTURER** |
| **Điều kiện trước** | Đăng nhập LECTURER có hồ sơ; để có dữ liệu cần ít nhất một danh tính APPROVED (UC-18) |
| **Luồng chính** | 1. Giảng viên vào **Công bố của tôi** (`/my-publications`).<br>2. Hệ thống (`GET /lecturers/me/publications`) lấy các danh tính APPROVED của giảng viên → các vị trí tác giả (`publication_authors`) → công bố, phân trang và tính số liệu tổng hợp trên toàn bộ kết quả |
| **Luồng thay thế** | A1. Chưa có danh tính APPROVED → danh sách rỗng (trạng thái trống, không lỗi).<br>A2. Phân trang/sắp xếp theo tham số hợp lệ |
| **Luồng lỗi** | E1. Tham số phân trang không hợp lệ → 422.<br>E2. ADMIN/REVIEWER gọi → 403; chưa đăng nhập → 401.<br>E3. Tài khoản chưa gắn hồ sơ → lỗi rõ ràng |
| **Điều kiện sau** | Chỉ đọc; **không rò dữ liệu giữa giảng viên** |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | LECTURER (chỉ dữ liệu của mình) |
| **API / UI thực tế** | `GET /api/v1/lecturers/me/publications`; UI `/my-publications`; dịch vụ `lecturer_scopus_projection.py` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Teacher DB: 0 danh tính APPROVED nên trống; minh chứng có dữ liệu chỉ từ DB kiểm thử sau một ACCEPT (ảnh 23 Task 16) |
| **Test case tương ứng** | `test_lecturer_scopus_api::test_a2_t05_lecturer_own_publications`, `test_a2_t07_empty_publication_state`, `test_a2_t16_to_t18_pagination_validation`, `test_a2_t19_publication_aggregates_cover_full_result_set`, `test_a2_t21_no_cross_lecturer_leak`; `test_lecturer_scopus_projection` |
