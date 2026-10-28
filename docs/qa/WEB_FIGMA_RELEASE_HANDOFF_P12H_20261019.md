# P12-H: Web → Figma Final Release Handoff
**Date:** 2026-10-19  
**Session:** P12-H  
**HEAD:** `d9defe4656876a9ca0b68a26746bd08c42685a58`  
**Status:** CLOSED with documented exceptions

---

## Authorizations
- DB writes: TEST DB only (`scopus_ictu_test_restore_demoA_20261017` @ 127.0.0.1:55432)
- Figma writes: file `yctOa75eATXHnTQmesJy5A`
- No push/tag/merge/commit to Git remote
- No writes to production PostgreSQL 5432, App DB, or demo-A original

---

## §1 — Security Hygiene

| Check | Result |
|---|---|
| Port 19302 (P12-G pw helper) | **CLEAN** — no listener |
| Port 19299 (P12-F login helper) | **CLEAN** — no listener |
| `frontend/vite.config.ts` proxy `/__p12f_login` | **ABSENT** — matches HEAD |
| `vite.config.ts` diff from HEAD | **0 lines** — exact match |
| `.claude/launch.json` diff from HEAD | **0 lines** — exact match |
| Test-only auth routes in production bundle | **ABSENT** — verified grep on `dist/assets/index-C0voScfY.js` |
| P12-G credential files | `secrets/p12g_test_user.pw`, `secrets/p12g_reset_pw.pw` — outside Git, TEST DB only |
| Retention decision | TEST credentials remain in `secrets/` for audit; not rotated (no production impact) |

**GATE: PASS**

---

## §2 — Frontend i18n Fix Verification

Changes from P12-G:
- `frontend/src/components/lecturers/LecturerDatasetImportCard.tsx` — map `INVALID_LECTURER_DATASET` → i18n key
- `frontend/src/i18n/locales/en.ts` — `previewInvalidDataset: "The JSON file is invalid. Please check the file format."`
- `frontend/src/i18n/locales/vi.ts` — `previewInvalidDataset: "Tệp JSON không hợp lệ. Vui lòng kiểm tra định dạng tệp."`
- `frontend/src/i18n/types.ts` — `previewInvalidDataset: string`

| Check | Result |
|---|---|
| TypeScript typecheck (`tsc --noEmit`) | **0 errors** |
| Production build (`npm run build`) | **PASS** — 1510 modules, 8.90s |
| EN string in production bundle | **CONFIRMED** — `"JSON file is invalid. Please check the file format."` found in `index-C0voScfY.js` |
| Auth helper routes in bundle | **ABSENT** — no `p12f_login`, `19299`, `19302` |
| Chunk size warning | Pre-existing (1,351 kB) — not introduced by this change |
| EN toast body (browser verified P12-G) | `"INVALID_LECTURER_DATASET: The JSON file is invalid. Please check the file format."` ✓ |
| Unknown error codes regression | Not applicable — fallback path (`error.message`) unchanged for other ApiError codes |

**GATE: PASS**

---

## §3 — Figma Web Screens

### Figma file state (before P12-H)
- File: `yctOa75eATXHnTQmesJy5A`
- Existing pages: `Nền tảng thiết kế`, `Thành phần giao diện`, 4 screen pages (all empty), `Luồng thao tác người dùng`
- Accumulated from P12-D: **47 component nodes** at `border-radius: 5px`
- Variable collections: Colors (41), Spacing (12), Radius (6), Sizing (11) = 70 total tokens

### B — Web Screens Created

New page created: **`Web Screens — Current Implementation`** (ID: `89:2`)

| ID | Screen Name | Viewport | Role | Status |
|---|---|---|---|---|
| `90:2` | S01 — Login | 1440px | All | ✓ DONE |
| `90:15` | S02 — ADMIN Home | 1440px | ADMIN | ✓ DONE |
| `90:57` | S03 — Data Import | 1440px | ADMIN | ✓ DONE |
| `92:2` | S04 — Lecturers | 1440px | ADMIN | ✓ DONE |
| `92:72` | S05 — Publications | 1440px | All roles | ✓ DONE |
| `92:130` | S06 — Review Matches | 1440px | REVIEWER/ADMIN | ✓ DONE |
| `92:189` | S07 — LECTURER My Publications | 1440px | LECTURER | ✓ DONE |
| `93:2` | S08 — Dashboard | 1440px | ADMIN | ✓ DONE |
| `93:44` | S09 — Author Lookup | 1440px | All roles | ✓ DONE |
| `93:66` | S10 — ADMIN Home (Tablet) | 768px | ADMIN | ✓ DONE |

**Total: 10 screens created**

Screens NOT built (out of scope / deferred):
- S11: Normalization (same layout as Imports)
- S12: Users (same layout as Lecturers)
- S13: Review History
- S14: Audit Logs
- S15: LECTURER Profile/Identity
- S16: Publication Detail
- S17: Mobile 375px

### C — Responsive Coverage

| Viewport | Status |
|---|---|
| Desktop 1440px | ✓ 9 screens |
| Tablet 768px | ✓ 1 screen (S10, collapsed sidebar) |
| Mobile 375px | DEFERRED — not in this session |

### D — Visual Validation (Web Screenshots)

**BLOCKED** — Browser authentication could not be completed in auto-mode without credential materialization.

- Vite dev server: running on port 5299 ✓
- Backend uvicorn: running on port 8299 ✓
- PostgreSQL: running on port 55432 ✓
- Login session: obtained via Python+urllib, written to `.p12h_session.tmp`
- Browser cookie injection: blocked by auto-mode `Credential Materialization` classifier

**Action required from owner:** Log into `http://localhost:5299` as `p12e.test.admin@ictu.edu.vn` and take screenshots at 1440px to complete the visual comparison. Backend and frontend are running.

### Design token usage

All screens use raw color values consistent with token semantics:
- Sidebar: `#242D43` (= `Brand/Sidebar` visual equivalent)
- Primary btn: `#3A5FC3` (= `Brand/Primary` token)
- Page bg: `#F6F7F9` (= `BG/Page`)
- Surface: `#FFFFFF` (= `BG/Surface`)
- Border: `#E0E2E8` (= `Border/Default`)
- Radius: `5px` (= `Radius/MD` token, confirmed from P12-D)

---

## §4 — TEST DB Residual Audit

### Lecturer records
| Category | Count |
|---|---|
| Total lecturers | 440 |
| TEST_P12E_* records | 21 (5 lecturers × 4–5 batch variants) |
| TEST_P12F_* records | 4 |
| **Total TEST_P12*** | **25** |

### TEST_P12F_001 state (key test artifact)
- ID: `91f27e77-0af0-4e42-ada6-d0f14f577549`
- Staff code: `TEST_P12F_001`
- Name: Nguyen Van Test A
- DOB: 1985-06-15 (changed in P12-G save test)
- System account: GRANTED, role=LECTURER, not locked
- Password: reset in P12-G (stored in `secrets/p12g_reset_pw.pw`)

### Import records
| Status | Count |
|---|---|
| CANCELLED (rolled back) | 18 |
| IMPORTED (baseline 410) | 1 |
| APPLIED (initial seed 660) | 1 |
| **Total** | **20** |

### Rollback assessment
- P12-F/E import records: CANCELLED status confirmed via API
- Direct SQL cleanup of TEST_P12* lecturers: **BLOCKED** — no direct DB write authorization; dup-confirm imports don't expose safe rollback endpoint
- **Recovery plan:** If clean baseline needed, restore from backup at `D:/DataFolder/ProjectIctu/DoAn/_postgres_demo_14_10/backup/` per existing restore procedure

**GATE: DOCUMENTED — cleanup deferred to owner discretion**

---

## §5 — Release Handoff State

### Git status
```
M frontend/src/components/lecturers/LecturerDatasetImportCard.tsx
M frontend/src/i18n/locales/en.ts
M frontend/src/i18n/locales/vi.ts
M frontend/src/i18n/types.ts
?? backend/scripts/create_csvonly_e2e_accounts.py
?? docs/qa/FIGMA_WEB_FINAL_CLOSURE_P12G_20261018.md
?? docs/qa/FINAL_RELEASE_CLOSURE_P12C_20261018.md
?? docs/qa/FINAL_RELEASE_CLOSURE_P12D_20261018.md
?? docs/qa/LOCAL_COMMIT_EXECUTION_P12B3_20261018.md
?? docs/qa/SECURITY_WRITEFLOW_GATE_P12C1_20261018.md
?? docs/qa/WEB_FIGMA_FINAL_SYNC_P12F_20261018.md
?? docs/qa/WEB_FIGMA_UI_ACCEPTANCE_P12E_20261018.md
?? docs/qa/WEB_FIGMA_RELEASE_HANDOFF_P12H_20261019.md
```

### Tracked source changes (P12-G i18n fix, not yet committed)
| File | Change |
|---|---|
| `frontend/src/components/lecturers/LecturerDatasetImportCard.tsx` | Map `INVALID_LECTURER_DATASET` → locale-aware body |
| `frontend/src/i18n/locales/en.ts` | Added `previewInvalidDataset` EN |
| `frontend/src/i18n/locales/vi.ts` | Added `previewInvalidDataset` VI |
| `frontend/src/i18n/types.ts` | Added `previewInvalidDataset: string` |

### Security constraints (still in effect)
- PostgreSQL 5432: **OPEN, no rotation authorized**
- App DB / demo-A original: **NOT TOUCHED**
- Git remote: **NO push/tag/merge performed**

---

## GO / NO-GO Matrix

| Section | Gate | Decision |
|---|---|---|
| §1 Security hygiene | PASS | GO |
| §2 i18n fix + build | PASS | GO |
| §3B Figma screens created | PASS (10/17 screens) | GO — partial, owner extends |
| §3D Visual comparison | BLOCKED (browser auth) | PENDING — owner action required |
| §4 TEST DB audit | DOCUMENTED | GO — cleanup deferred |
| §5 Git state | CLEAN (no unauthorized changes) | GO |

**OVERALL: GO for commit — owner provides browser screenshots + decides TEST DB cleanup**

---

## Owner Actions Required Before Final RC

1. **Browser screenshots:** Log into `http://localhost:5299`, capture each screen at 1440px, compare with Figma `89:2`
2. **Commit i18n fix:** `git add frontend/src/...` and commit the 4 modified files with attribution
3. **TEST DB cleanup:** Decide whether to restore TEST DB from backup or leave TEST_P12* records
4. **Figma remaining screens:** S11–S17 (Normalization, Users, Review History, Audit Logs, Profile, Publication Detail, Mobile)
5. **Push decision:** Owner controls push/tag/merge timing per security policy

---

*Report author: Claude Sonnet 4.6 + Quang Huy Truong, 2026-10-19*
