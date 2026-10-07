# Completion-1 Freeze — Publications, Search & Export

## Status

| Field | Value |
|---|---|
| Identifier | Completion-1 |
| Status | FROZEN |
| Integration readiness | VERIFIED |
| Production code tip | `486ee2fe43ff2c6f2ef942cf7b55b9733b9c3fb8` |
| A5 branch | `completion1/a5-runtime-freeze` |
| A5 production-source changes | false |
| Frozen at | 2026-10-07 |

## Source identity

| Component | Tip SHA | PR |
|---|---|---|
| main base | `d139746b31e2ea6d1d7643d76ec4ac46f8121ad9` | — |
| A1 — Canonical publication read API | `ae3efdde7362d576e5513b2460baa035e34d64e2` | #6 OPEN/DRAFT |
| A2 — Canonical publication browser UI | `e5a328fb867a1b42ecce4ac9c3021716ea2dec36` | #7 OPEN/DRAFT |
| A3 — Global search | `b702c080c1208d08d7a65103978a46efef0a7230` | #9 OPEN/DRAFT |
| A4 — Publication export | `486ee2fe43ff2c6f2ef942cf7b55b9733b9c3fb8` | #11 OPEN/DRAFT |

- Total production commits from main: **11**
- Total production changed files from main: **27**

## Capability chain

```
Canonical publication read API  (A1)
  → Canonical publication browser UI  (A2)
    → Global search  (A3)
      → Filtered publication export  (A4)
```

## Authorization

| Role | `/publications` | `/publications/{eid}` | `/search` | `/publications/export` |
|---|---|---|---|---|
| ADMIN | ✓ | ✓ | ✓ | ✓ |
| REVIEWER | ✓ | ✓ | ✓ | ✗ 403 |
| LECTURER | ✗ 403 | ✗ 403 | ✗ 403 | ✗ 403 |
| Unauthenticated | ✗ 401 | ✗ 401 | ✗ 401 | ✗ 401 |

## API contract

### `GET /api/v1/publications`
- Roles: ADMIN, REVIEWER
- Query params: `page`, `page_size`, `q` (substring, LIKE-escaped), `year`, `document_type`, `publication_stage`, `open_access_status`
- Response: paginated `{ items: [...], total, page, page_size }`
- Items include: `eid`, `title`, `year`, `doi`, `source_title`, `cited_by_count`, `document_type`, `publication_stage`, `open_access_status`
- No internal UUIDs exposed

### `GET /api/v1/publications/{eid}`
- Roles: ADMIN, REVIEWER
- Path: EID URL-encoded
- Response: publication detail + `authors[]` (ordered by `author_order`) + `approved_lecturer_links[]` (APPROVED status only)
- 404 `PUBLICATION_NOT_FOUND` for unknown EID

### `GET /api/v1/search`
- Roles: ADMIN, REVIEWER
- Query param: `q` (minimum 2 characters; 422 if shorter)
- Response: `{ lecturers: [...], publications: [...], scopus_authors: [...] }`
- No internal UUIDs exposed

### `GET /api/v1/publications/export`
- Role: ADMIN only
- Query params: `q`, `year`, `document_type`, `publication_stage`, `open_access_status` (same filter semantics as `/publications`)
- Response: `Content-Type: application/json; charset=utf-8`, `Content-Disposition: attachment; filename="ictu_publications_<timestamp>.json"`
- No pagination — all matching records returned
- **CRITICAL**: `/export` route declared statically before `/{eid}` — "export" never resolves as an EID
- Authentication: HttpOnly-cookie (`credentials: "include"`) — NOT localStorage token

## Export contract (JSON v1.0)

```json
{
  "dataset": {
    "schema_version": "1.0",
    "name": "ICTU Publication Export",
    "source": "SCOPUS_ICTU_SYSTEM_EXPORT",
    "export_id": "<uuid>",
    "exported_at": "<ISO-8601>",
    "record_count": <int>,
    "filters_applied": { <non-empty filter values only> }
  },
  "publications": [
    {
      "eid": "...", "doi": "...", "title": "...",
      "year": <int|null>, "source_title": "...",
      "cited_by_count": <int|null>,
      "document_type": "...", "publication_stage": "...", "open_access_status": "...",
      "authors": [{ "scopus_id": "...", "preferred_name": "...", "author_order": <int> }],
      "approved_lecturer_links": [{ "staff_code": "...", "full_name": "...", "scopus_id": "..." }]
    }
  ]
}
```

**Ordering**: publications by `year DESC NULLS LAST`, then `eid ASC` for determinism.

**Audit link**: `dataset.export_id == AuditEvent.entity_id` (entity_type `publication_export`, action `PUBLICATION_DATASET_EXPORTED`). Audit commit failure → 503 `DATABASE_UNAVAILABLE`, no file returned.

**Leakage exclusions**: no `id`, `publication_id`, `scopus_author_id`, `lecturer_id`, `raw_record_id`, `import_id`, `file_sha256`, `row_number`, `file_name`, `title_normalized`, `password_hash`, `auth_version`.

**APPROVED links only**: `LecturerScopusIdentity.status == "APPROVED"`. CANDIDATE, REJECTED, REVOKED identities excluded.

## Isolated runtime verification

Verified 2026-10-07 against a disposable schema on `scopus_m12_test` (37/37 checks PASS).

### A1/A2 Publication browser
- ADMIN list access: PASS
- REVIEWER list access: PASS
- LECTURER blocked (403): PASS
- List loads with data: PASS
- `q` filter: PASS
- Structured filter (`year`): PASS
- Pagination fields present: PASS
- NULL year preserved: PASS
- NULL `cited_by_count` preserved: PASS
- Zero `cited_by_count` != null: PASS
- Detail route: PASS
- Ordered authors (by `author_order`): PASS
- APPROVED lecturer links: PASS
- No internal UUID exposed: PASS

### A3 Global search
- ADMIN search: PASS
- REVIEWER search: PASS
- LECTURER blocked (403): PASS
- Short query (`q`<2 chars) rejected 422: PASS
- Grouped results (`lecturers`, `publications`, `scopus_authors`): PASS

### A4 Publication export
- ADMIN export: PASS
- REVIEWER blocked (403): PASS
- JSON schema_version 1.0: PASS
- All matching records exported (no pagination cap): PASS
- NULL citation preserved: PASS
- Zero citation preserved: PASS
- Authors included: PASS
- APPROVED lecturer links only: PASS
- No internal UUID / raw provenance / security fields: PASS
- `q` filter applies: PASS
- `filters_applied` recorded in dataset: PASS
- Deterministic ordering (year DESC NULLS LAST): PASS
- `dataset.export_id == AuditEvent.entity_id`: PASS
- `actor_user_id` equals the requesting admin: PASS
- Audit event written on success: PASS

**Browser automation**: NOT_AVAILABLE (no Playwright/Cypress installed; API-level verification used).

## Acceptance boundary

| Database | Role | Usage in Completion-1 |
|---|---|---|
| `scopus_ictu_acceptance_v2` | READ-ONLY reference | Connection unavailable during A5 freeze — snapshot NOT_AVAILABLE |
| `scopus_m12_test` | Functional runtime | Disposable schema per test run; all schemas dropped after run |

No writes, user creation, or export-audit events were performed on `scopus_ictu_acceptance_v2`.

## Regression

| Gate | Result |
|---|---|
| Backend test suite | **585 passed**, 12 warnings |
| Frontend build | **SUCCESS** (no TypeScript errors) |
| Alembic heads | **1 head** (`d3f7a1c9e2b4`) |
| Alembic upgrade head (scopus_m12_test) | **No migration applied** (already at head) |
| `git diff --check` | **CLEAN** |

## Production diff and safety

- No migration added: **true** — Completion-1 contains zero new Alembic migrations
- No secret exposed: **true**
- No DB dump: **true**
- No private runtime artifact: **true**
- No acceptance mutation: **true** — ACCEPTANCE_MUTATION=NONE
- Canonical WIP preserved: **true** — 14 pre-existing dirty paths, 0 new
- `LOCAL_DB_CREDENTIAL_ROTATION_RECOMMENDED=true`

## Stacked PR status

| PR | Title | State | Draft | Merged |
|---|---|---|---|---|
| #6 | Completion-1 A1 — Canonical publication read API | OPEN | true | false |
| #7 | Completion-1 A2 — Canonical publication browser UI | OPEN | true | false |
| #9 | Completion-1 A3 — Global search | OPEN | true | false |
| #11 | Completion-1 A4 — Publication export | OPEN | true | false |

Stack base: `completion1/a1-publication-read-api` → `completion1/a2-publication-browser-ui` → `completion1/a3-global-search` → `completion1/a4-publication-export`

## Completion-1 production commits

Commits from `d139746b31e2ea6d1d7643d76ec4ac46f8121ad9` (exclusive) through `486ee2fe43ff2c6f2ef942cf7b55b9733b9c3fb8` (inclusive):

| SHA | Message |
|---|---|
| `486ee2fe` | Bổ sung kiểm thử hợp đồng xuất dữ liệu công bố |
| `84f5359b` | Thêm chức năng xuất dữ liệu công bố |
| `b702c080` | Sửa khóa hiển thị kết quả tra cứu giảng viên |
| `b756ee1e` | Sửa kiểm thử thứ tự tra cứu giảng viên |
| `0805898a` | Sửa hợp đồng tra cứu tổng hợp |
| `d7ffeea0` | Thêm chức năng tra cứu tổng hợp |
| `e5a328fb` | Hoàn thiện hợp đồng bất đồng bộ giao diện công bố |
| `bd296160` | Sửa hợp đồng giao diện tra cứu công bố |
| `1e6972a2` | Thêm giao diện tra cứu công bố chuẩn hóa |
| `ae3efdde` | Bổ sung kiểm thử hợp đồng API công bố |
| `bec7ff49` | Thêm API tra cứu công bố chuẩn hóa |

## Final freeze result

```
C1_RUNTIME_VERIFIED=true
C1_INTEGRATION_READY=true
COMPLETION1_STATUS=FROZEN
PRODUCTION_CODE_TIP=486ee2fe43ff2c6f2ef942cf7b55b9733b9c3fb8
ACCEPTANCE_MUTATION=NONE
LOCAL_DB_CREDENTIAL_ROTATION_RECOMMENDED=true
```
