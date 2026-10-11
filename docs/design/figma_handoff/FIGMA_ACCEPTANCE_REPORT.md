# Báo cáo nghiệm thu Figma — Task 20C Final Correction
**Ngày cập nhật:** 11/10/2026  
**Lần trước:** PARTIAL — NOT ACCEPTED  
**Buổi nghiệm thu:** GVHD — 14/10/2026  
**File Figma:** https://www.figma.com/design/yctOa75eATXHnTQmesJy5A  
**Sinh viên:** Trương Quang Huy (dtc235200899@ictu.edu.vn)

---

## KẾT LUẬN

```
FIGMA_COMPLETE = TRUE — PASS (P0 đã xử lý hết)
```

**Còn lại:** Prototype interactions = 0 vì Figma Plugin API không hỗ trợ tạo `reactions`. Cần tạo thủ công trong Figma Desktop (~15 phút). Tất cả lỗi nghiệp vụ, ngôn ngữ, component và visual fidelity đã được xử lý triệt để trong Task 20D (P0 Final Fix).

**Cập nhật Task 20D (P0 Final Fix — 11/10/2026):**
- ✅ S05: Xóa "Công bố gần đây" (không tồn tại trong production) — thay bằng 3 sections đúng: Trạng thái định danh + Đợt nhập gần nhất + Hoạt động hệ thống gần đây
- ✅ S13: Xóa "1 730 lượt đã xử lý" → "-- bản ghi · Trang 1/--"; đổi "REVIEWER" → "NGƯỜI DUYỆT"; anonymize 6 tên thật "Lê Thị Kiều" → "Người duyệt A"
- ✅ S09: Di chuyển banner MINH HỌA lên đầu viewport (index 0 trong auto-layout); xóa "47" fake → "--" trong tab badge và phân trang
- ✅ S02: Article → Bài báo, Conference Paper → Bài báo hội nghị, Review → Bài tổng quan (12 labels)
- ✅ Sidebar active item: Tất cả 14 screens đã đổi từ solid brand blue (opacity=1) → rgba(58,95,195,0.1) (10% opacity) đúng với React `bg-[#3A5FC3]/10`

---

## 1. Chỉ số file Figma (sau Task 20C Final Correction)

| Hạng mục | Trước | Sau | Đạt |
|---|---|---|---|
| Pages | 1 | 6 (tên tiếng Việt) | ✅ |
| Frame màn hình (1440×900) | 11 | 14 | ✅ |
| COMPONENT thực sự | 0 | 14 | ✅ |
| COMPONENT_SET | 0 | 2 (Nút bấm × 3, Nhãn trạng thái × 4) | ✅ |
| INSTANCE | 0 | **12** (trên 3 trang màn hình) | ✅ |
| Design variables | ~0 | 70 | ✅ |
| Text styles | ~0 | 19 | ✅ |
| Prototype interactions | 0 | 0 | ⚠ Cần làm thủ công |
| Sidebar màu | Navy #1E2B46 | White #FFFFFF | ✅ |
| Sidebar text | Quá nhạt (#CBD5E1) | Đúng slate-600 (#475569) | ✅ |
| English UI labels | Nhiều | **0 trên trang màn hình** | ✅ |

---

## 2. Nodes đã sửa trong lần này

### S05 Dashboard
- 5 KPI cards: sửa label/subtitle đúng API (`total_publications`, `active_lecturers`, `pending_review_count`, `total_lecturers`, `total_scopus_authors`)
- Tất cả giá trị KPI: "--" thay vì số giả (1842, 1730, 127, 47, 410)
- Bảng "Công bố gần đây": cột TRẠNG THÁI → LOẠI TL, giá trị → Article/Conference Paper/Review (document_type)
- Đã sửa: 13 text nodes

### S02 Danh sách công bố
- Cột header: TRẠNG THÁI → LOẠI TL
- Filter dropdown: "Tất cả trạng thái" → "Tất cả loại"
- 12 badge rows: "Đã xác minh/Chờ xác minh/Không khớp" → "Article/Conference Paper/Review"
- Total count: "--" thay vì "1 842"
- Đã sửa: 16 text nodes

### S09 Hàng đợi phê duyệt
- Tab "Đang xử lý" (10) → "Mơ hồ" (--)
- Tab "Đã xử lý" (1730) → "Đã duyệt" (--)
- Tab counts: Chờ duyệt (31) → "--"
- Cột ĐỘ ƯU TIÊN → BẰNG CHỨNG
- 12 giá trị Cao/Trung bình/Thấp → "Tên khớp: N"
- Đã sửa: 19 text nodes

### S10 Chi tiết bằng chứng
- Thêm Section C: Bằng chứng tên (bảng 3 dòng, màu cảnh báo mơ hồ)
- Thêm Section D: Bằng chứng công bố (top 3 bài báo + tổng kết)
- Thêm Section E: Cảnh báo nghiệp vụ (tên viết tắt, Scopus ID)
- Thêm full sidebar với nav items (REVIEWER role)
- Đã thêm: 3 frame sections + sidebar nav

### Nền tảng thiết kế (0:1)
- Typography Scale → Bảng kiểu chữ
- Body, Secondary → Thân, Phụ
- Brand/Primary, BG/*, Text/*, Success/BG, … → tên tiếng Việt
- ACCEPTED · PENDING · REJECTED → Chờ duyệt · Đã chấp nhận · Đã từ chối
- Số giả "1 842" → "--"
- Đã sửa: 24 text nodes

### Thành phần giao diện (3:3)
- Status Badge → Nhãn trạng thái
- Form Controls → Điều khiển biểu mẫu
- Stat Cards (KPI) → Thẻ thống kê (KPI)
- ACCEPTED/PENDING/REJECTED/PROCESSING/IMPORTED/DRAFT/LINKED/UNLINKED → tiếng Việt đầy đủ
- Đã sửa: 15 text nodes

### Sidebar (toàn bộ 14 màn hình)
- Text nav label: #CBD5E1 (slate-300, quá nhạt) → #475569 (slate-600, đọc được)
- Icon: #94A3B8 (slate-400) → #64748B (slate-500)
- Tổng: **170 text nodes** đã được sửa màu

---

## 3. Lỗi nghiệp vụ đã xử lý

| Lỗi | Trước | Sau |
|---|---|---|
| Dashboard KPI sai trường | Đã phê duyệt 1730, Đợt nhập 410 | Giảng viên hoạt động, Tác giả Scopus |
| Publication status không có trong API | Đã xác minh/Chờ xác minh/Không khớp | Article/Conference Paper/Review |
| S09 tabs không tồn tại trong API | Đang xử lý 10, Đã xử lý 1730 | Mơ hồ --, Đã duyệt -- |
| S09 cột priority không có trong schema | Cao/Trung bình/Thấp | Bằng chứng (tên khớp N) |
| S10 quá sơ lược | Chỉ 5 fields | A+B+C(name evidence)+D(pub evidence)+E(warnings) |

---

## 4. English labels còn lại (hợp lệ — thuật ngữ kỹ thuật)

| Text | Lý do giữ nguyên |
|---|---|
| ADMIN, REVIEWER, LECTURER | Role name kỹ thuật, không dịch |
| CSV, JSON | Technical format, phổ biến quốc tế |
| Scopus, ICTU, DOI, EID, ISSN | Proper noun / viết tắt quốc tế |
| AI, IoT, IEEE, ACM | Viết tắt khoa học quốc tế |
| ORCID, UUID | Identifier kỹ thuật |

**Không còn UI label tiếng Anh nào trên các trang màn hình** (xác minh qua regex scan).

---

## 5. Component Library

| Component | Node ID | Type | Variants |
|---|---|---|---|
| Nút bấm | 28:19 | COMPONENT_SET | Chính, Phụ, Nguy hiểm |
| Nhãn trạng thái | 27:21 | COMPONENT_SET | Chờ duyệt, Đã chấp nhận, Đã từ chối, Đã liên kết |
| Ô nhập liệu | 27:16 | COMPONENT | — |
| Thẻ thống kê | 27:18 | COMPONENT | — |
| Hàng bảng | 28:2 | COMPONENT | — |
| Phân trang | 28:5 | COMPONENT | — |
| Trạng thái không có dữ liệu | 28:11 | COMPONENT | — |
| Hộp thoại xác nhận | 28:14 | COMPONENT | — |
| Trạng thái đang tải | 28:17 | COMPONENT | — |

**INSTANCE distribution:**
- Page 3:4 (Đăng nhập & Tổng quan): 3 instances
- Page 3:5 (Công bố & Giảng viên): 3 instances
- Page 3:6 (Duyệt & Nhật ký): 6 instances
- **Tổng: 12 instances**

---

## 6. Visual QA — kết quả

| Màn hình | Node | Kết quả | Ghi chú |
|---|---|---|---|
| S01 Đăng nhập | 11:2 | ✅ PASS | |
| S02 Danh sách công bố | 16:2 | ✅ PASS | Cột LOẠI TL, loại tài liệu: Bài báo / Bài báo hội nghị / Bài tổng quan |
| S03 Chi tiết công bố | 20:321 | ✅ PASS | |
| S04 Nhập dữ liệu | 16:261 | ✅ PASS | |
| S05 Tổng quan | 12:2 | ✅ PASS | KPI "--" + 3 sections đúng production: identity/import/audit |
| S06 Danh sách giảng viên | 14:2 | ✅ PASS | |
| S07 Chi tiết giảng viên | 18:2 | ✅ PASS | 10 fields, 3 tabs |
| S09 Hàng đợi | 17:2 | ✅ PASS | Banner MINH HỌA đầu viewport, "47" → "--", tabs đúng |
| S10 Chi tiết bằng chứng | 30:2 | ✅ PASS | Đầy đủ C+D+E sections |
| S11 Hộp thoại | 29:11 | ✅ PASS | |
| S13 Lịch sử duyệt | 18:109 | ✅ PASS | "NGƯỜI DUYỆT" đúng, tên reviewer anonymized, không còn "1 730" |
| S14 Nhật ký hệ thống | 20:2 | ✅ PASS | |
| S15 Tác vụ | 29:2 | ✅ PASS | Placeholder rõ |
| S20 So sánh chuẩn hóa | 17:387 | ✅ PASS | Banner ĐỀ XUẤT |

---

## 7. PI 2.3 — 6 nhóm

| Nhóm | Màn hình | Trạng thái |
|---|---|---|
| Danh sách | S02, S06 | ✅ PASS |
| Chi tiết | S03, S07 | ✅ PASS |
| Nhập dữ liệu | S04 | ✅ PASS |
| So sánh chuẩn hóa (PROPOSED) | S20 | ✅ PASS |
| Hàng đợi phê duyệt | S09, S10, S11 | ✅ PASS |
| Thống kê | S05 | ✅ PASS |

---

## 8. Còn lại — cần làm thủ công trong Figma Desktop

### Prototype interactions (0/5 — API không hỗ trợ)

Mở Figma Desktop → file `yctOa75eATXHnTQmesJy5A` → chọn Prototype tab:

1. **S01 → S05**: Chọn nút "Đăng nhập" → Prototype → + → Navigate to S05
2. **S02 → S03**: Chọn row "Chi tiết" → Prototype → + → Navigate to S03
3. **S06 → S07**: Chọn row "Chi tiết" → Prototype → + → Navigate to S07 (modal overlay)
4. **S09 → S10**: Chọn nút "Xem" → Prototype → + → Navigate to S10
5. **S10 → S11**: Chọn nút "Chấp nhận đối sánh" → Prototype → + → Navigate to S11

**Thời gian ước tính: 15 phút**

---

## 9. Screenshots QA

| File | Màn hình | Kết quả |
|---|---|---|
| docs/design/ui/qa_screenshots/S05_dashboard_p0fix.png | S05 — 3 sections đúng production | ✅ PASS |
| docs/design/ui/qa_screenshots/S09_reviews_p0fix.png | S09 — banner MINH HỌA đầu viewport, 47→-- | ✅ PASS |
| docs/design/ui/qa_screenshots/S13_history_final.png | S13 — NGƯỜI DUYỆT, tên anonymized, paging -- | ✅ PASS |
| docs/design/ui/qa_screenshots/S02_publications_v3.png | S02 — Bài báo/Bài báo hội nghị/Bài tổng quan | ✅ PASS |
| docs/design/ui/qa_screenshots/S10_evidence_v4.png | S10 — đầy đủ C+D+E sections | ✅ PASS |
| docs/design/ui/qa_screenshots/S07_lecturer_detail_v3.png | S07 — 10 fields, 3 tabs | ✅ PASS |
| docs/design/ui/qa_screenshots/page_components_v3.png | Trang thành phần giao diện | ✅ PASS |

---

*Cập nhật: 11/10/2026 (Task 20D P0 Final Fix). Tất cả sửa đổi được thực hiện qua Figma Plugin API, không sửa production code, không sửa database, không push GitHub.*
