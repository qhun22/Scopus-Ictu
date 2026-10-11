# Danh mục Use Case có thật (28)

> **Sinh tự động** từ `usecase_map.json` + `RBAC_API_MATRIX.json` (rút từ mã FastAPI) bởi `tools/gen_usecase_assets.py`. Mọi UC có route/API/script thật; `tools/check_consistency.py` kiểm lại quyền (actor ↔ `require_role`) và route giao diện (↔ `frontend/src/App.tsx`).

Trạng thái: **ĐÃ TRIỂN KHAI** = có đường chạy hoàn chỉnh · **MỘT PHẦN** · **CHỈ API** (chưa có UI) · **CHỈ CLI** (script, không có nút).

## Xác thực, thông báo và giám sát

| UC | Tên | Actor | API (quyền thực từ mã) | Giao diện | Trạng thái | Quan hệ UML |
|---|---|---|---|---|---|---|
| **UC-01** | Đăng nhập | ADMIN, REVIEWER, LECTURER | `POST /api/v1/auth/login` (công khai) | `/login` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-02** | Đăng xuất và kiểm tra phiên | ADMIN, REVIEWER, LECTURER | `POST /api/v1/auth/logout` (công khai)<br>`GET /api/v1/auth/me` (đã đăng nhập) | —<br><i>Menu người dùng ở Header (mọi trang)</i> | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-03** | Nhận thông báo tài khoản | ADMIN, REVIEWER, LECTURER | `GET /api/v1/notifications/unread` (đã đăng nhập)<br>`POST /api/v1/notifications/{notification_id}/read` (đã đăng nhập) | —<br><i>Cơ chế nền: lấy khi tải trang rồi hiển thị; không có trang/chuông Thông báo</i> | MỘT PHẦN (cơ chế nền) | — |
| **UC-07** | Xem nhật ký kiểm toán | ADMIN | `GET /api/v1/audits` (ADMIN) | `/audit-logs` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-26** | Khởi tạo dữ liệu và tài khoản ADMIN demo | TECH | script: `backend/scripts/bootstrap_demo_admin.py`, `backend/scripts/seed_demo_users.py`, `alembic upgrade head` | — | CHỈ CLI | — |

## Nhóm 1 — Nhập dữ liệu

| UC | Tên | Actor | API (quyền thực từ mã) | Giao diện | Trạng thái | Quan hệ UML |
|---|---|---|---|---|---|---|
| **UC-08** | Nhập hồ sơ giảng viên từ JSON (kiểm tra, xem trước, nhập) | ADMIN | `POST /api/v1/lecturers/import/preview` (ADMIN)<br>`POST /api/v1/lecturers/import` (ADMIN) | `/imports` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-08a** | Hoàn tác đợt nhập hồ sơ giảng viên | ADMIN | `POST /api/v1/lecturers/import/{import_id}/rollback` (ADMIN)<br>`POST /api/v1/imports/{import_id}/rollback` (ADMIN) | `/imports` | ĐÃ TRIỂN KHAI (UI+API) | «extend» UC-08 |
| **UC-10** | Nhập tệp CSV Scopus | ADMIN | `POST /api/v1/imports/scopus` (ADMIN)<br>`GET /api/v1/imports/config` (ADMIN)<br>`GET /api/v1/imports` (ADMIN)<br>`GET /api/v1/imports/history` (ADMIN)<br>`GET /api/v1/imports/{import_id}` (ADMIN) | `/imports` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-10a** | Quản lý đợt nhập CSV (hủy, lưu trữ, khôi phục lịch sử, xóa) | ADMIN | `POST /api/v1/imports/{import_id}/cancel` (ADMIN)<br>`POST /api/v1/imports/{import_id}/archive` (ADMIN)<br>`POST /api/v1/imports/{import_id}/restore-history` (ADMIN)<br>`DELETE /api/v1/imports/{import_id}` (ADMIN) | `/imports` | ĐÃ TRIỂN KHAI (UI+API) | «extend» UC-10 |
| **UC-25** | Nạp công bố đã biết (Craw) và đơn vị công tác ngoài (OpenAlex/Crossref) | TECH | script: `backend/scripts/ingest_craw_known_publications.py`, `backend/scripts/import_author_affiliations.py` | — | CHỈ CLI | — |

## Nhóm 2 — Quản lý hồ sơ tác giả/giảng viên

| UC | Tên | Actor | API (quyền thực từ mã) | Giao diện | Trạng thái | Quan hệ UML |
|---|---|---|---|---|---|---|
| **UC-05** | Quản lý hồ sơ giảng viên | ADMIN | `GET /api/v1/lecturers` (ADMIN)<br>`GET /api/v1/lecturers/master` (ADMIN)<br>`POST /api/v1/lecturers` (ADMIN)<br>`PATCH /api/v1/lecturers/{lecturer_id}` (ADMIN)<br>`PUT /api/v1/lecturers/{lecturer_id}` (ADMIN)<br>`DELETE /api/v1/lecturers/{lecturer_id}` (ADMIN)<br>`DELETE /api/v1/lecturers/unlinked/cleanup` (ADMIN) | `/lecturers` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-06** | Quản lý tài khoản và phân quyền | ADMIN | `GET /api/v1/users` (ADMIN)<br>`GET /api/v1/users/{user_id}` (ADMIN)<br>`PATCH /api/v1/users/{user_id}` (ADMIN)<br>`POST /api/v1/users/{user_id}/lock` (ADMIN)<br>`POST /api/v1/users/{user_id}/unlock` (ADMIN)<br>`POST /api/v1/users/{user_id}/reset-password` (ADMIN)<br>`GET /api/v1/auth/users` (ADMIN) | `/lecturers`<br><i>Nằm trong cửa sổ Chi tiết giảng viên; /users chuyển hướng sang /lecturers; GET /auth/users là bí danh cũ (deprecated)</i> | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-16** | Xem tác giả Scopus (danh sách, thống kê, chi tiết) | ADMIN | `GET /api/v1/authors` (ADMIN)<br>`GET /api/v1/authors/stats` (ADMIN)<br>`GET /api/v1/authors/{author_id}` (ADMIN) | `/normalization`<br><i>Tab 'Tác giả'; chi tiết tác giả chưa có nút trên UI</i> | MỘT PHẦN (UI chưa có chi tiết) | — |
| **UC-20** | Xem hồ sơ cá nhân | LECTURER | `GET /api/v1/lecturers/me/profile` (LECTURER) | `/profile` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-21** | Xem liên kết Scopus đã duyệt của tôi | LECTURER | `GET /api/v1/lecturers/me/identities` (LECTURER) | `/identity` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-23** | Quản trị xem hồ sơ/danh tính/công bố Scopus của một giảng viên | ADMIN | `GET /api/v1/lecturers/{lecturer_id}/scopus/profile` (ADMIN)<br>`GET /api/v1/lecturers/{lecturer_id}/scopus/identities` (ADMIN)<br>`GET /api/v1/lecturers/{lecturer_id}/scopus/publications` (ADMIN) | — | CHỈ API (chưa có UI) | — |

## Nhóm 3 — Quản lý công bố

| UC | Tên | Actor | API (quyền thực từ mã) | Giao diện | Trạng thái | Quan hệ UML |
|---|---|---|---|---|---|---|
| **UC-13** | Xem danh sách và chi tiết công bố (kèm đơn vị theo tác giả, nguồn gốc dòng CSV) | ADMIN, REVIEWER | `GET /api/v1/publications` (ADMIN/REVIEWER)<br>`GET /api/v1/publications/{eid}` (ADMIN/REVIEWER) | `/publications`, `/publications/:eid` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-22** | Xem công bố của tôi (từ danh tính APPROVED) | LECTURER | `GET /api/v1/lecturers/me/publications` (LECTURER) | `/my-publications` | ĐÃ TRIỂN KHAI (UI+API) | — |

## Nhóm 4 — Chuẩn hóa, đối soát và phê duyệt

| UC | Tên | Actor | API (quyền thực từ mã) | Giao diện | Trạng thái | Quan hệ UML |
|---|---|---|---|---|---|---|
| **UC-11** | Chuẩn hóa công bố từ bản ghi thô | ADMIN | `POST /api/v1/imports/{import_id}/normalize` (ADMIN) | `/normalization` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-12** | Bóc tách tác giả Scopus | ADMIN | `POST /api/v1/authors/normalize-import/{import_id}` (ADMIN) | `/normalization` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-24** | Sinh ứng viên đối sánh (lưu bền, idempotent) | TECH | script: `backend/scripts/generate_matching_candidates.py` | — | CHỈ CLI | — |
| **UC-17** | Xem hàng đợi ứng viên và bằng chứng | ADMIN, REVIEWER | `GET /api/v1/reviews/candidates` (ADMIN/REVIEWER)<br>`GET /api/v1/reviews/candidates/{candidate_id}` (ADMIN/REVIEWER) | `/reviews` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-18** | Duyệt ứng viên (ACCEPT / REJECT) | ADMIN, REVIEWER | `POST /api/v1/reviews/candidates/{candidate_id}/reviews` (ADMIN/REVIEWER) | `/reviews` | ĐÃ TRIỂN KHAI (UI+API) | «include» UC-17 |
| **UC-19** | Xem lịch sử review | ADMIN, REVIEWER | `GET /api/v1/reviews/history` (ADMIN/REVIEWER) | `/review-history` | ĐÃ TRIỂN KHAI (UI+API) | — |

## Nhóm 5 — Tìm kiếm, thống kê và xuất dữ liệu

| UC | Tên | Actor | API (quyền thực từ mã) | Giao diện | Trạng thái | Quan hệ UML |
|---|---|---|---|---|---|---|
| **UC-14** | Tra cứu tổng hợp (giảng viên, công bố, tác giả) | ADMIN, REVIEWER | `GET /api/v1/search` (ADMIN/REVIEWER) | `/search` | ĐÃ TRIỂN KHAI (UI+API) | — |
| **UC-04** | Xem thống kê tổng quan (dashboard) | ADMIN | `GET /api/v1/dashboard/summary` (ADMIN) | `/dashboard` | MỘT PHẦN (chỉ số đếm; biểu đồ giữ chỗ) | — |
| **UC-15** | Xuất dữ liệu công bố ra JSON | ADMIN | `GET /api/v1/publications/export` (ADMIN) | `/publications`<br><i>Nút Xuất JSON ở trang Công bố</i> | ĐÃ TRIỂN KHAI (UI+API); chỉ JSON | — |
| **UC-09** | Xuất hồ sơ giảng viên ra JSON | ADMIN | `GET /api/v1/lecturers/export` (ADMIN) | `/lecturers`<br><i>Nút Xuất JSON ở trang Giảng viên</i> | ĐÃ TRIỂN KHAI (UI+API); chỉ JSON | — |

## Không phải use case nghiệp vụ (đã loại có chủ đích)

- `GET /health` — healthcheck hạ tầng, không phải nghiệp vụ
- `GET /api/v1/lecturers/ping` — healthcheck giữ chỗ M2.3
- `GET /api/v1/matching/ping` — giữ chỗ M0 ('matching-stub'), không phải nghiệp vụ
- `/tasks` (trang giữ chỗ `NOT_IMPLEMENTED`), `/users` (chuyển hướng sang `/lecturers`), `DiffViewerStub` (không được dùng).
