# Scopus-Ictu

Institutional master-data reconciliation pipeline between ICTU Repository
and Scopus publication records.

---

## Architecture Status

| Item             | Value                                       |
| ---------------- | ------------------------------------------- |
| Architecture     | **v1.1 — FROZEN**                           |
| Skeleton         | **v1.1.1 — FINAL**                          |
| Milestone        | **M0 — Project Skeleton**                   |
| Governance       | STRICT                                      |
| Stack — Backend  | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL |
| Stack — Frontend | React + TypeScript + Vite + Tailwind + Ant Design |

> M0 contains **scaffolding and signatures only**.
> No business logic. No first Alembic migration. No real data.

---

## Repository Layout

```
.
├── docs/adr/                 Architecture Decision Records
├── data/                     Real source data is NEVER committed
├── backend/                  FastAPI service
├── frontend/                 React SPA
├── compose.yaml              Base compose (environment-neutral)
├── compose.local.yaml        Local overrides
└── compose.prod.yaml         Production reference overrides
```

See `docs/adr/` for the four frozen architectural decisions:

- `ADR-001-eid-canonical-identity.md`
- `ADR-002-ictu-repository-offline-ingestion.md`
- `ADR-003-audit-append-only.md`
- `ADR-004-identity-evidence-separation.md`

---

## M0 Scope (this commit)

- Folder skeleton as specified in MASTER CONSTRUCTION DIRECTIVE.
- Class / function signatures only.
- `pass`, `TODO`, `raise NotImplementedError` only.
- No CRUD, no matching, no parsing, no normalization.

Out of scope for M0:

- First real Alembic migration
- Production seed data
- Real JWT / hashing
- Real matching weights / thresholds
- Real crawler HTTP calls

---

## Local Development (M0)

### Backend

```bash
cd backend
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open <http://localhost:8000/docs>.

### Frontend

```bash
cd frontend
npm install
npm run build
```

### Docker Compose

```bash
docker compose -f compose.yaml -f compose.local.yaml up --build
```

Developer-specific overrides go to `compose.local.override.yaml`
(gitignored).

---

## Frozen Principles (summary)

1. ICTU Repository is master-data source, NOT ground truth.
2. Ground truth is the approved Lecturer ↔ Scopus Author identity mapping.
3. ICTU ingestion is OFFLINE (crawler → NDJSON → DB import).
4. Runtime business requests MUST NOT hit ICTU Repository directly.
5. Raw Scopus data and canonical data are separate.
6. Canonical publication identity = EID.
7. Provenance lives in `publication_raw_sources`.
8. Identity and evidence are separate.
9. Audit is append-only.
10. Revert = compensating revisions, never delete.