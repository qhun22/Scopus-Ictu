# Completion-2 Freeze: Dashboard, Audit History, and Review History

**Frozen**: 2026-10-07
**Status**: COMPLETE — pending integration merge

## Scope

| Slice | Title | Branch | SHA |
|-------|-------|--------|-----|
| A1 | Safe Audit Read API | completion2/a1-audit-read-api | 062bb22e2bcdb76f1410fb4fd8d35234bc03e236 |
| A2 | Audit Logs UI | completion2/a2-audit-logs-ui | c644c4f829d546663fd76f12dc7a77f80b6c3814 |
| A3 | Review History API + UI | completion2/a3-review-history | 5d87354ad6fbaa4eecfd5d69cfc0ae90e65773e8 |
| A4 | Dashboard Summary API | completion2/a4-dashboard-api | 0fda664144b5f2fb9a28e5e5f95d7703f04d8b49 |
| A5 | Dashboard UI | completion2/a5-dashboard-ui | c5f1b3450f888ae6912280d824602487fb2a3334 |
| A6 | Regression / Freeze | completion2/a6-freeze | freeze draft at 85c1b997c9e9b009961d250547d638ef24514023; corrected-freeze-record tip reported in final audit output |

## Real Stacked PRs

| PR | Base | Title | State |
|----|------|-------|-------|
| #13 | main | Completion-2 A1 — Safe Audit Read API | OPEN/DRAFT |
| #14 | completion2/a1-audit-read-api | Completion-2 A2 — Audit Logs UI | OPEN/DRAFT |
| #16 | completion2/a2-audit-logs-ui | Completion-2 A3 — Review History | OPEN/DRAFT |
| #18 | completion2/a3-review-history | Completion-2 A4 — Dashboard Summary API | OPEN/DRAFT |
| #20 | completion2/a4-dashboard-api | Completion-2 A5 — Dashboard UI | OPEN/DRAFT |

## CI Carrier Runs

| Slice | Carrier PR | CI Run ID | Conclusion |
|-------|-----------|-----------|------------|
| A1 | #15 (closed) | 37632090226 | success |
| A2 | #12 (closed) | 37635609204 | success |
| A3 | #17 (closed) | 37642235987 | success |
| A4 | #19 (closed) | 37644901723 | success |
| A5 | #21 (closed) | 37648194336 | success |

## Regression Results

| Check | Result |
|-------|--------|
| Backend full regression | 686 passed, 0 failures |
| Frontend npm ci + build | SUCCESS |
| Browser runtime | NOT_RUN |
| Runtime API smoke | NOT_RUN |

## Endpoints

| Endpoint | Method | Auth | Read-Only |
|----------|--------|------|-----------|
| /api/v1/audits | GET | ADMIN | Yes |
| /api/v1/reviews/history | GET | ADMIN + REVIEWER | Yes |
| /api/v1/dashboard/summary | GET | ADMIN | Yes |

## Safety Guarantees

- No acceptance DB (scopus_ictu_acceptance_v2) mutation at any point
- No migration files in Completion-2
- Audit raw JSON fields not exposed (no before_state, after_state, event_metadata, entity_id, actor_user_id, ip_address, user_agent, request_id, correlation_id)
- Review evidence_snapshot not exposed; candidate_id, observation_id, reviewer_user_id, resulting_identity_id not exposed
- Dashboard latest import: `file_name` (not `filename`), `created_at` and `updated_at` (not `imported_at`); id, file_sha256, error_summary, normalization_summary not exposed
- Dashboard recent audit reuses safe A1 AuditListItem DTO
- Dashboard pending_review_count and review queue share the same semantic helper (current_reviewable_candidates_subquery)
- Latest import ordered by created_at DESC, id DESC — not imported_at (no such field on ScopusImport)
- Identity counts always contain all 4 statuses (zero-filled)
- No credentials or DB URLs committed

## Known Limitations

- Browser runtime verification not performed (no automated browser available)
- Runtime API smoke not performed (no live test user session available)
