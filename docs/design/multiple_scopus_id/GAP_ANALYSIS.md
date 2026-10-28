# Gap Analysis — Nhiều Scopus Author ID & Lifecycle

> Trạng thái: **REVIEWED** · Ngày: 2026-10-27  
> Ký hiệu mức độ: **P0** = blocking · **P1** = high · **P2** = medium · **P3** = low/future

---

## G01 — [P2] Không có UI side-by-side so sánh nhiều candidates cho cùng giảng viên

**Mô tả:**  
Khi giảng viên L1 có 2 candidates (L1,A1) và (L1,A2) trong ApprovalQueue, reviewer thấy `other_candidates_for_lecturer` trong detail panel nhưng không có giao diện so sánh song song để quyết định nên ACCEPT candidate nào trước, candidate nào sau.

**Hệ quả:**  
Reviewer phải tự mở từng candidate riêng biệt. Tăng rủi ro ACCEPT nhầm (nhất là với TS. Đỗ Đình Cường có 2 IDs với tên viết khác nhau). Đây là **cải tiến UX**, không blocking chức năng cốt lõi.

**Nguồn gốc:**  
Frontend `ApprovalQueue/index.tsx` hiện tại — `other_candidates_for_lecturer` chỉ list text, không có action button.

**Đề xuất:**  
- Thêm "View other candidates" button mở split panel
- Hiện candidate score/evidence side-by-side

**Effort:** M (medium) — frontend only, không cần API mới  
**Priority cho đồ án:** P2 — Đề cập trong luận văn như UI improvement; không blocking chức năng multi-ID

---

## G02 — [P1] Không có API endpoint REVOKE identity

**Mô tả:**  
DB model `mapping_reviews` đã có constraint hỗ trợ `action='REVOKE'` (from_status=APPROVED → to_status=REVOKED). Nhưng không có POST endpoint `/identities/{id}/revoke` hoặc tương đương.

**Hệ quả:**  
ADMIN không thể thu hồi một APPROVED identity qua UI/API khi phát hiện nhầm sau thực tế. **Không có luồng quản trị được hỗ trợ hiện tại.** Bất kỳ can thiệp nào đòi hỏi quy trình khắc phục đặc biệt được thiết kế và phê duyệt riêng — đây không phải thao tác thông thường và nằm ngoài phạm vi tài liệu này.

**Code refs:**  
- `identity.py:280–305` — transitions constraint cho phép REVOKE  
- `backend/app/api/v1/endpoints/` — không có revoke endpoint

**Đề xuất:**  
`POST /api/v1/identities/{identity_id}/revoke` với body `{reason: str}`

**Effort:** S (small) — service + endpoint, pattern có sẵn  
**Priority cho đồ án:** Đề cập là limitation; không cần implement trong thời gian luận văn

---

## G03 — [P1] Không có API endpoint REOPEN candidate

**Mô tả:**  
`LecturerScopusCandidateReview` model hỗ trợ `action='REOPEN'` (ACCEPTED/REJECTED/SUPERSEDED → PENDING). GET `/reviews/history` filter `action=REOPEN` tồn tại nhưng không có POST.

**Hệ quả:**  
Sau khi REJECT nhầm, reviewer phải đợi generation run mới để candidate xuất hiện lại. Không có self-correction workflow.

**Code refs:**  
- `candidate.py:304–308` — transitions CHECK cho REOPEN  
- `backend/app/api/v1/endpoints/reviews.py` — chỉ có GET history với REOPEN filter

**Đề xuất:**  
`POST /api/v1/reviews/{candidate_id}/reopen` với body `{reason: str}`

**Effort:** M — service phức tạp hơn (phải clear ACCEPTED state nếu reopen từ ACCEPTED)  
**Priority cho đồ án:** Đề cập là limitation (P1 — có trường hợp dùng thực tế)

---

## G04 — [P2] Không xử lý Scopus External Merge lifecycle

**Mô tả:**  
Khi Scopus merge hai profiles (ví dụ: A1 + A2 → A1 là ID master, A2 bị retire), hệ thống không có:
1. Cơ chế phát hiện merge (không polling Scopus API)
2. Workflow migrate: publications của A2 → A1
3. Workflow REVOKE identity(L1,A2) sau merge

**Hệ quả:**  
Nếu giảng viên có 2 APPROVED IDs và Scopus merge chúng, hệ thống vẫn giữ 2 APPROVED identities nhưng một trong chúng không còn valid trên Scopus.

**Scenarios bị ảnh hưởng (từ Evidence Pack):**  
TS. Đỗ Đình Cường: `26423550300` và `60561601800` — nếu Scopus merge trong tương lai.

**Đề xuất:**  
- P2 (ngắn hạn): Document kịch bản trong luận văn; không đề xuất can thiệp DB trực tiếp làm workaround thông thường
- P1 (future): Background job poll Scopus API phát hiện merge, sau đó kích hoạt review workflow có API

**Effort:** L — cần Scopus API integration  
**Priority cho đồ án:** Đề cập là future work trong kết luận luận văn

---

## G05 — [P2] Không có cảnh báo khi `approved_identity_count > 1` trên Dashboard

**Mô tả:**  
Dashboard ADMIN hiện tại không có thống kê số giảng viên có `approved_identity_count > 1`. ICTU biết có 35 giảng viên nhiều IDs nhưng không thể theo dõi trực tiếp qua UI.

**Code refs:**  
- `lecturer_scopus_projection.py:286–292` — trả `approved_identity_count`  
- `frontend/src/pages/Dashboard/index.tsx` — không có widget này

**Đề xuất:**  
Thêm widget "Giảng viên có nhiều Scopus ID" trong Dashboard ADMIN

**Effort:** S — query có sẵn, chỉ cần thêm aggregate endpoint + widget  
**Priority cho đồ án:** Nice-to-have

---

## G06 — [P3] Thứ tự tác giả khi nhiều IDs đồng tác giả cùng publication

**Mô tả:**  
`get_lecturer_publications()` dùng `distinct()` đúng trên Publication.id, nhưng `linked_author_orders` là `set[int]` — khi A1 ở vị trí 2 và A2 ở vị trí 3 của cùng publication, kết quả là `[2, 3]`.

**⚠️ UNVERIFIED / REVIEW NEEDED:** Tài liệu này không thể xác nhận rằng "A1 vị trí 2" và "A2 vị trí 3" là cùng một người thực sự, vì:  
1. Hai Scopus Author ID khác nhau chỉ là bằng chứng một người có thể có nhiều hồ sơ, không chứng minh hai tác giả ở hai vị trí trong cùng publication là cùng người.
2. Việc xác nhận cần đối chiếu với dữ liệu thực (tên, ORCID, affiliation) cho từng trường hợp cụ thể.

**Code refs:**  
- `lecturer_scopus_projection.py:219–237` — `author_orders_by_publication` dùng `set[int]`

**Hệ quả kỹ thuật (có thể quan sát):**  
`linked_author_orders` sẽ chứa cả hai vị trí khi có 2 APPROVED IDs cùng xuất hiện trong `PublicationAuthor` của một publication.

**Đề xuất:**  
Cần xem xét UI thể hiện hành vi này rõ ràng, đặc biệt khi hai author_order xuất hiện cho cùng một lecturer; không kết luận "correct by design" trước khi có dữ liệu thực xác minh.

**Effort:** XS  
**Priority cho đồ án:** Ghi chú trong luận văn

---

## Tóm tắt

| Gap | Mức | Mô tả ngắn | Trạng thái |
|-----|-----|-----------|-----------|
| G01 | P2 | UI side-by-side comparison | Open — UI improvement |
| G02 | P1 | API REVOKE identity | Open |
| G03 | P1 | API REOPEN candidate | Open |
| G04 | P2 | External Scopus merge lifecycle | Open — future work |
| G05 | P2 | Dashboard multi-ID widget | Open |
| G06 | P3 | Author order với nhiều IDs | ⚠️ UNVERIFIED — cần review với dữ liệu thực |

**P1: 2** · **P2: 3** · **P3: 1**
