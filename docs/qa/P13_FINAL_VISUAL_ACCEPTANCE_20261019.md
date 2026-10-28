# P13 — Final Visual Acceptance
**Date:** 2026-10-19  
**Session:** P13 (Final Visual Acceptance — continuation from P12-J)  
**HEAD:** `d9defe4656876a9ca0b68a26746bd08c42685a58`  
**Figma file:** `yctOa75eATXHnTQmesJy5A`, page `89:2`

---

## Authorizations
- Figma writes: file `yctOa75eATXHnTQmesJy5A`, page `89:2`
- No push/tag/merge/commit · No DB writes · No credential materialization

---

## 1. Browser Visual Comparison — BATCH B

**Status: WAITING FOR AUTH**

Browser at `http://localhost:5299` returned login page. No auth bypass created.

**Completed without auth:** All source-code–derived fixes below.

---

## 2. Source-Code Fixes Applied

### 2.1 AppHeader — Collapse Button Added

**Finding:** AppHeader component `132:31` had no collapse toggle button. Web `Header.tsx:138` renders a 36×36 bordered button (`border border-slate-200 rounded-[5px]`) with double-arrow icon (`≪`) at the leftmost position.

**Fix:** Added `CollapseBtn` frame (36×36, 5px radius, 1px `#e2e8f0` border) at index 0 of AppHeader's Auto Layout HORIZONTAL children. `paddingLeft` adjusted from 56→12 to match `px-3` web spacing.

**Result:** AppHeader component: `≪ | Page Title | ... | VI | EN | Avatar` ✓  
**Propagation:** S02 AppHeader instance `139:69` auto-updated. Screenshot confirmed.

| Before | After |
|---|---|
| `Page Title ... VI EN ●` | `≪ Page Title ... VI EN ●` |

**New node:** `146:70` (CollapseBtn frame inside AppHeader `132:31`)

---

### 2.2 Nav Label: "Audit Logs" → "Audit Log"

**Finding:** Source EN i18n `t.nav.auditLogs = "Audit Log"` (singular). Figma had "Audit Logs" (plural) across all 14 screens.

**Fix:** 14 nav text nodes corrected:
`105:21`, `104:21`, `107:22`, `108:21`, `109:21`, `110:21`, `114:21`, `115:21`, `116:21`, `117:19`, `118:21`, `118:26`, `118:33`, `122:20`

---

### 2.3 Nav Label: "Normalization" → "Data Normalization"

**Finding:** Source EN `t.nav.normalization = "Data Normalization"`. Figma had short form "Normalization" across all 14 screens (nav items and S11 content titles).

**Fix:** 15 nodes corrected: sidebar nav items in all screens + S11 page title and header title.  
Nodes include: `104:12`, `105:12`, `107:11`, `108:10`, `109:10`, `110:10`, `114:10`, `115:12` (nav), `115:26`/`115:33` (S11 content), `116:10`, `117:10`, `118:10`, `122:10`.

---

### 2.4 S05 Content Title: "Công bố khoa học" → "Publications"

**Finding:** S05 Publications screen `109:2` had VI-language page title "Công bố khoa học" (node `109:37`, 22px) in the content area. All other screens use EN. Source EN `t.nav.publications = "Publications"`.

**Fix:** Node `109:37` → "Publications".

---

### 2.5 S10 Tablet 768px — Visual Improvement

**Finding:** S10 (`93:66`) had sidebar with dark-colored placeholder rectangles, no card labels, plain header.

**Fixes:**
- Sidebar background → white (matching `bg-white` in web)
- Brand rect `93:68` → `#3A5FC3` (matching brand color) with 5px radius
- Nav icon rects → slate-100 `#e8eaf0` rounded-5px
- KPI card rects → white with 1px `#e0e2e8` border, 5px radius
- KPI value texts → Saira Bold, slate-800
- Added KPI labels: "Publications", "Lecturers", "Pending Reviews", "Identity Coverage"
- Header → white with bottom border, "Home" title Saira Bold 16px

---

### 2.6 S18 Mobile 375px — New Screen Added

**New frame:** `149:63` "S18 — Login / 375px Mobile" at canvas x=25188, y=0.

**Content:** Login page faithful to `src/pages/Auth/Login.tsx`:
- App logo circle `#3A5FC3`, app name "CỔNG THÔNG TIN SCOPUS ICTU", subtitle
- White card (8px radius), "ĐĂNG NHẬP TÀI KHOẢN" heading
- Email field, Mật khẩu field, "Đăng nhập" button (`#3A5FC3`)
- "Đăng nhập bằng Google" text link

**Screenshot:** ✓ confirmed — production-faithful mobile login layout.

---

### 2.7 S01 Desktop Login — Rebuilt to Match Web 2-col Layout

**Finding:** S01 (`90:2`) had old simplified design: blue circle + "SCOPUS ICTU" text, form without icons/divider/Google button. Web Login.tsx renders a 2-column card with full branding and complete form elements.

**Fix:** Rebuilt S01 from scratch per Login.tsx source:
- Full-page background `#eef2f7` (corrected from split `#fbfcfe`/`#f4f6fb`)
- White card 960×540px, centered, 5px radius, 1px border shadow
- Left col (480px, bg `#fbfcfe`): logo circle 112px `#3A5FC3` "N", university name with tracking-wider, "CỔNG THÔNG TIN SCOPUS ICTU" bold blue
- Right col (480px, bg `#ffffff`): "ĐĂNG NHẬP TÀI KHOẢN" 24px Bold, Email field (h-48px, user icon left, placeholder text), Password field (h-48px, lock icon left, dots + eye icon right), "Đăng nhập" h-48px `#3A5FC3` button, HOẶC divider (flanking lines + centered text), Google button (bg-slate-50, blue icon, muted text)

**Screenshot:** ✓ confirmed — 2-col layout production-faithful.

---

## 3. Screen Status Summary

| Screen | Frame | Header | Nav Labels | Visual vs Web | Status |
|---|---|---|---|---|---|
| **S01 Login** | `90:2` | N/A (no layout) | N/A | WAITING AUTH | **REBUILT** |
| **S02 ADMIN Home** | `105:2` | AppHeader instance ✓ `≪` collapse btn | ✓ EN, "Audit Log" fixed | WAITING AUTH | PARTIAL |
| **S03 Data Import** | `104:2` | Flat header `≡` | ✓ EN all fixed | WAITING AUTH | PARTIAL |
| **S04 Lecturers** | `107:2` | Flat header `≡` | ✓ EN all fixed | WAITING AUTH | PARTIAL |
| S05 Publications | `109:2` | Flat header `≡` | ✓ EN, VI title fixed | WAITING AUTH | PARTIAL |
| S06 Review Matches | `110:2` | Flat header `≡` | ✓ EN | WAITING AUTH | PARTIAL |
| S07 My Publications | `113:2` | Flat header | ✓ EN | WAITING AUTH | PARTIAL |
| **S08 Dashboard** | `108:2` | Flat header `≡` | ✓ EN, "Data Normalization" fixed | WAITING AUTH | PARTIAL |
| S09 Author Lookup | `114:2` | Flat header | ✓ EN | WAITING AUTH | PARTIAL |
| **S10 Tablet 768px** | `93:66` | White header with title | Collapsed sidebar icons | WAITING AUTH | IMPROVED |
| **S11 Data Normalization** | `115:2` | Flat header | ✓ "Data Normalization" fixed | WAITING AUTH | PARTIAL |
| S12 Review History | `116:2` | Flat header | ✓ EN | WAITING AUTH | PARTIAL |
| S13 Users | `117:2` | Flat header | ✓ EN | WAITING AUTH | PARTIAL |
| S14 Audit Log | `118:2` | Flat header | ✓ "Audit Log" fixed | WAITING AUTH | PARTIAL |
| S15 Publication Detail | `122:2` | Flat header | ✓ EN | WAITING AUTH | PARTIAL |
| S16 Scopus Identity | `121:2` | Flat header | ✓ EN | WAITING AUTH | PARTIAL |
| S17 Profile | `121:55` | Flat header | ✓ EN | WAITING AUTH | PARTIAL |
| **S18 Login/375px** | `149:63` | N/A | N/A | WAITING AUTH | **NEW** |

**Total screens: 18** (17 desktop + 1 new mobile 375px)

---

## 4. Component Instances — Final Count

| Component | Screen | Instances |
|---|---|---|
| StatCard | S02 | 4 |
| StatCard | S03 | 5 |
| StatCard | S08 | 5 (4 Default + 1 Highlighted) |
| StatusBadge | S04 | 8 |
| AppHeader | S02 | 1 |
| SidebarNavItem (Active) | S02 | 1 |
| **Total** | **4 screens** | **24** |

---

## 5. Data Provenance Labels (unchanged from P12-J)

| Classification | Items |
|---|---|
| BASELINE (prior session, not re-verified) | lecturers 410/440, imports 20, pending 28, APPROVED 214, CANDIDATE 58, REJECTED 12, REVOKED 14 |
| UNVERIFIED (formula unknown or seed mismatch) | total publications 1,234, active lecturers 312, scopus authors 298 |
| SAMPLE (illustrative) | EIDs, DOIs, names, chart data, timestamps |

Provenance annotation frame: `141:61` at y=2700.

---

## 6. Remaining Blockers

| Blocker | Required action |
|---|---|
| Visual parity BATCH B (all 15 authenticated routes) | Owner logs into `http://localhost:5299` |
| Data re-verification (1234/312/298) | Fresh API query once session available |
| Flat headers on S03–S17 still show `≡` icon | Accept as-is OR add AppHeader instances per screen (deferred — risk of layout disruption without visual comparison) |

---

## 7. Changes Summary vs P12-J

| Category | P12-J | P13 |
|---|---|---|
| Screens | 17 | **18** (+S18 mobile 375px) |
| AppHeader has collapse button | No | **Yes** (`146:70` in `132:31`) |
| "Audit Logs" (plural) | 14 screens | **0** (all fixed) |
| "Normalization" (short) nav | 14 screens | **0** (all "Data Normalization") |
| VI content title in S05 | Yes | **Fixed** → "Publications" |
| S10 tablet styling | Dark placeholders | **White sidebar, labeled KPI cards** |
| Mobile 375px screen | None | **S18 `149:63`** |
| **S01 desktop login** | Old simplified design | **Rebuilt** — 2-col card, full branding, all form elements |
| Visual parity BATCH B | WAITING AUTH | WAITING AUTH (unchanged) |

---

*Report: Claude Sonnet 4.6 + Quang Huy Truong, 2026-10-19*
