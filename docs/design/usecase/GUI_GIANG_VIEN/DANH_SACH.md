# Bộ Sơ đồ Use Case — Hệ thống Scopus–ICTU
**Gửi giảng viên hướng dẫn xem trước · 2026-10-22**

28 Use Case · 3 vai trò người dùng (ADMIN / REVIEWER / LECTURER) · 10 sơ đồ

---

| # | File | Nội dung | Actors |
|---|---|---|---|
| 01 | `01_Tong_quan_he_thong.png` | Tổng quan toàn hệ thống theo 6 nhóm nghiệp vụ, hiển thị cả 3 vai trò và tác vụ CLI | ADMIN, REVIEWER, LECTURER, CLI |
| 02 | `02_Quan_tri_vien_ADMIN.png` | Toàn bộ 22 Use Case của Quản trị viên, phân nhóm chi tiết | ADMIN |
| 03 | `03_Phe_duyet_vien_REVIEWER.png` | 8 Use Case của Phê duyệt viên | REVIEWER |
| 04 | `04_Giang_vien_LECTURER.png` | 6 Use Case của Giảng viên | LECTURER |
| 05 | `05_Nhap_du_lieu.png` | Nhập CSV Scopus, nhập JSON giảng viên, hoàn tác, quản lý đợt nhập | ADMIN, CLI |
| 06 | `06_Quan_ly_ho_so_tai_khoan.png` | Quản lý hồ sơ giảng viên, tạo tài khoản LECTURER/REVIEWER, xem tác giả Scopus, hồ sơ cá nhân | ADMIN, LECTURER |
| 07 | `07_Quan_ly_cong_bo.png` | Xem danh sách và chi tiết công bố (ADMIN/REVIEWER), xem công bố của tôi (LECTURER) | ADMIN, REVIEWER, LECTURER |
| 08 | `08_Chuan_hoa_doi_soat_phe_duyet.png` | Chuẩn hóa công bố, bóc tách tác giả Scopus, sinh ứng viên đối sánh (CLI), xem hàng đợi, duyệt ACCEPT/REJECT, lịch sử review | ADMIN, REVIEWER, CLI |
| 09 | `09_Tim_kiem_thong_ke_xuat.png` | Tra cứu tổng hợp, thống kê dashboard, xuất JSON công bố và giảng viên | ADMIN, REVIEWER |
| 10 | `10_Xac_thuc_dang_nhap_giam_sat.png` | Đăng nhập/xuất, nhận thông báo, xem nhật ký kiểm toán | ADMIN, REVIEWER, LECTURER |

---

## Ghi chú

**CLI (Kỹ thuật viên vận hành)** — không phải vai trò đăng nhập trong ứng dụng web. Một số tác vụ tiền xử lý (sinh ứng viên đối sánh, nạp dữ liệu Craw) chạy bằng script trước khi ADMIN thao tác trên giao diện.

**Ký hiệu trong sơ đồ:**
- `[một phần]` — chức năng có API nhưng giao diện chưa hoàn chỉnh
- `[API]` — chỉ có API, chưa có trang UI
- `[CLI]` — chỉ chạy bằng script dòng lệnh
- `«include»` — use case bắt buộc gọi use case khác
- `«extend»` — hành vi tùy chọn mở rộng use case chính

**Nguồn sơ đồ:** `docs/design/usecase/diagrams/` (PlantUML) · Dữ liệu: `usecase_map.json`
