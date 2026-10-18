# Release Candidate — Scopus-ICTU (17/10/2026)

Phiên bản đề xuất: code `main` @ **`237f7bc`** (giống `731fa8f` về code; `731fa8f..237f7bc` chỉ khác 1 file docs). Working tree không có thay đổi code; chỉ có `.claude/launch.json` (cấu hình test cục bộ) và các tệp QA chưa commit.
Lượt này không sửa code, không migration, không chạy job trực tuyến, không đổi `MAX_DOIS_PER_RUN`, không tạo tag, không commit, không push.
Liên quan: [`RELEASE_READINESS_20261017.md`](RELEASE_READINESS_20261017.md), [`CSV_ONLY_ACCEPTANCE_20261016.md`](CSV_ONLY_ACCEPTANCE_20261016.md) (cả hai đã có phần đính chính).

---

## 1. Release checklist

| # | Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | Code nghiệm thu = HEAD `237f7bc` | ✅ | `git diff --stat 731fa8f 237f7bc` chỉ ra 1 file docs; working tree không đổi code |
| 2 | Bộ test backend | ✅ 1047 passed / 6 skipped / 0 failed (chạy 2 lần) | DB allowlist `scopus_ictu_test_pytest_20261013`; danh sách skip ở readiness §Đính chính 2 |
| 3 | Build frontend (`tsc && vite build`) | ✅ | 8,9 s; cảnh báo chunk > 500 kB |
| 4 | Cụm PostgreSQL 55432 hoạt động, không hỏng dữ liệu | ✅ | phục hồi WAL sạch 04:19 17/10 |
| 5 | App DB ở HEAD `c7f2a9b1d3e5` | ✅ | `alembic_version` |
| 6 | DB teacher không bị thay đổi | ✅ | số dòng khớp `docs/demo/BACKEND_LOCALHOST_14_10.md` |
| 7 | Phân quyền API (401/403/422, 3 vai trò) | ✅ | ma trận 36 endpoint + test tự động |
| 8 | REVIEWER Accept/Reject (API + DB + audit + idempotent) | ✅ | readiness §4B |
| 9 | Accept/Reject xem lại trên UI | ⚠️ chưa có bằng chứng browser | cần phiên REVIEWER |
| 10 | UI khi DB rỗng (M2) | ⛔ BLOCKED | §2 |
| 11 | VI/EN toàn bộ route | ⚠️ một phần | readiness §Đính chính 5 |
| 12 | Bộ nguồn offline toàn vẹn | ✅ 10/10 SHA-256 OK | §3 |
| 13 | Không có secret hoặc cache trong tệp dự kiến commit | ✅ | grep không thấy mật khẩu/token; cache chưa được ignore (xem §6) |
| 14 | Tài liệu demo khớp launcher hiện tại | ⚠️ `BACKEND_LOCALHOST_14_10.md` còn ghi DB teacher | §4, §5 |
| 15 | Chủ đồ án duyệt commit tài liệu, tag, push | ⏳ chờ | §6 |

## 2. M2 — UI khi DB rỗng: **BLOCKED**

**Rà DB hiện có** (kiểm kê 17/10): không DB nào thỏa đồng thời *ở HEAD + không có dữ liệu nghiệp vụ + có tài khoản đăng nhập + được phép dùng*.
- `scopus_ictu_test_pytest_20261013`: ở HEAD, 0 user, nhưng là DB riêng của pytest (fixture phá hủy) và còn dữ liệu sót từ test (3 giảng viên, 2 tác giả).
- `scopus_ictu_test_mig_20261014`, `scopus_ictu_test_empty_t15_20261009`: rỗng nhưng ở `a9c2e4f71b30`. Phải migrate mới chạy được HEAD; không được tự migrate.

Không truncate/drop/reset bất kỳ DB nào. **Không ghi PASS.**

**Quyền cần cấp để đóng M2** (đều chỉ trên cụm 55432, không đụng DB có sẵn):

| # | Thao tác | Lý do bị chặn | Cách cấp |
|---|---|---|---|
| 1 | `CREATE DATABASE scopus_ictu_test_empty_20261017 OWNER scopus_demo_user` bằng vai trò `demo_admin` (mẫu `_postgres_demo_14_10/tools/create_mig_db.py`; script từ chối nếu DB đã tồn tại) | Bộ phân quyền xếp loại "Unauthorized Persistence" | Chủ đồ án tự chạy, hoặc thêm quy tắc cho phép lệnh này. **Không cần** ghi `pgpass.conf`: backend nối bằng `DB_NAME` override. |
| 2 | `alembic upgrade head` với `DB_NAME=scopus_ictu_test_empty_20261017` | Hệ quả của bước 1 | Cho phép cùng bước 1 |
| 3 | Tạo 1 ADMIN (+ tùy chọn REVIEWER/LECTURER) bằng `scripts/bootstrap_demo_admin.py --apply --expected-database scopus_ictu_test_empty_20261017 --expected-port 55432` | Ghi vào DB mới | Cho phép cùng bước 1 |
| 4 | Đăng nhập trình duyệt | "Credential Materialization": tôi không được đọc mật khẩu test vào ngữ cảnh | **Chủ đồ án tự đăng nhập** trong Browser pane (cách được khuyến nghị). Sau đó tôi kiểm `/home`, `/dashboard`, `/publications`, `/search`, `/normalization`, `/reviews`, `/imports`. |

## 3. M1 — chốt phương án demo bằng **bộ nguồn offline**

| Chỉ số | Bộ offline `_du_lieu_demo_14_10/affiliation_survey` (tải 09/10) | Chế độ trực tuyến (App DB / DB CSV-only) |
|---|---|---|
| Toàn vẹn | `sha256sum -c SHA256SUMS.txt`: **10/10 OK** (kiểm lại 17/10) | — |
| DOI hợp lệ | 635 | 635 |
| **Đã truy vấn** | **635** | 300 (cố định, EID tăng dần) |
| Có dữ liệu ở ≥1 nguồn | 629 (OpenAlex 629, Crossref 629) | 296 |
| **Đã truy vấn nhưng không tìm thấy** | **6** | 4 |
| **Chưa truy vấn** | **0** | **335** |
| Không có DOI | 25 | 25 |
| ORCID (có khai Scopus ID) | 605 (190) | 310–314 |
| Kết quả trong DB | 217 tổ chức / 5.502 resolution / 4.147 dòng đơn vị; VERIFIED 781 · CORROBORATED 4.130 · UNRESOLVED 591 (dòng resolution); `NO_EXTERNAL_WORK` 182 dòng | 106 / 5.502 / 1.709–1.711; `NO_EXTERNAL_WORK` 3.060 dòng |

**DB và code tương thích với bộ offline:**
- `scopus_ictu_test_withjson_r2_20261011`: Alembic **HEAD**. Đơn vị đã nạp từ bộ offline: `retrieved_at` 09/10, 636 payload, phân bố trạng thái **trùng khớp** DB teacher. Có 0 job trực tuyến. Dùng được với code `237f7bc`. → **DB demo đề xuất**.
- DB teacher: cùng dữ liệu đơn vị nhưng ở `a9c2e4f71b30`, **không tương thích** code HEAD. Không migrate theo chỉ đạo.
- App DB: đang chứa kết quả trực tuyến 300 DOI. Muốn chuyển sang offline thì phải đặt `AFFILIATION_SOURCE_DIR` trong `secrets/backend_app.env` rồi chạy Preview → Apply (có ghi). Việc này chưa làm và không đề xuất trước buổi bảo vệ.

**Thao tác người dùng trong demo (không ghi dữ liệu):** mở các công bố mẫu để trình bày đơn vị theo tác giả và mức tin cậy (kịch bản §7). Không bấm "Bắt đầu thu thập trực tuyến". Không bấm "Xác nhận áp dụng".
*Tùy chọn (cần đổi cấu hình, chủ đồ án quyết định):* đặt `AFFILIATION_SOURCE_DIR` cho backend demo để trình diễn bước **Xem trước** của bộ offline (chỉ đọc). Bấm Áp dụng lại sẽ báo "Không có gì mới để ghi" (idempotent, đã kiểm 11/10).

## 4. Bản đồ môi trường demo

| | **A. Demo đề xuất (dữ liệu đầy đủ, offline)** | B. Launcher chính thức | C. CSV-only test | D. Teacher (đóng băng) |
|---|---|---|---|---|
| Code | `Scopus-Ictu` @ `237f7bc` | `Scopus-Ictu` @ `237f7bc` (launcher `ef625e1`) | `Scopus-Ictu` @ `237f7bc` | Không có code HEAD tương thích |
| Khởi động | backend từ `Scopus-Ictu/backend` dùng `backend/.env`; frontend proxy → 8199 (cấu hình `p4ui-backend`/`p4ui-frontend` trong `.claude/launch.json`) | `scopus-ictu-qhun22.bat` | `csvonly-backend`/`csvonly-frontend` | — |
| Database | `scopus_ictu_test_withjson_r2_20261011` | `scopus_ictu_app` | `scopus_ictu_test_csvonly_20261011` | `scopus_ictu_demo_teacher_20261014` |
| Alembic | `c7f2a9b1d3e5` (HEAD) | `c7f2a9b1d3e5` (launcher **tự migrate**) | HEAD | `a9c2e4f71b30` |
| Cổng BE / FE | 8199 / 5199 | 8001 / 5173 | 8299 / 5299 | — |
| Dữ liệu | 410 GV, 660 bài, 1.207 tác giả, Craw 327, đơn vị offline 217/4.147, 149 ứng viên (144 PENDING / 3 ACCEPTED / 2 REJECTED), 3 identity | 0 GV, 660 bài, đơn vị trực tuyến 300 DOI (106/1.709) | 0 GV, 660 bài, đơn vị trực tuyến 300 DOI (106/1.711) | 411 GV, đơn vị offline, 40 PENDING |
| Tài khoản | ADMIN, REVIEWER, LECTURER (có tài khoản đã liên kết hồ sơ và chưa liên kết) | 3 ADMIN (`admin@ictu.edu.vn`, `admin@gmail.com`, `user@ictu.edu.vn`); **không có REVIEWER/LECTURER** | `csvonly.e2e.*` (3 vai trò) | — |
| Demo được | tra cứu, chi tiết công bố + đơn vị + bằng chứng, Dashboard, giảng viên, duyệt đối sánh, lịch sử review, phân quyền 3 vai trò, VI/EN | nhập/chuẩn hóa/bóc tách, tra cứu, Dashboard, quản lý user, thu thập trực tuyến (kèm giới hạn) | luồng CSV-only không JSON, ca thiếu đơn vị | — |
| Không nên chạy | nhập lại JSON/CSV, sinh lại ứng viên, `/system/reset` | số liệu bao phủ đơn vị (bị giới hạn 300 DOI); `/system/reset` | `/system/reset` | **Không chạy launcher trỏ vào DB này** (sẽ tự migrate); không chạy code HEAD trên DB này |

Lưu ý: A là DB test và có 2 quyết định REVIEWER tạo ngày 17/10 (ghi rõ lý do "Nghiệm thu release"). Nếu muốn A trở thành demo chính thức qua launcher, cần đổi `DB_NAME` trong `secrets/backend_app.env` và `SCOPUS_DEMO_DB`; việc đó do chủ đồ án quyết định.

## 5. Known limitations

| # | Hạn chế | Ảnh hưởng demo | Kiểm soát |
|---|---|---|---|
| L1 | **Thu thập trực tuyến chỉ truy vấn tối đa `AFFILIATION_ONLINE_MAX_DOIS_PER_RUN` (mặc định 300) DOI**, chọn cố định theo EID tăng dần; job sau lặp lại cùng tập, không tiếp tục được. DOI chưa truy vấn mang cùng mã `NO_EXTERNAL_WORK` như DOI không có ở nguồn; Preview gộp hai loại; UI không báo bị cắt. | Số liệu bao phủ ở chế độ trực tuyến thấp và dễ hiểu sai | Demo bằng dữ liệu offline (môi trường A). Nếu trình bày chế độ trực tuyến thì nói rõ giới hạn. |
| L2 | Bước ORCID của job trực tuyến không có tiến độ trung gian (vài phút trông như treo) | Chỉ khi chạy job | Không chạy job trong demo |
| L3 | Đơn vị là lời khai của nguồn ngoài tại thời điểm thu thập, không phải tại thời điểm xuất bản; "Đã đối chiếu" ≠ "Đã xác minh" | Cần giải thích khi trình bày | Nhãn đã có trên UI |
| L4 | Chưa có bằng chứng UI khi DB rỗng (M2) | Không demo từ DB rỗng | §2 |
| L5 | Accept/Reject chưa xem lại trên UI sau khi Việt hóa `/reviews` (logic không đổi; bằng chứng API/DB/audit đầy đủ) | Thấp | Thử nhanh trên môi trường A trước buổi bảo vệ |
| L6 | VI/EN chưa test browser toàn bộ route; `/login` chỉ có tiếng Việt | Thấp | Demo bằng tiếng Việt |
| L7 | Sinh ứng viên và nạp Craw chỉ chạy được trên DB có JSON giảng viên; App DB không có giảng viên | Không demo đối sánh trên App DB | Dùng môi trường A |
| L8 | Code HEAD không chạy trên DB teacher; `docs/demo/BACKEND_LOCALHOST_14_10.md` còn mô tả DB teacher là DB demo | Nhầm lẫn khi khởi động | Cập nhật tài liệu demo (đề xuất, chờ duyệt) |
| L9 | Launcher tự `alembic upgrade head` trên DB mục tiêu | Có thể migrate ngoài ý muốn nếu đổi `DB_NAME` | Chỉ trỏ vào DB đã ở HEAD |
| L10 | Bundle JS 1,36 MB (đã nén 390 kB) | Tải trang lần đầu chậm hơn | Chạy localhost, không đáng kể |
| L11 | Tài khoản test (`csvonly.e2e.*`, `withjson.*`, `scroll.e2e.*`) còn hoạt động trên DB test | Không ảnh hưởng App DB | Khóa hoặc đổi mật khẩu khi bàn giao |

## 6. Git release

**Trạng thái:** `main` @ `237f7bc`, đi trước `origin/main` (`89cf46f`, 12/10) **37 commit**, chưa có tag nào.

| Tệp | Phân loại | Đề xuất |
|---|---|---|
| `docs/qa/CSV_ONLY_ACCEPTANCE_20261016.md` | tài liệu QA | **Commit** (sau khi duyệt) |
| `docs/qa/RELEASE_READINESS_20261017.md` | tài liệu QA | **Commit** |
| `docs/qa/RELEASE_CANDIDATE_20261017.md` | tài liệu QA | **Commit** |
| `backend/scripts/create_csvonly_e2e_accounts.py` | script tạo tài khoản test, mật khẩu đọc từ biến môi trường | **Không đưa vào release** (theo quyết định chốt RC); giữ cục bộ |
| `.gitignore` | thêm 1 dòng `backend/.tmp_*/` | **Commit** (sau khi duyệt) |
| `.claude/launch.json` (M) | cấu hình dev cục bộ (8299/5299 trỏ DB test) | **Không commit, không hoàn tác**: chỉ không stage. Diff chỉ thêm 2 mục `csvonly-*`, không sửa `p4ui-*` (môi trường A). Hoàn tác sẽ làm mất cấu hình khởi động môi trường C, không ảnh hưởng môi trường A. |
| `backend/.tmp_csvonly_affiliation_cache/` (3 tệp, 1,7 MB) | cache OpenAlex/Crossref/ORCID | **Loại trừ** (ignore rule ở trên) |
| `frontend/dist/`, `backend/.env` | build / cấu hình | Đã được ignore |
| `_postgres_demo_14_10/scratch/*`, `tools/*`, `secrets/*` | ngoài repo | Không thuộc Git |

Đã quét các tệp dự kiến commit: không có mật khẩu, token hay secret.

**Release metadata:**

| | Giá trị |
|---|---|
| Code baseline SHA (code đã nghiệm thu) | `237f7bc38bb63f8500e68bc07c53e0598c441002` |
| Release commit SHA | *chưa có*: commit chỉ chứa tài liệu QA + `.gitignore`, tạo sau khi chủ đồ án duyệt. Code giống baseline. |
| Release tag | `v1.0.0-rc.1` (annotated), **chỉ đặt lên release commit**, không đặt lên `237f7bc` |
| Bản cuối | `v1.0.0` sau buổi bảo vệ |

**Release notes:**
```
Scopus-ICTU v1.0.0-rc.1  (code baseline 237f7bc; release commit = commit tài liệu kế tiếp)

Chức năng đã nghiệm thu
- Nhập CSV Scopus qua giao diện → chuẩn hóa công bố → bóc tách tác giả (giữ đúng thứ tự),
  truy vết tệp/dòng/SHA-256; tra cứu công bố, tác giả, giảng viên.
- Đơn vị theo tác giả từ OpenAlex/Crossref/ORCID (bộ nguồn offline đã kiểm SHA-256, hoặc thu thập trực tuyến):
  Đã xác minh định danh (chuỗi ORCID→Scopus ID) / Đã đối chiếu · Chưa xác minh / Chưa xác định;
  không gán đơn vị khi thiếu bằng chứng; ADMIN hiệu chỉnh nhiều đơn vị có nguồn và lý do.
- Nhập JSON giảng viên, nạp Craw, sinh ứng viên đối sánh; REVIEWER chấp nhận/từ chối
  (idempotent, khóa phiên bản, có audit, tạo liên kết định danh khi chấp nhận).
- ADMIN tạo tài khoản REVIEWER/LECTURER không cần hồ sơ; phân quyền ADMIN/REVIEWER/LECTURER ở UI và API
  (401 chưa đăng nhập / 403 sai vai trò / 403 LECTURER_NOT_LINKED / 422 dữ liệu không hợp lệ).
- Dashboard dùng dữ liệu thật; Việt hóa toàn site; chuyển VI/EN.

Chất lượng
- Backend: 1047 passed, 6 skipped, 0 failed (chạy 2 lần). 6 skip: 5 test kiểm bộ dữ liệu giảng viên
  (dữ liệu không nằm trong repo), 1 test CLI bị rào chắn an toàn chặn khi process không trỏ DB test.
- Frontend: tsc + vite build PASS.

Hạn chế và hạng mục chưa đầy đủ
- Chế độ thu thập trực tuyến chỉ truy vấn tối đa 300 DOI mỗi lần (AFFILIATION_ONLINE_MAX_DOIS_PER_RUN),
  cố định theo EID tăng dần; DOI chưa truy vấn mang cùng mã NO_EXTERNAL_WORK như DOI không có ở nguồn.
- M2: CHƯA có bằng chứng UI thực tế trên database hoàn toàn trống; chỉ có bằng chứng ở tầng API/schema rỗng.
- PARTIAL: Accept/Reject chưa được xem lại trên UI; VI/EN chưa test browser toàn bộ route; kiểm tra UI demo
  cuối cần chủ đồ án đăng nhập.
- Code HEAD không tương thích DB teacher (a9c2e4f71b30); launcher demo tự migrate DB mục tiêu.

Môi trường demo
- Code 237f7bc; backend 8199 / frontend 5199; DB scopus_ictu_test_withjson_r2_20261011 (Alembic c7f2a9b1d3e5);
  đơn vị từ bộ offline affiliation_survey (tải 09/10, SHA-256 khớp audit áp dụng 12/10);
  410 giảng viên, 660 công bố, 1.207 tác giả, 217 tổ chức / 4.147 dòng đơn vị; tài khoản ADMIN, REVIEWER, LECTURER.
```

## 7. Đề xuất GO / NO-GO

**GO có điều kiện** khóa `v1.0.0-rc.1` (code `237f7bc`):
- Không còn BLOCKER nghiệp vụ. Nghiệp vụ cốt lõi (CSV → công bố → tác giả → đơn vị có bằng chứng → tra cứu; JSON/Craw → đối sánh → duyệt; phân quyền) đều có bằng chứng thực nghiệm. Test và build sạch.
- Điều kiện:
  - (1) Chủ đồ án chọn môi trường demo; đề xuất môi trường **A** cho dữ liệu đơn vị offline.
  - (2) Chấp nhận M2 (UI khi DB rỗng) là tồn đọng bằng chứng đã ghi, hoặc cấp quyền theo §2 để đóng trước khi khóa.
  - (3) Duyệt commit tài liệu QA và `.gitignore`.
- Nên làm trước buổi bảo vệ (khoảng 10 phút, không ghi dữ liệu): đăng nhập REVIEWER ở môi trường A, mở `/reviews` và `/review-history` để xác nhận L5.

## 8. Kịch bản demo sơ bộ (môi trường A, khoảng 15 phút, chỉ đọc)

1. **Giới thiệu và phân quyền (2'):** đăng nhập ADMIN → `/home` (shortcut theo vai trò) → sidebar đầy đủ chức năng quản trị. Nêu ba vai trò ADMIN / REVIEWER / LECTURER.
2. **Tổng quan (2'):** `/dashboard`: công bố theo năm, cơ cấu loại tài liệu, mức đầy đủ đơn vị tác giả. Số liệu lấy từ DB, không phải dữ liệu giả.
3. **Dữ liệu nguồn (2'):** `/imports`: đợt nhập CSV 660 bài, SHA-256 tệp. `/normalization`, tab Tác giả: 1.207 tác giả, biến thể tên.
4. **Tra cứu và bằng chứng đơn vị (4'):** `/search` → `2-s2.0-105000434624`: 3 tác giả đúng thứ tự; tác giả 1 *Đã xác minh định danh* (chuỗi ORCID → Scopus ID, ICTU); tác giả 2–3 *Đã đối chiếu · Chưa xác minh*; bảng truy vết tệp/dòng/SHA-256. Tiếp theo `2-s2.0-105000836388`: tác giả *Chưa có thông tin đơn vị*, hệ thống không bịa đơn vị.
5. **Giảng viên và đối sánh (3'):** `/lecturers` (410 hồ sơ) → `/reviews`: hàng đợi ứng viên, bằng chứng tên/công bố, cảnh báo mơ hồ và Scopus ID dùng chung → `/review-history`: quyết định đã có (ACCEPT/REJECT kèm lý do). **Không bấm** Chấp nhận/Từ chối khi trình diễn.
6. **Vai trò khác (2'):** đăng xuất → REVIEWER (thấy duyệt đối sánh, không thấy quản trị; mở `/dashboard` bị chuyển về `/home`) → LECTURER (Hồ sơ / Công bố của tôi / Liên kết Scopus). Chuyển **EN** một lần để cho thấy song ngữ.
7. **Hạn chế (trả lời hội đồng):** đơn vị là lời khai của nguồn ngoài; chế độ trực tuyến giới hạn 300 DOI mỗi lượt (L1); sinh ứng viên cần dữ liệu giảng viên.

Trước khi trình diễn: chạy `start_postgres.cmd`, khởi động backend 8199 và frontend 5199 (môi trường A), mở `http://localhost:5199`, thử đăng nhập cả 3 vai trò.

---

## 9. Chốt RC — quyết định của chủ đồ án và kiểm tra demo cuối (17/10)

**Quyết định:**
- Môi trường demo chính thức = **A**: DB `scopus_ictu_test_withjson_r2_20261011`, backend 8199 / frontend 5199, code `237f7bc`, đơn vị từ bộ offline đã nghiệm thu, đủ 3 vai trò.
- Không dùng DB teacher với code HEAD. Không dùng launcher tự migrate trên DB chưa xác nhận tương thích. Không chạy thu thập trực tuyến hay Apply mới.
- **M2 là tồn đọng nghiệm thu có kiểm soát của bản RC, KHÔNG phải PASS:**
  - Chưa có bằng chứng UI thực tế trên database hoàn toàn trống.
  - Đã có bằng chứng kiểm thử API/schema rỗng trước đó (`test_dashboard_api.py`, `TestChartsEmptyDatabase` và các test dashboard trên schema mới tạo; kèm màn hình rỗng ngày 11/10 trước khi có biểu đồ/Home mới).
  - Phạm vi demo chính thức dùng dataset đã chuẩn bị (môi trường A), không demo từ DB rỗng.

**Kiểm tra demo cuối trên môi trường A (chỉ đọc):**

| # | Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|---|
| 1 | Server nối đúng DB TEST | **PASS** | Backend 8199 (PID 26972) có đúng 1 kết nối, `pg_stat_activity.datname = scopus_ictu_test_withjson_r2_20261011` |
| 2 | Dữ liệu offline đã áp dụng thật và có provenance | **PASS** | Audit `AFFILIATION_IMPORT_APPLIED` (12/10 00:14) lưu `bundle_sha256` của 4 tệp nguồn, **khớp `SHA256SUMS.txt`** của bộ offline. 5.502 resolution `importer_version=affiliation-import/1`, `retrieved_at` 09/10; 4.147 dòng đơn vị / 217 tổ chức; 0 job trực tuyến. Kiểm tra toàn vẹn: 0 dòng UNRESOLVED có đơn vị, 0 dòng VERIFIED thiếu ORCID. |
| 3 | `/home` cho 3 vai trò | **API PASS · UI BLOCKED** | Đăng nhập API cả 3 vai trò OK. Xem UI cần chủ đồ án đăng nhập: tôi không được nhập mật khẩu test. |
| 4 | Dashboard ADMIN | **API PASS · UI BLOCKED** | `/dashboard/summary`: 660 công bố / 410 giảng viên / 1.207 tác giả / 144 PENDING. `/dashboard/charts`: 20 năm, 8 loại tài liệu, đơn vị 2.291/2.751 vị trí (VERIFIED 545 · CORROBORATED 2.053 · UNRESOLVED 153). REVIEWER/LECTURER nhận 403. |
| 5 | Công bố mẫu có tác giả, đơn vị, nguồn chứng cứ | **API PASS · UI BLOCKED** | `2-s2.0-105000434624`: 3 tác giả đúng thứ tự. Tác giả #1 VERIFIED: văn bản đơn vị "…(ICTU), Thai Nguyen, Vietnam", `ORCID_SCOPUS_ID_BRIDGE`, ORCID `0000-0003-1801-5887` khai Scopus ID `57560524600`. Truy vết CSV dòng 150, SHA-256 `6a62fcf6…`. |
| 6 | Thiếu bằng chứng không thành đơn vị giả | **API PASS · UI BLOCKED** | `2-s2.0-105000836388`: tác giả #3 Amago và #5 Maligalig có **0** đơn vị. |
| 7 | Danh sách đối sánh, lịch sử review, công bố | **API PASS · UI BLOCKED** | `/reviews/candidates` 144 PENDING; `/reviews/history` 5; `/reviews/context` `HAS_CANDIDATES`; `/publications` 660; `/lecturers` 410. REVIEWER xem được review và công bố, bị 403 ở dashboard/users. LECTURER xem được công bố, bị 403 ở review/dashboard, `/lecturers/me/profile` trả 403 `LECTURER_NOT_LINKED` (tài khoản `withjson.viewer` chưa liên kết). |
| 8 | Không có lỗi nghiêm trọng | **PASS** | Log backend/frontend không có lỗi server; console chỉ có 401 `/auth/me` trước đăng nhập (đúng thiết kế). DB không đổi sau lượt kiểm tra (audit 22, review 5, identity 3, đơn vị 4.147). |

**Kết luận kiểm tra demo:** **PARTIAL**. Dữ liệu, API và phân quyền sẵn sàng. Phần xem UI qua browser cần **chủ đồ án tự đăng nhập** ADMIN → REVIEWER → LECTURER tại `http://localhost:5199`, rồi đi qua các bước 1–6 của §8 (khoảng 10 phút, không bấm Chấp nhận/Từ chối/Áp dụng/Nhập). Lưu ý: tài khoản LECTURER `withjson.viewer` chưa liên kết hồ sơ nên trang "Hồ sơ của tôi" hiển thị "Tài khoản chưa được liên kết"; tài khoản LECTURER có liên kết hồ sơ là `vu.duc.quang.test@ictu.edu.vn`.

---

## Addendum 2026-10-18 (P12-B2/B3)

Tài liệu gốc phản ánh trạng thái **snapshot ngày 17/10/2026** — code @ `237f7bc`, working tree khi đó không có thay đổi code chưa commit.

### Những gì đã thay đổi từ 17/10

Từ ngày 17/10 đến 18/10, các thay đổi P07–P12 đã được hoàn thành trong working tree và sau đó được commit theo manifest P12-B2:

| Nhóm | Nội dung | Trạng thái |
|---|---|---|
| Backend P09 | Review governance D-2/D-3, identity evidence basis, publication queries | ✅ PASS — 1111 tests |
| Backend P10 | Launcher an toàn PA-1 (FORBIDDEN_PORTS, EXPECTED_DB, credential masking) | ✅ PASS |
| Frontend P11 | Design System R1–R4: Button/Badge/PageHeader components, token colors/sizes | ✅ Build clean |
| Frontend P11 | i18n hoàn thiện, shared components (ConfirmDialog, TextConfirmModal, Header) | ✅ TypeScript 0 errors |
| P12-B0 | Radius 5px alignment — 53 replacements / 10 files / 48/48 browser PASS | ✅ PASS |
| P12-A | Full regression 1111 PASS, browser smoke 12/12 PASS, App DB head c7f2a9b1d3e5 | ✅ PASS |

### Những gì vẫn chưa đóng

| Gate | Trạng thái |
|---|---|
| Security 5432 (`scopus_m12_user`) | ⚠️ OPEN — credential chưa rotate, chưa restrict listen_addresses |
| UI write-flow UI-12/13/14 | ⚠️ DEFER — i18n nhỏ, không blocking RC |
| Figma nodes 5:2/9:9/9:72/9:25/9:41 | ⏳ PENDING — cần auth Figma MCP hoặc designer |
| M2 (UI khi DB rỗng) | ⚠️ BLOCKED — vẫn như ghi chú §2 tài liệu gốc |
| RC tag / push | 🔴 HOLD — chờ owner approve sau commit |

Tài liệu gốc (nội dung trước addendum này) KHÔNG được sửa đổi.
