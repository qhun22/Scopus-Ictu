# Giải thích các ràng buộc nghiệp vụ quan trọng của CSDL

> **Nguồn sự thật:** lược đồ PostgreSQL thật (`source/schema_snapshot.json`, alembic `a9c2e4f71b30`); biểu thức CHECK đầy đủ xem `CONSTRAINTS_CATALOG.md` (99 CHECK), khóa/FK/UNIQUE xem `KEYS_RELATIONS.md`. Tài liệu này giải thích **vì sao** các ràng buộc quan trọng tồn tại và **chúng chặn được điều gì** — không liệt kê lại mọi ràng buộc.
> **Đọc kèm:** `docs/adr/ADR-001…004`, `docs/freeze/M1.0-AUTHORITATIVE-FREEZE-PACK-RESOLVED.md` (hợp đồng schema ban đầu 15 bảng).
> **Phân biệt:** "DB cưỡng chế" = PostgreSQL từ chối ghi vi phạm; "tầng ứng dụng" = chỉ mã Python bảo đảm (DB không chặn nếu ghi trực tiếp). Mục cuối liệt kê những gì **không** do DB cưỡng chế.

## 1. Chống trùng dữ liệu (nhập lại không sinh bản ghi trùng)

| Quy tắc | Ràng buộc (DB cưỡng chế) | Chặn điều gì | Dùng ở UC |
|---|---|---|---|
| Một công bố — một EID | `uq_publications_eid` UNIQUE(`eid`); `ck_publications_eid_not_empty` | Hai công bố cùng EID; EID rỗng. Là **chốt chặn cuối** cho chuẩn hóa (kể cả khi hai phiên chạy song song) | UC-11 |
| Một tác giả — một Scopus ID | `uq_scopus_authors_scopus_id` | Hai hồ sơ tác giả cùng Scopus Author ID | UC-12 |
| Một tác giả chỉ một lần trong một công bố; mỗi thứ tự tác giả một người | `uq_publication_authors_author` (công bố, tác giả); `uq_publication_authors_order` (công bố, thứ tự); `ck_publication_authors_author_order` (≥ 1) | Lặp tác giả, hai người cùng thứ tự | UC-12 |
| Một dòng thô chỉ dẫn tới tối đa một công bố | `uq_publication_raw_sources_raw_record_id` | Gắn một dòng thô vào nhiều công bố; liên kết nguồn gốc lặp | UC-11 |
| Mỗi số dòng một lần trong một đợt nhập | `uq_raw_scopus_records_import_row` (`import_id`, `row_number`) | Dòng thô trùng số thứ tự | UC-10 |
| Dạng tên không lưu hai lần | `uq_author_name_variants` (tác giả, loại, tên) | Biến thể tên trùng | UC-12 |
| Cặp (giảng viên, tác giả) chỉ một ứng viên/một danh tính | `uq_lecturer_scopus_candidates_pair`; `uq_lecturer_scopus_identities_pair` | Sinh lại ứng viên tạo bản ghi trùng | UC-24, UC-18 |
| Mỗi ứng viên một quan sát trong một lần chạy; bằng chứng không lặp | `uq_candidate_observations_candidate_run`; `uq_candidate_evidence_descriptor` (quan sát, luật, phiên bản, dấu vân tay); `uq_identity_evidence_dedup` | Lặp quan sát/bằng chứng khi chạy lại | UC-24, UC-18 |
| Nạp bằng chứng đơn vị không lặp | `uq_paar_author_source_payload` (vị trí tác giả, nguồn, SHA-256 payload); `uq_paa_resolution_ord` | Nạp lại cùng payload tạo thêm resolution/dòng đơn vị | UC-25 |
| Tổ chức không lặp | `uq_organizations_source_org` (nguồn, mã) khi có mã; `uq_organizations_source_name` (nguồn, tên) khi không có mã | Hai tổ chức cùng mã nguồn | UC-25 |
| Mã cán bộ, ORCID, email tài khoản duy nhất | `uq_lecturers_staff_code`, `uq_lecturers_orcid` (partial, khi có giá trị); `uq_users_email_ci` (`lower(email)`) | Hai giảng viên cùng mã/ORCID; hai tài khoản cùng email khác hoa/thường | UC-05, UC-06 |
| Mỗi hồ sơ giảng viên tối đa một tài khoản | `uq_users_lecturer` (partial, `lecturer_id` NOT NULL) | Hai tài khoản trỏ cùng một hồ sơ | UC-05, UC-06 |

**Lưu ý:** email **hồ sơ giảng viên** (`lecturers.email`) **cố ý không unique** (chỉ có chỉ mục `ix_lecturers_email_ci`; migration `c3f0b9a18d42`), phần mềm chỉ **cảnh báo** hồ sơ dùng chung email.

## 2. Giữ dữ liệu thô và truy xuất nguồn (provenance)

| Quy tắc | Ràng buộc / cơ chế | Ý nghĩa |
|---|---|---|
| Dòng thô là bất biến, lưu nguyên văn | `raw_scopus_records.raw_payload` JSONB (`ck_…_raw_payload_object`), `row_hash` SHA-256 (`ck_…_row_hash`), `validation_status` ∈ {VALID, INVALID} + `validation_errors` (JSON array) | Mọi giá trị gốc còn nguyên; lỗi theo dòng giữ lại; chuẩn hóa chạy lại không mất dữ liệu gốc. (Bất biến do **mã** bảo đảm, DB không có trigger chặn UPDATE) |
| Đợt nhập có dấu vân tay nội dung | `ck_scopus_imports_file_sha256` (64 ký tự hex), `ck_scopus_imports_record_counts` (≥ 0), `ck_scopus_imports_status` ∈ {RECEIVED, PARSING, VALIDATED, STAGED, APPLIED, FAILED, CANCELLED} | Phát hiện nhập trùng nội dung; vòng đời trạng thái hữu hạn |
| Từ công bố truy ngược về dòng nguồn | Bảng `publication_raw_sources` (FK tới `publications` và `raw_scopus_records`, đều RESTRICT) | Biết công bố đến từ tệp nào, dòng nào, SHA nào; **không xóa được** dòng thô đang được tham chiếu |
| Dạng tên truy về nơi thấy đầu tiên | `scopus_author_name_variants.first_seen_raw_record_id` (FK RESTRICT) | Giải thích vì sao một dạng tên có trong hệ thống |
| Bản chụp hồ sơ giảng viên bất biến | `lecturer_source_snapshots` (`snapshot_hash`, `raw_payload`, `parser_version`; không có `updated_at`) | Biết dữ liệu nguồn tại thời điểm nhập |
| Công bố đã biết thuộc đúng giảng viên của bản chụp | **FK ghép** `fk_lecturer_known_publications_snapshot_lecturer`: (`snapshot_id`, `lecturer_id`) → `lecturer_source_snapshots(id, lecturer_id)` nhờ `uq_lecturer_source_snapshots_id_lecturer` | Ngăn gán công bố đã biết của bản chụp A cho giảng viên B |

## 3. Vị trí tác giả và đơn vị công tác (affiliation)

| Quy tắc | Ràng buộc (DB cưỡng chế) | Ý nghĩa |
|---|---|---|
| Đơn vị gắn với **vị trí tác giả trên một bài**, không gắn với bài hay với người nói chung | `publication_author_affiliation_resolutions.publication_author_id` (FK CASCADE) | Một người có nhiều đơn vị khác nhau ở các bài khác nhau; không sao chép đơn vị cấp bài cho tác giả |
| Mỗi **nguồn** có kết quả đối chiếu riêng | `uq_paar_author_source_payload`; `ix_paar_source_status` | OpenAlex và Crossref có thể cho kết quả khác nhau, cùng lưu để đối chiếu |
| Độ tin cậy của việc gán tác giả nguồn ngoài cho vị trí Scopus | `ck_…_resolutions_link_status` ∈ {VERIFIED, CORROBORATED, UNRESOLVED}; `ck_…_link_method`: VERIFIED ⇔ `ORCID_SCOPUS_ID_BRIDGE`, CORROBORATED ⇔ `POSITION_COUNT_NAME`, UNRESOLVED ⇔ không có phương pháp | **Tên người dùng không đủ cho VERIFIED**: VERIFIED bắt buộc có ORCID ngoài (`ck_…_verified_orcid`) |
| UNRESOLVED luôn có lý do; đáng tin thì phải có vị trí và thời điểm lấy | `ck_…_reason` (UNRESOLVED ⇔ có `unresolved_reason`); `ck_…_trusted_position`; `ck_…_retrieved_at`; `ck_…_presence` | Không có kết quả "treo" không giải thích |
| Dòng đơn vị cùng trạng thái với resolution cha | **FK ghép** `fk_paa_resolution_link_status`: (`resolution_id`, `link_status`) → `…_resolutions(id, link_status)` (CASCADE); `ck_…_affiliations_link_status` ∈ {VERIFIED, CORROBORATED} | Chỉ kết quả đáng tin mới có dòng đơn vị; trạng thái không thể lệch giữa cha và con |
| Đơn vị phải có nội dung; chuỗi gốc tách khỏi tổ chức chuẩn hóa | `ck_…_affiliations_content` (có chuỗi gốc hoặc tổ chức); `ck_…_raw_text` | Thiếu dữ liệu để trống, không suy diễn |

## 4. Đối sánh, duyệt và danh tính

| Quy tắc | Ràng buộc (DB cưỡng chế) | Ý nghĩa |
|---|---|---|
| **Một Scopus Author ID chỉ được APPROVED cho đúng một giảng viên** | `uq_identities_scopus_author_approved` — UNIQUE(`scopus_author_id`) WHERE `status = 'APPROVED'` | Ngăn hai giảng viên cùng "sở hữu" một tác giả, kể cả khi hai người duyệt cùng lúc (test `test_concurrent_accept_same_author_has_one_winner`) |
| Vocabulary trạng thái ứng viên/danh tính | `ck_lecturer_scopus_candidates_status` ∈ {PENDING, ACCEPTED, REJECTED, SUPERSEDED}; `ck_lecturer_scopus_identities_status` ∈ {CANDIDATE, APPROVED, REJECTED, REVOKED} | Trạng thái hữu hạn, không giá trị lạ |
| **Bảng chuyển trạng thái của quyết định duyệt** | `ck_lecturer_scopus_candidate_reviews_transitions`: ACCEPT: PENDING→ACCEPTED; REJECT: PENDING→REJECTED; REOPEN: {ACCEPTED, REJECTED, SUPERSEDED}→PENDING | Không thể ghi một quyết định "nhảy cóc" (vd. ACCEPT từ REJECTED) |
| **Lý do bắt buộc** khi không phải ACCEPT | `ck_…_candidate_reviews_reason_required`; `ck_mapping_reviews_reason_required` | Mọi từ chối đều có lý do không rỗng |
| Quyết định lưu bằng chứng người duyệt đã xem + phiên bản ứng viên | `evidence_snapshot` (JSON object), `candidate_version` ≥ 1 | Truy vết đúng căn cứ tại thời điểm quyết định; phát hiện duyệt trên dữ liệu cũ |
| Bù trừ thay vì sửa lịch sử (thiết kế dự phòng) | `ck_mapping_reviews_compensates`: REVOKE/REOPEN **bắt buộc** `compensates_review_id`; APPROVE/REJECT **cấm**; `ck_mapping_reviews_transitions` | Hoàn tác là một bản ghi mới tham chiếu bản ghi cũ — **hiện chưa có mã sử dụng** (0 dòng) |
| Điểm tin cậy nằm trong [0, 1] khi có | `ck_identity_evidence_confidence_score`; cột NULL được (migration `d3f7a1c9e2b4`) | Hiện luôn NULL: không có điểm do máy tính |
| Khuyến nghị đi đôi với phiên bản và thời điểm | `ck_lecturer_scopus_identities_recommendation_consistency` (cả ba cột cùng NULL hoặc cùng có giá trị) | Cột `recommendation*` hiện chưa có mã ghi |
| Lần chạy sinh ứng viên: hoàn tất ⇔ có thời điểm kết thúc | `ck_candidate_generation_runs_completion_consistency`: RUNNING ⇒ `completed_at` NULL; COMPLETED/FAILED ⇒ có | Không có lần chạy "hoàn tất" thiếu mốc |
| Bằng chứng loại và dấu vân tay | `ck_…_candidate_evidence_evidence_kind` ∈ {NAME, PUBLICATION}; `ck_identity_evidence_evidence_type` (7 loại); `…_fingerprint` (SHA-256 64 hex) | Từ vựng đóng; chống trùng bằng dấu vân tay |

## 5. Tài khoản, vai trò và kiểm toán

| Quy tắc | Ràng buộc (DB cưỡng chế) | Ý nghĩa |
|---|---|---|
| Ba vai trò | `ck_users_role` ∈ {ADMIN, REVIEWER, LECTURER} | Không có vai trò thứ tư (không có "Operator") |
| Tài khoản LECTURER phải gắn hồ sơ giảng viên | `ck_users_lecturer_account_required`: role ≠ LECTURER **hoặc** `lecturer_id` NOT NULL | Một giảng viên đăng nhập luôn có hồ sơ để giới hạn dữ liệu của mình |
| Thu hồi phiên | `users.auth_version` ≥ 1 (`ck_users_auth_version`) | Tăng khi đổi mật khẩu/vai trò/khóa → token cũ vô hiệu |
| Nhật ký: người thực hiện nhất quán | `ck_audit_events_actor_invariant`: USER ⇒ có `actor_user_id`, không `actor_service`; SYSTEM ⇒ ngược lại (và tên dịch vụ không rỗng) | Mọi sự kiện đều biết ai/thành phần nào thực hiện |
| Định dạng hành động và loại thực thể | `ck_audit_events_action_format` (`^[A-Z][A-Z0-9_]*$`), `ck_audit_events_entity_type_format` (`^[a-z][a-z0-9_]*$`); trạng thái trước/sau/metadata phải là JSON object | Từ vựng sự kiện nhất quán |
| Xóa có kiểm soát | Mọi FK trừ 3 quan hệ phụ thuộc chặt dùng `ON DELETE RESTRICT` | Không xóa được bản ghi đang được tham chiếu; 3 CASCADE: công bố → vị trí tác giả → resolution → dòng đơn vị |
| Khóa lạc quan | `version` ≥ 1 (`ck_*_version`) ở các bảng có thể sửa | Hai người sửa cùng lúc: người sau nhận 409 `VERSION_CONFLICT` |

## 6. Những điều **KHÔNG** do DB cưỡng chế (nói thật khi bảo vệ)

1. **Audit chỉ-thêm** (ADR-003): không trigger/REVOKE; ai có quyền ghi DB vẫn UPDATE/DELETE được. Bảo đảm bằng mã dịch vụ + test, không phải bằng DB.
2. **Dòng thô bất biến** (`raw_scopus_records`, snapshot): cũng là quy ước tầng ứng dụng.
3. **Tính duy nhất DOI**: `publications.doi` không unique (có chỉ mục thường `ix_publications_doi`); chống trùng công bố dựa vào EID.
4. **Không có ràng buộc "một giảng viên — một danh tính"**: một giảng viên **có thể** có nhiều danh tính APPROVED (test `test_lecturer_can_have_multiple_approved_authors`); ràng buộc chỉ theo chiều ngược (một tác giả — một giảng viên).
5. **`audit_events.entity_id`** là tham chiếu đa hình không có FK: toàn vẹn tham chiếu do mã bảo đảm.
6. **Phần lớn ràng buộc nghiệp vụ "không tự động khẳng định theo tên"** nằm ở tầng dịch vụ và ADR-004 (DB chỉ bảo đảm trạng thái hợp lệ và chuyển trạng thái, không bảo đảm "người đã xem bằng chứng").
