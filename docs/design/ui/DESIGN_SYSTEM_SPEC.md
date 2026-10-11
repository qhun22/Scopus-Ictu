# Design System Specification — Scopus–ICTU

**Phiên bản:** Task 20B · 10/10/2026  
**Nguồn sự thật:** mã React/Tailwind `nhánh main@530bf0f` + chỉnh sửa Task 20A/R2 (chưa commit)  
**Trạng thái:** IMPLEMENTED (phản ánh giao diện đang chạy thật)

---

## 1. Công nghệ stack

| Thành phần | Phiên bản | Ghi chú |
|---|---|---|
| React | 18 | + Vite 5 |
| Tailwind CSS | 3.4.19 | `theme.extend` rỗng; custom classes qua arbitrary values |
| Ant Design | 5.x | Dùng trong: modal chi tiết /reviews, hai dialog ACCEPT/REJECT, một số form /lecturers |
| Font chính | Saira (Google Fonts) | weight 400/500/600/700 được tải; 900 (Black) không được tải → synth |
| Font mono | Roboto Mono | weight 400 |

---

## 2. Color tokens (nguồn: `tokens.json`)

### 2.1 Primitives (Collection: "Primitives · Tailwind 3.4")

| Tên token | Hex | Nguồn Tailwind |
|---|---|---|
| brand/600 | #3A5FC3 | custom |
| brand/700 | #2F4EA6 | custom |
| brand/50 | #EBEFF9 | custom |
| base/white | #FFFFFF | — |
| base/page | #F4F6FB | custom |
| base/login | #EEF2F7 | custom |
| base/ink | #172033 | custom |
| slate/50 | #F8FAFC | slate-50 |
| slate/100 | #F1F5F9 | slate-100 |
| slate/200 | #E2E8F0 | slate-200 |
| slate/300 | #CBD5E1 | slate-300 |
| slate/400 | #94A3B8 | slate-400 |
| slate/500 | #64748B | slate-500 |
| slate/600 | #475569 | slate-600 |
| slate/700 | #334155 | slate-700 |
| slate/800 | #1E293B | slate-800 |
| slate/900 | #0F172A | slate-900 |
| emerald/50 | #ECFDF5 | emerald-50 |
| emerald/200 | #A7F3D0 | emerald-200 |
| emerald/600 | #059669 | emerald-600 |
| emerald/700 | #047857 | emerald-700 |
| amber/50 | #FFFBEB | amber-50 |
| amber/200 | #FDE68A | amber-200 |
| amber/300 | #FCD34D | amber-300 |
| amber/600 | #D97706 | amber-600 |
| amber/700 | #B45309 | amber-700 |
| rose/50 | #FFF1F2 | rose-50 |
| rose/200 | #FECDD3 | rose-200 |
| rose/600 | #E11D48 | rose-600 |
| rose/700 | #BE123C | rose-700 |
| cyan/50 | #ECFEFF | cyan-50 |
| cyan/200 | #A5F3FC | cyan-200 |
| cyan/700 | #0E7490 | cyan-700 |
| indigo/50 | #EEF2FF | indigo-50 |
| indigo/200 | #C7D2FE | indigo-200 |
| indigo/700 | #4338CA | indigo-700 |
| violet/50 | #F5F3FF | violet-50 |
| violet/200 | #DDD6FE | violet-200 |
| violet/700 | #6D28D9 | violet-700 |
| blue/50 | #EFF6FF | blue-50 |
| blue/200 | #BFDBFE | blue-200 |
| teal/600 | #0D9488 | teal-600 |

### 2.2 Semantic colors (Collection: "Scopus–ICTU / Color · Semantic")

| Tên semantic | Alias (primitive) | Scopes |
|---|---|---|
| color/brand/primary | brand/600 | SHAPE_FILL, FRAME_FILL, TEXT_FILL, STROKE_COLOR |
| color/brand/hover | brand/700 | SHAPE_FILL, FRAME_FILL, TEXT_FILL |
| color/brand/subtle | brand/50 | SHAPE_FILL, FRAME_FILL |
| color/bg/page | base/page | FRAME_FILL |
| color/bg/surface | base/white | FRAME_FILL, SHAPE_FILL |
| color/bg/subtle | slate/50 | FRAME_FILL, SHAPE_FILL |
| color/bg/muted | slate/100 | FRAME_FILL, SHAPE_FILL |
| color/bg/login | base/login | FRAME_FILL |
| color/border/default | slate/200 | STROKE_COLOR |
| color/border/subtle | slate/100 | STROKE_COLOR |
| color/border/strong | slate/300 | STROKE_COLOR |
| color/text/primary | base/ink | TEXT_FILL |
| color/text/body | slate/700 | TEXT_FILL |
| color/text/secondary | slate/500 | TEXT_FILL |
| color/text/muted | slate/400 | TEXT_FILL |
| color/text/inverse | base/white | TEXT_FILL |
| color/icon/default | slate/500 | SHAPE_FILL |
| color/status/success/bg | emerald/50 | FRAME_FILL, SHAPE_FILL |
| color/status/success/border | emerald/200 | STROKE_COLOR |
| color/status/success/text | emerald/700 | TEXT_FILL |
| color/status/warning/bg | amber/50 | FRAME_FILL, SHAPE_FILL |
| color/status/warning/border | amber/200 | STROKE_COLOR |
| color/status/warning/text | amber/700 | TEXT_FILL |
| color/status/danger/bg | rose/50 | FRAME_FILL, SHAPE_FILL |
| color/status/danger/border | rose/200 | STROKE_COLOR |
| color/status/danger/text | rose/700 | TEXT_FILL |
| color/status/danger/solid | rose/600 | SHAPE_FILL, FRAME_FILL |
| color/status/info/bg | indigo/50 | FRAME_FILL, SHAPE_FILL |
| color/status/info/border | indigo/200 | STROKE_COLOR |
| color/status/info/text | indigo/700 | TEXT_FILL |
| color/status/neutral/bg | slate/100 | FRAME_FILL, SHAPE_FILL |
| color/status/neutral/border | slate/200 | STROKE_COLOR |
| color/status/neutral/text | slate/600 | TEXT_FILL |
| color/status/accent/bg | cyan/50 | FRAME_FILL, SHAPE_FILL |
| color/status/accent/text | cyan/700 | TEXT_FILL |
| color/status/violet/bg | violet/50 | FRAME_FILL, SHAPE_FILL |
| color/status/violet/text | violet/700 | TEXT_FILL |
| color/status/blue/bg | blue/50 | FRAME_FILL, SHAPE_FILL |
| color/status/blue/text | blue/200 | TEXT_FILL |
| color/accent/teal | teal/600 | SHAPE_FILL, TEXT_FILL |
| color/proposed/flag | amber/300 | SHAPE_FILL |

---

## 3. Spacing & Radius (Collection: "Scopus–ICTU / Spacing · Radius · Size · Layout")

### 3.1 Spacing (thang Tailwind ×4px)

| Tên | px | CSS var |
|---|---|---|
| space/0-5 | 2px | var(--space-0-5) |
| space/1 | 4px | var(--space-1) |
| space/1-5 | 6px | var(--space-1-5) |
| space/2 | 8px | var(--space-2) |
| space/2-5 | 10px | var(--space-2-5) |
| space/3 | 12px | var(--space-3) |
| space/3-5 | 14px | var(--space-3-5) |
| space/4 | 16px | var(--space-4) |
| space/5 | 20px | var(--space-5) |
| space/6 | 24px | var(--space-6) |
| space/8 | 32px | var(--space-8) |
| space/12 | 48px | var(--space-12) |

### 3.2 Radius

| Tên | px | CSS var |
|---|---|---|
| radius/sm | 4px | var(--radius-sm) |
| radius/md | 6px | var(--radius-md) |
| radius/lg | 8px | var(--radius-lg) |
| radius/xl | 12px | var(--radius-xl) |
| radius/2xl | 16px | var(--radius-2xl) |
| radius/full | 9999px | var(--radius-full) |

### 3.3 Control heights

| Tên | px | |
|---|---|---|
| size/control/2xs | 24px | badge, chip |
| size/control/xs | 28px | table action button |
| size/control/sm | 32px | small button |
| size/control/md | 36px | default input |
| size/control/lg | 40px | topbar button, lang switch |
| size/control/xl | 48px | login submit button |

### 3.4 Layout

| Tên | px | Nguồn |
|---|---|---|
| layout/sidebar | 256px | w-64 (expanded) |
| layout/sidebar/collapsed | 80px | w-20 |
| layout/header | 64px | h-16 |
| layout/content-padding/lg | 24px | lg:p-6 |
| layout/content-padding/sm | 20px | sm:p-5 |
| layout/content-padding/base | 14px | p-3.5 |

---

## 4. Typography (Text styles — Saira + Roboto Mono)

| Tên style | Font | Weight | Size/Leading | Dùng cho |
|---|---|---|---|---|
| Display/KPI | Saira Black | 900 (synth) | 24/32 | Số đếm KPI trên Dashboard |
| Heading/H1 Page | Saira Bold | 700 | 20/28 | Tiêu đề trang |
| Heading/H2 Section | Saira SemiBold | 600 | 16/24 | Tiêu đề vùng nội dung |
| Heading/H3 Card | Saira SemiBold | 600 | 14/20 | Tiêu đề card |
| Body/Base | Saira Regular | 400 | 14/20 | Nội dung chính |
| Body/Small | Saira Regular | 400 | 13/18 | Phụ |
| Body/Caption | Saira Regular | 400 | 12/16 | Chú thích, metadata |
| Label/Strong | Saira SemiBold | 600 | 14/20 | Nhãn nổi bật |
| Label/Field | Saira Medium | 500 | 13/18 | Nhãn trường form |
| Label/Table Header | Saira SemiBold | 600 | 11/14 | Header bảng (xs uppercase) |
| Badge/Default | Saira Bold | 700 | 11/14 | Badge, chip trạng thái |
| Micro/Tiny | Saira Regular | 400 | 10/14 | Footer bảng, chú thích nhỏ |
| Nav/Item | Saira Medium | 500 | 14/20 | Menu điều hướng |
| Nav/Brand | Saira Bold | 700 | 14/20 | Brand name sidebar |
| Nav/SubBrand | Saira Regular | 400 | 11/14 | Sub-brand sidebar |
| Button/Default | Saira SemiBold | 600 | 14/20 | Nút chính |
| Mono/ID | Roboto Mono Regular | 400 | 10/14 | EID, mã token |
| Toast/Message | Saira Medium | 500 | 13/18 | Thông báo toast |
| Input/Placeholder | Saira Regular | 400 | 14/20 | Placeholder input |

---

## 5. Effect styles

| Tên | Mô tả | Dùng cho |
|---|---|---|
| Elevation/0 Card | Không có bóng + viền slate/200 | Card phẳng (mặc định; shadow-xs không hoạt động TW 3.4) |
| Elevation/1 sm | drop-shadow(0 1px 2px rgba(0,0,0,.06)) | Sidebar, topbar |
| Elevation/3 xl | drop-shadow(0 10px 15px rgba(0,0,0,.08)) | Dropdown menu |
| Elevation/4 2xl | drop-shadow(0 20px 25px rgba(0,0,0,.10)) | Modal |
| Elevation/Login card | drop-shadow(0 20px 60px rgba(59,130,246,.15)) | Card đăng nhập |
| Focus/Ring brand 20% | outline 2px solid brand/600 20% opacity | Trạng thái focus |

---

## 6. Các badge nghiệp vụ

| Trạng thái | Nền | Viền | Chữ | Tailwind class |
|---|---|---|---|---|
| PENDING | amber/50 | amber/200 | amber/700 | bg-amber-50 border-amber-200 text-amber-700 |
| ACCEPTED | emerald/50 | emerald/200 | emerald/700 | bg-emerald-50 border-emerald-200 text-emerald-700 |
| REJECTED | rose/50 | rose/200 | rose/700 | bg-rose-50 border-rose-200 text-rose-700 |
| SUPERSEDED | slate/100 | slate/200 | slate/600 | bg-slate-100 border-slate-200 text-slate-600 |
| Có công bố | cyan/50 | cyan/200 | cyan/700 | bg-cyan-50 border-cyan-200 text-cyan-700 |
| Dùng chung | rose/50 | rose/200 | rose/700 | bg-rose-50 border-rose-200 text-rose-700 |
| ADMIN | blue/50 | blue/200 | brand/600 | bg-blue-50 border-blue-200 text-[#3A5FC3] |
| REVIEWER | amber/50 | amber/200 | amber/700 | bg-amber-50 border-amber-200 text-amber-700 |
| LECTURER | emerald/50 | emerald/200 | emerald/700 | bg-emerald-50 border-emerald-200 text-emerald-700 |

---

## 7. Các giới hạn đã biết (GAP / kỹ thuật)

| Mã | Mô tả | File ảnh hưởng |
|---|---|---|
| G-01 | shadow-xs / shadow-2xs / backdrop-blur-xs không sinh CSS ở Tailwind 3.4.19 → card phẳng | tailwind.config.js |
| G-02 | font-black (900) không được tải — chỉ 400–700 → synth từ 700 | index.html / global CSS |
| G-11 | Saira Black (weight 900) synthesized — không phải weight thật | — |
| GAP-01 | DOI field: nhiều công bố giữ nguyên văn "DOI:…" thay vì chỉ số DOI thuần | publications service |
| GAP-02 | source_title hiển thị "Scopus" cho mọi dòng trong bảng /publications | PublicationService |

---

*Xem thêm: `DESIGN_TO_CODE_GAP` trong TASK20B_FIGMA_REPORT.md.*
