# Restore Rehearsal & Actor Workflow Acceptance — Scopus-ICTU (17/10/2026)

Release `v1.0.0-rc.1`: **HOLD**. Code nền `237f7bc` + 6 file UI đã sửa (unstaged); 4 file RC đã stage giữ nguyên blob.
Không sửa code sản phẩm, không commit / tag / push.
Mọi thao tác ghi đều **chỉ** vào DB restore, theo phê duyệt cụ thể của chủ đồ án trong phiên này: (1) tạo DB + `pg_restore`; (2) TC-W1 qua UI; (3) đặt lại mật khẩu tài khoản TEST trên DB restore.

Bằng chứng (có dữ liệu cá nhân, **ngoài repo**):
- `_postgres_demo_14_10/scratch/` (script, fingerprint JSON).
- `scratch/ui_e2e_20261017/tc_w1/`, `…/tc_w2/` (ảnh + `results_tc_w*.json`).

## 1. Restore rehearsal — **PASS**

| Bước | Kết quả |
|---|---|
| B1 tiền kiểm | Dump `withjson_r2_demoA_20261017_144128.dump` — `sha256sum -c` OK; DB nguồn A **trùng** snapshot lúc backup (fingerprint 14 bảng); DB đích chưa tồn tại; cụm 55432 = PG17; `demo_admin` superuser (pgpass có sẵn), `scopus_demo_user` không CREATEDB; `pg_restore` không chạy alembic |
| B2 phê duyệt | Chủ đồ án duyệt cụ thể: DB `scopus_ictu_test_restore_demoA_20261017`, cụm 127.0.0.1:55432, `demo_admin` tạo DB, `scopus_demo_user` restore, dump trên, xử lý lỗi = dừng & giữ nguyên (không drop) |
| Tạo DB | `CREATE DATABASE … OWNER scopus_demo_user ENCODING 'UTF8' TEMPLATE template0 LC_COLLATE 'C' LC_CTYPE 'C'` + `REVOKE ALL … FROM PUBLIC` (script kiểm tra cổng, data_directory, phiên bản, tên DB chưa tồn tại) |
| `pg_restore` | `--no-owner --role=scopus_demo_user --exit-on-error` → exit 0, stderr rỗng |
| Đối chiếu (không chỉ dựa vào exit code) | Alembic `c7f2a9b1d3e5` = nguồn; 27 / 27 bảng; **số dòng 27 bảng giống hệt**; **md5 nội dung 14 bảng nghiệp vụ giống hệt** (publications 660, publication_authors 2.751, scopus_authors 1.207, lecturers 410, candidates 149, candidate_reviews 5, identities 3, identity_evidence 21, resolutions 5.502, affiliations 4.147, organizations 217, known_publications 327, users 8, audit_events 22); 100 index, 187 constraint, partial unique `uq_identities_scopus_author_approved … WHERE status='APPROVED'` có mặt |
| Quyền | ACL DB đích `{scopus_demo_user=CTc/scopus_demo_user}` = nguồn (không rộng hơn); owner `scopus_demo_user` |
| Sau backup | DB nguồn không thay đổi kể từ lúc backup → không có "thay đổi hợp lệ sau backup" cần phân biệt |

## 2. Môi trường TEST cô lập (VR)

- Backend **8399** (preview `restoreA-backend`, `DB_NAME` override) → `pg_stat_activity` xác nhận **chỉ** nối `scopus_ictu_test_restore_demoA_20261017`; `/health` 200.
- Frontend **5399** (`VITE_API_PROXY_TARGET=http://127.0.0.1:8399`) → log 8399 nhận request đi qua 5399.
- Thêm 2 cấu hình preview cục bộ vào `.claude/launch.json` (không commit).

## 3. TC-W1 — REVIEWER (`withjson.reviewer@ictu.edu.vn`, UI thật qua Chrome headless, DB restore)

| ID | Expected | Actual | Kết quả | Bằng chứng |
|---|---|---|---|---|
| **W1a ACCEPT** — `2da60549…` TS. Trần Quang Quý ↔ `60214163500` (bằng chứng `DOI_EXACT` / Craw, không mơ hồ, không dùng chung) | Mở chi tiết, xem bằng chứng, xác nhận 2 bước, toast thành công; candidate ACCEPTED; 1 identity APPROVED kèm evidence; audit; lịch sử | Chi tiết A–E (D: "DOI_EXACT · RULE_KNOWN_PUBLICATION_DOI_EXACT", DOI 10.1007/978-3-032-18162-6_5); modal "Xác nhận quyết định ACCEPT" → "Xác nhận ACCEPT"; toast "**Thành công — Đã xác nhận đối sánh.**"; `POST …/reviews` **200** `{candidate_status: ACCEPTED, candidate_version: 2, resulting_identity_id: 63f11977…, idempotent: false}`; DB: identity APPROVED + `identity_evidence` `DOI_EXACT`; audit `CANDIDATE_ACCEPTED` + `IDENTITY_CREATED_FROM_CANDIDATE`; `/review-history` dòng "Chấp thuận … TS. Trần Quang Quý" | **PASS** | `W1a_1…3.png`, `results_tc_w1.json` |
| W1a lý do | "Nhập lý do theo yêu cầu hiện tại" | Contract hiện tại: ACCEPT không yêu cầu lý do, và **modal ACCEPT không có ô lý do** (`ApprovalQueue/index.tsx:797-819`) → lịch sử ghi "—" | Đúng contract hiện tại; ghi nhận cho D-2 (W-01) | `W1a_2_confirm_modal.png` |
| **W1b REJECT** — `8c5c5510…` ThS. Nguyễn Thị Dung ↔ `59253245500` (chỉ tên, dùng chung 5 GV) | Bắt buộc lý do; không tạo identity; lịch sử + audit | Modal REJECT: nút "Xác nhận REJECT" **bị vô hiệu** khi chưa có lý do; nhập lý do → **200** `{REJECTED, version 3, resulting_identity_id: null}`; DB: không thêm identity; audit `CANDIDATE_REJECTED` có lý do; lịch sử "Từ chối … lý do TC-W1b…" | **PASS** | `W1b_1…4.png` |
| **W1c Xung đột** — `9ad02db0…` ThS. Nguyễn Thị Dung ↔ `59253245500` (đã APPROVED cho PGS.TS.) | Không tạo liên kết trùng; phản hồi dễ hiểu; unique giữ; không audit sai | `POST` **409** `SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER`; banner + toast "**Dữ liệu có xung đột** — Tác giả Scopus này đã được xác nhận cho một giảng viên khác. Không thể tự động thử lại quyết định."; candidate giữ **PENDING v2**; 0 review, 0 identity, 0 audit mới; truy vấn "APPROVED trùng Scopus ID" → rỗng | **PASS** | `W1c_1…2.png` |
| **W1d Idempotency** | Gửi lặp đúng request ACCEPT không tạo bản ghi mới | Replay từ trang (cùng cookie, cùng `observation_id` / `candidate_version`) → **200** `idempotent: true`, **cùng** `review_id 83e43ad0…` | **PASS** | `results_tc_w1.json` |

**Delta DB restore sau W1 (fingerprint):** `candidate_reviews` 5 → 7; `identities` 3 → 4; `identity_evidence` 21 → 22; `audit_events` 22 → 25; `candidates` 149 (nội dung đổi do 2 trạng thái). Không có thay đổi nào khác. Console: 0 lỗi.

## 4. TC-W2 — LECTURER đã liên kết (`vu.duc.quang.test@ictu.edu.vn`, DB restore)

**Chuẩn bị (được duyệt):**
- Script xác minh 8399 chỉ nối DB restore rồi mới để ADMIN TEST gọi `POST /users/{id}/reset-password` → 200 (`version` 2).
- Mật khẩu ngẫu nhiên lưu `secrets/backend_test_restore_demoA.env` (ACL: SYSTEM + chủ máy; không in, không Git).
- **Tài khoản trên DB A không bị chạm.**

| ID | Kiểm tra | Actual | Kết quả |
|---|---|---|---|
| W2-01 | Đăng nhập form | role LECTURER, `linked: true` | PASS |
| W2-02 | `/home` | Nhãn trung tính "Xem thông tin / Xem công bố / Xem liên kết"; 0 nhãn giả | PASS |
| W2-03 | `/my-publications` | **27** công bố (= API `total: 27` = DB), 38 trích dẫn, 0 thiếu trích dẫn, 1 định danh đã duyệt; phân bổ 2026 / 2025 / 2024 = 18 / 4 / 5 | PASS |
| W2-04 | Liên kết sang chi tiết công bố từ danh sách | **Không có liên kết** (thẻ chỉ hiển thị EID dạng chữ; `MyPublications/index.tsx` không có `Link` / `navigate`) | **PARTIAL** (W-02) |
| W2-05 | `/profile` | Đúng hồ sơ TS. Vũ Đức Quang, ORCID, URL kho lưu trữ; trường thiếu → "Chưa cập nhật" (EN "Not available") | PASS |
| W2-06 | `/identity` (Liên kết Scopus) | `57193082389` "Đã phê duyệt", biến thể tên; danh sách bằng chứng **lặp ~18 dòng mã thô** `DOI_EXACT / SUPPORTS` cùng thời điểm | PASS (chức năng) / UX W-03 |
| W2-07 | Chi tiết công bố của mình (`2-s2.0-105020674369`, mở bằng URL) | Tiêu đề, 6 tác giả, vị trí #6 "Vu, Duc-Quang" — "Đã xác minh định danh" + ORCID; **ẩn** "Nguồn dữ liệu & truy vết" và "Liên kết giảng viên ICTU" với LECTURER (API: `provenance` rỗng, `approved_lecturer_links` rỗng) | PASS (đúng phân quyền) |
| W2-08 | Route bị chặn | `/reviews`, `/dashboard`, `/lecturers`, `/users` → `/home` | PASS |
| W2-09 | VI / EN | Đổi EN + F5: `lang=en`, 0 chuỗi tiếng Việt lọt ở `/my-publications`, `/profile` | PASS |
| W2-10 | Mobile 375 px | `/my-publications`, `/profile` không tràn ngang | PASS |
| W2-11 | Ghi ngầm | UI tự gọi `POST /notifications/{id}/read` (thông báo do lần đặt lại mật khẩu sinh ra) — **hành vi thiết kế** (`NotificationContext.tsx:107-133`), ghi vào DB restore | Ghi nhận W-04 |

## 5. Bảo toàn

| Đối tượng | Kết quả |
|---|---|
| DB A | Fingerprint cuối phiên **= snapshot lúc backup** (không đổi) |
| DB teacher, App DB | **0** kết nối từ 14:39 (log PostgreSQL) |
| Cổng 5432 | Không dùng |
| Git index | 4 blob RC không đổi; 6 file UI không đổi trong phiên |
| Bí mật | Quét 87 tệp bằng chứng: 0 giá trị mật khẩu / `SECRET_KEY` |
| Chrome headless | Đã dừng, profile tạm đã xóa |
| Còn lại | DB `scopus_ictu_test_restore_demoA_20261017` (bản sao có dữ liệu cá nhân, ACL như nguồn) + server 8399 / 5399 — giữ để kiểm thử tiếp; **xóa DB cần duyệt riêng** |

## 6. Phát hiện mới (chưa sửa)

| ID | Mức | Mô tả | Sửa tối thiểu đề xuất |
|---|---|---|---|
| W-01 | P2 (gắn D-2) | Modal xác nhận ACCEPT không có ô lý do → ACCEPT qua UI luôn không có lý do | Thêm ô lý do (bắt buộc theo điều kiện D-2) vào modal ACCEPT |
| W-02 | P2 | "Công bố của tôi" không liên kết sang chi tiết công bố | Bọc tiêu đề thẻ bằng `Link to={/publications/${eid}}` |
| W-03 | P2 | `/identity` lặp bằng chứng, mã thô `DOI_EXACT / SUPPORTS` | Gom theo loại ("Trùng DOI × 17", "Khớp tên × 1"), dịch nhãn |
| W-04 | Info | Đăng nhập tài khoản có thông báo chưa đọc sẽ ghi trạng thái "đã đọc" | Ghi vào hướng dẫn demo / tài liệu ("xem" có thể ghi trạng thái thông báo) |
| W-05 | P3 | Modal xác nhận hiện mã thô "ACCEPT" / "REJECT" (tiêu đề và tag) | Dùng nhãn "Chấp nhận" / "Từ chối" |
| W-06 | P2 (gộp UI-17) | Mục D của chi tiết ứng viên in UUID nội bộ ("Nguồn: id: … kind: lecturer_known_publication …") | Ẩn UUID, hiển thị "Công bố Craw đã biết" + tiêu đề / DOI |
| (đã biết) | P2 | UI-13: header chi tiết công bố "Hệ thống" | — |

## 7. Kết luận và đề xuất

**TEST-01 — đóng theo phạm vi đã thực thi:**
- ADMIN / REVIEWER / LECTURER chưa liên kết (17/10, DB A, chỉ đọc).
- REVIEWER Accept / Reject / xung đột / idempotency **qua UI** (DB restore).
- LECTURER **đã liên kết** (DB restore).

Ngoài phạm vi / còn lại:
- Trạng thái "không có ứng viên" trên UI (cần DB không có ứng viên).
- UI DB rỗng (M2).
- Loading state Dashboard đo đúng cách.
- W-02 (liên kết từ "Công bố của tôi").

**Đề xuất tiếp theo (chờ duyệt):**
1. **D-2** (contract tại `REMEDIATION_VERIFICATION_20261017.md` §5) + **W-01**: backend kiểm lý do có điều kiện + ô lý do trong modal ACCEPT; test unit / integration; kiểm UI trên DB restore.
2. **D-3**: trường `evidence_basis` + nhãn "Duyệt theo tên / Có công bố hỗ trợ".
3. **PA-1**: áp patch + 7 test vào repo, kèm tinh chỉnh (bỏ qua backup khi đã ở head) và 4 kiểm thử còn thiếu (chạy trên DB restore / DB TEST lệch revision).
4. **Backlog Design System:**

   | Nhóm | Nội dung |
   |---|---|
   | Button | Chốt 36 / 40 px, 13 / 14 px; chuyển nút chính sang helper |
   | Badge / Tag | Mở rộng chuẩn pill 23 px cho `ReviewHistory`, `ImportStatusBadge`, AntD `Tag`; source badge gọn |
   | Radius | Token; LECTURER 16 px → chuẩn |
   | Table | Bảng tràn 1440 px ở `/imports`, `/lecturers`, `/audit-logs`; cột thao tác |
   | Form | Placeholder mật khẩu; validation |
   | Modal | AntD vs `ConfirmModal`; font; mã thô; UUID |
   | Responsive | Nút header Dashboard; bảng `/reviews` mobile |

   Cùng với đó là W-02, W-03, W-05, W-06, UI-12, UI-13, UI-14, UI-15, UI-18.
5. **Dashboard edge cases:** DASH-01 (nhãn "Có đơn vị công tác", chưa hiển thị 3 mức), DASH-02 (lấp năm trống), DASH-03 (miền giá trị năm), DASH-04 / UI-08 (màu trùng), UI-09 ("Retracted"), loading state, DB rỗng (M2).
6. **Kế hoạch commit theo nhóm (chờ duyệt, chưa thực hiện):**
   - (a) `docs(qa)`: 4 file RC đã stage + 6 báo cáo QA 17/10.
   - (b) `fix(ui)`: UI-01 / UI-02 / UI-03 (`locales/vi.ts`, `en.ts`, `types.ts`, `Dashboard/index.tsx`, `AffiliationsTab.tsx`).
   - (c) `fix(ui)`: UX-01 (`AuthorAffiliations.tsx`).
   - (d) sau này: PA-1; D-2 + W-01; D-3 — mỗi nhóm một commit.

   Không commit `.claude/launch.json`, `backend/scripts/create_csvonly_e2e_accounts.py`, dump, ảnh / bằng chứng có dữ liệu cá nhân.
