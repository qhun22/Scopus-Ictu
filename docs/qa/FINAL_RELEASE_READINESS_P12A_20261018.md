# FINAL RELEASE READINESS — PROMPT 12-A (18/10/2026)

**Phạm vi:** Security · Backend Regression · Frontend Regression · App DB · Git Hygiene · Commit Plan · GO/NO-GO

**Commit HEAD:** `237f7bc38bb63f8500e68bc07c53e0598c441002` (branch `main`)

---

## §0. Git Baseline & Bảo tồn Dữ liệu

| Mục | Kết quả |
|---|---|
| HEAD | `237f7bc` (main) |
| 4 blobs RC (staged) | `fb176d6 853c832 3b03317 0c34a85` — **INTACT** |
| Worktree diff SHA256 | `f6212a45bdd7491e8f7a09265d3986a9faf6431b68e8a75e351bd8113a21e2d9` |
| Staged files | 4 (`.gitignore`, 3 docs/qa) |
| Unstaged tracked | 41 files |
| Untracked | 24 files (backend src: 9, tests: 9, frontend src: 3+1, docs/qa: 12) |

**Untracked source checksums:**

| File | SHA-256 (16 ký tự đầu) |
|---|---|
| `backend/app/services/identity_evidence_basis.py` | `3c6b1533da9a7e42` |
| `backend/app/services/review_reason_policy.py` | `4226a96b33140963` |
| `backend/scripts/create_csvonly_e2e_accounts.py` | `ef6b91fb991fcc2f` |
| `frontend/src/components/ui/Badge.tsx` | `60cc53985bfcdec0` |
| `frontend/src/components/ui/Button.tsx` | `cfdee700e16725a4` |
| `frontend/src/components/ui/PageHeader.tsx` | `2a7a86c44140c2a4` |
| `frontend/src/components/ui/reviewTones.ts` | `80de148693b99894` |
| `frontend/src/pages/ApprovalQueue/ruleLabels.ts` | `15e62b73ced090c9` |
| `frontend/src/pages/Publications/LinkEvidence.tsx` | `28bce882e73f741d` |

---

## §1. Security Release Gate (READ-ONLY)

### Tình trạng

| Hạng mục | Kết quả |
|---|---|
| Git-tracked files (`git grep scopus_m12`) | 6 file — chỉ tên/reference, **không có password** |
| Git index (staged) | 4 file — không có credential nào |
| Git history (`.env`) | Không có `.env` thật trong history; chỉ `.env.example` |
| `.env` gitignore | ✅ đúng |
| `.tmp/` gitignore | ✅ đúng |
| QA docs | 1 reference `DB_PASSWORD` (tên key, không phải giá trị) — an toàn |
| Credential `scopus_m12_user` trong `.tmp/` | 18 files — **gitignored, không vào repo** |
| Credential trong Claude transcripts | 4 file `.jsonl` — local, không vào repo |
| Port 5432 `listen_addresses` | `0.0.0.0:5432` — **OPEN (chưa hành động)** |
| Firewall port 5432 | Unknown — chưa kiểm được trong phiên này |
| `demo_launcher.FORBIDDEN_PORTS` | `{5432}` — guard chặn kết nối tình cờ |
| Credential 5432 vs 55432 | **Khác nhau** — không ảnh hưởng cluster demo |

### Đánh giá

**SECURITY GATE = OPEN** — không có credential nào trong repo.

Rủi ro còn lại (tất cả bên ngoài git):
- `scopus_m12_user` credential trong `.tmp/` và transcripts local
- Port 5432 có thể bị truy cập từ mạng nếu firewall chưa chặn

**Hành động chờ chủ đồ án:**
1. Rotate/vô hiệu hóa `scopus_m12_user` trên dịch vụ 5432
2. Đổi `listen_addresses = 'localhost'` trong `postgresql.conf` cho service 5432
3. Dọn `.tmp/*.env` (nếu đã rotate credential)
4. Xác nhận firewall đã chặn port 5432 từ ngoài

---

## §2. Backend Full Regression

**Run:** `20261018T111353_p12a_full_regression`
**DB:** `scopus_ictu_test_pytest_20261013` @ 127.0.0.1:55432
**Thời gian:** 518.49s (8m38s)
**Python:** 3.12.10

| Kết quả | Số lượng |
|---|---|
| Passed | **1111** |
| Skipped | 6 |
| Failed | 0 |
| Errors | 0 |

**Warnings:** StarletteDeprecationWarning (HTTP_422 → tiêu chuẩn mới), InsecureKeyLengthWarning (JWT test key ngắn trong unit test) — cả hai đã tồn tại trước P07, không phải regression.

**Tăng từ P11:** P11 báo cáo 1025 tests → P12-A: 1111 tests (+86 tests từ các file test mới trong untracked).

Chú ý: Các file test mới (untracked) đã được pytest phát hiện và chạy thành công:
- `test_demo_launcher_migrate.py`, `test_demo_launcher_safety.py`
- `test_identity_evidence_basis.py`, `test_publication_link_evidence_basis.py`
- `test_review_reason_http.py`, `test_review_reason_policy.py`

**Kết luận:** Backend regression **PASS** — 0 lỗi, 0 regression.

---

## §3. Frontend Regression

### TypeScript

```
npx tsc --noEmit → exit 0, 0 errors
```

### Production Build (Vite)

| Build | Status | CSS | JS |
|---|---|---|---|
| P12-A current HEAD | ✅ | 62.21 kB | 1,351.48 kB |

Chunk size warning (>500 kB) là pre-existing, không phải regression.

### Browser Smoke Test

**Run:** `20261018T112800_p12a_browser_smoke`
**Env:** frontend `http://localhost:5199` → backend `127.0.0.1:8199` → DB `withjson_r2_20261011`

| Role | Checks | PASS | FAIL |
|---|---|---|---|
| ADMIN | dashboard stat cards, heading, users table, audit-logs, review-history, lecturers sticky | 6/6 | 0 |
| REVIEWER | reviews page, review-history | 2/2 | 0 |
| LECTURER | my-publications, /lecturers redirect (authz block) | 2/2 | 0 |
| Chung | No writes, No console errors | 2/2 | 0 |
| **Tổng** | | **12/12** | **0** |

Ghi chú kết quả kiểm tra authz:
- Dashboard heading không dùng tag `<h1>` — dùng element khác (văn bản "Tổng hợp số liệu hệ thống Scopus ICTU" vẫn hiện đúng)
- LECTURER bị redirect khỏi `/lecturers` → `/home` là **đúng** theo authz design

**Frontend regression: PASS**

---

## §4. UI Write-Flow Gate (UI-12/13/14)

| ID | Mô tả | Trạng thái |
|---|---|---|
| UI-12 | DuplicateImportDialog — `t.common.processing` khi loading | **BLOCKED** |
| UI-13 | LecturerDatasetImportCard — exit/check button | **BLOCKED** |
| UI-14 | Lecturers toasts EN (lock/unlock/reset/save) | **BLOCKED** |

Code đã đúng (thay đổi ở P11). Cần phê duyệt write test riêng trên DB TEST cô lập.

**Đánh giá release blocker:** UI-12/13/14 là các cải tiến i18n nhỏ, không ảnh hưởng luồng nghiệp vụ chính. Có thể release với BLOCKED → đưa vào backlog post-RC nếu chủ đồ án đồng ý.

---

## §5. App DB & Launcher E2E

| Hạng mục | Kết quả |
|---|---|
| App DB `scopus_ictu_app` revision | `c7f2a9b1d3e5` (head) |
| Source Alembic head | `c7f2a9b1d3e5` |
| DB synchronized | ✅ — không cần migrate |
| Launcher `FORBIDDEN_PORTS` | `{5432}` ✅ |
| Launcher `EXPECTED_DB` | `scopus_ictu_app` ✅ |
| Launcher `status` (READ-ONLY) | backend 8001: PID 12480 ✅ · frontend 5173: PID 23044 ✅ · postgres 55432: PID 26560 ✅ · health 200/200 ✅ |
| Migration guard | ✅ (kiểm DB name + yêu cầu gõ tên + backup trước migrate) |

**App DB E2E: PASS (READ-ONLY)**

---

## §6. Git History & PR Audit

### PRs Mở từ Completion-3

| PR | Tiêu đề | State | Commits chưa vào main |
|---|---|---|---|
| [#25](https://github.com/QuangHuyTruong/Scopus-Ictu/pull/25) | A1 — Matching Reference Evaluation Scaffold | OPEN | 3 |
| [#26](https://github.com/QuangHuyTruong/Scopus-Ictu/pull/26) | A2 — Human Matching Review Package | OPEN | 5 |
| [#29](https://github.com/QuangHuyTruong/Scopus-Ictu/pull/29) | A3 — Matching Quality Evaluation | OPEN | 8 |

**Các commit chưa vào main:**
- PR#25: `83f2ce1`, `9afda91`, `1530d93` (evaluation scaffold)
- PR#26: 5 commits (human review package + evaluation)
- PR#29: 8 commits (includes `[CANDIDATE — CHƯA NGHIỆM THU]` commit)

**Đánh giá:** PRs này chứa logic matching evaluation không thuộc phạm vi P07–P12. Không conflict với main (main đã đi trước 86 commit). Quyết định merge/close/archive là của chủ đồ án.

### Git History Integrity

- Không có `.env` thật trong history
- Không có password/token trong commit messages
- HEAD `237f7bc` và 4 RC blobs `fb176d6 853c832 3b03317 0c34a85` INTACT

---

## §7. Commit Plan — P07–P11.5

**Nguyên tắc:** Không stage/commit/push trong phiên này. Đây là kế hoạch cho phiên sau khi được phê duyệt.

### Staged (sẵn sàng commit ngay):
- `commit-RC-docs`: `.gitignore` + 3 docs/qa (CSV_ONLY, RELEASE_CANDIDATE, RELEASE_READINESS)

### Unstaged tracked (41 files) — đề xuất nhóm commit:

| # | Tên commit | Files chính | Phase |
|---|---|---|---|
| 1 | Design System tokens + Button/Badge | `tailwind.config.js`, `Button.tsx`, `Badge.tsx`, `styles.css`, `reviewTones.ts` | P07-P11 |
| 2 | Backend review governance (D-2/D-3) | `reviews.py`, `review_api.py`, `candidate_review_service.py`, `publication_queries.py` | P09 |
| 3 | Backend schemas + publication | `publication_api.py`, `review.ts`, `publication.ts` | P09 |
| 4 | Safe launcher PA-1 | `demo_launcher.py` | P10 |
| 5 | Design System R3 UI rollout | 20+ frontend pages | P11 |
| 6 | i18n + shared components | `en.ts`, `vi.ts`, `types.ts`, `ConfirmDialogFrame.tsx`, `TextConfirmModal.tsx`, `DuplicateImportDialog.tsx`, `Header.tsx`, `LecturerDatasetImportCard.tsx` | P11 |
| 7 | UI-10 sticky + Figma KPI | `Lecturers/index.tsx`, `Dashboard/index.tsx` | P11.5 |
| 8 | R4-A PageHeader pilot | `PageHeader.tsx`, `ReviewHistory/index.tsx`, `AuditLogs/index.tsx` | P11.5 |

### Untracked (cần `git add` trước khi commit):
- Backend src: `identity_evidence_basis.py`, `review_reason_policy.py` → commit #2
- Backend tests (7 files) → commit riêng `Backend test suite P09-P11`
- Frontend ui/: `Badge.tsx`, `Button.tsx`, `PageHeader.tsx`, `reviewTones.ts` → commit #1/#8
- `ApprovalQueue/ruleLabels.ts`, `Publications/LinkEvidence.tsx` → commit #5
- `docs/qa/` (11 files) → commit `QA evidence docs P07-P11.5`
- `backend/scripts/create_csvonly_e2e_accounts.py` → commit #4 hoặc riêng

**Không commit:**
- `.claude/` (mọi thứ trong đó)
- `scratch/` và `qa_runs/` (evidence ở ngoài repo)
- `.tmp/`, `dist/`, `node_modules/`

---

## §8. GO/NO-GO Matrix

| # | Gate | Trạng thái | Ghi chú |
|---|---|---|---|
| G1 | HEAD `237f7bc` intact | ✅ GO | |
| G2 | 4 RC blobs staged intact | ✅ GO | `fb176d6 853c832 3b03317 0c34a85` |
| G3 | TypeScript: 0 errors | ✅ GO | `tsc --noEmit` exit 0 |
| G4 | Production build clean | ✅ GO | 62.21 kB CSS, no build error |
| G5 | Backend regression: 0 fail | ✅ GO | 1111 passed, 6 skipped |
| G6 | Browser smoke: 3 roles PASS | ✅ GO | 12/12 PASS |
| G7 | App DB @ head | ✅ GO | `c7f2a9b1d3e5` == source head |
| G8 | App DB synchronized (no pending migrate) | ✅ GO | |
| G9 | Launcher safety guards | ✅ GO | `FORBIDDEN_PORTS={5432}` |
| G10 | Credential không trong git | ✅ GO | Chỉ trong `.tmp/` (gitignored) |
| G11 | Security gate (5432 exposure) | ⚠️ OPEN | Chờ hành động chủ đồ án (xem §1) |
| G12 | UI write-flow UI-12/13/14 | ⚠️ BLOCKED | i18n nhỏ, không blocking RC theo đánh giá |
| G13 | PRs #25/#26/#29 | ⚠️ PENDING | Không blocking — chờ quyết định chủ đồ án |
| G14 | Commit plan approved | ⏳ PENDING | Chờ chủ đồ án phê duyệt 8 commit groups |

### Tổng kết GO/NO-GO

**10 gates GO · 1 OPEN · 2 BLOCKED/PENDING · 1 PENDING**

**Đề xuất RC với điều kiện:**
- ✅ Sẵn sàng commit + release sau khi chủ đồ án phê duyệt commit plan (G14)
- ⚠️ Security gate G11 nên xử lý trước khi deploy production (không blocking demo)
- ⚠️ UI-12/13/14 (G12) có thể defer sang post-RC
- ⚠️ PRs #25/#26/#29 (G13) cần quyết định: merge, close, hay archive

---

## §9. QA Evidence Summary

| Run | Type | Checks | PASS | FAIL | Commit |
|---|---|---|---|---|---|
| `20261018T111353_p12a_full_regression` | backend-pytest | 1117 | 1111 | 0 | `237f7bc` |
| `20261018T112800_p12a_browser_smoke` | browser-readonly | 12 | 12 | 0 | `237f7bc` |
| `20261018T112558_p12a_browser_smoke` (draft) | browser-readonly | 12 | 10 | 2 | `237f7bc` |

Tất cả evidence ghi tại `_postgres_demo_14_10/scratch/qa_runs/` và `scratch/` — ngoài repo, không chứa secret.

---

## §10. Kết luận

| Hạng mục | Trạng thái |
|---|---|
| Backend regression 1111 tests | ✅ PASS |
| Frontend TypeScript + build | ✅ PASS |
| Browser smoke ADMIN/REVIEWER/LECTURER | ✅ PASS (12/12) |
| App DB revision synchronized | ✅ PASS |
| Launcher safety | ✅ PASS |
| Git baseline + RC blobs | ✅ INTACT |
| Security gate | ⚠️ OPEN — hành động chờ chủ đồ án |
| UI write-flow UI-12/13/14 | ⚠️ BLOCKED |
| PRs #25/#26/#29 | ⚠️ Chờ quyết định |
| Commit plan | ⏳ Chờ phê duyệt |

**RC sẵn sàng commit sau khi chủ đồ án phê duyệt commit plan và quyết định về security gate.**

---

**DỪNG** — chờ chủ đồ án và ChatGPT nghiệm thu PROMPT 12-A.

Không commit, tag hoặc push.
