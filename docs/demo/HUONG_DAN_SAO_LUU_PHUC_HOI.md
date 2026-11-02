# Hướng dẫn sao lưu và phục hồi cơ sở dữ liệu

Tài liệu này đáp ứng yêu cầu PI 3.1 và 4.1 của đề cương (kịch bản khởi tạo, sao lưu, phục hồi; hướng dẫn sao lưu/phục hồi).
Công cụ: `backend/scripts/db_backup.py`. Chỉ làm việc với cụm PostgreSQL demo (cổng 55432), không bao giờ dùng cổng 5432.

## 1. Sao lưu (kèm chứng minh khôi phục được)

Chạy từ thư mục `backend/`, với môi trường ảo của dự án:

```bash
python -m scripts.db_backup backup
```

Lệnh thực hiện lần lượt:

1. `pg_dump` định dạng custom vào `_postgres_demo_14_10/backups/<db>_backup_<thời điểm>.dump`.
2. Ghi tệp `.sha256` (băm SHA-256 của bản sao lưu) và tệp `.manifest.json` (số bảng, số dòng từng bảng, phiên bản Alembic).
3. **Kiểm chứng khôi phục:** tạo một database tạm, khôi phục vào đó, so sánh số bảng và số dòng từng bảng với bản gốc, rồi **xóa database tạm**. Kết quả được ghi lại trong manifest (`verified_by_restore`).

Thêm `--no-verify` nếu chỉ cần sao lưu nhanh. Bản sao lưu chưa kiểm chứng sẽ không được coi là đã chứng minh khôi phục được.

Kết quả chạy thật ngày 02/11/2026 trên database demo: 43 bảng, 18.597 dòng, khôi phục khớp từng bảng.

## 2. Kiểm tra một bản sao lưu có sẵn

```bash
python -m scripts.db_backup verify --dump <đường dẫn tệp .dump>
```

Kiểm tra SHA-256, khôi phục vào database tạm, so sánh số dòng với manifest, rồi xóa database tạm.

## 3. Phục hồi

```bash
python -m scripts.db_backup restore --dump <tệp .dump> --into <TEN_DATABASE_MOI>
```

Phục hồi luôn đi vào **một database mới**. Muốn thay thế database đang dùng, trước hết khôi phục sang database mới, kiểm tra nội dung, rồi trỏ `DB_NAME` trong `backend/.env` sang database mới.

## 4. Các từ chối an toàn (không phải cảnh báo)

| Tình huống | Hệ thống làm gì |
|---|---|
| Database đích đã tồn tại | Từ chối, không ghi đè |
| Đích là database đang chạy, database của giảng viên hướng dẫn, `postgres`, `template*` | Từ chối |
| Tên đích sai quy ước (chữ thường, số, gạch dưới, 3–63 ký tự) | Từ chối |
| SHA-256 của tệp không khớp, hoặc thiếu tệp `.sha256` | Từ chối |
| Cổng PostgreSQL là 5432 | Từ chối |
| `pg_restore` lỗi giữa chừng | Xóa database vừa tạo, báo lỗi |

Mật khẩu chỉ truyền qua biến môi trường, không xuất hiện trên dòng lệnh hay trong nhật ký.

## 5. Khuyến nghị vận hành

- Sao lưu trước mỗi lần di chuyển schema: trình khởi chạy (`scripts.demo_launcher migrate`) đã tự sao lưu trước khi nâng cấp.
- Giữ bản sao lưu ngoài thư mục mã nguồn và không đưa vào Git (có dữ liệu giảng viên).
- Chạy `verify` định kỳ trên bản sao lưu mới nhất.
