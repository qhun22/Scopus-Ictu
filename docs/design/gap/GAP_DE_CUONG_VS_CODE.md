# Bảng GAP — khoảng cách giữa đề cương GVHD và phần mềm hiện có

> **Phạm vi:** đối chiếu văn bản đề cương chính thức (`01.DTC235200899.Trương Quang Huy.CN CNTT K22A.pdf`, mục 5, 7a, 7b) với **mã nguồn, schema PostgreSQL và dữ liệu thật** ở thời điểm 09/10/2026.
> **Nguyên tắc:** chỉ nêu điều đã kiểm chứng; số liệu lấy bằng truy vấn **chỉ đọc** trên DB demo `scopus_ictu_demo_teacher_20261014` (phiên `READ ONLY`, ngày 09/10/2026) hoặc từ mã nguồn; không sửa mã, không tạo tính năng giả.
> **Tuyên bố:** **phần mềm hiện chưa đáp ứng đầy đủ đề cương** — còn các GAP dưới đây. Không tài liệu nào của Task 19 được hiểu là phần mềm đã đạt đề cương.
> Về trích dẫn PDF: văn bản PDF mất dấu khi trích; các câu dưới đây là bản đọc lại, **người dùng cần đối chiếu với PDF gốc** (trang theo chân trang: mục 5 tr.1; 7a tr.2; 7b tr.2–3).

## 1. Tổng hợp

Mức cấp thiết: **CAO** = yêu cầu bắt buộc rõ trong đề cương hoặc làm hiển thị sai dữ liệu khi trình diễn · **TRUNG BÌNH** · **THẤP**.

| GAP | Yêu cầu (đề cương) | Hiện trạng | Cấp thiết | Cần quyết định? |
|---|---|---|---|---|
| **GAP-02** | PI-2.1 "nguồn xuất bản" là thực thể; mục 5 "chuẩn hóa nguồn xuất bản" | **Lưu SAI:** `publications.source_title` = `'Scopus'` ở cả 660/660 dòng (đọc nhầm cột CSV `Source`), trong khi `raw_payload` có `Source title` (277 giá trị khác nhau) và `Publisher` (109); không có bảng nguồn xuất bản | **CAO** | Có |
| **GAP-06** | Mục 5, PI-3.4: đánh giá trên tập đối chiếu GVHD xác nhận | Chưa có tập đối chiếu, chưa đánh giá; công cụ C3 chỉ ở nhánh, `NOT_RUN` | **CAO** | Có |
| **GAP-11** | PI-2.3: thiết kế Figma 6 màn | Không có tệp Figma/mockup | **CAO** | Có (Task 20) |
| **GAP-03** | PI-3.4 / 7a: gợi ý theo **mã định danh, tên, đơn vị, công bố** | Chỉ **tên** + công bố đã biết; không dùng ORCID (352/411 giảng viên có ORCID) hay đơn vị (department/faculty có ở 1/411) | **CAO** | Có |
| **GAP-04** | 7a: hiển thị căn cứ và **mức độ phù hợp** | Có căn cứ định tính; **không có điểm/mức** (`confidence_score` luôn NULL) | **CAO** | Có |
| **GAP-05** | PI-2.3: màn **so sánh trước/sau chuẩn hóa** | Chưa có màn/API; dữ liệu có sẵn (`raw_payload` + `publications`) | TRUNG BÌNH | Có |
| **GAP-01** | Mục 5, 7a: chuẩn hóa **DOI** | DOI chuẩn hóa chỉ ở bước so khớp; `publications.doi` lưu nguyên văn (125/635 DOI có chữ hoa) | TRUNG BÌNH | Có |
| **GAP-07** | 7a: "xem lại và phục hồi kết quả trước khi gộp" | Hoàn tác cấp **đợt nhập** có; hoàn tác **quyết định duyệt** không có (chỉ schema) | TRUNG BÌNH | Có |
| **GAP-09** | 7a: xuất dữ liệu chuẩn; định dạng trao đổi thống nhất với GVHD | Chỉ JSON (công bố, giảng viên); không CSV/Excel; chưa có biên bản thống nhất định dạng | TRUNG BÌNH | Có |
| **GAP-08** | 7a, PI-2.3: thống kê | Chỉ chỉ số đếm; biểu đồ giữ chỗ | TRUNG BÌNH | Có |
| **GAP-10** | PI-3.1, PI-4.1: kịch bản + hướng dẫn **sao lưu/phục hồi** | Chỉ có thao tác `pg_dump`/`pg_restore` rời rạc | TRUNG BÌNH | Không |
| **GAP-12** | PI-1.2: FR/NFR, tiêu chí nghiệm thu thống nhất GVHD | Đã có bản nháp (Task 19); chưa được GVHD xác nhận | TRUNG BÌNH | Người dùng làm |
| **GAP-13** | PI-3.2: giao diện tương thích điện thoại | Có lớp responsive; chưa có bằng chứng khổ điện thoại | TRUNG BÌNH | Không |
| **GAP-19** | PI-4.2: bộ dữ liệu kiểm thử bao phủ loại lỗi; biên bản mong đợi/thực tế | Có báo cáo E2E và fixture; chưa có danh mục dữ liệu theo từng loại lỗi | THẤP–TB | Không |
| **GAP-14** | PI-4.1: triển khai ra môi trường thử nghiệm | Chạy localhost; compose chưa kiểm chứng | THẤP–TB | Xác nhận GVHD |
| **GAP-15** | 7a: chạy chức năng đối sánh | Sinh ứng viên/nạp bằng chứng chỉ bằng CLI; không có UI chạy/theo dõi | THẤP–TB | Có |
| **GAP-16** | PI-1.2: an toàn dữ liệu, truy vết | Thiếu giới hạn đăng nhập sai; audit không ghi đăng nhập; chỉ-thêm không do DB cưỡng chế | THẤP–TB | Không |
| **GAP-17** | (nhất quán kỹ thuật) | ORM thiếu 1 CHECK có trong DB (`scopus_imports.normalization_summary`) | THẤP | Không |
| **GAP-18** | (nhất quán tài liệu/mã) | Mã giữ chỗ M0 còn sót; README lỗi thời | THẤP | Không |
| **GAP-20** | P9 bàn giao: mã nguồn, CSDL, bộ kiểm thử | `main` chưa push; chưa có CI chứng minh cho các commit sau Completion-2 | THẤP–TB | Có |

## 2. Chi tiết từng GAP

### GAP-02 — Nguồn xuất bản (lưu sai và không có thực thể)

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | Mục 5: "Chuẩn hóa DOI, tên công bố, **nguồn xuất bản**, năm xuất bản và mã định danh tác giả Scopus Author ID"; PI-2.1: ERD có "**nguồn xuất bản**" cùng hồ sơ tác giả, công bố, tác giả công bố, ánh xạ giảng viên |
| **Hiện trạng source** | (1) Không có bảng nguồn xuất bản; nguồn là cột chuỗi `publications.source_title`. (2) **Lỗi ánh xạ dữ liệu:** `create_publication_from_raw` đọc `_raw_field({}, payload, "Source", "source_title")` (`backend/app/services/normalization/scopus_normalizer.py`, hàm `create_publication_from_raw`) — cột CSV **`Source`** chứa nhãn cơ sở dữ liệu (`'Scopus'`), không phải tên tạp chí/hội nghị. Truy vấn chỉ đọc: `SELECT source_title, count(*) FROM publications GROUP BY 1` → `('Scopus', 660)`; trong khi `raw_payload->>'Source title'` có **277** giá trị khác nhau, `Publisher` có **109**, và không dòng nào thiếu `Source title`. Cột CSV **không có ISSN** (22 cột: Authors, Author full names, Author(s) ID, Title, Year, Source title, Volume, Issue, Art. No., Page start, Page end, Cited by, DOI, Link, Abstract, Author Keywords, Document Type, Publication Stage, Open Access, Source, EID, Publisher) |
| **Hệ quả** | Giao diện chi tiết công bố (nhãn "Nguồn tạp chí") và dữ liệu xuất JSON hiển thị **'Scopus' cho mọi công bố** — sai về nghĩa, có thể bị giảng viên hoặc người phản biện phát hiện khi demo; không thể thống kê theo tạp chí/nhà xuất bản; ERD không có thực thể mà đề cương nêu |
| **Mức cấp thiết** | **CAO** (dữ liệu hiển thị sai trong sản phẩm đang trình diễn; yêu cầu bắt buộc PI-2.1) |
| **Phương án** | **A (tối thiểu, trung thực):** trong báo cáo và demo nêu rõ đây là lỗi/giới hạn đã biết; không dùng trường này khi trình bày; thiết kế ERD ghi GAP, **không tự thêm bảng `publication_sources`**. **B (sửa dữ liệu):** đổi ánh xạ sang cột `Source title`, tái chuẩn hóa (cần quyết định vì chạm production code và dữ liệu đã đóng băng; có thể làm ở DB kiểm thử trước). **C (đầy đủ):** B + bảng nguồn xuất bản (migration mới, ngoài thời hạn). **Task 19 không sửa gì** (đã gắn nhiệm vụ đề xuất riêng) |

### GAP-06 — Bộ nhãn đánh giá do GVHD xác nhận

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | Mục 5: "Kiểm thử chức năng, đánh giá chất lượng chuẩn hóa/đối soát trên bộ dữ liệu có GVHD xác nhận; báo cáo kết quả và các trường hợp chưa giải quyết được"; PI-3.4: "Đánh giá kết quả gợi ý trên tập đối chiếu do GVHD xác nhận" |
| **Hiện trạng source** | Không có tập đối chiếu trong dự án. Công cụ đánh giá nằm ở nhánh Completion-3 (`completion3/a1…a3`, chưa merge `main`): cohort 50/410 chọn trước (`SHA256_SEED_RANK_V1`), chỉ đo **độ phủ truy xuất ứng viên**, không đo precision/F1; trạng thái `Human-confirmed reference: NOT_AVAILABLE`, `Official evaluation: NOT_RUN`. Chưa có số liệu chất lượng nào |
| **Hệ quả** | Thiếu một yêu cầu kiểm thử bắt buộc; không được nêu precision/recall/F1 hay "độ chính xác" của gợi ý |
| **Mức cấp thiết** | **CAO** (bắt buộc theo đề cương; phụ thuộc người) |
| **Phương án** | **A:** hỏi GVHD (buổi 14/10) có/không có tập đối chiếu và định dạng; chuẩn bị giao thức + thư đề nghị + runbook (không code, không nhãn). **B:** sau khi có nhãn, đánh giá cohort 50 trên corpus demo (cần chỉnh/chạy công cụ C3). **C:** nếu không có nhãn, trình bày "chưa đánh giá được vì chưa có tập đối chiếu" cùng các trường hợp chưa giải quyết (Scopus ID dùng chung, tên viết tắt…). Không bao giờ tự tạo nhãn |

### GAP-11 — Figma / thiết kế giao diện

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | PI-2.3: "Có bản thiết kế giao diện bằng Figma cho màn hình danh sách, chi tiết, nhập dữ liệu, so sánh trước/sau chuẩn hóa, hàng đợi phê duyệt và thống kê" |
| **Hiện trạng** | Không có Figma, mockup, wireframe hay design tokens; 15 màn đã triển khai. Phiên làm việc không có công cụ Figma. Đầu vào bàn giao cho Task 20: `figma_handoff/FIGMA_HANDOFF_TASK20.md` |
| **Hệ quả** | Thiếu sản phẩm bắt buộc của CLO2 |
| **Mức cấp thiết** | **CAO** |
| **Phương án** | Task 20: tokens + mockup nguồn (HTML/SVG) bám giao diện đã triển khai + hướng dẫn nhập vào Figma; **file Figma thật do sinh viên tạo/xác nhận**. Không gọi PNG/SVG là Figma |

### GAP-03 — Gợi ý theo mã định danh, tên, đơn vị, công bố

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | 7a/PI-3.4: "Gợi ý ánh xạ hồ sơ tác giả Scopus với giảng viên dựa trên **mã định danh, tên, đơn vị và thông tin công bố**" |
| **Hiện trạng source** | `candidate_generator.py` chỉ so **tên bằng nhau tuyệt đối** sau chuẩn hóa (4 luật). Trên teacher DB: toàn bộ 134 bằng chứng tên đều từ luật `RULE_TITLE_STRIPPED_N2_FORMAT`; 69 bằng chứng công bố (57 theo DOI, 12 theo tiêu đề) cho 6/40 ứng viên. **Không dùng:** ORCID — dù `lecturers.orcid` có ở **352/411** hồ sơ (CHECK/unique đã sẵn); đơn vị — `department` có ở **1/411**, `faculty` ở **1/411**, `staff_code` ở **0/411**; năm công bố. Mã định danh Scopus chỉ có ở phía tác giả. Schema `identity_evidence` cho phép `ORCID_EXACT`, `AFFILIATION_MATCH`… nhưng **không có mã tạo các loại này** |
| **Hệ quả** | Gợi ý yếu (34/40 ứng viên chỉ có bằng chứng tên); không tận dụng ORCID; 373/411 hồ sơ giảng viên (372/410 giảng viên ICTU + 1 hồ sơ demo) không có ứng viên (không đồng nghĩa không có công bố) |
| **Mức cấp thiết** | **CAO** (yêu cầu mô tả rõ; không nên khẳng định đã đáp ứng) |
| **Phương án** | **A:** mô tả đúng trong báo cáo (đối sánh bằng tên + công bố đã biết; ORCID/đơn vị là hướng phát triển); **B:** thêm luật ORCID (cần dữ liệu ORCID phía tác giả Scopus — CSV không có cột ORCID, nguồn là OpenAlex/Crossref/ORCID đã nạp — cần khảo sát) — chạm luật đối sánh, **ngoài Task 19** |

### GAP-04 — Mức độ phù hợp

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | 7a/PI-3.4: "hiển thị căn cứ, **mức độ phù hợp** để người quản lý duyệt" |
| **Hiện trạng source** | Căn cứ hiển thị đầy đủ (luật, hai phía tên, công bố hỗ trợ, ngữ cảnh mơ hồ, cảnh báo dùng chung). **Không có điểm/mức độ**: `matching/scoring.py` và `engine.py` là mã giữ chỗ M0 (`NotImplementedError`); `identity_evidence.confidence_score` luôn NULL (test `test_evidence_promotion_count_and_confidence`); ADR-004 nêu thứ tự mạnh–yếu "không phải điểm số". Giao diện có bộ lọc "Mức độ mơ hồ" (số ứng viên khác), không phải mức phù hợp |
| **Hệ quả** | Thiếu một thành phần được đề cương nêu tên; dễ bị hiểu nhầm "mức mơ hồ" là "mức phù hợp" |
| **Mức cấp thiết** | **CAO** |
| **Phương án** | **A:** giải trình: mức phù hợp thể hiện **định tính** qua loại bằng chứng (có công bố hỗ trợ / chỉ tên) và ngữ cảnh mơ hồ; chưa có điểm. **B:** hiển thị nhãn định tính suy ra thuần từ loại bằng chứng (không đổi DB, không đổi luật) — cần code giao diện + API, ngoài Task 19. Không tự thêm công thức điểm |

### GAP-05 — So sánh trước/sau chuẩn hóa

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | PI-2.3: màn hình "so sánh trước/sau chuẩn hóa" (thiết kế Figma) |
| **Hiện trạng source** | **Không có màn/API.** `DiffViewerStub` là mã giữ chỗ không được dùng. Dữ liệu phục vụ có sẵn: `raw_scopus_records.raw_payload` (22 trường gốc) ↔ `publications` (đã chuẩn hóa) qua `publication_raw_sources`. Chi tiết công bố chỉ hiển thị nguồn gốc (tệp, số dòng, SHA-256), không so sánh giá trị. So sánh sẽ làm lộ GAP-02 (`Source title` gốc ↔ `'Scopus'` chuẩn hóa) |
| **Hệ quả** | Thiếu màn do đề cương nêu; chỉ cần *thiết kế* theo PI-2.3 |
| **Mức cấp thiết** | TRUNG BÌNH |
| **Phương án** | **A (đề xuất):** thiết kế mockup, gắn nhãn `THIẾT KẾ ĐỀ XUẤT — CHƯA TRIỂN KHAI` (Task 20). **B:** cài viewer chỉ-đọc (≈ 9 giờ, API + UI + test) — ngoài Task 19 |

### GAP-01 — Chuẩn hóa DOI

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | Mục 5 và 7a: "Chuẩn hóa DOI, tên công bố…" |
| **Hiện trạng source** | `publications.doi` lưu theo văn bản nguồn, chỉ cắt khoảng trắng (`_raw_doi`). Chuẩn hóa DOI (chữ thường, bỏ tiền tố `https://doi.org/`, `doi:`) có ở `normalize_doi_for_matching` (chỉ dùng khi so khớp) và ở `lecturer_known_publications.doi_normalized`. `doi_normalizer.py` là mã giữ chỗ M0. Dữ liệu hiện tại: 635/660 công bố có DOI; **125 DOI chứa chữ hoa**; 0 DOI có tiền tố URL; 0 DOI thừa khoảng trắng; **không có DOI trùng khi bỏ phân biệt hoa/thường** |
| **Hệ quả** | Về hình thức chưa chuẩn hóa DOI ở lưu trữ chính; chưa gây trùng/sai trên dữ liệu hiện có; `publications.doi` không được unique |
| **Mức cấp thiết** | TRUNG BÌNH |
| **Phương án** | **A:** mô tả đúng ("DOI giữ nguyên bản gốc; chuẩn hóa khi đối chiếu"). **B:** thêm cột/chỉ mục DOI chuẩn hóa (migration) — ngoài thời hạn |

### GAP-07 — Phục hồi/hoàn tác

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | 7a: "Giữ nguyên dữ liệu đầu vào, lưu nguồn và lịch sử chỉnh sửa; cho phép **xem lại và phục hồi kết quả trước khi gộp**" |
| **Hiện trạng source** | Giữ nguyên đầu vào ✔ (dòng thô bất biến, snapshot); lưu nguồn ✔ (provenance); lịch sử ✔ (audit, lịch sử review); xem lại ✔ (UC-19); phục hồi: **cấp đợt nhập** ✔ (JSON: `/lecturers/import/{id}/rollback`; CSV: hủy/lưu trữ/xóa đợt chưa dùng); **cấp quyết định duyệt ✖** — CHECK `REOPEN`/`REVOKE` và bảng `mapping_reviews` có trong schema nhưng không API/UI, 0 dòng, test `test_no_mapping_review_written`. Hệ thống **không gộp** hồ sơ tác giả (chỉ liên kết), nên "trước khi gộp" cần GVHD làm rõ nghĩa |
| **Hệ quả** | Nếu "phục hồi" được hiểu là hoàn tác quyết định duyệt thì chưa đáp ứng |
| **Mức cấp thiết** | TRUNG BÌNH |
| **Phương án** | **A:** giải trình phạm vi (hoàn tác cấp đợt nhập; quyết định duyệt là chỉ-thêm, sai thì cần cơ chế bù trừ — thiết kế dự phòng `mapping_reviews`); hỏi GVHD nghĩa "gộp". **B:** cài REOPEN/REVOKE (API + UI + test) — ngoài Task 19 |

### GAP-09 — Xuất dữ liệu chuẩn và định dạng trao đổi

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | 7a: "thống kê và **xuất dữ liệu chuẩn**"; "Định dạng trao đổi dữ liệu dùng chung được thống nhất với GVHD" |
| **Hiện trạng source** | `GET /publications/export` (JSON, `schema_version 1.0`, lọc, ghi audit, chỉ ADMIN) và `GET /lecturers/export` (JSON nhập lại được). **Không có CSV/Excel.** JSON Schema cho hồ sơ giảng viên ở `data/lecturers/schema/`. Chưa có biên bản thống nhất định dạng với GVHD. Sơ đồ UC cũ hứa Excel/CSV/JSON — không có thật |
| **Hệ quả** | Có thể đáp ứng nếu GVHD chấp nhận JSON; rủi ro nếu cần CSV/Excel |
| **Mức cấp thiết** | TRUNG BÌNH |
| **Phương án** | **A:** xin GVHD xác nhận JSON là định dạng chung; **B:** thêm xuất CSV (≈ 3–4 giờ) — ngoài Task 19 |

### GAP-08 — Thống kê

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | 7a: "thống kê"; PI-2.3: màn thống kê |
| **Hiện trạng source** | `GET /dashboard/summary`: số công bố, giảng viên (tổng/hoạt động), tác giả, danh tính theo trạng thái, hàng chờ, đợt nhập gần nhất, audit gần đây. Không có thống kê theo năm/loại tài liệu/khoa/nguồn; biểu đồ Trang chủ là giữ chỗ ("Đang phát triển") |
| **Hệ quả** | Thống kê sơ sài so với yêu cầu |
| **Mức cấp thiết** | TRUNG BÌNH |
| **Phương án** | **A:** thiết kế màn thống kê mở rộng ở Figma (đề xuất, gắn nhãn chưa triển khai); **B:** cài thêm truy vấn thống kê + biểu đồ — ngoài Task 19 |

### GAP-10 — Sao lưu và phục hồi

| Mục | Nội dung |
|---|---|
| **Yêu cầu PDF** | PI-3.1: "kịch bản khởi tạo, sao lưu và phục hồi"; PI-4.1: "hướng dẫn cài đặt, sử dụng, sao lưu và phục hồi" |
| **Hiện trạng** | Khởi tạo: `alembic upgrade head` + script bootstrap ✔. Sao lưu/phục hồi: đã dùng `pg_dump -Fc`/`pg_restore` nhiều lần (ngoài Git, kèm SHA256SUMS) nhưng **không có kịch bản/hướng dẫn chính thức trong repo** |
| **Hệ quả** | Thiếu tài liệu bắt buộc; dễ chứng minh được bằng một quy trình có kiểm chứng |
| **Mức cấp thiết** | TRUNG BÌNH |
| **Phương án** | Viết `BACKUP_RESTORE.md` và kiểm phục hồi vào DB mới đặt tên `*_restore_check` (không ghi teacher) — việc `REQ-04` ở kế hoạch Task 18 |

### Các GAP còn lại (ngắn)

| GAP | Hiện trạng đã kiểm | Phương án |
|---|---|---|
| **GAP-12** FR/NFR | `requirements/01_FR_NFR.md` (33 FR, 15 NFR) là bản nháp; tiêu chí nghiệm thu **chưa được GVHD xác nhận** | Mang bản nháp tới buổi 14/10 xin xác nhận bằng văn bản/email |
| **GAP-13** Điện thoại | `Sidebar.tsx` có chế độ mobile; `index.html` có viewport; Tailwind `sm:/lg:`; **chưa có ảnh/kiểm thử ở khổ điện thoại** | Chụp 3 màn ở 390×844 (Task 25) |
| **GAP-19** Bộ dữ liệu kiểm thử | Có `backend/tests/fixtures/scopus_sample.csv`, `ictu_lecturers_fixture.json`, E2E trên bản sao teacher, ví dụ công bố thật; `data/test_fixtures/` chỉ có `.gitkeep` | Lập danh mục dữ liệu theo loại lỗi (hợp lệ/thiếu trường/sai định dạng/trùng/tên giống/lỗi nhập) |
| **GAP-14** Triển khai | Localhost + BAT + cụm PostgreSQL 17 riêng (THEO BÁO CÁO TRƯỚC); `compose*.yaml`/`Dockerfile` chưa có bằng chứng chạy; PI-4.1 liệt kê "localhost, hosting, cloud" | Xin GVHD xác nhận localhost đủ; kiểm compose nếu có thời gian |
| **GAP-15** UI cho script | Sinh ứng viên, nạp Craw/affiliation, bootstrap chỉ qua CLI; `/tasks` là giữ chỗ; quản lý liên kết theo giảng viên và chi tiết tác giả chỉ có API | Nêu rõ trong báo cáo; thiết kế UI ở Figma nếu cần |
| **GAP-16** Bảo mật | Không có giới hạn số lần đăng nhập sai; `audit_events` không ghi đăng nhập; chỉ-thêm là quy ước tầng ứng dụng (DB không có trigger/REVOKE); cookie `secure=false` trên localhost | Ghi hạn chế; (tùy chọn sau) rate limit + audit đăng nhập |
| **GAP-17** ORM↔DB | ORM thiếu CHECK `ck_scopus_imports_ck_scopus_imports_normalization_summa_5872` có trong DB (`database/ORM_MIGRATION_DB_PARITY.md`) | Sửa mô hình/migration ở đợt sau |
| **GAP-18** Mã giữ chỗ/README | `matching/scoring.py`, `engine.py`, `normalization/*_normalizer.py` (stub `NotImplementedError`), `GET /matching/ping` ("matching-stub"), `DiffViewerStub`; README bảng milestone ghi M2.7/M2.8/M3/M4 là "chưa làm" | Ghi chú/dọn sau 14/10 (không đổi hành vi) |
| **GAP-20** Bàn giao/CI | `main` hơn `origin/main` ≥ 21 commit, chưa push; `.github/workflows/ci.yml` có nhưng chưa ghi kết quả CI cho các commit sau Completion-2 | Quyết định push/PR sau 14/10; bundle sao lưu cục bộ trong lúc chờ |

## 3. Điều KHÔNG phải GAP (để khỏi nhầm)

| Yêu cầu | Đã đáp ứng | Bằng chứng |
|---|---|---|
| Không tự khẳng định tác giả chỉ vì tên giống; thiếu căn cứ → danh sách chờ | ✔ | ADR-004; `test_no_mapping_review_written`; teacher: 0 APPROVED, 40 PENDING |
| Giữ nguyên dữ liệu đầu vào, lưu nguồn | ✔ | `raw_scopus_records.raw_payload`, `publication_raw_sources`, `lecturer_source_snapshots` |
| Nhập lại không sinh bản ghi trùng; báo lỗi theo dòng; xem trước JSON | ✔ | FR-011, FR-013 |
| Phân quyền, đăng nhập | ✔ | FR-003, RBAC_API_MATRIX |

## 4. Gợi ý ưu tiên xử lý (không phải cam kết)

1. **Trước 14/10:** hiểu và nêu thật GAP-02 (nguồn 'Scopus'), không phô diễn trường này; chuẩn bị câu hỏi GVHD cho GAP-06, GAP-09, GAP-12, GAP-14 (xem `figma_handoff` §Câu hỏi).
2. **Task 20:** GAP-11 (+ thiết kế GAP-05, GAP-08).
3. **Sau khi có quyết định:** sửa GAP-02 (B) là việc nhỏ nhưng chạm dữ liệu — làm ở DB kiểm thử trước; GAP-04 (nhãn định tính); GAP-06 (nhãn từ GVHD).
