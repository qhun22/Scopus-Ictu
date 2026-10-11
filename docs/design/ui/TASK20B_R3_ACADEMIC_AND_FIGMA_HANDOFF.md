# TASK 20B-R3: Chốt Chất Lượng Học Thuật và Hoàn Thiện Bàn Giao Figma
**Trạng thái:** PASS — Nội dung sai nghiệp vụ đã sửa, browser QA lại PASS, Figma checklist chuẩn bị  
**Ngày:** 10/10/2026 · Nhánh: main@530bf0f  
**Phạm vi:** Sửa prototype sai AS-IS; không sửa production, không sửa backend

---

## 1. Nội dung sai nghiệp vụ đã sửa

### 1.1 S09 — Hàng đợi phê duyệt (Reviews) ✅ ĐÃ SỬA

**Vấn đề:** Modal S10 hiển thị "Độ khớp: 89%" và score bars (Họ tên: 92%, Email: 85%, Khoa/BM: 90%). Bảng danh sách có cột "Độ khớp" với giá trị 89%, 76%, 95%, 42%.

**Căn cứ xác định sai:** `frontend/src/types/review.ts` — `ReviewQueueItem` và `ReviewCandidateDetail` không có trường `match_score`, `confidence`, `similarity`, hay bất kỳ giá trị định lượng tương đồng nào. Evidence thực tế là `name_evidence[]`, `publication_evidence[]`, `is_ambiguous`, `is_shared_scopus_author`.

**Đã sửa:**
- Bảng danh sách: Xóa cột "Độ khớp" → thay bằng cột "Bằng chứng" hiển thị `name_evidence_count` + `publication_support_count` + `is_ambiguous` / `is_shared_scopus_author`
- Modal S10: Xóa `.match-score-wrap` (28px bold score + score bars) → thay bằng evidence summary box (3 evidence counts AS-IS)
- Thêm NAME evidence list (rule-based: rule_id, lecturer_source_value, scopus_surface_value)
- Thêm PUBLICATION evidence list (reconciliation: DOI_EXACT / TITLE_EXACT)
- ACCEPT dialog: Xóa "Độ khớp: 89%" → thay bằng "Bằng chứng: 3 tên · 5 công bố hỗ trợ"
- CSS: Xóa `.match-score-wrap`, `.match-score-big`, `.score-breakdown`, `.score-bar-bg`, `.score-bar` → thêm `.evidence-summary`, `.ev-count-item`, `.rule-ev-list`

**Checksums trước/sau:**
- TRƯỚC: `04129960cf8c02c17c44a210e1d4145567e0727d923e00a716390aeebe032973`
- SAU: `6b202e10ba46d7db88f4aeb505b5d29f5be7ddbe0c8dd5775fdf43c1bea12294`

---

### 1.2 S05 — Tổng quan / Dashboard ✅ ĐÃ SỬA

**Vấn đề:** Bar chart "Công bố theo năm" và Donut "Trạng thái đối sánh" hiển thị như chức năng AS-IS. Không có nhãn phân biệt với chức năng thực tế.

**Căn cứ xác định sai:** `frontend/src/pages/Dashboard/index.tsx` — không import bất kỳ charting library nào (recharts, chart.js, etc.). `frontend/src/types/dashboard.ts` — `DashboardSummary` không có trường chuỗi thời gian (by year). Chỉ có: `total_publications`, `total_lecturers`, `active_lecturers`, `identity_counts`, `pending_review_count`, `latest_scopus_import`, `recent_audit_actions`.

**Đã sửa:**
- KPI cards: Thêm `<code>field_name</code>` mapping rõ từng card với field thực tế
- KPI card "Đã đối sánh": Đổi sub-text "67% tổng số" → "Candidate đã APPROVED" (đúng nghĩa)
- Thêm bảng "Phân bổ trạng thái identity" badge AS-IS — hiển thị 4 CANDIDATE/APPROVED/REJECTED/REVOKED với code field names
- Charts (bar + donut): Chuyển vào vùng **PROPOSED** có:
  - Border amber dashed
  - Banner "THIẾT KẾ ĐỀ XUẤT — CHƯA triển khai trong production"
  - Charts mờ (opacity 0.75), màu amber thay brand blue
  - Note "Số liệu giả — endpoint chưa có"
- "Top giảng viên": Badge PROPOSED (không có trong `DashboardSummary`)
- "Lần nhập gần đây": Badge AS-IS (dựa trên `latest_scopus_import`)

**Checksums trước/sau:**
- TRƯỚC: `29aa168f3c98e40ac7559fca7fd064aa205c90fe18bddcc2a4cbd1f6c61b527b`
- SAU: `dae0dd6b4066401cf39e5e4faa32ac4848bf0d2e00c1178ade485fde43021f3a`

---

### 1.3 S02 — Danh sách công bố ✅ ĐÃ SỬA

**Vấn đề:** Cột "Trạng thái" và filter dropdown dùng ACCEPTED/PENDING/REJECTED/SUPERSEDED — có thể gây nhầm nghĩ đây là trạng thái của publication, trong khi thực tế là trạng thái đối sánh tác giả (CandidateStatus).

**Căn cứ xác định sai:** `frontend/src/types/publication.ts` — không có trường status kiểu ACCEPTED/PENDING/REJECTED. `frontend/src/pages/Publications/index.tsx` chỉ filter theo `open_access_status`. Trạng thái đối sánh thuộc về `CandidateStatus` trong `frontend/src/types/review.ts`.

**Đã sửa:**
- Header cột: "Trạng thái" → "Đối sánh tác giả ⓘ" (tooltip giải thích)
- Filter: "Tất cả trạng thái" → "Tất cả đối sánh tác giả", options thêm mô tả ("ACCEPTED — Đã xác nhận")
- Thêm note xanh dưới bảng giải thích: "Cột 'Đối sánh tác giả' hiển thị CandidateStatus — không phải trạng thái của công bố Scopus"
- Comment header: Thêm giải thích rõ nguồn gốc trạng thái

**Checksums trước/sau:**
- TRƯỚC: `286f9aaf873aa8ff79905c320c9e3e046c18100d2e6194981f09a010d823def0`
- SAU: `7d1354a631cd249ea22e84a0615fcdd3badfdaa89ac22dd4de2e67c01a13d410`

---

### 1.4 Các màn khác — không cần sửa ✅

| Màn | Đánh giá | Lý do |
|---|---|---|
| S01 Login | OK | Không có dữ liệu nghiệp vụ |
| S03 Chi tiết công bố | OK | Data hiển thị từ Scopus CSV; không có score giả |
| S04 Nhập dữ liệu | OK | GAP-a đã được đánh dấu TO-BE rõ ràng |
| S06 Giảng viên | OK | Dữ liệu profile đúng cấu trúc; modal có H-index (từ Scopus — hợp lệ) |
| S13 Lịch sử review | OK | ActionBadge ACCEPT/REJECT đúng nghĩa (ReviewHistoryAction) |
| S14 Audit Logs | OK | Action codes đúng (CANDIDATE_ACCEPTED, etc.) |
| S15 Tasks | OK | Placeholder rõ AS-IS + FUTURE DESIGN zone |
| S20 Normalization | OK | Banner PROPOSED luôn hiển thị |

---

## 2. Browser QA sau khi sửa

| Màn | Viewport | Console | Layout | Kết luận |
|---|---|---|---|---|
| S09 Reviews | Desktop | 0 errors | ✅ | **PASS** |
| S09 Modal S10 (detail) | Desktop | 0 errors | Evidence grid đúng | **PASS** |
| S05 Dashboard | Desktop | 0 errors | PROPOSED zone amber rõ | **PASS** |
| S02 Publications | Desktop | 0 errors | "Đối sánh tác giả" đúng | **PASS** |

---

## 3. Figma — Đã làm thật đến đâu

### Có sẵn (9 legacy frames — nguyên vẹn)

| Node ID | Màn | Route |
|---|---|---|
| 4:2 | Login | /login |
| 4:22 | Dashboard | /dashboard |
| 4:85 | Imports | /imports |
| 4:138 | Publications list | /publications |
| 4:205 | Pub detail | /publications/:eid |
| 4:260 | Reviews queue | /reviews |
| 4:322 | Candidate modal S10 | /reviews → modal |
| 4:366 | Decision dialog S11/S12 | /reviews → dialog |
| 4:409 | S20 PROPOSED | /normalization |

**Variables/Styles (đã có):**
- 121 variables (3 collections: Color Semantic 43 + Primitives 42 + Spacing/Radius/Size 36)
- 19 text styles (14 typography + 5 special)
- 6 effect styles

### Còn thiếu — chưa làm được (Figma MCP rate-limit)

| Frame cần tạo | Prototype gốc | Screenshots Task 20A |
|---|---|---|
| /review-history | `s13_review_history.html` | 8 ảnh |
| /audit-logs | `s14_audit_logs.html` | 7 ảnh |
| /tasks | `s15_tasks.html` | 3 ảnh |

**Component library:** Phase 2 (atoms, molecules, organisms) chưa bắt đầu do rate-limit.

> **FIGMA_COMPLETE = FALSE** — Chưa có 3 frames và chưa có component library.

---

## 4. Việc còn thiếu để hoàn thành Figma

### 4.1 Khi Figma MCP reset — thứ tự thực hiện

1. **Phase 3.a**: Tạo frame S13 Review History
   - Nguồn: `s13_review_history.html` + `A_review_history_*.png` từ Task 20A
   - Data structure: `ReviewHistoryItem` từ `frontend/src/types/review.ts`

2. **Phase 3.b**: Tạo frame S14 Audit Logs
   - Nguồn: `s14_audit_logs.html` + `A_audit_logs_*.png`
   - Data structure: `AuditListItem` từ `frontend/src/types/audit.ts`

3. **Phase 3.c**: Tạo frame S15 Tasks
   - Nguồn: `s15_tasks.html` (placeholder AS-IS + FUTURE DESIGN zone)

4. **Phase 2**: Component library tối thiểu
   - Button (4 variants: primary/secondary/ghost/danger × default/disabled/loading)
   - Badge (5 types: ACCEPTED/PENDING/REJECTED/SUPERSEDED/PROPOSED)
   - Input (text, select, search)
   - Table (header + row + empty state)
   - Modal (lg 700px + sm 440px)
   - Sidebar (ADMIN 9 items, REVIEWER, LECTURER 4 items)
   - Topbar (role badge, user button, lang switch)
   - Card (stat card, chart card)
   - Pagination

5. **Phase 4**: Visual QA + screenshot Figma + Code Connect mapping

---

## 5. Checklist thao tác Figma Editor (khi MCP còn rate-limit)

Người dùng có thể thực hiện trực tiếp trên Figma Editor tại:
`https://www.figma.com/design/JL6qaElA0zehVEVhURJiIC`

### Tạo 3 frames còn thiếu (thao tác thủ công)

**B1: Tạo frame S13 Review History**
1. Mở Figma file → chọn page chứa 9 frames hiện có
2. Nhấn F để tạo Frame mới → resize 1440×900
3. Đặt tên: `S13 — Review History [AS-IS]`
4. Mở `http://127.0.0.1:7788/s13_review_history.html` trong browser → chụp màn hình
5. Import ảnh vào Figma làm reference → thiết kế lại từng thành phần
6. Hoặc: Plugin "Figma Import from URL / HTML" (nếu có)

**B2: Tạo frame S14 Audit Logs**
- Tên: `S14 — Audit Logs [AS-IS]`
- Nguồn: `s14_audit_logs.html` + `A_audit_logs_*.png` trong `_quan_ly_do_an/screenshots/`

**B3: Tạo frame S15 Tasks**
- Tên: `S15 — Tasks [AS-IS · Placeholder]`
- Nguồn: `s15_tasks.html`

### Cập nhật 9 frames cũ (tùy chọn)
1. Mở frame Dashboard (4:22) → cập nhật: xóa charts giả → thêm identity counts table
2. Mở frame Reviews (4:260) → cập nhật: xóa score column → thêm evidence columns
3. Mở frame Candidate modal (4:322) → cập nhật: xóa score wrap → thêm evidence summary

### Component library tối thiểu (thủ công)
1. Tạo page mới "Components" trong Figma file
2. Tạo component "Button" với 4 variants: Primary / Secondary / Ghost / Danger
3. Tạo component "Badge" với 5 variants
4. Bind variables đã có: `--color-brand-primary` (4:2), `--color-status-*`

---

## 6. Files cần bảo toàn trước 14/10

### Prototype (docs/design/ui/prototype/) — 13 files
```
_tokens.css   _shell.css   _components.css   _shared.html
index.html    s01_login.html   s02_publications.html   s03_pub_detail.html
s04_imports.html   s05_dashboard.html   s06_lecturers.html   s09_reviews.html
s13_review_history.html   s14_audit_logs.html   s15_tasks.html
s20_normalization_proposed.html
```

### Design documents (docs/design/ui/) — 13 files
```
tokens.json   DESIGN_SYSTEM_SPEC.md   SCREEN_INVENTORY.md
SCREEN_TO_ROUTE_MAPPING.md   COMPONENT_INVENTORY.md   USER_FLOWS.md
FIGMA_HANDOFF.md   FIGMA_VISUAL_QA.md   FIGMA_DELIVERY_MANIFEST.json
TASK20A_UI_SYNC_REPORT.md   TASK20B_FIGMA_REPORT.md
TASK20B_R1_OFFLINE_DESIGN_REPORT.md   TASK20B_R2_VISUAL_QA_REPORT.md
TASK20B_R3_ACADEMIC_AND_FIGMA_HANDOFF.md   (file này)
TASK20B_R2_CHECKSUMS.txt   TASK20B_R3_CHECKSUMS_DELTA.txt
```

### Figma file (cloud)
- URL: `https://www.figma.com/design/JL6qaElA0zehVEVhURJiIC`
- 9 legacy frames nguyên vẹn
- 121 variables + 19 text styles + 6 effect styles

### Task 19 assets (bảo toàn, không xóa)
- `_quan_ly_do_an/screenshots/` — 78 PNG (78/78 đã verify)
- `_quan_ly_do_an/logs/task20b/` — log files

---

## 7. Git status

```
Branch: main@530bf0f
Untracked (chưa commit):
  docs/design/    ← toàn bộ prototype + design docs
  docs/planning/

Modified (từ Task 17, trước R3):
  frontend/src/App.tsx
  frontend/src/pages/ApprovalQueue/index.tsx
  frontend/src/pages/AuditLogs/index.tsx
  frontend/src/pages/Imports/index.tsx
  frontend/src/pages/Normalization/index.tsx
  frontend/src/pages/ReviewHistory/index.tsx
```

**Không push.** Phương án commit local an toàn khi cần:
```bash
git add docs/design/ docs/planning/
git status  # Kiểm tra không có file nhạy cảm
git commit -m "Task 20B: Add UI prototype and design docs (11 screens, PI 2.3 coverage)"
```

> Không commit các file `frontend/src/pages/` modified cho đến khi Task 17 được kiểm duyệt riêng.

---

## 8. Ràng buộc an toàn (đã tuân thủ trong Task 20B-R3)

- ✅ Không sửa teacher DB
- ✅ Không migration, không sửa CSV/JSON/Craw gốc
- ✅ Không sửa backend, không sửa code production
- ✅ Không đổi RBAC/matching/review semantics
- ✅ Không push GitHub
- ✅ Không xóa worktree/stash, không xóa 122 tài sản Task 19
- ✅ Không ghi FIGMA_COMPLETE khi Figma chưa đầy đủ
- ✅ Không tự xóa thiết kế Figma hiện có
- ✅ Mật khẩu không in ra chat
- ✅ S20 vẫn đánh dấu PROPOSED

---

*Báo cáo tạo: Task 20B-R3 · Ngày 10/10/2026 · Claude Sonnet 4.6*  
*Deadline: 14/10/2026 · Git: main@530bf0f*
