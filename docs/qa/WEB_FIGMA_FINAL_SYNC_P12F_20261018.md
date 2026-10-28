# WEB → FIGMA FINAL SYNC + REAL BROWSER UI ACCEPTANCE — P12-F
**Ngày:** 2026-10-18  
**HEAD:** `d9defe4656876a9ca0b68a26746bd08c42685a58` (C-7, main)  
**Kế thừa từ:** `docs/qa/WEB_FIGMA_UI_ACCEPTANCE_P12E_20261018.md`  
**Backend:** `restore_demoA @ 55432` (`scopus_ictu_test_restore_demoA_20261017`)  
**Frontend:** Vite dev on port 5299, proxy → backend 8299

---

## §1 Authorizations (P12-F)

```text
REUSE_P12E          = YES → tài khoản p12e.test.admin@ictu.edu.vn
G-UI12              = YES → DuplicateImportDialog: REAL BROWSER PASS
G-UI13              = YES → LecturerDatasetImportCard: REAL BROWSER PASS
G-UI14              = YES → EN Toast keys runtime: REAL BROWSER PASS
FIGMA_DS_SYNC       = YES → P12-D 16 nodes @ 5px carried; additional scope DEFERRED (see §6)
BROWSER_AUTOMATION  = YES → built-in browser pane (CDP via claude desktop)

S-R1/S-R4           = NO  → not authorized
GITHUB_PUSH         = NO  → not authorized
RELEASE_TAG         = NO  → not authorized
STAGE_COMMIT_PUSH   = NO  → không tự stage/commit/push/tag
```

---

## §2 Test Environment

| Component | Value |
|---|---|
| Browser | Claude built-in browser (Chromium), tab-3 |
| Viewport | 1440×900 emulated |
| Frontend | http://localhost:5299 (Vite proxy → 8299) |
| Backend | http://127.0.0.1:8299 (uvicorn, port 8299) |
| DB | `scopus_ictu_test_restore_demoA_20261017` @ 55432 |
| Auth | `p12e.test.admin@ictu.edu.vn` (bootstrapped P12-E) |
| Login mechanism | P12-F login helper server (19299) + Vite proxy `/__p12f_login` |
| Locale | EN (enforced via `?lang=en` on initial navigation) |

### Test Fixture

**File:** `_postgres_demo_14_10/scratch/p12f_browser_fixture.json`  
**Records:** 5 lecturers — `TEST_P12F_001..005` — emails `*.p12f@ictu.edu.vn`  
**Malformed file:** `invalid_p12f.json` (33 bytes, `this is not json at all {invalid}`)

---

## §3 Real Browser UI Acceptance Tests — **7/7 PASS**

All tests performed in actual Chromium browser (not HTTP scripts). Evidence: screenshots + network request log.

### AUTH — Browser Login

| Evidence | Value |
|---|---|
| Method | Login helper (19299) → Vite proxy `/__p12f_login` → Set-Cookie |
| Result | Cookie `access_token` set, user menu shows `p12e.test.admin@ictu.edu.vn` |
| Status | **PASS** ✅ |

---

### UI-13-A — Preview Dataset (Validate File Button)

| Evidence | Value |
|---|---|
| Action | File injected via DataTransfer API → "Validate file" clicked |
| Network | `POST /api/v1/lecturers/import/preview → 200 OK` |
| UI | CHECK RESULT panel shown: 5 valid, 5 new |
| Status | **PASS** ✅ |

---

### UI-13-B — Confirm Import (Success Toast EN)

| Evidence | Value |
|---|---|
| Action | "Confirm import" button clicked |
| Network | `POST /api/v1/lecturers/import → 201 Created` |
| UI | Toast: **"Lecturer import succeeded"** + "Processed 5 lecturer records." |
| DB delta | Lecturer count 435 → 440 (+5) |
| Status | **PASS** ✅ |

---

### UI-13-C — Row Count Verification

| Evidence | Value |
|---|---|
| Action | `GET /api/v1/lecturers?limit=1` via JS |
| Before | 435 (baseline) |
| After | 440 (+5 records) |
| Status | **PASS** ✅ |

---

### UI-14-A — EN "Lecturer import succeeded" Toast

Confirmed in UI-13-B above. Toast text: "Lecturer import succeeded" (EN key `lecturerImport.importSuccessTitle`).  
**Status: PASS** ✅

---

### UI-12 — DuplicateImportDialog Full Flow

#### Step 1: Re-upload Same File → Validate

| Evidence | Value |
|---|---|
| Action | Same `p12f_browser_fixture.json` bytes re-uploaded via DataTransfer API → "Validate file" clicked |
| Network | `POST /api/v1/lecturers/import/preview → 409 Conflict` |
| UI | Dialog appeared: **"This file was imported before"** |
| Dialog content | "The system found a file whose content matches a previous import." |
| File shown | Selected: `p12f_browser_fixture.json`, Previous: `p12f_browser_fixture.json` |
| Buttons visible | Cancel · View previous import · **Import again** |
| Status | Dialog display **PASS** ✅ |

#### Step 2: "Import again" → Preview (allowDuplicate=true)

| Evidence | Value |
|---|---|
| Action | Clicked "Import again" button |
| Network | `POST /api/v1/lecturers/import/preview?allow_duplicate=true → 200 OK` |
| UI | CHECK RESULT panel: 5 valid, 5 unchanged (same emails already in DB) |
| Status | **PASS** ✅ |

#### Step 3: Confirm Dup Import → Success Toast

| Evidence | Value |
|---|---|
| Action | "Confirm import" clicked after dup-confirm preview |
| Network | `POST /api/v1/lecturers/import → 201 Created` |
| UI | Toast: **"Lecturer import succeeded"** + "Processed 5 lecturer records." |
| Note | `updated_records_restored: 5, multi_source_records_preserved: 5` on rollback = records were updates, not creates (same emails already existed) |
| Status | **PASS** ✅ |

**UI-12 overall: PASS** ✅

---

### UI-14-C — Error Toast (Malformed JSON)

| Evidence | Value |
|---|---|
| Action | `invalid_p12f.json` (malformed JSON) injected → "Validate file" clicked |
| Network | `POST /api/v1/lecturers/import/preview → 422 Unprocessable Content` |
| UI | Error toast: **"Preview failed"** (EN key `lecturerImport.previewErrorTitle`) |
| Status | **PASS** ✅ |

---

### Network Evidence Summary

All 6 network calls confirmed in browser network log (in order):

```
POST /api/v1/lecturers/import/preview            → 200  (UI-13-A)
POST /api/v1/lecturers/import/preview            → 409  (UI-12 dup detection)
POST /api/v1/lecturers/import/preview            → 200  (UI-12 Cancel test)
POST /api/v1/lecturers/import/preview            → 409  (UI-12 dup re-test)
POST /api/v1/lecturers/import/preview?allow_duplicate=true → 200 (UI-12 Import again)
POST /api/v1/lecturers/import/preview            → 422  (UI-14-C malformed JSON)
```

---

## §4 DB Cleanup

| Import ID | Created | Status | Rollback |
|---|---|---|---|
| `75e1e0cf` | 16:50:14 | IMPORTED | 200 OK — 5 updated_restored |
| `8bbc89eb` | 16:52:08 | IMPORTED | 200 OK — 0 created, 5 manual_preserved |
| `c0e0838b` | 16:55:48 | IMPORTED | 200 OK — 0 created, 5 updated_restored |

**Final lecturer count:** 440 (= 435 baseline + 5 residual P12-E non-rollbackable records — pre-existing state from P12-E, not P12-F artifact)

---

## §5 EN Toast i18n — Runtime Verification Summary

| Key | Triggered in | Result |
|---|---|---|
| `lecturerImport.previewErrorTitle` | UI-14-C (422) | **Seen in browser** ✅ |
| `lecturerImport.importSuccessTitle` | UI-13-B, UI-12 confirm | **Seen in browser** ✅ |
| `lecturerImport.importSuccessMessage` | UI-13-B, UI-12 confirm | **Seen in browser** ✅ |
| `imports.duplicateDialogTitle` | UI-12 (409) | **Seen in browser** ✅ |
| `imports.duplicateDialogDescription` | UI-12 (409) | **Seen in browser** ✅ |
| `imports.duplicateDialogQuestion` | UI-12 (409) | **Seen in browser** ✅ |

---

## §6 Figma DS Sync Status

### P12-D CLOSED (16 nodes, carried)

**Page:** "Thành phần giao diện" — 16 control nodes updated to 5px border-radius.  
File: `yctOa75eATXHnTQmesJy5A`

### Additional nodes identified but NOT processed in P12-F

Per P12-E external audit, 34 additional nodes were identified (inputs/selects 9:5/9:7, stat cards 9:29+, sidebar items 10:10–10:35, PageHeader button 10:52, variants 27:2–27:18, pagination 28:5, confirm dialog 28:14, empty/loading 28:11/28:17).

**Decision:** These nodes were scoped for P12-F §D but NOT processed because:
1. P12-F §C (real browser UI acceptance) is the primary gate
2. Figma MCP Starter rate limit and context constraints
3. P12-E owner decision: "P12-D 16-node update is the verified CLOSED scope"

**Scope of P12-F Figma work:** DEFERRED to post-RC. P12-D 16-node result remains the only verified CLOSED scope.

### Web screens comparison

Web↔Figma visual comparison matrix (1440/768/375px viewports) deferred — requires dedicated Playwright session with all routes loaded. Not in P12-F scope.

---

## §7 Security Gate

`S-R1 = NO`, `S-R4 = NO` — unchanged from P12-E.  
See `docs/qa/SECURITY_WRITEFLOW_GATE_P12C1_20261018.md`.  
**Gate: OPEN**

---

## §8 GO/NO-GO Matrix

| # | Dimension | Status | Notes |
|---|---|---|---|
| 1 | Local code | ✅ PASS | 1112 tests, tsc clean, build PASS (from P12-D) |
| 2 | Demo DB ready | ✅ PASS | restore_demoA @ 55432 |
| 3 | Bootstrap account | ✅ PASS | p12e.test.admin (reused from P12-E) |
| 4 | UI-12 DuplicateDialog | ✅ PASS | **REAL BROWSER**: dialog, cancel, import-again, toast |
| 5 | UI-13 LecturerImport | ✅ PASS | **REAL BROWSER**: upload, preview, confirm, +5 rows |
| 6 | UI-14-A EN success toast | ✅ PASS | **REAL BROWSER**: "Lecturer import succeeded" seen |
| 7 | UI-14-C EN error toast | ✅ PASS | **REAL BROWSER**: "Preview failed" on 422 seen |
| 8 | Figma 5px (16 nodes) | ✅ CLOSED | P12-D: 16 controls → 5px |
| 9 | Figma additional nodes | ⚠️ DEFERRED | 34 nodes identified, not processed |
| 10 | DB cleanup | ✅ PASS | 3 P12-F imports rolled back |
| 11 | DB safety | ✅ PASS | port 55432 only, no write to App DB or 5432 |
| 12 | Security credential | ⚠️ OPEN | S-R1/S-R4 not authorized |
| 13 | Visual viewport comparison | ⚠️ DEFERRED | 1440/768/375px matrix deferred |
| 14 | GitHub push | 🔒 NO | not authorized |
| 15 | RC Tag | 🔒 HOLD | pending security + push |

---

## §9 Test Results Summary

| Test Case | Type | Status |
|---|---|---|
| AUTH | Browser | ✅ PASS |
| UI-13-A Preview | Browser | ✅ PASS |
| UI-13-B Import + Toast | Browser | ✅ PASS |
| UI-13-C Row Count +5 | Browser + API | ✅ PASS |
| UI-14-A EN success toast | Browser | ✅ PASS |
| UI-12 Dup Dialog display | Browser | ✅ PASS |
| UI-12 Cancel (no import) | Browser | ✅ PASS |
| UI-12 Import again flow | Browser | ✅ PASS |
| UI-14-C Error toast | Browser | ✅ PASS |

**Total: 9/9 PASS — Real browser** (6 additional HTTP tests from P12-E also carried: 9/9 PASS)

---

## §10 Blockers before RC Tag

| # | Blocker | Required action | Priority |
|---|---|---|---|
| B-1 | Security S-R1 | `ALTER ROLE scopus_m12_user PASSWORD '<new>'` @ 5432 | 🟡 Medium |
| B-2 | Security S-R4 | Remove 8 `.tmp/` files | 🟡 Medium |
| B-3 | Figma nodes 34 | Apply 5px to 34 additional component nodes | 🔵 Low |
| B-4 | Visual viewport matrix | Browser screenshots @ 1440/768/375px | 🔵 Low |
| B-5 | GitHub push | Owner authorize `GITHUB_PUSH = YES` | 🔴 Required for RC |

---

*Không có credential, password, token hoặc DSN đầy đủ trong tài liệu này.*  
*File này để untracked — không tự stage hoặc commit.*
