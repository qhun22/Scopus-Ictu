# KẾ HOẠCH V4 — HOÀN THIỆN TÀI SẢN KỸ THUẬT ĐỒ ÁN TRƯỚC 14/10/2026 (TASK 18)

> **Loại tài liệu:** kiểm kê + đối chiếu + lập kế hoạch. **Chưa triển khai** sơ đồ, thiết kế hay thay đổi hệ thống nào.
> **Ngày soạn:** 09/10/2026 (thứ Sáu). **Hạn tận dụng Claude Code:** 14/10/2026 (thứ Tư). **Trạng thái:** BẢN NHÁP CHỜ NGƯỜI DÙNG / CHATGPT DUYỆT.
> **Repository:** `D:\DataFolder\ProjectIctu\DoAn\Scopus-Ictu` — `main` @ `530bf0f`, working tree sạch, chưa push.

---

## 0. Cách đọc và phương pháp (đọc trước)

### 0.1. Nhãn độ tin cậy dùng xuyên suốt

| Nhãn | Nghĩa |
|---|---|
| **ĐÃ XÁC MINH** | Task 18 đã tự đọc trực tiếp nguồn (tệp, mã, schema) và ghi rõ nơi đọc. |
| **THEO BÁO CÁO TRƯỚC** | Lấy từ báo cáo Task 15–17 (`docs/demo/*`), **không chạy lại** trong Task 18. |
| **SUY LUẬN / CẦN ĐỐI CHIẾU** | Kết luận suy ra, chưa có nguồn xác nhận trực tiếp. |
| **CHƯA TÌM THẤY NGUỒN CHÍNH THỨC** | Không có tệp/chứng cứ trong các vị trí thuộc dự án. |

### 0.2. Task 18 đã làm gì (và không làm gì)

| Việc | Cách thực hiện | Ghi chú an toàn |
|---|---|---|
| Đọc đề cương chính thức | `pdftotext` trên PDF của GVHD; trích văn bản `DoAn.docx` + 6 ảnh nhúng bằng `zipfile` vào thư mục tạm **ngoài repo** | Chỉ đọc; không sửa tệp gốc |
| Đọc schema PostgreSQL thực | `pg_restore --schema-only` trên bản sao lưu `_quan_ly_do_an\backups\task17\teacher_for_e2e_t17_20261009.dump` (bản `pg_dump` của teacher DB, `alembic_version = a9c2e4f71b30`) | **Cụm PostgreSQL demo (127.0.0.1:55432) lúc kiểm kê KHÔNG chạy:** Task 18 đã thử **một** kết nối chỉ-đọc (thông số lấy từ tệp môi trường demo, không in giá trị bí mật) và bị từ chối; sau đó **không khởi động cụm** và **không kết nối** cổng 5432 hay DB nào khác. Schema lấy từ bản dump, không phải từ ORM |
| Liệt kê API | Dựng `app.openapi()` trong tiến trình Python tách biệt (biến môi trường giả, không mở kết nối DB) → 57 thao tác | Không gọi mạng/DB |
| Đọc mã nguồn, ADR, freeze, tài liệu demo, C3 | Đọc trực tiếp; C3 đọc qua `docs/demo/TIEN_DO_V4_VA_BACKLOG_C3.md` và `evidence/task17/C3_A3_doc.md` + README trong worktree C3 | Không `git checkout`/`apply` nhánh C3 |
| Ảnh bằng chứng | Liệt kê 29 ảnh, đọc kích thước, mở 2 ảnh để đánh giá chất lượng/nội dung | Không sao chép ảnh vào Git |
| **KHÔNG làm** | Không chạy test/migration, không ghi DB, không APPROVE, không sửa CSV/JSON/Craw, không push, không stash/worktree/reset, không tạo nhãn C3 | Đúng mục XVI của yêu cầu Task 18 |

### 0.3. Giới hạn của kiểm kê này (nêu thật)

1. **PDF đề cương mất dấu tiếng Việt khi trích văn bản** (lỗi ánh xạ phông). Nội dung ở mục 2 là **bản đọc lại có đối chiếu ngữ cảnh**; tên đề tài và các mốc đã đối chiếu thêm với bìa `DoAn.docx`. **Người dùng cần mở PDF gốc đọc lại các mục 5, 7a, 7b, 8, 9 một lần** (≈15 phút) trước khi dùng làm căn cứ chính thức (việc `REQ-01`).
2. Bảng tiến độ 10 tuần (mục 9 PDF) bị lệch cột khi trích nên chỉ dùng ở mức tổng quát.
3. Số liệu dữ liệu (410/660/1.207…, 797 test…) **THEO BÁO CÁO TRƯỚC**; Task 18 chỉ kiểm lại những gì đọc được từ schema/mã.
4. Task 18 chưa xem được giao diện đang chạy (cụm DB không bật); đánh giá UI dựa trên mã `frontend/src` và ảnh Task 16–17.

---

# 1. EXECUTIVE SUMMARY

## 1.1. Kết luận một đoạn

Phần **mềm** (CLO3–CLO4: ≈50% điểm theo ma trận CLO của đề cương) đã ở mức mạnh: 24 bảng PostgreSQL có ràng buộc chặt, 57 API, 15 màn hình, 3 vai trò, 797 test, đã chạy thử E2E trên DB test. Phần **thiết kế và phân tích** (CLO1–CLO2: ≈50% điểm) lại là chỗ yếu nhất: **chưa có một sơ đồ nào ở dạng nguồn chỉnh sửa được**, năm sơ đồ duy nhất (BPMN, Use Case, 3 ERD) nằm dưới dạng ảnh trong `DoAn.docx` và **lệch rõ so với hệ thống thực tế**; **chưa có Figma/mockup**; chưa có bảng yêu cầu chức năng/phi chức năng, chưa có Use Case Specification, chưa có UML kiến trúc/sequence/activity. Ngoài ra có hai yêu cầu của đề cương mà hệ thống chỉ đáp ứng một phần (mức độ phù hợp; "đơn vị/mã định danh" trong gợi ý ánh xạ) và một yêu cầu chưa đáp ứng (đánh giá trên tập đối chiếu do GVHD xác nhận). Khả năng cao nhất để tạo giá trị trước 14/10 là **sinh tài sản thiết kế trực tiếp từ schema và mã thật** (ERD, data dictionary, ma trận quyền, sơ đồ UML), vì phần này tự động hóa được cao và chính là điểm đang thiếu.

## 1.2. Mức đáp ứng theo chuẩn đầu ra (PI) của đề cương

| PI (trọng số CLO) | Nội dung | Mức hiện tại | Ghi chú ngắn |
|---|---|---|---|
| 1.1 (CLO1 20%) | Khảo sát quy trình + BPMN + mô tả từng bước | **MỘT PHẦN** | Có sơ đồ quy trình (ảnh), nhưng lệch hệ thống; chưa phải BPMN; chưa có bảng bước/người thực hiện/vào–ra |
| 1.2 | Bảng yêu cầu chức năng + phi chức năng, tiêu chí nghiệm thu thống nhất GVHD | **THIẾU** | Chưa có tài liệu; chưa có biên bản thống nhất tiêu chí với GVHD |
| 1.3 | ≥5 UC chính + đặc tả | **MỘT PHẦN** | Có sơ đồ UC (ảnh, lệch); **chưa có đặc tả UC** |
| 2.1 (CLO2 30%) | ERD, khóa định danh, ràng buộc, chống trùng | **MỘT PHẦN** | DB thật rất tốt; **ERD cũ không khớp DB**; chưa có data dictionary/ERD thật |
| 2.2 | Kiến trúc UML (web, Web API, tầng dữ liệu), luồng nhập–xử lý–duyệt–xuất | **THIẾU** | Chưa có sơ đồ UML nào ngoài UC |
| 2.3 | Figma: danh sách, chi tiết, nhập dữ liệu, so sánh trước/sau chuẩn hóa, hàng đợi phê duyệt, thống kê | **THIẾU** | Không có Figma/mockup; màn "so sánh trước/sau" **chưa tồn tại** trong phần mềm |
| 3.1 (CLO3 40%) | CSDL quan hệ; lưu riêng dữ liệu gốc/kết quả; kịch bản khởi tạo, sao lưu, phục hồi | **PHẦN LỚN ĐẠT** | Khởi tạo bằng Alembic ✔; sao lưu/phục hồi chỉ có thao tác `pg_dump` rời rạc, **chưa có quy trình/tài liệu** |
| 3.2 | Web API + UI tương thích máy tính/điện thoại; xác thực + phân quyền | **PHẦN LỚN ĐẠT** | RBAC ✔; tương thích điện thoại **chưa có bằng chứng** (chưa chụp ở khổ mobile) |
| 3.3 | ≥5 UC cài đặt + kiểm thử; nhập lỗi không sinh trùng, báo lỗi theo dòng, duyệt trước khi áp dụng | **ĐẠT** | JSON: preview→import ✔; CSV: SHA-256 chống trùng ✔, lỗi theo dòng ✔ (CSV không có bước xem trước, chuẩn hóa là bước riêng) |
| 3.4 | Gợi ý ánh xạ theo mã định danh, tên, đơn vị, công bố; hiển thị căn cứ + mức độ phù hợp; đánh giá trên tập đối chiếu GVHD | **MỘT PHẦN / CHƯA ĐÁNH GIÁ** | Chỉ **tên** + **công bố đã biết (DOI/tiêu đề trùng khớp)**; không dùng ORCID/đơn vị; **không có điểm/mức độ phù hợp**; chưa có đánh giá (C3 chưa chạy) |
| 4.1 (CLO4 10%) | Triển khai môi trường thử nghiệm; cấu hình bảo mật cơ bản; hướng dẫn cài đặt/sử dụng/sao lưu/phục hồi | **PHẦN LỚN ĐẠT** | Localhost BAT ✔, hướng dẫn sử dụng ✔; hướng dẫn sao lưu/phục hồi ✖; `compose*.yaml` chưa có bằng chứng chạy |
| 4.2 | Bộ dữ liệu kiểm thử; biên bản kiểm thử mong đợi/thực tế; không coi dữ liệu giả là thật | **PHẦN LỚN ĐẠT** | `BAO_CAO_KIEM_THU_CHUC_NANG.md` ✔; chưa có danh mục bộ dữ liệu kiểm thử theo từng loại lỗi |

## 1.3. Đã hoàn thành (ĐÃ XÁC MINH hoặc THEO BÁO CÁO TRƯỚC)

- Hệ thống đầy đủ M0 → M2.8, Completion-1/2 (đóng băng), Task 04–17 (demo localhost). **THEO BÁO CÁO TRƯỚC:** 797 test PASS; TypeScript/Vite PASS; ADMIN/REVIEWER/LECTURER E2E trên DB test.
- Dữ liệu teacher (**THEO BÁO CÁO TRƯỚC**): 410 hồ sơ ICTU + 1 seed, 660 công bố, 1.207 tác giả Scopus, 2.751 vị trí tác giả, 5.502 resolution affiliation, 4.147 liên kết, 40 ứng viên PENDING, 0 APPROVED.
- Tài liệu: 4 ADR, 7 tài liệu freeze, 5 tài liệu demo (`docs/demo/`), 29 ảnh chụp (ngoài Git).

## 1.4. Còn thiếu (tổng hợp — chi tiết ở mục 2, 10, 11)

1. **Tài sản phân tích–thiết kế dạng nguồn chỉnh sửa được:** ERD (7), data dictionary, UC (6 sơ đồ + 8 đặc tả), kiến trúc (2), BPMN (1), sequence (8), activity (7), state (4), DFD (1).
2. **Thiết kế giao diện (Figma):** 0 tệp; cần ≥ 6 màn do đề cương nêu tên, trong đó 1 màn chưa tồn tại.
3. **Bảng FR/NFR + tiêu chí nghiệm thu; truy vết yêu cầu → UC → bảng → màn hình → test.**
4. **Tập đối chiếu do GVHD xác nhận + đánh giá chất lượng đối sánh** (đề cương yêu cầu; C3 mới có công cụ trên nhánh, chưa có nhãn, chưa chạy).
5. **Ảnh bằng chứng độ phân giải đủ cho báo cáo** (hiện tối đa 800×453 px).
6. **Quy trình sao lưu/phục hồi** và danh mục bộ dữ liệu kiểm thử.
7. **Giải trình trung thực những phần chưa đạt** (mức độ phù hợp, đơn vị/ORCID, DOI chuẩn hóa, hoàn tác duyệt, thống kê).

## 1.5. Rủi ro cao nhất (xếp theo mức nghiêm trọng)

| # | Rủi ro | Vì sao nghiêm trọng | Xử lý |
|---|---|---|---|
| R1 | **Sơ đồ trong `DoAn.docx` (BPMN/UC/3 ERD) không khớp hệ thống thật** — ERD có bảng `approval_queue`, `standardized_data`, `upload_batches`, `export_audit_log`, `author_extracted`… **không tồn tại** trong DB; khóa `bigserial` trong khi DB dùng `uuid`; "Match Score", "rollback 72 giờ", "Operator", xuất Excel/CSV **không có** trong phần mềm (chi tiết Phụ lục A) | Giảng viên kiểm tra tính trung thực/nhất quán; nhật ký tuần đã nộp mô tả hệ thống khác sản phẩm | Quyết định D1; vẽ lại theo hệ thống thật; ghi phiên bản "thiết kế ban đầu" nếu giữ |
| R2 | Đề cương yêu cầu **Figma** (PI 2.3) nhưng không có công cụ Figma trong phiên; màn "so sánh trước/sau chuẩn hóa" chưa tồn tại | Thiếu 1 sản phẩm bắt buộc của CLO2 | Quyết định D2, D4; chuẩn bị nguồn thiết kế + hướng dẫn nhập vào Figma |
| R3 | **Chưa có tập đối chiếu GVHD và chưa có đánh giá chất lượng** (PI 3.4, mục tiêu 5) | Có thể bị coi là thiếu phần kiểm thử chất lượng; C3 bị chặn (cần DBA, nhãn người, Commit #2) | Quyết định D5; chuẩn bị quy trình + thư đề nghị GVHD cung cấp nhãn; **không bịa số liệu** |
| R4 | Tuyên bố vượt khả năng: "mức độ phù hợp", gợi ý theo "mã định danh/đơn vị" — **không có điểm số; bộ sinh ứng viên chỉ so khớp tên (4 mức chuẩn hóa) + công bố đã biết trùng DOI/tiêu đề** | Dễ bị hỏi vặn khi bảo vệ | Mô tả đúng; quyết định D3 |
| R5 | `publications.doi` **lưu nguyên văn (chỉ cắt khoảng trắng)**, **không có thực thể "nguồn xuất bản"**; chuẩn hóa DOI chỉ phục vụ so khớp | PI 2.1/mục 5 nêu "chuẩn hóa DOI, nguồn xuất bản" | Mô tả đúng trong báo cáo; quyết định D6 |
| R6 | **Điểm đơn lẻ mất dữ liệu:** `main` hơn `origin/main` ≥ 21 commit, chưa push; 2 stash; ~40 worktree; backup chỉ cục bộ | Mất ổ đĩa = mất đồ án | Bundle + bản sao tài liệu mỗi cuối Task (đã có thói quen), cân nhắc push sau 14/10 |
| R7 | Ảnh bằng chứng nhỏ, một số chứa email tài khoản test; teacher DB có 0 APPROVED nên cảnh "Giảng viên xem công bố của tôi" chỉ có từ DB test | Không dùng được cho báo cáo in; dễ bị hiểu nhầm là dữ liệu thật | Chụp lại độ phân giải cao, ghi rõ nguồn DB trong chú thích |
| R8 | Mã giữ chỗ M0 gây hiểu lầm (`matching/scoring.py`, `engine.py` ghi "HIGH-RISK STUB", các `*_normalizer.py` ném `NotImplementedError`, `DiffViewerStub`, README milestone lỗi thời) | Người phản biện đọc mã có thể kết luận thuật toán chưa làm | Ghi chú trong hồ sơ; sửa nhỏ sau 14/10 (FIX-01/02) |
| R9 | **Tính trung thực / sử dụng công cụ AI:** 64/100 commit có dòng `Co-Authored-By` của công cụ AI (Claude, Copilot, Cursor); đề cương yêu cầu quyển báo cáo "do sinh viên tự xây dựng" và giảng viên kiểm tra tính trung thực | Vi phạm quy định học thuật nếu khai báo không đúng hoặc không giải thích được sản phẩm | SV xác nhận quy định của Khoa (D9), khai báo trung thực theo quy định, tự hiểu và giải thích từng thành phần (mục 10.6–10.7) |

## 1.6. Tài sản cần hoàn thiện trước hạn (tóm tắt — danh sách đầy đủ ở mục 13)

`P0:` bảng truy vết yêu cầu · use case (inventory + 6 sơ đồ + 8 đặc tả) · ERD 7 + data dictionary + ràng buộc · kiến trúc · BPMN as-implemented · 8 sequence + 7 activity + 4 state + DFD.
`P1:` hồ sơ thuật toán matching/chuẩn hóa/affiliation · design tokens + 8 mockup nguồn + hướng dẫn vào Figma · ảnh chụp độ phân giải cao + index + manifest · tài liệu kiểm thử/vận hành.
`P2:` gói chuẩn bị C3 (không code) · sửa nhỏ README. `P3:` toàn bộ văn bản báo cáo, slide, bảo vệ, C3 thực thi.

## 1.7. Số liệu kiểm kê chính (ĐÃ XÁC MINH trừ khi ghi khác)

| Hạng mục | Giá trị | Nguồn đọc |
|---|---|---|
| Bảng ORM | **24** | `backend/app/models/*.py` (`__tablename__`) |
| Bảng trong DB (dump task17, head `a9c2e4f71b30`) | **24 + `alembic_version`**; tên bảng ORM = tên bảng DB (diff rỗng) | `pg_restore --schema-only` |
| Khóa chính / Khóa ngoại | **24 PK / 30 FK** (2 FK ghép: `(snapshot_id, lecturer_id)`, `(resolution_id, link_status)`); tất cả `ON DELETE RESTRICT` trừ 3 `CASCADE` (`publication_authors→publications`, `affiliation_resolutions→publication_authors`, `affiliations→resolutions`) | dump |
| UNIQUE | **16** ràng buộc bảng + **7** chỉ mục unique một phần (partial) | dump |
| CHECK | **99** | dump |
| Chỉ mục thường | **45** (52 `CREATE INDEX` gồm 7 unique) | dump |
| Trigger / hàm / extension DB | **0 trigger, 0 hàm** (`gen_random_uuid()` dùng làm default) → "audit append-only" **không có cưỡng chế ở DB**, chỉ ở tầng dịch vụ (ADR-003) | dump |
| Migration Alembic | **7**: `e5b3…→a7d9…→c3f0…→f4c8…→b27c…→d3f7…→a9c2…` (head) | `backend/alembic/versions` |
| API | **57** thao tác OpenAPI | `app.openapi()` |
| Module endpoint | 13; `require_role` dùng ở 11 (còn lại: `matching` ping không xác thực; `notifications` chỉ cần đăng nhập) | `endpoints/*.py` |
| Màn hình (route) | **15 chức năng + 1 giữ chỗ `/tasks`** | `frontend/src/App.tsx` |
| Test backend | 52 tệp test; **797 PASS** (THEO BÁO CÁO TRƯỚC, không chạy lại) | `backend/tests`; Task 17 |
| Mã | ≈19,7 nghìn dòng Python (backend/app), ≈17,3 nghìn dòng TS/TSX | đếm dòng |
| Git | 100 commit, 46 nhánh local + 32 remote, 40 worktree, 2 stash | `git` |
| Ảnh bằng chứng | **29** (Task 16: 25; Task 17: 4), tối đa 800×453 px, 3–37 KB | `_quan_ly_do_an/evidence` |

---

# 2. ĐỐI CHIẾU YÊU CẦU GIẢNG VIÊN

## 2.1. Nguồn đề cương tìm thấy / không tìm thấy

| Nguồn | Vị trí | Vai trò | Ghi chú |
|---|---|---|---|
| **Đề cương chính thức (PDF)** `01.DTC235200899.Trương Quang Huy.CN CNTT K22A.pdf` | `D:\DataFolder\ProjectIctu\DoAn\` | **Nguồn chính thức** — "ĐỀ CƯƠNG ĐỒ ÁN / KHÓA LUẬN TỐT NGHIỆP", mã H01, 5 trang | SV: Trương Quang Huy (DTC235200899, CN CNTT K22A); GVHD: TS. Nguyễn Thế Vịnh, Bộ môn Công nghệ phần mềm; thực hiện **28/09/2026 → 07/12/2026 (10 tuần)**. Phần "Yêu cầu về chuẩn năng lực" (mục 6) và "Yêu cầu về quyển báo cáo" (mục 8) ghi **"Giảng viên không sửa nội dung này"** |
| `DoAn.docx` | `D:\DataFolder\ProjectIctu\DoAn\` | **Nhật ký tiến độ của sinh viên** (bìa khóa luận + nhật ký tuần 1–3 + 5 sơ đồ). **Không phải đề cương** | Sửa đổi lần cuối 27/09/2026 00:39 — **trước** ngày bắt đầu 28/09 và có cả mục "tuần 3" (hôm nay thuộc tuần 2). **SUY LUẬN / CẦN ĐỐI CHIẾU:** nhật ký soạn trước; cần chỉnh để phản ánh đúng thời điểm và đúng sản phẩm (xem R1, D1) |
| Tài liệu phân tích yêu cầu V1/V2/V3 dạng tệp | — | — | **CHƯA TÌM THẤY NGUỒN** trong repo, `docs/`, `_quan_ly_do_an/`. Các mã "NFR-02" trong ảnh ERD cũ gợi ý từng có bảng yêu cầu, nhưng **không còn tệp** |
| Biểu mẫu/khuôn mẫu trình bày của trường, quy định trích dẫn/chống đạo văn | — | — | **CHƯA TÌM THẤY NGUỒN CHÍNH THỨC** (PDF chỉ nói "tuân thủ khuôn mẫu và định dạng của trường"). Người dùng cần xin khuôn mẫu của Khoa/Trường (việc `REQ-01`, quyết định D9) |
| Hướng dẫn riêng của GVHD ngoài PDF (email, biên bản họp, tập dữ liệu đối chiếu) | — | — | **CHƯA TÌM THẤY NGUỒN**. Không có biên bản "thống nhất tiêu chí nghiệm thu", "thống nhất định dạng trao đổi", "bộ dữ liệu GVHD xác nhận" |
| Hồ sơ dự án nội bộ | `docs/adr/` (4), `docs/freeze/` (7), `docs/demo/` (5), `README.md` | Tài liệu kỹ thuật/tiến độ của chính dự án | Dùng làm bằng chứng triển khai, **không** thay thế yêu cầu GVHD |

**Chênh lệch đáng chú ý giữa nguồn:** tiêu đề trên bìa `DoAn.docx` là *"Ứng dụng website quản lý và chuẩn hóa hồ sơ tác giả công bố khoa học trên Scopus"*, còn PDF ghi *"Xây dựng ứng dụng web quản lý và chuẩn hóa hồ sơ tác giả, công bố khoa học trên Scopus phục vụ Trường Đại học Công nghệ thông tin và Truyền thông"*. **Tên đề tài trong báo cáo phải khớp đề cương chính thức** → việc `REQ-01`.

## 2.2. Bảng đối chiếu: yêu cầu → nguồn → đã triển khai → bằng chứng → thiếu → hành động

Quy ước "Bắt buộc": **BB** = bắt buộc theo văn bản đề cương; **BB\*** = bắt buộc ngầm (mục tiêu/PI tham chiếu) cần xác nhận với GVHD. Vị trí = mục + trang theo chân trang PDF. "Hành động" trỏ tới ID ở mục 11.

### 2.2.1. Mục tiêu (mục 5, tr.1)

| ID | Yêu cầu | Bắt buộc | Đã triển khai (code/tài liệu) | Bằng chứng | Còn thiếu | Hành động |
|---|---|---|---|---|---|---|
| G1 | Khảo sát, phân tích, thiết kế quy trình quản lý dữ liệu công bố từ Scopus phục vụ nhiệm vụ trọng điểm ICTU | BB | Quy trình nhập→chuẩn hóa→ứng viên→duyệt chạy thật | `HUONG_DAN…` ch.5; ảnh BPMN cũ (`DoAn.docx`) lệch | BPMN khớp thực tế; biên bản khảo sát | `UML-02`, `REQ-01` |
| G2 | Chuẩn hóa DOI, tên công bố, nguồn xuất bản, năm xuất bản, Scopus Author ID; liên kết công bố với GV ICTU | BB | EID chuẩn tắc (khóa chống trùng); `title_normalized` (NFKC+chữ thường); `year` ép số; tác giả theo Scopus ID; liên kết GV qua ứng viên + duyệt. **DOI lưu nguyên (chỉ trim)**; chuẩn hóa DOI chỉ ở bước so khớp (`normalize_doi_for_matching`); **nguồn xuất bản = chuỗi `source_title`, không chuẩn hóa/không bảng riêng** | `scopus_normalizer.py:141-176, 288-296, 340-377`; `publication_evidence_enricher.py:38-53` | Nói rõ mức chuẩn hóa thật; ra quyết định có chuẩn hóa DOI/nguồn trong lưu trữ hay chỉ trình bày giới hạn | `ALG-01`, D6 |
| G3 | Web có phân quyền; quản lý dữ liệu gốc và chuẩn; hỗ trợ kiểm tra và phê duyệt; xuất dữ liệu có cấu trúc | BB | RBAC 3 vai trò (kiểm tra ở backend); `raw_scopus_records` tách `publications`; hàng đợi duyệt; xuất JSON | OpenAPI 57 thao tác; `BAO_CAO_KIEM_THU…` §5.1 | Xuất mới chỉ JSON, ADMIN | Tài liệu (`USE-*`, `REQ-02`) |
| G4 | Kiểm thử chức năng; **đánh giá chất lượng chuẩn hóa/đối soát trên bộ dữ liệu GVHD xác nhận**; báo cáo kết quả và các trường hợp chưa giải quyết được | BB | Kiểm thử chức năng ✔; đánh giá chất lượng ✖ | 797 test; E2E 3 vai trò; C3 `NOT_RUN` | Tập đối chiếu GVHD; nhãn; số liệu | `C3P-01`, `REQ-03`, D5 |

### 2.2.2. Sản phẩm (mục 7a, tr.2)

| ID | Yêu cầu | Bắt buộc | Đã triển khai | Bằng chứng | Còn thiếu | Hành động |
|---|---|---|---|---|---|---|
| P1 | Chức năng nhập và kiểm tra dữ liệu | BB | JSON GV: preview→xác nhận→hoàn tác; CSV Scopus: tải, theo dõi, hủy, lưu trữ, xóa, hoàn tác; lỗi theo dòng | `imports.py`, `lecturers.py`; ảnh 30–34, 40–41 | — | `USE-03` |
| P2 | Tìm kiếm, lọc | BB | Tra cứu tổng hợp `/search` (không phân biệt dấu); lọc công bố (năm/loại/giai đoạn/OA); lọc hàng đợi | `search.py`, `publications.py`; ảnh 10, 19 | — | — |
| P3 | Quản lý liên kết với giảng viên | BB | Ứng viên→danh tính APPROVED; LECTURER xem liên kết của mình; **UI quản trị xem danh tính theo GV chưa có (API-only `/lecturers/{id}/scopus/*`)** | `lecturer_scopus.py` | Màn quản lý liên kết theo GV (không bắt buộc) | ghi nhận ở `UI-01` |
| P4 | Duyệt kết quả | BB | ACCEPT/REJECT (REJECT bắt buộc lý do); REVIEWER + ADMIN | `reviews.py`; ảnh 20b–22 | Hoàn tác (REOPEN/REVOKE) không có API/UI | D7 |
| P5 | **Thống kê** và xuất dữ liệu chuẩn | BB | Dashboard chỉ đếm (công bố, GV, tác giả, trạng thái danh tính, hàng đợi, nhật ký gần đây); biểu đồ Trang chủ là giữ chỗ; xuất JSON công bố (ADMIN) | `dashboard.py`; ảnh 02; `HUONG_DAN` §1.6 | Thống kê theo năm/nguồn/loại; xuất CSV/Excel (sơ đồ UC cũ hứa) | D8; `UI-02` (thiết kế) |
| P6 | Gợi ý ánh xạ theo **mã định danh, tên, đơn vị, thông tin công bố**; hiển thị căn cứ và **mức độ phù hợp** | BB | Căn cứ: quy tắc tên (4 mức) + công bố đã biết trùng DOI/tiêu đề; hiển thị rule, hai phía tên, công bố hỗ trợ, "ngữ cảnh mơ hồ", cảnh báo dùng chung. **Không dùng ORCID/đơn vị; không có điểm/mức độ** | `candidate_generator.py`; `candidate_types.py`; ADR-004 ("thứ tự mạnh–yếu, không phải điểm số") | Mức độ phù hợp; gợi ý theo ORCID/đơn vị | D3; `ALG-01` |
| P7 | Giữ nguyên dữ liệu đầu vào, lưu nguồn + lịch sử chỉnh sửa; **cho phép xem lại và phục hồi kết quả trước khi gộp** | BB | Dữ liệu thô bất biến (`raw_scopus_records`, `raw_payload`); provenance (`publication_raw_sources`, snapshot); `audit_events`; hoàn tác đợt nhập JSON/CSV. **Phục hồi quyết định duyệt: chỉ có trong schema** (`mapping_reviews`: REVOKE/REOPEN; `candidate_reviews.action=REOPEN`), **không có API/UI** | schema dump; `reviews.py:574` (chỉ lọc lịch sử theo REOPEN) | Luồng hoàn tác duyệt; hoặc trình bày đúng phạm vi | D7 |
| P8 | **Không tự khẳng định** tác giả chỉ vì tên giống; thiếu căn cứ → danh sách chờ xác minh | BB | ADR-004 cấm auto-approve; mọi ứng viên PENDING; chặn ACCEPT lần 2 cho cùng Scopus ID (409) | `candidate_review_service.py`; teacher 0 APPROVED | — | Dùng làm điểm mạnh |
| P9 | Bàn giao: mã nguồn, CSDL, tài liệu cài đặt/sử dụng, bộ kiểm thử, bản triển khai thử nghiệm | BB | Mã (Git cục bộ); DB (`pg_dump` ngoài Git); `HUONG_DAN`, `BACKEND_LOCALHOST`; test; BAT localhost | `docs/demo/*`; `compose*.yaml` (chưa có bằng chứng chạy) | Đóng gói bàn giao; hướng dẫn cài đặt từ đầu | `REQ-04`, `HND-01` |
| P10 | Định dạng trao đổi dữ liệu thống nhất với GVHD (không bắt buộc tích hợp trực tiếp) | BB | JSON GV có JSON Schema; xuất công bố `schema_version 1.0` | `data/lecturers/schema/ictu_lecturers.schema.json`; `publication_export.py` | Biên bản thống nhất định dạng với GVHD | D10 |

### 2.2.3. Yêu cầu chi tiết theo PI (mục 7b, tr.2–3)

| ID | Yêu cầu tối thiểu | Bắt buộc | Đã triển khai | Bằng chứng | Còn thiếu | Hành động |
|---|---|---|---|---|---|---|
| PI-1.1 | Khảo sát quy trình tiếp nhận–xử lý–duyệt dữ liệu Scopus; **BPMN**, mô tả từng bước, người thực hiện, vào/ra | BB | Quy trình thật + ảnh sơ đồ cũ | `DoAn.docx` ảnh 2 (lệch) | BPMN + bảng bước | `UML-02` |
| PI-1.2 | Bảng yêu cầu chức năng/phi chức năng: phân quyền, an toàn dữ liệu, truy vết chỉnh sửa, sao lưu, khả năng sử dụng; thống nhất tiêu chí nghiệm thu với GVHD | BB | Các thuộc tính có trong hệ thống nhưng chưa thành tài liệu | — | **Toàn bộ tài liệu** + xác nhận GVHD | `REQ-02`, D10 |
| PI-1.3 | Sơ đồ UC + đặc tả ≥5 UC chính: nhập dữ liệu; quản lý hồ sơ tác giả; quản lý công bố; chuẩn hóa/đối soát và phê duyệt; tìm kiếm, thống kê và xuất dữ liệu | BB | UC cũ (ảnh) | `DoAn.docx` ảnh 3 | Sơ đồ khớp thực tế + ≥5 đặc tả | `USE-01..03` |
| PI-2.1 | ERD: hồ sơ tác giả Scopus, công bố, tác giả công bố, **nguồn xuất bản**, ánh xạ GV; liên kết GV, lô nhập, nguồn dữ liệu, lịch sử chỉnh sửa; khóa định danh, ràng buộc toàn vẹn, nguyên tắc chống trùng | BB | DB 24 bảng (rất đầy đủ ràng buộc/chống trùng); **không có bảng "nguồn xuất bản"** | dump; ADR; freeze M1.0 | ERD thật, data dictionary; giải trình nguồn xuất bản | `DB-01..05` |
| PI-2.2 | Kiến trúc ứng dụng bằng **UML**: tách giao diện web, dịch vụ Web API, tầng dữ liệu; mô tả luồng nhập, xử lý, duyệt, xuất | BB | Kiến trúc React/Vite→FastAPI→PostgreSQL có thật | mã | Toàn bộ sơ đồ UML | `UML-01,03,04,05` |
| PI-2.3 | Thiết kế giao diện **Figma**: danh sách, chi tiết, nhập dữ liệu, **so sánh trước/sau chuẩn hóa**, hàng đợi phê duyệt, thống kê | BB | 15 màn thật; không Figma; **màn so sánh trước/sau chưa có** | `frontend/src` | Figma + màn so sánh | `UI-01,02`, D2, D4 |
| PI-3.1 | CSDL quan hệ theo thiết kế; lưu riêng dữ liệu gốc và kết quả xử lý; ràng buộc khóa, truy xuất nguồn; **kịch bản khởi tạo, sao lưu, phục hồi** | BB | Alembic khởi tạo ✔; tách raw/canonical ✔; provenance ✔; sao lưu/phục hồi thủ công | migrations; `BAO_CAO` ch.15 | Kịch bản/tài liệu sao lưu–phục hồi đã kiểm | `REQ-04` |
| PI-3.2 | Máy chủ Web API + giao diện web **tương thích máy tính, điện thoại**; xác thực, phân quyền người quản lý/xử lý | BB | FastAPI + JWT cookie, Argon2id; Tailwind responsive, sidebar mobile | `security.py`; `Sidebar.tsx` | Bằng chứng ở khổ điện thoại | `EVD-02` |
| PI-3.3 | Cài đặt và kiểm thử đầy đủ ≥5 UC; nhập lỗi không sinh bản ghi trùng; báo lỗi theo dòng; duyệt kết quả trước khi áp dụng | BB | ✔ (xem P1, P4) | Task 16–17 | Biên bản theo mẫu "mong đợi/thực tế" cho từng UC | `REQ-03` |
| PI-3.4 | Gợi ý ánh xạ (xem P6); **đánh giá trên tập đối chiếu GVHD xác nhận**; không tự động gộp trường hợp chưa đủ chứng cứ | BB | Gợi ý một phần; không tự gộp ✔; đánh giá ✖ | ADR-004; C3 `NOT_RUN` | Tập đối chiếu + đánh giá | `C3P-01`, D3, D5 |
| PI-4.1 | Triển khai môi trường thử nghiệm; cấu hình bảo mật cơ bản; tài khoản, phân quyền; hướng dẫn cài đặt, sử dụng, sao lưu, phục hồi | BB | Localhost BAT; 3 vai trò; hướng dẫn sử dụng | `BACKEND_LOCALHOST…`; `HUONG_DAN…` | Hướng dẫn sao lưu/phục hồi; tuyên bố môi trường thử nghiệm thật là localhost | `REQ-04` |
| PI-4.2 | Bộ dữ liệu kiểm thử từ dữ liệu được phép do GVHD cung cấp; dữ liệu giả lập phải đánh dấu; bao phủ: hợp lệ, thiếu trường, sai định dạng, trùng, **tên tác giả giống nhau**, lỗi nhập; biên bản kiểm thử mong đợi/thực tế | BB | `scopus_sample.csv`, `ictu_lecturers_fixture.json`, E2E trên bản sao teacher; 5 ví dụ affiliation thật; ca "5 GV dùng chung Scopus ID" | `BAO_CAO` ch.6–9; `data/test_fixtures` (chỉ `.gitkeep`; fixture thật ở `backend/tests/fixtures`) | Danh mục bộ dữ liệu theo loại; đánh dấu dữ liệu giả | `REQ-03` |

### 2.2.4. Quyển báo cáo (mục 8, tr.3) và tiến độ (mục 9, tr.3–5)

| ID | Yêu cầu | Bắt buộc | Trạng thái | Hành động |
|---|---|---|---|---|
| R1 | Do sinh viên tự xây dựng | BB | Phần mềm tự xây dựng (lịch sử Git 100 commit). **Cần bản tự khai + khả năng giải thích từng sơ đồ/thuật toán** | `ALG-01`, mục 13 (tài liệu "Vì sao" cho SV) |
| R2 | Cấu trúc 4 chương: (1) Cơ sở lý thuyết/công nghệ; (2) Khảo sát và phân tích hệ thống; (3) Thiết kế hệ thống; (4) Triển khai (cài đặt, bảo vệ, thử nghiệm, tài liệu hướng dẫn) | BB | Chưa viết (P3) | Bản đồ "tài sản → chương" ở mục 13 |
| R3 | Tuân thủ khuôn mẫu và định dạng của trường | BB | **CHƯA TÌM THẤY NGUỒN** khuôn mẫu | D9 |
| R4 | Không lỗi chính tả | BB | P3 | — |
| R5 | Không sử dụng nội dung vi phạm bản quyền | BB | Mọi hình do chính hệ thống/sơ đồ tự tạo; tài liệu ngoài phải trích nguồn | Mục 10.6 |
| R6 | Không vi phạm quy định chống đạo văn | BB | Không thể cam kết "qua phần mềm kiểm tra"; chỉ có thể bảo đảm nguồn gốc, minh chứng, diễn đạt tự thân | Mục 10.6 |
| T1 | Tiến độ 10 tuần 28/09–07/12/2026: tuần 1 khảo sát; tuần 2–3 phân tích/UC/tiêu chí; tuần 3–4 sơ đồ dữ liệu, kiến trúc, giao diện mẫu, đặc tả trao đổi; … tuần 10 báo cáo, bàn giao, bảo vệ (bảng PDF lệch cột — **cần đọc lại bản gốc**) | BB | Demo 14/10 (tuần 3) | `REQ-01` |

**Tổng số yêu cầu có đánh số:** 4 mục tiêu (G) + 10 sản phẩm (P) + 12 PI + 6 quyển báo cáo (R) = **32**, kèm 1 ràng buộc thời gian (T1). **Bắt buộc theo văn bản: cả 32.**
Phân loại 26 yêu cầu kỹ thuật (G + P + PI) theo bảng trên: **7 ĐẠT** (G3, P1, P2, P3, P4, P8, PI-3.3) · **4 PHẦN LỚN ĐẠT** (PI-3.1, PI-3.2, PI-4.1, PI-4.2) · **12 MỘT PHẦN** (G1, G2, G4, P5, P6, P7, P9, P10, PI-1.1, PI-1.3, PI-2.1, PI-3.4) · **3 THIẾU** (PI-1.2, PI-2.2, PI-2.3). 6 yêu cầu quyển báo cáo (R1–R6) thuộc giai đoạn viết (P3), chưa bắt đầu. *Đây là phân loại thủ công theo bảng, để định hướng ưu tiên — không phải điểm số.*

---

# 3. KIỂM KÊ USE CASE

> Nguyên tắc: **chỉ vẽ use case có thật** trong mã (`App.tsx`, `Sidebar.tsx`, 57 thao tác OpenAPI, `require_role`) hoặc script CLI có thật. Mọi UC dưới đây có cột "Bằng chứng". Không thêm UC chỉ vì sơ đồ cũ hoặc đề cương gợi ý.

## 3.1. Tác nhân (actor) thật của hệ thống

| Actor | Loại | Căn cứ | Ghi chú |
|---|---|---|---|
| **ADMIN** (Quản trị viên) | Vai trò trong hệ thống | `users.role` CHECK = `ADMIN`/`REVIEWER`/`LECTURER`; `require_role("ADMIN")` | Toàn quyền giao diện quản trị |
| **REVIEWER** (Phê duyệt viên) | Vai trò | `require_role("ADMIN","REVIEWER")` ở `reviews`, `publications` (đọc), `search` | Chỉ công bố, tra cứu, duyệt, lịch sử review. Vai trò thêm ở Task 17; teacher DB **chưa có tài khoản REVIEWER** (chỉ có trên DB test) |
| **LECTURER** (Giảng viên) | Vai trò | `require_role("LECTURER")` ở `lecturers/me/*`; CHECK `lecturer_id NOT NULL` khi role LECTURER | Chỉ xem dữ liệu của chính mình |
| **Kỹ thuật viên (CLI)** | Người chạy script, **không phải vai trò trong ứng dụng** | `backend/scripts/*.py` | Chạy sinh ứng viên, nạp Craw/affiliation, bootstrap ADMIN. Nên vẽ ở sơ đồ riêng "ngoài giao diện" |
| Hệ thống ngoài | Nguồn dữ liệu | Scopus CSV, ICTU Repository (DSpace)/Craw, OpenAlex/Crossref/ORCID | **Không có kết nối trực tuyến từ ứng dụng** — hệ thống **không gọi Scopus API**; dữ liệu ngoài vào qua tệp/script |

**Chú ý:** sơ đồ UC trong `DoAn.docx` dùng actor "Chuyên viên ICTU (Operator)" và "Cán bộ duyệt ICTU (Admin/Approver)". **"Operator" không tồn tại** như vai trò; "Approver" tương ứng REVIEWER/ADMIN. Phải thống nhất tên (D1).

## 3.2. Danh sách use case có thật (26)

Cột **UI**: ✔ có nút/màn trên giao diện; API = chỉ API; CLI = chỉ script. **Ghi** = có ghi DB.

| UC | Tên use case | Actor | Bằng chứng (route / API / script) | UI | Ghi | Bảng chính bị ghi |
|---|---|---|---|---|---|---|
| UC-01 | Đăng nhập | Mọi vai trò | `POST /auth/login`; `/login` | ✔ | Không ghi nghiệp vụ (chưa thấy sự kiện audit đăng nhập) | — |
| UC-02 | Đăng xuất, kiểm tra phiên | Mọi vai trò | `POST /auth/logout`, `GET /auth/me` | ✔ | Không | — |
| UC-03 | Xem thông báo của tôi | Mọi vai trò | `GET /notifications/unread`, `POST /notifications/{id}/read` | Một phần (cơ chế nền: tự lấy khi tải trang rồi hiển thị; **không có trang/chuông Thông báo** — `HUONG_DAN` §4.13) | Có (đánh dấu đã đọc) | `user_notifications` |
| UC-04 | Xem tổng quan hệ thống (dashboard) | ADMIN | `GET /dashboard/summary`; `/dashboard` | ✔ | Không | — |
| UC-05 | Quản lý hồ sơ giảng viên (tìm, thêm, sửa, xóa, dọn hồ sơ mồ côi) | ADMIN | `lecturers` GET/POST/PATCH/PUT/DELETE, `/unlinked/cleanup`; `/lecturers` | ✔ | Có | `lecturers`, `audit_events` |
| UC-06 | Quản lý tài khoản & phân quyền (sửa hồ sơ, đổi vai trò, khóa/mở khóa, đặt lại mật khẩu) | ADMIN | `users` GET/PATCH, `/lock`, `/unlock`, `/reset-password`; trong "Chi tiết giảng viên" | ✔ | Có | `users`, `user_notifications`, `audit_events` |
| UC-07 | Xem nhật ký kiểm toán | ADMIN | `GET /audits`; `/audit-logs` | ✔ | Không | — |
| UC-08 | Nhập hồ sơ giảng viên từ JSON (kiểm tra→xem trước→nhập→hoàn tác) | ADMIN | `POST /lecturers/import/preview`, `/lecturers/import`, `/import/{id}/rollback`; `/imports` | ✔ | Có | `lecturers`, `lecturer_source_snapshots`, `lecturer_known_publications`, `audit_events` |
| UC-09 | Xuất hồ sơ giảng viên ra JSON | ADMIN | `GET /lecturers/export` | ✔ (nút Xuất JSON) | Có (ghi audit) | `audit_events` |
| UC-10 | Nhập CSV Scopus (tải, theo dõi tiến trình, hủy, lưu trữ/khôi phục lịch sử, xóa, hoàn tác) | ADMIN | `POST /imports/scopus`, `/imports/*`, `/archive`, `/restore-history`, `/cancel`, `DELETE`, `/rollback` | ✔ | Có | `scopus_imports`, `raw_scopus_records`, `audit_events` |
| UC-11 | Chuẩn hóa công bố từ bản ghi thô | ADMIN | `POST /imports/{id}/normalize`; `/normalization` | ✔ | Có | `publications`, `publication_raw_sources`, `scopus_imports.normalization_summary` |
| UC-12 | Bóc tách tác giả Scopus | ADMIN | `POST /authors/normalize-import/{id}` | ✔ | Có | `scopus_authors`, `scopus_author_name_variants`, `publication_authors` |
| UC-13 | Xem danh sách/chi tiết công bố (kèm affiliation theo tác giả, nguồn gốc dòng CSV) | ADMIN, REVIEWER | `GET /publications`, `/publications/{eid}`; `/publications`, `/publications/:eid` | ✔ | Không | — |
| UC-14 | Tra cứu tổng hợp (giảng viên, công bố, tác giả) | ADMIN, REVIEWER | `GET /search`; `/search` | ✔ | Không | — |
| UC-15 | Xuất dữ liệu công bố ra JSON | **ADMIN** | `GET /publications/export` | ✔ | Có (ghi audit `PUBLICATION_DATASET_EXPORTED`) | `audit_events` |
| UC-16 | Xem danh sách/chi tiết/thống kê tác giả Scopus | ADMIN | `GET /authors`, `/authors/stats`, `/authors/{id}` | Một phần (tab "Tác giả"; **chi tiết tác giả chưa có nút**) | Không | — |
| UC-17 | Xem hàng đợi ứng viên đối sánh và bằng chứng | ADMIN, REVIEWER | `GET /reviews/candidates`, `/reviews/candidates/{id}`; `/reviews` | ✔ | Không | — |
| UC-18 | Duyệt ứng viên (ACCEPT / REJECT có lý do) | ADMIN, REVIEWER | `POST /reviews/candidates/{id}/reviews` | ✔ | Có | `lecturer_scopus_candidates`, `lecturer_scopus_candidate_reviews`, `lecturer_scopus_identities`, `identity_evidence`, `audit_events` |
| UC-19 | Xem lịch sử review | ADMIN, REVIEWER | `GET /reviews/history`; `/review-history` | ✔ | Không | — |
| UC-20 | Xem hồ sơ cá nhân | LECTURER | `GET /lecturers/me/profile`; `/profile` | ✔ | Không | — |
| UC-21 | Xem liên kết Scopus đã được duyệt của tôi | LECTURER | `GET /lecturers/me/identities`; `/identity` | ✔ | Không | — |
| UC-22 | Xem công bố của tôi (chỉ từ danh tính APPROVED) | LECTURER | `GET /lecturers/me/publications`; `/my-publications` | ✔ | Không | — |
| UC-23 | Xem hồ sơ/danh tính/công bố Scopus của **một** giảng viên | ADMIN | `GET /lecturers/{id}/scopus/{profile,identities,publications}` | **API** (chưa dùng ở UI) | Không | — |
| UC-24 | Sinh ứng viên đối sánh (và lưu bền, idempotent) | Kỹ thuật viên | `backend/scripts/generate_matching_candidates.py` | **CLI** | Có | `candidate_generation_runs`, `lecturer_scopus_candidates`, `…_observations`, `…_evidence` |
| UC-25 | Nạp công bố đã biết (Craw) và affiliation ngoài (OpenAlex/Crossref/ORCID) | Kỹ thuật viên | `ingest_craw_known_publications.py`, `import_author_affiliations.py` | **CLI** | Có | `lecturer_known_publications`, `organizations`, `publication_author_affiliation_resolutions`, `publication_author_affiliations` |
| UC-26 | Khởi tạo dữ liệu & tài khoản ADMIN demo | Kỹ thuật viên | `bootstrap_demo_admin.py`, `seed_demo_users.py`, `alembic upgrade head` | **CLI** | Có | `users`, `lecturers` |

*Còn lại không tính là UC nghiệp vụ:* `/health`, `/lecturers/ping`, `/matching/ping` (healthcheck/giữ chỗ), `GET /auth/users` (bí danh cũ, deprecated), `GET /imports` & `/imports/history` (trùng chức năng), `/tasks` (giữ chỗ `NOT_IMPLEMENTED`), `/users` (chuyển hướng sang `/lecturers`).

**Đối chiếu 5 UC bắt buộc của đề cương (PI-1.3):**

| UC bắt buộc | Gộp từ UC thật | Mức triển khai |
|---|---|---|
| (a) Nhập dữ liệu | UC-08, UC-10 (+UC-09 xuất GV) | Đầy đủ |
| (b) Quản lý hồ sơ tác giả | UC-05, UC-06, UC-12, UC-16, UC-21 (+UC-23 API) | Đầy đủ ở quản lý GV/tài khoản; tác giả Scopus xem được, chưa có chỉnh sửa (không cần: dữ liệu nguồn bất biến) |
| (c) Quản lý công bố | UC-11, UC-13 | Đầy đủ chuẩn hóa + xem; **không có sửa tay công bố** (thiết kế bất biến; nói rõ) |
| (d) Chuẩn hóa/đối soát và phê duyệt | UC-11, UC-12, UC-17, UC-18, UC-19, UC-24 | Đầy đủ; sinh ứng viên là CLI |
| (e) Tìm kiếm, thống kê, xuất dữ liệu | UC-14, UC-04, UC-15 | Tìm kiếm ✔; thống kê **sơ sài**; xuất **chỉ JSON** |

## 3.3. Ma trận Actor × Use case (ĐÃ XÁC MINH bằng `require_role` + `App.tsx`)

`●` được phép · `–` bị từ chối (API trả 403; giao diện ẩn menu) · `◐` chỉ dữ liệu của chính mình.

| UC | ADMIN | REVIEWER | LECTURER | UC | ADMIN | REVIEWER | LECTURER |
|---|:-:|:-:|:-:|---|:-:|:-:|:-:|
| 01 Đăng nhập | ● | ● | ● | 14 Tra cứu | ● | ● | – |
| 02 Đăng xuất | ● | ● | ● | 15 Xuất công bố | ● | – | – |
| 03 Thông báo | ● | ● | ● | 16 Tác giả Scopus | ● | – | – |
| 04 Tổng quan | ● | – | – | 17 Xem hàng đợi | ● | ● | – |
| 05 Quản lý GV | ● | – | – | 18 Duyệt | ● | ● | – |
| 06 Tài khoản | ● | – | – | 19 Lịch sử review | ● | ● | – |
| 07 Nhật ký kiểm toán | ● | – | – | 20 Hồ sơ cá nhân | – | – | ◐ |
| 08 Nhập JSON GV | ● | – | – | 21 Liên kết của tôi | – | – | ◐ |
| 09 Xuất GV | ● | – | – | 22 Công bố của tôi | – | – | ◐ |
| 10 Nhập CSV | ● | – | – | 23 Admin xem Scopus của GV | ● | – | – |
| 11 Chuẩn hóa công bố | ● | – | – | 24–26 (CLI) | (kỹ thuật viên) | | |
| 12 Bóc tách tác giả | ● | – | – | | | | |
| 13 Xem công bố | ● | ● | – | | | | |

Ràng buộc nghiệp vụ liên quan quyền (ĐÃ XÁC MINH trong Task 17 + CHECK DB): ADMIN không tự đổi vai trò của mình và không hạ ADMIN cuối cùng (409); tài khoản `LECTURER` bắt buộc gắn `lecturer_id` (CHECK `ck_users_lecturer_account_required`) và mỗi hồ sơ GV tối đa 1 tài khoản (`uq_users_lecturer`).

## 3.4. Include / Extend đúng ngữ nghĩa UML (đề xuất — phải kiểm lại với mã khi vẽ)

Định nghĩa dùng: **«include»** = hành vi con **bắt buộc** luôn xảy ra; **«extend»** = hành vi **tùy chọn**, chỉ xảy ra khi có điều kiện.

| Quan hệ đề xuất | Căn cứ trong mã | Khác với sơ đồ cũ ở điểm nào |
|---|---|---|
| UC-18 «include» *Kiểm tra xung đột Scopus ID dùng chung* | `_check_identity_conflicts`, `ScopusAuthorAlreadyApprovedError`, `PreexistingIdentityConflictError` | Cũ không có |
| UC-18 «include» *Ghi lịch sử review và audit* | `_record_audit_events`; `lecturer_scopus_candidate_reviews` | Cũ chỉ có "Audit Log" ở BPMN |
| UC-18 «include» *Chuyển bằng chứng sang danh tính* (chỉ khi ACCEPT) → thực chất **điều kiện** nên vẽ như ghi chú hoặc «extend» của nhánh ACCEPT | `_promote_candidate_evidence_to_identity` | — |
| UC-08 «include» *Kiểm tra hợp lệ & xem trước* | preview bắt buộc ở giao diện (API tách riêng) | Cũ: "Kiểm tra schema 22 cột" thuộc CSV |
| UC-08 «extend» *Hoàn tác đợt nhập* | `/import/{id}/rollback` | Cũ: rollback gắn nhầm vào duyệt |
| UC-10 «extend» *Hủy / Lưu trữ / Khôi phục / Xóa / Hoàn tác đợt nhập* | các endpoint `/imports/{id}/*` | — |
| UC-10 **không** «include» UC-11/UC-12 — chúng là **bước riêng, do ADMIN kích hoạt sau** (ghi tuần tự, không bắt buộc ngay) | `/normalization` có nút riêng | **Cũ vẽ «include» "Bóc tách tác giả & Tính Match Score" — sai** |
| UC-13 «include» *Xem đơn vị theo từng tác giả* | `AuthorAffiliations.tsx` hiển thị luôn trong chi tiết | — |
| UC-17 «extend» *Xem chi tiết ứng viên* | `GET /reviews/candidates/{id}` | — |
| Mọi UC cần đăng nhập → vẽ bằng **ghi chú/gói "Yêu cầu đăng nhập"**, không vẽ «include» UC-01 vào từng UC (tránh rối) | — | — |

## 3.5. Bộ sơ đồ Use Case cần tạo (6)

| # | Sơ đồ | Nội dung | Số UC | Vì sao tách |
|---|---|---|---|---|
| UCD-0 | Tổng thể mức nhóm | 5 nhóm UC khớp 5 UC đề cương + 4 actor | ≈ 10–12 oval | Một sơ đồ 26 oval sẽ không đọc được |
| UCD-1 | ADMIN — nhập & chuẩn hóa dữ liệu | UC-08…12, 15 | 7 | Luồng dữ liệu chính |
| UCD-2 | ADMIN — quản trị & giám sát | UC-04…07, 16, 23 | 6 | Quản trị tài khoản/audit |
| UCD-3 | REVIEWER (+ ADMIN) — đối soát | UC-13, 14, 17, 18, 19 | 5 | Trọng tâm nghiệp vụ |
| UCD-4 | LECTURER | UC-20…22 (+01–03) | 3–6 | Cổng giảng viên |
| UCD-5 | Tiến trình ngoài giao diện (CLI) | UC-24…26 | 3 | Phân biệt rõ phần chạy bằng script |

Công cụ/định dạng: **PlantUML** (`.puml` — hỗ trợ use case chuẩn UML; Mermaid **không** có sơ đồ use case chuẩn). Xuất SVG/PNG để chèn báo cáo. Có thể tạo tự động: **không** (phải thiết kế), nhưng **bảng actor–UC (3.3) sinh tự động từ `require_role` + OpenAPI** để đối chiếu. Phải kiểm tra thủ công: tên actor, include/extend.

## 3.6. Đặc tả Use Case cần viết (8 cốt lõi + 1 tùy chọn)

Mỗi đặc tả có: mã, tên, actor, mục đích, **điều kiện trước**, **điều kiện sau (thành công / lỗi)**, **luồng chính**, **luồng thay thế**, **luồng ngoại lệ**, quyền, dữ liệu **đọc/ghi** (bảng), quy tắc nghiệp vụ, bằng chứng mã/test. Dữ kiện đã xác minh để dùng:

| # | Đặc tả | Dữ kiện đã xác minh (rút ngắn) |
|---|---|---|
| S1 | Đăng nhập & phân quyền (UC-01/02) | JWT trong cookie `httponly`, `samesite=lax`, `secure` chỉ khi `ENVIRONMENT=prod`; Argon2id; khóa tài khoản → 403 `ACCOUNT_LOCKED`; token thu hồi qua `auth_version` → 401 `SESSION_REVOKED`; **chưa có giới hạn số lần đăng nhập sai** |
| S2 | Nhập hồ sơ GV từ JSON (UC-08) | Preview chỉ đọc; không dùng tên để gộp; khớp theo `source_id` → mã cán bộ → email; xung đột chặn **trước khi ghi**; giảng viên vắng mặt trong tệp không bị xóa; hoàn tác giữ bản ghi đa nguồn |
| S3 | Nhập CSV Scopus (UC-10) | SHA-256 tệp chống trùng; CSV không phải bản xuất Scopus (thiếu cột EID) bị từ chối (Task 17); lỗi theo dòng giữ nguyên giá trị gốc; vòng đời `RECEIVED→PARSING→VALIDATED→STAGED→APPLIED/FAILED/CANCELLED` |
| S4 | Chuẩn hóa công bố & tác giả (UC-11/12) | Kết quả mỗi dòng: `NEW`/`EXISTING_UNCHANGED`/`EXISTING_METADATA_CHANGED`/`INVALID_EID`…; không ghi đè dữ liệu cũ; idempotent (chạy lại 0 bản ghi mới); bất biến số đếm |
| S5 | Xem công bố, tra cứu, xuất (UC-13/14/15) | Lọc năm/loại/giai đoạn/OA; xuất JSON ghi audit và **trả 503 nếu ghi audit thất bại**; tìm kiếm không phân biệt dấu |
| S6 | Quản lý hồ sơ GV & tài khoản (UC-05/06) | Email trùng → 409; đổi vai trò/khóa gửi thông báo; không tự hạ ADMIN cuối |
| S7 | Duyệt ứng viên ACCEPT/REJECT (UC-17/18) | Điều kiện: ứng viên `PENDING`, quan sát (observation) hiện hành, `version` khớp; REJECT bắt buộc lý do (CHECK DB); ACCEPT tạo danh tính `APPROVED` + `identity_evidence`; chặn ACCEPT lần 2 cho cùng Scopus ID (409); lỗi: không tìm thấy, quan sát cũ, phiên bản cũ, đã quyết định, xung đột danh tính, người duyệt không đủ quyền |
| S8 | Giảng viên xem công bố của tôi (UC-20…22) | Chỉ hiện sau khi có danh tính APPROVED (teacher hiện 0 → trống; minh chứng từ DB test); `LECTURER` gọi API quản trị → 403 |
| S9 *(tùy chọn)* | Sinh ứng viên đối soát (UC-24) | Idempotent; bốn luật tên; làm giàu bằng công bố đã biết; CLI |

Định dạng: Markdown (một tệp mỗi UC hoặc một tệp gộp). Có thể tạo tự động: khung + dữ kiện tra cứu (≈40%); **phải do sinh viên đọc và hiểu để tự diễn đạt** (yêu cầu R1).

## 3.7. Phân quyền và nghiệp vụ ghi dữ liệu — tóm tắt cho bảng "UC × bảng"

- **Ghi bởi giao diện/API:** `lecturers`, `lecturer_source_snapshots`, `lecturer_known_publications` (qua nhập JSON); `users`, `user_notifications` (tài khoản); `scopus_imports`, `raw_scopus_records` (nhập CSV); `publications`, `publication_raw_sources`, `scopus_authors`, `scopus_author_name_variants`, `publication_authors` (chuẩn hóa); `lecturer_scopus_candidate_reviews`, `lecturer_scopus_identities`, `identity_evidence`, `lecturer_scopus_candidates.status` (duyệt); `audit_events` (hầu hết thao tác ghi).
- **Ghi chỉ bởi script:** `candidate_generation_runs`, `lecturer_scopus_candidates` (tạo), `…_observations`, `…_evidence`, `organizations`, `publication_author_affiliation_*`, nạp `lecturer_known_publications` từ Craw.
- **Có trong schema nhưng chưa có mã ghi:** `mapping_reviews` (REVOKE/REOPEN/compensation) và các cột `lecturer_scopus_identities.recommendation*`.

---

# 4. KIỂM KÊ DATABASE DESIGN VÀ ERD

## 4.1. Hiện trạng tài sản

| Tài sản | Có chưa? | Ghi chú |
|---|---|---|
| Schema PostgreSQL thật | **Có** (24 bảng, 30 FK, 99 CHECK…) | Lấy từ dump task17 (ĐÃ XÁC MINH); ORM và DB cùng 24 tên bảng |
| Migration | **Có** 7 bản, chuỗi tuyến tính, head `a9c2e4f71b30` | ĐÃ XÁC MINH |
| Hợp đồng schema (freeze) | **Có**: `docs/freeze/M1.0-AUTHORITATIVE-FREEZE-PACK-RESOLVED.md` (15 bảng ban đầu; sau đó thêm `user_notifications`, 5 bảng `candidate_*`/`lecturer_scopus_candidate*`, 3 bảng affiliation = 24) | Nguồn quy ước CHECK/tên ràng buộc |
| ADR liên quan | 4 (EID chuẩn tắc; ingest offline; audit append-only; tách danh tính ↔ bằng chứng) | Dùng để giải trình thiết kế |
| ERD ở dạng nguồn chỉnh sửa | **Không** | Không có `.drawio/.puml/.dbml/.mmd` nào trong toàn bộ `DoAn/` (đã quét) |
| ERD ảnh cũ trong `DoAn.docx` (3 ảnh) | Có nhưng **không khớp DB** (Phụ lục A) | Không dùng làm ERD cuối |
| Data dictionary | **Không** | |
| Kiểm tra ORM ↔ migration ↔ DB | **Chưa** | Mới so tên bảng (khớp). So cột/ràng buộc là việc `DB-01` |

## 4.2. Danh sách bảng theo cụm nghiệp vụ (24 bảng)

(Số dòng: **THEO BÁO CÁO TRƯỚC**; "—" = chưa có số trong báo cáo.)

| Cụm | Bảng | Vai trò | Số dòng teacher | Dùng trong UC |
|---|---|---|---|---|
| **A. Người dùng & kiểm toán** | `users` | Tài khoản, vai trò, liên kết 0..1 hồ sơ GV | 3 | 01, 06, 20–22 |
| | `user_notifications` | Thông báo cho người dùng | — | 03, 06 |
| | `audit_events` | Nhật ký **chỉ ghi thêm**, `before/after_state` JSONB, actor USER/SYSTEM | — | 07 và mọi UC ghi |
| **B. Hồ sơ giảng viên** | `lecturers` | Hồ sơ chủ (master) | 411 (410 + 1 seed) | 05, 08, 18 |
| | `lecturer_source_snapshots` | Bản chụp nguồn bất biến (payload JSONB + SHA-256) | — | 08 |
| | `lecturer_known_publications` | Công bố đã biết của GV (từ Craw), DOI/tiêu đề chuẩn hóa | 327 | 25, 24 |
| **C. Nhập thô Scopus** | `scopus_imports` | Một lần nhập CSV (SHA-256, trạng thái, số đếm, `normalization_summary`) | — | 10, 11 |
| | `raw_scopus_records` | Từng dòng thô (`raw_payload` JSONB, `row_hash`, VALID/INVALID) | 660 hợp lệ | 10, 11 |
| **D. Công bố & tác giả chuẩn** | `publications` | Công bố chuẩn, `eid` UNIQUE | 660 | 11, 13–15 |
| | `publication_raw_sources` | Nguồn gốc: dòng thô → công bố (UNIQUE theo `raw_record_id`) | — | 11, 13 |
| | `scopus_authors` | Tác giả Scopus, `scopus_id` UNIQUE | 1.207 | 12, 16, 24 |
| | `scopus_author_name_variants` | Các dạng tên (hiển thị/đầy đủ) | — | 12, 24 |
| | `publication_authors` | Vị trí tác giả trong công bố (UNIQUE theo (công bố, tác giả) và (công bố, thứ tự)) | 2.751 | 12, 13, 22 |
| **E. Đơn vị công tác (affiliation)** | `organizations` | Tổ chức theo nguồn ngoài (`source_system`, ROR) | ≈217 (Task 11) | 13, 25 |
| | `publication_author_affiliation_resolutions` | Kết quả đối chiếu **từng nguồn × từng vị trí tác giả** (VERIFIED/CORROBORATED/UNRESOLVED) | 5.502 | 13, 25 |
| | `publication_author_affiliations` | Từng dòng đơn vị gắn với một resolution | 4.147 | 13, 25 |
| **F. Đối soát & danh tính** | `candidate_generation_runs` | Một lần chạy sinh ứng viên (rule set/version, `source_state`) | — | 24 |
| | `lecturer_scopus_candidates` | Cặp (GV, tác giả Scopus) được đề xuất; UNIQUE theo cặp | 40 PENDING | 17, 18, 24 |
| | `lecturer_scopus_candidate_observations` | Lần thấy ứng viên trong một lần chạy (ảnh chụp JSONB, hash) | — | 17, 24 |
| | `lecturer_scopus_candidate_evidence` | Bằng chứng (NAME / PUBLICATION), rule id/version, dấu vân tay | — | 17, 24 |
| | `lecturer_scopus_candidate_reviews` | **Quyết định duyệt** (ACCEPT/REJECT/REOPEN; chuyển trạng thái có CHECK) | 0 | 18, 19 |
| | `lecturer_scopus_identities` | **Danh tính đã chốt** (CANDIDATE/APPROVED/REJECTED/REVOKED); UNIQUE một phần: 1 Scopus ID chỉ APPROVED cho 1 GV | 0 APPROVED | 18, 20–23 |
| | `identity_evidence` | Bằng chứng gắn danh tính (7 loại cho phép) | 0 | 18 |
| | `mapping_reviews` | Lịch sử đổi danh tính (APPROVE/REJECT/REVOKE/REOPEN + `compensates_review_id`) | 0 — **chưa có mã ghi** | — |

## 4.3. Quan hệ (30 khóa ngoại — danh sách đối chiếu cho ERD)

Mọi FK `ON DELETE RESTRICT` trừ ghi chú. Quan hệ `1—N` đọc "cha → con".

| Cụm | Cha → Con (cột con) | Ghi chú |
|---|---|---|
| A | `users` → `audit_events` (`actor_user_id`); → `user_notifications` (`user_id`) | `entity_id` của audit **không có FK** (đa hình theo `entity_type`) |
| A/B | `lecturers` → `users` (`lecturer_id`, UNIQUE một phần ⇒ 0..1 tài khoản/GV) | |
| B | `lecturers` → `lecturer_source_snapshots` (`lecturer_id`, NULL được); (`snapshot_id`,`lecturer_id`) ⇒ `lecturer_known_publications` | **FK ghép** bảo đảm công bố đã biết thuộc đúng GV của snapshot |
| C | `scopus_imports` → `raw_scopus_records` (`import_id`) | |
| D | `raw_scopus_records` → `publication_raw_sources` (`raw_record_id`, UNIQUE ⇒ 1 dòng thô ↔ ≤1 công bố); `publications` → `publication_raw_sources`; `publications` → `publication_authors` (**CASCADE**); `scopus_authors` → `publication_authors`; `scopus_authors` → `scopus_author_name_variants`; `raw_scopus_records` → `scopus_author_name_variants` (`first_seen_raw_record_id`) | |
| E | `publication_authors` → `…_affiliation_resolutions` (**CASCADE**); (`resolution_id`,`link_status`) ⇒ `publication_author_affiliations` (**CASCADE**, FK ghép: trạng thái dòng đơn vị luôn bằng trạng thái resolution); `organizations` → `publication_author_affiliations` (`organization_id`) | |
| F | `lecturers`,`scopus_authors` → `lecturer_scopus_candidates`; `candidate_generation_runs`,`candidates` → `…_observations`; `…_observations` → `…_evidence`; `candidates`,`…_observations`,`users`(reviewer),`lecturer_scopus_identities`(resulting) → `…_candidate_reviews`; `lecturers`,`scopus_authors` → `lecturer_scopus_identities`; `identities` → `identity_evidence`; `identities`,`users` → `mapping_reviews` (+ tự tham chiếu `compensates_review_id`) | |

## 4.4. Tài sản cần tạo (đối chiếu yêu cầu mục IV)

| # | Tài sản | Số lượng | Định dạng nguồn | Định dạng nộp báo cáo | Tự động từ schema? |
|---|---|---|---|---|---|
| 1 | **ERD tổng thể** (24 bảng, chỉ tên bảng + PK/FK) | 1 | `.dbml` + `.puml` (hoặc Mermaid `erDiagram`) | SVG/PNG | **Cao (≈90%)**: sinh bằng script từ `schema.sql` |
| 2 | **ERD phân cụm** (A–F) có đủ cột | 6 | cùng nguồn | SVG/PNG | Cao |
| 3 | Mô hình quan hệ (lược đồ quan hệ dạng chữ: `Bảng(PK, FK…)`) | 1 tài liệu | Markdown | bảng | Cao |
| 4 | **Data dictionary** 24 bảng (cột, kiểu, null, default, mô tả nghiệp vụ) | 1 tài liệu | Markdown + CSV | bảng phụ lục | Cột/kiểu: tự động; **mô tả nghiệp vụ: cần viết/duyệt** |
| 5 | Bảng khóa và quan hệ (30 FK, 16+7 UNIQUE) | 1 | Markdown/CSV | bảng | Tự động |
| 6 | Bảng ràng buộc nghiệp vụ (99 CHECK, rút gọn theo nhóm: vocab, JSONB object, định dạng SHA-256/ORCID, chuyển trạng thái, nhất quán) | 1 | Markdown | bảng | Một phần (nhóm hóa thủ công) |
| 7 | Mapping ORM ↔ migration ↔ bảng thực | 1 + script | Markdown + script kiểm | bảng | Cao (script) |
| 8 | Giải thích chọn kiểu dữ liệu và chỉ mục (`uuid` + `gen_random_uuid()`, `timestamptz`, `jsonb`, partial unique, `lower(email)`) | 1 | Markdown | đoạn văn | Thủ công (ý tưởng sẵn có ở freeze M1.0) |
| 9 | Sơ đồ vòng đời dữ liệu (thô → chuẩn → ứng viên → duyệt → danh tính → công bố của GV) | 1 | `.puml` | SVG | Thủ công |
| 10 | Ma trận bảng × use case | 1 | Markdown | bảng | Một phần |

**Số ERD cần:** 1 tổng thể + 6 phân cụm = **7**. Khuyến nghị **không** vẽ cả 24 bảng đầy đủ cột trong một hình (không đọc được); hình tổng thể chỉ có bảng + FK.
**Quy tắc kiểm:** script so danh sách FK trong sơ đồ với `pg_constraint` (30 FK); sai khác = FAIL (không vẽ quan hệ không có thật).

## 4.5. Điểm cần giải thích rõ trong báo cáo / dễ bị hiểu sai (nhận xét của Database Designer)

1. **`mapping_reviews` và `identity_evidence`**: `identity_evidence` có mã ghi (khi ACCEPT); `mapping_reviews` **không có mã ghi**, 0 dòng — chỉ là phần thiết kế dự phòng cho REVOKE/REOPEN. ERD phải đánh dấu "chưa dùng trong luồng hiện tại" để không bị hiểu là chức năng hoàn tác đã có.
2. **Schema rộng hơn phần cài đặt:** `identity_evidence.evidence_type` cho phép `ORCID_EXACT`, `COAUTHOR_CONFIRMED`, `AFFILIATION_MATCH`, `NAME_SIMILARITY`…; bộ sinh ứng viên chỉ tạo bằng chứng `NAME` và `PUBLICATION`; `confidence_score` **luôn NULL** (migration `d3f7a1c9e2b4` làm cho nullable). Cột `lecturer_scopus_identities.recommendation*` chưa có mã ghi.
3. **Hai bộ bảng review** (`lecturer_scopus_candidate_reviews` cho ứng viên; `mapping_reviews` cho danh tính) dễ gây nhầm — cần sơ đồ "ai ghi bảng nào, khi nào".
4. **Không có bảng "nguồn xuất bản" (journal)** — `publications.source_title` là chuỗi tự do. Đề cương PI-2.1 nêu "nguồn xuất bản" như thực thể; phải giải trình đây là lựa chọn thiết kế (dữ liệu Scopus CSV không có ISSN chuẩn hóa trong cột đang dùng — **SUY LUẬN, cần kiểm cột CSV**) hoặc nêu là hạn chế.
5. **`lecturers` không chứa Scopus Author ID.** Liên kết GV ↔ Scopus nằm hoàn toàn ở `lecturer_scopus_identities` (và ứng viên). ERD cũ ghi `lecturers.scopus_author_id UK` — sai với thiết kế hiện tại.
6. **`lecturers.email` cho phép trùng** (migration `c3f0b9a18d42`) nhưng `users.email` UNIQUE không phân biệt hoa/thường — cần giải thích (cảnh báo "email đang dùng cho nhiều hồ sơ").
7. **Audit append-only chỉ ở tầng dịch vụ** (ADR-003; không có trigger/REVOKE trong DB). Không viết "DB cấm sửa/xóa audit" trong báo cáo; viết "quy ước và kiểm thử ở tầng ứng dụng".
8. Dữ liệu nguồn giới hạn: Khoa/Bộ môn GV phần lớn trống; `tel` và Google Scholar có trong JSON nhưng **không có cột DB**; affiliation không đến từ Scopus mà từ OpenAlex/Crossref; chỉ 660 công bố trong CSV mẫu.

## 4.6. "Vì sao" — nội dung sinh viên cần tự hiểu để giải thích (không sao chép)

| Câu hỏi bảo vệ | Điểm then chốt (từ ADR/freeze/schema) |
|---|---|
| Vì sao có bảng thô và bảng chuẩn? | Giữ nguyên đầu vào (đề cương 7a), truy xuất nguồn, chuẩn hóa chạy lại được mà không mất dữ liệu gốc |
| Vì sao tách `scopus_authors` và `publication_authors`? | Một tác giả (Scopus ID) có nhiều công bố; một công bố có nhiều tác giả (quan hệ N–N có thuộc tính thứ tự) |
| Vì sao một tác giả nhiều affiliation; mỗi nguồn có resolution riêng? | Đơn vị là thuộc tính **của tác giả trên từng bài**, từ nguồn ngoài; mỗi nguồn có độ tin cậy khác nhau; không sao chép đơn vị cấp công bố cho tác giả |
| Vì sao candidate/evidence/review? | Tách "đề xuất" khỏi "quyết định"; giải thích được vì sao; con người chịu trách nhiệm (ADR-004) |
| Vì sao audit chỉ thêm? | Truy vết, không sửa lịch sử (ADR-003) |
| Vì sao không lưu danh tính đoán là APPROVED? | Tên giống ≠ cùng người; APPROVED chỉ sau ACCEPT của người |
| Vì sao có FK/UNIQUE ghép? | Ép bất biến ngay ở DB (vd. công bố đã biết thuộc đúng GV của snapshot; trạng thái dòng đơn vị = trạng thái resolution; 1 Scopus ID chỉ APPROVED cho 1 GV) |
| Vì sao không nối theo tên? | Trùng tên (ca 5 GV dùng chung 1 Scopus ID), viết tắt/đảo tên, dấu tiếng Việt |

---

# 5. KIỂM KÊ UML / KIẾN TRÚC

## 5.1. Hiện trạng

- **Không có tệp sơ đồ nguồn** (`.puml/.drawio/.mmd/.bpmn`) nào trong dự án; Task 18 đã quét toàn bộ `DoAn/` (trừ venv, `node_modules`, cluster PostgreSQL).
- Chỉ có 5 ảnh trong `DoAn.docx`: BPMN-like (tuần 1), Use Case (tuần 2), ERD ×3 (tuần 3) — **đều lệch hệ thống** (Phụ lục A). **Chưa có** kiến trúc, sequence, activity, state, DFD.
- Mô tả bằng chữ có sẵn để làm nguồn: `HUONG_DAN…` chương 5 (luồng dữ liệu), 4.9–4.11 (affiliation, matching, duyệt), ADR 001–004, freeze M1.0/M2.7/M2.8/C1/C2.

## 5.2. Kiến trúc thật (ĐÃ XÁC MINH — để vẽ đúng, không thêm thành phần không dùng)

```
Trình duyệt ── React 18 + Vite + TypeScript + Tailwind (+ AntD chỉ ở trang Duyệt đối sánh)
      │  HTTP/JSON, cookie JWT (httponly)
      ▼
FastAPI (api/v1/endpoints → services → repositories → models SQLAlchemy 2.x)  ── Alembic migrations
      │  psycopg2
      ▼
PostgreSQL 17 (cụm demo 127.0.0.1:55432; 24 bảng; không trigger/hàm)
      ▲
Script CLI (backend/scripts): sinh ứng viên · nạp Craw · nạp affiliation (OpenAlex/Crossref/ORCID đã tải sẵn dưới dạng tệp) · bootstrap ADMIN
Nguồn tệp ngoài: CSV Scopus · JSON hồ sơ GV (ICTU Repository/DSpace) · Craw snapshots
```

- **Không có** Redis, Kafka, Celery, hàng đợi tác vụ nền riêng: nhập CSV/chuẩn hóa chạy trong tiến trình API (có theo dõi tiến độ/hủy qua `scopus_imports`).
- **Không gọi Scopus API / dịch vụ ngoài trực tuyến** từ ứng dụng (ADR-002: nạp offline).
- `compose.yaml` + `compose.local.yaml` + `compose.prod.yaml` + `Dockerfile` (backend, frontend) **tồn tại** (PostgreSQL 16-alpine) nhưng **chưa có bằng chứng đã chạy**; môi trường thử nghiệm thật là **localhost + BAT + cụm PostgreSQL 17 riêng** (`docs/demo/BACKEND_LOCALHOST_14_10.md`). Sơ đồ triển khai phải vẽ **môi trường localhost thật**; compose chỉ ghi chú "tham chiếu, chưa kiểm chứng".
- Điểm cần ghi nhớ khi vẽ: tách tầng ✔ (giao diện / Web API / dữ liệu) đúng như PI-2.2; RBAC kiểm ở **backend** (`require_role`), menu giao diện chỉ để tiện.

## 5.3. Danh mục sơ đồ cần tạo (23 sơ đồ)

Cột "Nguồn dữ liệu" là tệp/hàm sẽ đọc khi vẽ; "Tự động" = mức độ sinh được từ mã; "Giờ" là giờ Claude (mục 11).

| ID | Sơ đồ | Cần? (đề cương) | Có chưa | Nguồn dữ liệu | Tự động | Phải kiểm thủ công | Nguồn → nộp | Giờ |
|---|---|---|---|---|---|---|---|---|
| **ARC-1** | Kiến trúc tổng thể phân tầng + thành phần | **Bắt buộc** PI-2.2 | Không | `main.py`, `api/v1/router.py`, cấu trúc thư mục, `frontend/package.json` | Thấp | Chỉ vẽ thành phần có thật | `.puml` → SVG/PNG | 1,5 |
| **ARC-2** | Triển khai (localhost demo) | Nên (PI-4.1) | Không | `BACKEND_LOCALHOST_14_10.md`, BAT, `start_*.cmd` (đọc, không in bí mật) | Thấp | Cổng/tiến trình đúng thực tế; không in mật khẩu | `.puml` → SVG | 1 |
| **BPMN-1** | Quy trình nghiệp vụ (as-implemented), 4 làn: ADMIN · Hệ thống · Kỹ thuật viên (CLI) · REVIEWER/ADMIN duyệt (+ LECTURER xem) | **Bắt buộc** PI-1.1 | Có ảnh cũ **sai** | `HUONG_DAN` ch.5; Phụ lục A | Thấp | Từng bước/người thực hiện/vào–ra khớp mã | `.bpmn` (bpmn.io) + `.puml` dự phòng → SVG | 2,5 |
| **SEQ-1** | Đăng nhập & phân quyền | Nên | Không | `auth.py`, `security.py`, `dependencies.py` | Trung bình | Mã trạng thái HTTP | `.puml` | 0,5 |
| **SEQ-2** | Nhập JSON GV: preview → import → rollback | Nên | Không | `lecturers.py`, `lecturer_dataset/importer.py`, `rollback.py` | Trung bình | | `.puml` | 0,5 |
| **SEQ-3** | Nhập CSV → chuẩn hóa công bố → bóc tách tác giả | **Nên** (luồng cốt lõi) | Không | `imports.py`, `scopus_import_service.py`, `scopus_normalizer.py`, `scopus_author_normalizer.py` | Trung bình | Điểm bất đồng bộ/tiến độ | `.puml` | 0,75 |
| **SEQ-4** | Xem chi tiết công bố (kèm đơn vị theo tác giả, nguồn gốc) | Nên | Không | `publications.py`, `publication_queries.py`, `author_affiliation` | Trung bình | | `.puml` | 0,5 |
| **SEQ-5** | Nạp affiliation ngoài (CLI) và hiển thị (VERIFIED/CORROBORATED/UNRESOLVED) | **Nên** (điểm nhấn kỹ thuật) | Không | `import_author_affiliations.py`, `affiliation_import.py`, `author_affiliation.py` | Trung bình | Quy tắc căn chỉnh | `.puml` | 0,75 |
| **SEQ-6** | Sinh ứng viên đối soát (CLI) | **Nên** | Không | `generate_matching_candidates.py`, `candidate_generator.py`, `publication_evidence_enricher.py`, `candidate_persistence.py` | Trung bình | | `.puml` | 0,5 |
| **SEQ-7** | Duyệt ACCEPT/REJECT (kể cả 409) | **Bắt buộc** (UC cốt lõi) | Không | `reviews.py`, `candidate_review_service.py` | Trung bình | Thứ tự khóa dòng, kiểm tra quan sát/phiên bản | `.puml` | 0,75 |
| **SEQ-8** | LECTURER xem công bố sau khi có APPROVED | Nên | Không | `lecturer_scopus.py`, `lecturer_scopus_projection.py` | Trung bình | | `.puml` | 0,5 |
| **ACT-1** | Đăng nhập | Tùy | Không | như SEQ-1 | Thấp | | `.puml` | 0,3 |
| **ACT-2** | Nhập JSON GV (nhánh lỗi/xung đột) | Nên | Không | `importer.py` (xung đột fail-closed) | Thấp | | `.puml` | 0,5 |
| **ACT-3** | Nhập CSV (trùng SHA-256, thiếu EID, lỗi dòng, hủy) | **Nên** | Không | `scopus_csv_parser.py`, `scopus_import_service.py` | Thấp | | `.puml` | 0,5 |
| **ACT-4** | Chuẩn hóa công bố + bóc tách tác giả | Nên | Không | `scopus_normalizer.py` | Thấp | Các kết quả NEW/EXISTING_* | `.puml` | 0,5 |
| **ACT-5** | Sinh ứng viên (4 luật tên → làm giàu công bố → lưu bền) | **Nên** | Không | `candidate_generator.py` | Thấp | | `.puml` | 0,5 |
| **ACT-6** | Duyệt ACCEPT/REJECT | **Bắt buộc** | Không | `candidate_review_service.py` | Thấp | | `.puml` | 0,5 |
| **ACT-7** | Xử lý lỗi & xung đột (Scopus ID dùng chung 409, phiên bản cũ, trùng nhập, lỗi dòng) | Nên (đề cương nêu lỗi/trùng/xung đột) | Không | các lớp `*Error` trong service | Thấp | | `.puml` | 0,5 |
| **STM-1** | Vòng đời đợt nhập CSV (`scopus_imports.status`: RECEIVED→PARSING→VALIDATED→STAGED→APPLIED/FAILED/CANCELLED) | Nên | Không | CHECK `ck_scopus_imports_status`; `M1C-02` | **Cao** (trạng thái từ DB) | Các chuyển trạng thái thật trong code | `.puml` | 0,5 |
| **STM-2** | Ứng viên (PENDING→ACCEPTED/REJECTED/SUPERSEDED; REOPEN chỉ trong schema) | **Nên** | Không | CHECK `…_candidate_reviews_transitions` | **Cao** | Đánh dấu phần chưa có API | `.puml` | 0,5 |
| **STM-3** | Danh tính (CANDIDATE/APPROVED/REJECTED/REVOKED) — **chỉ đường ACCEPT được cài đặt** | Nên | Không | CHECK `mapping_reviews_transitions` | Cao | Ghi chú REVOKE/REOPEN chưa dùng | `.puml` | 0,4 |
| **STM-4** | Tài khoản (hoạt động ↔ khóa; thu hồi phiên qua `auth_version`) | Tùy | Không | `users.is_active`, `auth_version` | Trung bình | | `.puml` | 0,3 |
| **DFD-1** | Luồng dữ liệu: ICTU/Craw/CSV → chuẩn → bằng chứng → ứng viên → duyệt → danh tính → "công bố của giảng viên" | **Nên** (PI-2.2 nêu "luồng nhập, xử lý, duyệt, xuất") | Một phần (chữ trong HUONG_DAN) | `HUONG_DAN` ch.5 + schema | Trung bình | | `.puml` (+ vòng đời dữ liệu cho `DB`) | 1 |

**Số lượng đề xuất:** 23 sơ đồ UML/kiến trúc/quy trình + 7 ERD + 6 Use Case = **36 sơ đồ**. Báo cáo không cần đưa hết vào văn bản: chương 2–3 chỉ cần ≈ 18–22 hình; phần còn lại là phụ lục/slide.

**Thứ tự tạo (đường găng):** schema/ERD (DB-02) → UC (USE-02) → BPMN (UML-02) → ARC-1 → SEQ-7/ACT-6 (cốt lõi) → còn lại. **Sequence/Activity nên viết sau khi chốt UC và ERD** vì tham chiếu tên bảng/route.

## 5.4. Công cụ và khả năng kiểm tra render

| Phương án | Hỗ trợ loại sơ đồ | Trạng thái trong máy | Khuyến nghị |
|---|---|---|---|
| **PlantUML** (`.puml`) | Use case ✔, sequence ✔, activity ✔, state ✔, component/deployment ✔, ER/IE ✔ | Có Java (`C:\Program Files\Common Files\Oracle\Java\javapath\java`); **chưa có `plantuml.jar`**; chưa có Graphviz (dùng bố cục `smetana` tích hợp) | **Chọn làm chuẩn cho UML** — nguồn văn bản, sửa tay dễ, render offline sau khi có jar |
| **Mermaid** (`.mmd`) | Sequence ✔, state ✔, ER ✔, flowchart ✔; **không có use case chuẩn UML** | Chưa có `mmdc`; có Node 24 | Dùng cho **ERD/state/flow nhúng Markdown** (xem trực tiếp trên GitHub/VS Code) khi cần |
| **DBML** (`.dbml`) | ERD | dbdiagram.io (web) | Sinh bằng script; **người dùng dán lên dbdiagram.io để chỉnh/ xuất ảnh** |
| **BPMN 2.0** (`.bpmn`) | BPMN đúng chuẩn | bpmn.io/demo.bpmn.io (web) | Đề cương ghi "BPMN" nên nên nộp `.bpmn`; kèm bản PlantUML dự phòng |
| **draw.io** (`.drawio`) | Mọi loại, vẽ tay | draw.io web/desktop | Phương án chỉnh sửa tay cuối cùng cho SV khi hết Claude |

**Phụ thuộc cần người dùng đồng ý (D11):** tải `plantuml.jar` (≈ 10–15 MB, từ phát hành chính thức; kiểm SHA-256 và đặt ở `_quan_ly_do_an\tools\` — ngoài Git) hoặc cho phép cài `@mermaid-js/mermaid-cli` (kéo theo Chromium ≈ 150 MB). **Nếu không đồng ý tải gì:** vẫn tạo `.puml/.dbml` nhưng **không kiểm tra được render** — khi đó phải ghi rõ trạng thái "CHƯA RENDER-KIỂM" và nhờ người dùng dán thử vào trình xem web (planttext.com/dbdiagram.io), rủi ro lỗi cú pháp cao hơn.

---

# 6. KIỂM KÊ UI / FIGMA

## 6.1. Hiện trạng giao diện (ĐÃ XÁC MINH từ `frontend/src`)

| Mục | Kết quả |
|---|---|
| Figma/mockup/wireframe/design system cũ | **Không có** tệp nào (không `.fig`, không tham chiếu Figma trong repo — kết quả quét `Figma\|figma` chỉ ra tệp không liên quan) |
| Công cụ thiết kế khả dụng trong phiên này | **Không có Figma API/plugin/connector** (không có công cụ Figma trong danh sách công cụ). **Không tuyên bố đã/có thể tạo Figma.** Có `mcp-registry` để *tìm* connector, nhưng việc kết nối và cấp quyền là của người dùng và chưa được kiểm tra |
| Thư viện | React 18, Vite 5, TypeScript 5, **Tailwind 3 (`theme.extend` rỗng)**, **AntD 5 chỉ ở trang Duyệt đối sánh**, không có `ConfigProvider` (AntD dùng màu mặc định, khác màu thương hiệu) |
| Design tokens | **Không có tệp token.** Màu rải rác dạng hex: `#3A5FC3` (≈302 lần — màu chủ đạo), `#2F4EA6` (≈21 lần, hover), nền `#F4F6FB`, thanh cuộn `#CBD5E1`; phông **Saira** (Google Fonts); thang xám `slate-*` của Tailwind |
| Responsive | Có lớp `sm:/lg:` và thanh bên dạng ngăn kéo trên điện thoại (`Sidebar.tsx`, `isMobile`), `meta viewport` đúng; **chưa có ảnh/bằng chứng ở khổ mobile** |
| Ngôn ngữ | Tiếng Việt có dấu + tiếng Anh (`i18n/locales`), một số chuỗi nhúng thẳng trong trang (`locale === "vi" ? … : …`) |
| Mức nhất quán | Khá tốt (thẻ trắng, bảng `slate`, nút xanh chủ đạo), **trừ trang Duyệt đối sánh dùng AntD** (Table/Select/Descriptions) nhìn khác các trang còn lại |
| Cấu trúc mã | Trang rất lớn, ít thành phần tái dùng: `Imports` ≈ 2,4 nghìn dòng, `Lecturers` ≈ 1,6 nghìn dòng → **không thể "xuất" Figma tự động từ cây thành phần**; tái dựng phải từ giao diện đang chạy hoặc từ ảnh/HTML |
| Trạng thái loading/empty/error | Có ở hầu hết trang (đếm từ khóa: nhiều trang có `animate-spin`/"Đang tải"/"Không có…"); `ErrorBoundary` toàn cục (Task 17); trang **Tra cứu** và **Trang chủ** ít trạng thái nhất (cần kiểm tay). Biểu đồ Trang chủ là giữ chỗ |
| Màn giữ chỗ | `/tasks` (`PlaceholderPage`), `DiffViewerStub` (**không được import ở đâu**) |
| Có tái dựng được thiết kế từ frontend hiện tại không? | **Có**, ở mức bố cục/màu/chữ/khoảng cách (rút từ lớp Tailwind + ảnh chụp độ phân giải cao); **không** tự động hóa hoàn toàn |

## 6.2. Danh mục màn hình thiết kế

**Đã triển khai (15 route) + hộp thoại quan trọng + 1 màn đề xuất:**

| Mã | Màn hình | Route | Vai trò | Triển khai | Trạng thái cần thiết kế (loading/empty/error/modal) |
|---|---|---|---|---|---|
| S01 | Đăng nhập | `/login` | Công khai | ✔ | lỗi sai mật khẩu, tài khoản khóa |
| S02 | Trang chủ | `/home` | Mọi vai trò | ✔ (biểu đồ giữ chỗ) | empty biểu đồ |
| S03 | **Tổng quan (thống kê)** | `/dashboard` | ADMIN | ✔ (chỉ số đếm) | loading, lỗi API |
| S04 | Nhập dữ liệu: JSON GV (kiểm tra → xem trước → xác nhận) và CSV Scopus | `/imports` | ADMIN | ✔ | lỗi cú pháp, trùng, xem trước, tiến độ, hủy |
| S05 | Chi tiết đợt nhập (lỗi theo dòng, hoàn tác) | `/imports` (modal) | ADMIN | ✔ | modal xác nhận xóa/hoàn tác |
| S06 | Chuẩn hóa dữ liệu (tab Công bố / Tác giả) | `/normalization` | ADMIN | ✔ | đang chạy, hoàn thành, lỗi |
| S07 | Danh sách giảng viên | `/lecturers` | ADMIN | ✔ | empty, tìm kiếm không dấu, cảnh báo email trùng |
| S08 | Chi tiết giảng viên + tài khoản/vai trò | `/lecturers` (modal) | ADMIN | ✔ | khóa/đặt lại mật khẩu, 409 |
| S09 | **Danh sách công bố** | `/publications` | ADMIN, REVIEWER | ✔ | empty, bộ lọc |
| S10 | **Chi tiết công bố** + đơn vị theo tác giả + nguồn gốc | `/publications/:eid` | ADMIN, REVIEWER | ✔ | 3 trạng thái affiliation |
| S11 | Tra cứu tổng hợp | `/search` | ADMIN, REVIEWER | ✔ | empty, loading |
| S12 | **Hàng đợi đối soát (phê duyệt)** | `/reviews` | ADMIN, REVIEWER | ✔ | bộ lọc, empty |
| S13 | Chi tiết ứng viên (A–E: GV, tác giả, bằng chứng tên, bằng chứng công bố, ngữ cảnh mơ hồ) | modal | ADMIN, REVIEWER | ✔ | cảnh báo dùng chung |
| S14 | Xác nhận ACCEPT / REJECT (lý do bắt buộc) | modal | ADMIN, REVIEWER | ✔ | 409 xung đột |
| S15 | Lịch sử review | `/review-history` | ADMIN, REVIEWER | ✔ | empty |
| S16 | Nhật ký hệ thống | `/audit-logs` | ADMIN | ✔ | lọc |
| S17 | Hồ sơ cá nhân (LECTURER) | `/profile` | LECTURER | ✔ | |
| S18 | Liên kết Scopus (LECTURER) | `/identity` | LECTURER | ✔ | empty (chưa có APPROVED) |
| S19 | Công bố của tôi (LECTURER) | `/my-publications` | LECTURER | ✔ | empty |
| **S20** | **So sánh trước/sau chuẩn hóa** (dòng CSV thô ↔ công bố chuẩn) | — | ADMIN (đề xuất) | **✖ CHƯA TRIỂN KHAI** — dữ liệu có sẵn (`raw_payload` + `publications`) nhưng không có màn | toàn bộ |

**Bộ tối thiểu theo PI-2.3 (8 mockup):** S09 (danh sách) · S10 (chi tiết) · S04 (nhập dữ liệu) · **S20 (so sánh trước/sau — thiết kế mới)** · S12+S13 (hàng đợi phê duyệt + chi tiết) · S03 (thống kê) · S01 (đăng nhập) · S14 (xác nhận duyệt). Bộ đầy đủ = 20 mã.

## 6.3. Phương án tạo bộ thiết kế chỉnh sửa được

| Phương án | Mô tả | Ưu | Nhược | Thời gian |
|---|---|---|---|---|
| **A (đề xuất)** | Claude tạo (1) **design tokens** (`tokens.json` + bảng màu/chữ/khoảng cách rút từ mã), (2) **bộ mockup nguồn HTML/SVG** dựng lại từ giao diện đã triển khai cho 8 màn (+S20 đánh dấu "đề xuất"), (3) **hướng dẫn nhập vào Figma** (plugin nhập HTML/SVG, ví dụ html.to.design — **cần SV tự kiểm tra có dùng được/điều khoản**) | Khớp phần mềm thật; có nguồn chỉnh sửa; nhanh | Lớp Figma cuối cùng do SV thực hiện; nhập tự động cần dọn lại | Claude 8,5 giờ (UI-01 2,5 + UI-02 6); SV 2–3 giờ |
| B | Claude chỉ làm tokens + đặc tả bố cục + ảnh độ phân giải cao; SV tự dựng Figma | Rủi ro kỹ thuật thấp | Tốn thời gian SV; có thể không kịp | Claude 3 giờ; SV 8–12 giờ |
| C | Kết nối Figma connector (nếu SV có và cấp quyền), Claude tạo file trực tiếp | Đúng "Figma thật" | **Chưa có công cụ trong phiên**; không chắc kết nối được trước 14/10 | Chưa ước lượng được |

Quy tắc bắt buộc cho mọi phương án: đồng bộ giao diện đã triển khai; tiếng Việt có dấu; **không** thiết kế khác hẳn rồi gọi là sản phẩm đã hoàn thành; màn S20 và mọi chức năng chưa có phải gắn nhãn **"Đề xuất thiết kế — chưa triển khai"**; không biến giữ chỗ (biểu đồ, `/tasks`) thành chức năng. **Không gọi SVG/PNG là Figma.**

**Tệp bàn giao UI:** `docs/design/ui/tokens.json`, `docs/design/ui/UI_INVENTORY.md` (20 màn × trạng thái × route × API), `docs/design/ui/mockups/*.html|*.svg`, `docs/design/ui/HUONG_DAN_NHAP_FIGMA.md`, `docs/design/ui/MANIFEST.md`.

---

# 7. KIỂM KÊ SCREENSHOT / BẰNG CHỨNG

## 7.1. Ảnh hiện có (ĐÃ XÁC MINH: liệt kê + kích thước 29/29; mở xem 2/29)

Thư mục `_quan_ly_do_an\evidence\task16\screenshots` (25 ảnh) và `…\task17\screenshots` (4 ảnh), **ngoài Git**.

| Nhận xét | Chi tiết |
|---|---|
| Chất lượng | **JPEG 3–37 KB, tối đa 800×453 px** (nhiều ảnh 400–560 px). Chữ nhỏ, **không đủ cho báo cáo in/slide**; chỉ phù hợp **nhật ký kiểm thử và demo dự phòng** |
| Chức năng thật | Ảnh chụp từ ứng dụng chạy thật |
| Nguồn dữ liệu | Chủ yếu **DB test** (`e2e_t16`, `empty_t16`, `e2e_t17` — bản sao teacher + dữ liệu thử). Ví dụ: "Tổng số 412" (411 + 1 hồ sơ thử), hồ sơ "Giảng viên Thử T16". **Không được trình bày như dữ liệu teacher/thật** |
| Thông tin nhạy cảm | Ảnh mở thấy **email tài khoản thử** (`admin@gmail.com`, `nvhuan@ictu.edu.vn`) và UUID hồ sơ. **Chưa rà 27 ảnh còn lại** — cần rà trước khi đưa vào báo cáo. Không thấy mật khẩu/JWT trong 2 ảnh đã mở |
| Vị trí | Ngoài Git (đúng quy tắc không đưa bằng chứng có thông tin cá nhân vào Git) |

## 7.2. Độ phủ so với bộ ảnh chuẩn

| Mục chuẩn | Ảnh hiện có | Đánh giá |
|---|---|---|
| Màn hình đăng nhập (sạch) | `01_dang_nhap_sai` (lỗi sai mật khẩu) | **Thiếu** ảnh đăng nhập sạch; có ảnh lỗi |
| Dashboard | `02_dashboard` | Có (thấp phân giải) |
| Danh sách giảng viên | — (chỉ modal 04, 05) | **Thiếu** |
| Chi tiết giảng viên | `05`, `06` | Có (thấp phân giải) |
| Import preview / result | `31`, `32`, `33`, `34` | Có |
| Lỗi validation | `30`, `34`, `41` | Có |
| Publications / detail / affiliation | `10`, `11`, `12` | Có |
| Matching queue / evidence / review modal | `19`, `20`, `20b`, `21` | Có |
| Ví dụ xung đột (409) | `22`, `t17/04` | Có |
| Review history | — | **Thiếu** |
| Audit | — | **Thiếu** (báo cáo ghi BROWSER_PASS nhưng không có ảnh) |
| LECTURER profile / identity | — (`23` là công bố của tôi) | **Thiếu** |
| REVIEWER menu | `t17/01` | Có |
| Import CSV result / chuẩn hóa | `40`, `42`, `43` | Có |
| Tra cứu, tab Tác giả, khổ điện thoại, trạng thái empty/error | — | **Thiếu** |

Kết luận: về **độ phủ nội dung ≈ 13/18 mục có ảnh**, nhưng **0/18 đạt độ phân giải cho báo cáo** → cần chụp lại.

## 7.3. Bộ ảnh chuẩn đề xuất (32 ảnh) — quy tắc

- **Khổ:** desktop 1440×900 (PNG); 3 ảnh mobile 390×844. **Nguồn:** DB kiểm thử (bản sao teacher) cho mọi ảnh có thao tác ghi; cảnh chỉ-đọc có thể dùng bản sao teacher, **ghi rõ "DB kiểm thử"** trong chú thích.
- **Mỗi ảnh có siêu dữ liệu (manifest JSON, ngoài Git):** mã ảnh · chức năng · vai trò · công cụ chụp · tên DB · thời điểm (ISO) · viewport · SHA-256 · bằng chứng đi kèm (API/test) · chú thích đề xuất · đường dẫn lưu.
- **Che/tránh:** mật khẩu, JWT/cookie, email cá nhân thật (dùng tài khoản thử), khóa API; **không** chụp ở teacher các thao tác ghi.
- **Lưu:** `D:\DataFolder\ProjectIctu\DoAn\_quan_ly_do_an\evidence\task2x\report_shots\` (ngoài Git); chỉ **mục lục + manifest không chứa PII** nằm trong Git (`docs/design/evidence/`).
- **Điều kiện tiên quyết:** cụm PostgreSQL demo hiện **không chạy**; cần người dùng bật qua BAT hoặc cho phép Claude chạy `start_postgres.cmd`, rồi khởi động backend/frontend trỏ DB kiểm thử (xem BACKEND_LOCALHOST §4b và Task 16–17). Không thao tác trên cổng 5432.

| Mã | Chức năng | Vai trò | Dữ liệu cần có | Dùng cho |
|---|---|---|---|---|
| E01 | Đăng nhập (sạch) | — | — | Báo cáo, slide |
| E02 | Đăng nhập sai mật khẩu | — | — | Báo cáo (lỗi) |
| E03 | Tổng quan | ADMIN | DB kiểm thử đã nạp | BC, slide |
| E04 | Trang chủ ADMIN | ADMIN | | Slide |
| E05 | Danh sách giảng viên | ADMIN | 410 hồ sơ | BC |
| E06 | Chi tiết giảng viên + tài khoản | ADMIN | | BC |
| E07 | Nhập JSON — kiểm tra/xem trước | ADMIN | DB rỗng/kiểm thử | BC, slide |
| E08 | Nhập JSON — kết quả + hoàn tác | ADMIN | | BC |
| E09 | Nhập JSON — lỗi (cú pháp/thiếu trường/email trùng) | ADMIN | tệp lỗi thử | BC (PI-4.2) |
| E10 | Nhập CSV — tải + kết quả | ADMIN | CSV 660 | BC, slide |
| E11 | Nhập CSV — trùng nội dung (cảnh báo/409) | ADMIN | | BC |
| E12 | Nhập CSV — lỗi theo dòng / thiếu cột EID | ADMIN | CSV lỗi thử | BC (PI-3.3) |
| E13 | Chuẩn hóa công bố (tiến độ + kết quả) | ADMIN | | BC |
| E14 | Tab Tác giả | ADMIN | | BC |
| E15 | Danh sách công bố + bộ lọc | ADMIN | | BC, slide |
| E16 | Chi tiết công bố — đầu trang + nguồn gốc dòng CSV | ADMIN | EID `…105006527625` (ví dụ HUONG_DAN) | BC |
| E17 | Chi tiết công bố — đơn vị theo tác giả (3 trạng thái) | ADMIN | EID ví dụ 1–5 | BC, slide |
| E18 | Tra cứu tổng hợp (không dấu) | ADMIN | | BC |
| E19 | Hàng đợi đối soát (40) | REVIEWER | | BC, slide |
| E20 | Chi tiết ứng viên (A–E, bằng chứng công bố) | REVIEWER | ứng viên có công bố hỗ trợ | BC, slide |
| E21 | Cảnh báo Scopus ID dùng chung (5 GV) | REVIEWER | `59253245500` | BC |
| E22 | Xác nhận ACCEPT | REVIEWER | DB kiểm thử | BC |
| E23 | REJECT bắt buộc lý do | REVIEWER | | BC |
| E24 | 409 xung đột (đã duyệt/dùng chung) | REVIEWER | | BC |
| E25 | Lịch sử review (sau ACCEPT/REJECT) | REVIEWER | | BC |
| E26 | Menu REVIEWER (không có mục quản trị) | REVIEWER | | BC (RBAC) |
| E27 | Nhật ký hệ thống | ADMIN | | BC |
| E28 | LECTURER — hồ sơ | LECTURER | tài khoản thử | BC |
| E29 | LECTURER — liên kết Scopus + công bố của tôi (sau APPROVED) | LECTURER | sau E22 | BC, slide |
| E30 | LECTURER bị chặn trang quản trị (403→về Home) | LECTURER | | BC (RBAC) |
| E31 | Giao diện điện thoại (Home/Công bố/Hàng đợi) ×3 | ADMIN/REVIEWER | | BC (PI-3.2) |
| E32 | Error Boundary / trạng thái lỗi | — | | Demo dự phòng |

**Ảnh nào dùng ở đâu:** báo cáo (chương 4) dùng E-xx đánh dấu BC; slide chọn ≈ 12 ảnh đánh dấu "slide"; **demo dự phòng** dùng bộ cũ (task16/17) + E19, E20, E17 khi mất mạng/DB. **Số ảnh hiện đủ cho báo cáo: 0/32; còn thiếu: 32/32** (nội dung đã có 13/18 mục nhưng phải chụp lại).

---

# 8. KIỂM KÊ THUẬT TOÁN VÀ NGHIÊN CỨU

> Nguyên tắc: **mô tả đúng cái đang chạy.** Bộ đối sánh là **rule-based, xác định (deterministic), không phải machine learning**; không có huấn luyện, không có điểm số tin cậy. Không bịa precision/recall/F1 khi chưa có nhãn tham chiếu.

## 8.1. Thuật toán/quy tắc hiện có (12 mục theo yêu cầu) — đối chiếu mã

| # | Mục | Hiện có (ĐÃ XÁC MINH) | Mã nguồn | Chưa giải quyết / giới hạn |
|---|---|---|---|---|
| 1 | Nhận diện giảng viên ICTU | Tập 410 hồ sơ lấy từ ICTU Repository (DSpace) → `build_ictu_lecturer_dataset.py`/`dspace_parser.py`; kiểm bằng `validate_ictu_lecturer_dataset.py` + JSON Schema; khóa nguồn = `source_id` (URL hồ sơ) | `backend/scripts/*`, `services/lecturer_dataset/*`, `data/lecturers/` | **Chưa đọc kỹ logic build/crawl** trong Task 18 (SUY LUẬN cho phần "cách chọn 410"); Khoa/Bộ môn phần lớn trống |
| 2 | Đối soát khi nhập hồ sơ (import reconciliation) | Khớp theo thứ tự `source_id` → `staff_code` → email (không phân biệt hoa/thường); **không bao giờ dùng tên để gộp** (chỉ cảnh báo trùng tên+bộ môn); xung đột (ID→A nhưng mã/email→B, v.v.) **chặn trước khi ghi**; GV vắng mặt trong tệp **không bị xóa** | `lecturer_dataset/importer.py` (docstring đầu tệp) | |
| 3 | Chuẩn hóa công bố Scopus | EID chuẩn tắc (`normalize_eid`) là khóa chống trùng; `title_normalized` = NFKC + chữ thường + trim; so sánh metadata trên 14 trường → `EXISTING_METADATA_CHANGED` (**không ghi đè**); race-safe bằng savepoint; bất biến số đếm | `normalization/scopus_normalizer.py` | **DOI lưu nguyên văn (trim); không chuẩn hóa nguồn xuất bản** (R5) |
| 4 | Chuẩn hóa tác giả Scopus | Tách các trường tác giả (tên hiển thị, tên đầy đủ, ID) theo `;`; **ID nhúng trong tên đầy đủ phải khớp trường ID** nếu không → lỗi có cấu trúc; upsert `scopus_authors` theo `scopus_id`; thêm biến thể tên (AUTHOR_DISPLAY/AUTHOR_FULL_NAME); gắn `publication_authors` (thứ tự, first-wins) | `normalization/scopus_author_normalizer.py` | Không phân giải nhập nhằng tên giữa các ID khác nhau (không cần: khóa là Scopus ID) |
| 5 | Sinh ứng viên | 4 luật so khớp **bằng nhau tuyệt đối** sau chuẩn hóa: `RULE_EXACT_N0`; `RULE_TITLE_STRIPPED_N0`; `RULE_TITLE_STRIPPED_N2`; `RULE_TITLE_STRIPPED_N2_FORMAT` (bỏ dấu phẩy). Tiền tố học hàm/học vị được **loại bỏ theo danh sách trắng**: `DH.`, `GS.TS.`, `PGS.TS.`, `ThS.`, `TS.`. N0 = NFKC+casefold+gom khoảng trắng; N2 = N0 + `đ→d` + bỏ dấu kết hợp (chỉ để truy xuất). So với 3 bề mặt tên Scopus: tên ưu tiên, `AUTHOR_FULL_NAME`, `AUTHOR_DISPLAY`. Kết quả sắp xếp xác định | `matching/candidate_generator.py` | **Không có so khớp mờ** (edit distance), **không dùng ORCID, đơn vị, năm**; GV tên viết tắt/đảo tên không được truy xuất |
| 6 | Bằng chứng tên | Mỗi (GV, tác giả) giữ tập `CandidateEvidence` (rule, giá trị gốc hai phía, giá trị so sánh, loại bề mặt) → lưu thành `…_candidate_evidence` loại `NAME` với `rule_id/version` + dấu vân tay | `candidate_types.py`, `candidate_persistence.py` | Bằng chứng tên **yếu**; ADR-004: không bao giờ đủ để tự duyệt |
| 7 | Bằng chứng công bố | Làm giàu ứng viên bằng *công bố đã biết* (Craw): khớp công bố chuẩn theo **DOI** (chuẩn hóa `DOI_N0`: NFKC, casefold, bỏ `https://doi.org/`, `doi:`…) rồi **tiêu đề**; luật `RULE_KNOWN_PUBLICATION_DOI_EXACT` / `…_TITLE_EXACT`; **xung đột fail-closed**: `DOI_AMBIGUOUS`, `DOI_TITLE_CONFLICT`, `TITLE_AMBIGUOUS`, `SNAPSHOT_LECTURER_MISMATCH` — xung đột **không tạo bằng chứng hỗ trợ** | `matching/publication_evidence_enricher.py` | Chỉ 48 GV/328 liên kết Craw → chỉ 6/40 ứng viên có bằng chứng công bố (THEO BÁO CÁO TRƯỚC) |
| 8 | Xung đột dùng chung tác giả | Giao diện cảnh báo "Tác giả Scopus dùng chung (N giảng viên)"; **ACCEPT lần 2 cho cùng Scopus ID bị chặn (409)** ở dịch vụ và bằng **chỉ mục unique một phần** ở DB (`uq_identities_scopus_author_approved`) | `candidate_review_service.py::_check_identity_conflicts`; schema | Không có công cụ giải quyết tự động (đúng thiết kế) |
| 9 | Duyệt bởi con người | `ACCEPT` (PENDING→ACCEPTED, tạo danh tính APPROVED + bằng chứng danh tính) / `REJECT` (lý do bắt buộc); kiểm quan sát hiện hành + `version`; khóa dòng; ghi review + audit; CHECK DB ép bảng chuyển trạng thái | `candidate_review_service.py`; CHECK `…_reviews_transitions` | Hoàn tác (REOPEN/REVOKE): **chỉ schema** |
| 10 | Đối soát đơn vị công tác (affiliation) | `align_paper`: theo từng *vị trí tác giả Scopus* của một bài, đối chiếu nguồn ngoài (OpenAlex/Crossref): **VERIFIED** (chuỗi định danh: ORCID của tác giả ngoài + hồ sơ ORCID công khai khai báo Scopus ID của vị trí đó) · **CORROBORATED** (không có ID chung; cùng số tác giả, cùng vị trí, trùng token tên, không mâu thuẫn) · **UNRESOLVED** (+ lý do: `NO_EXTERNAL_WORK`, `AUTHOR_COUNT_MISMATCH`, `NAME_MISMATCH`, `ID_CONFLICT`, …). Chuỗi đơn vị gốc giữ riêng khỏi tổ chức chuẩn hóa; **không** gán đơn vị cấp bài cho tác giả; `apply_cross_source_policy` xử lý nhiều nguồn | `author_affiliation.py`, `affiliation_import.py` | Tên người dùng **không bao giờ đủ** cho VERIFIED; đơn vị trên bài ≠ đơn vị hiện tại của GV (HUONG_DAN §4.9) |
| 11 | Nguồn gốc (provenance) | SHA-256 tệp (`file_sha256`), SHA-256 từng dòng (`row_hash`), `publication_raw_sources` (dòng thô → công bố), snapshot hồ sơ (`snapshot_hash`), `evidence_fingerprint`, `observation_hash`; hợp đồng băm xác định `M1C-04` | `scopus_import_service.py`, models, `docs/freeze/M1.0…` | |
| 12 | Độ tin cậy / trạng thái xác minh | **Không có điểm số.** `confidence_score` luôn NULL; thứ tự mạnh–yếu bằng chứng là quy ước (ADR-004), không phải công thức; "trạng thái xác minh" = trạng thái ứng viên/danh tính + `link_status` affiliation + "ngữ cảnh mơ hồ" (số ứng viên khác, dùng chung) | `candidate_review_service.py`, ADR-004, `scoring.py` (giữ chỗ) | Trả lời yêu cầu "mức độ phù hợp" của đề cương: **chưa có** (D3) |

## 8.2. Tài sản kỹ thuật cần tạo (trả lời mục IX)

| Tài sản | Nội dung | Định dạng | Số liệu/ví dụ thật cần lấy |
|---|---|---|---|
| Pseudocode đúng mã | 12 mục trên, mỗi mục ≤ 25 dòng, trích tên hàm thật | Markdown | — |
| Sơ đồ thuật toán | Activity cho #5, #7, #9, #10 (trùng ACT-5, ACT-6, SEQ-5) | `.puml` | — |
| Ví dụ input/output thật | `Lương Thị Minh Huế` ↔ `Luong, Thi Minh-Hue (60319803200)` (16 công bố hỗ trợ); ca dùng chung `59253245500` (5 GV); 5 công bố ví dụ affiliation trong HUONG_DAN §4.9 | Markdown | Đọc **chỉ-đọc** (API/DB kiểm thử); trích có nguồn |
| Phân tích độ phức tạp | Sinh ứng viên: dựng chỉ mục băm cho mỗi luật (R=4) trên S bề mặt tên (tác giả + biến thể) rồi tra cứu O(1) cho mỗi GV ⇒ **O(R·(S+L))** thời gian, O(S) bộ nhớ (suy ra từ mã, cần kiểm khi viết) | Markdown | — |
| Quy tắc trùng/xung đột | Bảng: loại xung đột → nơi chặn (parser/service/DB) → mã lỗi | Markdown | — |
| Trường hợp chưa giải quyết | GV tên viết tắt/đảo; Scopus ID dùng chung; công bố chưa có trong CSV; affiliation UNRESOLVED; Khoa/Bộ môn trống | Markdown | Số lượng thật từ báo cáo trước |
| Điều kiện chấp nhận/từ chối | Ma trận ACCEPT/REJECT/PENDING/409 | Markdown | — |
| **Số liệu mô tả (không phải chất lượng)** | Phân bố bằng chứng theo luật, số GV không có ứng viên (≈372/410), số ứng viên có công bố (6/40), số ID dùng chung (1 ID/5 GV), phân bố VERIFIED/CORROBORATED/UNRESOLVED (5.502 resolution) | Bảng + biểu đồ | Truy vấn chỉ-đọc trên DB kiểm thử/teacher; **ghi rõ "mô tả, không phải precision/recall"** |
| Thí nghiệm kiểm thử có thể làm **không cần nhãn** | Tính xác định (chạy 2 lần cùng kết quả), idempotent (chạy lại 0 bản ghi mới), hiệu năng (`benchmark_m2_6a_10k.py` — **chưa có kết quả trong tài liệu**) | Bảng | Cần cụm DB bật |

**Không được viết:** "mô hình học máy", "độ chính xác X%", "F1", "AI nhận diện tác giả". **Được viết:** "quy tắc xác định, có thể giải thích, người duyệt quyết định".

---

# 9. TIẾN ĐỘ COMPLETION-3 VÀ VIỆC HOÃN

## 9.1. C3 là gì (xác minh lại từ nguồn)

- `C3-01…C3-15` trong `docs/freeze/M1.0-…` là số thứ tự ràng buộc schema — **không phải** Completion-3. Completion-3 = chuỗi nhánh `completion3/*` + `docs/progress/C3_A*.md` (chỉ trên nhánh) về **đánh giá độ phủ truy xuất ứng viên** (candidate-retrieval coverage), trên **cohort 50/410 GV** chọn trước bằng `SHA256_SEED_RANK_V1` (seed `C3-A3-ICTU-PRIMARY-2026-V1`), với **nhãn do con người xác nhận**.
- Chỉ đo **truy xuất** (recall của việc đưa đúng cặp vào danh sách ứng viên). **Không** đo xếp hạng, **không** đo precision hay F1; không tinh chỉnh thuật toán (`C3_A3_doc.md` §1, §11).
- Hiện trạng: `Official evaluation: NOT_RUN`, `Human-confirmed reference: NOT_AVAILABLE`, `A2 review package: NOT_GENERATED_OR_NOT_VERIFIED` (§9). **Không có kết quả nào.**
- Nhánh có trong repo (ĐÃ XÁC MINH bằng `git branch`): `completion3/a1-reference-evaluation-scaffold`, `…/a2-human-review-package`, `…/a3-matching-quality-evaluation`, `…/a3-commit1-candidate`, `ci/c3-a3-p1-source-dump-88e7a3c` (cả local và `origin`). **Không** nằm trong `main`.
- Công cụ trong worktree A3: `run_matching_quality_evaluation.py` (`prepare-cohort`, `evaluate`), `build_matching_review_package.py`, `evaluate_matching_reference.py`, `dump_c3_eval_source.py`.

## 9.2. Bảng trạng thái và phân loại

Phân loại: **NÊN LÀM TRƯỚC 14/10** · **CHỈ CHUẨN BỊ TRƯỚC 14/10** · **BỊ BLOCKED** · **LÀM SAU 14/10** · **KHÔNG CẦN THIẾT CHO ĐỒ ÁN HIỆN TẠI**.

| Hạng mục | Phạm vi | Trạng thái (theo nguồn) | Blocker / cần gì | Phân loại | Ghi chú |
|---|---|---|---|---|---|
| **A1** | Hợp đồng CSV nhãn + bộ đánh giá truy xuất | Có code + test trên nhánh (`e502e71`+2); chưa nghiệm thu | Rà soát độc lập, quyết định merge | **LÀM SAU 14/10** (quyết định merge); **CHỈ CHUẨN BỊ**: đọc để mô tả giao thức | Không đụng `main` |
| **A2** | Gói rà soát thủ công (`candidate_review.csv`, phiếu nhãn trống, manifest) | Có code trên nhánh; **gói thật chưa sinh** | Cần DB đánh giá | **LÀM SAU 14/10** | |
| **A3 Phase 1** | Cohort 50 khóa + cổng nguồn gốc fail-closed | Có code + cohort | Nhãn người | **CHỈ CHUẨN BỊ** (mô tả cohort/giao thức) | Cohort **đã chọn trước**, không đổi |
| **A3 Commit #1** | Cổng DB `scopus_c3_eval_v1` + fingerprint v1 | `[CANDIDATE — CHƯA NGHIỆM THU]` | Dựng DB thật | **LÀM SAU 14/10** | |
| **P0** | Khảo sát nguồn dump | Đã đóng | — | **KHÔNG CẦN** làm lại | |
| **P1** | Bộ điều phối dump (code + test mock) | Có (4 commit, nhánh CI trên origin); **CI Linux chưa ghi kết quả** | Ghi nhận CI; rà soát cuối | **LÀM SAU 14/10** | 396 passed/1 skipped (Task 17 chạy độc lập) |
| **Commit #2** | Ghim `EXPECTED_INPUT_FINGERPRINT_SHA256` (hiện `None` ⇒ chặn đánh giá) | Chưa làm | Cần DB đánh giá dựng xong | **LÀM SAU 14/10** (phụ thuộc P2/P3) | Ở đây "Commit #2" là việc của A3, không liên quan Task 18 |
| **P2** | Dựng + restore DB đánh giá | NO-GO | Chỉ sau CI P1 | **LÀM SAU 14/10** | |
| **P3** | Dump thật từ nguồn | **BLOCKED** | Role chỉ `SELECT`, thông tin DBA qua kênh riêng, môi trường SQLAlchemy | **BỊ BLOCKED** | Có thể **không áp dụng** nếu chọn đánh giá trên corpus demo (xem D5) |
| **Nhãn người 50/50** | Xác nhận độc lập từng dòng cohort | Chưa có | **Cần con người (GVHD/người có thẩm quyền)**; Claude **không được tạo nhãn** | **LÀM SAU 14/10** (nhưng **yêu cầu GVHD cung cấp/xác nhận ngay 14/10**) | Liên quan trực tiếp PI-3.4 |
| **Đánh giá chính thức (Phase 2)** | Chạy đánh giá có nhãn | `NOT_RUN` | Nhãn + Commit #2 | **LÀM SAU 14/10** | |
| **F3 / R1 (R2, R3)** | "Finding/Review item" của vòng rà soát | **Không tìm thấy định nghĩa** — Task 18 tìm lại trong `docs/`, `README.md`, thân commit **mọi nhánh**, `C3_A3_doc.md`, `evidence/`: chỉ xuất hiện trong chính tài liệu Task 17 | Báo cáo rà soát gốc do người dùng/ChatGPT cung cấp | **KHÔNG CẦN THIẾT** cho đồ án hiện tại cho tới khi có định nghĩa | Không coi là backlog |

## 9.3. C3 và yêu cầu của đề cương — điểm cần quyết định

- Đề cương (mục 5, PI-3.4) yêu cầu **"đánh giá kết quả gợi ý trên tập đối chiếu do GVHD xác nhận"** → **C3 không phải tùy chọn ở mức đồ án**: nếu không có đánh giá, cần giải trình hoặc chỉ ra là *chưa thực hiện được vì chưa có tập đối chiếu*.
- Quy trình C3 hiện tại **thiết kế cho một DB nguồn do DBA quản lý** (role `SELECT`, `scopus_c3_eval_v1`, ghim fingerprint). Với đồ án (dữ liệu demo cục bộ, teacher DB) có thể phù hợp hơn **"C3-lite"**: dùng chính cohort 50 + công cụ A1 trên **corpus demo**. Đây là **quyết định thiết kế**, ngoài phạm vi Task 18 (D5).
- **Trước 14/10 (đề xuất, không code):** (1) tài liệu giao thức đánh giá bằng tiếng Việt (định nghĩa chỉ số, hạn chế, **không** nêu precision/F1); (2) mẫu đề nghị GVHD xác nhận/cung cấp tập đối chiếu + định dạng CSV nhãn (lấy từ hợp đồng A1); (3) runbook "khi có nhãn thì chạy lệnh nào, kiểm gì"; (4) câu hỏi chốt với GVHD tại buổi demo. → `C3P-01`.
- **Không** làm trước 14/10: merge nhánh C3, chạy P2/P3, chạy `evaluate`, tạo nhãn, báo bất kỳ số liệu nào.

---

# 10. ĐÁNH GIÁ CHẤT LƯỢNG ĐỒ ÁN (góc nhìn phản biện)

## 10.1. Software Architect

**Điểm mạnh:** phân tầng rõ (endpoint → service → repository → model); các quy trình **xác định, idempotent, fail-closed** (nhập GV, chuẩn hóa, sinh ứng viên, nhập affiliation đều có thể chạy lại không tạo trùng); RBAC kiểm ở backend; truy vết đầy đủ (hash, provenance, audit); quyết định kiến trúc có ADR.
**Điểm yếu:**
1. **Mã giữ chỗ M0 còn sót gây hiểu lầm:** `matching/scoring.py` ("M0 HIGH-RISK STUB", ném `NotImplementedError`), `matching/engine.py`, `normalization/{doi,name,orcid,text,title}_normalizer.py` (stub), `GET /matching/ping` trả `matching-stub`, `DiffViewerStub` không dùng, README mục "Future/incomplete milestones" lỗi thời. Người đọc mã có thể kết luận "chưa làm thuật toán". → ghi chú trong hồ sơ; sửa nhỏ sau 14/10 (`FIX-01/02`).
2. Trang giao diện rất lớn, ít thành phần tái dùng (`Imports` ≈ 2,4k dòng) — khó bảo trì, khó thiết kế lại; AntD chỉ ở một trang.
3. Chạy nặng trong tiến trình API (không hàng đợi) — chấp nhận được cho quy mô đồ án; nên nêu rõ giới hạn.
4. **Chưa có bằng chứng CI Linux** cho các commit sau Completion-2; `main` chưa push.
5. Môi trường triển khai thật = localhost; `compose*.yaml` chưa kiểm chứng.

## 10.2. Database Designer

**Mạnh:** 99 CHECK (từ vựng, JSONB là object, khuôn dạng SHA-256/ORCID, chuyển trạng thái, nhất quán), 30 FK (3 CASCADE chỉ ở quan hệ phụ thuộc chặt), UNIQUE/partial unique chống trùng ở DB, FK ghép bảo vệ bất biến, kiểu `uuid`/`timestamptz`/`jsonb` hợp lý.
**Yếu / cần giải thích:** xem 4.5 (mapping_reviews chưa dùng; schema rộng hơn cài đặt; không có thực thể nguồn xuất bản; audit không được DB cưỡng chế; `lecturers.email` trùng được). **Thiếu chỉ mục?** Chưa thấy truy vấn chậm; chưa có số đo — không khẳng định. **Chưa có ERD/dictionary**.

## 10.3. Business Analyst

- Thiếu bảng FR/NFR, tiêu chí nghiệm thu và truy vết yêu cầu (PI-1.2) — phần lớn thuộc tính đã có trong hệ thống nhưng **chưa thành tài liệu**.
- **Luồng chưa hoàn chỉnh:** (a) sinh ứng viên/nạp nguồn ngoài là CLI (không có nút/tiến trình trên UI); (b) hoàn tác quyết định duyệt; (c) thống kê/xuất ngoài JSON; (d) so sánh trước/sau chuẩn hóa (UI); (e) màn quản lý liên kết theo giảng viên (API có, UI không).
- **UI có nút nhưng không chạy:** `/tasks` (giữ chỗ), biểu đồ Trang chủ (ghi "Đang phát triển") — đã gắn nhãn; không phát hiện nút "chết" khác (**cần QA tay**).
- Vai trò: đủ cho đề tài (3 vai trò). **Không có** vai trò/luồng "Operator" như sơ đồ cũ.

## 10.4. UI/UX Designer

- Đủ rõ để trình diễn (đã có kịch bản 14 phút + 17 câu hỏi dự kiến); nhãn trung thực về giới hạn.
- Cần: bộ **Figma** (đề cương), **ảnh độ phân giải cao**, bằng chứng mobile; thống nhất AntD vs Tailwind; rà trạng thái empty/error cho Tra cứu và Trang chủ. Bảng "Duyệt đối sánh" và "Nhập dữ liệu" phức tạp nhưng có bộ lọc/modal — chấp nhận được.

## 10.5. QA Engineer

- **Mạnh:** 797 test backend; E2E 3 vai trò; ma trận OpenAPI 57 thao tác (BROWSER_PASS/API_PASS); đối soát fingerprint teacher DB bất biến.
- **Thiếu:** không có test giao diện tự động; chưa có biên bản "mong đợi/thực tế" theo mẫu từng UC (PI-4.2); chưa đo hiệu năng; chưa có bằng chứng CI; chưa có bằng chứng khổ mobile. Các số "PASS" **THEO BÁO CÁO TRƯỚC**, Task 18 không chạy lại.

## 10.6. Bảo mật, trung thực học thuật, đạo văn

| Chủ đề | Kết quả kiểm tra | Hành động |
|---|---|---|
| RBAC | Đúng theo `require_role`; menu ẩn + backend 403 (đã kiểm Task 16–17) | Giữ |
| Audit | Có audit cho thao tác ghi chính; **chưa thấy audit đăng nhập**; append-only chỉ ở tầng ứng dụng | Nêu đúng trong báo cáo |
| Chống dò mật khẩu | **Không có giới hạn số lần thử/khóa tự động** (không tìm thấy rate-limit trong mã) | Ghi vào hạn chế; `FIX-05` (tùy chọn) |
| Cookie/Mật khẩu | `httponly`, `samesite=lax`, `secure` chỉ khi `prod`; Argon2id | Ghi: localhost nên `secure=false` |
| Bí mật trong Git | Chỉ có `.env.example`; **không phát hiện** mật khẩu thật trong `docs/`, `README.md`, scripts (quét mẫu `mật khẩu/password = …`) | Quét lại trước khi nộp; **không thể kiểm các báo cáo/chat ngoài repo** — nếu từng dán credential vào đó, nên đổi mật khẩu demo |
| PII | `data/lecturers/ictu_lecturers.json` chứa tên + email đơn vị của 410 GV (dữ liệu công khai theo README) nằm trong Git; ảnh bằng chứng chứa email tài khoản thử (ngoài Git) | Không đưa email vào báo cáo/slide; che trong ảnh |
| Dữ liệu thử trình bày như thật | Ảnh Task 16–17 chụp trên DB kiểm thử (có "Giảng viên Thử T16", "412"); teacher có 0 APPROVED | Mỗi hình ghi rõ nguồn DB; không gọi đây là kết quả duyệt thật |
| **Sử dụng công cụ AI** | **64/100 commit** có dòng `Co-Authored-By` của công cụ AI (Claude Sonnet 4.6 ×21, Claude Sonnet 5.5 ×24, Copilot ×9, Cursor ×10); các tài liệu kế hoạch/thiết kế sắp tạo cũng do AI hỗ trợ | **Yêu cầu của GVHD về "do sinh viên tự xây dựng" và "tính trung thực" ⇒ sinh viên cần (1) xác nhận quy định của Khoa/Trường về dùng AI, (2) khai báo trung thực mức độ hỗ trợ theo quy định đó, (3) hiểu và giải thích được từng thành phần.** Task 18 **không** đưa ra khuyến nghị né tránh phát hiện |
| Đạo văn | Không thể và **không được** tuyên bố "qua phần mềm kiểm tra"; không giả lập báo cáo kiểm tra | Mọi hình do hệ thống/sơ đồ tự tạo; trích nguồn mọi tài liệu ngoài; không chép nguyên văn từ ADR/freeze/tài liệu ngoài mà phải diễn đạt lại bằng hiểu biết |
| Tính nhất quán nhật ký | `DoAn.docx` ghi sơ đồ khác hệ thống và soạn trước thời điểm | Cập nhật theo D1 |

**Những chỗ phải tìm nguồn và trích dẫn khi viết (Chương 1):** Scopus (khái niệm EID, Author ID, ORCID), OpenAlex, Crossref, DSpace; FastAPI, React, PostgreSQL, SQLAlchemy, Alembic; Argon2 (RFC 9106); JWT (RFC 7519); UML/BPMN/ERD (chuẩn OMG/Chen/Crow's Foot); thuật ngữ entity resolution. **Không sao chép nguyên văn** từ tài liệu bên ngoài hoặc từ sách hướng dẫn.

## 10.7. Đóng góp kỹ thuật của sinh viên — có rõ không?

Hiện **chưa rõ** trong tài liệu. Cần một bản **"Đóng góp và phạm vi cá nhân"** (việc `HND-01`): sinh viên tự mô tả phần mình quyết định/thiết kế/kiểm thử (vd. quy tắc không tự duyệt, thiết kế 24 bảng, các ADR, kịch bản kiểm thử), phần dùng công cụ hỗ trợ và cách kiểm chứng. Đây là nội dung **chỉ sinh viên viết được**; Claude chỉ có thể chuẩn bị dàn ý.

## 10.8. Danh sách cải tiến theo mức

| Mức | Hạng mục | ID |
|---|---|---|
| **BẮT BUỘC** | Thay sơ đồ cũ bằng bản khớp thực tế (UC, BPMN, ERD) và thống nhất tên/phiên bản; ERD + data dictionary; ≥5 đặc tả UC; kiến trúc UML; sequence/activity cốt lõi (đăng nhập, nhập CSV/JSON, duyệt); bảng FR/NFR bản nháp; hỏi GVHD ngày 14/10: tập đối chiếu, khuôn mẫu báo cáo, tiêu chí nghiệm thu, định dạng trao đổi | `DB-01..03`, `USE-01..03`, `UML-01..04`, `REQ-01,02`, D9, D10 |
| **RẤT NÊN** | Tokens + 8 mockup nguồn + hướng dẫn vào Figma; ảnh chụp độ phân giải cao + manifest; hồ sơ thuật toán; tài liệu kiểm thử/dữ liệu kiểm thử/sao lưu-phục hồi; gói chuẩn bị C3 (không code); sơ đồ state + DFD; bản đối chiếu sơ đồ cũ ↔ thực | `UI-01,02`, `EVD-01,02`, `ALG-01,02`, `REQ-03,04`, `C3P-01`, `UML-05` |
| **CÓ THỂ LÀM** | Dàn ý slide/hình; benchmark 10k; sửa README + ghi chú mã giữ chỗ (`FIX-01/02`); giới hạn đăng nhập (`FIX-05`); đóng gói thư mục `docs/design` kèm manifest | `DEM-01`, `FIX-*`, `HND-01` |
| **KHÔNG CẦN TRƯỚC HẠN** | Viết văn bản báo cáo; chạy C3 (Commit #2, P2, P3, nhãn, Phase 2); push GitHub/CI; nút chạy matching; nạp OpenAlex/Crossref trên UI; trang Tác vụ; biểu đồ Trang chủ; so sánh trước/sau bản cài đặt thật (`FIX-03`); điểm số phù hợp (`FIX-04`) — **trừ khi người dùng quyết định khác** | — |

---

# 11. MASTER BACKLOG

> **Hai hệ ưu tiên khác nhau — đừng nhầm:** `P0–P3` trong tài liệu này là **mức ưu tiên mới của kế hoạch Task 18**, **không liên quan** tới P0–P3 của Completion-3.
> **Ba tầng khối lượng (Tier):** **T1 = tối thiểu khả thi**, **T2 = mở rộng nếu còn thời gian**, **T3 = đầy đủ/không hứa chắc**. Giờ = giờ làm việc Claude tương đương **đã gồm kiểm chứng với mã/DB**; không gồm thời gian người dùng đọc duyệt.
> Nhóm: **P0** tài sản thiết kế không thể thiếu · **P1** giao diện, minh chứng, thuật toán · **P2** phát triển/chuẩn bị bổ sung · **P3** làm sau khi hết Claude.

## 11.1. Bảng điều phối (ID · ưu tiên · phụ thuộc · thời gian)

`★` = nằm trên **đường găng**. "Sau 14/10?" = có thể do sinh viên làm tiếp (với ChatGPT/công cụ web) khi không còn Claude, nếu Claude đã bàn giao dữ kiện/nguồn.

| Thứ tự | ID | Tên | Nhóm | Tier | Giờ T1 / Đủ | Phụ thuộc | Cần Claude? | Sau 14/10? | Cần quyết định? |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **DB-01** ★ | Trích schema, kiểm ORM↔migration↔DB, data dictionary | P0 | T1 | 4 / 4 | D11 (kiểm render, không bắt buộc) | **Có** (tự động hóa từ schema) | Khó | — |
| 2 | **DB-02** ★ | ERD tổng thể + 6 ERD cụm (nguồn + SVG) | P0 | T1 | 4 / 4 | DB-01, D11 | **Có** | Khó | D1 (cách xử lý ERD cũ) |
| 3 | **DB-05** | Đối chiếu 3 ERD cũ ↔ DB thật (bảng chênh lệch) | P0 | T1 | 1 / 1 | DB-01 | Có | Được | **D1** |
| 4 | **REQ-01** ★ | Bảng truy vết yêu cầu chính thức (RTM) + cập nhật đề cương | P0 | T1 | 2 / 2 | **SV đọc lại PDF** (15′) | Có (dàn) | Được | D9, D10 |
| 5 | **USE-01** ★ | Inventory UC + ma trận Actor×UC + RBAC từ OpenAPI | P0 | T1 | 2 / 2 | — | Có | Khó | — |
| 6 | **USE-02** | 6 sơ đồ Use Case (T1: UCD-0, 1, 3) | P0 | T1 | 1,5 / 3 | USE-01, D1, D11 | Có | Được (chỉnh) | D1 |
| 7 | **USE-03** | Đặc tả UC (T1: 5 UC khớp đề cương; đủ: 8 + 1) | P0 | T1 | 3,5 / 5,5 | USE-01, DB-01 | Có (khung + dữ kiện) | **Được** (SV diễn đạt lại) | — |
| 8 | **UML-01** ★ | Kiến trúc phân tầng + triển khai localhost | P0 | T1 | 2,5 / 2,5 | D11 | Có | Được | — |
| 9 | **UML-02** ★ | BPMN as-implemented + bảng bước/người/vào–ra | P0 | T1 | 2,5 / 2,5 | USE-01, D1 | Có | Khó (BPMN) | D1 |
| 10 | **UML-03** | Sequence (T1: SEQ-3, 6, 7, 8; đủ: 8) | P0 | T1 | 2,5 / 4,75 | USE-01, DB-01 | Có | Được (chỉnh) | — |
| 11 | **UML-04** | Activity (T1: ACT-3, 6, 7; đủ: 7) | P0 | T1 | 1,5 / 3,3 | USE-01 | Có | Được | — |
| 12 | **ALG-01** | Hồ sơ thuật toán (T1: 5 mục cốt lõi #3,5,7,9,10; đủ: 12) | P1 | T1 | 2,5 / 5 | — | **Có** (đọc mã) | Khó | D3, D6 |
| 13 | **UI-01** | Tokens + UI inventory (20 màn × trạng thái × route × API) | P1 | T1 | 2 / 2,5 | — | Có | Khó (rút từ mã) | D2 |
| 14 | **C3P-01** | Gói chuẩn bị C3 (giao thức VI, thư đề nghị GVHD, runbook) — **không code** | P2 | T1 | 1,5 / 2 | D5 | Có (tài liệu) | Được | **D5** |
| 15 | **HND-01** | Đóng gói bàn giao: `docs/design/README`, manifest SHA-256, hướng dẫn tự chỉnh, đóng góp cá nhân (dàn ý) | P0 | T1 | 2 / 3 | các mục trước | Có | Một phần | — |
| 16 | **HND-02** | Bundle/zip sao lưu cuối | P0 | T1 | 0,5 / 0,5 | HND-01 | Có | Được | — |
| — | **Tổng T1** | | | | **35,5 giờ** | | | | |
| 17 | **EVD-02** ★ | Chụp lại ảnh độ phân giải cao (T2: 18 ảnh; đủ: 32) + manifest | P1 | T2 | 3 / 4,5 | **D12 (bật DB/app)** | Có (qua trình duyệt) | Khó | D12 |
| 18 | **UI-02** | Mockup nguồn HTML/SVG (T2: 6; đủ: 8) + hướng dẫn nhập Figma | P1 | T2 | 4,5 / 6 | UI-01, EVD-02 (để đối chiếu) | Có | Một phần (Figma do SV) | D2, D4 |
| 19 | **UML-05** | State ×4 + DFD + vòng đời dữ liệu | P0 | T2 | 2,7 / 2,7 | DB-01 | Có | Được | — |
| 20 | **DB-03** | Ràng buộc/chỉ mục/kiểu dữ liệu + "Vì sao" cho SV | P1 | T2 | 3 / 3 | DB-01 | Có (dữ kiện) | **Được** | — |
| 21 | **DB-04** | Ma trận bảng × UC | P1 | T2 | 1,5 / 1,5 | USE-01, DB-01 | Có | Được | — |
| 22 | **EVD-01** | Rà 29 ảnh cũ (PII, chất lượng) + INDEX bằng chứng | P1 | T2 | 1,5 / 1,5 | — | Có | Được | — |
| 23 | **ALG-02** | Số liệu **mô tả** (không nhãn) từ truy vấn chỉ-đọc | P1 | T2 | 1,5 / 1,5 | D12 | Có | Khó | — |
| 24 | **REQ-02** | FR/NFR + tiêu chí nghiệm thu (bản nháp để GVHD ký) | P0 | T2 | 2,5 / 2,5 | REQ-01, USE-01 | Có | **Được** | D10 |
| 25 | USE-02/03, UML-03/04 phần còn lại | (xem dòng 6, 7, 10, 11) | P0 | T2 | — | | | | |
| 26 | **REQ-03** | Tài liệu kiểm thử: kế hoạch, danh mục ca, danh mục bộ dữ liệu, mẫu biên bản | P1 | T3 | 3,5 | `BAO_CAO_KIEM_THU…` | Một phần | **Được** | — |
| 27 | **REQ-04** | Hướng dẫn cài đặt + **sao lưu/phục hồi** (kiểm phục hồi trên DB mới) | P1 | T3 | 3 | D12 | Có (nên kiểm) | Một phần | — |
| 28 | **DEM-01** | Dàn ý slide/danh sách hình theo chương | P1 | T3 | 1,5 | — | Không bắt buộc | **Được** | — |
| 29 | **FIX-01** | Sửa README (bảng milestone) | P2 | T3 | 0,5 | — | Có | Được | — |
| 30 | **FIX-02** | Ghi chú/dọn mã giữ chỗ M0 (scoring/engine/normalizer stub, `DiffViewerStub`) | P2 | T3 | 1,5 | chạy lại 797 test | Có | Được (rủi ro) | — |
| — | *Tùy chọn (chỉ khi D quyết)* | **FIX-03** viewer so sánh trước/sau (≈9 h) · **FIX-04** nhãn mức phù hợp định tính (≈7 h) · **FIX-05** giới hạn đăng nhập sai (≈3 h) | P2 | — | | | Có | | D3, D4 |
| — | *Sau 14/10* | Viết văn bản báo cáo · chỉnh format · dựng Figma cuối · slide · C3 thực thi · push/CI · bảo vệ | **P3** | — | | | Không | | |
| — | **Tổng đầy đủ** (không gồm FIX-03/04/05) | | | | **≈ 80,8 giờ** | | | | |

**Cách đọc:** **T1 ≈ 35,5 giờ** (khả thi trong ≈ 4,5 ngày nếu tiến hành liền). Lịch ngày ở mục 12 bố trí **T1 + 7,5 giờ T2 (EVD-02, UI-02) ≈ 43 giờ**. Phần còn lại — **≈ 28 giờ T2** (phần mở rộng của USE/UML/ALG, UML-05, DB-03/04, EVD-01, ALG-02, REQ-02) và **≈ 10 giờ T3** (REQ-03/04, DEM-01, FIX-01/02) — **không nằm trong lịch**: chỉ làm nếu còn giờ trống, hoặc do sinh viên làm sau 14/10 nhờ dữ kiện Claude đã trích. **Không hứa tất cả kịp.**

---

## 11.2. Chi tiết từng công việc

| ID | Mục tiêu · Nguồn yêu cầu | Hiện trạng | Việc cần làm → File ra (định dạng) | Độ khó · Rủi ro | Tiêu chí PASS |
|---|---|---|---|---|---|
| **DB-01** | ERD/từ điển thật · PI-2.1, PI-3.1 | Có DB + ORM + migration; không có dictionary; chưa kiểm cột/ràng buộc ORM↔DB | Script (`docs/design/tools/`) đọc `pg_restore --schema-only` (hoặc DB kiểm thử chỉ-đọc) → sinh `DATA_DICTIONARY.md/.csv` (24 bảng), `KEYS_RELATIONS.md` (24 PK/30 FK/16+7 UNIQUE), `CONSTRAINTS_CATALOG.md` (99 CHECK nhóm hóa), `ORM_MIGRATION_DB_PARITY.md` (so tên bảng, cột, kiểu, null, FK, UNIQUE, CHECK) | Trung bình · Dump có thể lệch bản mới nhất → ghi `alembic_version` | 24/24 bảng; 30/30 FK; 99/99 CHECK; báo cáo parity nêu **mọi** chênh lệch (kể cả 0) |
| **DB-02** | ERD đúng · PI-2.1 | Không có nguồn | Sinh `ERD-0_tong_the`, `ERD-A…F` dạng `.dbml` + `.puml` (+Mermaid) từ schema; render SVG/PNG; **script kiểm FK** | Trung bình · Hình quá rối nếu gộp | 7 sơ đồ; **số FK trong hình = 30 = DB** (script PASS); mỗi bảng ≥1 sơ đồ cụm; bảng chưa dùng (`mapping_reviews`) có chú thích; `.dbml` nhập được dbdiagram.io |
| **DB-03** | Giải thích thiết kế · mục IV | Ý tưởng nằm rải rác ở freeze/ADR | `CONSTRAINTS_RATIONALE.md`, `DATA_TYPES_INDEXES_RATIONALE.md`, `VI_SAO_THIET_KE.md` (9 câu hỏi 4.6 + dẫn nguồn ADR) | Thấp · Diễn đạt phải để SV tự viết lại (R1) | Mỗi câu hỏi có dẫn ADR/CHECK/FK cụ thể có thật; không có tuyên bố vượt thực tế (xem 4.5) |
| **DB-04** | Bảng × UC · mục IV(10) | — | `TABLE_UC_MATRIX.md` (24 × 26); `DATA_LIFECYCLE.puml` | Thấp | Mỗi bảng có ít nhất 1 UC hoặc ghi "chưa dùng" |
| **DB-05** | Trung thực/nhất quán sơ đồ cũ · R1 mục 1.5 | 3 ERD ảnh lệch | `DOI_CHIEU_SO_DO_CU.md` (bảng chênh lệch từng bảng/cột + khuyến nghị thay/ghi chú "thiết kế ban đầu") — nền là **Phụ lục A** | Thấp · Nhạy cảm (nhật ký đã nộp) | Mọi bảng/cột cũ được gán: tương ứng / bị thay / không còn |
| **REQ-01** | RTM · mục 2 + PI-1.2 | Bảng ở mục 2 là bản đầu | Chốt bản đọc lại PDF (SV xác nhận), `00_BANG_TRUY_VET_YEU_CAU.md/.csv`: Yêu cầu → UC → bảng → màn hình → API → test → bằng chứng | Thấp · PDF mất dấu | 32/32 yêu cầu có hàng; mỗi ô "Đã triển khai" có đường dẫn mã/tài liệu |
| **REQ-02** | FR/NFR · PI-1.2 | Chưa có | `01_FR_NFR.md`: FR (từ 26 UC), NFR (phân quyền, an toàn dữ liệu, truy vết, sao lưu, khả năng sử dụng, hiệu năng — **chỉ số nào chưa đo thì ghi "chưa đo"**), tiêu chí nghiệm thu **đề xuất** | Thấp · "Thống nhất với GVHD" cần người | Mỗi FR trỏ UC + test; mỗi NFR trỏ bằng chứng hoặc "chưa kiểm chứng"; chừa ô GVHD xác nhận |
| **REQ-03** | Kiểm thử · PI-3.3, PI-4.2 | `BAO_CAO_KIEM_THU…` đủ nhưng chưa theo mẫu từng UC | `TEST_PLAN.md`, `TEST_DATA_CATALOG.md` (loại dữ liệu: hợp lệ/thiếu trường/sai định dạng/trùng/tên giống/lỗi nhập → tệp thật), `TEST_CASES.md` (mong đợi/thực tế/bằng chứng, trỏ tới test pytest và ảnh) | Trung bình | Mọi ca trỏ tới 1 test hoặc 1 ảnh có thật; dữ liệu giả lập được đánh dấu |
| **REQ-04** | Vận hành · PI-3.1, PI-4.1 | `pg_dump` rời rạc | `INSTALL.md`, `BACKUP_RESTORE.md` (khởi tạo bằng Alembic, sao lưu `pg_dump -Fc`, phục hồi `pg_restore` **kiểm trên DB mới đặt tên `*_restore_check`**, kiểm bất biến) | Trung bình · Cần cụm DB bật; **không ghi vào teacher** | Quy trình chạy thật trên DB mới và đối chiếu số dòng bằng nhau |
| **USE-01** | UC thật · PI-1.3 | Chỉ ảnh cũ | `UC_INVENTORY.md` (26 UC + bằng chứng), `ACTOR_UC_MATRIX.md` (sinh từ OpenAPI + `require_role` + `App.tsx`), `RBAC_API_MATRIX.csv` (57 thao tác) | Thấp | 57/57 thao tác OpenAPI được gán vai trò; không UC nào không có route/script |
| **USE-02** | Sơ đồ UC · PI-1.3 | Ảnh cũ sai | `UCD-0…5.puml` + SVG/PNG | Trung bình · include/extend đúng nghĩa | Mọi oval ↔ UC trong inventory; mọi actor đúng 3.1; «include»/«extend» theo 3.4; render được |
| **USE-03** | Đặc tả UC · PI-1.3 | Chưa có | `UCS-01…` theo mẫu (3.6), mỗi tệp có điều kiện trước/sau, luồng chính/thay thế/ngoại lệ, bảng đọc/ghi, test/bằng chứng | Trung bình · Phải chính xác với service | Mỗi luồng ngoại lệ ứng với 1 lớp lỗi/mã HTTP **có thật** (trích hàm); ≥5 đặc tả |
| **UML-01** | Kiến trúc · PI-2.2 | Chưa có | `ARC-1_kien_truc.puml`, `ARC-2_trien_khai_localhost.puml` + SVG | Thấp · Rủi ro nhất: vẽ thừa thành phần | Chỉ gồm thành phần ở 5.2; không Redis/Kafka/Celery; không in bí mật |
| **UML-02** | BPMN · PI-1.1 | Ảnh cũ sai | `BPMN-1.bpmn` (bpmn.io) + `.puml` dự phòng + `BPMN-1_bang_buoc.md` (bước, người thực hiện, vào, ra, bảng/route) | Cao (chuẩn BPMN + không có công cụ kiểm tự động) · Rủi ro lỗi XML | Mở được ở bpmn.io (SV kiểm) hoặc render PlantUML; mọi bước ↔ 1 UC/route/script |
| **UML-03** | Sequence · PI-2.2 | Chưa có | `SEQ-1…8.puml` + SVG | Trung bình | Mọi thông điệp ↔ route/hàm có thật (bảng đối chiếu kèm theo) |
| **UML-04** | Activity · PI-2.2 | Chưa có | `ACT-1…7.puml` + SVG | Thấp | Mọi nhánh lỗi ↔ lớp lỗi/mã HTTP thật |
| **UML-05** | State + DFD | Chưa có | `STM-1…4.puml`, `DFD-1.puml` | Thấp | Trạng thái = vocab CHECK trong DB; đánh dấu phần chưa có API |
| **ALG-01** | Hồ sơ thuật toán · G2, P6–P8, PI-3.4 | Rải rác ở docstring/HUONG_DAN | `ALG_DOSSIER.md` (12 mục: pseudocode đúng tên hàm, ví dụ thật, độ phức tạp, giới hạn) | Trung bình · Nguy cơ mô tả quá mức | Mọi pseudocode đối chiếu được tới hàm thật; **không** có từ "học máy", "độ chính xác %"; nêu rõ M0 stub không dùng |
| **ALG-02** | Số liệu mô tả | Có vài số trong HUONG_DAN | `ALG_RESULTS_MO_TA.md` — bảng đếm từ truy vấn chỉ-đọc, kèm câu lệnh | Thấp · Cần DB bật | Mỗi số có câu truy vấn và ngày; gắn nhãn "mô tả, không phải đánh giá chất lượng" |
| **UI-01** | Design system + inventory · PI-2.3 | Không có | `tokens.json`, `UI_INVENTORY.md` (20 màn, route, API, vai trò, trạng thái loading/empty/error/modal, lỗi nhất quán AntD vs Tailwind) | Thấp | 15/15 route + 4 modal + S20 được liệt kê; màu/phông khớp mã (`#3A5FC3`, Saira…) |
| **UI-02** | Mockup nguồn · PI-2.3 | Không có | `mockups/*.html` hoặc `*.svg` (6–8 màn) + `HUONG_DAN_NHAP_FIGMA.md` + `MANIFEST.md` | Cao (độ trung thực hình ảnh) · Nhập Figma phụ thuộc plugin | Mỗi mockup đặt cạnh ảnh chụp thật để đối chiếu; S20 gắn nhãn "Đề xuất — chưa triển khai"; tiếng Việt có dấu |
| **EVD-01** | Bằng chứng hiện có | 29 ảnh nhỏ | `docs/design/evidence/INDEX.md` (không PII): ảnh → chức năng → DB nguồn → chất lượng → dùng/không; danh sách ảnh có PII cần che | Thấp | 29/29 ảnh có hàng; mọi ảnh có email/UUID được đánh dấu |
| **EVD-02** | Ảnh cho báo cáo · PI-3.2, PI-4.2 | 0/32 đủ chất lượng | Chụp 1440×900 PNG (+3 mobile) trên DB kiểm thử, theo 7.3; manifest JSON (mã, chức năng, DB, thời điểm, SHA-256, chú thích) **ngoài Git**; INDEX trong Git | Trung bình · Cần môi trường chạy; tránh PII/mật khẩu | Mỗi ảnh đọc rõ ở 100%; không có mật khẩu/JWT/email thật; chú thích nêu "DB kiểm thử"; SHA-256 khớp manifest |
| **C3P-01** | Chuẩn bị tập đối chiếu · PI-3.4, G4 | C3 chưa chạy | `docs/design/c3/GIAO_THUC_DANH_GIA.md`, `THU_DE_NGHI_GVHD.md`, `RUNBOOK_KHI_CO_NHAN.md` (chỉ mô tả lệnh từ nhánh, **không chạy**) | Thấp · Không code, không nhãn | Không có số liệu chất lượng nào; ghi rõ phạm vi "độ phủ truy xuất, n=50, không precision" |
| **DEM-01** | Slide/hình | `KICH_BAN_TRINH_DIEN` đã có | `DANH_SACH_HINH_THEO_CHUONG.md` (hình → chương → nguồn) | Thấp | Mỗi hình có tệp nguồn |
| **HND-01** | Bàn giao · R1, mục 13 | — | `docs/design/README.md` (mục lục + cách chỉnh/render lại), `MANIFEST.json` (phiên bản, SHA-256, nguồn mã/DB), `DONG_GOP_CA_NHAN_DAN_Y.md` (dàn ý SV tự điền), script kiểm nhất quán (FK/route/OpenAPI) | Thấp | Chạy script kiểm: 0 lỗi; mọi tệp trong manifest tồn tại |
| **HND-02** | Sao lưu | — | `git bundle` + zip `docs/design` ra `_quan_ly_do_an\backups\task2x\` + SHA256SUMS | Thấp | Bundle verify OK |
| **FIX-01** | Hết lỗi thời | README ghi M2.7/2.8/3/4 là chưa làm | Cập nhật bảng milestone | Thấp | README khớp `TIEN_DO_V4…` |
| **FIX-02** | Tránh hiểu lầm | Stub M0 còn trong mã | Chỉ thêm chú thích/di chuyển, **không đổi hành vi**; chạy lại test | Trung bình (đụng mã) | 797 test vẫn PASS; không đổi API |

---

# 12. KẾ HOẠCH TỪNG NGÀY TRƯỚC 14/10

## 12.1. Giả định

- Hôm nay **Thứ Sáu 09/10** (tuần 2 của 10 tuần); Claude dùng được đến hết **14/10 (Thứ Tư)** — **14/10 là ngày trình diễn** nên **không lên kế hoạch việc cần Claude vào ngày này** (chỉ dự phòng).
- Mỗi ngày làm việc 10–12 giờ tương đương; **người dùng phải duyệt nhanh** (≤30′/Task) để không dừng đường găng.
- Có thể song song: nhóm **DB (Task 19)** ∥ **UC (Task 20)** ∥ **UI-01**; UML-03/04 có thể chia cho sub-agent (mỗi sub-agent khởi động nguội nên chỉ dùng khi thật sự tiết kiệm).
- **Việc phụ thuộc môi trường chạy (cụm DB bật):** `EVD-02`, `ALG-02`, `REQ-04` (kiểm phục hồi). Các việc còn lại **không cần bật DB**.

## 12.2. Chặng đường tới hạn

`D1 + D11` → `DB-01` → `DB-02` → `DB-05` ∥ `USE-01` → `USE-02/03` → `UML-02/03/04` → `HND-01`. Nếu **D11 (công cụ render)** không được duyệt, mọi sơ đồ chuyển sang trạng thái **"chưa render-kiểm"** (rủi ro cú pháp) — phải quyết định **ngay tối nay**.

## 12.3. Lịch

| Ngày | Task | Việc (ID) | Giờ ước lượng | Song song? | Điều kiện / chốt cuối ngày |
|---|---|---|---|---|---|
| **Thứ Sáu 09/10 (tối)** | *Người dùng/ChatGPT* | Duyệt Task 18; **chốt D1, D2, D11, D12**; đọc lại PDF (mục 5, 7a, 7b) | 1 | — | Không chốt D11 ⇒ ghi rủi ro |
| | **Task 19** (bắt đầu) | `DB-01` | 4 | — | Bản dump task17 làm nguồn; ghi `alembic_version` |
| **Thứ Bảy 10/10** | **Task 19** (xong) | `DB-02`, `DB-05` | 5 | ∥ Task 20 | ERD: 7/7 render; FK 30/30 |
| | **Task 20** | `REQ-01` (2) → `USE-01` (2) → `USE-02` T1 (1,5) | 5,5 | ∥ | Chốt tên actor/UC (khoá UC-ID) |
| | | Dự phòng/duyệt | — | | **Cuối ngày: DB + UC sơ bộ ⇒ cột mốc 1** |
| **Chủ Nhật 11/10** | **Task 20** (xong) | `USE-03` T1 (5 UC) | 3,5 | | |
| | **Task 21** | `UML-01` (2,5), `UML-02` (2,5), `UML-03` T1 (2,5) | 7,5 | ∥ (sub-agent cho SEQ) | **Cuối ngày: toàn bộ T1 "thiết kế" ⇒ cột mốc 2** |
| **Thứ Hai 12/10** | **Task 22** | `UML-04` T1 (1,5) | 1,5 | | |
| | **Task 23** | `ALG-01` T1 (2,5), `C3P-01` (1,5) | 4 | ∥ | Nhờ SV chuẩn bị câu hỏi cho GVHD (D9/D10) |
| | **Task 24** | `UI-01` (2) | 2 | ∥ | tokens + inventory |
| | **Task 25** (nếu D12 duyệt) | `EVD-02` (T2: 18 ảnh, 3) | 3 | | Cụm DB + app bật; **DB kiểm thử** |
| **Thứ Ba 13/10** | **Task 24/25** | `UI-02` T2 (4,5) *hoặc* `UML-05`/`DB-03` (ưu tiên theo quyết định cuối ngày 12/10) | 4,5 | | Chọn **một** nhánh vì không đủ giờ cho cả hai |
| | **Task 27** | `HND-01` (2), `HND-02` (0,5) — **luôn làm cuối** | 2,5 | | Bundle verify OK; **cột mốc 3 = chốt tài sản, hết yêu cầu việc mới cần Claude** |
| **Thứ Tư 14/10** | — | **Trình diễn.** Chỉ dự phòng sự cố; hỏi GVHD về tập đối chiếu, khuôn mẫu, tiêu chí nghiệm thu, định dạng trao đổi | — | | Mang theo bản in INDEX hình + kịch bản |

**Tổng T1 ≈ 35,5 giờ trong ≈ 4,5 ngày** (≈ 8 giờ/ngày thực tế còn dư để duyệt/sửa). Phần T2/T3 thực hiện **theo thứ tự rủi ro "hết Claude"**: ưu tiên việc **phụ thuộc mã/môi trường** (EVD-02, UI-02, ALG-02, UML-05) trước việc **có thể làm bằng ChatGPT từ dữ kiện đã trích** (REQ-02/03/04, DEM-01, DB-03 diễn giải).

## 12.4. Việc cần chốt trước khi hết quyền Claude (checklist)

1. ☐ Toàn bộ nguồn sơ đồ (`.puml/.dbml/.bpmn`) + hướng dẫn render lại **ở trong repo** (`docs/design/`) và **bundle sao lưu** ở `_quan_ly_do_an\backups\`.
2. ☐ Script kiểm nhất quán chạy PASS (FK 30/30, 57 route, mọi UC ↔ route).
3. ☐ `MANIFEST.json` + hướng dẫn "cách tự chỉnh khi không còn Claude" (mục 13.3).
4. ☐ Dữ kiện mô tả thuật toán đủ để SV tự viết Chương 3.
5. ☐ Danh sách ảnh cần chụp/đã chụp, kèm cách chụp lại.
6. ☐ Câu trả lời của GVHD cho 4 câu hỏi (14/10) được ghi lại.
7. ☐ Quyết định D1…D12 ghi vào `docs/design/DECISIONS.md`.

---

# 13. TÀI SẢN BÀN GIAO BẮT BUỘC

Mục tiêu: sau 14/10, sinh viên **viết được báo cáo mà không cần gọi Claude lại**. Mọi tài sản nằm trong `docs/design/` của repository (nguồn + bản xuất), có manifest và hướng dẫn tự chỉnh. Ảnh chụp và bản có PII nằm **ngoài Git**.

## 13.1. Cây thư mục đề xuất và mức bắt buộc

`[T1]` = nằm trong tối thiểu khả thi · `[T2]` = mở rộng · `[T3]` = có thể để sau 14/10.

```
docs/design/
├── README.md                          [T1] mục lục, cách mở/chỉnh/render lại, phiên bản
├── MANIFEST.json                      [T1] tệp · phiên bản · SHA-256 · nguồn mã/DB (alembic head, commit)
├── DECISIONS.md                       [T1] D1…D12 đã chốt
├── requirements/
│   ├── 00_BANG_TRUY_VET_YEU_CAU.md/.csv   [T1]
│   └── 01_FR_NFR.md                       [T2]
├── usecase/
│   ├── UC_INVENTORY.md, ACTOR_UC_MATRIX.md, RBAC_API_MATRIX.csv   [T1]
│   ├── diagrams/UCD-0…5.puml + .svg/.png                          [T1: UCD-0,1,3]
│   └── specs/UCS-01…09.md                                         [T1: 5 đặc tả]
├── database/
│   ├── DATA_DICTIONARY.md/.csv, KEYS_RELATIONS.md, CONSTRAINTS_CATALOG.md, ORM_MIGRATION_DB_PARITY.md  [T1]
│   ├── erd/ERD-0…6.dbml + .puml + .svg/.png                       [T1]
│   ├── DOI_CHIEU_SO_DO_CU.md                                      [T1]
│   ├── CONSTRAINTS_RATIONALE.md, VI_SAO_THIET_KE.md, TABLE_UC_MATRIX.md, DATA_LIFECYCLE.puml  [T2]
│   └── tools/ (script sinh/kiểm: schema → dictionary, ERD, kiểm FK)   [T1]
├── architecture/ ARC-1.puml, ARC-2.puml + .svg                    [T1]
├── process/ BPMN-1.bpmn, BPMN-1.puml, BPMN-1_bang_buoc.md, DFD-1.puml   [T1: BPMN; DFD T2]
├── sequence/ SEQ-1…8.puml + .svg                                  [T1: SEQ-3,6,7,8]
├── activity/ ACT-1…7.puml + .svg                                  [T1: ACT-3,6,7]
├── state/ STM-1…4.puml + .svg                                     [T2]
├── algorithms/ ALG_DOSSIER.md [T1: 5 mục], ALG_RESULTS_MO_TA.md   [T2]
├── ui/ tokens.json, UI_INVENTORY.md [T1]; mockups/, HUONG_DAN_NHAP_FIGMA.md [T2]
├── evidence/ INDEX.md (không PII)                                 [T2]
├── testing/ TEST_PLAN.md, TEST_DATA_CATALOG.md, TEST_CASES.md     [T3]
├── operations/ INSTALL.md, BACKUP_RESTORE.md                      [T3]
└── c3/ GIAO_THUC_DANH_GIA.md, THU_DE_NGHI_GVHD.md, RUNBOOK_KHI_CO_NHAN.md  [T1]
```

Ngoài Git: `_quan_ly_do_an\evidence\task2x\report_shots\*.png` + `manifest.json`; `_quan_ly_do_an\backups\task2x\` (bundle + zip + SHA256SUMS); `_quan_ly_do_an\tools\plantuml\` (jar, nếu D11 duyệt).

## 13.2. Bản đồ "tài sản → chương báo cáo" (cấu trúc 4 chương của đề cương)

| Chương | Tài sản dùng | Phần SV phải tự viết |
|---|---|---|
| **1. Cơ sở lý thuyết (công nghệ chính)** | ARC-1 (ngăn xếp công nghệ), ADR 001–004 (lý do chọn), bảng công nghệ thật ở 5.2 | Giới thiệu khái niệm (Scopus, EID, Author ID, ORCID, entity resolution…) **có trích nguồn tự tìm** |
| **2. Khảo sát và phân tích** | RTM + FR/NFR, BPMN-1 + bảng bước, UCD-0…5, đặc tả UC, ma trận Actor×UC, phân tích nguồn dữ liệu (CSV, JSON, Craw) | Diễn giải khảo sát, nhu cầu ICTU, phạm vi |
| **3. Thiết kế** | ERD ×7 + dictionary + ràng buộc, ARC-1/2, SEQ/ACT/STM/DFD, hồ sơ thuật toán, mockup/Figma | Giải thích lựa chọn thiết kế bằng lời mình ("Vì sao…") |
| **4. Triển khai** | Ảnh chụp E01–E32, test plan/cases, báo cáo kiểm thử, hướng dẫn cài đặt/sao lưu/phục hồi, kết quả mô tả, giới hạn và việc chưa làm, C3 (hiện trạng trung thực) | Quá trình cài đặt, kết quả, đánh giá, hạn chế |

## 13.3. Cách tự chỉnh sửa khi không còn Claude (đưa vào `docs/design/README.md`)

| Loại | Cách xem/chỉnh | Xuất ảnh |
|---|---|---|
| `.puml` (UML) | Dán vào trình soạn PlantUML (web hoặc extension VS Code "PlantUML" + `plantuml.jar`) | PNG/SVG |
| `.dbml` (ERD) | Dán vào dbdiagram.io; có thể chỉnh vị trí/màu | PNG/PDF |
| `.mmd` (nếu dùng Mermaid) | mermaid.live hoặc xem trực tiếp trên GitHub/VS Code | SVG/PNG |
| `.bpmn` | Mở ở demo.bpmn.io (sửa trực tiếp) | SVG/PNG |
| `.svg`/`.html` mockup | Mở bằng trình duyệt; chỉnh bằng Inkscape/VS Code; nhập vào Figma theo hướng dẫn | — |
| Script kiểm FK/route | `python docs/design/tools/<script>.py` (nêu rõ phụ thuộc: `pg_restore`, Python) | — |

Mọi sơ đồ phải kèm **ghi chú nguồn**: tên tệp mã/bảng/route mà sơ đồ dựa vào, `alembic_version` và commit tại thời điểm vẽ, để sinh viên **biết khi nào cần cập nhật** và **kiểm tra lại được**.

## 13.4. Quy tắc tạo tài sản (mục XIII của yêu cầu) và cách thực thi

| Quy tắc | Thực thi |
|---|---|
| 1–2. Có nguồn chỉnh sửa + bản xuất | `.puml/.dbml/.bpmn/.svg`/`.html` + `.svg/.png` |
| 3. Tên tiếng Việt rõ ràng | Tên tệp có mã ID + mô tả (vd. `ERD-C_ban_ghi_tho_scopus`) |
| 4. Phiên bản/manifest | `MANIFEST.json` (SHA-256, phiên bản, nguồn) |
| 5. Chỉ dẫn nguồn dữ liệu/logic | Ghi chú đầu mỗi tệp |
| 6. Không đổi schema/DB để vẽ | Chỉ đọc dump/DB; không migration |
| 7. Không vẽ quan hệ không có | **Script kiểm FK** (30/30) và kiểm route (57/57) |
| 8. Không ảnh giả | Ảnh chụp từ ứng dụng thật, manifest ghi DB + thời điểm |
| 9. Không sao chép giao diện dự án khác | Chỉ dựng lại từ `frontend/src` của chính dự án |
| 10. Không bí mật trong tài liệu | Quét mẫu các từ khóa `password`, `token`, `secret`, `.pw` trước khi commit |
| 11. Không tự nhận là Figma | Chỉ gọi "mockup nguồn (HTML/SVG)" cho tới khi SV có tệp Figma thật |
| 12. Quy trình tiếp tục chỉnh | Mục 13.3 |

---

# 14. QUYẾT ĐỊNH CẦN NGƯỜI DÙNG / CHATGPT CHỐT

Chỉ liệt kê quyết định thật sự ảnh hưởng đến công việc. **D1, D2, D11, D12 nên chốt trước tối nay** vì chặn đường găng.

| ID | Quyết định | Phương án A | Phương án B | Đề xuất |
|---|---|---|---|---|
| **D1** | Xử lý 5 sơ đồ cũ trong `DoAn.docx` (lệch hệ thống) | **A.** Thay hoàn toàn bằng bản khớp thực tế; giữ bản cũ chỉ như "thiết kế ban đầu/ý tưởng" ở phụ lục có chú thích **hoặc** bỏ — *ưu*: trung thực, nhất quán; *nhược*: phải cập nhật nhật ký đã nộp | **B.** Giữ nguyên ảnh cũ, chỉ thêm bản mới — *ưu*: ít sửa; *nhược*: hai bản mâu thuẫn, dễ bị hỏi vặn | **A**, đồng thời báo GVHD rằng sơ đồ cũ là thiết kế khái niệm ban đầu |
| **D2** | Cách có Figma (đề cương bắt buộc) | **A.** Claude dựng tokens + mockup nguồn HTML/SVG; SV nhập vào Figma (plugin) rồi chỉnh | **B.** SV dựng Figma tay từ tokens + ảnh độ phân giải cao; **C.** kết nối Figma connector nếu có | **A**, B là dự phòng; C chỉ nếu SV tự có connector hoạt động |
| **D3** | "Mức độ phù hợp" (PI-3.4) | **A.** Giữ như hiện tại; mô tả đúng: căn cứ **định tính** (luật + bằng chứng công bố + ngữ cảnh mơ hồ), **chưa có điểm số** | **B.** Thêm nhãn mức định tính hiển thị (suy từ loại bằng chứng, không đổi DB, ≈7 giờ code + test) | **A** trước 14/10; B là đề xuất sau (rủi ro đụng mã đã đóng băng) |
| **D4** | Màn "so sánh trước/sau chuẩn hóa" | **A.** Chỉ **thiết kế mockup**, gắn nhãn "đề xuất — chưa triển khai" | **B.** Cài viewer chỉ-đọc (≈9 giờ) | **A** (PI-2.3 yêu cầu *thiết kế*; B không nằm trong 5 UC bắt buộc) |
| **D5** | C3 / tập đối chiếu GVHD | **A.** Trước 14/10 chỉ chuẩn bị giao thức + thư đề nghị + runbook; hỏi GVHD ngày 14/10 | **B.** "C3-lite": dùng cohort 50 + công cụ A1 trên corpus demo sau khi có nhãn (cần Claude/ người code) | **A**; quyết B **sau** khi GVHD trả lời có/không có tập đối chiếu. **Không** tạo nhãn, **không** báo số liệu |
| **D6** | DOI/nguồn xuất bản (G2, PI-2.1) | **A.** Không đổi lưu trữ; giải trình mức chuẩn hóa thật + hạn chế | **B.** Chuẩn hóa DOI lưu trữ + bảng nguồn xuất bản (cần migration, tái chuẩn hóa) | **A** (B đụng schema đã đóng băng, ngoài thời hạn) |
| **D7** | Hoàn tác quyết định duyệt (P7) | **A.** Giải trình: chỉ hoàn tác ở cấp đợt nhập; REOPEN/REVOKE chỉ là thiết kế dự phòng | **B.** Cài REOPEN/REVOKE (API+UI+test) | **A** |
| **D8** | Thống kê và xuất (P5) | **A.** Giữ JSON + dashboard hiện có; thiết kế màn thống kê mở rộng ở Figma | **B.** Cài thêm CSV/Excel + biểu đồ | **A** |
| **D9** | Khuôn mẫu báo cáo, quy định trích dẫn, **quy định về dùng công cụ AI/chống đạo văn của Khoa** | **A.** SV xin tài liệu từ Khoa/GVHD (người dùng làm) | — | **A** — chưa có nguồn chính thức trong dự án |
| **D10** | Biên bản với GVHD: tiêu chí nghiệm thu (PI-1.2), định dạng trao đổi dữ liệu (P10), tập đối chiếu (PI-3.4) | **A.** Mang bản nháp FR/NFR + định dạng JSON hiện có đến buổi 14/10, xin xác nhận bằng văn bản/email | — | **A** |
| **D11** | Công cụ render để **kiểm chứng sơ đồ** | **A.** Cho phép tải `plantuml.jar` (kiểm SHA-256, đặt ngoài Git) — dùng Java sẵn có | **B.** Cho phép cài `@mermaid-js/mermaid-cli` (≈150 MB Chromium) **hoặc** không tải gì (sơ đồ ghi "chưa render-kiểm", SV tự dán vào trình xem web) | **A** |
| **D12** | Môi trường chạy cho `EVD-02`, `ALG-02`, `REQ-04` | **A.** Cho phép Claude khởi động cụm PostgreSQL demo (55432), backend/frontend trỏ **DB kiểm thử** (bản sao teacher), **không ghi vào teacher** | **B.** SV tự bật bằng BAT và báo lại | **A** (nếu SV có mặt), nếu không **B**. Teacher DB chỉ đọc; không dùng cổng 5432 |

Quyết định đã chốt ở Task 17 và **vẫn giữ** (không cần hỏi lại): ADMIN không tự đổi vai trò/hạ ADMIN cuối; từ chối CSV không có EID; tìm kiếm không phân biệt dấu chỉ ở tra cứu; **không tạo REVIEWER trên teacher DB**; chưa push GitHub.

---

# 15. KẾ HOẠCH DỰ PHÒNG

## 15.1. Nếu không đủ thời gian

| Loại | Nội dung | Vì sao |
|---|---|---|
| **Tài sản tối thiểu bắt buộc (T1, ≈ 35,5 giờ)** | RTM (REQ-01) · Use case: inventory + UCD-0/1/3 + 5 đặc tả · ERD 7 + data dictionary + đối chiếu ERD cũ · Kiến trúc ARC-1/2 · BPMN-1 + bảng bước · SEQ-3/6/7/8 · ACT-3/6/7 · hồ sơ thuật toán 5 mục · tokens + UI inventory · gói C3 (không code) · bàn giao + bundle | Phủ CLO1–CLO2 ở mức tối thiểu có thể bảo vệ; **toàn bộ tự động hóa hoặc bám sát mã** |
| **Có thể rút gọn** | UCD-2/4/5 · đặc tả UC còn lại (3) · SEQ/ACT còn lại · state/DFD · mockup từ 8 còn 6 · ảnh từ 32 còn 18 · hồ sơ thuật toán 12→5 mục | Có thể giữ ở mức nguồn `.puml` rồi SV hoàn thiện sau |
| **Có thể làm sau 14/10 bằng ChatGPT từ dữ kiện đã trích** | FR/NFR, test plan/cases, hướng dẫn cài đặt/sao lưu, dàn slide, diễn giải "Vì sao…", văn bản Chương 1–4 | Phụ thuộc chủ yếu vào văn bản, không cần đọc mã |
| **Không nên làm** (trước 14/10) | Sửa tính năng lớn (FIX-03/04, REOPEN/REVOKE, CSV/Excel); đổi schema/migration; merge nhánh C3; chạy C3; tạo nhãn/số liệu chất lượng; đổi `main` đã đóng băng; dựng Figma "khác hẳn" sản phẩm | Rủi ro hỏng bản demo đã kiểm thử; vi phạm quy tắc trung thực |

## 15.2. Rủi ro nếu bỏ qua từng nhóm

| Bỏ qua | Hệ quả |
|---|---|
| Thay sơ đồ cũ (D1/DB-05) | Nhật ký/báo cáo mô tả hệ thống không tồn tại ⇒ rủi ro **trung thực/nhất quán** nghiêm trọng nhất |
| ERD + dictionary + UC + đặc tả | Thiếu phần lớn điểm CLO1–2 (PI-1.3, 2.1) |
| Kiến trúc + BPMN + sequence/activity | Không đáp ứng PI-1.1, PI-2.2 |
| Figma/mockup | Không đáp ứng PI-2.3 (bắt buộc) — tối thiểu phải có tokens + mockup + hướng dẫn |
| Tập đối chiếu/đánh giá | Không đáp ứng PI-3.4/G4: phải giải trình "chưa thực hiện được vì…", không bịa số liệu |
| Ảnh độ phân giải cao | Chương 4 thiếu minh chứng đọc được |
| Hồ sơ thuật toán | Khó bảo vệ phần cốt lõi (R1 — phải tự giải thích) |
| Bundle sao lưu cuối | Mất sản phẩm nếu hỏng ổ đĩa |

---

# PHỤ LỤC A — ĐỐI CHIẾU 5 SƠ ĐỒ TRONG `DoAn.docx` VỚI HỆ THỐNG THẬT (cơ sở cho `DB-05`, D1)

Nguồn: 6 ảnh nhúng trong `DoAn.docx` (ảnh 1 là logo; ảnh 2 quy trình; ảnh 3 use case; ảnh 4–6 ERD). Đối chiếu với schema dump task17, `require_role`, `App.tsx`, mã dịch vụ.

## A.1. Quy trình nghiệp vụ (tuần 1)

| Phần tử trong sơ đồ cũ | Thực tế | Kết luận |
|---|---|---|
| "Operator: Tải file CSV 660 bản ghi, 22 trường" | ADMIN tải ở `/imports`. **Không có vai trò Operator.** 660 bản ghi ✔ (theo báo cáo trước). "22 trường": **chưa kiểm** (SUY LUẬN) | Sai tác nhân |
| "Schema & Idempotency OK?" — "Sai / trùng 100%" → "Báo lỗi / Dừng luồng" | Có kiểm tra cột EID (Task 17) và SHA-256 chống trùng (cảnh báo/409); **lỗi dòng được giữ và hiển thị, không dừng cả luồng** | Gần đúng, thiếu nhánh lỗi dòng |
| "Parse tác giả, chuẩn hoá tên, **tính Match Score**" | Bóc tách tác giả là bước **riêng** (`/normalization`); **không có Match Score**; sinh ứng viên là CLI riêng | Sai |
| "Admin: Phê duyệt / **Gán tay** / Chờ xác minh" | ACCEPT / REJECT / giữ PENDING; **không có "gán tay"** | Sai một phần |
| "Ghi Standardized + Audit Log + hỗ trợ **Rollback**" | Ghi danh tính APPROVED + audit; **không có rollback quyết định duyệt** (chỉ rollback đợt nhập) | Sai một phần |
| "Phát hiện duyệt nhầm" (vòng lặp) | Không có | Không tồn tại |
| "Operator: Xuất báo cáo chuẩn cho ICTU" | ADMIN xuất **JSON** công bố (và JSON GV) | Gần đúng, hẹp hơn |

## A.2. Use case (tuần 2)

| Phần tử | Thực tế | Kết luận |
|---|---|---|
| Actor "Chuyên viên ICTU (Operator)", "Cán bộ duyệt ICTU (Admin/Approver)" | ADMIN, REVIEWER, LECTURER (+ kỹ thuật viên CLI) | Sai tên/thiếu 2 vai trò |
| UC-01 Nhập CSV & Idempotency | UC-10 ✔ | Đúng |
| «include» Kiểm tra Schema 22 cột | Kiểm tra cột EID/định dạng; **"22 cột" chưa kiểm** | SUY LUẬN |
| UC-02 Bóc tách tác giả & Tính Match Score, **«include»** của UC-01 | Bước riêng, không bắt buộc ngay; **không Match Score** | Sai include |
| UC-03 Đối soát & Phê duyệt liên kết | UC-17/18 ✔ | Đúng |
| «extend» Gán thủ công giảng viên | Không có | Không tồn tại |
| «extend» Chuyển sang Chờ xác minh | ≈ giữ PENDING (không phải thao tác riêng) | Hiểu nhầm |
| UC-04 Hoàn tác kết quả duyệt (Rollback), «extend» UC-03 | **Không có** | Không tồn tại |
| Quản lý danh mục GV ICTU | UC-05, 08, 09 ✔ | Đúng |
| UC-05 Thống kê & xuất báo cáo (Excel/CSV/JSON) | Thống kê sơ sài; **chỉ JSON** | Quá mức |
| *(thiếu hoàn toàn)* | Đăng nhập/phân quyền, tài khoản, nhật ký kiểm toán, lịch sử review, tra cứu, xem công bố, cổng giảng viên, REVIEWER | Thiếu ≥ 12 UC thật |

## A.3. ERD (tuần 3 — 3 hình)

| Bảng trong ERD cũ | Bảng thật tương ứng | Khác biệt chính |
|---|---|---|
| `USERS` (`id bigserial`, `username`, `role`) | `users` | Khóa `uuid`; **không có `username`** (đăng nhập bằng `email`); thêm `display_name`, `lecturer_id`, `is_active`, `auth_version`… |
| `UPLOAD_BATCHES` (`operator_id` FK, `total_rows`, `duplicate_rows`, `correlation_id`) | `scopus_imports` | **Không có `operator_id`** (không FK tới users); có `file_sha256`, `status`, `valid/invalid_records`; `correlation_id` nằm ở `audit_events` |
| `RAW_SCOPUS_DATA` (`eid` **UK**, title, authors, year, doi, publisher, `duplicate`…) | `raw_scopus_records` | Dữ liệu thô nằm trong `raw_payload JSONB`; **`eid` không UNIQUE ở bảng thô** (UNIQUE ở `publications.eid`); không `publisher`/`duplicate` |
| `AUTHOR_EXTRACTED` (`match_score`, `evidence_payload`, `lecturer_id` FK) | `scopus_authors` + `scopus_author_name_variants` + `publication_authors` | Tách 3 bảng; **không `match_score`**; không FK tới giảng viên |
| `LECTURERS` (`lecturer_code` UK, `scopus_author_id` **UK**) | `lecturers` | `lecturer_code`→`staff_code` (UNIQUE một phần, null được); **không có `scopus_author_id`** |
| `APPROVAL_QUEUE` (`status` HIGH/MED/PENDING, `match_score`, `is_retracted`, `approved_at` "72h rollback") | `lecturer_scopus_candidates` (+ `…_observations`, `…_evidence`, `…_candidate_reviews`) | Trạng thái **PENDING/ACCEPTED/REJECTED/SUPERSEDED**; **không HIGH/MED, không điểm, không mốc 72 giờ** |
| `STANDARDIZED_DATA` (`is_invalidated`…) | `lecturer_scopus_identities` | Trạng thái CANDIDATE/APPROVED/REJECTED/REVOKED; hoàn tác chỉ trong schema |
| `AUDIT_LOG` (`action` APPROVE/OVERRIDE/ROLLBACK, `before_json/after_json`) | `audit_events` | Từ vựng hành động khác; có `actor_type`, `request_id`, `correlation_id`, `ip_address`… |
| `EXPORT_AUDIT_LOG` (`file_hash_sha256`, `row_count`) | **Không có bảng** | Việc xuất ghi vào `audit_events` (`PUBLICATION_DATASET_EXPORTED`: `record_count`, `format`, `schema_version`, `filters_applied`) — **không lưu SHA-256 tệp xuất** |

Tổng hợp: ERD cũ có **9 bảng**: **2** trùng tên (`users`, `lecturers`) nhưng khác cột; **6** có bảng tương ứng nhưng cấu trúc khác (có cái tách thành nhiều bảng); **1** không tồn tại. DB thật có **24 bảng**: **10** bảng có hình bóng trong ERD cũ, **14 bảng không có** (`publications`, `publication_raw_sources`, `organizations`, 2 bảng affiliation, `lecturer_source_snapshots`, `lecturer_known_publications`, `user_notifications`, `candidate_generation_runs`, `…_observations`, `…_evidence`, `…_candidate_reviews`, `identity_evidence`, `mapping_reviews`). Kiểu khóa: **`bigserial` (cũ) ≠ `uuid` (thật)**.

---

# PHỤ LỤC B — NGUỒN ĐÃ ĐỌC TRONG TASK 18 (để kiểm tra lại)

| Nhóm | Nguồn |
|---|---|
| Đề cương | `DoAn\01.DTC235200899.Trương Quang Huy.CN CNTT K22A.pdf` (5 trang); `DoAn\DoAn.docx` (văn bản + 6 ảnh) |
| Tài liệu dự án | `docs/demo/*.md` (5), `docs/adr/*.md` (4), `docs/freeze/*.md` (đề mục), `README.md` |
| Schema | `backend/app/models/*.py`; `backend/alembic/versions/*.py`; `pg_restore --schema-only` trên `_quan_ly_do_an\backups\task17\teacher_for_e2e_t17_20261009.dump` |
| API/RBAC | `app.openapi()` (57); `backend/app/api/v1/endpoints/*.py` (`require_role`) |
| Giao diện | `frontend/src/App.tsx`, `components/common/Sidebar.tsx`, `pages/*`, `tailwind.config.js`, `styles.css`, `package.json`, `types/*`, `api/imports.ts` |
| Thuật toán | `services/matching/*`, `services/normalization/scopus_normalizer.py` (đầu tệp + hàm chính), `scopus_author_normalizer.py` (docstring), `author_affiliation.py` (docstring), `lecturer_dataset/importer.py` (docstring), `candidate_review_service.py` (cấu trúc), `parser/scopus_csv_parser.py` (đầu tệp) |
| C3 | `docs/demo/TIEN_DO_V4_VA_BACKLOG_C3.md`; `_quan_ly_do_an\evidence\task17\C3_A3_doc.md`; `data/matching/evaluation/README.md` trong worktree `completion3-a3…` (chỉ đọc) |
| Bằng chứng | `_quan_ly_do_an\evidence\task16\` và `…\task17\` (29 ảnh, `openapi_coverage_matrix.md`) |
| Git | `git log`, `git worktree list`, `git stash list`, `git branch -a` |

# PHỤ LỤC C — NHỮNG ĐIỀU TASK 18 KHÔNG KIỂM ĐƯỢC (nêu thật)

1. Giao diện đang chạy, vì cụm PostgreSQL demo không bật (một lần thử kết nối chỉ-đọc bị từ chối) — mọi nhận xét UI dựa trên mã và ảnh cũ.
2. Chưa chạy lại 797 test, `tsc`/`vite build`, hay bất kỳ truy vấn nào trên DB.
3. Schema lấy từ **bản dump task17** (đúng `alembic_version = a9c2e4f71b30`); chưa so với DB đang chạy.
4. Chưa đọc hết mã nguồn: logic `build_ictu_lecturer_dataset.py`/crawler, `candidate_persistence.py`, phần lớn `scopus_import_service.py` chỉ được nhắc theo docstring/tên hàm.
5. Văn bản PDF đề cương đã mất dấu khi trích; bảng tiến độ 10 tuần lệch cột.
6. Số "22 cột" CSV, "ISSN/nguồn xuất bản trong CSV", hiệu năng, tương thích điện thoại: **chưa kiểm**.
7. Không thể kiểm các báo cáo/chat ngoài repo (có chứa credential hay không).
