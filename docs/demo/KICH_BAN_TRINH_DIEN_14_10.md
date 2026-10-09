# KỊCH BẢN TRÌNH DIỄN SCOPUS–ICTU — NGÀY 14/10/2026

> Tài liệu giúp sinh viên trình bày trước giảng viên (10–15 phút). Soạn ngày 09/10/2026 sau khi **thao tác thật** toàn bộ chức năng trên database test.
> Mọi số liệu và ví dụ dưới đây đã được đối chiếu trực tiếp với dữ liệu hiện có (teacher DB đọc bằng API chỉ-đọc; giao diện thử trên bản sao test giống hệt về nội dung).
> **Nguyên tắc vàng: trên teacher DB chỉ XEM. Không bấm bất cứ nút nào làm ghi dữ liệu** (danh sách ở mục 0.2).
> Không có mật khẩu trong tài liệu này; dùng tài khoản ADMIN demo do nhóm cấp riêng.

---

## 0. Chuẩn bị trước giờ trình bày

### 0.1. Danh sách kiểm tra (làm trước 30 phút)
- [ ] Nhấp đúp `scopus-ictu-qhun22.bat`; chờ `PHAN MEM SAN SANG: http://127.0.0.1:5173`. (Nếu đã chạy từ trước thì BAT dùng lại, không nhân đôi.)
- [ ] Đăng nhập bằng ADMIN; kiểm tra thẻ **Tổng quan** hiện **660 / 411 / 411 / 1207 / 40**.
- [ ] Mở sẵn các tab: **Công bố**, **Duyệt đối sánh**, **Nhật ký hệ thống**.
- [ ] Dán sẵn các EID ví dụ (mục 3) vào một ghi chú để copy vào ô tìm kiếm.
- [ ] Màn hình 1366×768 hoặc lớn hơn; phóng chữ trình duyệt 100–110%. Tắt thông báo hệ điều hành.
- [ ] Xác nhận đang ở **teacher DB** (BAT luôn dùng `scopus_ictu_demo_teacher_20261014`; dòng `Database dung: ...` trong cửa sổ BAT).

### 0.2. Chỉ giới thiệu bằng lời — KHÔNG bấm khi trình diễn
| Nút / chức năng | Vì sao không bấm |
|---|---|
| **Xuất JSON** (trang Giảng viên và trang Công bố) | Ghi thêm dòng nhật ký (`LECTURER_DATASET_EXPORTED`...) vào teacher DB |
| **Thêm giảng viên**, **Xóa**, **Lưu thay đổi** trong Chi tiết | Ghi/xóa dữ liệu; tạo tài khoản |
| Chi tiết giảng viên → **Khóa tài khoản / Đặt lại mật khẩu** | Làm đổi tài khoản + gửi thông báo |
| **Nhập dữ liệu** (CSV hoặc JSON), **Hoàn tác đợt nhập**, **Xóa đợt nhập** | Ghi/xóa dữ liệu nguồn |
| **Chuẩn hóa dữ liệu**, **Bóc tách tác giả** | Ghi dữ liệu chuẩn hóa |
| **Xác nhận đối sánh / Từ chối** | Tạo danh tính và quyết định thật — teacher DB phải giữ **0 danh tính** |
| Swagger `/docs` (thao tác "Try it out") | Có thể ghi/xóa. Chỉ mở để *cho xem* danh sách API nếu bị hỏi |

Chỉ mở cửa sổ **Chi tiết** rồi **đóng bằng nút Hủy/Đóng/×** là an toàn (không ghi). Nhưng để chắc chắn khi hồi hộp, hãy tránh mở Chi tiết giảng viên.

---

## A. KỊCH BẢN 14 PHÚT

| Mốc | Nội dung | Màn hình | Thao tác (chỉ đọc) |
|---|---|---|---|
| 0:00–1:00 | **1. Giới thiệu mục tiêu** | Slide hoặc Trang chủ | Nêu bài toán, 3 nguồn dữ liệu, 3 vai trò |
| 1:00–2:00 | **2. Khởi động bằng BAT** | Cửa sổ BAT (đã chạy sẵn) | Chỉ vào các dòng `[OK]` PostgreSQL → Backend → Frontend |
| 2:00–3:00 | **3. Đăng nhập ADMIN** | `/login` → `/home` | Đăng nhập; "Xin chào, Quản trị viên"; chỉ menu bên trái |
| 3:00–4:00 | **4. Dashboard** | Tổng quan | Đọc 5 thẻ + "Đợt nhập gần nhất" |
| 4:00–5:00 | **5. Quản lý giảng viên** | Giảng viên | Thẻ 411/1/410; gõ `Nguyễn Văn` → Enter; nói về `source_id` |
| 5:00–6:00 | **6. Danh sách công bố** | Công bố | Gõ `UML`; lọc Năm `2020` → Áp dụng |
| 6:00–7:30 | **7+8. Chi tiết bài; số tác giả và từng đơn vị** | Công bố → Chi tiết | EID `2-s2.0-105027527591` rồi `2-s2.0-105006527625` |
| 7:30–9:00 | **9. VERIFIED / CORROBORATED / UNRESOLVED** | Chi tiết bài | EID `2-s2.0-105013367684`; EID `2-s2.0-105035336993` |
| 9:00–10:00 | **10. Hàng đợi matching** | Duyệt đối sánh | 40 ứng viên; giải thích cột; lọc "Chỉ bằng chứng tên" / "Có công bố hỗ trợ" |
| 10:00–11:30 | **11. Publication evidence + shared-author warning** | Duyệt đối sánh → Xem chi tiết | Lương Thị Minh Huế (16 công bố) ; Nguyễn Thị Dung (dùng chung 5) |
| 11:30–13:00 | **12. Review / Audit** | Lịch sử review; Nhật ký hệ thống | Hiện 0 quyết định; nhật ký 16 dòng; nói về ACCEPT/REJECT đã thử trên DB test |
| 13:00–14:00 | **13. Tổng kết** | Trang chủ | Làm được gì, giới hạn, hướng phát triển |

> Nếu bị thiếu thời gian: bỏ mục 5 (giảng viên) và rút mục 6; **giữ nguyên mục 7–11** — đó là phần giảng viên quan tâm nhất.

---

## B. LỜI NÓI GỢI Ý (đọc/nói tự nhiên, có thể diễn đạt lại)

### 1. Giới thiệu mục tiêu (≈ 1 phút)
> "Em xin chào thầy cô. Đề tài của em là hệ thống Scopus–ICTU. Bài toán là nhà trường có danh sách giảng viên và có dữ liệu công bố xuất từ Scopus, nhưng hai nguồn này không nối được với nhau một cách tự động và chắc chắn, vì tên giảng viên và tên tác giả trong Scopus viết khác nhau, lại còn có người trùng tên.
> Hệ thống của em làm ba việc: một là quản lý hồ sơ giảng viên ICTU; hai là nạp và chuẩn hóa dữ liệu Scopus để biết mỗi bài có bao nhiêu tác giả và mỗi tác giả thuộc đơn vị nào theo thông tin của bài báo; ba là đề xuất các cặp ‘giảng viên – tác giả Scopus’ để quản trị viên kiểm tra bằng chứng và quyết định, mọi quyết định đều được lưu vết. Em xin chạy thử hệ thống trên dữ liệu thật."

### 2. Khởi động bằng BAT (≈ 1 phút)
> "Để chạy, em chỉ nhấp đúp một tệp BAT. Tệp này tự khởi động cơ sở dữ liệu PostgreSQL, rồi backend, rồi frontend và mở trình duyệt. Thầy cô có thể thấy ở đây từng bước đều báo OK, và nó kiểm tra đúng cơ sở dữ liệu demo, hiện có 411 hồ sơ giảng viên. Em cố ý để chương trình chỉ chạy trên cơ sở dữ liệu demo riêng và không đụng vào các dữ liệu khác của máy."

### 3. Đăng nhập (≈ 1 phút)
> "Em đăng nhập bằng tài khoản quản trị viên. Hệ thống có ba vai trò: quản trị viên làm được tất cả, phê duyệt viên chỉ xem công bố và duyệt đối sánh, giảng viên chỉ xem hồ sơ và công bố của chính mình. Phần phân quyền được kiểm tra ở cả giao diện lẫn máy chủ: ẩn menu chưa đủ, vì ai biết địa chỉ API vẫn có thể gọi, nên máy chủ trả lỗi 403 nếu không đủ quyền. Em đã thử điều đó bằng tài khoản giảng viên."

### 4. Dashboard (≈ 1 phút)
> "Đây là màn hình tổng quan. Hiện có 660 công bố, 411 hồ sơ giảng viên, 1.207 tác giả Scopus và 40 ứng viên đối sánh đang chờ duyệt. 411 là 410 giảng viên ICTU nhập từ kho lưu trữ của trường, cộng một hồ sơ demo để làm tài khoản giảng viên thử. Phần ‘trạng thái định danh’ đều bằng 0 vì chưa có ai được quản trị viên xác nhận; ứng viên là đề xuất của máy, còn định danh là kết luận của người. Em lưu ý đây là số thống kê tại thời điểm tải trang chứ không phải thời gian thực."

### 5. Quản lý giảng viên (≈ 1 phút)
> "Ở mục Giảng viên có danh sách 411 hồ sơ, tìm theo tên, email, mã cán bộ… Mỗi hồ sơ gốc có một mã nguồn gọi là source_id, thường là đường dẫn hồ sơ trên kho lưu trữ của trường; nhờ nó mà khi nhập lại dữ liệu, hệ thống nhận ra đúng người cũ và giữ nguyên mã nội bộ chứ không tạo bản sao. Em đã kiểm tra bằng cách nhập, sửa, nhập lại và hoàn tác trên cơ sở dữ liệu thử, mã nội bộ không đổi. Hôm nay em chỉ xem, không sửa dữ liệu thật."

### 6. Danh sách công bố (≈ 1 phút)
> "Mục Công bố liệt kê 660 bài. Em có thể tìm theo tiêu đề, EID hoặc DOI, và lọc theo năm, loại tài liệu. EID là mã duy nhất của bài trong Scopus; hệ thống dùng EID làm khóa chính của bài. Ví dụ em gõ UML thì ra các bài về UML."

### 7+8. Chi tiết một bài: số tác giả và từng đơn vị (≈ 1,5 phút)
*(mở EID `2-s2.0-105027527591`)*
> "Đây là bài MUFO về tối ưu bay đa UAV, có 3 tác giả. Em nhìn phần Danh sách tác giả: mỗi tác giả có một hàng riêng, và đơn vị là của riêng từng người, không phải đơn vị chung của cả bài. Tác giả thứ nhất, Nguyen Van-Linh, ghi hai đơn vị ở Đài Loan; hai tác giả còn lại cùng một đơn vị. Vì vậy 3 tác giả nhưng có 4 mục đơn vị. Điều quan trọng là đơn vị này em lấy từ OpenAlex và Crossref chứ không phải từ Scopus, và hệ thống ghi rõ như vậy ngay trên giao diện."

*(mở EID `2-s2.0-105006527625`)*
> "Bài này 5 tác giả. Bốn người được nối với dữ liệu ngoài và có đơn vị: ba người ở Feng Chia University, một người, Bui Van-Tung, ở Đại học Công nghệ Thông tin và Truyền thông Thái Nguyên của mình. Mỗi người xuất hiện hai lần vì có hai nguồn, Crossref và OpenAlex, nên có 8 mục đơn vị. Tác giả thứ năm, Lu Yueh-E, hệ thống ghi ‘chưa xác định được đơn vị’ vì tên không khớp ở cả hai nguồn. Hệ thống không đoán và không lấy đơn vị của người khác điền vào."

### 9. VERIFIED / CORROBORATED / UNRESOLVED (≈ 1,5 phút)
*(mở EID `2-s2.0-105013367684`)*
> "Có ba mức tin cậy. VERIFIED là có bằng chứng danh tính mạnh: ở đây là cầu nối ORCID – Scopus Author ID, nghĩa là hồ sơ ORCID công khai của tác giả tự khai đúng mã Scopus của vị trí này. Ví dụ tác giả Yamaka Woraphon là VERIFIED. CORROBORATED là mức yếu hơn: hai danh sách tác giả cùng độ dài, cùng vị trí, tên trùng khớp, nhưng chưa có định danh chung để chứng minh. Hệ thống không tự nâng CORROBORATED thành VERIFIED. Bài này 5 tác giả, 9 mục đơn vị vì có hai nguồn và có tác giả được ghi nhiều biến thể của cùng một đơn vị."

*(mở EID `2-s2.0-105035336993`)*
> "Còn đây là trường hợp UNRESOLVED: bài này cả OpenAlex lẫn Crossref đều không có dữ liệu, nên cả 3 tác giả đều chưa xác định đơn vị. Em chọn để trống còn hơn đoán sai."

### 10. Hàng đợi matching (≈ 1 phút)
> "Phần cuối là đối sánh giảng viên với tác giả Scopus. Một chương trình riêng, chạy ngoài web, so tên theo các quy tắc xác định: bỏ chức danh như TS., ThS., bỏ dấu, bỏ dấu phẩy, rồi sinh ra các ứng viên. Hiện có 40 ứng viên chờ duyệt. Hệ thống không chấm điểm hay tự duyệt; nó chỉ đưa ra đề xuất kèm bằng chứng. Phần lớn, 34 ứng viên, chỉ có bằng chứng tên, tức là yếu."

### 11. Bằng chứng công bố và cảnh báo dùng chung (≈ 1,5 phút)
*(lọc ‘Có công bố hỗ trợ’ → mở ThS. Lương Thị Minh Huế → Xem chi tiết)*
> "Có 6 ứng viên có thêm bằng chứng công bố. Ví dụ cô Lương Thị Minh Huế có 16 bài mà DOI trùng khớp giữa danh sách công bố đã biết của cô trên kho lưu trữ của trường và các bài của tác giả Scopus 60319803200. Đây là bằng chứng mạnh hơn nhiều so với chỉ trùng tên, và quản trị viên sẽ xem chi tiết từng bài để quyết định."

*(bỏ lọc → mở một dòng ‘ThS. Nguyễn Thị Dung’ có cảnh báo đỏ)*
> "Ngược lại, đây là một cảnh báo: cùng một mã Scopus 59253245500 đang được đề xuất cho 5 giảng viên khác nhau, đều tên Nguyễn Thị Dung. Chỉ có bằng chứng tên nên không thể biết ai là ai. Hệ thống chặn xác nhận lần hai cho cùng một mã, và em đã thử điều đó trên cơ sở dữ liệu thử: xác nhận người thứ hai bị từ chối với lỗi 409. Và việc một giảng viên không có ứng viên cũng không có nghĩa là họ không có công bố, chỉ là tên chưa đủ khớp theo quy tắc."

### 12. Review và Audit (≈ 1,5 phút)
*(mở Lịch sử review, rồi Nhật ký hệ thống)*
> "Trên cơ sở dữ liệu demo này em giữ nguyên, chưa có quyết định nào, nên Lịch sử review trống. Trên một bản sao riêng để thử, em đã xác nhận một ứng viên có 16 công bố và từ chối một ứng viên chỉ có tên; mỗi quyết định tạo ra một dòng lịch sử, một dòng nhật ký, và nếu xác nhận thì tạo một định danh được duyệt; giảng viên đó đăng nhập sẽ thấy 19 công bố của mình. Nhật ký hệ thống ở đây ghi mọi thao tác quan trọng như nhập dữ liệu, chuẩn hóa, và ghi cả người thực hiện, thời gian, lý do. Nó chỉ đọc, không sửa được, nên có thể truy vết khi cần."

### 13. Tổng kết (≈ 1 phút)
> "Tóm lại hệ thống đã nhập 410 giảng viên và 660 công bố với 1.207 tác giả; chuẩn hóa được vị trí tác giả và đơn vị theo từng người kèm mức tin cậy; và có quy trình duyệt đối sánh có bằng chứng và có lưu vết. Em cũng xin nói rõ giới hạn: đơn vị lấy từ OpenAlex và Crossref chứ không phải Scopus nên không đảm bảo đầy đủ 100%; chưa có định danh nào được duyệt trên dữ liệu demo; một số mục như ‘Tác vụ’ hay biểu đồ trang chủ còn đang phát triển. Hướng phát triển tiếp theo là bổ sung giao diện chạy matching và nạp dữ liệu ngoài, thêm biểu đồ thống kê, và để thầy cô cùng duyệt các ứng viên. Em xin cảm ơn thầy cô."

---

## C. BỘ VÍ DỤ THỰC TẾ (đã kiểm chứng từng giá trị ngày 09/10/2026)

### C.1. Công bố — cách mở trên giao diện
**Công bố** → ô tìm kiếm → dán EID → **Chi tiết** (hoặc gõ thẳng địa chỉ `http://127.0.0.1:5173/publications/<EID>`).

| # | EID | Vai trò trong demo | Số liệu đã kiểm chứng |
|---|---|---|---|
| 1 | `2-s2.0-105027527591` | **Ví dụ nhiều tác giả, dễ hiểu** | "MUFO: Multi-UAV flight optimization…", 2026. 3 tác giả; #1 Nguyen, Van-Linh (VERIFIED, 2 đơn vị: NYCU + National Chung Cheng Univ.), #2 Nguyen, Lan-Huong (CORROBORATED, NYCU), #3 Hwang, Ren-Hung (VERIFIED, NYCU) → 4 mục đơn vị |
| 2 | `2-s2.0-105006527625` | **Nhiều tác giả + nhiều liên kết + có tác giả ICTU + có UNRESOLVED** | 5 tác giả; 4 CORROBORATED có đơn vị (Feng Chia University ×3; **Thai Nguyen University of ICT** ×1 — Bui, Van-Tung) × 2 nguồn = **8 mục**; 1 UNRESOLVED (Lu, Yueh-E, NAME_MISMATCH) |
| 3 | `2-s2.0-105013367684` | **Đủ thông tin đơn vị cho 5/5 tác giả; có VERIFIED và CORROBORATED; một tác giả nhiều mục** | "Quantum AMDS Negacyclic Codes…", 2026. 5 tác giả, **9 mục**; #5 Yamaka Woraphon VERIFIED (Chiang Mai University, 3 mục); #4 Thi, Hiep L. CORROBORATED (3 mục, Thu Dau Mot University); #3 Nguyen, Van-Nui CORROBORATED — Thai Nguyen University of ICT |
| 4 | `2-s2.0-105036729228` | **VERIFIED/CORROBORATED nhưng nguồn thiếu đơn vị** | 4 tác giả (2 VERIFIED, 2 CORROBORATED), **không có mục đơn vị nào** (nguồn không cung cấp) |
| 5 | `2-s2.0-105035336993` | **UNRESOLVED** | 3 tác giả, cả 3 UNRESOLVED (`NO_EXTERNAL_WORK`); không có DOI |

- **CORROBORATED**: bài số 2 (4 người), số 3 (#1–#4), số 1 (#2).
- **UNRESOLVED / thiếu đơn vị**: bài số 5 (hoàn toàn), số 2 (#5), số 4 (thiếu đơn vị).

### C.2. Ứng viên đối sánh
- **Có bằng chứng công bố:** Duyệt đối sánh → **Loại bằng chứng = Có công bố hỗ trợ** → 6 dòng. Mở: **ThS. Lương Thị Minh Huế ↔ Luong, Thi Minh-Hue (60319803200) — 16 công bố**. Còn có: PGS.TS. Phùng Trung Nghĩa (28), TS. Vũ Đức Quang (17), TS. Nguyễn Văn Tảo (4), TS. Nguyễn Đức Bình (3), TS. Lê Văn Chung (1).
- **Cảnh báo dùng chung:** dòng đầu tiên của hàng đợi — **ThS. Nguyễn Thị Dung ↔ Nguyen Thi, Dung (59253245500)**, nhãn đỏ *"Tác giả Scopus dùng chung (5 giảng viên)"*; mở **Xem chi tiết** để thấy hộp cảnh báo đỏ ở mục **E**.
- **Mơ hồ (giảng viên có 2 ứng viên):** lọc **Mức độ mơ hồ = Có nhiều ứng viên** (4 dòng, ví dụ TS. Nguyễn Thị Hằng, TS. Vũ Xuân Nam).

> Nếu ví dụ không mở được: ghi **"Cần xác minh"** và dùng mục bất kỳ có cùng nhãn — **không bịa số liệu**.

### C.3. Kết quả đã thử trên DB test (để nói bằng lời, không bấm trên teacher)
- ACCEPT ứng viên Lương Thị Minh Huế → 1 danh định APPROVED; lịch sử + 2 dòng nhật ký; giảng viên đăng nhập thấy 19 công bố.
- REJECT một ứng viên chỉ-tên → bắt buộc nhập lý do; không tạo danh định.
- ACCEPT ứng viên thứ hai cùng Scopus ID `59253245500` → 409 "Tác giả Scopus này đã được xác nhận cho một giảng viên khác."

---

## D. 15 CÂU HỎI GIẢNG VIÊN CÓ THỂ HỎI (kèm trả lời ngắn)

**1. Hệ thống giải quyết bài toán gì?**
Nối *danh mục giảng viên ICTU* với *dữ liệu công bố Scopus* một cách có kiểm soát, và cho biết mỗi tác giả của từng bài thuộc đơn vị nào cùng độ tin cậy; không tự đoán, mọi quyết định có người chịu trách nhiệm và có lưu vết.

**2. Dữ liệu lấy từ đâu?**
Hồ sơ 410 giảng viên từ kho lưu trữ ICTU (JSON); 660 công bố từ tệp CSV xuất Scopus; công bố đã biết của giảng viên từ Craw ICTU; đơn vị theo tác giả từ OpenAlex, Crossref, ORCID. Hệ thống **không gọi Scopus API**.

**3. Vì sao cần normalize (chuẩn hóa)?**
CSV chỉ là bảng thô, một dòng chứa chuỗi nhiều tác giả. Chuẩn hóa tách thành bài (khóa EID), tác giả (khóa Scopus Author ID) và *vị trí tác giả* (ai đứng thứ mấy trong bài nào), nhờ vậy mới đếm, tìm và gắn đơn vị cho từng người được. Chạy lại nhiều lần không sinh trùng (đã kiểm: 0 bản ghi mới).

**3b. Vì sao 1.207 tác giả mà có 2.751 vị trí?** Một tác giả viết nhiều bài; vị trí đếm theo (người × bài).

**4. Vì sao không nối giảng viên với tác giả Scopus theo tên?**
Tên Scopus viết khác (“Nguyen, Thi Hang”, “Hang, Nguyen Thi”), lại có người trùng tên. Ví dụ một mã Scopus được đề xuất cho 5 giảng viên cùng tên Nguyễn Thị Dung. Tên chỉ đủ để *đề xuất*, không đủ để *kết luận*.

**5. Matching hoạt động ra sao?**
Một script chạy ngoài web: bỏ chức danh, hạ chữ thường, bỏ dấu, bỏ dấu phẩy rồi so tên theo 4 quy tắc xác định; sau đó đối chiếu DOI/tiêu đề với công bố đã biết của giảng viên để thêm bằng chứng công bố. Không chấm điểm, không tự duyệt.

**6. Evidence (bằng chứng) là gì?**
Những căn cứ cụ thể gắn với ứng viên: *bằng chứng tên* (quy tắc nào, tên hai phía) và *bằng chứng công bố* (bài nào trùng DOI/tiêu đề). Quản trị viên xem chúng ở cửa sổ chi tiết rồi mới quyết định; chúng còn được lưu lại cùng định danh sau khi ACCEPT.

**7. Vì sao một Scopus author được gợi ý cho nhiều giảng viên?**
Vì tên Scopus của người đó khớp với nhiều hồ sơ ICTU trùng/gần tên. Hệ thống đánh cờ đỏ “dùng chung”, và **chặn** xác nhận lần hai cho cùng mã (409). Một mã chỉ thuộc một người.

**8. VERIFIED và CORROBORATED khác nhau thế nào?**
VERIFIED = có chuỗi định danh (ORCID của tác giả ngoài + hồ sơ ORCID công khai tự khai đúng Scopus ID). CORROBORATED = chỉ khớp *số tác giả + vị trí + tên*, chưa có định danh chung nên chưa phải xác minh. Không tự nâng bậc.

**9. Có thể đảm bảo 100% tổ chức của từng tác giả không?**
Không, và hệ thống không hứa điều đó. Đơn vị đến từ nguồn ngoài (không phải Scopus); 545/2.751 vị trí VERIFIED, 2.053 CORROBORATED, 153 chưa xác định; một số nguồn không có chuỗi đơn vị. Giao diện luôn hiển thị mức tin cậy bên cạnh.

**10. Tại sao có dữ liệu thiếu?**
Nguồn ngoài không có mọi bài (91 vị trí tác giả không tìm thấy bài ở mỗi nguồn); Crossref nhiều bài không công bố đơn vị; khác số tác giả hoặc tên không khớp thì hệ thống để UNRESOLVED thay vì đoán.

**11. Audit giúp gì?**
Biết ai làm gì, khi nào, lý do; chỉ ghi thêm, không sửa/xóa (ADR-003). Ví dụ truy lại một quyết định ACCEPT, một lần nhập dữ liệu, một lần khóa tài khoản.

**12. Tại sao không tự động ACCEPT?**
Sai một liên kết là gán nhầm công bố cho người khác; cần người chịu trách nhiệm, có lý do, và có thể đảo ngược. Hệ thống còn chặn ACCEPT khi mã Scopus đã thuộc người khác.

**13. Cơ chế bảo vệ dữ liệu như thế nào?**
Phân quyền ba vai trò kiểm tra cả ở máy chủ; mật khẩu được băm, không nằm trong JSON xuất; phiên 60 phút, đổi mật khẩu/khóa tài khoản thì phiên cũ vô hiệu; mọi thao tác ghi quan trọng có nhật ký; tách *teacher DB* (chỉ xem) và *DB test* (thử ghi); dữ liệu nguồn không bị sửa; cơ chế khóa phiên bản (version) chống ghi đè.

**14. Hệ thống còn giới hạn gì?**
Chưa có giao diện cho matching, nạp OpenAlex/Crossref, nạp công bố đã biết (đang là script); trang Tác vụ và biểu đồ trang chủ chưa làm; chưa có định danh nào được duyệt trên dữ liệu demo; Khoa/Bộ môn giảng viên phần lớn trống; JSON xuất không khôi phục được điện thoại/Google Scholar; tìm kiếm phân biệt dấu; chưa có màn hình tạo người dùng độc lập.

**15. Nếu phát triển tiếp, nên làm gì?**
(1) Giao diện chạy matching và theo dõi tiến trình (làm trang Tác vụ thật); (2) nạp affiliation tự động và định kỳ; (3) thêm bằng chứng ORCID/đồng tác giả cho matching; (4) biểu đồ thống kê theo năm/đơn vị; (5) tìm kiếm không phân biệt dấu; (6) tự động hóa kiểm thử giao diện.

**(Câu khó bổ sung) 16. Làm sao biết hai hồ sơ trùng tên là hai người khác nhau?**
Mỗi hồ sơ có `source_id` là đường dẫn hồ sơ riêng trên kho lưu trữ ICTU; hệ thống chỉ gộp theo mã nguồn chứ không theo tên.

---

## E. XỬ LÝ NHANH KHI GẶP LỖI LÚC DEMO

| Sự cố | Làm ngay | **Không** làm |
|---|---|---|
| **Trình duyệt không tự mở** | Gõ tay `http://127.0.0.1:5173` | — |
| **Backend lỗi** (đăng nhập báo lỗi mạng, trang báo không tải được) | Xem cửa sổ BAT/`logs\demo\backend.log`. Mở `http://127.0.0.1:8001/health` — phải thấy `{"status":"ok"}`. Nếu không: đóng BAT bằng **S** rồi nhấp đúp lại BAT | Không khởi động thủ công backend với DB khác |
| **API chưa sẵn sàng** | Chờ 20–30 giây (lần đầu PostgreSQL khởi động lâu); F5 | Không chạy migration |
| **Không đăng nhập được** | Kiểm tra bàn phím (Caps Lock), nhập lại; nếu "Tài khoản đang bị khóa" → báo thầy/nhóm; dùng tài khoản ADMIN dự phòng nếu có | **Không** đặt lại mật khẩu hay mở khóa trên teacher DB lúc demo |
| **Không tìm thấy bài ví dụ** | Mở thẳng `/publications/<EID>`; dùng bài khác có cùng nhãn (mục C.1); nói thẳng "Cần xác minh" | Không bịa số liệu; không nhập lại CSV |
| **Trang matching không tải** | F5; kiểm tra bạn vẫn đăng nhập ADMIN (REVIEWER cũng vào được; LECTURER thì không); xem tab Network có `401/403` không | Không bấm ACCEPT/REJECT để "thử cho chắc" |
| **Trang trắng** | Ctrl+F5 | Không sửa mã khi đang demo |
| **Hết thời gian phiên (60 phút)** | Đăng nhập lại | — |
| **Lỡ bấm nhầm "Xuất JSON"** | Bình tĩnh: chỉ thêm một dòng nhật ký và tải một tệp; **không** xóa gì; báo lại cho nhóm sau buổi demo (ghi vào biên bản) | Không cố sửa DB |
| **Lỡ mở cửa sổ Chi tiết giảng viên** | Bấm **Hủy** | Không bấm **Lưu thay đổi** |

Nếu hệ thống hỏng hẳn: chuyển sang trình bày bằng **ảnh chụp màn hình trong thư mục bằng chứng** (`_quan_ly_do_an\evidence\task16\screenshots`) và kể lại luồng dữ liệu (Chương 5 trong hướng dẫn sử dụng).

---

## F. PHÂN VAI NÓI "THẬT" VỀ GIỚI HẠN (nên chủ động nói)
1. Đơn vị công tác theo tác giả **không do Scopus cung cấp**; đến từ OpenAlex/Crossref + đối chiếu.
2. Teacher DB hiện **0 danh tính được duyệt** — đây là chủ ý để giữ nguyên dữ liệu; quy trình duyệt đã chạy được trên DB test.
3. Một số khung trên giao diện (biểu đồ Trang chủ, Tác vụ) **đang phát triển**.
4. Giao diện chưa có chức năng chạy matching/nạp dữ liệu ngoài — thực hiện bằng script do nhóm quản trị chạy.
