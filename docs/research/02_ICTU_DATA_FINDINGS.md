# 02 — Phát hiện dữ liệu ICTU

**Tạo lần đầu:** 2026-10-27  
**Cập nhật gần nhất:** 2026-10-28 (v1.6 — FINDING-019: 3 triple-GV EIDs; FINDING-020: phân tách 5 Scopus variants vs 2 publisher forms; FINDING-021: provenance lesson DOI→ID)  
**Phạm vi:** Các phát hiện có bằng chứng từ kiểm tra read-only. Không thay đổi dữ liệu nguồn.

> **Quy ước:**
> - Mỗi finding có ID ổn định **FINDING-NNN**.
> - Khi bổ sung bằng chứng: giữ ID cũ, thêm vào section "Bằng chứng bổ sung".
> - Khi kết luận bị bác bỏ: đánh dấu `[SUPERSEDED]` hoặc `[CORRECTED]`, ghi lý do và ngày.
> - **Không xóa finding đã có.** Thêm vào phần Historical Findings nếu không còn áp dụng.

---

## THỐNG KÊ (2026-10-27, sau Gate D.2 Batch 1+2)

- **Findings trước cập nhật:** 0 (file mới tạo)
- **Findings mới trong lần này:** 13
- **Findings được bổ sung bằng chứng:** 0
- **Findings bị supersede:** 0 (nhưng FINDING-007 và FINDING-008 ghi errata)
- **Tổng findings hiện tại:** 13
- **IDs thay đổi:** FINDING-001 đến FINDING-013 (tất cả mới)

## THỐNG KÊ CẬP NHẬT (2026-10-27, sau Gate D.2 Batch 3)

- **Findings trước cập nhật:** 13
- **Findings mới trong lần này:** 3 (FINDING-014, FINDING-015, FINDING-016)
- **Findings được bổ sung bằng chứng:** 1 (FINDING-006 — extended to Batch 3)
- **Findings bị supersede:** 0
- **Tổng findings hiện tại:** 16

## THỐNG KÊ CẬP NHẬT (2026-10-27, sau Gate D.2 Batch 4)

- **Findings trước cập nhật:** 16
- **Findings mới trong lần này:** 3 (FINDING-017, FINDING-018, FINDING-019)
- **Findings được bổ sung bằng chứng:** 1 (FINDING-011 — TQQ×NHM cross-GV co-authorship bổ sung bằng chứng)
- **Findings bị supersede:** 0
- **Tổng findings hiện tại:** 19
- **IDs thay đổi:** FINDING-017 đến FINDING-019 (mới)
- **IDs thay đổi:** FINDING-014 đến FINDING-016 (mới)

## THỐNG KÊ CẬP NHẬT (2026-10-28, sau errata Batch 3–5)

- **Findings trước cập nhật:** 19 (+ FINDING-020 từ Batch 5 = 20)
- **Findings mới trong lần này:** 1 (FINDING-021)
- **Findings được sửa/cập nhật:** 2 (FINDING-019 [CORRECTED: thêm triple EID thứ 3], FINDING-020 [CORRECTED: phân tách nguồn])
- **Findings bị supersede:** 0
- **Tổng findings hiện tại:** 21
- **Errata mới:** E10 (DOI→ID mapping), E11 (Q11 count + FINDING-019)

---

## FINDING-001 — Kho giảng viên ICTU: 410 hồ sơ

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Bao nhiêu giảng viên ICTU có hồ sơ trên Repository? |
| **Nguồn dữ liệu** | `lecturers.json` — crawler snapshot |
| **Phương pháp** | Đọc JSON, đếm records |
| **Kết quả** | **410 records**. SHA-256: `c12252e02cbf73c58ae3add65a5b6b925f5e0fcd75273bd7e0a3cc28c8a0accb`. Crawled 2026-10-03. |
| **Ý nghĩa nghiệp vụ** | Tổng quy mô roster. Hệ thống cần xử lý 410 hồ sơ. |
| **Mức độ chắc chắn** | CAO — đếm trực tiếp từ file |
| **Hạn chế** | Crawler snapshot tại một thời điểm; có thể đã thay đổi |
| **Evidence** | `docs/qa/gate_d1r/master_lecturers_inventory.csv` (410 dòng) |
| **Trạng thái** | CONFIRMED |

---

## FINDING-002 — ICTU-WEB: 34 giảng viên nhiều Scopus IDs

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | ICTU-WEB liệt kê bao nhiêu GV có nhiều Scopus IDs cần rà soát? |
| **Nguồn dữ liệu** | `repository.ictu.edu.vn/huong-dan-gop-tai-khoan-scopus/` |
| **Phương pháp** | Browser DOM extraction, 2026-10-27 |
| **Kết quả** | Bảng có **35 hàng = 1 header + 34 data rows**. Tổng 83 Scopus ID occurrences trong 34 dòng. |
| **Ý nghĩa nghiệp vụ** | 34/410 ≈ 8.3% giảng viên có vấn đề đa ID — đủ lớn để cần quy trình xử lý có hệ thống |
| **Mức độ chắc chắn** | CAO — DOM thực tế, 2026-10-27 |
| **Hạn chế** | Danh sách có thể cập nhật sau ngày kiểm tra. Chưa kiểm tra được tất cả 34 GVs. |
| **Evidence** | `docs/qa/gate_d1r/ictu_multi_scopus_ids.csv` (34 rows), `docs/qa/gate_d2/batch2_browser_evidence.json` (DOM confirmation) |
| **Trạng thái** | CONFIRMED |

> **Ghi chú lịch sử:** Ban đầu tuyên bố "35 GV"; sau xác minh DOM = 35 hàng = 1 header + 34 data. (Xem RECONCILIATION_REPORT.md section D1.)

---

## FINDING-003 — 10 IDs nhập nhằng, 59 IDs chưa rõ chủ sở hữu

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Ngoài 34 GV nhiều IDs, còn bao nhiêu IDs chưa xác định chủ sở hữu? |
| **Nguồn dữ liệu** | ICTU-WEB (nguồn "DOM" theo ictu_ambiguous_ids.csv, ictu_unknown_owner_ids.csv) |
| **Phương pháp** | Đọc file CSV từ Gate D.1 |
| **Kết quả** | **10 IDs nhập nhằng** (có thể thuộc nhiều GV); **59 IDs chưa rõ chủ sở hữu** |
| **Ý nghĩa nghiệp vụ** | Tổng bức tranh: không chỉ 83 IDs trong 34 GV mà còn 69 IDs không rõ ràng |
| **Mức độ chắc chắn** | TRUNG BÌNH — chưa xác minh browser cho tất cả |
| **Hạn chế** | Chưa kiểm tra từng ID trong hai nhóm này |
| **Evidence** | `docs/qa/gate_d1r/ictu_ambiguous_ids.csv`, `docs/qa/gate_d1r/ictu_unknown_owner_ids.csv` |
| **Trạng thái** | SOURCE_CLAIM — cần kiểm tra thêm |

---

## FINDING-004 — Publication links trong ICTU crawler

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Bao nhiêu GV có công bố được liên kết và có bao nhiêu links? |
| **Nguồn dữ liệu** | `lecturers.json` (field `public_publication_links`) + `lecturer_publication_links.json` |
| **Phương pháp** | Đọc JSON, đếm programmatically |
| **Kết quả** | `lecturers.json`: 106 GV có links, 1160 URL occurrences (có thể trùng cross-lecturer). `lecturer_publication_links.json`: 48 GV, 328 rows, 155 unique target publications. Hai tập có quan hệ subset: craw links ⊂ lecturers pub links. |
| **Ý nghĩa nghiệp vụ** | Cần phân biệt raw URL count với unique publication count khi báo cáo |
| **Mức độ chắc chắn** | CAO — xác minh programmatically |
| **Evidence** | `docs/qa/gate_d1r/data_lineage_pub_counts.md` |
| **Trạng thái** | CONFIRMED |

---

## FINDING-005 — ORCID collision: Bùi Thị Quyên & Vi Thị Bích Ngọc

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Hai giảng viên khác nhau dùng chung một ORCID? |
| **Nguồn dữ liệu** | `lecturers.json` + ICTU Repository profiles + orcid.org |
| **Phương pháp** | Phát hiện programmatically; xác minh browser thực tế 2026-10-27 |
| **Kết quả** | ORCID `0009-0001-3939-8656` được hiển thị trên cả hồ sơ ThS. Bùi Thị Quyên (btquyen@ictu.edu.vn) VÀ ThS. Vi Thị Bích Ngọc (ngocvtb@ictu.edu.vn). orcid.org xác nhận ORCID này thuộc Vi Thị Bích Ngọc (tên, tổ chức ICTU, chức danh Lecturer of Chinese Language, tự nhập). |
| **Ý nghĩa nghiệp vụ** | Lỗi nhập liệu trong ICTU Repository — ORCID của Bùi Thị Quyên bị gán sai. Không dùng ORCID ICTU làm bằng chứng danh tính duy nhất. |
| **Mức độ chắc chắn** | CAO — browser + orcid.org |
| **Hạn chế** | Chỉ xác minh 1/10 cặp ORCID trùng bằng browser. 9 cặp SAME_NAME còn lại chưa mở browser. |
| **Evidence** | `docs/qa/gate_d1r/orcid_collision_review.csv`, `docs/qa/gate_d1r/orcid_browser_evidence.json` |
| **Trạng thái** | CONFIRMED (đối với cặp này). 9 cặp còn lại: SOURCE_CLAIM |

> **Lưu ý:** orcid_browser_evidence.json gốc chứa thông tin PII (DOB, phone). Không chia sẻ file này bên ngoài nhóm nghiên cứu.

---

## FINDING-006 — Intra-GV EID dedup: 0 duplicate trong Batch 1+2

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Các Scopus IDs của cùng một giảng viên có chứa bài báo trùng nhau không? |
| **Nguồn dữ liệu** | `Truong_Quang_Huy_Scopus_Sep2026.csv` (660 rows) |
| **Phương pháp** | Full scan 660 rows; groupby GV; đếm EID duplicates trong từng group. 2026-10-27. |
| **Kết quả** | **0 duplicate EIDs** trong từng nhóm ID của cùng GV cho 5 GVs Batch 1+2 (QXT, DQA, PTN, LMH, NHM). Xác nhận trên toàn bộ 660 rows (không chỉ sample 21 rows như Batch 1 ban đầu). |
| **Ý nghĩa nghiệp vụ** | Các secondary IDs chứa publication sets khác biệt — cần giữ tất cả khi thống kê. |
| **Mức độ chắc chắn** | CAO (trong phạm vi CSV này) |
| **Hạn chế** | CSV là personal export của Trưởng Quang Huy (Sep 2026) — không phải toàn bộ Scopus của ICTU. Chỉ chứa pubs mà QH đồng tác giả hoặc trong cùng export batch. |
| **Evidence** | `docs/qa/gate_d2/batch1_full_csv_reconciliation.csv`, `docs/qa/gate_d2/batch2_publication_evidence.csv` |
| **Trạng thái** | CONFIRMED (trong phạm vi CSV này) |

---

## FINDING-007 — Cross-GV EID: 5 bài đồng tác giả giữa các GVs

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Có EID nào xuất hiện ở nhiều giảng viên khác nhau trong dữ liệu Batch 1+2? |
| **Nguồn dữ liệu** | Batch 1+2 CSV files (98 pub rows) |
| **Phương pháp** | Cross-join EIDs từ tất cả 5 GVs; đếm EID xuất hiện ≥2 lần |
| **Kết quả** | **5 EIDs** xuất hiện ở 2 GVs khác nhau: 3 bài chung lmhue–qxtruong, 2 bài chung lmhue–ptnghia. Đây là quan hệ đồng tác giả, không phải lỗi data. |
| **Ý nghĩa nghiệp vụ** | **Không được cộng tổng publication cá nhân để ra tổng ICTU** — sẽ đếm trùng. Phải dùng distinct EID khi thống kê tổng sản lượng. |
| **Mức độ chắc chắn** | CAO — xác nhận bởi owner độc lập 2026-10-27 |
| **Hạn chế** | Chỉ trong phạm vi 5 GVs Batch 1+2. Khi kiểm tra thêm GVs, con số này sẽ tăng. |
| **Evidence** | Xác nhận độc lập trong GATE_D2_INDEPENDENT_REVIEW_20261027.md |
| **Trạng thái** | CONFIRMED |

---

## FINDING-008 — DQA: CSV chứa 7 pubs vs ICTU-WEB 53 pubs

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | GS.TS. Đặng Quang Á có 53 pubs trên ICTU-WEB nhưng CSV chỉ có 7. Tại sao? |
| **Nguồn dữ liệu** | `Truong_Quang_Huy_Scopus_Sep2026.csv` + ICTU-WEB |
| **Phương pháp** | Scan CSV; đối chiếu với ICTU-WEB count |
| **Kết quả** | CSV có 5 pubs cho ID 36852696600 + 2 pubs cho 55331947800 = 7 tổng. ICTU-WEB ghi 53 cho primary. |
| **Ý nghĩa nghiệp vụ** | CSV không phải nguồn toàn bộ pubs của DQA. Không dùng CSV để đánh giá completeness cho GVs khác là đồng tác giả ít của QH. |
| **Mức độ chắc chắn** | CAO về con số; INFERENCE về nguyên nhân |
| **Hạn chế** | [ERRATA — 2026-10-27] Nguyên nhân "CSV là personal export của QH" là INFERENCE từ tên file, chưa xác minh quy trình export. Không khẳng định đây là nguyên nhân duy nhất. |
| **Evidence** | `docs/qa/gate_d2/batch1_full_csv_reconciliation.csv` |
| **Trạng thái** | CONFIRMED (con số); INFERENCE (nguyên nhân) |

---

## FINDING-009 — Scopus IDs "page not found": LMH secondary IDs

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | 3/5 secondary IDs của ThS. Lương Thị Minh Huế trả "page not found or merged" |
| **Nguồn dữ liệu** | Scopus Preview, browser thực tế 2026-10-27 |
| **Phương pháp** | Navigate + DOM extraction |
| **Kết quả** | IDs 59708285400, 60248511400, 60320211100 trả: "This author profile does not exist or has merged with another author profile." |
| **Ý nghĩa nghiệp vụ** | Nếu đã merge vào primary 60319803200, pub count sẽ tăng; hệ thống phải xử lý trạng thái này. |
| **Mức độ chắc chắn** | CAO về trạng thái "not found"; THẤP về nguyên nhân |
| **Hạn chế** | [ERRATA — 2026-10-27] "Likely merged" là disjunction chưa chứng minh: có thể đã merged, hoặc xóa, hoặc lỗi truy cập. Không kết luận MERGED_INTO_PRIMARY mà chỉ ghi NOT_FOUND_MERGE_UNVERIFIED. |
| **Evidence** | `docs/qa/gate_d2/batch2_browser_evidence.json` |
| **Trạng thái** | PROFILE_NOT_FOUND; nguyên nhân UNVERIFIED |

---

## FINDING-010 — Publisher evidence: NHM + DOI 10.1371/journal.pone.0321009

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Bằng chứng từ nhà xuất bản có xác nhận danh tính TS. Nguyễn Hải Minh không? |
| **Nguồn dữ liệu** | PLOS ONE: `https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0321009` |
| **Phương pháp** | Kiểm tra trực tiếp trang nhà xuất bản bởi owner 2026-10-27 |
| **Kết quả** | Tác giả: Nguyen Hai Minh. Email liên hệ: **nhminh@ictu.edu.vn**. Cơ quan: ICTU, ĐH Thái Nguyên. ORCID: 0009-0002-6213-6299. Ngày xuất bản: 29/04/2025. |
| **Ý nghĩa nghiệp vụ** | Email tổ chức trực tiếp từ nhà xuất bản = bằng chứng E5 (mạnh nhất). Không cần suy luận từ tên hay affiliation. |
| **Mức độ chắc chắn** | CAO |
| **Hạn chế** | Chỉ 1 bài trong CSV có loại bằng chứng này. |
| **Evidence** | URL PLOS: `https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0321009`. Xác nhận độc lập trong GATE_D2_INDEPENDENT_REVIEW_20261027.md. |
| **Trạng thái** | PUBLICATION_CORROBORATED |

---

## FINDING-011 — Expression of Concern: bài báo NHM 2025

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Trạng thái học thuật của bài báo DOI 10.1371/journal.pone.0321009 |
| **Nguồn dữ liệu** | PLOS ONE: `https://doi.org/10.1371/journal.pone.0343787` |
| **Phương pháp** | Kiểm tra trang nhà xuất bản bởi owner 2026-10-27 |
| **Kết quả** | PLOS ban hành **Expression of Concern** ngày 26/02/2026 liên quan đến trích dẫn, tham khảo và chính sách dữ liệu. |
| **Ý nghĩa nghiệp vụ** | Đây là metadata trạng thái học thuật của bài báo — KHÔNG đồng nghĩa bài bị RETRACTED hay tác giả bị gán sai danh tính. Hệ thống nên phân biệt: (a) xác minh đúng tác giả vs (b) đánh giá trạng thái bài báo. Hai quyết định này độc lập. |
| **Mức độ chắc chắn** | CAO — trang nhà xuất bản |
| **Hạn chế** | Expression of Concern có thể được rút lại hoặc nâng lên Retraction trong tương lai. |
| **Evidence** | GATE_D2_INDEPENDENT_REVIEW_20261027.md (kiểm tra của owner) |
| **Trạng thái** | CONFIRMED |

---

## FINDING-012 — Colorectal cancer research: NHM multi-ID pattern

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Nghiên cứu ung thư đại trực tràng có phải "lạc lĩnh vực" với ID 59768336500 không? |
| **Nguồn dữ liệu** | CSV + ICTU Repository |
| **Phương pháp** | Đối chiếu chéo: tìm nghiên cứu cùng chủ đề ở các IDs khác của cùng GV |
| **Kết quả** | CSV có bài "Colorectal Cancer Diagnosis with Complex Fuzzy Inference System" năm 2020 thuộc ID `7003299472` của cùng NHM. ICTU Repository cũng ghi nhận bài này. DOI: `10.1007/978-981-32-9186-7_2`. URL: `https://repository.ictu.edu.vn/bai-bao/colorectal-cancer-diagnosis-with-complex-fuzzy-inference-system/`. |
| **Ý nghĩa nghiệp vụ** | Không nên dùng "domain inconsistency" làm nghi vấn danh tính khi chưa kiểm tra toàn bộ IDs của cùng GV. Bằng chứng từ email nhà xuất bản mạnh hơn suy luận từ lĩnh vực. |
| **Mức độ chắc chắn** | CAO |
| **Evidence** | GATE_D2_INDEPENDENT_REVIEW_20261027.md; CSV row EID 2-s2.0-85124904645 |
| **Trạng thái** | CONFIRMED |

> **Errata trên báo cáo Claude:** FINDING-012 supersedes cờ "DOMAIN_INCONSISTENCY — MEDIUM" trong batch2_summary.md. Cờ đó sai vì chưa kiểm tra toàn bộ IDs. Batch2_summary.md giữ nguyên để truy xuất lịch sử; kết luận đúng là trong FINDING-012 này.

---

## FINDING-013 — 10-digit Scopus ID 7003299472 là valid

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Scopus ID 10 chữ số có hợp lệ không? |
| **Nguồn dữ liệu** | ICTU-WEB DOM + Scopus Preview + CSV |
| **Phương pháp** | Browser, DOM extraction, CSV scan |
| **Kết quả** | ID `7003299472` (10 chữ số): (a) ICTU-WEB liệt kê; (b) Scopus Preview trả profile `Minh, Nguyen Hai` @ ICTU; (c) 5 pubs trong CSV. Valid và đang được sử dụng. |
| **Ý nghĩa nghiệp vụ** | Hệ thống không được reject ID vì độ dài; phải xử lý cả 10-digit và 11-digit IDs. |
| **Mức độ chắc chắn** | CAO |
| **Evidence** | `docs/qa/gate_d2/batch2_id_evidence.csv` (row 7), `docs/qa/gate_d2/batch2_browser_evidence.json` |
| **Trạng thái** | CONFIRMED |

---

---

## FINDING-014 — Intra-GV EID dedup: 0 duplicate mở rộng sang Batch 3

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | LHL và NVT (Batch 3) có bị trùng EID cross-ID không? |
| **Nguồn dữ liệu** | `Truong_Quang_Huy_Scopus_Sep2026.csv` |
| **Phương pháp** | Python scan: groupby LHL IDs (3) và NVT IDs (3); đếm EID duplicates, 2026-10-27 |
| **Kết quả** | **0 duplicate EIDs** intra-GV cho cả LHL (15 unique EIDs / 3 IDs) và NVT (14 unique EIDs / 3 IDs). FINDING-006 confirmed extended to Batch 3. |
| **Ý nghĩa nghiệp vụ** | Các secondary IDs mang thêm công bố duy nhất, không trùng primary. Quan trọng khi tổng hợp statistics. |
| **Mức độ chắc chắn** | CAO |
| **Hạn chế** | Trong phạm vi CSV này (personal export QH). Không phản ánh toàn bộ Scopus. |
| **Evidence** | `docs/qa/gate_d2/batch3_publication_evidence.csv` (29 rows, 0 dups); `docs/qa/gate_d2/batch3_id_evidence.csv` |
| **Trạng thái** | CONFIRMED |

---

## FINDING-015 — LHL secondary IDs: name tokenization variants

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | Ba IDs của TS. Lê Hùng Linh có tên khác nhau — là cùng một người không? |
| **Nguồn dữ liệu** | Scopus Preview page titles + CSV author names + CrossRef 2026-10-27 |
| **Phương pháp** | Browser page titles + CrossRef DOI check |
| **Kết quả** | 56548128100: "Le, Hung Linh" (13 pubs, 2014–2026); 58830932700: "Linh, Le Hung" (1 pub 2010, CrossRef xác nhận "Le Hung, Linh" cho IEEE paper); 57200439355: "Le, Linh" (1 pub 2018). Ba dạng tên là biến thể của cùng tên tiếng Việt Lê Hùng Linh. |
| **Ý nghĩa nghiệp vụ** | Minh họa điển hình cho vấn đề tên tiếng Việt: 3 IDs từ 3 cách viết khác nhau. Bằng chứng ngữ nghĩa cao nhưng chưa đạt mức IDENTITY_VERIFIED (chưa có email từ nhà xuất bản cho tất cả IDs). |
| **Mức độ chắc chắn** | CAO về name variants; TRUNG BÌNH về same-person inference |
| **Hạn chế** | Scopus Preview body "Unable to display" cho cả 3 (server error 2026-10-27). Chưa có email/ORCID publisher-level cho 57200439355. |
| **Evidence** | `docs/qa/gate_d2/batch3_browser_evidence.json`; CrossRef 10.1109/ICCA.2010.5524407 |
| **Trạng thái** | BROWSER_OPENED; 58830932700 → PUBLICATION_CORROBORATED |

> **Không kết luận:** Ba IDs chắc chắn là cùng một người chỉ từ tên và số lượng bài. Cần email nhà xuất bản hoặc ORCID cho 57200439355 trước khi ACCEPT.

---

## FINDING-016 — NVT DOI cross-check: 10.1109/MNET.010.2100509 — Van-Tao Nguyen là đồng tác giả thứ 5

> **[CORRECTED — 2026-10-27]** Nhận định ban đầu (v1.1) là FALSE POSITIVE do lỗi kỹ thuật: code CrossRef chỉ đọc `.slice(0,4)` tác giả đầu, bỏ sót tác giả thứ 5. Nội dung cũ được giữ trong section "Nhận định cũ (sai)" dưới đây. Kết luận đúng ở mục "Kết quả sau sửa".

| Trường | Nội dung |
|--------|----------|
| **Vấn đề** | DOI `10.1109/MNET.010.2100509` trong CSV thuộc ID 56967513900 (NVT) — có khớp với Nguyễn Văn Tảo không? |
| **Nguồn dữ liệu** | CrossRef API (full author list) + MDPI page + ICTU Repository + DBLP — kiểm tra 2026-10-27 |
| **Phương pháp** | CrossRef full author list (5 tác giả); ICTU Repository article page; NYCU scholar portal; DBLP |
| **Kết quả sau sửa** | Bài báo có **5 tác giả**: (1) Van-Linh Nguyen (CCU Taiwan), (2) Ren-Hung Hwang (NYCU Taiwan), (3) Po-Ching Lin (CCU Taiwan), (4) Abhishek Vyas (CCU Taiwan), **(5) Van-Tao Nguyen (Thai Nguyen University of ICT, Vietnam)**. CrossRef xác nhận tác giả thứ 5 là Van-Tao Nguyen từ ICTU. DBLP: `dblp.org/rec/journals/network/NguyenHLVN23`. NYCU scholar: `scholar.nycu.edu.tw/...`. ICTU Repository: `repository.ictu.edu.vn/bai-bao/towards-...`. |
| **Ý nghĩa nghiệp vụ** | DOI này hợp lệ cho ID 56967513900 — không phải anomaly. Bài này là công trình hợp tác quốc tế (4 tác giả Taiwan + 1 tác giả ICTU). Không cần human reviewer cho lý do này. |
| **Mức độ chắc chắn** | CAO — CrossRef full list xác nhận |
| **Hạn chế** | Bằng chứng này chứng minh Van-Tao Nguyen đồng tác giả bài cụ thể này, KHÔNG tự động chứng minh toàn bộ ID 56967513900 thuộc đúng TS. Nguyễn Văn Tảo ICTU. |
| **Evidence** | CrossRef API 2026-10-27 (full 5-author list); DBLP; NYCU scholar portal; ICTU Repository |
| **Trạng thái** | PUBLICATION_CORROBORATED (bài này); IDENTITY_UNVERIFIED (toàn bộ ID) |

**Nhận định cũ (sai — v1.1, 2026-10-27):**
> "CrossRef: Tác giả là 'Nguyen, Van-Linh' từ National Chung Cheng University, Taiwan — không phải ICTU và không phải Nguyễn Văn Tảo. ... DOI_ANOMALY — FLAGGED FOR HUMAN REVIEW."

**Nguyên nhân sai:** Code Python dùng `.slice(0,4)` chỉ lấy 4 tác giả đầu. Tác giả thứ 5 (Van-Tao Nguyen) bị cắt. Kết luận "không có Van-Tao Nguyen" là không đúng.

**Bài học:** Khi cross-check DOI với CrossRef, phải đọc **toàn bộ** danh sách tác giả, không giới hạn số lượng. Bài báo hợp tác nhiều tác giả (≥5) thường có tác giả ICTU không ở vị trí đầu.

---

## FINDING-017 — NHH name variant "Ngo, Huuhuy": hyphen dropped trong Scopus profile

| Trường | Giá trị |
|--------|---------|
| **Scopus ID** | 59775920700 |
| **GV** | TS. Ngô Hữu Huy (nhhuy@ictu.edu.vn) |
| **Phát hiện** | Scopus profile title = "Ngo, Huuhuy" — hyphen bị bỏ giữa "Huu" và "Huy". Trong CSV: có entry "Ngo, Huy-Huy" (57210434401, 2026) — đây là typo (đảo nhầm "Huu" thành "Huy"). |
| **Tổng cộng** | 5 name variants: "Ngo, Huu-Huy" / "Huy, Ngo Huu" / "Ngo, Huuhuy" / "Ngo, Huy-Huy" (typo) / "Ngo, Huu Huy" |
| **Mức độ** | LOW — name variants expected, không ảnh hưởng dedup nếu dùng EID |
| **Khuyến nghị** | Reviewer cần biết typo "Huy-Huy" để không nhầm là người khác khi dedup tên thủ công |
| **Bằng chứng** | Browser: Scopus Preview title (2026-10-27). CSV scan: `data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv` |

---

## FINDING-018 — Cross-GV scope: full CSV vs batch export CSV cho kết quả khác nhau

| Trường | Giá trị |
|--------|---------|
| **Phạm vi** | Tất cả 9 GVs Batch 1–4 |
| **Phát hiện** | Khi tính cross-GV EID bằng cách join các batch export CSV riêng lẻ, kết quả thấp hơn tính từ full 660-row CSV gốc. |
| **Giải thích** | Batch export chỉ chứa rows mà GV đó là lookup target. Nếu GV A và GV B đồng tác giả trên bài X, nhưng bài X chỉ được export trong batch của GV A (vì ID của GV A match, không phải GV B), thì bài X không có trong export của GV B → join hai exports cho 0 overlap. Full CSV chứa cả hai → intersection = 1. |
| **Số liệu** | Full CSV: 25 cross-GV EIDs (9 GVs). Batch exports riêng lẻ: thấp hơn, tùy cặp. |
| **Tác động** | HYPOTHESIS về "TQQ và NHH không đồng tác giả" từ batch export cần được xác minh lại bằng full CSV trước khi đưa vào báo cáo. |
| **Kết luận** | Full CSV là nguồn authoritative. Batch exports là subset, không đủ để kết luận 0 cross-GV. |
| **Mức độ** | MEDIUM — ảnh hưởng cách diễn giải số liệu cross-GV trong báo cáo |
| **Bằng chứng** | Python recount ngày 2026-10-27; xem `docs/qa/gate_d2/batch4_browser_evidence.json` section `cross_gv_coauthorship` |

---

## FINDING-019 — 9-GV tích lũy: 166 links, 138 unique EIDs, 25 cross-GV EIDs

| Trường | Giá trị |
|--------|---------|
| **Phạm vi** | 9 GVs: QXT, DQA, PTN, LMH, NHM, LHL, NVT, NHH, TQQ (Batch 1–4) |
| **Số liệu** | GV-publication links: 166; Unique EIDs: 138; Cross-GV EIDs (≥2 GVs): 25; Single-GV EIDs: 113 |
| **Cross-GV breakdown** | LHL×NHH: 9 (cặp cao nhất) · NHH×TQQ: 4 · QXT×TQQ: 5 · NHH×QXT: 2 · LMH×NHH: 1 · TQQ×NHM: 1 · LHL×TQQ: 1 · (và các cặp từ Batch 1–3: LMH×QXT: 3, LMH×PTN: 2, NHM×NVT: 1, NVT×QXT: 1, NVT×PTN: 1) |
| **3-way papers** | **[CORRECTED 2026-10-28] 3 EIDs** xuất hiện trong đúng 3 GVs cùng lúc: (1) `2-s2.0-105000957095` — NHH, QXT, TQQ; (2) `2-s2.0-105041762468` — NHH, QXT, TQQ; (3) `2-s2.0-85208627580` — LHL, NHH, TQQ. *(Phiên bản v1.3–v1.5 chỉ liệt kê 2 EIDs đầu; EID thứ 3 bị bỏ sót.)* |
| **Xác minh** | Python set intersection `data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv`, tái xác nhận 2026-10-28. Kết quả: `eid_gvs[eid]` = {'LHL','NHH','TQQ'} cho EID 3. |
| **Mức độ** | INFO — baseline cho Batch 5+ |
| **Bằng chứng** | Python scan từ `data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv` ngày 2026-10-27; tái xác nhận 2026-10-28 |

---

## FINDING-020 — DTB: 5 Scopus profile variants + 2 publisher metadata forms cho Đỗ Thị Bắc

> **[CORRECTED 2026-10-28]** Phiên bản v1.4 gộp chung 7 dạng tên không phân biệt nguồn. Sau sửa: **5 dạng đến từ Scopus profile page titles** (metadata của Scopus), **2 dạng đến từ CrossRef publisher metadata** (metadata của nhà xuất bản). Hai nguồn này có nguyên nhân và tác động khác nhau — không được gộp chung.

| Trường | Giá trị |
|--------|---------|
| **Phạm vi** | TS. Đỗ Thị Bắc (dtbac@ictu.edu.vn) — 5 Scopus IDs |
| **5 Scopus profile name variants** | Từ Scopus Preview page titles (5 IDs, 5 dạng): `59526508700` → "Do, Thi Bac"; `57819997900` → "Do, Bac Thi"; `59663496400` → "Bac, Do Thi"; `59159284800` → "do Thi, Bac" (lowercase family name); `57899449200` → "ThiBac, Do" (middle+given ghép vào family) |
| **2 CrossRef publisher metadata forms** | Từ CrossRef API (publisher-supplied): DOI `10.1007/s00542-026-06031-2` → "Thi-Bac Do" (Springer 2026, pos. 1); DOI `10.11591/eei.v14i3.9064` → "Bac Thi Do" (BEEI/IAES 2025, pos. 5) |
| **Nguồn gốc khác nhau** | Scopus variants: Scopus tự tokenize/chuẩn hóa khi tạo profile từ metadata bài báo lịch sử → sai số tích lũy qua nhiều lần. CrossRef forms: tác giả hoặc editor nhà xuất bản nhập khi submit → phản ánh thực tế submission. |
| **So sánh** | NHH: 5 variants (Batch 4). LHL: 3 variants (Batch 3). DTB: 5 Scopus + 2 CrossRef = 7 tổng, cao nhất trong audit. |
| **Mức độ** | LOW — name variants expected. Không ảnh hưởng dedup EID. Nhưng gây khó khăn cho name-based matching. Hệ thống phải normalize trước khi so sánh tên. |
| **Bằng chứng** | Browser Scopus Preview (2026-10-27); CrossRef full author list DOI check (2026-10-27). |

---

## FINDING-021 — Bài học provenance: DOI evidence phải gắn với đúng Scopus ID trong cùng CSV row

| Trường | Giá trị |
|--------|---------|
| **Phạm vi** | Áp dụng cho toàn bộ audit Gate D.2 |
| **Phát hiện** | Trong phiên bản đầu tiên của batch5_id_evidence.csv, 4 DOIs được gán làm bằng chứng cho sai Scopus ID. Ví dụ: DOI `10.1007/978-3-031-50818-9_35` được gán nhầm cho ID `26637116200` (primary của PDL), trong khi CSV row thực tế chứa DOI đó có Author(s) ID = `58805722900` (secondary). |
| **Nguyên nhân lỗi** | Claude gán DOI cho ID "quan trọng nhất" hoặc "primary" của GV đó, thay vì đọc cột `Author(s) ID` trong chính row chứa DOI đó trên CSV. |
| **Quy tắc đúng** | Một DOI chỉ có thể dùng làm bằng chứng cho Scopus Author ID mà **Scopus CSV gán trực tiếp** cho DOI đó (trong cùng row). Không được "chuyển" DOI sang ID khác của cùng người — dù hai IDs đó có thể thuộc cùng một người. |
| **Ý nghĩa thiết kế** | Bằng chứng phải mang tính provenance rõ ràng: biết rõ nguồn nào gán entity nào với entity nào. Khi các bằng chứng được "chuyển" giữa IDs của cùng người, chất lượng audit suy giảm. |
| **Sửa trong audit** | Tất cả 4 DOI→ID mapping sai trong batch5 đã được sửa ngày 2026-10-28 sau independent review của owner. Xem Errata E10. |
| **Mức độ** | HIGH-PROCESS — lỗi quy trình, ảnh hưởng chất lượng evidence |
| **Bằng chứng** | Python DOI→ID lookup từ `data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv`; independent review table ngày 2026-10-28. |

---

## ERRATA ĐÃ GHI NHẬN (từ kiểm tra độc lập 2026-10-27)

| Số | Nội dung sai trong báo cáo Claude | Đúng | Áp dụng cho |
|---|---|---|---|
| E1 | Batch 2: "33 pubs + 5 negative rows" | 34 pubs + 4 negative rows | batch2_summary.md dòng 87 |
| E2 | "Likely merged" cho 3 IDs LMH | NOT_FOUND_MERGE_UNVERIFIED | FINDING-009 |
| E3 | "Domain inconsistency MEDIUM" cho 59768336500 | Cần tắt cờ này — có bằng chứng pub cùng chủ đề từ 2020 | FINDING-012 supersedes |
| E4 | "CSV là personal export của QH" cho DQA | Là INFERENCE từ tên file, chưa xác minh | FINDING-008 |
| E5 | "0 EID overlap" có nghĩa tuyệt đối | Đúng trong từng nhóm GV, không đúng cross-GV | FINDING-006 và FINDING-007 |
| E6 | FINDING-016 v1.1: "CrossRef không có Van-Tao Nguyen" → DOI_ANOMALY | FALSE POSITIVE — Code chỉ đọc 4 tác giả đầu, bỏ sót tác giả thứ 5 (Van-Tao Nguyen, ICTU). CrossRef full list xác nhận. | FINDING-016 [CORRECTED] |
| E7 | batch3_id_evidence.csv: LHL 58830932700 gán evidence_level = PUBLICATION_CORROBORATED với chú thích "E5 evidence" | E5 yêu cầu email/ORCID/affiliation từ publisher. DOI 10.1109/ICCA.2010.5524407 chỉ xác nhận tên. Label đúng: PUBLICATION_NAME_CORROBORATED. | batch3_id_evidence.csv + batch3_summary.md [CORRECTED] |
| E8 | batch4_summary.md: TQQ pub count 13 (6+6+1) | CSV thực tế: 9+7+1 = 17 unique EIDs cho TQQ. Lỗi từ scan Batch 4 trước. | batch4_publication_evidence.csv re-exported; batch4_summary.md [CORRECTED] |
| E9 | batch4_summary.md: NHH×LHL = 8 EIDs | Full CSV recount: 9 EIDs. | batch4_summary.md cross-GV table [CORRECTED] |
| E10 | batch5: 4 DOIs gán nhầm cho sai Scopus ID (vd: DOI `10.1007/978-3-031-50818-9_35` → ID 26637116200 thay vì 58805722900) | Đọc cột `Author(s) ID` trong chính CSV row chứa DOI để xác định đúng ID. 4 DOI→ID đã sửa ngày 2026-10-28. | batch5_id_evidence.csv, batch5_browser_evidence.json, batch5_summary.md [CORRECTED]; xem FINDING-021 |
| E11 | Q11 (03_THESIS_DEFENSE_NOTES.md v1.3–v1.5): "2+4+5=11, union=9 EIDs" | Union đúng là 7 distinct EIDs (2 EIDs bị đếm 3 lần). FINDING-019 v1.4–v1.5 chỉ liệt kê 2 triple-GV EIDs thay vì 3. | 03_THESIS_DEFENSE_NOTES.md [CORRECTED v1.6]; FINDING-019 [CORRECTED]; xem FINDING-021 |

---

## HISTORICAL FINDINGS

*(Không có findings bị supersede trong phiên bản này.)*

---

## CHANGELOG

| Ngày | Version | Thay đổi |
|------|---------|---------|
| 2026-10-27 | v1.0 | Tạo file lần đầu. 13 findings từ Gate D.1 + D.2 Batch 1+2. 5 errata từ báo cáo độc lập. |
| 2026-10-27 | v1.1 | Batch 3: thêm FINDING-014, FINDING-015, FINDING-016. Cập nhật THỐNG KÊ. Không xóa finding cũ. |
| 2026-10-27 | v1.2 | FINDING-016 CORRECTED: false positive do code cắt `.slice(0,4)` tác giả. Van-Tao Nguyen là tác giả thứ 5, xác nhận bởi CrossRef full list + DBLP + NYCU + ICTU Repo. Thêm Errata E6. |
| 2026-10-27 | v1.3 | Batch 4: thêm FINDING-017 (NHH name variants/typo), FINDING-018 (cross-GV scope clarification), FINDING-019 (9-GV cumulative stats). Thêm Errata E7 (E5 label LHL), E8 (TQQ pub count), E9 (NHH×LHL EID count). Sửa batch3/4 artifacts. Cập nhật THỐNG KÊ. |
| 2026-10-27 | v1.4 | Batch 5: thêm FINDING-020 (DTB 7 name variants, nhiều nhất trong audit). Coverage 46/83 IDs (14/34 GVs). |
| 2026-10-28 | v1.5 | Errata: coverage sửa 41/83 unique, 13/34 GVs; DOI→ID mapping sửa 4 entries batch5; header update. |
| 2026-10-28 | v1.6 | FINDING-019 [CORRECTED]: thêm triple-GV EID thứ 3 (2-s2.0-85208627580, LHL×NHH×TQQ). FINDING-020 [CORRECTED]: phân tách rõ 5 Scopus profile variants vs 2 CrossRef publisher forms. FINDING-021 mới: bài học provenance DOI→ID. Errata E10, E11. |
