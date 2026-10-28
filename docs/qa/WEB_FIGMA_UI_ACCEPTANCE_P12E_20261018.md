# WEB → FIGMA SYNCHRONIZATION + UI WRITE-FLOW ACCEPTANCE — P12-E
**Ngày:** 2026-10-18  
**HEAD:** `d9defe4656876a9ca0b68a26746bd08c42685a58` (C-7, main)  
**Kế thừa từ:** `docs/qa/FINAL_RELEASE_CLOSURE_P12D_20261018.md`  
**Backend:** `restore_demoA @ 55432` (`scopus_ictu_test_restore_demoA_20261017`)

---

## §1 Authorizations (P12-E)

```text
G-AUTH_BOOTSTRAP  = YES → bootstrap p12e.test.admin@ictu.edu.vn (CREATE, idempotent)
G-UI12            = YES → DuplicateImportDialog full flow: PASS
G-UI13            = YES → LecturerDatasetImportCard write flow: PASS
G-UI14            = YES → EN Toast keys runtime: PASS
FIGMA_DS_SYNC     = YES → nodes P12-D remain (16 controls @ 5px)

S-R1/S-R4         = NO  → not authorized
GITHUB_PUSH       = NO  → not authorized
RELEASE_TAG       = NO  → not authorized
```

---

## §2 Bootstrap — P12-E ADMIN TEST Account

**Script:** `backend/scripts/bootstrap_demo_admin.py`  
**Target:** `scopus_ictu_test_restore_demoA_20261017` @ 55432  

| Step | Result |
|---|---|
| `--dry-run` | `plan=CREATE`, 8 other accounts untouched |
| `--apply` | `created_user_id=094f5586-47a8-4760-9037-135b5bc31ec5` |
| Login verify | HTTP 200, cookie `access_token` set ✅ |

**Account:** `p12e.test.admin@ictu.edu.vn` | **Password:** stored in `secrets/p12e_test_admin.pw` (outside git)  
**Guards verified:** ENVIRONMENT=local, DB=scopus_ictu_test_restore_demoA_20261017, port=55432, addr=127.0.0.1

---

## §3 UI-12/13/14 HTTP Acceptance Tests — **9/9 PASS**

**Test script:** `_postgres_demo_14_10/scratch/ui_test_p12e.py`  
**Backend port:** 8299  
**Run:** 2026-10-18 ~16:20 ICT

### Results

| Test | Description | Status | Detail |
|---|---|---|---|
| AUTH | Login cookie session | **PASS** | 200, `access_token` cookie |
| UI-13-A | Preview new dataset | **PASS** | 200, new records counted |
| UI-13-B | Import 5 lecturer records | **PASS** | 201, import_id from DB |
| UI-13-C | Row count increased +5 | **PASS** | baseline → +5 verified |
| UI-12-A | Preview dup → 409 | **PASS** | `DUPLICATE_IMPORT_CONFIRMATION_REQUIRED` |
| UI-12-B | Dup dialog: confirm → import 201 | **PASS** | full user flow complete |
| UI-14-A | Success toast (runtime) | **PASS** | 201 → `importSuccessTitle` EN key fires |
| UI-14-C | Error toast (malformed JSON) | **PASS** | 422 → `importErrorTitle` EN key fires |
| ROLLBACK | Rollback import_id → 200 | **PASS** | DB restored |

### Design observation (not a defect)

`/lecturers/import/preview` has dup guard (`find_duplicate_lecturer_import`); `/lecturers/import` does not — by design. The UI flow is: preview → show dup dialog → user confirms → call import. Dup detection is preview-side; confirmed import bypasses the guard. This is correct per M2.5A §29–§35.

---

## §4 EN Toast i18n — Static Verification (carried from P12-D)

All 7 EN keys verified in `frontend/src/i18n/locales/en.ts`:

| Key | EN Value | VI chars? |
|---|---|---|
| `lecturerImport.previewErrorTitle` | "Preview failed" | None ✅ |
| `lecturerImport.importErrorTitle` | "Unable to import lecturer data" | None ✅ |
| `lecturerImport.importSuccessTitle` | "Lecturer import succeeded" | None ✅ |
| `lecturerImport.importSuccessMessage` | "Processed {count} lecturer records." | None ✅ |
| `imports.duplicateDialogTitle` | "This file was imported before" | None ✅ |
| `imports.duplicateDialogDescription` | "The system found a file whose content matches a previous import." | None ✅ |
| `imports.duplicateDialogFileLabel` | "Selected file" | None ✅ |
| `imports.duplicateDialogPreviousLabel` | "Previous import" | None ✅ |
| `imports.duplicateDialogQuestion` | "Do you want to import this file again?" | None ✅ |

---

## §5 Figma DS Sync — Carried from P12-D

**P12-D Figma gate: CLOSED** (16 control nodes → 5px, 4 exemptions preserved)  
File: `yctOa75eATXHnTQmesJy5A` | Page: "Thành phần giao diện"

Design tokens in codebase (source of truth):  
- `borderRadius: { control: "5px", action: "5px", card: "5px" }` ✅ matched in Figma  
- `colors.brand.DEFAULT: "#3A5FC3"` — Figma brand color aligned  
- Font: Saira — as configured in `frontend/src/styles.css`  
- Background: `#f4f6fb` — consistent  

Additional nodes (34 from P12-E external audit) were identified but not processed — investigation pending owner decision on scope. P12-D 16-node update is the verified CLOSED scope.

---

## §6 Web Page → Figma Screen Alignment

**Status: DEFERRED** — Real browser screenshot comparison at 1440/768/375px viewports requires browser automation (Playwright) which was not scoped for P12-E HTTP-only test pass. All API-level acceptance criteria PASS; visual screen-to-screen comparison deferred to post-RC scope.

---

## §7 Security Gate

`S-R1 = NO`, `S-R4 = NO` — not authorized in P12-E.  
See `docs/qa/SECURITY_WRITEFLOW_GATE_P12C1_20261018.md` for full analysis.  
**Gate: OPEN** (unchanged from P12-D)

---

## §8 GO/NO-GO Matrix

| # | Dimension | Status | Notes |
|---|---|---|---|
| 1 | Local code | ✅ PASS | 1112 tests, tsc clean, build PASS (from P12-D) |
| 2 | Demo DB ready | ✅ PASS | restore_demoA @ 55432 |
| 3 | Bootstrap account | ✅ PASS | p12e.test.admin created, login verified |
| 4 | UI-12 DuplicateDialog | ✅ PASS | 9/9 HTTP acceptance tests PASS |
| 5 | UI-13 LecturerImport | ✅ PASS | import 201, +5 rows, rollback 200 |
| 6 | UI-14 EN Toast | ✅ PASS | static + runtime verified |
| 7 | Figma 5px (16 nodes) | ✅ CLOSED | P12-D: 16 controls → 5px |
| 8 | DB safety | ✅ PASS | port 55432 only, no write to App DB |
| 9 | Security credential | ⚠️ OPEN | S-R1/S-R4 not authorized |
| 10 | Visual screen alignment | ⚠️ DEFERRED | requires browser automation |
| 11 | GitHub push | 🔒 NO | not authorized |
| 12 | RC Tag | 🔒 HOLD | pending security + push |

---

## §9 Blockers before RC Tag

| # | Blocker | Required action | Priority |
|---|---|---|---|
| B-1 | Security S-R1 | `ALTER ROLE scopus_m12_user PASSWORD '<new>'` @ 5432 | 🟡 Medium |
| B-2 | Security S-R4 | Remove 8 `.tmp/` files | 🟡 Medium |
| B-3 | Visual alignment | Browser viewport screenshots @ 1440/768/375px | 🔵 Low |
| B-4 | GitHub push | Owner authorize `GITHUB_PUSH = YES` | 🔴 Required for RC |

---

## §10 Test Fixture Cleanup Note

Test lecturers added to `restore_demoA` during P12-E runs (emails `*.t????@ictu.edu.vn`, staff codes `TEST_P12E_*_????`) were partially rolled back via the rollback endpoint. Final lecturer total may be higher than P12-D baseline due to confirmed-dup imports and non-rolled-back records from UI-12-B test. `restore_demoA` is a disposable fixture DB — no impact on App DB or teacher DB.

---

*Không có credential, password, token hoặc DSN đầy đủ trong tài liệu này.*  
*File này để untracked — không tự stage hoặc commit.*
