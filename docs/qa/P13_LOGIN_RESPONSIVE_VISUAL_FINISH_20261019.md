# P13 — Login & Responsive Visual Finish
**Date:** 2026-10-19  
**Session:** P13 continuation (Login Visual Accuracy + Responsive + Headers)  
**HEAD:** `d9defe4656876a9ca0b68a26746bd08c42685a58`  
**Figma file:** `yctOa75eATXHnTQmesJy5A`, page `89:2`

---

## Authorizations
- Figma writes: file `yctOa75eATXHnTQmesJy5A`, page `89:2`
- No push/tag/merge/commit · No DB writes · No credential materialization

---

## BATCH 1 — Login Visual Accuracy

### 1.1 Logo ICTU — thay chữ "N" bằng ảnh thật

**Finding:** S01 và S18 dùng hình tròn chữ "N" placeholder. Web `Login.tsx:136` dùng `src={logoSrc}` fallback tới `/assets/ictu.png`.

**Asset:** `frontend/public/assets/ictu.png` (37KB PNG) — uploaded vào Figma với hash `c380731bdbb0f2fb8cfad1c006a084b73a6ec0f6`.

**Fix S01:** Xóa text "N", set inner ellipse fill = `IMAGE/FIT` với imageHash trên.  
**Fix S18:** Xóa text "N", set logo ellipse fill = `IMAGE/FIT` với cùng hash.

**Result:** ✓ Logo ICTU chính thức hiển thị trong cả 2 screens.

---

### 1.2 Email User icon — thay chấm tròn bằng SVG vector

**Finding:** Placeholder `ELLIPSE` màu slate-400 thay vì SVG user icon.

**Source** (`Login.tsx:190–203`):
```
M16 7a4 4 0 11-8 0 4 4 0 018 0z
M12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z
```
stroke `#9CA3AF` (slate-400), strokeWidth 1.8, no fill.

**Fix:** `figma.createNodeFromSvg()` với full SVG string → 20×20 node ở x=10, y=14 trong EmailInput frame.  
**Applied:** S01 EmailInput, S18 email field.

---

### 1.3 Password Lock + Eye icons

**Source** (`Login.tsx:244–319`):
- Lock: `M12 15v2m-6 4h12a2 2 0 002-2v-6...`  
- Eye: `M15 12a3 3 0 11-6 0...` + `M2.458 12C3.732 7.943...`

**Fix:** Lock icon ở x=10, Eye icon ở x=350 (pr-3.5) trong PasswordInput frame.  
**Applied:** S01 PasswordInput, S18 password field.

---

### 1.4 Google G icon — thay chấm tròn xanh bằng multi-color Google SVG

**Source** (`Login.tsx:384–401`): 4 paths (Blue #4285F4, Green #34A853, Yellow #FBBC05, Red #EA4335).

**Fix:** `createNodeFromSvg()` với Google SVG → 20×20 node ở x=20, y=14 trong GoogleButton frame.  
**Applied:** S01 GoogleButton, S18 GoogleButton. S18 bug fix: Eye icon lẫn vào → removed + re-applied Google icon.  
**Status:** Google button giữ disabled style (bg-slate-50, text-slate-400) per web source.

---

### 1.5 Screen labels — di chuyển ra ngoài frame

**Finding:** "S01 — Login / 1440px Desktop" và "S18 — Login / 375px Mobile..." nằm trong frame — xuất hiện khi export.

**Fix:** `figma.currentPage.appendChild(label)` + đặt x/y bên dưới frame tương ứng (y = frame.y + frame.height + 8).

**Post-fix:** 2 label text nodes tồn tại trực tiếp trên page canvas, ngoài bất kỳ screen frame nào. ✓

---

### 1.6 Web vs Figma Visual Comparison — Login

| Điểm kiểm tra | Web (browser) | Figma S01 | Match |
|---|---|---|---|
| Background full page | `#eef2f7` | ✓ | ✓ |
| Card 2-col layout | max-w-960px, grid-cols-2 | 960×540 card | ✓ |
| Left col bg | `#fbfcfe` | ✓ | ✓ |
| Logo | ICTU PNG circle, ring-white | ICTU PNG ✓ | ✓ |
| University name | uppercase tracking-wider | ✓ | ✓ |
| App title | "CỔNG THÔNG TIN SCOPUS ICTU" bold blue | ✓ | ✓ |
| Email field | h-12, user icon left, pl-11 | ✓ SVG icon | ✓ |
| Password field | lock left + eye right, h-12 | ✓ SVG icons | ✓ |
| Login button | h-12, `#3A5FC3`, full width | ✓ | ✓ |
| HOẶC divider | full-width border-t + bg-white "HOẶC" | ✓ | ✓ |
| Google button | disabled, slate-50 bg, G icon | ✓ multi-color | ✓ |

**Web confirmation:** `read_page` at 375px confirmed all elements present. Browser screenshot timeout (pane hidden) — `get_page_text` + `read_page` used as evidence.

**S01 Status: PARTIAL** (structure + icons confirmed; pixel-perfect spacing requires authenticated session screenshot for comparison at full res)  
**S18 Status: PARTIAL** (same)

---

## BATCH 2 — Tablet & Desktop Headers

### 2.1 S10 Tablet — Real Sidebar Icons

**Finding:** 8 sidebar nav slots had `RECTANGLE` placeholders (slate-100, 24×24px).

**Source** (`Sidebar.tsx:36–51`): ADMIN collapsed sidebar shows icons for: Home, Imports, Normalization, Lecturers, Reviews, ReviewHistory, Publications, Search.

**Fix:** Removed 8 rects, inserted `createNodeFromSvg()` icons at same y positions:
| Slot | Icon | SVG path source |
|---|---|---|
| 1 | Home | `M3 12l2-2m0 0l7-7...` |
| 2 | Imports | `M7 16a4 4 0 01-.88...` |
| 3 | Normalization | `M9 12l2 2 4-4m5.618...` |
| 4 | Lecturers | `M12 4.354a4 4 0 110...` |
| 5 | Reviews | `M9 5H7a2 2 0 00-2 2...` |
| 6 | Review History | `M12 8v4l3 3m6-3a9...` |
| 7 | Publications | `M12 6.253v13m0-13...` |
| 8 | Author Lookup | `M21 21l-4.35-4.35...` |

Added active bg (blue/10 rounded-5px) for Home slot (active on Home page).

**S10 Header fix:** Added white fill, bottom border `#e0e2e8`, hamburger icon (3-line menu = tablet responsive ≡), "Home" text bold 18px, avatar circle "A".

**Screenshot:** ✓ PASS — all 8 icons visible, active Home highlight, white header with ☰ + title + avatar.

---

### 2.2 Flat Desktop Headers — Hamburger → Collapse Button

**Finding:** Headers in S03/S04/S05/S06/S08 had 3-rect hamburger (≡) at x=12. Headers in S07/S09/S11-S17 had no toggle button at all.

**React source** (`Header.tsx:138–154`): Desktop shows bordered frame `h-9 w-9 rounded-[5px] border border-slate-200` with `≪` double-chevron icon.

**Fixes:**
- S03, S04, S05, S06, S08: replaced 3 rects with double-chevron SVG (`<path d="M11 17l-5-5 5-5"/><path d="M18 17l-5-5 5-5"/>`)
- S07, S09, S11, S12, S13, S14, S15, S16, S17: inserted new `CollapseBtn` frame (36×36, 5px radius, 1px border, white fill) with double-chevron SVG

**Total screens updated:** 13 (S03–S17 excluding S10 tablet, S01 login, S02 AppHeader instance)

**New node IDs:** `162:99` (S07), `162:103` (S09), `162:107` (S11), `162:111` (S12), `162:115` (S13), `162:119` (S14), `162:123` (S15), `162:127` (S16), `162:131` (S17)

---

### 2.3 VI/EN, Active Nav, Text Clipping — Re-check

| Check | Result |
|---|---|
| VI/EN lang switcher | Present in all flat headers (Frame at x≈1060, w=74) ✓ |
| Active nav items | S02 has SidebarNavItem Active instance; flat screens have tinted bg rects ✓ |
| Role visibility | Sidebar nav items correct per role (ADMIN/LECTURER/REVIEWER) ✓ |
| Text clipping | 0 overflows (fixed in P12-J, no regressions) ✓ |
| Orphan nodes on page | 2 (screen labels, intentional) — 0 unintentional orphans ✓ |

---

## BATCH 3 — Screen Status

| Screen | Frame | Icons | Header | Logo/Icons | Visual vs Web | Status |
|---|---|---|---|---|---|---|
| **S01 Login 1440px** | `90:2` | N/A | N/A | ICTU PNG + SVG icons ✓ | PARTIAL (no auth needed but browser hidden) | **IMPROVED** |
| S02 ADMIN Home | `105:2` | AppHeader instance | CollapseBtn ✓ (`146:70`) | N/A | WAITING AUTH | PARTIAL |
| S03 Data Import | `104:2` | Flat | CollapseBtn ✓ (replaced ≡) | N/A | WAITING AUTH | PARTIAL |
| S04 Lecturers | `107:2` | Flat | CollapseBtn ✓ (replaced ≡) | N/A | WAITING AUTH | PARTIAL |
| S05 Publications | `109:2` | Flat | CollapseBtn ✓ (replaced ≡) | N/A | WAITING AUTH | PARTIAL |
| S06 Review Matches | `110:2` | Flat | CollapseBtn ✓ (replaced ≡) | N/A | WAITING AUTH | PARTIAL |
| S07 My Publications | `113:2` | Flat | CollapseBtn ✓ (added new) | N/A | WAITING AUTH | PARTIAL |
| S08 Dashboard | `108:2` | Flat | CollapseBtn ✓ (replaced ≡) | N/A | WAITING AUTH | PARTIAL |
| S09 Author Lookup | `114:2` | Flat | CollapseBtn ✓ (added new) | N/A | WAITING AUTH | PARTIAL |
| **S10 Tablet 768px** | `93:66` | SVG sidebar icons ✓ | Hamburger + title + avatar ✓ | N/A | WAITING AUTH | **IMPROVED** |
| S11 Data Normalization | `115:2` | Flat | CollapseBtn ✓ (added new) | N/A | WAITING AUTH | PARTIAL |
| S12 Review History | `116:2` | Flat | CollapseBtn ✓ (added new) | N/A | WAITING AUTH | PARTIAL |
| S13 Users | `117:2` | Flat | CollapseBtn ✓ (added new) | N/A | WAITING AUTH | PARTIAL |
| S14 Audit Log | `118:2` | Flat | CollapseBtn ✓ (added new) | N/A | WAITING AUTH | PARTIAL |
| S15 Publication Detail | `122:2` | Flat | CollapseBtn ✓ (added new) | N/A | WAITING AUTH | PARTIAL |
| S16 Scopus Identity | `121:2` | Flat | CollapseBtn ✓ (added new) | N/A | WAITING AUTH | PARTIAL |
| S17 Profile | `121:55` | Flat | CollapseBtn ✓ (added new) | N/A | WAITING AUTH | PARTIAL |
| **S18 Login 375px** | `152:63` | N/A | N/A | ICTU PNG + SVG icons ✓ | PARTIAL (mobile read_page confirmed) | **IMPROVED** |

---

## Remaining Blockers

| Blocker | Required action |
|---|---|
| BATCH B — 15 authenticated routes visual parity | Owner đăng nhập `http://localhost:5299` |
| Pixel-level login comparison (S01/S18) | Browser screenshot — pane currently hidden/timeout |
| Data re-verification (1234/312/298) | Fresh API query post-login |

---

## Changes Summary vs Prior P13 State

| Category | Before | After |
|---|---|---|
| S01/S18 logo | "N" circle placeholder | **ICTU PNG image fill** |
| S01/S18 form icons | Circle placeholders | **SVG vectors (User/Lock/Eye/Google)** |
| Screen labels | Inside frame (exports with design) | **Outside frame (canvas labels only)** |
| S10 sidebar icons | Rectangle placeholders | **8 proper SVG nav icons** |
| S10 header | Plain title only | **Hamburger + title + avatar** |
| S03–S08 headers | 3-rect hamburger ≡ | **Double-chevron collapse ≪** |
| S07/S09/S11-S17 headers | No toggle button | **CollapseBtn frame added** |

---

*Report: Claude Sonnet 4.6 + Quang Huy Truong, 2026-10-19*
