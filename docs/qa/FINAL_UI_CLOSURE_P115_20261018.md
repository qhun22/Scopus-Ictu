# Final UI Closure — PROMPT 11.5 (18/10/2026)

- **Release:** `v1.0.0-rc.1` vẫn **HOLD** (release gates §11).
- **Scope thực hiện:**
  - UI-10 fix: sticky action column `/lecturers`.
  - Figma KPI conflict: Stat Card `9:25` → `rounded-card`, `p-5`, `text-[28px]`.
  - R4-A PageHeader pilot: ReviewHistory + AuditLogs.
  - R4-B StatusBadge: kiểm tra — không có vị trí mới cần migrate.
  - `/tasks` product decision proposal.
  - UI-12/13/14 write-flow test status.
- **Không làm:** stage, commit, tag, push; migration; ghi DB; thay đổi credential; R4 diện rộng.

---

## 0. Git Baseline

| Mục | Kết quả |
|---|---|
| HEAD | `237f7bc` (main) |
| 4 blobs RC (staged) | `fb176d6 853c832 3b03317 0c34a85` — **INTACT** |
| Worktree diff SHA (đầu P11.5) | `7ab42548aa17a108` — trùng patch cuối P11 |
| Worktree diff SHA (cuối P11.5) | `f6212a45bdd7491e` |
| Patch cuối P11.5 | `scratch/p115/worktree_after_p115.patch` |

---

## 1. UI-10 — Sticky Action Column `/lecturers`

### Root cause

Table `w-full` không có `min-width` → ở viewport hẹp hơn tổng width tự nhiên (1154px > container 1124px), các column bị ép nhỏ và action column (grid `w-52`) bị cắt bởi `overflow-x-auto` container.

### Fix

- `<th>` Actions: thêm `sticky right-0 z-10 bg-slate-50/90 border-l border-slate-200/80`
- `<td>` Actions: thêm `sticky right-0 z-10 bg-white border-l border-slate-100`

**Approach**: sticky-right thay vì tăng min-width. Column luôn visible kể cả khi người dùng scroll ngang — UX tốt hơn so với chỉ đảm bảo scroll.

### Verification

**Run:** `p115/ui10_sticky_20261018T104513` — **17/17 PASS**

| Viewport | position | actionColumnVisible | buttonsVisible |
|---|---|---|---|
| 1440px | sticky ✅ | ✅ | ✅ |
| 1280px | sticky ✅ | ✅ | ✅ |
| 1024px | sticky ✅ | ✅ | ✅ |
| 768px | sticky ✅ | ✅ | ✅ |
| 375px | sticky ✅ | ✅ | ✅ |

No write requests, no console errors.

**Files thay đổi:** [`frontend/src/pages/Lecturers/index.tsx`](../../../frontend/src/pages/Lecturers/index.tsx)

---

## 2. Figma Decision Matrix

### A. Table header 11px vs 12px

| Thành phần | Node Figma | Spec Figma | Code | Kết luận |
|---|---|---|---|---|
| Badge text (status, pill) | `5:34` | 11px Bold | `text-[11px] font-bold` | ✅ MATCH |
| Table header (thead) | `4:88` Table/Header | 12px | `text-xs` (=12px) | ✅ MATCH |
| Table action button (tonal sm) | `9:72` | 11px | `text-[11px]` | ✅ MATCH |

**Verdict**: Không có conflict. 11px = badge/action button đúng spec `5:34`/`9:72`. 12px = table header đúng spec `4:88`.

### B. KPI value 28px vs 24px

| Thành phần | Node Figma | Spec Figma | Code trước | Code sau | Kết luận |
|---|---|---|---|---|---|
| Stat Card (summary) | `9:25` | r10, p20, value 28px | `rounded-[5px] p-4 text-3xl` | `rounded-card p-5 text-[28px]` | ✅ FIXED |
| Identity mini-card | `4:88` KPI | 24px | `text-2xl` (24px) | không đổi | ✅ MATCH `4:88` |

**Fix:** [`frontend/src/pages/Dashboard/index.tsx`](../../../frontend/src/pages/Dashboard/index.tsx) — `StatCard` component: `rounded-[5px]` → `rounded-card`, `p-4` → `p-5`, `text-3xl` → `text-[28px] leading-none`.

**Scope ảnh hưởng:** chỉ `StatCard` component cục bộ trong Dashboard. Identity mini-cards là component riêng, giữ nguyên.

### C. Badge padding 8px vs 10px

| Thành phần | Node Figma | Spec Figma | Code | Kết luận |
|---|---|---|---|---|
| Badge thông thường | `5:34` | px10 (=`px-2.5`) | `px-2.5` | ✅ MATCH (fixed P11) |
| Table badge nhỏ | không có variant | — | `px-2.5` | PR — không có spec Figma riêng |

**Verdict**: Badge padding conflict đã resolved ở P11. Không có action mới.

---

## 3. R4 Migration Backlog — Updated

### R4-A PageHeader pilot ✅ DONE

**Trang pilot:** ReviewHistory, AuditLogs (cùng pattern chính xác).

**Component tạo mới:** [`frontend/src/components/ui/PageHeader.tsx`](../../../frontend/src/components/ui/PageHeader.tsx)

```tsx
// Props: title, subtitle?, action?
<PageHeader title={copy.title} subtitle={copy.subtitle} action={<button...>} />
```

**Thay đổi:** ReviewHistory, AuditLogs: import + JSX thay thế inline header div.

**Verification:** run `20261018T105149_p115_r4a_regression` — **16/16 PASS** (h1, subtitle, refresh button, flex layout, mobile, no writes).

### R4-B StatusBadge ✅ KHÔNG CÓ ACTION MỚI

| Trang | Trạng thái | Lý do |
|---|---|---|
| ReviewHistory | Đã dùng `<Badge tone=...>` qua `reviewTones.ts` | DONE từ R3 |
| AuditLogs | Không có badge trạng thái | N/A |
| Imports | `badgeClassName` + render functions với compound state | Giữ — compound logic hợp lệ |
| ApprovalQueue | Đã có Badge qua reviewTones | DONE |

**Kết luận:** Không có vị trí mới cần migrate trong pilot 1-2 màn hình. Imports cần IMPORT_STATUS_TONE mapping riêng — đó là R4 full scope.

### R4 migration backlog (cần phê duyệt riêng)

| Component | Trang | Risk | Notes |
|---|---|---|---|
| PageHeader | Lecturers, Users, Normalization, Dashboard, Imports | LOW | Cần xử lý `page-action-group` class |
| StatusBadge (Imports) | Imports | MEDIUM | Cần `IMPORT_STATUS_TONE` với compound logic |
| DataTable shell | Tất cả trang danh sách | HIGH | Nhiều props, pagination, sticky |
| FilterBar | Imports, Lecturers, Normalization | MEDIUM | 3 cách viết khác nhau |
| EmptyState | Imports, Normalization, Reviews | LOW | Chuẩn hóa đơn giản |

**Không cần làm trước RC:** chỉ nếu DataTable/FilterBar được phê duyệt thì mới có giá trị trước RC. PageHeader còn lại có thể làm sau RC.

---

## 4. UI Write-Flow Test Status (UI-12/13/14)

| ID | Mô tả | Trạng thái | Lý do |
|---|---|---|---|
| UI-12 | DuplicateImportDialog — text `t.common.processing` khi loading | **BLOCKED** | Cần upload file duplicate → write action → cần phê duyệt write test riêng trên DB TEST cô lập |
| UI-13 | LecturerDatasetImportCard — nút exit/check | **BLOCKED** | Cần upload JSON → write action |
| UI-14 | Lecturers toasts EN (lock/unlock/reset/save) | **BLOCKED** | Cần thao tác ghi trên tài khoản giảng viên → cần DB TEST cô lập và quyền riêng |

Code đã đúng (đã thay đổi ở P11). Không có quyền hiện tại để test runtime. Cần phê duyệt write test mới.

---

## 5. `/tasks` Product Decision Proposal

**Hiện trạng:**
- Route `/tasks` → `TasksPlaceholderPage` (đã triển khai P09)
- Chỉ hiển thị trong ADMIN sidebar, nhóm "Admin"
- Không có route link từ LECTURER, REVIEWER
- Placeholder text VI/EN rõ ràng: tính năng chưa triển khai, dành cho quản lý background tasks

**Đề xuất (READ-ONLY, chờ quyết định chủ đồ án):**

| Phương án | Mô tả | Khuyến nghị |
|---|---|---|
| A. Giữ nguyên | Route + sidebar link ADMIN-only, placeholder text | **KHUYẾN NGHỊ** — không ảnh hưởng UX LECTURER/REVIEWER; ADMIN thấy rõ giới hạn |
| B. Ẩn khỏi sidebar | Xóa nav item, giữ route | Có thể làm nếu muốn clean UI, nhưng không cần thiết |

**Không cần thay đổi code.** Chờ quyết định sản phẩm.

---

## 6. Regression

**TypeScript:** ✅ tsc --noEmit clean (sau mỗi thay đổi)

**Build production:** ✅

| Build | Status | CSS size |
|---|---|---|
| Sau UI-10 sticky fix | ✅ | 62.23 kB |
| Sau Stat Card Figma fix | ✅ | 62.21 kB |
| Sau R4-A PageHeader | ✅ | 62.21 kB |

**CSS tokens verify:**
- `position:sticky` ✅
- `right:0` ✅
- `border-radius:10px` (`rounded-card`) ✅
- `font-size:28px` ✅
- `border-l` ✅

**Browser runs:**

| Run | Checks | PASS | FAIL |
|---|---|---|---|
| `ui10_sticky_20261018T104513` | 17 | 17 | 0 |
| `p115_r4a_regression_20261018T105149` | 16 | 16 | 0 |

---

## 7. Git Diff — Files thay đổi (P11.5 so với P11)

**Frontend (tracked, unstaged):**

| File | Thay đổi |
|---|---|
| [`frontend/src/pages/Lecturers/index.tsx`](../../../frontend/src/pages/Lecturers/index.tsx) | TH+TD Actions: `sticky right-0 z-10 border-l` |
| [`frontend/src/pages/Dashboard/index.tsx`](../../../frontend/src/pages/Dashboard/index.tsx) | StatCard: `rounded-card p-5 text-[28px] leading-none` |
| [`frontend/src/pages/ReviewHistory/index.tsx`](../../../frontend/src/pages/ReviewHistory/index.tsx) | Import + dùng `<PageHeader>` |
| [`frontend/src/pages/AuditLogs/index.tsx`](../../../frontend/src/pages/AuditLogs/index.tsx) | Import + dùng `<PageHeader>` |

**Frontend (untracked mới):**

| File | Thay đổi |
|---|---|
| [`frontend/src/components/ui/PageHeader.tsx`](../../../frontend/src/components/ui/PageHeader.tsx) | Component mới (R4-A pilot) |

---

## 8. Đề xuất commit bổ sung (chưa thực hiện)

Thêm vào kế hoạch commit từ P11:

| # | Commit | File |
|---|---|---|
| 5 | UI-10 sticky action column | `Lecturers/index.tsx` |
| 6 | Figma KPI fix — Stat Card | `Dashboard/index.tsx` |
| 7 | R4-A PageHeader pilot | `PageHeader.tsx`, `ReviewHistory/index.tsx`, `AuditLogs/index.tsx` |

---

## 9. Vấn đề còn chặn Release Candidate

| # | Hạng mục | Trạng thái |
|---|---|---|
| 1 | Credential `scopus_m12_user` @5432: rotate, kiểm listen/firewall, dọn `.tmp` | **BLOCKED (chủ đồ án)** |
| 2 | Figma conflicts: đã resolve A và B trong P11.5; C đã done P11 | ✅ DONE |
| 3 | UI-10 overflow `/lecturers` | ✅ FIXED (P11.5) |
| 4 | Commit (7 commit đề xuất P07–P11.5) | Chờ chủ đồ án |
| 5 | Full backend regression (~1.050 test) + launcher E2E App DB | Bước release |
| 6 | App DB revision vs HEAD (`c7f2a9b1d3e5`) | Chưa kiểm (không đụng App DB) |
| 7 | UI-12/13/14 write-flow tests | **BLOCKED — cần phê duyệt write test riêng** |
| 8 | `/tasks` | Giữ nguyên / quyết định sản phẩm (không blocking) |
| 9 | R4 diện rộng (DataTable, FilterBar, PageHeader các trang còn lại) | Sau RC hoặc phê duyệt riêng |

---

**Dừng tại đây** — chờ chủ đồ án và ChatGPT nghiệm thu PROMPT 11.5.
