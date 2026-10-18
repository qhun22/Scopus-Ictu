# Release readiness — Scopus-ICTU (17/10/2026)

Tiếp nối [Final Release Gap Audit 17/10] và [`CSV_ONLY_ACCEPTANCE_20261016.md`](CSV_ONLY_ACCEPTANCE_20261016.md) (đã có phần đính chính).
Code được đánh giá: `main` @ `237f7bc` (giống `731fa8f` về code). Không sửa code, không migration App DB/demo, không tạo tag, không push.

Mức bằng chứng: **[TN]** thực nghiệm trong lượt này · **[TR]** phiên trước có bằng chứng · **[T]** đọc code · **[CK]** chưa kiểm.

---

## 1. Khôi phục PostgreSQL 55432 [TN]

| Bước | Kết quả |
|---|---|
| Trước khi khởi động | `pg_ctl status`: *no server running*. `postmaster.pid` ghi PID 17356, nhưng không có tiến trình nào mang PID đó. Mọi `postgres.exe` đang chạy đều thuộc dịch vụ 5432 (PID cha 5092/6260), không động tới. |
| `pg_controldata` | `in production` (dừng không sạch). System identifier `7694238084633166136` khớp các báo cáo trước. Checkpoint cuối `7/91C93030` khớp dòng checkpoint cuối trong log ngày 16/10. |
| Khởi động | Đúng lệnh trong `start_postgres.cmd` (`pg_ctl start -w`). Không xóa `postmaster.pid` thủ công, không reset hay tạo lại cluster. |
| Phục hồi | `redo starts at 7/91C92FA0` → `redo done at 7/91C930A8` (vài byte WAL). Checkpoint end-of-recovery xong, *ready to accept connections* lúc 04:19:04. |
| Lỗi sau khởi động | Không có lỗi hỏng dữ liệu (không có invalid page / read block / checksum). Các lỗi còn lại có nguyên nhân: (a) script kiểm kê chỉ-đọc của tôi truy vấn bảng chưa có ở DB đời cũ; (b) các ca test âm cố ý vi phạm ràng buộc trên DB pytest. |

## 2. Kiểm kê database [TN]

| Database | Alembic | Ghi chú |
|---|---|---|
| `scopus_ictu_app` (App DB) | **`c7f2a9b1d3e5` = HEAD** | 3 user ADMIN, 0 giảng viên, 660/1.207/2.751, 106 tổ chức, 5.502 resolution, 1.709 dòng đơn vị, 2 job trực tuyến (14/10). Đợt nhập CSV và áp dụng đơn vị ngày 15/10 do người dùng ADMIN thực hiện ở phiên trước. **Trạng thái CSV-only + đơn vị trực tuyến bị giới hạn 300 DOI (xem mục 5).** |
| `scopus_ictu_demo_teacher_20261014` (demo bảo vệ) | `a9c2e4f71b30` (đóng băng có chủ đích, chạy bằng bản code riêng `Backend-Localhost-14-10`) | 3 / 411 / 660 / 1.207 / 2.751 / 217 / 5.502 / 4.147 / 40 ứng viên / 0 identity / 327 known — **khớp đúng** `docs/demo/BACKEND_LOCALHOST_14_10.md`. Không bị thay đổi. |
| `scopus_ictu_test_withjson_r2_20261011` | HEAD | DB test có JSON + Craw; dùng cho ca REVIEWER ở mục 4. |
| `scopus_ictu_test_csvonly_20261011` | HEAD | DB test CSV-only của phiên 16/10. |
| `scopus_ictu_test_pytest_20261013` | HEAD | DB nằm trong allowlist của pytest. |

Tổng cộng 31 DB nghiệp vụ trên cụm; nhiều DB test cũ đang ở revision cũ, không ảnh hưởng release.

## 3. Migration App DB — đánh giá [TN/T]

- **App DB không lệch HEAD**, nên không cần migration. Ghi nhận "App DB ở `f6a1b2c3d4e5`" trong báo cáo 13/10 đã lỗi thời.
- Nếu muốn chạy code HEAD trên **DB teacher** thì cần 5 migration: `e1a2b3c4d5f6 → f6a1b2c3d4e5 → a3b7c9d1e2f4 → b5e8d2f1a4c7 → c7f2a9b1d3e5`. Cả 5 đều **additive / nới lỏng**:

| Migration | DDL | Loại | Tác động dữ liệu |
|---|---|---|---|
| `e1a2b3c4d5f6` | 4 cột nullable ở `lecturers` + CHECK `gender IS NULL OR IN (...)` | additive | không; CHECK luôn thỏa vì cột mới đều NULL |
| `f6a1b2c3d4e5` | DROP CHECK `ck_users_lecturer_account_required` | nới lỏng | không |
| `a3b7c9d1e2f4` | tạo bảng `affiliation_enrichment_jobs` | additive | không |
| `b5e8d2f1a4c7` | tạo bảng `publication_author_affiliation_overrides` | additive | không |
| `c7f2a9b1d3e5` | thêm 3 cột trạng thái/thu hồi, bỏ unique theo vị trí, thêm partial unique index ACTIVE | additive trên bảng mới (rỗng ở teacher) | không |

- Kế hoạch nếu được duyệt: `pg_dump -Fc` DB teacher → `pg_restore` sang DB tập dượt → `alembic upgrade head` trên bản tập dượt → so sánh fingerprint các bảng nghiệp vụ → chỉ khi đó mới làm trên bản thật. Rollback: khôi phục từ dump (ưu tiên), hoặc `alembic downgrade a9c2e4f71b30`.
- **Khuyến nghị: không migrate DB teacher.** Bản demo 14/10 chạy ổn bằng code đóng băng riêng. Nếu cần demo các tính năng mới (thu thập trực tuyến, hiệu chỉnh thủ công), dùng App DB hoặc DB test ở HEAD.

## 4. Bổ sung bằng chứng nghiệm thu

### 4A. UI khi DB hoàn toàn rỗng — **BLOCKED**
Không có DB ở HEAD nào hoàn toàn rỗng mà vẫn có tài khoản đăng nhập. Lệnh tạo DB test mới (`scopus_ictu_test_empty_20261017` + ghi thêm `pgpass`) bị bộ phân quyền tự động của phiên chặn. Tôi không tìm cách vượt qua. Bằng chứng hiện có vẫn chỉ là ở tầng API (`TestChartsEmptyDatabase` và các test dashboard trên schema rỗng) cùng màn hình rỗng ngày 11/10 (trước khi thêm biểu đồ / trang Home mới).

### 4B. REVIEWER Accept/Reject — **PASS (API + DB + audit)**, UI **PARTIAL** [TN]
DB `scopus_ictu_test_withjson_r2_20261011`, backend test 8199, tài khoản `withjson.reviewer@ictu.edu.vn`. Thao tác bằng script gọi đúng endpoint mà UI dùng (`POST /reviews/candidates/{id}/reviews`). Thông tin đăng nhập chỉ nằm trong script: việc đọc mật khẩu vào ngữ cảnh để gõ vào trình duyệt bị bộ phân quyền chặn.

| Ca | Candidate | Kết quả |
|---|---|---|
| Accept | `1ccefc12…` ThS. Đoàn Ngọc Phương ↔ Doan, Ngoc-Phuong (60598627700); 1 công bố hỗ trợ, không mơ hồ | 200; PENDING v1 → ACCEPTED v2; tạo identity `4b4e897a…` APPROVED; audit `CANDIDATE_ACCEPTED` + `IDENTITY_CREATED_FROM_CANDIDATE` |
| Reject | `830989d2…` ThS. Nguyễn Thị Dung ↔ Nguyen Thi, Dung; chỉ có bằng chứng tên, mơ hồ, Scopus ID dùng chung | 200; PENDING v2 → REJECTED v3; không tạo identity; audit `CANDIDATE_REJECTED` |
| Gửi lặp cùng body | cả 2 ca | trả lại đúng `review_id` cũ (idempotent), **không** tạo bản ghi review thứ hai |

Trước → sau: ứng viên 146/2/1 → 144/3/2 (PENDING/ACCEPTED/REJECTED); `candidate_reviews` 3 → 5; identity 2 → 3. Bản ghi review lưu đúng người duyệt (REVIEWER) và lý do.
**Còn thiếu:** nhìn kết quả trên UI `/reviews` và `/review-history` bằng phiên REVIEWER (cần chủ đồ án đăng nhập trên trình duyệt 5199).

### 4C. API authorization — **PASS** [TN + test tự động]
Ma trận 24 GET × 4 vai trò + 12 endpoint ghi × 3 vai trò, trên backend test 8199 (request ghi chỉ gửi bằng anon/REVIEWER/LECTURER với body rỗng; ADMIN chỉ gọi GET):

- Chưa đăng nhập: **401** (`SESSION_REVOKED`) ở mọi endpoint.
- Sai vai trò: **403** (`FORBIDDEN`). REVIEWER bị chặn ở users/audits/dashboard/imports/lecturers/affiliations/authors/export. LECTURER bị chặn thêm ở `/reviews/*`.
- Lỗi nghiệp vụ: **403 `LECTURER_NOT_LINKED`** ở `/lecturers/me/*` khi tài khoản LECTURER chưa liên kết hồ sơ (khác với `FORBIDDEN`).
- Đúng vai trò nhưng thiếu dữ liệu: **422** (REVIEWER gửi quyết định không có body).
- Mọi endpoint ghi nhạy cảm (`/system/reset`, `/users`, `/imports/scopus`, `/lecturers/import`, `/matching/*`, `/affiliations/apply|enrichment|overrides`) đều 401/403 với anon/REVIEWER/LECTURER.
- Toàn bộ test backend: **1047 passed, 0 failed** (mục 8).

## 5. M1 — phạm vi DOI trực tuyến [TN/T]

| Chỉ số (DB CSV-only, đối chiếu bằng chính `_dois_to_enrich`) | Giá trị |
|---|---|
| Công bố / không có DOI hợp lệ / DOI hợp lệ phân biệt | 660 / 25 / 635 (không có DOI trùng) |
| Cách chọn | `load_scopus_rows` sắp **EID tăng dần theo chuỗi**, giữ DOI đầu tiên gặp, cắt `[:AFFILIATION_ONLINE_MAX_DOIS_PER_RUN]`. **Tất định**: mọi job sau đều lấy lại đúng 300 DOI đó, không có offset hay cơ chế tiếp tục. |
| Đã truy vấn / có ở ≥1 nguồn / truy vấn nhưng không có | 300 / 296 / 4 |
| **Chưa từng truy vấn** | **335** |

Vị trí tác giả (2.751) theo kết quả tốt nhất:

| Loại DOI | Có đơn vị | Khớp nhưng nguồn không có đơn vị | UNRESOLVED |
|---|---|---|---|
| Có dữ liệu (296 bài) | 1.034 | 83 | 104 (thiếu chứng cứ: NAME_MISMATCH 84, AUTHOR_COUNT_MISMATCH 58, NO_EXTERNAL_AUTHOR_LIST 13, ORDER_INCONSISTENT 7, WITHHELD_SOURCE_CONFLICT 4, ID_CONFLICT 4, POSITION_CLAIMED 3 — tính theo dòng resolution) |
| Đã truy vấn, không có dữ liệu (4 bài) | 0 | 0 | 10 |
| **Chưa truy vấn (335 bài)** | 0 | 0 | **1.445** |
| Không có DOI (25 bài) | 0 | 0 | 75 |

**Vấn đề nghiệp vụ:** 1.445 vị trí (52,5%) chưa có đơn vị chỉ vì DOI chưa được truy vấn, nhưng lại mang **cùng mã `NO_EXTERNAL_WORK`** như bài thật sự không có ở nguồn. Preview gộp cả hai thành "Không có bài ở nguồn nào: 364". UI không báo cho người dùng biết job bị giới hạn 300 DOI. App DB đang ở đúng trạng thái này (2 job ngày 14/10, mỗi job 300 DOI).

Phương án:

| Phương án | Đánh giá |
|---|---|
| Tăng `AFFILIATION_ONLINE_MAX_DOIS_PER_RUN=1000` trên TEST (giới hạn `le=5000`, không sửa code) | Phủ đủ 635/635 DOI. Ước tính 15–20 phút mỗi job (300 DOI mất khoảng 7 phút). Phụ thuộc mạng ngoài và giới hạn tần suất của OpenAlex/Crossref/ORCID **lúc demo**; kết quả thay đổi theo thời gian, không tái lập được. **Chưa chạy job mới** theo yêu cầu. |
| **Bộ nguồn offline đã nghiệm thu** `_du_lieu_demo_14_10/affiliation_survey` (`AFFILIATION_SOURCE_DIR`) | Toàn vẹn: `sha256sum -c` **10/10 OK**. Phủ Crossref 635, OpenAlex 629, ORCID 605 (tải 09/10). Kết quả đã nghiệm thu 11/10: 217 tổ chức / 5.502 / 4.147; VERIFIED 545 · CORROBORATED 2.053 · UNRESOLVED 153. Tất định, không cần mạng. DB teacher demo dùng đúng bộ này. |

**Khuyến nghị demo:** dùng bộ nguồn offline (hoặc DB teacher đóng băng) cho số liệu chính thức. Thu thập trực tuyến chỉ nên trình bày như một tính năng, nói rõ giới hạn 300 DOI mỗi lần chạy và đã biết. Không dùng số liệu 106 / 1.711 của App DB làm số liệu bao phủ.

## 6. Git và cấu hình TEST [TN]

`main` @ `237f7bc`, đi trước `origin/main` 37 commit (không push).

| Tệp | Khuyến nghị |
|---|---|
| `.claude/launch.json` (M, đã được track) | Giữ cục bộ. Thêm `csvonly-backend`/`csvonly-frontend` (8299/5299, `DB_NAME` trỏ DB test, không chứa secret). Có thể commit nếu muốn lưu cấu hình test; nếu không, `git restore` sau khi kết thúc nghiệm thu. |
| `backend/scripts/create_csvonly_e2e_accounts.py` (??) | Có thể commit cùng 2 script `create_scroll_e2e_*` đã có (chỉ đọc mật khẩu từ biến môi trường, không chứa secret). |
| `backend/.tmp_csvonly_affiliation_cache/` (??, 1,7 MB metadata ngoài) | **Không commit.** Đề xuất thêm vào `.gitignore` gốc: `backend/.tmp_*/` (hoặc cụ thể hơn `backend/.tmp_*affiliation_cache/`). |
| `docs/qa/CSV_ONLY_ACCEPTANCE_20261016.md` (đã thêm phần đính chính), `docs/qa/RELEASE_READINESS_20261017.md` | Tài liệu QA, chờ chấp thuận để commit. |

Các script phục vụ nghiệm thu đặt ngoài repo, trong `_postgres_demo_14_10/scratch/` (`inventory_`, `appdb_trace_`, `authz_matrix_`, `review_decide_`, `doi_scope_20261017.py`). Mật khẩu test không xuất hiện trong báo cáo, repo hay đầu ra lệnh.

## 7. Bảng tổng hợp

| Hạng mục | Kết quả | Mức |
|---|---|---|
| Khôi phục PostgreSQL 55432 | PASS | TN |
| Dữ liệu demo (DB teacher) bảo toàn | PASS | TN |
| App DB revision = HEAD | PASS (không cần migration) | TN |
| Import CSV mới qua browser | PASS | TR (11/10) |
| UI khi DB hoàn toàn rỗng | **BLOCKED** | — |
| REVIEWER Accept/Reject (API, DB, audit, idempotent) | PASS | TN |
| REVIEWER Accept/Reject — xem trên UI | PARTIAL | CK |
| API authorization 3 vai trò + 401/403/422 | PASS | TN |
| CSV + JSON + Craw | PASS | TR (12/10, 14/10) |
| VI/EN theo vai trò | PARTIAL | TR + T |
| Phạm vi DOI trực tuyến (M1) | Đã xác minh; tồn đọng MAJOR | TN/T |
| Bộ test backend (1047 passed, 0 failed) | PASS | TN |

## 8. Bộ test backend [TN]
Code `237f7bc`, DB trong allowlist `scopus_ictu_test_pytest_20261013` (HEAD): **1047 passed, 6 skipped, 0 failed** (306 s). Có 11 cảnh báo `InsecureKeyLengthWarning`; chúng chỉ đến từ khóa giả trong test bảo mật. Bộ này gồm 22 file integration có kiểm 403 theo vai trò.

## 9. Tồn đọng

**BLOCKER:** không còn (B1 cụm DB đã khôi phục; B2 không cần migration).

**MAJOR**
- **M1** — Thu thập trực tuyến chỉ truy vấn 300/635 DOI, không tiếp tục được, mã lý do không phân biệt "chưa truy vấn" với "không có ở nguồn", UI không báo bị cắt. Xử lý cho demo: dùng bộ nguồn offline (không cần sửa code). Sửa tối thiểu sau này: hiển thị số DOI bị bỏ qua / tách mã lý do. *Không sửa trong lượt này.*
- **M2** — Chưa có bằng chứng UI khi DB rỗng sau khi thêm biểu đồ Dashboard / trang Home (mục 4A, BLOCKED).

**MINOR**
- Bước ORCID không có tín hiệu tiến độ (16/10).
- Chưa nhìn kết quả Accept/Reject trên UI bằng phiên REVIEWER.
- VI/EN mới kiểm qua browser một phần; `/login` chỉ có tiếng Việt (có chủ ý).
- Mã lỗi 401 cho người chưa đăng nhập là `SESSION_REVOKED` (chỉ là nhãn, không sai hành vi).
- Lệch giữa trí nhớ phiên làm việc và báo cáo 13/10 về revision App DB → đã đính chính.
- Tài khoản test `csvonly.e2e.*` và `withjson.*`: nên khóa hoặc đổi mật khẩu khi bàn giao.
- Thư mục cache cần luật `.gitignore`.

## 10. Đề xuất

**GO có điều kiện** để khóa phiên bản `237f7bc`, với điều kiện:
1. Kịch bản demo bảo vệ dùng DB teacher đóng băng hoặc bộ nguồn offline cho số liệu đơn vị (xử lý M1 mà không cần sửa code).
2. Chủ đồ án chấp nhận M2 là tồn đọng bằng chứng, hoặc cho phép tạo một DB test rỗng để đóng mục 4A trước khi khóa.
3. Bộ test backend ở mục 8 sạch.

---

## Đính chính và bổ sung (lượt chuẩn bị Release Candidate, 17/10)

Không sửa nội dung phía trên. Các điểm dưới đây thay thế nhận định tương ứng. Chi tiết: [`RELEASE_CANDIDATE_20261017.md`](RELEASE_CANDIDATE_20261017.md).

1. **Sai ở mục 2, 3 và 10 — "DB teacher chạy bằng bản code riêng `Backend-Localhost-14-10`":** điều này **không đúng**. `docs/demo/BACKEND_LOCALHOST_14_10.md` dòng 5 ghi các thư mục đó chỉ là worktree trung gian, không dùng để demo.
   - Launcher chính thức `scopus-ictu-qhun22.bat` → `backend/scripts/demo_launcher.py` (commit `ef625e1`, 15/10) chạy code HEAD trên **App DB `scopus_ictu_app`** (`EXPECTED_DB`, cổng 8001/5173). Launcher **tự chạy `alembic upgrade head`** khi DB chưa ở head; đây là lý do App DB đã ở `c7f2a9b1d3e5`.
   - Code HEAD **không tương thích** với DB teacher ở `a9c2e4f71b30`: model `Lecturer` đọc 4 cột (`specialization`, `gender`, `date_of_birth`, `phone`) mà DB teacher chưa có. Nếu trỏ launcher vào DB teacher thì launcher sẽ tự migrate DB đó. Vì vậy **không dùng DB teacher cho demo bản HEAD**.
2. **Bộ test backend:** chạy lại lần 2 với `-rs`: **1047 passed, 6 skipped, 0 failed** (289 s), khớp lần 1. 6 test bị skip:
   - 5 test trong `tests/unit/test_validate_ictu_lecturer_dataset.py` (dòng 33, 41, 49, 63, 83): *Canonical/Example dataset not built yet*. Bộ dữ liệu giảng viên đã được gỡ khỏi repo từ 12/10, nên bỏ qua là đúng thiết kế.
   - 1 test `tests/integration/test_generate_matching_candidates_cli.py:322`: *process settings do not point at the isolated test database*. Đây là rào chắn an toàn: `backend/.env` của tiến trình trỏ DB `withjson_r2`, không phải DB pytest. CLI sinh ứng viên đã có bằng chứng E2E qua UI ở Ưu tiên 4.
3. **Build frontend** (`tsc && vite build`) tại `237f7bc`: PASS (8,9 s). Chỉ có cảnh báo bundle JS 1,36 MB (đã nén 390 kB) lớn hơn ngưỡng 500 kB.
4. **Accept/Reject:** kết quả **chưa được xem lại trên UI** bằng phiên REVIEWER; chỉ có bằng chứng API, DB và audit.
5. **VI/EN:** **chưa test toàn bộ** qua browser. Đã kiểm `/reviews`, `/normalization?tab=matching` (15/10), `/profile` LECTURER và `/home` theo vai trò (16/10); các route khác chỉ audit tĩnh.
6. **M2** vẫn **BLOCKED**: không có DB nào ở HEAD vừa rỗng vừa có tài khoản đăng nhập. Quyền cần cấp được nêu trong báo cáo RC.

---

## Addendum 2026-10-18 (P12-B2/B3)

Tài liệu gốc phản ánh trạng thái **snapshot ngày 17/10/2026** — 1047 tests PASS (6 skip), build PASS tại `237f7bc`.

### Những gì đã thay đổi từ 17/10

| Nhóm | Nội dung | Trạng thái |
|---|---|---|
| P12-A | Full regression thêm 64 tests mới → **1111 passed, 6 skipped, 0 failed** | ✅ PASS |
| P12-A | Browser smoke 12/12 PASS (ADMIN/REVIEWER/LECTURER) | ✅ PASS |
| P12-A | App DB @ head `c7f2a9b1d3e5` — synchronized | ✅ PASS |
| P12-B0 | Radius 5px alignment: 53 replacements, 48/48 browser regression PASS | ✅ PASS |
| P11 DS | Design System R3–R4 hoàn thành: Button/Badge/PageHeader, token colors/sizes | ✅ Build clean |
| P09 | Review governance D-2 (required_reason) và D-3 (evidence_basis) | ✅ PASS |

### Những gì vẫn chưa đóng (bổ sung)

Các mục đã ghi trong tài liệu gốc (M2 BLOCKED, Accept/Reject UI PARTIAL, VI/EN chưa đầy đủ) vẫn giữ nguyên trạng thái. Thêm vào:

| Gate | Trạng thái |
|---|---|
| Security 5432 (`scopus_m12_user`) | ⚠️ OPEN — credential chưa rotate, chưa restrict listen_addresses |
| UI write-flow UI-12/13/14 | ⚠️ DEFER — không blocking RC |
| Figma nodes 5 — radius correction | ⏳ PENDING |

Tài liệu gốc (nội dung trước addendum này) KHÔNG được sửa đổi.
