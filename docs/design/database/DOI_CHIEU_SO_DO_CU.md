# Đối chiếu 5 sơ đồ cũ trong `DoAn.docx` với hệ thống thật (quyết định D1)

> **Quyết định D1 (đã chốt):** năm sơ đồ cũ (quy trình, use case, ba ERD) trong `D:\DataFolder\ProjectIctu\DoAn\DoAn.docx` **không còn khớp hệ thống**, vì vậy **không dùng làm sơ đồ chính thức**. **Tài liệu gốc `DoAn.docx` được giữ nguyên, không sửa.** Các sơ đồ chính thức mới được dựng từ mã và schema thật (xem `README.md`). Tài liệu này ghi rõ khác biệt để sinh sinh viên **báo cáo trung thực** với GVHD rằng các sơ đồ cũ là *thiết kế khái niệm ban đầu*, và để nhật ký tuần có thể được cập nhật đúng thực tế.
> Nguồn đối chiếu: ảnh 2–6 nhúng trong `DoAn.docx` (ảnh 1 là logo); schema thật `source/schema_snapshot.json`; `usecase/RBAC_API_MATRIX.csv`; mã dịch vụ. Đây là bản chính xác hóa của Phụ lục A trong `docs/planning/KE_HOACH_V4_…` (có sửa một điểm: CSV Scopus **có đúng 22 cột**, xem A.1).

## A.1. Sơ đồ quy trình (nhật ký tuần 1) → thay bằng `process/BPMN-1_quy_trinh_thuc_te`

| Phần tử trong sơ đồ cũ | Thực tế | Kết luận |
|---|---|---|
| "Operator: Tải file CSV 660 bản ghi, 22 trường" | ADMIN tải CSV ở `/imports`. **Không có vai trò Operator.** 660 bản ghi ✔ (demo). **CSV Scopus thật có đúng 22 cột** (kiểm bằng `raw_payload` của 660 dòng: Authors, Author full names, Author(s) ID, Title, Year, Source title, Volume, Issue, Art. No., Page start, Page end, Cited by, DOI, Link, Abstract, Author Keywords, Document Type, Publication Stage, Open Access, Source, EID, Publisher) | Sai tên tác nhân; "22 trường" **đúng** |
| "Schema & Idempotency OK?" → "Sai / trùng 100%" → "Báo lỗi / Dừng luồng" | Có kiểm tra cột `EID` (tệp không phải bản xuất Scopus bị từ chối) và chống trùng nội dung bằng SHA-256 (409, có thể xác nhận nhập lại); **lỗi từng dòng được giữ và hiển thị, không dừng cả đợt**. Chưa chứng minh bộ kiểm tra bắt buộc đủ 22 cột | Gần đúng, thiếu nhánh lỗi dòng |
| "Parse tác giả, chuẩn hoá tên, **tính Match Score**" | Bóc tách tác giả là bước riêng do ADMIN kích hoạt (UC-12); **không có Match Score**; sinh ứng viên là script CLI (UC-24) | Sai |
| "Admin: Phê duyệt / **Gán tay** / Chờ xác minh" | ACCEPT / REJECT / giữ PENDING; **không có "gán tay"** (không chọn tác giả ngoài danh sách ứng viên) | Sai một phần |
| "Ghi Standardized + Audit Log + hỗ trợ **Rollback**" | Ghi danh tính APPROVED + audit; **không có rollback quyết định duyệt** (chỉ rollback đợt nhập) | Sai một phần |
| "Phát hiện duyệt nhầm" (vòng lặp) | Không có | Không tồn tại |
| "Operator: Xuất báo cáo chuẩn cho ICTU" | ADMIN xuất **JSON** công bố (và JSON hồ sơ giảng viên) | Hẹp hơn |

## A.2. Sơ đồ use case (nhật ký tuần 2) → thay bằng `usecase/diagrams/UCD-*`

| Phần tử | Thực tế | Kết luận |
|---|---|---|
| Actor "Chuyên viên ICTU (Operator)", "Cán bộ duyệt ICTU (Admin/Approver)" | ADMIN, REVIEWER, LECTURER (+ kỹ thuật viên chạy script) | Sai tên, thiếu 2 vai trò |
| UC-01 Nhập tệp Scopus CSV & Idempotency | UC-10 | Đúng |
| «include» Kiểm tra Schema 22 cột | Kiểm tra cột `EID`/định dạng trong UC-10 (không phải UC con riêng) | Gần đúng |
| UC-02 Bóc tách tác giả & Tính Match Score, **«include»** của UC-01 | UC-12: bước **riêng** do ADMIN kích hoạt sau chuẩn hóa công bố (UC-11); **không** Match Score; không phải include | Sai quan hệ |
| UC-03 Đối soát & Phê duyệt liên kết | UC-17 + UC-18 (+UC-19) | Đúng |
| «extend» Gán thủ công giảng viên | Không có | Không tồn tại |
| «extend» Chuyển sang Chờ xác minh | ≈ giữ PENDING (không phải thao tác) | Hiểu nhầm |
| UC-04 Hoàn tác kết quả duyệt (Rollback), «extend» UC-03 | **Không có** | Không tồn tại |
| Quản lý danh mục GV ICTU | UC-05, UC-08, UC-09 | Đúng |
| UC-05 Thống kê & xuất báo cáo (Excel/CSV/JSON) | UC-04 (chỉ chỉ số đếm) + UC-15/UC-09 (**chỉ JSON**) | Quá mức |
| *(thiếu hoàn toàn)* | Đăng nhập, tài khoản/phân quyền, nhật ký kiểm toán, lịch sử review, tra cứu, xem công bố, cổng giảng viên, REVIEWER (≥ 14 UC thật không có trong sơ đồ cũ) | Thiếu |

## A.3. ERD (nhật ký tuần 3 — 3 hình) → thay bằng `database/erd/ERD-*` và `database/class/CLS-*`

| Bảng trong ERD cũ | Bảng thật tương ứng | Khác biệt chính |
|---|---|---|
| `USERS` (`id bigserial`, `username`, `role`) | `users` | Khóa `uuid`; **không có `username`** (đăng nhập bằng `email`); thêm `display_name`, `lecturer_id`, `is_active`, `auth_version`… |
| `UPLOAD_BATCHES` (`operator_id` FK, `total_rows`, `duplicate_rows`, `correlation_id`) | `scopus_imports` | **Không có `operator_id`** (không FK tới `users`; người nhập chỉ truy qua `audit_events`); có `file_sha256`, `status`, `valid/invalid_records`; `correlation_id` thuộc `audit_events` |
| `RAW_SCOPUS_DATA` (`eid` **UK**, title, authors, year, doi, publisher, `duplicate`…) | `raw_scopus_records` | Dữ liệu thô nằm trong `raw_payload` (JSONB, 22 khóa); **`eid_raw` không UNIQUE** ở bảng thô (UNIQUE ở `publications.eid`); không có cột `publisher`/`duplicate` |
| `AUTHOR_EXTRACTED` (`match_score`, `evidence_payload`, `lecturer_id` FK) | `scopus_authors` + `scopus_author_name_variants` + `publication_authors` | Tách 3 bảng; **không có `match_score`**; không FK tới giảng viên |
| `LECTURERS` (`lecturer_code` UK, `scopus_author_id` **UK**) | `lecturers` | `lecturer_code` → `staff_code` (UNIQUE một phần, null được); **không có `scopus_author_id`** (liên kết nằm ở ứng viên/danh tính) |
| `APPROVAL_QUEUE` (`status` HIGH/MED/PENDING, `match_score`, `is_retracted`, `approved_at` "72h rollback") | `lecturer_scopus_candidates` (+ `…_observations`, `…_evidence`, `…_candidate_reviews`) | Trạng thái **PENDING/ACCEPTED/REJECTED/SUPERSEDED**; **không HIGH/MED, không điểm, không mốc 72 giờ** |
| `STANDARDIZED_DATA` (`is_invalidated`, `invalidated_at`…) | `lecturer_scopus_identities` | Trạng thái CANDIDATE/APPROVED/REJECTED/REVOKED; hoàn tác chỉ nằm trong schema (không mã) |
| `AUDIT_LOG` (`action` APPROVE/OVERRIDE/ROLLBACK, `before_json/after_json`) | `audit_events` | Từ vựng hành động khác; có `actor_type`, `request_id`, `correlation_id`, `ip_address`… |
| `EXPORT_AUDIT_LOG` (`file_hash_sha256`, `row_count`) | **Không có bảng** | Việc xuất ghi vào `audit_events` (`PUBLICATION_DATASET_EXPORTED`: `record_count`, `format`, `schema_version`, `filters_applied`) — **không lưu SHA-256 tệp xuất** |

**Tổng hợp:** ERD cũ có **9 bảng** — **2** trùng tên (`users`, `lecturers`) nhưng khác cột; **6** có bảng tương ứng với cấu trúc khác (có cái tách thành nhiều bảng); **1** không tồn tại (`export_audit_log`). DB thật có **24 bảng**: **10** bảng có hình bóng trong ERD cũ, **14** bảng không có (`publications`, `publication_raw_sources`, `organizations`, 2 bảng affiliation, `lecturer_source_snapshots`, `lecturer_known_publications`, `user_notifications`, `candidate_generation_runs`, `…_observations`, `…_evidence`, `…_candidate_reviews`, `identity_evidence`, `mapping_reviews`). Kiểu khóa: `bigserial` (cũ) ≠ `uuid` (thật).

## A.4. Gợi ý xử lý trong hồ sơ đồ án (quyết định của sinh viên)

1. Trong báo cáo, dùng **sơ đồ mới** làm sơ đồ chính; nếu muốn nhắc sơ đồ cũ, ghi rõ *"thiết kế khái niệm ban đầu (tuần 1–3), được thay thế vì không còn khớp hệ thống đã triển khai"* và chỉ ra lý do (bảng này).
2. Cập nhật nhật ký tuần để phản ánh đúng thời điểm và sản phẩm; báo GVHD về việc thay thế sơ đồ.
3. Không đưa vào bất kỳ chương nào các bảng `approval_queue`, `standardized_data`, `export_audit_log`, `upload_batches`, `author_extracted`, `raw_scopus_data` như thể chúng tồn tại.
