# P12-B2 — Final Commit Manifest

| Field | Value |
|---|---|
| Report ID | FINAL_COMMIT_MANIFEST_P12B2_20261018 |
| Date | 2026-10-18 |
| Git HEAD | `237f7bc38bb63f8500e68bc07c53e0598c441002` |
| Branch | `main` |
| Approvals carried forward | B (tailwind.config.js vào commit DS), C (gộp R3 + radius tại common components) |

---

## §0 Git Baseline

| Item | Value | Status |
|---|---|---|
| HEAD | `237f7bc38bb63f8500e68bc07c53e0598c441002` | ✅ INTACT |
| Staged: `.gitignore` | `fb176d6c71b36233123e268ddce272c16eb1a3d6` | ✅ INTACT |
| Staged: `CSV_ONLY_ACCEPTANCE_20261016.md` | `853c832b71126b0c97faab0c87fce7a735d76dd6` | ✅ INTACT |
| Staged: `RELEASE_CANDIDATE_20261017.md` | `3b033179680b87fc421ed43e302688ee1baeead6` | ✅ INTACT |
| Staged: `RELEASE_READINESS_20261017.md` | `0c34a8532065274605a9567f1948a92e50ff4e8f` | ✅ INTACT |

---

## §1 Sửa số lượng commit

Báo cáo P12-B1 nêu "9 commits" nhưng đánh số #0–#9 = **10 mục**. Đây là lỗi đếm trong báo cáo.

Sau khi phân tích dependency import, rà tính nguyên tử, và loại bỏ commit trung gian có import hỏng, số commit được điều chỉnh xuống **7 commits** (không tính commit #0 RC-docs đang staged sẵn):

| P12-B1 # | P12-B2 # | Lý do gộp/tách |
|---|---|---|
| #0 RC docs (staged) | **C-0** | Giữ nguyên — staged sẵn |
| #1 Backend governance + #2 Backend schemas | **C-1** | `publication_api.py` phụ thuộc `review_reason_policy` trong cùng import chain; tách thành commit riêng tạo trạng thái import hỏng tạm thời |
| #3 Launcher | **C-2** | Giữ nguyên |
| #4 Backend tests | **C-3** | Giữ nguyên, sau C-1+C-2 |
| #5 DS tokens + ui/ | **C-4** | Giữ nguyên — **ui/ PHẢI trước pages** |
| #6 Shared components + i18n + #7 R3 pages + #8 Radius pages | **C-5** | Gộp 3 thành 1: tất cả pages đều import `Button`, `Badge`, `PageHeader` từ C-4; tách commit tạo build-broken trung gian |
| #9 QA docs | **C-6** | Giữ nguyên |

**Tổng: 7 commits (C-0 through C-6).**

---

## §2 Kiểm tra script và file không nên commit

### `create_csvonly_e2e_accounts.py`

| Tiêu chí | Kết quả | Phân tích |
|---|---|---|
| Thuộc mã nguồn chính thức? | **Không** | Docstring ghi "One-off", "run manually and delete when done" |
| Tham chiếu secret? | Không | Dùng `os.environ["CSVONLY_E2E_PASSWORD"]` — đúng chuẩn, không hardcode |
| Email hardcode? | Có | `csvonly.e2e.admin@ictu.edu.vn` — tài khoản test, không phải user thật |
| Ghi DB ngoài TEST? | **Không** — chỉ ghi vào `scopus_ictu_test_csvonly_20261011` qua session factory | Nhưng là one-off script, không wired vào startup |
| Cần đưa vào repo? | **Không rõ** — có thể hữu ích để tái tạo test env, nhưng docstring khuyến cáo "delete when done" |

**Quyết định đề xuất:** Không commit `create_csvonly_e2e_accounts.py` trong đợt này. Lý do: docstring tự ghi là one-off, không thuộc product source, không có test coverage cho nó. Nếu owner muốn giữ để tái tạo test env, đặt vào commit riêng `scripts/one-off/` với chú thích rõ.

### Các test files có `SECRET_KEY`

| File | SECRET_KEY usage | Verdict |
|---|---|---|
| `test_demo_launcher_migrate.py` | `"SECRET_KEY": "test-only-launcher-secret-key"` — fixture string trong dict | ✅ SAFE — giá trị test-only, không phải secret thật |
| `test_demo_launcher_safety.py` | `"SECRET_KEY": "synthetic-secret-456"` — fixture kiểm tra masking | ✅ SAFE — test kiểm tra rằng giá trị KHÔNG bị lộ ra log |

Cả hai files an toàn để commit.

### Files **không được commit**

| File/Pattern | Lý do |
|---|---|
| `.claude/launch.json` | Launcher config cục bộ, không thuộc product source |
| `_postgres_demo_14_10/scratch/*` | Evidence artifacts, outside repo |
| `_postgres_demo_14_10/secrets/*` | Secrets directory |
| `dist/`, `node_modules/` | Build artifacts |
| `.tmp/` | gitignored, may contain credentials |
| `create_csvonly_e2e_accounts.py` | One-off, xem trên |
| Bất kỳ `.env` thật | Không có trong working tree — đã OK |

---

## §3 Rà soát RC docs đang staged

**Bốn file RC đang staged tham chiếu code @ `237f7bc`.** Sau P07–P12 (tất cả trong working tree, chưa commit), HEAD vẫn là `237f7bc` — các docs viết về trạng thái working tree, không về commit history.

| Doc | Nội dung có còn đúng? | Vấn đề |
|---|---|---|
| `CSV_ONLY_ACCEPTANCE_20261016.md` | ✅ Đúng — CSV-only test scope, không liên quan radius/DS | Không cần sửa |
| `RELEASE_CANDIDATE_20261017.md` | ⚠️ Ghi "Working tree không có thay đổi code" — **Sai** so với trạng thái hiện tại (47 files unstaged) | Cần ghi chú addendum — xem §3.1 |
| `RELEASE_READINESS_20261017.md` | ⚠️ Không đề cập P12-B0 radius patch; ghi UI-12/13/14 BLOCKED | Phản ánh trạng thái 17/10, trước P12. Cần addendum — xem §3.1 |

### §3.1 Addendum cần thêm vào 2 docs trước khi commit

**Không sửa lịch sử — thêm phần Addendum ở cuối mỗi file.** Nội dung đề xuất:

**`RELEASE_CANDIDATE_20261017.md` — thêm cuối:**

```
---
## Addendum 2026-10-18 (P12-B2)

Tài liệu này được viết ngày 17/10/2026 khi working tree không có thay đổi code.
Từ đó, các thay đổi P07–P12 đã được hoàn thành và nằm trong working tree:
- Backend: review governance D-2/D-3, launcher PA-1, identity evidence basis
- Frontend: Design System R1–R4, i18n, radius 5px (P12-B0)
- QA: 1111 backend tests PASS, 48/48 browser radius PASS

Các thay đổi này sẽ được commit theo manifest P12-B2. HEAD sau commit sẽ khác 237f7bc.
Gate còn mở: security 5432 (OPEN), Figma 5 nodes (PENDING), UI-12/13/14 (DEFER).
```

**`RELEASE_READINESS_20261017.md` — thêm cuối:**

```
---
## Addendum 2026-10-18 (P12-B2)

Tài liệu này phản ánh trạng thái ngày 17/10/2026.
Sau ngày đó:
- P12-A: Full regression 1111 PASS, browser smoke 12/12 PASS, App DB head c7f2a9b1d3e5
- P12-B0: Radius 5px alignment — 53 replacements / 10 files / 48/48 browser PASS
- Design System R3–R4: Button/Badge/PageHeader components, token colors/sizes
- UI-12/13/14: Vẫn chưa test (DEFER sang post-RC)
- Security 5432: Vẫn OPEN — credential scopus_m12_user chưa rotate
```

**Quyết định:** Chủ đồ án phê duyệt thêm addendum trước khi chạy C-0, hoặc commit 2 docs này riêng trong C-6 (QA docs) sau khi đã thêm addendum.

---

## §4 Final Commit Manifest

### Quy ước commit message

Repo hiện tại dùng tiếng Việt, imperative mood: "Thêm", "Cập nhật", "Sửa", "Xóa". Giữ nguyên quy ước.

---

### C-0 — RC Docs (đang staged, commit ngay)

```
git commit -m "Thêm RC docs (CSV-only, Release Candidate, Release Readiness) và cập nhật .gitignore"
```

| Thuộc tính | Giá trị |
|---|---|
| Files | `.gitignore` (M·staged), `docs/qa/CSV_ONLY_ACCEPTANCE_20261016.md` (A·staged), `docs/qa/RELEASE_CANDIDATE_20261017.md` (A·staged), `docs/qa/RELEASE_READINESS_20261017.md` (A·staged) |
| Tất cả tracked? | ✅ Đang staged sẵn |
| Dependencies | Không |
| Test gate | Không có — docs only |
| Thay đổi tài liệu | ✅ Có |
| Ghi chú | Nếu addendum được duyệt (§3.1), sửa 2 docs TRƯỚC khi chạy lệnh này |

---

### C-1 — Backend: Review Governance + Identity Evidence

```
git commit -m "Backend P09: review governance D-2/D-3, identity evidence basis, publication queries"
```

| Thuộc tính | Giá trị |
|---|---|
| **Unstaged tracked (cần `git add`)** | `backend/app/api/v1/endpoints/reviews.py`, `backend/app/schemas/review_api.py`, `backend/app/schemas/publication_api.py`, `backend/app/services/candidate_review_service.py`, `backend/app/services/publication_queries.py` |
| **Untracked (cần `git add`)** | `backend/app/services/review_reason_policy.py`, `backend/app/services/identity_evidence_basis.py` |
| Dependencies | Không (các module này không import từ file chưa commit nào khác) |
| Import chain | `reviews.py` → `review_reason_policy`; `publication_queries.py` → `identity_evidence_basis` — **cả hai untracked phải có trong commit này** |
| Test gate | `python -m pytest backend/tests/integration/test_candidate_review_service.py -x -q` |
| Thay đổi tài liệu | Không |

---

### C-2 — Backend: Safe Launcher PA-1

```
git commit -m "Backend P10: launcher an toàn PA-1 (FORBIDDEN_PORTS, EXPECTED_DB, masking credentials)"
```

| Thuộc tính | Giá trị |
|---|---|
| **Unstaged tracked** | `backend/scripts/demo_launcher.py` |
| **Untracked** | ~~`backend/scripts/create_csvonly_e2e_accounts.py`~~ — **KHÔNG commit** (one-off script) |
| Dependencies | Không import từ C-1 |
| Test gate | `python -m pytest backend/tests/unit/test_demo_launcher_safety.py -x -q` |
| Thay đổi tài liệu | Không |

---

### C-3 — Backend: Test Suite P09–P11

```
git commit -m "Backend P09-P11: bổ sung test suite (review governance, launcher, identity evidence)"
```

| Thuộc tính | Giá trị |
|---|---|
| **Unstaged tracked** | `backend/tests/integration/test_candidate_review_service.py` |
| **Untracked** | `backend/tests/integration/test_demo_launcher_migrate.py`, `backend/tests/integration/test_publication_link_evidence_basis.py`, `backend/tests/integration/test_review_reason_http.py`, `backend/tests/integration/test_review_reason_policy.py`, `backend/tests/unit/test_demo_launcher_safety.py`, `backend/tests/unit/test_identity_evidence_basis.py` |
| Dependencies | C-1 (tests import từ review_reason_policy, identity_evidence_basis), C-2 (tests import demo_launcher) |
| Test gate | `python -m pytest backend/tests/ -q` → **1111 pass, 0 fail** |
| Thay đổi tài liệu | Không |
| Ghi chú | `test_candidate_review_service.py` là unstaged tracked (M) — cần add riêng |

---

### C-4 — Frontend: Design System tokens + ui/ primitives

```
git commit -m "Frontend P11: Design System tokens, Button/Badge/PageHeader components, xóa buttonStyles cũ"
```

| Thuộc tính | Giá trị |
|---|---|
| **Unstaged tracked** | `frontend/tailwind.config.js`⚠️, `frontend/src/styles.css`, `frontend/src/components/common/buttonStyles.ts` (D — deleted) |
| **Untracked** | `frontend/src/components/ui/Button.tsx`, `frontend/src/components/ui/Badge.tsx`, `frontend/src/components/ui/PageHeader.tsx`, `frontend/src/components/ui/reviewTones.ts` |
| Dependencies | Không (ui/ không import từ pages) |
| Split-concern note (B) | `tailwind.config.js` chứa cả P11 colors/sizes VÀ P12-B0 radius tokens (control/action/card=5px). **Owner đã duyệt B** — toàn bộ file vào commit này. |
| `buttonStyles.ts` | Deleted — được thay bằng `Button.tsx`. Tất cả consumers đã import từ `ui/Button` trong working tree. |
| Test gate | `cd frontend && npx tsc --noEmit` → exit 0 (chỉ kiểm tra file trong commit này, chưa có pages) |
| Thay đổi tài liệu | Không |
| ⚠️ Critical | Commit này **phải trước C-5** vì 17 files trong C-5 import Button/Badge/PageHeader |

---

### C-5 — Frontend: Design System R3 rollout + i18n + radius patch

```
git commit -m "Frontend P11-P12B0: Design System R3 rollout toàn site, i18n, radius 5px (P12-B0)"
```

| Thuộc tính | Giá trị |
|---|---|
| **Unstaged tracked** | Tất cả các file frontend còn lại — 37 files (xem danh sách đầy đủ bên dưới) |
| **Untracked** | `frontend/src/pages/ApprovalQueue/ruleLabels.ts`, `frontend/src/pages/Publications/LinkEvidence.tsx` |
| Dependencies | C-4 (Button, Badge, PageHeader, reviewTones phải tồn tại) |
| Split-concern note (C) | Common components (`ErrorBoundary`, `Header`, `Sidebar`, `LecturerDatasetImportCard`, `ToastContext`) chứa cả R3 design VÀ P12-B0 radius hunks. **Owner đã duyệt C** — gộp chung trong commit này với mục đích rõ ràng. |
| Test gate | `cd frontend && npx tsc --noEmit` → exit 0; `npm run build` → build clean |
| Thay đổi tài liệu | Không |

**Danh sách đầy đủ 39 files trong C-5:**

*Unstaged tracked (37):*
- `frontend/src/components/common/ConfirmDialogFrame.tsx`
- `frontend/src/components/common/DuplicateImportDialog.tsx`
- `frontend/src/components/common/ErrorBoundary.tsx` *(radius P12-B0)*
- `frontend/src/components/common/Header.tsx` *(radius P12-B0)*
- `frontend/src/components/common/Sidebar.tsx` *(radius P12-B0)*
- `frontend/src/components/common/TextConfirmModal.tsx`
- `frontend/src/components/lecturers/LecturerDatasetImportCard.tsx` *(radius P12-B0)*
- `frontend/src/contexts/ToastContext.tsx` *(radius P12-B0)*
- `frontend/src/i18n/locales/en.ts`
- `frontend/src/i18n/locales/vi.ts`
- `frontend/src/i18n/types.ts`
- `frontend/src/pages/ApprovalQueue/index.tsx`
- `frontend/src/pages/AuditLogs/index.tsx`
- `frontend/src/pages/Dashboard/charts/AffiliationCoverageChart.tsx`
- `frontend/src/pages/Dashboard/charts/DocumentTypeDonutChart.tsx`
- `frontend/src/pages/Dashboard/charts/PublicationsByYearChart.tsx`
- `frontend/src/pages/Dashboard/index.tsx`
- `frontend/src/pages/Home/index.tsx`
- `frontend/src/pages/Identity/index.tsx` *(radius P12-B0)*
- `frontend/src/pages/Imports/index.tsx`
- `frontend/src/pages/Lecturers/index.tsx`
- `frontend/src/pages/Login/index.tsx` *(radius P12-B0)*
- `frontend/src/pages/MyPublications/index.tsx`
- `frontend/src/pages/Normalization/AffiliationsTab.tsx`
- `frontend/src/pages/Normalization/AuthorsTab.tsx`
- `frontend/src/pages/Normalization/ManualReviewCard.tsx`
- `frontend/src/pages/Normalization/MatchingTab.tsx`
- `frontend/src/pages/Normalization/index.tsx`
- `frontend/src/pages/Profile/index.tsx` *(radius P12-B0)*
- `frontend/src/pages/Publications/AuthorAffiliations.tsx`
- `frontend/src/pages/Publications/Detail.tsx`
- `frontend/src/pages/Publications/index.tsx`
- `frontend/src/pages/ReviewHistory/index.tsx`
- `frontend/src/pages/Users/index.tsx` *(radius P12-B0)*
- `frontend/src/types/publication.ts`
- `frontend/src/types/review.ts`

*Untracked (2):*
- `frontend/src/pages/ApprovalQueue/ruleLabels.ts` *(consumer: ApprovalQueue/index.tsx)*
- `frontend/src/pages/Publications/LinkEvidence.tsx` *(consumer: Publications/Detail.tsx)*

---

### C-6 — QA Evidence Docs

```
git commit -m "Docs: QA evidence P07-P12B2 (governance, launcher, design system, radius, release readiness)"
```

| Thuộc tính | Giá trị |
|---|---|
| **Untracked (15 files)** | Xem danh sách bên dưới |
| Dependencies | C-0 through C-5 nên hoàn thành trước để docs phản ánh đúng trạng thái |
| Test gate | Không — docs only |
| Thay đổi tài liệu | ✅ Có |

**Danh sách 15 files:**
- `docs/qa/ACTOR_UI_ACCEPTANCE_20261017.md`
- `docs/qa/CONTROLLED_REMEDIATION_20261017.md`
- `docs/qa/DATA_INTEGRITY_DEMO_SAFETY_20261017.md`
- `docs/qa/DESIGN_SYSTEM_PILOT_20261017.md`
- `docs/qa/DESIGN_SYSTEM_R3_FINAL_UI_20261017.md`
- `docs/qa/DESIGN_SYSTEM_ROLLOUT_R1R2_20261017.md`
- `docs/qa/FINAL_RELEASE_READINESS_P12A_20261018.md`
- `docs/qa/FINAL_UI_CLOSURE_P115_20261018.md`
- `docs/qa/PRE_COMMIT_HANDOFF_P12B1_20261018.md`
- `docs/qa/PRE_RELEASE_QUALITY_AUDIT_20261017.md`
- `docs/qa/RADIUS_5PX_ALIGNMENT_20261018.md` *(updated P12-B1)*
- `docs/qa/REMEDIATION_VERIFICATION_20261017.md`
- `docs/qa/RESTORE_AND_WORKFLOW_ACCEPTANCE_20261017.md`
- `docs/qa/REVIEW_GOVERNANCE_EVIDENCE_20261017.md`
- `docs/qa/SECURITY_LAUNCHER_WORKFLOW_FIXES_20261017.md`
- `docs/qa/FINAL_COMMIT_MANIFEST_P12B2_20261018.md` *(this file)*

---

## §5 Commit Order & Test Gates

```
C-0  RC Docs          [staged]   → git commit (4 files)
      │
      ↓ (không dependency Python/TS)
C-1  Backend Gov      [add 7]    → pytest test_candidate_review_service -x
      │
      ↓
C-2  Launcher PA-1   [add 1]    → pytest test_demo_launcher_safety -x
      │
      ↓
C-3  Backend Tests    [add 7]    → pytest backend/tests/ -q  →  1111 PASS
      │
      ↓ (backend done; frontend starts)
C-4  DS tokens+ui/   [add 8]    → tsc --noEmit (only ui/ files)
      │
      ↓  ← CRITICAL: ui/ phải tồn tại trước khi build pages
C-5  Frontend R3+i18n+radius [add 39] → tsc --noEmit → npm run build
      │
      ↓
C-6  QA Docs          [add 16]   → kiểm tra git show HEAD --stat
```

**Verification sau toàn bộ:**
```bash
git log --oneline -8
npx tsc --noEmit   # frontend/
npm run build      # frontend/
python -m pytest backend/tests/ -q  # 1111 pass
```

---

## §6 Tổng kiểm tra mỗi thay đổi đúng một lần

| File | Commit | Tracked? |
|---|---|---|
| `.gitignore` | C-0 | Staged |
| `docs/qa/CSV_ONLY_ACCEPTANCE_20261016.md` | C-0 | Staged |
| `docs/qa/RELEASE_CANDIDATE_20261017.md` | C-0 | Staged |
| `docs/qa/RELEASE_READINESS_20261017.md` | C-0 | Staged |
| `backend/app/api/v1/endpoints/reviews.py` | C-1 | Unstaged tracked |
| `backend/app/schemas/review_api.py` | C-1 | Unstaged tracked |
| `backend/app/schemas/publication_api.py` | C-1 | Unstaged tracked |
| `backend/app/services/candidate_review_service.py` | C-1 | Unstaged tracked |
| `backend/app/services/publication_queries.py` | C-1 | Unstaged tracked |
| `backend/app/services/review_reason_policy.py` | C-1 | Untracked |
| `backend/app/services/identity_evidence_basis.py` | C-1 | Untracked |
| `backend/scripts/demo_launcher.py` | C-2 | Unstaged tracked |
| `backend/tests/integration/test_candidate_review_service.py` | C-3 | Unstaged tracked |
| `backend/tests/integration/test_demo_launcher_migrate.py` | C-3 | Untracked |
| `backend/tests/integration/test_publication_link_evidence_basis.py` | C-3 | Untracked |
| `backend/tests/integration/test_review_reason_http.py` | C-3 | Untracked |
| `backend/tests/integration/test_review_reason_policy.py` | C-3 | Untracked |
| `backend/tests/unit/test_demo_launcher_safety.py` | C-3 | Untracked |
| `backend/tests/unit/test_identity_evidence_basis.py` | C-3 | Untracked |
| `frontend/tailwind.config.js` | C-4 | Unstaged tracked |
| `frontend/src/styles.css` | C-4 | Unstaged tracked |
| `frontend/src/components/common/buttonStyles.ts` | C-4 | Unstaged tracked (deleted) |
| `frontend/src/components/ui/Button.tsx` | C-4 | Untracked |
| `frontend/src/components/ui/Badge.tsx` | C-4 | Untracked |
| `frontend/src/components/ui/PageHeader.tsx` | C-4 | Untracked |
| `frontend/src/components/ui/reviewTones.ts` | C-4 | Untracked |
| `frontend/src/components/common/ConfirmDialogFrame.tsx` | C-5 | Unstaged tracked |
| `frontend/src/components/common/DuplicateImportDialog.tsx` | C-5 | Unstaged tracked |
| `frontend/src/components/common/ErrorBoundary.tsx` | C-5 | Unstaged tracked |
| `frontend/src/components/common/Header.tsx` | C-5 | Unstaged tracked |
| `frontend/src/components/common/Sidebar.tsx` | C-5 | Unstaged tracked |
| `frontend/src/components/common/TextConfirmModal.tsx` | C-5 | Unstaged tracked |
| `frontend/src/components/lecturers/LecturerDatasetImportCard.tsx` | C-5 | Unstaged tracked |
| `frontend/src/contexts/ToastContext.tsx` | C-5 | Unstaged tracked |
| `frontend/src/i18n/locales/en.ts` | C-5 | Unstaged tracked |
| `frontend/src/i18n/locales/vi.ts` | C-5 | Unstaged tracked |
| `frontend/src/i18n/types.ts` | C-5 | Unstaged tracked |
| `frontend/src/pages/ApprovalQueue/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/AuditLogs/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Dashboard/charts/AffiliationCoverageChart.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Dashboard/charts/DocumentTypeDonutChart.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Dashboard/charts/PublicationsByYearChart.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Dashboard/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Home/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Identity/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Imports/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Lecturers/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Login/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/MyPublications/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Normalization/AffiliationsTab.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Normalization/AuthorsTab.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Normalization/ManualReviewCard.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Normalization/MatchingTab.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Normalization/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Profile/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Publications/AuthorAffiliations.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Publications/Detail.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Publications/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/ReviewHistory/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/pages/Users/index.tsx` | C-5 | Unstaged tracked |
| `frontend/src/types/publication.ts` | C-5 | Unstaged tracked |
| `frontend/src/types/review.ts` | C-5 | Unstaged tracked |
| `frontend/src/pages/ApprovalQueue/ruleLabels.ts` | C-5 | Untracked |
| `frontend/src/pages/Publications/LinkEvidence.tsx` | C-5 | Untracked |
| 15 `docs/qa/*.md` + this file | C-6 | Untracked |

**Không commit:**
- `.claude/launch.json`
- `backend/scripts/create_csvonly_e2e_accounts.py` (one-off)

---

## §7 GO/NO-GO

| Hành động | Verdict | Điều kiện |
|---|---|---|
| **GO: tạo commit C-0 đến C-6** | ⏳ **HOLD** | Chờ: (A) owner phê duyệt manifest này; (D) quyết định addendum §3.1; (E) xác nhận `create_csvonly_e2e_accounts.py` không commit |
| **GO: tag Release Candidate** | 🔴 **HOLD** | Sau khi C-0–C-6 xong; chờ owner approve tag |
| **GO: push remote** | 🔴 **HOLD** | Sau tag, chờ owner |
| **GO: demo local** | ✅ **GO** | App DB sync, launcher safe, 48/48 browser PASS — không phụ thuộc commits |
| **GO: public deployment** | 🔴 **BLOCKED** | Security gate 5432 OPEN, Figma PENDING, UI-12/13/14 DEFER |

### Gates còn mở — không được tự biến thành PASS

| Gate | Trạng thái | Ghi chú |
|---|---|---|
| Security 5432 (`scopus_m12_user`) | ⚠️ OPEN | Chưa rotate/disable, chưa restrict listen_addresses |
| UI write-flow UI-12/13/14 | ⚠️ DEFER | i18n nhỏ, chưa test nghiêm |
| Figma 5 nodes (5:2/9:9/9:72/9:25/9:41) | ⏳ PENDING | Cần auth Figma MCP hoặc designer thực hiện |
| RC tag | 🔴 HOLD | Chờ commit hoàn thành và owner approve |
| PRs #25/#26/#29 | ⚠️ PENDING | Không blocking RC |

---

## §8 Điều kiện còn cần owner phê duyệt trước PROMPT 12-B3

| # | Quyết định cần | Chi tiết |
|---|---|---|
| A | **Phê duyệt Final Commit Manifest này** (7 commits C-0–C-6) | Bắt buộc trước khi thực thi |
| D | **Quyết định addendum RC docs** | Có thêm addendum vào `RELEASE_CANDIDATE_20261017.md` và `RELEASE_READINESS_20261017.md` trước C-0 không? Hay để nguyên và ghi chú trong C-6? |
| E | **Xác nhận không commit `create_csvonly_e2e_accounts.py`** | Hoặc yêu cầu commit riêng nếu cần giữ |
| F | **Attribution lines** | Mỗi commit message kết thúc bằng `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` theo system reminder — xác nhận áp dụng cho tất cả commits |

B và C đã được duyệt, không cần hỏi lại.
