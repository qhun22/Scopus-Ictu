# BÁO CÁO KIỂM THỬ CHỨC NĂNG — SCOPUS–ICTU (TASK 16)

- Ngày thực hiện: **09/10/2026** · Hạn trình diễn: 14/10/2026
- Người thực hiện: Claude Code (vai trò kiểm thử + hướng dẫn + hỗ trợ bảo vệ), theo yêu cầu Task 16.
- Mã nguồn kiểm thử: repository `D:\DataFolder\ProjectIctu\DoAn\Scopus-Ictu`, nhánh `task16/sua-loi-trinh-dien` (khởi điểm `main` = `d51a055`).
- Bằng chứng (ngoài Git): `D:\DataFolder\ProjectIctu\DoAn\_quan_ly_do_an\evidence\task16\` (ảnh chụp, fingerprint JSON, OpenAPI, ma trận), nhật ký `_quan_ly_do_an\logs\task16\`, công cụ `_quan_ly_do_an\tools\task16\`.
- Báo cáo này phản ánh **lần chạy mới của Task 16**, không dùng baseline cũ làm kết quả.

**Quy ước nhãn** (đúng như yêu cầu): `BROWSER_PASS` đã thao tác thành công trên trình duyệt thật · `API_PASS` đã chạy qua API/integration test/CLI · `CODE_ONLY` mới đối chiếu mã · `MANUAL_REQUIRED` · `FAILED` · `BLOCKED` · `NOT_IMPLEMENTED`.
Nhãn được gán theo bằng chứng **thấp nhất** thực sự có; chỗ chỉ một phần được thao tác bằng trình duyệt có ghi chú.

---

## 1. Môi trường kiểm thử

| Hạng mục | Giá trị |
|---|---|
| Hệ điều hành | Windows 11 Home (10.0.26300) |
| PostgreSQL | 17.10, cụm demo `127.0.0.1:55432`, data dir `_postgres_demo_14_10\data`, `system_identifier` **7694238084633166136** (khớp báo cáo trước). Cổng **5432 không được chạm** |
| Teacher DB | `scopus_ictu_demo_teacher_20261014` — **chỉ đọc** |
| DB test thao tác ghi (bản sao teacher) | `scopus_ictu_test_e2e_t16_20261009` — tạo bằng `pg_dump -Fc` (đọc teacher) + `pg_restore`; dump lưu `_quan_ly_do_an\backups\task16\` |
| DB test khởi tạo sạch | `scopus_ictu_test_empty_t16_20261009` — tạo rỗng, `alembic upgrade head` → `a9c2e4f71b30`, seed 2 tài khoản demo |
| DB test chạy pytest | `scopus_ictu_test_roundtrip_20261014` (DB đã dùng ở Task 15.2) |
| Backend E2E | uvicorn 127.0.0.1:**8002** → `e2e_t16`; 127.0.0.1:**8003** → `empty_t16`. (Backend teacher của BAT: 8001) |
| Frontend E2E | Vite 127.0.0.1:**5174** → proxy 8002; 127.0.0.1/localhost:**5175** → proxy 8003. (Frontend teacher của BAT: 5173) |
| Phiên trình duyệt | Trình duyệt tích hợp của Claude Desktop (Browser pane), tách cookie theo host: `127.0.0.1` cho e2e, `localhost` cho empty |
| Tài khoản test | Mật khẩu **sinh riêng cho DB test** (`secrets\t16_test_accounts.env`, ngoài Git) — không dùng mật khẩu của teacher; không ghi vào tài liệu/ảnh |

**Bảo đảm cô lập:** (1) mỗi backend khởi động bằng `run_api_tree.py` — từ chối chạy nếu `DB_NAME`/cổng sai hoặc module `app` không nạp từ `Scopus-Ictu\backend`; (2) sau mỗi thao tác ghi đều **truy vấn trực tiếp DB test** để xác minh; (3) **dấu vân tay nội dung teacher** được lấy trước/giữa/sau (mục 15); (4) launcher teacher (BAT) không bị sửa.

## 2. Phiên bản

| Thành phần | Phiên bản |
|---|---|
| Python | **3.12.10** (`_venv_backend_demo_py312`) |
| FastAPI / Uvicorn | 0.142.4 / 0.54.0 |
| SQLAlchemy / Alembic | 2.1.4 / 1.20.0 (Alembic head `a9c2e4f71b30`) |
| Pydantic | 2.13.5 |
| Trình điều khiển PostgreSQL | **psycopg2-binary 2.9.13** (đang hoạt động; không dùng psycopg3) |
| pytest | 9.1.1 |
| Node / Vite / TypeScript | v24.19.0 / 5.4.21 / 5.9.3 |
| React / Ant Design / React Router | ^18.2 / ^5.16 / ^6.22 (theo `package.json`) |
| Phần mềm (nhãn trên giao diện) | M2.3 (chân sidebar) |

## 3. Kết quả Backend tests

| Lần chạy | Kết quả | Ghi chú |
|---|---|---|
| Baseline Task 15.2 (tham chiếu, **không** dùng làm kết quả) | 780 passed, 1 skipped, 0 failed, 0 errors, 10 warnings | |
| **Task 16 – lần 1** (mã `d51a055` + sửa giao diện, trước khi sửa backend) | **781 passed, 0 skipped, 0 failed, 0 errors, 10 warnings** — 343,5 giây | `pytest -q -rs`, Python 3.12.10 |
| **Task 16 – cuối cùng** (mã sau 3 commit sửa lỗi, 784 test) | **784 passed, 0 skipped, 0 failed, 0 errors, 10 warnings** — 323,97 giây (0:05:23) | `--basetemp _quan_ly_do_an\tests\pytest_temp\t16_full_final`, `TEMP`/`TMP` riêng |

- Lệnh: `python -I _quan_ly_do_an\tools\task16\pytest_t16.py t16_full_final -q -rs` (wrapper chỉ nạp env của DB `test_roundtrip`, đặt `TEST_DATABASE_URL`, `TEMP/TMP/--basetemp` trong `_quan_ly_do_an\tests\pytest_temp`, cổng 55432). **Không** dùng teacher DB.
- **Vì sao baseline có 1 skipped mà nay 0?** Test `test_generate_matching_candidates_cli.py` tự bỏ qua khi "process settings do not point at the isolated test database". Wrapper Task 16 nạp biến `DB_*` trỏ đúng DB test nên test đó **chạy và PASS**. Không có test nào bị bỏ qua.
- Test mới thêm trong Task 16: **3** (xem mục 12). Kết quả: 781 → 784.
- 10 cảnh báo là cảnh báo bản cũ của thư viện (Pydantic class-config, JWT key dưới 32 byte…), không phải lỗi.

## 4. Frontend

| Kiểm tra | Lệnh | Kết quả |
|---|---|---|
| Type-check | `tsc --noEmit` | **PASS** (exit 0, không lỗi) — chạy lại sau khi sửa giao diện |
| Build | `vite build --outDir _quan_ly_do_an\tests\t16_build` | **PASS** — "built in 14.35s" (cảnh báo kích thước chunk 1,37 MB, không phải lỗi). Kết quả build để ngoài repo |
| Proxy tích hợp | `GET <frontend>/api/v1/auth/me` | 401 (chưa đăng nhập) = proxy sang đúng backend trên cả 5173 (launcher), 5174, 5175 |

## 5. Danh sách chức năng và kết quả (theo Router + Sidebar + OpenAPI)

Nguồn danh sách: `frontend\src\App.tsx` (14 route + `*`), `Sidebar.tsx` (3 menu theo vai trò), `GET /openapi.json` (**57 thao tác**, `evidence\task16\openapi_endpoints.txt`).

| # | Chức năng | Route / nơi | Quyền | Trạng thái | Ghi chú bằng chứng |
|---|---|---|---|---|---|
| F01 | Đăng nhập (đúng/sai), đăng xuất, tải lại, URL bảo vệ, phiên hết hạn/thu hồi | `/login`, mọi trang | — | **BROWSER_PASS** | 01, 03; hết hạn 60' = 401 (API); thu hồi sau đặt lại mật khẩu → về `/login` |
| F02 | Phân quyền ADMIN / REVIEWER / LECTURER | toàn bộ | 3 vai trò | **BROWSER_PASS** (ADMIN, LECTURER) + **API_PASS** (REVIEWER) | 07; LECTURER vào `/audit-logs` → về `/home`; ma trận 403 |
| F03 | Trang chủ | `/home` | mọi | **BROWSER_PASS** | Biểu đồ/hoạt động là giữ chỗ |
| F04 | Tổng quan (Dashboard) | `/dashboard` | ADMIN | **BROWSER_PASS** | 02; đối chiếu API/DB |
| F05 | Giảng viên: danh sách, tìm, phân trang, chi tiết | `/lecturers` | ADMIN | **BROWSER_PASS** | |
| F06 | Giảng viên: thêm / sửa / xóa + validation + email trùng | `/lecturers` | ADMIN | **BROWSER_PASS** | 04, 05; mã cán bộ trùng, version conflict, vai trò sai (API_PASS) |
| F07 | Tài khoản: cấp, khóa, mở khóa, đặt lại mật khẩu | `/lecturers` → Chi tiết | ADMIN | **BROWSER_PASS** | 05, 06; đổi vai trò = **API_PASS** |
| F08 | Nhập JSON giảng viên (Preview → Import → Sửa → Khôi phục → Hoàn tác) | `/imports` | ADMIN | **BROWSER_PASS** | 30–34 |
| F09a | Nút **Xuất JSON** giảng viên (gọi server, ghi audit) | `/lecturers` | ADMIN | **BROWSER_PASS** (nút) | Tệp tải về không kiểm bằng trình duyệt tích hợp |
| F09b | Nội dung tệp xuất + nhập lại | API | ADMIN | **API_PASS** | 410 hồ sơ, 0 từ khóa nhạy cảm, reimport = unchanged 410 |
| F10 | Nhập CSV Scopus (đúng, trùng, sai đuôi, sai nội dung) | `/imports` | ADMIN | **BROWSER_PASS** | 40, 41 |
| F11 | Chuẩn hóa công bố | `/normalization` | ADMIN | **BROWSER_PASS** | 43 |
| F12 | Bóc tách tác giả | `/normalization` → Tác giả | ADMIN | **BROWSER_PASS** | 42; idempotent = API_PASS |
| F13 | Công bố: danh sách, tìm, lọc, chi tiết, không tìm thấy | `/publications` | ADMIN, REVIEWER | **BROWSER_PASS** | 10, 11 |
| F14 | **Affiliation theo từng tác giả** (VERIFIED/CORROBORATED/UNRESOLVED) | `/publications/:eid` | ADMIN, REVIEWER | **BROWSER_PASS** (test DB = bản sao nội dung của teacher) + **API_PASS** (teacher) | 12; quét 660 bài |
| F15 | Hàng đợi đối sánh + chi tiết ứng viên (A–E) + cảnh báo dùng chung | `/reviews` | ADMIN, REVIEWER | **BROWSER_PASS** | 19, 20 |
| F16 | ACCEPT / REJECT | `/reviews` | ADMIN, REVIEWER | **BROWSER_PASS** (test DB) | 20b, 21 |
| F17 | Xung đột review: 409 dùng chung (UI), stale, đã quyết định, idempotent, 422, 403 | `/reviews` | | **BROWSER_PASS** (409 dùng chung) + **API_PASS** (còn lại) | 22 |
| F18 | Lịch sử review | `/review-history` | ADMIN, REVIEWER | **BROWSER_PASS** | |
| F19 | Nhật ký hệ thống | `/audit-logs` | ADMIN | **BROWSER_PASS** | Bộ lọc chưa thao tác |
| F20 | Tra cứu tổng hợp | `/search` | ADMIN, REVIEWER | **BROWSER_PASS** | không dấu ≠ có dấu |
| F21 | Cổng giảng viên: Hồ sơ, Công bố của tôi, Liên kết Scopus | `/profile`, `/my-publications`, `/identity` | LECTURER | **BROWSER_PASS** | 23 (19 công bố sau ACCEPT) |
| F22 | Thông báo (toast nền) | — | đăng nhập | **API_PASS** | Không có trang riêng; đã tiêu thụ (`read_at`) |
| F23 | Hoàn tác đợt nhập giảng viên | `/imports` → Chi tiết | ADMIN | **BROWSER_PASS** | 33 |
| F24 | Quản lý đợt nhập: lưu trữ, khôi phục, hủy, xóa | API | ADMIN | **API_PASS** | Nút Xóa của đợt Scopus trên UI chưa bấm |
| F25 | Xuất JSON công bố | `/publications` | ADMIN, REVIEWER | **API_PASS** | Có ghi audit; nút UI **không bấm** |
| F26 | Chuyển ngôn ngữ VI/EN | đầu trang | mọi | **BROWSER_PASS** | |
| F27 | Launcher (BAT → `demo_launcher.py`): start/status | `scopus-ictu-qhun22.bat` | — | **API_PASS** (chạy `demo_launcher.py start/status` — lệnh mà BAT gọi) + **MANUAL_REQUIRED** (nhấp đúp BAT: người dùng đã tự kiểm trước đó, không lặp lại để khỏi bật trình duyệt) | Nhật ký launcher |
| F28 | Trang Tác vụ | `/tasks` | ADMIN | **NOT_IMPLEMENTED** | Trang giữ chỗ — đã xem bằng trình duyệt |
| F29 | Trang Người dùng riêng / nút tạo user độc lập | `/users` | ADMIN | **NOT_IMPLEMENTED** | `/users` chuyển sang `/lecturers`; không có `POST /users` |
| F30 | Biểu đồ Trang chủ | `/home` | | **NOT_IMPLEMENTED** | Luôn "Chưa có dữ liệu" (đổi nhãn "Đang phát triển") |
| F31 | Sinh ứng viên đối sánh; nạp OpenAlex/Crossref; nạp công bố đã biết | CLI `scripts/*.py` | quản trị viên chạy | **CODE_ONLY** (có thể đọc docstring + tests; **cố ý không chạy** trên teacher; không có nút UI) | |
| F32 | `DELETE /lecturers/unlinked/cleanup` | API | ADMIN | **FAILED → đã sửa → API_PASS** | Trước: 500; nay 410 |
| F33 | `PUT /lecturers/{id}`, `GET /users/{id}` | API | ADMIN | **CODE_ONLY** | UI dùng PATCH / danh sách |

**Tổng hợp theo chức năng (34 mục; F09 tách thành F09a/F09b):**
- `BROWSER_PASS`: **23** (F01, F02, F03–F08, F09a, F10–F21, F23, F26 — mục F02 và F17 có thêm phần API_PASS ghi ở cột Ghi chú).
- Chỉ `API_PASS`: **5** (F09b, F22, F24, F25, F27 — F27 còn một phần `MANUAL_REQUIRED`).
- `FAILED` → đã sửa → `API_PASS`: **1** (F32).
- `CODE_ONLY`: **2** (F31, F33).
- `NOT_IMPLEMENTED`: **3** (F28, F29, F30).
- `MANUAL_REQUIRED`: **1 phần** (nhấp đúp BAT, thuộc F27). `BLOCKED`: **0**.

**Số chức năng đã kiểm thử thực tế (BROWSER_PASS hoặc API_PASS, kể cả F32 sau sửa): 29 / 34.**

### 5.1. Ma trận coverage theo OpenAPI (57 thao tác)
Đầy đủ từng dòng: `evidence\task16\openapi_coverage_matrix.md`. Tóm tắt: **BROWSER_PASS 34 · API_PASS 20 · FAILED→sửa 1 · CODE_ONLY 2** (tổng 57). Frontend route: 14/14 route được mở (`/tasks` = placeholder); sidebar ADMIN 10/10 mục được bấm hoặc mở; sidebar LECTURER 4/4; sidebar REVIEWER: kiểm bằng API (403/200), chưa đăng nhập UI.

Ma trận route:

| Route | Quyền | Đã mở bằng trình duyệt | Kết quả |
|---|---|---|---|
| `/login` | công khai | ✔ | OK |
| `/home` | mọi | ✔ (ADMIN, LECTURER) | OK; khung biểu đồ giữ chỗ |
| `/dashboard` | ADMIN | ✔ | OK |
| `/imports` | ADMIN | ✔ | OK |
| `/normalization` | ADMIN | ✔ | OK |
| `/lecturers` | ADMIN | ✔ | OK |
| `/users` | ADMIN | ✔ | Chuyển → `/lecturers` |
| `/publications`, `/publications/:eid` | ADMIN, REVIEWER | ✔ | OK; 404 thân thiện |
| `/search` | ADMIN, REVIEWER | ✔ | OK |
| `/reviews`, `/approval-queue` | ADMIN, REVIEWER | ✔ (`/reviews`) | OK |
| `/review-history` | ADMIN, REVIEWER | ✔ | OK |
| `/audit-logs` | ADMIN | ✔ | OK |
| `/tasks` | ADMIN | ✔ | Placeholder |
| `/profile`, `/my-publications`, `/identity` | LECTURER | ✔ | OK |
| `*` | — | (chuyển hướng gốc) | CODE_ONLY |

## 6–9. Test case, kết quả mong đợi, kết quả quan sát, bằng chứng

*(Môi trường: B = trình duyệt trên `e2e_t16` hoặc `empty_t16`; A = API trên DB test; T = teacher chỉ đọc. Mọi bước ghi chỉ ở DB test và đã xác minh bằng SQL.)*

### 6.1. Đăng nhập, phiên, phân quyền
| TC | Bước | Mong đợi | Quan sát | Nhãn |
|---|---|---|---|---|
| TC01 | Mở `/dashboard` khi chưa đăng nhập | Về `/login` | Về `/login` | BROWSER_PASS |
| TC02 | Đăng nhập sai mật khẩu | Toast lỗi, ở lại | "Đăng nhập thất bại — Email hoặc mật khẩu không đúng." | BROWSER_PASS (ảnh 01) |
| TC03 | Đăng nhập ADMIN | Vào `/home`, tên "Quản trị viên" đúng dấu | "Xin chào, Quản trị viên" | BROWSER_PASS |
| TC04 | F5 trên `/dashboard` | Giữ phiên | Vẫn ở `/dashboard` | BROWSER_PASS |
| TC05 | Đăng xuất | Về `/login`, toast | OK; vào lại URL bảo vệ → `/login` | BROWSER_PASS (ảnh 03) |
| TC06 | Đăng nhập LECTURER; vào `/audit-logs` | Bị chặn | Menu chỉ 4 mục; URL về `/home` | BROWSER_PASS (ảnh 07) |
| TC07 | LECTURER gọi API quản trị (`/users /audits /dashboard/summary /lecturers /publications /reviews/candidates /imports`) | 403 | **403** cả 7; ẩn danh → 401 | API_PASS |
| TC08 | REVIEWER: `/reviews /publications /search /history` vs `/dashboard /imports /lecturers /users /audits /export` | 200 vs 403 | 200 ×4; **403** ×6; POST import 403 | API_PASS |
| TC09 | Token hết hạn / sai auth_version / rác | 401 | 401 ×3 (60 phút cấu hình) | API_PASS |
| TC10 | Admin đặt lại mật khẩu người đang đăng nhập → tải lại trang | Phiên bị thu hồi | Về `/login` (trước đó trang trắng do hot-reload — xem 11) | BROWSER_PASS |
| TC11 | Đăng nhập tài khoản bị khóa | 403 ACCOUNT_LOCKED | `{"detail":"Tài khoản đang bị khóa.","code":"ACCOUNT_LOCKED"}` | API_PASS |

### 6.2. Dashboard
| TC12 | Mở Tổng quan (test DB giống teacher) | 660/411/411/1207/40; ứng viên-định danh 0/0/0/0; đợt nhập gần nhất | Đúng (ảnh 02); API teacher: cùng số | BROWSER_PASS + API_PASS (T) |

### 6.3. Giảng viên và tài khoản (B, DB `e2e_t16`)
| TC | Bước | Mong đợi | Quan sát | Nhãn |
|---|---|---|---|---|
| TC20 | Tìm `Nguyễn Văn`; phân trang; Chi tiết | Lọc đúng, 10/trang | OK | BROWSER_PASS |
| TC21 | Sửa: xóa trống họ tên → Lưu | Chặn | Trình duyệt chặn ("Please fill out this field") | BROWSER_PASS |
| TC22 | Sửa mã cán bộ + khoa → Lưu | Cập nhật; version+1; audit `LECTURER_UPDATED` | version 1→2, audit có | BROWSER_PASS (SQL) |
| TC23 | Thêm giảng viên, mật khẩu 3 ký tự | Chặn | "Please lengthen this text to 8 characters or more" | BROWSER_PASS |
| TC24 | Thêm giảng viên email trùng hồ sơ cũ (chưa có tài khoản) | Cho phép, gắn **Cảnh báo** | Tạo thành công; thẻ Cảnh báo = 2; cả 2 hồ sơ nhãn "Cảnh báo" | BROWSER_PASS |
| TC25 | Thêm lần nữa cùng email (đã có tài khoản) | Lỗi | "Email đã được sử dụng." (409) | BROWSER_PASS (ảnh 04) |
| TC26 | Email sai định dạng | Chặn | "Please include an '@'…" | BROWSER_PASS |
| TC27 | Thêm giảng viên hợp lệ | Có audit | **Trước sửa: không có audit** (FAIL, mục 11). Sau sửa: `LECTURER_CREATED`, không có mật khẩu | BROWSER_PASS (SQL) |
| TC28 | Mã cán bộ trùng (POST/PATCH) | 409 STAFF_CODE_ALREADY_EXISTS | Đúng | API_PASS |
| TC29 | PATCH phiên bản cũ | 409 VERSION_CONFLICT | Đúng | API_PASS |
| TC30 | PATCH vai trò không hợp lệ / tên trống | 422 | Đúng | API_PASS |
| TC31 | PATCH ORCID "123" | 422 rõ ràng | **Trước sửa: 409 "bị trùng" (sai)**. Sau sửa: 422 "ORCID không hợp lệ…" | API_PASS |
| TC32 | Mật khẩu mới 3 ký tự → Đặt lại | Chặn | "Mật khẩu mới phải có ít nhất 8 ký tự." | BROWSER_PASS |
| TC33 | Khóa → xác nhận → thử đăng nhập → Mở khóa | Khóa/mở được; đăng nhập 403 khi khóa | Toast "Đã khóa tài khoản"; 403; "Đã mở khóa" | BROWSER_PASS |
| TC34 | Đặt lại mật khẩu hợp lệ → thử mật khẩu cũ/mới | cũ 401, mới 200 | 401 / 200; audit `USER_PASSWORD_RESET` | BROWSER_PASS |
| TC35 | Cấp tài khoản cho hồ sơ có sẵn (tích ô) | Tạo tài khoản LECTURER | Tạo được; đăng nhập OK | BROWSER_PASS |
| TC36 | Đổi vai trò LECTURER→REVIEWER (PATCH /users) | 200 | 200 | API_PASS |
| TC37 | Xóa hồ sơ có ứng viên / có tài khoản | Chặn 409 | Toast "Không thể xóa giảng viên…"; 409 LECTURER_IN_USE | BROWSER_PASS |
| TC38 | Xóa hồ sơ không phụ thuộc | Xóa; audit `LECTURER_DELETED` | 413→412; audit có | BROWSER_PASS (SQL) |
| TC39 | Thông báo sau khóa/mở/đặt lại | 3 thông báo, được tiêu thụ | `user_notifications` 3 dòng, `read_at` đã có | API_PASS |

### 6.4. Nhập JSON giảng viên (B, DB `empty_t16`, `localhost:5175`)
Tệp thử nghiệm: bản sao có SHA khớp nguồn — `merged_410.json` = `ictu_lecturers_merged.json` (SHA-256 `8d2ca5d9…`); các tệp lỗi/biến thể sinh từ nó trong `_quan_ly_do_an\tests\t16_upload\` (nguồn **không bị sửa**).
| TC | Bước | Mong đợi | Quan sát | Nhãn |
|---|---|---|---|---|
| TC40 | Chọn JSON cắt ngang → Kiểm tra dữ liệu | Lỗi rõ | "INVALID_LECTURER_DATASET: Tệp JSON không hợp lệ…" | BROWSER_PASS (ảnh 30) |
| TC41 | JSON thiếu `full_name` / `source_id` | Lỗi chỉ rõ trường | "lecturers[0].full_name là bắt buộc." | BROWSER_PASS |
| TC42 | JSON 2 bản ghi trùng email | Lỗi | "DUPLICATE_LECTURER_IDENTITY: Email … bị trùng giữa các bản ghi." | BROWSER_PASS (ảnh 34) |
| TC43 | JSON hợp lệ 410 → Preview | 410 hợp lệ / 410 tạo mới; **chưa ghi DB** | Đúng; SQL: vẫn 1 hồ sơ, 0 snapshot | BROWSER_PASS (ảnh 31) |
| TC44 | Xác nhận nhập | 410 tạo; 411 hồ sơ | 411; 410 snapshot; 410 có `source_id`; 352 ORCID; audit IMPORTED | BROWSER_PASS (ảnh 32) |
| TC45 | Nhập tệp đổi email + chức vụ (cùng `source_id`) | Cập nhật 2, giữ 408; UUID bền | Preview 2/408; sau nhập **mã băm bản đồ UUID↔source_id không đổi** (`a40ede48…`), email đổi, version+1 | BROWSER_PASS (SQL) |
| TC46 | Nhập tệp chỉ 50 hồ sơ | Không xóa 360 còn lại; khôi phục giá trị | 411 hồ sơ; 2 giá trị trở về cũ | BROWSER_PASS |
| TC47 | Hoàn tác đợt nhập (Chi tiết → Xóa đợt nhập → Hoàn tác) | Trạng thái "Đã hoàn tác"; giá trị trước trở lại; audit ROLLED_BACK | Đúng (email/chức vụ trở về giá trị trước đợt đó) | BROWSER_PASS (ảnh 33) |
| TC48 | Xuất JSON (nút) | Server xuất + audit | Audit `LECTURER_DATASET_EXPORTED` | BROWSER_PASS |
| TC49 | Nội dung xuất | 410 hồ sơ; không bí mật; không `tel`; không hồ sơ seed | 410; 0 lần password/hash/token/secret/argon/bcrypt; không `tel`; có `full_name_normalized` | API_PASS |
| TC50 | Nhập lại bản xuất | Không thay đổi | Preview: unchanged **410** | API_PASS |
| TC51 | Nhập bản thô cũ (không ORCID) lên DB đã có ORCID | Cảnh báo ghi đè | Preview: **update 352** (không áp dụng) | API_PASS |
| TC52 | Hoàn tác không theo thứ tự (API cũ) | Không mất dữ liệu | 200; 410 bản ghi đa nguồn **được giữ**, 0 bản bị xóa | API_PASS |

### 6.5. Nhập CSV Scopus và chuẩn hóa (B, DB `empty_t16`)
File nguồn dùng: **`D:\DataFolder\ProjectIctu\DoAn\Truong_Quang_Huy_Scopus_Sep2026.csv`** (SHA-256 `6a62fcf6…f75d`, 1.277.558 byte; khớp SHA ghi trên trang chi tiết bài của teacher). *(Bản CSV bị Git bỏ qua trong repo có checksum khác; không dùng.)*
| TC | Bước | Mong đợi | Quan sát | Nhãn |
|---|---|---|---|---|
| TC60 | Chọn tệp `.txt` | Từ chối | "Chỉ hỗ trợ tệp CSV." (UI); API 422 `UNSUPPORTED_IMPORT_FORMAT` | BROWSER_PASS |
| TC61 | CSV cột sai (`cot1,cot2`) → Bắt đầu nhập → Chuẩn hóa | (mong đợi) bị từ chối | **Nhập thô được chấp nhận** (1/1, trạng thái "Đã tiếp nhận"); Chuẩn hóa → `canonical_failed=1`, **0 công bố**; UI vẫn ghi "Hoàn thành" — xem 13 (giới hạn) | BROWSER_PASS (quan sát) |
| TC62 | CSV thật 660 dòng → Bắt đầu nhập | 660/660, 0 lỗi | 660 / 660 / 0 (ảnh 40) | BROWSER_PASS |
| TC63 | Chuẩn hóa công bố | 660 công bố | `canonical_new=660`, `failed=0` (ảnh 43) | BROWSER_PASS |
| TC64 | Bóc tách tác giả | 1.207 tác giả / 2.751 vị trí | **1.207 / 2.751 / 2.768 biến thể** | BROWSER_PASS |
| TC65 | Đối sánh nội dung với teacher | Trùng | Mã băm nội dung `publications`, `scopus_authors`, `publication_authors` (EID/DOI/tiêu đề/năm; Scopus ID; EID+ID+thứ tự) **giống hệt** teacher | API_PASS (SQL) |
| TC66 | Chọn lại cùng tệp | Cảnh báo trùng | Khung vàng "Tệp có nội dung trùng…"; API 409 `DUPLICATE_IMPORT_CONFIRMATION_REQUIRED` | BROWSER_PASS (ảnh 41) |
| TC67 | Chuẩn hóa lại công bố + tác giả (idempotent) | Không thêm | 0 tạo mới; `authors_existing=2751`; số liệu và mã băm không đổi | API_PASS |
| TC68 | Quản lý đợt nhập: lưu trữ / khôi phục / hủy đợt đã xong / xóa đợt đang dùng / xóa đợt chưa dùng / id không tồn tại | 200 / 200 / 409 / 409 IMPORT_IN_USE / 200 / 404 | Đúng cả 6 | API_PASS |

### 6.6. Công bố và affiliation (B trên `e2e_t16`; T = teacher đọc bằng API)
| TC | Bước | Mong đợi | Quan sát | Nhãn |
|---|---|---|---|---|
| TC70 | Danh sách: đọc tiêu đề | Đọc được | **Trước sửa: cột tiêu đề 77 px, chỉ ~7 ký tự**; sau sửa: tiêu đề đủ 2–3 dòng, nút "Chi tiết" thấy được ở 1366×768 | BROWSER_PASS (ảnh 10) |
| TC71 | Tìm `UML`; lọc Năm `2020` | Kết quả đúng | Toàn bộ dòng là năm 2020 (20/trang) | BROWSER_PASS |
| TC72 | `/publications/2-s2.0-000000000` | Thông báo thân thiện | "Không tìm thấy công bố này." | BROWSER_PASS |
| TC73 | Chi tiết `2-s2.0-105006527625` | 5 tác giả; 8 mục đơn vị; 1 UNRESOLVED | Đúng từng hàng (ảnh 11, 12) | BROWSER_PASS |
| TC74 | Quét 660 bài (API): tổng đơn vị theo tác giả | Không gắn nhầm | 2.751 vị trí; 3.451 mục hiển thị; trạng thái theo vị trí: 517 V có đơn vị, 28 V thiếu, 1.774 C có, 279 C thiếu, 153 UNRESOLVED | API_PASS |
| TC75 | Các EID ví dụ trên **teacher** | Khớp test DB | `105006527625`, `105035336993`, `105027527591`, `105013367684`, `105036729228`: tóm tắt đúng như tài liệu | API_PASS (T) |
| TC76 | Đối chiếu số DB teacher | | Đối chiếu: 5.502 bản ghi đối chiếu; 4.147 dòng liên kết (883 V + 3.264 C); 217 tổ chức; 2.291 vị trí có ≥1 đơn vị | API_PASS (SQL đọc) |

### 6.7. Matching, ACCEPT/REJECT, lịch sử, audit
| TC | Bước | Mong đợi | Quan sát | Nhãn |
|---|---|---|---|---|
| TC80 | Hàng đợi (teacher, đọc) | 40 PENDING; 6 có công bố; 5 dùng chung | Đúng: 38 giảng viên, 36 Scopus ID, 34 chỉ-tên, 4 mơ hồ | API_PASS (T) |
| TC81 | Hàng đợi + chi tiết ứng viên Lương Thị Minh Huế (B, test) | Phần A–E, 16 công bố DOI_EXACT | Đúng (ảnh 19, 20) | BROWSER_PASS |
| TC82 | ACCEPT (Lương Thị Minh Huế) | `ACCEPTED`; 1 identity APPROVED; ≥1 evidence; 2 audit | candidates PENDING 39/ACCEPTED 1; identity 1; identity_evidence 17; audit `CANDIDATE_ACCEPTED`+`IDENTITY_CREATED_FROM_CANDIDATE`; **teacher: vẫn 0 identity** | BROWSER_PASS (SQL) |
| TC83 | REJECT không lý do | Bị chặn | Nút "Xác nhận REJECT" khóa (ảnh 21) | BROWSER_PASS |
| TC84 | REJECT có lý do (Nguyễn Văn Giáp) | `REJECTED`; không identity | Đúng; audit `CANDIDATE_REJECTED` có lý do | BROWSER_PASS |
| TC85 | ACCEPT lặp cùng version | Idempotent | 200 `idempotent:true` | API_PASS |
| TC86 | ACCEPT ứng viên đã REJECT | 409 | 409 `CANDIDATE_ALREADY_DECIDED_CONFLICT` | API_PASS |
| TC87 | Stale version | 409 | 409 `STALE_CANDIDATE_VERSION` | API_PASS |
| TC88 | REJECT không lý do (API) | 422 | 422 `INVALID_REVIEW_REASON` | API_PASS |
| TC89 | LECTURER POST review / ẩn danh GET / id lạ | 403 / 401 / 404 | Đúng | API_PASS |
| TC90 | Scopus ID dùng chung: ACCEPT #1 rồi ACCEPT #2 | #2 bị chặn | API 409 `SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER`; **UI** toast "Không thể lưu quyết định — Tác giả Scopus này đã được xác nhận cho một giảng viên khác…" (ảnh 22) | BROWSER_PASS + API_PASS |
| TC91 | Lịch sử review | 3 dòng | 3 dòng (ACCEPT, REJECT, ACCEPT) | BROWSER_PASS |
| TC92 | Nhật ký hệ thống | Hiện đủ hành động | 25 dòng, đủ các hành động; bộ lọc **chưa thao tác** | BROWSER_PASS |
| TC93 | Sau ACCEPT, giảng viên đăng nhập → Công bố của tôi | Thấy công bố | **19 công bố** (17 năm 2026, 2 năm 2025), 1 định danh đã duyệt (ảnh 23) | BROWSER_PASS |

### 6.8. Khác
| TC | Bước | Quan sát | Nhãn |
|---|---|---|---|
| TC100 | Tra cứu `Lương Thị Minh` / `Luong Thi Minh` / `Luong` / `60319803200` / `UML` / DOI / EID / `a` | 1 giảng viên / 0 / 5 tác giả / 1 tác giả / 5 công bố / 1 / 1 / 422 "ít nhất 2 ký tự" — **phân biệt dấu** | BROWSER_PASS (trang) + API_PASS |
| TC101 | `/tasks` | "Tác vụ hệ thống — Tính năng đang trong quá trình hoàn thiện" | NOT_IMPLEMENTED |
| TC102 | Chuyển VI→EN | Đổi toàn bộ nhãn; có màn chuyển ngôn ngữ | BROWSER_PASS |
| TC103 | Quét 27 GET API với admin | 200 cả 27 | API_PASS |
| TC104 | Launcher: `demo_launcher.py start` / `status` | PostgreSQL (đúng cụm demo, Alembic head `a9c2e4f71b30`, 411 hồ sơ) → Backend 8001 → Frontend 5173 sẵn sàng; chạy lại không nhân đôi | API_PASS |
| TC105 | Teacher đọc qua launcher: đăng nhập ADMIN + dashboard + hàng đợi + 5 EID | Đúng; **fingerprint teacher không đổi sau đăng nhập/đọc** | API_PASS (T) |

## 10. Phân loại kết quả
Xem tổng hợp mục 5. Nhắc lại: **không** có mục nào bị gọi `BROWSER_PASS` khi chỉ gọi API; những mục chỉ gọi API ghi `API_PASS`.

## 11. Các lỗi và vấn đề đã phát hiện

| ID | Mô tả | Bước tái hiện | Nguyên nhân | Mức độ | Tình trạng |
|---|---|---|---|---|---|
| L1 | **Cột tiêu đề danh sách công bố co còn 77 px**, tiêu đề chỉ thấy ~7 ký tự; nút "Chi tiết" tràn khỏi bảng ở 1366×768 | `/publications` | `<td class="max-w-0">` làm ô co lại | **Cao** cho demo | **Đã sửa** |
| L2 | Thêm giảng viên + tạo tài khoản **không ghi audit** | Thêm giảng viên → xem Nhật ký | `create_lecturer` không tạo `AuditEvent` | Trung bình (vi phạm mục tiêu truy vết) | **Đã sửa** (`LECTURER_CREATED`) |
| L3 | PATCH ORCID sai định dạng trả **409 "bị trùng"** (sai nghĩa) | `PATCH /lecturers/{id}` với `"orcid":"123"` | Ràng buộc CHECK của DB bị bắt chung với trùng lặp | Thấp (UI không có ô ORCID) | **Đã sửa** (422) |
| L4 | `DELETE /lecturers/unlinked/cleanup` trả **500** | Gọi API bằng ADMIN | Hàm `clean_orphan_lecturers` không còn trong script | Thấp (không có trên UI) nhưng hiện trong Swagger | **Đã sửa** (410, không xóa gì) |
| L5 | Trang Chủ ghi **"Nguồn: Scopus API"**, "Thời gian thực", "Đồng bộ định kỳ" trong khi chỉ là khung giữ chỗ; hệ thống không gọi Scopus API | Mở Trang chủ | Nhãn i18n cứng | Trung bình (dễ bị hỏi vặn) | **Đã sửa** (nhãn trung thực) |
| L6 | CSV có tiêu đề hợp lệ nhưng **không phải định dạng Scopus** vẫn được nhập thô; chuẩn hóa thất bại nhưng UI ghi "Hoàn thành" | Nhập `bad_scopus.csv` → Chuẩn hóa | Bước nhập thô chỉ kiểm tra tiêu đề trùng/trống | Trung bình | **Chưa sửa** (thay đổi hành vi nhập) — đã ghi trong hướng dẫn |
| L7 | Khi mã nguồn giao diện được sửa lúc phiên đang mở (Vite hot-reload), trang **trắng** ("useI18n must be used within an I18nProvider"); không có Error Boundary | Sửa `i18n/locales/*.ts` khi đang đăng nhập | Fast Refresh nhân đôi context; không có ErrorBoundary | Thấp (chỉ khi dev); trang trắng khi lỗi render là rủi ro chung | Không sửa; ghi trong hướng dẫn |
| L8 | `updated_at` của hồ sơ giảng viên **không đổi** khi sửa (version đổi) | Sửa hồ sơ → xem `updated_at` | Cột chỉ có `server_default`, không `onupdate` | Thấp (không hiển thị trên UI) | Chưa sửa (không cần cho demo) |
| L9 | Tìm kiếm **phân biệt dấu** (Lương ≠ Luong) | `/search?q=Luong` | So khớp chuỗi thường | Thấp | Chưa sửa; ghi trong hướng dẫn |
| L10 | Ngày giờ hiển thị theo locale trình duyệt (kiểu Mỹ `10/9/2026`) | Dashboard/Nhật ký | `toLocaleString()` mặc định | Thấp | Chưa sửa; ghi trong hướng dẫn |
| L11 | Toast tiếng Anh hiện nội dung tiếng Việt từ máy chủ ("Cannot delete lecturer — Hồ sơ này đang…") | EN → Xóa hồ sơ có phụ thuộc | Thông điệp lỗi máy chủ chỉ có tiếng Việt | Rất thấp | Chưa sửa |
| L12 | Cột "Khoa / Bộ môn" của giảng viên ICTU gần như trống | `/lecturers` | Dữ liệu nguồn chưa có | Giới hạn dữ liệu | Không phải lỗi |

## 12. Các lỗi đã sửa (commit trên nhánh `task16/sua-loi-trinh-dien`)

| Commit | Nội dung | Tệp thay đổi | Test hồi quy | Kiểm tra lại thực tế |
|---|---|---|---|---|
| `69cffd3` Sửa lỗi nghiệp vụ giảng viên… | L2, L3, L4 | `backend/app/api/v1/endpoints/lecturers.py` | `test_create_lecturer_writes_audit_event_without_password`, `test_update_lecturer_rejects_malformed_orcid_with_422`, `test_bulk_cleanup_endpoint_is_retired_and_deletes_nothing` (trong `test_lecturer_staff_code_contract.py`) | L2: tạo giảng viên qua UI → SQL thấy `LECTURER_CREATED` (không mật khẩu); L3: API trả 422; L4: API trả 410 |
| `dfdd8fb` Sửa cột tiêu đề… | L1 | `frontend/src/pages/Publications/index.tsx` | (giao diện) tsc + build PASS | Mở lại `/publications` ở 1366×768: tiêu đề đọc được, nút Chi tiết hiện (ảnh 10) |
| `c47a9c5` Chỉnh nhãn Trang chủ… | L5 | `frontend/src/i18n/locales/vi.ts`, `en.ts` | tsc + build PASS | Trang chủ EN/VI hiện "Đang phát triển" |

Không sửa matching rules, không đổi phân loại VERIFIED/CORROBORATED, không migration, không nhập lại dữ liệu teacher.

## 13. Các giới hạn còn lại
- Teacher UI chưa được thao tác bằng trình duyệt trong Task 16: để **không nhập mật khẩu ADMIN thật vào ô đăng nhập**, các bước demo được thử trên `e2e_t16` (nội dung giống hệt teacher, đã đối chiếu mã băm) và teacher được đọc bằng **API chỉ-đọc** (TC75, TC80, TC105). Người dùng đã tự mở teacher UI ở các bước trước; nên diễn tập đầy đủ một lần trước 14/10 (checklist trong kịch bản).
- Tệp **Xuất JSON** tải về không kiểm bằng trình duyệt tích hợp (chỉ kiểm nút + audit + nội dung bằng API).
- Bộ lọc của Nhật ký hệ thống và Lịch sử review, nút **Xóa** đợt nhập Scopus trên UI, sidebar REVIEWER trên UI **chưa thao tác** bằng trình duyệt.
- Nhấp đúp BAT: `MANUAL_REQUIRED` (người dùng đã kiểm).
- Script sinh ứng viên / nạp affiliation / nạp công bố đã biết: `CODE_ONLY`, cố ý không chạy.
- Các vấn đề L6–L12 chưa sửa (xem mục 11).
- Chưa có Error Boundary; trang trắng nếu có lỗi render.

## 14. Phân biệt teacher DB và test DB

| | Teacher | Test e2e | Test empty |
|---|---|---|---|
| Tên | `scopus_ictu_demo_teacher_20261014` | `scopus_ictu_test_e2e_t16_20261009` | `scopus_ictu_test_empty_t16_20261009` |
| Nguồn gốc | Dữ liệu nghiệm thu | `pg_dump` teacher | Rỗng + migrate + seed |
| Thao tác trong Task 16 | **Chỉ đọc** (đăng nhập, GET) | Mọi thao tác ghi E2E | Nhập JSON/CSV/chuẩn hóa/xóa đợt nhập |
| Backend / Frontend | 8001 / 5173 (BAT) | 8002 / 5174 | 8003 / 5175 |
| Thay đổi sau thử nghiệm | **Không** | Có (ACCEPT 2, REJECT 1, +3 giảng viên, −1, v.v.) | Có |

## 15. Kết quả đối chiếu fingerprint (nội dung, không chỉ số dòng)

Công cụ: `_postgres_demo_14_10\tools\fingerprint.py` — với 20 bảng, tính `count` và `md5(string_agg(row::text ORDER BY row::text))` (độc lập thứ tự).

| Thời điểm | Teacher |
|---|---|
| Trước Task 16 (`teacher_fp_truoc_task16.json`) | = baseline Task 15 (`teacher_fp_inicio_task15.json`): **byte-identical** |
| Sau `pg_dump` (`..._sau_dump.json`) | trùng trước |
| Giữa Task 16, sau đăng nhập + đọc API (`..._giua_task16.json`) | trùng trước |
| **Cuối Task 16** (`teacher_fp_cuoi_task16.json`) | **byte-identical** với 3 lần lấy trước và với baseline Task 15 (mã băm MD5 của tệp fingerprint `9d3e5afb9e8cf098c7d4179304afc7ba` ở cả bốn mốc) |

Số liệu teacher cuối: 411 giảng viên · 660 công bố · 1.207 tác giả Scopus · 2.751 vị trí tác giả · 4.147 dòng liên kết đơn vị · 40 ứng viên PENDING · **0** danh tính APPROVED · **0** quyết định review · 16 sự kiện audit (không đổi) · `system_identifier` 7694238084633166136.

Đối sánh nội dung dữ liệu Scopus giữa teacher và `empty_t16` sau khi nhập/chuẩn hóa **qua giao diện**: `publications` (660), `scopus_authors` (1.207), `publication_authors` (2.751) — mã băm **giống hệt**.
`e2e_t16` ngay sau khi restore: giống hệt teacher (`e2e_t16_fp_ban_dau.json` = `teacher_fp_truoc_task16.json`).

Ba bảng đơn vị theo tác giả (không nằm trong 20 bảng của công cụ) cũng được so sánh: `organizations` (217, `64720a7b…`), `publication_author_affiliation_resolutions` (5.502, `ab383cb4…`), `publication_author_affiliations` (4.147, `e501f79f…`) — **giống hệt** giữa teacher (cuối Task 16) và `e2e_t16` (khôi phục từ bản dump teacher lấy đầu Task 16) ⇒ teacher không bị thay đổi.

Cũng đã xác minh: hồ sơ giảng viên `empty_t16` sau nhập có mã băm bản đồ `UUID↔source_id` `a40ede48d33b692137984a721b93ecbe` — **không đổi** qua nhập lại/cập nhật/khôi phục.

## 16. Đánh giá khả năng trình diễn 14/10

| Tiêu chí | Đánh giá |
|---|---|
| Khởi động một lần nhấp đúp | Launcher chạy đúng (Python = lệnh BAT gọi); người dùng đã tự kiểm trước đó |
| Luồng chính (Tổng quan → Công bố → Chi tiết → Affiliation → Hàng đợi → Chi tiết ứng viên → Nhật ký) | Đã thử đầy đủ trên bản sao giống hệt; **ổn định**; có 5 EID ví dụ đã kiểm chứng |
| Số liệu | Khớp 660/411/1207/2751/4147/40/0 |
| Rủi ro chính | (1) bấm nhầm nút ghi (danh sách "chỉ giới thiệu" trong kịch bản); (2) trang trắng nếu có lỗi render (không có Error Boundary); (3) khởi động PostgreSQL lần đầu sau khi bật máy có thể chậm 30–60 giây |
| Blocker cho demo | **Không có blocker**. L1 (cột tiêu đề) — rủi ro demo cao nhất — đã sửa |
| Khuyến nghị | Diễn tập đủ kịch bản trên teacher UI một lần (chỉ đọc); in ảnh chụp trong `evidence\task16\screenshots` làm phương án dự phòng |

## Phụ lục A. Danh sách ảnh chụp (ngoài Git)
`evidence\task16\screenshots\`: 01 đăng nhập sai · 02 Tổng quan · 03 đăng xuất · 04 email trùng · 05 chi tiết giảng viên + tài khoản · 06 xác nhận khóa · 07 LECTURER bị chặn · 10 danh sách công bố sau sửa · 11–12 chi tiết bài + đơn vị theo tác giả · 19 hàng đợi 40 · 20/20b chi tiết ứng viên + xác nhận ACCEPT · 21 REJECT bắt buộc lý do · 22 toast 409 dùng chung · 23 Công bố của tôi (19) · 30–34 JSON (lỗi, preview, nhập, hoàn tác, trùng email) · 40–43 CSV/chuẩn hóa.
Ảnh chụp **không chứa mật khẩu**; chỉ giữ ngoài Git.
Các tệp bằng chứng khác: `openapi.json`, `openapi_endpoints.txt`, `openapi_coverage_matrix.md`, `pub_details_snapshot.json` (660 bài, đọc từ DB test = bản sao teacher), các `*_fp_*.json`.
