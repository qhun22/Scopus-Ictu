# Component Inventory — Scopus–ICTU · Task 20B

**Ngày lập:** 10/10/2026  
**Nguồn:** `frontend/src/` (React/Tailwind/AntD); đối chiếu ảnh chụp thật

---

## Phân loại trạng thái

- **IMPLEMENTED** — component đang hoạt động trong sản phẩm
- **AntD** — dùng Ant Design, chưa chuyển sang Tailwind thuần
- **DESIGN IMPROVEMENT** — có đề xuất chỉnh code (xem DESIGN_TO_CODE_GAP)
- **PROPOSED** — chưa triển khai

---

## A. AppShell & Layout

| Component | Trạng thái | File | Mô tả |
|---|---|---|---|
| AppLayout | IMPLEMENTED | layouts/AppLayout.tsx | Wrapper chính: Sidebar + Header + nội dung |
| Sidebar | IMPLEMENTED | components/common/Sidebar.tsx | w-64 expanded / w-20 collapsed; menu theo vai trò |
| Header (Topbar) | IMPLEMENTED | components/common/Header.tsx | h-16 sticky; tiêu đề trang; công tắc VI/EN; user menu |
| UserMenu dropdown | IMPLEMENTED | Header.tsx | Avatar tròn + dropdown (Tài khoản / Đăng xuất) |
| LanguageSwitch | IMPLEMENTED | Header.tsx | VI \| EN h-10 |
| RoleBadge | IMPLEMENTED | Header.tsx | ADMIN(blue) / REVIEWER(amber) / LECTURER(emerald) |

---

## B. Atoms

### Buttons

| Variant | Trạng thái | Tailwind class | File |
|---|---|---|---|
| Primary | IMPLEMENTED | bg-[#3A5FC3] text-white rounded-lg | vd. Imports button |
| Secondary | IMPLEMENTED | border border-slate-200 bg-white text-slate-700 rounded-md | — |
| Ghost | IMPLEMENTED | text-[#3A5FC3] bg-transparent hover:bg-brand/5 | — |
| Danger | IMPLEMENTED | bg-rose-600 text-white | — |
| Table Action | IMPLEMENTED | h-7 rounded-md border-slate-200 text-[11px] | — |
| Disabled | IMPLEMENTED | opacity-50 cursor-not-allowed | — |
| Loading (spinner) | IMPLEMENTED | animate-spin icon inside | — |

> **GAP-b:** Nút Primary trong modal AntD ở /reviews hiển thị màu AntD #1677FF thay vì #3A5FC3.

### Badges / Status chips

| Variant | Trạng thái | Ghi chú |
|---|---|---|
| PENDING | IMPLEMENTED | amber |
| ACCEPTED | IMPLEMENTED | emerald |
| REJECTED | IMPLEMENTED | rose |
| SUPERSEDED | IMPLEMENTED | slate neutral |
| Có công bố | IMPLEMENTED | cyan |
| Dùng chung (cảnh báo) | IMPLEMENTED | rose — phải nổi bật |
| Role (ADMIN/REVIEWER/LECTURER) | IMPLEMENTED | — |

### Inputs

| Variant | Trạng thái | File |
|---|---|---|
| Text input | IMPLEMENTED | AntD + Tailwind |
| Search input | IMPLEMENTED | /publications, /lecturers |
| Select | IMPLEMENTED | — |
| Date range | IMPLEMENTED | /audit-logs |
| Textarea | IMPLEMENTED | /reviews reject dialog |

### Others

| Component | Trạng thái | File |
|---|---|---|
| Toast | IMPLEMENTED | components/common/ToastContext.tsx |
| Pagination | IMPLEMENTED | nhiều trang |
| Tab | IMPLEMENTED | /lecturers detail modal |

---

## C. Molecules

| Component | Trạng thái | File | Ghi chú |
|---|---|---|---|
| PageHeader | IMPLEMENTED | từng page | Tiêu đề + subtitle + action button |
| FilterBar | IMPLEMENTED | /reviews, /audit-logs, /publications | Thanh lọc + tìm kiếm |
| StatCard | IMPLEMENTED | /dashboard, /home | Số KPI + nhãn + icon + màu nền |
| Card | IMPLEMENTED | nhiều nơi | rounded-xl border-slate-200/80 |
| Table (header + row) | IMPLEMENTED | — | rounded-xl; thead bg-slate-50/70; ô px-4 py-3.5 |
| TableFooter (pagination) | IMPLEMENTED | — | bg-slate-50/50 text-[11px] |
| ConfirmModal | IMPLEMENTED | components/common/ConfirmModal.tsx | Variant: danger/warning/primary; rounded-2xl |
| UploadDropzone (CSV) | IMPLEMENTED | pages/Imports/index.tsx | — |
| UploadDropzone (JSON) | IMPLEMENTED | pages/Imports/index.tsx | — |
| ImportPreview table | IMPLEMENTED | pages/Imports/index.tsx | Hiển thị 410/352/58 hàng |
| EmptyState | IMPLEMENTED | nhiều trang | — |
| LoadingSpinner | IMPLEMENTED | nhiều trang | animate-spin |
| ErrorState | IMPLEMENTED | nhiều trang | Khi 503 |

---

## D. AntD organisms (chưa chuyển Tailwind)

| Component | Trạng thái | File | GAP |
|---|---|---|---|
| Modal chi tiết ứng viên | AntD | pages/ApprovalQueue/index.tsx | GAP-b: font default, màu AntD |
| Dialog ACCEPT confirm | AntD | pages/ApprovalQueue/index.tsx | GAP-b |
| Dialog REJECT + textarea | AntD | pages/ApprovalQueue/index.tsx | GAP-b, GAP-c (bộ đếm chồng nút) |
| Modal chi tiết giảng viên | AntD | pages/Lecturers/index.tsx | GAP-b |
| Modal thêm giảng viên | AntD | pages/Lecturers/index.tsx | GAP-b |

---

## E. Proposed (chưa triển khai)

| Component | Mục đích | Màn |
|---|---|---|
| NormalizationComparison table | Bảng 4 cột: Trường / Raw / Chuẩn hóa / Quy tắc | S20 |
| NormalizationDiffBadge | Nhãn Giữ nguyên / Đã chuẩn hóa / Khác biệt / Thiếu | S20 |
| NormalizationSummaryCounter | Bộ đếm NEW / EXISTING_UNCHANGED / EXISTING_METADATA_CHANGED / INVALID_EID | S20 |

---

## Tóm tắt

- **Tổng component IMPLEMENTED:** ~35
- **Dùng AntD (cần đánh giá migration):** 5 organism
- **PROPOSED:** 3
- **Figma component đã tạo (Phase 2–3):** PARTIAL — rate limit MCP. Variables/styles ✅; component frames chưa tạo được.
