# Ma trận Actor × Use Case

> **Sinh tự động** từ `usecase_map.json`. `●` = được phép · `–` = bị từ chối (API trả 403; giao diện ẩn menu) · `CLI` = chạy bằng script (không phải vai trò). Cột "Khớp mã" = kết quả đối chiếu với `require_role` thật (xem `check_consistency.py`).

| UC | Tên | ADMIN | REVIEWER | LECTURER | Script | Quyền theo mã |
|---|---|:-:|:-:|:-:|:-:|---|
| UC-01 | Đăng nhập | ● | ● | ● | – | mọi vai trò đã đăng nhập |
| UC-02 | Đăng xuất và kiểm tra phiên | ● | ● | ● | – | mọi vai trò đã đăng nhập |
| UC-03 | Nhận thông báo tài khoản | ● | ● | ● | – | mọi vai trò đã đăng nhập |
| UC-04 | Xem thống kê tổng quan (dashboard) | ● | – | – | – | ADMIN |
| UC-05 | Quản lý hồ sơ giảng viên | ● | – | – | – | ADMIN |
| UC-06 | Quản lý tài khoản và phân quyền | ● | – | – | – | ADMIN |
| UC-07 | Xem nhật ký kiểm toán | ● | – | – | – | ADMIN |
| UC-08 | Nhập hồ sơ giảng viên từ JSON (kiểm tra, xem trước, nhập) | ● | – | – | – | ADMIN |
| UC-08a | Hoàn tác đợt nhập hồ sơ giảng viên | ● | – | – | – | ADMIN |
| UC-09 | Xuất hồ sơ giảng viên ra JSON | ● | – | – | – | ADMIN |
| UC-10 | Nhập tệp CSV Scopus | ● | – | – | – | ADMIN |
| UC-10a | Quản lý đợt nhập CSV (hủy, lưu trữ, khôi phục lịch sử, xóa) | ● | – | – | – | ADMIN |
| UC-11 | Chuẩn hóa công bố từ bản ghi thô | ● | – | – | – | ADMIN |
| UC-12 | Bóc tách tác giả Scopus | ● | – | – | – | ADMIN |
| UC-13 | Xem danh sách và chi tiết công bố (kèm đơn vị theo tác giả, nguồn gốc dòng CSV) | ● | ● | – | – | ADMIN/REVIEWER |
| UC-14 | Tra cứu tổng hợp (giảng viên, công bố, tác giả) | ● | ● | – | – | ADMIN/REVIEWER |
| UC-15 | Xuất dữ liệu công bố ra JSON | ● | – | – | – | ADMIN |
| UC-16 | Xem tác giả Scopus (danh sách, thống kê, chi tiết) | ● | – | – | – | ADMIN |
| UC-17 | Xem hàng đợi ứng viên và bằng chứng | ● | ● | – | – | ADMIN/REVIEWER |
| UC-18 | Duyệt ứng viên (ACCEPT / REJECT) | ● | ● | – | – | ADMIN/REVIEWER |
| UC-19 | Xem lịch sử review | ● | ● | – | – | ADMIN/REVIEWER |
| UC-20 | Xem hồ sơ cá nhân | – | – | ● | – | LECTURER |
| UC-21 | Xem liên kết Scopus đã duyệt của tôi | – | – | ● | – | LECTURER |
| UC-22 | Xem công bố của tôi (từ danh tính APPROVED) | – | – | ● | – | LECTURER |
| UC-23 | Quản trị xem hồ sơ/danh tính/công bố Scopus của một giảng viên | ● | – | – | – | ADMIN |
| UC-24 | Sinh ứng viên đối sánh (lưu bền, idempotent) | – | – | – | CLI | — |
| UC-25 | Nạp công bố đã biết (Craw) và đơn vị công tác ngoài (OpenAlex/Crossref) | – | – | – | CLI | — |
| UC-26 | Khởi tạo dữ liệu và tài khoản ADMIN demo | – | – | – | CLI | — |

**Tổng:** ADMIN 22 UC · REVIEWER 8 UC · LECTURER 6 UC · script (CLI) 3 UC.
