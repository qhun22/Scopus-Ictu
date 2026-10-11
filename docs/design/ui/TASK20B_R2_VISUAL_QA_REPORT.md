# TASK 20B-R2: Visual QA Report
**Trạng thái:** PASS — 11/11 màn PASS, 0 lỗi nghiêm trọng, 3 lỗi đã sửa  
**Ngày:** 10/10/2026 · Nhánh: main@530bf0f  
**Phạm vi:** Nghiệm thu trực quan 11 prototype screens qua HTTP server (127.0.0.1:7788)

---

## 1. Kết quả tổng hợp

| Màn | File | Viewport 1440×900 | Viewport 1366×768 | Kết luận |
|---|---|---|---|---|
| Index | `index.html` | ✅ PASS | ✅ PASS | **PASS** |
| S01 Login | `s01_login.html` | ✅ PASS | ✅ PASS | **PASS** |
| S02 Danh sách công bố | `s02_publications.html` | ✅ PASS | ✅ PASS | **PASS** |
| S03 Chi tiết công bố | `s03_pub_detail.html` | ✅ PASS | ✅ PASS | **PASS** |
| S04 Nhập dữ liệu | `s04_imports.html` | ✅ PASS | ✅ PASS | **PASS** |
| S05 Tổng quan | `s05_dashboard.html` | ✅ PASS | ✅ PASS | **PASS** |
| S06 Giảng viên | `s06_lecturers.html` | ✅ PASS | ✅ PASS | **PASS** |
| S09 Hàng đợi phê duyệt | `s09_reviews.html` | ✅ PASS | ✅ PASS | **PASS** |
| S13 Lịch sử review | `s13_review_history.html` | ✅ PASS | ✅ PASS | **PASS** |
| S14 Nhật ký hệ thống | `s14_audit_logs.html` | ✅ PASS | ✅ PASS | **PASS** |
| S15 Tác vụ | `s15_tasks.html` | ✅ PASS | ✅ PASS | **PASS** |
| S20 Chuẩn hóa (PROPOSED) | `s20_normalization_proposed.html` | ✅ PASS | ✅ PASS | **PASS** |

**Console errors:** 0 trên tất cả các màn  
**JS runtime errors:** 0  
**Horizontal overflow:** 0 (không tràn bảng ở 1366px)

---

## 2. Màn ưu tiên — kiểm tra chi tiết

### S09 Hàng đợi phê duyệt (PI2.3-5) — PASS ✅
- Sidebar 9 items, topbar có REVIEWER role badge (amber)
- Bảng 7 cột hiển thị đúng không overflow ở 1366px
- Modal S10 (Candidate detail): mở đúng, 2-col evidence grid, score bars
- Modal S11 (ACCEPT dialog): icon xanh, note text rõ ràng
- Modal S11b (409 Conflict): `.conflict-box` red bg hiển thị rõ
- Modal S12 (REJECT): textarea `resize:none`, char counter hoạt động
- GAP-b notice AntD color hiển thị đúng trong mỗi modal

### S13 Lịch sử review — PASS ✅
- Filter bar: 5 inputs không wrap ở 1366px (đã fix ở R1)
- ActionBadge: GAP-j notice hiển thị đúng (CANDIDATE_ACCEPTED → nhãn VN thiếu ở AS-IS)
- Bảng không overflow, pagination đúng vị trí

### S14 Nhật ký hệ thống — PASS ✅
- Filter bar 5 inputs: GAP-i TO-BE fix hiển thị trong notice box
- Bảng 7 cột không overflow ở 1366×768
- Export button vị trí đúng topbar-right

### S15 Tác vụ — PASS ✅
- Placeholder icon (lightning bolt) + "Chức năng đang phát triển"
- FUTURE DESIGN zone amber border hiển thị đúng
- "Về Trang chủ" button hoạt động

---

## 3. Lỗi đã phát hiện và sửa (BEFORE/AFTER)

### Fix #1: Sidebar height trên viewport ngắn
**File:** `prototype/_shell.css`  
**Vấn đề:** `.sidebar { min-height: 100vh }` → sidebar không scroll được khi content dài hơn viewport  
**BEFORE:**
```css
.sidebar { min-height: 100vh; }
```
**AFTER:**
```css
.sidebar { height: 100vh; overflow-y: auto; }
```
**Ảnh hưởng:** Tất cả màn có sidebar (10/11 màn)  
**Kết quả:** PASS — sidebar scroll đúng ở 1366×768

---

### Fix #2: Broken link `s19_home.html`
**File:** `prototype/_shared.html`  
**Vấn đề:** Sidebar nav item "Trang chủ" trỏ đến file không tồn tại  
**BEFORE:** `href="s19_home.html"`  
**AFTER:** `href="index.html"`  
**Ảnh hưởng:** Link "Trang chủ" trên tất cả màn có sidebar  
**Kết quả:** PASS — navigation đúng

---

### Fix #3: Broken link `s21_normalization.html`
**File:** `prototype/_shared.html`  
**Vấn đề:** Sidebar nav item "Chuẩn hóa dữ liệu" trỏ đến file không tồn tại  
**BEFORE:** `href="s21_normalization.html"`  
**AFTER:** `href="s20_normalization_proposed.html"`  
**Ảnh hưởng:** Link "Chuẩn hóa dữ liệu" trên tất cả màn có sidebar  
**Kết quả:** PASS — navigation đến S20 PROPOSED đúng

---

## 4. Xác minh PI 2.3 — 6 nhóm màn

| Nhóm PI 2.3 | Màn | Prototype | Screenshot QA | Route mapping |
|---|---|---|---|---|
| PI2.3-1: Danh sách công bố | S02 | ✅ `s02_publications.html` | ✅ 1440+1366 | /publications |
| PI2.3-2: Chi tiết công bố | S03 | ✅ `s03_pub_detail.html` | ✅ 1440+1366 | /publications/:eid |
| PI2.3-3: Nhập dữ liệu | S04 | ✅ `s04_imports.html` | ✅ 1440+1366 | /imports |
| PI2.3-4: So sánh chuẩn hóa | S20 | ✅ `s20_normalization_proposed.html` | ✅ 1440+1366 | /publications/:eid/normalization (**PROPOSED**) |
| PI2.3-5: Hàng đợi phê duyệt | S09 | ✅ `s09_reviews.html` | ✅ 1440+1366 | /reviews |
| PI2.3-6: Thống kê/Tổng quan | S05 | ✅ `s05_dashboard.html` | ✅ 1440+1366 | /dashboard |

> **PI2.3-4 (S20)** được đánh dấu **PROPOSED** — chức năng chưa tồn tại trong production.

---

## 5. Kiểm tra file integrity

| Kiểm tra | Kết quả |
|---|---|
| CSS import `_tokens.css` trong tất cả màn | ✅ 11/11 |
| CSS import `_shell.css` (trừ S01 login) | ✅ 10/10 có sidebar |
| CSS import `_components.css` trong tất cả màn | ✅ 11/11 |
| S01 login không import `_shell.css` (đúng) | ✅ Không có sidebar |
| Không có link chết trong `_shared.html` | ✅ Sau Fix #2 và Fix #3 |
| Tổng số file prototype | 13 (3 CSS + 1 shared + 12 HTML) |

---

## 6. Figma Handoff Mapping

### 6.1 Frames hiện có (9 legacy frames)

| Node ID | Màn | Route | Trạng thái |
|---|---|---|---|
| 4:2 | Login | /login | ✅ Có |
| 4:22 | Dashboard | /dashboard | ✅ Có |
| 4:85 | Imports | /imports | ✅ Có |
| 4:138 | Publications list | /publications | ✅ Có |
| 4:205 | Pub detail | /publications/:eid | ✅ Có |
| 4:260 | Reviews queue | /reviews | ✅ Có |
| 4:322 | Candidate modal S10 | /reviews → modal | ✅ Có |
| 4:366 | Decision dialog S11/S12 | /reviews → dialog | ✅ Có |
| 4:409 | S20 PROPOSED | /normalization | ✅ Có |

### 6.2 Frames còn thiếu (3 frames — PI 2.3 coverage gap)

| Route | Figma frame | Prototype file | Screenshot QA |
|---|---|---|---|
| /review-history | ❌ CHƯA CÓ | ✅ `s13_review_history.html` | ✅ 8 ảnh Task 20A |
| /audit-logs | ❌ CHƯA CÓ | ✅ `s14_audit_logs.html` | ✅ 7 ảnh Task 20A |
| /tasks | ❌ CHƯA CÓ | ✅ `s15_tasks.html` | ✅ 3 ảnh Task 20A |

> **FIGMA_COMPLETE = FALSE** — 3 frames PI 2.3 chưa tồn tại trên Figma. Cần tạo sau khi Figma MCP rate-limit reset.

### 6.3 Thứ tự tạo frame khi resume Figma

1. Tạo frame S13 từ `s13_review_history.html` → node ID sẽ được ghi vào `figma_state.json`
2. Tạo frame S14 từ `s14_audit_logs.html`
3. Tạo frame S15 từ `s15_tasks.html`
4. Update 9 legacy frames với screenshot mới (production AS-IS)

---

## 7. Ràng buộc an toàn (đã tuân thủ trong Task 20B-R2)

- ✅ Không sửa teacher DB (`scopus_ictu_demo_teacher_20261014`)
- ✅ Không migration, không sửa CSV/JSON/Craw gốc
- ✅ Không sửa backend, không sửa code production
- ✅ Không đổi RBAC/matching/review semantics
- ✅ Không push GitHub
- ✅ Không xóa worktree/stash, không xóa 122 tài sản Task 19
- ✅ Không ghi FIGMA_COMPLETE khi Figma chưa đầy đủ
- ✅ Không tự xóa thiết kế Figma hiện có (9 legacy frames nguyên vẹn)
- ✅ Mật khẩu không in ra chat
- ✅ S20 đánh dấu rõ PROPOSED — không bịa tính năng đã triển khai

---

## 8. Tóm tắt kết luận

**GATE: PASS** ✅

- 11/11 màn mở thành công qua HTTP (127.0.0.1:7788)
- 0 lỗi JS console trên toàn bộ prototype
- 0 horizontal overflow ở 1366×768
- 4 màn ưu tiên (S09, S13, S14, S15) render nhất quán
- PI 2.3: 6/6 nhóm có prototype + QA screenshot + route mapping
- 3 lỗi layout/link đã sửa (BEFORE/AFTER documented)
- Figma handoff: 9 existing frames mapped, 3 missing clearly documented
- **FIGMA_COMPLETE = FALSE** (còn thiếu 3 frames: /review-history, /audit-logs, /tasks)

---

*Báo cáo tạo: Task 20B-R2 · Ngày 10/10/2026 · Claude Sonnet 4.6*  
*Deadline: 14/10/2026 · Git: main@530bf0f*
