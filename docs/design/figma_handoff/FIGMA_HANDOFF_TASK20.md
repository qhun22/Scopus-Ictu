# Bàn giao đầu vào cho Task 20 — Thiết kế giao diện Figma (PI-2.3)

> **TRẠNG THÁI: CHƯA CÓ FIGMA.** Task 19 **không** tạo tệp Figma, **không** có công cụ/connector Figma trong phiên làm việc, và **không** thay thế Figma bằng PNG/SVG. Tài liệu này chỉ chuẩn bị đầu vào để Task 20 và sinh viên dựng thiết kế bám sát phần mềm đang chạy.
> Máy đọc được: `screens.json` (cùng thư mục). Đề cương PI-2.3 (đọc lại từ PDF): *"Có bản thiết kế giao diện bằng Figma cho màn hình danh sách, chi tiết, nhập dữ liệu, so sánh trước/sau chuẩn hóa, hàng đợi phê duyệt và thống kê."*

## 1. Sáu màn bắt buộc theo PI-2.3 (bám đề cương)

| Mã | Màn theo đề cương | Màn thật trong phần mềm | Route hiện tại | Vai trò | **Trạng thái UI** |
|---|---|---|---|---|---|
| **FG-01** | Danh sách | Danh sách công bố | `/publications` | ADMIN, REVIEWER | **ĐÃ TRIỂN KHAI** |
| **FG-02** | Chi tiết | Chi tiết công bố (đơn vị theo từng tác giả, nguồn gốc) | `/publications/:eid` | ADMIN, REVIEWER | **ĐÃ TRIỂN KHAI** |
| **FG-03** | Nhập dữ liệu | Nhập dữ liệu (JSON hồ sơ giảng viên + CSV Scopus) | `/imports` | ADMIN | **ĐÃ TRIỂN KHAI** (CSV không có bước xem trước) |
| **FG-04** | So sánh trước/sau chuẩn hóa | **Không có** | — | (đề xuất: ADMIN) | **THIẾT KẾ ĐỀ XUẤT — CHƯA TRIỂN KHAI** |
| **FG-05** | Hàng đợi phê duyệt | Hàng đợi đối sánh + chi tiết ứng viên + xác nhận ACCEPT/REJECT | `/reviews` | ADMIN, REVIEWER | **ĐÃ TRIỂN KHAI** |
| **FG-06** | Thống kê | Tổng quan (dashboard) | `/dashboard` | ADMIN | **MỘT PHẦN** (chỉ số đếm; biểu đồ Trang chủ giữ chỗ) |

Chi tiết thành phần, API, trạng thái giao diện cần thiết kế (loading/empty/error/modal/409…) của từng màn: xem `screens.json`. Tệp nguồn React: cột `source` trong `screens.json`.

## 2. Quy tắc bắt buộc cho Task 20

1. **Đồng bộ phần mềm đã triển khai:** FG-01, 02, 03, 05, 06 phải dựng lại đúng bố cục/nhãn tiếng Việt có dấu/thành phần như giao diện đang chạy (ảnh chụp độ phân giải cao sẽ lấy ở Task chụp ảnh; ảnh Task 16–17 chỉ 800×453 px — không đủ). Không "thiết kế lại hoàn toàn" rồi gọi là sản phẩm đã hoàn thành.
2. **FG-04 phải mang nhãn rõ trên chính mockup:** *"THIẾT KẾ ĐỀ XUẤT — CHƯA TRIỂN KHAI"*. Mọi API của nó là **đề xuất**.
3. **Không biến giữ chỗ thành chức năng:** biểu đồ Trang chủ, `/tasks` (NOT_IMPLEMENTED), `DiffViewerStub` không được thiết kế như tính năng đã có. Thống kê mở rộng (theo năm/loại/khoa/nguồn) nếu thiết kế phải gắn nhãn *"đề xuất"* (GAP-08).
4. **Không thêm "điểm/mức độ phù hợp"** vào FG-05 như thể phần mềm có (GAP-04). Cột "Ngữ cảnh mơ hồ" = số ứng viên khác/cảnh báo dùng chung, không phải độ phù hợp.
5. **Dữ liệu trong mockup là minh họa tự tạo**, đánh dấu "dữ liệu minh họa"; **không dùng tên, email, mật khẩu, token thật**. Không dùng ảnh/giao diện của đồ án khác.
6. **Design tokens + thành phần tái dùng + trạng thái:** tạo `tokens.json`; thành phần: nút, ô nhập, bảng, thẻ chỉ số, nhãn trạng thái (VERIFIED/CORROBORATED/UNRESOLVED, PENDING…), hộp thoại xác nhận, toast, trạng thái rỗng/lỗi/đang tải.
7. **Không gọi SVG/PNG/HTML là "Figma".** Chỉ gọi là Figma khi có tệp Figma thật do sinh viên tạo hoặc do connector được cấp quyền tạo. Nếu dùng plugin nhập HTML/SVG vào Figma, sinh viên phải tự kiểm tra tính khả dụng/điều khoản (chưa được kiểm trong Task 19).

## 3. Đặc tả FG-04 — So sánh trước/sau chuẩn hóa (thiết kế đề xuất)

**Mục đích:** cho người quản trị thấy *cùng một công bố* ở dạng dữ liệu thô (dòng CSV) và dạng đã chuẩn hóa, cùng quy tắc nào đã áp dụng.

**Dữ liệu nguồn đã có trong DB (không cần bảng mới):** `raw_scopus_records.raw_payload` (JSON, 22 khóa CSV) nối `publication_raw_sources` → `publications` (+ `scopus_imports` cho tên tệp/SHA).

**Bố cục đề xuất**

| Vùng | Nội dung |
|---|---|
| Đầu trang | Chọn đợt nhập / tìm công bố theo EID; nhãn *Thiết kế đề xuất* |
| Khối nguồn gốc | Tên tệp, số dòng, SHA-256, thời điểm nhập (lấy từ `publication_raw_sources` → `raw_scopus_records` → `scopus_imports`) |
| Bảng so sánh (4 cột) | **Trường** · **Giá trị gốc (raw_payload)** · **Giá trị chuẩn hóa (publications)** · **Quy tắc / kết quả** |
| Nhãn từng dòng | *Giữ nguyên* · *Đã chuẩn hóa* · *Khác biệt* · *Thiếu* |
| Bộ đếm đợt | NEW · EXISTING_UNCHANGED · EXISTING_METADATA_CHANGED · INVALID_EID (từ `scopus_imports.normalization_summary`) |

**Ánh xạ trường có thật (từ `create_publication_from_raw`)**

| Trường hiển thị | Gốc (`raw_payload`) | Chuẩn hóa (`publications`) | Quy tắc hiện có |
|---|---|---|---|
| EID | `EID` | `eid` | Chuẩn tắc EID (khóa chống trùng) |
| Tiêu đề | `Title` | `title`, `title_normalized` | NFKC + chữ thường + cắt khoảng trắng |
| DOI | `DOI` | `doi` | **Giữ nguyên văn** (chỉ cắt khoảng trắng) — GAP-01 |
| Nguồn xuất bản | `Source title` (đúng) / `Source` | `source_title` | **Hiện lấy cột `Source` nên = `Scopus`** — GAP-02; mockup cần ghi chú khác biệt này |
| Năm | `Year` | `year` | Ép số nguyên |
| Trích dẫn | `Cited by` | `cited_by_count` | Số nguyên ≥ 0 |
| Loại tài liệu / giai đoạn / truy cập mở | `Document Type` / `Publication Stage` / `Open Access` | `document_type` / `publication_stage` / `open_access_status` | Cắt độ dài ≤ 50 |
| Tập/Số/Bài báo/Trang | `Volume`, `Issue`, `Art. No.`, `Page start`, `Page end` | `volume`, `issue`, `art_no`, `page_start`, `page_end` | Giữ nguyên |

**Trạng thái cần thiết kế:** đang tải; không có dòng thô; `EXISTING_METADATA_CHANGED` (khác biệt nổi bật — metadata mới *không ghi đè*); `INVALID_EID`; lỗi.

**API đề xuất (CHƯA TỒN TẠI):** `GET /api/v1/publications/{eid}/normalization-comparison` (chỉ đọc, ADMIN). Task 19 không tạo API.

## 4. Câu hỏi/quyết định cần chốt trước hoặc trong Task 20

| # | Câu hỏi | Gợi ý |
|---|---|---|
| 1 | Cách tạo Figma thật (D2): connector, plugin nhập HTML/SVG, hay sinh viên dựng tay từ tokens + ảnh? | Sinh viên tự kiểm tra plugin/điều khoản; Claude chuẩn bị tokens + mockup nguồn |
| 2 | FG-04 chỉ là mockup hay sẽ cài đặt? (D4) | Mockup (đề cương yêu cầu *thiết kế*) |
| 3 | Mockup nguồn nên lấy dạng nào (HTML tĩnh dựng lại từ lớp Tailwind, hay SVG)? | HTML/SVG tách theo màn, kèm ảnh chụp thật để đối chiếu |
| 4 | Có thiết kế thống kê mở rộng (GAP-08) không? | Có, nhưng gắn nhãn "đề xuất" |
| 5 | Thống nhất AntD ↔ Tailwind ở trang Duyệt đối sánh khi thiết kế? | Thiết kế theo phong cách chung (Tailwind), ghi chú khác biệt hiện tại |

**Câu hỏi cho GVHD (14/10):** chấp nhận mockup cho màn *chưa triển khai* không? Có cần thiết kế riêng cho điện thoại không (PI-3.2)? Màn "so sánh trước/sau" cần hiển thị những trường nào?

## 5. Tệp Task 20 cần tạo (đề xuất)

`docs/design/ui/tokens.json` · `UI_INVENTORY.md` (đủ 17 màn trong `screens.json`) · `mockups/FG-01…FG-06.*` (nguồn HTML/SVG) · `HUONG_DAN_NHAP_FIGMA.md` · `MANIFEST.md`; kèm kiểm: mỗi mockup đặt cạnh ảnh chụp thật (trừ FG-04), tiếng Việt có dấu, không cắt chữ.
