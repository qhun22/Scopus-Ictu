# Backlog — Nhiều Scopus Author ID

> Trạng thái: **TRIAGED** · Ngày: 2026-10-27  
> Thứ tự ưu tiên: P0 → P1 → P2 → P3

---

## P0 — Trong scope luận văn (cần để demo/acceptance)

### BL-01 ~~Viết test T06~~ → Phân tích coverage gap T06 (SHARED_SCOPUS_AUTHOR D-2 trigger)
- **Trạng thái:** Test đã có tại `tests/integration/test_review_reason_policy.py:129`
- **File:** `test_review_reason_policy.py`
- **Mô tả:** T06 đã được covered. Phân tích xem có edge cases nào cần bổ sung không (ví dụ: SHARED + MULTIPLE_CANDIDATES cùng lúc).
- **Effort:** XS (< 30 phút review)

### BL-02 Viết test T07 (Publication dedup qua N IDs)
- **File:** `tests/integration/test_candidate_review_service.py` hoặc `test_lecturer_scopus_projection.py`
- **Mô tả:** L1 có 2 APPROVED IDs cùng là author của 1 publication. Verify total=1 không phải 2.
- **Effort:** S (1–2h)

### BL-03 ~~Viết test T08~~ → Phân tích coverage gap T08 (Idempotent ACCEPT)
- **Trạng thái:** Test đã có tại `tests/integration/test_candidate_review_service.py:582` — `test_accept_retry_is_idempotent`
- **Mô tả:** T08 đã được covered. Phân tích xem có các retry scenario khác chưa test không.
- **Effort:** XS (< 30 phút review)

---

## P1 — Nên có trong luận văn nhưng không blocking

### BL-04 ~~Viết test T09~~ → Phân tích coverage gap T09 (Concurrent race condition)
- **Trạng thái:** 3 concurrent tests đã có tại dòng 1403, 1457, 1502 trong `test_candidate_review_service.py`
- **Mô tả:** T09 đã được covered. Xem xét có thêm concurrent scenario nào chưa được test.
- **Effort:** XS (< 30 phút review)

### BL-05 Document gap G02 (REVOKE API) trong luận văn
- **Mô tả:** Thêm phần "Hạn chế và hướng phát triển" — đề cập REVOKE endpoint chưa có.
- **Effort:** XS (30 phút viết)

### BL-06 Document gap G03 (REOPEN API) trong luận văn
- **Tương tự BL-05**

---

## P2 — Future work (sau luận văn)

### BL-07 Implement REVOKE identity endpoint
- `POST /api/v1/identities/{identity_id}/revoke`
- Pattern: copy từ candidate REJECT workflow
- **Effort:** M (2–3 ngày)

### BL-08 Implement REOPEN candidate endpoint
- `POST /api/v1/reviews/{candidate_id}/reopen`
- Phức tạp hơn REVOKE vì phải clear ACCEPTED state
- **Effort:** L (3–5 ngày)

### BL-09 Dashboard widget: giảng viên có nhiều Scopus IDs
- Aggregate query: `COUNT(*) WHERE approved_identity_count > 1`
- Thêm widget vào `Dashboard/index.tsx`
- **Effort:** S (1–2 ngày)

### BL-10 UI side-by-side comparison trong ApprovalQueue
- Khi `other_candidates_for_lecturer > 0`, hiện split panel
- **Effort:** M (3–5 ngày frontend)

---

## P3 — Nice-to-have

### BL-11 Scopus External Merge detection (nghiên cứu trước khi implement)
- **⚠️ Giả thuyết cần xác minh:** Hành vi "ID cũ redirect về ID mới" sau khi Scopus merge profile chưa được xác minh. Cần nghiên cứu tài liệu Scopus API chính thức trước khi thiết kế detection job.
- Hướng tiếp cận: Kiểm tra xem Scopus Author Profile API trả về gì khi gọi ID đã bị retire (404, redirect, hay response khác).
- Notify ADMIN khi phát hiện thay đổi trạng thái Author ID
- **Effort:** XL (nghiên cứu + integration với Scopus API, cần API key)

### BL-12 Tự động import publications khi ACCEPT ID mới
- Sau ACCEPT identity mới, trigger re-import publications của Scopus Author đó
- **Effort:** L (cần integration với import pipeline)

---

## Thứ tự triển khai đề xuất cho đồ án

1. BL-02 (T07) — viết test dedup; đây là test duy nhất còn thiếu trong nhóm P0
2. BL-01, BL-03, BL-04 — review coverage gaps cho T06/T08/T09 (các test đã có)
3. BL-05, BL-06 — viết document vào luận văn
4. BL-07, BL-08 — implement REVOKE/REOPEN nếu còn thời gian (P2, sau luận văn)
