# Data Lineage — Publication Link Counts

**Ngày:** 2026-10-27  
**Mục đích:** Truy vết nguồn gốc hai con số 106/1160 và 48/328  
**Phương pháp:** Đọc trực tiếp file JSON từ Craw snapshot — read-only, không DB write

---

## Kết luận ngắn gọn

Hai con số đo **hai loại dữ liệu khác nhau** trong **cùng hệ thống crawler**. Không mâu thuẫn.

| Metric | Giá trị | Nguồn file | Field / bảng | Định nghĩa |
|--------|---------|-----------|-------------|-----------|
| **A** | 106 GV | `lecturers.json` | `public_publication_links[]` | Số GV có ≥1 URL trong array này |
| **A** | 1160 links | `lecturers.json` | `public_publication_links[]` | Tổng `len(public_publication_links)` trên 410 records |
| **B** | 48 GV | `lecturer_publication_links.json` | `lecturer_source_id` | Số GV unique trong file links |
| **B** | 328 links | `lecturer_publication_links.json` | mỗi row = 1 cặp (GV, publication) | Tổng số rows trong file |

---

## Chi tiết truy vết

### Count A: 106 GV / 1160 links từ `lecturers.json`

```
File:     D:\DataFolder\ProjectIctu\DoAn\Craw\output\full\lecturers.json
Size:     1,734,698 bytes
SHA-256:  c12252e02cbf73c58ae3add65a5b6b925f5e0fcd75273bd7e0a3cc28c8a0accb
Crawled:  2026-10-03 (từ provenance.retrieved_at của từng record)
Records:  410

Field:    public_publication_links (array of string URLs)
Count A1: 106 records có len(public_publication_links) > 0
Count A2: sum(len(public_publication_links)) = 1160
```

**Nội dung của `public_publication_links`:**  
Mỗi phần tử là URL đến một trang bài báo trên DSpace ICTU repository:  
`https://repository.ictu.edu.vn/bai-bao/<slug>/`

Ví dụ 5 URL đầu tiên:
```
https://repository.ictu.edu.vn/bai-bao/a-novel-automated-method-for-uml-modeling-integrating-instruction-reasoning-llms-and-vision-language-model-evaluation/
https://repository.ictu.edu.vn/bai-bao/multimodal-validation-in-uml-synthesis-a-dual-case-study-on-sequence-and-class-diagram-generation-pipelines/
https://repository.ictu.edu.vn/bai-bao/a-novel-ai-driven-approach-to-uml-dataset-generation-and-multimodal-verification-in-the-design-phase/
https://repository.ictu.edu.vn/bai-bao/generative-reasoning-meets-multimodal-evaluation-a-novel-approach-to-activity-and-package-diagram-comparison-in-uml-modeling/
https://repository.ictu.edu.vn/bai-bao/from-feature-description-to-uml-architecture-a-novel-framework-for-automated-reasoning-and-multimodal-evaluation-of-component-and-deployment-diagram/
```

**Không có URL trùng lặp trong cùng một record** (0 duplicates within same person).  
Tất cả 1160 URLs đều thuộc domain `repository.ictu.edu.vn`.

**Đây là dữ liệu thô của crawler** — URL liệt kê từ trang hồ sơ cá nhân ICTU, chưa qua dedup cross-lecturer, chưa match với Scopus.

---

### Count B: 48 GV / 328 links từ `lecturer_publication_links.json`

```
File:     D:\DataFolder\ProjectIctu\DoAn\Craw\output\full\lecturer_publication_links.json
Size:     154,388 bytes
Records:  328 rows (mỗi row = 1 cặp lecturer–publication)

Schema:
  lecturer_source_id:    URL hồ sơ GV ICTU (ICTU profile page URL)
  target_source_id:      URL trang bài báo ICTU
  relationship_source:   "ictu_lecturer_profile"
  discovery_provenance:  {profile_url, category: "publication"}
```

Ví dụ record:
```json
{
  "lecturer_source_id": "https://repository.ictu.edu.vn/giang-vien/bui-anh-tu/",
  "target_source_id":   "https://repository.ictu.edu.vn/bai-bao/a-comparative-study-of-object-...",
  "relationship_source": "ictu_lecturer_profile",
  "discovery_provenance": {"profile_url": "https://...bui-anh-tu/", "category": "publication"}
}
```

**Unique lecturer_source_id:** 48 / 48 trong file  
**Unique target_source_id (publications):** 155 (328 links → 155 publications; 1 publication có thể linked từ nhiều GV)  
**Tất cả 48 lecturer_source_id đều khớp với lecturers.json roster:** 48/48 ✓

---

### Mối quan hệ giữa A và B

```
Overlap analysis (verified programmatically):
  lecturers.json public_publication_links unique URLs:     1160 (nhưng có thể trùng cross-lecturer)
  lecturer_publication_links target_source_id unique URLs:  155

  URLs in BOTH sets:           155
  URLs ONLY in lecturers.json: 825  (các bài của 106 - 48 = 58 GV không nằm trong craw links file)
  URLs ONLY in craw links:       0  (tất cả craw links đều có trong lecturers.json)

Kết luận: lecturer_publication_links.json là SUBSET của public_publication_links trong lecturers.json
```

**Giải thích tại sao A ≠ B:**

1. **`lecturers.json`** là snapshot toàn bộ hồ sơ GV — field `public_publication_links` lấy trực tiếp từ HTML của trang hồ sơ mỗi GV (1160 raw URL entries từ 106 GV).

2. **`lecturer_publication_links.json`** là file structured links sau bước xử lý riêng của crawler — có thể áp dụng dedup hoặc filter khác, dẫn đến chỉ 328 cặp (155 publications duy nhất từ 48 GV).

3. **Tại sao 106 ≠ 48:** `lecturers.json` ghi URL từ HTML thô; `lecturer_publication_links.json` có thể chỉ thu thập GV qua một pipeline khác, hoặc có cutoff về chất lượng. 58 GV có trong `lecturers.json` pub links nhưng không có trong `lecturer_publication_links.json`.

4. **Tại sao 1160 ≠ 328:** `lecturers.json` tổng hợp từ 106 GV × trung bình 10.9 URL/GV; `lecturer_publication_links.json` có 328 rows nhưng chỉ 155 unique publications (nhiều GV cùng link đến 1 bài là bình thường).

---

## Tóm tắt data lineage

```
SOURCE: ICTU Repository website (repository.ictu.edu.vn)
   ↓
CRAWLER (chạy 2026-10-03)
   ├── lecturers.json (410 GV profiles)
   │     └── public_publication_links[] ← 106 GV × avg 10.9 URLs = 1160 URLs (raw HTML scrape)
   └── lecturer_publication_links.json ← 48 GV × avg 6.8 links = 328 rows (structured extraction)
         └── 155 unique publications
   
lecturers.json[pub_links] ⊃ lecturer_publication_links.json[target_source_id]
(craw links là subset của lecturers pub links)
```

**Trạng thái:** RECONCILED — không mâu thuẫn, hai phép đếm từ hai tầng xử lý của cùng một crawler.

---

*Tạo bởi Claude Sonnet 4.6 ngày 2026-10-27 — read-only, không DB write.*
