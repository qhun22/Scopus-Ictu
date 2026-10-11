# Đặc tả Use Case — Nhóm 2: Quản lý hồ sơ tác giả/giảng viên

> Khớp "UC chính (b) Quản lý hồ sơ tác giả" của đề cương. Sơ đồ: `diagrams/UCD-2_quan_ly_ho_so`. "Hồ sơ tác giả" trong phần mềm gồm **hồ sơ giảng viên** (`lecturers`), **tài khoản** (`users`) và **tác giả Scopus** (`scopus_authors`); liên kết giữa giảng viên và tác giả Scopus nằm ở nhóm 4 (UC-18). Đối chiếu mã: `lecturers.py`, `users.py`, `user_admin_service.py`, `authors.py`, `lecturer_scopus.py`.

---

## UC-05 — Quản lý hồ sơ giảng viên

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-05 |
| **Mục tiêu** | Xem, tìm, thêm, sửa, xóa hồ sơ giảng viên (dữ liệu chủ) và dọn hồ sơ mồ côi, với khóa lạc quan và chặn trùng |
| **Actor chính / phụ** | Chính: **ADMIN**. Phụ: Hệ thống |
| **Điều kiện trước** | Đăng nhập ADMIN; hồ sơ cần sửa/xóa tồn tại |
| **Luồng chính** | 1. ADMIN vào **Giảng viên** (`/lecturers`): danh sách phân trang phía máy chủ, tìm kiếm (không phân biệt dấu), thống kê và cảnh báo (vd. email dùng cho nhiều hồ sơ).<br>2. **Thêm giảng viên** (`POST /lecturers`): nhập họ tên, email, mật khẩu (≥ 8 ký tự), vai trò, mã cán bộ (tùy chọn)… → tạo **hồ sơ giảng viên và tài khoản đăng nhập** cùng lúc; ghi audit `LECTURER_CREATED`.<br>3. **Sửa** (`PATCH/PUT /lecturers/{id}` kèm `version`): đổi thông tin hồ sơ; ghi audit `LECTURER_UPDATED`.<br>4. **Xóa** (`DELETE /lecturers/{id}`): xóa hồ sơ chưa được dùng; ghi audit `LECTURER_DELETED`.<br>5. **Dọn hồ sơ mồ côi** (`DELETE /lecturers/unlinked/cleanup`): xóa hồ sơ không còn tài khoản đang hoạt động gắn vào |
| **Luồng thay thế** | A1. Sửa hồ sơ chưa có tài khoản và bật `grant_account` để cấp tài khoản.<br>A2. Xem chi tiết hồ sơ trong cửa sổ "Chi tiết" (tiếp tục sang UC-06) |
| **Luồng lỗi** | E1. Tên/email trống hoặc mật khẩu < 8 ký tự → 422.<br>E2. Email đã dùng cho tài khoản → 409 (`EMAIL_ALREADY_EXISTS`).<br>E3. Mã cán bộ trùng → 409 `STAFF_CODE_ALREADY_EXISTS`.<br>E4. Sửa trên phiên bản cũ → 409 `VERSION_CONFLICT`.<br>E5. Xóa hồ sơ đang được dùng (tài khoản, danh tính, công bố đã biết…) → 409 `LECTURER_IN_USE`.<br>E6. Không tìm thấy → 404.<br>E7. Không phải ADMIN → 403; lỗi DB → 503 |
| **Điều kiện sau** | Hồ sơ phản ánh thay đổi, `version` tăng; mọi thao tác ghi có audit |
| **Dữ liệu thay đổi** | `lecturers`, `users` (khi tạo/cấp tài khoản), `audit_events` |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | `GET /api/v1/lecturers`, `GET /lecturers/master`, `POST /lecturers`, `PATCH|PUT|DELETE /lecturers/{id}`, `DELETE /lecturers/unlinked/cleanup`; UI `/lecturers` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Giới hạn: Khoa/Bộ môn phần lớn trống trong dữ liệu nguồn; `updated_at` không đổi khi sửa (L8, báo cáo Task 17) |
| **Test case tương ứng** | `unit/test_lecturer_account_update_conflicts`; `test_lecturer_staff_code_contract`; `test_lecturer_list_and_history`; `test_lecturer_import_api::test_list_master_requires_admin`, `test_list_master_returns_pagination_envelope`; `unit/test_lecturer_warning_detection`; `test_account_admin_and_notifications::test_30_optimistic_version_conflict`. E2E: §6.3 (ảnh 04–06) |

---

## UC-06 — Quản lý tài khoản và phân quyền

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-06 |
| **Mục tiêu** | Quản trị vòng đời tài khoản: sửa hồ sơ tài khoản, đổi vai trò (ADMIN/REVIEWER/LECTURER), khóa/mở khóa, đặt lại mật khẩu; thông báo cho người bị tác động |
| **Actor chính / phụ** | Chính: **ADMIN**. Phụ: người dùng bị tác động (nhận thông báo, bị thu hồi phiên) |
| **Điều kiện trước** | Đăng nhập ADMIN; tài khoản mục tiêu tồn tại |
| **Luồng chính** | 1. ADMIN mở **Chi tiết** giảng viên (cửa sổ có phần tài khoản liên kết).<br>2. Chọn: **lưu thay đổi hồ sơ/vai trò** (`PATCH /users/{id}`, kèm `version`), **khóa** (`POST /users/{id}/lock`), **mở khóa** (`/unlock`), **đặt lại mật khẩu** (`/reset-password`).<br>3. Hệ thống áp dụng, tăng `auth_version` khi cần để **thu hồi phiên cũ**, tạo thông báo (`user_notifications`: PROFILE_UPDATED, ROLE_CHANGED, ACCOUNT_LOCKED/UNLOCKED, PASSWORD_RESET) và ghi audit (`USER_UPDATED`, `USER_LOCKED`, `USER_UNLOCKED`, `USER_PASSWORD_RESET`) |
| **Luồng thay thế** | A1. Danh sách/chi tiết tài khoản (`GET /users`, `GET /users/{id}`); `GET /auth/users` là bí danh cũ (deprecated).<br>A2. Nhập mật khẩu mới ngay trong cửa sổ Chi tiết khi cấp tài khoản |
| **Luồng lỗi** | E1. ADMIN **tự đổi vai trò của mình** hoặc **tự khóa mình** → bị từ chối (409).<br>E2. **Hạ/khóa ADMIN hoạt động cuối cùng** → 409 `LAST_ADMIN_PROTECTED`.<br>E3. Phiên bản cũ → 409 `VERSION_CONFLICT`; dữ liệu xung đột → 409 `USER_DATA_CONFLICT`/`EMAIL_ALREADY_EXISTS`.<br>E4. Dữ liệu cập nhật không hợp lệ → 422 `INVALID_USER_UPDATE`; vai trò LECTURER thiếu hồ sơ → 422 `LECTURER_PROFILE_REQUIRED`.<br>E5. Không tìm thấy → 404 `USER_NOT_FOUND`.<br>E6. Không phải ADMIN → 403 |
| **Điều kiện sau** | Tài khoản bị khóa không đăng nhập được (403 `ACCOUNT_LOCKED`); sau đặt lại mật khẩu, phiên cũ bị từ chối (`SESSION_REVOKED`) và đăng nhập bằng mật khẩu cũ trả `PASSWORD_RESET_BY_ADMIN` |
| **Dữ liệu thay đổi** | `users`, `user_notifications`, `audit_events` |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | `GET/PATCH /api/v1/users[/{id}]`, `POST /users/{id}/lock|unlock|reset-password`; UI `/lecturers` (cửa sổ Chi tiết); `/users` chuyển hướng sang `/lecturers` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Không có màn hình "Người dùng" riêng; teacher DB chưa có tài khoản REVIEWER (chỉ DB kiểm thử) |
| **Test case tương ứng** | `test_account_admin_and_notifications` (24 ca): `test_04_05_06_07_admin_lock_lecturer`, `test_08_locked_lecturer_cannot_login`, `test_09_non_admin_cannot_lock`, `test_10_admin_cannot_lock_self`, `test_11_12_13_14_admin_unlock_lecturer`, `test_15_16_17_18_19_20_password_reset_mutation`, `test_21_old_session_rejected_after_reset`, `test_28_admin_update_creates_notification_and_audit`, `test_29_role_update_creates_role_changed_notification`, `test_32_admin_cannot_change_own_role`, `test_33_last_active_admin_cannot_be_demoted`, `test_34_admin_can_demote_another_admin_when_one_remains`. E2E: §18 (Task 17, ba vai trò) |

---

## UC-16 — Xem tác giả Scopus

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-16 |
| **Mục tiêu** | Xem tác giả Scopus đã bóc tách: danh sách, thống kê, chi tiết (dạng tên, công bố) |
| **Actor chính / phụ** | Chính: **ADMIN** |
| **Điều kiện trước** | Đăng nhập ADMIN; đã bóc tách tác giả (UC-12) |
| **Luồng chính** | 1. ADMIN vào **Chuẩn hóa dữ liệu** → tab **Tác giả** (`/normalization`).<br>2. Hệ thống tải danh sách (`GET /authors`) và thẻ thống kê (`GET /authors/stats`).<br>3. (API) xem chi tiết một tác giả (`GET /authors/{id}`) |
| **Luồng thay thế** | A1. Lọc/phân trang danh sách |
| **Luồng lỗi** | E1. Không tìm thấy tác giả → 404.<br>E2. Không phải ADMIN → 403 |
| **Điều kiện sau** | Chỉ đọc; không dữ liệu nào đổi |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | `GET /api/v1/authors`, `/authors/stats`, `/authors/{author_id}`; UI tab "Tác giả" |
| **Trạng thái triển khai** | **MỘT PHẦN**: giao diện chưa có nút mở chi tiết tác giả (chi tiết chỉ qua API) |
| **Test case tương ứng** | `unit/test_author_routes_contract`; `test_scopus_author_normalization`. E2E: `openapi_coverage_matrix` (BROWSER_PASS danh sách/thống kê; API_PASS chi tiết) |

---

## UC-20 — Xem hồ sơ cá nhân (giảng viên)

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-20 |
| **Mục tiêu** | Giảng viên xem hồ sơ của chính mình |
| **Actor chính / phụ** | Chính: **LECTURER** |
| **Điều kiện trước** | Đăng nhập bằng tài khoản LECTURER đã gắn hồ sơ giảng viên (ràng buộc CHECK `ck_users_lecturer_account_required`) |
| **Luồng chính** | 1. Giảng viên vào **Hồ sơ** (`/profile`).<br>2. Hệ thống trả hồ sơ của chính người đó (`GET /lecturers/me/profile`) |
| **Luồng thay thế** | — |
| **Luồng lỗi** | E1. Chưa đăng nhập → 401.<br>E2. ADMIN/REVIEWER gọi → 403.<br>E3. Tài khoản chưa gắn hồ sơ → lỗi rõ ràng |
| **Điều kiện sau** | Chỉ đọc |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | LECTURER (chỉ dữ liệu của mình) |
| **API / UI thực tế** | `GET /api/v1/lecturers/me/profile`; UI `/profile` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**; chỉ xem, không sửa |
| **Test case tương ứng** | `test_lecturer_scopus_api::test_a2_t01_unauthenticated_me_profile`, `test_a2_t02_lecturer_own_profile`, `test_a2_t03_lecturer_not_linked`, `test_a2_t08_reviewer_me_denied`, `test_a2_t09_admin_me_denied`, `test_a2_t21_no_cross_lecturer_leak` |

---

## UC-21 — Xem liên kết Scopus đã được duyệt của tôi

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-21 |
| **Mục tiêu** | Giảng viên xem các tác giả Scopus đã được người có quyền **duyệt (APPROVED)** là của mình |
| **Actor chính / phụ** | Chính: **LECTURER** |
| **Điều kiện trước** | Đăng nhập LECTURER; để có dữ liệu, ít nhất một ứng viên đã được ACCEPT (UC-18) |
| **Luồng chính** | 1. Giảng viên vào **Liên kết Scopus** (`/identity`).<br>2. Hệ thống trả danh sách danh tính APPROVED của giảng viên (`GET /lecturers/me/identities`) |
| **Luồng thay thế** | A1. Chưa có danh tính → trạng thái rỗng (không phải lỗi) |
| **Luồng lỗi** | Như UC-20 (401/403) |
| **Điều kiện sau** | Chỉ đọc |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | LECTURER (chỉ dữ liệu của mình) |
| **API / UI thực tế** | `GET /api/v1/lecturers/me/identities`; UI `/identity`; dịch vụ `lecturer_scopus_projection.py` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Teacher DB: 0 danh tính APPROVED nên màn trống; minh chứng có dữ liệu chỉ từ DB kiểm thử (ảnh 23 Task 16) |
| **Test case tương ứng** | `test_lecturer_scopus_api::test_a2_t04_lecturer_own_identities`, `test_a2_t06_empty_identity_state`, `test_a2_t20_safe_identity_serialization`; `test_lecturer_scopus_projection` |

---

## UC-23 — Quản trị xem hồ sơ/danh tính/công bố Scopus của một giảng viên

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-23 |
| **Mục tiêu** | Cho quản trị đọc cùng dữ liệu mà giảng viên thấy (hồ sơ, danh tính APPROVED, công bố) của một giảng viên bất kỳ |
| **Actor chính / phụ** | Chính: **ADMIN** |
| **Điều kiện trước** | Đăng nhập ADMIN; có mã giảng viên |
| **Luồng chính** | 1. Gọi `GET /lecturers/{id}/scopus/profile`, `/identities`, `/publications`.<br>2. Hệ thống trả dữ liệu chỉ đọc |
| **Luồng thay thế** | A1. Phân trang/lọc công bố |
| **Luồng lỗi** | E1. Không tìm thấy giảng viên → 404.<br>E2. Tham số phân trang sai → 422.<br>E3. Không phải ADMIN → 403 |
| **Điều kiện sau** | Chỉ đọc |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | Ba API trên; **chưa có giao diện** |
| **Trạng thái triển khai** | **CHỈ API** (GAP-15) |
| **Test case tương ứng** | `test_lecturer_scopus_api::test_a2_t10_admin_target_profile`, `test_a2_t11_admin_target_identities`, `test_a2_t12_admin_target_publications`, `test_a2_t13_admin_target_not_found`, `test_a2_target_routes_denied_to_non_admin`, `test_a2_t22_read_only_http` |
