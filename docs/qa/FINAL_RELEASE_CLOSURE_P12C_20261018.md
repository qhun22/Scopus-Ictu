# FINAL RELEASE CLOSURE — P12-C
**Ngày:** 2026-10-18  
**HEAD:** `d9defe4656876a9ca0b68a26746bd08c42685a58`  
**Prompt:** 12-C (Authorization Checkpoint + Preflight + Figma read + GitHub analysis)  
**Báo cáo nguồn:** `docs/qa/SECURITY_WRITEFLOW_GATE_P12C1_20261018.md`

---

## §1 Authorization Record

```text
S-R1_ROTATE_5432          = CHUA_CHON  → BLOCKED
S-R4_CLEANUP_8_FILES      = CHUA_CHON  → BLOCKED
G-UI12_DUPLICATE_IMPORT   = CHUA_CHON  → BLOCKED
G-UI13_LECTURER_IMPORT    = CHUA_CHON  → BLOCKED
G-UI14_EN_TOAST_TEST      = CHUA_CHON  → BLOCKED
FIGMA_UPDATE_5PX          = CHUA_CHON  → BLOCKED (read-only được thực hiện)

GITHUB_PUSH               = NO
RELEASE_TAG               = NO
```

Tất cả thao tác ghi và Figma update bị BLOCKED do thiếu phê duyệt. Các nhóm read-only đã được thực hiện đầy đủ.

---

## §2 Git / DB Preflight

| Kiểm tra | Kết quả |
|---|---|
| Branch | `main` ✅ |
| HEAD | `d9defe4656876a9ca0b68a26746bd08c42685a58` ✅ |
| C-0→C-7 chain | Toàn vẹn ✅ |
| Staged files | 0 ✅ |
| Working tree untracked | 3 files (expected) ✅ |
| Push | Chưa push — remote HEAD `89cf46f` ✅ |
| Tags | 0 tags mới ✅ |
| Backup P12-B4 | SHA-256 `35fd0d51...` match ✅ |
| Cluster 5432 | Đang chạy PID 6260, bind `0.0.0.0` ✅ confirmed |
| Cluster 55432 | Đang chạy PID 26424, bind `127.0.0.1` (localhost-only) ✅ |
| `restore_demoA` DB | Alembic `c7f2a9b1d3e5` = HEAD ✅ |
| PR #25/#26/#29 | Open, không bị merge/close ✅ |

**Untracked artifacts còn nguyên:**
- `backend/scripts/create_csvonly_e2e_accounts.py`
- `docs/qa/LOCAL_COMMIT_EXECUTION_P12B3_20261018.md`
- `docs/qa/SECURITY_WRITEFLOW_GATE_P12C1_20261018.md`

---

## §3 Security Remediation — BLOCKED

**S-R1 (rotate `scopus_m12_user`):** BLOCKED — `CHUA_CHON`

**S-R4 (cleanup 8 .tmp files):** BLOCKED — `CHUA_CHON`

**Current-state từ P12-C1 (không thay đổi):**
- `listen_addresses = '*'` — bind mọi interface
- `pg_hba.conf`: chỉ `127.0.0.1/32` + `::1/128`
- Windows Firewall: `BlockInbound` Public + Private — không có Allow rule cho 5432
- `scopus_m12_user` KHÔNG được dùng bởi application hiện hành
- 8 files `.tmp/` chứa credential cũ — gitignored, local only
- Không có credential trong Git history

**Security gate: `⚠️ OPEN`** — chưa có hành động rotate hay cleanup.

---

## §4 UI-12 DuplicateImportDialog — BLOCKED

`G-UI12_DUPLICATE_IMPORT = CHUA_CHON`

DB target sẵn sàng (`restore_demoA` Alembic `c7f2a9b1d3e5` ✅), nhưng không thực hiện write test.

**Trạng thái: `⏳ NOT TESTED (BLOCKED)`**

---

## §5 UI-13 LecturerDatasetImportCard — BLOCKED

`G-UI13_LECTURER_IMPORT = CHUA_CHON`

**Trạng thái: `⏳ NOT TESTED (BLOCKED)`**

---

## §6 UI-14 English Toast — BLOCKED

`G-UI14_EN_TOAST_TEST = CHUA_CHON`

Phụ thuộc G-UI13D. **Trạng thái: `⏳ NOT TESTED (BLOCKED)`**

---

## §7 Figma Radius 5px — READ-ONLY (Update BLOCKED)

`FIGMA_UPDATE_5PX = CHUA_CHON` — không sửa Figma.

Đã thực hiện read-only qua MCP `get_design_context` trên file `yctOa75eATXHnTQmesJy5A`.

### Figma Correction Matrix — Current State (đọc 2026-10-18)

| Node | Component | Radius hiện tại trong Figma | Yêu cầu | Trạng thái |
|---|---|---|---|---|
| 5:2 | Button frame | `6px` (`rounded-[6px]`) | 5px | ❌ Cần sửa |
| 9:9 | Search input | `6px` (`rounded-[6px]`) | 5px | ❌ Cần sửa |
| 9:72 | Table Action (View) | `4px` (`rounded-[4px]`) | 5px | ❌ Cần sửa |
| 9:25 | Stat Card | `10px` (`rounded-[10px]`) | 5px | ❌ Cần sửa |
| 9:41 | Data Table container | `10px` (`rounded-[10px]`) | 5px | ❌ Cần sửa |

**Ghi chú:**
- Badge pills trong node 9:41/9:68/9:85/9:103: `rounded-[9999px]` — đây là exemption hợp lệ (pill)
- Frame bao ngoài node 5:2: `rounded-[12px]` — đây là frame trang thiết kế, không phải button control
- Tất cả 5 nodes target đều cần cập nhật từ giá trị hiện tại về 5px

**Figma gate: `⏳ PENDING`** — cần `FIGMA_UPDATE_5PX = YES` để thực thi.

---

## §8 GitHub Remote Analysis

### Commits chưa push: 45 commits

| Nhóm | Commits |
|---|---|
| C-7 (P12-B4 corrective) | `d9defe4` |
| C-0→C-6 (P12-B3) | `f80713c` → `2410411` |
| Pre-P12-B3 (P07–P11.5) | 37 commits từ `237f7bc` → `f74ab7c` |

**Divergence point:** `origin/main` = `89cf46f` — local main là ancestor tuyến tính → **fast-forward push khả thi**.

### Remote state
- `origin/main`: `89cf46f` (Phân biệt rõ mạng container CI...)
- `integration/clean-main-rebase-20261012`: cùng SHA `89cf46f`
- PR #25, #26, #29: còn open, không bị merge/close

### Secret scan trong committed files
- Pickaxe search `m12_user` trong code files: chỉ tìm thấy trong QA docs (tên role, không phải credential) ✅
- Staged diff không có secret ✅
- `.tmp/` gitignored ✅

### Push plan (khi `GITHUB_PUSH = YES`)
```bash
git push origin main
# Fast-forward: origin/main → d9defe4
# Không cần force-push, không có conflict
```

**GitHub readiness: `✅ READY` (chờ gate bắt buộc và `GITHUB_PUSH = YES`)**

---

## §9 GO/NO-GO Matrix

| # | Dimension | Trạng thái | Ghi chú |
|---|---|---|---|
| 1 | Local code readiness | ✅ PASS | 1112 tests, TypeScript clean, build PASS |
| 2 | Local demo readiness | ✅ PASS | App DB @ 55432, launcher configured |
| 3 | Security — network exposure | ✅ ACCEPTED LIMITATION | pg_hba + firewall chặn external; credential chưa rotate |
| 4 | Security — credential rotate | ⚠️ OPEN | S-R1 BLOCKED; `.tmp/` chưa clean |
| 5 | UI-12 DuplicateImportDialog | ⏳ NOT TESTED | G-UI12 BLOCKED |
| 6 | UI-13 LecturerDatasetImportCard | ⏳ NOT TESTED | G-UI13 BLOCKED |
| 7 | UI-14 English Toast | ⏳ NOT TESTED | G-UI14 BLOCKED |
| 8 | Figma radius 5px (5 nodes) | ⏳ PENDING | FIGMA_UPDATE_5PX BLOCKED; all 5 nodes ≠ 5px |
| 9 | GitHub synchronization | ✅ READY | Fast-forward, no conflict |
| 10 | RC Tag | 🔒 HOLD | RELEASE_TAG = NO |
| 11 | Public deployment | 🔒 BLOCKED | Security gate OPEN + UI gates NOT TESTED |

---

## §10 Blockers còn lại

### Phải giải quyết trước RC tag

| Blocker | Action cần | Approval cần |
|---|---|---|
| Security credential `scopus_m12_user` | Rotate + cleanup `.tmp/` | `S-R1 = YES` + `S-R4 = YES` |
| UI-12/13/14 chưa kiểm thử | Chạy write-flow tests | `G-UI12 = YES` + `G-UI13 = YES` + `G-UI14 = YES` |
| Figma 5 nodes ≠ 5px | Sửa radius trong Figma | `FIGMA_UPDATE_5PX = YES` |

### Có thể push trước RC tag (tùy chủ đồ án)

- `GITHUB_PUSH = YES` có thể được cấp độc lập — code local đã sẵn sàng, fast-forward clean.

---

## §11 Đề xuất bước release cuối cùng

**Bước 1 (có thể làm ngay khi cấp phép):** Cấp `S-R1 = YES` để rotate `scopus_m12_user` password, sau đó `S-R4 = YES` để xóa 8 files `.tmp/`.

**Bước 2 (song song với bước 1):** Cấp `G-UI13 = YES` + `G-UI12 = YES` + `G-UI14 = YES` để chạy write-flow tests trên `restore_demoA` @ 55432.

**Bước 3:** Cấp `FIGMA_UPDATE_5PX = YES` để sửa 5 nodes (6px → 5px, 4px → 5px, 10px → 5px).

**Bước 4:** Cấp `GITHUB_PUSH = YES` để push 45 commits (fast-forward).

**Bước 5:** Sau khi tất cả gates đóng, cấp `RELEASE_TAG = YES`.

---

*Không có credential, password, token hoặc DSN đầy đủ nào được ghi trong tài liệu này.*  
*File này để untracked — không tự stage hoặc commit.*
