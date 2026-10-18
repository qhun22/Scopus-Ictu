# Design System Rollout R1/R2 — Scopus-ICTU (17/10/2026)

- **Release:** `v1.0.0-rc.1` vẫn **HOLD**. Đợt này dừng sau R1/R2 + regression để chờ chủ đồ án duyệt.
- **Tài liệu nền:** `DESIGN_SYSTEM_PILOT_20261017.md` (pilot). Báo cáo này bổ sung, không thay pilot.
- **Ràng buộc đã giữ:**
  - Không commit, tag, push, stage, reset, rebase.
  - Không migration, không ghi DB A hay DB restore.
  - Không đổi API/backend, handler, quyền hay công thức KPI.
  - Không đổi i18n; không format toàn frontend.

**Mức bằng chứng**

| Mã | Nghĩa |
|---|---|
| **FV** — FIGMA-VERIFIED | Đọc lại trong phiên này (17/10) bằng MCP `get_design_context` trên file `yctOa75eATXHnTQmesJy5A`, các node `5:2`, `5:34`, `9:9`, `9:25`, `9:41` |
| **PR** — PROPOSED | Chưa có trong Figma, chờ duyệt |
| **NV** — NOT VERIFIED | Chưa kiểm được |
| **VR** | Đo trên trình duyệt |
| **VU** | Unit test |
| **VI** | Integration: API thật đối chiếu SQL chỉ đọc |
| **VM** | Browser + mock API phía trình duyệt |

---

## 1. Component và token: trước / sau

| Mục | Trước PROMPT 08 | Sau PROMPT 08 | Mức |
|---|---|---|---|
| `rounded-control` (nút md, input) | 5px | **6px** | FV (`5:2`, `9:9`) |
| `rounded-action` (nút sm, action trong bảng) | — (nút sm dùng 5px) | **4px** (token mới) | FV (`9:72` "Xem" trong `9:41`) |
| `rounded-card` | 5px | **10px** | FV (`9:25` Stat Card, `9:41` Data Table) |
| Badge | pill, h23, px10, 11px Bold, không viền | không đổi | FV (`5:34`: px10 py3 11px, `rounded-[9999px]`, không viền) |
| `Button` | radius đặt chung ở lớp gốc | radius theo size: md → `rounded-control`, sm → `rounded-action` | FV |
| `components/common/buttonStyles.ts` | 4 hằng `BUTTON_*`, 5 file dùng | **đã xóa** (0 nơi dùng hợp lệ; bản sao ở `scratch/ds_rollout/buttonStyles.ts.bak`) | — |
| `components/ui/reviewTones.ts` | — | **mới**: `CANDIDATE_STATUS_TONE`, `REVIEW_ACTION_TONE` dùng chung `/reviews` và `/review-history` | — |

Toàn dự án chỉ còn **một** nguồn token (`tailwind.config.js`) và **một** component nút (`components/ui/Button`).

## 2. File đã sửa trong PROMPT 08

| File | Nội dung |
|---|---|
| `frontend/tailwind.config.js` | radius 6 / 4 / 10 (§1) |
| `frontend/src/components/ui/Button.tsx` | radius theo size |
| `frontend/src/components/ui/reviewTones.ts` (mới) | map tone trạng thái ứng viên / hành động review |
| `frontend/src/components/common/buttonStyles.ts` | **xóa** (` D` trong `git status`, không stage) |
| `pages/Lecturers/index.tsx` | 2 nút (R1) |
| `pages/Users/index.tsx` | 2 nút (R1) |
| `pages/Normalization/AffiliationsTab.tsx` | 4 nút (R1). 18/18 dòng UI-03 đã nghiệm thu vẫn còn nguyên. |
| `pages/Normalization/ManualReviewCard.tsx` | 5 nút (R1) |
| `pages/Normalization/MatchingTab.tsx` | 3 nút (R1) |
| `pages/ApprovalQueue/index.tsx` | R2: badge bằng chứng / mơ hồ / dùng chung → `Badge`; 5 AntD `Tag` → `Badge`; bỏ import `Tag` |
| `pages/ReviewHistory/index.tsx` | R2: `ActionBadge`, `StatusBadge` → `Badge` + `reviewTones` |
| `pages/Dashboard/charts/PublicationsByYearChart.tsx` | quy tắc năm theo ràng buộc DB (§6) |
| `pages/Dashboard/charts/DocumentTypeDonutChart.tsx` | nhãn EN chuẩn cho 14 loại (§6) |

**Không đụng:**
- i18n (`vi.ts`, `en.ts`, `types.ts`) và `AuthorAffiliations.tsx`: giống byte-for-byte patch nền.
- `Badge.tsx`, backend, DB, script launcher.

**Line ending:** giữ nguyên từng file (CRLF / LF như bản làm việc trước khi sửa); diff chỉ chứa thay đổi thật.

**Patch ngoài repo:**
- Trước khi sửa: `scratch/ds_rollout/baseline_worktree_before_p08.patch`.
- Sau khi sửa: `worktree_after_p08.patch`.

---

## 3. Figma – Implementation Matrix (cập nhật)

### 3.1 Button

| Thành phần | Figma | Implementation | Trạng thái |
|---|---|---|---|
| Primary md | `#3A5FC3`, h36, px16, 13px SemiBold, r6, mẫu 120w | `variant="primary"` | **FV**, khớp |
| Secondary md | trắng, viền 1.5 `#CBD5E1`, chữ `#334155`, r6 | `variant="secondary"` | **FV**, khớp (Chrome DPR 1 làm tròn viền 1.5 → 1px) |
| Danger md | `#E11D48`, chữ trắng, r6 | `variant="danger"` | **FV**, khớp |
| Ghost md | `#F1F5F9`, chữ `#334155`, r6 | `variant="ghost"` | **FV**; chưa có nơi dùng |
| Tonal sm (action trong bảng) | `#EBEFF9` / `#3A5FC3`, 11px SemiBold, px10 py5, r4 | `variant="tonal" size="sm"` | **FV**, khớp |
| Primary / Secondary **sm** | Figma không có | `size="sm"` (h28, r4) | **PR** (suy từ `9:72`) |
| Hover / focus / disabled / loading | Figma không có | ring brand, opacity 50%, spinner | **PR** |
| Độ rộng | mẫu 120; PageHeader 140 | `min-w-action` 120 + co theo nội dung | **FV** (suy từ 2 node) |

### 3.2 Badge, Input, Card / Table

| Thành phần | Figma | Implementation | Trạng thái |
|---|---|---|---|
| Badge 8 tone | `5:34` | `Badge tone=…` | **FV**, khớp |
| Badge trong bảng | `9:69`: px**8** (khác `5:34` px10) | dùng px10 chuẩn | Figma tự mâu thuẫn; **không** coi px8 là chuẩn |
| Badge có viền | không có | không dùng | **PR** (đề xuất §7) |
| Input / Search | `9:9`: nền `#F8FAFC`, viền `#E2E8F0`, r6, px12, 13px | `/home` đã áp dụng; trang khác chưa | **FV**, rollout R4 |
| Card / Stat Card | `9:25`: r10, p20, viền `#E2E8F0` | token `rounded-card` 10px; mới dùng ở `/my-publications` | **FV**, rollout R4 |
| Data Table | `9:41`: khung r10, header h40 `#F8FAFC` 11px uppercase, row h44 | chưa | R4 |

## 4. Trạng thái R1 / R2

### R1 — 16 nút trong 5 file từng dùng `buttonStyles.ts`

**Quy tắc ánh xạ theo thứ bậc hành động (Figma `5:2`):**
- `BUTTON_PRIMARY` → `primary`.
- `BUTTON_DANGER` → `danger`.
- `BUTTON_SECONDARY` → `secondary` (viền trắng). Kiểu cũ là tonal xanh cỡ md, Figma không có biến thể này. Các nút này là Hủy / Xem trước / Sửa / Thêm, tức hành động bậc hai.

**Giữ nguyên:**
- `onClick`, `disabled`, `type="button"`, `data-testid`, chữ "Đang …" khi bận.
- Không dùng prop `loading`, để logic `disabled` không đổi.

| File | Nút | Variant | VR |
|---|---|---|---|
| Lecturers | Đặt lại mật khẩu / Khóa tài khoản (Mở khóa) | secondary / danger (primary khi mở khóa) | **PASS**: 133 / 125 × 36, r6, VI / EN, mobile full-width 319 |
| Users | Tạo tài khoản / Hủy | primary / secondary | **PASS**: 120 / 124 × 36; submit **disabled** khi form trống; focus ring khi Tab |
| AffiliationsTab | Bắt đầu thu thập trực tuyến, Hủy, Xem trước / Xác nhận áp dụng | secondary / primary | **PASS** (Xác nhận áp dụng chỉ hiện sau Xem trước, nên **NV** runtime) |
| ManualReviewCard | Lưu (submit form), Hủy, Sửa, Hủy (thu hồi), Thêm đơn vị | primary / secondary | **PASS**: mở form "Thêm đơn vị" → primary + Hủy → đóng bằng Hủy, 0 request ghi |
| MatchingTab | Xem trước dữ liệu / Xác nhận bổ sung dữ liệu / Tạo danh sách đề xuất | secondary / primary / primary | **PASS** (Xác nhận bổ sung: **NV**, cần Xem trước) |

**Không đổi trong R1 (lý do):**
- Nút "Thu hồi" / "Xác nhận thu hồi" ở ManualReviewCard: viền đỏ; không dùng `buttonStyles`, và Figma không có danger-outline.
- Nút header `/lecturers` (Xuất JSON, Thêm giảng viên); "Chi tiết" / "Xóa" trong bảng; footer modal (Hủy / Lưu thay đổi). Tất cả không dùng `buttonStyles` → R3.

### R2 — `/reviews` và `/review-history`

| Loại | Ngữ nghĩa | Trước | Sau | VR |
|---|---|---|---|---|
| Trạng thái ứng viên | PENDING / ACCEPTED / REJECTED / SUPERSEDED (kết quả **review**, không phải định danh) | `Badge` (pilot); `/review-history`: xám bo 4 có viền | `CANDIDATE_STATUS_TONE`: warning / success / danger / neutral, dùng chung 2 trang | **PASS** (PENDING, ACCEPTED, REJECTED). SUPERSEDED: **NV**, DB A có 0 ứng viên. |
| Hành động review | ACCEPT / REJECT / REOPEN (hành động, không phải trạng thái) | span bo 4 có ring | `REVIEW_ACTION_TONE`: success / danger / warning | **PASS** (ACCEPT, REJECT). REOPEN: **NV**, không có dữ liệu. |
| Loại bằng chứng | crawl-only / có công bố hỗ trợ / chỉ tên | pill h20 10px có viền | `Badge` violet / info / neutral | **PASS** |
| Ngữ cảnh mơ hồ | có / không ứng viên khác; dùng chung Scopus ID | pill h20 10px có viền | `Badge` warning / neutral; dùng chung = danger | **PASS** (giữ `title`, `data-testid=shared-author-tag`) |
| Mã luật (rule_id) | định danh kỹ thuật | AntD `Tag` blue | `Badge` brand | **PASS** |
| Đối chiếu công bố (reconciliation) | `DOI_EXACT` / khác | AntD `Tag` green / blue | `Badge` success / brand (giữ đúng màu cũ) | **NV** runtime: ứng viên mở thử chỉ có bằng chứng tên |
| Biến thể tên | danh sách tên | AntD `Tag` mặc định | `Badge` neutral | **PASS** |
| Hành động trong modal xác nhận | ACCEPT / REJECT | AntD `Tag` green / red | `Badge` success / danger | **PASS**: mở modal xác nhận → badge ACCEPT h23 → đóng bằng **Hủy** (không bấm OK), 0 request ghi |
| Filter chip | — | `/reviews` không có (bộ lọc là `<select>`) | — | — |

**Kết quả đo**
- Sau R2: 0 AntD `Tag`, 0 pill có viền trong vùng nội dung.
- Mọi badge: h23, px10, viền 0, không bị cắt chữ.
- Mobile: overflowX 0 (bảng cuộn trong khung).

**Không gộp ngữ nghĩa:**
- REVIEW ACCEPTED ≠ IDENTITY VERIFIED.
- Hành động ACCEPT ≠ trạng thái ACCEPTED.
- Rejected proposal ≠ Revoked identity.
- Badge `/reviews` không dùng nhãn hay tone của AffiliationBadge.

**Không sửa:** logic Chấp nhận / Từ chối và các AntD `Button` trong modal.

---

## 5. Kết quả kiểm thử

| Bước | Kết quả |
|---|---|
| `npx tsc --noEmit` | **PASS** |
| `npm run build` | **PASS**. Cảnh báo chunk > 500 kB đã có từ trước. |
| CSS bản build (`dist/assets/*.css`) | `.rounded-control` 6px, `.rounded-action` 4px, `.rounded-card` 10px, `.h-badge` 23px, `.h-control` 36px, `.min-w-action` 120px; không còn `#E50000` |
| Dev server nạp config mới | Khởi động lại 5199 (dev server đã dừng do app restart). CSS phục vụ và `getComputedStyle` lúc chạy đều 6 / 4 / 10px. **Không** dùng CSS server cũ làm bằng chứng. |
| Unit `buildYearSeries` (node + esbuild) | **PASS** 5 / 5 case (§6) |
| Integration API ↔ SQL chỉ đọc | **PASS** (§6) |

### 5.1 Trình duyệt

**Phạm vi chạy**
- Script `scratch/ds_rollout/ui_ds_rollout_r1r2_cdp_20261017.py`; kết quả ở `results_ds_rollout.json` và `shots/` (31 ảnh).
- Môi trường A: 5199 → 8199 → DB A.
- Tài khoản TEST `withjson.*` theo quyền đã cấp (PROMPT 05).

| Vai trò | Màn hình | VI | EN | Mobile 375 | Trạng thái đặc biệt | Kết quả |
|---|---|---|---|---|---|---|
| ADMIN | `/lecturers` (modal chi tiết có tài khoản) | ✓ | ✓ | ✓ | — | PASS |
| ADMIN | `/users` (form tạo) | ✓ | ✓ | ✓ | disabled + focus | PASS |
| ADMIN | `/normalization` affiliations + ManualReviewCard | ✓ | ✓ | ✓ | form mở / đóng | PASS |
| ADMIN | `/normalization` matching | ✓ | ✓ | ✓ | focus | PASS |
| ADMIN | `/home`, `/publications`, `/dashboard` (ảnh hưởng token radius) | ✓ | ✓ | ✓ | Áp dụng disabled: opacity 0.5, `not-allowed`; focus Xuất JSON | PASS |
| REVIEWER | `/reviews` hàng đợi: lọc PENDING / ACCEPTED / REJECTED / SUPERSEDED (GET) | ✓ | ✓ | ✓ | Empty SUPERSEDED | PASS |
| REVIEWER | `/reviews` chi tiết + modal xác nhận (mở / hủy) | ✓ | ✓ | ✓ | — | PASS |
| REVIEWER | `/review-history` | ✓ | ✓ | ✓ | Error (chặn URL phía trình duyệt): thông báo + Thử lại | PASS |
| LECTURER | `/reviews`, `/review-history`, `/lecturers`, `/users`, `/normalization` | — | — | — | đều chuyển về `/home` (RoleRoute) | PASS |
| LECTURER | `/my-publications` | ✓ | — | — | card r10 | PASS |

**Kiểm tra bàn phím:** Tab tới nút → `:focus-visible` = true, ring `rgba(58,95,195,0.3)` 3px + offset trắng 1px. Đã thấy trên Hủy (`/users`), Xem trước dữ liệu (`/normalization`), Xuất JSON (`/publications`).

**Console / network**
- 0 lỗi console; 0 request không phải GET (ngoài login).
- Lỗi API duy nhất là 403 `/lecturers/me/publications` của giảng viên chưa liên kết: đúng hành vi, có từ trước.

**DB**
- Fingerprint DB A và DB restore trước = sau (**IDENTICAL**); DB A = snapshot nguồn.
- Quét 25 tệp bằng chứng: 0 giá trị bí mật.
- Đã xóa profile Chrome tạm; không còn tiến trình headless.

### 5.2 Sự cố quy trình (minh bạch)

1. **Bằng chứng PROMPT 07 bị ghi đè.**
   - Diễn biến: trong một script debug, lệnh `replace()` lồng nhau vô hiệu hóa việc tắt `main()` của script pilot. Script pilot vì vậy chạy lại toàn bộ lúc 19:17–19:19 và **ghi đè** `scratch/ds_pilot/results_ds_pilot.json` cùng 23 ảnh `ds_pilot/shots/`, nay chụp code hiện tại với radius 6 / 4 / 10.
   - Ảnh hưởng: script pilot chỉ đọc (0 request ghi; fingerprint DB vẫn IDENTICAL). Số liệu PROMPT 07 vẫn được ghi trong báo cáo pilot, nhưng ảnh minh chứng gốc của pilot **không còn**.
   - Đã sửa script để chuỗi tắt `main()` được ghép lúc chạy, không thể bị `replace()` bên ngoài sửa.
2. **Dev server dừng.** 4 dev server đã dừng (app khởi động lại). Chỉ khởi động lại môi trường A (5199, 8199); môi trường restore (5399, 8399) **không** bật lại vì lượt này không dùng.

---

## 6. Dashboard: kiểm tra logic đã triển khai

### 6.1 Quy tắc năm

**Phát hiện:** quy tắc pilot (loại năm < 1900 hoặc > năm hiện tại + 2) là ngưỡng **tự đặt, chưa được đặc tả**. Với năm 2026, quy tắc đó **loại năm 2030** khỏi trục.

Quy tắc năm duy nhất đã được đặc tả là ràng buộc DB `ck_publications_year_range`: `year IS NULL OR year BETWEEN 1000 AND 9999`. Nguồn: `backend/app/models/publication.py`, `docs/design/database/CONSTRAINTS_CATALOG.md`.

**Đã sửa (frontend, không đổi API):**
- Vẽ **mọi** năm 1000–9999.
- Năm ngoài khoảng đó (chỉ có thể đến từ phản hồi lỗi) được liệt kê trong ghi chú `year-outliers-note`, **không** bị loại âm thầm.
- Không gán cứng năm kết thúc; trục kết thúc ở năm lớn nhất có dữ liệu.
- Nhãn trục bật `autoSkip`, để khoảng năm dài không chồng chữ.
- Công bố không có năm vẫn được ghi chú riêng (Dashboard dòng 327, có từ trước).

### 6.2 Kết quả theo loại bằng chứng

| Kiểm tra | Loại bằng chứng | Kết quả |
|---|---|---|
| Năm trống hiển thị 0 | **VU** | 2016, 2019, 2024 → 2016…2024 liên tục; 2017–2018 và 2020–2023 bằng 0 |
| Năm trống hiển thị 0 | **VM** | Mock 2016, 2019, 2026, 2028, 2030 → 2016…2030 đủ 15 cột, năm trống = 0 |
| Không gán cứng 2027; 2028 và 2030 được vẽ | **VU** | `future_2028_2030`: 2025…2030, 2030 = 4, outliers rỗng |
| Không gán cứng 2027; 2028 và 2030 được vẽ | **VM** | 2028 = 2, 2030 = 6 có trên trục (VI / EN) |
| Năm không hợp lệ có thông báo | **VU** | 0 và 99999 → outliers, tổng số đếm được bảo toàn |
| Năm không hợp lệ có thông báo | **VM** | "1 công bố có năm không hợp lệ (0; hợp lệ: 1000–9999) nên không được vẽ trên trục năm." / EN tương ứng |
| Biên 1000 | **VU** | 1000…1003 liên tục |
| Màu ổn định theo loại | **VM** (PROMPT 07 + lượt này) | Mỗi loại một màu cố định; đảo thứ tự không đổi màu |
| VI / EN loại tài liệu | **VM** | 14 loại có nhãn VI và EN chuẩn (EN trước đây hiện chuỗi thô, lẫn "Conference Paper" / "Conference paper"); loại lạ hiện nguyên tên |
| KPI không đổi công thức | **VI** | API = SQL chỉ đọc trên DB A: `by_year` (20 năm, 2008–2027), `without_year` 0, 8 loại tài liệu, tổng 660 công bố, 2.751 vị trí tác giả, khớp hoàn toàn |
| Dữ liệu thật | **VI + VR** | 2008–2027 liên tục, không có ghi chú năm không hợp lệ |
| Import CSV thật | — | **NV**: cần ghi DB. Đề xuất chạy trên DB tạm dùng một lần (§6.3). |

### 6.3 Đề xuất policy (chưa triển khai, chờ duyệt)

**P-YEAR (năm bất thường)**
- Đề xuất: giữ hiển thị mọi năm hợp lệ theo DB. Nếu muốn coi năm "bất thường" (ví dụ > năm hiện tại + 1 vì bài in-press), nên thêm **cảnh báo ở bước kiểm tra import** (không loại dữ liệu) và cho phép ADMIN xem danh sách.
- Ngưỡng cần chủ đồ án chốt.
- Test case đề xuất:
  - CSV có Year = 2030 → import hợp lệ, có cảnh báo, Dashboard vẽ 2030.
  - Year trống → `without_year` tăng.
  - Year = 999 hoặc 10000 → bị từ chối ở validation với thông báo rõ.
  - Year chữ "2024a" → báo lỗi dòng.

**P-DOCTYPE (chữ hoa / thường)**
- Hiện trạng: backend nhóm `document_type` **phân biệt hoa thường** (`coalesce(document_type,'UNSPECIFIED')`). Mock cho thấy nếu dữ liệu có cả "Conference paper" và "Conference Paper" thì Dashboard hiện **2 dòng cùng nhãn "Bài báo hội nghị", cùng màu**.
- DB A hiện **không** có biến thể (SQL: 0).
- Đề xuất: chuẩn hóa ở backend (nhóm theo `lower()` hoặc chuẩn hóa lúc import). Đây là thay đổi API / backend, nên chỉ đề xuất.
- Test case: hai dòng CSV khác hoa thường → một nhóm, tổng đếm bằng nhau.

---

## 7. Variant còn thiếu trong Figma (cần bổ sung về sau)

| # | Variant | Lý do cần | Đề xuất |
|---|---|---|---|
| 1 | **Badge outline / bordered** cho thuộc tính và ngữ cảnh | Sau R2, trạng thái "Chờ duyệt" (warning) và ngữ cảnh "Còn 1 ứng viên khác" / "Có 3 ứng viên" (warning) trông **giống hệt**. Tương tự "Đã từ chối" và "Dùng chung (5 GV)" (danger). Trước R2 hai nhóm cũng cùng màu, nên không phải regression, nhưng người duyệt dễ nhầm. | **PR**: trạng thái = badge đặc (Figma). Thuộc tính / bằng chứng / ngữ cảnh = badge viền 1px cùng tông, nền trắng. Chưa triển khai. |
| 2 | Badge cỡ nhỏ trong bảng | `9:69` dùng px8, mâu thuẫn `5:34` px10 | Figma chốt một giá trị |
| 3 | Button **sm** primary / secondary | Figma chỉ có tonal sm (`9:72`) | Thêm vào `5:2` |
| 4 | Button **danger-outline** | "Thu hồi" (ManualReviewCard) đang tự định nghĩa | Thêm vào `5:2` |
| 5 | Trạng thái hover / focus / disabled / loading | Đang **PR** | Thêm frame state |
| 6 | Icon button / nút chỉ có icon | Header, bảng | Thêm |
| 7 | Filter chip (ví dụ "Bỏ lọc" Scopus ID ở `/publications`) | Chưa có | Thêm |
| 8 | Modal footer (AntD) và Select / Date input | `/reviews`, `/review-history` dùng AntD hoặc native | Thêm hoặc quyết định giữ AntD |

---

## 8. Màn hình chưa rollout

### R3: nút còn tự định nghĩa (đếm `<button` thô)

| File | Số nút |
|---|---|
| `Imports` | 25 |
| `Normalization/index` | 22 |
| `Lecturers` (còn lại) | 20 |
| `Normalization/AuthorsTab` | 7 |
| `ReviewHistory` | 6 |
| `AuditLogs` | 6 |
| `Header` | 6 |
| `AffiliationsTab` (còn lại) | 1 |
| `ManualReviewCard` (Thu hồi) | 2 |
| `Users` (mở form) | 2 |
| `Publications/Detail` | 4 |
| `Login` | 4 |
| `DuplicateImportDialog` | 3 |
| `ConfirmModal`, `TextConfirmModal` | 2 + 2 |
| `Search` | 2 |
| `LecturerDatasetImportCard` | 2 |
| `Profile`, `Identity`, `Toast` | 1 mỗi file |

Ngoài ra: AntD `Button` ở `/reviews` (Từ chối, Xác nhận đối sánh, OK / Hủy của modal).

**Ghi chú ngôn ngữ (không sửa trong lượt này):**
- Nhãn trạng thái không thống nhất giữa 2 trang: ACCEPTED "Đã xác nhận" (`/reviews`) và "Đã chấp thuận" (`/review-history`); PENDING "Chờ duyệt" và "Chờ xét duyệt".
- Enum thô vẫn hiển thị: modal ("ACCEPT" / "REJECT"), reconciliation (`DOI_EXACT`), rule_id, và empty state `/reviews` ("REJECTED: 2 · ACCEPTED: 3 · PENDING: 144").

### R4: component chung chưa có

- Data Table (`9:41`), Stat Card (`9:25`), Input (`9:9`).
- Thay 13 `rounded-2xl`, 13 `rounded-xl`, 31 `rounded-lg` và các `rounded-[5px]` bằng `rounded-card` / `rounded-control`.

**Hệ quả tạm thời:** card `/my-publications` đã là 10px, trong khi card Dashboard và các trang khác vẫn 5px cho tới R4.

---

## 9. Git status

**Stage (không đổi):** `.gitignore`, `CSV_ONLY_ACCEPTANCE_20261016.md`, `RELEASE_CANDIDATE_20261017.md`, `RELEASE_READINESS_20261017.md`.
- Blob: `fb176d6`, `853c832`, `3b03317`, `0c34a85`.
- `git diff --cached`: 4 file, +530.

**Unstaged**
- Xóa: `frontend/src/components/common/buttonStyles.ts`.
- Sửa — 6 file P1 đã nghiệm thu: `i18n` × 3 và `AuthorAffiliations` không đổi; `AffiliationsTab` chỉ thêm phần nút; `Dashboard/index` không đổi trong PROMPT 08.
- Sửa — pilot: `tailwind.config.js`, `Home`, `Dashboard/charts` × 3, `Publications/index`, `MyPublications`, `ApprovalQueue`.
- Sửa — PROMPT 08: `Lecturers`, `Users`, `ManualReviewCard`, `MatchingTab`, `ReviewHistory`.
- Sửa — khác: `.claude/launch.json` (cấu hình chạy cục bộ).

**Untracked**
- `frontend/src/components/ui/`: Button, Badge, reviewTones.
- 8 báo cáo QA ngày 17/10, trong đó có báo cáo này.
- `backend/scripts/create_csvonly_e2e_accounts.py`.

**Thao tác Git:** không stage, commit, tag, push, reset, rebase.

---

## 10. Đề xuất phạm vi PROMPT 09

1. **Quyết định trước khi code** (chủ đồ án):
   - Badge outline cho thuộc tính / ngữ cảnh (§7-1).
   - Policy P-YEAR và P-DOCTYPE (§6.3).
   - Thống nhất thuật ngữ trạng thái review giữa `/reviews` và `/review-history` (cần sửa i18n).
2. **R3a, rủi ro thấp:** `ConfirmModal`, `TextConfirmModal`, `DuplicateImportDialog` → `Button` (giữ `danger` cho hành động nguy hiểm); nút còn lại của `Lecturers`, `Users`, `ReviewHistory`, `AuditLogs`.
3. **R3b, cần cẩn trọng:** `Imports` (25 nút, luồng import / rollback) và `Normalization/index`. Kiểm thử trên DB restore với quyền ghi riêng nếu cần bấm thật.
4. **R2b (tùy quyết định ở mục 1):** AntD `Button` ở `/reviews`; nhãn thay enum thô.
5. **R4:** chỉ sau R3, dùng component Data Table / Stat Card / Input.

Mỗi đợt kiểm: `tsc` + build + CSS build, khởi động lại dev server, script trình duyệt 3 vai trò VI / EN desktop / mobile, fingerprint DB.

---

**Dừng tại đây** để chủ đồ án duyệt §6.3, §7 và §10.
