# Unified Diff Summary — docs/research/ (Batch 3 update)

**Ngày:** 2026-10-27  
**Note:** Files docs/research/ là untracked (tạo mới trong session này, chưa commit). Git diff không áp dụng. Bảng này mô tả thay đổi so với version v1.0 (Batch 1+2).

---

## 01_RESEARCH_KNOWLEDGE.md (v1.0 → v1.1)

| Dòng thay đổi | Trước | Sau |
|---|---|---|
| Header | `Cập nhật gần nhất: 2026-10-27 (Gate D.2 Batch 1+2)` | (không đổi) |
| Bảng giới hạn — hàng Scopus Preview | `Tất cả profile trả "Unable to display" trong một số thời điểm \| Phải dùng page title hoặc fallback` | `Batch 3 (2026-10-27): tất cả 6 profiles trả "Unable to display"; page title vẫn load → dùng làm PARTIAL evidence \| Fallback về page title; ghi BROWSER_OPENED thay vì PROFILE_ACCESSIBLE` |
| CHANGELOG | v1.0 only | v1.1 added: "Batch 3: cập nhật Scopus Preview server error note; DOI cross-check anomaly (FINDING-016)" |

**Net: +2 lines (1 table cell expanded, 1 changelog entry)**

---

## 02_ICTU_DATA_FINDINGS.md (v1.0 → v1.1)

| Phần | Thay đổi |
|---|---|
| Header | `Cập nhật gần nhất` → Batch 3 date |
| THỐNG KÊ | Thêm block "THỐNG KÊ CẬP NHẬT Batch 3" (6 dòng) |
| FINDING-014 (NEW) | Intra-GV EID dedup 0 dup — mở rộng Batch 3 (LHL 15 unique / NVT 14 unique) |
| FINDING-015 (NEW) | LHL 3 IDs: name tokenization variants (Le Hung Linh / Linh Le Hung / Le Linh); CrossRef E5 cho 58830932700 |
| FINDING-016 (NEW) | NVT DOI anomaly: 10.1109/MNET.010.2100509 CrossRef trả Taiwan author, không phải ICTU — FLAGGED |
| CHANGELOG | v1.1 added |

**Net: ~80 lines added (3 new findings + stats block + changelog). 0 lines deleted. 1 line edited (header).**

---

## 03_THESIS_DEFENSE_NOTES.md (v1.0 → v1.1)

| Phần | Thay đổi |
|---|---|
| Q1 "Không được khẳng định" | `26/83 IDs Batch 1+2` → `32/83 IDs Batch 1–3 (10/34 GVs)` |
| Q3 "Không được khẳng định" | Thêm: `Coverage audit hiện tại 32/83 IDs` |
| Q8 → Q9 spacing | Whitespace fix |
| Q10 (NEW) | DOI không khớp CrossRef — cách xử lý. Câu trả lời + giải thích + "Không được khẳng định" + Slide note |
| Bảng slide | `Coverage 26/83` → `Coverage 32/83 (Batch 3)` |
| CHANGELOG | v1.1 added |

**Net: ~25 lines added (Q10 + coverage updates + changelog). 0 lines deleted. 3 lines edited.**

---

## Tóm tắt

| File | Version | Lines added | Lines deleted | Lines edited |
|------|---------|-------------|---------------|--------------|
| 01_RESEARCH_KNOWLEDGE.md | v1.0 → v1.1 | +2 | 0 | 1 |
| 02_ICTU_DATA_FINDINGS.md | v1.0 → v1.1 | ~+80 | 0 | 1 |
| 03_THESIS_DEFENSE_NOTES.md | v1.0 → v1.1 | ~+25 | 0 | 3 |

Tất cả thay đổi là **append-only hoặc expansion**. Không có finding bị xóa. Không có lịch sử bị ghi đè.

---

*Tạo bởi Claude Sonnet 4.6 ngày 2026-10-27 — read-only audit, không DB write.*
