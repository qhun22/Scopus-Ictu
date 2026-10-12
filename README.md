# Scopus-Ictu

Institutional master-data reconciliation between the ICTU Repository and
Scopus publication records.

---

## Implemented scope

| Milestone | Status | Description |
|---|---|---|
| **M0 / M1** | ✅ | Database foundation: PostgreSQL, Alembic migrations, full schema with CHECK constraints, indexes, and audit contracts |
| **M2.1** | ✅ | Cookie-based JWT authentication, role-based authorization (`ADMIN`, `REVIEWER`, `LECTURER`) |
| **M2.2** | ✅ | Account administration: profile update, role change, lock/unlock, password reset; per-account audit trail and notifications |
| **M2.3** | ✅ | Lecturer master dataset: import, rollback, per-record provenance snapshots, duplicate name detection |
| **M2.4** | ✅ | Scopus raw CSV import lifecycle: SHA-256 deduplication, progress, cancellation, history, safe deletion |
| **M2.5A** | ✅ | ICTU lecturer dataset build and import pipeline; identity resolution (staff_code → email → name+department) |
| **M2.6A** | ✅ | Publication normalization from raw Scopus rows; canonical EID deduplication; `publication_raw_sources` provenance |
| **M2.7** | ✅ | Author/publication matching candidate generation, confidence scoring, candidate persistence |
| **M2.8** | ✅ | Lecturer ↔ Scopus publication read projection and API; lecturer-facing "My Publications" UI (read-only) |
| **M3** | ✅ | Human review workflow for match candidates; author affiliation per-publication data model and import |
| **M4** | ✅ | Unlinked LECTURER account handling; affiliation reconciliation workflow (ADMIN-driven, evidence-based) |

This is an ongoing undergraduate thesis project (đồ án tốt nghiệp). Scope
above reflects what has corresponding migrations, API endpoints, and tests
in the current codebase — it is not a final/frozen release.

### In progress

The current focus is the CSV-only ingestion path (no pre-built JSON
dataset): new Scopus CSV import → online affiliation collection per author →
ADMIN evidence-based correction → LECTURER read-only lookup. See
`docs/planning/` for the active task breakdown.

---

## Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL
- **Frontend:** React, TypeScript, Vite, Tailwind, Ant Design

---

## Repository data policy

**No real lecturer or Scopus personal data is committed to this repository.**
Only the dataset *schema* (`data/lecturers/schema/`) and fully synthetic
test fixtures (using `example.invalid` email domains) are versioned, for
reproducibility of the import/parsing logic. Real ICTU lecturer records,
raw crawl snapshots, and Scopus CSV exports are local-only, gitignored, and
must never be committed — see `.gitignore` for the enforced paths.
Credentials and local environment files are never committed.

---

## Environment configuration

### Backend

The backend reads `backend/.env` (gitignored). Copy the placeholder template:

```bash
cp backend/.env.example backend/.env
```

Fill in your local PostgreSQL credentials, a long random `SECRET_KEY`, and
set `ENVIRONMENT=local` for development.

### Frontend

```bash
cd frontend
cp .env.example .env.local  # if present
```

---

## Local development

### Backend

```bash
cd backend
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m pytest -q
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

### Docker Compose

```bash
docker compose -f compose.yaml -f compose.local.yaml up --build
```

Use `compose.local.override.yaml` for developer-specific overrides; it is
ignored by Git.

---

## Alembic workflow

Migrations are append-only and must not be rewritten after publication.
Inspect the current head:

```bash
cd backend
python -m alembic heads
python -m alembic upgrade head
```

The current migration head is `f6a1b2c3d4e5`.

---

## Developer tools

### Demo account seeding

```bash
# admin@gmail.com (ADMIN) is auto-created if missing.
# DEMO_ADMIN_PASSWORD required only when the admin account is absent.
# DEMO_USER_PASSWORD required only when the lecturer account is absent.
DEMO_USER_PASSWORD=your_password python -m scripts.seed_demo_users
```

### Acceptance testing (M2.6A)

```bash
cd backend
python scripts/run_m2_6a_acceptance.py --dataset ../data/scopus/local.csv
```

Requires `ENVIRONMENT != prod` and an explicit dataset path.
Do not commit private Scopus exports.

### Benchmark (M2.6A)

```bash
cd backend
python scripts/benchmark_m2_6a_10k.py
```

Creates a disposable PostgreSQL schema (`bench_m26a_*`), runs normalization,
reports query count and duration, then drops the schema.
Requires `ENVIRONMENT != prod`.

---

## Database isolation

Tests (`pytest`) must never mutate the development database.
See `backend/tests/conftest.py` for the isolation guard contract.
For CI, set `ENVIRONMENT=test` and `TEST_DATABASE_URL` to an isolated
test database URL.

---

## Git conventions

- Credentials, `.env`, and local-only CSV files are never committed.
- Migrations are append-only.
- Alembic head: `f6a1b2c3d4e5` (do not rewrite).
- Real lecturer/Scopus data must never be committed — see `.gitignore`.
