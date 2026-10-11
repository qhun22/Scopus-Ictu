# TASK 20B-R1: Offline Design Report
**Trạng thái:** PARTIAL — Prototype hoàn thành, Figma còn thiếu 3 màn PI 2.3  
**Ngày:** 10/10/2026 · Nhánh: main@530bf0f  
**Phạm vi:** Thiết kế UI/UX ngoài Figma (Figma MCP hit rate-limit trong session)

---

## 1. Kết quả tổng quan

| Hạng mục | Kế hoạch | Thực hiện | Ghi chú |
|---|---|---|---|
| Token CSS (design tokens) | 121 biến | ✅ `_tokens.css` (121 vars) | Source: tokens.json |
| Shell / AppShell CSS | Hoàn chỉnh | ✅ `_shell.css` | Sidebar 256px + Topbar 64px |
| Component library CSS | 16 nhóm component | ✅ `_components.css` | Đầy đủ theo COMPONENT_INVENTORY.md |
| Navigation hub | 1 trang | ✅ `index.html` | 14 card, status badges |
| Màn P0 - PI 2.3 | 6 màn | ✅ 6/6 | s02, s03, s04, s05, s09, s20 |
| Màn P0 bổ sung | 5 màn | ✅ 5/5 | s01, s06, s13, s14, s15 |
| Figma frames | 11 màn PI 2.3 | ⚠️ 9/12 | Thiếu /review-history, /audit-logs, /tasks |
| Visual QA screenshots | 3 viewports | ⏳ Chưa (cần server) | Thiếu ghi nhận ảnh mới |
| GAP table | 10 code + 14 visual | ✅ Trong báo cáo này | |
| FIGMA_COMPLETE | — | ❌ KHÔNG ghi | Còn thiếu 3 frames |

---

## 2. Bộ prototype HTML/CSS

### 2.1 CSS cơ sở (3 file)

| File | Nội dung |
|---|---|
| [`prototype/_tokens.css`](ui/prototype/_tokens.css) | 121 CSS custom properties: 42 primitives + 43 semantic + 36 spacing/radius/size |
| [`prototype/_shell.css`](ui/prototype/_shell.css) | AppShell: `.sidebar` (256px), `.topbar` (64px), `.nav-item`, `.page-content`, `.role-badge` |
| [`prototype/_components.css`](ui/prototype/_components.css) | `.btn`, `.badge`, `.input`, `.card`, `.table-wrap`, `.modal-*`, `.dropzone`, `.toast`, `.spinner`, `.error-state`, v.v. |

### 2.2 HTML Screens (12 file)

| File | Màn | Route | Status | PI 2.3 |
|---|---|---|---|---|
| [`index.html`](ui/prototype/index.html) | Navigation hub | — | ✅ | — |
| [`s01_login.html`](ui/prototype/s01_login.html) | Đăng nhập | /login | AS-IS | — |
| [`s02_publications.html`](ui/prototype/s02_publications.html) | Danh sách công bố | /publications | AS-IS | PI2.3-1 |
| [`s03_pub_detail.html`](ui/prototype/s03_pub_detail.html) | Chi tiết công bố | /publications/:eid | AS-IS | PI2.3-2 |
| [`s04_imports.html`](ui/prototype/s04_imports.html) | Nhập dữ liệu | /imports | AS-IS | PI2.3-3 |
| [`s05_dashboard.html`](ui/prototype/s05_dashboard.html) | Tổng quan/Thống kê | /dashboard | AS-IS | PI2.3-6 |
| [`s06_lecturers.html`](ui/prototype/s06_lecturers.html) | Giảng viên + modal | /lecturers | AS-IS | — |
| [`s09_reviews.html`](ui/prototype/s09_reviews.html) | Hàng đợi + S10 + S11 + S11b + S12 | /reviews | AS-IS | PI2.3-5 |
| [`s13_review_history.html`](ui/prototype/s13_review_history.html) | Lịch sử review | /review-history | AS-IS | — |
| [`s14_audit_logs.html`](ui/prototype/s14_audit_logs.html) | Nhật ký hệ thống | /audit-logs | AS-IS | — |
| [`s15_tasks.html`](ui/prototype/s15_tasks.html) | Tác vụ (placeholder) | /tasks | AS-IS | — |
| [`s20_normalization_proposed.html`](ui/prototype/s20_normalization_proposed.html) | So sánh chuẩn hóa | /publications/:eid/normalization | **PROPOSED** | PI2.3-4 |

> **S20 PROPOSED**: Chức năng chưa tồn tại trong production. Đây là thiết kế đề xuất. KHÔNG báo cáo là đã triển khai.

---

## 3. Đối chiếu GAP thống nhất

### 3.1 Code GAPs (10 items)

| ID | Severity | Page/Component | Mô tả vấn đề | File nguồn | Effort |
|---|---|---|---|---|---|
| GAP-a | **HIGH** | /imports | Dropzone background AS-IS: transparent. TO-BE: `#EEF2FF` | pages/Imports/index.tsx | 1h |
| GAP-b | MEDIUM | /reviews (AntD modals) | Primary color trong AntD modal: #1677FF. TO-BE: #3A5FC3 | pages/ApprovalQueue/index.tsx | 2h |
| GAP-c | MEDIUM | /reviews REJECT dialog | textarea resize:none + char counter thiếu | pages/ApprovalQueue/index.tsx | 1h |
| GAP-d | LOW | /publications | Badge "Có công bố" / "Dùng chung" — màu cần verify vs spec | pages/Publications/index.tsx | 30m |
| GAP-e | LOW | /publications/:eid | Detail page section layout cần verify vs ảnh thật | pages/Publications/Detail.tsx | 1h |
| GAP-f | LOW | Nhiều trang | `shadow-xs`/`shadow-2xs` không generate trong Tailwind 3.4.19 → cards flat | tailwind.config.js | 30m |
| GAP-g | LOW | Nhiều trang | Font Saira weight 900 synthesized (không có trên Google Fonts) | index.html / CSS | 1h |
| GAP-h | LOW | LECTURER pages | Sidebar LECTURER chỉ hiện 4 menu items — cần verify trên màn LECTURER | pages/Lecturer/*.tsx | 30m |
| GAP-i | LOW | /audit-logs | Filter bar 5 inputs bị wrap ở 1440px viewport | pages/AuditLogs/index.tsx | 2h |
| GAP-j | LOW | /review-history | ActionBadge hiển thị raw code (CANDIDATE_ACCEPTED) thay vì nhãn VN | pages/ReviewHistory/index.tsx | 1h |

> **Tổng effort ước tính:** ~10h (không bao gồm QA). Không sửa khi chưa có phê duyệt GVHD.

### 3.2 Visual GAPs (14 items — từ FIGMA_VISUAL_QA.md)

| ID | Màn hình | Mô tả | Trạng thái |
|---|---|---|---|
| GAP-a | /imports | Dropzone bg color | Code fix cần thiết |
| GAP-b | /reviews | AntD modal button color | Cần AntD theme override |
| GAP-c | /reviews | REJECT textarea | Code fix nhỏ |
| GAP-d | /publications | Badge color variant | Verify sau khi có spec |
| GAP-e | /publications/:eid | Detail layout | Cần screenshot so sánh |
| GAP-f | Toàn cục | shadow-xs missing | tailwind.config fix |
| GAP-g | Toàn cục | Font weight 900 | Font config fix |
| GAP-h | /lecturers LECTURER | Menu LECTURER 4 items | Verify RBAC |
| GAP-i | /audit-logs | Filter bar wrap | Layout fix |
| GAP-j | /review-history | ActionBadge labels | i18n fix |
| GAP-k | /dashboard | Chart library (recharts vs native) | N/A — chưa triển khai |
| GAP-l | /reviews 409 | Conflict dialog styling | Verify vs production |
| GAP-m | /login | Error state color | Verify vs ảnh |
| GAP-n | Toàn cục | Responsive 1366×768 overflow | CSS fix nhỏ |

---

## 4. Xác minh bằng chứng ảnh chụp (Task 20A)

Kết quả kiểm tra từ `_quan_ly_do_an/logs/task20b/screenshot_capture.log`:

| Hạng mục | Kết quả |
|---|---|
| Tổng log entries | 101 |
| Unique PNG files | 78 |
| PNG tồn tại trên disk | 78 / 78 (100% match) |
| PNG thiếu | **0** |
| Viewports | 1440×900 (84), 1366×768 (10), 1920×1080 (4), 390×844 (3) |

**Phân bổ theo route PI 2.3:**

| Route | Số ảnh |
|---|---|
| /imports | 12 |
| /reviews | 17 |
| /dashboard | 7 |
| /publications | 6 |
| /publications/:eid | 4 |
| /review-history | 8 |
| /audit-logs | 7 |
| /tasks | 3 |
| S20 /normalization | **0** (chưa tồn tại) |

---

## 5. Trạng thái Figma

### 5.1 Frames đã có (9 legacy frames)

| Node ID | Màn | Route |
|---|---|---|
| 4:2 | Login | /login |
| 4:22 | Dashboard | /dashboard |
| 4:85 | Imports | /imports |
| 4:138 | Publications list | /publications |
| 4:205 | Pub detail | /publications/:eid |
| 4:260 | Reviews queue | /reviews |
| 4:322 | Candidate modal | /reviews → modal |
| 4:366 | Decision modal | /reviews → dialog |
| 4:409 | S20 PROPOSED | /normalization |

### 5.2 Frames còn thiếu (3 — PI 2.3 coverage gap)

| Route | Figma frame | Ảnh có | Prototype có |
|---|---|---|---|
| /review-history | ❌ KHÔNG CÓ | ✅ 8 ảnh | ✅ s13_review_history.html |
| /audit-logs | ❌ KHÔNG CÓ | ✅ 7 ảnh | ✅ s14_audit_logs.html |
| /tasks | ❌ KHÔNG CÓ | ✅ 3 ảnh | ✅ s15_tasks.html |

> **FIGMA_COMPLETE = FALSE** — Không thể tuyên bố hoàn thành PI 2.3 khi 3 frames PI 2.3 chưa có trên Figma.

### 5.3 Variables và Styles đã có

- **121 variables** trong 3 collections (Color Semantic 43, Primitives Tailwind 42, Spacing/Radius/Size 36)
- **19 text styles** (14 typography + 5 special)
- **6 effect styles** (shadow-xs qua shadow-2xl + 2 focus ring)

### 5.4 Kế hoạch sau khi Figma MCP rate-limit reset

1. Phase 2.c: Tạo icons atom (SVG sprites → Figma component set)
2. Phase 2.d: Atoms: Button, Badge, Input, Spinner
3. Phase 2.e: Molecules: FilterBar, StatCard, DataTable
4. Phase 2.f: Organisms: AppShell, ConfirmModal, UploadDropzone
5. Phase 3.a: Frame S13 Review History từ prototype s13_review_history.html
6. Phase 3.b: Frame S14 Audit Logs từ prototype s14_audit_logs.html
7. Phase 3.c: Frame S15 Tasks từ prototype s15_tasks.html
8. Phase 3.d–3.f: Bổ sung states còn thiếu cho 9 legacy frames
9. Phase 4: Visual QA + Code Connect

---

## 6. Ràng buộc an toàn (đã tuân thủ)

- ✅ Không sửa teacher DB (`scopus_ictu_demo_teacher_20261014`)
- ✅ Không migration, không sửa CSV/JSON/Craw gốc
- ✅ Không sửa backend, không sửa code production
- ✅ Không đổi RBAC/matching/review semantics
- ✅ Không push GitHub
- ✅ Không xóa worktree/stash, không xóa 122 tài sản Task 19
- ✅ Không ghi FIGMA_COMPLETE khi Figma chưa đầy đủ
- ✅ Không tự xóa thiết kế Figma hiện có (9 legacy frames nguyên vẹn)
- ✅ Mật khẩu không in ra chat
- ✅ S20 được đánh dấu rõ PROPOSED — không bịa tính năng đã triển khai
- ✅ Dữ liệu trong prototype là dữ liệu giả an toàn

---

## 7. Files đã tạo trong session Task 20B-R1

### Design documents (`docs/design/ui/`)
- `tokens.json` — Source of truth design tokens
- `DESIGN_SYSTEM_SPEC.md` — Full spec: 42+43+36 tokens, typography, effects, badges
- `SCREEN_INVENTORY.md` — ~40 screens inventory
- `SCREEN_TO_ROUTE_MAPPING.md` — Route→Component→File table + RBAC
- `COMPONENT_INVENTORY.md` — 16 component types + AntD organisms
- `USER_FLOWS.md` — 6 flows (Login/RBAC, Import, Publications, Review/409, Lecturer, S20)
- `FIGMA_HANDOFF.md` — Figma structure, node IDs, 9 legacy frames, 10-step resume plan
- `FIGMA_VISUAL_QA.md` — 14 visual GAPs, 50+ screenshot references
- `FIGMA_DELIVERY_MANIFEST.json` — JSON manifest (PI 2.3 coverage, GAPs, git state)
- `TASK20B_FIGMA_REPORT.md` — Full audit-answer report (16 câu hỏi)
- **`TASK20B_R1_OFFLINE_DESIGN_REPORT.md`** — File này

### Prototype (`docs/design/ui/prototype/`)
- `_tokens.css`, `_shell.css`, `_components.css` — CSS foundation (3 files)
- `_shared.html` — Sidebar HTML snippet
- `index.html` — Navigation hub (14 screen cards)
- `s01_login.html` — Login (4 states)
- `s02_publications.html` — Publications list (4 states)
- `s03_pub_detail.html` — Publication detail (4 states + candidates)
- `s04_imports.html` — Imports (7 states + GAP-a TO-BE)
- `s05_dashboard.html` — Dashboard (4 states + charts)
- `s06_lecturers.html` — Lecturers list + detail modal
- `s09_reviews.html` — Reviews queue + S10 modal + S11 ACCEPT + S11b 409 + S12 REJECT
- `s13_review_history.html` — Review history (4 states + GAP-j notice)
- `s14_audit_logs.html` — Audit logs (4 states + GAP-i TO-BE fix)
- `s15_tasks.html` — Tasks placeholder (AS-IS + FUTURE DESIGN zone)
- `s20_normalization_proposed.html` — Normalization comparison (**PROPOSED**, mock data)

### State ledger
- `_quan_ly_do_an/tools/task20b/figma_state.json` — Figma node IDs, resume instructions

### Memory
- `memory/task20b_figma_state.md` — Cross-session memory
- `memory/MEMORY.md` — Updated index

---

## 8. Cách mở prototype

```
# Mở trong browser (file://)
start "" "D:\DataFolder\ProjectIctu\DoAn\Scopus-Ictu\docs\design\ui\prototype\index.html"
```

Hoặc mở file `index.html` trực tiếp từ file explorer.  
Prototype chạy standalone — không cần server, không cần network.

---

*Báo cáo tạo: Task 20B-R1 · Ngày 10/10/2026 · Claude Sonnet 4.6*  
*Deadline: 14/10/2026 · Git: main@530bf0f*
