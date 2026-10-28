# Vòng đời Identity — Nhiều Scopus Author ID

> Trạng thái: **ANALYZED** · Ngày: 2026-10-27

---

## Sơ đồ trạng thái LecturerScopusIdentity

> **Lưu ý quan trọng:** Trong luồng `CandidateReviewService._accept()`, `LecturerScopusIdentity` được tạo **trực tiếp với status=APPROVED** — không qua trạng thái trung gian. Tuy nhiên, model có `server_default='CANDIDATE'` trên cột `status` (`identity.py:67`), và DB schema cho phép trạng thái CANDIDATE (via REOPEN từ REVOKED). Trạng thái CANDIDATE trên identity do đó là **khả dĩ trong schema** nhưng **chưa có flow API nào tạo ra nó** trong code hiện tại.

```
                 CandidateReviewService._accept()
                          │
                          │ Tạo LecturerScopusIdentity trực tiếp
              ┌───────────▼───────────┐
              │       APPROVED        │◄──── Partial unique index
              └───────┬───────────────┘      uq_identities_scopus_author_approved
                      │ REVOKE (DB hỗ trợ; API gap G02 — endpoint chưa có)
              ┌───────▼───────────────┐
              │       REVOKED         │
              └───────┬───────────────┘
                      │ REOPEN-identity (schema-only; API chưa có — thuộc GAP G02, không liên quan G03)
              ┌───────▼───────────────┐
              │     CANDIDATE         │  (schema-only — chưa có flow API tạo ra; server_default='CANDIDATE')
              └───────────────────────┘
```

**REVOKE/REOPEN identity là schema-only:** DB model (`mapping_reviews`) có CHECK constraint hỗ trợ action=REVOKE và action=REOPEN trên identity, nhưng không có API endpoint nào để kích hoạt chúng. Cả hai đều thuộc **GAP G02** (REVOKE identity). REOPEN identity là schema khả dĩ nhưng chưa được đề xuất như API riêng.  
**Phân biệt:** GAP G03 là REOPEN **candidate** (LecturerScopusCandidateReview) — workflow hoàn toàn khác.

## Trạng thái LecturerScopusCandidate (khác với identity)

```
PENDING ──── ACCEPT ──► ACCEPTED
        └─── REJECT ──► REJECTED
        └─── SUPERSEDE ► SUPERSEDED (khi có generation run mới?)

ACCEPTED/REJECTED/SUPERSEDED ──► PENDING (REOPEN — API gap G03)
```

## 8 Kịch bản lifecycle

### Kịch bản A — Baseline (1 ID)
Giảng viên L1 có 1 Scopus Author A1. Reviewer ACCEPT.  
→ identity(L1,A1) = APPROVED. Không có bước tiếp theo bình thường.  
**Trạng thái:** ✅ Fully supported

---

### Kịch bản B — Thêm ID thứ hai (multi-ID chủ động)
ADMIN phát hiện L1 publish dưới ID A2 (tên khác). Generation tạo candidate(L1,A2). Reviewer ACCEPT với reason.  
→ identity(L1,A1) vẫn APPROVED + identity(L1,A2) = APPROVED mới.  
**Trạng thái:** ✅ Fully supported (test #38)

---

### Kịch bản C — Xung đột: Author A1 đề xuất cho 2 giảng viên
A1 được match với cả L1 (ORCID exact) lẫn L2 (tên similar). Reviewer ACCEPT (L1,A1) trước.  
→ identity(L1,A1) = APPROVED. Khi reviewer thử ACCEPT (L2,A1) → Case C blocked (ScopusAuthorAlreadyApprovedError).  
**Trạng thái:** ✅ Fully supported (test #39)

---

### Kịch bản D — REJECT nhầm, muốn REOPEN
Reviewer REJECT (L1,A2) nhầm. Muốn reopen để review lại.  
→ **GAP G03**: Không có REOPEN API. Phải đợi generation run mới.  
**Trạng thái:** ❌ API gap

---

### Kịch bản E — REVOKE một trong các APPROVED IDs
ADMIN phát hiện identity(L1,A2) nhầm. Muốn REVOKE A2 nhưng giữ A1.  
→ **GAP G02**: Không có REVOKE API. **Chưa có workflow UI/API được hỗ trợ.** Bất kỳ can thiệp nào đòi hỏi quy trình khắc phục đặc biệt được thiết kế và phê duyệt riêng — không hướng dẫn sửa DB trực tiếp.  
**Trạng thái:** ❌ API gap (DB model có constraint hỗ trợ trạng thái REVOKED; service/API chưa có)

---

### Kịch bản F — Scopus External Merge (A1 + A2 → A1 master)
Scopus merge profile A1 và A2 thành A1. L1 đang có APPROVED cho cả hai.  
→ **GAP G04**: Hệ thống không detect external merge.  
- Publications của A2 trên Scopus nay thuộc A1.  
- identity(L1,A2) vẫn APPROVED nhưng không còn valid.  
- Cần REVOKE identity(L1,A2) + re-import publications.  
**Trạng thái:** ❌ Future work

---

### Kịch bản G — Giảng viên rời ICTU
Giảng viên nghỉ việc. User account của giảng viên bị deactivate.  
→ Identity vẫn APPROVED (không tự REVOKE). Publications vẫn visible với bất kỳ user nào có quyền xem.  
→ **Lưu ý:** Không có API REVOKE nên ADMIN hiện **không thể** thu hồi identity qua UI/API. Xem GAP G02.  
**Trạng thái:** Partially handled (deactivate user account được hỗ trợ; identity **không** auto-REVOKE và không có API để REVOKE thủ công)

---

### Kịch bản H — Generation run thứ N tạo lại candidate cho ID đã APPROVED
Sau khi identity(L1,A1) = APPROVED, generation run tiếp theo tạo candidate(L1,A1) mới (candidate id khác).  
→ Reviewer ACCEPT candidate mới này. Khi ACCEPT:  
- `_check_identity_conflicts()` Case D: identity đã tồn tại với cùng (lecturer_id, scopus_author_id) và status=APPROVED.  
- Code path này **khác** với retry cùng candidate. Test `test_accept_retry_is_idempotent:582` tái-submit **cùng `candidate_id`**, không phải candidate mới từ generation run.  
- **CHƯA CÓ TEST** cho kịch bản ACCEPT candidate mới với identity đã APPROVED — đây là **NOT VERIFIED**.  
- Nếu identity REVOKED → path này cũng **CHƯA CÓ TEST** (blocked bởi GAP G02).  
**Trạng thái:** ⚠️ NOT VERIFIED — candidate mới + identity đã APPROVED chưa có test; REVOKE path blocked bởi GAP G02

---

## Bảng trạng thái tóm tắt

| Kịch bản | Mô tả | Trạng thái |
|----------|-------|-----------|
| A | 1 ID baseline | ✅ |
| B | Thêm ID thứ 2 | ✅ |
| C | Author conflict | ✅ |
| D | REOPEN sau REJECT nhầm | ❌ Gap G03 |
| E | REVOKE 1 trong N IDs | ❌ Gap G02 |
| F | Scopus external merge | ❌ Gap G04 |
| G | Giảng viên rời ICTU | Partial |
| H | Re-generation sau APPROVED | ⚠️ NOT VERIFIED (new candidate) |
