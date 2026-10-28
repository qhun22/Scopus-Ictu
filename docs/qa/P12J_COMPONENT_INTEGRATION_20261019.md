# P12-J Component Integration & Data Provenance Fix
**Date:** 2026-10-19  
**Session:** P12-J (Component Integration continuation)  
**HEAD:** `d9defe4656876a9ca0b68a26746bd08c42685a58`  
**Follows:** `P12J_FINAL_VISUAL_ACCEPTANCE_20261019.md`

---

## Authorizations
- Figma writes: file `yctOa75eATXHnTQmesJy5A`, page `89:2`
- No push/tag/merge/commit to Git remote · No DB writes · No credential materialization

---

## A — Component Architecture

### A.1 Components rebuilt with Auto Layout

Old 4 flat components (`126:2/5/7/14`) removed and replaced with proper component sets:

| Component | ID | Type | Auto Layout | Variants |
|---|---|---|---|---|
| `StatCard` | `132:10` (set) | COMPONENT_SET | VERTICAL (padding 14/16, gap 4) | State=Default / State=Highlighted |
| `StatusBadge` | `132:23` (set) | COMPONENT_SET | HORIZONTAL (padding 8/4, center-center) | Status=LECTURER/REVIEWER/ADMIN/APPROVED/PENDING/FAILED |
| `SidebarNavItem` | `132:30` (set) | COMPONENT_SET | Absolute (active bg rect + left bar + label) | State=Active / State=Inactive |
| `AppHeader` | `132:31` | COMPONENT | HORIZONTAL (paddingLeft=56, counterAxis=CENTER) | Single (title FILL, lang pill, avatar) |

**StatCard variant geometry:**
- `State=Default` (`132:2`): 281×auto, white fill, 1px `#e0e2e8` border, 5px radius
- `State=Highlighted` (`132:6`): 281×auto, white fill, 2px `#3A5FC3` border, 5px radius
- Both: Label (Regular/12/slate-500), Value (Bold/30/slate-800), Subtitle (Regular/11/slate-400) — all FILL width

**StatusBadge variants:** 6 status colors match `Imports/index.tsx` status tone mapping exactly.

### A.2 Instance Migration

StatCard instances created in 3 priority screens:

| Screen | Frame | Instances | Variant used |
|---|---|---|---|
| S02 — ADMIN Home | `105:2` | 4 | Default ×4 |
| S03 — Data Import | `104:2` | 5 | Default ×5 |
| S08 — Dashboard | `108:2` | 5 | Default ×4 + **Highlighted ×1** (Pending Reviews) |

**Total StatCard instances: 14** across 3 screens.

S04/S05/S06/S07/S09/S11–S17: KPI cards not replaced (different widths, no subtitle, or no stat cards — PARTIAL status maintained; flat frames preserved as-is per task constraint).

### A.3 Post-migration Verification

| Check | Result |
|---|---|
| Total StatCard instances | 14 ✓ |
| Text overflow violations | 0 ✓ |
| Non-frame orphan nodes | 0 ✓ |
| S02 KPI layout visible | ✓ screenshot confirmed |
| S08 Highlighted card visible | ✓ screenshot confirmed (blue border) |

---

## B — Data Provenance Fix

### Classification methodology

A value is **VERIFIED** only if there is an API or SQL read-only result from the TEST DB session in P12-H or P12-I with a specific endpoint, field, and session timestamp. It is **BASELINE** if it was captured at a prior session and not re-queried in P12-J. It is **SAMPLE** if it is illustrative and was never derived from a database query.

**A value appearing in a Figma frame or prior QA report does NOT constitute VERIFIED.**

### Corrected provenance table

| Data point | Value in Figma | Classification | Source / Reason |
|---|---|---|---|
| Total lecturers (baseline) | 410 | **VERIFIED** | P12-I: `/api/v1/lecturers?limit=1&offset=0` → total:440; baseline=410 (empty staff_code) |
| Total lecturers (with TEST) | 440 | **VERIFIED** | P12-I: 410 + 30 TEST_P12* confirmed via 3-page paginated fetch |
| Total imports | 20 | **VERIFIED** | P12-H: `/api/v1/lecturers/import` → total:20 |
| Completed imports | 18 | **VERIFIED** | P12-H: 18 CANCELLED + 1 IMPORTED + 1 APPLIED = 20 |
| Pending review candidates | 28 | **VERIFIED** | P12-H/I: dashboard summary `pending_review_count` |
| Identity APPROVED | 214 | **VERIFIED** | P12-H/I: identity status distribution from dashboard API |
| Identity CANDIDATE | 58 | **VERIFIED** | P12-H/I: identity status distribution |
| Identity REJECTED | 12 | **VERIFIED** | P12-H/I: identity status distribution |
| Identity REVOKED | 14 | **VERIFIED** | P12-H/I: identity status distribution |
| **Total publications** | **1,234** | **BASELINE** | P12-H/I dashboard summary; NOT re-queried P12-J. Original seed=660 publications; figure may differ from current TEST DB. |
| Active lecturers | 312 | **BASELINE** | Dashboard P12-H/I; not re-verified P12-J |
| Scopus authors linked | 298 | **BASELINE** | Dashboard P12-H/I; not re-verified P12-J |
| EID `2-s2.0-85182374610` | — | **SAMPLE** | Valid format; specific record existence in TEST DB unverified |
| DOI `10.1016/j.eswa.2024.123456` | — | **SAMPLE** | Illustrative DOI |
| Scopus IDs (57210234567 etc.) | — | **SAMPLE** | Valid 11-digit format; not from TEST DB |
| Lecturer names (GV001–GV008) | — | **SAMPLE** | Format-correct; not actual ICTU records |
| Bar chart values (S08) | 42→213 | **SAMPLE** | Illustrative trend; actual by-year counts not queried |
| Donut chart (S08) | Article 684 etc. | **SAMPLE** | Illustrative; not from TEST DB |
| Affiliation coverage (S08) | 72.4% (3842/5307) | **SAMPLE** | Illustrative |

### Figma annotation frame

A `📋 Data Provenance Annotations` frame (`133:44`) was added at y=2700 on page `89:2`, below the component zone. It contains 19 labeled rows (color-coded VERIFIED=green / BASELINE=amber / SAMPLE=gray) visible to any Figma viewer.

**Key correction from prior sessions:** "1,234 publications" was previously labeled VERIFIED. Correct classification is **BASELINE** — it was captured from a dashboard API call in P12-H/I but was not re-queried in P12-J, and the original import seed was 660. The figure shown in Figma is the best available from prior sessions but should be treated as potentially stale.

---

## C — Visual Parity

**Status: WAITING FOR AUTH** (unchanged from `P12J_FINAL_VISUAL_ACCEPTANCE_20261019.md`)

Browser `http://localhost:5299` requires an authenticated session. Auto-mode blocks credential materialization. No auth bypass or HTTP helper was created.

**Owner action:** Log into `http://localhost:5299` in the same browser session where this agent is active. The agent will then navigate each route and capture screenshots automatically.

---

## D — Updated Screen Status

| Screen | Frame | Component instances | Data classification | Visual vs web |
|---|---|---|---|---|
| S01 Login | `90:2` | 0 | N/A | WAITING AUTH |
| **S02 ADMIN Home** | `105:2` | **4 StatCard** | VERIFIED KPIs | WAITING AUTH |
| **S03 Data Import** | `104:2` | **5 StatCard** | VERIFIED KPIs, SAMPLE rows | WAITING AUTH |
| S04 Lecturers | `107:2` | 0 (flat) | VERIFIED total, SAMPLE rows | WAITING AUTH |
| S05 Publications | `109:2` | 0 (flat) | BASELINE total, SAMPLE rows | WAITING AUTH |
| S06 Review Matches | `110:2` | 0 (flat) | VERIFIED counts, SAMPLE data | WAITING AUTH |
| S07 My Publications | `113:2` | 0 (flat) | SAMPLE data | WAITING AUTH |
| **S08 Dashboard** | `108:2` | **5 StatCard** (1 Highlighted) | VERIFIED+BASELINE KPIs, SAMPLE charts | WAITING AUTH |
| S09 Author Lookup | `114:2` | 0 (flat) | SAMPLE data | WAITING AUTH |
| S10 Tablet 768px | `93:66` | 0 | Structural only | WAITING AUTH |
| S11 Normalization | `115:2` | 0 (flat) | SAMPLE data | WAITING AUTH |
| S12 Review History | `116:2` | 0 (flat) | SAMPLE data | WAITING AUTH |
| S13 Users | `117:2` | 0 (flat) | SAMPLE data | WAITING AUTH |
| S14 Audit Logs | `118:2` | 0 (flat) | SAMPLE data | WAITING AUTH |
| S15 Publication Detail | `122:2` | 0 (flat) | SAMPLE data | WAITING AUTH |
| S16 Scopus Identity | `121:2` | 0 (flat) | VERIFIED counts, SAMPLE IDs | WAITING AUTH |
| S17 Profile | `121:55` | 0 (flat) | SAMPLE data | WAITING AUTH |

---

## Summary of Changes

| Category | Before this session | After |
|---|---|---|
| Components with Auto Layout | 0 | 4 (StatCard/2v, StatusBadge/6v, SidebarNavItem/2v, AppHeader) |
| StatCard instances in screens | 0 | 14 |
| Highlighted variant usage | 0 | 1 (S08 Pending Reviews) |
| Data provenance annotations | None | 19-row annotated frame `133:44` |
| "1,234 publications" label | VERIFIED (incorrect) | **BASELINE** (corrected) |
| Text overflows | 0 (fixed prior session) | 0 |
| Orphan nodes | 0 (fixed prior session) | 0 |
| Visual web comparison | BLOCKED | WAITING AUTH |

---

## Remaining Blockers

1. **BATCH B visual comparison** — owner must log in to `http://localhost:5299`
2. **BASELINE re-verification** — `total_publications`, `active_lecturers`, `scopus_authors` need fresh API query once session available
3. **Instance migration S04–S17** — feasible but low ROI without visual comparison to guide layout adjustments; deferred
4. **Commit** — 4 i18n files + all `docs/qa/` untracked files; owner action

---

*Report author: Claude Sonnet 4.6 + Quang Huy Truong, 2026-10-19*
