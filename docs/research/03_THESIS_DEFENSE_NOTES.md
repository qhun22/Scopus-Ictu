# 03 — Ghi chú bảo vệ đồ án

**Tạo lần đầu:** 2026-10-27  
**Cập nhật gần nhất:** 2026-10-28 (v1.6 — Q11: 9→7 distinct EIDs, thêm triple EID thứ 3 LHL×NHH×TQQ, sửa tên Quách Xuân Trưởng)  
**Mục đích:** Chuẩn bị câu hỏi hội đồng, câu trả lời ngắn + chuyên sâu, và bằng chứng thực tế.

> **Cách dùng:** Mỗi câu hỏi có (a) câu trả lời 30–60 giây, (b) giải thích sâu nếu hỏi tiếp, (c) ví dụ từ dữ liệu thực tế ICTU. Phần "Không được khẳng định" nhắc những điều chưa có bằng chứng.

---

## Q1 — Tại sao cần xử lý nhiều Scopus IDs cho một giảng viên?

**Câu trả lời ngắn (30 giây):**
Scopus tự động tạo Author Profile từ metadata bài báo. Khi tên tiếng Việt được viết khác nhau — có dấu, không dấu, thứ tự khác — Scopus có thể tạo nhiều profiles riêng biệt cho cùng một người. Hệ thống phải hỗ trợ quan hệ 1-nhiều giữa giảng viên và Scopus IDs để thống kê chính xác.

**Giải thích chuyên sâu:**
- Ví dụ thực tế: TS. Nguyễn Hải Minh có 4 IDs: `57192956797` (tên: "Nguyen, Hai Minh"), `7003299472` ("Minh, Nguyen Hai"), `58771697600` ("Minh, Nguyen Hai"), `59768336500` ("Hai Minh, Nguyen"). Cùng một người, bốn cách viết tên khác nhau → bốn profiles trên Scopus.
- ThS. Lương Thị Minh Huế: 5 IDs — trong đó 3 IDs hiển thị "page not found" trên Scopus Preview (2026-10-27), có thể đã được gộp.
- Nếu không gộp IDs, thống kê công bố của giảng viên sẽ thiếu; nếu gộp sai, có thể ghép nhầm công bố của người khác.

**Bằng chứng:**
- 34/410 giảng viên ICTU có nhiều Scopus IDs — dữ liệu từ `repository.ictu.edu.vn/huong-dan-gop-tai-khoan-scopus/`, xác minh 2026-10-27.
- (Xem FINDING-002 trong 02_ICTU_DATA_FINDINGS.md)

**Không được khẳng định:** Chưa xác minh danh tính (ownership) của toàn bộ 83 IDs. Đã khảo sát 41/83 IDs unique đã truy cập, 13/34 GVs (hết Batch 5 — 5 IDs DTB đã counted từ Gate D.1).

**Slide:** Nên có. Dùng bảng thống kê và ví dụ NHM/LMH.

---

## Q2 — Làm sao xác định một công bố thuộc đúng giảng viên?

**Câu trả lời ngắn (30 giây):**
Hệ thống dùng pipeline gồm candidate generation và human review. Candidate generation chỉ đọc — không ghi DB, không thay đổi trạng thái. Chỉ reviewer mới có thể ACCEPT hoặc REJECT sau khi xem bằng chứng.

**Giải thích chuyên sâu:**
Thang bằng chứng tăng dần:
1. SOURCE_LISTED: ICTU-WEB liệt kê ID này cho GV
2. CSV_PRESENT: ID xuất hiện trong bản ghi Scopus
3. BROWSER_OPENED: Profile Scopus Preview đã mở
4. PROFILE_ACCESSIBLE: Tên + affiliation khớp ICTU trên Scopus
5. PUBLICATION_CORROBORATED: Email tổ chức hoặc ORCID từ chính nhà xuất bản

**Ví dụ E5 từ dữ liệu thực:**
DOI `10.1371/journal.pone.0321009` — PLOS ONE trực tiếp ghi nhận `nhminh@ictu.edu.vn` là email tác giả liên hệ. Đây là bằng chứng mạnh nhất, không cần suy luận tên hay affiliation.

**Bằng chứng:** FINDING-010 trong 02_ICTU_DATA_FINDINGS.md.

**Không được khẳng định:** Không phải tất cả IDs đều có bằng chứng E5. Phần lớn dừng ở E4 (profile accessible). Chưa ACCEPT/REJECT bất kỳ liên kết nào trong audit.

**Slide:** Có thể dùng thang bằng chứng dạng sơ đồ. Bổ sung ví dụ email nhà xuất bản.

---

## Q3 — ORCID có tuyệt đối đáng tin không?

**Câu trả lời ngắn (30 giây):**
Không. ORCID trên orcid.org do tác giả tự đăng ký và có độ tin cậy cao hơn. Nhưng ORCID trong ICTU Repository là do admin nhập — có thể sai. Hệ thống phát hiện ít nhất 10 cặp ORCID trùng trong dữ liệu ICTU.

**Giải thích chuyên sâu:**
Phát hiện quan trọng nhất: ORCID `0009-0001-3939-8656` được gán cho cả ThS. Bùi Thị Quyên VÀ ThS. Vi Thị Bích Ngọc trong ICTU Repository. Kiểm tra orcid.org xác nhận ORCID này thuộc về Vi Thị Bích Ngọc (tự đăng ký, có tổ chức ICTU).

**Ý nghĩa thiết kế:**
Không dùng ORCID từ ICTU Repository làm bằng chứng danh tính duy nhất. Phải xác minh ORCID ngược về orcid.org trước khi dùng.

**Bằng chứng:** FINDING-005 trong 02_ICTU_DATA_FINDINGS.md.

**Không được khẳng định:** 9 cặp ORCID trùng còn lại chưa mở browser để xác minh ai là chủ sở hữu thực sự. Coverage audit hiện tại 32/83 IDs (10/34 GVs).

**Slide:** Nên có. Ví dụ trực quan về ORCID collision.

---

## Q4 — Vì sao không tự động ACCEPT mọi trường hợp matching?

**Câu trả lời ngắn (30 giây):**
Dữ liệu thực tế ICTU chứa quá nhiều ngoại lệ: ORCID lỗi, nhiều IDs cho một người, tên biến thể, bài đồng tác giả. Một hệ thống auto-match sẽ tạo lỗi khó sửa. Thiết kế "human-in-the-loop" là lựa chọn có chủ đích, không phải thiếu tính năng.

**Giải thích chuyên sâu:**
Quy tắc D-2 trong `review_reason_policy.py`: ACCEPT bắt buộc có lý do khi:
- Bằng chứng chỉ là tên giống nhau (name-only)
- Scopus Author bị nhiều người tranh chấp
- Có nhiều candidates cho một giảng viên

**Ví dụ làm sai nếu auto-ACCEPT:**
- Nếu auto-ACCEPT dựa trên tên "Dang Quang A" → có thể gán nhầm 55331947800 (cũ, từ 2012) vào hồ sơ hiện tại
- Nếu auto-ACCEPT dựa trên affiliation "ICTU" → tất cả IDs có ICTU trong Scopus đều sẽ được chấp nhận, bao gồm những IDs thực ra đã gộp hoặc thuộc người khác

**Slide:** Nên có ngắn gọn. Không cần liệt kê kỹ thuật — nêu nguyên tắc và ví dụ.

---

## Q5 — Hệ thống chống đếm trùng công bố như thế nào?

**Câu trả lời ngắn (30 giây):**
Hệ thống dùng EID (Elsevier ID) làm canonical identifier để dedup. Có ba phạm vi dedup khác nhau: trong một giảng viên (intra-lecturer), toàn trường (school-wide), và quan hệ đồng tác giả.

**Giải thích chuyên sâu:**
Ba phạm vi không được nhầm lẫn:
1. **Intra-lecturer dedup:** Một bài xuất hiện qua nhiều Scopus IDs của cùng GV chỉ được đếm một lần cho GV đó.
2. **School-wide dedup:** Một bài có N giảng viên ICTU đồng tác giả chỉ được đếm một lần trong tổng ICTU.
3. **Co-authorship links:** Quan hệ GV–publication vẫn giữ đầy đủ để biết ai tham gia bài nào.

**Ví dụ thực tế:**
Trong Batch 1+2: 5 EIDs xuất hiện ở 2 GVs khác nhau (đồng tác giả). Nếu cộng 98 lượt → thực ra chỉ có 93 EID duy nhất. Không được lấy 98 làm "số bài báo ICTU".

**Không được khẳng định:** Chưa tính school-wide dedup cho toàn bộ 410 GVs.

**Slide:** Có thể dùng sơ đồ Venn 3 tập. Ví dụ 5 EIDs đồng tác giả.

---

## Q6 — Dữ liệu nguồn ICTU có những giới hạn nào?

**Câu trả lời ngắn (30 giây):**
Ba giới hạn chính: (1) ORCID có lỗi — ít nhất 10 cặp trùng. (2) ICTU Repository không lưu Scopus Author ID — phải tìm từ nguồn khác. (3) CSV Scopus chỉ là personal export của một người — không đại diện cho toàn bộ ICTU.

**Giải thích chuyên sâu:**

| Giới hạn | Ảnh hưởng | Cách xử lý trong thiết kế |
|---------|----------|--------------------------|
| ORCID lỗi trong ICTU Repository | Không thể dùng làm bằng chứng danh tính duy nhất | Xác minh ngược về orcid.org |
| Scopus ID không có trong crawler schema | Phải lấy từ ICTU-WEB riêng | Sử dụng trang /huong-dan-gop-tai-khoan-scopus/ |
| CSV coverage không đủ | DQA: 7/53 pubs; các GVs không phải đồng tác giả QH = 0 pubs | Cần import toàn bộ Scopus API, không chỉ personal export |
| Scopus Preview gián đoạn | "Unable to display" trong một số thời điểm | Fallback về page title; ghi PARTIAL |
| Crawler không có Scopus ID field | lecturers.json thiếu scopus_author_ids | Phải cross-reference từ nguồn khác |

**Slide:** Bảng giới hạn này phù hợp cho phần "Giới hạn và hướng phát triển".

---

## Q7 — Đóng góp thực tế của đồ án là gì?

**Câu trả lời ngắn (30 giây):**
Đồ án xây dựng nền tảng để ICTU có thể quản lý và xác minh hồ sơ tác giả Scopus một cách có hệ thống — với pipeline matching, tầng human review, và audit trail. Không chỉ là tính năng kỹ thuật mà là quy trình nghiệp vụ phù hợp với đặc thù dữ liệu ICTU.

**Giải thích chuyên sâu:**

| Vấn đề thực tế ICTU | Giải pháp trong đồ án |
|---------------------|----------------------|
| 34 GVs có nhiều IDs không ai quản lý | Giao diện multi-ID, candidate review |
| ORCID lỗi không ai biết | Audit pipeline phát hiện 10 cặp collision |
| Đếm trùng công bố khi tổng hợp | Dedup logic với EID canonical |
| Không biết bài báo nào đúng của ai | Evidence-based matching với thang 5 cấp |
| Không có audit trail | Mọi decision đều có reason + timestamp |

**Không được khẳng định:**
- Chưa đưa vào production ICTU
- 26/83 IDs đã khảo sát, còn 57 IDs chưa xác minh
- Chưa ACCEPT/REJECT bất kỳ liên kết nào trong audit

**Phần thuyết phục nhất cho hội đồng:** Bằng chứng từ thực tế (ORCID collision thực, đồng tác giả thực, Expression of Concern thực) cho thấy bài toán phức tạp hơn một CRUD đơn giản.

**Slide:** Nên có. Bảng "Vấn đề → Giải pháp" ngắn gọn.

---

## Q8 — Scopus Preview "not found" nghĩa là ID đó không tồn tại?

**Câu trả lời ngắn (30 giây):**
Không. "Page not found" trong Scopus Preview có thể có nhiều nguyên nhân: ID đã merge vào ID khác, ID đã xóa, hoặc lỗi truy cập tạm thời. Không được kết luận "đã merge" hay "không tồn tại" chỉ từ thông báo này.

**Bằng chứng:** FINDING-009 — 3 IDs của LMH trả "not found". Nguyên nhân chưa xác minh.

**Slide:** Không cần slide riêng. Dùng khi phản biện hỏi về LMH.

---

## Q9 — Expression of Concern có nghĩa là gì trong ngữ cảnh này?


**Câu trả lời ngắn (30 giây):**
Expression of Concern là cảnh báo từ nhà xuất bản rằng bài báo đang được điều tra về một vấn đề cụ thể. Nó không đồng nghĩa bài bị rút hay tác giả bị gán sai danh tính.

**Giải thích chuyên sâu:**
DOI `10.1371/journal.pone.0321009` của NHM có Expression of Concern từ PLOS (26/02/2026) liên quan đến trích dẫn và chính sách dữ liệu. Đây là vấn đề học thuật của bài báo — hoàn toàn tách biệt với câu hỏi "ai là tác giả".

**Ý nghĩa thiết kế:** Hệ thống nên lưu trữ publication status (normal / expression-of-concern / retracted) như một field riêng, không trộn với identity verification status.

**FINDING-011 trong 02_ICTU_DATA_FINDINGS.md.**

---

## Q10 — Rủi ro khi đọc metadata thiếu tác giả khi cross-check DOI *(từ Batch 3)*

> **[CORRECTED — 2026-10-27]** Q10 ban đầu (v1.1) dùng sai ví dụ. DOI `10.1109/MNET.010.2100509` KHÔNG phải anomaly — Nguyễn Văn Tảo là tác giả thứ 5 trong danh sách 5 người. Lỗi thuộc về phương pháp audit (code đọc thiếu tác giả), không phải lỗi dữ liệu. Q10 được viết lại dưới đây.

**Câu trả lời ngắn (30 giây):**
Khi cross-check DOI với CrossRef, hệ thống phải đọc toàn bộ danh sách tác giả, không chỉ tác giả đầu tiên. Bài báo hợp tác quốc tế nhiều tác giả thường có tác giả ICTU ở vị trí không đứng đầu. Đây là bài học thực tế từ quá trình audit: chính sai lầm này được phát hiện và sửa qua independent review.

**Giải thích chuyên sâu:**
DOI `10.1109/MNET.010.2100509` (IEEE Network, 2023): bài có 5 tác giả — 4 từ Taiwan (CCU/NYCU) và 1 là Van-Tao Nguyen từ ICTU (tác giả thứ 5). Code audit ban đầu chỉ đọc `.slice(0,4)` → bỏ sót tác giả thứ 5 → kết luận sai "CrossRef không có Van-Tao Nguyen".

**Bài học cho thiết kế hệ thống:**
- Khi gọi CrossRef API, không giới hạn số tác giả trả về
- Bài đồng tác giả quốc tế: tác giả ICTU có thể ở vị trí cuối
- Luôn cần independent review để phát hiện lỗi phương pháp

**Bằng chứng:** FINDING-016 [CORRECTED] trong 02_ICTU_DATA_FINDINGS.md. CrossRef full list + DBLP + NYCU scholar + ICTU Repository.

**Không được khẳng định:** Bài báo cụ thể này đã xác nhận Van-Tao Nguyen là đồng tác giả. Điều này chưa đủ để xác nhận toàn bộ ID 56967513900 thuộc đúng TS. Nguyễn Văn Tảo ICTU.

**Slide:** Không cần slide riêng. Dùng khi phản biện hỏi về quy trình kiểm chứng và vai trò của independent review.

---

## Q11 — Tại sao cùng một bài báo có thể xuất hiện ở nhiều cặp giảng viên khi phân tích cross-GV? *(từ Batch 4)*

**Câu trả lời ngắn (30 giây):**
Khi nhiều hơn 2 giảng viên ICTU cùng là đồng tác giả trên một bài báo, bài đó xuất hiện trong mọi cặp pairwise giữa các giảng viên đó. Đây là quan hệ đồng tác giả hợp lệ, không phải lỗi trùng lặp. Phân tích cross-GV cần dùng tập EIDs không trùng (distinct cross-GV EIDs), không cộng theo cặp.

**Giải thích chuyên sâu:**
- Trong Batch 4, 2 EIDs (`2-s2.0-105000957095`, `2-s2.0-105041762468`) xuất hiện trong cả 3 cặp: NHH×QXT, NHH×TQQ, QXT×TQQ — đây là bài có 3 GVs đồng tác giả: TS. Ngô Hữu Huy, TS. Quách Xuân Trưởng, TS. Trần Quang Quý.
- Có thêm triple-GV EID thứ 3: `2-s2.0-85208627580` xuất hiện ở LHL×NHH và LHL×TQQ và NHH×TQQ — bài có 3 GVs: TS. Lê Hải Lâm, TS. Ngô Hữu Huy, TS. Trần Quang Quý.
- **[CORRECTED 2026-10-28]** Nếu cộng theo cặp NHH×QXT + NHH×TQQ + QXT×TQQ: 2+4+5 = 11 pairwise occurrences, nhưng **union 3 cặp chỉ là 7 EIDs duy nhất** — vì 2 EIDs (`2-s2.0-105000957095`, `2-s2.0-105041762468`) xuất hiện trong cả 3 cặp, bị đếm 3 lần thay vì 1 lần. Công thức: union − 2×(bị đếm dư) = 11 − 2×2 = 7. *(Không phải 9 như phiên bản v1.3–v1.5.)*
- Công thức đúng: dùng union của tất cả EIDs có ≥2 GVs, không cộng pairwise.

**Bằng chứng:**
- Python analysis `data/scopus/Truong_Quang_Huy_Scopus_Sep2026.csv`, xác nhận lại 2026-10-28.
- NHH×QXT: 2 | NHH×TQQ: 4 | QXT×TQQ: 5 | union = 7 distinct (Python set union verified).
- 9 GVs Batch 1–4: 25 cross-GV EIDs không trùng (total distinct), không phải sum of pairs.

**Không được khẳng định:** Chưa xác nhận 3-way authorship từ publisher — chỉ từ CSV Scopus. Tên "TS. Quách Xuân Trưởng" dùng theo ICTU-WEB; tên tắt trong tài liệu là QXT.

**Slide:** Không cần. Dùng khi bị hỏi về phương pháp đếm/dedup.

---

## LƯU Ý CHO PHẦN SLIDE VÀ TRÌNH BÀY

| Phần | Nên đưa vào slide | Chỉ để trả lời phản biện |
|------|-------------------|--------------------------|
| ORCID collision 10 cặp | Có — ví dụ Bùi Thị Quyên/Vi Thị Bích Ngọc | — |
| Thang bằng chứng 5 cấp | Có — sơ đồ | — |
| NHM 4 IDs + email nhà xuất bản | Có — ví dụ E5 | — |
| 5 EIDs đồng tác giả cross-GV | Có — dedup minh họa | — |
| Expression of Concern | Không (quá chi tiết cho slide) | Có — nếu bị hỏi |
| DQA 7/53 pubs | Không (dễ gây nhầm) | Có — giải thích coverage limit |
| "Page not found" LMH | Không | Có — giải thích NOT_FOUND |
| Coverage 41/83 IDs unique (Batch 5) | Có — bảng coverage, ghi rõ là unique visited coverage | — |

---

## CHANGELOG

| Ngày | Version | Thay đổi |
|------|---------|---------|
| 2026-10-27 | v1.0 | Tạo file lần đầu. 9 câu hỏi từ Gate D.1–D.2. Tích hợp errata và findings mới. |
| 2026-10-27 | v1.1 | Batch 3: thêm Q10 (DOI anomaly). Cập nhật coverage 32/83 IDs (10/34 GVs). |
| 2026-10-27 | v1.2 | Q10 CORRECTED: ví dụ DOI_ANOMALY sai → viết lại thành bài học về đọc thiếu tác giả khi cross-check. |
| 2026-10-27 | v1.3 | Batch 4: thêm Q11 (3-way co-authorship và cross-GV distinct count). Cập nhật coverage 38/83 IDs (12/34 GVs). |
| 2026-10-27 | v1.4 | Batch 5: coverage 46/83 IDs (14/34 GVs). |
| 2026-10-28 | v1.5 | Errata: coverage sửa 41/83 unique, 13/34 GVs (DTB×5 đã counted từ Gate D.1). |
| 2026-10-28 | v1.6 | Q11: 9→7 distinct EIDs; thêm triple EID thứ 3 (2-s2.0-85208627580, LHL×NHH×TQQ); sửa tên "Quách Xuân Trưởng" (không phải "Quản Xuân Trường"). |
