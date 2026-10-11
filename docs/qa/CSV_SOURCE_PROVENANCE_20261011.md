# Xác minh nguồn CSV và lịch sử import (11/10/2026)

Chỉ kiểm tra READ-ONLY (đọc tệp, đọc DB bằng phiên `default_transaction_read_only=on`, đọc log). Không upload, không import JSON, không matching, không sửa code/DB, không restart tiến trình, không commit.

Kịch bản xác nhận: **CSV-ONLY** — giảng viên 0, công bố 660, tác giả 1.207, ứng viên 0 là trạng thái đúng kỳ vọng. Không đề xuất phục hồi 410 giảng viên.

## 1. CSV gốc

| Mục | Giá trị |
|---|---|
| Đường dẫn đầy đủ | `D:\DataFolder\ProjectIctu\DoAn\Truong_Quang_Huy_Scopus_Sep2026.csv` |
| Phần mở rộng thực tế | `.csv` (Explorer ẩn đuôi; `file` xác nhận "CSV Unicode text, UTF-8 (with BOM)") |
| Kích thước / mtime | 1.277.558 byte / 26/09/2026 17:16:58 |
| SHA-256 | `6a62fcf637b4244a66791e6a7ada84893fcd84ed7cf5c09dee81b8e34d7bf75d` |
| Encoding / xuống dòng | UTF-8 **có BOM**, ký tự xuống dòng LF (661 LF, 0 CRLF) |
| Header | 22 cột: Authors, Author full names, Author(s) ID, Title, Year, Source title, Volume, Issue, Art. No., Page start, Page end, Cited by, DOI, Link, Abstract, Author Keywords, Publisher, Document Type, Publication Stage, Open Access, Source, EID |
| Dòng dữ liệu | 660 (661 dòng vật lý gồm header); 660 EID khác nhau |

`ictu_lecturers_20261010_090704.json` (560.352 byte) nằm cùng thư mục, **không** được dùng trong E2E (0 giảng viên ở cả hai DB).

### Bản sao trùng tên / trùng hash trên máy (quét `D:\DataFolder\ProjectIctu`, `Downloads`, `Desktop`, `Documents`)

| Đường dẫn | Kích thước | SHA-256 (16 ký tự đầu) | Kết luận |
|---|---|---|---|
| `DoAn\Truong_Quang_Huy_Scopus_Sep2026.csv` | 1.277.558 | `6a62fcf637b4244a` | **bản gốc** |
| `DoAn\_bao_toan_truoc_14_10\restore_test\stash_restore_1\data\scopus\Truong_Quang_Huy_Scopus_Sep2026.csv` | 1.277.558 | `6a62fcf637b4244a` | **trùng hash** (bản sao trong thư mục bảo toàn) |
| `DoAn\_quan_ly_do_an\tests\t16_upload\scopus_660.csv` | 1.277.558 | `6a62fcf637b4244a` | **trùng hash**, khác tên (tệp test của nhiệm vụ cũ) |
| `DoAn\Scopus-Ictu\data\scopus\Truong_Quang_Huy_Scopus_Sep2026.csv` | 1.278.219 | `fa2e2a48ef325590` | **trùng tên, khác hash**: cùng nội dung nhưng dòng CRLF; mtime 03/10/2026; nằm trong `.gitignore` (không vào Git) |

Hai biến thể (LF/CRLF) có đúng 660 bản ghi bằng nhau sau khi chuẩn hóa xuống dòng (kiểm tra ở báo cáo E2E). Không có bản nào khác trùng hash hoặc cùng kích thước ngoài bốn tệp trên.

## 2. Lịch sử import — hai môi trường tách biệt

### A. Frontend 5173 / backend 8001 → `scopus_ictu_app`
- Chứng minh: PID 3948 (cổng 8001) có 3 kết nối tới 55432, cả ba trong `pg_stat_activity` thuộc `scopus_ictu_app` (user `scopus_demo_user`).
- Giao diện 5173 hiện ở trang đăng nhập (không có phiên); tôi **không** đăng nhập thay người dùng, nên không đọc được lịch sử qua giao diện 5173. Lịch sử lấy từ DB mà trang `/imports` hiển thị.

| Batch | Tệp | SHA-256 | Trạng thái | Tạo lúc | Raw | Tài khoản ghi trong audit |
|---|---|---|---|---|---|---|
| `46c2b7df-62a5-43fa-a7ad-23e1f262d6b6` | `Truong_Quang_Huy_Scopus_Sep2026.csv` | `6a62fcf6…` (**= bản gốc**) | APPLIED | 11/10 21:47:20 | 660 | `admin@ictu.edu.vn` (actor_type USER) |

Chuỗi audit: `SCOPUS_IMPORT_STARTED` 21:47:20 → `SCOPUS_IMPORT_COMPLETED` 21:47:21 → `SCOPUS_NORMALIZATION_TRIGGERED` 21:47:54 (660 mới, 0 lỗi).

### B. Frontend 5183 / backend 8011 → `scopus_ictu_test_csvonly_20261011`
- Chứng minh khi chạy: kết nối của PID 28416 (cổng 8011) thuộc DB test (đã ghi trong báo cáo E2E). Hai tiến trình 5183/8011 đã được tôi tắt cuối E2E; **tôi không khởi động lại** để chỉ đọc giao diện — DB là nguồn mà trang `/imports` đọc, ảnh `02_nhap_du_lieu_lich_su` trong `docs/qa/csv_only_e2e_20261011/` là ảnh chụp lúc đó.

| Batch | Tệp | SHA-256 | Trạng thái | Tạo lúc | Raw | Ai thực hiện |
|---|---|---|---|---|---|---|
| `e74d648b-bddc-44b7-b735-619c735f7888` | `Truong_Quang_Huy_Scopus_Sep2026.csv` | `6a62fcf6…` (**= bản gốc, từng byte**) | APPLIED | 22:16:05 | 660 | Tài khoản `e2e.admin@ictu.edu.vn` — **người thao tác không xác định được** |
| `cca5b589-be7c-432a-846d-0c18462b13c7` | `Truong_Quang_Huy_Scopus_Sep2026.csv` | `5494b864…` (= bản gốc **bỏ 3 byte BOM**) | CANCELLED | 22:31:23 (hủy 22:31:42) | 660 | **Claude** (script kiểm thử) |
| `1f460e0b-5bf5-4574-8bc7-72fee87ca7c5` | `thieu_cot_EID.csv` (tệp giả tự tạo, thiếu cột EID) | `2bdd76f8…` | FAILED `MISSING_EID_COLUMN` | 22:32:17 | 0 | **Claude** (ca âm tính) |

Chuỗi audit của batch `e74d648b`: IMPORT_STARTED 22:16:05 → COMPLETED 22:16:05 → NORMALIZATION_TRIGGERED 22:18:40 (Claude bấm) → bóc tách tác giả (Claude bấm, 22:19:29 `APPLIED`).

## 3. Đối chiếu dữ liệu DB với CSV gốc (chạy lại hôm nay, độc lập, chỉ đọc)

| Kiểm tra | App DB (`46c2b7df`) | DB test (`e74d648b`) | DB test (`cca5b589`, đã hủy) |
|---|---|---|---|
| Dòng raw / dòng CSV | 660 / 660 | 660 / 660 | 660 / 660 |
| Lệch EID, Title, DOI, Source title | 0 | 0 | 0 |
| Lệch Authors, Author full names, Author(s) ID | 0 | 0 | 0 |
| Lệch ở bất kỳ ô nào trong 22 cột | 0 | 0 | 0 |
| Công bố: thiếu / thừa / lệch DOI / lệch Title / lệch `source_title` | 0 / 0 / 0 / 0 / 0 (660 công bố) | 0 / 0 / 0 / 0 / 0 (660 công bố) | — |
| Chuỗi (thứ tự, Scopus ID) tác giả đúng | 660/660 bài | 660/660 bài | — |
| Tác giả / liên kết | 1.207 / 2.751 | 1.207 / 2.751 | — |
| Nguồn của `publication_raw_sources` | 660, đều từ `46c2b7df` | 660, đều từ `e74d648b` | 0 (đợt hủy không sinh công bố) |
| Giảng viên / ứng viên | 0 / 0 | 0 / 0 | — |

Nội dung dữ liệu của cả hai DB khớp từng ô với CSV gốc. Đợt `cca5b589` cũng khớp nội dung nhưng khác hash do mất BOM.

## 4. Chứng minh được gì, không chứng minh được gì

**Chứng minh được (bằng bằng chứng):**
- Hai batch `46c2b7df` (App DB) và `e74d648b` (DB test) có `file_sha256` **bằng đúng** SHA-256 của `DoAn\Truong_Quang_Huy_Scopus_Sep2026.csv` — cùng từng byte với tệp đó (và với hai bản sao trùng hash ở mục 1).
- Dữ liệu raw/công bố/tác giả của hai DB khớp từng ô với CSV đó.

**Không chứng minh được:**
- *Đường dẫn upload*: hệ thống chỉ lưu tên tệp + SHA-256, không lưu đường dẫn. Vì ba tệp (bản gốc, bản trong `stash_restore_1`, `scopus_660.csv`) cùng hash, **không thể phân biệt** người dùng chọn tệp nào trong ba tệp đó; tên `Truong_Quang_Huy_Scopus_Sep2026.csv` nghiêng về bản gốc hoặc bản `stash_restore_1`, nhưng đó là suy luận, không phải bằng chứng. Bản `data\scopus` (CRLF) **bị loại trừ** vì hash khác.
- Không tìm thấy manifest/log upload riêng ngoài `scopus_imports`, `audit_events` và log uvicorn (log chỉ ghi `POST /api/v1/imports/scopus 202`, không ghi tên tệp hay đường dẫn).
- *Người thao tác* của batch `46c2b7df` và `e74d648b`: audit chỉ ghi tài khoản đăng nhập, không ghi danh tính người ngồi trước máy.

## 5. Ai làm bước nào

| Bước | Thực hiện bởi | Căn cứ |
|---|---|---|
| Tạo DB test, backend 8011, frontend 5183, tài khoản `e2e.admin@ictu.edu.vn`, đăng nhập vào 5183 | **Claude** | lệnh trong phiên; audit `DEMO_ADMIN_BOOTSTRAPPED` 22:08 và 22:15 |
| Batch `e74d648b` (22:16:05): upload tệp CSV | **Không xác định.** Không phải lệnh upload của Claude | (a) lệnh Claude gần nhất là đăng nhập (22:15:42) và `grep` route (22:16:02), lệnh kế tiếp 22:17:10; không lệnh nào có `input[type=file]`/`FormData`/`imports/scopus`; (b) hash khớp từng byte với đĩa — kiểu upload bằng script của Claude luôn làm mất BOM (batch `cca5b589` chứng minh), nên khớp hơn với chọn tệp thật qua hộp thoại. Đây là **dấu hiệu**, không phải chứng minh danh tính; tôi không gán cho ai |
| Bấm "Chuẩn hóa dữ liệu" 22:18:40; bấm "Bóc tách tác giả" | **Claude** | lệnh trong phiên lúc 22:18:39 và 22:19:10 |
| Batch `cca5b589` (tải lại, mất BOM, rồi hủy) | **Claude** | lệnh ở 22:31:06 (`File` tạo từ `fetch().text()`); hủy 22:31:42 |
| Batch `1f460e0b` (thiếu cột EID) + upload `.txt` bị chặn phía client | **Claude** | lệnh ở 22:32:09 |
| Một `POST /imports/scopus` trả 409 ngay sau đó (không tạo batch) | **Claude (gián tiếp)** | xảy ra trong lúc script ca âm tính chạy; lý do chi tiết 409 không có trong log |
| Batch `46c2b7df` trên App DB (21:47) và thao tác chuẩn hóa (21:47:54) | **Không phải Claude** — xảy ra trước khi E2E bắt đầu (22:06); mọi kết nối của Claude tới App DB là chỉ-đọc | audit: tài khoản `admin@ictu.edu.vn`; bạn cho biết đã tự thử trạng thái không có JSON, nhưng log không ghi danh tính |
| Đọc và đối chiếu App DB, đối chiếu DB test, đọc log | **Claude (chỉ kiểm tra)** | |

## 6. Có dấu hiệu nhập nhầm file / nhầm DB không?

- **Nhầm file:** không. Cả hai batch chính dùng đúng nội dung `6a62fcf6…`, 660 dòng, không phải `data\scopus` (CRLF, hash khác) hay JSON giảng viên.
- **Nhầm DB:** không. 5173→8001→`scopus_ictu_app`; 5183→8011→DB test; số liệu hai DB khớp nhau nhưng là hai tập hợp độc lập (khác batch ID); App DB không bị Claude ghi.
- **Đính chính lỗi của tôi trong báo cáo E2E:** tôi từng ghi "tải lại cùng tệp (cùng SHA-256) vẫn tạo đợt mới, GAP không phát hiện trùng". **Sai.** Hash của bản tải lại khác (`5494b864…`) vì script của tôi làm mất BOM nên cơ chế phát hiện trùng của hệ thống (HTTP 409 `DUPLICATE_IMPORT_CONFIRMATION_REQUIRED`, `allow_duplicate`) không kích hoạt. Đã sửa trong `CSV_ONLY_E2E_20261011.md` (mục 2e, GAP 6, dòng I). Đường 409 với tệp byte-giống-hệt **chưa được kiểm thực nghiệm**.
- **Rủi ro còn lại:** batch `cca5b589` (đã hủy) còn 660 dòng raw trong DB test; không ảnh hưởng công bố/tác giả. Không phải vấn đề của App DB.
- **Giới hạn:** không đọc được lịch sử trên giao diện 5173 (chưa đăng nhập, tôi không nhập mật khẩu) và 5183 (đã tắt, không khởi động lại).
