# Gate D.2 Batch 4 — Summary

**Ngày:** 2026-10-27  
**Phương pháp:** Read-only. Browser mở thực tế. CSV scan. CrossRef DOI cross-check (full author list). Không DB write. Không ACCEPT/REJECT/REVOKE.  
**Phạm vi:** TS. Ngô Hữu Huy (×3 IDs) + TS. Trần Quang Quý (×3 IDs)  
**Cải tiến từ Batch 3:** CrossRef DOI check đọc toàn bộ author list, không giới hạn số tác giả (sửa lỗi từ FINDING-016 false positive).

---

## Coverage tích lũy (sau Batch 4)

| Metric | Batch 1–3 | Batch 4 | Tích lũy |
|--------|-----------|---------|----------|
| GVs đã kiểm tra | 10 | 2 | **12/34** |
| IDs đã kiểm tra | 32 | 6 | **38/83** |
| IDs body accessible | 16 | 0 | 16/38 |
| IDs page title confirmed | 22 | 6 | 28/38 |
| IDs không tìm thấy | 3 | 0 | 3/38 |
| IDs có bằng chứng E5/CORROBORATED | 3 | 2 | **5/38** |

---

## Nguồn ICTU-WEB

**URL:** `https://repository.ictu.edu.vn/huong-dan-gop-tai-khoan-scopus/`  
**Xác nhận:** Browser DOM extraction, 2026-10-27

---

## TS. Ngô Hữu Huy — `nhhuy@ictu.edu.vn`

**ICTU-WEB claim:** 3 IDs, 18 pubs, primary `57210434401`

| Scopus ID | Role | Page Title | Body | CSV pubs | Name in title | Notes |
|-----------|------|-----------|------|----------|---------------|-------|
| 57210434401 | PRIMARY | CONFIRMED | UNABLE_TO_DISPLAY | 12 | "Ngo, Huu Huy" | Main profile; 12 pubs 2021–2026 |
| 59708261900 | SECONDARY | CONFIRMED | UNABLE_TO_DISPLAY | 1 | "Huy, Ngo Huu" | Inverted name; 1 pub 2025 |
| 59775920700 | SECONDARY | CONFIRMED | UNABLE_TO_DISPLAY | 9 | "Ngo, Huuhuy" | **PUBLICATION_CORROBORATED** via CrossRef DOI; 9 pubs 2025–2026 |

**Name variants observed:** "Ngo, Huu-Huy" / "Ngo, Huu Huy" / "Huy, Ngo Huu" / "Ngo, Huuhuy" / "Ngo, Huy-Huy" — 5 forms for same name Ngô Hữu Huy. Misspelling "Huy-Huy" (should be "Huu-Huy") present in 1 CSV entry (57210434401, 2026).

**CrossRef DOI 10.5121/ijcnc.2026.18401:**  
Authors (full): Le Hoang Hiep · Hoang Van-Tam · **Ngo, Huu-Huy** (pos. 3/3)  
Publisher: AIRCC 2026. **MATCHES** ID 59775920700. → PUBLICATION_CORROBORATED

**Discrepancy — ICTU-WEB 18 pubs vs CSV 22:**  
ICTU-WEB: 18 pubs (likely primary only). CSV: 12+1+9 = 22 unique EIDs.  
+4 from secondary IDs not counted by ICTU-WEB. Pattern consistent with Batch 1 (QXT +3) and Batch 3 (LHL +3).

**Cross-ID EID duplicates:** 0

---

## TS. Trần Quang Quý — `tqquy@ictu.edu.vn`

**ICTU-WEB claim:** 3 IDs, 12 pubs, primary `58771615400`

| Scopus ID | Role | Page Title | Body | CSV pubs | Name in title | Notes |
|-----------|------|-----------|------|----------|---------------|-------|
| 58771615400 | PRIMARY | CONFIRMED | UNABLE_TO_DISPLAY | 9 | "Quy, Tran Quang" | **PUBLICATION_CORROBORATED** via CrossRef DOI; 9 pubs |
| 60214163500 | SECONDARY | CONFIRMED | UNABLE_TO_DISPLAY | 7 | "Tran, Quang Quy" | Different tokenization; 7 pubs |
| 59768494800 | SECONDARY | CONFIRMED | UNABLE_TO_DISPLAY | 1 | "Quy, Tran Quang" | 1 pub: PLOS EoC paper (see note) |

**CrossRef DOI 10.4108/eetiot.5210:**  
Authors (full): Ta Thi Nguyet Trang · Pham Chien Thang · **Tran Quang, Quy** (pos. 3/3)  
Publisher: EAI 2024. **MATCHES** ID 58771615400. → PUBLICATION_CORROBORATED

**Notable finding — 59768494800 pub:**  
DOI `10.1371/journal.pone.0321009` (PLOS ONE) — this is the same paper from FINDING-010/FINDING-011:
- TS. Nguyễn Hải Minh (ID 59768336500) confirmed as author with email nhminh@ictu.edu.vn
- TS. Trần Quang Quý (ID 59768494800) is confirmed as co-author on this paper
- Paper has Expression of Concern (FINDING-011)
- **This is valid co-authorship** — not anomaly. Cross-GV link TQQ×NHM confirmed.

**Discrepancy — ICTU-WEB 12 pubs vs CSV 17:**  
CSV: 9+7+1 = 17 unique EIDs. ICTU-WEB: 12. Chênh lệch +5 — ICTU-WEB chỉ đếm primary ID hoặc dữ liệu cũ. Pattern nhất quán với NHH (+4) và Batch 1-3.

**Cross-ID EID duplicates:** 0

---

## Cross-GV Coauthorship (Batch 4 additions)

**Nguồn:** Tái lập từ `data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv` (660 dòng, toàn bộ), phương pháp giao tập EID theo từng cặp GV. Số liệu này là authoritative cho audit này.

**Ghi chú scope:** Các batch export CSV (batch1–4 publication_evidence.csv) chỉ chứa rows mà GV đó là lookup target; khi hai GVs cùng đồng tác giả trên một bài nhưng chỉ một GV được lookup trong batch đó, bài này không xuất hiện trong export của GV kia → join hai exports riêng lẻ cho kết quả thấp hơn CSV gốc. Đây là sự khác biệt về scope (full CSV vs batch exports), không phải lỗi số liệu.

| GV pair | EID count | Ghi chú |
|---------|-----------|---------|
| LHL × NHH | **9** EIDs | NHH và LHL đồng tác giả thường xuyên — cặp cao nhất |
| NHH × QXT | 2 EIDs | 2 bài trong tập chung QXT×NHH×TQQ |
| NHH × TQQ | **4** EIDs | Bao gồm 2 EIDs chung với QXT |
| QXT × TQQ | **5** EIDs | Bao gồm 2 EIDs chung với NHH |
| LMH × NHH | 1 EID | Fine-Tuning Generative LLMs paper |
| TQQ × NHM | 1 EID | PLOS EoC paper (FINDING-011) |
| LHL × TQQ | 1 EID | |

**Lưu ý quan trọng:** 2 EIDs (`2-s2.0-105000957095`, `2-s2.0-105041762468`) xuất hiện ở cả 3 cặp NHH×QXT, NHH×TQQ, QXT×TQQ — đây là bài có 3 GVs đồng tác giả. Khi đếm theo cặp (pairwise), mỗi EID này được tính 3 lần (một lần mỗi cặp). Tổng cross-GV EIDs không trùng từ Batch 4 góp thêm: 9+4+5−3(chung)−... = không cộng được naively.

**Tổng hợp 9 GVs Batch 1–4 (từ CSV gốc):**
- GV-publication links (tổng): 166
- Unique EIDs: 138
- Cross-GV EIDs (≥2 GVs): **25** EIDs không trùng
- Single-GV EIDs: 113

---

## DOI Cross-Check Summary

| DOI | GV | ID | Full author count | NVT/NHH/TQQ position | Result |
|-----|----|----|---|---|---|
| 10.5121/ijcnc.2026.18401 | NHH | 59775920700 | 3 | #3 "Ngo, Huu-Huy" | PUBLICATION_CORROBORATED |
| 10.4108/eetiot.5210 | TQQ | 58771615400 | 3 | #3 "Tran Quang, Quy" | PUBLICATION_CORROBORATED |

---

## Findings Summary

| Finding | GV | Severity | Type |
|---------|-----|---------|------|
| 5 name variants for Ngô Hữu Huy (incl. "Huy-Huy" typo) | Ngô Hữu Huy | LOW | NAME_TOKENIZATION_VARIANT + 1 TYPO |
| ICTU-WEB 18 vs CSV 22 pubs | Ngô Hữu Huy | LOW | COVERAGE_GAP — secondaries not counted |
| TQQ ID 59768494800 pub = PLOS EoC paper | Trần Quang Quý | INFO | CROSS_GV_COAUTHORSHIP + existing EoC finding |
| ICTU-WEB 12 vs CSV 13 pubs | Trần Quang Quý | LOW | MINOR_COUNT_DIFF |
| All 6 Scopus bodies UNABLE_TO_DISPLAY | Both | OBSERVATION | SCOPUS_SERVER_ISSUE (continues from Batch 3) |

---

## Deliverables

| File | Rows | Description |
|------|------|-------------|
| `batch4_id_evidence.csv` | 6 | Per-ID: browser + CSV + CrossRef evidence |
| `batch4_publication_evidence.csv` | 39 | 22 NHH + 17 TQQ unique EIDs, 0 intra-GV dups (strict UTF-8, re-exported 2026-10-27) |
| `batch4_browser_evidence.json` | — | Full structured evidence; cross-GV corrected (scope note added) |
| `batch4_summary.md` | — | This file (corrected: cross-GV table, TQQ pub count) |

---

*Tạo bởi Claude Sonnet 4.6 ngày 2026-10-27 — read-only, không DB write.*
