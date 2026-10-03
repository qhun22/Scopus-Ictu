# Scopus-Ictu

Institutional master-data reconciliation between the ICTU Repository and
Scopus publication records.

---

## Implemented scope (complete/frozen)

| Milestone | Status | Description |
|---|---|---|
| **M0 / M1** | ✅ Frozen | Database foundation: PostgreSQL, Alembic migrations (`f4c8b1a2e9d7`), full schema with CHECK constraints, indexes, and audit contracts |
| **M2.1** | ✅ Frozen | Cookie-based JWT authentication, role-based authorization (`ADMIN`, `REVIEWER`, `LECTURER`) |
| **M2.2** | ✅ Frozen | Account administration: profile update, role change, lock/unlock, password reset; per-account audit trail and notifications |
| **M2.3** | ✅ Frozen | Lecturer master dataset: import, rollback, per-record provenance snapshots, duplicate name detection |
| **M2.4** | ✅ Frozen | Scopus raw CSV import lifecycle: SHA-256 deduplication, progress, cancellation, history, safe deletion |
| **M2.5A** | ✅ Frozen | ICTU lecturer dataset build and import pipeline; identity resolution (staff_code → email → name+department) |
| **M2.6A** | ✅ Frozen | Publication normalization from raw Scopus rows; canonical EID deduplication; `publication_raw_sources` provenance |

---

## Future / incomplete milestones

| Milestone | Description |
|---|---|
| **M2.7** | Author normalization: canonical Scopus author identity, name-variant resolution, ORCID matching |
| **M2.8** | Lecturer ↔ Scopus publication matching: linkage rules, confidence scoring |
| **M3** | Human review workflow: UI for reviewers to confirm/reject match candidates |
| **M4** | Complete publications management UI, dashboard, and audit reporting |

---

## Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL
- **Frontend:** React, TypeScript, Vite, Tailwind, Ant Design

---

## Repository data policy

Public ICTU lecturer source artifacts, schemas, reports, and provenance
snapshots are intentionally versioned for reproducibility. Private or
runtime-generated Scopus CSV exports remain local-only and are not committed.
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

The current migration head is `f4c8b1a2e9d7`.

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
- Alembic head: `f4c8b1a2e9d7` (do not rewrite).
