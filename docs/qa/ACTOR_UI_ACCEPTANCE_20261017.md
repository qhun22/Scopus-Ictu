# Actor UI Acceptance & Demo Environment Safety — Scopus-ICTU (17/10/2026)

Lượt kiểm thử **chỉ đọc** trên **môi trường A**: frontend `http://localhost:5199` → backend `127.0.0.1:8199` → DB `scopus_ictu_test_withjson_r2_20261011`.
Không sửa code, không ghi dữ liệu nghiệp vụ, không stage/commit/tag/push. 4 file RC đã stage giữ nguyên (blob `fb176d6`, `853c832`, `3b03317`, `0c34a85`).

Mức bằng chứng: **VR** runtime (trình duyệt / API / DB) · **VS** đọc code · **RO** báo cáo cũ · **BL** bị chặn.

## 0. Cách thực hiện và bảo đảm chỉ đọc

| Hạng mục | Chi tiết |
|---|---|
| Phiên đăng nhập | Browser pane: chủ đồ án thử đăng nhập 3 lần, backend ghi **3 × `POST /auth/login` → 401** (mật khẩu TEST sinh ngẫu nhiên, không có sẵn); sau đó không có thêm lần thử nào. Không tiếp tục hỏi lặp. |
| Phương án hợp lệ đã dùng | **Chrome headless** (`chrome.exe --headless=new`, profile tạm, xóa sau khi chạy) điều khiển qua DevTools Protocol bằng script `_postgres_demo_14_10/scratch/ui_e2e_cdp_20261017.py` + `…_pass2_20261017.py`. Đăng nhập **qua đúng form `/login`** bằng tài khoản TEST; thông tin đăng nhập chỉ đọc trong script từ tệp secrets ngoài Git, **không in, không lưu vào báo cáo, không vào ngữ cảnh phiên**. |
| Hành động được phép | Điều hướng, đổi VI/EN, thu gọn/mở sidebar, chọn bộ lọc, mở "Xem chi tiết" ứng viên, đóng modal, mô phỏng viewport 375 px. **Không** bấm Xác nhận / Từ chối / Nhập / Áp dụng / Xuất / Xóa / Đăng xuất (đổi phiên bằng xóa cookie của profile tạm). |
| Kiểm soát ghi | Script ghi lại mọi request không phải GET: **0** (ngoài `/auth/login`). Snapshot DB trước/sau (`audit_events`, reviews, identities, candidates, affiliations, overrides, users, notifications, imports, lecturers, publications, `max(updated_at)` users) **giống hệt** → `DB UNCHANGED`. |
| Bằng chứng | 60 ảnh + `results.json` (`scratch/ui_e2e_20261017/`), 17 ảnh + `notes.json` (`…/pass2/`), ngoài repo (có dữ liệu cá nhân giảng viên, không đưa vào Git). Viewport desktop 1440×900. |

## 1. Môi trường (VR)

| | Môi trường A | Launcher 5173 / 8001 |
|---|---|---|
| Frontend | Vite 5199 (PID 25884), chỉ lắng nghe `[::1]` → `localhost:5199` và `[::1]:5199` dùng được, `127.0.0.1:5199` **không**. Cookie theo host: đăng nhập ở `localhost` ≠ `[::1]` | Vite 5173 (PID 26564, khởi động 05:04:58 bởi launcher), vẫn chạy |
| Backend | uvicorn 8199 (PID 26972), 1 kết nối PG → `pg_stat_activity.datname = scopus_ictu_test_withjson_r2_20261011` | 8001 (PID 3524) **không còn**; `/api` qua 5173 → 500, `frontend.log`: `ECONNREFUSED 127.0.0.1:8001` (139 lần) |
| Alembic | `c7f2a9b1d3e5` (HEAD) | App DB `c7f2a9b1d3e5` |

**Vì sao 8001 dừng (17/10):**
- Launcher khởi động backend lúc 05:04:57; request cuối trong `backend.log` lúc **05:09:41**.
- **Không có** dòng `Shutting down` của uvicorn, **không có** dòng "Da dung" trong `launcher.log`, **không có** sự kiện crash nào của Python trong Windows Application log. Chỉ có `LiveKernelEvent` lúc 05:21–05:29, là sự kiện cấp driver/kernel, không gắn với tiến trình.
- Unit test `test_demo_launcher.py` không gọi `taskkill` (đã loại giả thuyết do pytest).
- Backend được tách bằng `DETACHED_PROCESS | NEW_PROCESS_GROUP` (`demo_launcher.py:44`), nên việc đóng console không giết được nó.
- **Kết luận:** tiến trình bị dừng cưỡng bức, nguyên nhân **chưa xác minh**. Điểm xác minh được là launcher **không giám sát sức khỏe** tiến trình con, nên frontend 5173 tiếp tục chạy một mình và trả lỗi API.

## A. Actor UI Acceptance Matrix (VR — Chrome headless, giao diện thật)

### ADMIN (`withjson.admin@ictu.edu.vn`)
| ID | Route | Hành động | Expected | Actual | Kết quả | Bằng chứng | Ảnh hưởng |
|---|---|---|---|---|---|---|---|
| A-01 | `/login` → `/home` | Đăng nhập form | Vào `/home`, `/auth/me` role ADMIN | Đúng | PASS | log LOGIN | — |
| A-02 | `/home` | Xem | Trạng thái thẻ phản ánh dữ liệu thật | Thẻ "Đối sánh cần xử lý" ghi **"Chưa có dữ liệu"** dù 144 PENDING. Nhãn là chuỗi tĩnh (`i18n/locales/vi.ts:125`), Home không gọi API | **FAIL** | `A01_home.png`, `A19_sidebar_collapsed.png` | P1 — UI-01 |
| A-03 | `/dashboard` | Xem KPI, biểu đồ | Số liệu = DB | 660 / 410 / 410 / 1.207 / 144; định danh 0/3/0/0; 20 năm 2008–2027; 8 loại; 83% (2.291) | PASS (số liệu) | `A02_dashboard.png` | — |
| A-03b | `/dashboard` | Nhãn / màu | Nhãn rõ nghĩa, màu không trùng | "Bài xã luận" **trùng màu** "Bài báo hội nghị"; **"Retracted"** chưa dịch; "ỨNG VIÊN 0" (identity) cạnh "Chờ duyệt 144" (candidate) dễ nhầm | PARTIAL | `A02_dashboard.png` | P2 — UI-08/09, P1 — UI-02 |
| A-04 | `/imports` | Xem bảng | Bảng vừa khung 1440 | Bảng 1.197 px > khung 1.124 px; **cột "Thao tác" bị cắt**, phải cuộn ngang | PARTIAL | `P05_imports.png` | P2 — UI-10 |
| A-04b | `/imports` | Nội dung | Chính tả đúng | "Đã **nap** / Bản ghi", "để **nap** và xử lý", "đã được **validate**" | PARTIAL | `P05_imports.png` | P2 — UI-11 |
| A-05 | `/normalization` (4 tab) | Xem | Mở được, không lỗi | 4 tab mở, 0 lỗi API / console | PASS | `A04`–`A07` | — |
| A-05b | `?tab=affiliations` | Xem | Trạng thái nguồn đúng với dữ liệu | Chữ đỏ "**Máy chủ chưa được cấu hình** thư mục nguồn đơn vị (`AFFILIATION_SOURCE_DIR`)" trong khi DB đã có 4.147 dòng đơn vị offline; hai mục cùng số "2."; mục rà soát hiện mã thô `crossref: CORROBORATED · openalex: UNRESOLVED (NAME_MISMATCH)` | PARTIAL | `A06_norm_affiliations.png`, `P04_affiliations_raw_enum.png`, `notes.json` | P1 — UI-03 (demo), P2 — UI-12 |
| A-06 | `/lecturers` | Xem | 410 hồ sơ | Hiển thị; bảng rộng hơn khung 30 px | PASS / PARTIAL | `A08_lecturers.png` | P2 — UI-10 |
| A-07 | `/users` | Xem | Danh sách tài khoản | Hiển thị (thẻ bo 12 px, lệch 5 px) | PASS | `P07_users.png` | P2 — UX-02 |
| A-08 | `/reviews`, `/review-history` | Xem | ADMIN được xem | Đúng; console 1 cảnh báo AntD `destroyOnClose` deprecated | PASS | `A10`, `A11` | P3 |
| A-09 | `/publications` | Danh sách | 660 bài | Đúng | PASS | `A12_publications.png` | — |
| A-10 | `/publications/2-s2.0-105000434624` | Chi tiết | 3 tác giả đúng thứ tự; #1 VERIFIED + ORCID; #2–3 CORROBORATED; truy vết CSV | Đúng: ORCID `0000-0003-1801-5887` → Scopus ID; tệp `Truong_Quang_Huy_Scopus_Sep2026.csv` dòng 150, SHA-256 `6a62fcf6…` | PASS | `A13`, `P02`, `P03` | — |
| A-11 | `/publications/2-s2.0-105000836388` | Chi tiết | 7 tác giả; thiếu đơn vị không bị gán | #3 Amago và #5 Maligalig: "**Chưa có thông tin đơn vị**" + lý do theo nguồn ("nguồn không có đơn vị", "Tên tác giả không khớp"); không có tổ chức giả | PASS | `P01_pub836388_missing_affiliation.png` | — |
| A-11b | chi tiết công bố | Header / badge | Tiêu đề đúng trang; badge cùng nhãn cùng cỡ | Header ghi **"Hệ thống"**; badge "Đã đối chiếu · Chưa xác minh" **hai cỡ khác nhau** trong cùng bảng (hàng có / không có đơn vị) | PARTIAL | `A13`, `P01` | P2 — UI-13, P1 — UX-01 |
| A-12 | `/search?q=Nguyen` | Tra cứu | Kết quả | Hiển thị | PASS | `A15_search.png` | — |
| A-13 | `/audit-logs` | Xem | Nhật ký | Hiển thị; bảng rộng hơn khung 75 px | PASS / PARTIAL | `A16`, `A23` | P2 — UI-10 |
| A-14 | `/tasks` | Xem | Chức năng thật hoặc ẩn | Trang "**Chức năng đang phát triển**" trong menu ADMIN | PARTIAL | `P06_tasks.png` | P2 — UX-07 |
| A-15 | route không tồn tại | Mở | Về trang an toàn | `/home` | PASS | `A18` | — |
| A-16 | Sidebar | Thu gọn / mở | Icon thẳng hàng, active rõ | Đúng | PASS | `A19`, `A19b` | — |
| A-17 | VI → EN | Bấm EN | Đổi ngôn ngữ, giữ sau F5 | Lớp phủ toàn màn hình **3,17 s** (`TRANSITION_DURATION_MS = 3000`, `I18nContext.tsx:14`), chỉ lưu `localStorage` sau 3 s; sau F5 vẫn `lang=en` | PASS (chức năng) / PARTIAL (UX) | `A20` (lớp phủ), `P08`, `P09`, `notes.json` | P2 — UI-14 |
| A-18 | EN | Nội dung | Không lẫn tiếng Việt | `/reviews`, `/audit-logs`, affiliations: sạch; **chi tiết công bố vẫn "Chưa cập nhật"** | PARTIAL | `P10_pub_EN.png` | P2 — UI-15 |
| A-19 | Mobile 375 px | `/home`, `/dashboard`, `/publications`, chi tiết, `/reviews` | Dùng được | Trang không tràn ngang (bảng cuộn trong khung); nút header Dashboard **bị cắt** "Làm …", "Reset…"; bảng `/reviews` phải cuộn ngang mới thấy trạng thái | PARTIAL | `A25`–`A29` | P2 — UI-16 |
| A-20 | Lỗi mạng / console | Toàn bộ 30 lượt ADMIN | Không 4xx/5xx | 0 lỗi API; console chỉ có cảnh báo AntD | PASS | `results.json` | — |

### REVIEWER (`withjson.reviewer@ictu.edu.vn`)
| ID | Route | Hành động | Expected | Actual | Kết quả | Bằng chứng | Ảnh hưởng |
|---|---|---|---|---|---|---|---|
| R-01 | `/home` | Xem | Shortcut REVIEWER | Đúng menu; nhãn thẻ tĩnh như A-02 | PARTIAL | `R01_home.png` | P1 — UI-01 |
| R-02 | `/reviews` | Hàng đợi | 144 PENDING, bằng chứng, mơ hồ | "Tổng số: 144"; badge "Chờ duyệt" (pill, đồng chiều rộng vì cùng nhãn); "Chỉ bằng chứng tên", "Còn 1 ứng viên khác" | PASS | `R02_reviews.png` | — |
| R-03 | `/reviews` → "Xem chi tiết" | Mở modal | Đủ A–E, nút quyết định, không tự ghi | Modal 1040×744: A. Giảng viên / B. Tác giả Scopus / C. Bằng chứng tên / D. Bằng chứng công bố / E. Ngữ cảnh mơ hồ; nút **Close / Từ chối / Xác nhận đối sánh**. Mở modal **không** gửi request ghi | PASS (đủ thông tin) | `P14_reviewer_candidate_detail.png`, `notes.json` | — |
| R-03b | modal | Dễ hiểu | Ngôn ngữ nghiệp vụ | Hiện mã kỹ thuật `RULE_TITLE_STRIPPED_N2_FORMAT`, `PREFERRED_NAME`, `AUTHOR_FULL_NAME`, "M2.7A-2"; **bằng chứng tên lặp 2 khối gần giống nhau**; font modal AntD khác font ứng dụng; "Chức danh: Chưa có dữ liệu" | PARTIAL | `P14` | P2 — UI-17 |
| R-04 | Lọc ACCEPTED / REJECTED | Chọn bộ lọc | Đúng số đã có | ACCEPTED: **3** (TS. Vũ Đức Quang; PGS.TS. Nguyễn Thị Dung; ThS. Đoàn Ngọc Phương). REJECTED: **2** (ThS. Đỗ Thị Mai; ThS. Nguyễn Thị Dung) — khớp DB / audit (2 ca ngày 17/10 + 3 ca ngày 12/10) | PASS | `P16`, `P17`, `notes.json` | — |
| R-04b | Dữ liệu demo | Xem lại ca ACCEPTED | Quyết định có cơ sở | **PGS.TS. Nguyễn Thị Dung ↔ 59253245500: "Đã xác nhận" chỉ với bằng chứng tên, Scopus ID "Dùng chung (5 GV)"**, tạo 12/10 trên DB test. Ca ThS. Nguyễn Thị Dung cùng Scopus ID bị từ chối ngày 17/10 | Cảnh báo dữ liệu | `P16` | P1 — DATA-01 (demo) |
| R-05 | `/review-history` | Xem | Phản ánh quyết định | 5 dòng: thời gian, hành động, chuyển trạng thái, giảng viên, Scopus ID, người duyệt, lý do (bị cắt "…") | PASS | `R04_review_history.png` | — |
| R-05b | Thuật ngữ | So sánh 3 màn | Thống nhất | Hàng đợi "Chờ duyệt / Đã xác nhận"; lịch sử "Chờ xét duyệt / Chấp thuận / Đã chấp thuận"; nút "Xác nhận đối sánh"; Figma "Đã chấp nhận" | PARTIAL | `R02`, `R04`, `P16` | P2 — UI-18 |
| R-06 | Chặn quyền | `/dashboard`, `/users`, `/imports`, `/audit-logs`, `/profile` | Về `/home` | Cả 5 → `/home` | PASS | `R07`–`R11` | — |
| R-07 | VI / EN | `/reviews`, `/review-history` | EN nhất quán | Lượt 1 chụp trong lúc lớp phủ 3 s đang chạy (`R13`/`R14` vẫn VI vì điều hướng trước khi lưu); lượt 2 ADMIN đã xác nhận `/reviews` EN sạch | PARTIAL | `R13`, `R14`, `P11` | P2 — UI-14 |
| R-08 | Trường hợp không có ứng viên | — | Thông điệp rỗng đúng nguyên nhân | Không tái hiện được trên A (luôn có 144); `/reviews/context` 4 trạng thái — RO (11/10) | NOT TESTED (UI) | — | — |
| R-09 | Accept / Reject trên UI | — | — | Không bấm theo phạm vi lượt này. Trạng thái 2 quyết định ngày 17/10 hiển thị đúng ở hàng đợi (lọc) và lịch sử, khớp API / DB / audit (VR ngày 17/10) | PASS (xem) / NOT TESTED (thao tác) | `P16`, `P17`, `R04` | Test case TC-W1 ở §B |

### LECTURER
| ID | Tài khoản | Route | Expected | Actual | Kết quả | Bằng chứng |
|---|---|---|---|---|---|---|
| L-01 | **Chưa liên kết** `withjson.viewer` | `/home` | Shortcut LECTURER | Đúng menu (Công bố, Tra cứu, Công bố của tôi, Liên kết Scopus, Hồ sơ); nhãn thẻ tĩnh ("Đang chờ kết nối") | PARTIAL | `L01_home.png` |
| L-02 | chưa liên kết | `/my-publications`, `/profile`, `/identity` | Thông báo chưa liên kết, không lỗi | "Tài khoản chưa được liên kết…" + "Thử lại"; API 403 `LECTURER_NOT_LINKED` (đúng thiết kế); thẻ bo 16 px | PASS (hành vi) | `L02`–`L04` |
| L-03 | chưa liên kết | `/publications`, chi tiết, `/search` | Đọc được | Mở được, API 200 (VR); việc ẩn truy vết / liên kết giảng viên với LECTURER mới xác minh ở mức code (`_for_role`, VS), chưa chụp được phần cuối trang | PASS (mở) / VS (ẩn truy vết) | `L05`–`L07` |
| L-04 | chưa liên kết | `/reviews`, `/dashboard`, `/lecturers` | Chặn | → `/home` | PASS | `L08`–`L10` |
| L-05 | chưa liên kết | EN, mobile | Nhất quán | EN chụp trong lúc lớp phủ (cùng nguyên nhân UI-14); mobile không tràn | PARTIAL | `L11`–`L15` |
| L-06 | **Đã liên kết** `vu.duc.quang.test` (TS. Vũ Đức Quang, 1 identity APPROVED, 27 công bố — VS từ DB) | Hồ sơ / Công bố của tôi / Liên kết Scopus | Hiển thị đúng dữ liệu | **BLOCKED**: không có thông tin đăng nhập lưu cho tài khoản này; đặt lại mật khẩu là thao tác ghi trên DB demo (cần phê duyệt riêng) | BLOCKED | — |

**Không kết luận LECTURER PASS toàn bộ:** mới kiểm tài khoản chưa liên kết.

## B. Danh sách lỗi UI thực tế (chưa sửa)

| ID | Ưu tiên | Route / component | Mô tả | Bằng chứng | Đề xuất sửa tối thiểu |
|---|---|---|---|---|---|
| UI-01 | **P1** | `/home` (3 vai trò), `Home/index.tsx:66-207`, `locales/vi.ts:119-140` | Nhãn trạng thái thẻ là chuỗi tĩnh ("Chưa có dữ liệu", "Đang chờ kết nối") → báo sai trạng thái nghiệp vụ | `A01`, `R01`, `L01` | Bỏ nhãn trạng thái, hoặc lấy số thật từ API đã có (`/dashboard/summary`, `/reviews/context`, `/lecturers/me/*`) |
| UI-02 | **P1** | `/dashboard` "Trạng thái định danh" | "ỨNG VIÊN 0" (identity `CANDIDATE`) cạnh "Chờ duyệt 144" (ứng viên đối sánh) | `A02` | Đổi nhãn (vd "Định danh: chờ xác lập") hoặc ẩn trạng thái luôn bằng 0 |
| UI-03 | **P1 (demo)** | `/normalization?tab=affiliations` | Thông báo đỏ "chưa cấu hình `AFFILIATION_SOURCE_DIR`" dù dữ liệu offline đã áp dụng; lộ tên biến môi trường | `A06` | Ghi rõ "đã có dữ liệu áp dụng lúc …; nguồn offline hiện không gắn với máy chủ" (giọng trung tính), hoặc cấu hình `AFFILIATION_SOURCE_DIR` cho môi trường A (thay đổi cấu hình, cần duyệt) |
| UX-01 | **P1** | Badge (nhiều trang) | Hai cỡ badge cho cùng nhãn trong cùng bảng chi tiết công bố; nhiều kiểu badge | `P01` | Badge dùng chung (xem audit) |
| DATA-01 | **P1 (demo)** | Dữ liệu DB A | Ca ACCEPTED chỉ bằng chứng tên cho Scopus ID dùng chung 5 giảng viên | `P16` | Không sửa dữ liệu demo; chuẩn bị lời giải thích, hoặc tránh mở ca này khi demo; nếu muốn, REOPEN trên bản sao TEST |
| UI-10 | P2 | `/imports`, `/lecturers`, `/audit-logs` (1440 px) | Bảng rộng hơn khung 30–75 px; cột thao tác của `/imports` bị cắt | `P05`, `A08`, `A16` | Thu hẹp cột / `table-fixed` / cố định cột thao tác |
| UI-11 | P2 | `/imports` | "nap" thiếu dấu, "validate" | `P05` | Sửa chuỗi i18n |
| UI-12 | P2 | affiliations → rà soát | Mã thô `CORROBORATED/UNRESOLVED (NAME_MISMATCH)`; hai mục đánh số "2." | `P04` | Dùng nhãn hiện có của `AffiliationBadge`; sửa số thứ tự |
| UI-13 | P2 | header chi tiết công bố | Tiêu đề "Hệ thống" | `A13` | Map tiêu đề route `/publications/:eid` |
| UI-14 | P2 | `I18nContext` | Đổi ngôn ngữ khóa màn hình 3 s; rời trang trước 3 s mất lựa chọn | `A20`, `notes.json` | Giảm còn ≤ 300 ms hoặc lưu `localStorage` ngay khi bấm |
| UI-15 | P2 | chi tiết công bố EN | "Chưa cập nhật" | `P10` | i18n giá trị NULL ở `Detail.tsx` |
| UI-16 | P2 | mobile Dashboard, `/reviews` | Nút header bị cắt; bảng phải cuộn để thấy trạng thái | `A26`, `A29` | `flex-wrap` header; ưu tiên cột trạng thái trên mobile |
| UI-17 | P2 | modal ứng viên | Mã quy tắc kỹ thuật; bằng chứng tên lặp; font AntD khác | `P14` | Nhãn nghiệp vụ cho rule / loại tên; gộp bằng chứng trùng giá trị; đặt `fontFamily` cho ConfigProvider |
| UI-18 | P2 | `/reviews`, `/review-history` | Thuật ngữ không thống nhất | `R02`, `R04` | Chốt một bộ thuật ngữ: Chờ duyệt / Đã chấp nhận / Đã từ chối |
| UI-08 | P2 | Dashboard donut | Trùng màu loại thứ 8 | `A02` | Thêm màu / gom "Khác" |
| UI-09 | P2 | Dashboard donut | "Retracted" chưa dịch | `A02` | Thêm nhãn VI |
| UX-02 | P2 | LECTURER pages, `/users` | Bo góc 12–16 px lệch 5 px | `L02`, `P07` | Token radius |
| UX-07 | P2 | `/tasks` | Placeholder trong menu | `P06` | Ẩn khỏi menu |
| UI-19 | P3 | `/reviews` | Cảnh báo AntD `destroyOnClose` deprecated | console | Đổi sang `destroyOnHidden` |
| UI-20 | P3 | `/review-history` | Ô ngày hiển thị `mm/dd/yyyy` (định dạng do trình duyệt headless locale en-US — **chưa xác nhận** trên Chrome tiếng Việt) | `R04` | Kiểm lại trên trình duyệt người dùng |

**Test case ghi cần phê duyệt riêng (chưa chạy):**
- **TC-W1 (Accept/Reject qua UI):**
  - Môi trường: bản sao TEST của DB A (`pg_restore` vào DB mới, xem §C).
  - Các bước: REVIEWER mở ca PENDING có công bố hỗ trợ → "Xác nhận đối sánh" → nhập lý do → xác nhận. Một ca chỉ có bằng chứng tên → "Từ chối".
  - Kỳ vọng: toast đúng, trạng thái chuyển ACCEPTED/REJECTED, lịch sử thêm 1 dòng, audit `CANDIDATE_*` (+ `IDENTITY_CREATED_FROM_CANDIDATE`), bấm lần 2 không tạo bản ghi trùng.
- **TC-W2 (LECTURER đã liên kết):**
  - Môi trường: trên bản sao TEST, ADMIN đặt lại mật khẩu `vu.duc.quang.test`.
  - Các bước: đăng nhập, kiểm Hồ sơ / Công bố của tôi (27) / Liên kết Scopus / liên kết tới chi tiết công bố.

## C. Backup Plan — OPS-01 (chưa thực hiện, chờ duyệt)

| Hạng mục | Giá trị xác minh (VR) |
|---|---|
| DB nguồn | `scopus_ictu_test_withjson_r2_20261011`, 40 MB, 27 bảng `public`, 1 extension, owner `scopus_demo_user` (= role kết nối của backend) |
| Công cụ | `C:\Program Files\PostgreSQL\17\bin\pg_dump.exe` 17.10 = server 17.10; `pg_restore` 17.10 |
| Thư mục đích | `D:\DataFolder\ProjectIctu\DoAn\_postgres_demo_14_10\backups\` — **ngoài repo**, ổ D còn trống 231 GB, đã có quy ước `*.dump` + `*.dump.sha256` + `SHA256SUMS.txt` |
| Xác thực | `pgpass.conf` **chưa có** dòng cho DB này → hoặc chủ đồ án thêm 1 dòng, hoặc chạy qua script đặt `PGPASSWORD` từ `backend/.env` cho tiến trình con (không in ra) |

**Quy trình đề xuất:**
1. **Dump (chỉ đọc nguồn):**
   `pg_dump -h 127.0.0.1 -p 55432 -U scopus_demo_user -d scopus_ictu_test_withjson_r2_20261011 -Fc --no-password -f backups\withjson_r2_demoA_20261017.dump`
   `pg_dump` dùng một snapshot nhất quán, không khóa ghi, không sửa DB nguồn.
2. **Xác minh tệp:**
   - Tạo `sha256sum` vào `withjson_r2_demoA_20261017.dump.sha256` và thêm dòng vào `SHA256SUMS.txt`.
   - Chạy `pg_restore --list` (đếm mục TOC: 27 bảng + `alembic_version` + index / constraint).
3. **Restore rehearsal** vào DB TEST mới, ví dụ `scopus_ictu_test_restore_demoA_20261017`. Việc này cần quyền `CREATE DATABASE` bằng vai trò `demo_admin`; lần trước bị chặn bởi quyền công cụ, nên cần chủ đồ án chạy hoặc cho phép.
   - Lệnh: `pg_restore --no-owner --role=scopus_demo_user -d <db mới>`.
   - So sánh: `alembic_version`, số dòng 27 bảng và băm nội dung `publications` / `publication_authors` / resolutions giữa nguồn và bản khôi phục.
4. **Không đưa vào Git:** thư mục `backups/` nằm ngoài repo; tệp dump chứa dữ liệu cá nhân 410 giảng viên và băm mật khẩu tài khoản TEST.

## D. Launcher Safety Proposal — OPS-02 (chưa sửa)

**Hiện trạng (VS):**
- `scopus-ictu-qhun22.bat` → `demo_launcher.py start`.
- DB đích cố định: `EXPECTED_DB = os.environ.get("SCOPUS_DEMO_DB", "scopus_ictu_app")`, cùng `ENV_FILE = secrets/backend_app.env` (`demo_launcher.py:37-39`). `validate_config` bắt `DB_NAME` phải bằng `EXPECTED_DB`.
- Cổng cố định 8001 / 5173.
- **`start` tự chạy `alembic upgrade head`** khi revision lệch (`check_database`, dòng 270–275), không backup, không hỏi lại, dù BAT đã có lệnh `migrate` riêng.
- Không giám sát tiến trình con sau khi khởi động.

**Hệ quả:**
- Launcher không chạy được môi trường A.
- Nếu ai đó đổi `SCOPUS_DEMO_DB` / `DB_NAME` sang DB teacher, launcher sẽ **tự migrate DB teacher**.

**Phương án (theo mức thay đổi):**

| PA | Nội dung | Thay đổi | Đánh giá |
|---|---|---|---|
| PA-0 (không sửa code) | Tài liệu vận hành môi trường A: khởi động backend 8199 từ `Scopus-Ictu/backend` (`backend/.env` → DB A) và frontend `VITE_API_PROXY_TARGET=http://127.0.0.1:8199 npm run dev -- --port 5199`; **không** chạy BAT khi demo; mở `http://localhost:5199` | Tài liệu | Dùng được ngay; dễ thao tác sai |
| **PA-1 (khuyến nghị)** | Trong `demo_launcher.py`: `start` **từ chối** khi revision lệch (in hướng dẫn), chỉ lệnh `migrate` mới migrate, và `migrate` **bắt buộc `pg_dump` trước** | ~15 dòng + unit test | Chặn migrate ngoài ý muốn cho mọi DB |
| PA-2 | Thêm hồ sơ môi trường: `start --profile demoA` đọc `secrets/backend_demoA.env` (DB A, cổng 8199 / 5199), danh sách DB cho phép rõ ràng, **chặn cứng** `scopus_ictu_demo_teacher_20261014` | Code + tệp env ngoài Git | Một nút bấm cho môi trường A |
| PA-3 | Giám sát nhẹ: `status` báo khi frontend còn chạy mà backend chết; dừng cả cặp | Code | Tránh tình trạng 5173 mồ côi |

Đề xuất: **PA-0 ngay cho buổi bảo vệ**; PA-1 (+ PA-2 nếu muốn một nút bấm) ở đợt sửa riêng, có unit test `test_demo_launcher.py`.

## E. Kết luận

- **TEST-01 đóng được một phần (PARTIAL).**
  - Đã có bằng chứng UI thật (VR) cho **ADMIN** và **REVIEWER** trên môi trường A, cùng **LECTURER chưa liên kết**.
  - **Còn BLOCKED:** LECTURER **đã liên kết** (TC-W2); thao tác Accept/Reject **qua UI** (TC-W1, có ghi); trạng thái "không có ứng viên" trên UI.
  - Bảo đảm chỉ đọc: DB không đổi, 0 request ghi.
- **BLOCKER nghiệp vụ mới:** **không**. Dữ liệu, thứ tự tác giả, bằng chứng, ca thiếu đơn vị và phân quyền route đều đúng.
- **Lỗi P1 ảnh hưởng demo:**
  - UI-01: trạng thái tĩnh ở Home.
  - UI-02: "Ứng viên 0" và "Chờ duyệt 144".
  - UI-03: thông báo "chưa cấu hình" ở tab Đơn vị tác giả.
  - UX-01: badge hai cỡ.
  - DATA-01: ca ACCEPTED chỉ có bằng chứng tên trên dữ liệu demo.
- **Cần chủ đồ án phê duyệt:**
  - (1) OPS-01: vị trí `backups\withjson_r2_demoA_20261017.dump`, cách xác thực (thêm `pgpass` hay script dùng `backend/.env`), và cho phép tạo DB rehearsal.
  - (2) OPS-02: chọn PA-0 cho demo; duyệt PA-1 / PA-2 cho đợt sửa.
  - (3) TC-W1 / TC-W2 trên bản sao TEST.
  - (4) Có cấu hình `AFFILIATION_SOURCE_DIR` cho môi trường A không (UI-03).
- **Có thể sang đợt sửa Dashboard / Design System:** **có, sau khi** (a) backup DB A (OPS-01) và (b) chốt danh sách P1 ở trên. Các lỗi P1 / P2 nằm ở frontend và chuỗi i18n, không đụng nghiệp vụ backend.
