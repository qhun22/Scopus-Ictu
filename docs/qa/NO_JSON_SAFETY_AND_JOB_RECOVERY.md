# Báo cáo an toàn pytest và khôi phục job affiliation NO-JSON

Ngày thực hiện: 13/10/2026 (Asia/Bangkok)
Mốc Git trước khi làm: `579cae5` — "Cho phép một tác giả có nhiều đơn vị hiệu chỉnh độc lập, khép kín luồng không cần JSON giảng viên".

**Xác minh mốc tham chiếu trước khi làm:** chạy lại toàn bộ backend test suite trên DB pytest riêng (`scopus_ictu_test_pytest_20261013`) trước khi sửa bất kỳ dòng code nào — kết quả **946 passed, 5 skipped, 0 failed**, khớp chính xác báo cáo trước. Mốc tham chiếu xác nhận đúng.

---

## 1. Nguyên nhân pytest từng tác động DB E2E

`backend/tests/conftest.py` trước đây tạo `ISOLATION_ENGINE` trực tiếp từ `TEST_DATABASE_URL`, không tự tạo schema cách ly. Guard cũ (`_assert_test_database_url`) chỉ chặn 2 tên DB "forensic" (`scopus_ictu_acceptance_v2`, `scopus_ictu_ui_clean`), chạy đúng 1 lần lúc import module, không xác minh server thật đang kết nối (không kiểm tra `system_identifier`, không phân biệt cluster), và có cờ `TEST_ALLOW_LOCAL=1` cho phép bỏ qua toàn bộ guard.

Khảo sát bằng agent (đọc cả 17 file test tự tạo `create_engine` từ `TEST_DATABASE_URL`) xác định chính xác 2 file ghi trực tiếp vào schema `public` không qua cách ly:

- `backend/tests/integration/test_candidate_review_service.py` — fixture `review_engine`/`review_session` chạy `TRUNCATE ... CASCADE` trên danh sách bảng cố định **bao gồm `users`**, cả ở setup lẫn teardown của mỗi test.
- `backend/tests/integration/test_identity_evidence_confidence.py` — ghi `INSERT` trực tiếp vào `public.lecturers`/`public.scopus_authors`/`public.identity_evidence` không rollback, không teardown.

15 file còn lại (bao gồm `test_review_shared_author_warning.py` — fixture `seeded`, nguồn gốc của 3 hồ sơ giảng viên mẫu quan sát được trong Ưu tiên 3) đều dùng `isolated_db_engine` của `conftest.py` hoặc tự tạo schema UUID riêng (`CREATE SCHEMA "..._{uuid4().hex}"` + `DROP SCHEMA ... CASCADE` đúng schema đó) — an toàn tự nhiên dù trỏ nhầm DB, vì không chạm `public`.

Vì vậy, pytest có thể sửa DB E2E khi `TEST_DATABASE_URL` vô tình trỏ vào đó: engine dùng URL trực tiếp, tên DB E2E (`scopus_ictu_nojson_test_20261013`) không nằm trong blocklist cũ, và cờ `TEST_ALLOW_LOCAL=1` còn cho phép bỏ qua guard hoàn toàn.

## 2. Guard trước và sau sửa đổi

**Trước:** kiểm tra tên URL ở mức hẹp (2 DB), chạy một lần lúc import module, không xác minh server đang thật sự kết nối, có cờ môi trường vượt guard tùy ý.

**Sau:** `backend/tests/db_safety_guard.py` — guard tập trung, gọi lại **mỗi lần** trước thao tác phá hủy (không chỉ 1 lần module-load):

1. **Allowlist tường minh** (`ALLOWED_TEST_DATABASE_NAMES`): chỉ 2 tên DB pytest cục bộ (`scopus_ictu_test_pytest_20261011`, `scopus_ictu_test_pytest_20261013`) và `test_db` (CI container). Không dùng pattern "chứa chữ test/demo".
2. **Blocklist cứng độc lập** (`FORBIDDEN_DATABASE_NAMES`): App DB (`scopus_ictu_app`), teacher DB (`scopus_ictu_demo_teacher_20261014`), 2 DB forensic cũ, và 4 tên DB E2E/thủ công đã biết (`scopus_ictu_nojson_test_20261013`, `scopus_ictu_e2e_nojson_20261013`, `scopus_ictu_test_nojson_20261011`, `scopus_ictu_test_p3_20261013`). Kiểm tra **trước** allowlist — ngay cả khi allowlist bị sửa nhầm, blocklist vẫn chặn.
3. **Cổng cấm**: `5432` (production/local-service), không bao giờ cho phép dù tên DB hợp lệ.
4. **Xác minh server sống** qua round-trip SQL thật: `current_database()`, `inet_server_port()`, `inet_server_addr()`, `current_user`, và `pg_control_system()`'s `system_identifier` — đối chiếu với URL đã khai báo (`_check_connection_claims`). Hai DB pytest cục bộ bắt buộc đúng `system_identifier = 7694238084633166136` (cluster demo đã xác minh trong các phiên trước), qua `EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS`.
5. **Kiểm tra tên DB 2 lần**: 1 lần tĩnh từ `engine.url.database` (chặn App DB/teacher DB **trước khi mở bất kỳ kết nối nào**, kể cả với thông tin đăng nhập giả), 1 lần sau round-trip xác nhận server không nói dối tên DB nó đang phục vụ.
6. **Fail closed tuyệt đối**: mọi trường hợp thiếu cấu hình, không kết nối được, tên không khớp, port cấm, hay bất kỳ sai lệch URL/server nào đều raise `DatabaseSafetyRefused` — không có đường nào tiếp tục với kết quả "best-effort".
7. **Không in password/secret**: thông điệp lỗi chỉ chứa `drivername://user@host:port/database`, không bao giờ password.
8. **Không có biến môi trường vượt guard tùy tiện**: đã xóa hoàn toàn `TEST_ALLOW_LOCAL=1`. Allowlist là literal Python trong file, sửa qua code review như mọi thay đổi khác.
9. **Tích hợp vào `conftest.py`**: `ISOLATION_ENGINE` được xác minh ngay khi module nạp (fail bằng `pytest.exit`, dừng toàn bộ phiên trước khi bất kỳ test nào chạy), và fixture `isolated_db_engine` xác minh lại **mỗi lần** một test yêu cầu nó.
10. **Vá 2 điểm nguy hiểm thật**: `test_candidate_review_service.py` (`review_engine` fixture) và `test_identity_evidence_confidence.py` (`confidence_engine` fixture) — thêm `assert_safe_for_destructive_test(engine)` ngay sau khi tạo engine, trước `Base.metadata.create_all()`/bất kỳ câu lệnh nào khác.
11. **CI GitHub Actions**: thêm `DB_SAFETY_GUARD_CI_CONTAINER_NETWORK: "1"` vào `.github/workflows/ci.yml`, cùng cơ chế với `MATCHING_CLI_CI_CONTAINER_NETWORK` đã có — chỉ hiệu lực khi **cả 3** tín hiệu đồng thời: cờ này + `ENVIRONMENT=test` + `GITHUB_ACTIONS=true` (biến GitHub Actions tự set). Không một tín hiệu nào được tin một mình.

## 3. Bằng chứng DB được bảo vệ khỏi destructive tests

Thực hiện trực tiếp, không mô phỏng:

| Kịch bản | Kết quả quan sát thật |
|---|---|
| `TEST_DATABASE_URL` trỏ `scopus_ictu_nojson_test_20261013` (DB E2E thật) | `pytest.exit` ngay khi nạp `conftest.py`: *"database 'scopus_ictu_nojson_test_20261013' is on the hard-coded protected list... This can never be overridden."* — **0 test nào chạy, 0 câu lệnh TRUNCATE nào được gửi tới server.** |
| `TEST_DATABASE_URL` trỏ `scopus_ictu_app` (App DB thật), **dùng thông tin đăng nhập giả** `fakeuser:fakepass` | `pytest.exit` ngay lập tức, cùng thông điệp blocklist — xác nhận guard chặn **trước khi mở bất kỳ kết nối TCP nào** tới App DB, không phụ thuộc server có phản hồi hay không. |
| `TEST_DATABASE_URL` trỏ sibling DB `postgres` (reachable, không trong allowlist) | `DatabaseSafetyRefused` sau round-trip xác nhận tên thật từ server — chứng minh lớp xác minh server-side hoạt động độc lập với lớp tĩnh. |
| `TEST_DATABASE_URL` trỏ đúng DB pytest allowlist | Toàn bộ 979 test chạy bình thường, không bị chặn nhầm. |

20 unit test mới (`backend/tests/unit/test_db_safety_guard.py`) bao phủ: mọi tên trong allowlist pass, mọi tên trong blocklist bị từ chối (kể cả giả lập allowlist bị sửa nhầm), tên lạ chứa "test" bị từ chối, cổng 5432 bị cấm, địa chỉ non-loopback bị từ chối khi thiếu đủ 3 tín hiệu CI, được chấp nhận khi đủ cả 3, cluster identifier sai bị từ chối, và 1 test sống xác nhận round-trip thật. Toàn bộ **PASS**.

Trong suốt quá trình kiểm thử, App DB và teacher DB được xác nhận lại nhiều lần qua truy vấn trực tiếp (không qua pytest) — không bị TRUNCATE/DELETE/DROP nào, `alembic_version` và số `publications` giữ nguyên trước/sau toàn bộ phiên làm việc (App DB: `f6a1b2c3d4e5`, 660 publications; teacher DB: `a9c2e4f71b30`).

## 4. Khôi phục hiển thị job sau refresh/tab switch

**Backend:** thêm `GET /api/v1/affiliations/enrichment/online/latest` (`app/services/affiliation_enrichment_service.get_latest_job`) — trả job tạo gần nhất bất kể trạng thái, hoặc `null`. Route khai báo **trước** `/enrichment/online/{job_id}` trong code để FastAPI match đường tĩnh trước, tránh lỗi parse `"latest"` thành UUID (lỗi thật đã gặp và sửa ở Ưu tiên 3).

**Frontend:** `AffiliationsTab.tsx` thêm `useEffect` gọi `getLatestOnlineEnrichment()` khi component mount — **không bao giờ** gọi `startOnlineEnrichment()`. Khi job đang active (`RECEIVED`/`RUNNING`), polling 2 giây hiện có tiếp tục. Khi job `FAILED` với `error_summary.code`, UI hiển thị thông điệp cụ thể theo mã lỗi (`ENRICHMENT_INTERRUPTED`, `ENRICHMENT_PROCESSING_FAILED`) thay vì raw message. Khi `ENRICHMENT_ALREADY_RUNNING` xảy ra lúc bấm "Bắt đầu" (job khác — tab khác hoặc ADMIN khác — đã tạo trước), UI tự đồng bộ lại với job thật qua `getLatestOnlineEnrichment()` thay vì để lại trạng thái "chưa có job" sai lệch.

**Bằng chứng qua UI thật** (DB E2E `scopus_ictu_nojson_test_20261013`):
- Reload trang nhiều lần liên tiếp: DB xác nhận **không có job mới nào được tạo** (đếm `affiliation_enrichment_jobs` giữ nguyên 4 dòng qua 2 lần reload).
- Chuyển sang tab "Công bố" rồi quay lại "Đơn vị tác giả": trạng thái "Hoàn tất" hiển thị lại đúng ngay lập tức, không phải nút "Bắt đầu thu thập trực tuyến".
- Bấm "Bắt đầu thu thập trực tuyến" (job thật, mạng thật, 4 DOI) rồi reload ngay: `GET /enrichment/online/latest` trả đúng job vừa tạo (`8340c7e2-...`), không phải job cũ.

## 5. Trạng thái job khi backend restart

**Không có cơ chế nối lại asyncio task sau khi process dừng** — tài liệu docstring `recover_interrupted_enrichment_jobs()` nói rõ điều này, không tuyên bố hỗ trợ tự phục hồi.

Khi FastAPI lifespan khởi động (`app/main.py`), `recover_interrupted_enrichment_jobs()` chạy ngay sau `recover_interrupted_imports()` (pattern đã có sẵn cho `ScopusImport`). Với mỗi job còn `RECEIVED`/`RUNNING`, hàm thử `pg_try_advisory_xact_lock` theo đúng khóa job đó:
- Nếu **không** có worker nào thật sự giữ session-lock tương ứng (worker cũ đã chết cùng process trước) → khóa lấy được → job chuyển `FAILED`, ghi `error_summary.code = "ENRICHMENT_INTERRUPTED"` và `AuditEvent` (actor SYSTEM).
- Nếu **có** một worker khác (process khác, hoặc cùng process nhưng job thực sự vẫn đang chạy) đang giữ session-lock sống → không đánh dấu FAILED, tránh race condition giả. Đã kiểm thử riêng (`test_recover_does_not_fail_a_job_with_a_live_worker_lease`).

**Bằng chứng qua restart thật** (không mô phỏng trong code, restart tiến trình uvicorn thật):
1. Tạo 1 job RUNNING giả lập (ghi trực tiếp DB, mô phỏng trạng thái "worker đã chết, job bị bỏ rơi" — vì job thật với 4 DOI hoàn tất quá nhanh để bắt kịp lúc kill).
2. `taskkill` tiến trình backend.
3. Khởi động lại `uvicorn` — log in ra chính xác: `"Marked 1 interrupted affiliation enrichment job(s) as FAILED."`
4. DB xác nhận: `status=FAILED`, `error_summary={"code": "ENRICHMENT_INTERRUPTED", "message": "Tiến trình thu thập đơn vị trực tuyến bị gián đoạn khi dịch vụ khởi động lại."}`.
5. **UI thật** (reload trang, không cần đăng nhập lại — JWT còn hiệu lực): hiển thị "Thất bại" kèm thông điệp đầy đủ, thân thiện: *"Tiến trình bị gián đoạn khi máy chủ khởi động lại. Dữ liệu đã thu thập trước đó (nếu có) không bị mất, nhưng lượt chạy này đã dừng — hãy bắt đầu một lượt thu thập mới."* Không có thanh tiến độ giả nào hiển thị.
6. Override thủ công (LeCun → Meta AI Research, NYU đã thu hồi) **hoàn toàn không bị ảnh hưởng** bởi job gián đoạn — xác nhận qua cả DB và UI publication detail.

## 6. Kết quả kiểm thử thực tế

| Hạng mục | Kết quả |
|---|---|
| Backend unit + integration (DB pytest riêng, `scopus_ictu_test_pytest_20261013`) | **979 passed, 5 skipped, 0 failed** |
| — trong đó: unit test guard mới (`test_db_safety_guard.py`) | **20/20 PASS** |
| — trong đó: test job latest/recovery mới (`test_affiliation_enrichment_api.py`) | **9/9 PASS** (7 latest/recovery cơ bản + 1 worker-lease race + 1 cleanup) |
| — trong đó: `test_candidate_review_service.py` sau khi vá guard | **29/29 PASS** |
| Frontend typecheck + production build | **PASS** — `npm run build`, 0 lỗi TypeScript |
| Alembic | 1 head duy nhất `c7f2a9b1d3e5` (không migration mới trong nhiệm vụ này), `alembic check` không phát hiện drift |
| Guard từ chối DB sai đích trước cleanup | **PASS** — DB E2E và App DB đều bị chặn tức thì, xác nhận bằng thực nghiệm (mục 3) |
| ADMIN khởi tạo job thu thập trực tuyến | **PASS** — job thật, mạng thật, 4 DOI, OpenAlex/Crossref/ORCID |
| Refresh trình duyệt khi có job | **PASS** — không tạo job mới, hiển thị đúng job gần nhất |
| Chuyển tab rồi quay lại | **PASS** — trạng thái hiển thị lại đúng ngay lập tức |
| Job hoàn tất → preview → xác nhận → áp dụng | **PASS** — 12 resolution, 3 affiliation ghi thành công qua UI thật |
| Job gián đoạn do backend restart | **PASS** — FAILED rõ lý do, UI hiển thị đúng, không tiến độ giả |
| Không nhân đôi job/dữ liệu | **PASS** — đếm job trong DB không tăng qua nhiều lần reload |
| LECTURER không thao tác job quản trị | **PASS** — `GET /enrichment/online/latest` và `POST /enrichment/online` đều 403 qua API thật |
| Dữ liệu affiliation tự động + hiệu chỉnh thủ công không bị phá | **PASS** — override LeCun/NYU nguyên vẹn qua mọi restart, mọi lần thu thập lại |
| `lecturers = 0` trong DB E2E NO-JSON | **PASS** — xác nhận đầu và cuối phiên, kể cả sau tạo 2 user `lecturer_id IS NULL` |
| LECTURER độc lập JSON vẫn tra cứu bình thường | **PASS** — gián tiếp qua 979 test (nhiều kịch bản `lecturer_id` liên kết), trực tiếp qua UI publication detail |

## 7. Lỗi đã sửa

1. **Partial unique index không tạo trên schema test cô lập** (kế thừa từ nhiệm vụ trước, không liên quan trực tiếp — không phát sinh lỗi mới lần này).
2. **`AttributeError: 'FixtureFunctionDefinition' object has no attribute 'url'`** — lỗi thật trong `test_candidate_review_service.py::review_session`: lời gọi `assert_safe_for_destructive_test(review_engine)` bên trong fixture tham chiếu nhầm tên fixture function module-level thay vì giá trị đã resolve, vì `review_session` không khai báo `review_engine` làm tham số. Sửa bằng cách thêm `review_engine: Engine` vào chữ ký fixture `review_session`. Phát hiện qua chạy test suite đầy đủ (28 ERROR), xác nhận sửa đúng bằng chạy lại (0 lỗi).
3. **Route `/enrichment/online/latest` bị `{job_id}: UUID` nuốt mất** nếu khai sau — đã đặt đúng thứ tự route trước khi viết test, tránh lặp lại lỗi đã gặp ở Ưu tiên 3.
4. **CI thiếu cờ container-network cho guard mới** — `db_safety_guard.py` yêu cầu đủ 3 tín hiệu để chấp nhận `test_db` trên địa chỉ Docker bridge; đã bổ sung `DB_SAFETY_GUARD_CI_CONTAINER_NETWORK: "1"` vào `.github/workflows/ci.yml` trước khi coi guard "tương thích CI hiện có".

## 8. Giới hạn còn lại

- **CI GitHub Actions chưa chạy thật** trong nhiệm vụ này (không push/publish theo ràng buộc an toàn) — cờ `DB_SAFETY_GUARD_CI_CONTAINER_NETWORK` đã thêm dựa trên cùng logic đã verify cho `MATCHING_CLI_CI_CONTAINER_NETWORK` hiện có trong CI, nhưng hành vi chính xác của `inet_server_addr()` trong GitHub Actions service container cho job PostgreSQL cụ thể này chưa được quan sát trực tiếp — chỉ suy luận từ comment/thiết kế đã có.
- **Cơ chế worker-lease advisory lock** (session-level, chống 2 job chạy song song đúng nghĩa, không chỉ chống tạo trùng lúc start) được giữ nguyên từ một phiên bản code trước đó trong working tree — đã đọc, hiểu, xác nhận có test riêng (`test_recover_does_not_fail_a_job_with_a_live_worker_lease`) và toàn bộ test suite PASS cùng nó, không tự đơn giản hóa hay loại bỏ vì đây là giải pháp đúng đắn cho race condition thật (worker nhiều process) mà không cần Redis/Celery.
- **CSV Scopus mới xuất thật quy mô lớn (660 bài) vẫn chưa được nghiệm thu E2E toàn diện** — nhiệm vụ này tiếp tục dùng dữ liệu tối thiểu tự xây dựng (4 bài, DOI thật) trên DB E2E đã có từ nhiệm vụ trước. Đây **không phải PASS toàn phần** cho quy mô dữ liệu thật; giữ nguyên là hạng mục chưa nghiệm thu.
- **Hai ADMIN qua 2 cửa sổ trình duyệt thật song song** chưa quan sát trực quan trong nhiệm vụ này (đã xác nhận qua test tích hợp đồng thời ở Ưu tiên 2/3).

## 9. Commit cục bộ đã tạo

Thay đổi được nhóm theo 2 chủ đề, mỗi chủ đề một commit cục bộ (chi tiết SHA và tiêu đề xem `git log`), không push, không dùng tiền tố `fix:`/`feat:`/`chore:`:

1. Rào chắn an toàn database tập trung cho pytest — `tests/db_safety_guard.py` mới, tích hợp vào `conftest.py`, vá 2 fixture nguy hiểm, cập nhật CI workflow, test mới.
2. Khôi phục hiển thị tác vụ thu thập affiliation sau refresh và xử lý gián đoạn do backend restart — endpoint `/latest`, `recover_interrupted_enrichment_jobs`, cập nhật `AffiliationsTab.tsx`, test mới.

## 10. Kết luận phạm vi sẵn sàng cho Ưu tiên 4

Hai vấn đề được giao trong nhiệm vụ này — rào chắn an toàn pytest và khôi phục hiển thị job — đã **hoàn thành và kiểm thử đầy đủ bằng bằng chứng thật** (không mô phỏng): 979 test backend PASS, build frontend sạch, guard chặn đúng DB sai đích qua thực nghiệm trực tiếp (không chỉ unit test), và toàn bộ chu trình khởi tạo/refresh/chuyển tab/hoàn tất/gián đoạn job đã xác nhận qua UI thật trên DB E2E cách ly tuyệt đối khỏi DB pytest.

**Vẫn giữ nguyên giới hạn đã nêu trong các báo cáo trước:** CSV Scopus mới xuất thật quy mô lớn chưa được nghiệm thu E2E toàn diện. Việc các kiểm thử kỹ thuật và guard an toàn đạt **không tự động chuyển** hạng mục này thành PASS.

Có thể bàn giao: toàn bộ phạm vi NO-JSON (nghiệp vụ ADMIN/LECTURER, nhiều đơn vị độc lập, rào chắn pytest, khôi phục job) đã sẵn sàng ở mức kỹ thuật và E2E với dữ liệu tối thiểu. Chưa chuyển sang Ưu tiên 4 (JSON + Craw) — chờ quyết định của bạn sau khi xem báo cáo này, đặc biệt về việc có cần E2E với CSV Scopus thật quy mô lớn trước khi coi NO-JSON hoàn toàn khép kín hay không.
