# Đặc tả Use Case — Nhóm 4: Chuẩn hóa, đối soát và phê duyệt

> Khớp "UC chính (d) Chuẩn hóa/đối soát và phê duyệt" của đề cương. Sơ đồ: `diagrams/UCD-4_chuan_hoa_doi_soat_phe_duyet`; quy trình tổng thể: `process/BPMN-1_*`. Đối chiếu mã: `scopus_normalizer.py`, `scopus_author_normalizer.py`, `matching/*`, `candidate_review_service.py`, `reviews.py`.
> **Không có bước tự động phê duyệt.** Hệ thống chỉ đề xuất ứng viên; danh tính APPROVED chỉ được tạo khi người có quyền ACCEPT (ADR-004). **Không có "Match Score".**
> **Quan hệ giữa các UC:** UC-18 «include» UC-17 (yêu cầu duyệt bắt buộc `observation_id` và `candidate_version` lấy từ chi tiết ứng viên — `ReviewDecisionRequest`). UC-11 → UC-12 là **thứ tự tiền điều kiện** (tác giả được bóc tách qua chuỗi dòng thô → nguồn gốc → công bố), không phải include/extend. UC-24 tiền điều kiện: UC-08, UC-11, UC-12 (và tùy chọn UC-25).

---

## UC-11 — Chuẩn hóa công bố từ bản ghi thô

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-11 |
| **Mục tiêu** | Chuyển các dòng thô hợp lệ của một đợt nhập CSV thành **công bố chuẩn hóa** (mỗi EID một dòng), giữ nguồn gốc dòng, không ghi đè dữ liệu đã có |
| **Actor chính / phụ** | Chính: **ADMIN**. Phụ: Hệ thống |
| **Điều kiện trước** | Đợt nhập ở trạng thái hoàn tất tiếp nhận nguồn (`STAGED`/`APPLIED`); có dòng thô `VALID` |
| **Luồng chính** | 1. ADMIN vào **Chuẩn hóa dữ liệu** (`/normalization`, tab Công bố) và bấm chuẩn hóa một đợt.<br>2. Hệ thống (`POST /imports/{id}/normalize`) lấy dòng `VALID`, chuẩn hóa **EID chuẩn tắc**, tạo `publications` mới hoặc dùng lại bản có cùng EID; liên kết `publication_raw_sources`.<br>3. Phân loại từng dòng: `NEW`, `EXISTING_UNCHANGED`, `EXISTING_METADATA_CHANGED` (**không ghi đè**), `INVALID_EID`…; trùng EID trong cùng tệp được đếm riêng.<br>4. Ghi bộ đếm vào `scopus_imports.normalization_summary` và audit `SCOPUS_NORMALIZATION_TRIGGERED/COMPLETED` |
| **Luồng thay thế** | A1. Chạy lại: kết quả `EXISTING_UNCHANGED`, **0 bản ghi mới** (idempotent).<br>A2. Hủy giữa các lô: phần đã hoàn thành được giữ, lỗi dòng thô được bảo toàn |
| **Luồng lỗi** | E1. Đợt không đủ điều kiện (đang xử lý/thất bại/đã hủy) → 409 `IMPORT_NOT_ELIGIBLE_FOR_NORMALIZATION`.<br>E2. Không tìm thấy đợt → 404 `IMPORT_NOT_FOUND`.<br>E3. EID không hợp lệ → dòng được đếm `INVALID_EID`, không tạo công bố.<br>E4. Hai phiên tạo cùng EID mới: phiên thua phục hồi qua ràng buộc UNIQUE (không tạo trùng).<br>E5. Không phải ADMIN → 403; lỗi DB → 503 |
| **Điều kiện sau** | Công bố chuẩn hóa và nguồn gốc đã lưu; bất biến số đếm (`NEW + EXISTING + … = đã xử lý`); dòng thô không đổi |
| **Dữ liệu thay đổi** | `publications`, `publication_raw_sources`, `scopus_imports.normalization_summary`, `audit_events` |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | `POST /api/v1/imports/{import_id}/normalize`; UI `/normalization`; dịch vụ `normalization/scopus_normalizer.py` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)** ở mức: EID chuẩn tắc, tiêu đề (`title_normalized` = NFKC + chữ thường), năm (số nguyên). **DOI lưu nguyên văn** (GAP-01); **nguồn xuất bản bị lưu sai `Scopus`** (GAP-02) |
| **Test case tương ứng** | `test_scopus_normalization` (21 ca): `test_all_new_records`, `test_existing_eid_reused`, `test_metadata_changed_not_overwritten`, `test_rerun_idempotent`, `test_intra_file_duplicate_counted`, `test_provenance_links_correct`, `test_unique_raw_record_constraint`, `test_staged_eligible`, `test_failed_not_eligible`, `test_cancelled_not_eligible`, `test_normalize_existing_import_rejects_ineligible`, `test_counters_sum_to_processed`, `test_concurrent_same_new_eid_two_sessions`, `test_cancel_between_batches_preserves_completed_work_and_raw_errors`; `unit/test_scopus_normalizer`. E2E: ảnh 43 (Task 16; 660 công bố) |

---

## UC-12 — Bóc tách tác giả Scopus

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-12 |
| **Mục tiêu** | Từ các công bố đã chuẩn hóa, tạo tác giả theo Scopus Author ID, các dạng tên và vị trí tác giả trong từng công bố |
| **Actor chính / phụ** | Chính: **ADMIN**. Phụ: Hệ thống |
| **Điều kiện trước** | Đợt nhập `APPLIED`, có bản ghi; công bố đã chuẩn hóa (UC-11) để chuỗi nguồn gốc dòng thô → công bố có sẵn |
| **Luồng chính** | 1. ADMIN vào `/normalization` và chạy bóc tách tác giả cho đợt.<br>2. Hệ thống (`POST /authors/normalize-import/{id}`) phân tích từng dòng: tách tên hiển thị/tên đầy đủ/ID theo `;`, kiểm **ID nhúng trong tên đầy đủ khớp trường ID**.<br>3. Upsert `scopus_authors` theo `scopus_id`; thêm `scopus_author_name_variants` (AUTHOR_DISPLAY/AUTHOR_FULL_NAME, tên ưu tiên chọn dạng đầy đủ); thêm `publication_authors` theo thứ tự (first-wins) |
| **Luồng thay thế** | A1. Chạy lại: không tác giả/biến thể/liên kết mới (idempotent); tóm tắt chuẩn hóa công bố giữ nguyên |
| **Luồng lỗi** | E1. Đợt không `APPLIED` → từ chối (`test_staged_import_rejected_for_author_normalization`).<br>E2. ID nhúng không khớp trường ID hoặc độ dài danh sách không khớp → lỗi có cấu trúc, **không tạo tác giả** cho dòng đó.<br>E3. Thiếu dòng nguồn gốc → ghi lỗi, không sập.<br>E4. Xung đột thứ tự/liên kết → ghi nhận, **không ghi đè**.<br>E5. Lỗi nghiêm trọng → đợt giữ trạng thái APPLIED, ghi lỗi; thử lại an toàn.<br>E6. Không phải ADMIN → 403 |
| **Điều kiện sau** | Mỗi Scopus ID một tác giả; mỗi (công bố, tác giả) và (công bố, thứ tự) một dòng |
| **Dữ liệu thay đổi** | `scopus_authors`, `scopus_author_name_variants`, `publication_authors`, `scopus_imports.normalization_summary` (khóa `authors`) |
| **Quyền truy cập** | ADMIN |
| **API / UI thực tế** | `POST /api/v1/authors/normalize-import/{import_id}`; UI `/normalization`; dịch vụ `normalization/scopus_author_normalizer.py` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)** |
| **Test case tương ứng** | `test_scopus_author_normalization` (26 ca): `test_applied_import_author_normalization_succeeds`, `test_unique_scopus_author_by_scopus_id`, `test_both_display_and_full_name_variants_created`, `test_correct_author_order`, `test_rerun_no_duplicate_authors`, `test_rerun_no_duplicate_variants`, `test_rerun_no_duplicate_publication_author_links`, `test_author_id_mismatch_no_author_created`, `test_author_list_length_mismatch_no_author_created`, `test_author_order_conflict_no_overwrite`, `test_preferred_name_stability_not_overwritten_on_rerun`; `unit/test_scopus_author_parser`. E2E: ảnh 42 (1.207 tác giả/2.751 vị trí) |

---

## UC-24 — Sinh ứng viên đối sánh giảng viên ↔ tác giả Scopus

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-24 — **chỉ chạy bằng script CLI** |
| **Mục tiêu** | Đề xuất các cặp (giảng viên, tác giả Scopus) có thể là cùng một người, kèm bằng chứng, ở trạng thái **PENDING**; không quyết định danh tính |
| **Actor chính / phụ** | Chính: **Kỹ thuật viên** (chạy script). Phụ: Hệ thống |
| **Điều kiện trước** | Có hồ sơ giảng viên (UC-08), tác giả + biến thể tên (UC-12); tùy chọn công bố đã biết (UC-25); chạy đúng DB (`--expected-database`, cổng 5432 bị từ chối) |
| **Luồng chính** | 1. Chạy `generate_matching_candidates.py --dry-run` (chỉ đọc) để xem số ứng viên sẽ sinh; có thể ràng buộc `--expected-candidates N`.<br>2. Chạy `--apply` với `--manifest` ngoài repo: ghi `candidate_generation_runs` (RUNNING→COMPLETED), `lecturer_scopus_candidates` (PENDING), `…_observations`, `…_evidence`.<br>3. Bộ sinh so khớp **tên bằng nhau tuyệt đối** theo 4 luật có thứ tự (`RULE_EXACT_N0`, `RULE_TITLE_STRIPPED_N0`, `RULE_TITLE_STRIPPED_N2`, `RULE_TITLE_STRIPPED_N2_FORMAT`; bỏ tiền tố `DH.`, `GS.TS.`, `PGS.TS.`, `ThS.`, `TS.` theo danh sách trắng) với ba bề mặt tên Scopus (tên ưu tiên, tên đầy đủ, tên hiển thị); sau đó **làm giàu** bằng công bố đã biết trùng DOI (chuẩn hóa) hoặc tiêu đề |
| **Luồng thay thế** | A1. Chạy lại: idempotent, không tạo ứng viên trùng; cần `--allow-new-run` nếu muốn một lần chạy mới khi đã có lần COMPLETED.<br>A2. `--resume-running` để tiếp tục một lần chạy bị kẹt RUNNING |
| **Luồng lỗi** | E1. Sai DB/cổng → từ chối.<br>E2. Số ứng viên ≠ `--expected-candidates` → từ chối.<br>E3. Xung đột đối chiếu công bố (`DOI_AMBIGUOUS`, `DOI_TITLE_CONFLICT`, `TITLE_AMBIGUOUS`, `SNAPSHOT_LECTURER_MISMATCH`) → **không tạo bằng chứng hỗ trợ** (fail-closed).<br>E4. Lỗi giữa chừng → lần chạy `FAILED`, không ghi dở |
| **Điều kiện sau** | Ứng viên PENDING kèm bằng chứng NAME/PUBLICATION; **không có danh tính nào được tạo**; kết quả xác định |
| **Dữ liệu thay đổi** | `candidate_generation_runs`, `lecturer_scopus_candidates`, `lecturer_scopus_candidate_observations`, `lecturer_scopus_candidate_evidence` |
| **Quyền truy cập** | Không qua API/RBAC; người chạy script có quyền DB |
| **API / UI thực tế** | Script `backend/scripts/generate_matching_candidates.py`; dịch vụ `matching/candidate_generator.py`, `publication_evidence_enricher.py`, `candidate_persistence.py`. **Không có UI** |
| **Trạng thái triển khai** | **CHỈ CLI**; **MỘT PHẦN so với đề cương**: chỉ tên + công bố đã biết, **không dùng ORCID/đơn vị**, **không có điểm/mức độ phù hợp** (GAP-03, GAP-04). Teacher DB (09/10/2026, chỉ đọc): 40 ứng viên PENDING/38 giảng viên/36 Scopus ID; 134 bằng chứng tên (đều từ luật `RULE_TITLE_STRIPPED_N2_FORMAT`); 69 bằng chứng công bố (6 ứng viên) |
| **Test case tương ứng** | `unit/test_candidate_generator` (13), `test_generate_matching_candidates_cli` (11), `unit/test_publication_evidence_enricher`, `unit/test_candidate_persistence`, `test_candidate_review_service::test_current_observation_is_deterministic_for_tied_completed_runs` |

---

## UC-17 — Xem hàng đợi ứng viên và bằng chứng

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-17 (được «include» bởi UC-18) |
| **Mục tiêu** | Cho người duyệt thấy ứng viên và **căn cứ** để quyết định: luật so khớp, tên hai phía, công bố hỗ trợ, ngữ cảnh mơ hồ, cảnh báo Scopus ID dùng chung |
| **Actor chính / phụ** | Chính: **REVIEWER, ADMIN**. Không dành cho LECTURER |
| **Điều kiện trước** | Đăng nhập REVIEWER hoặc ADMIN; đã có ứng viên (UC-24) |
| **Luồng chính** | 1. Vào **Duyệt đối sánh** (`/reviews`): bảng ứng viên (mặc định lọc `PENDING`, 20/trang).<br>2. Lọc theo **trạng thái** (PENDING/ACCEPTED/REJECTED/SUPERSEDED), **loại bằng chứng** (có công bố hỗ trợ / chỉ tên), **mức mơ hồ** (có nhiều ứng viên / không có ứng viên khác).<br>3. Mở **Xem chi tiết** (`GET /reviews/candidates/{id}`): A. giảng viên · B. tác giả Scopus · C. bằng chứng tên · D. bằng chứng công bố · E. ngữ cảnh mơ hồ, kèm cảnh báo đỏ "Tác giả Scopus dùng chung (N giảng viên)" |
| **Luồng thay thế** | A1. Danh sách rỗng khi bộ lọc không khớp |
| **Luồng lỗi** | E1. Không tìm thấy ứng viên → 404 `CANDIDATE_NOT_FOUND`.<br>E2. Tham số lọc sai (`status`, `ambiguity`) → 422.<br>E3. LECTURER → 403; chưa đăng nhập → 401 |
| **Điều kiện sau** | Chỉ đọc |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | ADMIN, REVIEWER |
| **API / UI thực tế** | `GET /api/v1/reviews/candidates`, `GET /api/v1/reviews/candidates/{candidate_id}`; UI `/reviews` (cũng `/approval-queue`) |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**; chỉ hiển thị căn cứ **định tính** (chưa có "mức độ phù hợp" dạng điểm/nhãn — GAP-04). Dùng AntD nên khác phong cách các trang còn lại |
| **Test case tương ứng** | `test_review_shared_author_warning::test_queue_flags_shared_scopus_author_without_changing_is_ambiguous`, `test_detail_exposes_shared_scopus_author_warning`; `test_review_api::test_openapi_contains_all_review_operations`, `test_lecturer_cannot_access_review_api`. E2E: ảnh 19–20 (Task 16), ảnh `t17/01` (REVIEWER) |

---

## UC-18 — Duyệt ứng viên (ACCEPT / REJECT)

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-18 — **«include» UC-17** |
| **Mục tiêu** | Người có quyền quyết định chấp nhận hoặc từ chối một ứng viên; ACCEPT tạo danh tính APPROVED; mọi quyết định có lý do, bằng chứng đã xem và dấu vết |
| **Actor chính / phụ** | Chính: **REVIEWER, ADMIN** (cùng quyền duyệt). Phụ: Hệ thống (`CandidateReviewService`); LECTURER là bên hưởng kết quả (UC-21, UC-22) |
| **Điều kiện trước** | Đăng nhập REVIEWER/ADMIN còn hoạt động; ứng viên ở trạng thái `PENDING`; có `observation_id` hiện hành và `candidate_version` từ chi tiết ứng viên (UC-17) |
| **Luồng chính** | 1. Người duyệt mở chi tiết ứng viên (UC-17) và chọn **Xác nhận đối sánh (ACCEPT)** hoặc **Từ chối (REJECT)**; REJECT bắt buộc nhập lý do.<br>2. Hệ thống (`POST /reviews/candidates/{id}/reviews`) lấy người duyệt **từ phiên đã xác thực** (request không được kèm danh tính/bằng chứng — `extra="forbid"`), khóa dòng ứng viên và kiểm: ứng viên PENDING, quan sát hiện hành, phiên bản khớp, không xung đột danh tính.<br>3. **ACCEPT:** ghi `lecturer_scopus_candidate_reviews` (ACCEPT, PENDING→ACCEPTED, ảnh chụp bằng chứng), đổi trạng thái ứng viên, tạo `lecturer_scopus_identities` (**APPROVED**) và sao bằng chứng sang `identity_evidence` (NAME → NAME_SIMILARITY; PUBLICATION → DOI_EXACT/PUBLICATION_OVERLAP; `confidence_score` NULL), ghi audit.<br>4. **REJECT:** ghi review (REJECT, PENDING→REJECTED, lý do), đổi trạng thái ứng viên, ghi audit; không tạo danh tính.<br>5. Giao diện hiển thị kết quả; ứng viên rời hàng đợi PENDING |
| **Luồng thay thế** | A1. Người duyệt **không quyết định** (đóng cửa sổ): ứng viên giữ PENDING, không ghi gì.<br>A2. Gửi lại đúng yêu cầu đã thành công: idempotent (cùng kết quả, không ghi trùng) |
| **Luồng lỗi** | E1. Không tìm thấy ứng viên/quan sát → 404 (`CANDIDATE_NOT_FOUND`, `OBSERVATION_NOT_FOUND`).<br>E2. Quan sát không thuộc ứng viên / quan sát cũ / phiên bản cũ / đã quyết định → 409 (`OBSERVATION_CANDIDATE_MISMATCH`, `STALE_CANDIDATE_OBSERVATION`, `STALE_CANDIDATE_VERSION`, `CANDIDATE_ALREADY_DECIDED_CONFLICT`).<br>E3. Scopus ID đã APPROVED cho giảng viên khác → 409 `SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER`; danh tính có sẵn mâu thuẫn nguồn gốc → 409 `PREEXISTING_IDENTITY_PROVENANCE_CONFLICT`; loại bằng chứng không thể sao → 409 `EVIDENCE_PROMOTION_UNSUPPORTED`.<br>E4. Lý do trống khi REJECT → 422 `INVALID_REVIEW_REASON` (và CHECK DB).<br>E5. Người duyệt không tồn tại/không hoạt động/vai trò LECTURER → 403 (`REVIEWER_NOT_FOUND`, `REVIEWER_NOT_AUTHORIZED`).<br>E6. Lỗi giữa chừng → rollback toàn bộ, **không ghi dở** |
| **Điều kiện sau** | Thành công: review ghi bất biến (chỉ thêm), ứng viên ở trạng thái cuối, (ACCEPT) danh tính APPROVED + bằng chứng, audit. Một Scopus ID chỉ APPROVED cho đúng một giảng viên (DB: chỉ mục unique một phần). Lỗi: DB không đổi |
| **Dữ liệu thay đổi** | `lecturer_scopus_candidate_reviews`, `lecturer_scopus_candidates` (status, version), `lecturer_scopus_identities` (ACCEPT), `identity_evidence` (ACCEPT), `audit_events`. **Không** ghi `mapping_reviews` |
| **Quyền truy cập** | ADMIN, REVIEWER (`require_role`); LECTURER bị 403 |
| **API / UI thực tế** | `POST /api/v1/reviews/candidates/{candidate_id}/reviews` (body: `observation_id`, `candidate_version`, `action`, `reason`); UI `/reviews` (cửa sổ xác nhận ACCEPT/REJECT); dịch vụ `candidate_review_service.py` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)**. Giới hạn: **không hoàn tác** được quyết định (REOPEN/REVOKE chỉ trong schema — GAP-07); teacher DB: 0 review (chưa ai duyệt) — minh chứng ACCEPT/REJECT chỉ từ DB kiểm thử |
| **Test case tương ứng** | `test_candidate_review_service` (29 ca): `test_accept_happy_path`, `test_reject_happy_path`, `test_accept_retry_is_idempotent`, `test_accept_then_reject_conflicts`, `test_stale_version_fails_closed`, `test_stale_observation_fails_closed`, `test_observation_candidate_mismatch`, `test_lecturer_role_rejected`, `test_inactive_user_rejected`, `test_admin_role_accepted`, `test_same_author_different_lecturer_rejected`, `test_preexisting_identity_provenance_conflict`, `test_evidence_promotion_count_and_confidence`, `test_no_scoring_artifact_in_evidence_promotion`, `test_no_mapping_review_written`, `test_reject_blank_reason_rejected`, `test_failure_rollback_no_partial_writes`, `test_concurrent_accept_same_author_has_one_winner`; `test_review_api::test_decision_rejects_identity_and_evidence_injection`, `test_decision_uses_authenticated_reviewer_and_domain_service`. E2E: ảnh 20b–22 (Task 16), `t17/04` (409) |

---

## UC-19 — Xem lịch sử review

| Trường | Nội dung |
|---|---|
| **Mã UC** | UC-19 |
| **Mục tiêu** | Truy vết các quyết định duyệt đã thực hiện (ai, khi nào, quyết định gì, lý do) |
| **Actor chính / phụ** | Chính: **REVIEWER, ADMIN** |
| **Điều kiện trước** | Đăng nhập REVIEWER/ADMIN |
| **Luồng chính** | 1. Vào **Lịch sử review** (`/review-history`).<br>2. Hệ thống (`GET /reviews/history`) trả danh sách review (chỉ đọc), lọc theo hành động (ACCEPT/REJECT/REOPEN) và khoảng ngày, phân trang |
| **Luồng thay thế** | A1. Chưa có review → trạng thái rỗng (teacher DB hiện 0) |
| **Luồng lỗi** | E1. Tham số lọc/ngày sai → 422.<br>E2. LECTURER → 403 |
| **Điều kiện sau** | Chỉ đọc; nguồn là bảng review chỉ-thêm |
| **Dữ liệu thay đổi** | Không |
| **Quyền truy cập** | ADMIN, REVIEWER |
| **API / UI thực tế** | `GET /api/v1/reviews/history`; UI `/review-history` |
| **Trạng thái triển khai** | **ĐÃ TRIỂN KHAI (UI + API)** |
| **Test case tương ứng** | `test_review_history_api` (32 ca) |
