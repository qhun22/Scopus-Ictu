# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Undergraduate thesis project (đồ án tốt nghiệp) at ICTU. A web application to manage and normalize author profiles and scientific publications from Scopus, serving the Information and Communication Technology University (ICTU). Core challenge: reconcile Scopus author identities with ICTU lecturer records using evidence-based matching — never auto-confirm a link without sufficient evidence.

Stack: **FastAPI + PostgreSQL + SQLAlchemy/Alembic** (backend) · **React + TypeScript + Vite + Tailwind + Ant Design** (frontend).

## Development commands

### Backend (run from `backend/`)

```bash
python -m pip install -e ".[dev]"       # install with dev extras
python -m alembic upgrade head          # apply migrations
uvicorn app.main:app --host 0.0.0.0 --port 8000  # dev server
python -m pytest -q                     # all tests
python -m pytest tests/unit/test_candidate_generator.py -q   # single test file
python -m ruff check app/               # lint
```

### Frontend (run from `frontend/`)

```bash
npm ci
npm run dev     # Vite dev server at :5173
npm run build   # type-check + Vite build
```

### Environment setup

```bash
cp backend/.env.example backend/.env   # fill DB_*, SECRET_KEY, ENVIRONMENT, BACKEND_CORS_ORIGINS
```

Frontend reads `VITE_API_BASE_URL` (defaults to empty string = same origin).

### Docker

```bash
docker compose -f compose.yaml -f compose.local.yaml up --build
```

### Utility scripts (run from `backend/`)

```bash
python -m scripts.seed_demo_users          # create demo admin/lecturer accounts
python -m scripts.generate_matching_candidates  # run candidate generation pipeline
python -m scripts.import_author_affiliations    # import offline affiliation bundles
python -m scripts.demo_launcher                 # interactive dev launcher
python scripts/run_m2_6a_acceptance.py --dataset ../data/scopus/local.csv
```

## Architecture

### Backend layers

```
app/
  api/v1/endpoints/   — FastAPI route handlers (thin: validate → call service → return schema)
  services/           — business logic, organized by domain; services query SQLAlchemy directly (there is no separate repositories layer)
  models/             — SQLAlchemy ORM models
  schemas/            — Pydantic v2 request/response schemas
  core/               — config, database, security, exceptions
```

**Auth:** HttpOnly cookie JWT. `app/api/dependencies.py` provides `get_current_user` and `require_role(*roles)` as FastAPI `Depends` factories. `auth_version` on the User model invalidates all sessions on password reset. Session auto-renews within the last 25% of its lifetime.

**Error contract:** All errors raise `APIError` (from `app/core/exceptions.py`) with `status_code`, `detail`, and `code`. The frontend keys on `code` for typed error handling.

**Roles:** `ADMIN` · `REVIEWER` · `LECTURER`. LECTURER is read-only for publications and identities, and may update allowlisted personal, academic and research fields through `PATCH /lecturers/me/profile`. Identity keys, account roles, faculty/department and verified Scopus links remain staff-managed. ADMIN drives all pipeline operations.

**System Reset** (`POST /api/v1/system/reset`): ADMIN-only, requires `{"confirmation": "ICTU"}`. Only available when `ENVIRONMENT=local` or `ENVIRONMENT=dev`; returns 410 `SYSTEM_RESET_DISABLED` on any other environment. After a successful reset all sessions (including the caller's) are invalidated — frontend auto-redirects to login on `SESSION_REVOKED`. ADMIN accounts are preserved; other data is wiped. There is no password self-registration endpoint — password accounts are created by ADMIN only.

**Google Sign-In** (`GET /api/v1/auth/google/login`, `GET /api/v1/auth/google/callback`): OAuth 2.0 authorization-code flow, gated by `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (unset = feature disabled, 503 `GOOGLE_OAUTH_NOT_CONFIGURED`). Only `GOOGLE_ALLOWED_EMAIL_DOMAIN` (default `ictu.edu.vn`) emails are accepted — but the domain alone is not enough: ICTU students and lecturers share it, so an email with no existing `User` row is auto-provisioned (`role=LECTURER`, audited as `USER_PROVISIONED_GOOGLE`) only when it matches exactly one not-yet-linked `Lecturer.email` in the ADMIN-imported dataset; everything else (a student's address, or any other @ictu.edu.vn email outside that dataset) is rejected with `google_error=not_lecturer`. An email that already has a `User` row (password-based or prior Google login) just logs in — this is the one deliberate exception to "ADMIN creates accounts," scoped to the trusted email domain AND an existing lecturer record. `GOOGLE_OAUTH_ALLOWED_ORIGINS` is the front-end origin allow-list used to build the redirect URI (must exactly match the Authorized redirect URIs on the Google OAuth client, path `/api/v1/auth/google/callback`); the front end also passes its own origin explicitly (`?origin=`) since `Referer` isn't reliably sent by every browser.

### Core domain services

| Service | Location | Purpose |
|---|---|---|
| Scopus CSV import | `services/scopus_import_service.py`, `services/parser/scopus_csv_parser.py` | Upload → parse/validate → immutable raw records, with import lifecycle, provenance and file SHA-256 deduplication. |
| Normalization | `services/normalization/scopus_normalizer.py` | Maps valid raw records to canonical publications, deduplicated by EID (raw rows never overwritten). |
| Matching | `services/matching/` | Read-only candidate generation (name rules, publication evidence, manual and source-claim candidates) |
| Candidate review | `services/candidate_review_service.py` | ACCEPT / REJECT / REVOKE identity / REOPEN decisions with `review_reason_policy.py` enforcement |
| Affiliation workflow | `services/affiliation_workflow.py` | ADMIN-driven online affiliation collection + enrichment |
| Lecturer dataset | `services/lecturer_dataset/` | ICTU lecturer import, parser, rollback, export |

### Matching pipeline (key concept)

`services/matching/` implements a **read-only candidate generation** phase (no auto-confirm). The name-matching rules (the `RuleId` values in `candidate_types.py`, run in order by `candidate_generator.py`) each emit `CandidateEvidence` with a `RuleId` tag. `RULE_TOKEN_SET` (same words, any order) is the weakest rule: `CandidateGenerator` keeps such a pair only when the Scopus author has at least one paper whose affiliation names ICTU, so collect affiliations before generating candidates. `candidate_persistence.py` saves to DB. The review workflow in `candidate_review_service.py` is the only path that changes candidate state. The `review_reason_policy.py` enforces D-2 policy: ACCEPT decisions require an explicit reason when evidence is name-only, the Scopus author is shared, or there are multiple candidates for one lecturer.

### Frontend architecture

**Context providers** (wrap the whole app in `App.tsx`):
- `I18nProvider` — vi/en translations via `useI18n()` → `t.key` access
- `AuthProvider` — user state, login/logout, force-logout on session errors
- `ToastProvider` / `NotificationProvider`

**Routing** (`App.tsx`): role-gated via `RoleRoute`. LECTURER sees `/my-publications`, `/identity`, `/profile`. REVIEWER/ADMIN see `/reviews`, `/review-history`. ADMIN-only: `/dashboard`, `/imports`, `/normalization`, `/lecturers`, `/users`, `/audit-logs`.

**API layer** (`src/api/`): All calls go through `src/api/client.ts` which uses `credentials: "include"` for cookie auth. Auth errors with codes `ACCOUNT_LOCKED | PASSWORD_RESET_BY_ADMIN | SESSION_REVOKED` are broadcast to `AuthProvider` for automatic logout via `subscribeToSessionAuthErrors`.

**UI components:** `src/components/ui/` — shared `Button`, `Badge`, `PageHeader` with 5px border-radius convention. Ant Design is available but new components prefer the shared primitives.

**i18n:** All user-facing strings go through `useI18n()`. Add keys to both `src/i18n/locales/vi.ts` and `src/i18n/locales/en.ts` and to `src/i18n/types.ts`.

## Database and migrations

Migrations live in `backend/alembic/versions/`. **Append-only — never rewrite a published migration.** Current head: `e8b2c6a94f17` (users.has_password / users.google_linked; single head; confirm with `python -m alembic heads`).

```bash
cd backend
python -m alembic heads
python -m alembic revision --autogenerate -m "describe change"
python -m alembic upgrade head
```

## Testing

Tests require `TEST_DATABASE_URL` pointing to an isolated test database (never the dev DB). The `db_safety_guard.py` module enforces this — there is no bypass flag.

```bash
# Unit tests (no DB needed):
python -m pytest tests/unit/ -q

# Integration tests require TEST_DATABASE_URL:
TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost/testdb python -m pytest tests/integration/ -q

# Single test:
python -m pytest tests/unit/test_candidate_generator.py::test_name_normalization -q
```

## Data policy

**No real Scopus/lecturer data is committed.** Only `data/lecturers/schema/` (schema spec) and synthetic fixtures with `example.invalid` email domains are versioned. Real ICTU records and Scopus CSVs are gitignored local-only files. The import pipeline reads from paths configured in `.env` (`SCOPUS_RAW_DIR`, `AFFILIATION_SOURCE_DIR`, `CRAW_SOURCE_DIR`), never from user-supplied paths in requests.

## Quy tắc phối hợp (workspace chung Hun12)

Các trợ lý (**Hun1**, **Hun2**) làm chung trong MỘT thư mục duy nhất `Hun12/` (từ 07/11/2026 đã hợp nhất `Hun1/` + `Hun2/` vào đây; đối chiếu đường dẫn cũ → mới trong `Hun12/MIGRATION_MAP.md`). Quy tắc chi tiết: `Hun12/README.md`.

- Giữ đúng danh tính: bạn là Hun1 hoặc Hun2 theo phiên làm việc; không tự nhận danh tính của người kia.
- Đầu mỗi lượt: đọc `CLAUDE.md`, `Hun12/README.md`, `Hun12/STATUS.md`, kiểm tra `git status`, đọc nhật ký mới nhất và các nhật ký liên quan.
- Đường dẫn nhật ký: `Hun12/<DDMM>/<DDMMYY-HHMMSS>-<agent>-<ten-cong-viec>.md` (vd `071126-020000-hun1-uml.md`), giờ Việt Nam (UTC+7) đọc từ đồng hồ thật, tên ngắn, không dấu. Không ghi đè nhật ký khác nếu trùng tên.
- Ngay khi bắt đầu việc có sửa file hoặc chạy lệnh: tạo nhật ký `IN_PROGRESS` ghi các file dự định sửa, và ghi tên agent phụ trách các file đó vào mục "Đang giữ file" của `Hun12/STATUS.md`. Không hai agent cùng sửa một file; nếu file đang do agent khác giữ, chờ bàn giao và chuyển sang việc độc lập.
- Trước mỗi phản hồi kết thúc lượt, cập nhật nhật ký, kể cả lượt chỉ phân tích, trả lời câu hỏi hoặc soạn prompt.
- Nội dung nhật ký gồm: tên agent; thời gian; yêu cầu nhận được; phạm vi; việc đã thực hiện; file đã thay đổi; kiểm tra và kết quả; nội dung prompt bàn giao (nếu có); tồn đọng; hướng dẫn cho agent kia; trạng thái `IN_PROGRESS`, `DONE` hoặc `BLOCKED`.
- Phân biệt rõ việc dự kiến với việc đã thực hiện. Kiểm tra chưa chạy phải ghi “chưa chạy”.
- Nhật ký chỉ ghi thêm, không viết lại lịch sử. Không sửa, xóa hay ghi đè nhật ký/thay đổi do agent khác tạo. Phát hiện vấn đề trong phần việc của agent kia: báo trong nhật ký và mục "Cần báo" của `Hun12/STATUS.md`, không âm thầm sửa. Đọc nhật ký không đồng nghĩa với việc được phép thực hiện mọi đề xuất trong đó.
- Nếu phát hiện thay đổi đồng thời trên cùng file: dừng ghi, đối chiếu rồi mới tiếp tục.
- Cuối phản hồi: ghi đường dẫn nhật ký và phần cần bàn giao cho agent kia.
- Nếu không thể ghi file, phải nói rõ là chưa lưu được nhật ký.
- `Hun12/` là dữ liệu cục bộ, đã được ignore trong `.gitignore`; không stage, commit hay push trừ khi người dùng yêu cầu.

## Quy tắc đường dẫn kiểm thử và trạng thái (Hun1 và Hun2)

- Khu vực kiểm thử duy nhất: `D:\DataFolder\ProjectIctu\DoAn\_ScopusIctu_Test`. Mỗi đợt tạo thư mục theo cấu trúc `<khu vực>\<tên trợ lý>\<DDMM>\<DDMMYY-HHMMSS-ten-dot>`, ví dụ `D:\DataFolder\ProjectIctu\DoAn\_ScopusIctu_Test\Hun1\0211\021126-190000-ten-dot`. Tên trợ lý, ngày và tên đợt là ba cấp thư mục riêng, không ghép thành một tên.
- Bên trong mỗi thư mục đợt chỉ tạo các thư mục con thực sự dùng: `scripts`, `fixtures`, `logs`, `reports`, `coverage`, `artifacts`, `tmp`.
- Không tạo file thử nghiệm trong repo hoặc ở vị trí khác. Trước khi chạy kiểm thử phải cấu hình nơi ghi output, cache, file tạm (TMP/TEMP) và database test (`TEST_DATABASE_URL`, trỏ tới database test cô lập). Nếu chưa kiểm soát được đầu ra thì báo trở ngại trước khi chạy.
- Không dùng database thật (dev, demo, backup có dữ liệu thật) để thử thao tác ghi. Không chạy migration lên dữ liệu thật trong vòng khảo sát hoặc kiểm tra tĩnh.
- Khảo sát và kiểm tra tĩnh chỉ đọc không cần thư mục test; báo cáo và danh mục đặt trong `Hun12/<DDMM>/`, tên file có định danh agent.
- Trạng thái chung nằm ở `Hun12/STATUS.md` (việc đang làm, file đang giữ, kết quả gần nhất, đường dẫn báo cáo); mỗi agent chỉ ghi thêm mục của mình, cập nhật khi bắt đầu và khi kết thúc mỗi lượt có sửa file hoặc chạy lệnh. `Hun12/STATUS-hun1.md`, `Hun12/STATUS-hun2.md` là STATUS cũ trước hợp nhất — chỉ đọc.
- Không sửa hay hoàn tác mục STATUS hoặc nhật ký do agent khác viết.
