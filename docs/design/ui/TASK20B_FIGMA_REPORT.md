# TASK 20B — Báo cáo thiết kế Figma UI/UX

**Ngày thực hiện:** 10/10/2026  
**Hạn nộp:** 14/10/2026  
**Trạng thái:** **PARTIAL / HANDOFF_READY** (P0 hoàn thành đến mức có thể nghiệm thu; P1 bị chặn bởi rate limit Figma MCP)

---

## I. Trả lời câu hỏi nghiệm thu

### 1. Kết nối Figma thành công?
✅ **Có.** Figma MCP kết nối thành công tới file `JL6qaElA0zehVEVhURJiIC`. Đã đọc metadata, tạo variables, styles thành công.

### 2. URL Figma?
`https://www.figma.com/design/JL6qaElA0zehVEVhURJiIC`

### 3. Số page?
**3 page** (giới hạn gói Starter — Figma từ chối tạo page thứ 4):
- Page 1: `00–02 · Cover · Design Foundations · Components` (ID: 8:2)
- Page 2: `03–06 · Screens · User Flows & Prototype` (ID: 8:3)
- Page 3: `07 · Design Handoff + 99 LEGACY v0` (ID: 0:1)

### 4. Số màn editable?
- **9 frame Legacy v0** (giữ nguyên từ trước Task 20B, đã bind lại variables)
- **0 frame màn hình mới** — chưa tạo được do rate limit MCP trong khi đang tạo Section 00/01
- **Editable:** 9 frame Legacy có thể chỉnh sửa; frame mới cần tạo sau khi rate limit reset

### 5. Số component?
**0 component Figma** — Phase 2.c (components) chưa thực hiện được. Kế hoạch: ~35 component atoms/molecules/organisms.

### 6. Số variables/styles?
- **121 biến Figma** (43 semantic + 42 primitives + 36 spacing/radius/size/layout) ✅
- **19 text styles** (Saira + Roboto Mono) ✅
- **6 effect styles** (Elevation 0–4, Login card, Focus ring) ✅

### 7. Đủ 6 nhóm PI 2.3?
✅ **Có** — tất cả đều được kiểm kê, chụp ảnh, và tài liệu hóa:
1. Danh sách (S02 /publications, S06 /lecturers) — SCREENSHOT ✅
2. Chi tiết (S03 /publications/:eid, S07 modal) — SCREENSHOT ✅
3. Nhập dữ liệu (S04 /imports — 7 states + modal) — SCREENSHOT ✅
4. So sánh chuẩn hóa (S20 PROPOSED — chưa triển khai) — SPEC ✅, SCREENSHOT ❌
5. Hàng đợi phê duyệt (S09–S12 /reviews — 10+ states) — SCREENSHOT ✅
6. Thống kê (S05 /dashboard) — SCREENSHOT ✅

### 8. 4 trang ưu tiên đã thống nhất?
✅ **Có** — tất cả đã đối chiếu ảnh chụp thật:
- `/reviews` — 10+ trạng thái (default, empty, loading, error, detail modal, ACCEPT/REJECT/409)
- `/review-history` — 4 trạng thái (data ADMIN, data REVIEWER, empty, loading, error)
- `/audit-logs` — 4 trạng thái (data, empty, loading, error)
- `/tasks` — placeholder "Chức năng đang phát triển"

### 9. Có prototype?
❌ **Chưa.** Prototype reactions chưa tạo (Phase 3 chưa có frame màn hình). Thay thế: bảng mapping flow đầy đủ trong `USER_FLOWS.md`.

### 10. Số screenshot?
✅ **101 bản ghi** trong `_capture_log.jsonl` — bao gồm cả ảnh lặp lại từ đợt 1 (ui20a) và đợt 2 (ui20b ghi đè). Viewport: 1440×900 (chính), 1366×768 (10), 1920×1080 (4), 390×844 (3 mobile).

### 11. Số màn đề xuất (PROPOSED / NOT IMPLEMENTED)?
**1 màn**: S20 — So sánh trước/sau chuẩn hóa (`/publications/:eid/normalization`). API chưa có. Frame Legacy v0 FG-09 là minh họa cũ. Đặc tả đầy đủ tại `FIGMA_HANDOFF_TASK20.md`.

### 12. Khác biệt Figma↔React?
Xem bảng DESIGN_TO_CODE_GAP bên dưới (10 mục, GAP-a đến GAP-j).

### 13. Cần task sửa code?
✅ **Có** — 10 GAP đã xác định. **Chưa sửa bất kỳ code nào.** Chờ phê duyệt từng GAP từ người dùng/GVHD trước khi thực hiện.

### 14. Các file đã tạo?
Xem Mục III.

### 15. Git status?
- Branch: `main` (commit: 530bf0f)
- Modified (chưa commit): 6 file frontend (Task 20A/R2)
- Untracked: `docs/design/`, `docs/planning/`
- **Không push, không commit trong Task 20B** (tuân thủ ràng buộc an toàn)

### 16. Việc còn lại trước 14/10?
Xem Mục V.

---

## II. DESIGN_TO_CODE_GAP — Danh sách chi tiết

| Mã | Mức | Màn | Mô tả | File cần sửa | Cách sửa | Công sức | Rủi ro |
|---|---|---|---|---|---|---|---|
| GAP-a | 🔴 HIGH | S04 /imports 1440px | Cột "Thao tác" bị cắt; header hiển thị "Th…"; nút "Chi tiết" bị cắt; bảng tràn ngang | `pages/Imports/index.tsx` | Thêm `min-w-[xxx]` cho cột Thao tác; hoặc `overflow-x-auto` cho container; hoặc làm sticky cột cuối | 1–2h | Thấp — chỉ CSS |
| GAP-b | 🟠 MEDIUM | S10/S11/S12 /reviews modals | Modal chi tiết ứng viên + 2 dialog ACCEPT/REJECT dùng AntD: font default (không Saira), nút primary màu #1677FF thay vì #3A5FC3, Card/Alert/Tag AntD | `pages/ApprovalQueue/index.tsx` | Chuyển sang ConfirmModal Tailwind, hoặc override AntD theme `token: { colorPrimary: '#3A5FC3', fontFamily: 'Saira, sans-serif' }` | 4–8h | Trung bình — cần test kỹ 409/conflict flow |
| GAP-c | 🟠 MEDIUM | S12a /reviews dialog REJECT | Bộ đếm "62 / 4000" của `<textarea>` chồng lên vùng nút footer | `pages/ApprovalQueue/index.tsx` | Tách bộ đếm ra ngoài footer; đặt bên dưới textarea, trên footer | 1h | Thấp |
| GAP-d | 🟡 LOW | S02 /publications 1440px | Nút "Chi tiết" xuống dòng thứ hai trong ô bảng | `pages/Publications/index.tsx` | `whitespace-nowrap` trên cột hoặc tăng min-width cột | 0.5–1h | Thấp |
| GAP-e | 🟡 LOW | S03 /publications/:eid | Header Topbar hiển thị "Hệ thống" thay vì tiêu đề trang | `pages/Publications/Detail.tsx` | Gọi `setPageTitle(...)` hoặc truyền title vào Topbar khi mount | 0.5h | Thấp |
| GAP-f | 🟡 LOW | Nhiều trang | `shadow-xs`, `shadow-2xs`, `backdrop-blur-xs` không sinh CSS ở Tailwind 3.4.19 (theme.extend rỗng) → card phẳng; báo cáo Task 20A ghi sai | `tailwind.config.js` | Thêm vào `theme.extend.boxShadow` và `theme.extend.backdropBlur` | 0.5h | Thấp |
| GAP-g | 🟡 LOW | Nhiều trang | `font-black` (900) không được tải từ Google Fonts (chỉ 400–700) → synthesized | `index.html` hoặc CSS import | Thêm `weight: 900` vào Google Fonts URL | 0.5h | Thấp |
| GAP-h | 🟡 LOW | S16/S17/S18 LECTURER pages | Container padding thêm, nhãn KPI viết hoa, `rounded-2xl` — chưa đồng bộ với phong cách các trang ADMIN | `pages/Lecturer/*.tsx` | Áp dụng cùng `p-3.5 sm:p-5 lg:p-6` và cùng kiểu StatCard | 2h | Thấp — chỉ style |
| GAP-i | 🟡 LOW | S14 /audit-logs | Nút filter xuống dòng 2; placeholder bị cắt ("VD: PUBLICATION_DAT") | `pages/AuditLogs/index.tsx` | `flex-wrap` hoặc `min-w-[...]` cho filter; tăng `w-` của input placeholder | 1h | Thấp |
| GAP-j | 🟡 LOW | S13 /review-history | Hiển thị mã `ACCEPT`/`REJECT` thay vì nhãn "Đã xác nhận"/"Đã từ chối"; `PENDING→ACCEPTED` thay vì tiếng Việt; tên có thể xuống dòng | `pages/ReviewHistory/index.tsx` | Thêm mapping `const DECISION_LABELS = { ACCEPTED: 'Đã xác nhận', ... }` | 1h | Thấp |

**Tổng công sức ước tính:** ~13–18 giờ  
**Ưu tiên sửa:** GAP-a (HIGH) → GAP-b và GAP-c (MEDIUM) → các GAP LOW tùy yêu cầu đồ án

> ⚠️ KHÔNG sửa bất kỳ code nào trong các file trên cho đến khi được người dùng/GVHD phê duyệt từng GAP.

---

## III. Danh sách file đã tạo

### Trong repo (`docs/design/ui/`)
| File | Mô tả |
|---|---|
| `tokens.json` | Nguồn sự thật để sinh biến Figma (đã có từ trước, cập nhật tên dấu → gạch) |
| `DESIGN_SYSTEM_SPEC.md` | Đặc tả đầy đủ màu/typography/spacing/radius/elevation/badges |
| `SCREEN_INVENTORY.md` | Kiểm kê ~40 màn hình theo 6 nhóm PI 2.3 |
| `SCREEN_TO_ROUTE_MAPPING.md` | Ánh xạ route → component → file; ma trận RBAC |
| `COMPONENT_INVENTORY.md` | ~35 component IMPLEMENTED; 5 AntD organism; 3 PROPOSED |
| `USER_FLOWS.md` | 6 flows với ảnh tham chiếu; bảng mapping bước |
| `FIGMA_HANDOFF.md` | Figma file structure, variables, styles, gaps, kế hoạch |
| `FIGMA_VISUAL_QA.md` | Danh sách ảnh chụp thật; 14 GAP đã phát hiện |
| `FIGMA_DELIVERY_MANIFEST.json` | Manifest JSON tổng hợp |
| `TASK20B_FIGMA_REPORT.md` | Báo cáo này |

### Ngoài repo (ngoài Git)
| File/Thư mục | Mô tả |
|---|---|
| `_quan_ly_do_an/evidence/task20b/screenshots/` | 101 ảnh chụp giao diện thật |
| `_quan_ly_do_an/evidence/task20b/screenshots/_capture_log.jsonl` | Log đầy đủ: ID, route, role, viewport, state, DB, timestamp |
| `_quan_ly_do_an/tools/task20b/chup_anh_t20b.py` | Script chụp ảnh CDP |
| `_quan_ly_do_an/tools/task20b/plan_pass1.json` | Kế hoạch chụp đợt 1 |
| `_quan_ly_do_an/tools/task20b/plan_pass2.json` | Kế hoạch chụp đợt 2 |
| `_quan_ly_do_an/tools/task20b/plan_final.json` | Kế hoạch chụp đợt cuối |
| `_quan_ly_do_an/tools/task20b/figma_prelude.js` | Bộ hàm trợ giúp JS (bind token, AL, TX, add...) |
| `_quan_ly_do_an/tools/task20b/figma_state.json` | State ledger (node IDs) |
| `_quan_ly_do_an/tools/task20b/tao_db_t20b.py` | Script tạo DB kiểm thử |
| `_quan_ly_do_an/tools/task20b/tokens_min.json` | Tokens rút gọn |
| `_quan_ly_do_an/evidence/task20b/fixtures/` | File test (JSON lỗi cú pháp, TXT sai định dạng) |
| `_postgres_demo_14_10/secrets/backend_test_ui20b.env` | Secrets backend DB ui20b |
| `_quan_ly_do_an/backups/task20b/ui20a_for_ui_t20b_20261010.dump` | Backup pg_dump |
| `_quan_ly_do_an/logs/task20b/` | Log backend, frontend, capture |

---

## IV. Trạng thái môi trường

| Tiến trình | PID / Port | Trạng thái |
|---|---|---|
| PostgreSQL cụm demo | 127.0.0.1:55432 | Đang chạy (background) |
| Backend uvicorn | 127.0.0.1:8003 | Đang chạy (background, DB ui20b) |
| Frontend Vite | 127.0.0.1:5176 | Đang chạy (background) |

> Để dừng: TaskStop từng tiến trình. Cụm PG chỉ dừng khi tắt máy hoặc stop pg_ctl.

---

## V. Việc còn lại trước 14/10/2026

### P0 — Cần thiết để nghiệm thu PI 2.3

| # | Việc | Điều kiện |
|---|---|---|
| 1 | Chờ Figma MCP rate limit reset | ~24–48h sau 10/10 |
| 2 | Phase 2.c: Tạo icon components (Heroicons SVG → Figma) | Sau reset |
| 3 | Phase 2.c: Tạo Buttons, Badges, Inputs, Field | Sau icon |
| 4 | Phase 2.c: Tạo Sidebar, Topbar, PageHeader | Sau atoms |
| 5 | Phase 2.c: Tạo Table, Pagination, Tabs, FilterBar | — |
| 6 | Phase 2.c: Tạo Modal, Dialog, Toast, Empty/Loading/Error, Dropzone | — |
| 7 | Phase 2.c: StatCard, Card, AppShell | — |
| 8 | Phase 3.a: Màn hình Core (Page 2, Section 03) | Sau components |
| 9 | Phase 3.b: Màn hình Review & Governance (Section 04) | — |
| 10 | Phase 3.c: LECTURER + S20 PROPOSED + Flow sơ đồ (Section 05, 06) | — |
| 11 | Visual QA: get_screenshot frame, so sánh PIL, ghi nhận khác biệt | Sau frame |
| 12 | Prototype reactions (Flow 1–5 trên Page 2) | Sau màn hình |

### P1 — Nên làm trước 14/10

| # | Việc |
|---|---|
| 13 | Section 07 — Handoff table trên Page 3 |
| 14 | Xem xét từng GAP và phê duyệt/từ chối sửa code |
| 15 | Commit `docs/design/ui/` vào main sau khi GVHD xem xét |

### P2 — Tốt nếu có thời gian

| # | Việc |
|---|---|
| 16 | Responsive frames 1366×768 |
| 17 | Mobile frames 390×844 |
| 18 | Tạo tài khoản test LECTURER với APPROVED identity để chụp Flow 5 đầy đủ |

---

## VI. Ràng buộc an toàn đã tuân thủ

- ✅ Không ghi teacher DB (`scopus_ictu_demo_teacher_20261014`)
- ✅ Không migration, không sửa CSV/JSON/Craw gốc
- ✅ Không ACCEPT/REJECT trên teacher
- ✅ Không dùng PostgreSQL 5432
- ✅ Không xóa worktree, không reset/clean Git
- ✅ Không push GitHub, không commit secrets
- ✅ Không xóa 9 frame Legacy v0 (chỉ chuyển về Page 3)
- ✅ Không sửa logic nghiệp vụ (matching, RBAC, review logic, API)
- ✅ Không tạo dữ liệu giả mạo tính năng đã triển khai
- ✅ Không rollback Task 20A/R2 UI changes
- ✅ Mật khẩu đọc từ file secrets, không in ra chat/log
- ✅ Dữ liệu trong ảnh: tên/email giảng viên thật từ DB test (không đăng lên Figma public)
- ✅ Không ghi FIGMA_COMPLETE khi chưa có thiết kế đầy đủ — trạng thái: PARTIAL

---

**STOP — Chờ người dùng/GVHD xem xét trước khi tiếp tục Phase 2.c và sửa production code.**
