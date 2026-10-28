# FINAL RELEASE CLOSURE — P12-D
**Ngày:** 2026-10-18  
**HEAD:** `d9defe4656876a9ca0b68a26746bd08c42685a58` (C-7, main)  
**Prompt:** 12-D (UI-12/13/14 write tests + Figma 5px update)  
**Kế thừa từ:** `docs/qa/FINAL_RELEASE_CLOSURE_P12C_20261018.md`

---

## §1 Authorization Record

```text
G-UI12_DUPLICATE_IMPORT   = YES  → attempted; BLOCKED by auth (see §4)
G-UI13_LECTURER_IMPORT    = YES  → attempted; BLOCKED by auth (see §5)
G-UI14_EN_TOAST_TEST      = YES  → PARTIAL (static i18n verified; write path blocked)
FIGMA_UPDATE_5PX          = YES  → ✅ COMPLETED (see §3)

S-R1_ROTATE_5432          = NO   → not attempted
S-R4_CLEANUP_8_FILES      = NO   → not attempted
GITHUB_PUSH               = NO   → not attempted
RELEASE_TAG               = NO   → not attempted
```

---

## §2 Preflight

| Check | Result |
|---|---|
| Branch | `main` ✅ |
| HEAD | `d9defe4656876a9ca0b68a26746bd08c42685a58` ✅ |
| C-0→C-7 chain | Intact ✅ |
| Staged files | 0 ✅ |
| No push / no tag | Confirmed ✅ |
| DB restore_demoA @ 55432 | Alembic `c7f2a9b1d3e5` ✅ |
| Baseline: lecturers | 410 |
| Baseline: imports | 1 (CSV scopus import) |
| Baseline: admin accounts | 3 (withjson.admin, p4ui.admin, scroll.e2e.admin) |

---

## §3 Figma Radius Update — ✅ COMPLETED

`FIGMA_UPDATE_5PX = YES` | File: `yctOa75eATXHnTQmesJy5A` | Page: "Thành phần giao diện"

### Before / After table

| Node ID | Name | Before | After | Exempt? |
|---|---|---|---|---|
| 5:6 | Xác nhận (Primary btn) | 6px | **5px** ✅ | — |
| 5:8 | Lưu thay đổi (Primary btn) | 6px | **5px** ✅ | — |
| 5:10 | Nhập dữ liệu (Primary btn) | 6px | **5px** ✅ | — |
| 5:14 | Hủy (Secondary btn) | 6px | **5px** ✅ | — |
| 5:16 | Chi tiết (Secondary btn) | 6px | **5px** ✅ | — |
| 5:18 | Tải xuống (Secondary btn) | 6px | **5px** ✅ | — |
| 5:22 | Xóa (Danger btn) | 6px | **5px** ✅ | — |
| 5:24 | Từ chối (Danger btn) | 6px | **5px** ✅ | — |
| 5:28 | Xem thêm (Ghost btn) | 6px | **5px** ✅ | — |
| 5:30 | Làm mới (Ghost btn) | 6px | **5px** ✅ | — |
| 9:9 | Search input | 6px | **5px** ✅ | — |
| 9:72 | View badge (Row 1) | 4px | **5px** ✅ | — |
| 9:89 | View badge (Row 2) | 4px | **5px** ✅ | — |
| 9:106 | View badge (Row 3) | 4px | **5px** ✅ | — |
| 9:25 | Tổng công bố (Stat Card) | 10px | **5px** ✅ | — |
| 9:41 | Data Table container | 10px | **5px** ✅ | — |

### Exemptions — giữ nguyên

| Node ID | Name | Radius | Lý do |
|---|---|---|---|
| 5:2 | Buttons (presentation frame) | 12px | Frame trình bày thiết kế, không phải control |
| 9:69 | Badge (pill status) | 9999px | Pill — exempt theo design policy |
| 9:86 | Badge (pill status) | 9999px | Pill — exempt |
| 9:103 | Badge (pill status) | 9999px | Pill — exempt |

**Tổng:** 16 nodes updated → 5px ✅ | 4 nodes kept (presentation/pill) ✅

### Verify sau update (Plugin API read-back)

Tất cả 16 target nodes đọc lại = 5. Tất cả 4 exemptions giữ nguyên (12, 9999, 9999, 9999).

**Figma gate: ✅ CLOSED**

---

## §4 UI-12 DuplicateImportDialog — ⚠️ PARTIAL (auth blocker)

### Blocker

Backend server khởi động thành công trên `restore_demoA @ 55432` (port 8299). Auth endpoint `POST /api/v1/auth/login` với JSON body hoạt động đúng. Tuy nhiên `admin.pw` không khớp với bất kỳ ADMIN account nào trong DB `restore_demoA`.

3 ADMIN accounts trong DB: `withjson.admin@ictu.edu.vn`, `p4ui.admin@ictu.edu.vn`, `scroll.e2e.admin@ictu.edu.vn` — tất cả đều trả về 401 khi dùng `admin.pw`.

**Cần owner cung cấp:** Tên file env chứa `DEMO_BOOTSTRAP_ADMIN_PASSWORD` cho `restore_demoA`, hoặc trực tiếp email + password của một trong 3 ADMIN accounts trên.

### Tests không thực hiện được

- UI-12-A/B/C/D/E — tất cả blocked (cần auth)
- Rollback UI-12-E — blocked

**Trạng thái: ⚠️ PARTIAL — auth blocker, không phải lỗi logic**

---

## §5 UI-13 LecturerDatasetImportCard — ⚠️ PARTIAL (auth blocker)

Cùng blocker như UI-12. Backend sẵn sàng, fixture file đã tạo (`ui_test_fixture_lecturers.json`, 5 records).

**Tests không thực hiện:**
- UI-13-A/B/C/D/E/F — tất cả blocked

**DB state:** Không có ghi nào. Baseline 410 lecturers giữ nguyên.

**Trạng thái: ⚠️ PARTIAL — auth blocker**

---

## §6 UI-14 English Toast — ⚠️ PARTIAL

### Đã verify (static i18n, không cần auth)

| Test | Key | Value (EN) | VI chars? | Result |
|---|---|---|---|---|
| UI-14-B | `lecturerImport.previewErrorTitle` | "Preview failed" | ✅ None | **PASS** |
| UI-14-C | `lecturerImport.importErrorTitle` | "Unable to import lecturer data" | ✅ None | **PASS** |
| UI-14-D | `imports.duplicateDialogTitle` | "This file was imported before" | ✅ None | **PASS** |
| UI-14-D | `imports.duplicateDialogDescription` | "The system found a file whose content matches a previous import." | ✅ None | **PASS** |
| UI-14-D | `imports.duplicateDialogFileLabel` | "Selected file" | ✅ None | **PASS** |
| UI-14-D | `imports.duplicateDialogPreviousLabel` | "Previous import" | ✅ None | **PASS** |
| UI-14-D | `imports.duplicateDialogQuestion` | "Do you want to import this file again?" | ✅ None | **PASS** |

**i18n source:** `frontend/src/i18n/locales/en.ts`

### Cần auth (chưa verify)

| Test | Key | Status |
|---|---|---|
| UI-14-A | `lecturerImport.importSuccessTitle/Message` | Keys present in en.ts: "Lecturer import succeeded" / "Processed {count} lecturer records." — **static PASS**; runtime display requires UI-13-D |

**Trạng thái: ⚠️ PARTIAL — static keys PASS, runtime write path blocked by auth**

---

## §7 Security Gate 5432 — ⚠️ OPEN (không thay đổi)

`S-R1 = NO`, `S-R4 = NO` — không thực hiện.

Xem `docs/qa/SECURITY_WRITEFLOW_GATE_P12C1_20261018.md` §1–§2 cho full analysis.

---

## §8 GO/NO-GO Matrix

| # | Dimension | Status | Notes |
|---|---|---|---|
| 1 | Local code | ✅ PASS | 1112 tests, tsc clean, build PASS |
| 2 | Demo DB ready | ✅ PASS | restore_demoA @ 55432, Alembic HEAD |
| 3 | Security network | ✅ Mitigated | pg_hba + firewall |
| 4 | Security credential | ⚠️ OPEN | S-R1/S-R4 not authorized |
| 5 | UI-12 DuplicateDialog | ⚠️ PARTIAL | Auth blocker; backend OK |
| 6 | UI-13 LecturerImport | ⚠️ PARTIAL | Auth blocker; backend OK |
| 7 | UI-14 EN Toast (static) | ✅ PASS | All 7 EN keys verified |
| 7b | UI-14-A (runtime) | ⚠️ PARTIAL | Keys OK in en.ts; runtime blocked |
| 8 | Figma 5px (5 nodes) | ✅ CLOSED | 16 controls → 5px, 4 exemptions kept |
| 9 | GitHub sync | ✅ READY | Fast-forward, no conflict |
| 10 | RC Tag | 🔒 HOLD | Pending UI-12/13 + security |
| 11 | Push | 🔒 NO | Not authorized |

---

## §9 Blockers còn lại trước RC tag

| # | Blocker | Cần gì | Priority |
|---|---|---|---|
| B-1 | UI-12/13 auth | Owner cung cấp ADMIN password cho restore_demoA | 🔴 High |
| B-2 | Security S-R1 | `ALTER ROLE scopus_m12_user PASSWORD '<new>'` @ 5432 | 🟡 Medium |
| B-3 | Security S-R4 | Xóa 8 files `.tmp/` | 🟡 Medium |

### B-1 — Cách giải quyết nhanh nhất

Owner chạy lệnh sau để lấy password file đúng:
```powershell
# Thay thế hoặc tạo file chứa password admin cho restore_demoA
# File: D:\DataFolder\ProjectIctu\DoAn\_postgres_demo_14_10\secrets\restore_demoA_admin.pw
# Nội dung: password của withjson.admin@ictu.edu.vn (hoặc admin khác trong DB)
```
Sau đó update `ADMIN_EMAIL` và `SECRETS_DIR / "restore_demoA_admin.pw"` trong script `ui_test_p12d.py` và chạy lại.

---

## §10 Đề xuất bước tiếp theo

1. **Ngay bây giờ:** Owner cung cấp password cho ADMIN account trong `restore_demoA` → chạy lại `ui_test_p12d.py`
2. **Sau UI tests PASS:** Cấp `S-R1 = YES` + `S-R4 = YES` để đóng security gate
3. **Sau security:** Cấp `GITHUB_PUSH = YES` → push 45 commits (fast-forward)
4. **Cuối cùng:** Cấp `RELEASE_TAG = YES`

---

*Không có credential, password, token hoặc DSN đầy đủ trong tài liệu này.*  
*File này để untracked — không tự stage hoặc commit.*
