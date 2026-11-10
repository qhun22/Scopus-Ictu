# AGENTS.md

Guidance for coding agents working in this repository. `CLAUDE.md` is the Claude Code
twin of this file; if they disagree, trust the code and update both.

## What this project is

Undergraduate thesis (đồ án tốt nghiệp, ICTU): a web app that reconciles ICTU lecturer
master data with Scopus author identities and publications. The central rule is
evidence-based reconciliation — **no automatic confirmation of a lecturer ↔ Scopus author
link**. Candidates are generated read-only; only a human review decision changes state.

Stack: FastAPI + PostgreSQL + SQLAlchemy 2.x/Alembic (backend) · React 18 + TypeScript +
Vite + Tailwind + Ant Design (frontend).

## Layout

```
backend/app/
  api/v1/endpoints/   thin routes (validate → service → schema); aggregated in api/v1/router.py
  services/           business logic by domain; queries SQLAlchemy directly (no separate repositories layer)
  models/             ORM models
  schemas/            Pydantic v2
  core/               config, database, security, exceptions, logging
backend/alembic/versions/   migrations (append-only)
backend/scripts/            operational CLIs (python -m scripts.<name>)
backend/tests/{unit,integration,fixtures}
frontend/src/{api,components,contexts,i18n,layouts,pages,types,utils}
data/                 local-only datasets (gitignored except schemas/fixtures)
docs/                 adr, design, planning, qa (gate handovers), freeze, research
```

## Commands

Backend — run from `backend/`:

```bash
python -m pip install -e ".[dev]"
python -m alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m pytest -q
python -m pytest tests/unit/test_candidate_generator.py -q     # single file
python -m pytest tests/unit/test_x.py::test_y -q               # single test
python -m ruff check app/
```

Frontend — run from `frontend/`:

```bash
npm ci
npm run dev      # Vite at :5173
npm run build    # tsc --noEmit && vite build  (this is the only real check)
```

There is no frontend test runner; `npm run lint` is a stub.

Windows demo (from repo root; uses a sibling venv `..\_venv_backend_demo_py312`):

```bat
scopus-ictu-qhun22.bat        :: DB → backend → frontend → browser
scopus-ictu-qhun22.bat stop
```

It delegates to `backend/scripts/demo_launcher.py` and logs to
`..\_quan_ly_do_an\logs\demo`. Credentials live outside Git; never inline them.

Docker: `docker compose -f compose.yaml -f compose.local.yaml up --build`.

## Configuration

- Backend reads `backend/.env` (gitignored). Template: `backend/.env.example`.
  Required: `DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME`, `SECRET_KEY`,
  `BACKEND_CORS_ORIGINS`, `ENVIRONMENT` (`local|dev|prod`).
  Optional: `AFFILIATION_SOURCE_DIR`, `CRAW_SOURCE_DIR`, `AFFILIATION_ONLINE_CACHE_DIR`.
  Settings are declared in `app/core/config.py`; never read `os.environ` elsewhere.
- Ingestion paths come from config only (`SCOPUS_RAW_DIR`, `DSPACE_SNAPSHOT_PATH`, …),
  never from request-supplied paths.
- Frontend reads `VITE_API_BASE_URL` (empty = same origin); dev proxy target via
  `VITE_API_PROXY_TARGET` (see `.claude/launch.json`, ports 8199/5199).

## Architecture rules

- Request flow: endpoint → service → repository → model. Keep endpoints thin; no SQL or
  business rules in routes.
- Auth: HttpOnly cookie JWT. Dependencies `get_current_user` and `require_role(*roles)`
  live in `app/api/dependencies.py`. `User.auth_version` revokes all sessions on password
  reset; sessions auto-renew in the last 25% of their lifetime.
- Errors: always raise `APIError` (`app/core/exceptions.py`) carrying `status_code`,
  `detail`, `code`. The frontend branches on `code`, so codes are part of the contract.
- Roles: `ADMIN` (all pipeline operations), `REVIEWER` (review queue), `LECTURER`
  (read-only publications/identities; self-service updates to allowlisted personal,
  academic and research fields through `PATCH /lecturers/me/profile`). Identity keys,
  account roles, faculty/department and verified Scopus links remain staff-managed.
- Startup recovers interrupted import/enrichment jobs (`app/main.py` lifespan).

## Domain services (backend/app/services/)

| Area | Path | Notes |
|---|---|---|
| Scopus CSV import | `scopus_import_service.py`, `parser/scopus_csv_parser.py` | upload → parse/validate → immutable raw records; import lifecycle, provenance, file SHA-256 dedupe |
| Normalization | `normalization/scopus_normalizer.py` | valid raw records → canonical publications, deduplicated by EID |
| Matching | `matching/` | read-only candidate generation; the name rules (`RuleId` in `candidate_types.py`, run by `candidate_generator.py`) emit `CandidateEvidence` |
| Candidate review | `candidate_review_service.py`, `review_reason_policy.py` | the only path that changes candidate state: ACCEPT / REJECT / REVOKE identity / REOPEN |
| Affiliation | `affiliation_workflow.py`, `affiliation_*.py`, `author_affiliation.py` | ADMIN-driven collection + enrichment |
| Lecturer dataset | `lecturer_dataset/` | import, parser, rollback, export |
| ICTU source claims (E3) | `source_claims/`, `source_staging/`, `source_claim_matching/` | contract/parser/canonical/provenance; append-only staging tables; bridge turning claims into evidence |

Matching policy: `review_reason_policy.py` enforces reason-required ACCEPT when evidence
is name-only, the Scopus author is shared, or one lecturer has several candidates.
In `source_claim_matching/bridge.py`, a source declaration is **evidence, never
approval**: subjects resolve only by profile URL or e-mail (never by name), and reviewer
decisions are echoed, never modified.

## Database and migrations

- Migrations are append-only. Never rewrite a published revision; add a new one.
- Current head: `e8b2c6a94f17` (users.has_password / users.google_linked), single head; verify with
  `python -m alembic heads`.
- `python -m alembic revision --autogenerate -m "describe change"`.

## Data and safety invariants

- No real lecturer or Scopus data is committed. Only `data/**/schema/` and synthetic
  fixtures (`example.invalid` emails) are versioned; everything else is gitignored.
- Never commit `.env`, credentials, `local_backups/`, or real CSV exports.
- Tests must never touch the dev database. `backend/tests/db_safety_guard.py` fails
  closed and has **no bypass flag**; it needs `TEST_DATABASE_URL` (and `ENVIRONMENT=test`).
  Do not work around it.
- Benchmarks/acceptance scripts refuse to run when `ENVIRONMENT=prod`.

## Testing

```bash
cd backend
python -m pytest tests/unit/ -q                              # no DB needed
TEST_DATABASE_URL=postgresql+psycopg2://u:p@localhost/testdb \
  python -m pytest tests/integration/ -q
```

~41 unit files, ~43 integration files. CI (`.github/workflows/ci.yml`) runs Alembic
upgrade + full pytest with a Postgres 16 service, then `npm run build`. Keep both green.

## Frontend conventions

- Providers wrap the app in `App.tsx`: `I18nProvider`, `AuthProvider`, `ToastProvider`,
  `NotificationProvider`. Routing and role gates are centralized in `App.tsx`
  (`RoleRoute`); `src/routes.tsx` only re-exports it.
- Admin routes: `/dashboard`, `/imports`, `/normalization`, `/lecturers`, `/users`,
  `/audit-logs`, `/tasks`. Shared routes: `/search`, `/publications[/:eid]`.
  Review: `/reviews`, `/approval-queue`, `/review-history`.
- All HTTP goes through `src/api/client.ts` (`credentials: "include"`). Session auth
  error codes (`ACCOUNT_LOCKED`, `PASSWORD_RESET_BY_ADMIN`, `SESSION_REVOKED`) are
  broadcast for automatic logout.
- Prefer shared primitives in `src/components/ui/` (`Button`, `Badge`, `PageHeader`);
  border-radius convention is 5px.
- Every user-facing string goes through `useI18n()`; add keys to
  `src/i18n/locales/vi.ts`, `src/i18n/locales/en.ts`, and `src/i18n/types.ts`.

## Work conventions

- Gated milestones (E3, Gate D.2, …) are delivered as handovers in `docs/qa/<gate>/`:
  `*_HANDOVER.md` (date, status, changed vs. unchanged files), `*_VALIDATION.json`,
  `*_TEST_RESULTS.txt`, `*_IMPLEMENTATION.diff`. Follow this shape when asked to do a
  gated task, and state explicitly when "no commit, no push, no DB connection".
- Design records go in `docs/adr/` (append-only decisions: EID canonical identity,
  offline ingestion, append-only audit, evidence separation).
- Commit messages are Vietnamese, imperative-ish, describing the change intent.
- Do not commit, push, run migrations against real data, or touch reviewer data unless
  explicitly asked. Prefer showing the diff over committing.

## Docs map

- `README.md` — scope table M0–M4 and local setup.
- `CLAUDE.md` — Claude Code variant of this file.
- `docs/planning/KE_HOACH_V4_HOAN_THIEN_DO_AN_TRUOC_14_10.md` — thesis completion plan.
- `docs/design/` — architecture, DB, auth, use cases, Figma handoff.
- `docs/qa/` — acceptance evidence per gate; `docs/freeze/` — frozen milestone specs.
