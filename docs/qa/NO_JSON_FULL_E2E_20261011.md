# E2E luồng KHÔNG CÓ JSON giảng viên (CSV-only + đơn vị tác giả) — 11–12/10/2026

**Kết luận Gate 1:** **PASS cho bộ nguồn offline (660 bài hiện tại)**; **CHƯA tuyên bố** hoàn tất khả năng xử lý "CSV mới chỉ có CSV" (thiếu thu thập trực tuyến, cần bạn phê duyệt — mục 9). Hai việc ghi ở mục 9 cũng cần quyết định.

Mức bằng chứng: **[TN]** thực nghiệm (chạy thật, đối chiếu DB↔API↔UI) · **[T]** đọc code · **[CK]** chưa kiểm được.

---

## 1. Khảo sát code trước khi xây (Phần I.2)

| # | Câu hỏi | Trả lời (đọc code + chạy thử) | Phân loại |
|---|---|---|---|
| 1 | ADMIN làm gì được với CSV, chuẩn hóa, bóc tách tác giả? | Nhập CSV, xem lịch sử, chuẩn hóa công bố, bóc tách tác giả, xem công bố/tác giả — đủ trên UI | **CÓ SẴN** |
| 2 | Pipeline đơn vị OpenAlex/Crossref/ORCID có gì? | `author_affiliation.py` (căn chỉnh thuần), `affiliation_import.py` (ghi idempotent, fail-closed), `scripts/import_author_affiliations.py` (CLI) | **CÓ SẴN** |
| 3 | Có phụ thuộc `lecturers`/JSON/Craw? | **Không.** Chỉ đọc `publications`, `publication_authors`, `scopus_authors` | **CÓ SẴN** |
| 4 | ADMIN kích hoạt qua giao diện? | **Chưa — chỉ CLI** (bắt buộc đường dẫn CSV + thư mục khảo sát trên đĩa) | **CẦN NỐI GHÉP** → đã làm |
| 5 | Hiệu chỉnh thủ công có bằng chứng khi thiếu đơn vị? | **Không có** (không bảng, không API). Cần schema + audit | **CHƯA THỂ LÀM** (xin quyết định, mục 9) |
| 6 | LECTURER tạo độc lập với JSON? | **Không:** CHECK `ck_users_lecturer_account_required` buộc `lecturer_id`; không có API tạo tài khoản rời | **CẦN SỬA** → đã làm (migration, bạn đã duyệt) |
| 7 | LECTURER xem/tra cứu công bố khi chưa liên kết hồ sơ? | **Không:** `/publications`, `/search` chỉ ADMIN/REVIEWER; LECTURER chỉ có `/lecturers/me/*` | **CẦN SỬA** → đã làm (đọc-only, bạn đã duyệt) |
| 8 | RBAC chặn đọc dữ liệu học thuật khi chưa có JSON? | Có (chính là mục 6–7) | **CẦN SỬA** |
| 9 | `/reviews` phân biệt các lý do rỗng? | **Không** — một câu chung "Không có ứng viên phù hợp" | **CẦN SỬA** → đã làm |

## 2. Môi trường và an toàn [TN]

- Repo HEAD `2652dc0`, nhánh `main`, 2 stash cũ; trước nhiệm vụ 42 mục chưa commit, nay 72 (32 mục do nhiệm vụ này, liệt kê ở mục 10). **Không** reset/checkout/stash/commit/push.
- DB mới (PostgreSQL 55432, system id 7694238084633166136, owner `scopus_demo_user`, tạo bằng `demo_admin`, script dừng nếu DB đã tồn tại):

| DB | Dùng cho | Alembic |
|---|---|---|
| `scopus_ictu_test_nojson_20261011` | **E2E NO-JSON** (đóng băng sau Gate 1) | `f6a1b2c3d4e5` |
| `scopus_ictu_test_newcsv_20261011` | kịch bản "CSV mới", gọi API | `f6a1b2c3d4e5` |
| `scopus_ictu_test_pytest_20261011` | DB dùng-một-lần cho pytest | `f6a1b2c3d4e5` |

  (DB thứ 2 và 3 ngoài "hai DB" bạn nêu: cần cho pytest và cho kịch bản 5b; DB WITH-JSON chưa tạo.)
- Tiến trình riêng: backend **8021**, frontend **5193** (host `localhost`, khác `127.0.0.1:5173` nên cookie không đè), helper nạp CSV/đăng nhập **5191**, backend kịch bản CSV mới **8022** (đã tắt). Chứng minh: `pg_stat_activity` — kết nối của PID 21108 (8021) thuộc `scopus_ictu_test_nojson_20261011`.
- Backend demo **8001 (PID 3948)** và frontend **5173 (PID 8000)** không đổi; cổng 5432 không chạm.
- App DB `scopus_ictu_app` và teacher DB `scopus_ictu_demo_teacher_20261014`: chỉ đọc (phiên `default_transaction_read_only`). App DB sau nhiệm vụ: 660 công bố / 1.207 tác giả / 2.751 liên kết / 1 đợt nhập / 0 giảng viên / 0 affiliation, băm nội dung công bố–tác giả–liên kết **bằng** DB test (cùng CSV); không đổi so với trước nhiệm vụ.
- Tài khoản test tạo bằng `scripts.bootstrap_demo_admin` (mở rộng thêm `--role`): `ADMIN`, `LECTURER` **không liên kết hồ sơ**, `REVIEWER`. Mật khẩu ngẫu nhiên lưu ở `_postgres_demo_14_10/secrets/` (ngoài Git), không in.
- Nguồn CSV: `D:\DataFolder\ProjectIctu\DoAn\Truong_Quang_Huy_Scopus_Sep2026.csv`, SHA-256 `6a62fcf6…bf75d` (trùng tham chiếu; tệp trong trình duyệt tính lại cũng `6a62fcf6…` — byte giống hệt).
- **Không** nhập JSON giảng viên, **không** Craw, **không** matching.

## 3. Những gì đã xây (tối thiểu, tái sử dụng code có sẵn)

| Hạng mục | Nội dung |
|---|---|
| Migration `f6a1b2c3d4e5` | Bỏ `ck_users_lecturer_account_required`. `downgrade` từ chối chạy nếu còn LECTURER chưa liên kết. Kiểm: up → down → up trên DB pytest; `alembic current` = head |
| RBAC LECTURER (đọc-only) | `GET /publications`, `GET /publications/{eid}`, `GET /search`. Chi tiết: **ẩn** truy vết nhập (tên tệp, SHA, dòng) và liên kết giảng viên; `/search` trả `lecturers: []`; **export vẫn chỉ ADMIN**. Thêm bộ lọc `scopus_id` cho danh sách |
| Workflow đơn vị (ADMIN) | `affiliation_sources.py` (kiểm tra bộ nguồn, dựng đầu vào), `affiliation_workflow.py` (xem trước/áp dụng), 3 endpoint `GET /affiliations/overview`, `POST /preview`, `POST /apply`; tab **"Đơn vị tác giả"** trong trang Chuẩn hóa. Tái sử dụng nguyên `AffiliationImportService` |
| An toàn áp dụng | Thư mục nguồn **chỉ** từ cấu hình `AFFILIATION_SOURCE_DIR` (request có `extra=forbid`, không nhận đường dẫn); API không lộ đường dẫn máy chủ (chỉ tên thư mục); `fingerprint` của bản xem trước bắt buộc + `confirm`; khóa advisory (409 khi đang chạy); giao dịch duy nhất; audit `AFFILIATION_IMPORT_APPLIED/FAILED` ghi cùng giao dịch; từ chối khi `PREVIEW_STALE`, `SOURCE_MISMATCH`, `NOTHING_TO_APPLY` |
| `/reviews` rỗng | `GET /reviews/context` + 4 thông điệp: chưa có giảng viên · chưa sinh ứng viên · đã sinh nhưng không có cặp · bộ lọc trả 0. Không thêm nút chạy matching (backend chưa có API an toàn) |
| UI | Tab đơn vị; LECTURER có "Công bố" + "Tra cứu tác giả" (bấm tên tác giả → danh sách bài theo Scopus ID); dòng "Bằng chứng" dưới mỗi đơn vị (ORCID khai Scopus ID / chỉ khớp số tác giả+vị trí+tên) |
| Script | `bootstrap_demo_admin --role {ADMIN,REVIEWER,LECTURER}` |

## 4. Số liệu trước/sau (DB NO-JSON) [TN]

| | Trước | Sau CSV + chuẩn hóa + bóc tách | Sau áp dụng đơn vị |
|---|---|---|---|
| Giảng viên / ứng viên / định danh / known publications | 0 | 0 | **0** |
| Công bố / tác giả / liên kết / biến thể tên | 0 | 660 / 1.207 / 2.751 / 2.768 | không đổi |
| Tổ chức / resolution / dòng đơn vị | 0 | 0 | **217 / 5.502 / 4.147** |
| Đợt nhập | 0 | 1 (`APPLIED`) | 2 (thêm 1 `FAILED` do ca âm tính) |

Khớp tuyệt đối mốc tham chiếu 217 / 5.502 / 4.147, 7 xung đột giữ lại an toàn (3 Crossref corroborated + 4 Crossref verified → ghi `UNRESOLVED/WITHHELD_SOURCE_CONFLICT`, không phải lỗi).

## 5. Kết quả kiểm thử (đối chiếu DB ↔ API ↔ UI)

### 5.1 Import / chuẩn hóa / bóc tách (ADMIN, giao diện thật)
| Kiểm tra | Kết quả |
|---|---|
| Chọn tệp → "Kiểm tra dữ liệu" → "Xác nhận nhập" | **PASS** (660/660 hợp lệ) |
| Raw ↔ CSV: 660 dòng × mọi ô | **PASS** — 0 lệch (EID, Title, DOI, Source title, Authors, Author full names, Author(s) ID, và toàn bộ 22 cột) |
| Công bố ↔ CSV: thiếu/thừa/lệch DOI/Title/`source_title` | **PASS** — 0 / 0 / 0 / 0 / 0; `source_title` = `Source title`, không có "Scopus" |
| Tác giả: chuỗi (thứ tự, Scopus ID) | **PASS** — 660/660 bài đúng |
| API `GET /publications/{eid}` cho **660/660** bài | **PASS** — 0 lỗi HTTP; lệch trường/số tác giả/thứ tự/tên = 0 |
| Tra cứu theo EID, DOI, tiêu đề, tên tác giả, Scopus ID | **PASS** (EID→1, DOI→1, "deep learning"→27 = 27 trong DB; `57210589113`→42 bài = 42 trong DB; "Nguyen, Vinh"→2 tác giả) |
| Tệp trùng **byte giống hệt** | **PASS** — HTTP 409 + hộp thoại "Tệp dữ liệu đã được nhập trước đó" (Hủy / Xem đợt trước / Vẫn nhập lại); không tạo đợt mới. *(Đính chính: kiểm thử trước từng kết luận sai là "không phát hiện trùng"; xem `CSV_SOURCE_PROVENANCE_20261011.md`)* |
| Tệp không phải CSV | **PASS** — chặn ngay "Chỉ hỗ trợ tệp CSV." |
| CSV thiếu cột `EID` | **PASS** — đợt `FAILED`, 0/0, đợt 660 bản ghi giữ nguyên "Được sử dụng" |
| Số request ghi của tôi | khớp log: 2 upload (202 + 409), 1 normalize, 1 bóc tách, 1 preview+apply; **một** `POST /affiliations/apply` dù bấm 3 lần liên tiếp (single-flight) |

### 5.2 Đơn vị tác giả (không JSON)
| Kiểm tra | Kết quả |
|---|---|
| Xem nguồn: 4 tệp + SHA-256, 629 bài OpenAlex, 629 Crossref, 605 ORCID (190 khai Scopus ID), tải 2026-10-09 | **PASS** (đếm độc lập từ tệp = giống) |
| Xem trước (chỉ đọc, ~1 s): bao phủ 660 bài; có ở OpenAlex 629; ở Crossref 629; **không ở nguồn nào 31**; không DOI 25; DOI trùng 0; đối chiếu chéo 5.502 khớp | **PASS** |
| Nút "Xác nhận áp dụng" bị vô hiệu tới khi tick xác nhận | **PASS** |
| Áp dụng → 217/5.502/4.147; áp dụng lần 2 → "Không có gì mới để ghi", nút bị vô hiệu | **PASS** (idempotent) |
| API ↔ DB trạng thái từng vị trí tác giả (2.751) | **PASS** — VERIFIED 545 · CORROBORATED 2.053 · UNRESOLVED 153 · NOT_RECONCILED 0 (cả hai phía) |
| Vị trí có ≥1 dòng đơn vị | 2.291 (83,3%); **460 vị trí chưa có đơn vị nào**; 485 tác giả có ≥2 đơn vị khác nhau |
| UNRESOLVED không bị gán đơn vị | **PASS** — 0 dòng đơn vị gắn vào UNRESOLVED (DB) và 0 trên API |
| VERIFIED có bằng chứng ORCID | **PASS** — 0 VERIFIED thiếu ORCID (DB); 0 mục đơn vị VERIFIED thiếu `evidence.orcid` (API) |
| CORROBORATED không hiển thị là VERIFIED | **PASS** — nhãn "Đã đối chiếu · Chưa xác minh"; ghi chú riêng khi định danh xác minh qua nguồn không có đơn vị |

Bài mẫu thật đã mở trên UI (8 EID): `2-s2.0-105000434624` (VERIFIED có đơn vị **ICTU**, hai tác giả CORROBORATED); `…105000836388` (VERIFIED nguồn không có đơn vị; CORROBORATED không có đơn vị); `…85122186355` (tác giả có **9** đơn vị; một UNRESOLVED); `…105006527625` (UNRESOLVED vì tên không khớp); `…105006623990` (xung đột giữ lại: "Giữ lại do xung đột giữa các nguồn"); `…105026360236` (không DOI → "Không tìm thấy bài trên nguồn ngoài"); `…105022089001` (có DOI nhưng không có ở nguồn). 0 lỗi JS.

### 5.3 LECTURER độc lập (`lecturer_id = NULL`) [TN]
| Kiểm tra | Kết quả |
|---|---|
| Tài khoản LECTURER tồn tại trong DB đã migrate mà không có hồ sơ giảng viên | **PASS** |
| Đăng nhập; menu: Trang chủ, Công bố, Tra cứu tác giả, Hồ sơ, Công bố của tôi, Liên kết Scopus | **PASS** |
| Danh sách 660 công bố, **không** có nút "Xuất JSON" | **PASS** |
| Tìm theo EID / DOI / tiêu đề / tên tác giả / Scopus ID; bấm tên → danh sách bài của tác giả | **PASS** |
| Chi tiết: số tác giả, tên, Scopus ID, thứ tự, đơn vị, nguồn, bằng chứng, mức xác minh; **không** hiện truy vết nhập và liên kết giảng viên | **PASS** |
| `/profile`, `/my-publications`, `/identity` | nói rõ "Tài khoản chưa được liên kết với hồ sơ giảng viên" — **không tự gán danh tính** |
| Trang quản trị (`/imports`, `/normalization`, `/lecturers`, `/dashboard`, `/reviews`, `/audit-logs`) | chuyển về `/home` |
| API 403: `export`, `/authors`, `/imports`, `/users`, `/lecturers`, `/audits`, `/dashboard/summary`, `/reviews/*`, `/affiliations/*` (cả POST), `/lecturers/me/*` (`LECTURER_NOT_LINKED`) | **PASS** |
| REVIEWER: đọc công bố 200, `/reviews/*` 200, `/affiliations/*` & `/imports` & `/authors` 403, export 403 | **PASS** |

### 5.4 `/reviews` trống [TN]
Trong DB NO-JSON hiển thị: "Chưa có dữ liệu giảng viên ICTU để đối sánh. Màn hình này duyệt việc đối sánh giảng viên ICTU với tác giả Scopus; đây không phải màn hình phê duyệt chuẩn hóa công bố. Hệ thống đang có 660 công bố và 1.207 tác giả Scopus nhưng 0 giảng viên…". Ba trạng thái còn lại kiểm bằng integration test (DB cách ly).

### 5.5 Kịch bản "CSV mới" (5b) — DB `…newcsv…`, gọi API [TN, mức API, không UI]
CSV tổng hợp 30 dòng: 20 dòng thật (có trong bộ nguồn) + 10 dòng EID/DOI/Scopus ID **không có** trong bộ nguồn.

| Tình huống | Kết quả |
|---|---|
| A. Máy chủ **không** cấu hình nguồn | Công bố, tác giả bình thường (88 + 45 vị trí `NOT_RECONCILED`, "Chưa đối chiếu"); `preview` → `SOURCE_DIR_NOT_CONFIGURED`; `apply` không thể chạy. Không vỡ hệ thống |
| B. Có nguồn, CSV hỗn hợp | **Phát hiện lỗi thật:** tệp `author_affiliation_links.jsonl` của bộ khảo sát khiến `SOURCE_MISMATCH` (5.416 dòng "không thuộc CSV") và chặn áp dụng cho một CSV khác. **Đã sửa** (xem 6) |
| B′. Sau sửa | 20 bài thật → VERIFIED 20 · CORROBORATED 60 · UNRESOLVED 8 vị trí; 176 resolution **giống hệt** DB NO-JSON (trạng thái, lý do, SHA payload, số dòng đơn vị; 176/176). 10 bài mới (45 vị trí) → **toàn bộ UNRESOLVED / `NO_EXTERNAL_WORK`, 0 đơn vị bịa** |

Kết luận 5b: luồng **không phụ thuộc dữ liệu demo** và trung thực; nhưng với CSV mới, **không có cách tự có đơn vị nếu chưa có bộ nguồn của chính các bài đó**.

## 6. Lỗi đã sửa

| # | Lỗi | Gốc | Sửa | Test |
|---|---|---|---|---|
| 1 | LECTURER không thể tồn tại nếu không có JSON; không đọc được công bố | CHECK DB + RBAC | migration + đọc-only (đã duyệt) | `test_unlinked_lecturer_account`, `test_publication_api`, `test_search_api` |
| 2 | Đối chiếu chéo nghiêm ngặt khiến bộ nguồn của CSV khác chặn áp dụng | CLI strict dùng chung cho workflow | `strict_cross_check` (CLI giữ strict; workflow chỉ kiểm bài có trong tệp, lệch vẫn chặn) | `test_survey_jsonl_for_other_papers_does_not_block…` |
| 3 | Báo cáo E2E trước ghi sai "không phát hiện trùng tệp" | tệp tải lại mất BOM | đính chính (`CSV_ONLY_E2E…`, `CSV_SOURCE_PROVENANCE…`) | thực nghiệm 409 ở 5.1 |
| 4 | `/reviews` rỗng một thông điệp chung | UX | `/reviews/context` + 4 thông điệp | `test_review_context_api` |

## 7. Test đã chạy
- **Backend toàn bộ: 880 passed** (trước nhiệm vụ 858 passed + 3 test khẳng định "LECTURER bị chặn" — cố ý đổi theo quyết định của bạn; thêm 19 test mới: 12 + 2 + 3 + 1 + 1). Tệp mới: `test_affiliation_workflow_api` (12: RBAC, nguồn thiếu/thiếu tệp/không lộ đường dẫn, luồng đủ không giảng viên, `confirm`, `PREVIEW_STALE`, không nhận đường dẫn, khóa đồng thời, JSONL bị sửa, JSONL của CSV khác), `test_review_context_api` (2), `test_unlinked_lecturer_account` (3), `test_bootstrap_demo_admin` (+1). Các test CLI affiliation/importer cũ vẫn xanh (CLI giữ hành vi).
- **Frontend:** `tsc --noEmit` sạch; `vite build` thành công (xuất ra thư mục tạm, không đụng `frontend/dist`). Repo chưa có bộ test frontend tự động **[CK]**.
- Migration: up→down→up trên DB pytest; DB NO-JSON dựng từ đầu bằng `alembic upgrade head` đến `f6a1b2c3d4e5`.

## 8. Ảnh QA và hạn chế
`docs/qa/nojson_full_e2e_20261011/` (5 ảnh): `800_00_admin_xem_nguon_truoc_ap_dung`, `800_01_admin_don_vi_tac_gia_sau_ap_dung`, `800_02_admin_chi_tiet_cong_bo_don_vi`, `800_03_admin_reviews_trong_giai_thich`, `800_04_lecturer_chi_tiet_cong_bo`. Công cụ chụp **chỉ trả ≤ 800 px** (khung giả lập 1440×900 bị thu còn 800×500, chữ không đọc được) → **không đạt chuẩn luận văn**. Bạn cần tự chụp trong Chrome (1440×900 hoặc 1920×1080, DevTools → Capture screenshot): tab "Đơn vị tác giả" (trước/sau áp dụng), chi tiết công bố `2-s2.0-105000434624` và `2-s2.0-105000836388` bằng ADMIN và bằng LECTURER, `/reviews` rỗng, `/publications?scopus_id=57210589113`, hộp thoại "Tệp đã được nhập trước đó".

## 9. Giới hạn và việc cần bạn quyết định
1. **Thu thập trực tuyến (OpenAlex/Crossref/ORCID) chưa làm.** Cần phê duyệt trước vì: (a) gọi mạng ngoài từ máy chủ, (b) giới hạn tần suất/lỗi mạng/thiếu kết quả, (c) lưu provenance, (d) quyền truy cập. Đề xuất: ADMIN bấm "Thu thập đơn vị" → xem trước danh sách DOI sẽ gửi → xác nhận → tác vụ nền ghi vào thư mục cache `AFFILIATION_SOURCE_DIR` (cùng định dạng 3 tệp hiện có, mỗi bản ghi kèm `retrieved_at`), dùng `harvest_affiliation.py` đã có làm gốc; dừng khi bị giới hạn; báo DOI không có kết quả. Cho tới khi duyệt, **"CSV mới chỉ với đầu vào CSV" chưa hoàn tất**. Kết quả offline này chỉ là PASS cho bộ nguồn chuẩn bị sẵn.
2. **CSV Scopus kèm `Authors with affiliations`:** parser hiện tại **không** hỗ trợ (không có cột, không có test, không có schema) — không tuyên bố.
3. **Hiệu chỉnh/duyệt đơn vị thủ công có dẫn nguồn:** chưa có. Cần bảng ghi đè + audit (thay đổi schema), và phải tách ba hành động "đã xem xét", "hiệu chỉnh có dẫn nguồn", "xác minh định danh" — **không** có nút nâng CORROBORATED→VERIFIED. Chưa làm, chờ quyết định.
4. **Tài khoản LECTURER rời:** chưa có UI/API cho ADMIN tạo (mới có `bootstrap_demo_admin --role`, chỉ cho môi trường demo/test). Cần `POST /users` (ADMIN, chỉ LECTURER/REVIEWER, chính sách mật khẩu, audit) nếu muốn giao diện.
5. `PATCH /users` đổi vai trò sang LECTURER vẫn đòi hồ sơ (`LECTURER_PROFILE_REQUIRED`) — giữ nguyên (bảo thủ).
6. `AFFILIATION_SOURCE_DIR` là cấu hình của người vận hành; **bộ nguồn không nằm trong sản phẩm** (đúng yêu cầu: không là nguồn duy nhất, không bắt buộc).
7. **Mức bao phủ thực tế (không phải 100%):** VERIFIED 19,8% vị trí; CORROBORATED 74,6%; UNRESOLVED 5,6%; 460/2.751 (16,7%) vị trí chưa có đơn vị nào. Đơn vị là lời khai nguồn ngoài, **không** do Scopus xác nhận.
8. `/identity` của LECTURER chưa liên kết hiển thị giọng "Không thể tải…" (kèm giải thích đúng) — nên mềm hơn; chưa sửa.
9. REVIEWER vẫn xem được truy vết nhập (giữ nguyên hành vi cũ).
10. Teacher DB `scopus_ictu_demo_teacher_20261014` vẫn có `source_title = 'Scopus'` ở 660 bài và ở Alembic `a9c2e4f71b30` — không đụng theo yêu cầu; chỉ ghi nhận.
11. Giao diện chưa có test tự động; kiểm bằng trình duyệt tích hợp + script đọc DOM.

## 10. Tệp thay đổi (32 mục, chưa commit)
Backend: `alembic/versions/f6a1b2c3d4e5_…` (mới), `app/models/governance.py`, `app/core/config.py`, `app/api/v1/router.py`, `endpoints/{affiliations(mới),publications,search,reviews}.py`, `schemas/review_api.py`, `services/{affiliation_sources(mới),affiliation_workflow(mới),publication_queries}.py`, `scripts/{bootstrap_demo_admin,import_author_affiliations}.py`, tests (3 mới + 2 sửa + `test_bootstrap_demo_admin`).
Frontend: `api/{affiliations(mới),publications,reviews}.ts`, `types/{publication,review}.ts`, `pages/Normalization/{AffiliationsTab(mới),index}.tsx`, `pages/Publications/{index,Detail,AuthorAffiliations}.tsx`, `pages/Search/index.tsx`, `pages/ApprovalQueue/index.tsx`, `pages/Home/index.tsx`, `components/common/Sidebar.tsx`, `App.tsx`.

## 11. Tài liệu thiết kế cần đồng bộ (không tự sửa)
`docs/design/database/{CONSTRAINTS_BUSINESS_RULES,CONSTRAINTS_CATALOG,DATA_DICTIONARY}.md` và `source/schema_snapshot.json` (bỏ `ck_users_lecturer_account_required`); `usecase/specs/UCS-G2_quan_ly_ho_so.md` (điều kiện trước); use case/activity/sequence mới: *ADMIN xem trước–áp dụng đơn vị tác giả*, *LECTURER tra cứu công bố/tác giả (đọc-only)*, *`/reviews` rỗng theo nguyên nhân*; Figma: tab "Đơn vị tác giả", menu LECTURER, trang rỗng `/reviews`. Không tạo sơ đồ hàng loạt; không nhận chatbot/AI đã hoàn thành.

## 12. Gate 1
| Điều kiện | Kết quả |
|---|---|
| ADMIN chuẩn hóa + đối chiếu đơn vị từ UI, không JSON | **PASS** (bộ nguồn offline) |
| LECTURER độc lập xem được trong phạm vi quyền | **PASS** |
| Số tác giả/thứ tự đúng CSV | **PASS** (660/660) |
| Đơn vị và trạng thái hiển thị trung thực | **PASS** |
| Không lỗi blocking luồng chính | **PASS** (lỗi 2 đã sửa) |
| Thay đổi liên quan đã kiểm thử | **PASS** (880 + build) |
| Không tác động App DB / teacher DB | **PASS** |
| Không bypass UI / không giảng viên giả / không SQL thay chức năng | **PASS** (không có lệnh ghi SQL tay; mọi ghi qua API/UI/alembic/bootstrap) |
| "CSV mới chỉ có CSV" | **CHƯA hoàn tất** (mục 9.1) |
