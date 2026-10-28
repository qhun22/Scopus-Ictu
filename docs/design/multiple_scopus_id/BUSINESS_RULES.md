# Quy tắc nghiệp vụ — Nhiều Scopus Author ID

> Trạng thái: **VERIFIED** · Ngày: 2026-10-27  
> Mọi quy tắc đã được đối chiếu với code, không suy luận từ yêu cầu.

---

## BR-01 — Một giảng viên có thể có nhiều APPROVED Scopus Author IDs

**Nguồn gốc:** Thực tế ICTU: 35 giảng viên có ≥ 2 IDs do publish ở nhiều cơ sở, đổi tên, hoặc Scopus chưa merge.  
**Constraint DB:** Không có unique(lecturer_id) trên `lecturer_scopus_identities`.  
**Code:** `identity.py:116–120` `uq_lecturer_scopus_identities_pair` — unique(lecturer_id, **scopus_author_id**).  
**Hệ quả:** `get_approved_identity_summaries(lecturer_id)` có thể trả N > 1 phần tử.

---

## BR-02 — Một Scopus Author ID chỉ được APPROVED cho tối đa một giảng viên

**Nguồn gốc:** Quy tắc nghiệp vụ ICTU — một Scopus Author ID đại diện cho một người tại một thời điểm. Lưu ý: trên thực tế, một người **có thể có nhiều** Scopus Author IDs (xem BR-01); BR-02 chỉ nói rằng mỗi ID riêng lẻ chỉ được liên kết với tối đa một giảng viên ICTU tại một thời điểm.  
**Constraint DB:** `uq_identities_scopus_author_approved` — `UNIQUE(scopus_author_id) WHERE status='APPROVED'`.  
**Code enforcement:** `_check_identity_conflicts()` tại `candidate_review_service.py:375–410` — Case C = blocked.  
**Exception:** Nếu Scopus merge → một trong hai ID bị retire; xem GAP G04.

---

## BR-03 — ACCEPT luôn đi qua quy trình review có người duyệt

**Nguồn gốc:** Đề cương §1.3: "Hệ thống KHÔNG auto-confirm bất kỳ liên kết nào mà không có bằng chứng và đánh giá con người."  
**Code:** Không có auto-accept path. `CandidateReviewService._accept()` luôn yêu cầu `reviewer_user_id`.  
**Phạm vi:** Cả lần 1 lẫn lần N khi giảng viên có nhiều IDs.

---

## BR-04 — ACCEPT với evidence yếu phải có lý do tường minh (D-2 Policy)

**Kích hoạt khi:**
1. Chỉ có NAME evidence, không có PUBLICATION (`NAME_EVIDENCE_ONLY`)
2. Scopus Author đang được đề xuất cho >1 giảng viên (`SHARED_SCOPUS_AUTHOR`)
3. Giảng viên có >1 candidate đang active (`MULTIPLE_CANDIDATES_FOR_LECTURER`)

**Code:** `review_reason_policy.py` — `ACTIVE_CANDIDATE_STATUSES = ("PENDING", "ACCEPTED")`.  
**Kết quả nếu vi phạm:** HTTP 422 + `ReviewReasonRequiredForWeakEvidenceError`.  
**Lý do KHÔNG thay đổi evidence level:** Reason lưu trên `CandidateReview.reason`, không thành `IdentityEvidence`.

---

## BR-05 — Publications được deduplicate qua tất cả APPROVED IDs của giảng viên

**Nguồn gốc:** Nếu L1 có A1 và A2, và cùng bài báo có cả A1 lẫn A2 là đồng tác giả, công trình chỉ đếm 1 lần.  
**Code:** `lecturer_scopus_projection.py:305–330` `_publication_set()` dùng `.distinct()` trên `Publication.id`.  
**Không áp dụng cho:** linked_author_orders — vẫn ghi cả hai order (xem G06).

---

## BR-06 — Candidate generation là read-only; không auto-persist decision

**Code:** `services/matching/candidate_generator.py` — "This module deliberately stops at candidate generation."  
**Áp dụng cho multi-ID:** Nếu giảng viên đã có 1 APPROVED ID, vòng generation tiếp theo vẫn có thể tạo candidate cho ID thứ 2 (nếu evidence đủ). Reviewer phải duyệt thủ công.

---

## BR-07 — Concurrent reviews được serialize bằng SELECT FOR UPDATE

**Code:** `candidate_review_service.py:287–300` lock candidate row; `candidate_review_service.py:391–405` lock ScopusAuthor row.  
**Hệ quả:** Trong trường hợp 2 reviewers submit cùng lúc cho cùng candidate, chỉ 1 người thành công (winner). Người kia nhận `CandidateAlreadyDecidedError` hoặc DB unique constraint error tùy thứ tự transaction commit.  
**Idempotency:** Nếu cùng một reviewer submit lại (retry), path idempotent tại Case D của `_check_identity_conflicts()` xử lý thành công mà không raise exception.

---

## BR-08 — Evidence snapshot được build server-side, không nhận từ client

**Code:** `_build_evidence_snapshot()` tại `candidate_review_service.py:412–462`.  
**Lý do:** Ngăn client forge evidence hoặc submit stale evidence.  
**Nội dung snapshot:** candidate_id, lecturer_id, scopus_author_id, observation_id, generation_run_id, evidence details.

---

## BR-09 — Không có endpoint REOPEN trong hệ thống hiện tại

**Trạng thái:** DB model hỗ trợ (CHECK constraint), API chưa có.  
**Ảnh hưởng:** Sau khi REJECT, candidate cần generation run mới để xuất hiện lại.  
**Xem:** GAP G03.

---

## BR-10 — REVOKE phải có `compensates_review_id`

**Code:** `identity.py:298–303` CHECK constraint `compensates` — `action IN ('REVOKE','REOPEN') AND compensates_review_id IS NOT NULL`.  
**Lý do:** Audit trail bắt buộc — REVOKE phải liên kết ngược về APPROVE review ban đầu.
