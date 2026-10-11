# Đặc tả Use Case — Nhóm 1: Nhập dữ liệu

> Nhóm này khớp "UC chính (a) Nhập dữ liệu" của đề cương (PI-1.3). Sơ đồ: `diagrams/UCD-1_nhap_du_lieu`. Mọi nội dung đã đối chiếu với mã (`imports.py`, `lecturers.py`, `lecturer_dataset/*`, `scopus_import_service.py`) và test pytest (tên hàm thật). Trạng thái dùng: **ĐÃ TRIỂN KHAI · MỘT PHẦN · CHỈ API · CHỈ CLI**.
> Quy ước tên bảng/API xem `database/DATA_DICTIONARY.md`, `usecase/RBAC_API_MATRIX.csv`. "E2E" = kiểm thử trình duyệt Task 16–17 (THEO BÁO CÁO TRƯỚC — `docs/demo/BAO_CAO_KIEM_THU_CHUC_NANG.md`).

---

## UC-08 — Nhập hồ sơ giảng viên từ JSON (kiểm tra, xem trước, nhập)

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-08 (mở rộng bởi UC-08a) |
| **Mục tiêu** | Đưa bộ hồ sơ giảng viên ICTU (tệp JSON theo `ictu_lecturers.schema.json`) vào CSDL một cách an toàn: kiểm tra, xem trước hậu quả, rồi mới áp dụng; không tạo bản ghi trùng; không gộp theo tên |
| **Actor chính / phụ** | Chính: **ADMIN**. Phụ: Hệ thống (dịch vụ nhập). Không có actor REVIEWER/LECTURER |
| **Điều kiện trước** | Đã đăng nhập bằng tài khoản ADMIN còn hoạt động; có tệp `.json` hợp lệ về đuôi và kích thước ≤ giới hạn cấu hình; DB sẵn sàng |
| **Luồng chính** | 1. ADMIN vào **Nhập dữ liệu** (`/imports`) và chọn tệp JSON.<br>2. Hệ thống **xem trước** (`POST /lecturers/import/preview`): kiểm schema, đếm bản ghi sẽ tạo mới/cập nhật/cảnh báo/lỗi — **không ghi DB**.<br>3. ADMIN xem kết quả xem trước và bấm xác nhận nhập.<br>4. Hệ thống áp dụng trong **một giao dịch** (`POST /lecturers/import`): khớp hồ sơ theo thứ tự `source_id` → mã cán bộ → email; ghi `lecturers`, `lecturer_source_snapshots`, `lecturer_known_publications`; ghi audit `LECTURER_DATASET_IMPORTED`.<br>5. Giao diện hiển thị kết quả và đợt nhập xuất hiện trong lịch sử |
| **Luồng thay thế** | A1. ADMIN chỉ xem trước rồi bỏ qua (không có thay đổi dữ liệu).<br>A2. Nhập lại cùng tệp: không tạo bản ghi mới (idempotent); bản ghi chỉ cập nhật khi nguồn đổi.<br>A3. Có cảnh báo trùng tên/bộ môn: chỉ cảnh báo, **không chặn** và **không gộp** |
| **Luồng lỗi** | E1. Không chọn tệp / tệp rỗng / tên tệp sai → 422 `INVALID_IMPORT_FILE`.<br>E2. Đuôi không phải `.json` → 422 `UNSUPPORTED_IMPORT_FORMAT`.<br>E3. Tệp quá lớn → 413 `IMPORT_FILE_TOO_LARGE`.<br>E4. JSON sai cú pháp/sai schema/email trùng trong tệp → từ chối ở bước xem trước hoặc nhập (422), không ghi gì.<br>E5. Xung đột định danh (source_id→hồ sơ A nhưng mã/email thuộc hồ sơ B, ORCID/URL đã thuộc người khác…) → **chặn trước khi ghi**.<br>E6. Không phải ADMIN → 403; chưa đăng nhập → 401.<br>E7. Lỗi DB → 503 `DATABASE_UNAVAILABLE`, giao dịch rollback |
| **Điều kiện sau** | Thành công: hồ sơ và bản chụp nguồn đã lưu, có audit; giảng viên vắng mặt trong tệp **không bị xóa/vô hiệu hóa**. Lỗi: DB không đổi |
| **Dữ liệu thay đổi** | Ghi: `lecturers`, `lecturer_source_snapshots`, `lecturer_known_publications`, `audit_events`. **Không** chạm `users` (tài khoản đăng nhập) |
| **Quyền truy cập** | ADMIN (cả hai API); route giao diện `/imports` chỉ ADMIN |
| **API / UI thực tế** | API: `POST /api/v1/lecturers/import/preview`, `POST /api/v1/lecturers/import`. UI: `/imports` (thẻ "Thêm giảng viên", khung kết quả "kiểm tra dữ liệu"). Dịch vụ: `lecturer_dataset/importer.py`, `parser.py` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Giới hạn: `tel` và Google Scholar trong JSON nguồn không có cột DB |
| **Test case tương ứng** | pytest: `test_lecturer_import_api` — `test_preview_does_not_mutate_db`, `test_preview_counts_match_fixture`, `test_preview_rejects_unsupported_extension`, `test_preview_rejects_invalid_schema`, `test_import_creates_records_then_idempotent`, `test_import_rejects_invalid_json`, `test_import_rejects_duplicate_emails`, `test_preview_requires_admin_role`, `test_import_requires_admin_role`, `test_import_requires_authentication`; `test_lecturer_json_roundtrip`. E2E: §6.4 báo cáo Task 16 (ảnh 30–34) |

---

## UC-08a — Hoàn tác đợt nhập hồ sơ giảng viên

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-08a — **«extend» UC-08** (hành vi tùy chọn sau khi đã có đợt nhập) |
| **Mục tiêu** | Đưa dữ liệu hồ sơ về trạng thái trước một đợt nhập mà không mất bản ghi do nguồn khác tạo |
| **Actor chính / phụ** | Chính: **ADMIN**. Phụ: Hệ thống |
| **Điều kiện trước** | Đợt nhập hồ sơ giảng viên đã áp dụng và chưa hoàn tác; không có tài khoản người dùng hoặc danh tính Scopus phụ thuộc vào bản ghi sẽ xóa |
| **Luồng chính** | 1. ADMIN mở **Chi tiết đợt nhập** → "Xóa đợt nhập" → chọn **Hoàn tác**.<br>2. Hệ thống (`POST /imports/{id}/rollback`, cùng dịch vụ với `POST /lecturers/import/{id}/rollback`) kiểm điều kiện phụ thuộc.<br>3. Xóa bản ghi do đợt này tạo; khôi phục bản ghi do đợt này cập nhật về trạng thái trước (theo bản chụp); **giữ bản ghi đa nguồn** và bản ghi tạo tay.<br>4. Đặt trạng thái đợt là đã hoàn tác; ghi audit `LECTURER_DATASET_ROLLED_BACK` |
| **Luồng thay thế** | A1. Xóa lịch sử đợt (ẩn) thay vì hoàn tác dữ liệu: audit `LECTURER_DATASET_HISTORY_DELETED` |
| **Luồng lỗi** | E1. Có tài khoản người dùng liên kết hoặc danh tính Scopus phụ thuộc → 409.<br>E2. Đợt đã hoàn tác → 409.<br>E3. Không tìm thấy đợt → 404 `LECTURER_IMPORT_NOT_FOUND`.<br>E4. Không phải ADMIN → 403.<br>E5. Lỗi DB giữa chừng → rollback nguyên tử, không để ghi dở |
| **Điều kiện sau** | Dữ liệu hồ sơ trở về trước đợt; audit cũ **không bị sửa** (chỉ thêm sự kiện mới) |
| **Dữ liệu thay đổi** | `lecturers`, `lecturer_source_snapshots`, `lecturer_known_publications`, `audit_events` |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | `POST /api/v1/imports/{import_id}/rollback` (giao diện dùng); `POST /api/v1/lecturers/import/{import_id}/rollback`; UI `/imports` → Chi tiết đợt nhập |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Chỉ hoàn tác cấp **đợt nhập**, không hoàn tác từng quyết định duyệt (GAP-07) |
| **Test case tương ứng** | `test_lecturer_rollback` (12 ca): `test_manual_lecturer_survives_and_created_lecturer_removed`, `test_updated_existing_lecturer_restores_prior_state`, `test_multi_source_lecturer_survives_rollback`, `test_user_linkage_blocks_rollback_with_409`, `test_scopus_identity_dependency_blocks_rollback`, `test_rollback_already_rolled_back_raises_409`, `test_rollback_unknown_import_returns_404`, `test_rollback_endpoint_requires_admin`, `test_rollback_is_atomic_on_database_error`, `test_regression_audit_trail_is_append_only`. E2E: ảnh 33 (Task 16) |

---

## UC-10 — Nhập tệp CSV Scopus

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-10 (mở rộng bởi UC-10a) |
| **Mục tiêu** | Đưa tệp CSV xuất từ Scopus vào hệ thống dưới dạng **dữ liệu thô bất biến**, chống nhập trùng nội dung, báo lỗi theo dòng, theo dõi được tiến độ |
| **Actor chính / phụ** | Chính: **ADMIN**. Phụ: Hệ thống (tiến trình nền) |
| **Điều kiện trước** | ADMIN đã đăng nhập; có tệp `.csv` xuất từ Scopus (có cột `EID`), kích thước ≤ `SCOPUS_IMPORT_MAX_BYTES` |
| **Luồng chính** | 1. ADMIN vào `/imports` → "Thêm tệp Scopus" và chọn CSV.<br>2. Hệ thống (`POST /imports/scopus`) kiểm tên/đuôi/kích thước/nội dung rỗng, **tính SHA-256 tệp** và tạo đợt nhập (**202 Accepted**), chạy xử lý ở **tiến trình nền** (`BackgroundTasks`).<br>3. Tiến trình nền phân tích CSV (`ScopusCsvParser`: giữ nguyên giá trị gốc, không chuẩn hóa), ghi từng dòng vào `raw_scopus_records` (VALID/INVALID kèm `validation_errors`, `row_hash`), cập nhật số đếm và trạng thái (`RECEIVED → PARSING → VALIDATED → STAGED → APPLIED`).<br>4. Giao diện hiển thị tiến độ; khi xong, đợt nhập có tổng/hợp lệ/lỗi và danh sách lỗi theo dòng (`row_errors`) trong chi tiết đợt |
| **Luồng thay thế** | A1. Cùng nội dung đang được xử lý → 409 `IMPORT_ALREADY_PROCESSING` kèm `existing_import_id`.<br>A2. Cùng nội dung đã nhập xong → 409 `DUPLICATE_IMPORT_CONFIRMATION_REQUIRED` kèm đợt gốc; ADMIN có thể xác nhận để nhập lại (`allow_duplicate=true`) — có cảnh báo, không ghi đè.<br>A3. ADMIN hủy giữa chừng (UC-10a) |
| **Luồng lỗi** | E1. Không chọn tệp/tên sai/tệp rỗng → 422 `INVALID_IMPORT_FILE` / `EMPTY_IMPORT_FILE`.<br>E2. Không phải CSV → 422 `UNSUPPORTED_IMPORT_FORMAT`.<br>E3. Quá lớn → 413 `IMPORT_FILE_TOO_LARGE`.<br>E4. CSV không phải bản xuất Scopus (thiếu cột `EID`) → bị từ chối ngay (Task 17).<br>E5. Dòng sai (thiếu EID, sai định dạng) → ghi INVALID kèm lý do, **không dừng cả đợt**.<br>E6. Lỗi lưu trữ → 500 `IMPORT_FAILED`; đợt chuyển `FAILED`.<br>E7. Không phải ADMIN → 403 |
| **Điều kiện sau** | Dòng thô đã lưu bất biến (nguồn cho chuẩn hóa); chưa có công bố chuẩn hóa nào được tạo (là UC-11); có audit `SCOPUS_IMPORT_STARTED/COMPLETED/FAILED` |
| **Dữ liệu thay đổi** | `scopus_imports`, `raw_scopus_records`, `audit_events` |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | API: `POST /api/v1/imports/scopus`; `GET /imports`, `/imports/history`, `/imports/{id}`, `/imports/config`. UI: `/imports`. Dịch vụ: `scopus_import_service.py`, `parser/scopus_csv_parser.py` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Giới hạn: **không có bước xem trước/duyệt trước khi lưu** như JSON (dữ liệu thô lưu ngay; chuẩn hóa là bước riêng); CSV 22 cột thật (`Authors`, `Author full names`, `Author(s) ID`, `Title`, `Year`, `Source title`, `Volume`, `Issue`, `Art. No.`, `Page start`, `Page end`, `Cited by`, `DOI`, `Link`, `Abstract`, `Author Keywords`, `Document Type`, `Publication Stage`, `Open Access`, `Source`, `EID`, `Publisher`) — bộ kiểm tra bắt buộc cột `EID`, chưa chứng minh kiểm đủ 22 cột |
| **Test case tương ứng** | `test_scopus_import_api` — `test_admin_upload_valid_csv`, `test_non_admin_upload_is_forbidden`, `test_invalid_uploads_return_stable_codes`, `test_oversized_upload_is_rejected`, `test_active_duplicate_returns_existing_job_id`, `test_completed_duplicate_requires_explicit_confirmation`; `test_scopus_csv_parser`; `test_scopus_import_service`; `test_scopus_decoupled_lifecycle`. E2E: §6.5 (ảnh 40–41; 660/660 bản ghi) |

---

## UC-10a — Quản lý đợt nhập CSV (hủy, lưu trữ, khôi phục lịch sử, xóa)

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-10a — **«extend» UC-10** |
| **Mục tiêu** | Kiểm soát vòng đời một đợt nhập CSV sau khi tạo: dừng, ẩn khỏi lịch sử, hiện lại, hoặc xóa nếu chưa có dữ liệu nào phụ thuộc |
| **Actor chính / phụ** | Chính: **ADMIN** |
| **Điều kiện trước** | Đã có đợt nhập CSV; để **hủy**: đợt còn đang chạy; để **xóa**: đợt đã kết thúc và chưa được công bố/tác giả tham chiếu |
| **Luồng chính** | 1. ADMIN mở danh sách đợt nhập hoặc chi tiết đợt.<br>2. Chọn thao tác: **Hủy** (`POST /imports/{id}/cancel`), **Lưu trữ/Ẩn** (`/archive`), **Hiện lại** (`/restore-history`), **Xóa** (`DELETE /imports/{id}`).<br>3. Hệ thống thực hiện, ghi audit (`SCOPUS_IMPORT_HISTORY_ARCHIVED/RESTORED`, `SCOPUS_IMPORT_DELETED`…) |
| **Luồng thay thế** | A1. Lưu trữ/khôi phục lặp lại: idempotent.<br>A2. Lưu trữ đợt đã được dùng: giữ nguyên provenance (chỉ ẩn khỏi danh sách mặc định) |
| **Luồng lỗi** | E1. Hủy đợt đã kết thúc → 409 `IMPORT_ALREADY_FINISHED`.<br>E2. Xóa đợt đã được công bố hoặc biến thể tên tác giả tham chiếu → 409 kèm số đếm tham chiếu (đợt đang xử lý cũng không xóa được).<br>E3. Không tìm thấy → 404 `IMPORT_NOT_FOUND`.<br>E4. Không phải ADMIN → 403 |
| **Điều kiện sau** | Trạng thái đợt thay đổi đúng thao tác; dữ liệu chuẩn hóa đã sinh từ đợt **không bị mất** khi chỉ ẩn |
| **Dữ liệu thay đổi** | `scopus_imports` (trạng thái/ẩn), xóa `raw_scopus_records` + `scopus_imports` khi xóa đợt chưa dùng, `audit_events` |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | `POST /api/v1/imports/{id}/cancel`, `/archive`, `/restore-history`; `DELETE /api/v1/imports/{id}`. UI `/imports` (chi tiết đợt, nút xóa); các thao tác hủy/lưu trữ/khôi phục chủ yếu kiểm qua API |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (API đầy đủ; UI một phần)** |
| **Test case tương ứng** | `test_import_usage_and_archive` (17 ca): `test_active_import_cannot_be_deleted`, `test_delete_unused_terminal_import_succeeds`, `test_delete_used_import_returns_409_with_counts`, `test_stale_delete_race_rechecks_dependencies`, `test_archive_unused_import_appends_audit`, `test_archive_used_import_preserves_provenance`, `test_repeated_archive_is_idempotent`, `test_repeated_restore_is_idempotent`; `test_scopus_import_api::test_delete_import_returns_boolean_deleted_flag` |

---

## UC-25 — Nạp công bố đã biết (Craw) và đơn vị công tác ngoài (OpenAlex/Crossref)

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-25 — **chỉ chạy bằng script CLI** |
| **Mục tiêu** | Bổ sung **bằng chứng ngoài** để hỗ trợ đối sánh: (a) công bố đã biết của từng giảng viên từ Craw ICTU; (b) đơn vị công tác theo từng tác giả trên từng bài từ OpenAlex/Crossref |
| **Actor chính / phụ** | Chính: **Kỹ thuật viên** (chạy script; không phải vai trò trong ứng dụng). Phụ: Hệ thống nguồn ngoài (tệp tải sẵn — không gọi API trực tuyến) |
| **Điều kiện trước** | CSDL đã có hồ sơ giảng viên (UC-08) và công bố/tác giả đã chuẩn hóa (UC-11, UC-12); có tệp snapshot Craw và JSONL OpenAlex/Crossref ngoài Git; script chạy trên đúng DB (có kiểm tên DB/cổng) |
| **Luồng chính** | 1. Kỹ thuật viên chạy `ingest_craw_known_publications.py`: ghi `lecturer_source_snapshots` (nguồn `ictu_craw`) và `lecturer_known_publications` (DOI/tiêu đề chuẩn hóa).<br>2. Chạy `import_author_affiliations.py`: với mỗi bài, căn chỉnh tác giả nguồn ngoài với **vị trí tác giả Scopus** (`align_paper`): **VERIFIED** (chuỗi ORCID → Scopus ID), **CORROBORATED** (cùng số tác giả/vị trí/tên, không mâu thuẫn), hoặc **UNRESOLVED** (kèm lý do); ghi `organizations`, `publication_author_affiliation_resolutions`, `publication_author_affiliations`.<br>3. In báo cáo số đếm (tạo/dùng lại/bỏ qua) |
| **Luồng thay thế** | A1. Chạy `--dry-run` (chỉ đọc, không ghi DB) trước, rồi `--apply`; cả hai bắt buộc `--expected-database` (và `--expected-port`; cổng 5432 luôn bị từ chối).<br>A2. Hai nguồn mâu thuẫn: chính sách đa nguồn (`apply_cross_source_policy`) loại bản ghi mâu thuẫn |
| **Luồng lỗi** | E1. DB/cổng không đúng → script từ chối.<br>E2. Dữ liệu nguồn không hợp lệ → bản ghi bị bỏ qua và đếm lỗi.<br>E3. Tên người dùng **không bao giờ** đủ để gán VERIFIED |
| **Điều kiện sau** | Bằng chứng ngoài đã lưu; nhập lại không tạo trùng (UNIQUE theo vị trí tác giả + nguồn + SHA-256 payload) |
| **Dữ liệu thay đổi** | `lecturer_source_snapshots`, `lecturer_known_publications`, `organizations`, `publication_author_affiliation_resolutions`, `publication_author_affiliations` |
| **Quyền truy cập** | Không qua API/RBAC; do người có quyền chạy script trên máy chủ và truy cập DB |
| **API / UI thực tế** | Script: `backend/scripts/ingest_craw_known_publications.py`, `backend/scripts/import_author_affiliations.py`; dịch vụ `lecturer_dataset/known_publication_ingestion.py`, `affiliation_import.py`, `author_affiliation.py`. **Không có UI** |
| **Trạng thái triển khai** | **CHỈ CLI** (GAP-15). Kết quả trên teacher DB (THEO BÁO CÁO TRƯỚC): 327 công bố đã biết/48 giảng viên; 5.502 resolution (VERIFIED 781, CORROBORATED 4.130, UNRESOLVED 591) |
| **Test case tương ứng** | `test_ingest_craw_known_publications_cli`, `test_import_author_affiliations_cli`, `test_affiliation_import_and_api`, `unit/test_author_affiliation`, `unit/test_known_publication_ingestion` |
