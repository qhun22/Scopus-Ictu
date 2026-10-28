# 01 — Kiến thức nghiên cứu: Bài toán Scopus–ICTU

**Tạo lần đầu:** 2026-10-27  
**Cập nhật gần nhất:** 2026-10-27 (v1.3 — Batch 4: cross-GV scope note, distinct EID counting)  
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
| Scopus Preview server error | Batch 3 (2026-10-27): tất cả 6 profiles trả "Unable to display"; page title vẫn load → dùng làm PARTIAL evidence | Fallback về page title; ghi BROWSER_OPENED thay vì PROFILE_ACCESSIBLE |
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

---

*Nguồn tham chiếu chính: `docs/qa/gate_d1r/`, `docs/qa/gate_d2/`, `CLAUDE.md`, `backend/app/services/matching/`, `backend/app/services/review_service.py`*
