# SECURITY & WRITE-FLOW GATE — P12-C1
**Ngày:** 2026-10-18  
**HEAD:** `d9defe4656876a9ca0b68a26746bd08c42685a58`  
**Mục tiêu:** Đóng hoặc xác định điều kiện đóng Security 5432 và UI-12/13/14  
**Trạng thái tổng:** Security 5432 `⚠️ OPEN (giảm thiểu)` · UI-12/13/14 `⏳ READY TO TEST`

---

## §0 Git Preservation Preflight

| Kiểm tra | Kết quả |
|---|---|
| Branch | `main` ✅ |
| HEAD | `d9defe4656876a9ca0b68a26746bd08c42685a58` ✅ |
| Chuỗi C-0→C-7 | Toàn vẹn (xem bảng bên dưới) ✅ |
| Working tree | 2 untracked, 0 modified ✅ |
| Staged | Không có ✅ |
| Push / tag | Chưa push; 0 tags mới ✅ |
| Backup P12-B4 | `launch_json_backup_p12b4_20261018.json` — SHA-256 match ✅ |

**Chuỗi commit C-0→C-7:**

| # | SHA | Subject |
|---|-----|---------|
| C-0 | `24104113a686...` | RC docs + .gitignore |
| C-1 | `82cbc03758d3...` | Backend governance P09 |
| C-2 | `5363e370973c...` | Backend launcher P10 |
| C-3 | `c99cf6d6b8f6...` | Backend tests P09/P10 |
| C-4 | `87706a9485f2...` | DS tokens radius 5px + ui/ |
| C-5 | `5fdc4b43dee9...` | Frontend DS migration |
| C-6 | `f80713c54599...` | QA docs P07–P12 |
| C-7 | `d9defe465687...` | chore: restore portable Claude launch config |

---

## §1 Security 5432 — Current-State Findings

### 1.1 Trạng thái cluster

| Đặc điểm | Giá trị | Đánh giá |
|---|---|---|
| Service | `postgresql-x64-17` — `Running`, `Automatic` | Đang chạy |
| Process PID | 6260 | Đã xác nhận |
| Data dir | `C:\Program Files\PostgreSQL\17\data` | Standard install |
| `listen_addresses` | `'*'` (postgresql.conf) | ⚠️ Lắng nghe mọi interface |
| Netstat | `0.0.0.0:5432 LISTENING` + `[::]:5432 LISTENING` | ⚠️ Xác nhận bind mọi interface |
| `pg_hba.conf` | `host all all 127.0.0.1/32 scram-sha-256` + `::1/128` | ✅ Chỉ localhost được phép kết nối |
| Windows Firewall (Public) | `BlockInbound` | ✅ Firewall chặn inbound Public |
| Windows Firewall (Private) | `BlockInbound` | ✅ Firewall chặn inbound Private |
| Firewall rule riêng cho 5432 | Không tìm thấy | ✅ Không có hole đặc biệt |

**Phân tích rủi ro mạng:**
- `listen_addresses = '*'` tạo ra socket nhưng `pg_hba.conf` chỉ accept từ `127.0.0.1/32` và `::1/128`.
- Windows Firewall `BlockInbound` trên cả Public và Private profile — không có rule Allow cho 5432.
- **Kết luận thực tế:** PostgreSQL 5432 hiện **không thể truy cập từ mạng ngoài** với cấu hình hiện tại — pg_hba + firewall tạo thành 2 lớp chặn độc lập.
- Rủi ro còn lại: nếu admin tắt firewall hoặc thêm rule cho 5432, thì `listen_addresses = '*'` sẽ tức thì mở rộng attack surface.

### 1.2 Role `scopus_m12_user` — Phạm vi sử dụng

| Nguồn | Tình trạng |
|---|---|
| `backend/app/` (tracked code) | **Không tồn tại** — `DB_USER` = role khác (16 ký tự, not m12) |
| `backend/.env` | **Không phải m12_user** |
| Secrets dir `*.env` | **Không có file nào dùng m12_user** (đã scan, không in values) |
| `.tmp/` (untracked, gitignored) | **8 files** — chứa credential (username + password plaintext) |
| Git history (pickaxe scan) | Chỉ xuất hiện trong QA docs (C-6 + C-0) dưới dạng **tên role**, không phải credential |
| Alembic, launcher, test configs | **Không dùng** m12_user |

**Kết luận:** `scopus_m12_user` **không được sử dụng bởi bất kỳ application process, test, hay launcher nào**. Credential tồn tại duy nhất trong `.tmp/` (gitignored, local only) và trong transcript local (ngoài repo).

### 1.3 Credential exposure inventory

| Vị trí | Loại | Trong Git? | Có thể xóa an toàn? |
|---|---|---|---|
| `.tmp/completion1-a5-runtime-freeze/backend/a5_runtime_verify.py` | DSN plaintext | ❌ gitignored | ✅ Sau khi rotate |
| `.tmp/m27b-review-service/check_db.py` + 4 files | DSN plaintext | ❌ gitignored | ✅ Sau khi rotate |
| `.tmp/m27b-review-ui/backend/_r4_*.py` (3 files) | DSN plaintext | ❌ gitignored | ✅ Sau khi rotate |
| Transcript local (Claude JSONL) | Có thể xuất hiện | ❌ Ngoài repo | Xóa theo retention policy |
| `docs/qa/` tracked files | **Tên role only**, không phải credential | ✅ Trong Git | Không cần xóa |

**Tổng cộng:** 8 files trong `.tmp/`, tất cả gitignored, không có credential nào trong Git history.

---

## §2 Credential Remediation Runbook

> Runbook này chỉ để owner thực hiện sau khi cấp phép. **Không tự thực hiện.**

### Điều kiện trước

- [ ] Xác nhận không có process nào đang dùng `scopus_m12_user` (query `pg_stat_activity`)
- [ ] Xác nhận `.tmp/` không có script nào đang chạy nền
- [ ] Backup `pg_hba.conf` và `postgresql.conf` ra ngoài repo

### Quyền hệ thống cần có

- PostgreSQL superuser (hoặc `pg_admin` role) trên cluster 5432
- Write access vào `C:\Program Files\PostgreSQL\17\data\` (Windows admin) để đổi `postgresql.conf`

### Phạm vi ảnh hưởng

- **Không ảnh hưởng** App DB (55432), DB teacher (55432), DB test (5432 via scoped users)
- **Không ảnh hưởng** application backend hiện tại (không dùng m12_user)
- **Chỉ ảnh hưởng** `.tmp/` scripts — những scripts này đã lỗi thời

### Bước thực hiện

**R-1 — Rotate password (PostgreSQL superuser)**
```sql
-- Chạy bởi superuser, không in kết quả
ALTER ROLE scopus_m12_user PASSWORD '<new-strong-password>';
```
- Xác nhận: credential cũ trong `.tmp/` sẽ bị từ chối khi connect

**R-2 — Vô hiệu hóa hoặc revoke login (nếu role không cần thiết nữa)**
```sql
ALTER ROLE scopus_m12_user NOLOGIN;
-- hoặc nếu muốn giữ role nhưng không cho connect:
REVOKE CONNECT ON DATABASE scopus_m12_test FROM scopus_m12_user;
```

**R-3 — Hạn chế listen_addresses (tùy chọn, thêm lớp bảo vệ)**

Sửa `C:\Program Files\PostgreSQL\17\data\postgresql.conf`:
```
listen_addresses = 'localhost'   # thay vì '*'
```
Sau đó restart service:
```
net stop postgresql-x64-17
net start postgresql-x64-17
```
*Lưu ý:* Bước này yêu cầu admin Windows và sẽ ngắt **tất cả** kết nối đang mở trong vài giây. App DB (55432) không bị ảnh hưởng nếu chạy trên cluster riêng.

**R-4 — Dọn credential trong `.tmp/`**

Sau khi R-1/R-2 xác nhận credential cũ không còn dùng được:
```
# Xóa 8 files chứa DSN cũ (owner tự thực hiện)
del /s .tmp\m27b-review-service\check_db.py  # etc.
# Hoặc xóa toàn bộ .tmp\ nếu không còn cần
```

**R-5 — Xóa transcript (theo retention policy)**

Claude conversation JSONL tại `C:\Users\QuangHuy\.claude\projects\...\*.jsonl` — owner quyết định giữ hay xóa theo chính sách lưu giữ của tổ chức.

### Hậu kiểm

```sql
-- Xác nhận role không còn login được (KHÔNG in kết quả với credential cũ)
SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname = 'scopus_m12_user';
-- Expected: rolcanlogin = false (nếu đã NOLOGIN)
```

Test negative: thử kết nối với credential cũ → phải fail với `authentication failed` hoặc `role... cannot log in`.

### Rollback

Nếu phát hiện application break sau R-1/R-2:
- R-1 rollback: `ALTER ROLE scopus_m12_user PASSWORD '<old-password>'` (cần ghi nhớ trước khi rotate)
- R-3 rollback: đổi lại `listen_addresses = '*'`, restart service

### Điều kiện chấp nhận rủi ro tạm thời (nếu chỉ demo local)

Trạng thái hiện tại có thể chấp nhận cho demo local **nếu và chỉ nếu**:
1. Máy chỉ kết nối LAN nội bộ đáng tin cậy hoặc không có mạng trong lúc demo
2. Firewall Windows `BlockInbound` đang ON (đã xác nhận ✅)
3. pg_hba chỉ `127.0.0.1/32` (đã xác nhận ✅)
4. Không demo với projector/screen share qua mạng công cộng

**Không chấp nhận rủi ro cho public deployment.**

---

## §3 UI-12 Test Specification — DuplicateImportDialog

### Context

`DuplicateImportDialog` được render bởi `LecturerDatasetImportCard` khi API `POST /api/v1/lecturers/import/preview` trả về `DUPLICATE_IMPORT_CONFIRMATION_REQUIRED`. Dialog có 3 buttons: Cancel / View Previous / Confirm.

### Test Environment

- **DB target:** `scopus_ictu_test_restore_demoA_20261017` @ `localhost:55432`
- **Alembic revision:** `c7f2a9b1d3e5` (HEAD) ✅ khớp
- **Actors:** ADMIN account trong DB (3 ADMIN users confirmed)
- **Backend:** env từ `backend_demo.env` (port 55432) với `DB_NAME` override

### Test Cases

| ID | Tên | Actor | Fixture | Route/API | DB delta | Expected UI | Cleanup | Risk | Approval |
|---|---|---|---|---|---|---|---|---|---|
| UI-12-A | Upload lần đầu (baseline) | ADMIN | JSON file nhỏ mới | `POST /lecturers/import/preview` | Không ghi (preview only) | Preview summary, không có dialog | Không cần | Thấp | Không cần riêng |
| UI-12-B | Phát hiện duplicate | ADMIN | Cùng file JSON đã import trong fixture | `POST /lecturers/import/preview` | Không ghi | DuplicateImportDialog mở | Không cần | Thấp | Không cần riêng |
| UI-12-C | Cancel duplicate dialog | ADMIN | Từ UI-12-B | UI click Cancel | Không ghi | Dialog đóng, không tạo import | Không cần | Thấp | Không cần riêng |
| UI-12-D | View Previous button | ADMIN | Từ UI-12-B | UI click View Previous | Không ghi | Navigate/scroll tới previous import | Không cần | Thấp | Không cần riêng |
| UI-12-E | Confirm duplicate (ghi) | ADMIN | Từ UI-12-B + Confirm | `POST /lecturers/import` với `force_duplicate=true` | +1 scopus_imports row | Import success toast EN | `POST /lecturers/import/{id}/rollback` | Trung bình | **G-UI12E** |
| UI-12-F | Loading state | ADMIN | Từ UI-12-B | Slow network sim | Không ghi | Buttons disabled, spinner | Không cần | Thấp | Không cần riêng |

**Prep fixture UI-12:** `scopus_imports` table đã có 1 record (confirmed). Dùng file JSON xuất từ `/api/v1/lecturers/export` của chính DB này làm duplicate candidate.

**i18n keys cần verify (EN locale):**
- `imports.duplicateDialogTitle`
- `imports.duplicateDialogDescription`
- `imports.duplicateDialogFileLabel`
- `imports.duplicateDialogPreviousLabel`
- `imports.duplicateDialogQuestion`

---

## §4 UI-13 Test Specification — LecturerDatasetImportCard

### Context

Component tại trang `/lecturers` (ADMIN). Flow: chọn file → `Validate file` → preview → `Confirm import` → import. Có rollback endpoint.

### Test Cases

| ID | Tên | Actor | Fixture | Route/API | DB delta | Expected UI | Cleanup | Risk | Approval |
|---|---|---|---|---|---|---|---|---|---|
| UI-13-A | File không hợp lệ (JSON sai schema) | ADMIN | JSON malformed | `POST /lecturers/import/preview` | Không ghi | Error toast EN: preview failed | Không cần | Thấp | Không cần riêng |
| UI-13-B | File hợp lệ — preview | ADMIN | Valid JSON fixture nhỏ (≤10 records) | `POST /lecturers/import/preview` | Không ghi | Preview card: total/valid/create/update counts | Không cần | Thấp | Không cần riêng |
| UI-13-C | Cancel sau preview | ADMIN | Từ UI-13-B | UI click Cancel | Không ghi | Form reset, không tạo import | Không cần | Thấp | Không cần riêng |
| UI-13-D | Submit / import thành công (ghi) | ADMIN | Valid JSON fixture ≤10 records | `POST /lecturers/import` | +1 scopus_imports, +N lecturers rows | Toast EN: "Lecturer import succeeded. Processed N lecturer records." | `POST /lecturers/import/{id}/rollback` | Trung bình | **G-UI13D** |
| UI-13-E | Import thất bại (server error giả lập) | ADMIN | Valid preview, kill backend giữa chừng | `POST /lecturers/import` | Không ghi (request fail) | Toast EN: "Unable to import lecturer data" | Không cần | Thấp | Không cần riêng |
| UI-13-F | Button loading/disabled state | ADMIN | Bất kỳ | Trong lúc request in-flight | Không ghi | "Confirm import" disabled, spinner | Không cần | Thấp | Không cần riêng |

**Fixture UI-13:** Tạo JSON file nhỏ (≤10 records) từ export hoặc viết tay, không dùng master dataset thật.

**Toast keys cần verify (EN locale):**
- `lecturerImport.importSuccessTitle` = `"Lecturer import succeeded"`
- `lecturerImport.importSuccessMessage` = `"Processed {count} lecturer records."`
- `lecturerImport.importErrorTitle` = `"Unable to import lecturer data"`
- `lecturerImport.previewErrorTitle` = `"Preview failed"`

**Rollback availability:** Endpoint `POST /api/v1/lecturers/import/{import_id}/rollback` đã xác nhận tồn tại và là ADMIN-only.

---

## §5 UI-14 Test Specification — Lecturers toasts EN

### Context

Nghiệm thu ngôn ngữ toast: khi locale = `en`, tất cả toast messages phải là tiếng Anh, không lẫn tiếng Việt, không lộ error nội bộ.

### Test Cases

| ID | Tên | Actor | Thao tác | Toast key | Expected EN | Risk | Approval |
|---|---|---|---|---|---|---|---|
| UI-14-A | Import success toast | ADMIN | UI-13-D success path | `lecturerImport.importSuccessTitle/Message` | "Lecturer import succeeded. Processed N lecturer records." | Phụ thuộc UI-13-D | **G-UI14A** (với G-UI13D) |
| UI-14-B | Preview error toast | ADMIN | UI-13-A error path | `lecturerImport.previewErrorTitle` | "Preview failed" | Thấp | Không cần riêng |
| UI-14-C | Import error toast | ADMIN | UI-13-E error path | `lecturerImport.importErrorTitle` | "Unable to import lecturer data" | Thấp | Không cần riêng |
| UI-14-D | Duplicate dialog text | ADMIN | UI-12-B path | `imports.duplicateDialogTitle/Description` | All EN, no VI | Thấp | Không cần riêng |

**Kiểm tra tự động ngôn ngữ:** Sau mỗi toast, screenshot hoặc DOM check để xác nhận không có ký tự tiếng Việt (`[àáâãèéêìíòóôõùúýăđơư]`) trong toast message.

---

## §6 TEST DB Isolation và Rollback Verification

| Tiêu chí | Kết quả |
|---|---|
| DB target | `scopus_ictu_test_restore_demoA_20261017` @ `localhost:55432` |
| DB exists | ✅ Confirmed |
| Alembic revision | `c7f2a9b1d3e5` = code HEAD ✅ |
| User counts | ADMIN=3, REVIEWER=2, LECTURER=3 |
| Key data | scopus_imports=1, publications=660, lecturers=410 |
| Isolation từ App DB | ✅ Khác cluster port (55432 vs 55432 nhưng khác DB_NAME) |
| Isolation từ 5432 | ✅ Khác cluster hoàn toàn |
| Outbound API/email | ✅ Không có (BackgroundTasks = 0, no SMTP config) |
| Online enrichment trigger | ✅ Không có trong import flow |
| Rollback mechanism | ✅ `POST /lecturers/import/{id}/rollback` — ADMIN-only, đã test trong P09 |
| Snapshot/restore | `backend_test_restore_demoA.env` tồn tại; procedure: khôi phục từ backup nếu cần |

**Blocked conditions:** Không có condition blocked. DB sẵn sàng.

**Snapshot procedure (nếu cần rollback toàn bộ DB):**
```bash
# Owner tự thực hiện trước khi chạy write tests
pg_dump -h localhost -p 55432 -U <user> scopus_ictu_test_restore_demoA_20261017 > restore_demoA_backup_before_ui_test.sql
# Rollback nếu cần:
psql -h localhost -p 55432 -U <user> -c "DROP DATABASE scopus_ictu_test_restore_demoA_20261017"
psql -h localhost -p 55432 -U <user> -c "CREATE DATABASE scopus_ictu_test_restore_demoA_20261017"
psql -h localhost -p 55432 -U <user> scopus_ictu_test_restore_demoA_20261017 < restore_demoA_backup_before_ui_test.sql
```

---

## §7 Authorization Request

Mỗi mục yêu cầu phê duyệt rõ ràng. Hiện tại **chưa cấp**.

### Security 5432

| ID | Thao tác | DB / System | Rollback |
|---|---|---|---|
| **S-R1** | `ALTER ROLE scopus_m12_user PASSWORD '<new>'` | cluster 5432 | Restore password cũ |
| **S-R2** | `ALTER ROLE scopus_m12_user NOLOGIN` | cluster 5432 | `ALTER ROLE ... LOGIN` |
| **S-R3** | Sửa `listen_addresses='localhost'` + restart service | PostgreSQL 17 cluster | Revert + restart |
| **S-R4** | Xóa 8 files trong `.tmp/` chứa DSN cũ | local filesystem | Không thể undo |
| **S-R5** | Xóa/archive Claude transcript JSONL | local filesystem | Không thể undo |

**Gợi ý tối thiểu cho local demo:** Chỉ cần S-R1 + S-R4 để đóng security gate trong phạm vi demo local. S-R2/R3 thêm hardening tùy chọn.

### UI Write Tests

| ID | Thao tác | DB target | Rollback |
|---|---|---|---|
| **G-UI12E** | Confirm duplicate import | `restore_demoA` @ 55432 | `POST /lecturers/import/{id}/rollback` |
| **G-UI13D** | Submit lecturer import (≤10 records) | `restore_demoA` @ 55432 | `POST /lecturers/import/{id}/rollback` |
| **G-UI14A** | (phụ thuộc G-UI13D) | — | — |

**Note:** UI-12-A/B/C/D, UI-13-A/B/C/E/F, UI-14-B/C/D không cần phê duyệt riêng — đây là read/preview operations.

---

## §8 GO/NO-GO Matrix

| Gate | Trạng thái | Điều kiện đóng |
|---|---|---|
| Security 5432 — credential exposure | ⚠️ OPEN (giảm thiểu) | Cần S-R1 + S-R4 |
| Security 5432 — network exposure | ✅ Mitigated (pg_hba + firewall) | Đã đủ cho local demo |
| UI-12 DuplicateImportDialog (read/cancel/dialog) | ⏳ Ready | Phê duyệt: Không cần riêng |
| UI-12E Confirm duplicate (ghi) | ⏳ Ready | Phê duyệt: G-UI12E |
| UI-13 Preview + error flows | ⏳ Ready | Phê duyệt: Không cần riêng |
| UI-13D Import success (ghi) | ⏳ Ready | Phê duyệt: G-UI13D |
| UI-14 Toast EN language | ⏳ Ready | Phụ thuộc UI-13D/14A |
| RC Tag / Push | 🔒 HOLD | Tất cả gates đóng trước |
| Figma 5 nodes | ⏳ PENDING (designer) | Ngoài phạm vi prompt này |

### Có thể thực hiện ngay sau phê duyệt

- **S-R1** (rotate password): có thể thực hiện độc lập, không ảnh hưởng application
- **S-R4** (xóa .tmp files): có thể thực hiện độc lập sau S-R1
- **UI-12-A/B/C/D, UI-13-A/B/C/E/F, UI-14-B/C/D**: ngay sau khi start backend+frontend TEST server
- **G-UI12E + G-UI13D + G-UI14A**: sau khi cấp phép ghi

### Vẫn BLOCKED

Không có item nào BLOCKED do thiếu kỹ thuật — tất cả điều kiện kỹ thuật đã PASS.

### Rủi ro demo local

- `listen_addresses='*'` + firewall OFF (nếu owner tắt firewall) → 5432 accessible; đã recommend S-R3
- Credential `scopus_m12_user` còn trong `.tmp/` — kẻ tấn công có quyền truy cập filesystem local có thể đọc

### Rủi ro public deployment

- **KHÔNG deploy lên public** cho đến khi S-R1/R2/R3 hoàn thành
- `listen_addresses='*'` trên server public sẽ expose 5432 nếu firewall không restrict — nghiêm trọng

---

*Không có credential, password, token, hoặc DSN đầy đủ nào được ghi trong tài liệu này.*  
*Tài liệu này để untracked — không commit trong prompt này.*
