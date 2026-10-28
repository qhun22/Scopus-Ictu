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
  services/           — business logic, organized by domain
  repositories/       — SQLAlchemy query objects (no business logic)
  models/             — SQLAlchemy ORM models
  schemas/            — Pydantic v2 request/response schemas
  core/               — config, database, security, exceptions
```

**Auth:** HttpOnly cookie JWT. `app/api/dependencies.py` provides `get_current_user` and `require_role(*roles)` as FastAPI `Depends` factories. `auth_version` on the User model invalidates all sessions on password reset. Session auto-renews within the last 25% of its lifetime.

**Error contract:** All errors raise `APIError` (from `app/core/exceptions.py`) with `status_code`, `detail`, and `code`. The frontend keys on `code` for typed error handling.

**Roles:** `ADMIN` · `REVIEWER` · `LECTURER`. LECTURER is read-only for publications; ADMIN drives all pipeline operations.

### Core domain services

| Service | Location | Purpose |
|---|---|---|
| Import pipeline | `services/import_pipeline/` | Scopus CSV ingestion: validate → normalize → diff → stage → apply. SHA-256 deduplication. |
| Normalization | `services/normalization/` | DOI, name, ORCID, title, text normalizers |
| Matching engine | `services/matching/` | Candidate generation + confidence scoring rules (rules/ sub-package) |
| Review service | `services/review_service.py` | ACCEPT/REJECT/SUPERSEDE review decisions with `review_reason_policy.py` enforcement |
| Affiliation workflow | `services/affiliation_workflow.py` | ADMIN-driven online affiliation collection + enrichment |
| Lecturer dataset | `services/lecturer_dataset/` | ICTU lecturer import, parser, rollback, export |

### Matching pipeline (key concept)

`services/matching/` implements a **read-only candidate generation** phase (no auto-confirm). Rules in `rules/` each emit `CandidateEvidence` with a `RuleId` tag. `candidate_persistence.py` saves to DB. The review workflow in `candidate_review_service.py` is the only path that changes candidate state. The `review_reason_policy.py` enforces D-2 policy: ACCEPT decisions require an explicit reason when evidence is name-only, the Scopus author is shared, or there are multiple candidates for one lecturer.

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

Migrations live in `backend/alembic/versions/`. **Append-only — never rewrite a published migration.** Current head: `c7f2a9b1d3e5`.

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
