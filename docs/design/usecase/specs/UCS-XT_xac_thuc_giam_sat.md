# Đặc tả Use Case — Xác thực, thông báo, giám sát và khởi tạo (nhóm hỗ trợ)

> Nhóm hỗ trợ cho cả năm nhóm nghiệp vụ. Sơ đồ: `diagrams/UCD-6_xac_thuc_giam_sat`. Mọi UC cần đăng nhập đều dựa trên UC-01; **không vẽ «include» UC-01 vào từng UC** để tránh rối (ghi chú chung trong sơ đồ). Đối chiếu mã: `auth.py`, `dependencies.py`, `core/security.py`, `notifications.py`, `audits.py`, `bootstrap_demo_admin.py`.

---

## UC-01 — Đăng nhập

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-01 |
| **Mục tiêu** | Xác thực người dùng và mở phiên làm việc theo vai trò |
| **Actor chính / phụ** | Chính: **ADMIN, REVIEWER, LECTURER**. Phụ: Hệ thống |
| **Điều kiện trước** | Có tài khoản (email + mật khẩu) do ADMIN cấp; tài khoản không bị khóa |
| **Luồng chính** | 1. Người dùng mở `/login`, nhập email và mật khẩu.<br>2. Hệ thống (`POST /auth/login`) tra email (không phân biệt hoa/thường), kiểm mật khẩu bằng Argon2id.<br>3. Đúng → tạo JWT đặt trong cookie `httponly` (`samesite=lax`; `secure` khi môi trường prod), trả thông tin người dùng.<br>4. Giao diện chuyển tới `/home`; menu hiển thị theo vai trò |
| **Luồng thay thế** | A1. Người dùng đã có phiên hợp lệ: mở thẳng `/home`.<br>A2. Phiên sắp hết hạn: được gia hạn khi hoạt động |
| **Luồng lỗi** | E1. Email không tồn tại hoặc sai mật khẩu → 401 `INVALID_CREDENTIALS` (cùng thông điệp, không lộ email nào tồn tại).<br>E2. Tài khoản bị khóa → 403 `ACCOUNT_LOCKED`.<br>E3. Mật khẩu vừa bị quản trị đặt lại, người dùng dùng mật khẩu cũ → 401 `PASSWORD_RESET_BY_ADMIN`.<br>E4. Lỗi DB → 503 |
| **Điều kiện sau** | Thành công: cookie phiên được đặt; vai trò quyết định route/API truy cập được (FR-003). Lỗi: không có phiên |
| **Dữ liệu thay đổi** | Không ghi dữ liệu nghiệp vụ; **không ghi audit đăng nhập** (GAP-16) |
| **Quyền truy cập** | Công khai (trước khi đăng nhập) |
| **API / UI thực tế** | `POST /api/v1/auth/login`; UI `/login` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Giới hạn: chưa có giới hạn số lần thử sai; cookie `secure=false` trên localhost |
| **Test case tương ứng** | `test_auth_flow`: `test_login_success_admin`, `test_login_success_lecturer`, `test_login_unknown_email`, `test_login_wrong_password`, `test_login_inactive_user`; `test_account_admin_and_notifications::test_01_normal_correct_login`, `test_02_normal_wrong_password`, `test_03_locked_login`, `test_22_offline_user_old_password_returns_password_reset_by_admin`, `test_23_offline_user_new_password_succeeds`; `unit/test_security`. E2E: ảnh 01–03 (Task 16) |

---

## UC-02 — Đăng xuất và kiểm tra phiên

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-02 |
| **Mục tiêu** | Kết thúc phiên; mọi trang kiểm tra phiên còn hiệu lực |
| **Actor chính / phụ** | Chính: **ADMIN, REVIEWER, LECTURER** |
| **Điều kiện trước** | Có phiên (đăng xuất) hoặc mở bất kỳ trang đã đăng nhập (kiểm tra phiên) |
| **Luồng chính** | 1. Mỗi lần tải ứng dụng, giao diện gọi `GET /auth/me`; hợp lệ → hiển thị trang theo vai trò.<br>2. Người dùng chọn **Đăng xuất** trong menu người dùng ở Header → `POST /auth/logout` xóa cookie → về `/login` |
| **Luồng thay thế** | A1. Phiên sắp hết hạn: gia hạn |
| **Luồng lỗi** | E1. Phiên hết hạn/không hợp lệ → 401, về `/login`.<br>E2. Phiên bị thu hồi (sau khóa/đặt lại mật khẩu/đổi vai trò, `auth_version` đổi) → 401 `SESSION_REVOKED` |
| **Điều kiện sau** | Sau đăng xuất không còn cookie phiên |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | `logout`: không yêu cầu xác thực; `me`: yêu cầu đăng nhập |
| **API / UI thực tế** | `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`; Header (menu người dùng) |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)** |
| **Test case tương ứng** | `test_auth_flow::test_me_and_logout_flow`; `test_account_admin_and_notifications::test_21_old_session_rejected_after_reset`, `test_active_session_is_renewed_near_expiration` |

---

## UC-03 — Nhận thông báo tài khoản

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-03 |
| **Mục tiêu** | Người dùng biết khi quản trị tác động lên tài khoản của mình |
| **Actor chính / phụ** | Chính: **ADMIN, REVIEWER, LECTURER** (người nhận). Phụ: ADMIN (nguồn sự kiện, qua UC-06) |
| **Điều kiện trước** | Có thông báo chưa đọc do UC-06 sinh ra (cập nhật hồ sơ, đổi vai trò, khóa/mở khóa, đặt lại mật khẩu) |
| **Luồng chính** | 1. Khi tải trang, giao diện (`NotificationProvider`) lấy thông báo chưa đọc (`GET /notifications/unread`).<br>2. Hiển thị cho người dùng.<br>3. Đánh dấu đã đọc (`POST /notifications/{id}/read`) → ghi `read_at` |
| **Luồng thay thế** | A1. Không có thông báo → không hiển thị gì |
| **Luồng lỗi** | E1. Đọc thông báo của người khác → 404 (cô lập theo người dùng, không lộ sự tồn tại).<br>E2. Chưa đăng nhập → 401 |
| **Điều kiện sau** | Thông báo đã đọc không còn trong danh sách chưa đọc |
| **Dữ liệu thay đổi** | `user_notifications` (`is_read`, `read_at`) |
| **Quyền truy cập** | Mọi người dùng đã đăng nhập (chỉ thông báo của mình) |
| **API / UI thực tế** | `GET /api/v1/notifications/unread`, `POST /api/v1/notifications/{id}/read`; `frontend/src/contexts/NotificationContext.tsx` |
| **Trạng thái triển khai** | **MỘT PHẦN**: cơ chế nền; **không có trang/chuông Thông báo** |
| **Test case tương ứng** | `test_account_admin_and_notifications::test_24_27_unread_notifications_isolation`, `test_25_other_user_cannot_read_notification`, `test_26_mark_read_sets_read_fields`, `test_31_lock_unlock_supersedes_stale_lock_notification` |

---

## UC-07 — Xem nhật ký kiểm toán

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-07 |
| **Mục tiêu** | Truy vết ai đã làm gì, lúc nào, trước/sau ra sao |
| **Actor chính / phụ** | Chính: **ADMIN** |
| **Điều kiện trước** | Đăng nhập ADMIN |
| **Luồng chính** | 1. ADMIN vào **Nhật ký hệ thống** (`/audit-logs`).<br>2. Hệ thống (`GET /audits`) trả các sự kiện `audit_events` có lọc và phân trang (hành động, thực thể, người thực hiện, thời gian) |
| **Luồng thay thế** | A1. Lọc theo loại thực thể/hành động |
| **Luồng lỗi** | E1. Không phải ADMIN → 403.<br>E2. Tham số lọc sai → 422 |
| **Điều kiện sau** | Chỉ đọc; không có API sửa/xóa audit |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | `GET /api/v1/audits`; UI `/audit-logs` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Giới hạn: chỉ-thêm là quy ước tầng ứng dụng; đăng nhập không được audit. Teacher DB (09/10/2026): 16 sự kiện (nhập/xuất hồ sơ, nạp tài khoản demo, nhập CSV, chuẩn hóa…), chưa có sự kiện duyệt |
| **Test case tương ứng** | `test_audit_api` (35 ca) |

---

## UC-26 — Khởi tạo dữ liệu và tài khoản ADMIN demo

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-26 — **chỉ chạy bằng script CLI** |
| **Mục tiêu** | Dựng lược đồ CSDL và tạo tài khoản ADMIN đầu tiên để bắt đầu dùng hệ thống |
| **Actor chính / phụ** | Chính: **Kỹ thuật viên** |
| **Điều kiện trước** | PostgreSQL chạy; biến môi trường kết nối; mật khẩu demo qua biến môi trường (không ghi vào mã/tài liệu) |
| **Luồng chính** | 1. `alembic upgrade head` tạo lược đồ (7 migration tuyến tính).<br>2. `bootstrap_demo_admin.py` tạo tài khoản ADMIN (kiểm đúng DB/cổng; mật khẩu lấy từ `DEMO_BOOTSTRAP_ADMIN_PASSWORD`; từ chối mật khẩu yếu nếu không có cờ cho phép); ghi audit `DEMO_ADMIN_BOOTSTRAPPED`.<br>3. (Tùy chọn) `seed_demo_users.py` tạo tài khoản demo khác |
| **Luồng thay thế** | A1. Chạy lại: idempotent, không tạo trùng |
| **Luồng lỗi** | E1. Sai DB/cổng → từ chối (cổng 5432 bị từ chối).<br>E2. Thiếu biến mật khẩu → từ chối |
| **Điều kiện sau** | Có tài khoản ADMIN đăng nhập được |
| **Dữ liệu thay đổi** | `users`, (demo) `lecturers`, `audit_events` |
| **Quyền truy cập** | Không qua API/RBAC; người chạy script có quyền DB |
| **API / UI thực tế** | `alembic upgrade head`; `backend/scripts/bootstrap_demo_admin.py`, `seed_demo_users.py` |
| **Trạng thái triển khai** | **CHỈ CLI**; phục vụ demo/phát triển |
| **Test case tương ứng** | `test_bootstrap_demo_admin`; `unit/test_demo_launcher` |
