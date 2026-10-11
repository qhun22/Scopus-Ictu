# Báo cáo kiểm toán Git và commit cục bộ an toàn — 12/10/2026

**Không push.** Không dùng `git add .`/`-A`, `commit -am`, `reset`, `clean`, `stash`, `checkout .`, `restore .`, `--no-verify`, `--amend`, `rebase`. Mọi commit stage bằng danh sách tệp cụ thể. Kết quả quét bí mật không bảo đảm tuyệt đối; báo cáo này không tuyên bố "100% không rủi ro".

## A. Trạng thái trước khi commit

| Mục | Giá trị |
|---|---|
| Repo | `D:/DataFolder/ProjectIctu/DoAn/Scopus-Ictu` (gốc xác nhận bằng `rev-parse --show-toplevel`) |
| Nhánh / upstream | `main` → `origin/main` (`https://github.com/qhun22/Scopus-Ictu.git`) |
| HEAD cũ | `2652dc05653710a324a250fb5511c2c148d010c5` |
| Chưa push sẵn | `main` đã **trước `origin/main` 32 commit** (cũ, chưa đẩy); sau nhiệm vụ này là 45 |
| Staged từ trước | 0 |
| Modified (tracked) | 51 |
| Untracked (`-uall`, đã mở thư mục) | 384 |
| Deleted / renamed | 0 |
| Stash | 2: `stash@{0}` WIP lecturer UI ngoài scope M2.6B, `stash@{1}` codex-group-a-verification — **không đụng** |
| Ghi đồng thời | không có `index.lock`, không tiến trình git, số mục ổn định 435 qua hai lần đọc; vẫn có nhiều worktree khác của các nhánh khác (`.tmp/*`, `Integration-*`…) nhưng không ghi vào worktree này |
| Git identity | đã cấu hình sẵn (`Quang Huy Truong`), không đổi cấu hình; không có hook |

### Giải thích 435 so với 32
- **435 = 51 sửa + 384 tệp mới** (VS Code đếm từng tệp, `git status` mặc định chỉ hiện 72 mục vì gộp thư mục).
- **32 mục** là phần thay đổi **riêng của nhiệm vụ NO-JSON/WITH-JSON** (23 sửa + 9 mới). Ngoài ra còn:
  - **28 tệp sửa** thuộc các nhiệm vụ trước chưa commit (nhập/xuất giảng viên kèm tài khoản, sửa `source_title`, hộp thoại/nút bấm, reset hệ thống, i18n…);
  - **~335 tệp tài liệu thiết kế** `docs/design/` (sơ đồ, ảnh render, prototype, ảnh QA);
  - **31 tệp** `docs/qa/` và `docs/planning/` (5 báo cáo, 1 kế hoạch, **25 ảnh chụp giao diện**).
- Số hiển thị ở Source Control **không** phải số thay đổi riêng của nhiệm vụ gần nhất.

## B. Phân loại

| Nhóm | Tệp | Quyết định |
|---|---|---|
| Mã nguồn backend/frontend (51 sửa + 18 mới) | 69 | **Đã commit** (7 commit chức năng) |
| `.gitignore` | 1 | **Đã commit** (thêm `*.dump`, `*.dump.sha256`, `.env.*`, giữ `!.env.example`) |
| Thiết kế `docs/design/` (kể cả ảnh render, prototype minh họa, CSV từ điển/ma trận) | 335 | **Đã commit** (4 commit) |
| Báo cáo QA đã rà soát | 3 | **Đã commit** |
| **Chưa commit — NEEDS REVIEW** | 28 | xem dưới |

**Giữ nguyên tại chỗ, không stage (28 tệp):**
| Tệp | Lý do |
|---|---|
| `docs/qa/WITH_JSON_CRAW_FULL_E2E_20261011.md`, `docs/qa/SCOPUS_TWO_MODE_ACCEPTANCE_20261011.md` | nêu **tên giảng viên thật** kèm quyết định duyệt/từ chối thử, Scopus ID và ORCID của giảng viên |
| `docs/planning/KE_HOACH_V4_HOAN_THIEN_DO_AN_TRUOC_14_10.md` | chứa email và tên giảng viên thật |
| 25 ảnh `docs/qa/{affiliation_ui,csv_only_e2e,nojson_full_e2e,source_title}_20261011/*.jpg` | ảnh giao diện chạy thật, hiện tên tác giả/công bố từ CSV thật, email tài khoản test; chưa đánh giá quyền chia sẻ |

**Không bao giờ nên commit (đã ở ngoài repo hoặc bị ignore, xác nhận không có trong commit mới):** `.env`, `backend/.env`, `_postgres_demo_14_10/secrets/*`, `*.dump` (kể cả bản sao lưu WITH-JSON), `data/scopus/*.csv` (ignored), `ictu_lecturers_*.json`, `Craw/output/`, bộ khảo sát OpenAlex/Crossref/ORCID, `venv`/`node_modules`/`dist`, `__pycache__`, log.

## C. Kiểm tra bảo mật

**Phương pháp (cục bộ, không gửi dịch vụ ngoài, không in giá trị):** quét mẫu khóa riêng, `AKIA`, `ghp_`, JWT, URI cơ sở dữ liệu có mật khẩu, gán `PASSWORD/SECRET/TOKEN`; quét tên tệp nguy hiểm; kích thước > 1 MB; symlink/submodule (`mode 120000/160000`: không có); đối chiếu **email, ORCID và tên đầy đủ trong JSON giảng viên thật** với mọi tệp văn bản sắp commit; xem trực tiếp 10/96 ảnh `qa_screenshots` và 6 tệp đại diện.

| Kết quả | Chi tiết |
|---|---|
| Khóa riêng / token / JWT / AWS / GitHub PAT trong dòng thêm mới | **0** |
| Tệp tên nguy hiểm trong commit mới | 0 (ba `.csv` trong `docs/design` là từ điển dữ liệu, FR/NFR, ma trận RBAC — tài liệu, không phải dữ liệu nguồn) |
| Tệp > 1 MB | 0 (lớn nhất 546 KB) |
| Mẫu "mật khẩu" bị gắn cờ | đều là hằng kiểm thử tổng hợp (`MatKhau@12345`…), URI giả `u:p@…`, **tên biến môi trường** (`DEMO_BOOTSTRAP_ADMIN_PASSWORD`) hoặc giá trị CI giả đã có trong lịch sử |
| Email/ORCID giảng viên thật trong mã/tài liệu đã commit | **0** |
| Trùng **tên** giảng viên | 5 tệp prototype HTML (`s02,s05,s06,s09,s13`) trùng 2–3 tên phổ biến (ví dụ "Nguyễn Thị Dung"); nội dung là dữ liệu minh họa (đã xem hàng/ảnh: SĐT, Scopus ID giả, nhãn "DỮ LIỆU MINH HỌA") → coi là trùng ngẫu nhiên, **ghi nhận mức thấp** |
| Đường dẫn cục bộ | một số tài liệu nêu `D:\DataFolder\ProjectIctu\DoAn\…`; `docs/qa` nêu **tên** tệp bí mật (`backend_test_*.env`, `pgpass`) nhưng **không có giá trị** |
| Tài khoản | `admin@ictu.edu.vn`, `e2e.admin@ictu.edu.vn` xuất hiện trong báo cáo truy vết (tài khoản demo/test) |
| Mã có chủ đích nhạy cảm | `exporter.py` có thể xuất băm Argon2 mật khẩu trong tệp xuất JSON (tệp xuất là bảo mật; không có tệp xuất trong repo); `system.py` là endpoint xóa dữ liệu (ADMIN + cụm xác nhận, xóa cả audit) |
| `.env.example` đã tracked | 3 tệp chỉ có giá trị mẫu |

**Vấn đề thuộc lịch sử (không rewrite, không xoay khóa):**
1. `data/lecturers/ictu_lecturers.json` (410 giảng viên, **410 email công vụ**, tên, hồ sơ nguồn) và `data/lecturers/raw/ictu_lecturers_archive_snapshot.html` **đã được commit từ trước và nằm trong `origin/main`** (commit `b6842d1`). Chỉ loại khỏi commit mới không giải quyết được; cần quyết định riêng (dữ liệu từ trang công khai của trường nhưng là hồ sơ cá nhân).
2. Tệp CSV Scopus thật `data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv` tồn tại trong **commit checkpoint cục bộ** thuộc `refs/agents/*` (84 ref, **không có trên remote**). `git push --all` hoặc `--mirror` sẽ đẩy chúng — **không dùng**; chỉ đẩy `main` (và chỉ khi đã duyệt).
3. 32 commit cũ chưa push (`origin/main..main`, 87 tệp): đã quét dòng thêm, không có bí mật; không có tệp nhạy cảm kiểu dump/.env/CSV.
4. Nội dung hai stash chưa được kiểm tra (không push stash theo mặc định).

## D. Các commit cục bộ (13, theo thứ tự)

| # | SHA | Tên commit | Tệp | Kiểm tra |
|---|---|---|---|---|
| 1 | `10ddab4` | Cập nhật quy tắc loại trừ tệp sao lưu và cấu hình cục bộ khỏi Git | 1 | `check` sạch |
| 2 | `e4c2426` | Sửa tên nguồn xuất bản của công bố Scopus theo cột Source title | 4 | 90 test pass tại commit |
| 3 | `40193c0` | Hoàn thiện nhập và xuất dữ liệu giảng viên kèm tài khoản, nhận biết tệp trùng | 13 | 393 test pass tại commit |
| 4 | `821c748` | Hoàn thiện giao diện nhập dữ liệu, hộp thoại xác nhận và bộ nút bấm thống nhất | 13 | `tsc` sạch |
| 5 | `84d185c` | Bổ sung chức năng đặt lại dữ liệu hệ thống có xác nhận bằng văn bản | 5 | `tsc` sạch; `router.py` chỉ stage phần `system` |
| 6 | `2ccfe2d` | Cho phép giảng viên chưa liên kết hồ sơ tra cứu công bố ở chế độ chỉ đọc | 17 | 81 test pass; **`tsc` lỗi 1** (xem E) |
| 7 | `de58ee3` | Bổ sung quy trình đối chiếu đơn vị theo tác giả cho quản trị viên | 12 | 32 test pass; `tsc` sạch |
| 8 | `0ce7bbe` | Giải thích nguyên nhân khi hàng đợi duyệt đối sánh đang trống | 6 | 8 test pass; `tsc` sạch |
| 9 | `f29f635` | Hoàn thiện tài liệu phân tích yêu cầu, quy trình nghiệp vụ và kiến trúc hệ thống | 29 | whitespace cuối tệp (cosmetic) |
| 10 | `9e346e5` | Bổ sung thiết kế cơ sở dữ liệu: ERD, sơ đồ lớp, từ điển dữ liệu và ràng buộc | 53 | — |
| 11 | `a5a9f3b` | Bổ sung Use Case, ma trận phân quyền API và thiết kế xác thực | 120 | — |
| 12 | `1731bd6` | Hoàn thiện thiết kế giao diện, prototype minh họa và hồ sơ bàn giao Figma | 133 | xem F |
| 13 | `2720ba3` | Bổ sung báo cáo kiểm thử luồng Scopus chỉ có CSV và truy vết nguồn tệp nhập | 3 | — |
| 14 | (commit chứa báo cáo này) | Bổ sung báo cáo kiểm toán Git trước khi đẩy lên GitHub | 1 | — |

Tổng 13 commit chức năng/tài liệu: 408 tệp (30.810 dòng thêm, 966 dòng xóa); 0 tệp bị xóa/đổi tên; 0 commit rỗng. Mỗi commit đều có trailer `Co-Authored-By`. Tên commit tiếng Việt, không dùng tiền tố tiếng Anh.

**Tệp trộn nhiều nhiệm vụ (không tách theo hunk):** `Normalization/index.tsx` và `AuthorAffiliations.tsx` (chứa cả sửa đổi cũ và tab/dòng bằng chứng mới) nằm ở commit 7; `Detail.tsx` nằm ở commit 6; `lecturers.py`, `scopus_import_service.py`, i18n nằm ở commit 3/4. Đã tách đúng `router.py` (hai phần khác nhau thuộc commit 5 và 7).

## E. Kiểm thử và toàn vẹn

| Kiểm tra | Kết quả |
|---|---|
| `compileall` backend (app, scripts, tests, alembic) | OK |
| Alembic | **một head** `f6a1b2c3d4e5`; đồ thị hợp lệ |
| Backend toàn bộ (chạy lại hôm nay, DB test dùng một lần `scopus_ictu_test_pytest_20261011`) | **880 passed** |
| Frontend `tsc --noEmit`, `vite build` (ra thư mục tạm) tại HEAD | sạch / thành công |
| Từng commit (worktree tạm, đã gỡ; `node_modules` nối bằng junction rồi gỡ junction, thư mục gốc còn nguyên 151 mục) | `import app.main` OK ở 6 commit backend; test liên quan pass; `tsc` OK ở 4/5 commit frontend |
| **Lỗi tại commit trung gian `2ccfe2d`** | `Detail.tsx` dùng prop `authors` của `AffiliationSummaryBar`, định nghĩa mới nằm ở `AuthorAffiliations.tsx` thuộc commit `de58ee3`. HEAD và mọi commit sau đều sạch. **Không sửa lịch sử**; khi `git bisect` hoặc `revert` cần xử lý hai commit này cùng nhau |
| Link nội bộ tài liệu | 15 link kiểm tra, 15 hỏng — cùng một tệp có sẵn (`TASK20B_R1_OFFLINE_DESIGN_REPORT.md` dùng đường dẫn `ui/prototype/…` tương đối sai); không do commit này gây ra, chưa sửa |
| `git diff --cached --check` | sạch ở mọi commit mã; chỉ cảnh báo khoảng trắng cuối dòng/dòng trống cuối tệp ở tài liệu sinh tự động |
| Cảnh báo `LF will be replaced by CRLF` | do `core.autocrlf=true` trên Windows; không chặn commit |
| Kết nối App DB / teacher DB | chỉ **đọc**; App DB: 660/1.207/2.751, băm công bố–tác giả–liên kết **không đổi** so với trước nhiệm vụ; teacher DB 411 giảng viên; demo 5173/8001 vẫn chạy (PID 8000/3948) |

## F. Kiểm tra sau commit

- `git status`: chỉ còn 28 tệp untracked đã liệt kê ở B (không sửa tệp tracked nào chưa commit).
- Stash: 2 mục còn nguyên. Không có thao tác push (`reflog` không có push); `origin/main` vẫn `f492818…`, không fetch.
- Không có tệp cấu hình/dump/CSV nguồn/JSON giảng viên trong 13 commit; 0 khớp mẫu khóa bí mật trong dòng thêm.
- Ghi chú chất lượng đã phát hiện sau khi commit (không sửa lịch sử):
  1. commit 12 ghi "prototype HTML tĩnh **15** màn hình" nhưng thực tế có **12** màn hình (17 tệp gồm CSS, index, shared);
  2. tài liệu cơ sở dữ liệu/Use Case/RBAC (commit 10–11) phản ánh lược đồ **trước** migration `f6a1b2c3d4e5` nên cần đồng bộ;
  3. 1 tệp tài liệu cũ có link tương đối sai.

## G. Mức sẵn sàng đẩy lên GitHub

| Hạng mục | Đánh giá |
|---|---|
| `10ddab4`, `e4c2426`, `40193c0`, `821c748`, `2ccfe2d`, `de58ee3`, `0ce7bbe`, `f29f635`, `9e346e5`, `a5a9f3b`, `2720ba3` | **SAFE TO PUSH** về bí mật/dữ liệu (đã quét; có ghi chú chức năng bên dưới) |
| `84d185c` (reset hệ thống) | **NEEDS REVIEW** về chức năng: endpoint xóa toàn bộ dữ liệu và audit, chỉ có cụm xác nhận `ICTU`, không có chốt môi trường; đề nghị người phụ trách xem trước khi công khai |
| `1731bd6` (thiết kế giao diện) | **NEEDS REVIEW** nhẹ: mới xem 10/96 ảnh và 6 prototype; có 5 prototype trùng tên phổ biến |
| 28 tệp chưa commit | **DO NOT PUSH** cho tới khi bạn quyết định |
| Lịch sử: `data/lecturers/ictu_lecturers.json` trong `origin/main`; CSV thật trong `refs/agents/*` | **NEEDS REVIEW riêng** (không rewrite theo yêu cầu) |
| 32 commit cũ chưa push | **NEEDS REVIEW**: đã quét tự động, chưa xem tay |

**Khuyến nghị:** chưa push cho tới khi bạn xem mục B (28 tệp), C.1–C.2 và `84d185c`. Khi push, chỉ `git push origin main`, tuyệt đối không `--all`/`--mirror`/`--tags` với `refs/agents`.

## H. Việc cần bạn quyết định
1. Có commit 2 báo cáo QA nêu tên giảng viên thật (có thể che tên) và `KE_HOACH_V4` (có email giảng viên) không?
2. 25 ảnh QA chạy thật: giữ ngoài Git, che dữ liệu, hay commit?
3. Có xử lý `data/lecturers/ictu_lecturers.json` đã nằm trong `origin/main`? (đề nghị bàn riêng; cần quyết định về lịch sử.)
4. Có giữ endpoint `/system/reset` ở nhánh sẽ công khai không?
5. Có áp dụng migration `f6a1b2c3d4e5` lên App DB/teacher DB không (hiện chưa).
