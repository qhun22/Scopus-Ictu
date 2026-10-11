# Figma Design Handoff — Scopus–ICTU · Task 20B

**File Figma:** `JL6qaElA0zehVEVhURJiIC`  
**URL:** https://www.figma.com/design/JL6qaElA0zehVEVhURJiIC  
**Ngày:** 10/10/2026  
**Trạng thái:** PARTIAL — rate limit MCP Starter; foundations ✅; component/screen frames chưa tạo đủ

---

## Cấu trúc file (3 page — giới hạn gói Starter)

| Page | Page ID | Nội dung |
|---|---|---|
| 00–02 · Cover · Design Foundations · Components | 8:2 | Section 00 Cover, 01 Foundations, 02 Components |
| 03–06 · Screens · User Flows & Prototype | 8:3 | Section 03 Core Screens, 04 Review & Governance, 05 Proposed, 06 Flows |
| 07 · Design Handoff + 99 LEGACY v0 | 0:1 | Section 07 Handoff, 99 Legacy (9 frame v0) |

> Figma trả lỗi "The Starter plan only comes with 3 pages" khi tạo page thứ 4. Cấu trúc Section thay thế page.

---

## Variable Collections (121 biến)

| Collection | ID | Mode | Số biến |
|---|---|---|---|
| Scopus–ICTU / Color · Semantic | VariableCollectionId:3:2 | Light | 43 |
| Primitives · Tailwind 3.4 | VariableCollectionId:11:2 | Value | 42 |
| Scopus–ICTU / Spacing · Radius · Size · Layout | VariableCollectionId:11:79 | Value | 36 |

---

## Text Styles (19)

| Tên | Font | Size |
|---|---|---|
| Display/KPI | Saira Black | 24/32 |
| Heading/H1 Page | Saira Bold | 20/28 |
| Heading/H2 Section | Saira SemiBold | 16/24 |
| Heading/H3 Card | Saira SemiBold | 14/20 |
| Body/Base | Saira Regular | 14/20 |
| Body/Small | Saira Regular | 13/18 |
| Body/Caption | Saira Regular | 12/16 |
| Label/Strong | Saira SemiBold | 14/20 |
| Label/Field | Saira Medium | 13/18 |
| Label/Table Header | Saira SemiBold | 11/14 |
| Badge/Default | Saira Bold | 11/14 |
| Micro/Tiny | Saira Regular | 10/14 |
| Nav/Item | Saira Medium | 14/20 |
| Nav/Brand | Saira Bold | 14/20 |
| Nav/SubBrand | Saira Regular | 11/14 |
| Button/Default | Saira SemiBold | 14/20 |
| Mono/ID | Roboto Mono Regular | 10/14 |
| Toast/Message | Saira Medium | 13/18 |
| Input/Placeholder | Saira Regular | 14/20 |

---

## Effect Styles (6)

| Tên | Style ID | Mô tả |
|---|---|---|
| Elevation/0 Card | S:2d57d852... | Phẳng (card mặc định) |
| Elevation/1 sm | S:a59d6515... | drop-shadow nhỏ |
| Elevation/3 xl | S:c0135fc5... | Dropdown menu |
| Elevation/4 2xl | S:0f13c5b8... | Modal |
| Elevation/Login card | S:6543ff1a... | Login card blue glow |
| Focus/Ring brand 20% | S:9f9618fc... | Focus outline |

---

## Legacy v0 — 9 frame giữ nguyên (Page 3)

| Frame | Node ID | Tên | Kích thước |
|---|---|---|---|
| FG-01 | 4:2 | S01 Login | 1280×820 |
| FG-02 | 4:22 | S03 Dashboard | 1280×820 |
| FG-03 | 4:85 | S04 Imports | 1280×820 |
| FG-04 | 4:138 | S09 Publications | 1280×820 |
| FG-05 | 4:205 | S10 Pub detail | 1280×820 |
| FG-06 | 4:260 | S12 Reviews | 1280×820 |
| FG-07 | 4:322 | S13 Candidate modal | 1280×820 |
| FG-08 | 4:366 | S14 Decision modal | 1280×820 |
| FG-09 | 4:409 | S20 Proposed | 1280×820 |

> 9 frame được đổi tên sang: biến bind bằng các biến mới (renamed). Màu có thể bị nhạt do legacy vars được đổi tên alias.

---

## Design-to-Code Gap (tóm tắt — chi tiết trong TASK20B_FIGMA_REPORT.md)

| GAP | Severity | Mô tả | File cần sửa | Công sức ước tính |
|---|---|---|---|---|
| GAP-a | HIGH | Cột "Thao tác" bị cắt tại /imports 1440px | pages/Imports/index.tsx | 1–2h |
| GAP-b | MEDIUM | Modal /reviews dùng AntD: màu primary sai, font không Saira | pages/ApprovalQueue/index.tsx | 4–8h |
| GAP-c | MEDIUM | Bộ đếm textarea REJECT chồng nút footer | pages/ApprovalQueue/index.tsx | 1h |
| GAP-d | LOW | Nút "Chi tiết" xuống dòng /publications 1440 | pages/Publications/index.tsx | 1h |
| GAP-e | LOW | Header /publications/:eid hiển thị "Hệ thống" | pages/Publications/Detail.tsx | 0.5h |
| GAP-f | LOW | shadow-xs/2xs không hoạt động TW 3.4 | tailwind.config.js | 0.5h |
| GAP-g | LOW | font-black 900 không tải | index.html / CSS | 0.5h |
| GAP-h | LOW | LECTURER pages container khác | pages/Lecturer/*.tsx | 2h |
| GAP-i | LOW | /audit-logs filter xuống dòng; placeholder bị cắt | pages/AuditLogs/index.tsx | 1h |
| GAP-j | LOW | /review-history hiển thị mã thay vì nhãn tiếng Việt | pages/ReviewHistory/index.tsx | 1h |

---

## Việc còn lại trước 14/10

| Ưu tiên | Việc | Ghi chú |
|---|---|---|
| P0 | Chờ rate limit Figma MCP reset (24–48h) | Sau đó tiếp Phase 2 components + Phase 3 screens |
| P0 | Tạo frame components (Phase 2.c) | Buttons, Badges, Inputs, Sidebar, Topbar, Table, Modal... |
| P0 | Tạo frame màn hình (Phase 3) | 6 nhóm PI 2.3 + 4 trang ưu tiên |
| P1 | Visual QA (PIL so sánh) | Sau khi có frame màn hình |
| P1 | Prototype reactions (Page 2) | Flow 1–5 |
| P1 | Section 07 Handoff (Page 3) | Bảng mapping |
| P2 | S20 PROPOSED frame | Page 2 Section 05 |
| P2 | Responsive frames (1366×768, mobile 390×844) | P2 |
| P2 | Commit tài liệu docs/design/ui/ | Sau khi người dùng xem xét |

---

## Kế hoạch sau rate limit

```
use_figma lần 1 (Phase 2.c.1): Icon components từ Heroicons SVG
use_figma lần 2 (Phase 2.c.2): Buttons + Badges
use_figma lần 3 (Phase 2.c.3): Inputs + Fields
use_figma lần 4 (Phase 2.c.4): Sidebar + Topbar + PageHeader
use_figma lần 5 (Phase 2.c.5): Table + Pagination + Tabs + FilterBar
use_figma lần 6 (Phase 2.c.6): Modal + Dialog + Toast + Empty/Loading/Error + Dropzone
use_figma lần 7 (Phase 2.c.7): StatCard + Card + AppShell template
use_figma lần 8 (Phase 3.a): Màn hình Core — Page 2 (S01/S05/S04/S06/S02/S03/S19/S21)
use_figma lần 9 (Phase 3.b): Màn hình Review — Page 2 (S09/S10/S11/S12/S13/S14/S15)
use_figma lần 10 (Phase 3.c): LECTURER + S20 PROPOSED + Flows
```
