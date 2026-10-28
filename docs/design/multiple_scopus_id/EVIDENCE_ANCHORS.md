# EVIDENCE_ANCHORS.md
# Bằng chứng gốc cho 10 kết luận — Gate A.2

HEAD: `80a5e2a119a41bae61271ae4301b16c20d7dfb50`  
Ngày đọc code: 2026-10-27  
**QUAN TRỌNG: Không có lệnh `pytest` nào được thực thi trong phiên này. Mọi trạng thái test ghi dưới đây là kết quả ĐỌC CODE, không phải CHẠY TEST.**

---

## Phần 1 — Bằng chứng cho 10 kết luận

---

### Kết luận 1: Backend cho phép 1 lecturer có nhiều APPROVED Scopus IDs

**File:** `backend/app/models/identity.py`  
**Dòng:** 115–131 (đọc tại HEAD)  
**Trích đoạn:**
```python
# C4-03
UniqueConstraint(
    "lecturer_id",
    "scopus_author_id",
    name="uq_lecturer_scopus_identities_pair",
),
# C4-04: a Scopus author can be APPROVED for at most one lecturer.
# Partial unique index — explicit name.
Index(
    "uq_identities_scopus_author_approved",
    "scopus_author_id",
    unique=True,
    postgresql_where=text("status = 'APPROVED'"),
),
```

**Phân tích:**
- `uq_lecturer_scopus_identities_pair` = unique(lecturer_id, scopus_author_id) — không phải unique(lecturer_id) một mình. Không có constraint nào ngăn một lecturer có nhiều rows với status='APPROVED'.
- `uq_identities_scopus_author_approved` = UNIQUE(scopus_author_id) WHERE status='APPROVED' — chỉ giới hạn phía Scopus Author: một Author chỉ thuộc một lecturer.
- Không có `UniqueConstraint("lecturer_id")` standalone.

**Service:**  
`backend/app/services/candidate_review_service.py` dòng 375–410:  
> ⚠️ **ILLUSTRATIVE PSEUDOCODE** — không phải nguyên văn source. Để xác minh, đọc file tại HEAD `80a5e2a`.
```python
# ILLUSTRATIVE PSEUDOCODE — không phải nguyên văn source
def _check_identity_conflicts(self, lecturer_id, scopus_author_id) -> None:
    # Case A: no existing identity → allowed (no-op)
    # Case B: identity exists for same lecturer → allowed (multi-ID)
    # Case C: identity exists for DIFFERENT lecturer → BLOCKED
    # [query: SELECT FOR UPDATE on LecturerScopusIdentity WHERE scopus_author_id AND status=APPROVED]
    if existing is not None and existing.lecturer_id != lecturer_id:
        raise ScopusAuthorAlreadyApprovedError(...)
```
Điều kiện block chỉ khi `existing.lecturer_id != lecturer_id`. Cùng lecturer không bị block.

**Test:** `test_candidate_review_service.py:891` `test_lecturer_can_have_multiple_approved_authors` — `assert len(identities) == 2` (dòng 948). **CHƯA CHẠY.**

**Trạng thái: CODE VERIFIED / TEST NOT RUN**

---

### Kết luận 2: Một Scopus Author ID không thể APPROVED cho hai lecturers

**File:** `backend/app/models/identity.py` dòng 121–128  
**Trích đoạn (xem Kết luận 1 ở trên):** Index `uq_identities_scopus_author_approved` — UNIQUE(scopus_author_id) WHERE status='APPROVED'.

**File:** `backend/app/services/candidate_review_service.py` dòng 397–410  
**Trích đoạn:**
```python
existing = self._session.scalar(
    select(LecturerScopusIdentity)
    .where(
        LecturerScopusIdentity.scopus_author_id == scopus_author_id,
        LecturerScopusIdentity.status == "APPROVED",
    )
    .with_for_update()
)
if existing is not None and existing.lecturer_id != lecturer_id:
    raise ScopusAuthorAlreadyApprovedError(
        f"Scopus author {scopus_author_id} is already APPROVED "
        f"for lecturer {existing.lecturer_id}"
    )
```

**Test:** `test_candidate_review_service.py:955` `test_same_author_different_lecturer_rejected`  
**Assertion chính:** `with pytest.raises(ScopusAuthorAlreadyApprovedError):` (dòng 990)  
**CHƯA CHẠY.**

**Trạng thái: CODE VERIFIED / TEST NOT RUN**

---

### Kết luận 3: Test #38 tồn tại (và cấu trúc logic đúng)

**File:** `backend/tests/integration/test_candidate_review_service.py`  
**Dòng hàm:** 891–948  
**Nội dung key:**  
> ⚠️ **ILLUSTRATIVE PSEUDOCODE** — đây KHÔNG phải trích nguyên văn có thể đối chiếu. Các tên tham số, giá trị reason, và luồng fixture đã được đơn giản hóa. Để xác minh nguyên văn, đọc file tại HEAD `80a5e2a`.
```python
# ILLUSTRATIVE PSEUDOCODE — không phải nguyên văn source
def test_lecturer_can_have_multiple_approved_authors(...):
    # [setup: tạo 2 candidates (L1,A1) và (L1,A2) với reason required]
    r_a = service.accept_candidate(AcceptCandidateCommand(candidate_id=..., reason="..."))
    r_b = service.accept_candidate(AcceptCandidateCommand(candidate_id=..., reason="..."))
    assert r_a.action == "ACCEPT" and r_a.idempotent is False
    assert r_b.action == "ACCEPT" and r_b.idempotent is False
    assert r_a.resulting_identity_id != r_b.resulting_identity_id
    # [verify: 2 APPROVED identities tồn tại cho lecturer_id]
    assert len(identities) == 2
```

**Phạm vi tìm kiếm:** đọc trực tiếp file tại offset 891.  
**Test PASS/FAIL: CHƯA CHẠY. Chỉ xác nhận code tồn tại và logic đọc được nhất quán với Kết luận 1+2.**

**Trạng thái: CODE VERIFIED / TEST NOT RUN**

---

### Kết luận 4: `/identity` page hiển thị nhiều danh tính

**File:** `frontend/src/pages/Identity/index.tsx` dòng 197–200  
**Trích đoạn:**
```tsx
{!loading && !error && identities.length > 0 ? (
  <div className="grid gap-6 lg:grid-cols-2">
    {identities.map((identity) => <IdentityCard key={identity.scopus_id} identity={identity} copy={copy} locale={locale} />)}
  </div>
) : null}
```

**Phân tích:** `identities.map(...)` không giới hạn số lượng. `getMyApprovedScopusIdentities()` (dòng 160) gọi API `/me/identities`. API `lecturer_scopus.py:116–122` trả `list[ApprovedIdentitySummaryRead]` không giới hạn count.

**Test frontend:** Không có. Không chạy browser trong phiên.

**Trạng thái: CODE VERIFIED**

---

### Kết luận 5: Publication query dùng DISTINCT đúng (per-lecturer)

**File:** `backend/app/services/lecturer_scopus_projection.py`

**`_publication_set()` dòng 305–330:**  
> ⚠️ **ILLUSTRATIVE PSEUDOCODE** — cấu trúc join là chính xác; danh sách cột select đã lược bỏ. Để xác minh đầy đủ, đọc file tại HEAD `80a5e2a`.
```python
# ILLUSTRATIVE PSEUDOCODE — join logic chính xác; select columns lược bỏ
def _publication_set(self, lecturer_id: uuid.UUID):
    return (
        select(Publication.id.label("publication_id"), ...)  # [additional columns lược bỏ]
        .join(PublicationAuthor, PublicationAuthor.publication_id == Publication.id)
        .join(LecturerScopusIdentity,
              LecturerScopusIdentity.scopus_author_id == PublicationAuthor.scopus_author_id)
        .where(
            LecturerScopusIdentity.lecturer_id == lecturer_id,
            LecturerScopusIdentity.status == "APPROVED",
        )
        .distinct()
        .subquery("lecturer_scopus_publications")
    )
```

**Paginated query dòng 186:** `.distinct()` trên cùng join chain.

**Phân tích:** JOIN qua nhiều APPROVED identities của cùng một lecturer sẽ tạo ra duplicate Publication.id nếu publication có nhiều PublicationAuthor rows ứng với các approved identities khác nhau. `.distinct()` loại trùng tại SQL level.

**Test riêng cho dedup qua N IDs:** Không tìm thấy. `grep` kết quả: không có test tên `test_publication_dedup` hay `test_distinct`. **TEST NOT RUN / NO DEDICATED TEST FOUND.**

Lệnh grep đã dùng:
```
grep -rn "def test_.*dedup\|def test_.*distinct\|def test_.*publication.*multi" backend/tests/ --include="*.py"
```
→ Không có output.

**Trạng thái: CODE VERIFIED / NO DEDICATED TEST**

---

### Kết luận 6: Dedup per-lecturer KHÔNG áp dụng cho `/publications/export`

**File:** `backend/app/services/publication_export.py` dòng 165–180  
**Trích đoạn:**
```python
pubs = session.scalars(
    select(Publication)
    .where(*publication_filters(q=q, year=year, ...))
    .order_by(Publication.year.desc().nullslast(), Publication.eid.asc())
).all()
```

**Phân tích:** Export query trực tiếp `select(Publication)` với text filters, không join qua `LecturerScopusIdentity`. Export này là **canonical publication dataset toàn bộ**, không phải per-lecturer view. Dedup per-lecturer (qua DISTINCT trên identity join) không liên quan đến endpoint này. Báo cáo gốc không làm rõ điều này — scope dedup chỉ là `/me/publications` và `/me/publications` aggregate.

**Trạng thái: CODE VERIFIED / Làm rõ scope**

---

### Kết luận 7: Không có REVOKE identity tại service/API

**Lệnh grep đã chạy:**
```bash
grep -rn "def.*revoke_identity\|def.*revoke_mapping" backend/app/ --include="*.py"
```
→ **Không có output.**

```bash
grep -rn "def \|router\." backend/app/api/v1/endpoints/reviews.py | head -20
```
→ Các routes chỉ có: `review_context`, `list_review_candidates`, `review_candidate_detail`, `decide_review_candidate`, `list_review_history_endpoint`. Không có route nào tên `revoke`.

```bash
grep -rn "revoke" backend/app/api/v1/endpoints/ --include="*.py" | grep -i "identity\|mapping\|lecturer_scopus"
```
→ **Không có output.** (Kết quả `revoke` duy nhất trong API là `revoke_override_endpoint` tại `affiliations.py:494` — khác domain.)

**DB model hỗ trợ:** `identity.py:280–305` có `action='REVOKE'` trong CHECK constraint của `mapping_reviews`. Constraint DB tồn tại; service/API chưa implement.

**Trạng thái: CODE VERIFIED — Không có REVOKE identity trong service/API**

---

### Kết luận 8: Không có POST REOPEN candidate tại API

**Lệnh grep đã chạy:**
```bash
grep -rn "def.*revoke_identity\|def.*revoke_mapping\|def.*reopen_candidate\|def.*reopen_identity" backend/app/ --include="*.py"
```
→ **Không có output.**

**Evidence dương:** `reviews.py:647`:
```python
action: Literal["ACCEPT", "REJECT", "REOPEN"] | None = Query(default=None),
```
Đây là **query parameter** của GET `/history`, không phải POST endpoint. Dùng để filter lịch sử, không phải để thực hiện REOPEN.

**Reviews endpoint functions (toàn bộ routes trong reviews.py):**
- `GET /context` → `review_context`
- `GET /candidates` → `list_review_candidates`
- `GET /candidates/{id}` → `review_candidate_detail`
- `POST /candidates/{id}/reviews` → `decide_review_candidate` (chỉ nhận action='ACCEPT'/'REJECT')
- `GET /history` → `list_review_history_endpoint`

Không có POST REOPEN route.

**DB model hỗ trợ:** `candidate.py:284` `action IN ('ACCEPT', 'REJECT', 'REOPEN')` và `identity.py:269` — constraint cho phép REOPEN ở DB, chưa có service/API.

**Trạng thái: CODE VERIFIED — Không có POST REOPEN**

---

### Kết luận 9: Compensation/reversal — DB schema sẵn sàng, service chưa implement

**File:** `backend/app/models/identity.py` dòng 256–260, 296–305  
**Trích đoạn `compensates_review_id`:**
```python
compensates_review_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("mapping_reviews.id", ondelete="RESTRICT"),
    nullable=True,
)
```

**CHECK constraint:**
```python
CheckConstraint(
    "(action IN ('APPROVE', 'REJECT') AND compensates_review_id IS NULL) "
    "OR "
    "(action IN ('REVOKE', 'REOPEN') AND compensates_review_id IS NOT NULL)",
    name="compensates",
),
```

**Grep service layer:**
```bash
grep -rn "compensation\|compensates_review_id" backend/app/ --include="*.py" | grep -v "model\|#"
```
→ **Không có output.** Field `compensates_review_id` chỉ tồn tại trong model definition, không được ghi bởi bất kỳ service method nào.

**Trạng thái: PARTIAL — DB schema sẵn sàng, service/API chưa implement**

---

### Kết luận 10: Review-policy triggers được mô tả đúng

**File:** `backend/app/services/review_reason_policy.py` dòng 32–42  
**Trích đoạn:**
```python
TRIGGER_NAME_EVIDENCE_ONLY = "NAME_EVIDENCE_ONLY"
TRIGGER_SHARED_SCOPUS_AUTHOR = "SHARED_SCOPUS_AUTHOR"
TRIGGER_MULTIPLE_CANDIDATES_FOR_LECTURER = "MULTIPLE_CANDIDATES_FOR_LECTURER"

ACCEPT_REASON_TRIGGERS = (
    TRIGGER_NAME_EVIDENCE_ONLY,
    TRIGGER_SHARED_SCOPUS_AUTHOR,
    TRIGGER_MULTIPLE_CANDIDATES_FOR_LECTURER,
)
```

**Logic:**
- `NAME_EVIDENCE_ONLY`: dòng 64 `if "PUBLICATION" not in set(evidence_kinds): triggers.append(...)`
- `SHARED_SCOPUS_AUTHOR`: dòng 66–72 `if author_candidates > 1: triggers.append(...)`
- `MULTIPLE_CANDIDATES_FOR_LECTURER`: dòng 74–81 `if lecturer_candidates > 1: triggers.append(...)`

**Tests đã đọc (CHƯA CHẠY):**

`test_review_reason_policy.py:93–108` — `test_name_only_accept_without_real_reason_is_refused_and_writes_nothing`:
```python
assert err.value.triggers == ("NAME_EVIDENCE_ONLY",)
```

`test_review_reason_policy.py:129–137` — `test_shared_scopus_author_requires_reason_even_with_publication_evidence`:
```python
assert err.value.triggers == ("SHARED_SCOPUS_AUTHOR",)
```

`test_review_reason_policy.py:140–145` — `test_lecturer_with_several_candidates_requires_reason`:
```python
assert err.value.triggers == ("MULTIPLE_CANDIDATES_FOR_LECTURER",)
```

`test_review_reason_policy.py:148–154` — `test_all_three_triggers_are_reported_together`:
```python
assert err.value.triggers == ("NAME_EVIDENCE_ONLY", "SHARED_SCOPUS_AUTHOR", "MULTIPLE_CANDIDATES_FOR_LECTURER")
```

**Trạng thái: CODE VERIFIED / TEST NOT RUN**

---

## Phần 2 — Bảng đối chiếu T01–T10a/T10b

> **Cập nhật Gate A.3.1 errata:** T10 được tách thành T10a/T10b; T04/T05 hạ từ "đủ" xuống "partial". Đồng bộ với TEST_CASE_MATRIX.md.

| ID | Tên T-case | Test trong codebase | Bao phủ assertions | Đã chạy? |
|----|-----------|--------------------|--------------------|---------|
| T01 | ACCEPT ID thứ nhất (baseline) | `test_accept_happy_path:436` | 🔶 Partial — thiếu D-2 trigger=[] khi có PUBLICATION | ❌ NOT RUN |
| T02 | ACCEPT ID thứ hai (multi-ID) | `test_lecturer_can_have_multiple_approved_authors:891` | 🔶 Partial — thiếu dedup assertion | ❌ NOT RUN |
| T03 | Case C blocked | `test_same_author_different_lecturer_rejected:955` | 🔶 Partial — thiếu HTTP 409 assertion | ❌ NOT RUN |
| T04 | NAME_EVIDENCE_ONLY no reason → fail | `test_name_only_accept_without_real_reason...:93` | 🔶 Partial — thiếu HTTP 422 assertion | ❌ NOT RUN |
| T05 | NAME+PUBLICATION no reason → pass | `test_strong_unique_evidence_accepts_without_reason:76` | 🔶 Partial — thiếu `publication_evidence_promoted` assertion | ❌ NOT RUN |
| T06 | SHARED_SCOPUS_AUTHOR trigger | `test_shared_scopus_author_requires_reason...:129` | 🔶 Partial — thiếu HTTP 422 assertion | ❌ NOT RUN |
| T07 | Publication dedup qua N IDs | Không có test chuyên biệt | — | ❌ NOT RUN / NO TEST |
| T08 | Idempotent ACCEPT (retry cùng candidate, version=first.candidate_version) | `test_accept_retry_is_idempotent:582` | ✅ Đủ cho phạm vi retry cùng candidate | ❌ NOT RUN |
| T09 | Concurrent ACCEPT (2 threads, cùng candidate) | `test_concurrent_accept_same_candidate_has_no_duplicates:1457` + 2 tests khác | ✅ Đủ — `len(successes) in {1,2}`; nếu 2 thì 1 idempotent; `count(identities)==1` | ❌ NOT RUN |
| T10a | REVOKE identity (MappingReview) | Không có test | — | ❌ Blocked — GAP G02 (P1) |
| T10b | REOPEN candidate (CandidateReview) | Không có test | — | ❌ Blocked — GAP G03 (P1) |

**Tóm tắt (Gate A.3.1 errata):**

| Nhóm | Cases | Ghi chú |
|------|-------|---------|
| Test tồn tại, bao phủ đủ | T08, T09 | 2/11 — CHƯA CHẠY |
| Test tồn tại, bao phủ một phần | T01–T06 | 6/11 — CHƯA CHẠY |
| Không có test chuyên biệt | T07 | Cần viết |
| Blocked bởi API gap | T10a, T10b | G02 (P1), G03 (P1) |

---

## Phần 3 — Grep commands đã dùng để xác nhận "không tồn tại"

```bash
# Không có REVOKE identity endpoint
grep -rn "def.*revoke_identity\|def.*revoke_mapping" backend/app/ --include="*.py"
# → Không có output

# Không có REOPEN candidate POST endpoint
grep -rn "def.*revoke_identity\|def.*revoke_mapping\|def.*reopen_candidate\|def.*reopen_identity" backend/app/ --include="*.py"
# → Không có output

# Xác nhận REVOKE chỉ có ở affiliations (khác domain)
grep -rn "revoke" backend/app/api/v1/endpoints/ --include="*.py" | grep -i "identity\|mapping\|lecturer_scopus"
# → Không có output (chỉ có revoke_override_endpoint trong affiliations.py)

# Xác nhận không có test dedup publications
grep -rn "def test_.*dedup\|def test_.*distinct\|def test_.*publication.*multi" backend/tests/ --include="*.py"
# → Không có output

# Xác nhận không có service layer compensation
grep -rn "compensation\|compensates_review_id" backend/app/ --include="*.py" | grep -v "model\|#"
# → Không có output
```

**Phạm vi tìm kiếm:** toàn bộ `backend/app/` và `backend/tests/` tại HEAD `80a5e2a119a41bae61271ae4301b16c20d7dfb50`. File `.pyc` bị loại.

---

## Phần 4 — Nguồn chưa kiểm chứng

Các URL sau trong `SOURCE_REGISTRY.md` **chưa được truy cập** trong phiên này:
- `https://service.elsevier.com/app/answers/detail/a_id/11212`
- `https://api.openalex.org/...`
- `https://api.crossref.org/works/{doi}`
- `https://pub.orcid.org/v3.0/{orcid}/external-identifiers` (endpoint đúng; tuy nhiên sự hiện diện của Scopus Author ID trong response **không được bảo đảm** — chỉ có khi người dùng đã liên kết tài khoản)
- `https://api.elsevier.com/documentation/...`

SOURCE_REGISTRY.md là tài liệu tham chiếu từ kiến thức chung, không phải kết quả truy cập trong phiên.
