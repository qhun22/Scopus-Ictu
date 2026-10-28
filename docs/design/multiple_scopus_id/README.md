# Tài liệu: Hỗ trợ nhiều Scopus Author ID

> Ngày tạo: 2026-10-27  
> Bối cảnh: ICTU báo cáo 35 giảng viên có ≥ 2 Scopus Author IDs (ví dụ: TS. Đỗ Đình Cường với IDs `26423550300` và `60561601800`)

## Nội dung thư mục này

| File | Mô tả |
|------|-------|
| [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) | Danh sách nguồn chính thức (Scopus, OpenAlex, Crossref, ORCID, ICTU) |
| [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md) | Nghiệp vụ → Model → Service → API → UI → Test |
| [BUSINESS_RULES.md](BUSINESS_RULES.md) | 10 quy tắc nghiệp vụ đã xác minh từ code |
| [IDENTITY_LIFECYCLE.md](IDENTITY_LIFECYCLE.md) | Vòng đời identity + 8 kịch bản (A–H) |
| [TEST_CASE_MATRIX.md](TEST_CASE_MATRIX.md) | T01–T10: spec đầy đủ, trạng thái hiện tại |
| [GAP_ANALYSIS.md](GAP_ANALYSIS.md) | G01–G06: gaps P0–P3 với đề xuất |
| [BACKLOG.md](BACKLOG.md) | BL-01–BL-12: backlog có priority và effort |

## Kết luận chính

**Hệ thống ĐÃ hỗ trợ** nhiều APPROVED IDs cho 1 giảng viên:
- DB constraint: `uq_identities_scopus_author_approved` — partial unique index
- Service: `_check_identity_conflicts()` Case B = allowed
- Projection: `_publication_set()` với `DISTINCT` dedup
- UI: `Identity/index.tsx` render N IdentityCards
- Test: integration test #38 **tồn tại** (code đọc được); **chưa được chạy PASS**

**Hệ thống CHƯA có:**
- REVOKE identity endpoint (Gap G02, P1)
- REOPEN candidate endpoint (Gap G03, P1)
- External Scopus merge detection (Gap G04, P2)
- UI side-by-side comparison (Gap G01, P2 — cải tiến UX, không blocking)

**Test tồn tại: 8/11** · **Bao phủ đủ assertions: 2/11 (T08, T09)** · **Bao phủ một phần: 6/11 (T01–T06)** · **Cần viết: 1 (T07)** · **Blocked (API gap): 2 (T10a, T10b)**  
*Không có test nào được chạy PASS. Xem TEST_CASE_MATRIX.md để biết chi tiết từng assertion.*
