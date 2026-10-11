# Nguyên tắc thiết kế dữ liệu: chống trùng, thô/chuẩn hóa, vị trí tác giả, đơn vị công tác, duyệt danh tính

> **Mục đích:** giúp sinh viên **hiểu và tự giải thích** thiết kế CSDL (PI-2.1) — mỗi mục nêu *vấn đề → cách thiết kế → bảng/ràng buộc thật → giới hạn*. Nội dung bám schema thật (24 bảng) và ADR 001–004; **không phải văn bản để chép nguyên văn vào báo cáo** — cần diễn đạt lại theo hiểu biết của mình và dẫn ADR/ràng buộc đã kiểm.
> Số liệu "demo" lấy từ DB `scopus_ictu_demo_teacher_20261014` (truy vấn chỉ đọc 09/10/2026), là **dữ liệu demo, không phải dữ liệu thật của ICTU**.

## 1. Bức tranh tổng thể: dòng đời dữ liệu

```
 CSV Scopus ──► scopus_imports ─► raw_scopus_records          (THÔ, bất biến)            C
                                      │ (publication_raw_sources: nguồn gốc)
                                      ▼
                   publications ◄─ publication_authors ─► scopus_authors ◄─ scopus_author_name_variants     D
                                      │ (vị trí tác giả)
                                      ▼
   OpenAlex/Crossref ─► publication_author_affiliation_resolutions ─► publication_author_affiliations ─► organizations   E

 JSON hồ sơ GV ──► lecturers ◄─ lecturer_source_snapshots ◄─ lecturer_known_publications (Craw)      B
                      │
                      ▼  (sinh ứng viên — script)
   candidate_generation_runs ─► lecturer_scopus_candidates ─► …_observations ─► …_evidence                  F
                      │  (người duyệt: ACCEPT / REJECT)
                      ▼
   lecturer_scopus_candidate_reviews ─► lecturer_scopus_identities (APPROVED) ─► identity_evidence           F
                      │
                      ▼
   audit_events (mọi thao tác ghi) · users · user_notifications                                            A
```

| Giai đoạn | Số dòng demo (09/10/2026) |
|---|--:|
| Hồ sơ giảng viên / bản chụp nguồn | 411 / 1.687 (48 từ Craw + 1.639 từ DSpace) |
| Đợt nhập CSV / dòng thô | 1 (APPLIED, 660/660 hợp lệ) / 660 |
| Công bố chuẩn hóa / nguồn gốc | 660 / 660 |
| Tác giả Scopus / dạng tên / vị trí tác giả | 1.207 / 2.768 / 2.751 |
| Công bố đã biết (Craw) | 327 (48 giảng viên) |
| Tổ chức / resolution đơn vị / dòng đơn vị | 217 / 5.502 / 4.147 |
| Ứng viên (PENDING) / quan sát / bằng chứng | 40 / 80 / 203 |
| Review / danh tính / bằng chứng danh tính | 0 / 0 / 0 |
| Nhật ký kiểm toán | 16 |

## 2. Chống trùng (nhập lại không sinh bản ghi trùng)

- **Vấn đề:** cùng một tệp có thể nhập hai lần, cùng một bài xuất hiện ở nhiều tệp, hai tiến trình có thể chạy cùng lúc.
- **Thiết kế:** mỗi thực thể có một **khóa tự nhiên** được DB cưỡng chế bằng UNIQUE, và mã dùng nó để làm cho thao tác **idempotent**: `publications.eid`, `scopus_authors.scopus_id`, (công bố, tác giả), (công bố, thứ tự), (giảng viên, tác giả), (vị trí tác giả, nguồn, SHA-256 payload)… Tệp được nhận diện bằng `scopus_imports.file_sha256`.
- **Ví dụ:** hai phiên cùng chuẩn hóa một EID mới → một phiên thắng, phiên kia gặp vi phạm UNIQUE và dùng lại bản đã có (`test_concurrent_same_new_eid_two_sessions`).
- **Giới hạn:** DOI không unique; chống trùng công bố dựa vào EID. Danh sách đầy đủ: `CONSTRAINTS_BUSINESS_RULES.md` §1.

## 3. Tách dữ liệu thô và dữ liệu chuẩn hóa

- **Vấn đề:** đề cương yêu cầu giữ nguyên đầu vào, lưu nguồn và cho xem lại; chuẩn hóa có thể sai hoặc đổi luật.
- **Thiết kế:** `raw_scopus_records.raw_payload` (JSONB) giữ **toàn bộ 22 cột CSV** nguyên văn + `row_hash`; `publications` là kết quả chuẩn hóa; `publication_raw_sources` nối hai bên. Chuẩn hóa chạy lại **không ghi đè** metadata đã có (kết quả `EXISTING_METADATA_CHANGED` chỉ ghi nhận).
- **Lợi ích:** có thể chuẩn hóa lại, so sánh trước/sau (GAP-05: dữ liệu có sẵn nhưng chưa có màn), truy xuất "bài này đến từ dòng nào của tệp nào".
- **Giới hạn (nói thật):** chuẩn hóa hiện chỉ gồm EID chuẩn tắc, tiêu đề (`title_normalized`) và năm; **DOI giữ nguyên văn** (GAP-01); **`publications.source_title` hiện = `Scopus` ở mọi dòng do đọc nhầm cột `Source`** thay vì `Source title` (GAP-02) — dữ liệu đúng vẫn còn nguyên trong `raw_payload`, chính là lợi ích của việc giữ thô.

## 4. Tách `scopus_authors` và `publication_authors` (vị trí tác giả)

- **Vấn đề:** một tác giả có nhiều công bố; một công bố có nhiều tác giả theo thứ tự; cùng tác giả có nhiều dạng tên.
- **Thiết kế:** quan hệ N–N có thuộc tính thứ tự: `publication_authors(publication_id, scopus_author_id, author_order)` với UNIQUE (công bố, tác giả) và (công bố, thứ tự). Thực thể người là `scopus_authors` (khóa tự nhiên Scopus ID); các dạng tên ở `scopus_author_name_variants` (vừa là dữ liệu hiển thị, vừa là "bề mặt" để so khớp tên).
- **Vì sao không gộp vào một bảng:** thông tin tác giả (tên) lặp theo từng công bố nếu gộp; và đơn vị công tác phải gắn với **vị trí** (xem §5), nên cần một dòng riêng cho mỗi (bài, tác giả).
- **Giới hạn:** hệ thống tin vào Scopus Author ID; không tách/gộp hai ID của cùng một người.

## 5. Đơn vị công tác theo từng tác giả trên từng bài; mỗi nguồn một kết quả riêng

- **Vấn đề:** Scopus CSV trong hệ thống không cung cấp đơn vị theo từng tác giả; đơn vị là thuộc tính **của tác giả trên một bài** và có thể khác giữa các bài; mỗi nguồn ngoài có độ tin cậy riêng.
- **Thiết kế:** `publication_author_affiliation_resolutions` — một dòng cho mỗi (vị trí tác giả × nguồn × payload) ghi **độ tin cậy** của việc gán tác giả nguồn ngoài cho vị trí Scopus: **VERIFIED** (qua chuỗi ORCID → Scopus ID), **CORROBORATED** (cùng số tác giả, vị trí, token tên, không mâu thuẫn), **UNRESOLVED** (có lý do). Chỉ resolution đáng tin mới có `publication_author_affiliations` (chuỗi gốc + tổ chức chuẩn hóa). FK ghép bảo đảm trạng thái con = trạng thái cha.
- **Số liệu demo:** 5.502 resolution = OpenAlex (VERIFIED 526 · CORROBORATED 1.830 · UNRESOLVED 395) + Crossref (VERIFIED 255 · CORROBORATED 2.300 · UNRESOLVED 196).
- **Giới hạn:** đây **không** phải đơn vị hiện tại của giảng viên (đơn vị trên bài ≠ đơn vị hiện nay); không có Khoa/Bộ môn của giảng viên để so (department/faculty chỉ có ở 1/411 hồ sơ).

## 6. Vì sao có candidate → observation → evidence → review → identity

- **Vấn đề:** liên kết giảng viên ↔ tác giả Scopus là **tri thức có hệ quả** (sai là gán nhầm công bố cho người khác), nhưng bằng chứng chỉ là tên giống + công bố trùng.
- **Thiết kế (ADR-004: tách danh tính khỏi bằng chứng):**
  - `lecturer_scopus_candidates` — **đề xuất** (chưa là sự thật), một dòng cho mỗi cặp.
  - `…_observations` + `…_evidence` — mỗi lần chạy bộ sinh, chụp lại trạng thái và các bằng chứng (NAME/PUBLICATION, luật + phiên bản + dấu vân tay) → giải thích được vì sao.
  - `…_candidate_reviews` — **quyết định của người** (ACCEPT/REJECT, lý do, ảnh chụp bằng chứng đã xem, phiên bản ứng viên để phát hiện duyệt trên dữ liệu cũ).
  - `lecturer_scopus_identities` — **danh tính đã chốt**; chỉ tạo khi ACCEPT; một Scopus ID chỉ APPROVED cho một giảng viên (chỉ mục unique một phần).
  - `identity_evidence` — bằng chứng được sao từ ứng viên sang danh tính khi ACCEPT.
- **Vì sao không lưu "danh tính đoán" là APPROVED:** tên giống ≠ cùng người (ví dụ demo: một Scopus ID được 5 hồ sơ giảng viên cùng đề xuất). APPROVED chỉ tồn tại sau quyết định của người.
- **Giới hạn:** `mapping_reviews` (REVOKE/REOPEN có bù trừ) và `identity_evidence.confidence_score` **chưa có mã sử dụng**; không hoàn tác quyết định (GAP-07); không có điểm phù hợp (GAP-04).

## 7. Kiểm toán và truy xuất nguồn

- `audit_events`: chỉ INSERT (ADR-003), có `actor_type` USER/SYSTEM, `before_state`/`after_state` JSONB, `request_id`, `correlation_id`. `entity_id` là tham chiếu đa hình nên không có FK. **Chỉ-thêm là quy ước tầng ứng dụng**, DB không cưỡng chế.
- Provenance: SHA-256 tệp, SHA-256 từng dòng, `publication_raw_sources`, `snapshot_hash`, `evidence_fingerprint`, `observation_hash`.

## 8. Lựa chọn kiểu dữ liệu và chỉ mục

| Lựa chọn | Lý do (từ mã/freeze) | Giới hạn |
|---|---|---|
| Khóa chính `uuid` mặc định `gen_random_uuid()` | Sinh ở DB, không đoán được tuần tự, an toàn khi nhập/gộp nhiều nguồn | Cần giải thích khi sơ đồ cũ dùng `bigserial` |
| `timestamptz` | Mốc thời gian có múi giờ | — |
| `jsonb` cho payload thô/bằng chứng/ảnh chụp | Giữ nguyên cấu trúc nguồn mà không phải thiết kế cột cho từng trường; có CHECK `jsonb_typeof` | Truy vấn trong JSON không có chỉ mục (chưa cần) |
| Chỉ mục unique một phần (partial) | Ràng buộc có điều kiện (APPROVED, giá trị không NULL) mà UNIQUE thường không biểu diễn được | PostgreSQL-specific |
| Chỉ mục `lower(email)` | So email không phân biệt hoa/thường | — |
| Chuỗi `text`/`varchar(n)` | `varchar(n)` cho mã ngắn (ORCID 19, SHA 64); `text` cho tiêu đề/đơn vị | — |
| Chỉ mục thường trên cột FK/lọc | Hỗ trợ truy vấn danh sách/duyệt | **Chưa đo hiệu năng** nên không khẳng định tối ưu |

## 9. Bảng nào được dùng trong từng use case

Xem `DATA_DICTIONARY.md` (cột "UC liên quan" của từng bảng) và `usecase/UC_INVENTORY.md` (cột "Bảng chính bị ghi" nằm trong các đặc tả `usecase/specs/`). Bảng `mapping_reviews` không thuộc UC nào (chưa dùng).
