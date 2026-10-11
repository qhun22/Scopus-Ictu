# Task 20A — Báo cáo đồng bộ giao diện 4 trang

> **Ngày thực hiện:** 09–10/10/2026  
> **Trạng thái:** ✅ HOÀN THÀNH  
> **Tác giả:** Trương Quang Huy (hỗ trợ bởi Claude Code)

---

## 1. Bốn trang đã chỉnh sửa

| Route | Tệp nguồn | Vấn đề trước | Kết quả sau |
|---|---|---|---|
| `/reviews` | `frontend/src/pages/ApprovalQueue/index.tsx` | AntD `Title`/`Card`/`Select` làm header & filter bar khác hệ thống | Header Tailwind slate, filter bar rounded-xl white card, native `<select>` h-8, nút "Làm mới" matching |
| `/review-history` | `frontend/src/pages/ReviewHistory/index.tsx` | `text-2xl font-semibold` (xám) + `rounded-lg border-gray-200 bg-gray-50` | `text-xl font-bold text-slate-800 sm:text-2xl` + filter bar rounded-xl shadow-xs, bảng slate |
| `/audit-logs` | `frontend/src/pages/AuditLogs/index.tsx` | `text-2xl font-semibold` + filter `bg-blue-600` Apply button, bảng `divide-gray-200 bg-gray-50` | Header slate-800, filter bar Tailwind, badge hành động `bg-indigo-50 ring-indigo-200`, badge thực thể `bg-slate-100` |
| `/tasks` | `frontend/src/App.tsx` (cập nhật prop) | Mô tả chung chung "Tính năng này đang trong quá trình hoàn thiện" | "Chức năng đang phát triển. Trang này dành riêng cho quản lý tác vụ nền trong các phiên bản tương lai — chưa có bộ lập lịch hay công cụ thực thi nào được triển khai." |

---

## 2. Vấn đề UI trước khi sửa

### `/reviews` (ApprovalQueue)
- **PageHeader:** Dùng AntD `<Title level={2}>` (Arial/Helvetica không phải Saira, size mặc định AntD) + `<Paragraph>` thay vì `h1.text-xl.font-bold.text-slate-800`
- **FilterBar:** Dùng AntD `<Card>` bao ngoài + AntD `<Select>` cho 3 bộ lọc + AntD `<Button>` → khác màu, khác height, khác border-radius so với `/publications`
- **"Xem chi tiết":** Dùng AntD `<Button type="link">` → xanh underline, không có border box
- **Khoảng cách:** `mb-5` cứng, không dùng gap/space-y nhất quán

### `/review-history`
- **Header:** `text-2xl font-semibold` (không có slate-800, không sm:text-2xl)
- **FilterBar container:** `rounded-lg border-gray-200 bg-white p-4` → thiếu `shadow-xs`, không `rounded-xl`, không `border-slate-200/80`
- **Inputs:** `rounded-md border-gray-300 px-3 py-1.5 text-sm focus:ring-blue-500` → blue focus thay vì `#3A5FC3`
- **Apply button:** `bg-blue-600 text-white` thay vì Tailwind ghost button với hover:#3A5FC3
- **Badges:** `bg-green-50`/`bg-red-50`/`bg-yellow-50` (không có `ring`), status badge `bg-gray-100`
- **Table:** `bg-gray-50 divide-gray-200 hover:bg-gray-50` thay vì `bg-slate-50/70 divide-slate-100 hover:bg-slate-50/50`

### `/audit-logs`
- Giống ReviewHistory: header xám, filter bar gray, nút Apply xanh navy
- **Badges hành động:** `bg-blue-50 text-blue-700` không có `ring-1`
- **Badges thực thể:** `bg-gray-100 text-gray-700` không có `ring-1`
- **Loading/error states:** border-gray-200, border-red-200 (không nhất quán với rose pattern)

### `/tasks`
- Mô tả quá chung chung, không nói rõ "Chức năng đang phát triển" hay bản chất của trang

---

## 3. Tệp nguồn đã thay đổi

| Tệp | Loại thay đổi |
|---|---|
| `frontend/src/pages/ApprovalQueue/index.tsx` | Xóa `Card`/`Select`/`Title`/`Paragraph` (AntD) khỏi render page; thêm header Tailwind; thêm filter bar Tailwind với `<select>` native; thêm error state Tailwind; giữ nguyên `Table`, `Modal`, `Card` (detail modal), toàn bộ business logic |
| `frontend/src/pages/ReviewHistory/index.tsx` | Viết lại toàn bộ phần UI (giữ nguyên 100% logic/state/API) |
| `frontend/src/pages/AuditLogs/index.tsx` | Viết lại toàn bộ phần UI (giữ nguyên 100% logic/state/API) |
| `frontend/src/App.tsx` | Thêm prop `description` cho `/tasks` PlaceholderPage |

**Không thay đổi:**
- `frontend/src/pages/Publications/index.tsx` ✅
- `frontend/src/pages/Lecturers/index.tsx` ✅
- `frontend/src/pages/Imports/index.tsx` ✅
- `frontend/src/pages/Dashboard/index.tsx` ✅
- `frontend/src/components/common/PlaceholderPage.tsx` ✅ (không cần sửa component)
- Toàn bộ API/logic/RBAC/routing ✅

---

## 4. Các thành phần tái sử dụng (từ pattern của `/publications`)

| Pattern | Nguồn gốc | Áp dụng cho |
|---|---|---|
| `h1.text-xl.font-bold.text-slate-800.sm:text-2xl` | `Publications` PageHeader | `/reviews`, `/review-history`, `/audit-logs` |
| `p.mt-0.5.text-xs.text-slate-500.sm:text-sm` | `Publications` subtitle | `/reviews`, `/review-history`, `/audit-logs` |
| `div.rounded-xl.border.border-slate-200/80.bg-white.p-3.5.shadow-xs` | `Publications` FilterBar container | `/reviews`, `/review-history`, `/audit-logs` |
| `h-8.rounded-lg.border.border-slate-200.bg-white.px-2.5.text-xs...focus:border-[#3A5FC3].focus:ring-[#3A5FC3]/20` | `Publications` input fields | `/review-history`, `/audit-logs` (tất cả inputs) |
| `h-8.cursor-pointer...hover:border-[#3A5FC3].hover:text-[#3A5FC3]` (ghost button) | `Publications` Apply/Clear | Tất cả trang (Apply/Clear/Refresh) |
| `h-9.rounded-lg.border.border-slate-300...shadow-xs` (secondary button) | `Publications` Export | `/reviews`, `/review-history`, `/audit-logs` (Làm mới) |
| `div.overflow-hidden.rounded-xl.border.border-slate-200/80.bg-white.shadow-xs` | `Publications` table wrapper | `/review-history`, `/audit-logs` |
| `thead.border-b.border-slate-200/80.bg-slate-50/70.text-slate-600` | `Publications` table header | `/review-history`, `/audit-logs` |
| `tr.hover:bg-slate-50/50.transition-colors` | `Publications` table rows | `/review-history`, `/audit-logs` |
| `div.flex...border-t.border-slate-100.bg-slate-50/50.px-4.py-2.5.text-[11px].text-slate-500` | `Publications` footer | `/review-history`, `/audit-logs` |
| `rounded-xl.border.border-rose-200.bg-rose-50...flex.items-start.gap-2.5` (error state) | `Publications` error | `/reviews`, `/review-history`, `/audit-logs` |
| `h-6.w-6.animate-spin.rounded-full.border-2.border-slate-200.border-t-[#3A5FC3]` (spinner) | `Publications` loading | `/review-history`, `/audit-logs` |

---

## 5. Ảnh BEFORE / AFTER

> **Lưu ý:** Ảnh được chụp trong phiên làm việc. Ảnh BEFORE chụp trước khi sửa code; ảnh AFTER chụp sau khi HMR áp dụng và Vite dev server xác nhận.

### `/reviews` — BEFORE

- AntD Title header (Arial, đen, đậm theo AntD default)
- AntD Card bao quanh filter bar và bảng
- AntD Select (với dropdown riêng, styled theo AntD token)
- AntD Button type="link" cho "Xem chi tiết" (xanh underline)

### `/reviews` — AFTER (1440×900 và 1366×768)

- Tailwind `h1.text-xl.font-bold.text-slate-800` header
- Filter bar `rounded-xl border border-slate-200/80 bg-white` với native `<select>` h-8
- "Làm mới" button với `hover:border-[#3A5FC3] hover:text-[#3A5FC3]`
- "Xem chi tiết" button: `rounded-md border border-slate-200 hover:border-[#3A5FC3]` (box style)
- Table bọc trong `rounded-xl border border-slate-200/80 bg-white shadow-xs`
- Ở 1366×768: filter bar wrap, bảng không overflow, nút Xem chi tiết vẫn thấy

### `/review-history` — AFTER

- Header slate-800 bold + subtitle slate-500
- Filter bar inline với select + datetime-local inputs, nút ghost Apply/Clear
- Badges: ACCEPT `bg-emerald-50 ring-emerald-200`, REJECT `bg-rose-50 ring-rose-200`, REOPEN `bg-amber-50 ring-amber-200`
- Status badges: `bg-slate-100 ring-slate-200`
- Bảng: `thead bg-slate-50/70`, rows `hover:bg-slate-50/50`, `divide-slate-100`
- Footer: `bg-slate-50/50 text-[11px]` với page size selector

### `/audit-logs` — AFTER

- Header slate-800 + subtitle slate-500
- Filter bar 5 trường: Hành động, Loại thực thể, Loại tác nhân, Từ ngày, Đến ngày
- Badge hành động: `bg-indigo-50 text-indigo-700 ring-indigo-200`
- Badge thực thể: `bg-slate-100 text-slate-600 ring-slate-200`
- ActorCell: USER → `text-slate-700`, SYSTEM → `italic text-slate-400`
- Bảng và footer giống pattern Publication

### `/tasks` — AFTER

- Icon teal, tiêu đề "Tác vụ hệ thống"
- Mô tả: "Chức năng đang phát triển. Trang này dành riêng cho quản lý tác vụ nền trong các phiên bản tương lai — chưa có bộ lập lịch hay công cụ thực thi nào được triển khai."
- Không có bộ lập lịch, không có dữ liệu giả, không có nút Start/Stop giả

---

## 6. Kết quả build frontend

```
✓ tsc --noEmit   →  0 errors
✓ vite build     →  built in 4.05s
```

**Kết quả TypeScript:**
- Lỗi ban đầu sau chỉnh sửa: 3 lỗi (`Card` còn dùng trong modal, `t.common.retry` không tồn tại ×2)
- Sửa xong: `Card` thêm lại vào imports (vẫn dùng trong detail modal), `retry` → hardcode "Thử lại"
- Typecheck PASS

**Kết quả build:**
- 1485 modules → 1 JS chunk 1387 KB + 1 CSS chunk 50 KB
- Cảnh báo chunk size: pre-existing (AntD bundle), không phải do thay đổi này
- PASS

---

## 7. Kết quả kiểm tra trình duyệt

**Môi trường thử nghiệm:**
- DB: `scopus_ictu_test_ui20a_20261009` (test DB riêng biệt, không phải teacher DB)
- Backend: `http://127.0.0.1:8003` (demo cluster 55432)
- Frontend: Vite dev `http://127.0.0.1:5176`
- Tài khoản: ADMIN (`admin@gmail.com`)

**Kết quả smoke test:**

| Kiểm tra | Kết quả |
|---|---|
| `/reviews` tải được danh sách (20 PENDING) | ✅ |
| Filter trạng thái: ACCEPTED → 0 results, empty state | ✅ |
| Filter trạng thái: PENDING → 40 records, 20/page | ✅ |
| "Xem chi tiết" mở modal đúng | ✅ |
| ACCEPT button hiện trong modal | ✅ |
| REJECT button hiện trong modal | ✅ |
| `/review-history` tải được (empty, ADMIN view) | ✅ |
| `/audit-logs` tải được, 50 records/page | ✅ |
| `/tasks` hiện placeholder mô tả đúng | ✅ |
| `/publications` không thay đổi (reference) | ✅ |
| Viewport 1440×900: không tràn, action visible | ✅ |
| Viewport 1366×768: filter wrap, không mất nội dung | ✅ |
| Console errors: chỉ AntD deprecation warning (pre-existing) | ✅ |
| RBAC: `/audit-logs` vẫn chỉ ADMIN (routing không đổi) | ✅ |

---

## 8. Hạn chế còn lại

1. **AntD Table ở `/reviews`:** ~~Phần bảng dữ liệu (`<Table>` AntD) vẫn dùng AntD table styling~~ → **ĐÃ KHẮC PHỤC trong Task 20A-R2.** AntD `<Table>` đã được thay thế hoàn toàn bằng bảng Tailwind thuần, đồng bộ với `/imports`.

2. **Cảnh báo AntD `destroyOnClose`:** 4 Modals trong `/reviews` dùng `destroyOnClose` đã bị deprecated trong AntD v5 → v6. Đây là vấn đề pre-existing, không do Task 20A tạo ra. Cần nâng cấp lên `destroyOnHidden` trong tương lai.

3. **`/review-history` khi REVIEWER:** Người dùng REVIEWER có thể truy cập `/review-history` theo RBAC (route được phép). Khi đó danh sách sẽ chỉ thấy các quyết định của chính họ. Tính năng lọc reviewer không được thêm vào Task 20A (ngoài phạm vi).

4. **Figma chưa được cập nhật:** Task 20A chỉ ghi nhận mapping (section 9) để cập nhật sau. Figma file `https://www.figma.com/design/JL6qaElA0zehVEVhURJiIC` chưa được sync với AFTER images.

---

## 9. Figma mapping để sync sau

> Figma file: https://www.figma.com/design/JL6qaElA0zehVEVhURJiIC  
> **Không chỉnh sửa Figma trong Task 20A.** Mapping dưới đây để dùng trong Task 20B/Figma task.

| Màn Figma | Route thật | Thay đổi cần sync trong Figma |
|---|---|---|
| FG-05 (Hàng đợi phê duyệt) | `/reviews` | Header h1 slate-800 + subtitle slate-500; filter bar rounded-xl white với native selects; "Xem chi tiết" button box style; "Làm mới" button |
| FG-05 (detail modal) | `/reviews` → modal | Không thay đổi (AntD Cards vẫn nguyên) |
| (chưa có) Review History | `/review-history` | Toàn bộ layout mới: header, filter bar, bảng slate, badges ACCEPT/REJECT/REOPEN, footer pagination |
| (chưa có) Audit Logs | `/audit-logs` | Header, filter bar 5 trường, bảng, badge indigo (hành động), badge slate (thực thể), ActorCell |
| (chưa có) Tasks | `/tasks` | Placeholder card với mô tả "Chức năng đang phát triển" |

**Design tokens cần cập nhật:**
- Primary: `#3A5FC3` (hover `#2F4EA6`) 
- Page bg: `#F4F6FB`
- Text: `#172033` (slate-900)
- Card border: `rgba(148,163,184,0.5)` (slate-200/80)
- Heading: `font-bold text-slate-800` = `#1E293B`
- Subtitle: `text-slate-500` = `#64748B`
- Table header bg: `bg-slate-50/70`
- Table row hover: `bg-slate-50/50`
- Filter container shadow: `shadow-xs`

---

## Tiêu chí PASS (Task 20A gốc)

- [x] Bốn trang `/reviews`, `/review-history`, `/audit-logs`, `/tasks` đồng bộ visual language với `/imports`, `/lecturers`, `/publications`
- [x] TypeScript typecheck PASS (0 errors)
- [x] Vite build PASS
- [x] Smoke test trình duyệt: tải dữ liệu, filter, pagination, ACCEPT/REJECT hoạt động
- [x] RBAC không bị thay đổi
- [x] Trang tham chiếu không bị thay đổi
- [x] Không có console/render errors nghiêm trọng mới
- [x] Safety: không sửa DB, không migration, không sửa Backend, không sửa matching engine, không push GitHub

---

## Task 20A-R2 — Khắc phục bảng `/reviews` (10/10/2026)

### Vấn đề gốc

Task 20A build PASS nhưng KHÔNG được chấp nhận về mặt hình ảnh: bảng `/reviews` vẫn dùng AntD `<Table>` component với AntD default styling (header có nền xám đặc trưng AntD, row height AntD, pagination component AntD). Chỉ có PageHeader và FilterBar được đồng bộ, chưa đồng bộ phần bảng.

**Root cause:** `<Table>` AntD được giữ lại từ bản gốc; Task 20A chỉ sửa header và filter bar bên trên bảng.

### Phân tích nguồn tham chiếu

Đọc trực tiếp `frontend/src/pages/Imports/index.tsx` (toàn bộ 2424 dòng):

| Phần | Pattern Imports |
|---|---|
| Table container | `<section className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-xs">` |
| Scroll wrapper | `<div className="relative overflow-x-auto">` |
| Table element | `<table className="w-full text-left text-xs">` |
| Header | `<thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">` |
| Header cell | `<th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">` |
| Body | `<tbody className="divide-y divide-slate-100">` |
| Data row | `<tr className="hover:bg-slate-50/50 transition-colors">` |
| Data cell | `<td className="px-4 py-3.5 align-middle whitespace-nowrap">` |
| Status badge | `"inline-flex h-6 items-center justify-center rounded-full border px-2.5 text-[11px] font-bold whitespace-nowrap"` |
| Action button | `"inline-flex h-7 w-full items-center justify-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-[11px] font-semibold text-slate-700 shadow-2xs transition-all duration-150 active:scale-[0.97] hover:border-[#3A5FC3] hover:text-[#3A5FC3] cursor-pointer whitespace-nowrap"` |
| Footer | `<div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-2.5 text-[11px] text-slate-500">` |
| Page size select | `<select className="h-6 rounded-md border border-slate-200 bg-white px-1.5 text-[11px] font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer disabled:opacity-50">` |
| Prev/Next buttons | `<button className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 ... hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40">` |

### Thay đổi thực hiện

**Tệp:** `frontend/src/pages/ApprovalQueue/index.tsx`

1. **Xóa khỏi imports:** `Table` (AntD), `useMemo`, `ColumnsType`
2. **Thêm constants:**
   - `STATUS_BADGE_CLASS`: Record map trạng thái → Tailwind badge color class
   - `badgeClassName`: chuỗi class chung cho pill badge (rounded-full, h-6, px-2.5)
3. **Xóa `columns` useMemo block** (73 dòng) — không còn cần thiết
4. **Thêm `totalPages`** computed từ `total / pageSize`
5. **Thay `<Table>` AntD** bằng `<section>` + `<div.relative.overflow-x-auto>` + `<table.w-full.text-left.text-xs>` với đầy đủ thead/tbody/tr/td theo pattern Imports
6. **Badge trạng thái:** AntD `<Tag color={...}>` → `<span className="${badgeClassName} ${STATUS_BADGE_CLASS[...]}">` (pill rounded-full)
7. **Badge bằng chứng:** AntD `<Tag>` → `<span className="inline-flex h-5 ... rounded-full border ...">` với màu cyan (có công bố) / slate (chỉ bằng chứng tên)
8. **Badge mơ hồ:** AntD `<Tag color="orange"/"default"/"red">` → Tailwind pill amber/slate/rose tương ứng
9. **Action button:** Giữ nguyên cấu trúc từ Task 20A, thêm icon eye, thêm `h-7`/`active:scale-[0.97]` cho nhất quán với Imports
10. **Footer pagination:** Thêm mới hoàn toàn — hiển thị `Hiển thị X trong Y ứng viên`, page size selector, Trước/Trang N/M/Sau

### Badge màu theo business meaning

| Trạng thái | Màu badge |
|---|---|
| PENDING (Chờ duyệt) | amber-50 / amber-300 border / amber-700 text |
| ACCEPTED (Đã xác nhận) | emerald-50 / emerald-200 border / emerald-700 text |
| REJECTED (Đã từ chối) | rose-50 / rose-200 border / rose-700 text |
| SUPERSEDED (Đã thay thế) | slate-100 / slate-200 border / slate-600 text |
| Có công bố hỗ trợ | cyan-50 / cyan-200 border / cyan-700 text |
| Chỉ bằng chứng tên | slate-100 / slate-200 border / slate-600 text |
| Có nhiều ứng viên (mơ hồ) | amber-50 / amber-300 border / amber-700 text |
| Không có ứng viên khác | slate-100 / slate-200 border / slate-600 text |
| Dùng chung (shared Scopus author) | rose-50 / rose-200 border / rose-700 text |

### Kết quả build R2

```
✓ tsc --noEmit   →  0 errors
✓ vite build     →  built in 3.38s, 1485 modules
```

### Smoke test R2

| Kiểm tra | Kết quả |
|---|---|
| `/reviews` hiển thị bảng Tailwind (không còn AntD Table) | ✅ |
| Header row: `bg-slate-50/70`, font-semibold, whitespace-nowrap | ✅ |
| Data rows: `hover:bg-slate-50/50`, `divide-slate-100` | ✅ |
| PENDING badge: amber pill rounded-full | ✅ |
| Evidence badge: cyan/slate pill | ✅ |
| Ambiguity badge: amber/slate/rose pill | ✅ |
| "Xem chi tiết" button: h-7, border, eye icon, hover #3A5FC3 | ✅ |
| Footer: `bg-slate-50/50`, page size select, Trước/Sau nav | ✅ |
| 40 PENDING records, 20/page, 2 pages total | ✅ |
| Double-click row mở modal chi tiết | ✅ |
| ACCEPT/REJECT modals vẫn hoạt động | ✅ |
| TypeScript PASS | ✅ |
| Build PASS | ✅ |

## Tiêu chí PASS (Task 20A-R2)

- [x] Bảng `/reviews` nhìn thống nhất rõ rệt với bảng `/imports`
- [x] Không còn AntD `Table` component trong render chính
- [x] Status badges dạng pill rounded-full với màu semantic (amber/emerald/rose/slate)
- [x] Action button matching Imports style (h-7, shadow-2xs, active:scale, eye icon)
- [x] Pagination footer matching Imports style (slate-50/50 bg, page size select, nav buttons)
- [x] TypeScript typecheck PASS (0 errors)
- [x] Vite build PASS
- [x] ACCEPT/REJECT logic, RBAC, API, database không thay đổi
- [x] Không sửa `/imports`, `/publications`, `/lecturers`, các trang tham chiếu
