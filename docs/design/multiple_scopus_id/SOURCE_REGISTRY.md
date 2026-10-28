# Source Registry — Hỗ trợ nghiệp vụ nhiều Scopus Author ID

> Trạng thái: **PARTIALLY VERIFIED** · Ngày: 2026-10-27 · Cập nhật: 2026-10-27 (Gate A.3)  
> Phạm vi: Tính năng một giảng viên ↔ nhiều Scopus Author ID (ICTU: 35 giảng viên có ≥ 2 ID)  
> Chú thích trạng thái: ✅ Đã truy cập · ⚠️ Chưa truy cập (ghi nhận từ tài liệu / suy luận) · ❌ Thông tin sai — đã sửa

---

## 1. Nguồn chính thức Scopus / Elsevier

| Mã | Tên nguồn | URL / Tham chiếu | Nội dung xác nhận | Trạng thái |
|----|-----------|------------------|-------------------|-----------|
| SCP-01 | Scopus Author Profile Help | `https://service.elsevier.com/app/answers/detail/a_id/11212` | Một người có thể có nhiều Profile nếu tên viết theo nhiều cách khác nhau hoặc đăng ký ở nhiều cơ sở | ⚠️ Chưa truy cập |
| SCP-02 | Author Profile Merger | `https://service.elsevier.com/app/answers/detail/a_id/11212/~/request-to-merge-author-profiles-in-scopus` | Scopus cung cấp công cụ merge; hành vi redirect của ID cũ sau merge **chưa xác minh** (suy luận từ tài liệu Elsevier) | ⚠️ Chưa xác minh redirect |
| SCP-03 | Scopus Author ID FAQ | `https://www.scopus.com/freelookup/form/author.uri` | Mỗi Scopus Author ID là định danh duy nhất, bền vững | ⚠️ Chưa truy cập |
| SCP-04 | Elsevier Author Feedback Wizard | Giao diện tự báo cáo trùng hồ sơ | Giảng viên có thể tự yêu cầu merge qua wizard | ⚠️ Chưa truy cập |
| SCP-05 | Scopus Preview API | `https://api.elsevier.com/documentation/SCOPUSSearchAPI.wadl` | `dc:identifier` chứa `AUTHOR_ID:XXXXXXX` | ⚠️ Chưa truy cập |

## 2. Nguồn dữ liệu mở / bổ trợ

| Mã | Nguồn | URL | Vai trò trong dự án | Trạng thái |
|----|-------|-----|---------------------|-----------|
| OA-01 | OpenAlex Works API | `https://api.openalex.org/works?filter=authorships.author.id:…` | Tra cứu cross-reference DOI → Author | ⚠️ Chưa truy cập |
| OA-02 | OpenAlex Authors API | `https://api.openalex.org/authors/A…` | Xem thông tin author, external IDs; **không xác nhận được mapping ORCID → Scopus ID** trực tiếp qua API này | ⚠️ Khả năng bị ghi quá mức |
| OA-03 | OpenAlex merge history | `ids.openalex` field | **Lưu ý:** `ids.openalex` chứa OpenAlex ID, không phải lịch sử merge Scopus; phát hiện merge Scopus cần endpoint riêng của Elsevier | ⚠️ Mô tả ban đầu không chính xác |
| CR-01 | Crossref REST API | `https://api.crossref.org/works/{doi}` | Xác thực DOI, author affiliation | ⚠️ Chưa truy cập |
| CR-02 | Crossref metadata | `author[].affiliation[]` | ICTU affiliation lookup | ⚠️ Chưa truy cập |
| OR-01 | ORCID Public API | `https://pub.orcid.org/v3.0/{orcid}/external-identifiers` | Endpoint đúng để lấy danh sách định danh liên kết; **không bảo đảm hồ sơ ORCID luôn chứa Scopus Author ID** — chỉ có nếu người dùng đã liên kết thủ công hoặc qua Scopus OAuth | ⚠️ Endpoint đúng nhưng diễn giải cần kiểm tra từng trường hợp |

## 3. Nguồn chính thức ICTU

| Mã | Nguồn | URL / Nơi lưu trữ | Ghi chú | Trạng thái |
|----|-------|--------------------|---------|-----------|
| ICTU-WEB | Hướng dẫn gộp tài khoản Scopus ICTU | `https://repository.ictu.edu.vn/huong-dan-gop-tai-khoan-scopus/` | Nguồn chính thức của ICTU — liệt kê ID Scopus của giảng viên | ✅ Đã truy cập (2026-10-27) |
| ICTU-01 | DS. Vũ Thị Quỳnh Anh | `SCOPUS_RAW_DIR` / CRAW | Author ID: `57223028088` | ⚠️ Chưa đối chiếu ICTU-WEB |
| ICTU-02 | TS. Trương Thị Thu Hà | `SCOPUS_RAW_DIR` | Author ID: `57226012765` | ⚠️ Chưa đối chiếu ICTU-WEB |
| ICTU-03 | TS. Đỗ Đình Cường | `SCOPUS_RAW_DIR` | Author IDs: `26423550300`, `60561601800` | ⚠️ Chưa đối chiếu ICTU-WEB |
| ICTU-04 | TS. Đinh Xuân Lâm | `SCOPUS_RAW_DIR` | Author ID chính (từ ICTU-WEB): `59707347300`; ID thứ hai cần rà soát (từ ICTU-WEB): `58805827700`; ID cũ `59192485500` — **UNVERIFIED, không đưa vào danh sách tin cậy** | ✅ ID chính/phụ sửa từ ICTU-WEB; ID cũ loại khỏi danh sách trusted |
| ICTU-05 | PGS.TS. Nguyễn Xuân Huy | `SCOPUS_RAW_DIR` | Author ID: xác nhận bổ sung | ⚠️ Chưa đối chiếu ICTU-WEB |
| ICTU-06 | GS.TS. Lương Chi Mai | `SCOPUS_RAW_DIR` | Author ID: xác nhận bổ sung | ⚠️ Chưa đối chiếu ICTU-WEB |

**Ghi chú ICTU-04:** Tài liệu cũ ghi "ThS. Đinh Xuân Lâm" với ID `59192485500`. Nguồn chính thức ICTU-WEB xác nhận học hàm là **TS.**, ID chính là **`59707347300`**, ID thứ hai cần rà soát là `58805827700`. ID `59192485500` là **UNVERIFIED** và không được đưa vào danh sách ID tin cậy.

**Ghi chú ICTU-03:** TS. Đỗ Đình Cường với IDs `26423550300`, `60561601800` — chưa đối chiếu trực tiếp với ICTU-WEB trong phiên này (ICTU-WEB đã truy cập nhưng xác nhận ICTU-04 là trọng tâm). Trạng thái ⚠️ là đúng.

## 4. Nguồn kỹ thuật nội bộ (repository)

| File | Vai trò |
|------|---------|
| `backend/app/models/identity.py` | LecturerScopusIdentity, IdentityEvidence, MappingReview — constraint chính |
| `backend/app/models/candidate.py` | LecturerScopusCandidate, CandidateGenerationRun, Evidence, Review |
| `backend/app/services/candidate_review_service.py` | Logic ACCEPT/REJECT, _check_identity_conflicts (Cases A–E) |
| `backend/app/services/review_reason_policy.py` | D-2 policy: 3 trigger conditions |
| `backend/app/services/lecturer_scopus_projection.py` | _publication_set() DISTINCT, get_approved_identity_summaries() |
| `backend/app/services/matching/candidate_generator.py` | 7 rules RULE_EXACT_N0 → RULE_N2_HYPHEN |
| `backend/tests/integration/test_candidate_review_service.py` | Tests #38, #39 xác nhận multi-ID |

## 5. Ấn phẩm làm bằng chứng (Evidence Pack)

| Mã | DOI | Giảng viên | Ghi chú |
|----|-----|------------|---------|
| PUB-01 | `10.1007/978-3-031-50818-9_37` | TS. Đỗ Đình Cường | ORCID `0009-0004-7250-6710`, Springer 2024 |
| PUB-02 | `10.1007/978-3-031-80943-9_19` | TS. Đinh Xuân Lâm | IAST/ICTU, tác giả thứ 3, Springer |

---
*File này chỉ mô tả cấu trúc nguồn; không chứa dữ liệu thực Scopus/ICTU.*
