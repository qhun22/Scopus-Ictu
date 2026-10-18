# Design System R3 / R4 — Controlled Final UI Rollout — PROMPT 11 (17/10/2026)

- **Release:** `v1.0.0-rc.1` vẫn **HOLD**.
- **Phạm vi đã làm:**
  - **R3a**: Lecturers, Users, ReviewHistory, AuditLogs, các hộp xác nhận.
  - **R3b**: Imports, Normalization.
  - Quy tắc đếm ứng viên mơ hồ (D-2, file riêng).
- **R4:** chỉ trình bày **Component Migration Matrix**, **chưa triển khai**; chờ duyệt riêng (§7).
- **Không làm:** stage, commit, tag, push; migration; ghi DB A; xóa DB restore; đụng credential, PostgreSQL 5432 hay firewall.

**Nhãn**

| Nhãn | Nghĩa |
|---|---|
| **CODE** | đã sửa code |
| **BUILD** | `tsc` + build PASS |
| **UI** | đã kiểm trình duyệt |
| **NOT TESTED** | chưa kiểm |
| **LIMITATION** | chấp nhận là hạn chế |
| **FV** | Figma-verified |
| **PR** | PROPOSED |

---

## 0. Baseline (VERIFIED)

| Mục | Kết quả |
|---|---|
| HEAD / branch | `237f7bc` / `main` |
| Worktree đầu phiên | sha256 của `git diff` = `6abb7fac…`, **trùng** patch cuối PROMPT 10 |
| 4 file RC | `fb176d6`, `853c832`, `3b03317`, `0c34a85`, không đổi |
| Patch | trước: `_postgres_demo_14_10/scratch/p11/baseline_worktree_p11.patch`; sau: `worktree_after_p11.patch` (sha256 `7ab42548…`) |
| DB A | fingerprint trước = sau = snapshot nguồn (**IDENTICAL**) |
| DB restore | = cuối PROMPT 10 (**IDENTICAL**), không ghi |

---

## 1. Figma – Implementation Matrix sau R3

Đã truy cập lại Figma `yctOa75eATXHnTQmesJy5A` trong phiên. Metadata `5:2` (Buttons) và `9:41` (Data Table) vẫn đúng như đã xác minh ở PROMPT 08. Trang `0:1` còn có bảng màu `4:2` và kiểu chữ `4:88`. **Không có** component Modal, Form, Select hay Tabs.

| Thành phần | Figma | Implementation | Trạng thái |
|---|---|---|---|
| Button primary / secondary / danger / ghost md | `5:2` (h36, px16, r6, 13px) | `Button` / `buttonClass` | FV — R1–R3 |
| Table action "Xem" sm | `9:72` (r4, 11px, `#EBEFF9`) | `buttonClass("tonal","sm")` | FV — Publications, Lecturers, Imports, Normalization, AuthorsTab |
| Button sm primary / secondary (Áp dụng, phân trang, Thử lại) | không có | `buttonClass(*, "sm")` | PR (suy từ `9:72`) |
| Button warning (xác nhận cảnh báo, "Hủy đợt nhập") | không có | hình dạng md + màu amber | PR |
| Danger-outline sm ("Xóa" trong bảng, "Thu hồi") | không có | giữ class riêng, bo 4px | PR |
| Badge trạng thái | `5:34` (h23, px10, 11px Bold, pill, không viền) | `Badge`; Imports / Normalization dùng lớp nền chung đã đổi theo `5:34` | FV |
| Badge outline (thuộc tính / ngữ cảnh) | không có | `Badge appearance="outline"` | PR (PROMPT 09) |
| Search / Input | `9:9` (h36, r6, 13px, `#F8FAFC`, `#E2E8F0`) | Home, Imports, Normalization; input của Reset dialog | FV |
| Select, Textarea, Label | không có (chỉ kiểu chữ "Label/Field 12px" `4:111`) | chưa đổi | R4 (chờ duyệt) |
| Modal / Confirm dialog | không có | khung bo 10px (`rounded-card`), footer `flex-wrap`, nút theo `5:2` | PR (suy từ card) |
| Card / Stat Card | `9:25` (r10, p20, value 28px) | MyPublications dùng `rounded-card`; KPI các trang chưa đổi | R4 (chờ duyệt) |
| Data Table | `9:41` (header h40 `#F8FAFC`, 11px uppercase; row h44) | chưa chuẩn hóa chung; `/imports` có cột thao tác sticky (P10) | R4 (chờ duyệt) |
| AntD (chỉ `/reviews`) | — | `ConfigProvider` brand / danger (P10) | VERIFIED |

---

## 2. Shared components

| Component / helper | File | Ghi chú |
|---|---|---|
| `Button`, `buttonClass(variant, size, fullWidth)` | `components/ui/Button.tsx` | không đổi trong P11 |
| `Badge` (tone, appearance) | `components/ui/Badge.tsx` | không đổi trong P11 |
| `CANDIDATE_STATUS_TONE`, `REVIEW_ACTION_TONE` | `components/ui/reviewTones.ts` | không đổi |
| `ConfirmDialogFrame` + `dialogCancelButtonClass` / `dialogSecondaryButtonClass` / `dialogConfirmButtonClass` | `components/common/ConfirmDialogFrame.tsx` | **P11:** nút dựa trên `buttonClass`; khung bo 10px; footer `flex-wrap` |
| `ConfirmModal`, `DuplicateImportDialog` | `components/common/` | dùng lại class của frame |
| `TextConfirmModal` | `components/common/TextConfirmModal.tsx` | **P11:** nút secondary / danger, input h36 r6, khung bo 10px |
| `.page-action-group` | `styles.css` | **P11:** 320px → 352px (2 nút md có icon không bị cắt chữ) |

---

## 3. Tokens

**Chính thức (FV, không đổi trong P11)**

| Nhóm | Giá trị |
|---|---|
| Màu thương hiệu | `brand #3A5FC3`, `brand-hover #2F4EA6`, `brand-subtle #EBEFF9` (khớp bảng màu Figma `4:4`) |
| Màu chữ | `ink` / `ink-body` / `ink-muted` / `ink-faint` (`4:69`) |
| Màu viền | `line` / `line-strong` |
| Màu nguy hiểm | `danger #E11D48` |
| Bo góc | `rounded-control 6px`, `rounded-action 4px`, `rounded-card 10px` |
| Kích thước | `h-control 36px`, `h-badge 23px`, `min-w-action 120px` |

**PROPOSED:** `danger-hover #BE123C`; hover / focus / disabled / loading của Button; Badge outline; màu warning của nút; bo 10px cho Modal.

**Mâu thuẫn trong Figma (cần chốt ở R4)**
- Header bảng: 11px (`9:44`) so với "Table/Header 12px" (`4:114`).
- Badge trong bảng: px8 (`9:69`) so với px10 (`5:34`).
- Giá trị KPI: 28px (`9:25`) so với "Display/KPI 24px" (`4:90`).

`tailwind.config.js` **không đổi** trong P11, nên không cần khởi động lại dev server. CSS production vẫn có `.rounded-card` 10px, `.rounded-t-card`, `.rounded-control` 6px, `.rounded-action` 4px, `.h-control` 36px, `.min-w-action` 120px.

---

## 4. File diff thực tế (PROMPT 11)

**Frontend (tracked)**

| File | Thay đổi | CODE | BUILD | UI |
|---|---|---|---|---|
| `components/common/ConfirmDialogFrame.tsx` | nút dựa trên `buttonClass`; warning PR; bo 10px; footer `flex-wrap` | ✓ | ✓ | ✓ (Delete confirm) |
| `components/common/TextConfirmModal.tsx` | nút secondary / danger; input h36 r6; bo 10px | ✓ | ✓ | ✓ (Reset dialog) |
| `components/common/DuplicateImportDialog.tsx` | "Đang xử lý..." viết cứng → `t.common.processing` | ✓ | ✓ | NOT TESTED (chỉ xuất hiện khi upload trùng, mà upload là thao tác ghi) |
| `pages/Lecturers/index.tsx` | 12 nút → `buttonClass`; "Xóa" bo 4px; 2 modal bo 10px; **19 chuỗi chỉ có VI** được thêm nhánh EN (toast, lỗi, option học vị / giới tính, cảnh báo) | ✓ | ✓ | ✓ (nút, modal, option EN); toast **NOT TESTED** (chỉ hiện sau thao tác ghi) |
| `pages/Users/index.tsx` | 2 nút; chú thích bảng EN | ✓ | ✓ | ✓ |
| `pages/ReviewHistory/index.tsx` | 6 nút; "Thử lại" viết cứng → `copy.retry` | ✓ | ✓ | ✓ (VI / EN) |
| `pages/AuditLogs/index.tsx` | 6 nút | ✓ | ✓ | ✓ |
| `i18n/locales/vi.ts`, `en.ts`, `types.ts` | thêm `reviewHistory.retry` | ✓ | ✓ | ✓ |
| `pages/Imports/index.tsx` | 17 nút → `buttonClass`; 2 nút bảng bo 4px; badge trạng thái theo `5:34`; ô tìm kiếm theo `9:9`; modal bo 10px | ✓ | ✓ | ✓ |
| `pages/Normalization/index.tsx` | 8 nút; badge; ô tìm kiếm; modal bo 10px; 1 lỗi VI-only → EN | ✓ | ✓ | ✓ |
| `pages/Normalization/AuthorsTab.tsx` | 6 nút ("Đóng" từ primary → secondary); modal bo 10px | ✓ | ✓ | ✓ |
| `components/lecturers/LecturerDatasetImportCard.tsx` | 2 nút | ✓ | ✓ | NOT TESTED (nút chỉ hiện sau khi chọn tệp) |
| `styles.css` | `.page-action-group` 352px | ✓ | ✓ | ✓ (Imports, Lecturers, Dashboard) |

**Backend (review policy, tách riêng khỏi Design System)**
- `app/services/review_reason_policy.py`: chỉ đếm ứng viên `{PENDING, ACCEPTED}` (§6).
- `tests/integration/test_review_reason_policy.py`: thêm 9 case.

**Không đổi nghiệp vụ**
- Không đổi handler, `disabled`, validation, API, quyền hay luồng nhập CSV / preview / apply.
- Chỉ thay thuộc tính `className` của thẻ `<button>` có sẵn. Mỗi nút được xác định theo dòng, và script assert đúng nhãn / handler trước khi thay.
- Không bấm upload / kiểm tra dữ liệu / xác nhận / chuẩn hóa / xóa / khôi phục / hủy trong khi test.

---

## 5. R3a (VERIFIED)

### Kiểm kê và ánh xạ

| Màn hình | Nút | Ánh xạ |
|---|---|---|
| Lecturers | 20 nút | Xuất JSON → **secondary** (Figma xếp "Tải xuống" là Secondary); Thêm / Áp dụng / Tạo / Lưu → primary; Đặt lại / Hủy → secondary; Chi tiết → tonal sm; phân trang → secondary sm. **Giữ nguyên:** 5 thẻ KPI-lọc (R4), chip ×, nút icon đóng / hiện mật khẩu, "Xóa" trong bảng (danger-outline PR, chỉ đổi bo 4px). |
| Users | 2 nút | Thêm tài khoản → primary; Làm mới → secondary |
| ReviewHistory, AuditLogs | 6 nút mỗi trang | Làm mới → secondary; Áp dụng → primary sm; Xóa bộ lọc / Thử lại / phân trang → secondary sm (giống `/publications`) |
| Hộp xác nhận | — | Hủy → secondary; hành động phụ → ghost; Xác nhận → primary / danger; warning → PR |

### Kết quả trình duyệt

| Run | Loại | Kết quả |
|---|---|---|
| `20261017T213755_p11_r3a_browser_readonly` | original | 27 / 27 PASS — **check chưa đủ chặt** (§8.2, có `NOTE.txt`) |
| `20261017T214812_p11_r3a_browser_readonly_rerun` | rerun (check đã sửa) | **27 / 27 PASS** |

**Nội dung đã kiểm**
- Màu / chiều cao / bo góc từng nhóm nút.
- Focus ring khi Tab.
- Modal tạo / chi tiết giảng viên: bo 10px, vừa màn hình desktop và mobile, đóng bằng Hủy / Escape, 0 request.
- Hộp xác nhận xóa: Hủy secondary, Xóa danger `#E11D48`, focus vào nút xác nhận, Escape đóng, không xóa gì.
- Reset dialog: nút danger **disabled** cho tới khi gõ đúng từ; input h36; Escape đóng.
- AuditLogs / ReviewHistory: trạng thái lỗi (chặn URL phía trình duyệt) có "Thử lại" / "Retry" đúng ngôn ngữ.
- VI / EN; mobile không tràn, không cắt chữ.
- 0 request ghi, 0 lỗi.

**Lỗi có sẵn phát hiện thêm (không do R3a):** `/lecturers` ở 1440px, cột "Thao tác" tràn mép phải và nút "Xóa" bị cắt một phần. Đây là phần `/lecturers` của UI-10, đưa vào R4 Data Table (§7).

---

## 6. R3b (VERIFIED) và quy tắc đếm ứng viên

### R3b

| Màn hình | Ánh xạ |
|---|---|
| Imports | 2 nút header → primary (full-width trong `.page-action-group`); Kiểm tra dữ liệu / Xác nhận nhập / Xác nhận nhập giảng viên → primary (bỏ gradient không có trong Figma); Hủy tệp / Hủy tiến trình → secondary; Áp dụng / Đặt lại → primary / secondary md; Chi tiết → tonal sm; Khôi phục / Xóa trong bảng → bo 4px (PR); phân trang → secondary sm; footer modal: Đóng → secondary, Xóa đợt nhập → danger, Khôi phục → secondary, Hủy đợt nhập → warning-outline (PR) |
| Badge trạng thái (Imports, Normalization) | màu nền / chữ **đã khớp** tone Figma (emerald / amber / rose / slate / violet / blue-50); chỉ đổi lớp nền chung: bỏ `w-32` và viền, h23, 11px |
| Ô tìm kiếm | bo 6px, 13px (theo `9:9`) |
| Normalization / AuthorsTab | Chi tiết → tonal sm; Chuẩn hóa → primary sm / md; Chuẩn hóa lại → secondary; Đóng → secondary; phân trang → secondary sm; **tab (segmented) giữ nguyên** (không có trong Figma → R4) |

**Kiểm "Preview có ghi không" (VS):** mở chi tiết chỉ gọi `GET /api/v1/imports/{id}`, `GET /api/v1/authors/{id}` hoặc đổi state cục bộ. Không bấm "Kiểm tra dữ liệu" (`POST` upload) hay bất kỳ nút Apply / Confirm / Normalize nào.

| Run | Loại | Kết quả |
|---|---|---|
| `20261017T214511_p11_r3b_browser_readonly` | original | 19 PASS / 3 FAIL: 2 FAIL do lỗi script; 1 lỗi thật đã sửa — nhãn "Thêm tệp Sco…" bị cắt ở header (§8.2) |
| `20261017T214935_p11_r3b_browser_readonly_rerun` | rerun (sau sửa `.page-action-group` + script) | **22 / 22 PASS** |

**Nội dung đã kiểm**
- Header, ô tìm kiếm, nút bảng, badge h23 không viền, không cắt chữ.
- **Regression P10 của bảng `/imports`:** bảng vừa khung, cột thao tác sticky và hiển thị, cột "Trạng thái" không bị che.
- Phân trang; modal chi tiết Imports (bo 10px, Đóng secondary, Xóa đợt nhập danger, Escape đóng, vừa mobile).
- Normalization: ô tìm kiếm, Chi tiết tonal, badge, modal chi tiết; AuthorsTab (Chi tiết tonal, modal tác giả, Đóng secondary).
- Mobile không tràn.
- 0 request ghi, 0 lỗi API / console.

### Quy tắc đếm ứng viên mơ hồ (CODE + backend test; UI không đổi)

| Ứng viên "anh em" | Cùng giảng viên | Cùng Scopus ID (giảng viên khác) |
|---|---|---|
| PENDING | bắt buộc lý do | bắt buộc lý do |
| ACCEPTED | bắt buộc lý do (đã có liên kết đã duyệt với Scopus ID khác) | **409 xung đột**, xử lý trước khi xét lý do |
| REJECTED | **không** tính | **không** tính |
| SUPERSEDED | **không** tính | **không** tính |

**Kiểm state machine (VS)**
- Chỉ có PENDING → ACCEPTED (tạo đúng một identity APPROVED, `resulting_identity_id`) và PENDING → REJECTED.
- Không có code thu hồi identity hay đặt SUPERSEDED. Vậy ACCEPTED ⇔ có liên kết đã duyệt; quy tắc **không mâu thuẫn**.
- Idempotency: bước kiểm lý do đặt sau nhánh phát lại, nên không ảnh hưởng.
- Mã lỗi / thông báo frontend không đổi (`REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE`, `reason_triggers`; modal lấy điều kiện từ `review_policy` của server).

**Test:** run `20261017T215148_p11_review_policy`: **67 passed**, gồm 9 case mới:
- anh em PENDING / ACCEPTED / REJECTED / SUPERSEDED, cùng giảng viên và cùng Scopus ID;
- 409 trước 422;
- phát lại idempotent sau khi anh em bị REJECT.

**Tác động dữ liệu hiện tại:** 0 ứng viên đổi điều kiện (PROMPT 10 §5).

**Runtime:** backend 8199 và 8399 đã khởi động lại để chạy chính sách mới.

**LIMITATION:**
- Số "Còn N ứng viên khác" ở hàng đợi vẫn đếm mọi trạng thái, để giữ nguyên ngữ nghĩa bộ lọc "mơ hồ". Điều kiện bắt buộc lý do trong modal lấy từ server nên vẫn khớp với điều server áp dụng.
- Đổi cách đếm hiển thị cần quyết định riêng.

---

## 7. R4 — Component Migration Matrix (PROPOSED, chưa triển khai, chờ duyệt)

| Thành phần | Nguồn Figma | Nơi dùng thực tế | Đề xuất trích xuất | Phạm vi file | Regression impact |
|---|---|---|---|---|---|
| **Data Table** | `9:41` (header h40 `#F8FAFC`, 11 / 12px uppercase SemiBold `#64748B`; row h44; cell 12–13px) | `/publications`, `/lecturers`, `/imports`, `/audit-logs`, `/review-history`, `/normalization` (2 bảng), AuthorsTab, `/reviews` hàng đợi, chi tiết công bố (3 bảng) | helper class (không phải component lớn): `tableFrameClass`, `thClass`, `tdClass`, **`stickyActionCellClass`** (cột thao tác sticky phải + viền trái, như `/imports` P10); không đụng sort / filter / pagination | 9 file trang | 11 bảng × VI / EN × 1440 / 375; kiểm cột thao tác không tràn và không che (sửa luôn `/lecturers` UI-10) |
| **Form controls** | `9:9` (Input), kiểu chữ "Label/Field 12px" `4:111`; **không có** Select / Textarea | Lecturers (2 form ~15 trường), Users (form tạo), bộ lọc AuditLogs / ReviewHistory / Publications / `/reviews` (select h-8), ManualReviewCard | `inputClass`, `selectClass` (PR: giống input), `textareaClass`, `labelClass`; không thay validation | ~8 file | các form tạo / sửa: mở, nhập (không gửi), lỗi hiển thị, focus, disabled, VI / EN, mobile |
| **Stat Card / KPI** | `9:25` (r10, p20, label 12 `#64748B`, value 28 bold, sub 11) — **mâu thuẫn** với "Display/KPI 24px" | Dashboard (5), Lecturers (5 thẻ-lọc bấm được), Imports (5), Normalization (5), MyPublications (4) | `StatCard` có `onClick` / `active` tùy chọn; giữ nguồn số liệu và ngữ nghĩa lọc | 5 file | đối chiếu số trước / sau từng thẻ (không đổi công thức), trạng thái active của thẻ lọc, mobile |
| **Modal frame** | không có | Lecturers (2), Imports, Normalization, AuthorsTab, `ConfirmDialogFrame` | `ModalFrame` (backdrop, panel r10, header, footer wrap, Escape, max-h) — PR | 5 file | mở / đóng / Escape / focus từng modal, mobile |
| **Tabs (segmented)** | không có | Normalization (4 tab) | giữ nguyên hoặc PR | 1 file | — |

**Cần chủ đồ án chốt trước R4:** header bảng 11px hay 12px; giá trị KPI 28px hay 24px; badge trong bảng px8 hay px10; có chuẩn hóa Modal / Select / Tabs khi Figma chưa có hay không.

---

## 8. Browser regression và sự cố kiểm thử

### 8.1 Tổng hợp

| Run | Phạm vi | Kết quả |
|---|---|---|
| `20261017T214812_p11_r3a_browser_readonly_rerun` | R3a (ADMIN, REVIEWER) | 27 / 27 |
| `20261017T214935_p11_r3b_browser_readonly_rerun` | R3b (ADMIN) | 22 / 22 |
| `20261017T215552_p11_backlog_readonly` | nhãn EN mới; sidebar thu gọn; `/tasks` | 6 PASS + 1 PARTIAL (`/tasks` vẫn placeholder, giữ theo quyết định sản phẩm) |
| `20261017T215148_p11_review_policy` | backend (DB pytest cô lập) | 67 passed |
| `tsc` / `npm run build` | — | PASS / PASS |

**Phạm vi vai trò:** LECTURER không có quyền vào các route R3. Việc LECTURER bị chặn khỏi các route này đã kiểm ở PROMPT 08 / 10 và không đổi trong lượt này.

**Mỗi run có:** thư mục riêng; `manifest.json` (commit, branch, sha256 của diff, môi trường, original / rerun / `rerun_of`, tổng PASS / FAIL / PARTIAL / BLOCKED, checksum); `results.json` (expected / actual); ảnh theo route; `secrets_stored: false`. Quét 30 file bằng chứng P11: **0** giá trị bí mật.

### 8.2 Sự cố kiểm thử (minh bạch)

1. **PASS giả trong hai run original.**
   - Hàm phát hiện modal lọc theo `offsetParent`, luôn bằng `null` với phần tử `position: fixed`, nên các check "modal đã đóng" của modal tự viết (Lecturers, Imports) có thể PASS dù modal còn mở.
   - "Bị cắt chữ" chỉ so khung nút, bỏ sót nhãn bị `truncate` trong `span` con.
   - Đã thêm `NOTE.txt` vào hai run gốc (không sửa kết quả). Sửa script dùng `getClientRects()` và kiểm cả phần tử con, rồi rerun: các check đóng modal vẫn PASS (Escape / Hủy hoạt động thật).
2. **Lỗi thật lộ ra nhờ rerun:** nhãn nút header "Thêm tệp Scopus" bị cắt sau khi đổi sang Button md → sửa `.page-action-group` 320 → 352px, kiểm lại ở Imports / Lecturers / Dashboard.
3. **Lệnh vá script nối chuỗi trong shell.** Ở R3a, một lệnh vá lỗi escape thất bại nhưng lệnh chạy phía sau vẫn thực thi bản script gốc. Kết quả code vẫn đúng (12 + 2 nút), chỉ tạo import tách 2 dòng, đã gộp lại. Từ đó tôi tách lệnh vá và lệnh chạy.

---

## 9. UI backlog còn lại

| Vấn đề | Còn tồn tại? | Xử lý |
|---|---|---|
| VI / EN thiếu | **có**, ngoài phạm vi R3: toast thành công / lỗi ở các màn hình khác chưa rà; các toast của Lecturers chỉ hiện sau thao tác ghi nên NOT TESTED runtime | rà toàn hệ thống: đợt riêng |
| Nút mobile bị cắt chữ | **không** trên các route đã kiểm (R3a / R3b / P10) | — |
| Bảng tràn ngang | **có**: `/lecturers` 1440 cắt cột thao tác (UI-10); `/audit-logs`, `/review-history` cuộn ngang trong khung | R4 Data Table |
| Loading khi đổi route / section | không đổi; không thêm loading giả | thiết kế riêng |
| Sidebar thu gọn | **đã đúng**: icon căn giữa ±2px (`sidebar_collapsed.png`) | — |
| Empty / error state | đã kiểm AuditLogs, ReviewHistory, `/publications`, `/my-publications` (lỗi + Thử lại) | chuẩn hóa chung ở R4 nếu duyệt |
| Thuật ngữ khác nhau giữa các trang | `/reviews` / `/review-history` đã thống nhất (P09); Dashboard "Đã duyệt" (UI-02) giữ; trang khác chưa rà toàn bộ | đợt riêng |
| `/tasks` placeholder | **có** | quyết định sản phẩm (không tạo chức năng mới) |
| AntD Modal / Button ở `/reviews` | giữ, chỉ theme brand (P10) | thay bằng component chung nếu duyệt Modal frame |
| `DuplicateImportDialog`, `LecturerDatasetImportCard` | code đã sửa, **NOT TESTED** UI (cần upload, là thao tác ghi) | kiểm trên DB TEST cô lập nếu được duyệt |

---

## 10. Git status

**Stage (không đổi):** 4 file RC.

**Unstaged:** thay đổi PROMPT 07–10 giữ nguyên. Thay đổi riêng P11 nằm ở 15 file tracked (§4) và 2 file untracked đã có trước (`review_reason_policy.py`, `test_review_reason_policy.py`).

**Untracked mới:** báo cáo này.

### Đề xuất chia commit (không thực hiện)

| # | Commit | File |
|---|---|---|
| 1 | Design System R3a — dialogs & admin pages | `ConfirmDialogFrame.tsx`, `TextConfirmModal.tsx`, `Lecturers`, `Users`, `ReviewHistory`, `AuditLogs`, i18n `reviewHistory.retry`, `styles.css` |
| 2 | Design System R3b — Imports & Normalization | `Imports`, `Normalization/index`, `AuthorsTab`, `LecturerDatasetImportCard`, `DuplicateImportDialog` |
| 3 | i18n — EN cho chuỗi VI-only ở Lecturers / Users / Normalization | có thể gộp vào 1 / 2 theo file |
| 4 | Review policy — count only active candidates (D-2) | `review_reason_policy.py`, `test_review_reason_policy.py` — **tách khỏi Design System** |

---

## 11. Chưa đủ điều kiện GO release

| # | Hạng mục | Trạng thái |
|---|---|---|
| 1 | Credential `scopus_m12_user` @5432: rotate / khóa, kiểm listen / firewall, dọn `.tmp` và transcript (PROMPT 10) | BLOCKED (chủ đồ án) |
| 2 | Duyệt R4 Component Migration Matrix và các mâu thuẫn Figma (§7) | PROPOSED |
| 3 | `/lecturers` tràn cột thao tác 1440px (UI-10) | chờ R4 |
| 4 | Commit theo kế hoạch PROMPT 07–11 | chờ chủ đồ án |
| 5 | Full regression backend (~1.050 test) và START launcher end-to-end trên App DB | đề xuất ở bước release |
| 6 | Revision App DB so với HEAD (`c7f2a9b1d3e5`); nếu lệch chỉ migrate qua `scopus-ictu-qhun22.bat migrate` | chưa kiểm (không đụng App DB) |
| 7 | UI các luồng ghi (upload trùng, toast sau khi lưu / khóa / reset) | NOT TESTED; cần DB TEST cô lập và quyền riêng |
| 8 | `/tasks` | quyết định sản phẩm |

---

**Dừng tại đây** để chủ đồ án và ChatGPT nghiệm thu R3a / R3b / quy tắc đếm ứng viên, và duyệt riêng R4.
