# Nghiệm thu hai chế độ SCOPUS–ICTU: không JSON → có JSON + Craw (11–12/10/2026)

Chi tiết số liệu và bằng chứng: `NO_JSON_FULL_E2E_20261011.md`, `WITH_JSON_CRAW_FULL_E2E_20261011.md`. Nguồn gốc tệp CSV: `CSV_SOURCE_PROVENANCE_20261011.md`.

| Cổng | Kết quả | Phạm vi |
|---|---|---|
| **Gate 1** (không JSON) | **PASS** cho bộ nguồn offline (660 bài) | ADMIN chuẩn hóa + áp dụng đơn vị qua giao diện; LECTURER độc lập tra cứu; số liệu đúng CSV |
| "CSV mới chỉ có CSV" | **CHƯA hoàn tất** | thiếu thu thập trực tuyến (cần bạn phê duyệt) |
| **Gate 2** (JSON + Craw) | **PASS** có giới hạn | không phá kết quả no-JSON; mọi duyệt thử ở DB test |

Kiểm thử: backend **880 passed**; frontend `tsc` + `vite build` sạch. App DB / teacher DB / tiến trình demo không bị tác động.

---

## 1. ADMIN có hoàn thành quy trình Scopus khi KHÔNG có JSON giảng viên không?
**Có, với bộ nguồn đơn vị chuẩn bị sẵn.** Trên DB mới (0 giảng viên) ADMIN làm hết bằng giao diện: chọn CSV → kiểm tra → nhập (xử lý tệp trùng 409, tệp sai định dạng, thiếu cột `EID`) → chuẩn hóa công bố → bóc tách tác giả → tab "Đơn vị tác giả" (xem nguồn → xem trước → xác nhận → áp dụng). Kết quả khớp CSV từng ô: 660 công bố, 1.207 tác giả, 2.751 vị trí, thứ tự đúng 660/660; đơn vị 217 tổ chức / 5.502 resolution / 4.147 dòng. Không giảng viên, ứng viên, định danh nào được tạo.

**Chưa có:** với một CSV *hoàn toàn mới*, hệ thống **không tự lấy được đơn vị**. Thử nghiệm: 10 bài mới → 45 vị trí đều `UNRESOLVED / NO_EXTERNAL_WORK`, 0 đơn vị bịa; nếu máy chủ không có bộ nguồn → "Chưa đối chiếu", không vỡ. Muốn xử lý CSV mới cần thu thập OpenAlex/Crossref/ORCID trực tuyến — **cần bạn phê duyệt** (xem mục 6).

## 2. LECTURER có đăng nhập và tra cứu mà không cần liên kết JSON không?
**Có.** Cần một sửa đổi đã được bạn duyệt: bỏ ràng buộc DB `ck_users_lecturer_account_required` (migration `f6a1b2c3d4e5`) và mở **đọc-only** `/publications`, `/search` cho LECTURER. Tài khoản `lecturer_id = NULL` đăng nhập, xem 660 công bố, tìm theo EID / DOI / tiêu đề / tên tác giả / Scopus ID, bấm tên tác giả để xem các bài của họ, xem chi tiết với tác giả–thứ tự–đơn vị–nguồn–bằng chứng–mức xác minh. Không thấy truy vết nhập, liên kết giảng viên, danh sách giảng viên; không export/nhập/xóa; 403 ở mọi API quản trị; `/lecturers/me/*` trả "chưa liên kết" — **không tự gán danh tính Scopus**. LECTURER có hồ sơ + định danh được duyệt thì thấy thêm "Công bố của tôi" (27 bài trong thử nghiệm, bằng đúng tra cứu theo Scopus ID).

Hạn chế: chưa có UI/API để ADMIN tạo tài khoản LECTURER **không** hồ sơ (hiện chỉ script demo `bootstrap_demo_admin --role`).

## 3. Bài báo có bao nhiêu tác giả, đơn vị từng người và mức xác minh đến đâu?
Ví dụ thật `2-s2.0-105000434624` (xem trên giao diện bằng ADMIN hoặc LECTURER): **3 tác giả**, theo thứ tự:

| STT | Tác giả (Scopus ID) | Mức | Đơn vị (nguồn) | Bằng chứng |
|---|---|---|---|---|
| 1 | Nguyen, Thanh-Hai (57560524600) | **Đã xác minh định danh** | Faculty of Information Technology, University of ICT (**ICTU**), Thai Nguyen, Vietnam (Crossref, OpenAlex) | ORCID 0000-0003-1801-5887 khai Scopus ID này |
| 2 | Kim, Kyoung-Sook (57193455307) | Đã đối chiếu · **Chưa xác minh** | Kyonggi University / Contents Convergence Software Research Institute… (3 dòng) | chỉ khớp số tác giả + vị trí + tên |
| 3 | Kim, Kwanghoon Pio (57297022700) | Đã đối chiếu · **Chưa xác minh** | 3 dòng đơn vị | như trên |

Trên toàn bộ 660 bài (2.751 vị trí): **VERIFIED 545 (19,8%) · CORROBORATED 2.053 (74,6%) · UNRESOLVED 153 (5,6%)**; 2.291 vị trí (83,3%) có ≥1 đơn vị, **460 vị trí chưa có đơn vị nào**; 485 tác giả có ≥2 đơn vị. Đơn vị là lời khai của nguồn ngoài (OpenAlex/Crossref), **không** do Scopus xác nhận; "Đã đối chiếu" **không** phải "Đã xác minh"; UNRESOLVED không bị gán đơn vị; không sao chép đơn vị cấp bài xuống từng tác giả. Không có con số "100% chính xác".

## 4. JSON và Craw bổ sung giá trị cụ thể gì?
Số liệu thực nghiệm (cùng 660 công bố):

| | Bổ sung |
|---|---|
| **JSON giảng viên** (410 hồ sơ) | Là điều kiện để có đối sánh: cho 39 ứng viên (37 giảng viên, 35 tác giả Scopus) nhờ **66 bằng chứng tên**; cho hàng đợi `/reviews`, danh sách/hồ sơ giảng viên, và tài khoản giảng viên. Không tự khẳng định danh tính Scopus; 16 hồ sơ đồng tên (7 nhóm) cần người duyệt |
| **Craw** (327 công bố đã biết, 48 giảng viên) | **Không sinh thêm ứng viên** (cùng `pairs_sha256` có/không Craw). Thêm **41 bằng chứng công bố** (32 DOI chính xác + 9 tiêu đề chính xác) cho 5 ứng viên, giúp người duyệt thấy ví dụ cụ thể (ví dụ Vũ Đức Quang ↔ 57193082389 có 17 công bố chung). 82/660 công bố Scopus (12,4%), 30/410 giảng viên (7,3%) có liên hệ với Craw |
| **Giới hạn đo được** | DOI khớp chứng minh *hai công bố là một*, không chứng minh Scopus Author ID của giảng viên; 24/30 giảng viên có công bố trùng Craw nhưng **không có ứng viên nào** vì ứng viên chỉ do quy tắc tên sinh ra |

## 5. Hệ thống còn thiếu gì để trình bày trung thực với GVHD và hội đồng?
**Đã làm rõ/ phải nói thẳng khi trình bày**
1. Đơn vị tác giả đến từ **nguồn ngoài đã tải sẵn**, phủ 83% vị trí, chỉ 20% ở mức "đã xác minh"; không phải dữ liệu của Scopus. Không nêu "100%".
2. Craw và JSON là **nguồn phụ trợ cho đối sánh giảng viên**, không phải điều kiện của chuẩn hóa Scopus. Không có gold labels → **không nêu precision/recall**.
3. Sinh ứng viên và nạp Craw hiện là **công cụ dòng lệnh**; giao diện chỉ để duyệt.
4. Chức năng chatbot/AI **chưa có**; không được nêu là đã hoàn thành.

**Còn thiếu (đề xuất theo thứ tự ưu tiên; mục 1–3 cần quyết định của bạn)**
1. **Thu thập đơn vị trực tuyến** (OpenAlex/Crossref/ORCID) do ADMIN kích hoạt: xem trước danh sách DOI sẽ gửi → xác nhận → tác vụ nền có giới hạn tần suất, xử lý lỗi mạng/thiếu kết quả, lưu `retrieved_at` và nguồn; ghi vào thư mục cache cùng định dạng 3 tệp hiện có. Không có bước này, "CSV mới chỉ có CSV" chưa hoàn tất.
2. **Hiệu chỉnh/xem xét đơn vị thủ công có dẫn nguồn:** cần bảng ghi đè + audit (đổi schema); tách ba hành động *đã xem xét* / *hiệu chỉnh có dẫn nguồn* / *xác minh định danh*; **không** có nút nâng CORROBORATED → VERIFIED.
3. **Hỗ trợ CSV Scopus xuất kèm `Authors with affiliations`:** parser hiện không hỗ trợ (chưa có cột, test, schema).
4. Tạo tài khoản LECTURER/REVIEWER không hồ sơ qua UI/API (ADMIN).
5. Sinh ứng viên ngược từ DOI Craw; nút chạy matching an toàn trên UI (kèm xem trước/fingerprint như workflow đơn vị).
6. Bộ test giao diện tự động; chụp ảnh luận văn ở độ phân giải thật (công cụ hiện chỉ ≤ 800 px).
7. Đồng bộ tài liệu thiết kế (danh sách ở `NO_JSON_FULL_E2E…` mục 11) và xử lý `source_title = 'Scopus'` còn lại ở teacher DB (không đụng theo yêu cầu).

## 6. Việc cần bạn quyết định
| # | Quyết định | Tác động |
|---|---|---|
| 1 | Cho phép thu thập đơn vị trực tuyến (mạng ngoài, tần suất, lưu provenance)? | quyết định "CSV mới chỉ có CSV" có hoàn tất không |
| 2 | Cho phép thêm bảng/audit để hiệu chỉnh đơn vị thủ công? | đổi schema |
| 3 | Có thêm `POST /users` (ADMIN tạo LECTURER/REVIEWER không hồ sơ)? | thêm bề mặt tạo tài khoản |
| 4 | Có áp dụng migration `f6a1b2c3d4e5` lên App DB / teacher DB khi tiếp tục demo? | hiện **chưa** áp dụng; code mới yêu cầu cột như cũ nên chạy được, nhưng LECTURER chưa liên kết chỉ tạo được sau migration |

## 7. Danh sách DB test và dọn dẹp
`scopus_ictu_test_nojson_20261011` (đối chứng, đóng băng) · `…withjson_r2_20261011` (chính) · `…jsononly_20261011` (khôi phục trước Craw) · `…newcsv_20261011` (CSV mới, API) · `…pytest_20261011` (pytest) · `…withjson_20261011` (bỏ). Tất cả còn nguyên, không xóa (chờ phép). Mọi tiến trình do tôi mở (8021, 8022, 8031, 5191–5194) đã tắt; demo 5173/8001 giữ nguyên. Không commit/push.
