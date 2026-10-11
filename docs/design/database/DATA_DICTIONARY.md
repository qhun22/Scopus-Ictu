# Data Dictionary — 24 bảng PostgreSQL của Scopus–ICTU

> **Sinh tự động** từ lược đồ PostgreSQL thật bằng `docs/design/tools/gen_database_assets.py` (cấu trúc) + `database/source/descriptions_vi.json` (mô tả nghiệp vụ, biên soạn tay). Nguồn cấu trúc: DB `scopus_ictu_demo_teacher_20261014` (PostgreSQL 17.10, `alembic_version = a9c2e4f71b30`), trích lúc `2026-10-09T15:10:58+00:00` ở chế độ **chỉ đọc**. Số dòng là số đếm tại thời điểm trích (dữ liệu demo teacher), **không phải dữ liệu thật của ICTU**.

**Phạm vi:** 24 bảng · 245 cột · 30 khóa ngoại · 99 CHECK. Không có trigger, hàm hay view do dự án định nghĩa (trigger = 0, hàm = 0).

**Chú giải:** `PK` khóa chính · `FK→bảng.cột` khóa ngoại · `UQ` duy nhất · `UQ một phần` chỉ mục unique có điều kiện (partial) · `NULL` = cho phép NULL. Mọi khóa chính là `uuid` mặc định `gen_random_uuid()`; mọi mốc thời gian là `timestamptz`.

## Mục lục

| Cụm | Bảng | Số cột | Số dòng (demo) |
|---|---|--:|--:|
| A. Người dùng và kiểm toán | [`users`](#users) | 11 | 3 |
| A. Người dùng và kiểm toán | [`user_notifications`](#user_notifications) | 9 | 0 |
| A. Người dùng và kiểm toán | [`audit_events`](#audit_events) | 16 | 16 |
| B. Hồ sơ giảng viên (dữ liệu chủ) | [`lecturers`](#lecturers) | 17 | 411 |
| B. Hồ sơ giảng viên (dữ liệu chủ) | [`lecturer_source_snapshots`](#lecturer_source_snapshots) | 11 | 1687 |
| B. Hồ sơ giảng viên (dữ liệu chủ) | [`lecturer_known_publications`](#lecturer_known_publications) | 10 | 327 |
| C. Nhập dữ liệu thô Scopus | [`scopus_imports`](#scopus_imports) | 12 | 1 |
| C. Nhập dữ liệu thô Scopus | [`raw_scopus_records`](#raw_scopus_records) | 10 | 660 |
| D. Công bố và tác giả chuẩn hóa | [`publications`](#publications) | 19 | 660 |
| D. Công bố và tác giả chuẩn hóa | [`publication_raw_sources`](#publication_raw_sources) | 4 | 660 |
| D. Công bố và tác giả chuẩn hóa | [`scopus_authors`](#scopus_authors) | 5 | 1207 |
| D. Công bố và tác giả chuẩn hóa | [`scopus_author_name_variants`](#scopus_author_name_variants) | 7 | 2768 |
| D. Công bố và tác giả chuẩn hóa | [`publication_authors`](#publication_authors) | 5 | 2751 |
| E. Đơn vị công tác theo tác giả (affiliation) | [`organizations`](#organizations) | 7 | 217 |
| E. Đơn vị công tác theo tác giả (affiliation) | [`publication_author_affiliation_resolutions`](#publication_author_affiliation_resolutions) | 17 | 5502 |
| E. Đơn vị công tác theo tác giả (affiliation) | [`publication_author_affiliations`](#publication_author_affiliations) | 8 | 4147 |
| F. Đối sánh, duyệt và danh tính | [`candidate_generation_runs`](#candidate_generation_runs) | 10 | 2 |
| F. Đối sánh, duyệt và danh tính | [`lecturer_scopus_candidates`](#lecturer_scopus_candidates) | 9 | 40 |
| F. Đối sánh, duyệt và danh tính | [`lecturer_scopus_candidate_observations`](#lecturer_scopus_candidate_observations) | 7 | 80 |
| F. Đối sánh, duyệt và danh tính | [`lecturer_scopus_candidate_evidence`](#lecturer_scopus_candidate_evidence) | 9 | 203 |
| F. Đối sánh, duyệt và danh tính | [`lecturer_scopus_candidate_reviews`](#lecturer_scopus_candidate_reviews) | 12 | 0 |
| F. Đối sánh, duyệt và danh tính | [`lecturer_scopus_identities`](#lecturer_scopus_identities) | 10 | 0 |
| F. Đối sánh, duyệt và danh tính | [`identity_evidence`](#identity_evidence) | 10 | 0 |
| F. Đối sánh, duyệt và danh tính | [`mapping_reviews`](#mapping_reviews) | 10 | 0 |

## Cụm A — Người dùng và kiểm toán

### users

**Tài khoản đăng nhập.** Tài khoản và vai trò (ADMIN / REVIEWER / LECTURER). Một hồ sơ giảng viên có tối đa một tài khoản; tài khoản LECTURER bắt buộc gắn hồ sơ giảng viên.

- Cụm: **A** · Số dòng demo: **3** · UC liên quan: UC-01, 02, 06, 20–22
- Khóa chính: `id`
- Khóa ngoại: `lecturer_id` → `lecturers(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK, UQ một phần | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `email` | `varchar(255)` | không |  | UQ một phần; CHECK: `email_not_empty` | Email đăng nhập; duy nhất không phân biệt hoa/thường (chỉ mục unique trên lower(email)). |
| 3 | `password_hash` | `text` | không |  |  | Mật khẩu đã băm (Argon2id). Không bao giờ lưu mật khẩu thô. |
| 4 | `display_name` | `varchar(255)` | không |  | CHECK: `display_name_not_empty` | Tên hiển thị. |
| 5 | `role` | `varchar(20)` | không |  | CHECK: `lecturer_account_required`, `role` | Vai trò: ADMIN, REVIEWER hoặc LECTURER. |
| 6 | `lecturer_id` | `uuid` | có |  | FK→`lecturers.id`, UQ một phần; CHECK: `lecturer_account_required` | Hồ sơ giảng viên được liên kết (NULL với ADMIN/REVIEWER; bắt buộc với LECTURER; mỗi hồ sơ tối đa 1 tài khoản). |
| 7 | `is_active` | `boolean` | không | `true` |  | FALSE = tài khoản bị khóa (đăng nhập bị từ chối). |
| 8 | `version` | `integer` | không | `1` | CHECK: `version` | Số phiên bản dùng cho khóa lạc quan (optimistic locking); luôn >= 1. |
| 9 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |
| 10 | `updated_at` | `timestamptz` | không | `now()` |  | Thời điểm cập nhật gần nhất (timestamptz, mặc định now()). |
| 11 | `auth_version` | `integer` | không | `1` | CHECK: `auth_version` | Tăng khi đổi mật khẩu/vai trò/khóa để thu hồi các phiên (token) cũ. |

**Ràng buộc duy nhất:** `uq_users_email_ci` (lower((email)::text)) WHERE None; `uq_users_lecturer` (lecturer_id) WHERE (lecturer_id IS NOT NULL)

### user_notifications

**Thông báo cho người dùng.** Thông báo hệ thống gửi tới người dùng khi tài khoản bị tác động (cập nhật hồ sơ, đổi vai trò, khóa/mở khóa, đặt lại mật khẩu). Được lấy về khi tải trang; chưa có trang Thông báo riêng.

- Cụm: **A** · Số dòng demo: **0** · UC liên quan: UC-03, 06
- Khóa chính: `id`
- Khóa ngoại: `user_id` → `users(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `user_id` | `uuid` | không |  | FK→`users.id` | Người nhận. |
| 3 | `notification_type` | `varchar(40)` | không |  | CHECK: `notification_type` | PROFILE_UPDATED, ROLE_CHANGED, ACCOUNT_LOCKED, ACCOUNT_UNLOCKED, PASSWORD_RESET. |
| 4 | `title` | `varchar(255)` | không |  |  | Tiêu đề thông báo. |
| 5 | `message` | `text` | không |  |  | Nội dung thông báo. |
| 6 | `metadata` | `jsonb` | không | `'{}'::jsonb` | CHECK: `metadata_object` | Dữ liệu kèm theo (JSON object). |
| 7 | `is_read` | `boolean` | không | `false` | CHECK: `read_consistency` | Đã đọc chưa. |
| 8 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |
| 9 | `read_at` | `timestamptz` | có |  | CHECK: `read_consistency` | Thời điểm đọc (NULL khi chưa đọc; nhất quán với is_read). |

**Chỉ mục:** `ix_user_notifications_created_at` (created_at); `ix_user_notifications_unread_lookup` (user_id, is_read, created_at); `ix_user_notifications_user_id` (user_id)

### audit_events

**Nhật ký kiểm toán (chỉ ghi thêm).** Nhật ký bất biến theo quy ước ADR-003: chỉ INSERT, không UPDATE/DELETE. Tính chỉ-thêm được bảo đảm ở tầng dịch vụ, KHÔNG có trigger/REVOKE trong DB. entity_id là tham chiếu đa hình (không có khóa ngoại).

- Cụm: **A** · Số dòng demo: **16** · UC liên quan: UC-07 và mọi UC có ghi dữ liệu
- Khóa chính: `id`
- Khóa ngoại: `actor_user_id` → `users(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `entity_type` | `varchar(100)` | không |  | CHECK: `entity_type_format` | Loại thực thể bị tác động (snake_case, ví dụ lecturer, publication_export). |
| 3 | `entity_id` | `uuid` | không |  |  | UUID thực thể bị tác động — KHÔNG có khóa ngoại (đa hình theo entity_type). |
| 4 | `action` | `varchar(64)` | không |  | CHECK: `action_format` | Mã hành động IN HOA (ví dụ LECTURER_CREATED, PUBLICATION_DATASET_EXPORTED). |
| 5 | `actor_type` | `varchar(20)` | không |  | CHECK: `actor_invariant`, `actor_type` | USER (người dùng) hoặc SYSTEM (tiến trình hệ thống). |
| 6 | `actor_user_id` | `uuid` | có |  | FK→`users.id`; CHECK: `actor_invariant` | Người thực hiện khi actor_type = USER (FK → users). |
| 7 | `actor_service` | `varchar(100)` | có |  | CHECK: `actor_invariant` | Tên dịch vụ/tiến trình khi actor_type = SYSTEM. |
| 8 | `before_state` | `jsonb` | có |  | CHECK: `before_state_object` | Trạng thái trước (JSON object, tùy chọn). |
| 9 | `after_state` | `jsonb` | có |  | CHECK: `after_state_object` | Trạng thái sau (JSON object, tùy chọn). |
| 10 | `reason` | `text` | có |  |  | Lý do/ghi chú. |
| 11 | `request_id` | `varchar(128)` | có |  |  | Mã yêu cầu HTTP. |
| 12 | `correlation_id` | `varchar(128)` | có |  |  | Mã tương quan giữa nhiều sự kiện. |
| 13 | `ip_address` | `inet` | có |  |  | Địa chỉ IP nguồn. |
| 14 | `user_agent` | `text` | có |  |  | User-Agent của trình duyệt/máy khách. |
| 15 | `metadata` | `jsonb` | có |  | CHECK: `metadata_object` | Thông tin bổ sung (JSON object), ví dụ record_count/format của lần xuất. |
| 16 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Chỉ mục:** `ix_audit_events_actor` (actor_user_id, created_at); `ix_audit_events_correlation` (correlation_id) WHERE (correlation_id IS NOT NULL); `ix_audit_events_created` (created_at); `ix_audit_events_entity` (entity_type, entity_id, created_at)

## Cụm B — Hồ sơ giảng viên (dữ liệu chủ)

### lecturers

**Hồ sơ giảng viên (dữ liệu chủ).** Hồ sơ giảng viên ICTU. KHÔNG chứa Scopus Author ID: liên kết giảng viên ↔ Scopus nằm ở lecturer_scopus_candidates / lecturer_scopus_identities. Email hồ sơ được phép trùng (có cảnh báo); mã cán bộ và ORCID duy nhất khi có.

- Cụm: **B** · Số dòng demo: **411** · UC liên quan: UC-05, 08, 09, 18, 20
- Khóa chính: `id`

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK, UQ một phần | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `staff_code` | `varchar(50)` | có |  | UQ một phần | Mã cán bộ (có thể NULL; duy nhất khi có giá trị). |
| 3 | `full_name` | `varchar(255)` | không |  |  | Họ tên đầy đủ như nguồn (có thể kèm tiền tố học hàm/học vị như TS., ThS.). |
| 4 | `full_name_normalized` | `varchar(255)` | không |  |  | Họ tên đã chuẩn hóa để tra cứu. |
| 5 | `email` | `varchar(255)` | có |  |  | Email đơn vị (cho phép trùng giữa các hồ sơ; có chỉ mục lower(email)). |
| 6 | `academic_rank` | `varchar(50)` | có |  |  | Học hàm. |
| 7 | `academic_degree` | `varchar(50)` | có |  |  | Học vị. |
| 8 | `position` | `varchar(100)` | có |  |  | Chức vụ. |
| 9 | `department` | `varchar(150)` | có |  |  | Bộ môn/phòng ban (phần lớn dữ liệu nguồn còn trống). |
| 10 | `faculty` | `varchar(150)` | có |  |  | Khoa (phần lớn dữ liệu nguồn còn trống). |
| 11 | `repository_profile_url` | `text` | có |  |  | Đường dẫn hồ sơ trên ICTU Repository (khóa nguồn). |
| 12 | `repository_profile_id` | `varchar(100)` | có |  |  | Mã hồ sơ trên ICTU Repository. |
| 13 | `orcid` | `varchar(19)` | có |  | UQ một phần; CHECK: `orcid_format` | ORCID (định dạng 0000-0000-0000-000X); duy nhất khi có giá trị. |
| 14 | `is_active` | `boolean` | không | `true` |  | Hồ sơ còn hiệu lực. |
| 15 | `version` | `integer` | không | `1` | CHECK: `version` | Số phiên bản dùng cho khóa lạc quan (optimistic locking); luôn >= 1. |
| 16 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |
| 17 | `updated_at` | `timestamptz` | không | `now()` |  | Thời điểm cập nhật gần nhất (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_lecturers_orcid` (orcid) WHERE (orcid IS NOT NULL); `uq_lecturers_staff_code` (staff_code) WHERE (staff_code IS NOT NULL)

**Chỉ mục:** `ix_lecturers_email_ci` (lower((email)::text)) WHERE (email IS NOT NULL); `ix_lecturers_full_name_normalized` (full_name_normalized)

### lecturer_source_snapshots

**Bản chụp nguồn của hồ sơ giảng viên.** Bản chụp bất biến (append-only) dữ liệu nguồn của một lần nhập hồ sơ giảng viên: payload JSON gốc, SHA-256, phiên bản bộ phân tích. Là cha của lecturer_known_publications qua khóa ghép (id, lecturer_id).

- Cụm: **B** · Số dòng demo: **1687** · UC liên quan: UC-08, 25
- Khóa chính: `id`
- Khóa ngoại: `lecturer_id` → `lecturers(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK, UQ(id,lecturer_id) | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `lecturer_id` | `uuid` | có |  | FK→`lecturers.id`, UQ(id,lecturer_id) | Giảng viên được bản chụp mô tả (có thể NULL khi chưa gán). |
| 3 | `source_system` | `varchar(50)` | không |  |  | Hệ nguồn (ví dụ ICTU Repository). |
| 4 | `source_url` | `text` | không |  |  | Địa chỉ nguồn. |
| 5 | `snapshot_hash` | `varchar(64)` | không |  | CHECK: `snapshot_hash` | SHA-256 của bản chụp (64 ký tự hex). |
| 6 | `raw_payload` | `jsonb` | không |  | CHECK: `raw_payload_object` | Payload gốc (JSON object). |
| 7 | `parser_version` | `varchar(100)` | không |  |  | Phiên bản bộ phân tích đã xử lý. |
| 8 | `validation_status` | `varchar(20)` | không |  | CHECK: `validation_status` | VALID hoặc INVALID. |
| 9 | `validation_errors` | `jsonb` | có |  | CHECK: `validation_errors_array` | Danh sách lỗi (JSON array) khi INVALID. |
| 10 | `fetched_at` | `timestamptz` | không |  |  | Thời điểm lấy dữ liệu nguồn. |
| 11 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_lecturer_source_snapshots_id_lecturer` (id, lecturer_id)

**Chỉ mục:** `ix_lecturer_source_snapshots_lecturer_id` (lecturer_id); `ix_snapshots_source_lookup` (source_system, source_url, fetched_at)

### lecturer_known_publications

**Công bố đã biết của giảng viên (từ nguồn ICTU/Craw).** Công bố do nguồn ICTU liệt kê cho một giảng viên; dùng làm bằng chứng công bố khi sinh ứng viên (khớp DOI/tiêu đề với công bố Scopus). Khóa ghép (snapshot_id, lecturer_id) bảo đảm công bố thuộc đúng giảng viên của bản chụp.

- Cụm: **B** · Số dòng demo: **327** · UC liên quan: UC-08, 24, 25
- Khóa chính: `id`
- Khóa ngoại: `snapshot_id,lecturer_id` → `lecturer_source_snapshots(id,lecturer_id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `lecturer_id` | `uuid` | không |  | FK→`lecturer_source_snapshots.lecturer_id` | Giảng viên sở hữu công bố. |
| 3 | `snapshot_id` | `uuid` | không |  | FK→`lecturer_source_snapshots.id` | Bản chụp nguồn chứa công bố (FK ghép cùng lecturer_id). |
| 4 | `title_raw` | `text` | không |  |  | Tiêu đề nguyên văn. |
| 5 | `title_normalized` | `text` | không |  |  | Tiêu đề đã chuẩn hóa để so khớp. |
| 6 | `doi_raw` | `varchar(255)` | có |  |  | DOI nguyên văn. |
| 7 | `doi_normalized` | `varchar(255)` | có |  |  | DOI đã chuẩn hóa (chữ thường, bỏ tiền tố URL) để so khớp. |
| 8 | `source_title_raw` | `text` | có |  |  | Tên nguồn xuất bản nguyên văn (chuỗi, không chuẩn hóa). |
| 9 | `published_year` | `integer` | có |  | CHECK: `published_year` | Năm xuất bản (1000–9999). |
| 10 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Chỉ mục:** `ix_known_pubs_lecturer_year` (lecturer_id, published_year); `ix_lecturer_known_publications_doi` (doi_normalized) WHERE (doi_normalized IS NOT NULL); `ix_lecturer_known_publications_lecturer_id` (lecturer_id); `ix_lecturer_known_publications_snapshot_id` (snapshot_id)

## Cụm C — Nhập dữ liệu thô Scopus

### scopus_imports

**Đợt nhập CSV Scopus.** Một lần tải tệp CSV Scopus: SHA-256 tệp để chống nhập trùng, thống kê bản ghi, vòng đời trạng thái và tóm tắt chuẩn hóa. Không có khóa ngoại tới users (người nhập được truy qua audit_events).

- Cụm: **C** · Số dòng demo: **1** · UC liên quan: UC-10, 11, 12
- Khóa chính: `id`

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `file_name` | `varchar(255)` | không |  |  | Tên tệp tải lên. |
| 3 | `file_sha256` | `varchar(64)` | không |  | CHECK: `file_sha256` | SHA-256 nội dung tệp (chống nhập trùng nội dung). |
| 4 | `total_records` | `integer` | không | `0` | CHECK: `record_counts` | Tổng số dòng dữ liệu. |
| 5 | `valid_records` | `integer` | không | `0` | CHECK: `record_counts` | Số dòng hợp lệ. |
| 6 | `invalid_records` | `integer` | không | `0` | CHECK: `record_counts` | Số dòng không hợp lệ. |
| 7 | `status` | `varchar(20)` | không | `'RECEIVED'::character varying` | CHECK: `status` | RECEIVED, PARSING, VALIDATED, STAGED, APPLIED, FAILED hoặc CANCELLED. |
| 8 | `error_summary` | `jsonb` | có |  | CHECK: `error_summary_object` | Tóm tắt lỗi nhập (JSON object). |
| 9 | `version` | `integer` | không | `1` | CHECK: `version` | Số phiên bản dùng cho khóa lạc quan (optimistic locking); luôn >= 1. |
| 10 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |
| 11 | `updated_at` | `timestamptz` | không | `now()` |  | Thời điểm cập nhật gần nhất (timestamptz, mặc định now()). |
| 12 | `normalization_summary` | `jsonb` | có |  | CHECK: `normalization_summa_5872` | Bộ đếm kết quả chuẩn hóa công bố/tác giả (JSON object). |

**Chỉ mục:** `ix_scopus_imports_file_sha256` (file_sha256); `ix_scopus_imports_status` (status)

### raw_scopus_records

**Dòng dữ liệu thô Scopus (bất biến).** Từng dòng CSV được giữ nguyên trong raw_payload (JSON) cùng row_hash; không bị sửa khi chuẩn hóa. EID thô KHÔNG unique ở bảng này (tính duy nhất nằm ở publications.eid).

- Cụm: **C** · Số dòng demo: **660** · UC liên quan: UC-10, 11
- Khóa chính: `id`
- Khóa ngoại: `import_id` → `scopus_imports(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `import_id` | `uuid` | không |  | FK→`scopus_imports.id`, UQ(import_id,row_number) | Đợt nhập chứa dòng. |
| 3 | `row_number` | `integer` | không |  | UQ(import_id,row_number); CHECK: `row_number` | Số thứ tự dòng trong tệp (>= 1); duy nhất trong một đợt. |
| 4 | `row_hash` | `varchar(64)` | không |  | CHECK: `row_hash` | SHA-256 của dòng. |
| 5 | `eid_raw` | `text` | có |  |  | EID nguyên văn (có thể trống/sai). |
| 6 | `doi_raw` | `text` | có |  |  | DOI nguyên văn. |
| 7 | `raw_payload` | `jsonb` | không |  | CHECK: `raw_payload_object` | Toàn bộ giá trị các cột của dòng (JSON object). |
| 8 | `validation_status` | `varchar(20)` | không |  | CHECK: `validation_status` | VALID hoặc INVALID. |
| 9 | `validation_errors` | `jsonb` | có |  | CHECK: `validation_errors_array` | Lỗi theo dòng (JSON array) khi INVALID. |
| 10 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_raw_scopus_records_import_row` (import_id, row_number)

**Chỉ mục:** `ix_raw_scopus_records_doi_raw` (doi_raw) WHERE (doi_raw IS NOT NULL); `ix_raw_scopus_records_eid_raw` (eid_raw) WHERE (eid_raw IS NOT NULL)

## Cụm D — Công bố và tác giả chuẩn hóa

### publications

**Công bố chuẩn hóa.** Công bố sau chuẩn hóa, mỗi EID một dòng (khóa chống trùng). DOI lưu theo văn bản nguồn (đã cắt khoảng trắng, chưa chuẩn hóa chữ thường/tiền tố); nguồn xuất bản là chuỗi source_title (CHƯA có bảng thực thể nguồn xuất bản).

- Cụm: **D** · Số dòng demo: **660** · UC liên quan: UC-11, 13–15, 22
- Khóa chính: `id`

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `eid` | `text` | không |  | UQ; CHECK: `eid_not_empty` | Scopus EID chuẩn tắc (duy nhất). |
| 3 | `doi` | `varchar(255)` | có |  |  | DOI theo văn bản nguồn (chưa chuẩn hóa). |
| 4 | `title` | `text` | không |  |  | Tiêu đề công bố. |
| 5 | `title_normalized` | `text` | không |  |  | Tiêu đề chuẩn hóa (Unicode NFKC, chữ thường). |
| 6 | `source_title` | `text` | có |  |  | Tên nguồn xuất bản (tạp chí/hội nghị) dạng chuỗi. |
| 7 | `year` | `integer` | có |  | CHECK: `year_range` | Năm xuất bản (1000–9999). |
| 8 | `volume` | `text` | có |  |  | Tập. |
| 9 | `issue` | `text` | có |  |  | Số. |
| 10 | `art_no` | `text` | có |  |  | Mã bài báo. |
| 11 | `page_start` | `text` | có |  |  | Trang bắt đầu. |
| 12 | `page_end` | `text` | có |  |  | Trang kết thúc. |
| 13 | `cited_by_count` | `integer` | có |  | CHECK: `cited_by_count` | Số lần được trích dẫn (>= 0). |
| 14 | `document_type` | `varchar(50)` | có |  |  | Loại tài liệu (Article, Conference Paper…). |
| 15 | `publication_stage` | `varchar(50)` | có |  |  | Giai đoạn xuất bản. |
| 16 | `open_access_status` | `varchar(50)` | có |  |  | Tình trạng truy cập mở. |
| 17 | `version` | `integer` | không | `1` | CHECK: `version` | Số phiên bản dùng cho khóa lạc quan (optimistic locking); luôn >= 1. |
| 18 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |
| 19 | `updated_at` | `timestamptz` | không | `now()` |  | Thời điểm cập nhật gần nhất (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_publications_eid` (eid)

**Chỉ mục:** `ix_publications_doi` (doi) WHERE (doi IS NOT NULL); `ix_publications_year` (year)

### publication_raw_sources

**Nguồn gốc công bố (dòng thô → công bố).** Bảng provenance nối mỗi dòng thô với công bố chuẩn hóa sinh ra từ nó. Mỗi dòng thô tối đa một công bố; một công bố có thể có nhiều dòng thô (nhiều lần nhập).

- Cụm: **D** · Số dòng demo: **660** · UC liên quan: UC-11, 13
- Khóa chính: `id`
- Khóa ngoại: `publication_id` → `publications(id)` (ON DELETE RESTRICT); `raw_record_id` → `raw_scopus_records(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `publication_id` | `uuid` | không |  | FK→`publications.id` | Công bố chuẩn hóa. |
| 3 | `raw_record_id` | `uuid` | không |  | FK→`raw_scopus_records.id`, UQ | Dòng thô nguồn (duy nhất). |
| 4 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_publication_raw_sources_raw_record_id` (raw_record_id)

**Chỉ mục:** `ix_publication_raw_sources_publication_id` (publication_id)

### scopus_authors

**Tác giả Scopus.** Một tác giả theo Scopus Author ID (duy nhất). Là thực thể trung tâm cho đối sánh; chưa gắn với giảng viên cho đến khi một ứng viên được duyệt.

- Cụm: **D** · Số dòng demo: **1207** · UC liên quan: UC-12, 16, 24
- Khóa chính: `id`

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `scopus_id` | `text` | không |  | UQ; CHECK: `scopus_id_not_empty` | Scopus Author ID (duy nhất). |
| 3 | `preferred_name` | `varchar(255)` | không |  |  | Tên ưu tiên khi tạo tác giả (ưu tiên dạng tên đầy đủ hơn dạng hiển thị — `scopus_author_normalizer.py`). |
| 4 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |
| 5 | `updated_at` | `timestamptz` | không | `now()` |  | Thời điểm cập nhật gần nhất (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_scopus_authors_scopus_id` (scopus_id)

### scopus_author_name_variants

**Các dạng tên của tác giả Scopus.** Mọi dạng tên đã gặp của một tác giả (dạng hiển thị và dạng đầy đủ). Là các 'bề mặt' tên để so khớp với tên giảng viên khi sinh ứng viên.

- Cụm: **D** · Số dòng demo: **2768** · UC liên quan: UC-12, 24
- Khóa chính: `id`
- Khóa ngoại: `first_seen_raw_record_id` → `raw_scopus_records(id)` (ON DELETE RESTRICT); `scopus_author_id` → `scopus_authors(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `scopus_author_id` | `uuid` | không |  | FK→`scopus_authors.id`, UQ(scopus_author_id,variant_type,variant_name) | Tác giả. |
| 3 | `variant_type` | `varchar(30)` | không |  | UQ(scopus_author_id,variant_type,variant_name); CHECK: `variant_type` | AUTHOR_DISPLAY hoặc AUTHOR_FULL_NAME. |
| 4 | `variant_name` | `varchar(255)` | không |  | UQ(scopus_author_id,variant_type,variant_name) | Tên nguyên văn. |
| 5 | `variant_name_normalized` | `varchar(255)` | không |  |  | Tên chuẩn hóa. |
| 6 | `first_seen_raw_record_id` | `uuid` | không |  | FK→`raw_scopus_records.id` | Dòng thô nơi dạng tên này xuất hiện lần đầu (provenance). |
| 7 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_author_name_variants` (scopus_author_id, variant_type, variant_name)

**Chỉ mục:** `ix_author_name_variants_normalized` (variant_name_normalized); `ix_author_name_variants_raw_source` (first_seen_raw_record_id)

### publication_authors

**Vị trí tác giả trong công bố.** Quan hệ N–N giữa công bố và tác giả, có thuộc tính thứ tự tác giả. Mỗi (công bố, tác giả) một dòng và mỗi (công bố, thứ tự) một dòng. Là mốc để gắn đơn vị công tác theo từng tác giả trên từng bài.

- Cụm: **D** · Số dòng demo: **2751** · UC liên quan: UC-12, 13, 22
- Khóa chính: `id`
- Khóa ngoại: `publication_id` → `publications(id)` (ON DELETE CASCADE); `scopus_author_id` → `scopus_authors(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `publication_id` | `uuid` | không |  | FK→`publications.id`, UQ(publication_id,scopus_author_id), UQ(publication_id,author_order) | Công bố (xóa công bố sẽ xóa dây chuyền vị trí tác giả). |
| 3 | `scopus_author_id` | `uuid` | không |  | FK→`scopus_authors.id`, UQ(publication_id,scopus_author_id) | Tác giả. |
| 4 | `author_order` | `integer` | không |  | UQ(publication_id,author_order); CHECK: `author_order` | Thứ tự tác giả trong bài (>= 1). |
| 5 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_publication_authors_author` (publication_id, scopus_author_id); `uq_publication_authors_order` (publication_id, author_order)

**Chỉ mục:** `ix_publication_authors_scopus_author_id` (scopus_author_id)

## Cụm E — Đơn vị công tác theo tác giả (affiliation)

### organizations

**Tổ chức (theo nguồn ngoài).** Tổ chức do nguồn ngoài (OpenAlex/Crossref) cung cấp. Duy nhất theo (nguồn, mã tổ chức) hoặc (nguồn, tên) khi nguồn không có mã. Không chứa tổ chức do Scopus cung cấp.

- Cụm: **E** · Số dòng demo: **217** · UC liên quan: UC-13, 25
- Khóa chính: `id`

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK, UQ một phần | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `source_system` | `varchar(50)` | không |  | UQ một phần, UQ một phần; CHECK: `source_system` | Hệ nguồn ngoài (script nạp hỗ trợ `openalex`, `crossref`). |
| 3 | `source_org_id` | `text` | có |  | UQ một phần; CHECK: `source_org_id` | Mã tổ chức theo nguồn (có thể NULL). |
| 4 | `ror` | `text` | có |  |  | Mã ROR (nếu có). |
| 5 | `display_name` | `text` | không |  | UQ một phần; CHECK: `display_name` | Tên hiển thị. |
| 6 | `country_code` | `varchar(2)` | có |  | CHECK: `country_code` | Mã quốc gia ISO-2 (chữ in hoa). |
| 7 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_organizations_source_name` (source_system, display_name) WHERE (source_org_id IS NULL); `uq_organizations_source_org` (source_system, source_org_id) WHERE (source_org_id IS NOT NULL)

**Chỉ mục:** `ix_organizations_ror` (ror)

### publication_author_affiliation_resolutions

**Kết quả đối chiếu đơn vị theo (vị trí tác giả × nguồn).** Với mỗi vị trí tác giả trên một bài và mỗi nguồn ngoài, lưu độ tin cậy của việc gán tác giả nguồn ngoài cho vị trí Scopus: VERIFIED (qua chuỗi ORCID↔Scopus ID), CORROBORATED (cùng số tác giả/vị trí/tên) hoặc UNRESOLVED (kèm lý do). Mỗi nguồn có bản ghi riêng.

- Cụm: **E** · Số dòng demo: **5502** · UC liên quan: UC-13, 25
- Khóa chính: `id`
- Khóa ngoại: `publication_author_id` → `publication_authors(id)` (ON DELETE CASCADE)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK, UQ(id,link_status) | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `publication_author_id` | `uuid` | không |  | FK→`publication_authors.id`, UQ(publication_author_id,source_system,source_payload_sha256) | Vị trí tác giả được đối chiếu. |
| 3 | `source_system` | `varchar(50)` | không |  | UQ(publication_author_id,source_system,source_payload_sha256); CHECK: `source_system` | Nguồn ngoài (`openalex` hoặc `crossref` theo script nạp). |
| 4 | `source_payload_sha256` | `varchar(64)` | không |  | UQ(publication_author_id,source_system,source_payload_sha256); CHECK: `payload_hash` | SHA-256 payload nguồn (chống nạp trùng). |
| 5 | `link_status` | `varchar(20)` | không |  | UQ(id,link_status); CHECK: `link_method`, `link_status`, `presence`, `reason`, `retrieved_at`, `trusted_position`, `verified_orcid` | VERIFIED, CORROBORATED hoặc UNRESOLVED. |
| 6 | `link_method` | `varchar(40)` | có |  | CHECK: `link_method` | ORCID_SCOPUS_ID_BRIDGE (VERIFIED) hoặc POSITION_COUNT_NAME (CORROBORATED); NULL khi UNRESOLVED. |
| 7 | `unresolved_reason` | `varchar(80)` | có |  | CHECK: `reason` | Lý do khi UNRESOLVED (bắt buộc khi và chỉ khi UNRESOLVED). |
| 8 | `affiliation_presence` | `varchar(10)` | có |  | CHECK: `presence` | PRESENT/ABSENT: nguồn có/không liệt kê đơn vị (NULL khi UNRESOLVED). |
| 9 | `evidence` | `jsonb` | không | `'{}'::jsonb` | CHECK: `evidence_object` | Bằng chứng đối chiếu (JSON object). |
| 10 | `source_doi` | `text` | có |  |  | DOI theo nguồn ngoài. |
| 11 | `source_work_id` | `text` | có |  |  | Mã công trình trong nguồn ngoài. |
| 12 | `external_position` | `integer` | có |  | CHECK: `ext_position`, `trusted_position` | Vị trí tác giả trong nguồn ngoài (>= 1; bắt buộc khi không UNRESOLVED). |
| 13 | `external_author_name` | `text` | có |  |  | Tên tác giả theo nguồn ngoài. |
| 14 | `external_author_orcid` | `varchar(19)` | có |  | CHECK: `orcid_format`, `verified_orcid` | ORCID tác giả theo nguồn ngoài (bắt buộc khi VERIFIED). |
| 15 | `retrieved_at` | `timestamptz` | có |  | CHECK: `retrieved_at` | Thời điểm lấy dữ liệu nguồn ngoài (bắt buộc khi không UNRESOLVED). |
| 16 | `importer_version` | `varchar(40)` | không |  |  | Phiên bản trình nạp. |
| 17 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_paar_author_source_payload` (publication_author_id, source_system, source_payload_sha256); `uq_paar_id_link_status` (id, link_status)

**Chỉ mục:** `ix_paar_publication_author` (publication_author_id); `ix_paar_source_status` (source_system, link_status)

### publication_author_affiliations

**Dòng đơn vị gắn với một kết quả đối chiếu.** Các đơn vị (chuỗi gốc và/hoặc tổ chức chuẩn hóa) của một resolution đáng tin cậy. Chỉ tồn tại cho VERIFIED/CORROBORATED; link_status ở đây luôn bằng link_status của resolution nhờ FK ghép (resolution_id, link_status).

- Cụm: **E** · Số dòng demo: **4147** · UC liên quan: UC-13, 25
- Khóa chính: `id`
- Khóa ngoại: `organization_id` → `organizations(id)` (ON DELETE RESTRICT); `resolution_id,link_status` → `publication_author_affiliation_resolutions(id,link_status)` (ON DELETE CASCADE)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `resolution_id` | `uuid` | không |  | FK→`publication_author_affiliation_resolutions.id`, UQ(resolution_id,ord) | Resolution cha (xóa resolution sẽ xóa dây chuyền). |
| 3 | `link_status` | `varchar(20)` | không |  | FK→`publication_author_affiliation_resolutions.link_status`; CHECK: `link_status` | Bản sao link_status của resolution (VERIFIED/CORROBORATED), ép nhất quán bằng FK ghép. |
| 4 | `ord` | `integer` | không |  | UQ(resolution_id,ord); CHECK: `ord` | Thứ tự đơn vị (>= 1). |
| 5 | `raw_index` | `integer` | có |  | CHECK: `raw_text` | Chỉ số chuỗi đơn vị gốc trong nguồn (>= 1; NULL khi không có chuỗi gốc). |
| 6 | `raw_affiliation_text` | `text` | có |  | CHECK: `content`, `raw_text` | Chuỗi đơn vị nguyên văn của nhà xuất bản. |
| 7 | `organization_id` | `uuid` | có |  | FK→`organizations.id`; CHECK: `content` | Tổ chức chuẩn hóa (tùy chọn; phải có chuỗi gốc hoặc tổ chức). |
| 8 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_paa_resolution_ord` (resolution_id, ord)

**Chỉ mục:** `ix_paa_organization_id` (organization_id)

## Cụm F — Đối sánh, duyệt và danh tính

### candidate_generation_runs

**Lần chạy sinh ứng viên.** Một lần chạy bộ sinh ứng viên (CLI): bộ luật + phiên bản, ảnh chụp trạng thái nguồn, trạng thái chạy.

- Cụm: **F** · Số dòng demo: **2** · UC liên quan: UC-24
- Khóa chính: `id`

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `rule_set_id` | `text` | không |  | CHECK: `rule_set_id_not_empty` | Mã bộ luật. |
| 3 | `rule_set_version` | `text` | không |  | CHECK: `rule_set_version_not_empty` | Phiên bản bộ luật. |
| 4 | `source_state` | `jsonb` | không |  | CHECK: `source_state_object` | Ảnh chụp trạng thái dữ liệu đầu vào (JSON object). |
| 5 | `status` | `varchar(20)` | không | `'RUNNING'::character varying` | CHECK: `completion_consistency`, `status` | RUNNING, COMPLETED hoặc FAILED. |
| 6 | `started_at` | `timestamptz` | không | `now()` |  | Thời điểm bắt đầu. |
| 7 | `completed_at` | `timestamptz` | có |  | CHECK: `completion_consistency` | Thời điểm kết thúc (bắt buộc khi không còn RUNNING). |
| 8 | `version` | `integer` | không | `1` | CHECK: `version` | Số phiên bản dùng cho khóa lạc quan (optimistic locking); luôn >= 1. |
| 9 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |
| 10 | `updated_at` | `timestamptz` | không | `now()` |  | Thời điểm cập nhật gần nhất (timestamptz, mặc định now()). |

**Chỉ mục:** `ix_candidate_generation_runs_status_created` (status, created_at)

### lecturer_scopus_candidates

**Ứng viên đối sánh (giảng viên ↔ tác giả Scopus).** Đề xuất rằng một giảng viên có thể là một tác giả Scopus. Mỗi cặp (giảng viên, tác giả) một dòng. Đây là FACT truy xuất, KHÔNG phải quyết định danh tính; trạng thái đổi bởi người duyệt.

- Cụm: **F** · Số dòng demo: **40** · UC liên quan: UC-17, 18, 24
- Khóa chính: `id`
- Khóa ngoại: `lecturer_id` → `lecturers(id)` (ON DELETE RESTRICT); `scopus_author_id` → `scopus_authors(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `lecturer_id` | `uuid` | không |  | FK→`lecturers.id`, UQ(lecturer_id,scopus_author_id) | Giảng viên. |
| 3 | `scopus_author_id` | `uuid` | không |  | FK→`scopus_authors.id`, UQ(lecturer_id,scopus_author_id) | Tác giả Scopus. |
| 4 | `status` | `varchar(20)` | không | `'PENDING'::character varying` | CHECK: `status` | PENDING, ACCEPTED, REJECTED hoặc SUPERSEDED. |
| 5 | `first_seen_at` | `timestamptz` | không | `now()` |  | Lần đầu bộ sinh thấy cặp này. |
| 6 | `last_seen_at` | `timestamptz` | không | `now()` |  | Lần gần nhất bộ sinh thấy cặp này. |
| 7 | `version` | `integer` | không | `1` | CHECK: `version` | Số phiên bản dùng cho khóa lạc quan (optimistic locking); luôn >= 1. |
| 8 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |
| 9 | `updated_at` | `timestamptz` | không | `now()` |  | Thời điểm cập nhật gần nhất (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_lecturer_scopus_candidates_pair` (lecturer_id, scopus_author_id)

**Chỉ mục:** `ix_lecturer_scopus_candidates_lecturer` (lecturer_id); `ix_lecturer_scopus_candidates_scopus_author` (scopus_author_id); `ix_lecturer_scopus_candidates_status_updated` (status, updated_at)

### lecturer_scopus_candidate_observations

**Lần quan sát ứng viên trong một lần chạy.** Ảnh chụp trạng thái của một ứng viên tại một lần chạy (candidate_snapshot + hash). Duyệt luôn gắn với quan sát hiện hành để phát hiện dữ liệu đã cũ.

- Cụm: **F** · Số dòng demo: **80** · UC liên quan: UC-17, 18, 24
- Khóa chính: `id`
- Khóa ngoại: `candidate_id` → `lecturer_scopus_candidates(id)` (ON DELETE RESTRICT); `generation_run_id` → `candidate_generation_runs(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `candidate_id` | `uuid` | không |  | FK→`lecturer_scopus_candidates.id`, UQ(candidate_id,generation_run_id) | Ứng viên. |
| 3 | `generation_run_id` | `uuid` | không |  | FK→`candidate_generation_runs.id`, UQ(candidate_id,generation_run_id) | Lần chạy sinh ứng viên. |
| 4 | `observed_at` | `timestamptz` | không |  |  | Thời điểm quan sát. |
| 5 | `candidate_snapshot` | `jsonb` | không |  | CHECK: `candidate_sna_25cc` | Ảnh chụp ứng viên (JSON object). |
| 6 | `observation_hash` | `varchar(64)` | không |  | CHECK: `observation_hash` | SHA-256 của quan sát. |
| 7 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_candidate_observations_candidate_run` (candidate_id, generation_run_id)

**Chỉ mục:** `ix_candidate_observations_candidate` (candidate_id, created_at); `ix_candidate_observations_run` (generation_run_id)

### lecturer_scopus_candidate_evidence

**Bằng chứng của quan sát ứng viên.** Bằng chứng giải thích vì sao một cặp được đề xuất: NAME (so khớp tên theo luật) hoặc PUBLICATION (công bố đã biết trùng DOI/tiêu đề). Không có điểm số.

- Cụm: **F** · Số dòng demo: **203** · UC liên quan: UC-17, 24
- Khóa chính: `id`
- Khóa ngoại: `observation_id` → `lecturer_scopus_candidate_observations(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `observation_id` | `uuid` | không |  | FK→`lecturer_scopus_candidate_observations.id`, UQ(observation_id,rule_id,rule_version,evidence_fingerprint) | Quan sát chứa bằng chứng. |
| 3 | `evidence_kind` | `varchar(30)` | không |  | CHECK: `evidence_kind` | NAME hoặc PUBLICATION. |
| 4 | `rule_id` | `text` | không |  | UQ(observation_id,rule_id,rule_version,evidence_fingerprint); CHECK: `rule_id_not_empty` | Mã luật sinh bằng chứng. |
| 5 | `rule_version` | `text` | không |  | UQ(observation_id,rule_id,rule_version,evidence_fingerprint); CHECK: `rule_version_not_empty` | Phiên bản luật. |
| 6 | `payload` | `jsonb` | không |  | CHECK: `payload_object` | Chi tiết bằng chứng (JSON object). |
| 7 | `source_refs` | `jsonb` | không |  | CHECK: `source_refs_array` | Tham chiếu nguồn (JSON array). |
| 8 | `evidence_fingerprint` | `varchar(64)` | không |  | UQ(observation_id,rule_id,rule_version,evidence_fingerprint); CHECK: `evidence_fingerprint` | Dấu vân tay SHA-256 (chống trùng). |
| 9 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_candidate_evidence_descriptor` (observation_id, rule_id, rule_version, evidence_fingerprint)

**Chỉ mục:** `ix_candidate_evidence_observation` (observation_id, created_at)

### lecturer_scopus_candidate_reviews

**Quyết định duyệt ứng viên.** Mỗi lần người có quyền ACCEPT/REJECT một ứng viên (REOPEN có trong CHECK nhưng chưa có API). Lưu trạng thái trước/sau, phiên bản ứng viên, lý do (bắt buộc với REJECT/REOPEN), ảnh chụp bằng chứng và danh tính được tạo (nếu ACCEPT).

- Cụm: **F** · Số dòng demo: **0** · UC liên quan: UC-18, 19
- Khóa chính: `id`
- Khóa ngoại: `candidate_id` → `lecturer_scopus_candidates(id)` (ON DELETE RESTRICT); `observation_id` → `lecturer_scopus_candidate_observations(id)` (ON DELETE RESTRICT); `resulting_identity_id` → `lecturer_scopus_identities(id)` (ON DELETE RESTRICT); `reviewer_user_id` → `users(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `candidate_id` | `uuid` | không |  | FK→`lecturer_scopus_candidates.id` | Ứng viên được duyệt. |
| 3 | `observation_id` | `uuid` | không |  | FK→`lecturer_scopus_candidate_observations.id` | Quan sát hiện hành tại thời điểm duyệt. |
| 4 | `reviewer_user_id` | `uuid` | không |  | FK→`users.id` | Người duyệt (FK → users). |
| 5 | `action` | `varchar(20)` | không |  | CHECK: `action`, `reason_required`, `transitions` | ACCEPT, REJECT hoặc REOPEN. |
| 6 | `from_status` | `varchar(20)` | không |  | CHECK: `from_status`, `transitions` | Trạng thái ứng viên trước khi duyệt. |
| 7 | `to_status` | `varchar(20)` | không |  | CHECK: `to_status`, `transitions` | Trạng thái ứng viên sau khi duyệt. |
| 8 | `candidate_version` | `integer` | không |  | CHECK: `candidate_version` | Phiên bản ứng viên lúc duyệt (phát hiện duyệt trên dữ liệu cũ). |
| 9 | `reason` | `text` | có |  | CHECK: `reason_required` | Lý do (bắt buộc khi không phải ACCEPT). |
| 10 | `evidence_snapshot` | `jsonb` | không |  | CHECK: `evidence_snapshot_object` | Ảnh chụp bằng chứng người duyệt đã xem (JSON object). |
| 11 | `resulting_identity_id` | `uuid` | có |  | FK→`lecturer_scopus_identities.id` | Danh tính APPROVED được tạo khi ACCEPT (NULL nếu REJECT). |
| 12 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Chỉ mục:** `ix_candidate_reviews_candidate_created` (candidate_id, created_at); `ix_candidate_reviews_observation` (observation_id); `ix_candidate_reviews_reviewer` (reviewer_user_id)

### lecturer_scopus_identities

**Danh tính giảng viên ↔ tác giả Scopus.** Liên kết đã chốt. Một Scopus Author ID chỉ được APPROVED cho đúng một giảng viên (chỉ mục unique một phần). Hiện chỉ đường ACCEPT tạo APPROVED; REVOKE/REOPEN/recommendation chưa có mã ghi.

- Cụm: **F** · Số dòng demo: **0** · UC liên quan: UC-18, 20–23
- Khóa chính: `id`
- Khóa ngoại: `lecturer_id` → `lecturers(id)` (ON DELETE RESTRICT); `scopus_author_id` → `scopus_authors(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK, UQ một phần | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `lecturer_id` | `uuid` | không |  | FK→`lecturers.id`, UQ(lecturer_id,scopus_author_id) | Giảng viên. |
| 3 | `scopus_author_id` | `uuid` | không |  | FK→`scopus_authors.id`, UQ(lecturer_id,scopus_author_id), UQ một phần | Tác giả Scopus. |
| 4 | `status` | `varchar(20)` | không | `'CANDIDATE'::character varying` | CHECK: `status` | CANDIDATE, APPROVED, REJECTED hoặc REVOKED. |
| 5 | `recommendation` | `varchar(30)` | có |  | CHECK: `recommendation`, `recommendation_consistency` | MATCH/NO_MATCH/MANUAL_VERIFY (chưa có mã ghi cột này). |
| 6 | `recommendation_algorithm_version` | `varchar(100)` | có |  | CHECK: `recommendation_consistency` | Phiên bản thuật toán khuyến nghị (đi cùng recommendation). |
| 7 | `recommended_at` | `timestamptz` | có |  | CHECK: `recommendation_consistency` | Thời điểm khuyến nghị (đi cùng recommendation). |
| 8 | `version` | `integer` | không | `1` | CHECK: `version` | Số phiên bản dùng cho khóa lạc quan (optimistic locking); luôn >= 1. |
| 9 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |
| 10 | `updated_at` | `timestamptz` | không | `now()` |  | Thời điểm cập nhật gần nhất (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_lecturer_scopus_identities_pair` (lecturer_id, scopus_author_id); `uq_identities_scopus_author_approved` (scopus_author_id) WHERE ((status)::text = 'APPROVED'::text)

**Chỉ mục:** `ix_identities_scopus_author_id` (scopus_author_id); `ix_identities_status_updated` (status, updated_at)

### identity_evidence

**Bằng chứng gắn với danh tính.** Bằng chứng được sao từ ứng viên sang danh tính khi ACCEPT (NAME → NAME_SIMILARITY; PUBLICATION → DOI_EXACT/PUBLICATION_OVERLAP). CHECK cho phép thêm APPROVED_ID, ORCID_EXACT, COAUTHOR_CONFIRMED, AFFILIATION_MATCH nhưng chưa có mã tạo các loại này.

- Cụm: **F** · Số dòng demo: **0** · UC liên quan: UC-18
- Khóa chính: `id`
- Khóa ngoại: `identity_id` → `lecturer_scopus_identities(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `identity_id` | `uuid` | không |  | FK→`lecturer_scopus_identities.id`, UQ(identity_id,evidence_type,algorithm_version,evidence_fingerprint) | Danh tính. |
| 3 | `evidence_type` | `varchar(40)` | không |  | UQ(identity_id,evidence_type,algorithm_version,evidence_fingerprint); CHECK: `evidence_type` | APPROVED_ID, ORCID_EXACT, DOI_EXACT, PUBLICATION_OVERLAP, COAUTHOR_CONFIRMED, NAME_SIMILARITY, AFFILIATION_MATCH. |
| 4 | `direction` | `varchar(20)` | không |  | CHECK: `direction` | SUPPORTS hoặc CONTRADICTS. |
| 5 | `confidence_score` | `numeric(5,4)` | có |  | CHECK: `confidence_score` | Điểm tin cậy 0–1; luôn NULL hiện nay (không có điểm do máy tính). |
| 6 | `algorithm_version` | `varchar(100)` | không |  | UQ(identity_id,evidence_type,algorithm_version,evidence_fingerprint) | Phiên bản thuật toán/luật. |
| 7 | `features` | `jsonb` | không |  | CHECK: `features_object` | Đặc trưng bằng chứng (JSON object). |
| 8 | `source_refs` | `jsonb` | không |  | CHECK: `source_refs_array` | Tham chiếu nguồn (JSON array). |
| 9 | `evidence_fingerprint` | `varchar(64)` | không |  | UQ(identity_id,evidence_type,algorithm_version,evidence_fingerprint); CHECK: `fingerprint` | Dấu vân tay SHA-256 (chống trùng). |
| 10 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Ràng buộc duy nhất:** `uq_identity_evidence_dedup` (identity_id, evidence_type, algorithm_version, evidence_fingerprint)

**Chỉ mục:** `ix_identity_evidence_created_at` (created_at)

### mapping_reviews

**Lịch sử đổi trạng thái danh tính (dự phòng).** Thiết kế dự phòng cho APPROVE/REJECT/REVOKE/REOPEN ở cấp danh tính, có bù trừ (compensates_review_id). HIỆN CHƯA CÓ MÃ GHI và 0 dòng; không phải chức năng hoàn tác đã triển khai.

- Cụm: **F** · Số dòng demo: **0** · UC liên quan: (chưa dùng)
- Khóa chính: `id`
- Khóa ngoại: `compensates_review_id` → `mapping_reviews(id)` (ON DELETE RESTRICT); `identity_id` → `lecturer_scopus_identities(id)` (ON DELETE RESTRICT); `reviewer_user_id` → `users(id)` (ON DELETE RESTRICT)

| # | Cột | Kiểu | NULL | Mặc định | Khóa / ràng buộc | Mô tả |
|--:|---|---|:-:|---|---|---|
| 1 | `id` | `uuid` | không | `gen_random_uuid()` | PK | Khóa chính (UUID sinh bởi gen_random_uuid()). |
| 2 | `identity_id` | `uuid` | không |  | FK→`lecturer_scopus_identities.id` | Danh tính. |
| 3 | `reviewer_user_id` | `uuid` | không |  | FK→`users.id` | Người duyệt. |
| 4 | `action` | `varchar(20)` | không |  | CHECK: `action`, `compensates`, `reason_required`, `transitions` | APPROVE, REJECT, REVOKE hoặc REOPEN. |
| 5 | `from_status` | `varchar(20)` | không |  | CHECK: `transitions` | Trạng thái trước. |
| 6 | `to_status` | `varchar(20)` | không |  | CHECK: `transitions` | Trạng thái sau. |
| 7 | `reason` | `text` | có |  | CHECK: `reason_required` | Lý do (bắt buộc khi không phải APPROVE). |
| 8 | `evidence_snapshot` | `jsonb` | không |  | CHECK: `evidence_snapshot_object` | Ảnh chụp bằng chứng (JSON object). |
| 9 | `compensates_review_id` | `uuid` | có |  | FK→`mapping_reviews.id`; CHECK: `compensates` | Quyết định được bù trừ (bắt buộc với REVOKE/REOPEN, cấm với APPROVE/REJECT). |
| 10 | `created_at` | `timestamptz` | không | `now()` |  | Thời điểm tạo bản ghi (timestamptz, mặc định now()). |

**Chỉ mục:** `ix_mapping_reviews_compensates` (compensates_review_id) WHERE (compensates_review_id IS NOT NULL); `ix_mapping_reviews_identity_id` (identity_id); `ix_mapping_reviews_reviewer` (reviewer_user_id)

