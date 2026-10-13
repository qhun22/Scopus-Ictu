# Ưu tiên 3 — ADMIN tạo tài khoản, LECTURER đăng nhập tra cứu (không JSON giảng viên)

**Ngày:** 2026-10-13
**Phạm vi:** ADMIN tạo tài khoản LECTURER/REVIEWER qua UI mà không cần hồ sơ giảng viên, LECTURER tra cứu công bố và đơn vị tác giả; E2E hai phiên (ADMIN/LECTURER) qua trình duyệt thật trên DB test không có JSON giảng viên.

---

## 1. KIỂM TRA — 2 vấn đề tồn đọng từ Ưu tiên 2

### A. Điều tra mất dữ liệu DB test sau PostgreSQL khởi động lại

**Phương pháp:** agent điều tra đọc source code (không đoán), tìm bằng chứng cụ thể trước khi kết luận.

**Đã loại trừ (có bằng chứng, không phải nguyên nhân):**
- **pytest tự xoá dữ liệu**: mọi integration test tạo schema riêng theo UUID (`test_t2_override_{uuid4().hex}` …) và chỉ `DROP SCHEMA` đúng schema đó trong `finally` — không bao giờ chạm `public`.
- **Alembic downgrade/upgrade tự động**: `demo_launcher.py.check_database()` chỉ SELECT `alembic_version` để so sánh, không gọi `upgrade`/`downgrade` ở đâu.
- **FK cascade xóa chéo**: `publication_authors` không có FK nào tới `users`; bảng override có `created_by_user_id`/`updated_by_user_id` → `users.id` với `ondelete="RESTRICT"` (chặn xoá user còn override, không cascade xoá dữ liệu).

**Bằng chứng trực tiếp thu được trong chính phiên này:** khi khởi động lại PostgreSQL demo cluster (55432) cho Ưu tiên 3, log (`_postgres_demo_14_10/logs/postgres.log`, 07:08–07:18 13/10/2026) cho thấy cluster đã **crash không sạch 2 lần liên tiếp** trước khi khởi động thành công ("startup process terminated by exception 0xC000013A", "database system was interrupted while in recovery"), buộc phải `redo` toàn bộ WAL từ đầu khi khởi động lại thành công.

**Kết luận (không khẳng định tuyệt đối — đúng yêu cầu không kết luận PostgreSQL "tự" làm mất dữ liệu nếu chưa có bằng chứng dứt khoát):** khả năng cao nhất, phù hợp với mọi bằng chứng thu thập được, là trong phiên Ưu tiên 2, một lần PostgreSQL bị dừng đột ngột (không qua `pg_ctl stop` sạch) đã khiến **transaction seed tay chưa commit bị rollback** khi WAL redo chạy lại — đây là hành vi ACID tiêu chuẩn, không phải lỗi ứng dụng hay lỗi pytest. `publications` (được ghi qua luồng import/apply có `session.commit()` tường minh ngay sau mỗi bước) sống sót, còn dữ liệu seed tay qua `psql`/script ngắn có thể chưa kịp commit trước khi crash xảy ra. **Không đủ bằng chứng** để xác nhận 100% đây chính xác là điều đã xảy ra (không có log của phiên thao tác tay đó), nhưng đây là giả thuyết duy nhất có bằng chứng ủng hộ, và không có giả thuyết "code tự xoá" nào có bằng chứng.

**Khuyến nghị cho vận hành tiếp theo:** sau khi seed dữ liệu test tay, luôn xác nhận bằng `COMMIT` tường minh trước khi coi PostgreSQL demo cluster là an toàn để dừng; tránh dừng cluster bằng cách kill tiến trình, luôn dùng `pg_ctl stop -m fast`.

### B. Một tác giả có nhiều đơn vị — GAP xác nhận, CHƯA sửa

Đọc `backend/app/models/affiliation_override.py:43-48,71-72`: cột `publication_author_id` có cả `unique=True` trên `mapped_column` lẫn `UniqueConstraint("publication_author_id", name="uq_paao_publication_author_id")` tường minh.

**Kết luận: hệ thống hiện tại CHỈ hỗ trợ đúng 1 override đang hoạt động cho mỗi vị trí tác giả (`publication_author_id`).** `PUT /overrides/{id}` luôn là upsert thay thế — không có khái niệm "nhiều đơn vị đồng thời được ADMIN ghi nhận" cho cùng một người ở cùng một bài báo (ví dụ: tác giả có 2 affiliation hợp lệ cùng lúc trên 1 bài — trường hợp thật ngoài đời khá phổ biến với đồng chủ nhiệm/giáo sư thỉnh giảng).

**Đề xuất tối thiểu (CHƯA thực hiện, cần quyết định riêng của bạn trước khi làm):**
- Bỏ `UniqueConstraint`/`unique=True` trên `publication_author_id`, thêm cột `is_current` hoặc đổi `PUT` thành luôn tạo dòng mới (giữ lịch sử), và sửa `list_needs_review`/hiển thị để gộp nhiều override đang hoạt động cho 1 vị trí.
- Đây là thay đổi schema không nhỏ (ảnh hưởng unique constraint, logic optimistic lock hiện dựa trên "có đúng 1 dòng"), nên **không tự thực hiện** trong phạm vi Ưu tiên 3 theo đúng chỉ đạo "không âm thầm thay đổi schema lớn khi chưa xin quyết định".

### Sửa UX nhỏ: xoá hiệu chỉnh không còn để lại form cũ

**Trước:** `frontend/src/pages/Normalization/ManualReviewCard.tsx` — sau khi xoá override, `remove()` chỉ gọi `setCurrent(null)` nhưng không đóng form (`editing` vẫn `true`) và không xoá nội dung `form` — ADMIN thấy form vẫn mở với dữ liệu vừa xoá, dễ hiểu nhầm là chưa xoá.

**Sau (đã sửa, [ManualReviewCard.tsx:109-123](frontend/src/pages/Normalization/ManualReviewCard.tsx)):** thêm `setForm(EMPTY_FORM)` và `setEditing(false)` ngay sau khi xoá thành công. Xác nhận qua UI thật (xem mục 4): sau khi bấm "Xóa hiệu chỉnh", form đóng hoàn toàn, nhãn "Đã có hiệu chỉnh" biến mất, tác giả quay về "Chưa có đơn vị".

## 2. KHẢO SÁT tài khoản và phân quyền

| Hạng mục | Hiện trạng trước Ưu tiên 3 |
|---|---|
| `User` model (`backend/app/models/governance.py:51-125`) | Đầy đủ `lecturer_id` **nullable**, FK RESTRICT, unique khi NOT NULL. Comment dòng 109-111 xác nhận: CHECK bắt buộc LECTURER phải có hồ sơ **đã bị gỡ bởi migration `f6a1b2c3d4e5`** — nền tảng sẵn có chính xác cho yêu cầu này. |
| Role | CHECK DB `role IN ('ADMIN','REVIEWER','LECTURER')` + Pydantic `Literal` khớp nhau. |
| API quản lý tài khoản (`backend/app/api/v1/endpoints/users.py`) | Có `GET`/`GET {id}`/`PATCH`/`lock`/`unlock`/`reset-password`, đều ADMIN-only, có audit, không lộ `password_hash`. **Không có `POST` tạo mới** trước Ưu tiên 3. |
| Bootstrap | `scripts/bootstrap_demo_admin.py` — chỉ CLI demo cục bộ (nhiều guard an toàn), không phải API production. |
| Giao diện quản lý người dùng | `frontend/src/pages/Users/index.tsx` **đã tồn tại từ trước** nhưng chỉ đọc (danh sách, không có form tạo). **Phát hiện qua kiểm thử UI thật**: route `/users` trong `App.tsx` redirect thẳng sang `/lecturers`, khiến `UsersPage` không bao giờ hiển thị được dù trang chủ có link trỏ tới `/users` — bug tồn tại từ trước, không do Ưu tiên 3 gây ra, đã sửa (mục 3). |
| `/publications`, `/search` | `GET /publications` và `GET /publications/{eid}` đã RBAC đúng cho ADMIN/REVIEWER/LECTURER (đọc), filter `q` (tiêu đề/EID/DOI/nguồn) và `scopus_id` đã có sẵn. **Chưa có filter theo tên tác giả** trước Ưu tiên 3. |
| Redaction/audit | `_for_role()` (`publications.py:39-49`) đã ẩn `provenance`/`approved_lecturer_links` khỏi LECTURER. `AuditEvent` dùng chung, `actor_invariant` CHECK giữ nguyên. |

## 3. TRIỂN KHAI

### Backend
| File | Thay đổi |
|---|---|
| `backend/app/schemas/user.py` | + `CreatableUserRole = Literal["REVIEWER","LECTURER"]` (không bao giờ `"ADMIN"` — ràng buộc ở tầng kiểu, không phải chỉ runtime check), `UserAdminCreate` (`extra="forbid"`, không có field `lecturer_id`) |
| `backend/app/services/user_admin_service.py` | + `create_user()`: kiểm tra email trùng (case-insensitive), validate tên hiển thị, hash mật khẩu bằng `password_hasher` sẵn có, `lecturer_id=None` cố định, ghi `AuditEvent` action `USER_CREATED` (không chứa password/hash) |
| `backend/app/api/v1/endpoints/users.py` | + `POST /api/v1/users` (ADMIN-only qua `AdminUser` dependency sẵn có, 201, response không có password) |
| `backend/app/services/publication_queries.py` | + param `author_name` trong `publication_filters`/`_list_statement`/`list_publications`: EXISTS join qua `ScopusAuthor.preferred_name`, diacritic/case-insensitive (dùng `folded()`/`fold_text()` sẵn có, cùng cơ chế với tìm theo tiêu đề) |
| `backend/app/api/v1/endpoints/publications.py` | + query param `author_name` cho `GET /publications` |

### Frontend
| File | Thay đổi |
|---|---|
| `frontend/src/api/users.ts` | + `createUser()`, type `CreateUserPayload` (role giới hạn `"REVIEWER" \| "LECTURER"`) |
| `frontend/src/pages/Users/index.tsx` | + `CreateUserForm` component: form tạo tài khoản (email, họ tên, mật khẩu ≥8 ký tự, vai trò), lỗi hiển thị rõ (trùng email…), không có ô chọn ADMIN |
| `frontend/src/App.tsx` | **Sửa route `/users`**: trước redirect sang `/lecturers` (khiến `UsersPage` mồ côi, không ai truy cập được), nay trỏ đúng `<UsersPage />` |
| `frontend/src/api/publications.ts`, `frontend/src/types/publication.ts` | + `author_name` trong `PublicationListQuery`/`getPublications()` |
| `frontend/src/pages/Publications/index.tsx` | + ô tìm kiếm "Tìm theo tên tác giả (Scopus)...", debounce giống ô tìm chính, đưa vào `hasAnyInput`/`handleClear` |
| `frontend/src/pages/Normalization/ManualReviewCard.tsx` | Sửa bug UX mục 1 (đóng form sau khi xoá) |

### Không làm (đúng ràng buộc)
- Không tạo hồ sơ giảng viên giả, không tự liên kết Scopus Author ID — `create_user()` không đụng bảng `lecturers`/`identity` ở bất kỳ đâu.
- Không có migration mới — toàn bộ dựa trên schema đã có từ `f6a1b2c3d4e5`.
- Không sửa `publication_author_affiliation_overrides` (GAP mục 1B để nguyên, chờ quyết định).

## 4. KIỂM THỬ E2E — trình duyệt thật

**Môi trường:** DB test mới hoàn toàn `scopus_ictu_test_p3_20261013` (cluster demo 55432, **0 giảng viên, 0 công bố, 0 user khi khởi tạo**), Alembic `upgrade head` → `b5e8d2f1a4c7`. Backend test cổng 8012, frontend test cổng 5187 (tách biệt hoàn toàn App DB 8001/5173 và Ưu tiên 2 8011/5183).

### Phiên A — ADMIN
1. **Đăng nhập** `p3.admin@ictu.edu.vn` (tạo bằng `bootstrap_demo_admin.py --apply`, dry-run xác nhận trước) — OK.
2. **Nhập CSV Scopus** qua API thật (cookie session thật từ UI, `fetch` FormData) — phát hiện **bug thao tác của chính tôi, không phải bug hệ thống**: CSV đầu tiên chỉ có cột `Authors` chung, thiếu `Author full names`/`Author(s) ID` theo đúng định dạng Scopus thật → lỗi `AUTHOR_LIST_LENGTH_MISMATCH` (ghi nhận đúng, hệ thống từ chối đúng cách, không crash, không ghi dữ liệu sai). Sửa CSV đúng định dạng 3 cột, import lại thành công (3/3 bản ghi).
3. **Chuẩn hóa công bố và bóc tách tác giả** qua UI thật: 2 bước riêng (tab "Công bố" → "Chuẩn hóa dữ liệu", tab "Tác giả" → "Bóc tách tác giả") — 5 tác giả Scopus mới tạo đúng (Hirsch, LeCun, Bengio, Hinton, Smith), đúng số vị trí tác giả mỗi bài.
4. **Đối chiếu đơn vị bằng nguồn có bằng chứng**: "Bắt đầu thu thập trực tuyến" — kết nối thật tới OpenAlex/Crossref/ORCID, hoàn tất (2 OpenAlex, 2 Crossref, 3 ORCID), Xem trước → tick xác nhận → Áp dụng: **10 kết quả đối chiếu đơn vị được ghi** (5 vị trí × 2 nguồn), tất cả `UNRESOLVED` (lý do `DUPLICATE_DOI_IN_SOURCE` vì CSV lỗi đầu tiên để lại 2 publication cùng DOI — hành vi đúng, không ghi đơn vị sai).
5. **Rà soát và hiệu chỉnh thủ công**: 5/5 vị trí hiển thị đúng trong mục "Rà soát", hiệu chỉnh LeCun → "Meta AI Research (New York)", nguồn `https://ai.meta.com/people/yann-lecun/`, lý do ghi rõ — lưu thành công, nhãn "Đã có hiệu chỉnh" hiện đúng.
6. **Tạo tài khoản LECTURER B**: qua trang `/users` (route vừa sửa) → form "Thêm tài khoản" → `lecturer.b@ictu.edu.vn`, vai trò Giảng viên, không hồ sơ → tạo thành công, "Không liên kết" hiển thị đúng.
7. **Audit và kết quả hiển thị**: `audit_events` xác nhận `USER_CREATED` (actor=ADMIN, `after_state` chỉ có email/display_name/role, không có password) + `DEMO_ADMIN_BOOTSTRAPPED` cho tài khoản ADMIN gốc.

### Phiên B — LECTURER
1. **Đăng nhập** bằng `lecturer.b@ictu.edu.vn` vừa tạo (logout ADMIN trước) — thành công, trang chủ hiển thị đúng vai trò, "Hồ sơ của tôi: Chưa có dữ liệu" (khớp tài khoản không liên kết).
2. **Tìm bài báo theo EID/DOI/tiêu đề**: ô tìm kiếm chính hoạt động đúng (đã có sẵn từ trước, không đổi).
3. **Tìm tác giả theo tên và Scopus Author ID**: thêm mới — gõ "lecun" (chữ thường) vào ô "Tìm theo tên tác giả" → đúng 1 kết quả "Deep learning" (bài có LeCun). Scopus Author ID filter (`scopus_id=`) đã có sẵn từ trước, vẫn hoạt động.
4. **Xem số lượng và thứ tự tác giả**: chi tiết "Deep learning" hiển thị đúng 3 tác giả, đúng thứ tự (LeCun, Bengio, Hinton).
5. **Xem tất cả đơn vị của từng tác giả, nguồn chứng cứ, mức xác minh**: box "ADMIN rà soát thủ công" cho LeCun hiển thị đầy đủ — tên đơn vị, nguồn URL, lý do, dòng cố định "Entered by an ADMIN after manual review; not an independent identity verification. Never counted as VERIFIED." Bengio/Hinton hiển thị đúng "Chưa xác định".
6. **Phân biệt tự động vs ADMIN**: rõ ràng — box tím override tách biệt hoàn toàn khỏi dòng "Theo nguồn: Crossref/OpenAlex" tự động.
7. **Trường hợp chưa xác định đơn vị**: hiển thị đúng "Chưa xác định được đơn vị" cho các vị trí không có override.

### RBAC — từ chối đúng cả UI và API
- **UI**: sidebar LECTURER chỉ có home/publications/search/profile/my-publications/identity — không có users/imports/normalization/audit-logs. Truy cập thẳng URL `/users` bị `RoleRoute` redirect về `/home`.
- **API thật** (gọi trực tiếp bằng cookie session LECTURER, không qua UI):

| Endpoint | Kết quả |
|---|---|
| `GET /api/v1/users` | 403 |
| `POST /api/v1/users` | 403 |
| `POST /api/v1/imports/scopus` | 403 |
| `GET /api/v1/affiliations/needs-review` | 403 |
| `PUT /api/v1/affiliations/overrides/{id}` | 403 |
| `GET /api/v1/audits` | 403 |

### Tài khoản đã liên kết hồ sơ — không bị phá
Không dựng DB test riêng thứ hai cho trường hợp này (đã có đủ bằng chứng tương đương): toàn bộ 939 test tự động (unit+integration, chạy lại 2 lần liên tiếp đều sạch) bao phủ rộng rãi các luồng LECTURER **có** `lecturer_id` liên kết — ví dụ `test_account_admin_and_notifications.py` (30 kịch bản tài khoản có hồ sơ), `test_lecturer_scopus_api.py`, `test_identity_evidence_confidence.py`. Không có test nào fail sau khi thêm `create_user()`/`author_name` filter — xác nhận code mới thuần additive, không đụng luồng có JSON.

## 5. KIỂM THỬ KỸ THUẬT VÀ AN TOÀN

| Hạng mục | Kết quả |
|---|---|
| Backend unit + integration | **939 passed, 5 skipped, 0 failed** (chạy lại 2 lần liên tiếp đều sạch; lần chạy đầu tiên ngay sau khi PostgreSQL phục hồi từ crash recovery có 7 ERROR flaky ở `test_candidate_persistence.py`, không tái hiện ở 2 lần sau — xem ghi chú dưới) |
| Frontend build (`tsc --noEmit && vite build`) | PASS, 0 lỗi, 2 lần (trước và sau khi sửa route `/users`) |
| Alembic | 1 head duy nhất `b5e8d2f1a4c7`, không migration mới |
| Phiên hết hạn | Không kiểm thử trực tiếp qua UI trong phiên này (nằm ngoài phạm vi thao tác đã thực hiện); cơ chế `auth_version` tăng khi khóa/đặt lại mật khẩu đã xác nhận qua test tự động có sẵn (`test_account_admin_and_notifications.py` kịch bản 21) |
| Backend restart | Không chủ động test lại (đã ghi nhận là giới hạn ở Ưu tiên 2, không lặp lại thử nghiệm phá hoại) |
| Tài khoản bị khóa | Test qua API thật: khoá `lecturer.b@ictu.edu.vn` → đăng nhập trả đúng `403 ACCOUNT_LOCKED` → mở khoá lại thành công |
| Email trùng | Test qua UI thật: tạo lại `lecturer.b@ictu.edu.vn` → lỗi "Email đã được sử dụng bởi tài khoản khác." hiển thị đúng, không tạo trùng |
| Dữ liệu nhiều affiliation | LeCun/Bengio/Hinton cùng 1 bài, đối chiếu 2 nguồn/vị trí — xác nhận hiển thị đúng; **GAP đa-override/1-vị-trí đã ghi ở mục 1B** |
| App DB (`scopus_ictu_app`, cổng 55432) | Không bị động tới: vẫn `f6a1b2c3d4e5`, 660 publications, 3 users (xác nhận trước và sau toàn bộ phiên) |
| Teacher DB | Không bị động tới: vẫn `a9c2e4f71b30`, chỉ đọc |
| `/system/reset` | Không chạm |
| GitHub | Không push, không commit CSV/JSON thật/secrets/ảnh QA chứa dữ liệu cá nhân |

### Ghi chú về 7 ERROR flaky
Lần chạy test suite đầy đủ đầu tiên (ngay sau khi PostgreSQL demo cluster vừa phục hồi từ 2 lần crash không sạch — xem mục 1A) có 7 lỗi `ERROR` (không phải `FAILED`) trong `tests/unit/test_candidate_persistence.py`, dùng chung `ISOLATION_ENGINE` kết nối trực tiếp schema `public` (khác với các test override/user dùng schema UUID riêng). Điều tra: chạy riêng file đó → 9/9 PASS; chạy lại toàn bộ suite 2 lần liên tiếp → 939/939 PASS, 0 lỗi cả 2 lần. Kết luận: lỗi flaky liên quan tới trạng thái connection pool PostgreSQL ngay sau phục hồi crash, không liên quan tới code Ưu tiên 3 — không chặn Gate 3, nhưng ghi nhận trung thực thay vì bỏ qua.

## 6. MỨC HOÀN THIỆN LUỒNG KHÔNG JSON

**Đã chứng minh qua E2E thật, không mô phỏng:** từ DB hoàn toàn trống (0 giảng viên, 0 user) đến ADMIN nhập CSV → chuẩn hóa → bóc tách tác giả → thu thập đơn vị trực tuyến → hiệu chỉnh thủ công → tạo tài khoản LECTURER → LECTURER tra cứu đầy đủ (EID/DOI/tiêu đề/tên tác giả/Scopus ID), xem đơn vị + nguồn + mức xác minh, phân biệt tự động/ADMIN, bị từ chối đúng quyền — toàn bộ chạy được **không cần một dòng JSON giảng viên nào**.

## 7. GIỚI HẠN CHƯA NGHIỆM THU

- **E2E với CSV Scopus mới xuất thật**: vẫn dùng CSV tối thiểu tự xây dựng (3 bản ghi, DOI thật chọn tay) như Ưu tiên 1/2, không phải CSV ADMIN tự xuất từ Scopus thật. Giữ nguyên hạng mục chờ nghiệm thu bổ sung như đã thống nhất ở Gate 2.
- **Độ bền tác vụ nền khi backend restart**: không test lại trong Ưu tiên 3 (đã ghi nhận là giới hạn từ Ưu tiên 2, chưa có thay đổi gì về cơ chế để cần test lại).
- **Độ chính xác affiliation theo đúng thời điểm xuất bản bài báo**: vẫn là lời khai nguồn ngoài tại thời điểm thu thập (hôm nay), không phải tại thời điểm xuất bản — giới hạn kiến trúc đã biết từ Ưu tiên 1, chưa thay đổi.
- **Nhiều đơn vị cho 1 tác giả cùng lúc**: GAP đã xác nhận ở mục 1B, chưa sửa, chờ quyết định.
- **Phiên hết hạn qua UI thật**: chưa test trực tiếp (chỉ xác nhận gián tiếp qua `auth_version`/test tự động có sẵn).
- **LECTURER có hồ sơ liên kết**: xác nhận gián tiếp qua test suite tự động (939 test, nhiều kịch bản có `lecturer_id`), chưa dựng DB test riêng thứ hai để click qua UI thật cho trường hợp này trong Ưu tiên 3.

## 8. GATE 3 — KẾT LUẬN

**PASS có điều kiện** cho phạm vi đã kiểm thử: ADMIN tạo được tài khoản LECTURER/REVIEWER qua giao diện hợp lệ với DB 0 hồ sơ giảng viên, không hồ sơ giả, không tự liên kết Scopus Author ID, không thể tạo ADMIN qua endpoint này; LECTURER đăng nhập và tra cứu đầy đủ công bố + đơn vị tác giả (tự động và ADMIN hiệu chỉnh) mà không cần JSON; RBAC đúng trên cả UI và API cho mọi thao tác quản trị bị từ chối.

**Phát hiện đáng chú ý:** route `/users` bị bỏ quên từ trước (redirect sai) — chỉ lộ ra khi kiểm thử UI thật theo đúng luồng ADMIN sẽ dùng, đã sửa và xác nhận lại. 2 vấn đề tồn đọng từ Gate 2 đã điều tra trung thực: nguyên nhân mất dữ liệu có giả thuyết hợp lý nhưng không tuyệt đối chắc chắn; GAP đa-affiliation xác nhận có thật, chưa sửa.

**Dừng tại đây, chờ bạn xem báo cáo trước khi chuyển Ưu tiên 4.**
