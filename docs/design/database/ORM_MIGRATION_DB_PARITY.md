# So khớp ORM ↔ Alembic ↔ PostgreSQL thật

> Tệp **sinh tự động** bởi `docs/design/tools/orm_parity.py` — không sửa tay. Snapshot: DB `scopus_ictu_demo_teacher_20261014` (PostgreSQL 17.10), trích lúc `2026-10-09T15:10:58+00:00` ở chế độ chỉ đọc.

## 1. Kết luận

**CÓ 1 CHÊNH LỆCH** giữa ORM (`backend/app/models`) và DB trên các mặt: tên bảng, tên/kiểu/NULL của cột, PK, FK (cột, bảng tham chiếu, ON DELETE), UNIQUE, tên CHECK và tên chỉ mục.

- Bảng: ORM 24 · DB 24 · giao nhau 24
- Cột đã so: 245 · PK: 24 · FK: 30 · UNIQUE: 16 · CHECK: 99 · INDEX thường/partial: 52
- Alembic: head trong `alembic/versions` = `a9c2e4f71b30`; `alembic_version` trong DB = `a9c2e4f71b30` → **khớp**
- Chuỗi migration (cũ → mới): `e5b3cf21c1d12b64 → a7d9c4e2f601 → c3f0b9a18d42 → f4c8b1a2e9d7 → b27c9d1e4f60 → d3f7a1c9e2b4 → a9c2e4f71b30` (7 bản, tuyến tính)

### Giới hạn của phép so khớp

- **Biểu thức CHECK** chỉ so theo *tên* (PostgreSQL chuẩn hóa lại biểu thức nên không so chuỗi). Nội dung từng CHECK lấy từ DB, xem `CONSTRAINTS_CATALOG.md`.
- **DEFAULT/server_default** và **comment** không được so.
- **Chưa chạy `alembic upgrade head` trên DB trống** để so migration ↔ DB (Task 19 cấm migration). Việc kiểm migration chỉ ở mức: chuỗi revision tuyến tính, head = `alembic_version` của DB thật.

## 2. Chi tiết chênh lệch

- `scopus_imports`: CHECK chỉ có ở DB `ck_scopus_imports_ck_scopus_imports_normalization_summa_5872`

### Giải thích các chênh lệch đã biết (ghi tay, đã kiểm tra mã nguồn)

- `scopus_imports` — CHECK `ck_scopus_imports_ck_scopus_imports_normalization_summa_5872`: do migration `f4c8b1a2e9d7` (`op.create_check_constraint("ck_scopus_imports_normalization_summary_object", …)`) tạo ra; quy ước đặt tên `ck_%(table_name)s_%(constraint_name)s` được áp thêm một lần nữa nên tên vật lý bị lặp tiền tố và rút gọn kèm hậu tố băm `_5872`. **Mô hình ORM `ScopusImport` không khai báo CHECK này** (`backend/app/models/scopus_raw.py`, cột `normalization_summary`). Hệ quả: DB có ràng buộc `normalization_summary` phải là JSON object hoặc NULL; ORM không phản ánh. Đây là *lệch ORM ↔ migration*, không ảnh hưởng dữ liệu hiện có. **Không sửa trong Task 19** (cấm đổi mã/migration); ghi nhận để sửa sau.

## 3. Thống kê theo bảng (từ DB)

| Bảng | Cột | FK | UNIQUE (ràng buộc) | CHECK | INDEX (thường/partial) |
|---|--:|--:|--:|--:|--:|
| `audit_events` | 16 | 1 | 0 | 7 | 4 |
| `candidate_generation_runs` | 10 | 0 | 0 | 6 | 1 |
| `identity_evidence` | 10 | 1 | 1 | 6 | 1 |
| `lecturer_known_publications` | 10 | 1 | 0 | 1 | 4 |
| `lecturer_scopus_candidate_evidence` | 9 | 1 | 1 | 6 | 1 |
| `lecturer_scopus_candidate_observations` | 7 | 2 | 1 | 2 | 2 |
| `lecturer_scopus_candidate_reviews` | 12 | 4 | 0 | 7 | 3 |
| `lecturer_scopus_candidates` | 9 | 2 | 1 | 2 | 3 |
| `lecturer_scopus_identities` | 10 | 2 | 1 | 4 | 3 |
| `lecturer_source_snapshots` | 11 | 1 | 1 | 4 | 2 |
| `lecturers` | 17 | 0 | 0 | 2 | 4 |
| `mapping_reviews` | 10 | 3 | 0 | 5 | 3 |
| `organizations` | 7 | 0 | 0 | 4 | 3 |
| `publication_author_affiliation_resolutions` | 17 | 1 | 2 | 12 | 2 |
| `publication_author_affiliations` | 8 | 2 | 1 | 4 | 1 |
| `publication_authors` | 5 | 2 | 2 | 1 | 1 |
| `publication_raw_sources` | 4 | 2 | 1 | 0 | 1 |
| `publications` | 19 | 0 | 1 | 4 | 2 |
| `raw_scopus_records` | 10 | 1 | 1 | 5 | 2 |
| `scopus_author_name_variants` | 7 | 2 | 1 | 1 | 2 |
| `scopus_authors` | 5 | 0 | 1 | 1 | 0 |
| `scopus_imports` | 12 | 0 | 0 | 6 | 2 |
| `user_notifications` | 9 | 1 | 0 | 3 | 3 |
| `users` | 11 | 1 | 0 | 6 | 2 |
| **Tổng** | **245** | **30** | **16** | **99** | **52** |
