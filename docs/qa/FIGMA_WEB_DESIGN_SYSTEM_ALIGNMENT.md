# FIGMA ↔ WEB DESIGN SYSTEM ALIGNMENT

**Ngày kiểm toán:** 2026-10-14  
**Phiên bản Figma:** `yctOa75eATXHnTQmesJy5A` (page "Nền tảng thiết kế")  
**Kết quả tổng thể:** ✅ ALIGNED

---

## 1. Nguồn Figma

| Mục | Giá trị |
|-----|---------|
| File key | `yctOa75eATXHnTQmesJy5A` |
| Page hiển thị | "Nền tảng thiết kế" (design tokens) |
| Công cụ đọc | Figma MCP (`mcp__a93d5e4a-3cba-4c77-9b35-ecdc3728505b`) |
| Tài khoản xác thực | dtc235200899@ictu.edu.vn |

---

## 2. Màu sắc thương hiệu — Figma → Code

| Token Figma | Hex | Ứng dụng trong code |
|-------------|-----|---------------------|
| Brand Primary | `#3A5FC3` | `BUTTON_PRIMARY`, Sidebar active, border, text accent |
| Brand Hover | `#2F4EA6` | Hover state của button primary |
| Brand Light BG | `#EBEFF9` | `BUTTON_SECONDARY` bg, WorkflowBanner bg, Sidebar group heading bg |
| Page BG | `#F4F6FB` | Body background (không thay đổi) |
| Status Success BG | `#ECFDF5` | WorkflowBanner màu xanh (matching→reviews) |
| Status Warning BG | `#FFFBEB` | (chưa dùng trong sprint này) |
| Status Danger BG | `#FFF1F2` | (chưa dùng trong sprint này) |
| Danger | `#E50000` | `BUTTON_DANGER` |

### Trước/Sau

| File | Trước | Sau |
|------|-------|-----|
| `buttonStyles.ts` | `#5B45D2` (purple) | `#3A5FC3` (Figma brand blue) |

---

## 3. Button system — `buttonStyles.ts`

```typescript
BUTTON_PRIMARY   = border+bg #3A5FC3, hover #2F4EA6, text white
BUTTON_SECONDARY = border #3A5FC3/30, bg #EBEFF9, text #3A5FC3, hover #dde5f7
BUTTON_DANGER    = border+bg #E50000, hover #C70000, text white
BUTTON_GHOST     = bg transparent, text #3A5FC3, hover bg #EBEFF9 (mới thêm)
```

Tất cả button dùng base class chung: `rounded-lg px-5 py-2 min-h-10 font-bold` — khớp với spec Figma.

---

## 4. Sidebar — thiết kế lại theo nhóm quy trình

### ADMIN navigation groups

| Nhóm | Items |
|------|-------|
| (ungrouped) | Home |
| Quy trình xử lý | Nhập dữ liệu → Chuẩn hóa → Giảng viên → Kiểm duyệt → Lịch sử kiểm duyệt |
| Tra cứu & kết quả | Công bố → Tra cứu tác giả |
| Quản trị | Dashboard → Nhật ký hệ thống → Tác vụ |

### REVIEWER navigation groups

| Nhóm | Items |
|------|-------|
| (ungrouped) | Home |
| Quy trình xử lý | Kiểm duyệt → Lịch sử kiểm duyệt |
| Tra cứu & kết quả | Công bố → Tra cứu tác giả |

### LECTURER navigation groups

| Nhóm | Items |
|------|-------|
| (ungrouped) | Home |
| Tra cứu & kết quả | Công bố → Tra cứu tác giả |
| (ungrouped) | Công bố của tôi → Nhận dạng → Hồ sơ |

### Visual specs

- Group headings: `text-[10px] font-bold uppercase tracking-wider text-slate-400`, bg `#EBEFF9`
- Active item: left pill indicator `bg-[#3A5FC3]`, item bg `bg-[#EBEFF9]`, text `#3A5FC3`
- Collapsed: headings ẩn, thay bằng divider; icons vẫn hiện

---

## 5. Kiểm tra tương thích TypeScript & Build

| Bước | Lệnh | Kết quả |
|------|------|---------|
| TypeScript typecheck | `npx tsc --noEmit` | ✅ 0 errors |
| Production build | `npm run build` | ✅ built in 3.55s |

---

## 6. GAP còn lại

| Mục | Mô tả | Mức độ |
|-----|-------|--------|
| Component pages | Figma chỉ có page "Nền tảng thiết kế" — không có component mockups | Không thể kiểm tra |
| Font weight | Figma dùng `Inter` — web dùng system font stack (không có CDN load) | Low priority |
| Shadow tokens | Figma không định nghĩa shadow tokens rõ — web dùng `shadow-xs` Tailwind | Acceptable |

---

*Tạo tự động bởi kiểm toán Figma↔Web — 2026-10-14*
