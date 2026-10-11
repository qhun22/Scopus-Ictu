# BPMN-1 — Mô tả từng bước của quy trình nghiệp vụ thực tế (PI 1.1)

> **Hình:** `process/BPMN-1_quy_trinh_thuc_te.bpmn` (nguồn chỉnh sửa — mở bằng <https://demo.bpmn.io> hoặc Camunda Modeler) · `process/render/BPMN-1_quy_trinh_thuc_te.svg` / `.png` (6660×1960 px).
> **Cách tạo:** sinh từ mô hình khai báo trong `tools/gen_bpmn.py`; **đã kiểm** bằng thư viện bpmn-js 17.11.1 (nhập 0 cảnh báo, 82 phần tử) — xem `README.md` mục "Kiểm tra".
> **Phạm vi:** chỉ quy trình **đang chạy được** trong phần mềm (UI + API + script CLI). Không có bước tự động phê duyệt danh tính (ADR-004; test `test_no_mapping_review_written`, `test_no_scoring_artifact_in_evidence_promotion`).
> **Khác với sơ đồ quy trình trong `DoAn.docx` (tuần 1):** không có "Match Score", "gán tay", "rollback quyết định duyệt", vai trò "Operator"; chuẩn hóa là bước riêng do ADMIN kích hoạt; sinh ứng viên là script CLI. Xem `gap/GAP_DE_CUONG_VS_CODE.md` §3 và `database/DOI_CHIEU_SO_DO_CU.md`.

## 1. Làn (swimlane) và tác nhân

| Làn | Ai/cái gì | Căn cứ |
|---|---|---|
| ADMIN | Quản trị viên, thao tác trên giao diện | `require_role("ADMIN")` ở `imports`, `lecturers`, `authors` |
| Hệ thống (API/dịch vụ — tự động) | FastAPI + dịch vụ nghiệp vụ, không cần người trực tiếp | `backend/app/services/*` |
| Kỹ thuật viên (script CLI) | Người chạy script dòng lệnh — **không phải vai trò trong ứng dụng** | `backend/scripts/*.py` |
| REVIEWER / ADMIN (người duyệt) | Hai vai trò đều được xem hàng đợi và ACCEPT/REJECT | `require_role("ADMIN","REVIEWER")` ở `reviews` |
| LECTURER | Giảng viên xem dữ liệu của chính mình | `require_role("LECTURER")` ở `lecturers/me/*` |

## 2. Bảng bước

Cột **Dữ liệu ghi** dùng tên bảng thật (xem `database/DATA_DICTIONARY.md`). "—" = không ghi.

| Mã | Bước | Người/thành phần thực hiện | Đầu vào | Đầu ra | UC / API / script | Dữ liệu ghi | Bằng chứng kiểm thử (ví dụ) |
|---|---|---|---|---|---|---|---|
| S0 | Có dữ liệu nguồn | ADMIN | Tệp CSV xuất từ Scopus **hoặc** JSON hồ sơ giảng viên (ICTU Repository) | Tệp sẵn sàng tải | — | — | — |
| A1 | Tải tệp lên | ADMIN | Tệp CSV/JSON | Yêu cầu tải lên | UC-08 `POST /lecturers/import/preview`; UC-10 `POST /imports/scopus` | — (JSON: xem trước không ghi) | `test_preview_does_not_mutate_db`; `test_admin_upload_valid_csv` |
| S1 | Kiểm tra tệp | Hệ thống | Tệp tải lên | Kết quả hợp lệ/không; lỗi từng dòng; cảnh báo trùng | `ScopusCsvParser`; `lecturer_dataset/parser.py`; SHA-256 tệp | — (CSV: ghi phiên nhập ở S2) | `test_invalid_uploads_return_stable_codes`; `test_active_duplicate_returns_existing_job_id`; `test_completed_duplicate_requires_explicit_confirmation`; `test_preview_rejects_invalid_schema` |
| G1 | Cổng: hợp lệ và không trùng? | Hệ thống | Kết quả S1 | Có → S2; Không → AE | Mã lỗi ổn định: `INVALID_IMPORT_FILE`, `EMPTY_IMPORT_FILE`, `UNSUPPORTED_IMPORT_FORMAT`, `IMPORT_FILE_TOO_LARGE`, `IMPORT_ALREADY_PROCESSING`, `DUPLICATE_IMPORT_CONFIRMATION_REQUIRED` | — | `test_oversized_upload_is_rejected` |
| AE | Đọc lỗi theo dòng, sửa tệp hoặc xác nhận nhập trùng | ADMIN | Lỗi/cảnh báo | Tệp đã sửa (quay lại A1) hoặc xác nhận trùng | UI `/imports` (chi tiết đợt nhập hiển thị `row_errors`) | — | Task 16 §6.4–6.5 (`BAO_CAO_KIEM_THU_CHUC_NANG.md`) |
| S2 | Lưu dữ liệu **thô** + audit | Hệ thống | Tệp hợp lệ (JSON đã xác nhận / CSV) | JSON: hồ sơ giảng viên + snapshot; CSV: đợt nhập + dòng thô bất biến | UC-08 `POST /lecturers/import`; UC-10 (tiến trình nền theo dõi/hủy được) | JSON: `lecturers`, `lecturer_source_snapshots`, `lecturer_known_publications`, `audit_events`; CSV: `scopus_imports`, `raw_scopus_records`, `audit_events` | `test_import_creates_records_then_idempotent`; `test_import_rejects_duplicate_emails`; `test_scopus_decoupled_lifecycle` |
| G2 | Cổng: là CSV Scopus? | Hệ thống | Loại dữ liệu | CSV → A3; JSON → E1 | — | — | — |
| E1 | Kết thúc: hồ sơ giảng viên đã lưu | — | — | Hồ sơ giảng viên sẵn sàng cho đối sánh | — | — | — |
| A3 | Chạy chuẩn hóa công bố và bóc tách tác giả | ADMIN | Đợt nhập CSV đã hoàn tất (APPLIED/STAGED hợp lệ) | Yêu cầu chuẩn hóa | UC-11 `POST /imports/{id}/normalize`; UC-12 `POST /authors/normalize-import/{id}` | — | `test_staged_eligible`; `test_failed_not_eligible`; `test_staged_import_rejected_for_author_normalization` |
| S3 | Chuẩn hóa | Hệ thống | Dòng thô VALID | Công bố chuẩn (mỗi EID một dòng), nguồn gốc, tác giả, tên biến thể, vị trí tác giả | `scopus_normalizer.py`; `scopus_author_normalizer.py` | `publications`, `publication_raw_sources`, `scopus_authors`, `scopus_author_name_variants`, `publication_authors`, `scopus_imports.normalization_summary` | `test_rerun_idempotent`; `test_metadata_changed_not_overwritten`; `test_rerun_no_duplicate_authors`; `test_author_id_mismatch_no_author_created` |
| C1 | Nạp bằng chứng ngoài | Kỹ thuật viên (script) | Craw snapshot (công bố đã biết); JSONL OpenAlex/Crossref | Công bố đã biết; đơn vị công tác theo từng tác giả/từng nguồn | UC-25 `ingest_craw_known_publications.py`, `import_author_affiliations.py` | `lecturer_known_publications`, `organizations`, `publication_author_affiliation_resolutions`, `publication_author_affiliations` | `test_ingest_craw_known_publications_cli`; `test_import_author_affiliations_cli`; `test_author_affiliation` |
| C2 | Sinh ứng viên đối sánh | Kỹ thuật viên (script) | Giảng viên + tác giả Scopus + tên biến thể + công bố đã biết | Ứng viên **PENDING** kèm bằng chứng NAME/PUBLICATION (idempotent) | UC-24 `generate_matching_candidates.py` — 4 luật so khớp tên + làm giàu bằng công bố | `candidate_generation_runs`, `lecturer_scopus_candidates`, `…_observations`, `…_evidence` | `test_candidate_generator`; `test_generate_matching_candidates_cli`; `test_publication_evidence_enricher` |
| R1 | Xem hàng đợi và bằng chứng ứng viên | REVIEWER hoặc ADMIN | Ứng viên PENDING | Hiểu căn cứ: luật, tên hai phía, công bố hỗ trợ, ngữ cảnh mơ hồ, cảnh báo Scopus ID dùng chung | UC-17 `GET /reviews/candidates`, `…/{id}` | — | `test_queue_flags_shared_scopus_author_without_changing_is_ambiguous`; `test_detail_exposes_shared_scopus_author_warning` |
| G3 | Cổng: quyết định của người duyệt | REVIEWER hoặc ADMIN | Bằng chứng | **ACCEPT** → S4; **REJECT** (lý do bắt buộc) → S6; **giữ PENDING** → EP | UC-18 `POST /reviews/candidates/{id}/reviews` | — | `test_candidate_review_service` (29 ca) |
| EP | Kết thúc: giữ PENDING | — | Không quyết định | Ứng viên vẫn trong hàng đợi, **không ghi gì** | — | — | Teacher DB hiện: 40 ứng viên PENDING, 0 review |
| S4 | Kiểm tra trước khi ACCEPT | Hệ thống | Yêu cầu ACCEPT (`observation_id`, `candidate_version`) | Hợp lệ hoặc lỗi | `CandidateReviewService._accept` | — | `test_stale_version_fails_closed`; `test_stale_observation_fails_closed`; `test_same_author_different_lecturer_rejected` |
| G4 | Cổng: hợp lệ? | Hệ thống | Kết quả S4 | Có → S5; Không → ER | — | — | — |
| ER | Dừng với HTTP 409 (hoặc 403/404/422) | — | Xung đột/dữ liệu cũ/đã quyết định/không đủ quyền/lý do trống | Người duyệt tải lại và làm lại từ R1 | Mã: `STALE_CANDIDATE_OBSERVATION`, `STALE_CANDIDATE_VERSION`, `CANDIDATE_ALREADY_DECIDED_CONFLICT`, `SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER`, `PREEXISTING_IDENTITY_PROVENANCE_CONFLICT`, `INVALID_REVIEW_REASON`… | Không ghi (giao dịch rollback) | `test_failure_rollback_no_partial_writes`; `test_accept_then_reject_conflicts`; `test_concurrent_accept_same_author_has_one_winner` |
| S5 | Ghi quyết định ACCEPT | Hệ thống | Yêu cầu hợp lệ | Review ACCEPT, danh tính **APPROVED**, bằng chứng danh tính, audit | `CandidateReviewService._accept` | `lecturer_scopus_candidate_reviews`, `lecturer_scopus_candidates.status`, `lecturer_scopus_identities`, `identity_evidence`, `audit_events` | `test_accept_happy_path`; `test_evidence_promotion_count_and_confidence`; `test_accept_retry_is_idempotent` |
| S6 | Kiểm tra lý do và ghi REJECT | Hệ thống | Yêu cầu REJECT + lý do | Review REJECT + audit | `CandidateReviewService._reject` | `lecturer_scopus_candidate_reviews`, `lecturer_scopus_candidates.status`, `audit_events` | `test_reject_happy_path`; `test_reject_blank_reason_rejected` |
| GP | Cổng song song | Hệ thống | Sau ACCEPT | Hai nhánh: truy vết và khai thác | — | — | — |
| R2 | Truy vết | REVIEWER/ADMIN | Review + audit | Xem lịch sử review; ADMIN xem nhật ký hệ thống | UC-19 `GET /reviews/history`; UC-07 `GET /audits` | — | `test_review_history_api` (32 ca); `test_audit_api` (35 ca) |
| E2 | Kết thúc: đã truy vết | — | — | — | — | — | — |
| L1 | Xem liên kết Scopus và công bố của tôi | LECTURER | Danh tính APPROVED | Liên kết và công bố của chính giảng viên | UC-21 `GET /lecturers/me/identities`; UC-22 `GET /lecturers/me/publications` | — | `test_a2_t04_lecturer_own_identities`; `test_a2_t05_lecturer_own_publications`; `test_a2_t21_no_cross_lecturer_leak` |
| E3 | Kết thúc: giảng viên khai thác kết quả | — | — | — | — | — | — |

## 3. Những điều sơ đồ cố ý **không** thể hiện (để tránh hiểu sai)

1. **Không có cổng "ghép tự động"**: không tồn tại đường nào tạo danh tính APPROVED mà không có ACCEPT của người.
2. **Hoàn tác quyết định duyệt không có** (schema có `REOPEN`/`REVOKE` nhưng không API/UI). Chỉ có hoàn tác ở **cấp đợt nhập** (UC-08a, UC-10a) — nằm ngoài luồng chính nên không vẽ; xem `usecase/specs/`.
3. **Nạp bằng chứng ngoài (C1) và sinh ứng viên (C2) là script CLI**, không có nút giao diện; vì vậy nằm ở làn Kỹ thuật viên.
4. **Tra cứu, thống kê (dashboard), xuất JSON, quản lý tài khoản** là các UC hỗ trợ độc lập, không nằm trên đường găng của quy trình này (xem UCD-5, UCD-2).
5. Thứ tự **S3 → C1/C2** là **tiền điều kiện dữ liệu** (cần công bố/tác giả đã chuẩn hóa), không phải ràng buộc mà phần mềm cưỡng chế bằng mã.
