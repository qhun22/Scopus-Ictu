# Gate D.2 Batch 5 — Summary

**Ngày:** 2026-10-27  
**Phương pháp:** Read-only. Browser mở thực tế. CSV scan. CrossRef DOI cross-check (full author list). Không DB write. Không ACCEPT/REJECT/REVOKE.  
**Phạm vi:** TS. Phạm Đức Long (×3 IDs) + TS. Đỗ Thị Bắc (×5 IDs)  
**Tiếp nối từ Batch 4:** Scopus Preview server tiếp tục trả "Unable to display author profile" (server issue kéo dài từ Batch 3).

---

## Coverage tích lũy (sau Batch 5)

**Lưu ý:** 5 IDs của TS. Đỗ Thị Bắc đã được mở từ Gate D.1 (trước Batch 1). Batch 5 re-visit sâu 8 IDs (2 GVs) nhưng chỉ bổ sung 3 IDs mới (PDL) và 1 GV mới (PDL) vào tập unique.

| Metric | Hết Batch 4 | Batch 5 mới | Unique tích lũy |
|--------|-------------|-------------|-----------------|
| GVs unique đã truy cập | 12 | +1 (PDL) | **13/34** |
| IDs unique đã mở | 38 | +3 (PDL ×3) | **41/83** |
| IDs body accessible | 16 | 0 | 16/41 |
| IDs page title confirmed | 28 | +3 (PDL) | 31/41 |
| IDs không tìm thấy | 3 | 0 | 3/41 |
| IDs có bằng chứng CORROBORATED | 5 | +2 (57819997900, 59526508700) | **7/41** |
| **Batch 5 revisit** | — | DTB ×5 (đã từng mở từ Gate D.1) | không cộng vào unique |

---

## Nguồn ICTU-WEB

**URL:** `https://repository.ictu.edu.vn/huong-dan-gop-tai-khoan-scopus/`  
**Xác nhận:** Browser DOM extraction, 2026-10-27

---

## TS. Phạm Đức Long — `pdlong@ictu.edu.vn`

**ICTU-WEB claim:** 3 IDs, 6 pubs, primary `26637116200`

| Scopus ID | Role | Page Title | Body | CSV pubs | Name in title | Notes |
|-----------|------|-----------|------|----------|---------------|-------|
| 26637116200 | PRIMARY | CONFIRMED | UNABLE_TO_DISPLAY | 4 | "Long, Pham Duc" | BROWSER_OPENED — không có DOI riêng cho ID này trong CSV |
| 57197579769 | SECONDARY | CONFIRMED | UNABLE_TO_DISPLAY | 1 | "Pham, Duc Long" | **PUBLICATION_NAME_CORROBORATED** — DOI 10.1109/CISP.2009.5303557 trong CSV row có ID này |
| 58805722900 | SECONDARY | CONFIRMED | UNABLE_TO_DISPLAY | 1 | "Long, Pham Duc" | **PUBLICATION_NAME_CORROBORATED** — DOI 10.1007/978-3-031-50818-9_35 trong CSV row có ID này |

**CrossRef DOI 10.1007/978-3-031-50818-9_35 (Springer 2024):**  
Authors (full): **Pham Duc Long** (pos. 1/1)  
CSV row có Author(s) ID = **58805722900** (không phải 26637116200). Publisher: Springer LNCS. **MATCHES** ID 58805722900. → PUBLICATION_NAME_CORROBORATED cho 58805722900.  
*(No affiliation in CrossRef metadata. Name-only.)*

**CrossRef DOI 10.1109/CISP.2009.5303557 (IEEE 2009):**  
Authors (full): Nguyen Tuan Minh · Pham Thuong Cat · **Pham Duc Long** (pos. 3/3)  
CSV row có Author(s) ID = **57197579769** (không phải 58805722900). **MATCHES** ID 57197579769. → PUBLICATION_NAME_CORROBORATED cho 57197579769.

**[CORRECTION NOTE 2026-10-28]:** DOI→ID assignments đã được sửa theo Scopus CSV nguồn. ID 26637116200 chỉ có BROWSER_OPENED — không có DOI riêng mapping về ID này trong CSV.

**Domain:** Image processing, cellular neural networks, AI in agriculture — coherent domain.

**Discrepancy — ICTU-WEB 6 pubs vs CSV 6:**  
CSV: 4+1+1 = 6 unique EIDs. ICTU-WEB: 6. **No discrepancy.** Count matches exactly.

**Cross-ID EID duplicates:** 0

---

## TS. Đỗ Thị Bắc — `dtbac@ictu.edu.vn`

**ICTU-WEB claim:** 5 IDs, 11 pubs, primary `59526508700`

| Scopus ID | Role | Page Title | Body | CSV pubs | Name in title | Notes |
|-----------|------|-----------|------|----------|---------------|-------|
| 59526508700 | PRIMARY | CONFIRMED | UNABLE_TO_DISPLAY | 8 | "Do, Thi Bac" | **PUBLICATION_NAME_CORROBORATED** — DOI 10.1007/s00542-026-06031-2 trong CSV row có ID này |
| 57819997900 | SECONDARY | CONFIRMED | UNABLE_TO_DISPLAY | 3 | "Do, Bac Thi" | **PUBLICATION_CORROBORATED** — DOI 10.11591/eei.v14i3.9064; publisher (beei.org) xác nhận affil=ICTU, email=dtbac@ictu.edu.vn |
| 59663496400 | SECONDARY | CONFIRMED | UNABLE_TO_DISPLAY | 1 | "Bac, Do Thi" | BROWSER_OPENED; 1 pub 2023 |
| 59159284800 | SECONDARY | CONFIRMED | UNABLE_TO_DISPLAY | 1 | "do Thi, Bac" | BROWSER_OPENED; lowercase "do"; 1 pub |
| 57899449200 | SECONDARY | CONFIRMED | UNABLE_TO_DISPLAY | 1 | "ThiBac, Do" | BROWSER_OPENED — DOI 10.1007/s00542-026-06031-2 thuộc ID 59526508700, không phải ID này |

**Name variants observed:** "Do, Thi Bac" / "Do, Bac Thi" / "Bac, Do Thi" / "do Thi, Bac" / "ThiBac, Do" / "Thi-Bac Do" / "Bac Thi Do" — **7 forms** for same name Đỗ Thị Bắc. Highest count in this audit.

**CrossRef DOI 10.11591/eei.v14i3.9064 (IAES/BEEI 2025):**  
Authors (full, 5 tác giả): May Thu Duong · Alexander A. Moldovyan · Nikolay A. Moldovyan · Minh Hieu Nguyen · **Bac Thi Do** (pos. 5/5)  
CSV row có Author(s) ID = **57819997900**. Publisher page (beei.org) xác nhận affil=Thai Nguyen University of ICT, email=dtbac@ictu.edu.vn. → **PUBLICATION_CORROBORATED** cho 57819997900 (E5-level: publisher confirms affil+email).

**CrossRef DOI 10.1007/s00542-026-06031-2 (Springer 2026):**  
Authors (full, 2 tác giả): **Thi-Bac Do** (pos. 1/2) · Quang-Huy Tran (ID 57208579583)  
CSV row có Author(s) ID = **59526508700**. **MATCHES** ID 59526508700. → PUBLICATION_NAME_CORROBORATED cho 59526508700.  
*Note: Co-author "Quang-Huy Tran" (ID 57208579583) is NOT in the 9-GV audit list.*

**[CORRECTION NOTE 2026-10-28]:** DOI→ID assignments đã được sửa theo Scopus CSV nguồn. ID 57899449200 không có DOI riêng trong CSV — downgraded về BROWSER_OPENED.

**Discrepancy — ICTU-WEB 11 pubs vs CSV 14:**  
CSV: 8+3+1+1+1 = 14 unique EIDs. ICTU-WEB: 11. Chênh lệch +3 — secondary IDs không được đếm bởi ICTU-WEB. Pattern nhất quán với tất cả các Batch trước.

**Cross-ID EID duplicates:** 0

---

## Cross-GV Coauthorship (Batch 5)

**PDL cross-GV:** Không có cross-GV EIDs với các GVs Batch 1–4 trong CSV này.  
**DTB cross-GV:** Không có cross-GV EIDs với các GVs Batch 1–4 trong CSV này.  
**PDL × DTB:** 0 EIDs.

*Lưu ý: CSV là personal export của QH (Sep 2026). PDL và DTB có thể đồng tác giả với GVs khác không có trong CSV này. Thiếu thông tin không có nghĩa là không đồng tác giả.*

---

## DOI Cross-Check Summary

| DOI | GV | ID trong CSV | Full author count | Match | Result |
|-----|----|----|---|---|---|
| 10.1007/978-3-031-50818-9_35 | PDL | **58805722900** | 1 | #1 "Pham Duc Long" | PUBLICATION_NAME_CORROBORATED |
| 10.1109/CISP.2009.5303557 | PDL | **57197579769** | 3 | #3 "Pham Duc Long" | PUBLICATION_NAME_CORROBORATED |
| 10.11591/eei.v14i3.9064 | DTB | **57819997900** | 5 | #5 "Bac Thi Do" | PUBLICATION_CORROBORATED (publisher xác nhận ICTU affil + email) |
| 10.1007/s00542-026-06031-2 | DTB | **59526508700** | 2 | #1 "Thi-Bac Do" | PUBLICATION_NAME_CORROBORATED |

*[CORRECTED 2026-10-28] Cột "ID trong CSV" đã được sửa để phản ánh đúng Scopus Author ID mà Scopus CSV gán cho từng DOI, không phải ID được suy luận.*

---

## Findings Summary

| Finding | GV | Severity | Type |
|---------|-----|---------|------|
| 7 name variants cho Đỗ Thị Bắc — nhiều nhất trong audit này | Đỗ Thị Bắc | LOW | NAME_TOKENIZATION_VARIANT (7 forms) |
| ICTU-WEB 11 vs CSV 14 pubs | Đỗ Thị Bắc | LOW | COVERAGE_GAP — secondaries không đếm |
| ICTU-WEB 6 vs CSV 6 pubs | Phạm Đức Long | INFO | COUNT_MATCH — không chênh lệch |
| Tất cả 8 IDs UNABLE_TO_DISPLAY | Cả 2 | OBSERVATION | SCOPUS_SERVER_ISSUE (tiếp tục từ Batch 3) |
| Co-author "Quang-Huy Tran" (57208579583) không trong audit list | Đỗ Thị Bắc | INFO | UNRESOLVED_COAUTHOR — không thể xác nhận ICTU identity |

---

## Deliverables

| File | Rows | Description |
|------|------|-------------|
| `batch5_id_evidence.csv` | 8 | Per-ID: browser + CSV + CrossRef evidence |
| `batch5_publication_evidence.csv` | 20 | 6 PDL + 14 DTB unique EIDs, 0 intra-GV dups (strict UTF-8) |
| `batch5_browser_evidence.json` | — | Full structured evidence |
| `batch5_summary.md` | — | This file |

---

*Tạo bởi Claude Sonnet 4.6 ngày 2026-10-27 — read-only, không DB write.*
