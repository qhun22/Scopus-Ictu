# Remediation Verification & Isolated Test Preparation — Scopus-ICTU (17/10/2026)

Release `v1.0.0-rc.1`: **HOLD**.
Code nền `237f7bc`; 4 file RC đã stage giữ nguyên blob (`fb176d6`, `853c832`, `3b03317`, `0c34a85`); 6 file frontend đã sửa (unstaged, +44 / −37) giữ nguyên.
Không commit, tag, push, migration; không ghi DB nghiệp vụ; không tạo DB; không restore.
Mức bằng chứng: **VR** runtime · **VS** đọc code / log.

---

## 1. Browser regression — UI-01 / UI-02 / UI-03 / UX-01 (VR)

**Phiên:** chủ đồ án **cấp phép rõ ràng** (17/10) cho script Chrome headless đọc `secrets/backend_test_withjson.env` (chỉ tài khoản TEST `withjson.*`).
- Đăng nhập qua form `/login`; giá trị không in, không lưu.
- Môi trường A (5199 → 8199 → `scopus_ictu_test_withjson_r2_20261011`).
- Script: `_postgres_demo_14_10/scratch/ui_e2e_cdp_pass3_20261017.py`. Bằng chứng: `scratch/ui_e2e_20261017/pass3/` (ảnh + `results_pass3.json`).

**Bảo đảm chỉ đọc:**
- 0 request không phải GET (ngoài login), 0 lỗi API, 0 lỗi console.
- Fingerprint DB A (Alembic, số dòng + md5 nội dung 14 bảng) trước và sau **giống hệt**.
- Profile Chrome tạm đã xóa, không còn tiến trình headless.
- Quét 73 tệp bằng chứng: 0 giá trị bí mật. 1 lần khớp mẫu token là dương tính giả: chuỗi `access_token=` được nhắc nguyên văn trong báo cáo trước.

| ID | Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|---|
| UI-01 ADMIN | `/home` VI: không còn "Chưa có dữ liệu" / "Đang chờ kết nối"; nhãn "Xem hàng đợi", "Xem lịch sử", "Xem danh mục"; link `/lecturers`, `/publications`, `/reviews`, `/imports`, `/dashboard`, `/audit-logs` | **PASS** | `U01_ADMIN_home_VI.png` |
| UI-01 ADMIN EN | Đổi EN + F5: `lang=en`; "Open queue", "View history", "View directory", "View catalog"; 0 nhãn giả | **PASS** | `U01_ADMIN_home_EN.png` |
| UI-01 REVIEWER | VI: "Xem hàng đợi" → `/reviews`, "Xem lịch sử" → `/review-history`; EN: "Open queue", "View history"; 0 nhãn giả | **PASS** | `U01_REVIEWER_*` |
| UI-01 LECTURER (chưa liên kết) | VI: "Xem thông tin" → `/profile`, "Xem công bố" → `/my-publications`, "Xem liên kết" → `/identity`; EN: "View publications", "View links"; 0 nhãn giả; không vỡ bố cục | **PASS** | `U01_LECTURER_*` |
| UI-02 nhãn | KPI "**Ứng viên chờ duyệt** 144"; khối "**Liên kết định danh Scopus**" + dòng giải thích ("…được đếm riêng ở thẻ 'Ứng viên chờ duyệt'"); "CHỜ XÁC LẬP 0 · ĐÃ DUYỆT 3 · BỊ TỪ CHỐI 0 · BỊ THU HỒI 0" | **PASS** | `U02_dashboard_VI.png` |
| UI-02 số liệu | 660 / 410 / 410 / 1.207 / 144; identity 0 / 3 / 0 / 0 — **không đổi** so với các lượt trước và khớp DB | **PASS** | `results_pass3.json` |
| UI-02 EN | "Candidates awaiting review", "Scopus identity links", "…counted separately…" | **PASS** | `U02_dashboard_EN.png` |
| UI-02 trạng thái lỗi | Chặn riêng `/api/v1/dashboard/charts` trong trình duyệt → "Không thể kết nối đến máy chủ…" + nút **"Thử lại"**, phần còn lại của trang vẫn hiển thị | **PASS** | `U02_dashboard_charts_error.png` |
| UI-02 trạng thái loading | Giả lập trễ 2,5 s cho **mọi** request làm chậm cả module JS của Vite dev → ảnh trắng toàn trang (artefact của cách đo). Nhánh loading có trong code (`Dashboard/index.tsx:286`, VS) | **PARTIAL** (đo lại bằng cách chỉ trễ `/api/*`) | `U02_dashboard_loading.png` |
| UI-02 mobile 375 px | Không tràn ngang (`overflowX = 0`) | **PASS** | `U02_dashboard_mobile_identity.png` |
| UI-03 VI / EN | Panel "1. Nguồn dữ liệu đơn vị": "Chưa gắn bộ nguồn offline với máy chủ, nên chưa thể Xem trước / Áp dụng một lần đối chiếu mới…" + "**Dữ liệu đơn vị đã áp dụng trước đó vẫn được giữ nguyên** (xem mục 2)" + dòng nhỏ cho người vận hành; mục 2 vẫn "660 công bố · 2.751 vị trí tác giả · 217 tổ chức · 4.147 dòng đơn vị"; **không còn** câu "Thu thập trực tuyến chưa được bật"; nút "Xem trước" vẫn hiện (không che chức năng); `.env` môi trường A **không sửa** | **PASS** | `U03_affiliations_VI.png`, `_EN.png` |
| UX-01 desktop | 2 công bố mẫu, 20 badge: **cao 23 px**, `padding 10px / 10px`, `border-radius 9999px`, 11 px / 700; rộng theo nội dung (VI: "Đã xác minh định danh" 138 px, "Đã đối chiếu · Chưa xác minh" 168 px); **0 badge bị cắt**; hàng thiếu đơn vị (#3, #5) giờ cùng cỡ với hàng có đơn vị | **PASS** (khớp Figma `5:34`) | `X01_2-s2.0-105000836388_VI.png`, `…434624_VI.png` |
| UX-01 EN | "Identity verified" 106 px, "Cross-checked · Not verified" 166 px; cao 23 px | **PASS** | `X01_836388_EN.png` |
| UX-01 mobile 375 px | Trang không tràn ngang; 10 badge cao 23 px, không cắt | **PASS** | `X01_836388_mobile.png` |

**Quan sát (P3, không chặn):**
- Hàng #6 ở `2-s2.0-105000836388`: badge lớn hơn làm dòng văn bản đơn vị dài xuống dòng (`flex-wrap`), không bị cắt.
- Panel đơn vị vẫn có hai mục cùng số "2." (UI-12, đã ở backlog).

## 2. Backup và điều kiện restore

| Hạng mục | Kết quả |
|---|---|
| Tệp | `_postgres_demo_14_10\backups\withjson_r2_demoA_20261017_144128.dump` — 2.037.848 byte, mtime 14:41:29 (**không đổi**) |
| SHA-256 | `0681e42eb51cfcfde502ec367e261c503f0439260604efe45cedaf2fc2d2103a` — `sha256sum -c` **OK** |
| Định dạng | Header `PGDMP`; `pg_restore --list`: Format CUSTOM, gzip, Dump Version 1.16-0, `dbname: scopus_ictu_test_withjson_r2_20261011`, PG 17.10 / pg_dump 17.10, **193 TOC entries**: 27 TABLE, 27 TABLE DATA, 43 CONSTRAINT, 34 FK CONSTRAINT, 57 INDEX |
| Extension | Nguồn chỉ có `plpgsql` (có sẵn) → restore bằng `scopus_demo_user` không vướng quyền extension |
| Mốc so sánh nguồn | `scratch/fingerprint_demoA_source_20261017.json` (Alembic `c7f2a9b1d3e5`, 27 bảng, 14 bảng với số dòng + md5 nội dung: publications 660, publication_authors 2.751, scopus_authors 1.207, lecturers 410, candidates 149, candidate_reviews 5, identities 3, identity_evidence 21, resolutions 5.502, affiliations 4.147, organizations 217, known_publications 327, users 8, audit_events 22) |
| **Restore** | **CHƯA chạy** — chờ phê duyệt; tệp dump **không** được gọi là "restore verified" |

**Kế hoạch restore có kiểm soát (chờ duyệt):**
- DB đích: `scopus_ictu_test_restore_demoA_20261017` (chưa tồn tại); UTF8, `LC_COLLATE` / `LC_CTYPE` = `C` như nguồn; cụm 127.0.0.1:55432.
- Xác thực:
  - Tạo DB: `demo_admin` (superuser, đã có trong `pgpass.conf`; `scopus_demo_user` không có CREATEDB).
  - Restore: `scopus_demo_user` qua credential của backend (như lượt backup).
- Lệnh (một script có kiểm tra cổng 55432, data_directory, tên DB, DB chưa tồn tại, không phải DB teacher):
  1. `CREATE DATABASE scopus_ictu_test_restore_demoA_20261017 OWNER scopus_demo_user ENCODING 'UTF8' TEMPLATE template0 LC_COLLATE 'C' LC_CTYPE 'C'` + `REVOKE ALL … FROM PUBLIC` (mẫu `tools/create_mig_db.py`, **không** ghi thêm `pgpass`).
  2. `sha256sum -c` tệp dump.
  3. `pg_restore -h 127.0.0.1 -p 55432 -U scopus_demo_user -d scopus_ictu_test_restore_demoA_20261017 --no-owner --role=scopus_demo_user --exit-on-error <dump>`.
  4. `python scratch/db_fingerprint_20261017.py scopus_ictu_test_restore_demoA_20261017 fingerprint_restore.json` → so sánh JSON với mốc nguồn; **chỉ PASS khi giống hệt**.
- Hoàn tác: DB rehearsal là DB TEST mới; nếu lỗi, chỉ xóa đúng DB đó (cần duyệt riêng).

## 3. Sự cố môi trường dừng — kết luận

| Giả thuyết | Bằng chứng | Kết luận |
|---|---|---|
| Crash PostgreSQL | Không có `PANIC` / `FATAL` / lỗi đọc trang; 3 lần khởi động (16/10 13:06, 17/10 04:19, 14:39) đều "not properly shut down" → redo vài byte WAL → ready; log trước mỗi lần dừng là hoạt động bình thường (checkpoint, kết nối) | **Không phải crash** |
| Shutdown có chủ đích (`pg_ctl stop`, launcher `stop`) | Không có "received fast shutdown request"; `launcher.log` không có "Da dung" từ 11/10 | **Không phải** |
| Tiến trình bị chấm dứt cùng phiên Claude Desktop | (1) Cây tiến trình hiện tại: uvicorn 8199 và Vite 5199 là **con trực tiếp của `Claude.exe`** (`C:\Program Files\WindowsApps\Claude_…\Claude.exe`, ứng dụng MSIX); postgres 55432 có tiến trình cha là shell công cụ của phiên (đã thoát). (2) `Claude.exe` hiện tại khởi động **14:37:23** — nằm giữa dòng log cuối của cụm (08:08:59) và lần khởi động lại (14:39:42). (3) Dừng kiểu "TerminateProcess" khớp với dấu hiệu không có log shutdown. Không tìm thấy sự kiện AppX cho thời điểm cụ thể | **LIKELY** (bằng chứng gián tiếp mạnh), **chưa VERIFIED** thời điểm |
| Launcher đóng tiến trình con | Launcher tách tiến trình bằng `DETACHED_PROCESS \| NEW_PROCESS_GROUP`; không có log dừng | Không phải |
| Backend 8001 (05:09 ngày 17/10) | Backend chết nhưng frontend 5173 (cùng launcher) sống tiếp → không khớp kiểu "cả cây bị giết" | **UNKNOWN** |
| Mất kết nối do proxy / frontend | Đây là **hệ quả** (Vite báo `ECONNREFUSED` khi backend đã chết), không phải nguyên nhân | — |

**Quy trình vận hành demo đề xuất (PA-0, chạy từ cửa sổ CMD / PowerShell riêng của chủ đồ án, KHÔNG từ terminal hay công cụ trong Claude Desktop):**
1. **PostgreSQL:** `"C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" status -D D:\DataFolder\ProjectIctu\DoAn\_postgres_demo_14_10\data`. Nếu không chạy và không có tiến trình nào giữ `postmaster.pid` → `start_postgres.cmd`. **Không** đụng cổng 5432.
2. **Kiểm tra DB trước khi phục vụ (chỉ đọc):** trong `Scopus-Ictu\backend`: `..\..\_venv_backend_demo_py312\Scripts\python.exe ..\..\_postgres_demo_14_10\scratch\db_fingerprint_20261017.py scopus_ictu_test_withjson_r2_20261011` → kỳ vọng `alembic = c7f2a9b1d3e5`, publications 660, lecturers 410. Sai → **dừng, không migrate**.
3. **Backend:** `..\..\_venv_backend_demo_py312\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8199` → `curl http://127.0.0.1:8199/health` = 200.
4. **Frontend:** trong `Scopus-Ictu\frontend`: `set VITE_API_PROXY_TARGET=http://127.0.0.1:8199` → `npm run dev -- --port 5199` → mở `http://localhost:5199` (không dùng `127.0.0.1:5199`); `curl -I http://localhost:5199/` = 200.
5. **Khi demo:** lỗi API → xem cửa sổ backend; chỉ khởi động lại backend. **Không** chạy `scopus-ictu-qhun22.bat`, **không** chạy `alembic`.
6. **Tắt có kiểm soát:** Ctrl+C frontend → Ctrl+C backend → `pg_ctl stop -D …\data -m fast` (hoặc `stop_demo.cmd`, vốn chỉ dừng 5173 / 8001 / cụm demo).

## 4. Kế hoạch TC-W1 / TC-W2 (chưa chạy — sau khi restore được duyệt và PASS)

- **Môi trường:** DB `scopus_ictu_test_restore_demoA_20261017`; backend **8399** (`DB_NAME` override, cùng code); frontend **5399** proxy → 8399; thêm 2 cấu hình preview cục bộ.
- **Xác thực:** tài khoản TEST `withjson.*` có trong bản sao (cùng băm mật khẩu) → dùng cùng cấp phép script như mục 1.
- **TC-W2:** cần đặt lại mật khẩu `vu.duc.quang.test` **trên bản sao** (ADMIN `POST /users/{id}/reset-password`), lưu mật khẩu ngẫu nhiên vào `secrets/backend_test_restore_demoA.env` (ngoài Git) — **cần duyệt riêng**.

| TC | Dữ liệu (bản sao) | Thao tác ghi | Expected | Bằng chứng |
|---|---|---|---|---|
| W1a ACCEPT | Ứng viên PENDING có `publication_support_count ≥ 1`, không mơ hồ, không dùng chung (chọn bằng truy vấn chỉ đọc trên bản sao) | REVIEWER: Xem chi tiết → "Xác nhận đối sánh" → lý do → xác nhận | +1 review ACCEPT, candidate ACCEPTED (version + 1), +1 identity APPROVED, audit `CANDIDATE_ACCEPTED` + `IDENTITY_CREATED_FROM_CANDIDATE`; bấm lại → idempotent, không tạo bản ghi | Ảnh trước / sau, `POST …/reviews` 200 + body, fingerprint bảng liên quan trước / sau, audit |
| W1b REJECT | 1 trong 3 ứng viên PENDING ThS. Nguyễn Thị Dung ↔ `59253245500` (chỉ tên, dùng chung) | "Từ chối" **không** lý do → bị chặn; có lý do → OK | +1 review REJECT, candidate REJECTED, 0 identity, +1 audit | Như trên |
| W1c Ràng buộc | Ứng viên PENDING khác ↔ `59253245500` (đã APPROVED cho PGS.TS.) | "Xác nhận đối sánh" | **409** `SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER`; UI hiện thông điệp đã dịch (`ApprovalQueue:76`); DB không đổi | Mạng + fingerprint |
| W2 LECTURER đã liên kết | `vu.duc.quang.test` (TS. Vũ Đức Quang, identity `57193082389`, 27 công bố) | Reset mật khẩu (bản sao) | `/home` nhãn trung tính; `/my-publications` = 27 bài; `/profile` đúng hồ sơ; `/identity` hiện `57193082389`; mở 1 chi tiết công bố; `/reviews`, `/dashboard`, `/lecturers` → `/home`; VI / EN | Ảnh, API, DB |

## 5. Contract D-2 / D-3 (chờ duyệt — chưa triển khai)

### D-2 — Lý do quyết định

| Điểm | Contract |
|---|---|
| Bắt buộc lý do | REJECT (như cũ); **ACCEPT** khi observation hiện hành **không có bằng chứng `PUBLICATION`**, **hoặc** Scopus author có ứng viên cho > 1 giảng viên (`is_shared_scopus_author`), **hoặc** giảng viên có > 1 ứng viên (`is_ambiguous`) |
| Rỗng | `reason.strip() == ""` coi như thiếu |
| Backend | `_accept`: kiểm tra **sau bước 3 (idempotent)** và **sau bước 8 (đã nạp bằng chứng)**, trước khi tạo identity; lớp lỗi mới `ReasonRequiredForWeakEvidenceError(InvalidReviewReasonError)` với `code = "REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE"` → **422** qua ánh xạ sẵn có (`reviews.py:205-225`) |
| Frontend | Modal quyết định: hiện dấu "bắt buộc" và nút xác nhận bị vô hiệu cho tới khi có lý do, khi `publication_evidence.length === 0 \|\| ambiguity.is_shared_scopus_author \|\| ambiguity.is_ambiguous`; ánh xạ mã lỗi mới vào bảng thông điệp `approvalQueue` (VI / EN) |
| Lịch sử | Không sửa 3 quyết định cũ không có lý do; **replay** một quyết định đã có vẫn trả `idempotent=true` (kiểm tra xảy ra sau bước idempotent) |
| Không đổi | Schema / CHECK DB, quyền ADMIN / REVIEWER, mức tin cậy (lý do không nâng mức tin cậy) |
| Test | Unit: ACCEPT chỉ tên không lý do → lỗi; có lý do → OK; ACCEPT có công bố, không mơ hồ, không lý do → OK; shared không lý do → lỗi; ambiguous không lý do → lỗi; khoảng trắng → lỗi; replay → idempotent. Integration API: 422 + `code`. Frontend: build + UI kiểm trên bản sao |

### D-3 — Mức chứng cứ trên liên kết giảng viên

| Điểm | Contract |
|---|---|
| Nguồn chứng cứ | `identity_evidence.evidence_type` của identity `APPROVED` (đã có: `NAME_SIMILARITY`, `DOI_EXACT`, `PUBLICATION_OVERLAP`) |
| Mức chứng cứ (trường mới, tùy chọn) | `evidence_basis: "NAME_ONLY" \| "PUBLICATION" \| "NAME_AND_PUBLICATION" \| null` trên `PublicationLecturerLinkRead` |
| Trạng thái review | Luôn là "đã được người duyệt chấp nhận" (identity APPROVED); có thể thêm `reviewed_at` |
| Hiển thị | Tiêu đề "Liên kết giảng viên đã duyệt" / "Approved lecturer links"; nhãn cạnh mỗi liên kết: "Duyệt theo tên" (NAME_ONLY), "Có công bố hỗ trợ" (PUBLICATION / NAME_AND_PUBLICATION); tooltip "Được người duyệt chấp nhận — không phải xác minh định danh độc lập"; **không** dùng "xác minh định danh"; ORCID ghi rõ "ORCID hồ sơ giảng viên" |
| Thiếu dữ liệu | `evidence_basis = null` → nhãn trung tính "Chưa rõ mức chứng cứ" |
| Tương thích API | Trường mới **tùy chọn** (additive), client cũ không vỡ; `_for_role` vẫn ẩn với LECTURER như hiện tại; không đổi schema DB |
| Figma | Cần thêm variant *source / evidence badge* (dạng gọn như "Crossref / OpenAlex", không phải pill status) cho "Duyệt theo tên" / "Có công bố hỗ trợ"; và variant *status badge* (pill 23 px) cho 4 mức tin cậy đơn vị (đã áp dụng ở UX-01) |
| Test | Integration `GET /publications/{eid}` cho 3 loại + null; UI VI / EN |

D-4 REOPEN: giữ ở backlog thiết kế (`CONTROLLED_REMEDIATION_20261017.md` §3).

## 6. Launcher PA-1 — patch và kiểm thử còn thiếu

- **Tệp phải đổi khi được duyệt:** `backend/scripts/demo_launcher.py` (43 dòng); thêm `backend/tests/unit/test_demo_launcher_pa1.py` (7 test). `scopus-ictu-qhun22.bat` **không** cần đổi (đã có `migrate`). Cập nhật `docs/demo/BACKEND_LOCALHOST_14_10.md` (tài liệu cũ).
- **Đã xác minh trên bản sao** (`scratch/launcher_pa1/`, diff `PA1.diff`): 15 / 15 test PASS. Launcher trong repo **giống hệt** bản gốc (`cmp`).
- **Đáp ứng yêu cầu:** `start` lệch revision → dừng an toàn, không migrate / backup / khởi động backend; `migrate` → chặn DB teacher → `pg_dump -Fc` + sha256 (lỗi → không migrate) → `alembic upgrade head` → kiểm tra lại. Không đổi `start` khi schema khớp, `stop`, `status`, cổng, tệp env.
- **Tinh chỉnh đề xuất trước khi áp:**
  - (a) `migrate` kiểm tra revision trước; nếu đã ở head → báo "không cần migrate", **không** backup.
  - (b) Thông điệp sau backup ghi rõ "đây là bản sao lưu, chưa restore thử".
- **Kiểm thử còn thiếu:**
  - (1) Chạy test cũ + mới trong repo với `TEST_DATABASE_URL` allowlist (conftest bắt buộc).
  - (2) Tích hợp thật trên DB TEST cô lập: `start` với DB lệch revision (vd một DB test ở `a9c2e4f71b30` **không** phải DB teacher) → phải dừng.
  - (3) `migrate` trên bản sao DB → tạo dump + sha256 + upgrade.
  - (4) `migrate` với `DB_NAME` = DB teacher → bị từ chối, không có tệp dump.

## 7. Git

- Nhánh `main`, HEAD `237f7bc`, đi trước `origin/main` 37 commit.
- Staged: 4 file RC (blob không đổi).
- Unstaged (6 file frontend, +44 / −37) — không đổi trong phiên này: `frontend/src/i18n/locales/vi.ts`, `en.ts`, `frontend/src/i18n/types.ts`, `frontend/src/pages/Dashboard/index.tsx`, `frontend/src/pages/Normalization/AffiliationsTab.tsx`, `frontend/src/pages/Publications/AuthorAffiliations.tsx`.
- `.claude/launch.json` (M, cục bộ).
- Untracked: `backend/scripts/create_csvonly_e2e_accounts.py` và 5 báo cáo QA (`PRE_RELEASE_QUALITY_AUDIT`, `ACTOR_UI_ACCEPTANCE`, `DATA_INTEGRITY_DEMO_SAFETY`, `CONTROLLED_REMEDIATION`, `REMEDIATION_VERIFICATION` — tệp này — cùng ngày 17/10).
- Ngoài repo: dump + sha256 (`backups\`), script / bằng chứng (`scratch\`).

## 8. Blocker thực tế trước khi sang Design System

| # | Blocker | Loại | Cần |
|---|---|---|---|
| 1 | **Chưa có restore rehearsal** → chưa có phương án khôi phục *đã kiểm chứng* cho DB A | Phê duyệt | Cho phép tạo `scopus_ictu_test_restore_demoA_20261017` (`demo_admin`) + `pg_restore` + so fingerprint |
| 2 | **TC-W1 / TC-W2 chưa chạy** (Accept / Reject qua UI; LECTURER đã liên kết) | Phụ thuộc #1 + phê duyệt ghi trên bản sao + reset mật khẩu trên bản sao | Phê duyệt §4 |
| 3 | **Môi trường demo không ổn định nếu khởi động từ phiên Claude** | Vận hành | Áp dụng quy trình PA-0 (§3), chạy từ cửa sổ riêng của chủ đồ án |
| 4 | Thay đổi UI P1 **chưa commit** | Phê duyệt | Duyệt commit 6 file frontend (đã có browser regression PASS) |
| 5 | D-2 / D-3 / PA-1 | Phê duyệt contract / patch | §5, §6 |

Không phải blocker: UI-02 loading (đo lại khi tiện), quan sát P3 ở §1, UI-12.
