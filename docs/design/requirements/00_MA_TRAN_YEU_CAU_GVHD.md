# Ma trận yêu cầu GVHD ↔ chức năng thực tế ↔ CSDL ↔ API ↔ bằng chứng

> **Nguồn yêu cầu:** đề cương chính thức `01.DTC235200899.Trương Quang Huy.CN CNTT K22A.pdf` (mục 7b "Yêu cầu chi tiết" theo PI; mục 5; mục 7a). Văn bản PDF mất dấu khi trích; các dòng "Yêu cầu" dưới đây là **bản đọc lại cần đối chiếu với PDF gốc**.
> **Phạm vi Task 19:** PI-1.1, PI-1.2, PI-1.3, PI-2.1, PI-2.2 (đầy đủ), PI-2.3 (chỉ chuẩn bị đầu vào Figma). Các PI/ yêu cầu khác: xem `gap/GAP_DE_CUONG_VS_CODE.md`.
> **Nguyên tắc:** không mô tả chức năng chưa triển khai là đã hoàn thành. Cột **Mức** dùng: **ĐÁP ỨNG** · **MỘT PHẦN** · **CHƯA** (và tham chiếu GAP).
> "Tài sản T19" = tệp do Task 19 tạo trong `docs/design/`. Số liệu CSDL là snapshot 09/10/2026 (alembic `a9c2e4f71b30`).

## 1. PI-1.1 — Khảo sát quy trình, BPMN và mô tả từng bước

| Mã | Yêu cầu (đề cương) | Chức năng thực tế (UC) | CSDL (bảng) | API / script | Bằng chứng (tài sản T19 · test) | Mức | GAP |
|---|---|---|---|---|---|---|---|
| 1.1-a | Khảo sát quy trình tiếp nhận, xử lý và duyệt dữ liệu Scopus do GVHD cung cấp | Quy trình có thật: nhập CSV/JSON → dữ liệu thô → chuẩn hóa → bằng chứng → ứng viên → duyệt → khai thác (UC-08/10/11/12/24/17/18/21/22) | `scopus_imports`, `raw_scopus_records`, `publications`, `lecturer_scopus_candidates`, `lecturer_scopus_identities`… | `/imports/*`, `/reviews/*`; scripts CLI | `process/BPMN-1_bang_buoc.md`; `architecture/DFD-1_luong_du_lieu`; `docs/demo/HUONG_DAN…` ch.5 | **MỘT PHẦN** — quy trình được mô tả theo **phần mềm đã làm**; chưa có biên bản khảo sát nhu cầu/nguồn dữ liệu với GVHD | — |
| 1.1-b | Có sơ đồ quy trình nghiệp vụ **BPMN** | — | — | — | `process/BPMN-1_quy_trinh_thuc_te.bpmn` (+ `.svg`/`.png`); đã mở được bằng bpmn-js 17.11.1 (0 cảnh báo) | **ĐÁP ỨNG** (quy trình *thực tế*; sơ đồ cũ trong `DoAn.docx` bị thay — `database/DOI_CHIEU_SO_DO_CU.md`) | — |
| 1.1-c | Mô tả từng bước, người thực hiện, đầu vào/đầu ra | 25 nút BPMN gồm 5 làn: ADMIN, Hệ thống, Kỹ thuật viên, REVIEWER/ADMIN, LECTURER | Xem cột "Dữ liệu ghi" trong bảng bước | Xem cột UC/API/script | `process/BPMN-1_bang_buoc.md` (bảng bước kèm test) | **ĐÁP ỨNG** | — |

## 2. PI-1.2 — Yêu cầu chức năng và phi chức năng

| Mã | Yêu cầu (đề cương) | Chức năng thực tế | CSDL | API | Bằng chứng (tài sản T19 · test) | Mức | GAP |
|---|---|---|---|---|---|---|---|
| 1.2-a | Bảng yêu cầu **chức năng** | 33 FR gắn UC/API/test | — | — | `requirements/01_FR_NFR.md/.csv` (FR-001…FR-054; tên test đã kiểm tồn tại) | **ĐÁP ỨNG** về tài liệu (bản nháp); trạng thái từng FR nêu rõ (ĐÃ TRIỂN KHAI/MỘT PHẦN) | GAP-12 |
| 1.2-b | **Phân quyền** | RBAC 3 vai trò, 57 API đã gán quyền | `users.role` + CHECK | `require_role` | NFR-002; `usecase/RBAC_API_MATRIX.csv`; `test_review_api::test_lecturer_cannot_access_review_api` | **ĐÁP ỨNG** | — |
| 1.2-c | **An toàn dữ liệu** | Argon2id, cookie httponly, ràng buộc DB, không bí mật trong Git | `users.password_hash`, CHECK | `/auth/*` | NFR-001, NFR-003, NFR-010 | **MỘT PHẦN** — thiếu giới hạn đăng nhập sai, không mã hóa lưu trữ | GAP-16 |
| 1.2-d | **Truy vết chỉnh sửa** | Audit chỉ-thêm; lịch sử review; provenance | `audit_events`, `…_candidate_reviews`, `publication_raw_sources` | `/audits`, `/reviews/history` | NFR-004, NFR-005; `test_audit_api`, `test_review_history_api` | **MỘT PHẦN** — chỉ-thêm không do DB cưỡng chế; đăng nhập không audit | GAP-16 |
| 1.2-e | **Sao lưu** | Chỉ thao tác `pg_dump`/`pg_restore` rời rạc | (toàn DB) | — | NFR-007 | **CHƯA** có kịch bản/hướng dẫn chính thức | GAP-10 |
| 1.2-f | **Khả năng sử dụng** | Giao diện tiếng Việt, Error Boundary, bộ lọc | — | — | NFR-008, NFR-009 | **MỘT PHẦN** — chưa có bằng chứng điện thoại | GAP-13 |
| 1.2-g | **Tiêu chí nghiệm thu thống nhất với GVHD** | Tiêu chí đề xuất nằm trong cột "Điều kiện nghiệm thu" | — | — | `01_FR_NFR.md` | **CHƯA** — chưa có xác nhận của GVHD | GAP-12 |

## 3. PI-1.3 — Use Case và đặc tả ít nhất 5 UC chính

Đề cương nêu năm UC chính: **nhập dữ liệu; quản lý hồ sơ tác giả; quản lý công bố; chuẩn hóa/đối soát và phê duyệt; tìm kiếm, thống kê và xuất dữ liệu.**

| Mã | UC chính của đề cương | UC con có thật | CSDL chính | API chính | Bằng chứng (tài sản T19) | Mức | GAP |
|---|---|---|---|---|---|---|---|
| 1.3-0 | Sơ đồ Use Case | 28 UC (22 UI/API + 4 CLI + 2 UC con) | — | — | `usecase/diagrams/UCD-0A…0C, UCD-1…6` (9 sơ đồ); `UC_INVENTORY.md`; `ACTOR_UC_MATRIX.md`; kiểm khớp `require_role` | **ĐÁP ỨNG** | — |
| 1.3-1 | **Nhập dữ liệu** | UC-08, UC-08a, UC-10, UC-10a, UC-25 | `scopus_imports`, `raw_scopus_records`, `lecturers`, `lecturer_source_snapshots` | `/lecturers/import*`, `/imports/*` | `usecase/specs/UCS-G1_nhap_du_lieu.md` (5 đặc tả) | **ĐÁP ỨNG** (CSV không có bước xem trước) | — |
| 1.3-2 | **Quản lý hồ sơ tác giả** | UC-05, UC-06, UC-16, UC-20, UC-21, UC-23 | `lecturers`, `users`, `scopus_authors` | `/lecturers`, `/users`, `/authors`, `/lecturers/me/*` | `UCS-G2_quan_ly_ho_so.md` (6 đặc tả) | **ĐÁP ỨNG** (chi tiết tác giả/UC-23 chỉ API) | GAP-15 |
| 1.3-3 | **Quản lý công bố** | UC-13, UC-22 | `publications`, `publication_authors`, `publication_raw_sources` | `/publications`, `/lecturers/me/publications` | `UCS-G3_quan_ly_cong_bo.md` (2 đặc tả) | **ĐÁP ỨNG** (chỉ đọc; trường nguồn xuất bản sai) | GAP-02 |
| 1.3-4 | **Chuẩn hóa/đối soát và phê duyệt** | UC-11, UC-12, UC-24, UC-17, UC-18, UC-19 | `publications`, `scopus_authors`, `lecturer_scopus_candidates`, `…_reviews`, `lecturer_scopus_identities` | `/imports/{id}/normalize`, `/authors/normalize-import/{id}`, `/reviews/*`; script sinh ứng viên | `UCS-G4_chuan_hoa_doi_soat_phe_duyet.md` (6 đặc tả) | **MỘT PHẦN** — đối sánh chỉ theo tên + công bố; không điểm; không hoàn tác duyệt | GAP-03/04/07 |
| 1.3-5 | **Tìm kiếm, thống kê và xuất dữ liệu** | UC-14, UC-04, UC-15, UC-09 | (đọc) `audit_events` khi xuất | `/search`, `/dashboard/summary`, `/publications/export`, `/lecturers/export` | `UCS-G5_tim_kiem_thong_ke_xuat.md` (4 đặc tả) | **MỘT PHẦN** — thống kê sơ sài; chỉ JSON | GAP-08/09 |
| 1.3-6 | (bổ trợ) Xác thực, thông báo, giám sát, khởi tạo | UC-01, 02, 03, 07, 26 | `users`, `user_notifications`, `audit_events` | `/auth/*`, `/notifications/*`, `/audits` | `UCS-XT_xac_thuc_giam_sat.md` (5 đặc tả) | **ĐÁP ỨNG** | GAP-16 |

**Tổng đặc tả:** 5 nhóm UC chính + 1 nhóm hỗ trợ = **6 tệp, 28 đặc tả UC** (mỗi đặc tả có đủ 13 mục: mã, mục tiêu, actor, điều kiện trước, luồng chính/thay thế/lỗi, điều kiện sau, dữ liệu thay đổi, quyền, API/UI, trạng thái, test).

## 4. PI-2.1 — Mô hình thực thể và thiết kế CSDL

| Mã | Yêu cầu (đề cương) | Thực thể/bảng thật | Khóa / ràng buộc | Bằng chứng (tài sản T19) | Mức | GAP |
|---|---|---|---|---|---|---|
| 2.1-a | Thực thể **hồ sơ tác giả Scopus** | `scopus_authors`, `scopus_author_name_variants` | PK uuid; `uq_scopus_authors_scopus_id`; `uq_author_name_variants` | `database/erd/ERD-D…`; `DATA_DICTIONARY.md` | **ĐÁP ỨNG** | — |
| 2.1-b | **Công bố** | `publications`, `publication_raw_sources` | `uq_publications_eid`; `ck_publications_*` | `ERD-D` | **ĐÁP ỨNG** (DOI chưa chuẩn hóa ở lưu trữ) | GAP-01 |
| 2.1-c | **Tác giả công bố** (vị trí) | `publication_authors` | `uq_publication_authors_author/_order` | `ERD-D` | **ĐÁP ỨNG** | — |
| 2.1-d | **Nguồn xuất bản** | **Không có thực thể**; chỉ `publications.source_title` (chuỗi) — **đang lưu sai `Scopus`** | — | `gap/GAP_DE_CUONG_VS_CODE.md` GAP-02 | **CHƯA** — không tự thêm bảng | GAP-02 |
| 2.1-e | **Ánh xạ/liên kết giảng viên** | `lecturer_scopus_candidates`, `…_observations`, `…_evidence`, `…_candidate_reviews`, `lecturer_scopus_identities`, `identity_evidence` (`mapping_reviews` chưa dùng) | `uq_*_pair`; `uq_identities_scopus_author_approved`; CHECK chuyển trạng thái | `ERD-F` | **ĐÁP ỨNG** | — |
| 2.1-f | **Lô nhập, nguồn dữ liệu** | `scopus_imports`, `raw_scopus_records`; `lecturer_source_snapshots`, `lecturer_known_publications`; `organizations` + 2 bảng affiliation (nguồn ngoài) | `file_sha256`, `row_hash`, `snapshot_hash` | `ERD-B`, `ERD-C`, `ERD-E` | **ĐÁP ỨNG** | — |
| 2.1-g | **Lịch sử chỉnh sửa** | `audit_events`; `…_candidate_reviews` | CHECK actor invariant; chỉ-thêm (quy ước ứng dụng) | `ERD-A`, `ERD-F`; `CONSTRAINTS_BUSINESS_RULES.md` §5–6 | **ĐÁP ỨNG** (chỉ-thêm không do DB cưỡng chế) | GAP-16 |
| 2.1-h | **Khóa định danh, ràng buộc toàn vẹn, nguyên tắc chống trùng** | 24 PK uuid; 30 FK; 16 UNIQUE + 7 partial; 99 CHECK | xem `KEYS_RELATIONS.md`, `CONSTRAINTS_CATALOG.md` | `NGUYEN_TAC_THIET_KE_DU_LIEU.md` §2; `ORM_MIGRATION_DB_PARITY.md` | **ĐÁP ỨNG** | GAP-17 (ORM thiếu 1 CHECK) |
| 2.1-i | Sơ đồ ERD | 1 ERD tổng thể + 6 ERD cụm + 7 sơ đồ lớp UML + DBML | — | `database/erd/*.puml/.dbml` + `render/*.svg/.png`; `database/class/*` | **ĐÁP ỨNG** (FK 30/30 khớp DB — `tools/check_consistency.py`) | — |

## 5. PI-2.2 — Kiến trúc ứng dụng bằng UML và luồng dữ liệu

| Mã | Yêu cầu (đề cương) | Thực tế | Bằng chứng (tài sản T19) | Mức | Ghi chú |
|---|---|---|---|---|---|
| 2.2-a | Kiến trúc UML **tách giao diện web, dịch vụ Web API và tầng dữ liệu** | React/Vite SPA → FastAPI (endpoints → services → repositories → models) → PostgreSQL 17; script CLI và nguồn tệp ngoài; không Redis/Kafka/Celery | `architecture/ARC-1_kien_truc_tong_the` (sơ đồ thành phần UML) | **ĐÁP ỨNG** | Sơ đồ triển khai localhost chưa vẽ (không bắt buộc) |
| 2.2-b | Mô tả luồng **nhập, xử lý, duyệt và xuất** dữ liệu | DFD mức 1 + BPMN | `architecture/DFD-1_luong_du_lieu`; `process/BPMN-1_*` | **ĐÁP ỨNG** | Sequence/Activity diagram chi tiết **chưa làm** (đề xuất Task sau) |

## 6. PI-2.3 — Đầu vào cho Figma (chỉ chuẩn bị; Figma thật CHƯA có)

| Mã | Yêu cầu | Trạng thái | Tài sản T19 |
|---|---|---|---|
| 2.3 | Thiết kế **Figma**: danh sách, chi tiết, nhập dữ liệu, so sánh trước/sau chuẩn hóa, hàng đợi phê duyệt, thống kê | **CHƯA** — chưa có tệp Figma; màn "so sánh trước/sau" **chưa tồn tại trong phần mềm** (`THIẾT KẾ ĐỀ XUẤT — CHƯA TRIỂN KHAI`) | `figma_handoff/FIGMA_HANDOFF_TASK20.md`, `figma_handoff/screens.json` |

## 7. Tổng hợp

| PI | Mức đáp ứng sau Task 19 |
|---|---|
| PI-1.1 | Tài sản đủ cho BPMN + bảng bước; thiếu biên bản khảo sát nhu cầu |
| PI-1.2 | Có bản nháp FR/NFR; **chưa** có xác nhận GVHD; sao lưu/phục hồi chưa có kịch bản (GAP-10, GAP-12) |
| PI-1.3 | Đủ 5 UC chính có sơ đồ và đặc tả; 2 nhóm đáp ứng **một phần** về chức năng (nhóm 4, nhóm 5) |
| PI-2.1 | ERD/Class/Dictionary đầy đủ và khớp DB; thiếu thực thể **nguồn xuất bản** (GAP-02) |
| PI-2.2 | Có kiến trúc + DFD; chưa có sequence/activity |
| PI-2.3 | Chưa có Figma (Task 20) |

**Không tuyên bố:** phần mềm đáp ứng đủ đề cương. Còn các GAP nêu trong `gap/GAP_DE_CUONG_VS_CODE.md`.
