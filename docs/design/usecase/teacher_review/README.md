# Bộ Sơ đồ Use Case — Hệ thống Scopus–ICTU
**Dành cho giảng viên hướng dẫn xem trước · Ngày chuẩn bị: 2026-10-22**

---

## 1. Tổng quan hệ thống

**Hệ thống Cổng thông tin Scopus–ICTU** hỗ trợ quản trị viên nhập, chuẩn hóa và đối sánh dữ liệu công bố khoa học từ Scopus với hồ sơ giảng viên của Đại học ICTU; đồng thời cho phép phê duyệt viên xét duyệt kết quả đối sánh và giảng viên xem công bố của mình.

| Hạng mục | Số lượng |
|---|---|
| **Actor** | **4** (3 vai trò trong ứng dụng + 1 kỹ thuật viên chạy CLI) |
| **Use Case duy nhất** | **28** |
| **Sơ đồ tổng quan theo vai trò** | 3 (UCD-0A, 0B, 0C) |
| **Sơ đồ theo nhóm nghiệp vụ** | 6 (UCD-1 → UCD-6) |
| **Sơ đồ chuyên sâu phân hệ** | 1 (UCD-NHAP-DU-LIEU) |
| **Tổng sơ đồ trong bộ này** | **10** |

---

## 2. Các Actor

| Actor | Vai trò |
|---|---|
| **ADMIN — Quản trị viên** | Toàn quyền: nhập dữ liệu, chuẩn hóa, đối sánh, duyệt, quản lý tài khoản, xem nhật ký |
| **REVIEWER — Phê duyệt viên** | Xem hàng đợi ứng viên, duyệt ACCEPT/REJECT, xem công bố, tra cứu |
| **LECTURER — Giảng viên** | Xem hồ sơ cá nhân, xem liên kết Scopus đã duyệt, xem công bố của mình |
| **TECH — Kỹ thuật viên** | Chạy script CLI để nạp dữ liệu, sinh ứng viên, khởi tạo demo *(không phải vai trò trong ứng dụng web)* |

---

## 3. Danh sách sơ đồ trong bộ này

### Sơ đồ tổng quan theo vai trò

| File | Nội dung | Số UC | Đề xuất báo cáo |
|---|---|---|---|
| `UCD-0A_tong_the_admin.svg/.png` | Tất cả 22 UC của ADMIN, phân theo 6 nhóm nghiệp vụ | 22 | **BẮT BUỘC** |
| `UCD-0B_tong_the_reviewer.svg/.png` | 8 UC của REVIEWER | 8 | **BẮT BUỘC** |
| `UCD-0C_tong_the_lecturer.svg/.png` | 6 UC của LECTURER | 6 | **BẮT BUỘC** |

### Sơ đồ theo nhóm nghiệp vụ (chi tiết)

| File | Nội dung | Số UC | Đề xuất báo cáo |
|---|---|---|---|
| `UCD-1_nhap_du_lieu.svg/.png` | Nhập CSV Scopus, nhập JSON giảng viên, hoàn tác, quản lý đợt nhập | 5 | **BẮT BUỘC** |
| `UCD-4_chuan_hoa_doi_soat_phe_duyet.svg/.png` | Chuẩn hóa, bóc tách tác giả, sinh ứng viên (CLI), duyệt ứng viên, lịch sử review | 6 | **BẮT BUỘC** |
| `UCD-2_quan_ly_ho_so.svg/.png` | Quản lý giảng viên, tài khoản, tác giả Scopus, hồ sơ LECTURER | 6 | Nên đưa vào |
| `UCD-3_quan_ly_cong_bo.svg/.png` | Xem công bố (ADMIN/REVIEWER), xem công bố của tôi (LECTURER) | 2 | Nên đưa vào |
| `UCD-5_tim_kiem_thong_ke_xuat.svg/.png` | Tra cứu, thống kê dashboard, xuất JSON | 4 | Phụ lục |
| `UCD-6_xac_thuc_giam_sat.svg/.png` | Đăng nhập/xuất, thông báo, nhật ký kiểm toán, khởi tạo CLI | 5 | Phụ lục |

### Sơ đồ chuyên sâu phân hệ

| File | Nội dung | Đề xuất báo cáo |
|---|---|---|
| `UCD-NHAP-DU-LIEU.svg/.png` | Chi tiết phân hệ nhập dữ liệu: quan hệ extend giữa các bước, xử lý cảnh báo trùng, ẩn/xóa đợt nhập | Phụ lục hoặc thay UCD-1 |

---

## 4. Phân loại đề xuất cho báo cáo đồ án

### A — BẮT BUỘC ĐƯA VÀO BÁO CÁO CHÍNH (4 sơ đồ)
1. **UCD-0A** — Tổng thể ADMIN: thể hiện đầy đủ phạm vi hệ thống và phân quyền
2. **UCD-1** — Nhập dữ liệu: nghiệp vụ lõi, giá trị cốt lõi của đồ án
3. **UCD-4** — Chuẩn hóa / Đối sánh / Phê duyệt: luồng xử lý chính, thể hiện tính mới của hệ thống
4. **UCD-0B** hoặc **UCD-0C** — chọn một trong hai để minh họa phân quyền vai trò phụ

### B — NÊN ĐƯA VÀO BÁO CÁO CHÍNH (1–2 sơ đồ)
- **UCD-2** — Quản lý hồ sơ giảng viên: thể hiện nghiệp vụ quản lý dữ liệu con người
- **UCD-3** — Quản lý công bố: kết quả cuối của cả quy trình

### C — ĐƯA VÀO PHỤ LỤC
- UCD-0B, UCD-0C (cái không chọn ở nhóm A)
- UCD-5 — Tìm kiếm và thống kê
- UCD-6 — Xác thực và giám sát
- UCD-NHAP-DU-LIEU — Chi tiết kỹ thuật phân hệ nhập

### D — CHỈ GIỮ TRONG TÀI LIỆU KỸ THUẬT
- Các sơ đồ A4 thử nghiệm trong `diagrams/a4/` (thử nghiệm bố cục, không phải bản chính)

---

## 5. Trạng thái triển khai từng UC

| Trạng thái | Số UC | Ghi chú |
|---|---|---|
| **ĐÃ TRIỂN KHAI (UI+API)** | 21 | Có đường chạy hoàn chỉnh, đã kiểm thử |
| **MỘT PHẦN** | 2 | UC-03 (thông báo nền), UC-16 (UI thiếu trang chi tiết tác giả) |
| **CHỈ API** | 1 | UC-23 (Admin xem Scopus của giảng viên — có API, chưa có trang UI) |
| **CHỈ CLI** | 4 | UC-24, UC-25, UC-26 (script vận hành), UC-26 (bootstrap demo) |

---

## 6. Vấn đề UML cần thầy góp ý

1. **Actor TECH (Kỹ thuật viên CLI)**: Trong UML thuần, các tác nhân chạy script thường không vẽ vào sơ đồ use case của hệ thống. Hệ thống hiện giữ lại để phản ánh đúng thực tế vận hành (cần chạy script trước khi ADMIN có dữ liệu để duyệt). **Thầy có đồng ý giữ không, hay nên chuyển thành ghi chú ngoài sơ đồ?**

2. **UC-18 «include» UC-17**: Việc duyệt ứng viên bắt buộc phải đọc chi tiết ứng viên trước (lấy `observation_id`). Quan hệ `include` đã phản ánh đúng. **Thầy có muốn thêm precondition dưới dạng note không?**

3. **UC-08 và UC-10 có «extend» riêng**: UC-08a (hoàn tác nhập giảng viên), UC-10a (quản lý đợt nhập CSV) là hành vi tùy chọn nên dùng `extend`. **Thầy có muốn tách thành sơ đồ riêng cho rõ hơn không?**

4. **UC-04 (Dashboard)**: Đã có biểu đồ thật (công bố theo năm, theo loại, mức đầy đủ đơn vị) từ commit gần đây. Trạng thái đã cập nhật thành "ĐÃ TRIỂN KHAI".

5. **UC-23 (API xem Scopus của giảng viên)**: Có API nhưng chưa có trang UI. Có thể bỏ khỏi sơ đồ tổng quan nếu thầy muốn chỉ hiện UC có UI đầy đủ.

---

## 7. Các file nguồn PlantUML

Tất cả file `.puml` nguồn nằm tại:
- Sơ đồ tổng quan: `docs/design/usecase/diagrams/`
- Sơ đồ chuyên sâu nhập dữ liệu: `docs/design/usecase/import_data/`
- Nguồn dữ liệu: `docs/design/usecase/usecase_map.json`
- Tái sinh tự động: `docs/design/tools/gen_usecase_assets.py`

Để render lại sau khi chỉnh sửa: `python -X utf8 docs/design/tools/render.py usecase`

---

*Chuẩn bị bởi: Quang Huy Truong · Claude Sonnet 4.6 · 2026-10-22*
