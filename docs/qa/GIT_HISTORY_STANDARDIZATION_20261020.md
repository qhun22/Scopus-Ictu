# Git History Standardization — Final Code Readiness

**Date:** 2026-10-20
**Scope:** Local-only commit history reword (Conventional Commits, English), no push/merge/tag

---

## 1. HEAD và origin/main ban đầu

| Ref | SHA |
|---|---|
| `main` (HEAD) before rewrite | `d9defe4656876a9ca0b68a26746bd08c42685a58` |
| `origin/main` | `89cf46f52663af129a0999cfc00e92cec45d011f` (unchanged, verified after rewrite) |
| `main` (HEAD) after rewrite | `f1bc84ec9238a4281f774ff303b1b85d4238f086` |

`origin/main` was fetched (no pull/rebase onto it) solely to compute the exact unpublished range. It was not written to.

---

## 2. Backup branch

| Backup | SHA | Purpose |
|---|---|---|
| `backup-before-history-standardization-20261020` | `d9defe4656876a9ca0b68a26746bd08c42685a58` | Explicit backup branch created before any rewrite |
| `refs/original/refs/heads/main` | `d9defe4656876a9ca0b68a26746bd08c42685a58` | Auto-created by `git filter-branch` — second safety net |

Both still exist and point to the pre-rewrite HEAD. Neither was deleted (per constraint).

---

## 3. Số commit local thực tế

**45 commits** in range `origin/main..HEAD`, confirmed before and after rewrite (count unchanged — reword only, no split/squash/drop).

No merge commits in this range. No tags point into this range. No open PR references any of these 45 SHAs (`gh pr list` search returned empty). Only the `main` branch (and the disposable backup refs above) contain `d9defe4`; no other local branch shares this tip.

---

## 4. Mapping — trước/sau (toàn bộ 45 commits, REWORD)

Chronological, oldest → newest. Full table with per-commit reasoning saved at `C:\Users\QuangHuy\AppData\Local\Temp\git-history-backup-20261020\mapping_proposal.md` (local temp file, not part of repo).

| # | New SHA | Old message (vi) | New message (Conventional Commits, en) |
|---|---|---|---|
| 1 | `8057311` | Bổ sung thu thập đơn vị tác giả trực tuyến từ OpenAlex, Crossref và ORCID | `feat(affiliation): fetch author affiliations from OpenAlex, Crossref and ORCID` |
| 2 | `044bd4d` | Thêm lớp phủ cho ADMIN rà soát và hiệu chỉnh đơn vị tác giả có bằng chứng | `feat(affiliation): add admin manual override review with evidence` |
| 3 | `52c2eec` | Thêm chức năng ADMIN tạo tài khoản Giảng viên/Phê duyệt viên không cần hồ sơ... | `feat(users): allow admin to create profile-less lecturer/reviewer accounts and search publications by author name` |
| 4 | `0c6da6e` | Cho phép một tác giả có nhiều đơn vị hiệu chỉnh độc lập... | `feat(affiliation): support multiple independent overrides per author` |
| 5 | `f978d56` | Xây rào chắn an toàn tập trung chặn pytest ghi nhầm vào database thật | `test(db): add centralized safety guard blocking tests from writing to real DB` |
| 6 | `f6b738d` | Khôi phục hiển thị tác vụ thu thập đơn vị trực tuyến sau tải lại trang... | `fix(affiliation): recover enrichment job status after page reload and server restart` |
| 7 | `4e5ee92` | Hoàn thiện Ưu tiên 4: API/UI sinh ứng viên và nạp Craw... | `feat(matching): add Craw-assisted candidate generation and discovery workflow` |
| 8 | `b4c8282` | Sửa lỗi đối sánh Craw gán nhầm đồng tác giả... | `fix(matching): prevent Craw co-author false-match on common surname/middle-name overlap` |
| 9 | `dab11fd` | Xử lý tên Scopus đảo thứ tự và học hàm trong đối sánh Craw-assisted | `fix(matching): normalize reversed Scopus names and academic titles in Craw matching` |
| 10 | `8b372b3` | Nghiệm thu tổng thể trước demo: 23/23 yêu cầu PASS, 1025 tests, 0 GAP must-fix | `docs(qa): record pre-demo final acceptance (23/23 requirements, 1025 tests)` |
| 11 | `f7400b9` | Khóa code trước demo: kiểm thử hai luồng UI cuối — PASS | `docs(qa): record final UI closure before demo (last two flows PASS)` |
| 12 | `288ea1d` | Kiểm toán 410↔48 mapping: xác nhận nguyên nhân và hướng dẫn thao tác | `docs(qa): audit 410 to 48 lecturer-Craw mapping root cause and runbook` |
| 13 | `46ae779` | Đồng bộ Figma design system và thiết kế lại Sidebar theo quy trình nghiệp vụ | `feat(sidebar): redesign navigation per business workflow and align with Figma design system` |
| 14 | `7a0f4ef` | Thêm dark mode: ThemeContext, toggle button trong header, Tailwind darkMode class | `feat(frontend): add dark mode with ThemeContext and header toggle` |
| 15 | `35d30d9` | Redesign PageLoadingBar: overlay → thanh mỏng NProgress-style ở top | `refactor(frontend): redesign PageLoadingBar as NProgress-style top bar` |
| 16 | `719a14e` | Khôi phục PageLoadingBar: chạy cả thanh top bar lẫn overlay first-visit | `fix(frontend): restore PageLoadingBar overlay for first-visit alongside top bar` |
| 17 | `2af2f56` | Sửa dark mode: inject CSS runtime thay vì dùng Tailwind dark: utilities | `fix(frontend): switch dark mode to runtime CSS injection instead of Tailwind dark utilities` |
| 18 | `2e24993` | Xóa dark mode: trở về giao diện trắng mặc định | `revert(frontend): remove dark mode, restore default light theme` |
| 19 | `b489b46` | Sửa crash ứng dụng: khôi phục PageVisitProvider bị thiếu sau revert dark mode | `fix(frontend): restore missing PageVisitProvider after dark mode revert` |
| 20 | `edf6676` | Thu hẹp bảng lịch sử nhập: giảm thanh cuộn ngang ở zoom 100% | `fix(import): reduce horizontal scroll on import history table at 100 percent zoom` |
| 21 | `24a4b4f` | Sửa lỗi scroll bị giữ nguyên khi chuyển route trong sidebar | `fix(router): reset scroll position on sidebar route change` |
| 22 | `e58dc6e` | Sửa triệt để lỗi giữ vị trí cuộn sai khi chuyển route qua sidebar | `fix(router): fully resolve stale scroll position on sidebar navigation` |
| 23 | `ac5c43b` | Sửa KPI "Tổng đợt nhập" đếm thiếu khi có file JSON giảng viên đang preview | `fix(import): correct total-imports KPI undercount during lecturer JSON preview` |
| 24 | `047cdb9` | Sửa KPI "Đang xử lý" không đếm dòng JSON đang chờ xác nhận nhập | `fix(import): include pending-confirmation JSON rows in in-progress KPI` |
| 25 | `a84dd29` | Đồng bộ border-radius 8px cho toàn bộ nhóm sidebar "Quy trình xử lý" | `style(frontend): unify 8px border-radius across Processing sidebar group` |
| 26 | `993ca35` | Giảm border-radius xuống 5px cho toàn bộ nhóm "Quy trình xử lý" | `style(frontend): reduce border-radius to 5px across Processing page group` |
| 27 | `4e203b4` | Giảm border-radius xuống 5px cho Trang chủ, Tra cứu & kết quả, Quản trị | `style(frontend): reduce border-radius to 5px on Home, Search and Admin pages` |
| 28 | `2d334ea` | Thêm biểu đồ Tổng quan dùng dữ liệu thật... | `feat(dashboard): add real-data charts for publications by year, document type and affiliation coverage` |
| 29 | `273d1f8` | Việt hóa tab Đối sánh cho người dùng không chuyên kỹ thuật + sửa enum thô | `i18n(matching): localize matching tab for non-technical users and fix raw enum labels` |
| 30 | `973c77d` | Việt hóa hoàn toàn trang Duyệt đối sánh (/reviews), thêm namespace approvalQueue | `i18n(review): fully localize approval queue page and add approvalQueue namespace` |
| 31 | `7dacfd5` | Việt hóa placeholder giảng viên + i18n hóa ConfirmModal/TextConfirmModal | `i18n(lecturer): localize lecturer placeholder and shared confirm modal components` |
| 32 | `d581e58` | Việt hóa nốt khu vực "Tài khoản hệ thống liên kết" trong chi tiết giảng viên | `i18n(lecturer): localize linked system account section in lecturer detail` |
| 33 | `644dc6f` | Việt hóa PlaceholderPage dùng chung (route /tasks) theo locale | `i18n(frontend): localize shared PlaceholderPage for the tasks route` |
| 34 | `1999eff` | Việt hóa nốt nút "Thử lại" trong Nhật ký hệ thống (AuditLogs) | `i18n(audit): localize retry button on audit log page` |
| 35 | `d154b93` | Thêm 3 báo cáo QA: Dashboard biểu đồ thật, kiểm toán ngôn ngữ toàn site, đối chiếu Figma | `docs(qa): add dashboard charts, site-wide i18n audit and Figma comparison reports` |
| 36 | `e146d88` | Xóa 2 cụm "Đang phát triển" ở /home, thay bằng shortcut thật theo vai trò | `feat(home): replace under-development placeholders with role-based shortcuts` |
| 37 | `a4213f0` | Cập nhật báo cáo Dashboard: /home placeholder đã xử lý (mục 7.1) | `docs(qa): update dashboard report noting home placeholder resolved` |
| 38 | `b1c2791` | Thêm RC docs (CSV-only, Release Candidate, Release Readiness) và cập nhật .gitignore | `docs(release): add CSV-only acceptance, release candidate and readiness reports` |
| 39 | `bc02c9e` | Backend governance P09: review reason policy, identity evidence basis, candidate review | `feat(review): add review reason policy and identity evidence basis for candidate review` |
| 40 | `a569044` | Backend launcher P10: PA-1 security (FORBIDDEN_PORTS, EXPECTED_DB, credential masking) | `feat(security): add launcher port guard, DB allowlist and credential masking` |
| 41 | `00897ec` | Backend tests P09/P10: governance và launcher test suite | `test(backend): add governance and launcher security test suite` |
| 42 | `19a327b` | Design System P11/P12-B0: tokens radius 5px, Button/Badge/PageHeader primitives | `feat(design-system): add Button, Badge and PageHeader primitives with 5px radius tokens` |
| 43 | `f75b8c2` | Frontend P11/P12-B0: DS migration, radius 5px, i18n, pages hoàn chỉnh | `refactor(frontend): migrate pages to design system primitives and 5px radius` |
| 44 | `a3d91dd` | QA docs P07–P12: audit trail toàn bộ chu trình release | `docs(qa): add P07-P12 release cycle audit trail reports` |
| 45 | `f1bc84e` | chore: restore portable Claude launch config | *(unchanged — already Conventional Commits, English, accurate)* |

**Method:** `git filter-branch --msg-filter`, scoped strictly to `origin/main..HEAD` (the 45 unpublished commits). Each message was derived from reading the actual diffstat/content of that commit, not translated from the old title.

---

## 5. Danh sách commits được giữ nguyên vì đã publish

All commits at or before `89cf46f` (origin/main) were **not touched**:
```
89cf46f Phân biệt rõ mạng container CI với địa chỉ loopback khi xác thực server
026fbf8 Buộc PostgreSQL CI lắng nghe đúng cổng 5433 thay vì chỉ ánh xạ cổng
3eaea1e Chuyển cổng PostgreSQL CI sang 5433 để tránh guard chặn cổng 5432
7b13d2d Cập nhật README: sửa chính sách dữ liệu, đồng bộ tiến độ và Alembic head
cdaf8cf Bổ sung báo cáo kiểm toán Git trước khi đẩy lên GitHub
... (and all history before it)
```
These remain as-is, in Vietnamese, untouched — they are published on `origin/main` and rewriting them would diverge from the remote.

---

## 6. Kết quả bảo toàn source tree

| Check | Result |
|---|---|
| Tree hash before rewrite (`d9defe4^{tree}`) | `027786774d9d94ed8127c962b120825a832405b1` |
| Tree hash after rewrite (new HEAD `^{tree}`) | `027786774d9d94ed8127c962b120825a832405b1` |
| **Match** | **✓ IDENTICAL — 100% source content preserved** |
| Commit count | 45 before, 45 after — unchanged |
| Commit order | Unchanged (chronological) |
| Author/committer | `Quang Huy Truong <qhun22@gmail.com>` on all 45 — unchanged |
| `git diff --check` | Only pre-existing trailing-whitespace in original `.md`/test files (not introduced by rewrite — confirmed via tree hash match) |

---

## 7. Trạng thái worktree/untracked

Verified identical before and after the rewrite (stash/pop round-trip):

**Modified (tracked, unstaged) — 4 files:**
- `frontend/src/components/lecturers/LecturerDatasetImportCard.tsx`
- `frontend/src/i18n/locales/en.ts`
- `frontend/src/i18n/locales/vi.ts`
- `frontend/src/i18n/types.ts`

**Untracked — 13 files:**
- `backend/scripts/create_csvonly_e2e_accounts.py` (reviewed — no hardcoded credentials, password sourced from `os.environ["CSVONLY_E2E_PASSWORD"]`, targets test DB only, not wired into app startup)
- 12 `docs/qa/*.md` reports (P12J–P14 QA/visual acceptance reports)

No files lost, no files accidentally staged, no `.env`/secrets touched.

---

## 8. Danh sách thay đổi chưa commit còn cần xử lý

These 17 items (4 modified + 13 untracked) are **not yet committed** — they predate and are unrelated to this history-standardization task. Owner decision needed on how to group them into logical commits (e.g., `feat(lecturer): ...` for the component change, `i18n(...): ...` for locale files, `docs(qa): ...` for the QA reports, `chore(e2e): add CSV-only test account script` for the Python script). Not committed in this session per task scope (history standardization only).

---

## 9. Những việc cần owner phê duyệt

**None required for what was done** — this session performed REWORD-only on unpublished local commits (explicitly pre-authorized by the task). No SPLIT/SQUASH/DROP was applied.

**Pending owner decisions for next steps:**
1. How to commit the 17 outstanding changes (§8) — grouping/scope.
2. Whether to delete `backup-before-history-standardization-20261020` and `refs/original/refs/heads/main` once satisfied (not done automatically, per constraint).
3. Whether/when to push the rewritten `main` (45 commits, same content, new SHAs) to `origin` — this was explicitly out of scope this session.

---

## 10. Trạng thái READY / BLOCKED

**READY** for Release Readiness to proceed, with the following notes:
- History standardization: **DONE** — 45/45 commits reworded, Conventional Commits + English, source tree byte-identical, backups intact.
- Outstanding uncommitted changes (§8): still pending, not a blocker for history standardization itself but should be resolved before a release tag.
- No push/force-push/merge/tag was performed — `origin/main` is exactly as it was (`89cf46f`).

---

## Commit Convention Setup (Phase 5)

Format: `type(scope): concise English description`

**Types:** `feat` `fix` `refactor` `test` `docs` `chore` `ci` `build` `style` `perf`

**Scopes in use this project:** `affiliation` `matching` `review` `users` `lecturer` `publication` `identity` `import` `router` `sidebar` `frontend` `backend` `db` `security` `design-system` `dashboard` `audit` `release` `qa`

**Rules going forward:**
- One logical change → one commit. Don't bundle unrelated fixes/features/docs.
- Never use `git add .` or `git add -A` blindly — stage files explicitly by path.
- Never commit `docs/qa/*` scratch files together with unrelated business logic changes.
- Never commit `.env`, credentials, DB dumps, or files containing real secrets.
- Write the commit body (not just title) when the "why" isn't obvious from the diff.

A `.gitmessage` template and `git config --local commit.template` can be set up on request — not created this session to avoid committing unreviewed config changes.

---

*Report: Claude Sonnet 5 + Quang Huy Truong, 2026-10-20*
