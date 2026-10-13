# Ưu tiên 4 — Kiểm toán trước triển khai (JSON + Craw + Matching)

**Ngày:** 13-14/10/2026
**Mốc Git khi bắt đầu:** HEAD `0322f96` (nhánh `main`, working tree sạch ngoài các file `docs/qa/*` untracked từ các nhiệm vụ trước, không thuộc phạm vi này).

---

## 1. Xác minh repository và mốc tham chiếu

| Hạng mục | Mốc báo cáo trước | Kiểm chứng thực tế | Phân loại |
|---|---|---|---|
| HEAD | `0322f96` | Khớp (`git log -1`) | **VERIFIED BY CODE** |
| 979 backend test PASS, 5 skipped | Có | Chạy lại thật trên DB pytest `scopus_ictu_test_pytest_20261013`: **979 passed, 5 skipped, 0 failed** | **VERIFIED BY TEST** |
| Database guard chặn pytest ghi nhầm App DB/E2E DB | Có | Đọc `backend/tests/db_safety_guard.py`, xác nhận allowlist/blocklist/system-identifier đúng thiết kế đã báo cáo | **VERIFIED BY CODE** |
| PostgreSQL cluster `127.0.0.1:55432`, system identifier `7694238084633166136` | Có | `select system_identifier from pg_control_system()` → khớp | **VERIFIED BY TEST** |
| CI GitHub Actions xác nhận sau thay đổi guard | Chưa (ghi đúng) | **Phát hiện lỗi thật**: `.github/workflows/ci.yml` có dòng `DB_SAFETY_GUARD_CI_CONTAINER_NETWORK: "1"` bị lặp 2 lần liên tiếp (YAML duplicate key) — đã sửa còn 1 dòng. CI vẫn **chưa chạy trên GitHub** (không push) | **NOT VERIFIED** (CI thật), lỗi cấu hình đã sửa |
| CSV Scopus mới xuất thật chưa nghiệm thu E2E | Có | Không có hành động mới trong nhiệm vụ này liên quan hạng mục này | **DOCUMENTED ONLY** (giữ nguyên, không đổi) |

### Các báo cáo đã đọc và đối chiếu

| Báo cáo | Vai trò | Ghi chú |
|---|---|---|
| `NO_JSON_FULL_E2E_20261011.md` | Gate 1 CSV-only gốc (11/10) | Xác nhận 660 publications/1.207 authors, 0 lecturers trong App DB — khớp hiện trạng |
| `WITH_JSON_CRAW_FULL_E2E_20261011.md` | **Báo cáo WITH-JSON + Craw gốc (12/10), chưa từng được nhắc trong các nhiệm vụ Ưu tiên 1-3** | Đây là nguồn dữ liệu quan trọng nhất cho nhiệm vụ này — đã chạy E2E thật trên DB test riêng, kết luận cốt lõi: **"Craw không sinh thêm ứng viên nào; nó chỉ thêm bằng chứng công bố cho các cặp đã có"** (mục 5). Số liệu 39/5/34 là số liệu lịch sử của DB test đó, **không phải mốc cần tái lập** |
| `NO_JSON_FINAL_ACCEPTANCE.md`, `PRIORITY_1/2/3_*.md` | Ưu tiên 1-3 | Đã xác nhận trong các nhiệm vụ trước, không đọc lại chi tiết (ngoài phạm vi JSON/Craw) |
| `NO_JSON_SAFETY_AND_JOB_RECOVERY.md` | Guard + job recovery | Khớp code hiện tại |
| `docs/planning/KE_HOACH_V4_HOAN_THIEN_DO_AN_TRUOC_14_10.md` | Kế hoạch luận văn (UC, sơ đồ, báo cáo) | Đọc phần đầu (UC inventory, risk R8 xác nhận `engine.py`/`scoring.py` là stub chết). Phần còn lại (sơ đồ UML/Figma/BPMN) thuộc công việc viết luận văn, **ngoài phạm vi kỹ thuật** của nhiệm vụ này |
| `README.md` | Tài liệu gốc | **Lỗi thời**: ghi "Alembic head: f6a1b2c3d4e5" nhưng head thật là `c7f2a9b1d3e5` (sau Ưu tiên 2-3). Không sửa trong nhiệm vụ này (ngoài phạm vi yêu cầu, không phải lỗi nghiệp vụ) |

---

## 2. Bản đồ chức năng code/API/UI/database

### A. Business Analysis — phân biệt chính xác các luồng nghiệp vụ

| Luồng | Trạng thái | Bằng chứng |
|---|---|---|
| Nhập CSV Scopus | Đầy đủ UI/API | `imports.py`, `ImportsPage` |
| Chuẩn hóa + bóc tách tác giả | Đầy đủ UI/API | `/imports/{id}/normalize`, `/authors/normalize-import/{id}` |
| Đối chiếu đơn vị tác giả (offline/online) | Đầy đủ UI/API (Ưu tiên 1-3) | `affiliations.py`, tab "Đơn vị tác giả" |
| Nhập JSON giảng viên ICTU | Đầy đủ UI/API, idempotent | `POST /lecturers/import/preview`, `/lecturers/import`, hoàn tác |
| Thu thập Craw ICTU | **Chỉ CLI** (`ingest_craw_known_publications.py`) | Không có API/UI |
| Sinh ứng viên đối sánh (candidate generation) | **Chỉ CLI** (`generate_matching_candidates.py`) | Không có API/UI |
| REVIEWER chấp thuận/từ chối danh tính | Đầy đủ UI/API | `reviews.py`, `ApprovalQueuePage` |
| LECTURER xem/liên kết công bố của mình | Đầy đủ UI/API | `/lecturers/me/*` |

**Phân biệt quan trọng (đúng yêu cầu "không nhầm đối chiếu đơn vị với xác minh danh tính"):** đối chiếu đơn vị tác giả (Ưu tiên 1-3, bảng `publication_author_affiliation_*`) trả lời câu hỏi "tác giả này thuộc tổ chức nào tại thời điểm công bố" — hoàn toàn tách biệt khỏi matching/identity (bảng `lecturer_scopus_candidates`/`lecturer_scopus_identities`) trả lời câu hỏi "Scopus Author ID này có phải là giảng viên ICTU cụ thể nào không". Hai luồng dùng bảng khác nhau, không giao nhau, không có code nào trộn lẫn hai khái niệm.

### B. Database & migrations

Alembic head hiện tại: **`c7f2a9b1d3e5`** (12 migration, chain liên tục, xác nhận bằng `alembic heads`/`alembic check` — 1 head, không drift).

**Liên kết giữa các thực thể (đã đọc trực tiếp model):**

| Liên kết | Khóa | Ghi chú |
|---|---|---|
| Lecturer ↔ Craw | `lecturers.repository_profile_url` (unique theo URL hồ sơ DSpace, không qua tên) | `known_publication_ingestion.py:336-351` — map chính xác bằng URL, báo `unmapped` nếu lecturer thiếu URL |
| Lecturer ↔ Scopus Author (ứng viên) | `lecturer_scopus_candidates(lecturer_id, scopus_author_id)` UNIQUE | Candidate root, không phải identity |
| Candidate ↔ bằng chứng | `lecturer_scopus_candidate_observations` (theo từng run) → `lecturer_scopus_candidate_evidence` (`evidence_kind` CHECK chỉ `NAME`/`PUBLICATION`) | Append-only, immutable |
| Candidate ↔ quyết định REVIEWER | `lecturer_scopus_candidate_reviews` (append-only, `action` CHECK `ACCEPT/REJECT/REOPEN`, transition CHECK chặt) | — |
| Identity đã duyệt | `lecturer_scopus_identities` (status `CANDIDATE`/`APPROVED`/…) ← tạo từ `ACCEPT` | `_promote_candidate_evidence_to_identity` |
| User ↔ Lecturer | `users.lecturer_id` nullable (từ migration `f6a1b2c3d4e5`, Ưu tiên 3) | Tài khoản LECTURER không bắt buộc có hồ sơ |
| Publication ↔ Craw | **Gián tiếp qua Lecturer**: `lecturer_known_publications` (DOI/title reconciliation riêng với `publications` thật qua `publication_evidence_enricher.py`) | Không có bảng Publication↔Craw trực tiếp |

**Rủi ro đã kiểm tra, không phát hiện mới:**
- Duplicate candidate root: chặn bằng `UniqueConstraint(lecturer_id, scopus_author_id)` + `ON CONFLICT DO NOTHING` (`candidate_persistence.py:580-591`) — **VERIFIED BY CODE**.
- Ghi đè quyết định REVIEWER: `_get_or_create_root` **không bao giờ** gán lại `status` của root đã tồn tại — chỉ cập nhật `last_seen_at`. Chạy lại generation nhiều lần không đụng tới `ACCEPTED`/`REJECTED` — **VERIFIED BY CODE**.
- Mất chứng cứ nguồn: evidence là append-only, `UniqueConstraint` theo fingerprint chống trùng nhưng giữ nguyên lịch sử — **VERIFIED BY CODE**.
- Dữ liệu mồ côi: `ON DELETE RESTRICT` trên hầu hết FK (trừ 3 CASCADE đã biết từ kế hoạch V4) — không đổi trong nhiệm vụ này.

### C. Thuật toán — đọc code thật, không suy diễn

**`candidate_generator.py` (sinh ứng viên, 305 dòng, đã đọc toàn bộ):**
- Input: `Lecturer.full_name`, `ScopusAuthor.preferred_name` + `ScopusAuthorNameVariant`. **Không đọc Craw, không đọc Publication.**
- 4 rule theo thứ tự cố định: `RULE_EXACT_N0` (NFKC+casefold), `RULE_TITLE_STRIPPED_N0` (bỏ tiền tố học hàm/học vị theo whitelist 5 giá trị quan sát từ bộ 410 giảng viên: `DH.`, `GS.TS.`, `PGS.TS.`, `ThS.`, `TS.`), `RULE_TITLE_STRIPPED_N2` (thêm bỏ dấu tiếng Việt qua NFD+combining strip, `đ→d`), `RULE_TITLE_STRIPPED_N2_FORMAT` (thêm chuẩn hóa dấu phẩy, chỉ áp dụng khi surface value có dấu phẩy).
- Đảo thứ tự tên: **không xử lý** — `normalize_comma_equivalence` chỉ gỡ dấu phẩy giữ nguyên thứ tự token, không hoán vị "Họ Tên" ↔ "Tên Họ".
- Viết tắt tên: **không xử lý** — không có logic khớp "Nguyen V." với "Nguyen Van".
- Trùng tên: **không có cơ chế phân biệt** — mọi lecturer khớp cùng 1 Scopus surface đều sinh candidate riêng (đúng thiết kế, để REVIEWER tự phân biệt — xác nhận qua ca "5 giảng viên Nguyễn Thị Dung cùng đề xuất 1 Scopus ID" trong báo cáo WITH-JSON cũ).
- Thiếu dữ liệu: lecturer không có `full_name` hợp lệ hoặc Scopus author không có surface nào thì không sinh candidate (không lỗi, không rỗng giả).

**`publication_evidence_enricher.py` (làm giàu, 320 dòng, đã đọc toàn bộ):**
- **Chỉ làm giàu candidate đã tồn tại** từ bước trên (dòng 226-231: `for pair, _candidate in candidate_by_pair.items(): if lecturer_id != ...: continue`) — **không bao giờ tạo candidate mới**. Đây là phát hiện cốt lõi khớp đúng báo cáo WITH-JSON cũ.
- DOI reconciliation: `normalize_doi_for_matching` (NFKC+casefold+strip 5 dạng prefix DOI URL) — chỉ dùng để nối `LecturerKnownPublication` ↔ `Publication` thật, không liên quan tới việc suy ra con người.
- Xung đột (DOI_AMBIGUOUS, TITLE_AMBIGUOUS, DOI_TITLE_CONFLICT, SNAPSHOT_LECTURER_MISMATCH) được phát hiện và **loại trừ an toàn**, không tạo evidence giả khi mơ hồ.

**`matching/engine.py`, `matching/scoring.py`:** xác nhận đúng cảnh báo R8 của kế hoạch V4 — **dead code M0 stub**, `raise NotImplementedError`, không được import bởi bất kỳ module nào khác ngoài chính chúng. Không ảnh hưởng tới luồng thật.

**Kết luận thuật toán (không tự tuyên bố chính xác khi chưa có bộ mẫu kiểm chứng):** hệ thống hiện tại là **retrieval theo quy tắc xác định (rule-based exact/near-exact name matching)**, không có trọng số/điểm số/threshold xác suất nào (đúng ADR-004 "thứ tự mạnh-yếu, không phải điểm số"). Không có ground truth/gold labels trong repo — **không công bố precision/recall**.

### D. API và phân quyền

RBAC thực thi ở **backend** qua `require_role()` (`app/api/dependencies.py:170-186`), kiểm tra role trên JWT đã xác thực, trả `403 FORBIDDEN` — không chỉ ẩn nút frontend. Xác nhận qua đọc trực tiếp dependency, không chỉ tin UI.

Candidate generation/Craw ingestion **hoàn toàn không có route** trong `app/api/v1/endpoints/` (grep xác nhận 0 kết quả) — đây là gap cần API mới.

### E. UI/UX — đối chiếu với API thật

| Màn hình | UI tồn tại | API tương ứng | Ghi chú |
|---|---|---|---|
| Nhập JSON giảng viên | ✔ (`ImportsPage`) | ✔ | Đầy đủ |
| Quản lý giảng viên | ✔ (`LecturersPage`) | ✔ | Đầy đủ |
| Review candidates | ✔ (`ApprovalQueuePage`) | ✔ | Đầy đủ, nhưng **không có nút "Chạy sinh ứng viên"** |
| Nạp Craw | **Không tồn tại** | Không | Chỉ CLI |
| Sinh ứng viên | **Không tồn tại** | Không | Chỉ CLI |
| Hồ sơ giảng viên (LECTURER) | ✔ | ✔ | Đầy đủ (Ưu tiên 3) |
| Công bố của tôi | ✔ | ✔ | Đầy đủ |

### F. QA và vận hành

- Regression NO-JSON: xác nhận qua 979 test PASS (không có test nào trong bộ này phụ thuộc JSON/Craw bị fail).
- Database guard: đã xác minh lại hoạt động đúng (phần 1).
- Migration chain: 1 head, không drift.
- Frontend build: chưa chạy lại trong phần kiểm toán này (sẽ chạy ở giai đoạn triển khai/kiểm thử).
- CI: **NOT VERIFIED** — không coi "test suite xanh cục bộ" là bằng chứng CI PASS.

---

## 3. Xác minh trạng thái WITH-JSON

Dữ liệu JSON thật trên máy: `D:\DataFolder\ProjectIctu\DoAn\ictu_lecturers_20261010_090704.json` — tồn tại, chưa đọc nội dung chi tiết trong kiểm toán này (sẽ đọc khi dựng DB E2E WITH-JSON ở Phần V).

| Yêu cầu | Trạng thái | Bằng chứng |
|---|---|---|
| 1. ADMIN nhập JSON theo schema hợp lệ | **CÓ SẴN** | `LecturerImportService`, schema `data/lecturers/schema/ictu_lecturers.schema.json` |
| 2. Kiểm tra hồ sơ sai/trùng/thiếu trường/Unicode/email | **CÓ SẴN** | `preview_lecturer_dataset` trả `conflicts`, `invalid`; báo cáo WITH-JSON cũ xác nhận "16 hồ sơ trùng tên chuẩn hóa" được phát hiện đúng |
| 3. Dữ liệu giảng viên lưu bền vững | **CÓ SẴN** | Bảng `lecturers` + `lecturer_source_snapshots` (provenance) |
| 4. Không bắt buộc nhập lại JSON mỗi lần CSV mới | **CÓ SẴN** | Hai pipeline (CSV Scopus vs JSON giảng viên) hoàn toàn độc lập, không có ràng buộc chéo nào trong code |
| 5. Không tự tạo User account từ hồ sơ giảng viên | **CÓ SẴN** | Xác nhận qua báo cáo cũ: "JSON không có khối `account` → không có tài khoản nào được tạo từ JSON"; `LecturerImportService` không chạm bảng `users` |
| 6. Không tự xác nhận Scopus Author ID vì trùng tên | **CÓ SẴN** | Mọi candidate ở trạng thái `PENDING`, không có auto-approve (ADR-004, xác nhận qua code `candidate_persistence.py` không có đường nào set `ACCEPTED`) |
| 7. Không ghi đè quyết định REVIEWER đã duyệt | **CÓ SẴN** | Xác nhận bằng code ở mục 2.B |
| 8. Tái nhập JSON có quy tắc cập nhật/idempotency rõ ràng | **CÓ SẴN** | `preview`→`import` trả `created/updated/unchanged/conflicts`; SHA-256 chống trùng byte-for-byte |
| 9. CSV-only vẫn hoạt động khi không có JSON | **CÓ SẴN** | Đây chính là toàn bộ phạm vi Ưu tiên 1-3, xác nhận lại bằng 979 test PASS |

**Kết luận mục 3:** luồng WITH-JSON (phần nhập liệu) đã **hoàn thiện và đúng đắn**, không cần viết lại. Gap duy nhất nằm ở bước **sau** nhập liệu: sinh ứng viên và nạp Craw thiếu API/UI.

---

## 4. Kiểm toán Craw ICTU

| Câu hỏi | Trả lời (đọc code + dữ liệu thật trên máy) |
|---|---|
| Nguồn Craw lấy từ đâu | ICTU Repository (DSpace), thu thập bằng `scripts/crawl_dspace_snapshot.py` + `ictu_harvester` (parser_version `ictu_harvester/1.4-full`) |
| Có liên kết nhận diện hồ sơ giảng viên ICTU không | **Có, qua URL hồ sơ** (`repository_profile_url`), không qua so khớp tên |
| Có DOI, tiêu đề, năm, tác giả, đồng tác giả, tổ chức, URL nguồn không | `publications.json` có `title`, `doi`, `year`, `source_id` (URL). **Không thấy trường đồng tác giả/tổ chức** trong cấu trúc `CrawPublicationAttribution` (chỉ `source_publication_url`, `title_raw`, `doi_raw`, `published_year`) |
| Dữ liệu chuẩn hóa ra sao | DOI qua `normalize_doi_for_matching` (NFKC+casefold+strip prefix); title qua `title_normalized` cùng chuẩn normalizer dùng cho Publication |
| Cách tìm công bố Craw tương ứng Scopus | Reconciliation DOI-exact ưu tiên, fallback title-exact, loại trừ khi mơ hồ (nhiều khớp) — `_reconcile_known_publications` |
| Provenance, thời gian thu thập, phiên bản nguồn | `LecturerSourceSnapshot` (append-only, `snapshot_hash`, `source_system='ICTU_CRAW'`, `parser_version`), payload gốc giữ nguyên trong `_known_publication_links` |
| Craw chỉ bổ sung evidence hay giúp phát hiện ứng viên mới | **Hiện tại: chỉ bổ sung evidence** cho candidate đã có từ bước tên (xác nhận mục 2.C) |
| Gọi qua CLI/API/UI | **Chỉ CLI** (`python -m scripts.ingest_craw_known_publications`) |

**Giới hạn quan trọng không được bỏ qua:** dữ liệu Craw hiện có **không chứa danh sách đồng tác giả đầy đủ** của mỗi công bố trong cấu trúc dùng cho matching (`CrawPublicationAttribution` chỉ có title/DOI/year của chính công bố, không có tên các đồng tác giả). Điều này giới hạn khả năng neo danh tính qua "đồng tác giả" — hướng cải tiến phải dựa trên **vị trí tác giả trong Publication Scopus thật** (đã có DOI reconciliation sẵn), không phải dữ liệu đồng tác giả từ Craw.

---

## 5. Kiểm toán candidate generation hiện tại

### Sơ đồ luồng hiện tại (trước cải tiến)

```
Lecturer.full_name ──┐
                      ├─► [4 rule so khớp tên] ──► LecturerScopusCandidate (PENDING)
ScopusAuthor +        │        (candidate_generator.py)
ScopusAuthorNameVariant┘
                                        │
                                        ▼
LecturerKnownPublication (từ Craw) ──► [chỉ làm giàu evidence
  + Publication (Scopus thật)           cho candidate ĐÃ CÓ]
                                        (publication_evidence_enricher.py)
                                        │
                                        ▼
                              CandidatePersistenceService
                              (ghi observation + evidence,
                               KHÔNG đụng status đã quyết)
                                        │
                                        ▼
                              REVIEWER duyệt qua /reviews
```

### Bảng so sánh trước cải tiến

| # | Câu hỏi | Trả lời (đọc code, không mặc định số liệu cũ) |
|---|---|---|
| 1 | Candidate sinh từ đâu | Chỉ từ so khớp tên (`generate_candidates`), 4 rule cố định |
| 2 | Điều kiện khiến ứng viên bị bỏ sót | Tên không khớp bất kỳ rule nào trong 4 rule (đảo thứ tự, viết tắt không chuẩn, lỗi chính tả, tên đệm khác) |
| 3 | Có bị giới hạn bởi "normalized name phải trùng trước" | **Có, tuyệt đối** — đây chính là nút thắt cổ chai duy nhất của toàn bộ pipeline hiện tại |
| 4 | Craw liên kết lecturer/publication qua khóa nào | `repository_profile_url` (lecturer) + DOI/title reconciliation (publication) |
| 5 | Có tìm đúng vị trí tác giả trong bài Scopus không | Có — `publication_evidence_enricher` dùng `PublicationAuthor` để lọc đúng `scopus_author_id` xuất hiện ở publication đó (dòng 214-216, 226-231), không chỉ khớp DOI công bố mà bỏ qua vị trí tác giả |
| 6 | Trùng DOI/title có bị dùng sai để suy hai người là một không | **Không** — enrichment chỉ gắn thêm bằng chứng vào candidate (lecturer, scopus_author) đã tồn tại từ bước tên; DOI/title không tự tạo khẳng định danh tính nào |
| 7 | REVIEWER xem được bằng chứng nào | Cả `CandidateEvidence` (tên) và `PublicationEvidence` (DOI/title) qua `/reviews/candidates/{id}` — xác nhận UI hiện có hiển thị đủ cả 2 loại (báo cáo WITH-JSON cũ, mục 6) |
| 8 | Sinh lại candidates có tôn trọng quyết định cũ không | **Có**, xác nhận bằng code (mục 2.B) |

**Số liệu 39 ứng viên / 5 có evidence Craw (báo cáo WITH-JSON cũ):** đây là số liệu đo trên DB test `scopus_ictu_test_withjson_r2_20261011` tại thời điểm 12/10, **không phải mốc cố định của hệ thống** — phụ thuộc hoàn toàn vào tập 410 lecturer + 660 publication + Craw cụ thể nạp vào DB đó. Nhiệm vụ này sẽ đo lại số liệu thật trên DB WITH-JSON mới dựng ở Phần V, không giả định số cũ còn đúng.

---

## 6. Bảng GAP

| Requirement | Hiện trạng | Bằng chứng | Hành vi thiếu | Mức độ | Đề xuất thay đổi | Test bắt buộc |
|---|---|---|---|---|---|---|
| ADMIN khởi chạy sinh ứng viên qua UI | Chỉ CLI | `generate_matching_candidates.py`, không có route API | Không thể demo/vận hành qua web | **Cao** | API `POST /matching/candidates/generate` (ADMIN-only) gọi lại đúng `CandidateGenerator`+`PublicationEvidenceEnricher`+`CandidatePersistenceService` hiện có, tự sinh `run_id`; UI nút "Chạy sinh ứng viên" trong trang quản trị | RBAC, idempotent khi gọi 2 lần liên tiếp, không ghi đè ACCEPTED/REJECTED |
| ADMIN nạp Craw qua UI | Chỉ CLI | `ingest_craw_known_publications.py` | Không thể demo/vận hành qua web | **Cao** | API `POST /matching/craw/ingest` (ADMIN-only, đọc thư mục Craw đã cấu hình sẵn — cùng mẫu an toàn với `AFFILIATION_SOURCE_DIR`, không nhận path từ request) gọi `KnownPublicationIngestionService`; UI xem preview trước khi áp dụng | Preview/apply tách biệt, không nhận path tùy ý, RBAC |
| Craw chỉ bổ sung evidence, không phát hiện candidate mới | Xác nhận đúng (mục 2.C, mục 5) | `publication_evidence_enricher.py:226-231` | Giảng viên có `LecturerKnownPublication` trùng DOI với 1 Publication Scopus, nhưng **tên không khớp bất kỳ rule nào** → không bao giờ có candidate, dù vị trí tác giả rõ ràng tồn tại trong Publication đó | **Trung bình-Cao** (đúng trọng tâm yêu cầu "Craw-assisted candidate discovery") | **Đã triển khai** `app/services/matching/craw_assisted_discovery.py`. Bản đầu tiên chỉ neo vào vị trí tác giả (author position) đơn thuần — đã tự phát hiện đây là lỗi mass-candidate-generation thật (một công bố 5 tác giả sẽ sinh 5 candidate chỉ vì 1 giảng viên có known-publication trùng DOI) và sửa lại thành **quy tắc 2 neo bắt buộc đồng thời**: (1) vị trí tác giả thật qua `PublicationAuthor` trên publication đã reconcile DOI/title-exact không ambiguous, VÀ (2) có ít nhất 1 token tên (sau chuẩn hóa N2, độ dài ≥2) trùng giữa tên giảng viên và tên/biến thể tên của đúng Scopus Author ở vị trí đó. Vị trí tác giả thỏa (1) nhưng fail (2) **không trở thành candidate** — trả về riêng dưới dạng `unattributed` (bằng chứng công bố có thật nhưng chưa quy thuộc về ai) để ADMIN/REVIEWER nhìn thấy mà hệ thống không tự bịa danh tính | Candidate mới có đủ 2 neo danh tính, REVIEWER thấy rõ nguồn gốc khác với candidate từ tên (`evidence=()` rỗng), không tự APPROVE. Test bắt buộc: công bố 5 tác giả/1 khớp tên → đúng 1 candidate + 4 unattributed (`test_five_author_publication_with_one_ictu_match_does_not_mass_generate`, cả bản thuần logic và bản E2E qua API) |
| `evidence_kind` CHECK chỉ `NAME`/`PUBLICATION` | Xác nhận (`candidate.py:219`) | — | Candidate mới sinh từ Craw cần phân biệt rõ là "chỉ có bằng chứng công bố, chưa có bằng chứng tên" để REVIEWER không hiểu nhầm là candidate mạnh như loại có cả 2 | **Thấp** | **Không cần thay đổi CHECK constraint** — dùng lại đúng `evidence_kind='PUBLICATION'` đã có sẵn (không migration), chỉ cần candidate có `evidence=()` (rỗng, không rule tên nào khớp) + `publication_evidence` khác rỗng là đủ để UI phân biệt | Test xác nhận REVIEWER UI hiển thị đúng "không có bằng chứng tên" khi evidence rỗng |
| Không có migration mới cần thiết cho GAP trên | — | — | — | — | **Quyết định: không cần migration.** Thiết kế trên tái dùng 100% schema hiện có (`LecturerScopusCandidate`, `..._observations`, `..._evidence` với `evidence_kind='PUBLICATION'`) | — |
| README lỗi thời (Alembic head sai) | `f6a1b2c3d4e5` ghi trong README, thật là `c7f2a9b1d3e5` | — | Gây nhầm lẫn khi đọc tài liệu | **Thấp** | Có thể sửa nhỏ, không bắt buộc cho Ưu tiên 4 | — |
| CI workflow duplicate key | Xác nhận, **đã sửa** trong kiểm toán này | `.github/workflows/ci.yml` | — | Thấp (đã xử lý) | Đã xóa dòng trùng | Không cần test riêng (cấu hình) |

---

## 7. Quyết định thiết kế — KHÔNG cần dừng xin ý kiến

Theo đúng quy tắc Phần III của yêu cầu: "nếu chỉ cần bổ sung logic/service/API/UI trong kiến trúc hiện tại và có thể kiểm thử an toàn, được phép triển khai tiếp."

Toàn bộ GAP đã liệt kê ở mục 6 **không yêu cầu**:
- Migration phức tạp hay phá compatibility (tái dùng bảng/CHECK hiện có).
- Thay đổi định nghĩa `VERIFIED`/`APPROVED` (candidate mới từ Craw vẫn vào đúng vòng đời `PENDING` → REVIEWER quyết định, không có đường tắt).
- Thay đổi policy matching đã chốt (ADR-004 "không điểm số, không auto-approve" được giữ nguyên tuyệt đối — candidate Craw-assisted vẫn chỉ là **đề xuất chờ duyệt**).
- Sửa dữ liệu thật (chỉ đọc Craw/JSON, ghi vào DB test).

**Quyết định kỹ thuật đã chốt, ghi lại để minh bạch:**
1. Candidate Craw-assisted **bắt buộc neo vào vị trí tác giả thật trong Publication Scopus** (qua `PublicationAuthor`) **VÀ** có tương quan tên độc lập (token tên trùng, sau chuẩn hóa N2) — không chỉ DOI equality, và không chỉ vị trí tác giả đơn thuần. Đây là điểm đã tự sửa sau khi phát hiện bản đầu (chỉ dùng vị trí tác giả) sẽ sinh candidate cho MỌI tác giả trên một công bố đã reconcile, kể cả người không liên quan gì tới giảng viên — đúng yêu cầu "DOI hoặc title khớp chỉ chứng minh hai bản ghi nói về cùng một công bố, chưa chứng minh ai là tác giả nào", và vị trí tác giả riêng lẻ cũng không đủ khi công bố có nhiều tác giả.
2. Không tự động nâng candidate Craw-assisted lên `ACCEPTED`/identity `APPROVED` dù điểm "mạnh" tới đâu — REVIEWER luôn là người quyết định cuối.
3. Không đoán đơn vị tác giả từ Craw — phạm vi Craw trong nhiệm vụ này chỉ phục vụ matching người, **không** đụng tới bảng `publication_author_affiliation*` (đã đóng ở Ưu tiên 1-3).
4. API nạp Craw đọc từ thư mục cấu hình sẵn qua biến môi trường (theo đúng mẫu `AFFILIATION_SOURCE_DIR` đã dùng cho đơn vị tác giả), **không nhận đường dẫn tùy ý từ request** — tránh path traversal/gọi lệnh hệ thống tùy ý.
5. API sinh ứng viên không nhận tham số nào từ request ngoài xác nhận (giống `apply` affiliation) — toàn bộ logic xác định đầu vào nằm trong service, request chỉ là lệnh "chạy".

**Không có hạng mục nào trong hành động mục 6 cần dừng xin quyết định của bạn.** Tiến hành triển khai ở Phần IV.
