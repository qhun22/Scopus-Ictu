# Security Hygiene, Safe Launcher & Remaining Workflow Fixes — PROMPT 10 (17/10/2026)

- **Release:** `v1.0.0-rc.1` vẫn **HOLD**. Đợt này dừng để chủ đồ án và ChatGPT nghiệm thu.
- **Không làm:** rotate / xuất credential; xóa thư mục chứa secrets; migrate DB nghiệp vụ; drop / reset DB; ghi dữ liệu demo; stage, commit, tag, push; REOPEN; R3 / R4.

**Nhãn trạng thái**
- **VERIFIED:** đã chạy và có bằng chứng.
- **PARTIAL:** làm một phần, hoặc kiểm chưa đủ.
- **BLOCKED:** chưa thể làm hoặc kiểm.
- **PROPOSED:** đề xuất, chờ duyệt.

## 0. Baseline & Git safety (VERIFIED)

| Mục | Kết quả |
|---|---|
| HEAD / branch | `237f7bc` / `main` |
| 4 file RC đã stage | blob `fb176d6`, `853c832`, `3b03317`, `0c34a85` không đổi (đầu và cuối phiên) |
| Worktree đầu phiên | sha256 của `git diff` = `a8577530…`, **trùng** manifest run cuối PROMPT 09 (`20261017T202153_p09_backend_unit`) → thay đổi P07 / 08 / 09 còn nguyên |
| Patch | trước: `_postgres_demo_14_10/scratch/p10/baseline_worktree_p10.patch`; sau: `worktree_after_p10.patch` (sha256 `6abb7fac…`); riêng P10: `p10_only_tracked_files.patch` |
| DB A | fingerprint cuối phiên = snapshot nguồn (**IDENTICAL**) |
| DB restore | fingerprint trước = sau phiên (**IDENTICAL**); không ghi |
| DB teacher, App DB | không kết nối, không migrate |

---

## 1. Security incident assessment

### 1.1 Phạm vi

Phương pháp: script `scratch/p10/secret_exposure_assess.py`. Script chỉ in tên khóa, metadata kết nối không bí mật, kết quả boolean và số lượng. Giá trị chỉ nằm trong bộ nhớ. **Không** thử đăng nhập vào cổng 5432 (quy tắc dự án).

| Câu hỏi | Kết quả | Trạng thái |
|---|---|---|
| File | `Scopus-Ictu/.tmp/completion2-a1-audit-read-api/backend/.env`, 1.401 byte, sửa lần cuối 07/10/2026 — bản sao cấu hình backend của một worktree tạm cũ (task "completion2-a1 audit read API") | VERIFIED |
| Git | **không** track, **không** stage, **không** có trong lịch sử (0 commit); nằm dưới `.tmp/` bị ignore (`.gitignore:65 *.tmp`) | VERIFIED |
| Khóa bí mật trong file | `DB_PASSWORD`, `SECRET_KEY`, `TEST_DATABASE_URL` (connection string có mật khẩu) | VERIFIED |
| Credential của dịch vụ nào | PostgreSQL **cổng 5432**, user `scopus_m12_user`, DB `scopus_ictu_acceptance_v2` và `scopus_m12_test`. Cổng 5432 là dịch vụ Windows `postgresql-x64-17` (PID 6260), **khác** cụm demo 55432 | VERIFIED |
| Trùng credential A / restore / App DB / teacher | **Không**: mật khẩu khác mọi credential của cụm 55432 (backend/.env, `backend_test_withjson.env`, `backend_test_restore_demoA.env`, `backend_test_roundtrip.env`); user `scopus_m12_user` **không tồn tại** trên cụm 55432 (catalog `pg_roles`) nên không đăng nhập được vào A, restore, App DB hay teacher | VERIFIED |
| `SECRET_KEY` (khóa ký JWT) | **không** trùng khóa JWT của môi trường A hay các file secrets TEST, nên không dùng được để giả token ở các môi trường đang demo | VERIFIED |
| Credential còn hiệu lực | Có tiến trình đang listen ở 5432, nhưng **không** thử xác thực | **CHƯA RÕ** |
| Phơi nhiễm mạng | Dịch vụ 5432 listen trên **mọi interface** (`0.0.0.0:5432`, `[::]:5432`). Nếu firewall mở cổng này và credential còn hiệu lực, có thể bị truy cập từ mạng LAN. | VERIFIED (listen); firewall CHƯA RÕ |
| Các bản sao khác | mật khẩu DB này xuất hiện trong **28 file**: các `.env` / `.env.r4` và script `.py` cũ trong `Scopus-Ictu/.tmp/` (đều ignore, không track; tổng 27 file `.tmp` chứa ít nhất một giá trị bị lộ), cộng **4 transcript** phiên Claude Code trong hồ sơ người dùng (`%USERPROFILE%\.claude\projects\…\*.jsonl`, gồm cả phiên hiện tại). `SECRET_KEY` xuất hiện trong 23 file. | VERIFIED |
| Repo, docs, bằng chứng QA hiện tại | 0 lần xuất hiện trong mã đang track, `docs/qa/` và `scratch/qa_runs/` (quét 133 file, 9 giá trị bí mật đã biết) | VERIFIED |
| Dấu hiệu dùng ngoài phạm vi | Không có bằng chứng; chưa kiểm log của dịch vụ 5432 (không truy cập) | CHƯA RÕ |

**Kết luận:** sự cố là **lộ trong terminal và transcript cục bộ** của một credential thuộc dịch vụ PostgreSQL 5432 (không phải môi trường demo). Không có bằng chứng xâm nhập; tôi không khẳng định có xâm nhập.

Lưu ý minh bạch: để so sánh "trùng hay không", script đã đọc **trong bộ nhớ** các file secrets `backend_test_restore_demoA.env` và `backend_test_roundtrip.env`, chỉ in kết quả boolean.

### 1.2 Phương án khắc phục (PROPOSED — chủ đồ án thực hiện)

1. **Rotate** mật khẩu `scopus_m12_user` trên dịch vụ 5432, hoặc khóa / xóa role nếu không còn dùng.
   - Phạm vi chỉ là dịch vụ 5432. Cụm 55432 không bị ảnh hưởng.
   - Phụ thuộc cần cập nhật: các worktree cũ trong `.tmp/` (nếu còn dùng) và mọi job / tooling còn trỏ `scopus_m12_test` / `scopus_ictu_acceptance_v2` @5432.
   - Launcher, backup và test của dự án đều dùng 55432 nên **không ảnh hưởng** (`demo_launcher.FORBIDDEN_PORTS = {5432}`; guard test cấm 5432).
2. Kiểm `listen_addresses` / `pg_hba.conf` của dịch vụ 5432. Nếu chỉ dùng cục bộ, giới hạn `listen_addresses='localhost'` và kiểm Windows Firewall cho cổng 5432.
3. Đổi `SECRET_KEY` trong các bản sao `.tmp` nếu worktree đó còn được chạy. Nếu không chạy nữa thì bản chất là dữ liệu tồn đọng.
4. Sau rotate: xác minh kết nối lại bằng tài khoản quản trị của dịch vụ đó, kiểm quyền tối thiểu (role chỉ có quyền trên DB cần thiết).
5. **Dọn bản sao:** xem xét xóa `Scopus-Ictu/.tmp/` (41 worktree tạm cũ) sau khi xác nhận không còn cần. Có thể xóa / làm sạch các transcript `.jsonl` cũ có chứa giá trị. Không tự làm vì cần phê duyệt.
6. Không cần đổi backup hay launcher của demo.

### 1.3 Phòng ngừa tái diễn (PROPOSED + đang áp dụng)

- Không `cat` / `grep` thô trên thư mục có `.env`. Chỉ dùng script trả về tên khóa / boolean (như `secret_exposure_assess.py`).
- Không lưu credential trong JSON evidence. Mọi manifest PROMPT 09–10 có `secrets_stored: false`, kèm quét trùng giá trị sau mỗi run.
- Launcher che giá trị bí mật (`***`) trong mọi dòng in màn hình và log (§2, đã có test).
- `.gitignore` đã chặn `.env*` (trừ `.env.example`), `secrets/`, `*.tmp` (VERIFIED). 3 file `.env.example` đang track không chứa giá trị thật (VERIFIED).
- Không tạo worktree / bản sao `.env` mới trong repo. Đặt cấu hình ngoài repo (`_postgres_demo_14_10/secrets/`).
- Quyền đọc `secrets/` chỉ trong phạm vi được duyệt theo từng phiên và từng công cụ (đã áp dụng trong PROMPT 09–10).

---

## 2. PA-1 — Safe demo launcher (VERIFIED)

**File:**
- `backend/scripts/demo_launcher.py`: +129 / −40, giữ CRLF.
- Test mới: `tests/unit/test_demo_launcher_safety.py`, `tests/integration/test_demo_launcher_migrate.py`.
- **BAT không sửa**: BAT đã gọi `migrate`, và xác nhận tương tác chạy được trong cửa sổ console.

### Đối chiếu với patch PA-1 đã thử

PA-1 (`scratch/launcher_pa1/PA1.diff`) đã có:
- START không migrate;
- chặn DB teacher;
- backup lỗi thì dừng.

PROMPT 10 bổ sung:
1. MIGRATE **không backup / không migrate** khi DB đã ở HEAD.
2. **Xác nhận đúng tên DB** (gõ tương tác hoặc `--confirm <ten_database>`; phải khớp chính xác).
3. Kiểm revision từ chính server (`current_database()`, cổng, địa chỉ) **trước** backup.
4. Thông báo "**Bản sao lưu ĐÃ TẠO nhưng CHƯA kiểm chứng restore**".
5. `pg_dump` không chạy được (`OSError`) → dừng với thông báo, không crash.
6. **Health check fail-fast:** tiến trình backend / frontend do lần chạy này khởi động mà thoát → báo ngay kèm mã thoát, không chờ 60 giây.
7. **Che giá trị bí mật** trong `say()` và `log()`. Mật khẩu chỉ truyền qua biến môi trường `PGPASSWORD`, không nằm trên dòng lệnh.

Giữ nguyên: frontend chỉ báo sẵn sàng khi `/api/v1/auth/me` qua proxy trả 200 / 401.

### Hành vi

| Lệnh | Hành vi |
|---|---|
| START | kiểm môi trường → PostgreSQL demo → kiểm DB và revision (**lệch thì dừng**, hướng dẫn `migrate`) → backend (health, fail-fast) → frontend (health + proxy API) |
| MIGRATE | kiểm cấu hình (host 127.0.0.1, cổng 55432, đúng DB) → **chặn teacher** (trước mọi kết nối) → PostgreSQL → revision từ server → đã ở HEAD thì **thoát, không backup** → xác nhận tên DB → backup + sha256 + cảnh báo chưa kiểm chứng restore → `alembic upgrade head` → kiểm lại revision |

### Test

| Run | Nội dung | Kết quả |
|---|---|---|
| `20261017T210257_p10_launcher_unit` | 8 test cũ + 15 test mới (giả lập): helper; START đúng / lệch revision (không migrate, không khởi động dịch vụ); MIGRATE ở HEAD (không backup); chặn teacher (0 lời gọi); xác nhận sai (cả `--confirm` lẫn nhập tương tác); backup lỗi → dừng, xóa dump dở; thiếu `pg_dump` → `LauncherError`; backup OK → sha256 + cảnh báo; backend chết → báo trong < 5 giây; frontend không proxy được API → không báo thành công; che secret trên màn hình và log | **23 passed** |
| `20261017T210356_p10_launcher_migrate_isolated` | **migrate thật** trên DB TEST cô lập `scopus_ictu_test_pytest_20261011` (allowlist, guard xác minh server trước khi reset schema): dựng ở revision `b5e8d2f1a4c7` (HEAD−1) → START bị từ chối → MIGRATE (backup thật bằng `pg_dump` + sha256 khớp) lên `c7f2a9b1d3e5` → START qua → MIGRATE lần 2 không tạo backup; backup lỗi thật → revision giữ nguyên; xác nhận sai → không đổi; teacher → từ chối, không kết nối; log không chứa mật khẩu | **4 passed** |

**Không** chạy START end-to-end trên App DB / DB A (sẽ khởi động dịch vụ demo ở cổng 8001 / 5173). Đây là known limitation; phần kiểm DB / revision, health và proxy đã test riêng.

---

## 3. W-02 — My Publications → chi tiết công bố (VERIFIED)

### Kiểm tra trước khi sửa (VS)

- Route `/publications/:eid` đã cho phép ADMIN / REVIEWER / LECTURER (RBAC hiện hành).
- API chi tiết cho LECTURER ẩn sẵn provenance và liên kết giảng viên khác.
- API `/lecturers/me/publications` trả `eid` → **không cần đổi RBAC hay API**.

### Sửa đổi

- `MyPublications/index.tsx`: mỗi thẻ có `Link` "Xem chi tiết công bố" / "View publication details".
  - `to=/publications/${encodeURIComponent(eid)}`, với `eid` lấy từ API, cùng quy ước với `/publications`.
  - Kiểu `buttonClass("tonal","sm")` (Figma `9:72`).
  - `aria-label` kèm tiêu đề; `state.from`.
- `Publications/Detail.tsx`: nút quay lại về `/my-publications` ("Quay lại công bố của tôi" / "Back to my publications") khi đến từ trang này; các trường hợp khác giữ nguyên.
- Không đổi owner, matching hay identity links.

### Bằng chứng

Run `20261017T212223_p10_w02_restore_readonly`, **13 / 13 PASS**:
- LECTURER **đã liên kết** `vu.duc.quang.test` trên DB restore, theo quyền chủ đồ án cấp trong phiên.
- Mọi thẻ (20 / 27 ở trang 1) có href = `/publications/<eid>` đúng API.
- Tab tới link: `<a>`, `:focus-visible`, nền `#EBEFF9`, cao 28px, bo 4px.
- Enter mở đúng chi tiết; header "Công bố"; LECTURER không thấy khu vực liên kết / provenance; nút quay lại trở về `/my-publications`.
- EN đúng; mobile không tràn, không cắt chữ.
- 0 request ghi, 0 lỗi API / console, fingerprint DB restore trước = sau.

---

## 4. Lỗi UI độc lập

### 4.1 Phân loại

| Lỗi (nguồn bằng chứng) | Loại | Xử lý | Trạng thái |
|---|---|---|---|
| UI-10: `/imports` 1440px — bảng 1.197 > 1.124px, cột "Thao tác" bị cắt (`ACTOR_UI_ACCEPTANCE` A-04) | sửa tối thiểu | cột "Thao tác" **sticky** mép phải (nền + viền trái); padding ô bảng `px-4` → `px-3`; ô tên tệp tối đa 180px (đã `truncate` + `title`). Bảng 1.150 → **vừa khung**, cột "Trạng thái" không bị che; mobile vẫn thấy cột thao tác. | VERIFIED |
| UI-16: nút bị cắt chữ trên mobile (Dashboard) | đã sửa ở PROMPT 07 | kiểm lại: không cắt | VERIFIED |
| Nút OK / primary AntD không đúng brand (`/reviews`) | sửa tối thiểu | `ConfigProvider` **chỉ bọc trang `/reviews`** (nơi duy nhất dùng AntD): `colorPrimary #3A5FC3`, `colorError #E11D48`, nút bo 6px | VERIFIED |
| Mã kỹ thuật thô ở chi tiết `/reviews` | sửa tối thiểu | `ruleLabels.ts`: 7 rule id, 2 reconciliation, 3 loại tên Scopus → nhãn VI / EN theo ngữ nghĩa `candidate_generator.py`; mã gốc giữ ở tooltip; mã lạ hiện nguyên. Nhãn quy tắc dài hiện bằng chữ có xuống dòng (không dùng badge `nowrap`). | VERIFIED |
| Header chi tiết công bố hiện "Hệ thống" (UI-13 một phần) | sửa tối thiểu | `/publications/:eid` → "Công bố" / "Publications" | VERIFIED |
| VI / EN lệch ở màn hình đang sửa | sửa tối thiểu | EN "Approved ICTU Lecturer Links" → "ICTU Lecturer Links" (khớp VI) | VERIFIED |
| `/tasks` placeholder | quyết định sản phẩm | không đụng | — |
| Data Table, Form, Modal, Card dùng chung; AntD `Button` → `Button` | R3 / R4 | không làm | — |

### 4.2 Regression trình duyệt (môi trường A, chỉ đọc)

| Run | Loại | Kết quả |
|---|---|---|
| `20261017T211026_p10_browser_readonly` | original | 17 / 17 PASS. **Ghi chú:** hai check chưa đủ chặt. Khi xem ảnh, tôi phát hiện cột sticky che một phần cột "Trạng thái" và enum thô `AUTHOR_FULL_NAME` / `PREFERRED_NAME` vẫn hiển thị. Đã sửa code và bổ sung check. |
| `20261017T211248_p10_browser_readonly` | **SUPERSEDED** (`NOTE.txt`) | chạy nhầm script chưa vá: lệnh vá thất bại vì lỗi escape của shell, còn lệnh nối phía sau vẫn chạy. Giữ nguyên, không xóa. |
| `20261017T211423_p10_browser_readonly_rerun` | rerun | 17 PASS / **1 FAIL**: bảng `/imports` còn rộng 1.150 > 1.124px |
| `20261017T211613_p10_browser_readonly_rerun` | rerun (sau khi thu hẹp ô tên tệp) | **18 / 18 PASS**: `/imports` 1440 + 375; header VI / EN; tiêu đề EN; Dashboard mobile; `/reviews` không còn mã thô, nhãn VI / EN; nút primary `rgb(58,95,195)` bo 6px; danger `rgb(225,29,72)`; OK của modal đúng brand; mobile không tràn; LECTURER chưa liên kết vẫn đúng trạng thái; 0 request ghi, 0 lỗi |

---

## 5. Chính sách "giảng viên có nhiều ứng viên" (PROPOSED — chưa sửa D-2)

### Truth table: ứng viên X đang PENDING được xét ACCEPT

| Ứng viên khác cùng **giảng viên** | Ý nghĩa | Hiện tại (đếm mọi trạng thái) | Đề xuất |
|---|---|---|---|
| PENDING | còn cạnh tranh tại thời điểm quyết định | bắt buộc lý do | **bắt buộc** |
| ACCEPTED | giảng viên đã có liên kết định danh đã duyệt với Scopus ID khác (được phép, Case B) — cần nêu vì sao thêm ID thứ hai | bắt buộc | **bắt buộc** |
| REJECTED | lịch sử; đã bị loại, không còn cạnh tranh | bắt buộc | không tính |
| SUPERSEDED | bị thay bởi lần sinh ứng viên mới; không còn hiệu lực | bắt buộc | không tính |

| Ứng viên khác cùng **Scopus ID** | Ý nghĩa | Hiện tại | Đề xuất |
|---|---|---|---|
| PENDING (giảng viên khác) | còn cạnh tranh | bắt buộc | **bắt buộc** |
| ACCEPTED (giảng viên khác) | Scopus ID đã có liên kết đã duyệt → **409 xung đột** trước khi xét lý do | (409) | (409, không đổi) |
| REJECTED / SUPERSEDED | lịch sử | bắt buộc | không tính |

**Đề xuất:**
- Chỉ đếm ứng viên **còn hiệu lực** `{PENDING, ACCEPTED}`.
- `NAME_EVIDENCE_ONLY` giữ nguyên.
- **Đổi đồng thời** số đếm ngữ cảnh mơ hồ hiển thị cho reviewer (`candidate_count_for_lecturer`, `candidate_count_for_scopus_author`, `is_ambiguous`), để điều thấy được và điều server áp dụng không lệch nhau.

**Tác động đo được (SQL chỉ đọc):**

| | DB A (144 PENDING) | DB restore (140 PENDING) |
|---|---|---|
| Có "nhiều ứng viên" (cách cũ / đề xuất) | 113 / 113 | 113 / 113 |
| Có "Scopus ID dùng chung" (cách cũ / đề xuất) | 77 / 77 | 76 / 76 |
| Ứng viên đổi tập điều kiện | **0** | **0** |
| Xung đột 409 sẵn | 3 | 2 |

Hiện chưa có ứng viên REJECTED / SUPERSEDED nào "che" ứng viên khác, nên đề xuất **không đổi kết quả với dữ liệu hiện tại**. Nó chỉ có tác dụng sau các quyết định REJECT về sau.

**Test bị ảnh hưởng nếu được duyệt:**
- Giữ nguyên: `test_lecturer_with_several_candidates_requires_reason`, `test_all_three_triggers_are_reported_together`, `test_shared_scopus_author_requires_reason_even_with_publication_evidence` (đều PENDING).
- Cần thêm: anh / chị em REJECTED → không trigger; SUPERSEDED → không trigger; ACCEPTED cùng giảng viên → trigger.
- `test_review_shared_author_warning` và hiển thị hàng đợi: cập nhật nếu đổi định nghĩa số đếm.

**DỪNG ở hạng mục này để duyệt riêng.**

---

## 6. Regression tổng hợp

| Hạng mục | Kết quả |
|---|---|
| Backend: launcher unit (23) + migrate thật trên DB TEST cô lập (4) | **PASS** |
| Backend: test review / policy | không chạy lại. PROMPT 10 không đổi code `backend/app/` (worktree backend app trùng PROMPT 09, nơi đã 200 passed). |
| Frontend `tsc --noEmit` / `npm run build` | **PASS** / **PASS** (cảnh báo chunk > 500 kB có từ trước) |
| CSS mới | chỉ dùng utility Tailwind sẵn có (`sticky`, `right-0`, `z-[1]`, `border-l`) và token hiện có; **không** đổi `tailwind.config.js`, nên không cần khởi động lại dev server |
| Trình duyệt A (ADMIN / REVIEWER / LECTURER chưa liên kết) | 18 / 18 PASS (§4.2) |
| Trình duyệt restore (LECTURER đã liên kết) | 13 / 13 PASS (§3) |
| Môi trường | 5199 → 8199 → DB A; 5399 → 8399 → DB restore (kiểm cấu hình launch và runtime); 0 request ghi; fingerprint A và restore IDENTICAL; không migrate DB nghiệp vụ |

---

## 7. QA evidence manifest (`_postgres_demo_14_10/scratch/qa_runs/`)

| Run | Loại | evidence | Kết quả |
|---|---|---|---|
| `20261017T210257_p10_launcher_unit` | backend-pytest | original | 23 passed |
| `20261017T210356_p10_launcher_migrate_isolated` | backend-pytest (DB TEST cô lập, có ghi trên DB đó) | original | 4 passed |
| `20261017T211026_p10_browser_readonly` | browser A | original | 17 / 17 (check chưa đủ chặt, xem §4.2) |
| `20261017T211248_p10_browser_readonly` | browser A | original → **SUPERSEDED** (`NOTE.txt`) | 17 / 17 |
| `20261017T211423_p10_browser_readonly_rerun` | browser A | rerun | 17 / 1 FAIL |
| `20261017T211613_p10_browser_readonly_rerun` | browser A | rerun | 18 / 18 |
| `20261017T212223_p10_w02_restore_readonly` | browser restore | original | 13 / 13; fingerprint đầu = cuối |

**Nội dung manifest:** mỗi run có thư mục riêng, không ghi đè. Manifest gồm thời gian, commit SHA, branch, sha256 của `git diff`, môi trường (frontend, backend, DB), loại test, original / rerun (`rerun_of`, `rerun_reason`), checksum từng file, `secrets_stored: false`. Run trình duyệt có `results.json` với **expected / actual / result** cho từng check.

**Đã xóa:** file dump của DB TEST trong run migrate, sau khi assert checksum.

**Run PROMPT 09:** `20261017T202444_p09_restore_write` **giữ nhãn INCOMPLETE**, kèm run xác minh riêng `20261017T202720_p09_restore_write_verify`. Không sửa lại, không tạo thêm quyết định.

---

## 8. Git status

**Stage (không đổi):** 4 file RC.

**Unstaged — PROMPT 10:**
- `backend/scripts/demo_launcher.py`
- `frontend/src/components/common/Header.tsx`
- `frontend/src/pages/Imports/index.tsx`
- `frontend/src/pages/MyPublications/index.tsx`
- `frontend/src/pages/Publications/Detail.tsx`
- `frontend/src/pages/ApprovalQueue/index.tsx`

**Untracked mới:**
- `backend/tests/unit/test_demo_launcher_safety.py`
- `backend/tests/integration/test_demo_launcher_migrate.py`
- `frontend/src/pages/ApprovalQueue/ruleLabels.ts`
- báo cáo này

**Còn lại:** thay đổi PROMPT 07 / 08 / 09 giữ nguyên.

### Đề xuất chia commit (chỉ đề xuất, không thực hiện)

1. **Launcher safety (PA-1):** `backend/scripts/demo_launcher.py`, `tests/unit/test_demo_launcher_safety.py`, `tests/integration/test_demo_launcher_migrate.py`.
2. **MyPublications navigation (W-02):** `pages/MyPublications/index.tsx`, `pages/Publications/Detail.tsx` (phần nút quay lại).
3. **Independent UI fixes:** `pages/Imports/index.tsx`, `components/common/Header.tsx`, `pages/ApprovalQueue/index.tsx` (ConfigProvider + nhãn quy tắc), `pages/ApprovalQueue/ruleLabels.ts`, `pages/Publications/Detail.tsx` (nhãn EN).
4. **Review policy:** không có thay đổi trong PROMPT 10.

Các nhóm của PROMPT 07–09 (Design System, D-2 / D-3) nên là các commit riêng, trước các commit trên. Không gộp với 4 file RC đang stage.

---

## 9. Backlog R3 / R4

| Nhóm | Phạm vi |
|---|---|
| R3 | nút còn tự định nghĩa ở Imports, Normalization, Lecturers, AuditLogs, ReviewHistory, Header, Login, Search, Profile, Identity, ConfirmModal / TextConfirmModal / DuplicateImportDialog; AntD `Button` / `Modal` ở `/reviews` → `Button` dùng chung (màu đã đúng brand nhờ `ConfigProvider`) |
| R4 | Data Table (`9:41`), Stat Card (`9:25`), Input (`9:9`) dùng chung; các `rounded-*` còn lại; cột sticky và độ rộng cột trong Data Table chung |
| Khác | UI-13 (các tiêu đề header còn lại), UI-14 (khóa 3 giây khi đổi ngôn ngữ), UI-15, UI-18; `/tasks` (quyết định sản phẩm) |

## 10. Vấn đề còn chặn Release Candidate

| # | Vấn đề | Trạng thái |
|---|---|---|
| 1 | Rotate / khóa credential `scopus_m12_user` trên dịch vụ 5432, kiểm listen / firewall, dọn bản sao `.tmp` và transcript | **BLOCKED** (chờ chủ đồ án) |
| 2 | Quyết định chính sách đếm ứng viên mơ hồ (§5) | **PROPOSED** (chờ duyệt) |
| 3 | Commit các nhóm thay đổi PROMPT 07–10 theo kế hoạch | chờ chủ đồ án (không tự commit) |
| 4 | Full regression backend (~1.047 test) và START launcher end-to-end trên App DB trước khi tag | đề xuất cho bước release |
| 5 | Migration App DB lên HEAD (nếu App DB chưa ở HEAD) | chỉ qua `scopus-ictu-qhun22.bat migrate`, có xác nhận và backup; **không** làm trong lượt này |

---

**Dừng tại đây** để chủ đồ án và ChatGPT nghiệm thu PROMPT 10.
