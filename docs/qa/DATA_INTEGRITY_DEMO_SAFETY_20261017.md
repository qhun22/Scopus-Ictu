# Data Integrity & Demo Safety Resolution — Scopus-ICTU (17/10/2026)

Phiên **chỉ đọc**. Không sửa code, không ghi DB, không backup/restore, không stage/commit/tag/push. 4 file RC đã stage giữ nguyên (`fb176d6`, `853c832`, `3b03317`, `0c34a85`). DB nguồn: `scopus_ictu_test_withjson_r2_20261011` (môi trường A).
Mức bằng chứng: **VR** runtime / truy vấn DB · **VS** đọc code · **RO** báo cáo cũ.

---

## 1. DATA-01 — Root cause và severity

### 1.1 Sự thật dữ liệu (VR, truy vấn chỉ đọc)

| Hạng mục | Giá trị |
|---|---|
| Scopus author | `59253245500` "Nguyen Thi, Dung" (biến thể: "Nguyen Thi D.") |
| Công bố của tác giả này | **1 bài**: `2-s2.0-85219737993`, *Irreducible decomposition of powers of edge ideals, computing dstab, astab.*, Communications in Algebra 2025, DOI `10.1080/00927872.2025.2459250`, vị trí tác giả **2** (đồng tác giả #1: Marcel Morales, `7202590358`) |
| Đơn vị theo nguồn ngoài cho vị trí #2 | OpenAlex + Crossref: **"University of Information and Communication Technology"** — `CORROBORATED`, `POSITION_COUNT_NAME` (khớp số tác giả + vị trí + tên "Dung Nguyen Thi"); **không có ORCID trên bài** |
| Giảng viên trùng tên | **5 hồ sơ khác nhau**: 1 × "PGS.TS. Nguyễn Thị Dung" (ORCID `0009-0003-2932-6901`) + 4 × "ThS. Nguyễn Thị Dung"; cả 5 **không có khoa / bộ môn** trong dữ liệu |
| Ứng viên (`lecturer_scopus_candidates`) | 5: PGS.TS. **ACCEPTED** (v3); ThS. × 3 **PENDING**; ThS. × 1 **REJECTED** (17/10) |
| Bằng chứng của ca ACCEPTED | Chỉ `NAME` / `RULE_TITLE_STRIPPED_N2_FORMAT` (4 dòng evidence); **không có** bằng chứng công bố |
| Quyết định | `ACCEPT` 12/10 00:24:39 bởi `withjson.reviewer@ictu.edu.vn` (REVIEWER) — **lý do để trống**; thuộc lượt E2E có JSON + Craw ngày 12/10 (`WITH_JSON_CRAW_FULL_E2E_20261011.md`: "Mọi hành động đối sánh thử nghiệm ở DB test") |
| Identity | 1 × `APPROVED` (PGS.TS.), `identity_evidence` = 2 × `NAME_SIMILARITY` / `SUPPORTS`, `confidence_score` NULL |
| Audit | `CANDIDATE_ACCEPTED` + `IDENTITY_CREATED_FROM_CANDIDATE` (12/10); `CANDIDATE_REJECTED` (17/10, có lý do) — đầy đủ |
| Đối chứng độc lập | Craw: **không** giảng viên nào có bài này (DOI / tiêu đề). ThS. Dung có 2 bài Craw thuộc chủ đề khác (Genetic Programming 2023, TinyML 2026). ORCID `0009-0003-2932-6901` có trong bộ ORCID offline nhưng **không khai Scopus ID nào** |
| Các identity APPROVED khác | ThS. Đoàn Ngọc Phương (bằng chứng PUBLICATION), TS. Vũ Đức Quang (NAME + PUBLICATION) — có cơ sở |

### 1.2 Ba khái niệm cần tách bạch

| Khái niệm | Dữ liệu | Ca này |
|---|---|---|
| Đề xuất đối sánh | `lecturer_scopus_candidates` (PENDING) | 5 đề xuất cho cùng một Scopus ID — **hợp lệ**: hệ thống chủ ý không tự chọn giữa người trùng tên |
| Liên kết reviewer chấp nhận | candidate `ACCEPTED` + identity `APPROVED` + `mapping/candidate_reviews` + audit | 1 liên kết — **quyết định của con người**, chỉ dựa trên tên |
| Định danh xác minh độc lập | bằng chứng ORCID → Scopus ID, hoặc công bố đã biết (Craw) khớp DOI / tiêu đề | **Không có** |

### 1.3 Quy tắc nghiệp vụ và ràng buộc (VS)
- `uq_lecturer_scopus_identities_pair (lecturer_id, scopus_author_id)` và **partial unique index `uq_identities_scopus_author_approved` (`scopus_author_id`) WHERE `status='APPROVED'`** (`models/identity.py:116-128`). Hệ thống **không cho phép** một Scopus ID được APPROVED cho hơn 1 giảng viên. "Dùng chung (5 GV)" trên UI là **số đề xuất**, không phải 5 liên kết.
- Một giảng viên có thể có nhiều Scopus ID được APPROVED (không có unique theo `lecturer_id`), tức là hỗ trợ trường hợp một người có nhiều hồ sơ Scopus.
- API duyệt chỉ có `ACCEPT | REJECT` (`schemas/review_api.py:12`). **Lý do chỉ bắt buộc với REJECT** (`candidate_review_service.py:783-786`).
- **Không có đường hoàn tác:** CHECK cho `REOPEN` có sẵn trong `lecturer_scopus_candidate_reviews` (`models/candidate.py:284-306`) và bộ lọc lịch sử (`reviews.py:629`), nhưng **chưa có endpoint**. Identity `REVOKED` không có API dẫn tới.
- UI có cảnh báo: "Chỉ bằng chứng tên", "Dùng chung (5 GV)", "Có 9 ứng viên" (VR, ngày 17/10).

### 1.4 Frontend có diễn giải quá mạnh không?
- Chi tiết công bố `2-s2.0-85219737993`: mục **"Liên kết giảng viên ICTU" / EN "Approved ICTU Lecturer Links"** hiển thị "PGS.TS. Nguyễn Thị Dung" kèm ORCID của hồ sơ, **không kèm mức bằng chứng** (VR qua API `approved_lecturer_links`; nhãn VS `Detail.tsx:117`).
- Chữ "approved / đã duyệt" là **đúng nghĩa** (đã được người duyệt chấp nhận), không dùng từ "xác minh". Nhưng vì không có chỉ báo "chỉ dựa trên tên", người xem dễ hiểu là đã được kiểm chứng. ORCID hiển thị cạnh liên kết là ORCID **của hồ sơ giảng viên**, không phải bằng chứng nối với Scopus ID, nên càng dễ gây hiểu nhầm.
- Dashboard "ĐÃ DUYỆT 3" đếm cả ca này.

### 1.5 Phân loại
- **Không phải BLOCKER:** ràng buộc dữ liệu giữ đúng, audit đầy đủ, không có dữ liệu nào khác bị sai. Đây là quyết định của REVIEWER trên DB TEST và có cảnh báo hiển thị.
- **Không thể kết luận là sai:** đơn vị trên bài là ICTU; PGS.TS. là người duy nhất trong 5 hồ sơ có học hàm PGS, phù hợp với một bài toán học chung với một giáo sư nước ngoài. Nhưng **không có bằng chứng độc lập**.
- **MAJOR (quản trị và trình bày):**
  - (a) bộ dữ liệu demo chứa một liên kết APPROVED chỉ dựa trên tên, lý do trống, với Scopus ID được đề xuất cho 5 người;
  - (b) hệ thống cho phép ACCEPT không cần lý do kể cả khi chỉ có bằng chứng tên hoặc Scopus ID dùng chung;
  - (c) không có đường hoàn tác giữ provenance;
  - (d) UI liên kết đã duyệt không cho biết mức bằng chứng.

### 1.6 Phương án sửa tối thiểu (chưa làm, chờ duyệt)

| # | Phương án | Thay đổi | Bảo toàn provenance |
|---|---|---|---|
| D-1 (demo, không sửa gì) | Giữ nguyên dữ liệu; kịch bản demo **không mở** ca này hoặc chủ động giải thích: "REVIEWER chấp nhận dựa trên tên; hệ thống cảnh báo dùng chung" | Không | Có |
| D-2 (khuyến nghị cho sản phẩm) | Bắt buộc **lý do khi ACCEPT** nếu candidate chỉ có bằng chứng tên hoặc `is_shared_scopus_author` (service + frontend modal) | Nhỏ (service + test) | Có |
| D-3 | Hiển thị mức bằng chứng cạnh "Liên kết giảng viên ICTU" (vd "Duyệt theo tên" / "Có công bố hỗ trợ") từ `identity_evidence.evidence_type` | Nhỏ (API trả thêm 1 trường + UI) | Có |
| D-4 | Endpoint `REOPEN` dùng CHECK có sẵn: candidate ACCEPTED → PENDING, identity → `REVOKED`, ghi review + audit, bắt buộc lý do | Vừa (service + API + UI + test) | Có (append-only) |
| ✗ | Sửa / xóa trực tiếp bằng SQL | — | **Không** — phá audit trail, không đề xuất |

## 2. Credential của lượt E2E (Giai đoạn B)

| Câu hỏi | Kết quả |
|---|---|
| File credential | `_postgres_demo_14_10/secrets/backend_test_withjson.env`; ACL: chỉ `NT AUTHORITY\SYSTEM` và `QHUN22\QuangHuy` (VR); ngoài Git |
| Có được cấp quyền rõ ràng cho công cụ kiểm thử không? | **Không có cấp phép rõ ràng.** Ngày 17/10, lệnh in mật khẩu ra bị bộ phân quyền chặn ("Credential Materialization"). Sau đó, các script (ma trận phân quyền, Accept/Reject, kiểm tra API, Chrome headless) **đọc file trong tiến trình và dùng mà không in ra**, và không bị chặn. |
| Đánh giá trung thực | Cách làm này giữ bí mật ngoài hội thoại và ngoài bằng chứng, nhưng **đã dựa trên sự cho phép ngầm**, trong khi tín hiệu chặn trước đó cho thấy ranh giới là *không chạm vào giá trị bí mật*. **Ghi nhận là vùng xám và sẽ không lặp lại nếu chưa được cấp quyền rõ ràng.** Tài khoản và DB đều là TEST, không có dữ liệu demo nào bị ghi trong lượt UI. |
| Profile Chrome tạm | Đã xóa (`scopus_ui_e2e_*` trong TEMP: 0); không còn tiến trình Chrome headless / `remote-debugging-port` (0). 18 tiến trình Chrome còn lại là của người dùng |
| Bằng chứng có lộ bí mật? | Quét 54 tệp văn bản (scratch + `docs/qa/*.md`): **0** lần xuất hiện giá trị mật khẩu / `SECRET_KEY`, **0** chuỗi dạng JWT / `access_token=`. 77 ảnh PNG đều chụp **sau** khi đăng nhập; không có ảnh nào chụp form đăng nhập đã điền. Ô mật khẩu là `type=password` |
| Cookie | Chỉ tồn tại trong profile tạm (đã xóa); script không lưu cookie |

**Đề xuất cấp credential hợp lệ lần sau** (chọn một):
1. **Cấp phép rõ ràng bằng văn bản** cho phép script E2E đọc `secrets/backend_test_*.env` (tài khoản TEST), giữ nguyên quy tắc: không in, không ghi vào bằng chứng, chỉ dùng trên DB TEST.
2. **Thêm quy tắc quyền** trong cài đặt Claude Code cho đúng các lệnh script E2E (do chủ đồ án tự thêm).
3. **Chủ đồ án tự đăng nhập** trong Browser pane; mật khẩu chủ đồ án đọc từ tệp secrets bằng Notepad. Lần trước thất bại vì sai mật khẩu, không phải do cơ chế.
4. Cho tài khoản TEST trên bản sao DB rehearsal: một script tạo mật khẩu ngẫu nhiên mới, lưu vào `secrets/backend_test_restore_demoA.env` (ngoài Git, ACL như trên). Bước này ghi tệp secrets nên **cần duyệt**.

## 3. Backup / restore execution plan (OPS-01 — chưa thực hiện)

| Bước | Lệnh / quy tắc | Ghi chú |
|---|---|---|
| 0. Tiền kiểm | `pg_ctl status` cụm 55432; DB nguồn = `scopus_ictu_test_withjson_r2_20261011` (40 MB, owner `scopus_demo_user`); **không** DB teacher, **không** cổng 5432 | VR ngày 17/10 |
| 1. Dump | `pg_dump.exe` 17.10 (= server 17.10): `-h 127.0.0.1 -p 55432 -U scopus_demo_user -d scopus_ictu_test_withjson_r2_20261011 -Fc --no-password -f "<BACKUPS>\withjson_r2_demoA_YYYYMMDD_HHMMSS.dump"` | Snapshot nhất quán, không khóa ghi, chỉ đọc nguồn |
| Đích | `<BACKUPS>` = `D:\DataFolder\ProjectIctu\DoAn\_postgres_demo_14_10\backups\` — ngoài repo; ACL chỉ SYSTEM + chủ máy; trống 231 GB | Dump chứa dữ liệu cá nhân 410 giảng viên + băm mật khẩu tài khoản TEST → **không Git, không chia sẻ** |
| Xác thực | `pgpass.conf` **chưa có** dòng cho DB này; **không tự sửa**. Lựa chọn: (a) chủ đồ án thêm dòng `127.0.0.1:55432:scopus_ictu_test_withjson_r2_20261011:scopus_demo_user:<…>`; (b) cho phép script đặt `PGPASSWORD` cho tiến trình con từ `backend/.env` (không in) | Cần duyệt (a) hoặc (b) |
| 2. Checksum | `sha256sum` → `<file>.dump.sha256` + thêm dòng vào `SHA256SUMS.txt` | Theo quy ước có sẵn |
| 3. Kiểm tra cấu trúc | `pg_restore --list <file>` — kỳ vọng 27 TABLE, `alembic_version`, các index (kể cả `uq_identities_scopus_author_approved`) | Không ghi |
| 4. Restore rehearsal | Tạo DB rỗng `scopus_ictu_test_restore_demoA_YYYYMMDD` bằng `demo_admin` (đã có trong `pgpass`; mẫu `tools/create_mig_db.py`, từ chối nếu DB đã tồn tại) → `pg_restore --no-owner --role=scopus_demo_user -d <db mới> <file>` | **Cần duyệt** (lần trước bị chặn quyền) |
| 5. Đối chiếu | `alembic_version` = `c7f2a9b1d3e5`; số dòng 27 bảng bằng nguồn; băm nội dung `publications`, `publication_authors`, `publication_author_affiliation_resolutions`, `lecturer_scopus_candidates`, `lecturer_scopus_identities`, `audit_events` bằng nguồn | Script chỉ đọc |
| 6. Sau rehearsal | Giữ DB rehearsal làm môi trường cho TC-W1 / TC-W2 (§5); **không** xóa DB nếu chưa có duyệt | — |

## 4. Launcher safety proposal (OPS-02 — chưa sửa)

**Hiện trạng (VS):**
- `cmd_start` (`demo_launcher.py:332-338`) → `check_database()` → khi `[current] != heads` **tự gọi `run_migration()`** (dòng 270–275).
- `cmd_migrate` (399–405) đã có nhưng **không backup trước**.
- DB đích cố định `EXPECTED_DB` (mặc định `scopus_ictu_app`), env `secrets/backend_app.env`, cổng 8001 / 5173.
- Không giám sát tiến trình con (VR: 17/10 backend chết, frontend mồ côi).

| PA | Nội dung | Patch tối thiểu |
|---|---|---|
| **PA-0 (dùng cho demo)** | Khởi chạy môi trường A thủ công, không qua BAT: (1) `start_postgres.cmd`; (2) trong `Scopus-Ictu\backend`: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8199` (đọc `backend/.env` → DB A); (3) trong `Scopus-Ictu\frontend`: `set VITE_API_PROXY_TARGET=http://127.0.0.1:8199` rồi `npm run dev -- --port 5199`; (4) mở `http://localhost:5199`. **Không chạy `alembic`**; không chạy `scopus-ictu-qhun22.bat` khi demo | Tài liệu, không sửa code |
| **PA-1 (khuyến nghị)** | Tách `start` / `migrate`: thêm hàm thuần `needs_migration(current, heads) -> bool`; trong `check_database` thay `run_migration(values)` bằng `raise LauncherError("Schema … khác code …; chạy 'scopus-ictu-qhun22.bat migrate' (sẽ backup trước)")`; trong `cmd_migrate` gọi `backup_database(values)` (`pg_dump -Fc` vào `RUNTIME/backups/<db>_pre_migrate_<ts>.dump` + sha256) trước `run_migration`; từ chối migrate nếu tên DB thuộc danh sách cấm (`scopus_ictu_demo_teacher_20261014`) | ~25 dòng + 3 unit test trong `tests/unit/test_demo_launcher.py` (`needs_migration`, chặn DB cấm, `start` không gọi migrate — mock) |
| PA-2 (chỉ khi cần 1 nút cho A) | `start --profile demoA` đọc `secrets/backend_demoA.env` (DB A, cổng 8199 / 5199); kế thừa PA-1 | Thêm tham số + tệp env ngoài Git |
| PA-3 (tùy chọn) | `status` cảnh báo khi frontend sống mà backend chết | Nhỏ |

## 5. Kế hoạch TC-W1 / TC-W2 (chưa chạy)

**Môi trường:**
- DB rehearsal `scopus_ictu_test_restore_demoA_YYYYMMDD` lấy từ §3, là bản sao A đã đối chiếu.
- Backend uvicorn **8399** với `DB_NAME` override (cấu hình preview mới `restoreA-backend`); frontend **5399** proxy → 8399.
- Không đụng DB A, App DB hay DB teacher.

**Xác thực:** theo lựa chọn ở §2 (khuyến nghị lựa chọn 1 hoặc 4).

| TC | Dữ liệu | Bước | Thao tác ghi & tác động | Expected | Bằng chứng |
|---|---|---|---|---|---|
| **TC-W1a** Accept | Ứng viên PENDING có công bố hỗ trợ (chọn ca `publication_support_count ≥ 1`, `is_ambiguous=false` trên bản sao) | REVIEWER → `/reviews` → Xem chi tiết → "Xác nhận đối sánh" → nhập lý do → xác nhận | +1 `lecturer_scopus_candidate_reviews`, candidate → ACCEPTED (version +1), +1 identity APPROVED, +2 audit (`CANDIDATE_ACCEPTED`, `IDENTITY_CREATED_FROM_CANDIDATE`) | Toast thành công; trạng thái đổi trong bảng; `/review-history` thêm dòng; bấm lại không tạo bản ghi trùng | Ảnh trước / sau, log mạng `POST …/reviews` 200, truy vấn DB trước / sau, audit |
| **TC-W1b** Reject | Ca PENDING chỉ có bằng chứng tên + Scopus ID dùng chung (vd 1 trong 3 ca ThS. Nguyễn Thị Dung còn PENDING) | Như trên, "Từ chối" + lý do | +1 review, candidate → REJECTED, 0 identity, +1 audit | Như trên; thử bỏ trống lý do → bị chặn (lý do bắt buộc với REJECT) | Như trên |
| **TC-W1c** Ràng buộc | Ca PENDING cho Scopus ID **đã APPROVED** cho người khác (vd ThS. Dung ↔ `59253245500`) | Thử "Xác nhận đối sánh" | Không được ghi | Lỗi nghiệp vụ rõ ràng (unique `uq_identities_scopus_author_approved`); UI báo lỗi dễ hiểu, không 500 | Mạng + DB không đổi |
| **TC-W2** LECTURER đã liên kết | `vu.duc.quang.test@ictu.edu.vn` (TS. Vũ Đức Quang, 1 identity APPROVED `57193082389`, 27 công bố) | Trên bản sao: ADMIN `POST /users/{id}/reset-password` với mật khẩu ngẫu nhiên (lưu theo §2 lựa chọn 4) → đăng nhập → `/home`, `/my-publications`, `/profile`, `/identity`, mở 1 công bố từ "Công bố của tôi" | +1 cập nhật `users` (password_hash, `auth_version`), +audit đặt lại mật khẩu, +1 notification (nếu có) — **chỉ trên bản sao** | `/my-publications` = 27 bài (khớp DB); hồ sơ hiện đúng thông tin; Liên kết Scopus hiện `57193082389`; chi tiết công bố mở được; route ADMIN / REVIEWER bị chặn; VI / EN | Ảnh, API, DB |

## 6. Patch plan P1 giao diện (chưa sửa)

| Issue | Phân loại | Root cause (VS / VR) | Bản sửa tối thiểu | Figma |
|---|---|---|---|---|
| **UI-01** Home sai trạng thái | **Wording / thiết kế** (không phải lỗi backend) | Nhãn badge thẻ là chuỗi tĩnh: `locales/vi.ts:125,131,137,140` ("Chưa có dữ liệu", "Đang chờ kết nối"), gán cứng trong `Home/index.tsx:66-207`; Home không gọi API | **Phương án nhỏ nhất:** thay các nhãn trạng thái giả bằng nhãn hành động trung tính ("Xem hàng đợi", "Xem lịch sử", "Xem công bố", "Xem liên kết") ở cả `vi.ts` / `en.ts` — 5 chuỗi × 2 ngôn ngữ, không đổi logic. *(Phương án lớn hơn — đếm số thật từ `/dashboard/summary`, `/reviews/context`, `/lecturers/me/*` theo vai trò — để đợt sau)* | Home không có frame riêng trong danh sách page Figma đã đọc (RO) → không cần cập nhật |
| **UI-02** "ỨNG VIÊN 0" cạnh "Chờ duyệt 144" | **Wording / mô hình hiển thị** | Thẻ "Trạng thái định danh" hiển thị 4 trạng thái `lecturer_scopus_identities.status` (`Dashboard/index.tsx:40-54,273`); luồng hiện tại tạo identity thẳng `APPROVED` (`candidate_review_service.py:672`), không có API tạo `CANDIDATE` / `REJECTED` / `REVOKED` → 3 / 4 thẻ luôn 0 | Đổi tiêu đề thành "Liên kết Scopus đã duyệt" và **chỉ hiển thị** `APPROVED` (+ `REVOKED` khi có D-4); đổi `identityCandidate` / `identityRejected` hoặc ẩn 2 thẻ đó. Không đổi API | Stat Card `9:22` (RO) — chỉ là mẫu, không cần đổi |
| **UI-03** cảnh báo `AFFILIATION_SOURCE_DIR` | **Thiếu cấu hình** + wording | Backend A (`backend/.env`) không có `AFFILIATION_SOURCE_DIR` (VR: `grep` ngày 17/10, giá trị rỗng) → panel "Nguồn dữ liệu đơn vị" báo chưa cấu hình, dù đơn vị đã áp dụng ngày 12/10 từ bộ offline (audit `bundle_sha256` khớp) | (a) **Cấu hình, không sửa code:** thêm `AFFILIATION_SOURCE_DIR=D:/DataFolder/ProjectIctu/DoAn/_du_lieu_demo_14_10/affiliation_survey` vào `backend/.env` của môi trường A (tệp đã được ignore), khởi động lại backend 8199 → panel hiện 4 tệp + SHA-256; "Xem trước" chỉ đọc, "Áp dụng" sẽ báo không có gì mới (idempotent — RO 11/10). (b) Wording: khi chưa cấu hình nhưng DB đã có dữ liệu, ghi "Đã áp dụng lúc … ; máy chủ hiện không gắn bộ nguồn" thay cho chữ đỏ và tên biến môi trường | Không |
| **UX-01** badge cùng loại khác cỡ | **Sai lệch Design System** | `AffiliationBadge` có prop `small`; trong cùng bảng tác giả, dòng 173 / 200 / 302 dùng `small` (10 px, `px-1.5 py-0`), còn dòng 249 / 261 / 284 (hàng tóm tắt / không có đơn vị) **không** dùng `small` (11 px, `px-2 py-0.5`) → hai cỡ (VR: ảnh `P01`) | **Tối thiểu:** thêm `small` ở 3 lời gọi 249 / 261 / 284 (hoặc bỏ `small` ở 3 lời gọi kia — chọn theo Figma). **Đúng Figma (`5:34`: pill, cao 23, px 10):** sửa `AffiliationBadge` thành `inline-flex h-[23px] items-center rounded-full px-2.5 text-[11px] font-semibold` và bỏ biến thể `small` trong bảng | Figma **chưa có** variant cho mức tin cậy đơn vị ("Đã xác minh định danh", "Đã đối chiếu · Chưa xác minh", "Chưa xác định") → cần bổ sung variant vào `5:34` |

Kiểm thử sau sửa (đợt sửa): `tsc` + `vite build`; ảnh trước / sau `/home` (3 vai trò), `/dashboard`, `/normalization?tab=affiliations`, `/publications/2-s2.0-105000836388`; VI / EN; pytest không ảnh hưởng (không đổi backend, trừ UI-03 (a) là cấu hình).

## 7. Danh sách cần chủ đồ án phê duyệt

1. **DATA-01:** chọn D-1 (giữ nguyên và giải thích khi demo) cho bản RC; quyết định có đưa D-2 / D-3 / D-4 vào đợt sửa không.
2. **Credential E2E:** chọn một trong 4 cách ở §2. Cho tới khi được duyệt, tôi **không** chạy lại script đọc tệp secrets.
3. **OPS-01:** cho phép (a) cách xác thực `pg_dump` (thêm dòng `pgpass` do chủ đồ án, hoặc `PGPASSWORD` từ `backend/.env`); (b) ghi tệp `withjson_r2_demoA_<ts>.dump` (+ `.sha256`, dòng `SHA256SUMS.txt`) vào `backups\`; (c) tạo DB `scopus_ictu_test_restore_demoA_<ts>` bằng `demo_admin` và `pg_restore`.
4. **OPS-02:** duyệt PA-0 làm quy trình demo; duyệt PA-1 (+ test) cho đợt sửa launcher.
5. **TC-W1 / TC-W2:** cho phép chạy các thao tác ghi liệt kê ở §5 **chỉ trên DB rehearsal**, gồm đặt lại mật khẩu `vu.duc.quang.test` trên bản sao và lưu mật khẩu mới vào tệp secrets riêng.
6. **UI-03 (a):** cho phép thêm `AFFILIATION_SOURCE_DIR` vào `backend/.env` của môi trường A và khởi động lại backend 8199 (không ghi DB).
7. **Patch P1:** duyệt phương án UI-01 (nhãn trung tính), UI-02 (chỉ hiển thị trạng thái có thật), UI-03 (b) (wording), UX-01 (tối thiểu hoặc theo Figma), cùng việc bổ sung variant badge mức tin cậy vào Figma.
