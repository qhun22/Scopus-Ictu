# Ưu tiên 4 — JSON + Craw + Matching: E2E thật (Gate 4)

**Ngày:** 13-14/10/2026
**Mốc Git khi hoàn tất:** nhánh `main`, chưa commit (chờ bạn xem báo cáo). HEAD trước khi bắt đầu: `0322f96`.
**DB dùng để E2E sống (live UI):** `scopus_ictu_test_withjson_r2_20261011` (PostgreSQL `127.0.0.1:55432`, role `scopus_demo_user`) — DB test cũ có sẵn từ nghiệm thu WITH-JSON 12/10, nâng cấp Alembic head lên `c7f2a9b1d3e5` trong phiên này (3 migration thuần cộng thêm bảng affiliation, không đụng bảng lecturer/publication/candidate).
**DB pytest (tách biệt tuyệt đối):** `scopus_ictu_test_pytest_20261013`, đã allowlist sẵn, không dùng cho E2E sống.

---

## 1. Thay đổi code/schema

**Không có migration mới.** Toàn bộ GAP đóng bằng service/API/UI mới, tái dùng 100% schema hiện có (`evidence_kind='PUBLICATION'` đã có sẵn trong CHECK constraint).

### Backend — service mới
| File | Vai trò |
|---|---|
| [backend/app/services/matching/craw_assisted_discovery.py](../../backend/app/services/matching/craw_assisted_discovery.py) | Thuật toán phát hiện candidate mới từ Craw. **Đã tự phát hiện và sửa một lỗi thiết kế nghiêm trọng của chính mình** trong phiên này (xem mục 2) — bản cuối dùng quy tắc 2 neo bắt buộc: vị trí tác giả thật (`PublicationAuthor`) VÀ tương quan tên độc lập (token trùng sau chuẩn hóa N2). Trả về `discovered` (candidate mới) tách biệt `unattributed` (bằng chứng công bố có thật nhưng chưa quy thuộc về ai — không bao giờ trở thành candidate). |
| [backend/app/services/matching/generation_workflow.py](../../backend/app/services/matching/generation_workflow.py) | Điều phối ADMIN-triggered run: `CandidateGenerator` → `PublicationEvidenceEnricher` → `discover_craw_assisted_candidates` → `CandidatePersistenceService`. Tự sinh `run_id` (UUID), không nhận tham số từ request ngoài xác nhận. |
| [backend/app/services/lecturer_dataset/craw_ingestion_workflow.py](../../backend/app/services/lecturer_dataset/craw_ingestion_workflow.py) | ADMIN preview→apply nạp Craw qua web, đọc `CRAW_SOURCE_DIR` (biến môi trường, không nhận path từ request — cùng mẫu `AFFILIATION_SOURCE_DIR`), tái dùng nguyên vẹn `KnownPublicationIngestionService` đã có (không viết lại logic mapping/dedup). |

### Backend — API mới (`/api/v1/matching/*`, ADMIN-only)
| Route | Mục đích |
|---|---|
| `POST /matching/candidates/generate` | Chạy sinh ứng viên (tên + Craw-assisted), ghi PENDING, trả số liệu thật |
| `POST /matching/craw/preview` | Xem trước nạp Craw, chỉ đọc |
| `POST /matching/craw/apply` | Áp dụng nạp Craw (yêu cầu `fingerprint` khớp preview + `confirm: true`) |

### Frontend mới
| File | Vai trò |
|---|---|
| [frontend/src/api/matching.ts](../../frontend/src/api/matching.ts) | Client gọi 3 route trên |
| [frontend/src/pages/Normalization/MatchingTab.tsx](../../frontend/src/pages/Normalization/MatchingTab.tsx) | Tab "Đối sánh" mới trong trang Chuẩn hóa dữ liệu (ADMIN-only qua `RoleRoute` có sẵn ở `/normalization`) — 2 thẻ: nạp Craw (preview/checkbox xác nhận/apply) và sinh ứng viên (1 nút, số liệu kết quả ngay sau khi chạy) |
| [frontend/src/pages/ApprovalQueue/index.tsx](../../frontend/src/pages/ApprovalQueue/index.tsx) (sửa) | Thêm badge tím "Chỉ từ Craw (không khớp tên)" phân biệt rõ với "Có công bố hỗ trợ" (tên+Craw) và "Chỉ bằng chứng tên"; thêm `Alert` cảnh báo rõ ràng trong modal chi tiết khi candidate không có bằng chứng tên nào — **không dùng field mới nào từ backend**, suy ra hoàn toàn từ `name_evidence_count === 0 && publication_support_count > 0` đã có sẵn trong response |

---

## 2. Lỗi thiết kế tự phát hiện và sửa trong phiên này (quan trọng, không được bỏ qua)

Bản đầu tiên của `craw_assisted_discovery.py` chỉ neo candidate Craw-assisted vào **vị trí tác giả** (`PublicationAuthor`) đơn thuần: mọi tác giả xuất hiện trên một công bố Scopus đã reconcile DOI/title với known-publication của 1 giảng viên đều trở thành candidate — kể cả khi công bố đó có 5 tác giả và chỉ 1 người thật sự liên quan tới giảng viên đó. Đây chính là lỗi "mass candidate generation" mà bạn phát hiện và yêu cầu sửa trước khi tích hợp tiếp.

**Đã sửa:** quy tắc 2 neo bắt buộc đồng thời — (1) vị trí tác giả thật + (2) tương quan tên độc lập (ít nhất 1 token tên trùng sau chuẩn hóa N2 giữa tên giảng viên và tên/biến thể tên của đúng Scopus Author ở vị trí đó, độ dài token ≥2 để tránh false-positive từ chữ cái đơn). Vị trí tác giả thỏa (1) nhưng fail (2) không bao giờ trở thành candidate — trả về riêng dưới dạng `unattributed`.

**Test bắt buộc đã viết và PASS** (cả bản thuần logic `test_craw_assisted_discovery.py` và bản E2E qua API thật `test_matching_api.py`): công bố 5 tác giả/chỉ 1 giảng viên ICTU khớp tên → đúng 1 candidate + 4 unattributed; DOI trùng nhưng sai người (tác giả ở vị trí đó không liên quan tên) → 0 candidate; tên giống hệt → candidate đúng; tên viết tắt (qua biến thể tên `ScopusAuthorNameVariant`) → vẫn neo được; 2 giảng viên ICTU cùng 1 bài → cả 2 đều neo đúng độc lập, cặp chéo không khớp tên bị loại đúng.

**Bằng chứng đo được trên dữ liệu thật** (xem mục 4): trong 571 vị trí tác giả được xét trên DB WITH-JSON thật, chỉ 110 (19%) có tương quan tên và trở thành candidate; 461 (81%) bị loại đúng vì không có ai liên quan tên — xác nhận quy tắc 2 neo hoạt động bảo thủ đúng như thiết kế, không sinh ồ ạt.

---

## 3. Lỗi hạ tầng tự phát hiện và sửa trong phiên này

### 3.1. `httpx2` — điều tra sai rồi tự sửa lại đúng
Lúc đầu nghi ngờ `httpx2` trong `pyproject.toml`/`affiliation_online_fetch.py` là typosquatting, đã sửa thành `httpx` — **sai**. Xác minh lại: `httpx2` là gói PyPI thật (2.13.1, do chính tác giả Starlette/httpx phát hành), và Starlette 1.6+/1.7 cài trong venv demo thật sự `import httpx2` trước tiên trong `starlette/testclient.py`. Đã **revert nguyên trạng cả 4 file** về đúng commit gốc. Nguyên nhân gốc của lỗi import ban đầu: dùng nhầm Python 3.14 hệ thống thay vì venv `_venv_backend_demo_py312` đã có sẵn `httpx2`.

### 3.2. Advisory lock session-scoped bị "mất dấu" qua connection pool (lỗi thật, đã sửa triệt để)
`generation_workflow.py` bản đầu dùng `pg_advisory_lock` (session-scoped) để chống 2 lượt sinh ứng viên chạy chồng nhau, giữ khóa qua một `session.commit()` giữa hàm. Phát hiện qua test tích hợp chạy 2 lần liên tiếp: đôi khi câu lệnh mở khóa chạy trên **một connection khác** với câu lệnh khóa ban đầu (do `session.commit()` trả connection cũ về pool, câu lệnh sau đó có thể nhận một connection khác từ pool) → khóa bị treo vĩnh viễn trên connection cũ, lượt sinh ứng viên sau luôn bị từ chối `GENERATION_IN_PROGRESS` dù không ai đang chạy thật.

**Đã sửa bằng cách bỏ hẳn cơ chế khóa ứng dụng này** — không cần thiết vì `CandidatePersistenceService.persist_generation` đã tự an toàn dưới concurrency thật qua `ON CONFLICT DO NOTHING` + `with_for_update()` (2 lượt chạy đồng thời chỉ tạo 2 run_id khác nhau, không bao giờ trùng candidate root). Xác nhận lại bằng test chạy 10 lần liên tiếp không flaky, và toàn bộ 1004 test chạy sạch.

### 3.3. Thư mục pytest tạm bị khóa quyền (môi trường, không phải code)
`C:\Users\...\Temp\pytest-of-QuangHuy` bị từ chối quyền liệt kê (không phải do phiên này gây ra, không phải tiến trình sống giữ khóa). Giải quyết bằng `--basetemp` trỏ tới thư mục riêng an toàn (`_postgres_demo_14_10/pytest_tmp_priority4_20261013`), **không xóa/sửa thư mục cũ**.

---

## 4. Kết quả E2E thật trên DB WITH-JSON (410 lecturer, 660 publication, 1207 Scopus author, Craw 48 lecturer mapped/327 known-publication)

**Thực hiện qua trình duyệt thật (Browser pane), đăng nhập ADMIN thật, bấm nút UI thật — không gọi API trực tiếp bỏ qua giao diện.**

| Bước | Kết quả quan sát |
|---|---|
| Đăng nhập ADMIN (`p4ui.admin@ictu.edu.vn`, tài khoản tạo riêng cho phiên kiểm thử này) | Thành công, vào Trang chủ |
| Mở tab "Đối sánh" mới (`/normalization`) | Hiển thị đúng 2 thẻ, banner giải thích rõ ràng |
| Bấm "Xem trước" nạp Craw | 48 giảng viên trong nguồn Craw, 48 đã khớp hồ sơ, 0 chưa khớp, 327 công bố đã biết **đã có sẵn** (từ nghiệm thu 12/10 trước đó), 0 mới — đúng kỳ vọng vì chưa đổi dữ liệu nguồn |
| Bấm "Chạy sinh ứng viên" | **149 ứng viên tổng** (39 từ khớp tên, **110 mới từ Craw-assisted**), **571 bằng chứng công bố Craw chưa quy thuộc về ai** |
| Xác nhận ghi DB thật (không chỉ UI) | `select count(*) from lecturer_scopus_candidates` → **149**, khớp UI tuyệt đối |
| Xác nhận không ghi đè quyết định REVIEWER cũ | DB có sẵn 1 REJECTED + 2 ACCEPTED từ lần nghiệm thu 12/10 — **vẫn còn nguyên trạng thái đó sau khi chạy lại generation**, không bị reset về PENDING |
| Mở "Duyệt đối sánh", lọc "Có công bố hỗ trợ" | Badge tím mới "Chỉ từ Craw (không khớp tên)" hiển thị đúng cho candidate Craw-assisted thật, badge xanh cyan "Có công bố hỗ trợ" cho candidate có cả 2 loại bằng chứng |
| Mở chi tiết 1 candidate Craw-assisted thật (PGS.TS. Nguyễn Văn Núi ↔ Nguyen, Van-Nui) | Mục C hiển thị đúng `Alert` cảnh báo "KHÔNG khớp tên theo 4 quy tắc chuẩn", mục D hiển thị đúng bằng chứng DOI_EXACT thật (`10.1007/978-3-031-18162-6`) |
| Xác nhận App DB (`scopus_ictu_app`) không bị động tới | `candidate_generation_runs` = 0 (không đổi) |
| Xác nhận teacher DB không bị động tới | `candidate_generation_runs` = 2 (số cũ, không tăng trong phiên này) |
| Xác nhận DB pytest không bị động tới | Full suite backend chạy lại ngay sau demo UI: **1004 passed, 5 skipped, 0 failed, 0 errors** |

**Diễn giải số liệu 110/571:** 571 là tổng số cặp (known-publication đã reconcile DOI/title-exact) × (vị trí tác giả trên công bố Scopus tương ứng) được xét qua toàn bộ 48 giảng viên có Craw. Trong đó chỉ 110 (≈19%) có tương quan tên độc lập và được promote thành candidate — phần còn lại (461, ≈81%) là các vị trí tác giả thật nhưng không có bằng chứng gì cho thấy đó là giảng viên ICTU cụ thể nào, nên **đúng thiết kế** là không trở thành candidate.

---

## 5. Kết quả kiểm thử backend

| Hạng mục | Kết quả |
|---|---|
| Full suite (venv `_venv_backend_demo_py312`, DB pytest `scopus_ictu_test_pytest_20261013`) | **1004 passed, 5 skipped, 0 failed, 0 errors** — chạy lại nhiều lần đều sạch |
| Module mới `test_craw_assisted_discovery.py` | 12/12 PASS, bao gồm đủ các ca âm bắt buộc: 5 tác giả/1 khớp, DOI trùng sai người, tên giống hệt, tên viết tắt qua biến thể, 2 giảng viên ICTU cùng bài |
| Module mới `test_matching_api.py` | 17/17 PASS: RBAC (ADMIN-only, 403 cho REVIEWER/LECTURER, 401 ẩn danh), sinh ứng viên idempotent khi chạy 2 lần liên tiếp (không trùng candidate root), ca 5-tác-giả E2E qua API thật, nạp Craw preview→apply→idempotent-rerun→stale-fingerprint-rejected |
| Alembic | 1 head duy nhất `c7f2a9b1d3e5`, không migration mới trong phiên này |
| Frontend build (`tsc --noEmit && vite build`) | PASS, 0 lỗi |
| CI GitHub Actions | **NOT VERIFIED** — không push, không coi test suite xanh cục bộ là bằng chứng CI PASS |

---

## 6. Giới hạn chưa nghiệm thu / chưa triển khai

- **UI nạp Craw/sinh ứng viên chưa test với trình duyệt thật đa phiên** (2 ADMIN bấm đồng thời) — chỉ xác nhận an toàn concurrency qua test tích hợp gọi trực tiếp, chưa qua 2 tab trình duyệt thật cùng lúc.
- **Chưa có E2E cho trường hợp 2 REVIEWER duyệt đồng thời cùng 1 candidate Craw-assisted** — logic concurrency của `CandidateReviewService` không đổi trong Ưu tiên 4 (đã xác nhận qua test cũ từ Ưu tiên trước, không viết lại), nhưng chưa thử nghiệm lại riêng với candidate loại mới này.
- **Không có ground truth cho 110 candidate Craw-assisted mới** — không công bố precision/recall, chỉ báo cáo số lượng và cơ chế lọc.
- **CI GitHub Actions** — không push, không xác nhận.
- **Dữ liệu CSV Scopus mới xuất thật** — giữ nguyên hạng mục chờ từ các Ưu tiên trước, không đổi trong phiên này.

---

## 7. Trả lời 8 câu hỏi kết luận bắt buộc

1. **WITH-JSON có thực sự E2E không?** Có — đã chạy qua trình duyệt thật, đăng nhập ADMIN thật, bấm nút UI thật, xác nhận ghi DB thật và khớp UI 100%, trên dữ liệu 410 giảng viên/660 công bố/Craw thật.
2. **Craw tạo thêm candidate hợp lệ hay chỉ bổ sung bằng chứng?** **Cả hai, tách biệt rõ ràng theo thiết kế mới của phiên này.** Bổ sung bằng chứng cho candidate đã có từ tên (không đổi, hành vi gốc vẫn giữ nguyên). **Tạo thêm candidate mới thật sự** khi có đủ 2 neo (vị trí tác giả + tương quan tên) — đây là điểm khác biệt so với trạng thái "Craw không bao giờ tạo candidate mới" ghi nhận trong báo cáo WITH-JSON gốc 12/10.
3. **Bao nhiêu candidate mới, căn cứ gì?** 110 candidate mới trên dữ liệu thật, căn cứ: known-publication của giảng viên reconcile DOI/title-exact với 1 Publication Scopus thật + Scopus Author ở đúng vị trí tác giả đó có ít nhất 1 token tên trùng (kể cả qua biến thể tên) với giảng viên. 461 vị trí tác giả khác bị loại đúng vì thiếu neo tên.
4. **REVIEWER duyệt+giữ lịch sử được không?** Có — xác nhận bằng DB thật: 3 quyết định REVIEWER cũ (1 REJECTED, 2 ACCEPTED) từ lần nghiệm thu trước **không bị ghi đè** sau khi chạy lại generation trong phiên này.
5. **Nguy cơ gán nhầm lecturer↔Scopus Author?** Giảm đáng kể so với thiết kế ban đầu (chỉ vị trí tác giả) nhờ quy tắc 2 neo, nhưng **vẫn không phải xác nhận danh tính** — token tên trùng chỉ là tương quan yếu, cố ý yếu hơn 4 quy tắc tên nghiêm ngặt. UI đã cảnh báo rõ ràng, REVIEWER vẫn là người quyết định cuối, không có đường tắt tự động APPROVE.
6. **NO-JSON còn nguyên vẹn?** Có — 1004 test full suite PASS bao gồm toàn bộ test NO-JSON cũ, không có test nào liên quan JSON/Craw bị fail.
7. **Còn thiếu gì để demo/bảo vệ?** UI đã chạy thật, số liệu thật, có thể demo trực tiếp luồng ADMIN nạp Craw → sinh ứng viên → REVIEWER thấy badge phân biệt → xem chi tiết bằng chứng. Thiếu: test đa phiên trình duyệt thật, ground truth để nói precision/recall.
8. **Cần thêm migration/quyết định/dữ liệu kiểm chứng không?** Không cần migration. Không cần quyết định mới (toàn bộ quyết định kỹ thuật đã chốt trong báo cáo A, đã tuân thủ tuyệt đối kể cả khi tự sửa lỗi thiết kế). Có thể cần dữ liệu kiểm chứng thủ công (ground truth) nếu luận văn cần công bố precision/recall — hiện không có.

---

## 8. GATE 4 — KẾT LUẬN

**PASS có điều kiện** cho phạm vi đã kiểm thử: luồng JSON+Craw+Matching đã hoàn thiện API/UI, chạy E2E thật trên dữ liệu 410 giảng viên/660 công bố/Craw thật qua trình duyệt, candidate Craw-assisted mới được neo đúng 2 lớp bằng chứng độc lập (không mass-generate), quyết định REVIEWER cũ được bảo toàn, NO-JSON không hồi quy (1004/5/0/0).

**Phát hiện đáng chú ý đã tự sửa trong phiên, không che giấu:**
- Thiết kế candidate Craw-assisted ban đầu có lỗi mass-candidate-generation thật — đã tự phát hiện (nhờ câu hỏi của bạn) và sửa triệt để trước khi tích hợp API/UI.
- Lỗi advisory lock orphaned qua connection pool — lỗi concurrency thật, hiếm gặp, chỉ lộ ra khi chạy test tích hợp 2 lần liên tiếp, đã sửa bằng cách bỏ cơ chế khóa không cần thiết thay vì vá tạm.
- Một lần điều tra sai (`httpx2`) đã tự nhận và revert đúng, không giữ thay đổi sai.

**Không có hạng mục nào trong Gate 4 bị bỏ qua hoặc giả lập.**

**Dừng tại đây, chờ bạn xem báo cáo trước khi chuyển sang chuẩn bị phát hành/luận văn.**
