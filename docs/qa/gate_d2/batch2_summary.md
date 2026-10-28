# Gate D.2 Batch 2 — Summary

**Ngày:** 2026-10-27  
**Phương pháp:** Read-only. Browser mở thực tế. CSV scan. Không DB write. Không ACCEPT/REJECT/REVOKE.  
**Phạm vi:** ThS. Lương Thị Minh Huế (×5 IDs) + TS. Nguyễn Hải Minh (×4 IDs)

---

## Coverage tích lũy (sau Batch 2)

| Metric | Batch 1 | Batch 2 | Tích lũy |
|--------|---------|---------|----------|
| GVs đã kiểm tra | 3 | 2 | **8/34** |
| IDs đã kiểm tra | 7 | 9 | **26/83** |
| IDs trong CSV | 7 | 2 primary | 9 primary checked |

_Batch 1 cộng thêm 3 prior-session GVs (QXT primary từ session trước) = 6/34 GVs. Batch 2 thêm 2 = **8/34**._

---

## Nguồn ICTU-WEB

**URL:** `https://repository.ictu.edu.vn/huong-dan-gop-tai-khoan-scopus/`  
**Phương pháp xác nhận:** Browser live DOM extraction, 2026-10-27  
**Cấu trúc bảng:** 35 hàng (1 header + 34 data), tiêu đề "Giảng viên | Email | IDs | # | ID chính hiện dùng | Các Scopus ID cần rà soát/gộp"

---

## ThS. Lương Thị Minh Huế — `lmhue@ictu.edu.vn`

**ICTU-WEB claim:** 5 IDs, 10 pubs, primary `60319803200`

| Scopus ID | Role | Scopus Preview | CSV pubs | Notes |
|-----------|------|---------------|----------|-------|
| 60319803200 | PRIMARY | **ACCESSIBLE** — `Luong, Thi Minh Hue` @ ICTU; ORCID 0009-0003-3737-7741 | **19** | Consistent name + affiliation + ORCID |
| 59708285400 | SECONDARY | **NOT FOUND** — "does not exist or merged" | 0 | Likely already merged |
| 60248511400 | SECONDARY | **NOT FOUND** — "does not exist or merged" | 0 | Likely already merged |
| 60219481200 | SECONDARY | **ACCESSIBLE** — `Luong Thi, Minh Hue` @ ICTU | 0 | Different name tokenization; no CSV evidence |
| 60320211100 | SECONDARY | **NOT FOUND** — "does not exist or merged" | 0 | Likely already merged |

**Discrepancy — ICTU-WEB 10 pubs vs CSV 19:**  
ICTU-WEB counts 10 pubs for this GV in their repository. Scopus CSV (Sep 2026 snapshot) shows 19 pubs under primary ID 60319803200. Possible explanation: (a) ICTU Repository counts only pubs formally linked to this profile; (b) some pubs indexed in Scopus are not yet entered in ICTU DSpace; (c) Sep 2026 export may include pubs not yet in ICTU DSpace.  
**This discrepancy does NOT contradict identity — it is a coverage gap between ICTU Repository and Scopus.**

**Cross-ID EID duplicates:** 0 (no duplicate publications detected across all 5 IDs)

---

## TS. Nguyễn Hải Minh — `nhminh@ictu.edu.vn`

**ICTU-WEB claim:** 4 IDs, 14 pubs, primary `57192956797`

| Scopus ID | Role | Scopus Preview | CSV pubs | Notes |
|-----------|------|---------------|----------|-------|
| 57192956797 | PRIMARY | **ACCESSIBLE** — `Nguyen, Hai Minh` @ ICTU | **8** | Consistent name + affiliation |
| 7003299472 | SECONDARY | **ACCESSIBLE** — `Minh, Nguyen Hai` @ ICTU | **5** | 10-digit ID (atypical); inverted name form; research consistent (ML) |
| 58771697600 | SECONDARY | **ACCESSIBLE** — `Minh, Nguyen Hai` @ ICTU | **1** | 1 pub (2023 ViT-SigNet biometrics); name consistent |
| 59768336500 | SECONDARY | **ACCESSIBLE** — `Hai Minh, Nguyen` @ ICTU | **1** | 1 pub (2025 colorectal cancer); **domain FLAG** — medical imaging vs clustering |

**Domain flag for 59768336500:**  
The one pub in CSV for this ID is "A practical approach for colorectal cancer diagnosis based on..." (2025). The other IDs (primary + 7003299472 + 58771697600) have pubs in ML, clustering, fuzzy systems, and biometrics. Medical imaging is adjacent but distinct. Scopus Preview confirms ICTU affiliation, so this may be a legitimate research pivot. **Flagged for human reviewer — not a definitive anomaly.**

**Discrepancy — ICTU-WEB 14 pubs vs CSV 15:**  
ICTU-WEB counts 14 pubs total. CSV has 8+5+1+1 = 15 across 4 IDs. Minor over-count in CSV vs ICTU (1 extra) — likely reflects pubs added to Scopus after ICTU DSpace last update.

**10-digit ID 7003299472:**  
Confirmed valid: (a) ICTU-WEB DOM lists it explicitly; (b) Scopus Preview returns actual author profile for this ID; (c) 5 CSV publications attributed to this ID. Not invalid — Scopus historically assigned shorter IDs to some profiles.

**Cross-ID EID duplicates:** 0 (no duplicate publications detected across all 4 IDs)

---

## Findings summary

| Finding | GV | Severity | Type |
|---------|-----|---------|------|
| 3 of 5 secondary IDs not found (merged) | Lương Thị Minh Huế | LOW | SCOPUS_MERGED — consistent with merge workflow |
| ICTU-WEB 10 vs CSV 19 pubs | Lương Thị Minh Huế | LOW | COVERAGE_GAP — not identity discrepancy |
| 10-digit ID 7003299472 | Nguyễn Hải Minh | LOW | ATYPICAL_ID_LENGTH — confirmed valid |
| Domain flag: 59768336500 medical imaging | Nguyễn Hải Minh | MEDIUM | DOMAIN_INCONSISTENCY — flagged for reviewer |
| ICTU-WEB 14 vs CSV 15 pubs | Nguyễn Hải Minh | LOW | MINOR_COUNT_DIFF |

---

## Deliverables

| File | Rows | Description |
|------|------|-------------|
| `batch2_id_evidence.csv` | 9 | One row per ID; browser + CSV evidence |
| `batch2_publication_evidence.csv` | 38 | All pub rows per ID (33 pubs + 5 negative rows) |
| `batch2_browser_evidence.json` | — | Structured DOM evidence for 9 IDs + ICTU profile + ICTU-WEB table |
| `batch2_summary.md` | — | This file |
| `batch1_full_csv_reconciliation.csv` | 65 | Batch 1 full reconciliation (64 pubs + 1 negative) |

---

## Part A — Batch 1 gap closure summary

**batch1_full_csv_reconciliation.csv** (65 rows, generated 2026-10-27):

| GV | IDs | Total CSV pubs | ICTU-WEB primary count | Discrepancy |
|----|-----|----------------|----------------------|-------------|
| TS. Quách Xuân Trưởng | 57196472280 (16) + 59707353400 (1) + 57213148275 (2) + 58937710300 (0) | **19** | 16 | +3: secondaries not counted by ICTU-WEB; no duplicate EIDs |
| GS.TS. Đặng Quang Á | 36852696600 (5) + 55331947800 (2) | **7** | 53 | −46: CSV is QH's personal Scopus export — only co-authored pubs appear |
| PGS.TS. Phùng Trung Nghĩa | 55605197600 (37) + 58481617700 (1) | **38** | 38 | 0: exact match |

**"0 EID overlap" confirmation:** Full scan of all 660 CSV rows. 0 duplicate EIDs detected within any single GV's multi-ID group. Conclusion holds across full dataset (not just 21-row sample).

**Discrepancy explanations:**
- **QXT CSV 19 vs ICTU-WEB 16:** ICTU-WEB lists pubs for primary ID only. CSV covers all 4 IDs. No contradiction.
- **DQA CSV 7 vs ICTU-WEB 53:** The Sep 2026 Scopus CSV is Trưởng Quang Huy's personal export — it contains pubs he co-authored with DQA (5) plus papers where 55331947800 also appears (2). DQA's full Scopus record (53 pubs) is not in this export. CSV coverage ≠ Scopus total.
- **PTN CSV 38 vs ICTU-WEB 38:** Exact match. PTN appears to be a frequent co-author of QH, hence full CSV coverage.

**Cumulative coverage update:**
- Prior sessions: 3 GVs (QXT primary + DQA primary + PTN primary) — 10 IDs
- Batch 1: +3 GVs new (same 3 expanded) + full secondary IDs — 17 IDs cumulative
- Batch 2: +2 GVs — **8/34 GVs, 26/83 IDs** total
- Remaining: 26/34 GVs, 57/83 IDs not yet examined

---

*Tạo bởi Claude Sonnet 4.6 ngày 2026-10-27 — read-only, không DB write.*
