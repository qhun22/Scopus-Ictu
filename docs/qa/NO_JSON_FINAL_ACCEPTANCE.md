# Khép kín luồng NO-JSON — Nghiệm thu cuối cùng

**Ngày:** 2026-10-13
**Phạm vi:** Giải quyết 2 vấn đề tồn đọng từ Ưu tiên 2/3 — (A) điều tra dứt điểm hiện tượng mất/lạ dữ liệu trong DB test, (B) cho phép một tác giả có nhiều đơn vị hiệu chỉnh độc lập — và chứng minh lại toàn bộ luồng ADMIN↔LECTURER không cần JSON giảng viên trên môi trường hoàn toàn mới, cách ly khỏi DB chạy pytest.

---

## 1. KẾT QUẢ ĐIỀU TRA DB

### Nguyên nhân thật của hiện tượng "3 giảng viên mẫu lạ" và "mất dữ liệu users/publication_authors"

**Có bằng chứng dứt khoát, không phải suy đoán.** Trong DB test `scopus_ictu_test_p3_20261013` (dùng cho Ưu tiên 3), phát hiện 3 lecturer "Nguyen Van A", "Nguyen Van B", "Tran Thi C" — cùng `created_at` chính xác tới mili-giây, không có `AuditEvent` nào tương ứng (0 audit event cho `entity_type='lecturers'`). Grep toàn bộ test suite tìm ra khớp chính xác: [`backend/tests/integration/test_review_shared_author_warning.py:67-72`](backend/tests/integration/test_review_shared_author_warning.py) — fixture `seeded` tạo đúng 3 lecturer này.

Cơ chế: fixture dùng `isolated_db_engine` — **không phải** schema UUID riêng như phần lớn test khác, mà kết nối **trực tiếp vào schema `public`** của bất kỳ database nào `TEST_DATABASE_URL` trỏ tới, rồi `TRUNCATE {table} CASCADE` trên một danh sách bảng cố định (bao gồm `lecturers`, `scopus_authors`...) trước khi seed, và **không có teardown nào dọn lại sau test**.

Grep sâu hơn tìm thấy bằng chứng còn nặng hơn: [`backend/tests/integration/test_candidate_review_service.py:94-113`](backend/tests/integration/test_candidate_review_service.py) — cùng cơ chế `isolated_db_engine`, nhưng danh sách `TRUNCATE ... CASCADE` **chứa trực tiếp bảng `User`** (bảng `users`), với comment nguyên văn: *"Use TRUNCATE ... CASCADE to safely handle cross-table FK references"*.

**Kết luận: nguyên nhân gốc rễ của cả hai hiện tượng (users/publication_authors "biến mất" trong Ưu tiên 2, và 3 lecturer mẫu "xuất hiện" trong Ưu tiên 3) là MỘT và CÙNG MỘT nguồn — một hoặc nhiều lần chạy `pytest` với `TEST_DATABASE_URL` vô tình trỏ vào đúng database đang dùng cho kiểm thử UI thủ công.** `TRUNCATE ... CASCADE` trong PostgreSQL xóa cả các bảng phụ thuộc bất kể chính sách `ON DELETE`, nên dù `publication_authors.scopus_author_id` dùng `ondelete="RESTRICT"`, một lệnh `TRUNCATE lecturers CASCADE`/`TRUNCATE users CASCADE` vẫn xóa sạch dữ liệu liên quan. `publications` sống sót vì không bảng `TRUNCATE` nào trong 4 file đã kiểm tra (`test_review_shared_author_warning.py`, `test_candidate_review_service.py`, `test_generate_matching_candidates_cli.py`, `test_ingest_craw_known_publications_cli.py`) liệt kê `publications`.

Đây **không phải** PostgreSQL tự làm mất dữ liệu, và **không phải** bug trong code sản phẩm — là rủi ro vận hành: `isolated_db_engine`/`ISOLATION_ENGINE` (định nghĩa tại `backend/tests/conftest.py:63-71,97-100`) không tự tạo schema cô lập, chỉ dùng thẳng URL được cấu hình, nên bất kỳ ai chạy pytest full suite trỏ vào một DB đang có dữ liệu UI thủ công sẽ làm mất dữ liệu đó. Không sửa `conftest.py`/các fixture TRUNCATE trong nhiệm vụ này (ngoài phạm vi yêu cầu, rủi ro phá vỡ các test đang PASS) — thay vào đó giải quyết bằng quy trình vận hành (mục dưới).

### Biện pháp đã áp dụng: cách ly tuyệt đối 2 database

| Mục đích | Database | Cổng | Ghi chú |
|---|---|---|---|
| Chạy `pytest` (unit + integration) | `scopus_ictu_test_pytest_20261013` | 55432 | **Không bao giờ** dùng cho UI/E2E thủ công |
| E2E UI thủ công (Phiên A/B) | `scopus_ictu_nojson_test_20261013` | 55432 | **Không bao giờ** chạy `pytest` trỏ vào đây |

Hai database này được tạo mới hoàn toàn trong nhiệm vụ này, độc lập với mọi DB test trước đó (`scopus_ictu_test_p3_20261013` của Ưu tiên 3 không bị động tới và không được tái sử dụng).

### Chứng minh dữ liệu đã commit còn nguyên sau backend restart

Trên DB E2E (`scopus_ictu_nojson_test_20261013`), chụp nhanh dữ liệu trước/sau khi dừng và khởi động lại tiến trình backend (`uvicorn`, cổng 8013 — **tiến trình test riêng, không phải demo 8001**):

| Chỉ số | Trước restart | Sau restart |
|---|---|---|
| `publications` | 4 | 4 |
| `users` | 2 | 2 |
| `lecturers` | 0 | 0 |
| Override "New York University" | REVOKED, version 2 | REVOKED, version 2 |
| Override "Meta AI Research (FAIR) - ADMIN A edit" | ACTIVE, version 2 | ACTIVE, version 2 |

Khớp tuyệt đối trước/sau — xác nhận lại qua cả truy vấn DB trực tiếp lẫn tải lại trang chi tiết công bố qua UI thật (nội dung override hiển thị đúng nguyên văn sau restart).

## 2. THAY ĐỔI SCHEMA / API / UI — hỗ trợ nhiều đơn vị độc lập

### Schema (migration `c7f2a9b1d3e5`, trên DB test, chưa chạm App DB/teacher DB)

Thiết kế tối thiểu, additive, không sửa bảng nào khác ngoài `publication_author_affiliation_overrides`:
- Xóa `UniqueConstraint("publication_author_id")` cũ (ép 1-override-per-position).
- Thêm cột `status` (`ACTIVE`/`REVOKED`, mặc định `ACTIVE`), `revoked_at`, `revoked_by_user_id`.
- Thêm CHECK `revoked_state_consistent`: `REVOKED` bắt buộc có `revoked_at`+`revoked_by_user_id`; `ACTIVE` bắt buộc cả hai là NULL — chặn trạng thái nửa vời ở tầng DB.
- Thêm **partial unique index** `uq_paao_active_position_text` trên `(publication_author_id, affiliation_text) WHERE status='ACTIVE'` — chống trùng đơn vị đang hoạt động cho cùng 1 vị trí, nhưng cho phép thu hồi rồi thêm lại đúng tên đó.
- Index đồng thời được khai báo trong model SQLAlchemy (`Index(..., postgresql_where=...)`) để `Base.metadata.create_all()` (dùng bởi schema test cô lập UUID) tạo đúng cùng một ràng buộc mà không cần chạy Alembic — phát hiện qua 1 test fail thật (`test_duplicate_active_text_on_same_position_is_rejected`), đã sửa và xác nhận lại PASS.

### Service (`affiliation_override_service.py`) — 3 thao tác tách biệt hoàn toàn

- `add_override()` — luôn **tạo dòng mới**, không đụng dòng nào khác trên cùng vị trí. Đây là cách biểu đạt "tác giả này cũng thuộc tổ chức khác" (kiêm nhiệm), phân biệt rõ với sửa/thu hồi.
- `update_override(override_id, ...)` — sửa **đúng một dòng** theo ID riêng của nó (không còn theo `publication_author_id` như thiết kế cũ), optimistic lock bằng `version`.
- `revoke_override(override_id, ...)` — chuyển `status='REVOKED'`, ghi `revoked_at`/`revoked_by_user_id`, **giữ nguyên dòng** (không xóa) để lịch sử kiểm toán còn truy vấn được. Yêu cầu `reason` bắt buộc.
- Tất cả thao tác dùng `SELECT ... FOR UPDATE` + kiểm tra `version` tường minh — cùng pattern 2-ADMIN-đồng-thời đã kiểm chứng ở Ưu tiên 2, viết lại test cho đúng cấu trúc ID mới.

### API (`affiliations.py`)

| Trước | Sau |
|---|---|
| `PUT /overrides/{publication_author_id}` (upsert 1 dòng) | `POST /overrides` (thêm mới, body có `publication_author_id`) |
| `DELETE /overrides/{publication_author_id}?expected_version=N` | `PUT /overrides/{override_id}` (sửa theo ID riêng) |
| — | `POST /overrides/{override_id}/revoke` (thu hồi, `reason` bắt buộc) |
| `GET /needs-review` trả `override: OverrideRead \| null` | `GET /needs-review` trả `overrides: OverrideRead[]` (đầy đủ active+revoked) |

### UI ADMIN (`ManualReviewCard.tsx`)

Mỗi vị trí tác giả hiển thị **danh sách** đơn vị (không còn 1 ô), mỗi dòng có badge "Đang hoạt động"/"Đã thu hồi" và nút Sửa/Thu hồi riêng; nút "Thêm đơn vị" riêng để bổ sung đơn vị mới mà không ảnh hưởng các đơn vị đã có. Không dùng một ô văn bản chứa nhiều tên tổ chức — mỗi đơn vị là một bản ghi độc lập với nguồn/lý do/lịch sử riêng.

### UI LECTURER (`AuthorAffiliations.tsx`)

`author.affiliation_overrides` (list, chỉ gồm override **ACTIVE**) được lặp qua và hiển thị từng box "ADMIN rà soát thủ công" riêng — LECTURER thấy đầy đủ mọi đơn vị đang hiệu lực, không thấy đơn vị đã thu hồi (lịch sử thu hồi chỉ ADMIN truy cập qua `/needs-review`), không lộ ID nội bộ/actor.

## 3. BẰNG CHỨNG MỘT TÁC GIẢ CÓ NHIỀU ĐƠN VỊ (DB → API → UI)

Thực hiện qua UI thật trên tác giả **LeCun, Y. (Scopus ID 7004754506)**, bài "Deep learning":

1. Thêm đơn vị 1: "New York University" (nguồn `https://cs.nyu.edu/~yann/`) → UI hiện "1 đơn vị đang hoạt động".
2. Thêm đơn vị 2: "Meta AI Research (FAIR)" (nguồn `https://ai.meta.com/people/yann-lecun/`, lý do kiêm nhiệm) → UI hiện "2 đơn vị đang hoạt động", cả 2 hiển thị song song với nút Sửa/Thu hồi riêng.
3. Thu hồi "New York University" (lý do "Vị trí tại NYU đã kết thúc") → UI hiện "1 đơn vị đang hoạt động"; dòng NYU chuyển badge "Đã thu hồi", mất nút thao tác nhưng **vẫn hiển thị đầy đủ nguồn/lý do cũ**.
4. **DB xác nhận** (`publication_author_affiliation_overrides`):
   ```
   affiliation_text          | status  | version
   New York University       | REVOKED | 2
   Meta AI Research (FAIR)   | ACTIVE  | 1 (sau đó 2, sau khi test 2-ADMIN)
   ```
5. **Audit trail xác nhận** (`audit_events`, `entity_type='publication_author_affiliation_override'`): 2× `AFFILIATION_OVERRIDE_CREATED` (before=null) + 1× `AFFILIATION_OVERRIDE_REVOKED` (before `status:ACTIVE` → after `status:REVOKED`) — đúng 3 dòng, đúng trước/sau.
6. **LECTURER xem qua UI** (`/publications/2-s2.0-NJTEST0002`): chỉ thấy "Meta AI Research (FAIR)" (đơn vị đang hoạt động) — **không thấy** NYU đã thu hồi, đúng thiết kế public-safe "đang có hiệu lực".
7. **Sửa độc lập không ảnh hưởng đơn vị khác**: test tự động (`test_editing_one_override_never_touches_a_sibling_override`, `test_revoking_one_override_never_touches_a_sibling_override`) và xác nhận thủ công qua UI — sửa/thu hồi 1 đơn vị, đơn vị còn lại giữ nguyên `version`.

## 4. KẾT QUẢ KIỂM THỬ KỸ THUẬT

| Hạng mục | Kết quả |
|---|---|
| Migration `c7f2a9b1d3e5` trên DB test sạch | PASS, đạt head mới |
| Backend unit + integration (DB pytest riêng, `scopus_ictu_test_pytest_20261013`) | **946 passed, 5 skipped, 0 failed** |
| Test override mới (`test_affiliation_override_api.py`, viết lại hoàn toàn cho API multi-override) | **27/27 PASS** |
| Frontend build (`tsc --noEmit && vite build`) | PASS, 0 lỗi, nhiều lần build lại trong quá trình sửa |
| RBAC qua API thật | LECTURER: 403 trên `imports/scopus`, `needs-review`, `overrides` (POST), `users` (GET/POST) |
| 2 ADMIN đồng thời | Qua API thật: ADMIN A commit trước (version 1→2 thành công), ADMIN B gửi cùng `expected_version=1` sau đó → `409 STALE_OVERRIDE_VERSION`, dữ liệu A không bị ghi đè |
| Dữ liệu trước/sau backend restart | Khớp tuyệt đối (mục 1) |
| Tái thu thập affiliation không làm mất hiệu chỉnh | Chạy lại "Bắt đầu thu thập trực tuyến" sau khi đã có 2 override → áp dụng lại bị từ chối đúng (`NOTHING_TO_APPLY`, idempotent theo payload hash) → **version override không đổi** (2 → vẫn 2) |
| `lecturers = 0` trong chế độ NO-JSON | Xác nhận đầu nhiệm vụ (0) và cuối nhiệm vụ (vẫn 0), kể cả sau khi tạo 2 user LECTURER/ADMIN với `lecturer_id IS NULL` |

### 5 kịch bản bắt buộc — đối chiếu DB → API → UI

| # | Kịch bản | Bài/tác giả | DB | API | UI |
|---|---|---|---|---|---|
| 1 | Một tác giả, một đơn vị | Hirsch, J.E. (2-s2.0-NJTEST0001) | 2 resolution CORROBORATED (crossref+openalex), cùng tổ chức UCSD | `affiliation_status=CORROBORATED`, `affiliations[]` có 2 mục | Hiển thị đúng đơn vị + nguồn + tổ chức chuẩn hóa |
| 2 | Một tác giả, hai đơn vị | LeCun, Y. (2-s2.0-NJTEST0002) | 2 override ACTIVE | `affiliation_overrides: [Meta, NYU]` | "2 đơn vị đang hoạt động", 2 box riêng |
| 3 | Tác giả chưa xác định đơn vị | Smith, J.A. (2-s2.0-NJTEST0003) | 0 affiliation, resolution UNRESOLVED (NO_EXTERNAL_WORK) | `affiliation_status=UNRESOLVED` | "Chưa xác định được đơn vị" |
| 4 | Đơn vị tự động + ADMIN bổ sung | Hirsch (tự động) vs LeCun (ADMIN) trên cùng đợt dữ liệu | Resolution tự động và override ADMIN ở 2 bảng tách biệt | 2 field riêng (`affiliations` vs `affiliation_overrides`) | Box tím "ADMIN rà soát thủ công" tách biệt rõ với dòng nguồn tự động |
| 5 | Một đơn vị đã thu hồi, còn lịch sử | NYU trên LeCun | `status=REVOKED`, `revoked_at`/`revoked_by_user_id` có giá trị | `/needs-review` (ADMIN) trả về đủ cả REVOKED | UI ADMIN hiện "Đã thu hồi" + nguồn/lý do cũ; UI LECTURER không hiện |

## 5. KẾT QUẢ E2E ADMIN → LECTURER (DB `scopus_ictu_nojson_test_20261013`, 0 JSON giảng viên)

### Phiên ADMIN
1. Đăng nhập `e2e.admin@ictu.edu.vn` (bootstrap qua `scripts/bootstrap_demo_admin.py --apply`, dry-run xác nhận trước) — OK.
2. Nhập CSV Scopus 4 bài (Hirsch, LeCun/Bengio/Hinton, Smith, Knuth) qua API thật (cookie session ADMIN) — 202 RECEIVED, 4/4 bản ghi.
3. Chuẩn hóa (tab "Công bố") + bóc tách tác giả (tab "Tác giả") qua UI — 6 tác giả Scopus, **0 lỗi dữ liệu** (so với Ưu tiên 3 từng có 1 lỗi do CSV sai định dạng — lần này đúng ngay từ đầu).
4. Đối chiếu đơn vị trực tuyến (OpenAlex/Crossref/ORCID thật) — job COMPLETED 4/4, áp dụng 12 resolution + 3 affiliation.
5. Bổ sung 2 đơn vị có bằng chứng cho LeCun (mục 3).
6. Xem lịch sử — audit trail đầy đủ (mục 3), truy vết qua DB trực tiếp và `needs-review`.
7. Tạo tài khoản LECTURER độc lập (`lecturer.nojson@ictu.edu.vn`, `lecturer_id=NULL`) qua trang `/users`.

### Phiên LECTURER
1. Đăng nhập `lecturer.nojson@ictu.edu.vn` — OK, trang chủ hiển thị đúng vai trò, "Hồ sơ của tôi: Chưa có dữ liệu".
2. Tìm bài theo DOI (`10.1038/nature14539`) — đúng 1 kết quả. Tìm theo tên tác giả ("hinton") — đúng 1 kết quả.
3. Xem chi tiết "Deep learning" — đúng 3 tác giả, đúng thứ tự (LeCun, Bengio, Hinton).
4. Xem đầy đủ đơn vị của LeCun — chỉ thấy "Meta AI Research (FAIR)" (ACTIVE), không thấy NYU (REVOKED).
5. Xem rõ nguồn và mức xác minh — ghi rõ "Đã đối chiếu · Chưa xác minh", URL nguồn, lý do, dòng cố định "not an independent identity verification. Never counted as VERIFIED."
6. Không thực hiện được chức năng quản trị — xác nhận qua API thật: `imports/scopus`, `needs-review`, `overrides` (POST), `users` (GET/POST) đều 403.

## 6. TRẠNG THÁI `lecturers = 0`

| Thời điểm | `lecturers` | `users` | Ghi chú |
|---|---|---|---|
| Ngay sau migrate DB E2E mới | 0 | 0 | DB vừa tạo |
| Sau bootstrap ADMIN | 0 | 1 | ADMIN `lecturer_id=NULL` |
| Sau nhập CSV + chuẩn hóa + bóc tách tác giả | 0 | 1 | Bóc tách chỉ tạo `scopus_authors`, không tạo `lecturers` |
| Sau tạo tài khoản LECTURER | 0 | 2 | LECTURER `lecturer_id=NULL` |
| Cuối nhiệm vụ (sau mọi thao tác ADMIN/LECTURER, kể cả backend restart) | **0** | 2 | Không có bước nào trong toàn bộ luồng tạo hồ sơ giảng viên |

Không có JSON giảng viên nào được import, không có Craw nào được nạp, không có ứng viên matching nào được sinh — xác nhận bằng cách không gọi bất kỳ endpoint/CLI nào thuộc các luồng đó trong suốt nhiệm vụ, và bảng `lecturers`/`lecturer_scopus_candidates` xác nhận trống qua truy vấn DB trực tiếp ở cả đầu và cuối.

## 7. CÁC LỖI ĐÃ SỬA

1. **Partial unique index không được tạo trên schema test cô lập**: `uq_paao_active_position_text` chỉ tồn tại qua Alembic (raw SQL), nhưng `Base.metadata.create_all()` (dùng bởi fixture test schema UUID riêng) không chạy Alembic nên không tạo index này — phát hiện qua 1 test fail thật (`test_duplicate_active_text_on_same_position_is_rejected`: 201 thay vì 409 mong đợi). Sửa bằng cách khai báo `Index(..., postgresql_where=...)` trực tiếp trong `__table_args__` của model, để cả 2 đường tạo schema (Alembic và `create_all()`) đều enforce đúng cùng một ràng buộc.
2. **CSV test thiếu cột `Author full names`/`Author(s) ID`** (lặp lại kinh nghiệm Ưu tiên 3): lần này viết đúng định dạng Scopus thật ngay từ đầu, 0 lỗi `AUTHOR_LIST_LENGTH_MISMATCH`.
3. (Tái xác nhận, không phải lỗi mới) UI polling trạng thái job thu thập trực tuyến không tự khôi phục sau khi reload trang (job vẫn COMPLETED trong DB, nhưng UI hiển thị lại nút "Bắt đầu" thay vì trạng thái đã hoàn tất) — đã dùng API trực tiếp để Preview/Apply bằng `job_id` đã biết, không chặn chức năng nhưng là một UX gap nên ghi nhận.

## 8. GIỚI HẠN CÒN TỒN TẠI

- **E2E với CSV Scopus mới xuất thật (660 bài hoặc tương đương)**: nhiệm vụ này tiếp tục dùng CSV tối thiểu tự xây dựng (4 bản ghi, DOI thật chọn tay) để kiểm tra đủ 5 kịch bản bắt buộc trong thời gian hợp lý. **Chưa chạy được E2E đầy đủ với một CSV Scopus 660 bài xuất thật** — đây vẫn là hạng mục chưa nghiệm thu, không tự tuyên bố PASS toàn phần cho quy mô dữ liệu thật.
- **UI polling job thu thập trực tuyến không khôi phục sau reload** (mục 7.3) — chức năng vẫn đúng qua API/DB, nhưng trải nghiệm ADMIN khi vô tình reload trang giữa lúc job đang chạy chưa mượt.
- **`conftest.py`/các fixture `TRUNCATE ... CASCADE` dùng schema `public` chung** (nguyên nhân gốc mục 1) — **không sửa** trong nhiệm vụ này vì ngoài phạm vi yêu cầu và có rủi ro phá vỡ nhiều test đang PASS; giải pháp áp dụng là quy trình vận hành (2 DB tách biệt tuyệt đối), không phải sửa code test.
- **Phiên hết hạn qua UI thật**: không test trực tiếp trong nhiệm vụ này (đã xác nhận gián tiếp qua `auth_version`/test tự động có sẵn ở Ưu tiên 3).

## 9. KẾT LUẬN: PASS CÓ ĐIỀU KIỆN

Đạt đầy đủ mục tiêu chính: ADMIN xử lý được dữ liệu Scopus (nhập → chuẩn hóa → bóc tách → đối chiếu tự động/trực tuyến → hiệu chỉnh thủ công nhiều đơn vị độc lập có bằng chứng/lý do/lịch sử) và LECTURER xem đầy đủ số tác giả, danh sách tác giả, và **tất cả** đơn vị đang hiệu lực của từng người — toàn bộ **không cần nhập JSON giảng viên ICTU** (`lecturers = 0` xuyên suốt, xác nhận đầu-cuối).

Nguyên nhân gốc của hiện tượng dữ liệu bất thường trong các DB test trước đây đã được xác định có bằng chứng cụ thể (không phải PostgreSQL tự làm mất dữ liệu), và đã áp dụng biện pháp cách ly triệt để cho môi trường E2E lần này. Thiết kế nhiều-đơn-vị-độc-lập đã triển khai đúng yêu cầu: thêm/sửa/thu hồi từng đơn vị riêng biệt, chống trùng, phân biệt rõ bổ sung/thay thế/bác bỏ, giữ nguyên Scopus raw và bằng chứng tự động, không tự nâng VERIFIED, không bị tái thu thập ghi đè, có kiểm soát đồng thời.

**Điều kiện (chưa PASS toàn phần)**: hạng mục E2E với CSV Scopus mới xuất thật quy mô lớn (660 bài) chưa thực hiện trong nhiệm vụ này.

## 10. NGƯỜI DÙNG TỰ KIỂM TRA BẰNG TRÌNH DUYỆT (khuyến nghị)

1. Mở `/normalization` (tab "Đơn vị tác giả"), kiểm tra lại bằng mắt danh sách "2 đơn vị đang hoạt động" của LeCun và trạng thái "Đã thu hồi" của NYU trên DB E2E (`scopus_ictu_nojson_test_20261013`, nếu còn giữ) hoặc dựng lại tương tự trên DB khác.
2. Reload trang `/normalization` ngay sau khi bấm "Bắt đầu thu thập trực tuyến" để tự quan sát UX gap đã ghi ở mục 7.3 (job vẫn chạy đúng trong DB, chỉ UI hiển thị lại nút ban đầu).
3. Thử 2 cửa sổ trình duyệt ADMIN khác nhau sửa cùng 1 đơn vị gần như đồng thời, để xác nhận trực quan thông báo "Dữ liệu đã bị người khác thay đổi" (đã xác nhận qua API, chưa quan sát qua 2 cửa sổ trình duyệt thật song song).
4. Khi có CSV Scopus 660 bài xuất thật, chạy lại trọn vẹn Phiên A/B trên một DB test mới để đóng nốt hạng mục còn lại ở mục 8.
