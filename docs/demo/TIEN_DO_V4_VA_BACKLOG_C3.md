# TIẾN ĐỘ V4 VÀ BACKLOG COMPLETION-3 (C3)

> Soạn ngày **09/10/2026** (Task 17, V4). **Chỉ đọc và lập kế hoạch — chưa triển khai bất kỳ code nào của C3 / F3 / R1 / P3.**
> Mọi kết luận có dẫn chứng (đường dẫn tệp, nhánh hoặc commit). Chỗ không có nguồn ghi **`CHƯA ĐỦ BẰNG CHỨNG`**; suy luận được ghi rõ là suy luận.
> Phương pháp: đọc `README.md`, `docs/freeze/*`, `docs/adr/*`, `docs/progress/C3_A*.md` (đọc từ các nhánh bằng `git show`), thân commit (`git show -s`), nhãn nhánh, `_postgres_demo_14_10/evidence/TASK*_SUMMARY.md`, các tệp patch ngoài Git. **Không** `git apply` patch nào; **không** checkout nhánh C3 vào `main`.

---

## 1. Trạng thái hiện tại (đối chiếu thực tế ngày 09/10/2026)

| Hạng mục | Giá trị |
|---|---|
| Local `main` (đầu Task 17) | `f88c022` (Task 16). Nhánh làm việc Task 17: `task17/hoan-thien-vai-tro` (fast-forward vào `main` khi gate đạt) |
| `origin/main` | `f492818` (= đóng băng Completion-2 A6) — **local `main` hơn remote 21 commit trước Task 17**; chưa push (theo quy định) |
| Stash | 2 stash còn nguyên (`WIP lecturer UI ngoài scope M2.6B`, `codex-group-a-verification-2026-10-03`) |
| Worktree | còn nguyên (`Backend-Localhost-14-10`, `Integration-*`, `Scopus-Ictu-A2`, `.tmp/*`) |
| Backend tests | **784 passed** (đầu Task 17) → xem số cuối ở `BAO_CAO_KIEM_THU_CHUC_NANG.md` chương 19 |
| Frontend | `tsc --noEmit` PASS; `vite build` PASS |
| Teacher DB | 411 / 660 / 1.207 / 2.751 / 4.147 / 40 PENDING / 0 APPROVED / 0 review; fingerprint 20 bảng không đổi; `users` = 3 (2 ADMIN, 0 REVIEWER, 1 LECTURER) |
| CI GitHub | `.github/workflows/ci.yml` tồn tại; kết quả CI cho các commit sau Completion-2 **chưa được kiểm chứng** (xem 6) |

---

## 2. Toàn bộ milestone đã hoàn thành (trên `main`)

| Mốc | Nội dung | Bằng chứng nguồn | Trạng thái |
|---|---|---|---|
| **M0 / M1** | Nền tảng database: PostgreSQL, Alembic, schema đầy đủ, CHECK, audit | `README.md` bảng "Implemented scope"; `docs/freeze/M1.0-*.md`, `M1.2-*.md`; commit `7ca09b4`, `3026d78` | ĐÃ HOÀN THÀNH (frozen) |
| **M2.1** | Đăng nhập JWT cookie, phân quyền 3 vai trò | README; `docs/adr/` | ĐÃ HOÀN THÀNH |
| **M2.2** | Quản trị tài khoản: sửa hồ sơ, đổi vai trò, khóa/mở khóa, đặt lại mật khẩu, thông báo | README; commit `2166ba8`; test `test_account_admin_and_notifications.py` | ĐÃ HOÀN THÀNH |
| **M2.3** | Dữ liệu giảng viên: nhập, hoàn tác, snapshot nguồn, phát hiện trùng tên | README; commit `b6842d1` | ĐÃ HOÀN THÀNH |
| **M2.4** | Vòng đời nhập CSV Scopus: SHA-256, tiến trình, hủy, lịch sử, xóa an toàn | README; commit `f602abe`, `96b33b0` | ĐÃ HOÀN THÀNH |
| **M2.5A** | Dataset giảng viên ICTU (410) + pipeline nhập | README; `data/lecturers/` | ĐÃ HOÀN THÀNH |
| **M2.6A/B** | Chuẩn hóa công bố (EID canonical) + bóc tách tác giả | commit `c2822e4`, `576ffd6`, `46d53ed` | ĐÃ HOÀN THÀNH |
| **M2.7** | Bộ sinh ứng viên + bằng chứng công bố + lưu bền + dịch vụ/API/UI duyệt | `docs/freeze/m2.7-freeze.md` (tip `b413b57`); nhánh `m27a/*`, `m27b/*` | ĐÃ HOÀN THÀNH (frozen, FF) |
| **M2.8** *(định danh dự án, `M28_ID_IS_OFFICIAL=false`)* | Tiêu thụ định danh đã duyệt: hồ sơ, liên kết Scopus, công bố của tôi | `docs/freeze/m2.8-freeze.md` (tip `280de04`) | ĐÃ HOÀN THÀNH (frozen) |
| **Completion-1** | Công bố (API + UI), tra cứu tổng hợp, xuất công bố | `docs/freeze/completion1-freeze.md` (tip `486ee2f`) | ĐÃ HOÀN THÀNH (frozen); PR #6/#7/#9/#11 OPEN/DRAFT trên GitHub |
| **Completion-2** | Nhật ký kiểm toán (API + UI), lịch sử review, dashboard (API + UI) | `docs/freeze/completion2_dashboard_audit_history_freeze.md` (tip `f492818`) | ĐÃ HOÀN THÀNH (frozen); PR #13–#22 OPEN/DRAFT |
| **Completion-3** | Đánh giá chất lượng đối sánh (xem mục 6) | nhánh `completion3/*`, `docs/progress/C3_A*.md` (**chỉ trên nhánh**) | **KHÔNG nằm trong `main`**; CHƯA NGHIỆM THU |

> Cảnh báo tên gọi: `README.md` mục "Future / incomplete milestones" còn ghi M2.7, M2.8, M3, M4 là *chưa làm* — **đã lỗi thời** (M2.7/M2.8 đã frozen; "M3 Human review workflow" thực chất là M2.7B; "M4 Publications UI/Dashboard/Audit" thực chất là Completion-1/2). Đây là việc sửa tài liệu, xem backlog mục 9.

---

## 3. Task 04–17 (giai đoạn localhost demo 14/10)

Nguồn: thân commit, `_postgres_demo_14_10/evidence/TASK*_SUMMARY.md`, `manifests/`, báo cáo Task 15–16 trong `docs/demo/`. Cột "Ghi chú" nêu rõ khi thiếu tài liệu.

| Task | Nội dung chính | Bằng chứng | Ghi chú |
|---|---|---|---|
| 04 | *(trước seed + E2E)* | — | **CHƯA ĐỦ BẰNG CHỨNG** chi tiết trong repo/evidence |
| 05 / 05C | Seed 2 tài khoản demo; E2E: nhập JSON/CSV, chuẩn hóa; audit CSV 660 dòng/1.207 ID/2.751 vị trí; Craw 328 liên kết/48 giảng viên | `TASK05_SUMMARY.md`, `AUDIT_05C_SUMMARY.md` | Dry-run đầu: 40 ứng viên |
| 06R | JSON giảng viên: nhập/sửa/xuất/khôi phục round-trip | commit `f03d23c`; `_du_lieu_demo_14_10/v2/README_QA.md` | `tel`, Google Scholar không lưu DB |
| 07 | Cổng khôi phục JSON (UUID bền); nhập CSV vào teacher: 660/1.207/2.751 | `TASK07_SUMMARY.md` | |
| 08 | CLI sinh và lưu ứng viên (40 PENDING, idempotent) | `TASK08_SUMMARY.md`; commit `9334a18` | Review rehearsal trên DB test |
| 09 | Nạp công bố đã biết từ Craw (328 → 327) + API cờ dùng chung | `TASK09_SUMMARY.md`; commit `55c899f` | 6 ứng viên có bằng chứng công bố |
| 10 / 11 | Alignment affiliation theo tác giả + migration `a9c2e4f71b30` + nhập 5.502 resolution/4.147 dòng/217 tổ chức | `TASK11_SUMMARY.md`; commit `4bced46`, `360f334`, `3142380` | Quy tắc VERIFIED/CORROBORATED/UNRESOLVED |
| 12 | Hiển thị affiliation theo từng tác giả + cảnh báo dùng chung trên UI | commit `b90ab53`, `3fccb80` | |
| 13 | Backend localhost trên Python 3.12, tài liệu chạy thử | commit `e2f2d01`, `95244be`; `BACKEND_LOCALHOST_14_10.md` | |
| 14 / 14.5 | Công cụ tạo ADMIN demo; chuẩn hóa thông điệp commit; kiểm kê/di chuyển hiện vật | commit `d27682f`; `_quan_ly_do_an/manifests/` | |
| 15 / 15.1 | BAT khởi động một lần, dọn cuối | commit `d51a055` (merge); `scopus-ictu-qhun22.bat` | BAT đã được người dùng kiểm tay |
| 15.2 | Sửa môi trường pytest (TEMP/TMP) → 780 passed, 1 skipped | báo cáo Task 15.2 (không nằm trong repo) | |
| 16 | Kiểm thử chức năng thật + 3 tài liệu hướng dẫn/kịch bản/báo cáo; sửa 5 lỗi | commit `69cffd3`…`f88c022` | 784 passed |
| **17** | Ba vai trò (REVIEWER E2E trình duyệt), sửa CSV/Error Boundary/tìm kiếm/ngày giờ/vai trò, đối soát tài liệu, kiểm kê C3 | commit trên `task17/hoan-thien-vai-tro`; tài liệu này | Xem `BAO_CAO_KIEM_THU_CHUC_NANG.md` chương 17–19 |

---

## 4. Chức năng — tình trạng triển khai

**Có trên giao diện (đã BROWSER_PASS ở Task 16/17):** đăng nhập/đăng xuất/phiên · Trang chủ · Tổng quan · Giảng viên (danh sách, thêm, sửa, xóa, tài khoản, đổi vai trò) · Nhập JSON giảng viên (preview, nhập, hoàn tác) · Nhập CSV Scopus · Chuẩn hóa công bố/tác giả · Công bố + affiliation theo tác giả · Tra cứu · Duyệt đối sánh (ACCEPT/REJECT) · Lịch sử review · Nhật ký hệ thống · Cổng giảng viên (hồ sơ, công bố của tôi, liên kết Scopus) · chuyển VI/EN · REVIEWER (Task 17).

**Chỉ có API/CLI (không có nút giao diện):** sinh ứng viên (`generate_matching_candidates.py`) · nạp công bố đã biết Craw (`ingest_craw_known_publications.py`) · nạp affiliation (`import_author_affiliations.py`) · bootstrap ADMIN/seed users · crawl/xây dataset giảng viên · các script Completion-3 · quản lý đợt nhập (archive/restore/cancel — qua API) · Xuất JSON công bố (nút có, nhưng chỉ ADMIN).

**Chưa có / còn thiếu UI:** trang Tác vụ (`/tasks` giữ chỗ) · trang Người dùng độc lập (tài khoản nằm trong Chi tiết giảng viên) · biểu đồ Trang chủ · giao diện chạy matching và theo dõi tiến trình · giao diện nạp OpenAlex/Crossref · Khoa/Bộ môn giảng viên (dữ liệu nguồn trống).

**Lỗi/giới hạn còn lại sau Task 17:** `updated_at` của giảng viên không đổi khi sửa (L8) · toast EN hiện nội dung tiếng Việt từ máy chủ (L11) · teacher DB chưa có tài khoản REVIEWER · `README.md` lỗi thời · chưa có CI chứng minh cho các commit sau Completion-2 · remote GitHub thiếu 21+ commit (chưa push).

---

## 5. Những phần KHÔNG cần làm lại

M0–M2.8, Completion-1 và Completion-2 (đã frozen và đã chạy thật), pipeline nhập/chuẩn hóa 660/1.207/2.751, ứng viên 40 PENDING + bằng chứng công bố, affiliation theo tác giả (migration + nhập + UI), BAT một lần nhấp, môi trường pytest 3.12, ba tài liệu demo của Task 16 (chỉ cập nhật), REVIEWER E2E (Task 17).

---

## 6. COMPLETION-3 (C3) — định nghĩa theo nguồn gốc

### 6.1. Hai nghĩa của "C3" — không được lẫn
1. **`C3-01 … C3-15` trong `docs/freeze/M1.0-AUTHORITATIVE-FREEZE-PACK-RESOLVED.md`** là *số thứ tự quyết định/ràng buộc schema* (ví dụ C3-01: `eid` UNIQUE; C3-12: `UNIQUE (publication_id, scopus_author_id)`). **Không liên quan** tới Completion-3.
2. **Completion-3** = chuỗi nhánh `completion3/a1 … a3` + `docs/progress/C3_A1/A2/A3_*.md` về **đánh giá chất lượng truy xuất ứng viên đối sánh** (matching quality evaluation). Đây là nghĩa dùng trong tài liệu này. **Không** phải milestone "M3" của README.

### 6.2. Phạm vi (theo `C3_A1/A2/A3` đọc từ nhánh)
Đo xem bộ sinh ứng viên *có truy xuất được* cặp đúng "giảng viên ↔ Scopus author" hay không (độ phủ truy xuất), dựa trên **nhãn do con người xác nhận** cho một **nhóm mẫu 50/410 giảng viên** chọn trước bằng thuật toán băm có hạt giống (`SHA256_SEED_RANK_V1`, seed `C3-A3-ICTU-PRIMARY-2026-V1`). Không xếp hạng, không chấm điểm, không chỉnh luật matching; không đổi code production; không migration; không frontend.

| Slice | Nhánh (đầu) | Nội dung | Số tệp |
|---|---|---|---|
| **A1** | `completion3/a1-reference-evaluation-scaffold` (`e502e71`) | Hợp đồng CSV nhãn tham chiếu, bộ đánh giá truy xuất thuần (`evaluation.py`), script validate/evaluate, test | 7 tệp / 2.790 dòng |
| **A2** | `completion3/a2-human-review-package` (`a1e761c`) | Gói rà soát thủ công: `candidate_review.csv`, phiếu gán nhãn trống, manifest (`review_package.py`, CLI build) | thêm 5 tệp |
| **A3 – Phase 1** | `…/a3-matching-quality-evaluation` (`4a805e5`, `387aea0`) | Công cụ đánh giá có kiểm chứng + cohort 50 đã khóa + cổng nguồn gốc fail-closed | |
| **A3 – Commit #1** | `completion3/a3-commit1-candidate` (`bf2eaf4`) `[CANDIDATE — CHƯA NGHIỆM THU]` | Cổng DB đánh giá (`scopus_c3_eval_v1`), fingerprint đầu vào v1, re-render gói rà soát | |
| **A3 – P1** | `ci/c3-a3-p1-source-dump-88e7a3c`, `…/a3-matching-quality-evaluation` (`34f9cbd` → `480c819` → `1d85486` → `88e7a3c`) | Bộ điều phối dump snapshot nguồn (`eval_source_dump.py`, `dump_c3_eval_source.py`), **chỉ code + test mock**, không gọi `pg_dump` thật | tổng nhánh: 21 tệp / ~10.500 dòng |

### 6.3. Quy ước P0–P3, F, R trong A3 (suy ra từ `C3_A3_matching_quality_evaluation.md` và thân commit)
- **P0–P3 = các pha chuẩn bị dữ liệu đánh giá**: **P0** khảo sát (đã đóng); **P1** mã nguồn điều phối dump (có, test mock); **P2** dựng/restore DB đánh giá (**NO-GO**, chỉ xét sau CI của P1); **P3** dump thật (cần role chỉ `SELECT`, thông tin DBA qua kênh riêng, môi trường SQLAlchemy chạy được; bị chặn bởi B2/B3/B4).
- **F1, F2** = *finding* của rà soát P1: đã sửa ở `1d85486` (báo lỗi dọn artifact, dọn staging metadata).
- **R4, R5, R6** = *review item* của P1: đã sửa ở `480c819` (cùng đường dẫn archive/metadata, ghi metadata atomic, vòng đời artifact); phần dư R6 sửa ở `88e7a3c`.
- **F3, R1 (và R2, R3)**: **`CHƯA ĐỦ BẰNG CHỨNG`**. Tìm trong mã, commit, tài liệu, patch, DOCX không thấy định nghĩa. Suy luận (chưa xác nhận): R1–R3 là các mục rà soát vòng trước khi có commit `34f9cbd`; F3 là finding thứ ba của vòng rà soát sau `1d85486`. **Cần người dùng/ChatGPT cung cấp báo cáo rà soát gốc** (nơi các mã này được định nghĩa) trước khi coi chúng là backlog.
- Tên "A3 P1 R4/R5/R6" đối chiếu trực tiếp với tên tệp patch ngoài Git `p1_f1f2_fix_1d85486.patch`, `p1_r4r5r6_fix_480c819.patch`, `p1_r6residual_fix_88e7a3c.patch`, `c3_p1_commit_34f9cbd_full.patch` ⇒ các patch này **chỉ là bản sao** của commit đã có trên nhánh; **không áp dụng**.

### 6.4. Kiểm tra độc lập (đọc, không sửa)
Chạy test của nhánh A3 trong worktree `.tmp/completion3-a3-matching-quality-evaluation` (không chạm `main`, DB giả, `--noconftest`): `test_matching_evaluation.py`, `test_matching_review_package.py`, `test_matching_quality_evaluation.py`, `test_c3_eval_source_dump.py` ⇒ **396 passed, 1 skipped (symlink Windows)**. Khớp với con số trong thân commit (67/105/173…).
Không có CI Linux nào được xác nhận cho các commit này (tài liệu ghi `NOT_AVAILABLE_AT_COMMIT_TIME`; nhánh `ci/c3-a3-p1-source-dump-88e7a3c` đã đẩy lên GitHub để chạy CI nhưng **kết quả chưa được ghi lại** trong repo).

---

## 7. Bảng backlog C3 / F3 / R1 / P3

| Mã | Yêu cầu gốc | Bằng chứng nguồn | Code / commit đã có | Tests | Trạng thái | Còn thiếu | Ưu tiên |
|---|---|---|---|---|---|---|---|
| **C3-A1** | Hợp đồng nhãn tham chiếu + bộ đánh giá truy xuất | `docs/progress/C3_A1_*.md` (nhánh `completion3/a1…`) | `e502e71` (+2 commit sửa), nhánh có trên origin | trong 396 passed | ĐÃ CÓ CODE, CHƯA NGHIỆM THU (không merge vào `main`) | Rà soát độc lập, CI Linux, quyết định merge | Trung bình (sau demo) |
| **C3-A2** | Gói rà soát thủ công có provenance | `docs/progress/C3_A2_*.md` | `89164cf`, `a1e761c` | trong 396 passed | ĐÃ CÓ CODE, CHƯA NGHIỆM THU | Sinh gói thật chỉ sau khi có DB đánh giá | Trung bình |
| **C3-A3 Phase 1** | Công cụ đánh giá + cohort 50 khóa + cổng nguồn gốc | `docs/progress/C3_A3_*.md` §1–7 | `387aea0`, `4a805e5` | trong 396 passed | ĐÃ CÓ CODE, CHƯA NGHIỆM THU | Nhãn người; pin fingerprint | Trung bình |
| **C3-A3 Commit #1** | Cổng DB `scopus_c3_eval_v1`, fingerprint v1 | §"Commit #1" | `bf2eaf4` `[CANDIDATE — CHƯA NGHIỆM THU]` | có | HOÀN THÀNH MỘT PHẦN | **Commit #2: pin `EXPECTED_INPUT_FINGERPRINT_SHA256`** (hiện `None` = chặn đánh giá); dựng DB thật | Cao nếu tiếp tục C3 |
| **P0** | Khảo sát nguồn dump | §"A3 P1" ("P0 closes the survey") | — | — | ĐÃ HOÀN THÀNH (đóng) | — | — |
| **P1** | Bộ điều phối dump snapshot (code, test mock) | §"A3 P1" | `34f9cbd`, `480c819`, `1d85486`, `88e7a3c`; nhánh CI trên origin | 105 P1 + 173 + … | ĐÃ CÓ CODE, CHƯA NGHIỆM THU | CI Linux; rà soát độc lập cuối; quyết định chấp nhận | Trung bình |
| **P2** | Dựng + restore DB đánh giá | §"A3 P1" ("P2 … NO-GO") | chưa có | — | CHƯA TRIỂN KHAI (NO-GO) | Chỉ xét sau CI của P1 | Thấp→Trung bình |
| **P3** | Dump thật từ nguồn | §"A3 P1" ("P3 (real dump) needs …") | chưa có | — | ĐANG BLOCKED | Role `SELECT`-only; thông tin DBA kênh riêng; môi trường SQLAlchemy; B2/B3/B4 | Thấp (cần quyết định) |
| **F1, F2** | Finding rà soát P1 | thân commit `1d85486` | `1d85486` | `TestF1…`, `TestF2…` | ĐÃ HOÀN THÀNH (trên nhánh) | — | — |
| **R4, R5, R6 (+dư)** | Review item P1 | thân commit `480c819`, `88e7a3c` | `480c819`, `88e7a3c` | `TestR4/5/6…` | ĐÃ HOÀN THÀNH (trên nhánh) | — | — |
| **F3** | *(không rõ)* | **không tìm thấy** | — | — | **CHƯA ĐỦ BẰNG CHỨNG** | Báo cáo rà soát gốc | Cần quyết định |
| **R1 (R2, R3)** | *(không rõ)* | **không tìm thấy** | — | — | **CHƯA ĐỦ BẰNG CHỨNG** | Báo cáo rà soát gốc | Cần quyết định |
| **Nhãn người 50/50** | Xác nhận nhãn độc lập cho cohort | §12 "Next Gate" mục 4 | — | — | CHƯA TRIỂN KHAI (cần con người) | Người xác nhận | Cao nếu tiếp tục C3 |
| **Đánh giá chính thức (Phase 2)** | Chạy đánh giá có nhãn | §9 ("Official evaluation: NOT_RUN") | — | — | CHƯA TRIỂN KHAI | Sau Commit #2 + nhãn | Cao nếu tiếp tục C3 |
| **PR/CI GitHub** | CI Linux cho nhánh Completion-1/2/3 | `docs/freeze/*` ("OPEN/DRAFT") | `.github/workflows/ci.yml` | — | CẦN QUYẾT ĐỊNH | Ghi nhận kết quả CI; quyết định merge/PR | Sau demo |

**Không có việc nào của Task 06–16 thay thế C3**: C3 là đánh giá chất lượng (đo), còn Task 06–16 là hoàn thiện sản phẩm demo (nhập/chuẩn hóa/affiliation/UI/BAT/kiểm thử). Duy nhất có liên quan: Task 08–09 *tạo* 40 ứng viên + 6 bằng chứng công bố — chính là đối tượng mà C3 sẽ *đo*.

---

## 8. Lộ trình

### 8.1. Trước 14/10 (chỉ việc ảnh hưởng trực tiếp buổi demo)
1. Nhấp đúp BAT → kiểm tra `PHAN MEM SAN SANG`; diễn tập đủ kịch bản trên teacher UI (chỉ đọc) một lần.
2. Quyết định: có tạo tài khoản REVIEWER trên teacher hay chỉ trình bày bằng ảnh (mục 10, câu 1).
3. In/chuẩn bị ảnh chụp dự phòng (`_quan_ly_do_an/evidence/task16|17/screenshots`).
4. **Không** thao tác ghi nào trên teacher; **không** bấm Xuất JSON.
5. (Khuyến nghị) Sao lưu working tree bằng bundle/`pg_dump` mới nếu có phiên bản thay đổi.

### 8.2. Sau 14/10
| Thứ tự | Việc | Ghi chú |
|---|---|---|
| 1 | **Push an toàn lên GitHub** (cần quyết định) + mở PR/CI cho Task 06–17 | Remote đang thiếu 21+ commit; CI chưa chứng minh trên Linux |
| 2 | Sửa `README.md` (milestone lỗi thời) + hợp nhất ghi chú dự án | Việc nhỏ |
| 3 | Quyết định C3: tiếp tục (Commit #2 pin fingerprint → dựng DB đánh giá → nhãn 50/50 → Phase 2) hay hoãn | Cần định nghĩa F3/R1 trước |
| 4 | Giao diện còn thiếu: chạy matching/theo dõi tiến trình (thay `/tasks`), nạp affiliation, biểu đồ Trang chủ | Không làm lại những gì đã PASS |
| 5 | Chất lượng dữ liệu: Khoa/Bộ môn giảng viên, affiliation OpenAlex/Crossref cập nhật, `updated_at` | |
| 6 | Báo cáo tốt nghiệp: ERD, use case, kiến trúc, mô tả thuật toán; **slide + video bảo vệ** | Tận dụng ADR + freeze docs |
| 7 | Dọn nợ kỹ thuật: Error Boundary đã có; thêm test giao diện tự động | |

---

## 9. Danh sách việc còn lại (backlog tổng hợp)

1. Push + CI (mục 8.2-1) · 2. README lỗi thời · 3. C3 (A1–A3, P2, P3, nhãn, đánh giá) · 4. F3/R1 chưa định nghĩa · 5. REVIEWER trên teacher · 6. `updated_at` giảng viên · 7. toast EN · 8. UI cho matching/affiliation · 9. trang Tác vụ/Người dùng · 10. biểu đồ Trang chủ · 11. Khoa/Bộ môn · 12. tài liệu báo cáo tốt nghiệp, slide, video · 13. dọn các stash/WIP **chỉ khi được duyệt** (không làm trong Task 17).

---

## 10. Quyết định cần người dùng xác nhận

1. **Tài khoản REVIEWER trên teacher DB?** Teacher hiện chỉ có 2 ADMIN + 1 LECTURER. Nếu cần minh họa trực tiếp, cần **phê duyệt ngoại lệ ghi** cho đúng một bước bootstrap (chỉ `users` + `audit_events`; backup trước; kiểm tra danh tính DB; idempotent; so fingerprint tách nhóm). Mặc định Task 17: **không làm**.
2. **Chính sách vai trò mới**: ADMIN không tự đổi vai trò của mình và không hạ ADMIN cuối cùng (409). Đồng ý giữ?
3. **CSV không có cột EID bị từ chối ngay khi nhập** (trước đây nhập thô). Đồng ý giữ?
4. **Tìm kiếm không phân biệt dấu** (chỉ tra cứu/danh sách; không ảnh hưởng matching). Đồng ý giữ?
5. **C3**: tiếp tục sau 14/10 hay hoãn? Nếu tiếp tục: ai là người xác nhận nhãn 50/50 và có cung cấp được báo cáo định nghĩa **F3/R1** không?
6. **Push GitHub** khi nào và theo cách nào (PR từng slice hay fast-forward `main`)?
7. README: cập nhật bảng milestone ngay hay gộp vào đợt viết tài liệu tốt nghiệp?

> Mọi mục trên là **đề xuất**, không phải quyết định đã được duyệt.
