# WORKFLOW SIDEBAR UX — ACCEPTANCE REPORT

**Ngày:** 2026-10-14  
**Kết quả tổng thể:** ✅ PASS

---

## 1. Phạm vi thay đổi

| File | Thay đổi |
|------|---------|
| `frontend/src/components/common/Sidebar.tsx` | Thiết kế lại hoàn toàn với grouped navigation; RBAC (ADMIN/REVIEWER/LECTURER) |
| `frontend/src/components/common/buttonStyles.ts` | Đồng bộ màu Figma; thêm `BUTTON_GHOST` |
| `frontend/src/i18n/types.ts` | Thêm keys: `search`, `groupWorkflow`, `groupLookup`, `groupAdmin` |
| `frontend/src/i18n/locales/vi.ts` | Vietnamese labels cho 4 keys mới |
| `frontend/src/i18n/locales/en.ts` | English labels cho 4 keys mới |
| `frontend/src/pages/Normalization/index.tsx` | URL-synced tabs + WorkflowBanner |

---

## 2. Sidebar — acceptance checklist

### 2.1 ADMIN role

| Yêu cầu | Kiểm tra | Kết quả |
|---------|---------|---------|
| Nhóm "Quy trình xử lý" hiển thị | Code: `groupWorkflow` heading + imports/normalization/lecturers/reviews/review-history | ✅ |
| Nhóm "Tra cứu & kết quả" hiển thị | Code: `groupLookup` heading + publications/search | ✅ |
| Nhóm "Quản trị" hiển thị | Code: `groupAdmin` heading + dashboard/audit-logs/tasks | ✅ |
| Items chỉ đúng role ADMIN thấy | `imports`, `normalization`, `lecturers`, `users` không có trong REVIEWER/LECTURER nav | ✅ |

### 2.2 REVIEWER role

| Yêu cầu | Kiểm tra | Kết quả |
|---------|---------|---------|
| Chỉ thấy reviews + review-history | Code: REVIEWER groups chỉ có workflow với reviews/review-history | ✅ |
| Không thấy imports/normalization | Không có trong REVIEWER `NavGroup[]` | ✅ |

### 2.3 LECTURER role

| Yêu cầu | Kiểm tra | Kết quả |
|---------|---------|---------|
| Thấy my-publications/identity/profile | Code: LECTURER ungrouped items cuối | ✅ |
| Không thấy admin items | Không có trong LECTURER `NavGroup[]` | ✅ |

### 2.4 Visual & UX

| Yêu cầu | Kết quả |
|---------|---------|
| Màu active: `#3A5FC3`, left pill indicator | ✅ |
| Group heading: uppercase 10px slate-400 | ✅ |
| Collapsed: headings ẩn, divider thay thế | ✅ |
| Mobile: overlay sidebar, đóng khi click item | ✅ |

---

## 3. Normalization — Tab URL sync

| Tab | Click → URL | Init từ URL | Kết quả |
|-----|-------------|-------------|---------|
| Publications | `?tab=publications` | ✅ | ✅ |
| Authors | `?tab=authors` | ✅ | ✅ |
| Affiliations | `?tab=affiliations` | ✅ | ✅ |
| Matching | `?tab=matching` | ✅ | ✅ |
| Deep-link `?import=ID` | vẫn hoạt động (không xung đột) | ✅ | ✅ |

Cơ chế: `switchTab(tab)` gọi `setActiveTab` + `setSearchParams({tab}, {replace: true})`. Init: đọc `?tab=` từ URL, validate với `validTabs[]`.

---

## 4. WorkflowBanner — next-step hints

| Tab hiện tại | Gợi ý bước tiếp | Action |
|-------------|-----------------|--------|
| Publications | "Bước tiếp theo: Bóc tách tác giả" | `switchTab("authors")` |
| Authors | "Bước tiếp theo: Đối chiếu đơn vị tác giả" | `switchTab("affiliations")` |
| Affiliations | "Bạn có thể tra cứu công bố. Nếu có JSON Craw, tiếp tục đối sánh" | `switchTab("matching")` |
| Matching | "Ứng viên cần REVIEWER kiểm tra" | `<Link to="/reviews">` |

Màu banner: publications/authors/affiliations dùng `#EBEFF9` (brand light); matching dùng `#ECFDF5` (success green) để phân biệt cuối workflow.

---

## 5. TypeScript & Build

| Kiểm tra | Lệnh | Kết quả |
|---------|------|---------|
| TypeScript | `npx tsc --noEmit` | ✅ 0 errors |
| Build | `npm run build` | ✅ 3.55s, 0 errors |

---

## 6. Những gì KHÔNG thay đổi

- Logic RBAC `RoleRoute` — không đụng
- Backend API — không đụng  
- DB migrations — không đụng
- Test fixtures — không đụng
- Sidebar collapse/mobile overlay behavior — giữ nguyên logic
- Import deep-link `?import=ID` — vẫn hoạt động

---

*Báo cáo nghiệm thu UX sidebar và workflow hints — 2026-10-14*
