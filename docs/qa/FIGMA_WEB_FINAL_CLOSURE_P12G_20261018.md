# P12-G: Final Web → Figma Closure & QA Sign-off
**Date:** 2026-10-18  
**Session:** P12-G  
**HEAD:** `d9defe4656876a9ca0b68a26746bd08c42685a58`  
**Status:** CLOSED — All in-scope items resolved or formally documented

---

## Authorizations (carried from P12-E/F)
- DB writes: TEST DB only (`scopus_ictu_test_restore_demoA_20261017` @ 127.0.0.1:55432)
- No writes to production PostgreSQL 5432, App DB, demo-A original, or teacher DB
- No push/tag/merge/commit to Git remote
- No rewrite of Git history

---

## §A — Preservation Gate

| Check | Result |
|---|---|
| HEAD verified | `d9defe4656876a9ca0b68a26746bd08c42685a58` ✓ |
| Backend uvicorn | port 8299, TEST DB @ 55432 ✓ |
| Frontend Vite | port 5299 ✓ |
| PostgreSQL | port 55432 (recovered via pg_ctl start after outage) ✓ |
| Auth session | `p12e.test.admin@ictu.edu.vn` JWT cookie valid ✓ |

**GATE: PASS**

---

## §B — Figma Design Sync

### Carried from P12-D (2026-10-16)
- 16 control component nodes updated to `border-radius: 5px` in Figma file `yctOa75eATXHnTQmesJy5A`
- Nodes covered: `9:5`, `9:7`, `9:13`, `9:16`, `9:19`, `9:29`, `9:33`, `9:37`, `10:10`, `10:13`, `10:16`, `10:19`, `10:22`, `10:25`, `10:28`, `10:52`

### P12-G Scope Decision
- `Web Screens — Current Implementation` page creation: **NOT EXECUTED**
- Reason: Figma MCP rate-limit constraints encountered during P12-D/E; and P12-G authorized scope did not include a new full web-screen capture session
- Per P12-G instructions: "Không nhận 100% Web↔Figma synchronization nếu screens chưa được cập nhật"
- **Decision recorded:** Figma web screens page deferred to next sprint milestone

**GATE: PARTIAL (token synced, screens deferred — documented)**

---

## §C — UI-14 EN Toast Verification

All toasts tested in real browser (locale=EN, port 5299) with authenticated admin session.

### UI-14-A: Save Lecturer (success)
- **Action:** Edit lecturer date-of-birth (TEST_P12F_001), click Save
- **Toast:** Title `"Success"` / Body `"Lecturer Nguyen Van Test A updated successfully."` ✓ EN

### UI-14-B: Lock Account
- **Action:** Click lock icon on TEST_P12F_001 (after granting account)
- **Toast:** Title `"Account locked"` / Body `"The account of Nguyen Van Test A has been locked."` ✓ EN

### UI-14-B2: Unlock Account
- **Action:** Click unlock icon on TEST_P12F_001 (account was locked)
- **Toast:** Title `"Account unlocked"` / Body `"Nguyen Van Test A can sign in again."` ✓ EN

### UI-14-C: Reset Password
- **Action:** Click reset password on TEST_P12F_001, fill new password via one-shot server (port 19302), confirm
- **Toast:** Title `"Password reset"` / Body `"The password of Nguyen Van Test A has been updated."` ✓ EN

### UI-14-C (i18n error fix): Preview Failed Toast Body
- **Pre-fix finding:** Backend returns `{"detail": "Tệp JSON không hợp lệ...", "code": "INVALID_LECTURER_DATASET"}` — frontend displayed Vietnamese body verbatim even when locale=EN
- **Root cause:** `LecturerDatasetImportCard.tsx:182–189` passed `error.message` directly without locale mapping for `ApiError`
- **Fix applied:** Added `previewInvalidDataset` i18n key to `types.ts`, `en.ts`, `vi.ts`; updated component to use `t.lecturerImport.previewInvalidDataset` when `code === "INVALID_LECTURER_DATASET"`
- **Verified (post-fix):** Toast body = `"INVALID_LECTURER_DATASET: The JSON file is invalid. Please check the file format."` ✓ EN

**GATE: PASS (4/4 toasts EN, i18n fix applied and verified)**

---

## §D — TEST DB Data Integrity Audit

### Record counts (before P12-G session)
| Category | Count |
|---|---|
| Total lecturers | ~440 |
| TEST_P12* records | 30 (5 P12-F + 25 P12-E) |
| P12-G new accounts granted | 1 (TEST_P12F_001) |

### Rollback status
- P12-F imports (3 sessions): **Rolled back** via API during P12-F ✓
- P12-E imports (25 records): **BLOCKED** — dup-confirm imports do not have snapshot_ids, rollback API returns error
- P12-F additional import (1, 0/5): rolled back during P12-F ✓

### Residual test artifacts (TEST DB only, not production)
| Artifact | State | Action |
|---|---|---|
| TEST_P12F_001 (Nguyen Van Test A) | DOB changed to 1985-06-15, account granted (LECTURER role), password reset | Documented, TEST DB only |
| `secrets/p12g_test_user.pw` | Random password for granted account | Outside Git, TEST DB only |
| `secrets/p12g_reset_pw.pw` | Reset password generated for test | Outside Git, TEST DB only |
| Scratch scripts (grant_account_p12g.py, pw_server_p12g.py, inject_reset_pw.py) | In `_postgres_demo_14_10/scratch/` | Not tracked in Git |

**GATE: PARTIAL (residuals documented, rollback of P12-E dup-confirm records blocked — no safe mechanism exists)**

---

## §E — Temporary Infrastructure Cleanup

| Item | Action | Status |
|---|---|---|
| `/__p12f_login` proxy in `frontend/vite.config.ts` | Removed via `git checkout -- frontend/vite.config.ts` | ✓ Restored to HEAD |
| `frontend-p12f` config in `.claude/launch.json` | Removed via `git checkout -- .claude/launch.json` | ✓ Restored to HEAD |
| Login helper server (port 19299) | Was never started in P12-G; P12-F server already exited | ✓ Not running |
| pw_server_p12g.py (port 19302) | Served 2 requests then exited | ✓ Not running |

**GATE: PASS**

---

## §F — Security Gate (final)

| Constraint | Status |
|---|---|
| Không ghi PostgreSQL 5432 | ✓ No writes to port 5432 |
| Không rotate credentials | ✓ No credential rotation |
| Không xóa transcripts/.tmp | ✓ Not touched |
| Không ghi App DB hoặc demo A gốc | ✓ Only TEST DB written |
| Không push/tag/merge GitHub | ✓ No remote operations |
| Không migration ngoài DB TEST | ✓ |
| Không rewrite Git history | ✓ |
| Không stage, commit, tag hoặc push | ✓ All work untracked/unstaged |
| Password không in ra chat/log | ✓ Injected via one-shot server |

**SECURITY GATE: PASS**

---

## GO / NO-GO Matrix

| Section | Gate | Decision |
|---|---|---|
| §A Preservation | PASS | GO |
| §B Figma sync | PARTIAL (documented) | GO — screens deferred per policy |
| §C UI-14 toasts | PASS | GO |
| §C i18n error fix | PASS | GO |
| §D TEST DB cleanup | PARTIAL (rollback blocked) | GO — documented limitation |
| §E Infrastructure cleanup | PASS | GO |
| §F Security | PASS | GO |

**OVERALL: GO — P12-G CLOSED**

---

## Files Changed (P12-G, untracked)

| File | Change |
|---|---|
| `frontend/src/i18n/types.ts` | Added `previewInvalidDataset: string` |
| `frontend/src/i18n/locales/en.ts` | Added EN string for `previewInvalidDataset` |
| `frontend/src/i18n/locales/vi.ts` | Added VI string for `previewInvalidDataset` |
| `frontend/src/components/lecturers/LecturerDatasetImportCard.tsx` | Map `INVALID_LECTURER_DATASET` to i18n key instead of raw backend message |
| `docs/qa/FIGMA_WEB_FINAL_CLOSURE_P12G_20261018.md` | This document |

Previously written (P12-F, also untracked):
- `docs/qa/WEB_FIGMA_FINAL_SYNC_P12F_20261018.md`
- `backend/scripts/create_csvonly_e2e_accounts.py`
- Other P12 QA docs in `docs/qa/`

---

*Report author: Claude Sonnet 4.6 + Quang Huy Truong, 2026-10-18*
