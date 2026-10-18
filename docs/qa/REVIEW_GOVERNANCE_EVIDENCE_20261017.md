# Review Governance & Evidence Transparency — PROMPT 09 (17/10/2026)

- **Release:** `v1.0.0-rc.1` vẫn **HOLD**. Đợt này dừng để chủ đồ án nghiệm thu.
- **Phạm vi:** D-2 / W-01 (lý do khi duyệt), D-3 (minh bạch mức chứng cứ), thống nhất thuật ngữ review.
- **Ngoài phạm vi:** R3/R4, D-4 REOPEN, launcher PA-1, refactor i18n toàn hệ thống.
- **Ràng buộc đã giữ:**
  - Không stage, commit, tag, push, rebase, amend, reset.
  - Không migration, không đổi schema DB.
  - Không ghi DB A; không drop/reset DB restore; không đổi credential.

**Mức bằng chứng**

| Mã | Nghĩa |
|---|---|
| **VT** | pytest trên DB pytest cô lập trong allowlist của `tests/db_safety_guard.py` (`scopus_ictu_test_pytest_20261013`, guard xác minh server trước mỗi TRUNCATE) |
| **VR** | trình duyệt headless |
| **VW** | trình duyệt có ghi trên DB restore, đã được chủ đồ án duyệt riêng trong phiên này |
| **VS** | đọc code |

---

## 0. Bảo toàn (kiểm thực tế trước khi sửa)

| Mục | Kết quả |
|---|---|
| HEAD / branch | `237f7bc` / `main` |
| 4 file RC đã stage | blob `fb176d6`, `853c832`, `3b03317`, `0c34a85` không đổi (kiểm đầu và cuối phiên) |
| Worktree trước PROMPT 09 | sha256 của `git diff` = `3ac0fc68…`, **trùng** patch sau PROMPT 08 |
| Thay đổi PROMPT 07/08 | so từng dòng `+` của patch sau P08 với file hiện tại: còn đủ. Riêng 6 dòng ở `ApprovalQueue` được PROMPT 09 thay **có chủ đích** (badge ngữ cảnh → outline; "ACCEPT" / "REJECT" → nhãn đã bản địa hóa). |
| DB A | fingerprint cuối phiên = snapshot nguồn (**IDENTICAL**) |

---

## 1. File đã sửa

### Backend

| File | Nội dung |
|---|---|
| `app/services/review_reason_policy.py` (mới) | chính sách D-2: 3 điều kiện, tính từ dữ liệu server; `normalize_reason` |
| `app/services/candidate_review_service.py` | kiểm lý do ACCEPT (bước 10b); lỗi `ReviewReasonRequiredForWeakEvidenceError`; lưu lý do đã cắt khoảng trắng; audit thêm `reason_required` / `reason_triggers` |
| `app/api/v1/endpoints/reviews.py` | 422 + `reason_triggers` (additive trong envelope hiện có); `review_policy` trong chi tiết ứng viên |
| `app/schemas/review_api.py` | `ReviewDecisionPolicy`, `ReasonTrigger` (additive, có giá trị mặc định) |
| `app/services/identity_evidence_basis.py` (mới) | phân loại `evidence_basis` từ `identity_evidence` |
| `app/schemas/publication_api.py` | `LinkEvidenceBasisRead`, `LinkReviewDecisionRead`; thêm 3 trường **tùy chọn** vào `PublicationLecturerLinkRead` |
| `app/services/publication_queries.py` | truy vấn tập hợp (không N+1) cho evidence và quyết định review; identity id nội bộ **không** trả ra API |

### Test

| File | Nội dung |
|---|---|
| `tests/integration/test_review_reason_policy.py` (mới) | 15 case service |
| `tests/integration/test_review_reason_http.py` (mới) | 4 case HTTP, dữ liệu sinh bằng persistence thật |
| `tests/integration/test_publication_link_evidence_basis.py` (mới) | 3 case |
| `tests/unit/test_identity_evidence_basis.py` (mới) | 12 case |
| `tests/integration/test_candidate_review_service.py` | 3 lệnh ACCEPT thêm `reason=` — §2.4 |

### Frontend

| File | Nội dung |
|---|---|
| `pages/ApprovalQueue/index.tsx` | W-01: ô lý do ACCEPT, bắt buộc theo `review_policy`, xử lý 422, chống double-submit; nhãn hành động; empty-state không còn enum thô; badge ngữ cảnh dạng outline |
| `pages/ReviewHistory/index.tsx` | không đổi code (chỉ đổi nhãn i18n) |
| `pages/Publications/LinkEvidence.tsx` (mới), `pages/Publications/Detail.tsx` | D-3: 3 cột mới + ghi chú |
| `components/ui/Badge.tsx` | `appearance="outline"` (**PROPOSED**); mặc định `solid`, nên badge hiện có không đổi |
| `types/review.ts`, `types/publication.ts` | trường mới đều tùy chọn |
| `i18n/locales/vi.ts`, `en.ts`, `types.ts` | chỉ trong section `approvalQueue` và `reviewHistory` (§5) |

Line ending của từng file giữ nguyên (CRLF / LF).

---

## 2. D-2 — chính sách lý do đã thực hiện

### 2.1 Hợp đồng trước khi sửa (VS)

- REJECT đã bắt buộc lý do có nội dung ở service và CHECK DB (`ck_…_candidate_reviews_reason_required`: `action = 'ACCEPT' OR btrim(reason) <> ''`).
- ACCEPT nhận lý do tùy ý, **kể cả chuỗi toàn khoảng trắng** (lưu nguyên).
- Modal ACCEPT không có ô lý do (W-01).

**Không mâu thuẫn** với quy tắc mới: CHECK DB cho phép `reason` NULL với ACCEPT, nên quy tắc có điều kiện **không cần migration**.

### 2.2 Quy tắc (server là nguồn quyết định cuối)

Điều kiện được tính từ dữ liệu server; cờ do client gửi không được tin.

| Trigger | Điều kiện | Nguồn dữ liệu |
|---|---|---|
| `NAME_EVIDENCE_ONLY` | observation hiện hành **không** có bằng chứng `PUBLICATION` | `lecturer_scopus_candidate_evidence` |
| `SHARED_SCOPUS_AUTHOR` | Scopus Author ID có > 1 ứng viên | `lecturer_scopus_candidates` |
| `MULTIPLE_CANDIDATES_FOR_LECTURER` | giảng viên có > 1 ứng viên | `lecturer_scopus_candidates` |

**Cách áp dụng:**
- Khi có ≥ 1 trigger, ACCEPT cần lý do có nội dung; nếu không → **HTTP 422** `REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE`.
- Body lỗi: `{"detail", "code", "reason_triggers": [...]}`. Đây là envelope `APIError` hiện có, chỉ thêm trường; client cũ vẫn đọc được `code`.
- Lớp lỗi mới kế thừa `InvalidReviewReasonError` (cùng họ 422).
- Không có trigger → ACCEPT không cần lý do. Lý do toàn khoảng trắng được lưu là **NULL**, không lưu chuỗi rỗng.
- REJECT giữ hợp đồng cũ (`INVALID_REVIEW_REASON`, 422).

**Định nghĩa đếm:** dùng **đúng** định nghĩa đếm của ngữ cảnh mơ hồ đang hiển thị cho reviewer (mọi trạng thái), nên điều reviewer thấy và điều server áp dụng không lệch nhau. Nếu muốn chỉ đếm ứng viên còn PENDING, đó là quyết định nghiệp vụ riêng (§10).

### 2.3 Bất biến được giữ

| Bất biến | Cách giữ | Bằng chứng |
|---|---|---|
| Lý do không phải bằng chứng | lý do chỉ ghi vào review và audit; `IdentityEvidence` chỉ sao từ bằng chứng ứng viên | VT `test_name_only_accept_with_reason_succeeds_and_reason_is_not_evidence`; VW: liên kết mới chỉ có `NAME_SIMILARITY` |
| Idempotency | kiểm lý do đặt **sau** nhánh idempotent; phát lại quyết định đã ghi trả kết quả cũ, kể cả khi không gửi lý do | VT (đếm review / identity / evidence / audit không đổi); VW: phát lại → 200 `idempotent: true` |
| Xung đột Scopus ID | kiểm lý do đặt **sau** kiểm xung đột: ứng viên đã xung đột được báo 409 đúng bản chất, không bị đòi lý do trước; lý do không vượt được ràng buộc | VT `test_reason_does_not_bypass_scopus_author_conflict`, `test_same_author_different_lecturer_rejected` |
| Race | giữ `SELECT … FOR UPDATE` trên ứng viên và tác giả + unique `uq_identities_scopus_author_approved` (không đổi) | VT `test_concurrent_accept_same_author_has_one_winner` |
| Quyền | `require_role("ADMIN","REVIEWER")` + `_authorize_reviewer` (không đổi) | VT `test_lecturer_role_cannot_decide`; VW: LECTURER → 403 `FORBIDDEN` |
| Không ghi khi bị từ chối | lỗi phát sinh trước mọi `add` / `flush` | VT (đếm không đổi; ứng viên vẫn PENDING, version giữ nguyên); VW: 3 lần 422 không ghi |
| Lịch sử không đổi | không sửa bản ghi review cũ | VW: 2 ACCEPT cũ không lý do trên DB A / restore vẫn nguyên; DB A IDENTICAL |

### 2.4 Test cũ được cập nhật (3 lệnh, không nới assert)

Ba test cũ ACCEPT **không lý do** đúng các tình huống nay thuộc quy tắc bắt buộc. Chúng mã hóa hợp đồng cũ, nên được thêm `reason=`; mọi assert về xung đột và race giữ nguyên:
- `test_lecturer_can_have_multiple_approved_authors`
- `test_concurrent_accept_same_author_has_one_winner`

`test_same_author_different_lecturer_rejected` **không cần sửa**, sau khi kiểm lý do được đặt sau kiểm xung đột.

### 2.5 Frontend (W-01)

- Modal ACCEPT có ô lý do:
  - Nhãn "Lý do chấp nhận \*" khi bắt buộc, "(không bắt buộc)" khi không.
  - Cảnh báo liệt kê điều kiện bằng lời người dùng hiểu được, không hiện mã.
  - Ghi chú "Lý do không phải bằng chứng…".
- Nút "Chấp nhận" bị **disabled** khi bắt buộc mà lý do rỗng hoặc chỉ có khoảng trắng.
- Xử lý lỗi:
  - Nếu server vẫn trả 422 (ví dụ policy đã thay đổi), modal **giữ nguyên nội dung đã nhập** và hiện điều kiện server áp dụng.
  - `INVALID_REVIEW_REASON` hiện thông báo tương ứng; 409 giữ luồng cũ.
- Chống double-submit: `submitDecision` bỏ qua khi đang gửi; AntD `confirmLoading`; không đóng modal khi đang gửi.
- Mở / đóng modal không gửi request nào (VR: 0 request không phải GET).
- `aria-required`, `aria-invalid`; lỗi `role="alert"`.
- Đã sửa trong phiên: bộ đếm `0/4000` của AntD đè lên dòng ghi chú (thêm `mb-5` cho cả hai ô lý do).

---

## 3. D-3 — API contract `evidence_basis`

### 3.1 Nguồn dữ liệu (VS)

- `identity_evidence.evidence_type` là tập 7 giá trị đóng (CHECK DB).
- Bằng chứng được **sao** từ bằng chứng ứng viên khi ACCEPT (NAME → `NAME_SIMILARITY`; PUBLICATION → `DOI_EXACT` / `PUBLICATION_OVERLAP`).
- Quyết định của người duyệt **không bao giờ** được lưu là evidence (bất biến có sẵn của service).

→ Thêm theo hướng additive, **không cần migration**.

### 3.2 Kiểu dữ liệu

`PublicationLecturerLinkRead` thêm 3 trường tùy chọn: `link_status`, `evidence_basis`, `review_decision`.

**`link_status`:** `"APPROVED"`, luôn có giá trị này (danh sách chỉ gồm liên kết đã duyệt).

**`evidence_basis`:** `LinkEvidenceBasisRead | null`

| Trường | Kiểu |
|---|---|
| `level` | `IDENTIFIER_SUPPORT` \| `PUBLICATION_SUPPORT` \| `NAME_ONLY` \| `NO_RECORDED_EVIDENCE` |
| `supporting_evidence_types`, `contradicting_evidence_types` | `string[]` (giá trị CHECK DB, đã sắp xếp, không trùng) |
| `identifier_evidence_count`, `publication_evidence_count`, `name_evidence_count`, `affiliation_evidence_count` | `int` |
| `independently_verified` | `bool` |

**`review_decision`:** `{ action: "ACCEPT", decided_at, reason \| null } \| null`

### 3.3 Ánh xạ mức chứng cứ

Chỉ dòng `SUPPORTS` được tính:

| evidence_type | Nhóm | Ghi chú |
|---|---|---|
| `ORCID_EXACT` | IDENTIFIER | chưa có mã sinh (tài liệu `DATA_DICTIONARY` §585) |
| `DOI_EXACT`, `PUBLICATION_OVERLAP`, `COAUTHOR_CONFIRMED` | PUBLICATION | `PUBLICATION_OVERLAP` = trùng công bố theo tiêu đề |
| `NAME_SIMILARITY` | NAME | |
| `AFFILIATION_MATCH` | bằng chứng đơn vị | **không** nâng mức định danh |
| `APPROVED_ID` | chưa có đặc tả nghĩa | báo cáo nhưng **không** nâng mức (bảo thủ) |

**Quy tắc chặn suy luận VERIFIED:** `independently_verified` chỉ là `true` khi `level = IDENTIFIER_SUPPORT` và **không** có dòng `CONTRADICTS`.

**Bản ghi lịch sử thiếu bằng chứng:**
- Identity APPROVED không có dòng evidence → `NO_RECORDED_EVIDENCE`, `independently_verified = false`.
- Không có review tạo ra liên kết → `review_decision = null`, UI hiện "Không có bản ghi quyết định duyệt".

**Phân biệt hai khái niệm:**
- *Trạng thái liên kết* (`link_status`, tức quyết định duyệt) khác *mức chứng cứ* (`level`).
- `review_decision` là *provenance*, không phải *evidence*.

**Tương thích**
- Mọi trường mới có mặc định hoặc nullable.
- Client cũ bỏ qua được.
- Test cũ `"id" not in link` vẫn PASS (không lộ id nội bộ).
- LECTURER vẫn nhận `approved_lecturer_links = []`.
- Export (`PublicationExportLecturerLink`) **không đổi**.

**Truy vết**
- Mỗi mức truy được về dòng `identity_evidence` (`evidence_fingerprint`, `source_refs` vốn có).
- Quyết định truy được về `lecturer_scopus_candidate_reviews.resulting_identity_id` và trang `/review-history`.

---

## 4. UI hiển thị chứng cứ (khu vực "Liên kết giảng viên ICTU")

| Cột / thành phần | Hiển thị | Ghi chú |
|---|---|---|
| Ghi chú đầu bảng | "Liên kết đã duyệt là quyết định của người duyệt. Liên kết chỉ được coi là định danh đã xác minh khi có chứng cứ định danh độc lập…" | VI / EN |
| Trạng thái liên kết | Badge solid success "Liên kết định danh đã duyệt" / "Approved identity link" | trạng thái |
| Mức chứng cứ | Badge **outline**: "Có định danh độc lập" (success), "Có công bố hỗ trợ" (info), "Chỉ trùng tên" (warning), "Chưa ghi nhận chứng cứ" (neutral). Chỉ khi `independently_verified` mới hiện "Định danh đã xác minh độc lập". | thuộc tính, không phải trạng thái |
| Nguồn | "Nguồn: Trùng DOI công bố · Trùng tên · Trùng công bố (tiêu đề)" | không hiện mã nội bộ |
| Thiếu chứng cứ | "Liên kết không có bản ghi chứng cứ (có thể tạo trước khi hệ thống lưu chứng cứ)." | |
| Chứng cứ mâu thuẫn | dòng đỏ "Có chứng cứ mâu thuẫn: …" | |
| Quyết định duyệt | "Đã chấp nhận · thời gian", lý do (rút gọn 2 dòng, có `title`) hoặc "Không ghi lý do", liên kết "Xem lịch sử duyệt" | chỉ ADMIN / REVIEWER (LECTURER không thấy cả khu vực, giữ như cũ) |

**Kết quả VR trên DB A (3 liên kết đã duyệt thật)**

| Liên kết | Mức chứng cứ | Lý do |
|---|---|---|
| `DOI_EXACT` | "Có công bố hỗ trợ · Nguồn: Trùng DOI công bố" | có lý do |
| `NAME_SIMILARITY` | **"Chỉ trùng tên"** · "Không ghi lý do" | duyệt 12/10, trước D-2; giờ được minh bạch, dữ liệu không đổi |
| DOI + tên + tiêu đề | "Có công bố hỗ trợ", đủ 3 nguồn | — |

Không có mã thô; không có chữ "đã xác minh độc lập"; mobile overflowX 0; LECTURER không thấy khu vực.

---

## 5. Thuật ngữ VI / EN đã thống nhất

Phạm vi: chỉ section `approvalQueue` và `reviewHistory`. Đã kiểm: các khóa này chỉ 2 trang `/reviews` và `/review-history` dùng.

| Khái niệm | VI trước | VI sau | EN sau |
|---|---|---|---|
| PENDING | "Chờ duyệt" / "**Chờ xét duyệt**" (history) | **Chờ duyệt** | Pending review |
| ACCEPTED | "**Đã xác nhận**" / "**Đã chấp thuận**" | **Đã chấp nhận** | Accepted |
| REJECTED | Đã từ chối | Đã từ chối | Rejected |
| SUPERSEDED | "Đã thay thế" / "Đã bị thay thế" | **Đã thay thế** | Superseded |
| Hành động ACCEPT / REJECT / REOPEN (history) | "Chấp thuận (ACCEPT)"… | **Chấp nhận** / Từ chối / Mở lại | Accept / Reject / Reopen |
| Nút mở modal | "Xác nhận đối sánh" | **Chấp nhận đối sánh** | Accept match |
| Tiêu đề / OK modal | "Xác nhận quyết định ACCEPT" / "Xác nhận ACCEPT" / "Xác nhận REJECT" | **Chấp nhận ứng viên đối sánh** / **Chấp nhận** / **Từ chối** | Accept match candidate / Accept / Reject |
| Badge hành động trong modal | "ACCEPT" / "REJECT" (enum thô) | **Chấp nhận** / **Từ chối** | Accept / Reject |
| Kết quả ACCEPT | "Đã xác nhận đối sánh." | "Đã chấp nhận đối sánh. **Liên kết định danh đã duyệt** được tạo." | "…An approved identity link was created." |
| Xung đột | "…đã được xác nhận cho một giảng viên khác" | "…đã có **liên kết định danh đã duyệt** với một giảng viên khác" | "…already has an approved identity link…" |
| Empty-state | "REJECTED: 2 · ACCEPTED: 3 · PENDING: 144" | "Đã từ chối: 2 · Đã chấp nhận: 3 · Chờ duyệt: 144" | (theo nhãn EN) |

- **"VERIFIED"** chỉ còn dùng theo mức chứng cứ ("Định danh đã xác minh độc lập" khi `independently_verified`).
- **Ngữ cảnh khác trạng thái:**
  - "Còn 1 ứng viên khác", "Dùng chung (5 GV)" và các badge loại bằng chứng → **outline** (viền 1px, nền trắng).
  - "Chờ duyệt", "Đã chấp nhận" giữ **solid**.
  - VR: queue có badge trạng thái `border 0` và badge ngữ cảnh `border 1px`, cùng cao 23px.

---

## 6. Kết quả kiểm thử

### 6.1 Backend (VT)

| Run (`_postgres_demo_14_10/scratch/qa_runs/`) | Loại | Kết quả |
|---|---|---|
| `20261017T195059_baseline_review` | baseline **trước** khi sửa (5 file test review) | **71 passed** |
| `20261017T195713_p09_review_related` | — | **ABORTED**: launcher lỗi decode cp1252 trước khi ghi kết quả; giữ nguyên thư mục (không có manifest), có `ABORTED.txt` |
| `20261017T195932_p09_review_related` / `20261017T200353_p09_review_related_r2` | lần chạy giữa (lỗi đã sửa ở §2.4 và fixture HTTP) | 194 / 196 passed |
| `20261017T200619_p09_review_related_r3` | 11 file liên quan (4 file mới) | **200 passed** |
| `20261017T202153_p09_backend_unit` | toàn bộ `tests/unit` | **411 passed, 5 skipped** |

Không chạy lại toàn bộ 1.047 test; đề xuất full regression ở bước release.

### 6.2 Frontend

- `npx tsc --noEmit`: **PASS**.
- `npm run build`: **PASS**. Cảnh báo chunk > 500 kB đã có từ trước.
- Frontend không có test runner.

### 6.3 Trình duyệt

| Run | Môi trường | Ghi | Nội dung chính | Kết quả |
|---|---|---|---|---|
| `20261017T201703_p09_browser_readonly` (original) | A: 5199 → 8199 (backend khởi động lại để nạp code mới) | không | `review_policy` thật; modal ACCEPT VI / EN / mobile: bắt buộc + cảnh báo + OK disabled khi rỗng / khoảng trắng, enabled khi có nội dung → **Hủy**; modal REJECT OK disabled; empty-state; history; D-3 trên 3 liên kết; LECTURER | **PASS**. 0 request không phải GET, 0 lỗi API, 0 lỗi console. |
| `20261017T201947_p09_browser_readonly_rerun` (**rerun**, `rerun_of` ghi trong manifest) | A | không | xác nhận bản sửa bộ đếm đè ghi chú | **PASS** |
| `20261017T202444_p09_restore_write` (**original-incomplete**) | restore: 5399 → 8399 | **có** (2 quyết định) | ACCEPT 1 ứng viên chỉ-trùng-tên có lý do qua UI; REJECT 1 ứng viên có lý do qua UI | Ghi xong. `results.json` **không được tạo** (truy vấn SQL tổng hợp cuối dùng sai tên cột `event_metadata`, cột thật là `metadata`). Còn 5 ảnh + `INCOMPLETE.txt`. **Không chạy lại** (sẽ vượt giới hạn 2 quyết định). |
| `20261017T202720_p09_restore_write_verify` (**replacement**) | restore | **không** (fingerprint đầu = cuối) | thay quan sát đã mất bằng SQL chỉ đọc + request theo hợp đồng không ghi | **PASS** (chi tiết §6.4) |

Mỗi run có thư mục riêng, tên duy nhất, `manifest.json` (thời gian, commit, branch, sha256 của `git diff`, môi trường, loại test, checksum từng file). Không lưu mật khẩu, cookie, token; `secrets_stored: false`.

### 6.4 Chi tiết test ghi trên DB restore (VW, đã được duyệt)

**Trước khi ghi**
- Runtime guard: `candidates_by_status` của API 8399 = SQL trên DB restore (script dừng nếu lệch).
- Baseline sau TC-W1 / W2: PENDING 142, ACCEPTED 4, REJECTED 3.
- Đã chụp fingerprint.

**Sau khi ghi**
- PENDING 140, ACCEPTED 5, REJECTED 4: đúng **2** quyết định.
- Bảng thay đổi: `lecturer_scopus_candidate_reviews`, `lecturer_scopus_candidates`, `lecturer_scopus_identities`, `identity_evidence`, `audit_events`.

**Các quyết định đã ghi**
- Review ACCEPT: `PENDING → ACCEPTED`, lý do đã cắt khoảng trắng, có `resulting_identity_id`.
- Review REJECT: `PENDING → REJECTED`, có lý do, không tạo identity.
- Audit:
  - `CANDIDATE_ACCEPTED`: có lý do, `reason_required = true`, `reason_triggers = ["NAME_EVIDENCE_ONLY"]`.
  - `IDENTITY_CREATED_FROM_CANDIDATE`.
  - `CANDIDATE_REJECTED`: có lý do.
  - Quét audit tìm password / token / secret / cookie: **0**.
- Liên kết mới: evidence chỉ `NAME_SIMILARITY` ×2 (lý do **không** sinh evidence). Trang công bố hiện "**Chỉ trùng tên** · Nguồn: Trùng tên", "Đã chấp nhận · 20:25 17/10/2026 · PROMPT 09 restore: …", **không** có chữ "đã xác minh".

**Request không ghi**
- 422 trên một ứng viên PENDING chỉ-trùng-tên khác: thiếu lý do, `""` và `"   "` → 422 `REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE` + `reason_triggers`; ứng viên vẫn PENDING, cùng version.
- Phát lại ACCEPT đã ghi → 200, `idempotent: true`, cùng `review_id` và `resulting_identity_id`.
- Trạng thái nút trong modal (không gửi): ACCEPT disabled / disabled / enabled; REJECT disabled / disabled.
- LECTURER POST quyết định → 403 `FORBIDDEN`.
- Lịch sử hiện "Chấp nhận · Chờ duyệt → Đã chấp nhận" và "Từ chối · Chờ duyệt → Đã từ chối" kèm lý do.

### 6.5 Kiểm tra theo danh mục PROMPT 09 §4

| Test | Bằng chứng | Kết quả |
|---|---|---|
| ACCEPT bằng chứng mạnh, không lý do | VT | PASS |
| ACCEPT chỉ trùng tên, thiếu lý do → 422 | VT + VW | PASS |
| ACCEPT trùng tên có lý do | VT + VW | PASS |
| ACCEPT Scopus ID dùng chung | VT (trigger `SHARED_SCOPUS_AUTHOR`, có lý do thì PASS) | PASS |
| REJECT thiếu lý do / có lý do | VT + VW | PASS |
| Lý do chỉ khoảng trắng | VT (ACCEPT và REJECT) + VW (422, nút disabled) | PASS |
| Gửi lặp → idempotent | VT + VW | PASS |
| Xung đột Scopus ID không tạo liên kết sai | VT | PASS |
| LECTURER không quyết định được | VT + VW | PASS |
| Audit đầy đủ, không có secret | VT + VW | PASS |
| Lịch sử không đổi | VW (bản ghi cũ giữ nguyên; DB A IDENTICAL) | PASS |
| `evidence_basis` đúng chứng cứ thực tế | VT + VR (3 liên kết thật) + VW (liên kết mới) | PASS |
| Bản ghi thiếu bằng chứng không bị gắn VERIFIED | VT (`NO_RECORDED_EVIDENCE`, `APPROVED_ID`, `AFFILIATION_MATCH`, `CONTRADICTS`) | PASS |
| VI / EN, desktop / mobile, loading / error / disabled | VR (VI / EN / mobile, disabled); loading = AntD `confirmLoading` (VS) | PASS; loading **không đo** runtime |

---

## 7. Test ghi bị BLOCKED

Không có. Test ghi trình duyệt đã chạy trong phạm vi chủ đồ án duyệt riêng (tối đa 2 quyết định trên DB restore).

**Hạn chế còn lại:**
- Trạng thái *loading* của nút OK trong lúc gửi không đo riêng (thời gian phản hồi quá ngắn).
- Quan sát trong trình duyệt của run ghi gốc đã mất; đã thay bằng run xác minh (§6.3).

---

## 8. Variant Figma còn thiếu (PROPOSED, chưa sửa Figma)

| Variant | Dùng ở | Đặc tả đề xuất |
|---|---|---|
| **Badge outline** (thuộc tính / ngữ cảnh / mức chứng cứ) | `/reviews` (loại bằng chứng, mơ hồ, dùng chung); mức chứng cứ ở trang công bố | cao 23, px10, 11px Bold, pill; viền 1px tông nhạt (ví dụ warning `#FCD34D`), nền trắng, chữ cùng màu tone Figma `5:34` |
| Modal xác nhận có ô lý do (bắt buộc / tùy chọn) | ACCEPT / REJECT | Figma chưa có frame Modal. Đề xuất: tiêu đề 16 Bold; khối cảnh báo warning; nhãn có `*`; textarea r6 viền `#E2E8F0`; ghi chú 12px `#64748B`; footer Secondary "Hủy" + Primary / Danger. Hiện dùng AntD. |
| Hiển thị "mức chứng cứ + nguồn + quyết định" trong bảng | Data Table `9:41` | ô 2–3 dòng: badge outline + dòng nguồn 11px `#64748B` |
| Nút OK của modal AntD | `/reviews` | đang là xanh mặc định của AntD, chưa phải `brand #3A5FC3` → R3 / R2b |

---

## 9. Git status

**Stage (không đổi):**
- `.gitignore`
- `docs/qa/CSV_ONLY_ACCEPTANCE_20261016.md`
- `docs/qa/RELEASE_CANDIDATE_20261017.md`
- `docs/qa/RELEASE_READINESS_20261017.md`

**Unstaged — mới trong PROMPT 09:**
- Backend: `app/api/v1/endpoints/reviews.py`, `app/schemas/{publication_api,review_api}.py`, `app/services/{candidate_review_service,publication_queries}.py`, `tests/integration/test_candidate_review_service.py`.
- Frontend: `pages/{ApprovalQueue/index,Publications/Detail}.tsx`, `types/{publication,review}.ts`, `i18n/{locales/vi,locales/en,types}.ts`, `components/ui/Badge.tsx`.

**Unstaged — từ PROMPT 07/08 (giữ nguyên):** Dashboard / Home / MyPublications / Lecturers / Users / Normalization / Publications index, `tailwind.config.js`, xóa `buttonStyles.ts`, `.claude/launch.json`.

**Untracked mới:**
- `backend/app/services/{identity_evidence_basis,review_reason_policy}.py`
- 4 file test mới
- `frontend/src/pages/Publications/LinkEvidence.tsx`
- báo cáo này

**Bằng chứng QA:** nằm ngoài repo (`_postgres_demo_14_10/scratch/qa_runs/`), không đưa vào Git.

---

## 10. Backlog tiếp theo

| Mục | Ghi chú |
|---|---|
| **PA-1** launcher | chưa động tới |
| **W-02** và các lỗi nghiệp vụ độc lập | phương án riêng |
| **R3 / R4** | theo `DESIGN_SYSTEM_ROLLOUT_R1R2_20261017.md` §8 / §10, gồm AntD `Button` ở `/reviews` (nút OK chưa đúng brand) |
| Quyết định nghiệp vụ D-2 | Có đếm ứng viên REJECTED / SUPERSEDED khi xét "nhiều ứng viên" không? (Hiện đếm mọi trạng thái, khớp ngữ cảnh đang hiển thị.) |
| `rule_id` thô ở chi tiết `/reviews` | ví dụ `RULE_TITLE_STRIPPED_N2_FORMAT` (có câu giải thích bên cạnh) → đề xuất nhãn người dùng |
| `reconciliation` thô (`DOI_EXACT`) ở bằng chứng công bố `/reviews` | — |
| Dashboard | thẻ "Liên kết định danh Scopus" vẫn dùng "Đã duyệt" (UI-02 đã nghiệm thu, không đổi trong lượt này) |
| UI-13 / UI-14 / UI-15 / UI-18, `/tasks`, `/imports` | như báo cáo trước |
| `APPROVED_ID` | cần đặc tả nghĩa trước khi cho phép nâng mức chứng cứ |
| Sinh `ORCID_EXACT` | chưa có mã sinh, nên hiện không liên kết nào đạt `IDENTIFIER_SUPPORT` |
| **Bảo mật (quan sát trong phiên)** | `Scopus-Ictu/.tmp/completion2-a1-audit-read-api/backend/.env` chứa chuỗi kết nối kèm mật khẩu ở dạng rõ (thư mục tạm cũ). Đề xuất chủ đồ án kiểm tra và dọn; tôi không sửa, không lặp lại giá trị. |
| Full regression | đề xuất chạy toàn bộ backend test ở bước release |

---

**Dừng tại đây** để chủ đồ án và ChatGPT nghiệm thu PROMPT 09.
