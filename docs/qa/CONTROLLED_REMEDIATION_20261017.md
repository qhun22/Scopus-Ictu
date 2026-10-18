# Controlled Remediation — Data Governance, UI P1 & Demo Safety (17/10/2026)

Release `v1.0.0-rc.1`: **HOLD**.
Code nền: `237f7bc`; 4 file RC đã stage giữ nguyên (`fb176d6`, `853c832`, `3b03317`, `0c34a85`).
Không commit, tag, push, migration; không ghi DB nghiệp vụ.
Mức bằng chứng: **VR** runtime · **VS** đọc code.

## 0. Sự cố môi trường trong phiên (VR)

Khi bắt đầu, cụm PostgreSQL 55432 **lại đang tắt**:
- Log dừng ở checkpoint 08:08:59, không có dòng shutdown, trạng thái `in production`, PID 16712 không còn.
- Các server 8199 / 5199 cũng đã dừng.

Đã kiểm tra không còn tiến trình nào giữ data directory, rồi khởi động bằng `pg_ctl start -w` (cùng quy trình chuẩn đã dùng trước đó). Cụm tự phục hồi WAL sạch lúc 14:39:57.

DB A sau khi khởi động **trùng khớp snapshot** trước đó (11 bảng nghiệp vụ, audit cuối, `max(updated_at)` của users), Alembic `c7f2a9b1d3e5`.

**Phát hiện vận hành:** mọi tiến trình khởi động từ shell công cụ của phiên làm việc đều bị dừng cưỡng bức khi phiên kết thúc hoặc khởi động lại: cụm Postgres (bật lúc 04:19), các preview server 8199 / 5199, và nhiều khả năng cả backend 8001. Cho buổi demo, **chủ đồ án phải tự khởi động** cụm và server từ cửa sổ của mình (PA-0), không dựa vào tiến trình do công cụ bật.

## 1. OPS-01 — Backup và restore verification

| Bước | Kết quả | Bằng chứng |
|---|---|---|
| DB nguồn | `scopus_ictu_test_withjson_r2_20261011` @ 127.0.0.1:55432, owner `scopus_demo_user`, Alembic `c7f2a9b1d3e5` | VR |
| Xác thực | Dùng **chính credential DB của backend** (`app.core.config.settings`, nạp từ `backend/.env`, như mọi truy vấn chỉ đọc trước đây), truyền cho tiến trình con qua biến môi trường; **không in**; **không** sửa `pgpass.conf`; **không** đọc tệp secrets tài khoản TEST | VS (script `_postgres_demo_14_10/scratch/backup_demoA_20261017.py`) |
| Dump | `pg_dump` 17.10 `-Fc` → **`_postgres_demo_14_10\backups\withjson_r2_demoA_20261017_144128.dump`**, 2.037.848 byte | VR |
| Checksum | sha256 `0681e42eb51cfcfde502ec367e261c503f0439260604efe45cedaf2fc2d2103a`; sidecar `.dump.sha256`; **`sha256sum -c` → OK** | VR |
| `pg_restore --list` | 27 TABLE, 27 TABLE DATA (gồm `alembic_version`), 43 CONSTRAINT, 34 FK CONSTRAINT, 57 INDEX (gồm `uq_identities_scopus_author_approved`) | VR |
| Bảo vệ dữ liệu | Thư mục `backups\` ngoài repo, ACL chỉ `NT AUTHORITY\SYSTEM` + chủ máy; dump chứa dữ liệu cá nhân 410 giảng viên + băm mật khẩu TEST, **không Git** | VR |
| Sự cố trong quá trình | Lần 1–2 `pg_dump` lỗi rỗng do script lọc bớt biến môi trường Windows → để lại 2 tệp 0 byte (`…_144032`, `…_144052`); **đã xóa** (tệp do chính script tạo). Lần 3 dùng môi trường đầy đủ → thành công. Sidecar sha256 lần đầu có CRLF → ghi lại bằng LF | VR |
| **Restore rehearsal** | **BLOCKED — chờ phê duyệt riêng** (tạo DB `scopus_ictu_test_restore_demoA_<ts>` bằng `demo_admin` + `pg_restore`). Tệp dump **chưa** được gọi là "restore verified" | — |

**Hệ quả:** chưa có phương án khôi phục *đã kiểm chứng*, vì vậy **không chạy** TC-W1 / TC-W2 (test có ghi) trong phiên này.

## 2. D-2 / D-3 — Thiết kế cuối (chưa triển khai: chính sách và contract cần duyệt)

### D-2 Validation lý do quyết định

**Contract hiện tại (VS):**
- API chỉ nhận `ACCEPT | REJECT`; `reason` tùy chọn, tối đa 4000 ký tự.
- Service bắt buộc lý do không rỗng cho REJECT (`candidate_review_service.py:783-787`, kiểm tra ở bước 2).
- DB CHECK `reason_required`: `action = 'ACCEPT' OR btrim(reason) <> ''`.
- `_accept`: (3) kiểm tra quyết định trùng (idempotent) → (8) nạp bằng chứng của observation → (9) kiểm tra xung đột identity.
- `InvalidReviewReasonError` → HTTP **422** (`reviews.py:218`).

**Quy tắc đề xuất (cần chủ đồ án chốt):**

| Tình huống | Lý do |
|---|---|
| REJECT | Bắt buộc (giữ nguyên) |
| ACCEPT khi observation **không có bằng chứng `PUBLICATION`** (chỉ tên) | **Bắt buộc** |
| ACCEPT khi Scopus author được đề xuất cho **> 1 giảng viên** (`is_shared_scopus_author`) | **Bắt buộc** |
| ACCEPT khi giảng viên có **> 1 ứng viên** (`is_ambiguous`) | **Bắt buộc** |
| ACCEPT có bằng chứng công bố, không mơ hồ, không dùng chung | Tùy chọn (giữ nguyên) |
| Lý do chỉ có khoảng trắng | Coi như rỗng (`strip()`) |

**Triển khai dự kiến (sau khi duyệt):**
- Trong `_accept`, đặt kiểm tra **sau bước 8** (đã có bằng chứng) và **sau bước 3**. Nhờ vậy gửi lặp một quyết định cũ (kể cả quyết định lịch sử không có lý do) **vẫn trả idempotent**, không bị chặn.
- Lỗi mới dùng `InvalidReviewReasonError` sẵn có → 422 với mã rõ ràng (vd `REASON_REQUIRED_FOR_WEAK_EVIDENCE`).
- **Không đổi schema** (CHECK DB cho phép ACCEPT có hoặc không có lý do), **không đổi quyền** (REVIEWER / ADMIN như cũ), **không sửa** 3 quyết định lịch sử, **không** nâng mức tin cậy vì có lý do.
- Frontend modal quyết định: đánh dấu ô lý do là bắt buộc khi `publication_evidence.length === 0 || ambiguity.is_shared_scopus_author || ambiguity.is_ambiguous` (các trường **đã có** trong API chi tiết), hiển thị thông báo 422.
- Test: unit service (ACCEPT name-only không lý do → 422; có lý do → OK; ACCEPT có công bố không lý do → OK; idempotent replay không lý do → OK; REJECT không đổi); integration API tương ứng.

### D-3 Mức chứng cứ trên "Liên kết giảng viên ICTU"

**Contract hiện tại (VS):** `PublicationLecturerLinkRead` (`schemas/publication_api.py:149`) chỉ có `author_order, scopus_id, full_name, staff_code, department, faculty, orcid`. **Không có trường bằng chứng**, nên frontend **không thể** hiển thị mức chứng cứ nếu chỉ dùng dữ liệu hiện có. ORCID hiển thị là ORCID của **hồ sơ giảng viên**, không phải bằng chứng nối với Scopus ID.

**Thay đổi tối thiểu đề xuất (additive, không đổi schema DB):**
- Backend: thêm trường tùy chọn `evidence_basis: Literal["NAME_ONLY", "PUBLICATION", "NAME_AND_PUBLICATION"] | None`, tính từ `identity_evidence.evidence_type` của identity APPROVED (`NAME_SIMILARITY` / `DOI_EXACT` / `PUBLICATION_OVERLAP`). Có thể thêm `reviewed_at` từ `lecturer_scopus_candidate_reviews`.
  - Ảnh hưởng: 1 truy vấn phụ trong `publication_queries.py` (`_for_role` vẫn ẩn với LECTURER như hiện tại), schema response thêm trường tùy chọn (client cũ không vỡ).
- Frontend: tiêu đề mục "**Liên kết giảng viên đã duyệt**"; mỗi dòng kèm nhãn "Duyệt theo tên" / "Có công bố hỗ trợ"; tooltip "Đã được người duyệt chấp nhận — không phải xác minh định danh độc lập". **Không** dùng chữ "xác minh định danh".
- Test: integration `GET /publications/{eid}` cho 3 trường hợp; UI VI / EN.

## 3. D-4 — REOPEN (chỉ thiết kế, KHÔNG code)

| Hạng mục | Đề xuất |
|---|---|
| Actor | `REVIEWER` và `ADMIN` (cùng quyền với ACCEPT / REJECT). LECTURER: 403 |
| Endpoint | `POST /api/v1/reviews/candidates/{id}/reviews` với `action: "REOPEN"` (mở rộng `ReviewAction`) — tái dùng route sẵn có |
| Body | `observation_id` (observation hiện hành), `candidate_version` (khóa lạc quan), **`reason` bắt buộc** (DB CHECK `reason_required` đã yêu cầu) |
| Trạng thái | Nguồn: `ACCEPTED` / `REJECTED` / `SUPERSEDED` → đích: `PENDING` (khớp CHECK `transitions` có sẵn, `models/candidate.py:303-308`). Từ `PENDING` → **409** `CANDIDATE_NOT_DECIDED` |
| Identity (khi nguồn = ACCEPTED) | Identity `APPROVED` của cặp (lecturer, scopus_author) → **`REVOKED`** (version + 1); **không xóa** `identity_evidence`; ghi `resulting_identity_id` của review REOPEN = identity bị thu hồi |
| Unique | Sau khi `REVOKED`, partial unique `uq_identities_scopus_author_approved` (WHERE APPROVED) **giải phóng** Scopus ID → có thể ACCEPT cho giảng viên khác. ACCEPT lại cùng cặp: identity cùng cặp đã tồn tại (unique pair) → chuyển `REVOKED → APPROVED` (version + 1) thay vì tạo mới — **cần sửa bước 10–11 của `_accept`** |
| Giao dịch | Một transaction: `SELECT … FOR UPDATE` candidate + identity → kiểm tra version → insert review → cập nhật candidate (PENDING, version + 1) → cập nhật identity → audit → commit một lần; lỗi bất kỳ → rollback toàn bộ |
| Audit | `CANDIDATE_REOPENED` (before / after status, reason, reviewer) + `IDENTITY_REVOKED` (before / after, liên kết review) |
| Idempotency | Gửi lặp cùng (candidate, observation, REOPEN, `candidate_version` cũ) sau khi đã REOPEN → trả review cũ `idempotent=true`; `candidate_version` lệch → 409 `STALE_VERSION` |
| Tác động dữ liệu | Công bố của Scopus ID đó **biến mất** khỏi "Công bố của tôi" của giảng viên bị thu hồi và khỏi "Liên kết giảng viên ICTU"; Dashboard "Đã duyệt" − 1, "Đã thu hồi" + 1; lịch sử review thêm dòng REOPEN |
| Test cases | (1) REOPEN ACCEPTED → PENDING + identity REVOKED + 2 audit; (2) REOPEN REJECTED → PENDING, không đụng identity; (3) thiếu lý do → 422; (4) từ PENDING → 409; (5) version cũ → 409; (6) replay → idempotent; (7) LECTURER → 403; (8) sau REOPEN, ACCEPT cho giảng viên khác cùng Scopus ID → OK; (9) ACCEPT lại cùng cặp → identity APPROVED (không trùng); (10) lỗi giữa chừng → rollback, không đổi gì |

## 4. UI P1 — Đã sửa (code UI, không đụng dữ liệu)

| Issue | Root cause (VS) | Thay đổi | Tệp |
|---|---|---|---|
| **UI-01** Home | Nhãn badge trạng thái là chuỗi tĩnh, Home không gọi API | Đổi 4 nhãn trạng thái giả thành nhãn hành động trung tính: "Chưa có dữ liệu" → **"Xem hàng đợi" / "Xem lịch sử" / "Xem công bố"**; "Đang chờ kết nối" → **"Xem liên kết"** (EN: "Open queue", "View history", "View publications", "View links"). Không hardcode số liệu; không đổi logic; áp dụng cho cả ADMIN / REVIEWER / LECTURER vì dùng chung khóa | `i18n/locales/vi.ts`, `en.ts` |
| **UI-02** Dashboard | Khối "Trạng thái định danh" đếm `lecturer_scopus_identities.status`; luồng duyệt hiện tạo identity thẳng `APPROVED` → "Ứng viên 0" dễ nhầm với "Chờ duyệt 144" (đếm `lecturer_scopus_candidates` PENDING) | **Giữ nguyên 4 số đếm và công thức**; KPI "Chờ duyệt" → **"Ứng viên chờ duyệt"**; tiêu đề khối → **"Liên kết định danh Scopus"**; "Ứng viên" (identity CANDIDATE) → **"Chờ xác lập"**; thêm 1 dòng giải thích hai khái niệm khác nhau | `locales/vi.ts`, `en.ts`, `types.ts` (+1 khóa `identityHint`), `pages/Dashboard/index.tsx` |
| **UI-03** Nguồn offline | Panel "1. Nguồn dữ liệu đơn vị" chỉ phản ánh **cấu hình máy chủ** (`source.configured`) nhưng in chữ cảnh báo + tên biến môi trường như thể hệ thống lỗi; còn khẳng định sai "Thu thập trực tuyến chưa được bật" (thu thập trực tuyến dùng cấu hình khác) | Tách 3 ý: (1) "Chưa gắn bộ nguồn offline với máy chủ, nên chưa thể Xem trước / Áp dụng **một lần đối chiếu mới**"; (2) nếu DB đã có kết quả (`database.resolutions_by_source_and_status` không rỗng): "**Dữ liệu đơn vị đã áp dụng trước đó vẫn được giữ nguyên** (xem mục 2)"; (3) dòng nhỏ cho người vận hành về `AFFILIATION_SOURCE_DIR`. Bỏ câu sai về thu thập trực tuyến. **Không sửa `.env`** | `pages/Normalization/AffiliationsTab.tsx` |
| **UX-01** Badge | `AffiliationBadge` có 2 biến thể (`small` 10 px / thường 11 px, bo 4 px); trong cùng bảng tác giả, hàng có đơn vị dùng `small`, hàng không có dùng cỡ thường | Một biến thể duy nhất theo Figma `5:34` (VS): **pill `rounded-full`, cao `h-[23px]`, padding ngang `px-2.5` (10 px), rộng theo nội dung**; giữ chữ 11 px đậm và bảng màu hiện có (Figma chưa cho thông số font badge → không tự đổi); bỏ prop `small` và 3 lời gọi dùng nó. Thẻ nguồn "Crossref / OpenAlex" là *source badge* → giữ dạng gọn | `pages/Publications/AuthorAffiliations.tsx` |

Figma: cần bổ sung variant *mức tin cậy đơn vị* ("Đã xác minh định danh", "Đã đối chiếu · Chưa xác minh", "Chưa xác định", "Chưa đối chiếu") vào `5:34` với đúng thông số trên (chủ đồ án cập nhật).

## 5. OPS-02 — Launcher PA-1 (patch đề xuất, đã kiểm thử trên bản sao cô lập; repo KHÔNG đổi)

- Bản sao: `_postgres_demo_14_10/scratch/launcher_pa1/` (launcher + test hiện có + BAT); patch: `apply_pa1.py`; diff: `PA1.diff`.
- Nội dung patch (43 dòng thay đổi):
  1. `needs_migration(current, heads)` (hàm thuần).
  2. `MIGRATION_PROTECTED_DBS = {"scopus_ictu_demo_teacher_20261014"}` + `migration_block_reason()`.
  3. `check_database()` **không còn gọi `run_migration`**; lệch revision → `LauncherError` kèm hướng dẫn "chạy `scopus-ictu-qhun22.bat migrate` (sẽ sao lưu trước)".
  4. `cmd_migrate`: kiểm tra DB được bảo vệ → `backup_database()` (`pg_dump -Fc` vào `RUNTIME/backups/<db>_pre_migrate_<ts>.dump` + sha256; lỗi → **không migrate**) → `run_migration` → `check_database`.
- Không đổi `start` khi schema khớp, `stop`, `status`, cổng, tệp env → workflow dev / test hiện tại giữ nguyên.
- Test mới `test_demo_launcher_pa1.py` (7): `needs_migration`; DB teacher bị chặn; `check_database` không có đường migrate; `start` lệch schema → exit 1, không migrate / backup / khởi động backend; `migrate` gọi theo thứ tự `env → pg → backup → migrate → check`; DB bảo vệ bị từ chối trước khi backup; backup lỗi → không migrate.
- **Kết quả trên bản sao: 15 / 15 PASS** (8 test cũ + 7 test mới). Test cũ trên repo gốc không chạy đơn lẻ được vì `conftest` yêu cầu `TEST_DATABASE_URL` (rào chắn có chủ đích); test này đã PASS trong lượt chạy đầy đủ 1047 test hôm nay.
- Áp vào repo: chờ duyệt (mục 8).

## 6. Kiểm thử

| Kiểm thử | Kết quả |
|---|---|
| `tsc --noEmit` (frontend) | **PASS** |
| `npm run build` | **PASS** (1505 modules, 14,98 s) |
| Vite dev biên dịch 6 module đã sửa (`GET /src/...` → 200) | **PASS** |
| Trang `/login` trên 5199: console | **PASS** (chỉ 401 `/auth/me` trước đăng nhập) |
| Launcher PA-1 trên bản sao | **PASS** 15 / 15 |
| Backup: `sha256sum -c`, `pg_restore --list` | **PASS** |
| Restore rehearsal | **BLOCKED** (chờ duyệt tạo DB) |
| Browser regression có đăng nhập cho `/home` (3 vai trò), `/dashboard`, `/normalization?tab=affiliations`, `/publications/{eid}`, VI / EN | **BLOCKED** — chưa có phê duyệt cách cấp credential (DATA_INTEGRITY §2); tôi không đọc tệp secrets |
| Pytest backend | **Không chạy** — không đổi code backend |
| TC-W1 / TC-W2 | **Không chạy** — chưa có restore đã kiểm chứng + chưa duyệt |
| DB A sau phiên | Không đổi (`pg_dump` chỉ đọc; không thao tác ghi) |

## 7. Git

**Không stage, không commit.** 4 file RC đã stage giữ nguyên blob.

Thay đổi mới (unstaged), 6 tệp frontend, +44 / −37 dòng:
- `frontend/src/i18n/locales/vi.ts`, `en.ts` — UI-01, UI-02 (chuỗi). Giữ nguyên CRLF như blob HEAD.
- `frontend/src/i18n/types.ts` — thêm khóa `identityHint`.
- `frontend/src/pages/Dashboard/index.tsx` — dòng giải thích dưới tiêu đề khối identity.
- `frontend/src/pages/Normalization/AffiliationsTab.tsx` — UI-03.
- `frontend/src/pages/Publications/AuthorAffiliations.tsx` — UX-01.

Tài liệu mới (untracked): `docs/qa/CONTROLLED_REMEDIATION_20261017.md`.
Ngoài repo: dump + sha256 trong `backups\`; script và bản sao launcher trong `scratch\`.

## 8. Cần phê duyệt riêng

1. **Restore rehearsal:** tạo DB `scopus_ictu_test_restore_demoA_<ts>` bằng `demo_admin` + `pg_restore --no-owner --role=scopus_demo_user` từ `withjson_r2_demoA_20261017_144128.dump`, rồi đối chiếu schema / số dòng / băm nội dung. Đây là điều kiện để chạy TC-W1 / TC-W2.
2. **Credential cho browser regression và TC-W1 / TC-W2:** chọn một cách ở `DATA_INTEGRITY_DEMO_SAFETY_20261017.md` §2.
3. **D-2:** chốt bảng quy tắc bắt buộc lý do (mục 2) → cho phép sửa `candidate_review_service.py` + modal quyết định + test.
4. **D-3:** cho phép thêm trường tùy chọn `evidence_basis` vào `PublicationLecturerLinkRead` + UI + test.
5. **D-4:** duyệt thiết kế REOPEN (mục 3) trước khi code.
6. **OPS-02:** cho phép áp patch PA-1 + test vào repo (`backend/scripts/demo_launcher.py`, `backend/tests/unit/test_demo_launcher_pa1.py`).
7. **UI-03 (a) (tùy chọn):** thêm `AFFILIATION_SOURCE_DIR` vào `backend/.env` của môi trường A + khởi động lại 8199.
8. **Figma:** bổ sung variant badge mức tin cậy đơn vị.
9. **Commit** các thay đổi UI P1 (sau khi có browser regression) và tài liệu.

## 9. Backlog còn lại cho Dashboard + Design System

- **Dashboard:**
  - DASH-01 (nhãn "Có đơn vị công tác" gộp CORROBORATED; chưa hiển thị `by_link_status`).
  - DASH-02 (lấp năm trống trên trục).
  - DASH-03 (kiểm miền giá trị năm khi chuẩn hóa).
  - DASH-04 / UI-08 (màu trùng loại thứ 8).
  - UI-09 ("Retracted" chưa dịch).
  - UI-16 (nút header bị cắt chữ trên mobile).
- **Design System:**
  - UX-01 mở rộng (Badge dùng chung cho `ReviewHistory`, `ImportStatusBadge`, AntD `Tag` ở `/reviews`).
  - UX-02 (token radius; trang LECTURER 16 px, `/users` 12 px).
  - UX-03 (nút: 158 nút viết tay, helper 5 / 28 tệp; 40 px so với Figma 36 px).
  - UX-07 (`/tasks` placeholder).
  - UI-10 (bảng tràn ở 1440 px).
  - UI-11 (chính tả "nap", "validate").
  - UI-12 (mã thô ở rà soát đơn vị, trùng số "2.").
  - UI-13 (header "Hệ thống" ở chi tiết công bố).
  - UI-14 (đổi ngôn ngữ khóa 3 s).
  - UI-15 ("Chưa cập nhật" ở EN).
  - UI-17 (modal ứng viên: mã quy tắc, bằng chứng lặp, font AntD).
  - UI-18 (thuật ngữ duyệt).
  - UI-19 (`destroyOnClose` deprecated).
