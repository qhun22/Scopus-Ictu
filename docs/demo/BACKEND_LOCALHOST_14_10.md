# Backend + Frontend localhost — hướng dẫn trình diễn 14/10/2026

Tài liệu này **không chứa mật khẩu, token hay DSN**. Mọi bí mật nằm ngoài Git (xem mục 1).
`<DOAN>` là thư mục dự án trên máy demo (chứa **`Scopus-Ictu/`** — repository chính, branch `main` — và `_postgres_demo_14_10/`).
Các thư mục `Backend-Localhost-14-10/`, `Integration-*` chỉ là worktree trung gian, **không** dùng để chạy demo.

## 0. Hiện trạng dữ liệu (đã nghiệm thu)

| Hạng mục | Giá trị |
|---|---|
| Giảng viên | 411 hồ sơ = 410 hồ sơ ICTU (có `source_id`) + 1 hồ sơ seed (tài khoản demo, không có `source_id`) |
| Công bố Scopus | 660 bài, 1.207 tác giả Scopus, 2.751 vị trí tác giả |
| Known publications (Craw) | 327 bản ghi / 48 giảng viên (328 liên kết nguồn, 1 liên kết trùng DOI được gộp) |
| Candidate đối sánh | 40 `PENDING` (38 giảng viên, 36 tác giả Scopus), 6 candidate có bằng chứng công bố, 2 generation run `COMPLETED` |
| Danh tính `APPROVED` | **0** — chưa có review thật nào |
| Affiliation theo tác giả | 5.502 resolution (2.751 vị trí × OpenAlex/Crossref), 4.147 dòng affiliation, 217 tổ chức |
| Alembic head | `a9c2e4f71b30` |

## 1. Thành phần và nơi lưu trữ

| Thành phần | Vị trí | Ghi chú |
|---|---|---|
| Mã nguồn (Backend + Frontend) | `<DOAN>/Scopus-Ictu` (branch `main`, local) | Trong Git |
| PostgreSQL demo 17 | `<DOAN>/_postgres_demo_14_10/data`, `127.0.0.1:55432` | Cluster **riêng**, không phải service 5432 |
| Python | `<DOAN>/_venv_backend_demo_py312` (Python 3.12) | |
| Cấu hình + mật khẩu | `<DOAN>/_postgres_demo_14_10/secrets/` | **Ngoài Git**, ACL chỉ SYSTEM + chủ máy |
| Launcher | `<DOAN>/_postgres_demo_14_10/*.cmd` | Ngoài Git, không chứa mật khẩu (đọc file env lúc chạy) |
| Backup `pg_dump` | `<DOAN>/_postgres_demo_14_10/backups/` + `SHA256SUMS.txt` | Ngoài Git |

Database nghiệp vụ: `scopus_ictu_demo_teacher_20261014`.
Các database `*_test_*` chỉ dùng để thử nghiệm/ghi dữ liệu (review, restore, migration), **không** dùng để trình diễn dữ liệu thật.

## 2. Khởi động (MỘT file BAT duy nhất)

Người dùng trình diễn đồ án **chỉ cần một thao tác nhấp đúp chuột** vào file BAT gốc:

* **Bước 1**: Nhấp đúp file BAT khởi động Scopus-Ictu: **`scopus-ictu-qhun22.bat`** (nằm tại thư mục gốc repository `Scopus-Ictu/scopus-ictu-qhun22.bat`).
* **Bước 2**: Chờ hệ thống tự động kiểm tra và khởi động theo chu trình:
  - Khởi động cluster PostgreSQL demo (`127.0.0.1:55432`) nếu chưa chạy (chỉ dùng data directory của demo, không chạm service 5432).
  - Kiểm tra kết nối database `scopus_ictu_demo_teacher_20261014` và Alembic migration head.
  - Khởi động Backend demo (Uvicorn `127.0.0.1:8001`, mã nguồn chuẩn từ `Scopus-Ictu/backend`).
  - Khởi động Frontend demo (Vite `http://127.0.0.1:5173`, mã nguồn chuẩn từ `Scopus-Ictu/frontend`).
  - Kiểm tra trạng thái `/health` và proxy `/api/v1/auth/me`.
* **Bước 3**: Trình duyệt mặc định tự động mở địa chỉ: **`http://127.0.0.1:5173`**.
* **Bước 4**: Đăng nhập tài khoản **ADMIN demo** (`admin@ictu.edu.vn`) và bắt đầu trình diễn.

> **Lưu ý quan trọng:** Người dùng tuyệt đối không cần mở ba cửa sổ terminal hay chạy tay từng file CMD riêng biệt. Nếu chạy lại file BAT khi hệ thống đang chạy, launcher tự nhận diện tiến trình của demo và không khởi động trùng lặp.

### Dành cho kỹ thuật viên / Xử lý sự cố (Technical Troubleshooting Only)
Nếu cần gỡ lỗi từng thành phần riêng lẻ khi có sự cố, ba launcher nội bộ nằm tại `<DOAN>/_postgres_demo_14_10/`:
1. `start_postgres.cmd`: Khởi động riêng PostgreSQL demo 55432 (`pg_ctl ... -D <DOAN>/_postgres_demo_14_10/data`).
2. `start_demo_backend.cmd`: Khởi động riêng Backend uvicorn 8001 (kiểm tra nguồn import từ `Scopus-Ictu/backend`).
3. `start_demo_frontend.cmd`: Khởi động riêng Frontend vite 5173 (chuyển tiếp proxy `/api` → 8001).

## 3. Xác nhận đang trỏ đúng database

Dùng `psql` với `PGPASSFILE` (file ngoài Git), kết nối `-h 127.0.0.1 -p 55432`:

```sql
select current_database(), inet_server_port(), current_setting('data_directory');
-- kỳ vọng: scopus_ictu_demo_teacher_20261014 | 55432 | <DOAN>/_postgres_demo_14_10/data
select version_num from alembic_version;   -- kỳ vọng: a9c2e4f71b30
select datname, client_port from pg_stat_activity where usename = 'scopus_demo_user';
-- phiên của uvicorn phải ở database scopus_ictu_demo_teacher_20261014
```

Backend: `GET http://127.0.0.1:8001/openapi.json` phải có 52 path; schema `PublicationAuthorRead` có `affiliation_status`.

## 4. URL

* Swagger: `http://127.0.0.1:8001/docs`
* OpenAPI: `http://127.0.0.1:8001/openapi.json`
* Giao diện: `http://127.0.0.1:5173` (đăng nhập bằng email + mật khẩu).
* Đăng nhập API: `POST /api/v1/auth/login` (cookie HttpOnly).
* Tài khoản ADMIN demo: **`admin@ictu.edu.vn`** (role `ADMIN`, được cấp ngay khi tạo, không có bước phê duyệt). Mật khẩu nằm trong `secrets/demo_admin_bootstrap.env` (ngoài Git) — **không** ghi vào tài liệu/ảnh chụp màn hình.
* Tài khoản demo cũ vẫn tồn tại và không bị đổi: `admin@gmail.com` (ADMIN), `user@gmail.com` (LECTURER, dùng để minh họa 403). Mật khẩu của chúng nằm trong `secrets/seed_accounts.env`.

### Tạo (hoặc kiểm tra) tài khoản ADMIN demo

Chạy từ `Scopus-Ictu/backend` với môi trường DB demo và file `secrets/demo_admin_bootstrap.env` (`DEMO_BOOTSTRAP_ADMIN_EMAIL`, `DEMO_BOOTSTRAP_ADMIN_PASSWORD`, nạp từ ngoài Git):

```
python -m scripts.bootstrap_demo_admin --dry-run --expected-database <db> --expected-port 55432 --allow-weak-demo-password
python -m scripts.bootstrap_demo_admin --apply   --expected-database <db> --expected-port 55432 --allow-weak-demo-password
```

Script chỉ chạy khi `ENVIRONMENT=local`, DB loopback, cổng khác 5432, tên DB chứa `demo`/`test` và khớp server thật; lưu mật khẩu bằng Argon2id; idempotent; **không bao giờ** sửa tài khoản đã có (nếu email đã tồn tại nhưng không phải ADMIN hợp lệ thì báo lỗi, giữ nguyên). Cờ `--allow-weak-demo-password` chỉ cho phép mật khẩu ngắn trong script này; chính sách mật khẩu của API (≥ 8 ký tự) không bị thay đổi.

## 5. Thứ tự trình diễn (chỉ đọc trên dữ liệu thật)

| # | Nghiệp vụ | Endpoint (an toàn) | Kết quả cần thấy |
|---|---|---|---|
| 1 | Đăng nhập, phân quyền | `POST /auth/login`, `GET /auth/me` | role `ADMIN`; tài khoản LECTURER nhận **403** ở `/reviews/*`, `/publications` |
| 2 | Giảng viên | `GET /lecturers?page=1&page_size=100` | `total=411`; 410 hồ sơ có `profile_url`, 1 hồ sơ seed không có |
| 3 | JSON preview | `POST /lecturers/import/preview` với file JSON nguồn | `total 410, create 0, update 0, unchanged 410` — chỉ **xem trước**, không ghi |
| 4 | Công bố | `GET /publications?page_size=20`, `GET /publications/{eid}` | `total=660`; mỗi bài có đúng số tác giả/thứ tự như CSV Scopus |
| 5 | Affiliation theo tác giả | `GET /publications/{eid}` | xem mục 6 |
| 6 | Đối sánh | `GET /reviews/candidates?status=PENDING` | 40 `PENDING`; 6 bài có `publication_evidence_count > 0`; 5 candidate có `is_shared_scopus_author=true` |
| 6b | Giao diện hàng đợi | `http://127.0.0.1:5173/reviews` | cột "Ngữ cảnh mơ hồ" có thẻ đỏ "Tác giả Scopus dùng chung (5 giảng viên)" |
| 7 | Chi tiết candidate | `GET /reviews/candidates/{id}` | tên, Scopus ID, bằng chứng tên, `observation_id`, `candidate_version`, khối `ambiguity` |

Bài báo gợi ý cho bước 5 (EID Scopus):

| Tình huống | EID |
|---|---|
| Toàn bộ tác giả VERIFIED | `2-s2.0-105000920497` |
| Chỉ CORROBORATED | `2-s2.0-85180150665` |
| 14 tác giả | `2-s2.0-85104417112` |
| Có đúng 1 tác giả UNRESOLVED (5 tác giả còn lại CORROBORATED) | `2-s2.0-85122186355` |
| Toàn bộ UNRESOLVED (bài không có DOI) | `2-s2.0-105026360236` |
| Tác giả nhiều đơn vị / nhiều tổ chức | `2-s2.0-105032716211` |

Trên giao diện (đăng nhập ADMIN): **Trang chủ** → **Giảng viên** (411/410, tài khoản và vai trò nằm trong trang này) → **Công bố** → mở một EID ở bảng trên (cột "Đơn vị theo tác giả (nguồn ngoài) & độ tin cậy", thanh tóm tắt `VERIFIED/CORROBORATED/UNRESOLVED`, dòng `Chưa có thông tin đơn vị`) → **Duyệt đối sánh** (40 candidate, cảnh báo dùng chung Scopus Author ID). **Không bấm** Xác nhận/Từ chối/Xuất JSON/Nhập trên teacher.

### Không thực hiện trên teacher DB khi trình diễn

* `GET /lecturers/export` — **ghi** một audit event (`LECTURER_DATASET_EXPORTED`). Trình diễn export trên database test.
* `POST /lecturers/import` — thêm 410 snapshot/lần và làm đổi `source_state` của candidate.
* `POST /imports/*`, `POST /reviews/candidates/{id}/reviews` (ACCEPT/REJECT), CLI `--apply`.
* Review ACCEPT/REJECT chỉ được trình diễn trên database `*_test_*`.

## 6. Cách đọc affiliation (quan trọng)

Mỗi tác giả trong `authors[]` có:

* `affiliation_status`: `VERIFIED` | `CORROBORATED` | `UNRESOLVED` | `NOT_RECONCILED`.
* `source_has_affiliation`: `true` (nguồn liệt kê đơn vị), `false` (nguồn **không** có đơn vị), `null` (chưa xác định).
* `affiliations[]`: từng chuỗi đơn vị nguyên văn (`raw_affiliation_text`), `organizations[]` do **nguồn** chuẩn hóa, `link_status`, `source_system`, `retrieved_at`, `provenance`.
* `affiliation_resolutions[]`: kết quả đối chiếu theo từng nguồn, kể cả `unresolved_reason` (ví dụ `AUTHOR_COUNT_MISMATCH`, `NAME_MISMATCH`, `NO_EXTERNAL_WORK`, `WITHHELD_SOURCE_CONFLICT`).

Ý nghĩa mức tin cậy:

* **VERIFIED** — có chuỗi định danh ORCID → Scopus Author ID (hồ sơ ORCID công khai khai báo đúng Scopus ID của tác giả này trên bài).
* **CORROBORATED** — **chưa được xác minh**: chỉ khớp số tác giả + vị trí + tên. Không được trình bày là đã được Scopus xác nhận.
* **UNRESOLVED** — không đủ bằng chứng; **không** có đơn vị nào được gán.

Mọi affiliation có `scope = AUTHOR_ON_PUBLICATION_EXTERNAL_SOURCE`: là đơn vị của tác giả **trên bài báo** theo **nguồn metadata ngoài** (OpenAlex/Crossref). Đó **không phải**: (a) khẳng định của Scopus, (b) trường `Đơn vị` cấp bài của repository ICTU, (c) đơn vị hiện tại của giảng viên (`approved_lecturer_links`).

`affiliation_summary` đếm vị trí tác giả theo 5 nhóm loại trừ nhau. Toàn bộ 2.751 vị trí: VERIFIED có đơn vị 506, VERIFIED nguồn không có đơn vị 39, CORROBORATED có đơn vị 1.774, CORROBORATED nguồn không có đơn vị 279, UNRESOLVED 153. "474 bài có mọi tác giả VERIFIED hoặc CORROBORATED" **không** có nghĩa là 474 bài đã xác minh hoàn toàn (chỉ 13 bài mọi tác giả đều VERIFIED có đơn vị).

## 7. Dừng dịch vụ

Có hai cách dừng an toàn, không làm gián đoạn các dịch vụ khác trên máy:

* **Cách 1 (Từ cửa sổ BAT chính)**: Trong cửa sổ console của `scopus-ictu-qhun22.bat`, gõ phím **`S`** khi nhận được lời nhắc:
  `Nhan S de DUNG phan mem, K de giu phan mem chay va thoat:`
* **Cách 2 (Bằng lệnh)**: Chạy lệnh `scopus-ictu-qhun22.bat stop` từ thư mục gốc repository.
* **Cách kỹ thuật viên**: Chạy `stop_demo.cmd` trong `<DOAN>/_postgres_demo_14_10/`.

Quá trình dừng sẽ tắt Frontend, Backend và cluster PostgreSQL demo; **tuyệt đối không** đụng đến PostgreSQL service cổng 5432 hay các tiến trình không thuộc đồ án.

## 8. JSON nguồn/backup và PostgreSQL runtime

* **JSON/CSV nguồn** (`ictu_lecturers_merged.json`, CSV Scopus, thư mục Craw, thư mục khảo sát affiliation): bằng chứng đầu vào, **chỉ đọc**, có SHA-256, nằm ngoài Git.
* **JSON export/restore**: bản sao tường minh của hồ sơ giảng viên (có `source_id`), dùng để khôi phục giá trị cũ qua preview → import; không chứa mật khẩu/tài khoản; `tel` và Google Scholar không nằm trong DB nên không được xuất.
* **PostgreSQL** là dữ liệu runtime duy nhất mà API đọc. **`pg_dump`** (`backups/`) là bản sao lưu để khôi phục; đã diễn tập restore vào database mới (khớp từng dòng) mà không đụng teacher.
* Cập nhật JSON → import làm tăng snapshot (append-only) và đổi `source_state`; candidate đã sinh phải được sinh lại bằng run mới (CLI Task 08), `candidate_version` sẽ tăng.

## 9. Giới hạn đã biết

* Không có review thật: **0 danh tính APPROVED**; 40 candidate vẫn `PENDING`. 34/40 candidate chỉ dựa vào tên; 5 candidate cùng đề xuất **một** Scopus Author ID cho 5 giảng viên (cờ `is_shared_scopus_author`).
* Affiliation là dữ liệu bản chụp 09/10/2026 của OpenAlex/Crossref/ORCID; phần lớn ở mức CORROBORATED; 153 vị trí UNRESOLVED (91 vị trí thuộc 31 bài không có DOI hoặc không tìm thấy ở nguồn ngoài).
* Số điện thoại (`tel`) và Google Scholar **chưa lưu trong DB** (được ghi là `not_preserved_fields` trong JSON export).
* Tổ chức được lưu theo từng nguồn, chưa gộp xuyên nguồn.
* Hiển thị tên: chỉ riêng chuỗi hỏng `Qu?n tr? vi?n` được sửa thành `Quản trị viên` (backend + frontend); tên khác chứa `?` được giữ nguyên.
* Frontend chạy bằng Vite dev server cho buổi demo (chưa có bản triển khai production).
* Chính sách snapshot (mỗi lần import JSON thêm 410 snapshot) chưa được tối ưu.
