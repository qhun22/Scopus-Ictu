# 01 — Kiến thức nghiên cứu: Bài toán Scopus–ICTU

**Tạo lần đầu:** 2026-10-27  
**Cập nhật gần nhất:** 2026-10-29 (v1.9 — errata E17: phân tầng bằng chứng ORCID)  
**Tác giả:** Claude Sonnet 4.6 (tổng hợp từ tài liệu QA và thiết kế)  
**Phạm vi:** Kiến thức nền, định nghĩa, mô hình nghiệp vụ, nguyên tắc thiết kế hệ thống

> **Nguyên tắc đọc:** File này là kiến thức đã kiểm chứng hoặc được đánh nhãn rõ ràng (FACT / SOURCE CLAIM / INFERENCE / HYPOTHESIS / UNVERIFIED). Không đọc con số là FACT nếu chỉ có nhãn INFERENCE.

---

## PHẦN 1 — BỐI CẢNH VÀ BÀI TOÁN

### 1.1 Bối cảnh tổ chức

**[FACT]** ICTU (Trường Đại học Công nghệ Thông tin và Truyền thông — ĐH Thái Nguyên) quản lý hồ sơ giảng viên và công bố khoa học qua hai hệ thống:
- **ICTU Repository (DSpace):** `repository.ictu.edu.vn` — hồ sơ cá nhân, danh sách công bố, ORCID, Google Scholar.
- **ICTU Website chính:** `ictu.edu.vn` — thông tin chung, trang tìm kiếm tác giả Scopus.

**[FACT]** Scopus (Elsevier) là cơ sở dữ liệu thư mục khoa học lớn. Mỗi tác giả có thể có một hoặc nhiều **Scopus Author ID** (chuỗi số 10–11 chữ số).

**[SOURCE CLAIM — từ thiết kế hệ thống]** Mục tiêu đồ án: xây dựng ứng dụng web để quản lý và chuẩn hoá hồ sơ tác giả + công bố khoa học từ Scopus, phục vụ ICTU. Thách thức cốt lõi: đối chiếu Scopus Author Identity với hồ sơ giảng viên ICTU bằng bằng chứng — không tự xác nhận liên kết khi chứng cứ chưa đủ.

---

### 1.2 Vì sao một giảng viên có nhiều Scopus IDs?

**[FACT]** Scopus tự động tạo Author Profile dựa trên metadata bài báo. Khi tên tác giả được viết khác nhau (dấu tiếng Việt, cách viết không dấu, thứ tự họ/tên), hoặc tác giả chuyển tổ chức, Scopus có thể tạo nhiều profile riêng biệt cho cùng một người.

**[FACT — từ ICTU-WEB]** ICTU-WEB công bố danh sách 34 giảng viên với nhiều Scopus IDs cần rà soát/gộp. Nguồn: `repository.ictu.edu.vn/huong-dan-gop-tai-khoan-scopus/`. Xác minh DOM thực tế ngày 2026-10-27.

**[INFERENCE]** Tên tiếng Việt không dấu tạo nhiều biến thể: "Nguyen Hai Minh", "Minh Nguyen Hai", "Hai Minh Nguyen" — tất cả có thể dẫn đến profile riêng. ID 7003299472 cho TS. Nguyễn Hải Minh là ví dụ thực tế (xác nhận 2026-10-27).

**Hàm ý thiết kế:** Hệ thống phải hỗ trợ một giảng viên có nhiều Scopus IDs (quan hệ 1:n), không giả định 1:1.

---

### 1.3 Vì sao một Scopus ID có thể bị tranh chấp?

**[FACT — từ thiết kế]** Nếu hai người có tên giống nhau, cùng tổ chức hoặc cùng lĩnh vực, Scopus có thể gộp nhầm công bố của hai người vào một profile, hoặc ngược lại có thể chia một người thành nhiều profiles.

**[INFERENCE]** Không có bằng chứng trực tiếp về tranh chấp trong dữ liệu Batch 1–2, nhưng cơ chế này là lý do thiết kế cần tầng review thủ công.

**[FACT — Gate D.3 mission, 2026-10-29; CORRECTED cùng ngày]** Quan sát được **nghi vấn trộn hồ sơ** (HIGH-PRIORITY POTENTIAL IDENTITY CONFLICT, chưa kết luận chính thức): Scopus ID 57211884261 (ICTU-WEB liệt kê cho Nguyễn Thị Hải Anh) chứa bài Heliyon 2024 — do ORCID 0009-0005-2135-2544 của GV tự nhận — và một bài vật lý mà hồ sơ ORCID 0009-0007-0103-6055 của một nhà nghiên cứu VAST tự liệt kê (FINDING-026). *(Bản đầu ghi "quan sát được trường hợp trộn hồ sơ thực tế" — nói quá mức bằng chứng.)* Như vậy "một ID — một người" cũng không được giả định; đơn vị cần review có thể là **từng công bố trên ID**, không chỉ cả ID.

**[SOURCE CLAIM — ORCID tự khai, 2026-10-29]** Nơi công tác thay đổi theo thời gian: ORCID 0009-0005-2135-2544 ghi GV làm việc tại ICTU 2013-01→2024-02 và tại Trường Ngoại ngữ – ĐH Thái Nguyên từ 2024-03. **[INFERENCE]** Việc ICTU Repository/ICTU-WEB còn liệt kê một GV không chứng minh GV đó đang công tác tại ICTU; affiliation cần có **thời gian hiệu lực** và nguồn.

**[FACT — Batch 6, 2026-10-28]** Lần đầu quan sát được một tín hiệu mâu thuẫn cụ thể: hồ sơ 58771657000 (TS. Nguyễn Đức Bình theo ICTU-WEB) hiển thị affiliation HCM-UTE, trong khi 5/5 công bố trong CSV của ID này ghi ICTU + email `ndbinh@ictu.edu.vn`. **[HYPOTHESIS]** Có thể hồ sơ chứa công bố của người trùng tên, hoặc chỉ do 2 docs ngoài CSV. Chưa kiểm chứng (FINDING-022).

---

### 1.4 DOI, EID và khử trùng công bố

**[FACT]** DOI (Digital Object Identifier) là định danh toàn cầu duy nhất cho một bài báo. EID (Elsevier ID) là định danh nội bộ của Scopus cho mỗi bản ghi.

**[FACT — từ thực nghiệm Batch 1+2]** EID là đơn vị an toàn nhất để khử trùng trong phạm vi dữ liệu CSV Scopus. DOI có thể thiếu (xem `2-s2.0-84864863503` — không có DOI, năm 2012).

**Hai phạm vi dedup khác nhau — quan trọng cho thiết kế:**

| Phạm vi | Định nghĩa | Mục đích |
|---------|-----------|----------|
| **Intra-lecturer** | Đếm mỗi bài 1 lần cho một giảng viên, dù họ có N Scopus IDs | Thống kê công bố cá nhân chính xác |
| **Toàn trường** | Đếm mỗi bài 1 lần dù có N giảng viên ICTU đồng tác giả | Thống kê tổng sản lượng khoa học ICTU |
| **Quan hệ đồng tác giả** | Giữ toàn bộ liên kết Lecturer–Publication | Biết ai đóng góp vào bài nào |

**[FACT — từ Batch 1+2, xác nhận độc lập ngày 2026-10-27]** 5 EID xuất hiện ở hai giảng viên khác nhau trong dữ liệu Batch 1+2: đây là quan hệ đồng tác giả hợp lệ, không phải lỗi trùng lặp. (Xem FINDING-009.)

**[FACT]** Không được cộng tổng công bố cá nhân của tất cả giảng viên để ra tổng ICTU — sẽ đếm trùng mọi bài đồng tác giả.

---

### 1.5 ORCID và giới hạn độ tin cậy

**[FACT]** ORCID (Open Researcher and Contributor ID) là định danh không thể thay đổi được đăng ký bởi chính nhà nghiên cứu trên orcid.org. Thông tin trên orcid.org do tác giả tự cập nhật.

**[FACT — từ Gate D.1, xác nhận browser 2026-10-27]** ICTU Repository hiển thị sai ORCID: `0009-0001-3939-8656` được gán cho cả ThS. Bùi Thị Quyên (btquyen@ictu.edu.vn) VÀ ThS. Vi Thị Bích Ngọc (ngocvtb@ictu.edu.vn). ORCID.org xác nhận ORCID này thuộc về Vi Thị Bích Ngọc. (Xem FINDING-005.)

**[INFERENCE]** ORCID trong ICTU Repository không đáng tin tuyệt đối — có thể do nhập liệu sai. Không dùng ORCID từ ICTU Repository làm bằng chứng danh tính duy nhất.

**[FACT]** ORCID trên orcid.org do tác giả tự nhập (self-reported), nhưng có quy trình xác minh tổ chức. Đáng tin hơn ICTU Repository nhưng vẫn không thể coi là tuyệt đối.

**[FACT — Batch 6, 2026-10-28]** Có ba vị trí ORCID khác nhau, cần ghi rõ nguồn: (1) trên hồ sơ Scopus, (2) trên metadata công bố (Crossref, do nhà xuất bản ghi), (3) trên ICTU Repository. Chúng có thể không đồng bộ: hồ sơ 58771657000 không liên kết ORCID, nhưng cả 5 công bố của nó trên Crossref đều mang ORCID 0000-0002-1258-394X, chính là ORCID trên hồ sơ 57075583000 (FINDING-023).

**[INFERENCE]** ORCID cấp công bố trùng ORCID hồ sơ của một ID khác là tín hiệu mạnh rằng hai ID thuộc cùng người, nhưng vẫn chỉ là bằng chứng cho reviewer, không phải căn cứ merge tự động.

**[FACT — Gate D.3 mission, 2026-10-29]** Thứ tự tin cậy của nguồn ORCID quan sát được: (1) hồ sơ ORCID registry **liệt kê chính DOI** — mạnh nhất; (2) ORCID do nhà xuất bản ghi (Crossref); (3) ORCID trên hồ sơ Scopus; (4) ORCID do nguồn tổng hợp gán cho thực thể tác giả (OpenAlex) — **không dùng làm bằng chứng**: 6 ca sai tên/ORCID (FINDING-027). Ngược lại, hồ sơ registry **không** liệt kê một DOI chỉ là phản chứng yếu.

**[FACT — errata 2026-10-29]** Trong hồ sơ ORCID cần phân biệt **ai khai** từng work: tự khai bởi chủ hồ sơ (self-asserted) hay do tổ chức thành viên nhập (Crossref, "Scopus – Elsevier"). Ví dụ 0009-0005-2135-2544 có bài Heliyon cả hai dạng; bài IJLTER chỉ tự khai. Việc tìm ORCID ứng viên chỉ qua Crossref/OpenAlex là **không đầy đủ** — ORCID của GV Hải Anh chỉ được tìm thấy qua tra cứu ORCID công khai (E14).

---

### 1.6 Phương pháp kiểm chứng danh tính — cấp độ bằng chứng

Hệ thống sử dụng thang bằng chứng tăng dần:

| Cấp | Tên | Mô tả |
|-----|-----|-------|
| E1 | SOURCE_LISTED | ICTU-WEB liệt kê ID này cho giảng viên X |
| E2 | CSV_PRESENT | ID xuất hiện trong ≥1 bản ghi Scopus CSV |
| E3 | BROWSER_OPENED | Profile Scopus Preview đã mở thực tế |
| E4 | PROFILE_ACCESSIBLE | Profile hiển thị tên + affiliation khớp |
| E5 | PUBLICATION_CORROBORATED | ≥1 bài báo: email/ORCID/affiliation xác nhận bởi nhà xuất bản |
| — | IDENTITY_UNVERIFIED | Không đủ bằng chứng để liên kết |

**[FACT]** Cấp E5 (bằng chứng từ nhà xuất bản) mạnh hơn nhiều so với E4. Ví dụ: DOI `10.1371/journal.pone.0321009` — PLOS xác nhận `nhminh@ictu.edu.vn` là tác giả liên hệ. (Xem FINDING-010.)

**[INFERENCE]** Không có bằng chứng E5 cho phần lớn các IDs trong Gate D.2 do giới hạn thời gian. Đây là giới hạn của audit hiện tại.

**[FACT — Batch 6, 2026-10-28]** Thang trên cần thêm hai nhãn song song, không xếp theo cấp:
- **CONFLICTING_EVIDENCE** — các nguồn mâu thuẫn nhau (ví dụ affiliation hồ sơ ≠ affiliation trên công bố). Có thể tồn tại cùng lúc với E4/E5.
- Tách E5 thành **PUBLICATION_NAME_CORROBORATED** (chỉ khớp tên) và **PUBLICATION_AFFILIATION_CORROBORATED** (khớp affiliation/email do nhà xuất bản ghi); ORCID cấp công bố được ghi kèm.

Ví dụ: 58771657000 đạt đồng thời PROFILE_ACCESSIBLE, PUBLICATION_AFFILIATION_CORROBORATED và CONFLICTING_EVIDENCE, nên trạng thái danh tính vẫn là IDENTITY_UNVERIFIED.

**[FACT — Batch 7, 2026-10-29]** Email tác giả trên metadata nhà xuất bản có thể sai: Springer từng gán một email cho hai tác giả khác nhau trong cùng bài, và cùng một người có thể mang hai dạng email (`ndbinh@` / `binhnd@`). Vì vậy bằng chứng email chỉ có giá trị khi khớp cả **vị trí tác giả** và **tên**; một email đứng riêng không đủ cho PUBLICATION_AFFILIATION_CORROBORATED (FINDING-024).

**[FACT — Batch 7, 2026-10-29]** Một ID có thể đạt SOURCE_LISTED và PROFILE_ACCESSIBLE nhưng không có bất kỳ công bố nào trong dữ liệu để kiểm tra (60320483500: 0 dòng CSV, hồ sơ ghi HUST). "Được liệt kê" không phải là bằng chứng công bố (FINDING-025).

**[FACT — Gate D.3 mission, 2026-10-29]** Affiliation trên công bố thường là **danh sách**: 7/17 GV có bài ghi ICTU kèm nơi học tập/hợp tác (HUST-MICA, Budapest, Irkutsk, GUST-VAST, VNU-ITI, NPUST, ĐH Sư phạm TN). Affiliation phụ không phải mâu thuẫn; chỉ affiliation không-ICTU **không kèm** ICTU mới cần xem xét (FINDING-028). *(Phạm vi: các DOI đã chọn có metadata đọc được; phần lớn affiliation từ bản sao thứ cấp OpenAlex raw.)*

**[FACT — Gate D.4, 2026-10-29]** Bằng chứng ORCID phải gắn với **vị trí tác giả**, không chỉ với bài báo: ORCID registry của một GV liệt kê DOI chỉ chứng minh GV đó là **một** tác giả của bài (đồng tác giả cũng liệt kê). ~~Quy tắc dùng trong D.4: liên kết mạnh = ORCID nhà xuất bản tại đúng vị trí trùng ORCID hồ sơ GV, hoặc ORCID registry nhận DOI **và** tên khớp (FINDING-029).~~ **[CORRECTED E17, 2026-10-29]** Hai tín hiệu này **không tương đương**. Chỉ "ORCID nhà xuất bản tại đúng vị trí (CSV = Crossref) trùng ORCID hồ sơ GV **và** registry nhận DOI" mới xác minh vị trí tác giả (T1). "Registry nhận DOI + tên khớp" (T3, hoặc T4 nếu chỉ viết tắt) chỉ **hỗ trợ ứng viên** — một đồng tác giả cùng tên vẫn có thể là người nhận. ORCID tại vị trí mà registry không nhận (T2) phải đi kèm phản chứng. Không có quy tắc này, 5/69 ID bị gán nhầm cho đồng tác giả; bản trước còn gọi 6 ca T3/T4 là "mạnh".

**[FACT — Gate D.4, 2026-10-29]** "Không có ứng viên trong danh mục GV" (NO_CANDIDATE) khác "không thuộc ICTU": 39/69 ID chưa rõ chủ không khớp 410 hồ sơ GV, nhưng một số có affiliation ICTU/tên cũ của ICTU và gom được theo người (FINDING-030). **[METHOD]** Sự nhất quán chủ đề giữa các bài của một ID là tín hiệu phản chứng hữu ích (ví dụ cụm "Nguyễn Thị Dung" đại số giao hoán vs một bài lập trình di truyền), nhưng chỉ là chỉ báo, không phải bằng chứng danh tính.

**[FACT — Gate D.3 mission, 2026-10-29]** Cần phân biệt bốn trạng thái kết quả kiểm chứng, không gộp: CORROBORATED (nguồn đồng ý) · CONFLICT (nguồn không đồng ý) · NOT_VERIFIABLE (nguồn thiếu dữ liệu: DOI 404, Crossref không có tác giả) · UNRESOLVED (không có dữ liệu để đánh giá: ID 0 dòng CSV + hồ sơ không xem được).

---

### 1.7 Vai trò của reviewer và audit

**[FACT — từ thiết kế CLAUDE.md]** Hệ thống có ba vai trò: ADMIN, REVIEWER, LECTURER. LECTURER chỉ đọc. REVIEWER phê duyệt các liên kết candidate. ADMIN điều phối toàn bộ pipeline.

**[FACT — từ thiết kế review_reason_policy.py]** Quy tắc D-2: quyết định ACCEPT bắt buộc có lý do khi bằng chứng chỉ là tên, hoặc Scopus Author bị nhiều người tranh chấp, hoặc có nhiều candidates cho một giảng viên.

**[INFERENCE]** Thiết kế "không tự động ACCEPT" không phải là thiếu tính năng — đây là quyết định có chủ đích dựa trên bài học từ dữ liệu ICTU (nhiều IDs, tên biến thể, ORCID lỗi).

---

### 1.8 Lý do chọn quy tắc nghiệp vụ và giới hạn hệ thống

**[FACT — từ thiết kế]** Pipeline matching đọc-only ở giai đoạn candidate generation: không ghi DB, không thay đổi trạng thái. Ghi DB chỉ xảy ra khi reviewer ra quyết định.

**[INFERENCE]** Lý do: dữ liệu ICTU chứa nhiều ngoại lệ (ORCID lỗi, multi-ID, tên biến thể, bài đồng tác giả). Một hệ thống auto-match sẽ tạo ra lỗi khó sửa. Human-in-the-loop là lựa chọn đúng cho bài toán này.

**[HYPOTHESIS]** Khi dữ liệu được làm sạch đủ mức (ORCID đã sửa, multi-IDs đã gộp), có thể bổ sung rule auto-ACCEPT cho các trường hợp bằng chứng rất cao. Nhưng quyết định này phụ thuộc vào ngưỡng risk tolerance của ICTU.

---

## PHẦN 2 — GIỚI HẠN HỆ THỐNG ĐANG BIẾT

| Giới hạn | Mô tả | Tác động |
|---------|-------|---------|
| CSV coverage | CSV là personal export của QH — không chứa toàn bộ pubs ICTU | DQA: 7 trong CSV vs 53 trên Scopus |
| Scopus Preview server error | Batch 3 (2026-10-27): tất cả 6 profiles trả "Unable to display"; page title vẫn load → dùng làm PARTIAL evidence. Batch 6 (2026-10-28): cả 4 profiles tải được body → lỗi phụ thuộc thời điểm, không phải thuộc tính của ID | Fallback về page title; ghi BROWSER_OPENED thay vì PROFILE_ACCESSIBLE; có thể mở lại sau |
| Scopus Preview không liệt kê documents | Preview chỉ hiện số lượng docs, không cho xem danh sách ("Limited access") | Không xác định được docs của hồ sơ nằm ngoài CSV local (ví dụ 2/7 docs của 58771657000) |
| Ba nguồn đếm công bố | ICTU-WEB, CSV và Scopus Preview cho số khác nhau theo cả hai chiều (Bình 24/24/34, Khánh 17/20/21; Batch 7: Sơn 11/21/21, Việt 10/21/22) | Luôn ghi nguồn và thời điểm của số đếm |
| Trang nhà xuất bản chặn truy cập bằng script | Springer trả "Client Challenge" cho request tự động; chỉ đọc được trong browser | Response Crossref lưu nguyên bản bằng script; meta Springer chép từ browser và kiểm bằng SHA-256 lần chụp lại (Batch 7). Không vượt cơ chế chống bot. |
| Cụm đồng tác giả dày đặc | Sơn–Việt–Huệ chung 15–17 EID từng cặp; 1 EID có 5 GV (Batch 7) | Tín hiệu đồng tác giả kém phân biệt trong cụm; không dùng làm bằng chứng danh tính |
| Scopus Preview lỗi toàn phiên | Gate D.3 mission: từ 00:34Z mọi hồ sơ (kể cả ID đối chứng đã hiển thị lúc 00:18Z) trả "Unable to display"; chỉ có title | PROFILE_ACCESSIBLE = 0/34 cho nhiệm vụ; ghi trạng thái có timestamp, thử lại sau; không gọi API nội bộ |
| Nguồn tổng hợp (OpenAlex) | Thực thể tác giả có thể sai tên/ORCID (6 ca) | Chỉ dùng chuỗi raw; ORCID thực thể không phải bằng chứng |
| Trang nhà xuất bản sau Cloudflare | Cell/Heliyon trả trang "Just a moment…" | Dùng Europe PMC/OpenAlex raw; ghi nhãn SECONDARY_AGGREGATOR; không vượt chống bot |
| Chọn mẫu DOI | Nhiệm vụ lớn: mọi DOI nếu ID có ≤3 bài; nếu nhiều hơn: sớm nhất / trung vị / muộn nhất | Bằng chứng công bố không bao phủ mọi DOI của ID lớn; bổ sung bằng kiểm tra ORCID registry trên **toàn bộ** DOI |
| ICTU Repository ORCID lỗi | Ít nhất 10 cặp ORCID trùng (1 HIGH risk, 9 MEDIUM) | Không dùng ORCID ICTU làm evidence duy nhất |
| Scopus ID "not found" ambiguity | Có thể đã merged, hoặc xóa, hoặc lỗi truy cập | Không kết luận MERGED từ "not found" |
| Không có DOM snapshot portable | browser_evidence.json là bản ghi quan sát, không có HTML gốc | Khó tái kiểm tra độc lập |
| CrossRef author list truncation | **[BÀI HỌC TỪ FINDING-016]** Khi query CrossRef API, phải đọc toàn bộ `author` array — không slice/limit. Bài đồng tác giả nhiều người (≥5) thường có tác giả ICTU không đứng đầu. | Luôn dùng `w.author?.map(...)` không dùng `.slice(0,N)` |
| Cross-GV scope: full CSV vs batch export | **[BÀI HỌC TỪ FINDING-018]** Batch export CSV chứa rows theo lookup target, không chứa toàn bộ đồng tác giả. Join hai batch exports riêng lẻ có thể báo 0 overlap dù thực tế có đồng tác giả. Dùng full CSV gốc cho cross-GV analysis. | Không kết luận "không đồng tác giả" từ batch export CSV riêng lẻ |
| Pairwise cross-GV counting | **[BÀI HỌC TỪ FINDING-019]** Bài có ≥3 GVs đồng tác giả xuất hiện trong nhiều cặp pairwise. Cộng theo cặp sẽ đếm trùng. Dùng distinct EID union để tính cross-GV không trùng. | Số cross-GV EIDs = `len({e for e,gvs in eid_gvs.items() if len(gvs)>=2})` |

---

## CHANGELOG

| Ngày | Phiên bản | Thay đổi |
|------|----------|---------|
| 2026-10-27 | v1.0 | Tạo file lần đầu từ Gate D.1–D.2, Batch 1+2 |
| 2026-10-27 | v1.1 | Batch 3: cập nhật Scopus Preview server error note; DOI cross-check anomaly (FINDING-016) |
| 2026-10-27 | v1.2 | FINDING-016 CORRECTED: bổ sung quy tắc CrossRef — phải đọc toàn bộ author list, không giới hạn số tác giả |
| 2026-10-27 | v1.3 | Batch 4: bổ sung giới hạn "cross-GV scope" (FINDING-018) và "pairwise cross-GV counting" (FINDING-019) |
| 2026-10-28 | v1.4 | Gate D.3 Batch 6: 1.3 thêm tín hiệu mâu thuẫn đầu tiên (FINDING-022); 1.5 thêm ba vị trí ORCID và ORCID cấp công bố (FINDING-023); 1.6 thêm CONFLICTING_EVIDENCE và tách E5 name/affiliation; Phần 2 thêm 2 giới hạn và cập nhật Scopus Preview error. Không xóa nội dung cũ. |
| 2026-10-29 | v1.5 | Gate D.3 Batch 7: 1.6 thêm giới hạn bằng chứng email (FINDING-024) và "được liệt kê ≠ có bằng chứng công bố" (FINDING-025); Phần 2 bổ sung số đếm Batch 7, thêm giới hạn chặn bot của nhà xuất bản và cụm đồng tác giả. Không xóa nội dung cũ. |
| 2026-10-29 | v1.6 | Gate D.3 mission A/B/C: 1.3 thêm ca trộn hồ sơ (FINDING-026); 1.5 thêm thứ tự tin cậy nguồn ORCID (FINDING-027); 1.6 thêm affiliation dạng danh sách (FINDING-028) và bốn trạng thái kiểm chứng; Phần 2 thêm 4 giới hạn (Scopus Preview lỗi toàn phiên, OpenAlex, Cloudflare, chọn mẫu DOI). Không xóa nội dung cũ. |
| 2026-10-29 | v1.7 | Scientific errata: 1.3 hạ "trộn hồ sơ thực tế" xuống nghi vấn HIGH-PRIORITY, thêm ORCID 0009-0005-2135-2544 và affiliation có thời gian hiệu lực; 1.5 thêm phân biệt self-asserted vs member-imported và giới hạn tìm ORCID ứng viên; 1.6 giới hạn phạm vi dual affiliation. Giữ văn bản cũ trong ghi chú. |
| 2026-10-29 | v1.8 | Gate D.4: 1.6 thêm quy tắc ORCID gắn với vị trí tác giả (FINDING-029), NO_CANDIDATE ≠ không thuộc ICTU (FINDING-030), tín hiệu nhất quán chủ đề. Không xóa nội dung cũ. |
| 2026-10-29 | v1.9 | Errata E17: tách "ORCID nhà xuất bản tại vị trí + registry" (T1, xác minh vị trí) khỏi "registry + tên khớp" (T3/T4, chỉ hỗ trợ); câu cũ giữ dạng gạch ngang. |

---

*Nguồn tham chiếu chính: `docs/qa/gate_d1r/`, `docs/qa/gate_d2/`, `CLAUDE.md`, `backend/app/services/matching/`, `backend/app/services/review_service.py`*
