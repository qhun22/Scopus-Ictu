# Bộ tài sản phân tích và thiết kế — Scopus–ICTU (Task 19)

> **Mục đích:** các tài sản phân tích nghiệp vụ và thiết kế CSDL theo đề cương GVHD (PI 1.1 → 2.2), dựng **từ mã nguồn và lược đồ PostgreSQL thật**, có file nguồn chỉnh sửa được và bản xuất dùng được trong báo cáo.
> **Phiên bản:** 1.0 · ngày 09/10/2026 · `MANIFEST.json` ghi SHA-256 từng tệp, commit, `alembic_version` và phiên bản công cụ.
> **Quyết định đã chốt (Task 19):** D1 — năm sơ đồ cũ trong `DoAn.docx` **không** dùng làm sơ đồ chính thức (giữ nguyên tài liệu gốc; khác biệt ở `database/DOI_CHIEU_SO_DO_CU.md`); D2 — Figma thật là bắt buộc nhưng **chưa có** (chuẩn bị đầu vào cho Task 20); D11 — công cụ render tải từ nguồn chính thức có xác minh; D12 — chỉ đọc DB.

## 0. Tuyên bố trung thực (đọc trước)

- Phần mềm **chưa đáp ứng đầy đủ đề cương**. Các khoảng cách được liệt kê, không che giấu, ở **`gap/GAP_DE_CUONG_VS_CODE.md`** (20 GAP). Nghiêm trọng nhất: trường *nguồn xuất bản* của mọi công bố đang là `Scopus` (đọc nhầm cột CSV) và không có thực thể nguồn xuất bản; chưa có tập đối chiếu GVHD/đánh giá chất lượng; chưa có Figma; gợi ý đối sánh chỉ dựa trên tên + công bố đã biết, không có điểm "mức độ phù hợp".
- **Figma: CHƯA CÓ.** Không có tệp Figma; không công cụ Figma trong phiên; không PNG/SVG nào được gọi là Figma.
- **Không có kết quả đánh giá chất lượng đối sánh** (precision/recall/F1) nào, và không có nhãn nào được tạo.
- Mọi sơ đồ chỉ chứa **bảng, quan hệ, use case, API có thật**; không có `approval_queue`, `standardized_data`, `export_audit_log`, `publication_sources`… (kiểm tự động).
- Tài liệu có hỗ trợ của công cụ AI trong biên soạn. Sinh viên cần tự đọc, hiểu, kiểm lại và diễn đạt bằng lời của mình trước khi dùng trong báo cáo; đồng thời xác nhận quy định của Khoa/Trường về khai báo sử dụng công cụ AI.

## 1. Cấu trúc thư mục

```
docs/design/
├── README.md · MANIFEST.json
├── requirements/
│   ├── 00_MA_TRAN_YEU_CAU_GVHD.md        Ma trận yêu cầu GVHD ↔ chức năng ↔ CSDL ↔ API ↔ bằng chứng (PI 1.1–2.2, +2.3)
│   └── 01_FR_NFR.md / .csv               33 FR + 15 NFR, mã ổn định (nguồn: tools/fr_nfr_data.py)
├── process/
│   ├── BPMN-1_quy_trinh_thuc_te.bpmn     BPMN 2.0 (nguồn chỉnh sửa) · render/*.svg, *.png
│   └── BPMN-1_bang_buoc.md               bảng bước: người thực hiện, vào/ra, API, bảng ghi, test
├── usecase/
│   ├── usecase_map.json                  nguồn sự thật của sơ đồ + bảng UC
│   ├── UC_INVENTORY.md · ACTOR_UC_MATRIX.md · RBAC_API_MATRIX.csv/.json (57 API, quyền rút từ mã)
│   ├── diagrams/UCD-0A…0C (3 actor), UCD-1…UCD-6 (theo nhóm) *.puml · render/
│   └── specs/UCS-G1…G5, UCS-XT            28 đặc tả UC (13 mục mỗi UC)
├── architecture/ ARC-1 (kiến trúc), DFD-1 (luồng dữ liệu) *.puml · render/
├── database/
│   ├── source/schema_snapshot.json       lược đồ thật trích chỉ-đọc · descriptions_vi.json (mô tả nghiệp vụ)
│   ├── DATA_DICTIONARY.md/.csv           24 bảng, 245 cột
│   ├── KEYS_RELATIONS.md                 24 PK, 30 FK (cardinality), 16 UNIQUE, 7 partial unique, chỉ mục
│   ├── CONSTRAINTS_CATALOG.md            99 CHECK nhóm theo loại · CONSTRAINTS_BUSINESS_RULES.md (giải thích)
│   ├── NGUYEN_TAC_THIET_KE_DU_LIEU.md    chống trùng, thô/chuẩn hóa, vị trí tác giả, affiliation, duyệt danh tính
│   ├── ORM_MIGRATION_DB_PARITY.md        so khớp ORM ↔ Alembic ↔ DB (1 chênh lệch đã giải thích)
│   ├── DOI_CHIEU_SO_DO_CU.md             5 sơ đồ cũ trong DoAn.docx ↔ thực tế
│   ├── erd/ERD-0 (tổng thể), ERD-A…F (6 cụm), scopus_ictu.dbml · render/
│   └── class/CLS-0 (khóa), CLS-A…F (6 cụm, đủ cột) · render/
├── gap/GAP_DE_CUONG_VS_CODE.md           20 GAP: yêu cầu PDF, hiện trạng, hệ quả, cấp thiết, phương án
├── figma_handoff/ FIGMA_HANDOFF_TASK20.md · screens.json      đầu vào Task 20 (Figma CHƯA có)
└── tools/                                 script sinh/kiểm/render (xem §4)
```

## 2. Danh mục sơ đồ (mỗi sơ đồ có nguồn + SVG + PNG)

| Nhóm | Sơ đồ | Số lượng | Nguồn | Xuất |
|---|---|--:|---|---|
| ERD | ERD-0 tổng thể (24 bảng, 30 FK) · ERD-A…F (6 cụm, đủ cột) | 7 | `database/erd/*.puml` + `scopus_ictu.dbml` | SVG + PNG |
| Lớp UML (Entity/Class) | CLS-0 (cột khóa) · CLS-A…F (6 cụm, đủ cột; CASCADE = composition) | 7 | `database/class/*.puml` | SVG + PNG |
| Use Case | UCD-0A/0B/0C (ADMIN/REVIEWER/LECTURER) · UCD-1…UCD-6 (theo nhóm nghiệp vụ) | 9 | `usecase/diagrams/*.puml` (sinh từ `usecase_map.json`) | SVG + PNG |
| BPMN | BPMN-1 quy trình thực tế (5 làn, 25 nút, 26 luồng) | 1 | `process/*.bpmn` | SVG + PNG (6660×1960) |
| Kiến trúc | ARC-1 (giao diện — Web API — dữ liệu + CLI + nguồn tệp) | 1 | `architecture/ARC-1_*.puml` | SVG + PNG |
| Luồng dữ liệu | DFD-1 (mức 1) | 1 | `architecture/DFD-1_*.puml` | SVG + PNG |
| **Tổng** | | **26** | 25 `.puml` + 1 `.bpmn` | |

**Chưa làm trong Task 19 (nêu thật):** sequence/activity/state diagram; sơ đồ triển khai; thiết kế Figma/mockup; ảnh chụp độ phân giải cao; hồ sơ thuật toán; kịch bản sao lưu–phục hồi; đánh giá chất lượng đối sánh.

## 3. Cách mở, chỉnh sửa và render

| Loại tệp | Mở/chỉnh | Xuất |
|---|---|---|
| `.puml` (ERD, lớp, use case, kiến trúc, DFD) | Bất kỳ trình soạn văn bản; xem trực tiếp bằng PlantUML (extension VS Code "PlantUML" hoặc trình xem web PlantUML). **Phần tự sinh** (ERD, lớp, use case) có dòng ghi chú đầu tệp: sửa **nguồn sinh** (`schema_snapshot.json`, `usecase_map.json`) rồi chạy lại script, đừng sửa tay | `python -X utf8 tools/render.py [thư_mục_con]` |
| `.dbml` | Dán vào <https://dbdiagram.io> để xem/chỉnh/xuất ảnh (đã kiểm cú pháp bằng `@dbml/core`: 24 bảng, 30 quan hệ) | trong dbdiagram.io |
| `.bpmn` | Mở tại <https://demo.bpmn.io> hoặc Camunda Modeler; sửa trực tiếp; (đã kiểm bằng bpmn-js 17.11.1: nhập 0 cảnh báo, 82 phần tử) | trong bpmn.io |
| `render/*.svg` | Mở bằng trình duyệt; vector, phóng to không vỡ; chèn vào Word/PowerPoint được | — |
| `render/*.png` | PNG độ phân giải cao (PlantUML `dpi 160`; BPMN x2) để chèn báo cáo | — |
| `.md`/`.csv` | Văn bản; CSV mở bằng Excel (UTF-8 BOM) | — |

**Chuẩn bị công cụ render** (một lần; tải từ nguồn chính thức, đã kiểm SHA-256 — xem `_quan_ly_do_an\tools\plantuml\SOURCE.txt` và `…\graphviz\SOURCE.txt`, ngoài Git):

1. Java (đã có). 2. `plantuml-1.2026.8.jar` (GitHub release chính thức; SHA-256 `5e1ecfa8…c462`). 3. Graphviz 16.1.0 `dot.exe` (gói zip chính thức; SHA-256 `733e4962…6abc`) — nếu thiếu, `render.py` tự dùng bố cục smetana (kém đẹp hơn). Đường dẫn mặc định nằm ở đầu `tools/render.py`; có thể truyền `--jar`, `--dot`.
4. PNG của BPMN: `python -X utf8 tools/render_svg_png.py process/render/BPMN-1_quy_trinh_thuc_te.svg` (Edge/Chrome headless).

## 4. Tái sinh và kiểm tra (`tools/`)

| Script | Việc | Cần |
|---|---|---|
| `extract_schema.py --env-file … --out database/source/schema_snapshot.json` | Trích lược đồ thật ở chế độ **READ ONLY** (từ chối cổng 5432; không in mật khẩu) | psycopg2 + cụm PostgreSQL demo bật |
| `orm_parity.py --backend-dir ../../backend …` | So khớp ORM ↔ Alembic ↔ DB → `ORM_MIGRATION_DB_PARITY.md` | môi trường backend (không DB) |
| `gen_database_assets.py` | Sinh DATA_DICTIONARY, KEYS_RELATIONS, CONSTRAINTS_CATALOG, ERD, DBML, lớp UML | chỉ snapshot + descriptions |
| `rbac_matrix.py --backend-dir …` | Rút quyền từng API từ mã FastAPI → `RBAC_API_MATRIX` | môi trường backend (không DB) |
| `gen_usecase_assets.py` | Sinh sơ đồ use case + `UC_INVENTORY.md` + `ACTOR_UC_MATRIX.md` | `usecase_map.json` |
| `gen_bpmn.py` | Sinh `.bpmn` + SVG từ mô hình quy trình trong tệp | — |
| `gen_requirements.py` | Sinh `01_FR_NFR.md/.csv`; kiểm tên test có thật | `fr_nfr_data.py` |
| `render.py`, `render_svg_png.py` | Xuất SVG/PNG | Java, PlantUML, Graphviz, Edge |
| **`check_consistency.py`** | **Cổng PASS**: FK trong hình = 30 FK DB; số cột từng bảng; UC ↔ `require_role` (57 API); route UI ↔ `App.tsx`; mọi sơ đồ có SVG+PNG hợp lệ; BPMN XML hợp lệ; không bí mật; đủ 24 bảng/245 cột trong từ điển; tên test trong tài liệu có thật; không có bảng cũ không tồn tại | Python |
| `check_dbml.js` | Kiểm cú pháp DBML bằng `@dbml/core` | Node + `@dbml/core` |
| `gen_manifest.py` | Sinh `MANIFEST.json` (chạy cuối) | — |

Thứ tự tái sinh đầy đủ: `extract_schema` → `orm_parity` → `rbac_matrix` → `gen_database_assets` → `gen_usecase_assets` → `gen_bpmn` → `gen_requirements` → `render` → `render_svg_png` → `check_consistency` → `gen_manifest`.

## 5. Kết quả kiểm tra tại thời điểm bàn giao (chạy `check_consistency.py`)

| Kiểm | Kết quả |
|---|---|
| ERD-0/CLS-0: tập FK trong hình = tập FK trong schema (30), không thừa không thiếu | PASS |
| 6 ERD cụm + 6 lớp cụm: FK và số cột từng bảng khớp schema | PASS |
| 57 API: 54 thuộc ≥ 1 UC + 3 loại trừ có lý do (health/ping) | PASS |
| Hợp actor của UC = `require_role` của từng API | PASS |
| Route giao diện của UC có trong `App.tsx` với vai trò khớp | PASS |
| 25 sơ đồ PlantUML có SVG + PNG hợp lệ; BPMN XML hợp lệ (26 luồng/33 shape/28 edge) | PASS |
| Từ điển dữ liệu: 24 bảng, 245 cột | PASS |
| Tên test pytest trích dẫn trong tài liệu đều tồn tại | PASS |
| Không có mật khẩu/token/chuỗi kết nối; không có bảng cũ không tồn tại | PASS |
| `.bpmn` mở được bằng bpmn-js 17.11.1 (0 cảnh báo); `.dbml` parse được (`@dbml/core`: 24 bảng, 30 ref) | PASS |
| ORM ↔ Alembic ↔ DB | **1 chênh lệch** đã giải thích (ORM thiếu CHECK trên `scopus_imports.normalization_summary`) — không sửa trong Task 19 |

## 6. Giới hạn của bộ tài sản (nêu thật)

- Schema lấy từ **DB demo teacher** (`alembic a9c2e4f71b30`) ở chế độ chỉ đọc; số dòng là dữ liệu demo, **không phải dữ liệu thật của ICTU**.
- Biểu thức CHECK ORM↔DB chỉ so theo **tên**; **chưa chạy `alembic upgrade head` trên DB trống** (Task 19 cấm migration).
- Quyền API rút từ cây phụ thuộc FastAPI (`require_role`, `get_current_user`); phần giao diện ẩn menu chỉ để tiện.
- Mô tả cột/bảng (`descriptions_vi.json`) và đặc tả UC do người/AI biên soạn từ mã và test; đã kiểm tên test, mã lỗi, API, bảng — nhưng **nội dung diễn giải cần sinh viên đọc lại**.
- Số liệu 797 test PASS và kết quả E2E trình duyệt là **THEO BÁO CÁO TRƯỚC** (Task 16–17); Task 19 không chạy lại test.
- Sơ đồ BPMN rất rộng (3330×980 px; PNG 6660×1960) — khi chèn vào báo cáo nên dùng trang ngang hoặc cắt theo làn.

## 7. An toàn đã tuân thủ trong Task 19

Không ghi teacher DB (phiên `READ ONLY`, kiểm `transaction_read_only = on`) · không migration · không đổi mã sản phẩm/luật đối sánh/auth/RBAC · không sửa CSV/JSON/Craw · không dùng PostgreSQL 5432 · không push · không tạo launcher. Cụm PostgreSQL demo (55432) đã được khởi động để đọc lược đồ và truy vấn thống kê chỉ-đọc, rồi được dừng lại.
