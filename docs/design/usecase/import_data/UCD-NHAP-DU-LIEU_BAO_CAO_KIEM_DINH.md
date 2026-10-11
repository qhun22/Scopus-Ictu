# Use Case Diagram — Phân hệ Nhập dữ liệu: Báo cáo kiểm định

Sơ đồ: `UCD-NHAP-DU-LIEU.pdf` (A4 dọc, 1 trang) · nguồn: `UCD-NHAP-DU-LIEU.puml` · vector: `render/UCD-NHAP-DU-LIEU.svg` · xem trước: `render/UCD-NHAP-DU-LIEU.png`.
Dựng lại: `python build_ucd_nhap_du_lieu.py` rồi `python build_pdf.py` (cùng thư mục).
Nguồn Task 19 (`usecase/diagrams/UCD-1_nhap_du_lieu.puml`, `specs/UCS-G1_nhap_du_lieu.md`, `UC_INVENTORY.md`…) **không bị sửa**.

> **Lưu ý trạng thái mã nguồn.** AS-IS lấy từ cây làm việc ngày 11/10/2026. Ba hành vi sau đã có trong code nhưng **chưa commit** (làm trong phiên 11/10) và chưa có trong tài liệu Task 19: (a) hủy bản xem trước JSON được ghi lại là đợt «Đã hủy»; (b) phát hiện trùng nội dung cho JSON (so SHA‑256, chỉ áp dụng với các lần nhập từ khi bắt đầu lưu mã băm); (c) hủy được đợt CSV đã `STAGED` nhưng chưa chuẩn hóa. Nếu commit bị bỏ, sơ đồ cần cập nhật tương ứng.

## 1. Actor và quyền

| Actor | Bằng chứng | Kết luận |
|---|---|---|
| **Quản trị viên (ADMIN)** | `backend/app/api/v1/endpoints/imports.py:44` (`AdminUser = require_role("ADMIN")`, dùng cho mọi route `/imports…`); `lecturers.py:1005,1075,1136,1202` (`require_role("ADMIN")` cho preview/import/cancel/rollback); `frontend/src/App.tsx:92-94` (`/imports` nằm trong `RoleRoute allowedRoles=["ADMIN"]`) | Actor duy nhất |
| REVIEWER, LECTURER | Cùng các route trên → 403 (xem `usecase/RBAC_API_MATRIX.csv`, test `test_import_requires_admin_role`, `test_non_admin_upload_is_forbidden`) | Không có quyền nhập; không vẽ |
| Hệ thống ngoài (Scopus, PostgreSQL, tiến trình nền, bộ phân tích CSV) | CSV do người dùng tự xuất từ Scopus rồi tải lên (`POST /imports/scopus`); không có lời gọi API Scopus; DB/tiến trình nền là thành phần nội bộ | **Không** là Actor |
| Kỹ thuật viên (script CLI UC‑25) | `backend/scripts/ingest_craw_known_publications.py`… không đi qua `/imports` | Ngoài phạm vi sơ đồ này (xem §6) |

## 2. Use Case đã chọn và truy vết

ID `UC-N#` là nhãn nội bộ của sơ đồ này; cột "Task 19" cho biết nguồn tương ứng.

| UC trên sơ đồ | Actor | API (backend) | Giao diện `/imports` | FR / Task 19 | Bằng chứng code |
|---|---|---|---|---|---|
| **Nhập dữ liệu từ tệp** *(trừu tượng)* | — (không có actor trực tiếp) | — | — | khái quát hóa mới | `schemas/scopus_import.py:46,59` (`ImportType = SCOPUS \| LECTURERS`, một mô hình đợt nhập chung); `list_imports` hợp nhất hai loại đợt (`scopus_import_service.py:425`) |
| **UC-N1 Nhập tệp CSV công bố Scopus** | ADMIN | `POST /api/v1/imports/scopus` (202 + tiến trình nền); `GET /imports/config` | tải CSV → «Kiểm tra dữ liệu» (`Imports/index.tsx:545 startImport`) | UC-10 · FR-013 | `imports.py:55-60,125`; `scopus_import_service.py:119 create_import_job` |
| **UC-N2 Nhập tệp JSON danh sách giảng viên** | ADMIN | `POST /api/v1/lecturers/import/preview` (không ghi DB) → `POST /api/v1/lecturers/import` (một giao dịch) | tải JSON → «Kiểm tra dữ liệu» → «Xác nhận nhập» (`handleConfirmLecturerImport:656`) | UC-08 · FR-010, FR-011 | `lecturers.py:1005,1075`; `lecturer_dataset/importer.py:503 import_dataset` |
| **Xử lý cảnh báo tệp trùng** («extend» *Nhập dữ liệu từ tệp*) | ADMIN | CSV: `POST /imports/scopus` → 409 `DUPLICATE_IMPORT_CONFIRMATION_REQUIRED`, gửi lại với `?allow_duplicate=true`; JSON: `POST /lecturers/import/preview` → cùng mã 409 và tham số | hộp thoại «Tệp dữ liệu đã được nhập trước đó»: Hủy / Xem đợt trước / Vẫn nhập lại (`DuplicateImportDialog`, `Imports/index.tsx:1309`; `LecturerDatasetImportCard.tsx:343`) | UC-10 luồng A2 · FR-013 | `scopus_import_service.py:136`; `lecturers.py` (preview, `allow_duplicate`); `scopus_import_service.py:299 find_duplicate_lecturer_import` |
| **Hủy tiến trình nhập** («extend» *Nhập dữ liệu từ tệp*) | ADMIN | CSV: `POST /imports/{id}/cancel`; JSON: `POST /lecturers/import/cancel` (ghi đợt «Đã hủy», không đụng dữ liệu giảng viên) | nút «Hủy tiến trình» ở khung kết quả (`cancelPendingImport:617`, `cancelLecturerPreview:637`) | UC-10a · FR-014 | `imports.py:263`; `scopus_import_service.py:193-205` (cho phép hủy khi đang chạy hoặc `STAGED` chưa chuẩn hóa); `lecturers.py:1136` |
| **UC-N6 Hoàn tác đợt nhập giảng viên** («extend» *UC-N2*) | ADMIN | `POST /imports/{id}/rollback` (cùng dịch vụ với `/lecturers/import/{id}/rollback`) | «Xóa» đợt JSON chưa hoàn tác → hộp «Cần hoàn tác trước khi xóa» → «Hoàn tác đợt nhập» (`Imports/index.tsx:2285-2303`) | UC-08a · FR-012 | `imports.py:233`; `lecturers.py:1202`; `lecturer_dataset/rollback.py:69` |
| **UC-N7 Xem lịch sử các đợt nhập** | ADMIN | `GET /imports`, `GET /imports/history` | bảng đợt nhập, tìm kiếm, thẻ lọc trạng thái | UC-10 (API liệt kê) · FR-013 | `imports.py:136`; `scopus_import_service.py:425 list_imports` |
| **UC-N8 Xem chi tiết đợt nhập** | ADMIN | `GET /imports/{id}` | nút «Chi tiết» (số bản ghi, lỗi theo dòng, trạng thái) | UC-10 · FR-013 | `imports.py:291`; `Imports/index.tsx:688 openDetail` |
| **UC-N10 Xóa đợt nhập** | ADMIN | `DELETE /imports/{id}` | nút «Xóa» → hộp «Xóa đợt nhập dữ liệu?» / «Xóa lịch sử nhập dữ liệu?» | UC-10a · FR-014 | `imports.py:207`; `scopus_import_service.py:735 delete_scopus_import`, `:823 delete_lecturer_import_history`; `Imports/index.tsx:739` |
| **Ẩn đợt nhập khỏi lịch sử** («extend» *UC-N10*) | ADMIN | `POST /imports/{id}/archive` | hộp «Không thể xóa đợt nhập» → «Ẩn khỏi lịch sử» (`handleConfirmArchive:896`) | UC-10a · FR-014 | `imports.py:155`; `scopus_import_service.py:1463 archive_import_history` |

## 3. Quan hệ UML — lý do và bằng chứng

| Quan hệ | Ký hiệu | Lý do nghiệp vụ | Bằng chứng |
|---|---|---|---|
| ADMIN — 5 UC (N1, N2, N7, N8, N10) | Association | Các mục tiêu ADMIN khởi tạo trực tiếp | Route ADMIN (§1) |
| UC-N1, UC-N2 → *Nhập dữ liệu từ tệp* | **Generalization** | Hai loại đợt cùng một mô hình `type` và lịch sử/trạng thái chung; cả hai dùng chung cảnh báo trùng và hủy tiến trình. Luồng riêng vẫn tách ở hai UC con | `ImportType`, `list_imports` hợp nhất; hộp trùng dùng chung một component |
| *Xử lý cảnh báo tệp trùng* → *Nhập dữ liệu từ tệp* | «extend» | Chỉ xảy ra **khi** tệp trùng nội dung; không trùng thì luồng nhập chạy thẳng. Đúng ngữ nghĩa extend (hành vi có điều kiện) | 409 chỉ khi `previous is not None and not allow_duplicate` |
| *Hủy tiến trình nhập* → *Nhập dữ liệu từ tệp* | «extend» | Tùy chọn của ADMIN khi đợt chưa hoàn tất/chưa xác nhận | `cancel_import` từ chối đợt đã kết thúc (409 `IMPORT_ALREADY_FINISHED`) |
| *UC-N6 Hoàn tác* → *UC-N2* | «extend» | Tùy chọn sau khi đã nhập; chỉ áp dụng cho JSON giảng viên | rollback chỉ cho đợt giảng viên (đã khớp Task 19) |
| *Ẩn đợt nhập* → *UC-N10 Xóa đợt nhập* | «extend» | Được đề xuất **khi** không xóa được vì đợt đang được sử dụng | `handleDeleteIntent` → `blockedDeleteState SCOPUS_IN_USE` → xác nhận gọi `archive` (`Imports/index.tsx:739`, `:2285-2303`) |

**Không vẽ «include».** Phân tích: bước "kiểm tra tệp" có ở cả hai luồng nhưng cài đặt khác nhau (CSV nằm trong `POST /imports/scopus`; JSON là API `preview` riêng, chỉ-đọc) và chỉ là một bước của luồng, không phải mục tiêu độc lập hay hành vi dùng chung đã được tách trong code. Vì vậy được mô tả trong đặc tả luồng (§5), không tách thành UC.

## 4. Ứng viên bị loại (và lý do)

| Ứng viên | Quyết định | Lý do |
|---|---|---|
| Kiểm tra dữ liệu / xem trước | Không là UC | Bước trong luồng nhập (xem §3). Với CSV, nút «Kiểm tra dữ liệu» thực chất **tải lên và tạo đợt nhập** (`startImport`) |
| Xác nhận nhập (CSV) | Không là UC | Chỉ đóng khung kết quả, **không gọi API** (`confirmPendingImport:600`); đợt đã được lưu từ lúc tải lên |
| Hủy chọn tệp | Không là UC | Thao tác giao diện, không gọi API; khác «Hủy tiến trình nhập» |
| Xem đợt trước (trong hộp trùng) | Không vẽ quan hệ riêng | Điều hướng sang *Xem chi tiết đợt nhập* (`viewDuplicateImport:957`); ghi trong đặc tả |
| Khôi phục hiển thị (restore-history) | Không vẽ | Có API và nút, nhưng giao diện chỉ dùng bộ lọc `archiveFilter="active"` (`Imports/index.tsx:120,1615` — không có chỗ chọn «đã ẩn») nên đợt đã ẩn không hiện ra → **không tới được từ UI** (hỏi GVHD/sinh viên, xem §7) |
| Trạng thái «Thành công/Cảnh báo/Đang xử lý/Lỗi» | Không là UC | Trạng thái của đợt nhập, không phải mục tiêu |
| Chuẩn hóa công bố / bóc tách tác giả | Ngoài phạm vi | UC-11/UC-12 (nhập ≠ chuẩn hóa); chỉ có liên kết điều hướng ở chi tiết đợt |
| Script nạp Craw, OpenAlex/Crossref (UC-25) | Ngoài phạm vi sơ đồ chính | Chạy bằng CLI, không qua `/imports`; đề xuất sơ đồ con riêng (Kỹ thuật viên) nếu GVHD muốn |
| Đặt lại toàn hệ thống (Dashboard) | Ngoài phạm vi | Khác «Xóa đợt nhập»: xóa toàn bộ dữ liệu ứng dụng, không thuộc phân hệ nhập |

## 5. Đặc tả ngắn — Use Case «Nhập dữ liệu» (hai luồng khác nhau)

**Actor:** ADMIN. **Điều kiện tiên quyết chung:** đã đăng nhập bằng tài khoản ADMIN đang hoạt động; vào `/imports`; tệp đúng đuôi và không vượt giới hạn kích thước.

### 5.1 UC-N1 — Nhập tệp CSV công bố Scopus (lưu dữ liệu thô ngay)
- **Luồng thành công:** (1) ADMIN chọn tệp `.csv` xuất từ Scopus. (2) Bấm «Kiểm tra dữ liệu». (3) Hệ thống kiểm tra đuôi/kích thước/rỗng, tính SHA‑256, tạo đợt nhập (202) và xử lý nền: ghi từng dòng vào dữ liệu thô, đếm hợp lệ/lỗi. (4) Giao diện hiện khung kết quả (tổng, hợp lệ, lỗi, tiến độ) và đợt xuất hiện trong lịch sử. (5) ADMIN bấm «Xác nhận nhập» — chỉ đóng khung kết quả; đợt chuyển sang «Chờ chuẩn hóa».
- **Luồng thay thế:** hủy chọn tệp (không gọi API); «Hủy tiến trình» (`POST /imports/{id}/cancel`); xem chi tiết.
- **Tệp/dữ liệu không hợp lệ:** sai đuôi → 422 `UNSUPPORTED_IMPORT_FORMAT`; rỗng → `EMPTY_IMPORT_FILE`; quá lớn → 413; thiếu cột `EID` (không phải bản xuất Scopus) → bị từ chối; dòng sai → ghi INVALID kèm lý do, không dừng cả đợt; lỗi lưu → `FAILED`.
- **Tệp trùng:** cùng nội dung đang xử lý → 409 `IMPORT_ALREADY_PROCESSING` (kèm đợt đang chạy); đã nhập xong → 409 `DUPLICATE_IMPORT_CONFIRMATION_REQUIRED` → hộp thoại: **Hủy** (không nhập lại, không tạo bản ghi), **Xem đợt trước** (mở chi tiết đợt cũ), **Vẫn nhập lại** (gửi lại `allow_duplicate=true`, tạo đợt mới). Cảnh báo trùng **không** chặn mọi lần nhập lại.
- **Điều kiện kết thúc:** dòng thô đã lưu bất biến; **chưa** có công bố chuẩn hóa nào (đó là UC chuẩn hóa); có audit.

### 5.2 UC-N2 — Nhập tệp JSON danh sách giảng viên (xem trước rồi mới ghi)
- **Luồng thành công:** (1) ADMIN chọn tệp `.json`. (2) «Kiểm tra dữ liệu» → `preview`: kiểm schema, đếm tạo mới/cập nhật/không đổi/cảnh báo; **không ghi DB**. (3) ADMIN xem khung kết quả. (4) «Xác nhận nhập» → `POST /lecturers/import`: một giao dịch ghi hồ sơ, bản chụp nguồn, công bố đã biết, audit. (5) Đợt xuất hiện trong lịch sử.
- **Luồng thay thế:** «Hủy tiến trình» → `POST /lecturers/import/cancel` ghi đợt «Đã hủy» (không đổi dữ liệu giảng viên); hoàn tác đợt đã nhập (UC‑N6).
- **Không hợp lệ:** sai đuôi `UNSUPPORTED_IMPORT_FORMAT`; JSON sai cú pháp/schema, email trùng trong tệp → 422; xung đột định danh → chặn trước khi ghi; lỗi DB → 503 và rollback.
- **Tệp trùng:** `preview` trả 409 `DUPLICATE_IMPORT_CONFIRMATION_REQUIRED` nếu đã có đợt nhập cùng mã băm chưa bị hoàn tác/ẩn; cùng ba hành động như CSV; «Vẫn nhập lại» gọi lại `preview` với `allow_duplicate=true`. Nhập lại vẫn idempotent ở tầng dữ liệu (không sinh bản ghi trùng).
- **Điều kiện kết thúc:** thành công → hồ sơ + audit đã lưu, giảng viên vắng mặt trong tệp không bị xóa; lỗi/hủy → dữ liệu giảng viên không đổi.

**Khác biệt cốt lõi CSV vs JSON:** CSV ghi dữ liệu thô **ngay khi tải lên** (không có bước xem trước ghi/không ghi); JSON **xem trước chỉ-đọc** rồi mới ghi vào danh sách giảng viên.

## 6. Cổng kiểm định

### Cổng A — SEMANTIC: **PASS**
| Tiêu chí | Kết quả |
|---|---|
| Actor đúng; RBAC đúng | ADMIN duy nhất; đối chiếu `require_role` + `RoleRoute` (§1) ✔ |
| UC đúng mục tiêu, đúng chức năng đã triển khai | 9 UC cụ thể + 1 UC trừu tượng, mỗi UC có API/UI/bằng chứng (§2); UC chỉ-API/UI-không-tới-được (khôi phục) không vẽ ✔ |
| Include/extend/generalization có lý do | §3 ✔ (không có include vô căn cứ) |
| Không nhầm CSV/JSON | hai UC con tách riêng + đặc tả hai luồng (§5) ✔ |
| Xóa lịch sử ≠ xóa dữ liệu; nhập ≠ chuẩn hóa; hủy chọn tệp ≠ hủy tiến trình; cảnh báo trùng ≠ chặn mọi lần nhập lại; CSV ≠ tích hợp Scopus API | §4, §5 ✔ |
| Truy vết tới code | §2 ✔ |

### Cổng B — A4 VISUAL: **PASS**
Đo trên bản PDF xuất cuối (render lại từ PDF để xem bằng mắt; số đo bằng engine in của Chrome):
| Tiêu chí | Kết quả |
|---|---|
| PDF A4 dọc thật, 1 trang | 209,9 × 297,0 mm, 1 trang ✔ |
| Toàn vector | 0 ảnh raster; font Segoe UI nhúng ✔ |
| Lề an toàn | nội dung từ x = 15 mm đến 195 mm (lề 15 mm hai bên) ✔ |
| Cỡ chữ in | nhãn Use Case 10,6 pt; nhãn «extend»/chú giải 9,3 pt (≥ 9 pt) ✔ |
| Hình chiếm trang | hình rộng 180 mm × cao 182 mm (kín bề ngang; phần dưới là chú giải + ghi chú, trống cuối trang ≈ 26 mm) ✔ |
| Không cắt/đè/chéo | không phần tử bị cắt; mọi chữ nằm trong ellipse; đường nối không xuyên ellipse; không giao cắt; nhãn «extend» không đè đường (đã sửa 1 lỗi đè nhãn khi xem PDF) ✔ |
| Actor ngoài ranh giới; tên hệ thống trong khung chữ nhật | ✔ |
| Không dải ngang nhỏ | bố cục 2 cột dọc, tỷ lệ gần vuông, phủ chiều rộng trang ✔ |

**FINAL: Cổng A PASS + Cổng B PASS.** Cổng nhất quán Task 19 (`check_consistency.py`): thư mục mới không thêm lỗi (51 lỗi sẵn có từ trước, thuộc tài liệu Task 20, không liên quan).

## 7. Điểm cần hỏi GVHD / sinh viên quyết định
1. **Khái quát hóa «Nhập dữ liệu từ tệp»**: dựa trên mô hình đợt nhập chung (`type`). Nếu GVHD không muốn dùng generalization, có thể thay bằng nối «extend» từ *Xử lý cảnh báo trùng* và *Hủy tiến trình* tới từng UC con (sơ đồ có thêm 4 đường).
2. **«Duyệt kết quả trước khi áp dụng» (PI‑3.3):** JSON có xem trước chỉ-đọc; CSV lưu thô ngay và «Xác nhận nhập» chỉ là thao tác giao diện. GVHD có coi bước chuẩn hóa (UC‑11) là "áp dụng" không?
3. **«Khôi phục hiển thị»:** có API và nút nhưng giao diện không có đường xem đợt đã ẩn → nên bổ sung bộ lọc hoặc loại khỏi phạm vi nghiệm thu.
4. **Xóa đợt CSV** thực sự xóa đợt và dòng thô (nếu chưa được dùng), còn **JSON** chỉ ẩn lịch sử sau hoàn tác — cần ghi rõ trong báo cáo để không bị hiểu là cùng một hành vi.
5. **Script CLI (UC‑25)** có cần sơ đồ con riêng với Actor «Kỹ thuật viên» không?
6. Ba hành vi chưa commit (xem đầu báo cáo) cần được commit cùng tài liệu để bảng truy vết khớp mã.
