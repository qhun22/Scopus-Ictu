# Ma trận truy xuất nguồn gốc — Nhiều Scopus Author ID

> Trạng thái: **CODE REVIEWED / NO TESTS RUN** · Ngày: 2026-10-27 · Cập nhật: 2026-10-27 (Gate A.3.1 errata)  
> Phạm vi: Từ nghiệp vụ → model → service → API → UI → test  
> Lưu ý: Tất cả xác nhận dưới đây là kết quả ĐỌC CODE tại HEAD `80a5e2a`; không có test nào được chạy PASS.

---

## M1 — Một giảng viên có nhiều Scopus Author ID được APPROVED

| Khía cạnh | Vị trí trong code | Xác nhận |
|-----------|-------------------|----------|
| **Constraint DB** | `identity.py:116–120` `uq_lecturer_scopus_identities_pair` — unique(lecturer_id, scopus_author_id) | Ngăn trùng cặp, không ngăn nhiều author khác nhau |
| **Partial unique index** | `identity.py:123–128` `uq_identities_scopus_author_approved` — unique(scopus_author_id) WHERE status='APPROVED' | Mỗi Scopus Author chỉ thuộc 1 giảng viên APPROVED |
| **Case B cho phép** | `candidate_review_service.py:375–410` `_check_identity_conflicts()` | Case B (lecturer đã có APPROVED) = OK |
| **Projection** | `lecturer_scopus_projection.py:65–150` `get_approved_identity_summaries()` | Trả ALL identities, order by scopus_id ASC |
| **Publication DISTINCT** | `lecturer_scopus_projection.py:305–330` `_publication_set()` | JOIN qua nhiều APPROVED IDs → DISTINCT → không đếm trùng |
| **Aggregate** | `lecturer_scopus_projection.py:286–292` | `approved_identity_count` luôn đếm đúng |
| **API endpoint** | `lecturer_scopus.py:112–122` `GET /me/identities` | list[ApprovedIdentitySummaryRead] — N phần tử |
| **UI** | `frontend/src/pages/Identity/index.tsx:197–200` | `grid gap-6 lg:grid-cols-2` → mỗi item = 1 IdentityCard |
| **Test** | `test_candidate_review_service.py:891` test #38 | Tạo 2 candidates, ACCEPT cả 2, assert len==2 ✓ |

## M2 — D-2 Policy: khi nào cần lý do khi ACCEPT

| Trigger | Điều kiện | Code |
|---------|-----------|------|
| `NAME_EVIDENCE_ONLY` | evidence chỉ có NAME, không có PUBLICATION | `review_reason_policy.py:64` `"PUBLICATION" not in set(evidence_kinds)` |
| `SHARED_SCOPUS_AUTHOR` | Scopus Author ID đang được đề xuất cho >1 giảng viên (PENDING/ACCEPTED) | `review_reason_policy.py:66–72` |
| `MULTIPLE_CANDIDATES_FOR_LECTURER` | Giảng viên có >1 candidate PENDING/ACCEPTED | `review_reason_policy.py:74–81` |
| **Kết quả** | `AcceptReasonPolicy.required == True` → HTTP 422 nếu không có reason | `candidate_review_service.py:188–198` `ReviewReasonRequiredForWeakEvidenceError` |

## M3 — Xung đột identity (Case C)

| Kịch bản | Kết quả | HTTP code | Code |
|----------|---------|-----------|------|
| Scopus Author đã APPROVED cho giảng viên KHÁC | Blocked | 409 | `ScopusAuthorAlreadyApprovedError` |
| Scopus Author đã APPROVED cho CÙNG giảng viên, retry **cùng candidate/observation** | Cho phép, trả AcceptResult(idempotent=True) — xác nhận qua `test_accept_retry_is_idempotent:582` (NOT RUN) | 200 | `candidate_review_service.py:565–585` |
| Scopus Author đã APPROVED cho CÙNG giảng viên, **candidate mới từ generation run khác** | ⚠️ NOT VERIFIED — path này chưa có test chuyên biệt | N/A | `_check_identity_conflicts()` Case D |
| Giảng viên đã có APPROVED IDs nhưng Scopus Author mới | Cho phép (Case B) | 200 | `_check_identity_conflicts():383–386` |

## M4 — Quy trình ACCEPT đầy đủ

| Bước | Hành động | File:line |
|------|-----------|-----------|
| 1 | Authorize reviewer (ADMIN/REVIEWER, is_active) | `candidate_review_service.py:551` |
| 2 | SELECT FOR UPDATE candidate | `candidate_review_service.py:554` |
| 3 | Check idempotency (cùng observation đã ACCEPT) | `candidate_review_service.py:557–590` |
| 4 | Validate candidate.status == PENDING | `candidate_review_service.py:592–596` |
| 5 | Validate observation & version | tiếp theo |
| 6 | Compute D-2 reason policy | `review_reason_policy.py:54–82` |
| 7 | Check identity conflicts (Cases C, E) | `_check_identity_conflicts():375–410` |
| 8 | Build evidence snapshot (server-side) | `candidate_review_service.py:412–462` |
| 9 | Create LecturerScopusIdentity (status=APPROVED) | trong `_accept()` |
| 10 | Promote candidate evidence → IdentityEvidence | `_promote_candidate_evidence_to_identity():464–508` |
| 11 | Tạo CandidateReview record | trong `_accept()` |
| 12 | Ghi AuditEvent | `_record_audit_events():510–541` |

## M5 — Matching Rules

| Rule ID | Mô tả | Evidence kind |
|---------|-------|---------------|
| RULE_EXACT_N0 | Tên chính xác (NFKC casefold) | NAME |
| RULE_TITLE_STRIPPED_N0 | Tên sau khi bỏ tiền tố học hàm | NAME |
| RULE_TITLE_STRIPPED_N2 | Tên stripped + bỏ diacritics | NAME |
| RULE_TITLE_STRIPPED_N2_FORMAT | Tên stripped + N2 + comma format | NAME |
| RULE_N2 | N0 + bỏ diacritics (d/đ fold) | NAME |
| RULE_N2_FORMAT | N2 + comma format normalization | NAME |
| RULE_N2_HYPHEN | N2 + bỏ comma và hyphen | NAME |
| (Publication overlap) | DOI/title match qua PublicationOverlapRule | PUBLICATION |
| (ORCID exact) | ORCID → Scopus ID | NAME (ORCID_EXACT khi promote) |

## M6 — Frontend: ApprovalQueue xử lý xung đột

| Sự kiện | Xử lý | File |
|---------|-------|------|
| 409 `SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER` | Toast lỗi conflict | `ApprovalQueue/index.tsx` |
| 422 `REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE` | Modal giữ mở, hiện triggers | `ApprovalQueue/index.tsx` |
| ambiguity_count > 0 | Badge "SHARED" trong queue table | `ApprovalQueue/index.tsx` |
| other_candidates_for_lecturer | Hiện trong detail panel | `ApprovalQueue/index.tsx` |

---
*Được sinh tự động từ code review ngày 2026-10-27. Cần cập nhật nếu model/service thay đổi.*
