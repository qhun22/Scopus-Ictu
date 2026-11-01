# Scopus Multi-ID Completion Handover

Date: 2026-11-01 (Asia/Bangkok)

## Result

**PARTIAL_COMPLETE**

The existing backend multi-ID projection and review/revocation contracts were reused.
This change completes the missing ADMIN frontend action for revoking an approved
candidate identity. A full CORE_MULTI_ID_COMPLETE classification is not claimed because
authorized PostgreSQL and web E2E validation were not available.

## Implemented

- Added typed frontend API support for `POST /api/v1/reviews/candidates/{id}/revocation`.
- Added an ADMIN-only revoke action for `ACCEPTED` candidates in the review detail modal.
- Required a non-empty revocation reason and sent the current candidate version.
- Refreshed the queue and detail after successful revocation.
- Added Vietnamese and English translations for the revocation flow.

## Reused and unchanged

- Approved multi-ID projection, canonical EID publication deduplication, exclusion
  handling and revoked-identity filtering remain in the existing backend service.
- Human ACCEPT/REJECT review, candidate freshness checks and one-author ownership
  constraints remain server-authoritative.
- External Scopus profile merge automation remains **NOT_IMPLEMENTED**.
- `SOURCE_CLAIM_WORKFLOW_INACTIVE` remains unchanged.

## Files changed

- `frontend/src/api/reviews.ts`
- `frontend/src/types/review.ts`
- `frontend/src/pages/ApprovalQueue/index.tsx`
- `frontend/src/i18n/types.ts`
- `frontend/src/i18n/locales/vi.ts`
- `frontend/src/i18n/locales/en.ts`

## Validation

- `cd frontend && npm run build` — **PASS** (`tsc --noEmit` and Vite build).
- `cd backend && python -m pytest --noconftest tests/unit/test_author_normalizer_transactions.py tests/unit/test_author_position_drift.py tests/unit/test_scopus_author_parser.py -q`
  — **PASS** (75 passed).
- `cd backend && python -m pytest tests/integration/test_lecturer_scopus_projection.py tests/integration/test_g09_g10_g12_revocation_exclusion_counts.py tests/integration/test_candidate_review_service.py tests/integration/test_review_api.py -q --collect-only`
  — **NOT_EXECUTED**: `tests/conftest.py` refused collection because no
  allowlisted disposable PostgreSQL `TEST_DATABASE_URL` was available. The guard
  was not bypassed.
- `git diff --check` — **PASS**.
- PostgreSQL integration, concurrency and web E2E — **NOT_EXECUTED**.

## Feature classification

| Feature | Status |
|---|---|
| Multi-ID aggregation and canonical publication deduplication | IMPLEMENTED_NOT_TESTED (existing T05/T08/T10 projection coverage not executed this run) |
| ADMIN revocation UI integration | IMPLEMENTED_NOT_TESTED (frontend build PASS; no browser E2E) |
| Revocation lifecycle filtering | IMPLEMENTED_NOT_TESTED (existing G09/G10 integration coverage not executed this run) |
| Reviewer rejection, stale version, missing reason, repeated request and ownership conflict | IMPLEMENTED_NOT_TESTED (existing review integration coverage not executed this run) |
| External Scopus profile merge observation | NOT_IMPLEMENTED |
| SOURCE_CLAIM production workflow | BLOCKED_BY_AUTHORITY_OR_POLICY |

## Acceptance boundary

The existing backend tests contain synthetic scenarios for L1 with multiple approved
authors, overlapping EIDs, revocation retaining the other identity, G09 exclusion,
history/audit preservation, stale versions, repeated decisions and cross-lecturer
ownership conflicts. They were not executed in this environment because the database
safety guard had no approved disposable PostgreSQL target. No HTTP or web E2E result is
claimed, and no data was written to port 5432.

No commit, push or database migration was performed.
