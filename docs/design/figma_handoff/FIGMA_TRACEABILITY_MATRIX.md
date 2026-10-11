# Ma trận truy vết Figma — Scopus–ICTU
**Ngày lập:** 11/10/2026  
**File Figma:** https://www.figma.com/design/yctOa75eATXHnTQmesJy5A  
**Người lập:** qhun22 (dtc235200899@ictu.edu.vn)  
**Trạng thái:** Task 20C Final Correction

---

## 1. Tổng quan file Figma

| Hạng mục | Giá trị |
|---|---|
| File key | yctOa75eATXHnTQmesJy5A |
| Team | qhun22 |
| Gói | Figma Education |
| Số pages | 6 |
| Số frame màn hình (1440×900) | 14 |
| COMPONENT thực sự | 14 |
| COMPONENT_SET / Variants | 2 (Nút bấm × 3, Nhãn trạng thái × 4) |
| INSTANCE | 0 (chưa tạo — xem blocker) |
| Design variables | 70 |
| Text styles | 19 |
| Prototype interactions | 0 (chưa có — xem blocker) |

---

## 2. Cấu trúc 6 pages

| Page ID | Tên tiếng Việt | Nội dung |
|---|---|---|
| 0:1 | 🎨 Nền tảng thiết kế | Hệ thống màu sắc, Hệ thống kiểu chữ |
| 3:3 | 🧩 Thành phần giao diện | 14 COMPONENT + 2 COMPONENT_SET |
| 3:4 | 📱 Màn hình — Đăng nhập và Tổng quan | S01, S04, S05 |
| 3:5 | 📋 Màn hình — Công bố và Giảng viên | S02, S03, S06, S07 |
| 3:6 | 🔍 Màn hình — Duyệt đối sánh và Nhật ký | S09, S10, S11, S13, S14, S15, S20 |
| 3:7 | 🔄 Luồng thao tác người dùng | 4 luồng thao tác |

---

## 3. Ma trận truy vết màn hình

| Screen ID | Tên màn hình | Vai trò | Route React | PI 2.3 | Trạng thái | Figma Page | Figma Node ID | QA |
|---|---|---|---|---|---|---|---|---|
| S01 | Đăng nhập | ALL | /login | — | AS-IS | 📱 Đăng nhập & Tổng quan | 11:2 | PASS |
| S02 | Danh sách công bố | ADMIN | /publications | PI2.3-1 Danh sách | AS-IS | 📋 Công bố & Giảng viên | 16:2 | PASS |
| S03 | Chi tiết công bố | ADMIN | /publications/:eid | PI2.3-2 Chi tiết | AS-IS | 📋 Công bố & Giảng viên | 20:321 | PASS |
| S04 | Nhập dữ liệu | ADMIN | /imports | PI2.3-3 Nhập dữ liệu | AS-IS | 📱 Đăng nhập & Tổng quan | 16:261 | PASS |
| S05 | Tổng quan / Thống kê | ADMIN | /dashboard | PI2.3-6 Thống kê | AS-IS + MINH HỌA | 📱 Đăng nhập & Tổng quan | 12:2 | PASS |
| S06 | Danh sách giảng viên | ADMIN | /lecturers | PI2.3-1 Danh sách | AS-IS | 📋 Công bố & Giảng viên | 14:2 | PASS |
| S07 | Chi tiết giảng viên (modal) | ADMIN | /lecturers (modal) | PI2.3-2 Chi tiết | AS-IS | 📋 Công bố & Giảng viên | 18:2 | PASS |
| S09 | Hàng đợi duyệt đối sánh | REVIEWER/ADMIN | /reviews | PI2.3-5 Hàng đợi | AS-IS + MINH HỌA | 🔍 Duyệt & Nhật ký | 17:2 | PASS |
| S10 | Chi tiết bằng chứng đối sánh | REVIEWER | /reviews (modal) | PI2.3-5 Hàng đợi | TO-BE (new) | 🔍 Duyệt & Nhật ký | 30:2 | PASS |
| S11 | Hộp thoại Chấp nhận/Từ chối | REVIEWER | /reviews (dialog) | PI2.3-5 Hàng đợi | TO-BE (new) | 🔍 Duyệt & Nhật ký | 29:11 | PASS |
| S13 | Lịch sử duyệt đối sánh | ADMIN | /review-history | — | AS-IS + MINH HỌA | 🔍 Duyệt & Nhật ký | 18:109 | PASS |
| S14 | Nhật ký hệ thống | ADMIN | /audit-logs | — | AS-IS + MINH HỌA | 🔍 Duyệt & Nhật ký | 20:2 | PASS |
| S15 | Tác vụ (placeholder) | ADMIN | /tasks | — | PLACEHOLDER | 🔍 Duyệt & Nhật ký | 29:2 | PASS |
| S20 | So sánh chuẩn hóa | ADMIN | /publications/:eid/normalization | PI2.3-4 Chuẩn hóa | PROPOSED | 🔍 Duyệt & Nhật ký | 17:387 | PASS |

---

## 4. Ma trận PI 2.3 — 6 nhóm bắt buộc

| Nhóm | Tên | Màn hình | Figma Node | Trạng thái |
|---|---|---|---|---|
| PI2.3-1 | Danh sách | S02 (Công bố), S06 (Giảng viên) | 16:2, 14:2 | ✅ PASS |
| PI2.3-2 | Chi tiết | S03 (Công bố), S07 (Giảng viên) | 20:321, 18:2 | ✅ PASS |
| PI2.3-3 | Nhập dữ liệu | S04 | 16:261 | ✅ PASS |
| PI2.3-4 | So sánh chuẩn hóa (PROPOSED) | S20 | 17:387 | ✅ PASS (Có nhãn ĐỀ XUẤT) |
| PI2.3-5 | Hàng đợi phê duyệt | S09, S10, S11 | 17:2, 30:2, 29:11 | ✅ PASS |
| PI2.3-6 | Thống kê | S05 | 12:2 | ✅ PASS |

---

## 5. Component Library

| Component | ID | Type | Variants |
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

---

## 6. Ngôn ngữ — Việt hóa

| Hạng mục | Trạng thái |
|---|---|
| Tên 6 pages Figma | ✅ Đã Việt hóa |
| Design Foundations labels | ✅ Đã Việt hóa (20 text nodes) |
| Nav sidebar labels | ✅ Đã sửa toàn bộ |
| ACCEPTED/PENDING/REJECTED (publications) | ✅ Đã đổi → Đã xác minh/Chờ xác minh/Không khớp |
| ACCEPTED/REJECTED (reviews/history) | ✅ Đã đổi → Đã chấp nhận/Đã từ chối |
| LINKED/UNLINKED | ✅ Đã đổi → Đã liên kết/Chưa liên kết |
| SUCCESS/FAILED | ✅ Đã đổi → Thành công/Thất bại |
| IMPORTED | ✅ Đã đổi → Đã nhập |
| HIGH/MEDIUM/LOW | ✅ Đã đổi → Cao/Trung bình/Thấp |
| PROCESSING | ✅ Đã đổi → Chờ duyệt |
| Lịch sử review | ✅ Đã đổi → Lịch sử duyệt |
| Component names | ✅ Đặt tên tiếng Việt |
| Thuật ngữ giữ nguyên | DOI, EID, ISSN, CSV, JSON, Scopus, ICTU, UUID, ORCID, API |

---

## 7. Dữ liệu và nghiệp vụ

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Dashboard KPI | MINH HỌA có nhãn | Có banner ⚠ DỮ LIỆU MINH HỌA |
| Publication status | Đã sửa | Không dùng ACCEPTED/PENDING/REJECTED của review |
| Reviews evidence/status | MINH HỌA có nhãn | Đã loại bỏ PROCESSING, priority không thật |
| Lecturer fields | Đúng schema | Học vị, Học hàm tách biệt, có Giới tính/Ngày sinh/SĐT/Chuyên ngành |
| Audit/Review History | MINH HỌA có nhãn | Không có dữ liệu thật |
| Tasks placeholder | Đúng | Chỉ hiển thị "Chức năng đang phát triển" |
| S20 Proposed | Đúng | Có banner THIẾT KẾ ĐỀ XUẤT — CHƯA TRIỂN KHAI |
| RBAC | Đúng | ADMIN/REVIEWER/LECTURER khác nhau |

---

## 8. Blockers đã xác minh

| Hạng mục | Tình trạng | Lý do |
|---|---|---|
| INSTANCE count = 0 | BLOCKER | Figma Plugin API `createInstance()` cần component master trên cùng page. Tất cả instances cần được tạo thủ công qua Figma Editor → Right-click component → Create instance. |
| Prototype interactions = 0 | BLOCKER | Figma Plugin API không hỗ trợ tạo `reactions` (prototype arrows). Cần tạo thủ công trong Figma Desktop: chọn node → Prototype tab → + drag. |
| Screens chưa phân trang (page 3:5, 3:6 chưa có layout cụ thể) | PARTIAL | Đã move frames nhưng layout trong page chưa được sắp xếp canvas. |

---

## 9. Hành động thủ công cần làm trong Figma Editor

Để hoàn thiện prototype và instances:

**Bước 1 — Tạo instances:** Mở page 🧩 Thành phần giao diện → Right-click mỗi component → "Create instance" → Kéo vào màn hình.

**Bước 2 — Prototype interactions:**
- S01 → S05 (Đăng nhập → Tổng quan): Chọn nút "Đăng nhập" → Prototype → + → Navigate to S05
- S06 → S07 (Danh sách → Chi tiết): Chọn nút "Chi tiết" → Prototype → + → Navigate to S07  
- S09 → S10 (Hàng đợi → Chi tiết): Chọn nút "Xem" → Prototype → + → Navigate to S10
- S10 → S11 (Chi tiết → Xác nhận): Chọn nút "Chấp nhận đối sánh" → Prototype → + → Navigate to S11
- S04 → S04 (Nhập → Kết quả): Cùng frame, chọn nút "Bắt đầu nhập" → Overlay/Navigate

---

*Tài liệu này là ma trận truy vết chính thức cho buổi nghiệm thu GVHD ngày 14/10/2026.*
