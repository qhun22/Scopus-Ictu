# Design System Foundation & Dashboard Quality — Pilot — Scopus-ICTU (17/10/2026)

**Trạng thái**
- Release `v1.0.0-rc.1`: **HOLD**.
- Đợt này dừng sau Pilot + Regression, chờ chủ đồ án duyệt rollout.

**Ràng buộc đã giữ**
- Không commit, tag, push, migration.
- Không ghi DB, không đổi backend.
- Không đổi handler, quyền hay công thức KPI.

**Hiện trạng Git**
- 4 file RC đã stage giữ nguyên blob: `fb176d6`, `853c832`, `3b03317`, `0c34a85`.
- 5/6 file frontend đã nghiệm thu trước đó giữ nguyên **byte-for-byte** so với patch nền.
- File thứ 6 là `Dashboard/index.tsx`: phần UI-02 vẫn giữ, chỉ thay nút và badge (xem §4).

**Mức bằng chứng**
- **FV** = FIGMA-VERIFIED: đọc từ file Figma `yctOa75eATXHnTQmesJy5A` bằng `get_metadata` / `get_design_context` trong phiên này.
- **PR** = PROPOSED: không có trong Figma, đề xuất để chủ đồ án duyệt.
- **VR** = runtime trên trình duyệt.
- **VS** = đọc code.

> Ghi chú truy cập Figma: dữ liệu Figma ở §1 đã lấy trong Phase A. Đến cuối phiên, MCP Figma yêu cầu xác thực lại, nên lượt này không chụp thêm ảnh Figma. §6 so sánh **giá trị đo trên trình duyệt** với **thông số FV**, không so ảnh với ảnh.

---

## 1. Design System Specification

### 1.1 Button — Figma "Buttons" (`5:2`), PageHeader (`10:52`), Data Table (`9:41`)

| Thuộc tính | Giá trị | Mức |
|---|---|---|
| Chiều cao | 36px | FV |
| Padding ngang | 16px | FV |
| Chữ | Saira SemiBold 13px | FV |
| Bo góc | Figma 6px. **Code giữ 5px** theo quyết định toàn dự án, chờ duyệt (§10) | FV / quyết định |
| Độ rộng | Mẫu 120px; PageHeader 140×36 nên là **min-width 120, co giãn theo nội dung**. Không áp 120 cố định. | FV (suy ra từ 2 node) |
| Primary | nền `#3A5FC3`, chữ trắng | FV |
| Secondary | nền trắng, viền 1.5px `#CBD5E1`, chữ `#334155` | FV |
| Danger | nền `#E11D48`, chữ trắng | FV |
| Ghost | nền `#F1F5F9`, chữ `#334155` | FV |
| Tonal sm (nút "Xem" trong bảng) | nền `#EBEFF9`, chữ `#3A5FC3`, 11px SemiBold, px10, bo 4px | FV (`9:41`) |
| Hover, focus ring, disabled (opacity 50%), loading spinner | — | **PR** |
| Kích thước `sm` cao 28px | Figma chỉ có padding py5 + 11px ≈ 26–28px | **PR** (gần FV) |

### 1.2 Badge — Figma "Status Badges" (`5:34`)

**Hình dạng (FV):** pill, cao 23px, px10, Saira Bold 11px, **không viền**.

| Tone | Nền / Chữ | Mức |
|---|---|---|
| success | `#ECFDF5` / `#047857` | FV |
| warning | `#FFFBEB` / `#B45309` | FV |
| danger | `#FFF1F2` / `#BE123C` | FV |
| info | `#ECFEFF` / `#0E7490` | FV |
| indigo | `#EEF2FF` / `#4338CA` | FV |
| neutral | `#F1F5F9` / `#475569` | FV |
| violet | `#F5F3FF` / `#6D28D9` | FV |
| brand | `#EFF6FF` / `#3A5FC3` | FV |

**Quy tắc nghiệp vụ:**
- Tone chỉ là màu. Ánh xạ trạng thái → tone do từng màn hình quyết định.
- Hai trạng thái cùng tone **không phải** cùng trạng thái. Ví dụ: REVIEW `ACCEPTED` (success) ≠ IDENTITY `VERIFIED`; AFFILIATION `MATCHED` ≠ `VERIFIED`.

### 1.3 Thành phần khác (đã đọc, chưa triển khai trong pilot)

| Thành phần | Thông số | Mức |
|---|---|---|
| Data Table (`9:41`) | header cao 40, nền `#F8FAFC`, chữ 11px SemiBold `#64748B` viết hoa; dòng cao 44, zebra `#F8FAFC`; badge trong bảng px8 (≠ px10 của `5:34`) | FV (có mâu thuẫn nội bộ Figma) |
| Stat Card (`9:25`) | bo 10, viền `#E2E8F0`, p20; nhãn 12 `#64748B`; giá trị 28 đậm có màu; dòng phụ 11 `#94A3B8`; khung ngoài bo 12 | FV |
| Search / Input (`9:9`) | 280×36, nền `#F8FAFC`, viền `#E2E8F0`, bo 6, px12, 13px | FV |

---

## 2. Figma – Frontend Component Matrix

| Figma | Frontend trước pilot | Sau pilot | Ghi chú |
|---|---|---|---|
| Button Primary | class rời rạc mỗi trang; `buttonStyles.ts` (`min-h-10 rounded-lg px-5 text-sm font-bold`) | `components/ui/Button` `variant="primary"` | `buttonStyles.ts` giữ nguyên (5 file ngoài pilot) |
| Button Secondary | viền `slate-200/300`, chữ `slate-700` | `variant="secondary"` (viền 1.5 `#CBD5E1`) | Lưu ý: `BUTTON_SECONDARY` cũ trong `buttonStyles.ts` thực chất là **tonal** của Figma |
| Button Danger | `#E50000` (buttonStyles), rose các nơi khác | `variant="danger"` `#E11D48` | |
| Button Ghost | transparent | `variant="ghost"` `#F1F5F9` | Chưa dùng trong pilot |
| Table action "Xem" | outline trắng | `variant="tonal" size="sm"` | |
| Status Badge | `ImportStatusBadge` tự định nghĩa màu; AntD `<Tag>` ở `/reviews`; pill có viền ở nhiều trang | `components/ui/Badge` `tone=…` | Pilot: import status (Dashboard), candidate status (`/reviews`, 3 vị trí) |
| AffiliationBadge (UX-01) | pill có viền, h23, 11px | **giữ nguyên** | Đã PASS; khác Figma ở viền → §10 |
| Data Table | nhiều kiểu header | chưa đổi | Rollout |
| Stat Card | `rounded-[5px]`, p≈16 | chưa đổi | Rollout, phụ thuộc quyết định bo góc |
| Search / Input | `/home` dùng `rounded-lg`, h≈40 | `/home`: `h-control rounded-control border-line bg-slate-50 text-[13px]` | Các trang khác: rollout |

---

## 3. Tokens (nguồn duy nhất: `frontend/tailwind.config.js`)

Không thêm CSS variables và không tạo nguồn token thứ hai.

| Token | Giá trị | Mức |
|---|---|---|
| `brand` / `brand-hover` / `brand-subtle` | `#3A5FC3` / `#2F4EA6` / `#EBEFF9` | FV / **PR** / FV |
| `ink` / `ink-body` / `ink-muted` / `ink-faint` | `#1E293B` / `#334155` / `#64748B` / `#94A3B8` | FV |
| `line` / `line-strong` | `#E2E8F0` / `#CBD5E1` | FV |
| `danger` / `danger-hover` | `#E11D48` / `#BE123C` | FV / **PR** |
| `rounded-control`, `rounded-card` | 5px (chờ quyết định 6 / 10) | quyết định dự án |
| `h-control`, `h-badge`, `min-w-action` | 36px, 23px, 120px | FV |

---

## 4. Pilot diff (so với HEAD `237f7bc`)

Patch đầy đủ nằm ngoài repo: `_postgres_demo_14_10/scratch/ds_pilot/pilot_full_vs_HEAD.patch`.

**File mới (untracked)**
- `components/ui/Button.tsx`:
  - 5 variant: primary, secondary, danger, ghost, tonal.
  - 2 size: md, sm.
  - Props `fullWidth`, `loading`, `icon`; mặc định `type="button"`; `forwardRef`; export thêm `buttonClass()`.
- `components/ui/Badge.tsx`: 8 tone Figma; truyền tiếp mọi thuộc tính HTML (`title`, `data-testid`).

**File sửa**

| File | Thay đổi | Handler / API |
|---|---|---|
| `tailwind.config.js` | Thêm tokens §3 | — |
| `Home/index.tsx` | Nút Tìm kiếm → `Button primary`; ô tìm kiếm dùng token (h36, nền `#F8FAFC`, 13px) | không đổi |
| `Dashboard/index.tsx` | Header xếp dọc trên mobile (sửa cắt chữ); Làm mới → `secondary` + `loading`; Reset → `danger`; nút "Thử lại" của biểu đồ → `secondary sm`; `ImportStatusBadge` → `Badge` (RECEIVED brand, PARSING indigo, VALIDATED info, STAGED warning, APPLIED success, FAILED danger, CANCELLED neutral) | không đổi; UI-02 giữ nguyên |
| `Dashboard/charts/PublicationsByYearChart.tsx` | DASH-01, DASH-02 (§7) | — |
| `Dashboard/charts/DocumentTypeDonutChart.tsx` | DASH-03 (§7); thêm nhãn VI cho Retracted, Conference Review, Data Paper | — |
| `Dashboard/charts/AffiliationCoverageChart.tsx` | DASH-04 (§7) | công thức không đổi |
| `Publications/index.tsx` | Xuất JSON → `secondary`; Áp dụng → `primary sm`; Đặt lại → `secondary sm`; Thử lại → `secondary sm`; Chi tiết → `tonal sm`; Trước / Sau → `secondary sm` | không đổi `onClick` / `disabled` |
| `MyPublications/index.tsx` | Thử lại, Trước, Sau → `secondary`; 10 × `rounded-2xl` → `rounded-card` | không đổi |
| `ApprovalQueue/index.tsx` | Trạng thái ứng viên ở 3 vị trí (danh sách, lịch sử ứng viên cùng giảng viên, "Trạng thái hiện tại") → `Badge` qua `STATUS_TONE` (PENDING warning, ACCEPTED success, REJECTED danger, SUPERSEDED neutral); xóa `STATUS_COLORS`, `STATUS_BADGE_CLASS`, `badgeClassName` vì không còn dùng | không đổi; nút AntD Chấp nhận / Từ chối giữ nguyên |

**Cố ý giữ nguyên**
- Chip "Bỏ lọc" (Scopus ID) ở `/publications`: chip lọc, không phải nút Figma.
- Pill bằng chứng / mơ hồ ở `/reviews`: cỡ h20 / 10px không có variant tương ứng trong Figma (§10).
- AntD `Button` ở `/reviews`.
- `buttonStyles.ts` và 5 file dùng nó.

---

## 5. Kết quả kiểm thử

### 5.1 Tĩnh

| Bước | Kết quả |
|---|---|
| `npx tsc --noEmit` | **PASS** (exit 0) |
| `npm run build` | **PASS** (exit 0). Cảnh báo chunk > 500 kB đã có từ trước. |
| Token có trong CSS build | `.h-control`, `.rounded-control`, `.bg-brand`, `.min-w-action`, `.h-badge`, `.border-line-strong`, `.bg-danger`: có đủ |

### 5.2 Trình duyệt

**Phạm vi chạy**
- Script `scratch/ds_pilot/ui_ds_pilot_cdp_20261017.py`; kết quả ở `results_ds_pilot.json` và `shots/` (23 ảnh).
- Môi trường A: 5199 → 8199 → `scopus_ictu_test_withjson_r2_20261011`.
- Chrome headless; desktop 1440×900 và mobile 375×812.
- Đăng nhập bằng tài khoản TEST `withjson.*` theo quyền chủ đồ án đã cấp (PROMPT 05). Giá trị không in, không lưu.

**Sự cố phát hiện trong lượt 1 (đã xử lý)**
- Triệu chứng: dev server 5199 vẫn phục vụ CSS sinh từ cấu hình Tailwind **cũ** (Tailwind v3 nạp config khi khởi động). Đo được: nút cao 15–24px, bo 0px, nền trong suốt; nút "Reset hệ thống" chữ trắng trên nền trắng.
- Xử lý: khởi động lại dev server frontend 5199 và 5399 (không đụng backend / DB). Lượt 2 và 3 đo đúng.
- **Bài học cho demo:** mỗi lần sửa `tailwind.config.js` phải khởi động lại dev server.

| Vai trò | Màn hình | VI | EN | Mobile | Loading / Empty / Error | Kết quả |
|---|---|---|---|---|---|---|
| ADMIN | `/home` | ✓ | — (không đổi i18n) | ✓ (nút full-width 313px) | — | **PASS** |
| ADMIN | `/dashboard` | ✓ | ✓ | ✓ header 2 nút không cắt chữ, overflowX 0 | Error biểu đồ (chặn URL phía trình duyệt): nút Thử lại `secondary sm`. Loading không đổi cơ chế nên không chạy lại. | **PASS** |
| ADMIN | `/publications` | ✓ | ✓ | ✓ (bảng cuộn trong khung, overflowX trang = 0) | Error: Thử lại `secondary sm` | **PASS** |
| REVIEWER | `/home`, `/publications` | ✓ | — | — | — | **PASS** |
| REVIEWER | `/reviews` (danh sách + chi tiết) | ✓ | ✓ ("Pending review") | ✓ | — | **PASS** |
| LECTURER (chưa liên kết) | `/home`, `/my-publications` | ✓ | ✓ | ✓ | Empty "Tài khoản chưa được liên kết" + Thử lại; Error mạng + Thử lại | **PASS** |

**Bảo đảm chỉ đọc (VR)**
- 0 request không phải GET (ngoài login); 0 lỗi console.
- Lỗi API duy nhất là 403 `/lecturers/me/publications` của giảng viên chưa liên kết: hành vi đúng, có từ trước.
- Fingerprint DB A và DB restore trước = sau (**IDENTICAL**); DB A = snapshot nguồn `fingerprint_demoA_source_20261017.json`.
- Quét 13 tệp bằng chứng: 0 giá trị bí mật.
- Profile Chrome tạm đã xóa; không còn tiến trình headless.

**Dương tính giả:** "REJECTED" ở Dashboard EN là nhãn "Rejected" hiển thị chữ hoa do CSS `uppercase`, không phải enum thô.

**Không kiểm được trong lượt này**
- `/my-publications` có dữ liệu và phân trang (cần giảng viên đã liên kết). Trên môi trường A, tài khoản TEST LECTURER chưa liên kết. Tài khoản đã liên kết chỉ có trên DB restore, và quyền đã cấp cho tài khoản đó thuộc phạm vi TC-W1 / TC-W2 (PROMPT 06). Vì vậy lượt này **không** dùng.
- Nút phân trang dùng chung component với nút Thử lại đã đo (cùng variant `secondary`).

---

## 6. So sánh Figma (thông số FV) với đo thực tế (VR)

| Thành phần | Figma | Đo được | Đánh giá |
|---|---|---|---|
| Primary (Tìm kiếm `/home`) | 36h, ≥120w, `#3A5FC3`, 13px SemiBold | 120×36, `rgb(58,95,195)`, 13px / 600 | Khớp (bo 5 thay vì 6, §10) |
| Secondary (Làm mới, Xuất JSON, Thử lại `/my-publications`) | trắng, viền 1.5 `#CBD5E1`, chữ `#334155` | 36h, nền trắng, chữ `rgb(51,65,85)`; viền tính ra 1px ở DPR 1 (Chrome làm tròn 1.5px; DPR 2 hiển thị 1.5) | Khớp |
| Danger (Reset hệ thống) | `#E11D48` chữ trắng | `rgb(225,29,72)`, 156×36 | Khớp |
| Tonal sm (Chi tiết) | nền `#EBEFF9`, chữ `#3A5FC3`, 11px | 58×28, `rgb(235,239,249)` / `rgb(58,95,195)`, 11px | Khớp (bo 5 thay vì 4) |
| Badge import (Đã áp dụng) | `#ECFDF5` / `#047857`, h23, không viền | 78×23, đúng màu, viền 0 | Khớp |
| Badge review (Chờ duyệt / Pending review) | `#FFFBEB` / `#B45309`, h23, px10 | 72×23 (EN 100×23), đúng màu, px10, viền 0 | Khớp |
| Độ rộng nút | min 120, co theo nội dung | md: 120 / 129 / 156 / 170; sm co theo nội dung (46–83) | Đúng quy tắc, không cố định 120 |

Ảnh minh họa:
- `A_home_VI`, `A_dash_VI`, `A_dash_mobile_header`
- `A_pub_VI`, `A_pub_EN`, `A_pub_mobile`, `A_pub_error`
- `R_reviews_VI`, `R_reviews_mobile`
- `L_mypub_VI`, `L_mypub_EN`, `L_mypub_error`

---

## 7. Dashboard edge cases

**Cách kiểm**
- Dữ liệu thật: DB A.
- Dữ liệu biên: dựng bằng cách giả lập phản hồi `GET /api/v1/dashboard/charts` **chỉ trong trình duyệt** (CDP `Fetch.fulfillRequest`), không ghi DB.

| ID | Vấn đề | Cách xử lý (frontend, không đổi API / công thức) | Kết quả |
|---|---|---|---|
| DASH-01 | Năm không có công bố bị bỏ qua làm trục năm "nhảy" | `buildYearSeries` lấp năm trống bằng 0 trong khoảng [năm nhỏ nhất, năm lớn nhất] | **PASS**: dữ liệu biên 2016, 2019, 2020, 2024 hiển thị đủ 2016…2024, các năm 2017–2018 và 2021–2023 bằng 0 (VI / EN). Dữ liệu thật 2008–2027 liên tục, không đổi. |
| DASH-02 | Năm bất thường (0, 2099) kéo giãn trục | Năm < 1900 hoặc > năm hiện tại + 2 không vẽ lên trục. Có dòng ghi chú số công bố và năm bị loại (`data-testid=year-outliers-note`). Đây là quy tắc **hiển thị**, không phải quy tắc import. | **PASS**: "3 công bố có năm ngoài khoảng 1900–2028 (0, 2099) nên không được vẽ trên trục năm." / EN tương ứng. Dữ liệu thật có 1 công bố năm 2027, vẫn trong khoảng nên được vẽ, không có ghi chú. |
| DASH-03 | Màu theo thứ hạng nên đổi khi số liệu đổi; chỉ có 7 màu | `TYPE_COLOR` gắn theo loại (không phân biệt hoa thường); 7 loại đầu giữ màu cũ; thêm Editorial, Book, Letter, Short Survey, Conference Review, Data Paper, Unspecified; loại lạ dùng bảng màu dự phòng | **PASS**: 10 loại (gồm "Mystery Type") đều khác màu. Đảo thứ tự dữ liệu thì mỗi loại **giữ nguyên màu**. |
| DASH-04 | Nhãn "Có / Chưa có đơn vị công tác" gây hiểu nhầm là đã xác nhận nơi công tác | Nhãn mới "Có / Chưa có thông tin đơn vị" (EN "Has / No affiliation information"). Chú thích nêu đúng quy tắc backend: VERIFIED hoặc CORROBORATED + PRESENT, "chưa phải xác nhận đơn vị công tác". Thêm "Mức đối chiếu theo vị trí tác giả" từ `by_link_status` (đã có trong API), dùng **đúng nhãn** `statusLabel` của AffiliationBadge. | **PASS**: 2.291 / 460 (83%) không đổi; phân bố 545 / 2.053 / 153 (VI / EN). Dòng "Chưa đối chiếu" chỉ hiện khi tổng − (V + C + U) > 0; hiện bằng 0 nên ẩn. |

Ghi chú DASH-03:
- Màu "Chương sách" (`#1D9E75`) trùng màu "Có thông tin đơn vị" của biểu đồ bên cạnh.
- Hai biểu đồ độc lập, có chú giải riêng, nên chấp nhận được. Nếu muốn tách màu, cần quyết định ở rollout.

---

## 8. UI backlog còn lại (không sửa trong đợt này)

| ID | Mô tả | Ghi chú |
|---|---|---|
| W-02 | Lỗi nghiệp vụ đã ghi nhận trước | Phương án riêng, không mở rộng phạm vi |
| W-03 / W-05 / W-06 | Đã ghi nhận ở báo cáo trước | Như trên |
| `/imports` | Bảng tràn ngang trên mobile | Rollout Data Table |
| UI-13 | Header "Hệ thống" | |
| UI-14 | Khóa 3 giây khi đổi ngôn ngữ (`TRANSITION_DURATION_MS`) | |
| UI-15 | EN vẫn hiện "Chưa cập nhật" ở một số trang (theo báo cáo trước) | Riêng `/publications` EN đã hiển thị đúng "Not available" (`A_pub_EN`) |
| Mới | Thẻ người dùng ở header vẫn hiện tên vai trò VI ("Quản trị viên") khi đang ở EN | Thấy trong `A_pub_EN`; gộp với UI-13 |
| UI-18 | Thuật ngữ chưa thống nhất | VI "Reset hệ thống" (`vi.ts:741`) vẫn trộn tiếng Anh |
| `/tasks` | Placeholder | |
| `/reviews` | AntD `Button` / `Tag` còn lại: rule_id, reconciliation, ACCEPT / REJECT trong modal, name variants. Pill bằng chứng / mơ hồ h20 / 10px có viền. Nút "Xem chi tiết" khác kiểu "Chi tiết" ở `/publications`. | Sau pilot, trong một dòng có badge trạng thái kiểu Figma (không viền) đứng cạnh pill cũ (có viền). Cần rollout đồng bộ. |
| `/publications` | Bảng EN rộng hơn khung 6px (1112 so với 1106), cuộn được, không cắt | Độ rộng cột |
| Khác | `rounded-2xl` 13, `rounded-xl` 13, `rounded-lg` 31 vị trí còn lại | Rollout bo góc |

---

## 9. Git status (sau pilot)

**Stage (không đổi):**
- `.gitignore`
- `docs/qa/CSV_ONLY_ACCEPTANCE_20261016.md`
- `docs/qa/RELEASE_READINESS_20261017.md`
- `docs/qa/RELEASE_CANDIDATE_20261017.md`

**Unstaged:**
- 6 file đã nghiệm thu: `i18n/locales/vi.ts`, `en.ts`, `types.ts`, `Normalization/AffiliationsTab.tsx`, `Publications/AuthorAffiliations.tsx`, `Dashboard/index.tsx`. Năm file đầu không đổi; `Dashboard/index.tsx` có thêm thay đổi pilot.
- Pilot: `tailwind.config.js`, `Home/index.tsx`, `Dashboard/charts/*` (3 file), `Publications/index.tsx`, `MyPublications/index.tsx`, `ApprovalQueue/index.tsx`.
- `.claude/launch.json` (cấu hình chạy cục bộ).

**Untracked:**
- `frontend/src/components/ui/` (Button, Badge).
- 6 báo cáo QA ngày 17/10 cùng báo cáo này.
- `backend/scripts/create_csvonly_e2e_accounts.py`.

**Thao tác Git:** không commit, tag, push, reset, rebase; không tự stage. Line ending của các file sửa giữ đúng như HEAD.

---

## 10. Phạm vi rollout đề xuất (chờ duyệt) và điểm cần quyết định

### 10.1 Quyết định cần chủ đồ án chốt (STOP)

1. **Bo góc.** Figma: nút / input 6px, card 10px, khung 12px, action trong bảng 4px. Dự án đang dùng 5px toàn bộ.
   - Đề xuất A: giữ 5px (không đổi gì).
   - Đề xuất B: theo Figma qua token `rounded-control` = 6, `rounded-card` = 10.
   - Đổi một chỗ trong `tailwind.config.js` là áp dụng cho mọi nơi đã dùng token.
2. **Viền badge.** Figma không có viền. AffiliationBadge (UX-01, đã PASS) và pill ở `/reviews` có viền. Giữ hay bỏ?
3. **Badge trong bảng.** Figma `9:41` dùng px8 nhưng `5:34` dùng px10; `/reviews` có pill h20 / 10px. Figma **chưa có** variant badge nhỏ, nên cần Figma bổ sung hoặc duyệt variant `size="sm"` (**PR**).
4. Hover / focus / disabled / loading của Button là **PR**: cần duyệt.
5. Nút "Áp dụng" ở `/publications` đổi từ viền trung tính sang **primary** (hành động chính của bộ lọc). Cần xác nhận.

### 10.2 Rollout theo đợt (đề xuất)

| Đợt | Phạm vi | Rủi ro |
|---|---|---|
| R1 | 5 file dùng `buttonStyles.ts` (Lecturers, Users, AffiliationsTab, ManualReviewCard, MatchingTab): chuyển sang `Button`, rồi xóa `buttonStyles.ts`. `BUTTON_SECONDARY` cũ ánh xạ sang `tonal`. | Thấp. AffiliationsTab thuộc 6 file đã nghiệm thu nên chỉ đổi phần nút. |
| R2 | `/reviews`: pill bằng chứng / mơ hồ sang `Badge` (sau quyết định 10.1-3); "Xem chi tiết" sang `tonal sm`; AntD Tag còn lại. AntD Button trong modal quyết định giữ hay thay. | Trung bình (luồng Chấp nhận / Từ chối, không đổi handler) |
| R3 | Imports (25 nút), Normalization (22), Lecturers (22), AuthorsTab, ReviewHistory, AuditLogs, Users, Publications/Detail, Login, Search, ConfirmModal / TextConfirmModal / DuplicateImportDialog | Trung bình. Modal xác nhận nguy hiểm cần giữ `danger`. |
| R4 | Data Table (`9:41`), Stat Card (`9:25`), Input (`9:9`) thành component dùng chung; bo góc `rounded-*` còn lại | Phụ thuộc quyết định 10.1-1 |

**Mỗi đợt:**
- Kiểm `tsc` và build.
- Chạy lại script trình duyệt cho 3 vai trò, VI / EN, desktop / mobile.
- So fingerprint DB.
- Khởi động lại dev server sau khi đổi token.

---

**Dừng tại đây** để chủ đồ án duyệt các quyết định §10.1 và phạm vi rollout §10.2.
