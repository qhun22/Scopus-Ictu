# Báo cáo nghiệm thu CSV-only — Scopus-ICTU (16/10/2026)

Nhiệm vụ: "NGHIỆM THU CSV-ONLY — SCOPUS-ICTU". Mục tiêu: chứng minh hệ thống xử lý và tra cứu được dữ liệu từ CSV Scopus độc lập, không phụ thuộc JSON giảng viên, trên DB test cô lập.

Báo cáo này **bổ sung** cho [`CSV_ONLY_E2E_20261011.md`](CSV_ONLY_E2E_20261011.md) (đã PASS các bước nhập CSV / chuẩn hóa / bóc tách tác giả / baseline affiliation = 0) — không lặp lại các mục đã PASS ở đó. Trọng tâm hôm nay: **thu thập đơn vị trực tuyến (online enrichment) → Xem trước (read-only) → Áp dụng (ghi thật)**, cộng với kiểm tra quyền truy cập theo vai trò (ADMIN/REVIEWER/LECTURER) trên cùng luồng CSV-only.

Quy ước: **PASS** / **FAIL** / **PARTIAL** / **BLOCKED**. Mức bằng chứng: **[TN]** thực nghiệm (UI + API + truy vấn DB trực tiếp) · **[T]** đọc code tĩnh.

---

## Giai đoạn A — Môi trường và an toàn

| Hạng mục | Giá trị |
|---|---|
| Nhánh git | `main`, commit nền `731fa8f` (không có thay đổi chức năng mới kể từ đó) |
| Backend test | `csvonly-backend`, cổng 8299, `DB_NAME=scopus_ictu_test_csvonly_20261011` |
| Frontend test | `csvonly-frontend`, cổng 5299, proxy → 8299 |
| Database | `scopus_ictu_test_csvonly_20261011` @ 127.0.0.1:55432 (**không phải** cổng 5432, **không phải** App DB `scopus_ictu_app`, **không phải** demo `scopus_ictu_demo_teacher_20261014`) |
| Alembic | nâng lên `head` (`e1a2b3c4d5f6 → f6a1b2c3d4e5 → a3b7c9d1e2f4 → b5e8d2f1a4c7 → c7f2a9b1d3e5`) — đã xin phép người dùng trước khi chạy; không migrate/seed vào App DB/demo |
| Dữ liệu trước test | 660 công bố, 0 giảng viên, 2.751 `publication_authors`, 0 tổ chức/affiliation — xác nhận lại bằng truy vấn DB, không giả định |
| Tài khoản test | `csvonly.e2e.admin/reviewer/lecturer@ictu.edu.vn` (script `backend/scripts/create_csvonly_e2e_accounts.py`, idempotent, chỉ ghi vào DB test này, có audit `DEMO_ACCOUNT_SEEDED`) |

**Kết luận Giai đoạn A: PASS.** DB cô lập được xác minh bằng truy vấn trực tiếp trước khi có bất kỳ thao tác ghi nào; không migration/seed vào DB chính; không restart server demo/production.

---

## Giai đoạn B — Kiểm thử thật trên DB cô lập

### B.1 Trạng thái trước khi can thiệp
Xác nhận lại qua UI tab "Đơn vị tác giả": *"Chưa áp dụng đối chiếu đơn vị nào. Mọi tác giả đang hiển thị 'Chưa đối chiếu'."* — khớp báo cáo 11/10.

### B.2 Thu thập đơn vị trực tuyến (OpenAlex / Crossref / ORCID)
- Kích hoạt job thật qua nút "Bắt đầu thu thập trực tuyến" (ADMIN, có xác nhận trước khi chạy HTTP thật ra ngoài).
- Job `6d6c2bbd-f941-44db-9142-f995c8a000d9`: `total_dois=300`.
- **Hiện tượng quan sát được:** sau khi OpenAlex/Crossref xử lý xong 300/300 (`openalex_found=296, crossref_found=296`), cột `updated_at`/tiến độ hiển thị **đứng yên** trong vài lần kiểm tra liên tiếp (~20–30 giây), `orcid_fetched` vẫn ở 0, trạng thái vẫn `RUNNING`.
- **Chẩn đoán (đọc mã nguồn [T], `backend/app/services/affiliation_online_fetch.py`):** đây là hành vi đúng thiết kế, không phải treo. `run_enrichment()` chỉ gọi `progress_cb` (cập nhật DB) từ bên trong vòng lặp Crossref (`on_crossref`); bước ORCID (`fetch_orcid_records`) **không có callback tiến độ trung gian** — toàn bộ bước ORCID chạy "im lặng" rồi mới ghi `progress_cb` một lần cuối khi xong. Do đó UI/DB không có tín hiệu tiến độ nào trong suốt thời gian xử lý ORCID, dễ bị hiểu nhầm là treo.
- **Kết quả thật sự:** job hoàn tất sau ~4 phút kể từ khi Crossref xong — `status=COMPLETED, orcid_fetched=310, error_summary=None`. UI cập nhật đúng: "Hoàn tất · 296 bài OpenAlex · 296 bài Crossref · 310 ORCID".
- **Phân loại:** **MINOR (UX)** — không phải lỗi dữ liệu, không BLOCKER. Đề xuất sửa tối thiểu: thêm `progress_cb` (hoặc chỉ cập nhật `updated_at`) bên trong vòng lặp `fetch_orcid_records` để tránh cảm giác treo khi chờ lâu. **Chưa tự triển khai**, chỉ báo cáo theo đúng yêu cầu nhiệm vụ.

### B.3 Xem trước (Preview) — xác minh thật sự read-only
- Trước khi bấm "Xem trước": truy vấn trực tiếp `organizations=0, publication_author_affiliations=0, publication_author_affiliation_resolutions=0`.
- Bấm "Xem trước" → UI hiển thị đầy đủ bảng mức độ tin cậy theo nguồn (sẽ ghi mới/đã có/bỏ qua/xung đột), tổng "Sẽ ghi: 5.502 kết quả đối chiếu, 1.711 dòng đơn vị, 106 tổ chức mới", và 4 xung đột được giữ lại an toàn (`WITHHELD_SOURCE_CONFLICT`).
- Truy vấn lại ngay sau Preview: **cả 3 bảng vẫn 0 dòng** — xác nhận Preview không ghi dữ liệu, đúng như dòng chữ "Xem trước chỉ đọc, không ghi dữ liệu" trong giao diện.
- **Kết luận: PASS [TN].**

### B.4 Áp dụng (ghi thật) — chỉ sau khi tick xác nhận
- Nút "Xác nhận áp dụng" bị vô hiệu cho đến khi tick ô "Tôi đã xem kết quả trên...".
- Sau khi tick và bấm áp dụng: UI báo "Đã áp dụng: 5.502 kết quả đối chiếu đơn vị được ghi", "106 tổ chức", "1.711 dòng đơn vị" — khớp **chính xác** số liệu đã hiển thị ở bước Preview (không có sai lệch giữa dự báo và kết quả ghi).
- Truy vấn DB xác nhận: `organizations=106, publication_author_affiliations=1711, publication_author_affiliation_resolutions=5502`.
- **Kết luận: PASS [TN].**

### B.5 Mở công bố thật — kiểm tra từng tác giả, thứ tự, đơn vị, bằng chứng
Công bố ví dụ đầy đủ: **`2-s2.0-105000434624`** — "A Switch-Transformer Predictive Process Monitoring Model for Next Activity Prediction in Business Process Management", DOI `10.1145/3704137.3704186`, 3 tác giả.

| STT | Tên | Scopus ID | Mức tin cậy | Đơn vị chuẩn hóa | Bằng chứng |
|---|---|---|---|---|---|
| 1 | Nguyen, Thanh-Hai | 57560524600 | **Đã xác minh định danh** (Crossref + OpenAlex) | Thai Nguyen University of Information and Communication Technology (VN) | Chuỗi ORCID `0000-0003-1801-5887` → Scopus Author ID, vị trí 1 khớp trên cả 2 nguồn |
| 2 | Kim, Kyoung-Sook | 57193455307 | Đã đối chiếu · Chưa xác minh | Kyonggi University (KR) | Chỉ khớp số tác giả + vị trí + tên, không có định danh chung |
| 3 | Kim, Kwanghoon Pio | 57297022700 | Đã đối chiếu · Chưa xác minh | Kyonggi University (KR) | Như trên |

Thứ tự tác giả (`author_order` 1→3) đúng với CSV gốc; bảng truy vết vẫn còn nguyên (tên tệp, dòng 150, SHA-256) — không bị ảnh hưởng bởi bước enrichment. Hệ thống phân biệt rõ "Đã xác minh định danh" (có chuỗi ORCID→Scopus ID) với "Đã đối chiếu · Chưa xác minh" (chỉ khớp heuristic) — đúng ngữ nghĩa governance đã thống nhất trước đó, không gộp hai khái niệm.

### B.6 Ca thiếu bằng chứng — không bịa đơn vị
Công bố **`2-s2.0-105000836388`** (7 tác giả) — tác giả #3 (Amago, Jerico) và #5 (Maligalig, Cielito) hiển thị **"Chưa có thông tin đơn vị"**, kèm lý do cụ thể theo từng nguồn:
- Crossref: "nguồn không có đơn vị"
- OpenAlex: "Chưa xác định (Tên tác giả không khớp)"

Không có tổ chức nào bị gán giả cho hai tác giả này. **Kết luận: PASS [TN]** — đúng yêu cầu "tác giả không đủ bằng chứng sẽ giữ 'Chưa xác định'" nêu rõ ngay trong UI và không vi phạm.

### B.7 Ca lỗi nhập CSV không hợp lệ
Đợt nhập `thieu_cot_EID.csv` (đã có sẵn trong lịch sử nhập của DB test) ở trạng thái `FAILED`; hộp thoại "Chi tiết" hiển thị thông báo tiếng Việt rõ ràng: *"Tệp CSV không phải bản xuất từ Scopus: thiếu cột EID (mã định danh bài báo bắt buộc để chuẩn hóa)."* Nút "Xác nhận nhập" bị vô hiệu hóa cho đợt này. **Kết luận: PASS [TN]** (đã xác minh ở phiên trước, không thay đổi).

### B.8 HTTP 200 không được coi là đủ bằng chứng
Toàn bộ kết luận PASS ở trên dựa trên đối chiếu 3 lớp: số liệu trả về UI ⟷ truy vấn SQL trực tiếp trên DB test ⟷ nội dung hiển thị từng trường trên trang chi tiết công bố — không dừng ở việc request trả mã 200.

**Kết luận Giai đoạn B: PASS**, có 1 phát hiện MINOR (B.2, UX tiến độ ORCID).

---

## Giai đoạn C — Quyền truy cập và ngôn ngữ theo vai trò

Thực hiện trên cùng DB CSV-only, dùng 3 tài khoản `csvonly.e2e.*`.

| Vai trò | Đăng nhập | Trang chủ đúng vai trò | Chặn route ngoài quyền | VI/EN |
|---|---|---|---|---|
| ADMIN | PASS | PASS (đã kiểm ở B.2–B.6, dùng để Apply) | — (có toàn quyền) | PASS (đã kiểm phiên trước) |
| REVIEWER | PASS | PASS — shortcut "Duyệt đối sánh / Công bố / Lịch sử review" | PASS — `/dashboard` và `/audit-logs` tự động chuyển hướng về `/home` | — (không kiểm lại, đã PASS trước đó) |
| LECTURER | PASS | PASS — shortcut "Hồ sơ cá nhân / Công bố của tôi / Liên kết Scopus" | PASS — `/normalization` (màn ghi dữ liệu) tự động chuyển hướng về `/home` | **PASS** — chuyển EN toàn bộ layout + nội dung nhất quán (vd. "Lecturer profile", "Account not linked", "Retry"), không còn chữ tiếng Việt sót lại |

**Trường hợp đặc biệt đã kiểm:** tài khoản LECTURER test không gắn `lecturer_id` (chưa liên kết hồ sơ giảng viên). Trang `/profile` hiển thị đúng trạng thái "Tài khoản chưa được liên kết với hồ sơ giảng viên ICTU" kèm nút "Thử lại" — không lỗi, không trang trắng, không dữ liệu giả.

**Kết luận Giai đoạn C: PASS.** Không cần xây Dashboard riêng cho REVIEWER (đúng yêu cầu nhiệm vụ).

---

## Giai đoạn D — Tổng kết

### Bảng tổng hợp

| Giai đoạn | Kết luận |
|---|---|
| A — Môi trường/an toàn | PASS |
| B — Luồng CSV-only + affiliation trực tuyến | PASS (1 MINOR) |
| C — Phân quyền + ngôn ngữ | PASS |

### Vấn đề phát hiện

**MINOR** — Không có tín hiệu tiến độ trong bước thu thập ORCID của job enrichment trực tuyến (`backend/app/services/affiliation_online_fetch.py`, hàm `run_enrichment`): `progress_cb` chỉ được gọi trong vòng lặp Crossref, không có trong `fetch_orcid_records`, khiến `updated_at`/tiến độ hiển thị đứng yên trong toàn bộ thời gian xử lý ORCID (có thể vài phút với job lớn), dễ gây hiểu nhầm là treo.
- **Phương án sửa tối thiểu (đề xuất, chưa triển khai):** truyền một callback nhỏ vào `fetch_orcid_records` để cập nhật `progress.orcid_fetched` (số đã xử lý, không cần đợi xong toàn bộ) sau mỗi ORCID, gọi `progress_cb` định kỳ như đã làm với Crossref.

Không phát hiện vấn đề BLOCKER hoặc MAJOR trong phạm vi đã kiểm thử.

### Bằng chứng
- DB: các truy vấn SQLAlchemy trực tiếp trên `scopus_ictu_test_csvonly_20261011` (đếm bảng trước/sau Preview, trước/sau Apply; truy vấn bản ghi `affiliation_enrichment_jobs`).
- API/UI: `preview_logs` của `csvonly-backend` (không có exception); nội dung trang `/normalization?tab=affiliations`, `/publications/2-s2.0-105000434624`, `/publications/2-s2.0-105000836388`, `/profile` (VI và EN).
- Không ghi mật khẩu/token/secret trong báo cáo này.

### Khuyến nghị: **GO**

Hệ thống chứng minh được khả năng xử lý và tra cứu dữ liệu từ CSV Scopus độc lập, không phụ thuộc JSON giảng viên:
- Nhập → chuẩn hóa → bóc tách tác giả → đối chiếu đơn vị trực tuyến (OpenAlex/Crossref/ORCID) → tra cứu đều hoạt động đúng trên DB cô lập, có bằng chứng truy vết đầy đủ.
- Ca thiếu bằng chứng affiliation được xử lý đúng (không bịa dữ liệu).
- Ca lỗi nhập CSV hiển thị thông báo rõ ràng.
- Phân quyền ADMIN/REVIEWER/LECTURER hoạt động đúng, kể cả tài khoản LECTURER chưa liên kết hồ sơ.
- VI/EN nhất quán trên các màn hình đã kiểm.

Khuyến nghị khóa phiên bản hiện tại (commit nền `731fa8f`), kèm theo việc ghi nhận và lên lịch sửa MINOR nêu trên trong một nhiệm vụ riêng (không sửa trong nhiệm vụ nghiệm thu này theo đúng ràng buộc).

---

*Báo cáo này không sửa code sản phẩm, không migrate/seed App DB hoặc DB demo, không push GitHub, không commit thay đổi chức năng — đúng ràng buộc của nhiệm vụ.*

---

## Đính chính 17/10/2026 (bổ sung, không sửa nội dung gốc ở trên)

Xác minh lại trong lượt rà soát release ngày 17/10 (chi tiết: [`RELEASE_READINESS_20261017.md`](RELEASE_READINESS_20261017.md)).

1. **Commit đã test:** HEAD thực tế lúc test là `237f7bc`, không phải `731fa8f`. `731fa8f..237f7bc` chỉ khác 1 file tài liệu (`DASHBOARD_REAL_DATA_CHARTS_ACCEPTANCE.md`), nên code được test giống hệt `731fa8f`.
2. **Phạm vi thu thập trực tuyến (mục B.2–B.4):** job chỉ truy vấn **300/635 DOI hợp lệ** do `AFFILIATION_ONLINE_MAX_DOIS_PER_RUN=300` (mặc định). Các DOI được chọn tất định (EID tăng dần), nên mọi lần chạy lại đều lấy đúng 300 DOI đó. Con số "Không có bài ở nguồn nào: 364" ở Preview gồm **335 DOI chưa từng được truy vấn** + 4 DOI đã truy vấn nhưng không có ở nguồn + 25 bài không có DOI. 1.445/2.751 vị trí tác giả mang `UNRESOLVED/NO_EXTERNAL_WORK` chỉ vì DOI chưa được truy vấn. Vì vậy các số 106 tổ chức / 1.711 dòng đơn vị **không** phản ánh mức bao phủ thật của nguồn. Bộ nguồn offline đã nghiệm thu 11/10 cho 217 / 4.147.
3. **Bước "trạng thái chưa có dữ liệu nghiệp vụ"** của Giai đoạn B **không được thực hiện** ngày 16/10. Bằng chứng import CSV mới qua browser lấy từ phiên 11/10 (`NO_JSON_FULL_E2E_20261011.md` §5.1), không phải từ phiên 16/10.
4. **Bằng chứng phiên 16/10** chỉ gồm nội dung trang và truy vấn ghi trong transcript phiên làm việc, cùng 3 tệp bundle trong `backend/.tmp_csvonly_affiliation_cache/`. Không có ảnh chụp lưu trong repo.
5. Sau phiên 16/10, cụm PostgreSQL 55432 dừng không sạch (khoảng 15:42). Ngày 17/10 đã khởi động lại bằng `pg_ctl`, tự phục hồi WAL thành công.
6. **Đối chứng với bộ nguồn offline đã nghiệm thu** (`_du_lieu_demo_14_10/affiliation_survey`, `sha256sum -c` 10/10 OK): bộ này đã truy vấn **635/635** DOI. Trong đó 629 có dữ liệu, **6 đã truy vấn nhưng không tìm thấy**, 0 chưa truy vấn; cộng 25 bài không có DOI thành 31 bài không có ở nguồn nào. Vậy 364 ở chế độ trực tuyến **không** nói lên việc nguồn ngoài thiếu dữ liệu: phần lớn (335) là DOI chưa được truy vấn.
