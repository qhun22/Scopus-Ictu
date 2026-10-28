# Ma trận test case — Nhiều Scopus Author ID

> Trạng thái: **SPECIFIED** · Ngày: 2026-10-27 · Cập nhật: 2026-10-27 (Gate A.3.1)  
> Phạm vi: T01–T10 — unit + integration, không ghi DB 5432, không auto-ACCEPT  
> Ký hiệu: ✅ **Test tồn tại + bao phủ đủ assertions** · 🔶 **Test tồn tại nhưng bao phủ một phần** · 🔴 **Không có test** · ❌ **Blocked (API gap)**  
> **QUAN TRỌNG: "Đã có" chỉ nghĩa test file tồn tại + logic được đọc từ code. Không có test nào được CHẠY PASS trong project này.**

---

## T01 — Giảng viên ACCEPT ID thứ nhất (baseline)

**Mô tả:** Giảng viên L1 chưa có APPROVED identity nào. Candidate (L1, A1) được ACCEPT.  
**Pre-condition:** candidate(L1,A1) status=PENDING, không có identity APPROVED nào cho L1 hay A1.  
**Inputs:** AcceptCandidateCommand(candidate_id, observation_id, version, reviewer_id)  
**Expected:**
- `AcceptResult.candidate_status == "ACCEPTED"`
- `AcceptResult.idempotent == False`
- `LecturerScopusIdentity` mới với status=APPROVED
- D-2 triggers: `[]` nếu có PUBLICATION evidence, `["NAME_EVIDENCE_ONLY"]` nếu chỉ có NAME
- Không exception

**Test file:** `tests/integration/test_candidate_review_service.py:436` — `test_accept_happy_path`  
**Assertions bao phủ:** AcceptResult fields, identity APPROVED tạo ra  
**Assertions chưa bao phủ:** D-2 trigger = `[]` khi có PUBLICATION (test dùng fixture có reason)  
**Status:** 🔶 Test tồn tại, bao phủ một phần (partial coverage) — NOT RUN

---

## T02 — Giảng viên ACCEPT ID thứ hai (multi-ID happy path)

**Mô tả:** Giảng viên L1 đã có APPROVED identity (L1,A1). Reviewer ACCEPT (L1,A2).  
**Pre-condition:** identity(L1,A1) status=APPROVED; candidate(L1,A2) status=PENDING.  
**Inputs:** AcceptCandidateCommand(L1,A2, reason="Tên khác nhau do viết tắt")  
**Expected:**
- Case B: allowed (không raise exception)
- `AcceptResult.candidate_status == "ACCEPTED"`
- `get_approved_identity_summaries(L1)` trả 2 phần tử
- `_publication_set(L1)` dedup publications qua cả A1 lẫn A2
- D-2 trigger `MULTIPLE_CANDIDATES_FOR_LECTURER` → reason required ✓

**Test file:** `tests/integration/test_candidate_review_service.py:891` — `test_lecturer_can_have_multiple_approved_authors`  
**Assertions bao phủ:** Case B allowed, 2 identities tạo ra (`len==2`), không exception  
**Assertions chưa bao phủ:** `_publication_set(L1)` dedup qua cả A1+A2 (không có assertion dedup trong test này)  
**Status:** 🔶 Test tồn tại, bao phủ một phần (partial coverage) — NOT RUN

---

## T03 — BLOCKED: Scopus Author đã APPROVED cho giảng viên khác (Case C)

**Mô tả:** A1 đã APPROVED cho L1. Reviewer thử ACCEPT (L2,A1).  
**Pre-condition:** identity(L1,A1) status=APPROVED; candidate(L2,A1) status=PENDING.  
**Expected:**
- `ScopusAuthorAlreadyApprovedError` raised
- HTTP 409 tại endpoint
- Không tạo identity mới
- identity(L1,A1) không bị ảnh hưởng

**Test file:** `tests/integration/test_candidate_review_service.py:955` — `test_same_author_different_lecturer_rejected`  
**Assertions bao phủ:** `ScopusAuthorAlreadyApprovedError` raised, không tạo identity mới  
**Assertions chưa bao phủ:** HTTP 409 response code (test là service-layer, không test HTTP layer); identity(L1,A1) không bị ảnh hưởng (implicit qua constraint)  
**Status:** 🔶 Test tồn tại, bao phủ một phần (service-layer) — NOT RUN

---

## T04 — D-2: ACCEPT với NAME_EVIDENCE_ONLY không có reason → fail

**Mô tả:** Candidate chỉ có NAME evidence (không có PUBLICATION). Reviewer ACCEPT mà không có reason.  
**Pre-condition:** observation evidence chỉ chứa kind=NAME.  
**Inputs:** AcceptCandidateCommand(reason=None)  
**Expected:**
- `ReviewReasonRequiredForWeakEvidenceError(triggers=("NAME_EVIDENCE_ONLY",))` — service layer
- HTTP 422 với triggers trong response body — HTTP layer (chưa có API-layer test)
- Không có LecturerScopusIdentity được tạo; candidate.status tetains PENDING

**Test file:** `tests/integration/test_review_reason_policy.py:93` — `test_name_only_accept_without_real_reason_is_refused_and_writes_nothing`  
**Assertions bao phủ:** exception raised + `triggers==("NAME_EVIDENCE_ONLY",)` + writes nothing + candidate stays PENDING (`fresh.status == "PENDING"`)  
**Assertions chưa bao phủ:** HTTP 422 response envelope (test là service-layer, không test HTTP layer)  
**Status:** 🔶 Test tồn tại, bao phủ một phần (service-layer) — NOT RUN

---

## T05 — D-2: ACCEPT với NAME+PUBLICATION và reason=None → pass

**Mô tả:** Candidate có cả NAME lẫn PUBLICATION evidence. Reviewer ACCEPT mà không có reason.  
**Pre-condition:** observation evidence chứa kind=NAME và kind=PUBLICATION.  
**Inputs:** AcceptCandidateCommand(reason=None)  
**Expected:**
- Không raise `ReviewReasonRequiredForWeakEvidenceError`
- `AcceptResult` thành công; `result.candidate_status == "ACCEPTED"`; `review.reason is None`
- `AcceptResult.publication_evidence_promoted >= 1` — chưa có assertion trong test tìm được

**Test file:** `tests/integration/test_review_reason_policy.py:76` — `test_strong_unique_evidence_accepts_without_reason`  
**Assertions bao phủ:** không exception; `result.idempotent is False`; `result.candidate_status == "ACCEPTED"`; `review.reason is None`  
**Assertions chưa bao phủ:** `publication_evidence_promoted >= 1` (không có assertion này trong test tại local HEAD)  
**Status:** 🔶 Test tồn tại, bao phủ một phần (thiếu assertion publication_evidence_promoted) — NOT RUN

---

## T06 — D-2: SHARED_SCOPUS_AUTHOR trigger

**Mô tả:** Scopus Author A1 đang là PENDING candidate cho cả L1 lẫn L2. Reviewer ACCEPT (L1,A1).  
**Pre-condition:** candidate(L1,A1) PENDING, candidate(L2,A1) PENDING.  
**Inputs:** AcceptCandidateCommand(reason="Đây là giảng viên L1 vì ORCID khớp")  
**Expected:**
- `SHARED_SCOPUS_AUTHOR` trong triggers
- AcceptResult thành công vì reason được cung cấp
- Candidate (L2,A1) vẫn PENDING nhưng bước tiếp theo sẽ bị Case C block

**Test file:** `tests/integration/test_review_reason_policy.py:129` — `test_shared_scopus_author_requires_reason_even_with_publication_evidence`  
**Assertions bao phủ:** `SHARED_SCOPUS_AUTHOR` trigger fire, reason required kể cả khi có PUBLICATION evidence, accept thành công khi có reason  
**Assertions chưa bao phủ:** HTTP 422 response envelope (test là service-layer)  
**Status:** 🔶 Test tồn tại, bao phủ một phần (service-layer) — NOT RUN

---

## T07 — Publication dedup qua nhiều APPROVED IDs

**Mô tả:** L1 có 2 APPROVED IDs (A1, A2). Cả hai đồng tác giả cùng publication P1. Khi get_lecturer_publications(L1), P1 chỉ xuất hiện 1 lần.  
**Pre-condition:** PublicationAuthor(P1, A1) và PublicationAuthor(P1, A2) đều tồn tại.  
**Expected:**
- `get_lecturer_publications(L1)` total = 1 (không phải 2)
- `items[0].linked_author_orders` chứa cả hai author_order
- `approved_identity_count == 2`

**Status:** 🔶 Test T07 chưa có — cần viết; dedup logic đã có tại `lecturer_scopus_projection.py:305–330`

---

## T08 — Idempotent ACCEPT (cùng observation submit 2 lần)

**Mô tả:** Reviewer submit ACCEPT cùng candidate + observation 2 lần (retry).  
**Pre-condition:** Sau khi ACCEPT lần 1 thành công.  
**Inputs:** AcceptCandidateCommand với cùng `candidate_id` + `observation_id`; `candidate_version` dùng `first.candidate_version` (version sau lần 1, không phải version gốc ban đầu)  
**Expected:**
- `AcceptResult.idempotent == True`
- Không tạo thêm identity
- Trả `resulting_identity_id` giống lần 1
- Không exception

**Test file:** `tests/integration/test_candidate_review_service.py:582` — `test_accept_retry_is_idempotent`  
**Phạm vi chính xác:** Test submit lại **cùng `candidate_id` + cùng `observation_id`** lần 2 (retry path). Đây **không** phải kịch bản candidate mới từ generation run khác.  
**Assertions bao phủ:** `idempotent=True`, `resulting_identity_id` giống lần 1, không tạo thêm rows  
**Status:** ✅ Test tồn tại, bao phủ đủ phạm vi retry cùng candidate — NOT RUN

---

## T09 — Concurrent ACCEPT: race condition SELECT FOR UPDATE

**Mô tả:** Hai request/worker đồng thời submit ACCEPT cho cùng candidate (L1, A1) — **trong test hiện tại dùng cùng `reviewer_user_id`** (không phải hai reviewer khác nhau).  
**Pre-condition:** Không có identity APPROVED nào.  
**Expected (theo test tại local HEAD `test_concurrent_accept_same_candidate_has_no_duplicates:1457`):**
- `len(successes) in {1, 2}` — có thể 1 hoặc 2 AcceptResult thành công
- Nếu 2 successes: đúng 1 trong 2 là idempotent (`sum(result.idempotent) == 1`)
- Nếu 1 success: người kia nhận `CandidateAlreadyDecidedError` (không phải IntegrityError trực tiếp)
- Không có 2 APPROVED identities được tạo (`count(lecturer_scopus_identities) == 1`)

**Phạm vi test hiện tại vs. phạm vi cần mở rộng:**
- Test hiện tại bao phủ: 2 request song song dùng **cùng reviewer_user_id** → đủ để kiểm tra SELECT FOR UPDATE và idempotency
- Phạm vi bổ sung (chưa có test): 2 reviewer **khác nhau** cùng submit → behavior có thể khác nhau ở idempotency logic (xác minh đòi hỏi test bổ sung)

**Test files:** `tests/integration/test_candidate_review_service.py`:
- Dòng 1403: `test_concurrent_accept_same_author_has_one_winner` — 2 candidates khác nhau cùng author
- Dòng 1457: `test_concurrent_accept_same_candidate_has_no_duplicates` — cùng candidate, kết quả {1,2} successes
- Dòng 1502: `test_concurrent_opposite_decisions_have_one_terminal_winner` — ACCEPT và REJECT song song  
**Assertions bao phủ (dòng 1457):** `len(successes) in {1, 2}`; nếu 2 successes thì 1 idempotent; `count(identities)==1`  
**Status:** ✅ Test tồn tại, bao phủ đủ phạm vi concurrent ACCEPT cùng reviewer_user_id — NOT RUN  
**Phạm vi chưa test:** 2 reviewer_user_id khác nhau → ghi là phạm vi kiểm thử bổ sung, không mặc định đã PASS

---

## T10a — REVOKE identity (MappingReview)

**Mô tả:** Identity(L1,A1) status=APPROVED → REVOKE → status=REVOKED qua ADMIN endpoint.  
**Pre-condition:** identity(L1,A1) APPROVED; `MappingReview` constraint `identity.py` cho phép action=REVOKE với compensates_review_id NOT NULL.  
**Expected nếu được implement:**
- REVOKE: action=REVOKE, from_status=APPROVED, to_status=REVOKED, compensates_review_id NOT NULL (audit trail)
- Identity không còn xuất hiện trong `_publication_set()`

**Gap:** **G02 [P1]** — không có API endpoint REVOKE identity. DB schema hỗ trợ; service/API chưa có.  
**Status:** ❌ Blocked — GAP G02 (P1). Xem GAP_ANALYSIS.md mục "G02"

---

## T10b — REOPEN candidate (LecturerScopusCandidateReview)

**Mô tả:** Candidate(L1,A1) status=REJECTED → REOPEN → status=PENDING, có thể review lại.  
**Pre-condition:** `candidate.py` CHECK constraint cho phép action=REOPEN từ ACCEPTED/REJECTED/SUPERSEDED.  
**Expected nếu được implement:**
- REOPEN: candidate.status = PENDING
- Candidate xuất hiện lại trong ApprovalQueue

**Lưu ý phân biệt với T10a:** T10a là REVOKE/REOPEN **identity** (MappingReview); T10b là REOPEN **candidate** (CandidateReview). Đây là hai workflow riêng biệt với model riêng.  
**Gap:** **G03 [P1]** — không có POST REOPEN candidate endpoint. DB schema hỗ trợ; service/API chưa có.  
**Status:** ❌ Blocked — GAP G03 (P1). Xem GAP_ANALYSIS.md mục "G03"

---

## Tóm tắt trạng thái

| Test | Mô tả ngắn | Test tồn tại | Bao phủ assertions | Đã chạy |
|------|-----------|-------------|-------------------|---------|
| T01 | Multi-ID baseline (ID 1) | ✅ Có | 🔶 Partial (thiếu D-2 trigger=[] khi PUBLICATION) | ❌ NOT RUN |
| T02 | Multi-ID happy path (ID 2) | ✅ Có | 🔶 Partial (thiếu dedup assertion trong test) | ❌ NOT RUN |
| T03 | Case C blocked | ✅ Có | 🔶 Partial (thiếu HTTP 409 assertion) | ❌ NOT RUN |
| T04 | D-2 NAME_ONLY no reason | ✅ Có | 🔶 Partial (thiếu HTTP 422 assertion) | ❌ NOT RUN |
| T05 | D-2 bypass khi có PUBLICATION | ✅ Có | 🔶 Partial (thiếu publication_evidence_promoted assertion) | ❌ NOT RUN |
| T06 | D-2 SHARED_SCOPUS_AUTHOR | ✅ Có | 🔶 Partial (thiếu HTTP 422 assertion) | ❌ NOT RUN |
| T07 | Publication dedup N IDs | 🔴 Không có | — | ❌ NOT RUN |
| T08 | Idempotent ACCEPT (cùng candidate) | ✅ Có | ✅ Đủ (retry cùng candidate) | ❌ NOT RUN |
| T09 | Concurrent race condition | ✅ Có | ✅ Đủ (3 concurrent scenarios) | ❌ NOT RUN |
| T10a | REVOKE identity (MappingReview) | 🔴 Không có | — | ❌ Blocked — GAP G02 (P1) |
| T10b | REOPEN candidate (CandidateReview) | 🔴 Không có | — | ❌ Blocked — GAP G03 (P1) |

**Tổng hợp:** 8/11 test tồn tại · 2 bao phủ đủ (T08, T09) · 6 bao phủ một phần (T01, T02, T03, T04, T05, T06) · 3 không có test (T07, T10a, T10b)  
**Tất cả "đã có" = test tồn tại trong codebase; KHÔNG CÓ test nào được chạy PASS.**
