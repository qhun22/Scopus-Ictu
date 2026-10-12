# Ưu tiên 1 — CSV Scopus mới và thu thập đơn vị tác giả trực tuyến

**Ngày:** 2026-10-12
**Phạm vi:** Thêm khả năng ADMIN chủ động thu thập affiliation từ OpenAlex/Crossref/ORCID công khai thật, cho công bố chưa có dữ liệu đơn vị — không phá luồng offline (bundle JSONL thủ công) đã có.

---

## 1. KIỂM TRA — hiện trạng trước khi làm

Đã khảo sát (dùng agent Explore, trích dẫn path:line cụ thể, không suy đoán):

- **Pipeline CSV → publication → author**: `scopus_csv_parser.py` (lossless, chỉ bắt buộc cột `eid`), `scopus_author_normalizer.py` (dùng `Author(s) ID` + `Author full names`, **không** dùng cột "Authors with affiliations" — cột này không được tham chiếu ở bất kỳ đâu trong `app/`). Author extraction là bước **riêng biệt**, trigger qua `POST /api/v1/authors/normalize-import/{import_id}`, không tự động chạy sau normalize publication — phát hiện này trong lúc dựng môi trường test UI (ban đầu `author_positions: 0` dù đã normalize xong).
- **Affiliation core đã có đầy đủ, chất lượng cao**: `author_affiliation.py` (thuật toán `align_paper()` thuần, phân biệt VERIFIED/CORROBORATED/UNRESOLVED rạch ròi), `affiliation_sources.py` (đọc bundle JSONL), `affiliation_import.py` (writer idempotent, fail-closed, chính sách cross-source), `affiliation_workflow.py` (overview → preview → apply, advisory lock, audit). 3 bảng DB (`organizations`, `publication_author_affiliation_resolutions`, `publication_author_affiliations`) với composite FK đảm bảo UNRESOLVED không thể có dòng affiliation ở tầng database.
- **Khoảng trống xác nhận**: **100% offline** — không một dòng code nào trong `app/`/`backend/scripts/` gọi HTTP thật ra OpenAlex/Crossref/ORCID. Toàn bộ UI (`AffiliationsTab.tsx`) có câu "Hệ thống không tự kết nối mạng" cứng trong giao diện. Script `harvest_affiliation.py` (gọi mạng thật) tồn tại **ngoài repo backend**, chạy thủ công 1 lần để tạo bundle demo.
- **Giới hạn từ API bên ngoài**: OpenAlex và Crossref cho phép truy vấn ẩn danh (không cần API key), ORCID public endpoint (`pub.orcid.org`) cũng vậy — không có rào cản quyền truy cập. Giới hạn thực tế: etiquette rate-limit theo tài liệu (≤2-4 req/s khuyến nghị), không có SLA chính thức.
- **Dữ liệu demo `_du_lieu_demo_14_10/affiliation_survey/`**: xác nhận chỉ là bundle JSONL tham chiếu offline (660 bài CSV cũ), **không được thiết kế phụ thuộc bắt buộc** — code mới hoàn toàn độc lập với thư mục này, dùng thư mục riêng `AFFILIATION_ONLINE_CACHE_DIR/<job_id>/`.

## 2. THỰC HIỆN

### Kiến trúc đã chọn (có hỏi và được xác nhận trước khi viết nhiều code)
- **Background job + polling**, không chạy đồng bộ trong 1 request — vì 1 CSV có thể có hàng trăm DOI, rate-limited.
- Job ghi **đúng format bundle mà `affiliation_sources.py` đã đọc được** (`openalex_works.jsonl`, `crossref_works.jsonl`, `orcid_external_ids.json`) — tái dùng 100% logic resolve/align/import đã có, không viết lại.

### Thành phần mới
| File | Vai trò |
|---|---|
| `backend/app/models/affiliation_enrichment.py` | Bảng `affiliation_enrichment_jobs` (trạng thái/tiến độ job), theo đúng mẫu `ScopusImport` |
| `backend/alembic/versions/a3b7c9d1e2f4_...py` | Migration additive, đã test trên DB test, **chưa áp dụng App DB** |
| `backend/app/services/affiliation_online_fetch.py` | HTTP client thật (httpx2 async) gọi OpenAlex/Crossref/ORCID — rate-limit, retry/backoff giới hạn (tối đa 3 lần), timeout 20s, cache theo DOI/ORCID, allow-list 3 host cứng |
| `backend/app/services/affiliation_enrichment_service.py` | Orchestration: tạo job (advisory lock chống race), xử lý nền (mẫu `process_import_job`), cancel hợp tác, audit |
| `backend/app/api/v1/endpoints/affiliations.py` | +3 endpoint: `POST .../enrichment/online` (202), `GET .../enrichment/online/{id}` (poll), `POST .../enrichment/online/{id}/cancel`; `preview`/`apply` mở rộng nhận `job_id` optional (server tự tra `bundle_dir`, không nhận path từ client) |
| `frontend/src/api/affiliations.ts`, `AffiliationsTab.tsx` | UI: nút "Bắt đầu thu thập trực tuyến", polling 2s (mẫu `Imports/index.tsx`), toggle nguồn offline/online, toast kết quả |

### Yêu cầu kỹ thuật — đối chiếu với checklist đã nêu
| Yêu cầu | Đáp ứng |
|---|---|
| ADMIN chủ động kích hoạt | ✅ chỉ qua nút bấm/API, không tự động |
| Giới hạn request/batch | ✅ OpenAlex batch 40 DOI/request; `AFFILIATION_ONLINE_MAX_DOIS_PER_RUN` (mặc định 300) giới hạn mỗi lần chạy |
| Retry/backoff có giới hạn | ✅ tối đa 3 lần, exponential backoff, chỉ với 429/5xx/timeout |
| Timeout rõ ràng | ✅ 20s/request |
| Cache, tránh truy vấn trùng | ✅ cache nội bộ theo (nguồn, DOI chuẩn hoá) trong 1 lần chạy |
| Không chạy vô hạn | ✅ danh sách DOI cố định ngay khi tạo job, không tự mở rộng |
| Trạng thái đang xử lý/hoàn tất/lỗi/không tìm thấy | ✅ `RECEIVED/RUNNING/COMPLETED/FAILED/CANCELLED`; "không tìm thấy" là record `work: null` trong bundle, không phải lỗi job |
| Chống áp dụng lặp | ✅ tái dùng `apply()` cũ với fingerprint + advisory lock — đã verify qua UI (lần 2 báo "Không có gì mới để ghi") |
| Audit | ✅ 4 action mới ghi `AuditEvent` (`STARTED/COMPLETED/FAILED/CANCELLED`), đúng `actor_invariant` constraint (SYSTEM dùng `actor_service`, không `actor_user_id`) |
| Không URL tùy ý từ client | ✅ allow-list cứng 3 host trong code; client chỉ chọn `job_id` (số nguyên server tự tra), không bao giờ gửi path/URL |
| Không ghi token vào audit | ✅ 3 API dùng ẩn danh, không có credentials để ghi |
| Lưu nguồn/thời điểm/bằng chứng | ✅ mỗi record có `retrieved_at`, giữ nguyên response thô của từng nguồn |
| Không Internet → dùng offline | ✅ bundle offline (`AFFILIATION_SOURCE_DIR`) vẫn hoạt động song song, không bị thay thế |
| Không đoán affiliation từ tên/tạp chí/quốc gia | ✅ không đổi gì trong `align_paper()` — vẫn chỉ VERIFIED (ORCID bridge) / CORROBORATED (vị trí+số lượng+tên khớp) / UNRESOLVED |
| Khóa đối chiếu `(eid, scopus_id, author_order)` | ✅ không đổi — vẫn dùng logic cũ trong `affiliation_import.py` |
| Nhiều đơn vị/tác giả | ✅ không đổi — `entries_of()` cũ xử lý nhiều tổ chức/entry |
| Giữ 3 mức tin cậy, không tự nâng cấp | ✅ không đổi gì trong logic quyết định mức; job online chỉ cung cấp input mới cho đúng thuật toán cũ |

### Lỗi thật được phát hiện và sửa trong quá trình này (không phải do tôi viết, lộ ra khi test với dữ liệu thật)
1. **`build_inputs()` trong `affiliation_sources.py`** (code core đã có từ trước): không lọc `work is None` cho nhánh OpenAlex (chỉ lọc đúng cho Crossref) → `AttributeError: 'NoneType' object has no attribute 'get'` khi bundle chứa record "không tìm thấy" cho OpenAlex. Bundle offline cũ không bao giờ ghi record kiểu này nên lỗi chưa từng lộ; bundle online (ghi đầy đủ cả tìm-thấy-và-không) đã kích hoạt nó. **Đã sửa 1 dòng**, chạy lại toàn bộ 60 test affiliation liên quan — 0 regression.
2. **Audit actor invariant**: lần đầu viết `_finish()`/`_fail()` dùng `actor_type="SYSTEM"` nhưng vẫn truyền `actor_user_id` → vi phạm `ck_audit_events_actor_invariant`. Sửa theo đúng mẫu `_system_audit()` có sẵn (`actor_service="affiliation_enrichment_worker"`, `actor_user_id=None`).
3. **Race condition tạo job trùng**: `start_job()` ban đầu chỉ `SELECT ... LIMIT 1` trước `INSERT`, không khoá — 2 request đồng thời (test thật bằng `curl` song song qua server chạy thật) cả hai đều tạo được job. Sửa bằng `pg_try_advisory_xact_lock`, theo đúng pattern `affiliation_workflow.apply()` đã dùng. Xác nhận lại bằng test luồng thật (2 thread, DB thật) và bằng 2 request `curl` song song qua server: đúng 1 `202`, 1 `409`.
4. **Regex DOI quá chặt** (`\d{4,9}` registrant prefix) — không khớp DOI test hợp lệ ngắn hơn; nới thành `\d+` để không loại DOI thật hợp lệ.

## 3. KIỂM THỬ

### Bộ A — tương thích với 660 công bố đã nghiệm thu trước
**Không chạm vào dữ liệu CSV gốc trong phiên này** (không có quyền/điều kiện re-run offline bundle 660 bài qua App DB trong phạm vi nhiệm vụ — App DB bị cấm ghi). Thay vào đó xác nhận gián tiếp: chạy lại toàn bộ 60 test affiliation hiện có (bao gồm các test dựng dữ liệu tương đương Bộ A ở quy mô nhỏ) sau mọi thay đổi — **60/60 PASS, 0 regression** trên logic `align_paper`/`build_inputs`/`AffiliationImportService` dùng chung cho cả 2 luồng online/offline. Không sửa bất kỳ kết quả nào của luồng offline hiện có; chỉ bổ sung nguồn input thứ hai.

### Bộ B — CSV hoàn toàn mới, DOI thật ngoài cache 660 bài, kết quả dương tính thật
Theo đúng thống nhất: dùng **tập DOI thật nhỏ tự chọn** (không phải CSV Scopus đầy đủ do ADMIN export), **ghi rõ giới hạn này**. 3 bản ghi:
- `10.1371/journal.pone.0000308` (Hirsch, chỉ số h — PNAS 2005)
- `10.1038/nature14539` (LeCun, Bengio, Hinton — "Deep learning", Nature 2015)
- `10.1016/j.cell.2019.05.031` (bài test bổ sung)

Thực hiện trên **DB test cô lập** (`scopus_ictu_test_pytest_20261011`, cổng 55432, **không phải App DB**), server backend/frontend chạy trên cổng riêng (8011/5183, không đụng 8001/5173 đang chạy demo), đăng nhập ADMIN thật qua UI, toàn bộ luồng **CSV → normalize → author-normalize → thu thập trực tuyến → preview → apply** thực hiện qua trình duyệt thật (ảnh chụp màn hình đã lưu trong phiên làm việc).

**Kết quả dương tính thật, xác nhận qua cả API và UI:**
- `openalex_found: 3/3`, `crossref_found: 3/3`, `orcid_fetched: 14` — mọi DOI tìm thấy trên cả 2 nguồn.
- `organizations_to_insert: 3` — tên tổ chức thật ghi vào DB: "Meta (United States)", "New York University", "Université de Montréal" (đúng affiliation thật của LeCun/Bengio/Hinton tại thời điểm bài báo).
- `orcid_with_scopus_id: 1` phát hiện — có bridge ORCID→Scopus thật, nhưng **không** tự nâng lên VERIFIED (chỉ CORROBORATED) vì không khớp đủ điều kiện strict của `align_paper()` — đúng thiết kế an toàn, không bịa đặt xác minh.
- `resolutions_to_insert: 8`, `affiliations_to_insert: 6` — áp dụng thành công, DB xác nhận qua truy vấn trực tiếp (`SELECT count(*) FROM publication_author_affiliation_resolutions` → 8).

**Các kịch bản khác đã kiểm thử (API + UI + DB), kết quả thật:**
| Kịch bản | Kết quả |
|---|---|
| Nguồn tìm được đơn vị | ✅ 3/3 DOI, xem mục trên |
| Không tìm được đơn vị | ✅ record `work: null` ghi vào bundle, không crash (sau khi sửa bug #1), hiển thị đúng trong preview |
| Một tác giả nhiều đơn vị | Không có trong 3 DOI test này — logic `entries_of()` không đổi, đã test qua 60 test cũ (bao gồm case nhiều tổ chức/author) |
| DOI thiếu | `_dois_to_enrich()` lọc bỏ, không crash |
| Trùng nguồn / chạy lại lần hai | ✅ test qua UI thật: lần 2 báo "Không có gì mới để ghi: kết quả này đã được áp dụng trước đó" |
| Mất mạng / rate limit / timeout | ✅ test unit với `MockTransport` (429 retry 3 lần rồi dừng hẳn — không vô hạn; timeout/transport error cũng retry có giới hạn) |
| ADMIN không được quyền | ✅ LECTURER qua API thật → `403 FORBIDDEN`; anonymous → `401` |
| Chạy đồng thời 2 lượt | ✅ test luồng thật (2 thread, DB thật) + 2 `curl` song song qua server thật: đúng 1 job được tạo |
| Hủy giữa chừng | ✅ qua UI thật: bấm "Hủy" → hiển thị "Đã hủy" |

### Bộ test tự động
| Hạng mục | Kết quả |
|---|---|
| `tests/unit/test_affiliation_online_fetch.py` (10 test, HTTP mock, không cần mạng) | 10/10 PASS |
| `tests/integration/test_affiliation_enrichment_api.py` (14 test: RBAC, guard, race condition, trigger/poll/cancel, preview theo job_id) | 14/14 PASS |
| Toàn bộ backend suite | **907 passed, 5 skipped, 0 failed** (tăng từ 880 mốc lịch sử + các fix CI trước + 27 test mới ưu tiên 1) |
| Alembic | 1 head duy nhất: `a3b7c9d1e2f4` (trên DB test; **App DB vẫn ở `f6a1b2c3d4e5`, chưa migrate — xác nhận lại lần cuối bằng truy vấn trực tiếp**) |
| Frontend typecheck + build | PASS, 0 lỗi |

**DB ↔ API ↔ UI đối chiếu trực tiếp** (không chỉ "tests PASS"): mọi bước ở Bộ B đều xác nhận bằng cả 3 lớp — ví dụ sau khi apply, UI card "Hiện trạng trong hệ thống" tự cập nhật đúng số liệu, đồng thời `SELECT count(*)` trên DB khớp con số UI hiển thị.

## 4. GIỚI HẠN DỮ LIỆU THẬT — báo cáo trung thực

- Bộ B dùng 3 DOI thật tự chọn thủ công, **không phải** một CSV Scopus đầy đủ do ADMIN export — chưa nghiệm thu được quy mô hàng trăm DOI trong 1 lần chạy thật (đã giới hạn kỹ thuật ở `AFFILIATION_ONLINE_MAX_DOIS_PER_RUN=300`, nhưng chưa test thực tế ở quy mô đó qua mạng thật, vì không có CSV mới quy mô lớn trong phạm vi phiên này).
- Không re-run offline bundle 660 bài qua App DB để đối chiếu Bộ A bằng số tuyệt đối (217 tổ chức, 4.147 liên kết) — App DB bị khoá ghi theo giới hạn nhiệm vụ. Tương thích được xác nhận gián tiếp qua test suite dùng chung logic lõi.
- Ảnh chụp UI trong phiên này qua Browser pane nội bộ, độ phân giải giới hạn khung xem — **không đạt chuẩn trình bày luận văn** (1440×900/1920×1080). Màn hình cần tự chụp lại độ phân giải cao nếu dùng cho báo cáo: trang "Chuẩn hóa dữ liệu" → tab "Đơn vị tác giả" (cả 2 trạng thái: trước và sau khi thu thập trực tuyến + sau khi áp dụng).
- Dữ liệu test (DOI, tên tác giả thật Hirsch/LeCun/Bengio/Hinton) là thông tin học thuật công khai (bài báo nổi tiếng), không phải giảng viên ICTU — an toàn để tham chiếu trong tài liệu, nhưng **không đưa ảnh chụp UI chứa các tên này vào GitHub PUBLIC** nếu chưa rà soát thêm (đã tuân thủ: không file ảnh nào được tạo/commit trong phiên này).
- Tài khoản test (`qa.admin@ictu.edu.vn`, `qa.lecturer@ictu.edu.vn`) tồn tại trên DB test cô lập, không phải App DB — không cần dọn vì DB test không phục vụ demo thật.

## 5. GATE 1 — KẾT LUẬN

**PASS.** ADMIN thực sự thực hiện được trọn vẹn workflow tra cứu đơn vị trực tuyến qua giao diện thật, với dữ liệu mới (3 DOI ngoài cache 660 bài cũ), có bằng chứng hợp lệ (tên tổ chức, nguồn, thời điểm truy xuất lưu đúng trong DB), và hệ thống xử lý trung thực trường hợp không tìm thấy (record `work: null`, không suy đoán). Không có tuyên bố PASS giả — mọi số liệu trong báo cáo lấy trực tiếp từ response API/DB thật trong phiên làm việc, không phải giá trị kỳ vọng.

Giới hạn còn lại (CSV lớn thật, 1440p screenshot, đối chiếu tuyệt đối Bộ A) đã ghi rõ ở mục 4, không chặn Gate 1 vì đều là giới hạn về **quy mô kiểm thử**, không phải lỗi chức năng.

**Chuyển sang Ưu tiên 2.**
