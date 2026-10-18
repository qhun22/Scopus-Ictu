# Pre-Release Quality Review — Scopus-ICTU (17/10/2026)

Lượt **AUDIT chỉ đọc**. Không sửa code/cấu hình, không ghi DB, không stage/commit/tag/push.
Mức bằng chứng: **VR** = VERIFIED-RUNTIME · **VS** = VERIFIED-STATIC · **RO** = REPORTED-ONLY · **NV** = NOT-VERIFIED · **BL** = BLOCKED.

---

## A. Executive Summary

**Mức sẵn sàng:** nghiệp vụ lõi và phân quyền đã có bằng chứng tốt.
- **VR** ngày 17/10: ma trận API 3 vai trò; Accept/Reject qua API + DB + audit; provenance dữ liệu offline khớp SHA-256; 1047 test pass; build PASS.

**Vẫn còn hai khoảng trống lớn:**
1. **UI thực tế theo từng tác nhân chưa kiểm được trong lượt này.**
   - Hai lần mời đăng nhập trong Browser pane đều không tạo được phiên: backend 8199 không nhận request đăng nhập nào từ trình duyệt. Phần UI có đăng nhập vì vậy là **BL**.
   - Bằng chứng UI hiện có đều là **RO**: các lượt 15–16/10, chạy trên môi trường khác (DB `csvonly`/`withjson_r2`).
2. **Design system chưa thống nhất với Figma ở mức component (VS):**
   - Không có component Badge dùng chung.
   - Badge trong code bo 4px, còn Figma là pill.
   - Nút chuẩn cao 40px / 14px bold, còn Figma 36px / 13px SemiBold; `buttonStyles` chỉ được 5/28 file dùng.
   - Bo góc 5px là giá trị cứng ở 349 chỗ, nhưng khu vực LECTURER vẫn 16px.

**Không phát hiện BLOCKER nghiệp vụ hay bảo mật.** Biểu đồ theo năm **tự cập nhật** khi có năm mới, không cần sửa code (mục D).

**Khuyến nghị:** **giữ release ở trạng thái chờ** (không tag `v1.0.0-rc.1`) cho tới khi:
- (1) có ít nhất một lượt UI E2E thật cho 3 tác nhân (kể cả LECTURER đã liên kết) trên môi trường A;
- (2) chủ đồ án quyết định phạm vi sửa design system (đợt 3, mục I).

4 file đã stage vẫn nguyên vẹn; nên commit chúng **sau khi** cập nhật kết luận theo audit này.

## B. Environment Matrix (VR ngày 17/10)

| | Môi trường A (demo chính thức) | Launcher chính thức | Môi trường C (CSV-only) | DB teacher |
|---|---|---|---|---|
| Frontend | Vite dev **5199** (lắng nghe `[::1]`; `localhost`/`[::1]` dùng được, `127.0.0.1:5199` không) — đang chạy | Vite dev **5173** (`127.0.0.1`) — **đang chạy nhưng mồ côi** | 5299 — tắt | — |
| Proxy → backend | `VITE_API_PROXY_TARGET=http://127.0.0.1:8199` | `…:8001` → **ECONNREFUSED** từ 05:21 (log `frontend.log`); `/api/v1/auth/me` qua 5173 trả **500** | 8299 | — |
| Backend | uvicorn **8199** (PID 26972), cấu hình `backend/.env` — đang chạy | uvicorn **8001** khởi động 05:04 17/10 bởi launcher, **đã dừng** (PID 3524 không còn; log dừng ~05:09, không có dòng shutdown) | 8299 — tắt | không có code tương thích |
| DB | `scopus_ictu_test_withjson_r2_20261011` (xác minh bằng `pg_stat_activity` theo client port) | `scopus_ictu_app` | `scopus_ictu_test_csvonly_20261011` | `scopus_ictu_demo_teacher_20261014` |
| Alembic | `c7f2a9b1d3e5` (HEAD) | `c7f2a9b1d3e5` — launcher **tự `alembic upgrade head`** | HEAD | `a9c2e4f71b30` |
| Code | `Scopus-Ictu` @ `237f7bc` (working tree = baseline về code) | cùng | cùng | — |
| Dữ liệu | 410 GV · 660 bài · 1.207 tác giả · 2.751 vị trí · offline 217 tổ chức / 4.147 dòng đơn vị · 144/3/2 ứng viên · 3 identity | 0 GV · 660 bài · trực tuyến 300 DOI (106/1.709) · chỉ 3 ADMIN | 0 GV · online 300 DOI | 411 GV · offline · 40 PENDING |
| Đọc / ghi | Đọc tự do; ghi chỉ khi có phê duyệt | Không ghi (App DB) | Ghi TEST được | **Không chạy, không migrate** |
| Backup trạng thái hiện tại | **Không có** (dump `withjson_*` đều ngày 12/10, trước Craw/matching và các quyết định 14/10, 17/10) | dump đến 11/10 | — | dump 09–10/10 |

**5173 và 5199 KHÔNG tương đương:** cùng mã nguồn frontend nhưng khác backend, khác DB và khác dữ liệu. Ảnh chủ đồ án chụp ở `127.0.0.1:5173` là App DB (không có giảng viên/REVIEWER/LECTURER), và tại thời điểm audit backend phía sau đã tắt.
Cả hai đều là **Vite dev server** (HMR), không phải bản build production.

## C. Actor Acceptance Matrix

Trong lượt này UI có đăng nhập là **BL**: chủ đồ án đăng nhập hai lần nhưng backend 8199 không nhận request `POST /auth/login` nào từ trình duyệt; tab vẫn ở `/login`. Bằng chứng API là VR ngày 17/10 (script chỉ đọc, không gọi export).

### C.1 Chung (chưa đăng nhập) — VR
| Kịch bản | Kết quả |
|---|---|
| Truy cập `/dashboard`, `/reviews`, `/publications/{eid}`, route không tồn tại khi chưa đăng nhập | Chuyển về `/login` ✅ |
| Trang đăng nhập 375px | Không tràn ngang, `label[for]` gắn đúng `#email`/`#password` ✅ |
| Sau khi đăng nhập | Luôn về `/home` (`Login/index.tsx:77`); **deep link bị mất** (VS) |
| Trang đăng nhập | Không có công tắc VI/EN (có chủ ý); placeholder mật khẩu `••••••••` trông như đã điền (VR, ảnh chụp) |

### C.2 ADMIN
| Route / chức năng | Kịch bản | Kết quả | Mức | Vấn đề / vị trí |
|---|---|---|---|---|
| Phân quyền route | `RoleRoute` ADMIN cho dashboard/imports/normalization/lecturers/users/audit-logs/tasks | Khớp ma trận API 401/403 | VS + VR(API) | `App.tsx:108-115` |
| `/dashboard` | KPI + 3 biểu đồ | API: 660/410/1.207/144; charts 20 năm, 8 loại tài liệu, 2.291/2.751 vị trí có đơn vị | VR(API) · UI BL | DASH-01, DASH-04 |
| Loading / error / empty Dashboard | Có spinner, lỗi + nút thử lại, rỗng từng biểu đồ, ghi chú công bố không có năm | Có đủ nhánh | VS | `Dashboard/index.tsx:286-369` |
| `/publications`, chi tiết | Bài mẫu, thứ tự tác giả, bằng chứng ORCID, truy vết CSV | Đúng | VR(API) · UI RO (16/10) | — |
| `/imports`, `/normalization` | Nhập/chuẩn hóa/đơn vị | UI RO (11/10, 16/10) | RO | Không thao tác ghi trong lượt này |
| `/lecturers`, `/users` | Danh sách 410, quản lý tài khoản | API 200 | VR(API) · UI NV | `/users` không có trong sidebar (truy cập từ trang Giảng viên) |
| `/audit-logs` | Đọc audit | API 200 | VR(API) · UI NV | — |
| `/tasks` | Trang placeholder trong menu ADMIN | — | VS | UX-07 |
| VI/EN | — | RO một phần (15–16/10) | RO | — |

### C.3 REVIEWER
| Route / chức năng | Kịch bản | Kết quả | Mức | Ghi chú |
|---|---|---|---|---|
| Phân quyền | `/reviews`, `/review-history` (REVIEWER+ADMIN); 403 ở dashboard/users | Đúng | VR(API) + VS | `App.tsx:98-104` |
| Hàng đợi | 144 PENDING; `/reviews/context = HAS_CANDIDATES` | Đúng | VR(API) | UI BL |
| Bằng chứng / mơ hồ / Scopus ID dùng chung | API detail có `name_evidence`, `publication_evidence`, `ambiguity`, `is_shared_scopus_author` | Có | VS + VR(API ngày 17/10) | UI hiển thị: RO (14/10, trước khi viết lại i18n) |
| Accept/Reject | Khóa phiên bản `candidate_version`, gửi lặp → idempotent, audit + tạo identity | Đúng | VR(API, DB, audit ngày 17/10) | **Chưa xem trên UI** sau commit `1aaf513` (viết lại 398 dòng, chỉ đổi chuỗi theo VS) |
| Xác nhận thao tác | `setDecisionAction("ACCEPT"/"REJECT")` mở hộp thoại quyết định trước khi gửi | Có bước xác nhận | VS | `ApprovalQueue/index.tsx` |
| Lịch sử | `/reviews/history` = 5 | Đúng | VR(API) | Badge xem UX-01 |
| Gợi ý ≠ định danh | Ứng viên (`lecturer_scopus_candidates.status`) tách khỏi identity (`APPROVED`) | Đúng | VS | — |

### C.4 LECTURER
| Trạng thái | Kịch bản | Kết quả | Mức |
|---|---|---|---|
| Chưa liên kết (`withjson.viewer`) | Công bố/tra cứu 200; `/lecturers/me/*` → 403 `LECTURER_NOT_LINKED`; review/dashboard 403 | Đúng | VR(API) · UI RO (16/10: "Tài khoản chưa được liên kết", EN đúng) |
| **Đã liên kết** (`vu.duc.quang.test`, TS. Vũ Đức Quang: 1 identity APPROVED, 27 công bố — VS từ DB) | Hồ sơ / Công bố của tôi / Liên kết Scopus | **BL**: không có quyền đăng nhập tài khoản này | BL |
| Giao diện | `MyPublications`/`Profile`/`Identity` dùng `rounded-2xl` (16px), lệch với phần còn lại (5px) | Lệch thiết kế | VS (UX-02) |

**Kết luận C:** *không* được ghi PASS UI cho bất kỳ tác nhân nào trong lượt này. Không dùng tài khoản LECTURER chưa liên kết để kết luận cho toàn bộ LECTURER.

## D. Dashboard & Future-Year Audit (VS + VR dữ liệu)

**"Năm 2028, 2029, 2030 có công bố mới thì hệ thống tự cập nhật không?" → CÓ, không cần sửa code**, với các điều kiện và lưu ý bên dưới.

**Đường đi dữ liệu:**
1. CSV cột `Year` → `raw_scopus_records.raw_payload`.
2. Chuẩn hóa: `_raw_int()` = `int(float(str(val).strip()))`, lỗi → `NULL` (`scopus_normalizer.py:309-319, 372`).
3. `publications.year` (`Integer`, nullable, **không có CHECK miền giá trị** — `models/publication.py:66`).
4. `GET /api/v1/dashboard/charts` (ADMIN) → `get_dashboard_charts()`: `SELECT year, count(*) … WHERE year IS NOT NULL GROUP BY year ORDER BY year` (`dashboard_queries.py:105-117`). Đếm `publications` (mỗi EID 1 dòng, EID unique, nên không đếm trùng). Không filter, không cache, không hardcode năm.
5. Frontend: `getDashboardCharts()` gọi **một lần khi mount** (`Dashboard/index.tsx:116-148`) → `PublicationsByYearChart`: `labels = data.map(d => String(d.year))` trên **`CategoryScale`**, `autoSkip:false`, `maxRotation:45`, cao 260px.

| Trường hợp | Hành vi | Đánh giá |
|---|---|---|
| Có thêm 2028/2030 | Xuất hiện sau khi nhập + chuẩn hóa, và **mở lại / F5** trang | ✅ |
| Chỉ có 2025 | 1 cột | ✅ |
| Năm trống ở giữa (vd 2028 rồi 2030) | API không trả 2029 → trục X **nhảy cóc**, 2028 và 2030 nằm liền nhau | ⚠️ DASH-02 (tiềm ẩn: dữ liệu hiện tại liên tục 2008–2027) |
| DB rỗng | Hiện "empty" riêng cho từng biểu đồ | ✅ VS (UI DB rỗng: **M2 chưa có bằng chứng**) |
| Không có năm | Bị loại khỏi biểu đồ, ghi chú số lượng riêng | ✅ |
| Năm bất thường (0, 9999, "2025.7" → 2025) | Được chấp nhận và vẽ thành cột | ⚠️ DASH-03 |
| 10–20 năm | Hiện tại 20 nhãn, xoay 45° | ✅; với 30+ năm trên màn hình hẹp sẽ chật (không autoSkip) |
| VI/EN | Nhãn tooltip/aria theo `locale` | ✅ VS |
| Năm 2027 | Dữ liệu thật có 1 bài 2027 (bài in trước) — không phải giới hạn của code | ✅ |

**Các KPI khác (VS + VR API trên A):**
- `total_publications` = 660 (bài).
- `total_scopus_authors` = 1.207 (**tác giả Scopus duy nhất**).
- `total_lecturers` = 410 (**giảng viên ICTU**, đếm cả không hoạt động; `active_lecturers` tách riêng).
- `pending_review_count` = 144 (ứng viên chờ duyệt hợp lệ hiện hành).
- Độ phủ đơn vị tính trên **2.751 vị trí tác giả** (không phải 5.502 dòng resolution = 2.751 × 2 nguồn). Mỗi vị trí lấy trạng thái tốt nhất: VERIFIED 545 · CORROBORATED 2.053 · UNRESOLVED 153.
- "Có đơn vị" = vị trí có resolution VERIFIED/CORROBORATED **và** `affiliation_presence='PRESENT'` = 2.291.

**Vấn đề:**
- **DASH-01:** biểu đồ gọi nhóm này là **"Có đơn vị công tác"**, trong khi phần lớn là CORROBORATED (đối chiếu, chưa xác minh) và là *đơn vị ghi trên bài báo theo nguồn ngoài*, không phải đơn vị công tác của giảng viên. `by_link_status` có trong API nhưng **không được hiển thị** (`types/dashboard.ts:53`, không dùng ở đâu).
- **DASH-04:** `PALETTE` 7 màu cho 8 loại tài liệu → loại thứ 8 trùng màu loại thứ 1 (`DocumentTypeDonutChart.tsx:8,43`).

**Sẵn sàng vận hành dài hạn:** **Tốt** về động / không hardcode; cần sửa DASH-02 (lấp năm trống) và cân nhắc DASH-03 (chặn năm vô lý lúc chuẩn hóa).

## E. Figma–Frontend Gap Matrix

Figma `yctOa75eATXHnTQmesJy5A`, đọc trực tiếp ngày 17/10 bằng `get_metadata` (VS). Thông số màu/radius/font chữ lấy từ báo cáo `FIGMA_DASHBOARD_COMPONENT_ALIGNMENT.md` (RO, đã đọc `get_design_context` ngày 15/10).

| # | Figma node / variant | Thông số Figma | React / CSS hiện tại | Khác biệt | Lý do | Ảnh hưởng | Đề xuất | Phạm vi sửa tối thiểu |
|---|---|---|---|---|---|---|---|---|
| E1 | `5:2` Buttons: Primary/Secondary/Danger/Ghost | **120×36** mọi nút (VS); `rounded 6px`, Saira SemiBold 13px, `px 16` (RO) | `buttonStyles.ts`: `min-h-10` (40px), `rounded-lg` (8px), `px-5` (20px), `text-sm font-bold`; chỉ **5/28 file** dùng; **158 `<button>` viết tay** | cao +4px, radius 8 ≠ 6 ≠ 5 (quyết định 5px), font 14 bold ≠ 13 semibold; không có min-width 120 | Chưa đồng bộ khi chốt 5px | Cao (mọi màn hình) | Chủ đồ án chốt: 36px hay 40px; 5px hay 6px | Sửa `BASE` trong `buttonStyles.ts` + chuyển dần các nút chính sang helper |
| E2 | `5:34` Status Badges (12 mẫu) | Pill `9999px` (RO); **cao 23, padding ngang 10, rộng theo nội dung 37–90px** (VS) | Không có component chung. `ActionBadge`/`StatusBadge` (`ReviewHistory:61,78`): `rounded` 4px, 11px, px 6; `ImportStatusBadge` (`Dashboard:571`): 4px, 12px medium, px 8, không viền; `AffiliationBadge` (`AuthorAffiliations:109`): 4px border, 10–11px bold; `/reviews` dùng AntD `Tag`; 87 `rounded-full` khác | **Hai hình dạng** (4px và pill), 4 cỡ chữ, 3 kiểu viền | Mỗi trang tự viết | Cao (Reviews, Lịch sử, Dashboard, Công bố, Search) | Một `<Badge tone size>` dùng chung | Tạo component + thay 5 điểm chính |
| E3 | `9:9` Search Input | `#f8fafc`, `rounded 6px`, border `#e2e8f0` (RO) | Input viết tay từng trang | NV từng trang | — | Trung bình | Kiểm khi có UI | — |
| E4 | `9:22`/`9:25` Stat Card | `rounded 10px`, padding 20, giá trị 28px bold `#3a5fc3` (RO) | KPI card Dashboard dùng `rounded-[5px]` (quyết định 5px) | radius 10 → 5 | **Quyết định chủ đồ án (5px)** — Figma lỗi thời | Thấp | Cập nhật Figma theo 5px | Figma |
| E5 | `10:2` Sidebar | Có mục "Thống kê" (RO) | Không có; `/dashboard` = "Tổng quan" | Lệch cấu trúc | Chưa quyết định | Thấp | Đổi tên Figma hoặc bỏ mục | Figma |
| E6 | Radius toàn cục | 6 / 9999 / 10 | `rounded-[5px]` **349 lần (giá trị cứng, không token)**; còn `rounded-2xl` 23 (MyPublications/Profile/Identity/Login), `rounded-xl` 13 (Users, LecturerDatasetImportCard), `rounded-lg` 34 | Khu vực LECTURER và Users lệch | Commit 3c31d6f/7de955c bỏ sót | Trung bình–cao | Token `--radius` / `theme.borderRadius` | Thêm token + thay 3 trang LECTURER |
| E7 | `28:11`, `28:17` Empty/Loading | Có symbol (RO) | Spinner + chữ "Đang tải…", empty viết tay từng trang | NV | — | Thấp | Đọc `get_design_context` khi sửa | — |
| E8 | Modal | Không có node riêng trong `3:3` (RO) | `ConfirmModal`/`TextConfirmModal` dùng chung + AntD Modal ở `/reviews` | Hai hệ modal | Lịch sử | Trung bình | Chọn 1 | — |

**Phản biện yêu cầu "badge cùng nhóm phải đồng chiều rộng":** Figma **không** quy định chiều rộng cố định. Status badge trong Figma rộng theo nội dung (37–90px), chỉ cố định chiều cao 23 và padding 10. Vì vậy quy tắc đề xuất:
- (a) badge dùng `inline-flex h-[23px] px-2.5 rounded-full` + cỡ chữ thống nhất, chiều rộng theo nội dung;
- (b) **chỉ trong cột bảng trạng thái** mới thêm `min-width` theo nhãn dài nhất của nhóm đó. Đây là **PROPOSED**, không phải thông số Figma; cần chủ đồ án quyết định và cập nhật Figma nếu áp dụng.

**Component Specification (PROPOSED trừ chỗ ghi VS):**

| Nhóm | Kích thước | Radius | Chữ | Padding | Trạng thái | Responsive / VI-EN |
|---|---|---|---|---|---|---|
| Button | **36px cao (VS Figma)**, min-w 120 (VS Figma, nhãn dài thì giãn) | theo token (5 hoặc 6) | 13px semibold (RO) | px 16 (RO) | hover / focus-visible ring / disabled 50% / loading spinner | `whitespace-nowrap`; nhãn EN dài hơn → min-width, không cố định width |
| Status badge | **cao 23, px 10 (VS)** | pill (RO) | 11–12px semibold (PROPOSED) | — | tone theo nghiệp vụ: success / warning / danger / neutral / info | content-fit; min-w trong cột bảng (PROPOSED) |
| Source badge (Crossref/OpenAlex) | cao 20 (PROPOSED) | 4px (PROPOSED, để khác status) | 10–11px | px 6 | — | content-fit |
| Stat card | — | token | giá trị 28 bold (RO) | 20 (RO) | — | 1–4 cột theo breakpoint |

## F. Git History Quality Audit (VS — dữ liệu Git local, không fetch)

**Kiểm kê:**
- 160 commit; 123 đã có trên `origin/main`, **37 chỉ có ở local**.
- 0 merge, 0 tag.
- 48 branch local + 32 remote; 46 branch "chưa merge" vì đưa code vào `main` bằng cherry-pick.
- **42 worktree**.
- 1 lần đảo thứ tự author date; 30 commit có author date ≠ committer date (dấu hiệu cherry-pick / rebase).
- Author: 157 `Quang Huy Truong`, 2 `Quang Huy <…@scopus-ictu.local>` (`c2debbe`, `87253db`), **1 author tên `M2.7A-4 Ingestion`** (`6909458`) — cả 3 **đã push**.
- `Co-Authored-By` có ở **106/160 commit**, từ 5 nguồn: Claude Sonnet 5.5 (37), Claude Sonnet 4.6 (37), Claude Sonnet 5 (32), Cursor (10), Copilot (9). Không commit nào có dòng "Generated with".

**Diễn biến quy ước:**

| Giai đoạn | Đặc điểm |
|---|---|
| 01–07/10 (74 commit) | Tiếng Việt, động từ đầu câu ("Hoàn thiện…", "Xử lý…"), **dài trung bình 36–44 ký tự, tối đa 60**, không prefix — nhất quán |
| từ 09/10 | Trung bình **65–97 ký tự**, tối đa 114; 33 subject > 72 ký tự; nhiều subject liệt kê nhiều thay đổi ("…: công bố theo năm, cơ cấu loại tài liệu, mức độ đầy đủ…") |

**Commit nên xem xét:**

| SHA | Vấn đề | Đã push? |
|---|---|---|
| `7aebe0d` | `wip: preserve uncommitted work…` — tiếng Anh, WIP, 14 file (+402/−203), có `scripts/poll_bridge_ci.ps1` | Có |
| `4bdc7a8` | Tiếng Việt **không dấu** ("Task 15.1: Hoan thien BAT…") | Có |
| `6909458` | Author "M2.7A-4 Ingestion" | Có |
| `0322f96`, `df0c4d3`, `9065c8f`, `8491480` | Subject 108–114 ký tự | Local (cả 4) |
| `7a01458` | Body 33 dòng, **trộn 2 phạm vi** (copy tab Đối sánh + enum thô ở 5 trang), nhắc ngữ cảnh phiên ("audit Giai đoạn 1", "Giai đoạn 3") | Local |
| `1a4dc96` → `daeb546` → `ef625e1` | Thêm dark mode → sửa → **xóa dark mode** trong cùng ngày | Local |
| `945feaf` → `95e0f1c` | Redesign → khôi phục PageLoadingBar | Local |
| `30b3e2d` → `3c31d6f` → `7de955c` | radius 8px → 5px → 5px (3 commit) | Local |

Không phát hiện văn phong hội thoại kiểu chatbot ("tôi / bạn") trong body; body nhìn chung mang tính kỹ thuật nhưng **quá dài**, giống changelog chi tiết.

**Quy ước đề xuất** (giữ tinh thần giai đoạn đầu):
- Subject **tiếng Việt có dấu, ≤ 72 ký tự (mục tiêu ≤ 60)**, động từ đầu câu, **một ý**. Giữ nguyên tên route / API / class (`/reviews`, `ApprovalQueue`).
- Tùy chọn tiền tố phạm vi trong ngoặc vuông: `[frontend]`, `[backend]`, `[docs]`, `[test]`.
- Body ≤ 8 dòng: *Mục đích* → *Thay đổi chính* → *Ảnh hưởng / kiểm thử*. Không ghi bối cảnh phiên làm việc.
- **Một** `Co-Authored-By` khi AI thực sự đóng góp. Đây là ghi nhận hợp lệ, không phải lỗi.
- Không commit WIP lên `main`.

Ví dụ:
| Hiện tại | Đề xuất |
|---|---|
| Thêm biểu đồ Tổng quan dùng dữ liệu thật: công bố theo năm, cơ cấu loại tài liệu, mức độ đầy đủ đơn vị tác giả | `[frontend] Thêm 3 biểu đồ Tổng quan từ API /dashboard/charts` |
| Khôi phục hiển thị tác vụ thu thập đơn vị trực tuyến sau tải lại trang và xử lý gián đoạn do khởi động lại máy chủ | `[backend] Khôi phục job thu thập đơn vị sau khi khởi động lại` |
| Hoàn thiện Ưu tiên 4: API/UI sinh ứng viên và nạp Craw, phát hiện candidate mới từ Craw có neo danh tính 2 lớp | `Thêm API và UI sinh ứng viên, nạp Craw` |
| Thêm chức năng ADMIN tạo tài khoản Giảng viên/Phê duyệt viên không cần hồ sơ và tìm công bố theo tên tác giả | Tách 2 commit: `Cho ADMIN tạo tài khoản REVIEWER/LECTURER` + `Tìm công bố theo tên tác giả` |
| Việt hóa tab Đối sánh cho người dùng không chuyên kỹ thuật + sửa enum thô | Tách: `[frontend] Viết lại nội dung tab Đối sánh` + `[frontend] Thay mã trạng thái thô bằng nhãn i18n` |
| wip: preserve uncommitted work from main before Backend integration | (không nên tồn tại trên main) |
| Task 15.1: Hoan thien BAT khoi dong… | `Hoàn thiện BAT khởi động demo một lần` |

**Rủi ro rewrite:**
- 123 commit đã push: **không rewrite** (force-push trên `main`, mất tính truy vết).
- 37 commit local: về kỹ thuật có thể reword / squash, nhưng sẽ **đổi SHA của baseline `237f7bc`**. SHA này được trích dẫn trong 4 tài liệu QA đã stage, bằng chứng test và release notes. Rewrite sẽ làm sai lệch toàn bộ bằng chứng nghiệm thu.

**Phương án an toàn đề xuất:**
- (1) **không rewrite**; áp dụng quy ước cho các commit từ nay;
- (2) dọn branch / worktree đã tích hợp sau khi lưu danh sách refs (`git for-each-ref > refs_backup.txt`) và có phê duyệt;
- (3) nếu muốn trình bày gọn, viết `CHANGELOG.md` theo đợt tính năng thay vì sửa lịch sử.

## G. Long-Term Risk Register

| ID | Rủi ro | Căn cứ | Ảnh hưởng | Mức |
|---|---|---|---|---|
| R1 | Online enrichment chỉ 300 DOI, cố định, không tiếp tục; mã lý do không phân biệt "chưa truy vấn" với "không có ở nguồn" | VS (`affiliation_enrichment_service.py:150`) + VR (17/10) | Bao phủ thấp, dễ hiểu sai khi dữ liệu tăng | Major (đã có phương án demo offline) |
| R2 | DB demo A không có backup trạng thái hiện tại | VR (thư mục `backups/`) | Mất dữ liệu demo nếu có sự cố hoặc thao tác nhầm | Major |
| R3 | Launcher tự `alembic upgrade head` lên DB mục tiêu | VS (`demo_launcher.py:225-275`) | Migrate ngoài ý muốn nếu đổi `DB_NAME` (DB teacher) | Major |
| R4 | 5173 mồ côi khi backend 8001 chết, không có cảnh báo trên UI ngoài lỗi 500 | VR | Nhầm môi trường khi demo | Minor |
| R5 | Năm không kiểm tra miền giá trị | VS | Cột năm vô lý trên Dashboard | Minor |
| R6 | Năm trống không được lấp trên trục | VS | Biểu đồ gây hiểu sai khi dữ liệu không liên tục | Minor (tiềm ẩn) |
| R7 | Lỗi 500 trong log launcher không kèm traceback (`normalize-import` ngày 14/10, retry thành công) | VR (log) | Khó chẩn đoán sự cố | Minor; nguyên nhân NV |
| R8 | Import CSV nhiều lần | RO: trùng tệp theo SHA → 409, cập nhật metadata theo version | Đã kiểm soát | — |
| R9 | Tác giả trùng tên / Scopus ID đề xuất cho nhiều giảng viên | VS + VR: cảnh báo `is_shared_scopus_author`; ví dụ 2 giảng viên "Nguyễn Thị Dung" (1 APPROVED, 1 REJECTED) | Kiểm soát bằng REVIEWER | — |
| R10 | Một tác giả nhiều đơn vị / đơn vị đổi tên / nguồn mâu thuẫn | VS: nhiều dòng đơn vị theo nguồn, `WITHHELD_SOURCE_CONFLICT`, override nhiều đơn vị (M7) | Đã có cơ chế; đơn vị là lời khai tại thời điểm thu thập | Minor (giới hạn kiến trúc) |
| R11 | Giảng viên đổi đơn vị công tác | Không có lịch sử đơn vị công tác theo thời gian ngoài snapshot JSON | Dữ liệu hiện thời ghi đè; snapshot append-only | Minor |
| R12 | Phân trang | VR (11/10): `page_size` tối đa 100, 1000 → 422 | Đã kiểm soát | — |
| R13 | Hiệu năng khi dữ liệu tăng | Dashboard đếm toàn bảng mỗi lần mở; chưa đo | NV | — |
| R14 | Đăng nhập không giữ deep link | VS | UX | Minor |

## H. Prioritized Fix Backlog (chờ duyệt — KHÔNG tự triển khai)

| ID | Mô tả | Mức | Evidence | Root cause | File / module | Sửa tối thiểu | Ảnh hưởng | Test sau sửa | Cập nhật Figma / tài liệu |
|---|---|---|---|---|---|---|---|---|---|
| **TEST-01** | Chưa có UI E2E thật 3 tác nhân trên môi trường A (kể cả LECTURER đã liên kết, Accept/Reject trên UI) | MAJOR | BL (lượt này), RO cũ | Thiếu phiên đăng nhập hợp lệ trong công cụ | — | Chủ đồ án đăng nhập trong Browser pane (hoặc cấp tài khoản TEST cho tôi dùng); chạy checklist đọc | Không đổi code | Checklist RC §8 + VI/EN | RC §9 |
| **UX-01** | Không có Badge dùng chung; 2 hình dạng, 4 cỡ chữ, AntD Tag riêng ở `/reviews` | MAJOR (phạm vi rộng) | VS + Figma `5:34` | Mỗi trang tự viết | `ReviewHistory`, `Dashboard`, `AuthorAffiliations`, `ApprovalQueue`, Search | `components/common/Badge.tsx` (tone, size) theo `h-23 px-10 pill`; thay 5 điểm chính | Chỉ UI | Build, test UI các trang, VI/EN nhãn dài | Có (chốt min-width cột) |
| **UX-02** | Bo góc: 5px là giá trị cứng ở 349 chỗ; LECTURER (16px), Users / ImportCard (12px), button (8px) lệch | MAJOR | VS | Bước 5px bỏ sót; không có token | `tailwind.config`, `MyPublications`, `Profile`, `Identity`, `Users`, `buttonStyles` | Thêm token radius; sửa 3 trang LECTURER + `buttonStyles` | Chỉ UI | Build, chụp trước/sau | Cập nhật Figma 6/10 → 5 nếu giữ 5 |
| **UX-03** | Nút: 158 nút viết tay, helper chỉ 5/28 file; 40px/14 bold ≠ Figma 36/13 semibold | MAJOR | VS + Figma `5:2` | Helper ra đời muộn | `buttonStyles.ts` + các trang | Chốt kích thước, sửa `BASE`, chuyển các nút hành động chính sang helper theo đợt | Chỉ UI | Build, modal / form / table | Có |
| **DASH-01** | Nhãn "Có đơn vị công tác" gộp CORROBORATED; không hiển thị VERIFIED / CORROBORATED / UNRESOLVED | MAJOR (dễ hiểu sai nghiệp vụ) | VS + VR API | Chọn nhãn chưa đúng thuật ngữ | `AffiliationCoverageChart.tsx`, i18n | Đổi nhãn ("Có đơn vị theo nguồn ngoài") + chú thích 3 mức từ `by_link_status` | Chỉ UI | Test dashboard + VI/EN | Tài liệu demo |
| **OPS-01** | DB demo A chưa có backup trạng thái hiện tại | MAJOR | VR | — | `_postgres_demo_14_10/backups` | `pg_dump -Fc` DB A + `sha256` (chỉ đọc DB) — cần phê duyệt | Không | `pg_restore --list` | RC §4 |
| **OPS-02** | Tài liệu / launcher demo trỏ App DB, không phải môi trường A; 5173 mồ côi | MAJOR | VR | Chưa cập nhật quy trình demo | `docs/demo/BACKEND_LOCALHOST_14_10.md`, quy trình khởi động A | Tài liệu khởi động A (lệnh 8199 / 5199) + cảnh báo không dùng 5173 khi demo | Không đổi code | Thử khởi động lại A | Có |
| DASH-02 | Trục năm không lấp năm trống | MINOR | VS | CategoryScale + API sparse | `PublicationsByYearChart.tsx` | Lấp `min..max` với 0 ở frontend | UI | Unit dữ liệu có khoảng trống | Không |
| DASH-03 | Năm không kiểm miền giá trị | MINOR | VS | `_raw_int` | `scopus_normalizer.py` | Cho NULL nếu ngoài 1900..(năm hiện tại + 2) + cảnh báo | Backend | Unit normalizer | Không |
| DASH-04 | 7 màu / 8 loại tài liệu | MINOR | VS | PALETTE ngắn | `DocumentTypeDonutChart.tsx` | Thêm màu / gom "Khác" | UI | Xem chart | Không |
| UX-05 | Đăng nhập mất deep link | MINOR | VS | `navigate("/home")` | `ProtectedRoute`, `Login` | Lưu `state.from` | UI | Route test | Không |
| UX-06 | Placeholder mật khẩu `••••••••` | MINOR | VR | — | `Login` | Placeholder chữ | UI | — | Không |
| UX-07 | `/tasks` placeholder trong menu ADMIN | MINOR | VS | — | `Sidebar`, `App.tsx` | Ẩn khỏi menu đến khi có tính năng | UI | — | Figma Sidebar |
| OBS-01 | 500 không kèm traceback trong log launcher | MINOR | VR | NV | logging config | Ghi exception ra log | Backend | — | Không |
| GIT-01 | Lịch sử commit thiếu nhất quán từ 09/10; branch / worktree nhiều | MINOR (không ảnh hưởng phần mềm; ưu tiên trình bày cao) | VS | Nhiều công cụ / phiên | — | Không rewrite; áp quy ước mới; dọn refs có backup | Không | — | CONTRIBUTING / CHANGELOG |
| M1 | Giới hạn 300 DOI | (đã chấp nhận) | VR | — | — | Giữ trong known limitations | — | — | Có |
| M2 | UI DB rỗng chưa có bằng chứng | (đã chấp nhận) | — | — | — | — | — | — | Có |

## I. Proposed Execution Plan (chỉ đề xuất)

1. **Đợt 1 — Nghiệp vụ & phân quyền (không đổi code):** TEST-01 UI E2E 3 tác nhân trên A (chỉ đọc) + một ca Accept/Reject trên UI (cần phê duyệt riêng vì có ghi); OPS-01 backup DB A.
2. **Đợt 2 — Dashboard:** DASH-01, DASH-02, DASH-04 (frontend), DASH-03 (backend + unit test).
3. **Đợt 3 — Design system:** chốt kích thước nút / radius / badge (chủ đồ án + Figma) → UX-01 Badge, UX-02 token radius, UX-03 nút, UX-05 → UX-07.
4. **Đợt 4 — Git:** áp quy ước commit; quyết định dọn branch / worktree (có backup refs); không rewrite.
5. **Đợt 5 — Regression:** pytest đầy đủ, `npm run build`, checklist UI 3 tác nhân VI/EN, chụp trước/sau.
6. **Đợt 6 — RC mới:** cập nhật tài liệu RC (baseline SHA mới), commit tài liệu, tag `v1.0.0-rc.1` (hoặc rc.2) sau phê duyệt.

---
*Lượt audit này không sửa code, không ghi DB, không stage / commit / tag / push. Viewport trình duyệt đã trả về mặc định.*
