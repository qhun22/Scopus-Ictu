# HƯỚNG DẪN SỬ DỤNG PHẦN MỀM SCOPUS–ICTU

> Dành cho sinh viên lần đầu sử dụng hệ thống quản lý dữ liệu khoa học.
> Tài liệu viết ngày 09/10/2026 (Task 16), cập nhật Task 17 (đã bổ sung vai trò Phê duyệt viên, sửa các số liệu và giới hạn), **dựa trên thao tác thật trên phần mềm** — mọi tên nút, tên menu, số liệu và ví dụ
> đều lấy từ giao diện và dữ liệu đang có. Chỗ nào chưa được thử bằng trình duyệt sẽ ghi rõ.
> Tài liệu này **không chứa mật khẩu**. Tài khoản demo do giảng viên hướng dẫn / nhóm cấp riêng.

## Cách đọc nhãn trong tài liệu

Mỗi thao tác có một nhãn an toàn. **Hãy nhìn nhãn trước khi bấm.**

| Nhãn | Ý nghĩa | Dùng ở đâu |
|---|---|---|
| **[CHỈ XEM]** | Chỉ đọc dữ liệu, không ghi vào database. An toàn cho teacher demo. | Teacher DB và test DB |
| **[CÓ GHI DỮ LIỆU]** | Làm thay đổi database (thêm/sửa/xóa/nhập). **Chỉ thử trên test DB.** | Test DB — **không bao giờ** trên teacher DB |
| **[QUẢN TRỊ QUAN TRỌNG]** | Hậu quả lớn, khó hoàn tác hoặc ảnh hưởng tài khoản/danh tính. Phải hiểu rõ trước khi xác nhận. | Test DB, hoặc chỉ giới thiệu bằng lời |

Trạng thái kiểm thử dùng trong tài liệu (chi tiết ở `BAO_CAO_KIEM_THU_CHUC_NANG.md`):
`BROWSER_PASS` (đã thao tác trên trình duyệt thật) · `API_PASS` (đã chạy qua API/test) · `CODE_ONLY` (mới đọc mã) ·
`MANUAL_REQUIRED` · `BLOCKED` · `NOT_IMPLEMENTED` (chưa có chức năng).

---

# Chương 1 — Giới thiệu đồ án

## 1.1. Scopus–ICTU là gì?

**Scopus–ICTU** là hệ thống web nội bộ của Trường Đại học Công nghệ Thông tin và Truyền thông – Đại học Thái Nguyên (ICTU).
Hệ thống giúp **quản lý hồ sơ giảng viên ICTU**, **quản lý các công bố khoa học trong tệp xuất của Scopus**, và
**đối sánh (matching) giảng viên ICTU với tác giả Scopus** một cách có kiểm soát: máy chỉ *đề xuất*, con người (ADMIN) *quyết định*,
mọi quyết định đều được lưu lại (lịch sử review + nhật ký kiểm toán).

## 1.2. Mục tiêu hệ thống

1. Có **một danh sách giảng viên ICTU chuẩn** (hồ sơ gốc từ kho lưu trữ ICTU), giữ ổn định khi nhập lại.
2. Nạp **tệp CSV xuất từ Scopus** và **chuẩn hóa** thành công bố / tác giả / vị trí tác giả.
3. Cho biết với mỗi bài báo: **có bao nhiêu tác giả, mỗi tác giả thuộc tổ chức nào theo thông tin của bài báo**, và độ tin cậy của thông tin đó.
4. Đề xuất **ứng viên đối sánh** giữa giảng viên ICTU và Scopus Author ID, để ADMIN kiểm tra bằng chứng rồi **ACCEPT / REJECT / giữ PENDING**.
5. Ghi lại mọi thao tác quan trọng để **truy vết** (Audit Trail).

## 1.3. Nguồn dữ liệu đang sử dụng

| Nguồn | Nội dung | Cách vào hệ thống |
|---|---|---|
| Kho lưu trữ ICTU (DSpace, `repository.ictu.edu.vn`) | Hồ sơ 410 giảng viên (tên, email đơn vị, học vị, link hồ sơ…) | Tệp JSON → **Nhập dữ liệu → Thêm giảng viên** |
| Tệp CSV xuất từ Scopus (`Truong_Quang_Huy_Scopus_Sep2026.csv`) | 660 công bố, tác giả theo từng bài | **Nhập dữ liệu → Thêm tệp Scopus** → **Chuẩn hóa dữ liệu** |
| Craw ICTU (công bố đã biết của giảng viên) | 328 liên kết nguồn (48 giảng viên, 155 công bố) → lưu **327** bản ghi "công bố đã biết" (liên kết thứ 328 tái sử dụng một bản ghi đã có, không mất dữ liệu) | Script dòng lệnh (không có nút trên giao diện) |
| OpenAlex / Crossref / ORCID (metadata ngoài) | Đơn vị công tác theo từng tác giả trên từng bài | Script dòng lệnh (không có nút trên giao diện) |

> Lưu ý quan trọng: **đơn vị công tác theo tác giả KHÔNG do Scopus cung cấp** trong hệ thống này; nó lấy từ OpenAlex/Crossref và được đối chiếu với tác giả Scopus (xem Chương 4.9 và 6).
> Hệ thống **không gọi Scopus API**.

## 1.4. Các nhóm người dùng

| Vai trò | Là ai | Làm được gì (đã kiểm chứng) |
|---|---|---|
| **ADMIN** ("Quản trị viên") | Cán bộ quản trị hệ thống / người trình diễn | Tất cả: nhập dữ liệu, chuẩn hóa, quản lý giảng viên & tài khoản, xem công bố, duyệt đối sánh, xem lịch sử review và nhật ký |
| **REVIEWER** ("Phê duyệt viên") | Người chỉ chuyên duyệt đối sánh | Xem **Công bố**, **Duyệt đối sánh**, **Lịch sử review**, Tra cứu và **ACCEPT/REJECT**. **Không** vào được Tổng quan, Nhập dữ liệu, Chuẩn hóa, Giảng viên, Nhật ký, Tác vụ, Xuất JSON. Đã `BROWSER_PASS` trên DB test (Task 17); **teacher DB hiện chưa có tài khoản REVIEWER** (3 tài khoản: 2 ADMIN + 1 LECTURER) |
| **LECTURER** ("Giảng viên") | Giảng viên có tài khoản | Chỉ xem **Hồ sơ cá nhân**, **Công bố của tôi**, **Liên kết Scopus** của chính mình |

Ma trận quyền chi tiết (đã kiểm chứng, Task 17) xem mục **4.16**. Vì sao Frontend ẩn menu nhưng Backend vẫn phải kiểm tra quyền? Vì menu chỉ là giao diện; ai biết địa chỉ API vẫn có thể gọi trực tiếp.
Đã kiểm chứng: tài khoản LECTURER gọi API quản trị nhận **HTTP 403**; chưa đăng nhập nhận **HTTP 401** (`API_PASS`).

## 1.5. Vấn đề hệ thống giải quyết

- Một giảng viên có thể xuất hiện trong Scopus dưới nhiều dạng tên; nhiều người có thể **trùng tên**. Không thể nối bằng tên.
- Một bài báo nhiều tác giả, mỗi người một đơn vị; thông tin đơn vị trên bài phải gắn **đúng người**.
- Cần **bằng chứng** và **người chịu trách nhiệm** cho mỗi liên kết giảng viên ↔ Scopus.

## 1.6. Giới hạn chức năng hiện tại (nói thật khi trình bày)

- **Không có** màn hình "Tác vụ hệ thống" (`/tasks` chỉ là trang giữ chỗ — `NOT_IMPLEMENTED`).
- **Không có** màn hình riêng "Người dùng": quản lý tài khoản nằm trong cửa sổ **Chi tiết** của giảng viên (`/users` tự chuyển sang `/lecturers`).
- **Không có** nút trên giao diện để: sinh ứng viên đối sánh, nạp OpenAlex/Crossref, nạp công bố đã biết (đều là script dòng lệnh).
- Các khung biểu đồ ở **Trang chủ** là giữ chỗ (luôn "Chưa có dữ liệu để hiển thị biểu đồ"), nhãn đã đổi thành "Đang phát triển".
- Trường **điện thoại (`tel`)** và **Google Scholar** có trong JSON nguồn nhưng **không có cột trong database**, nên **Xuất JSON không khôi phục được** hai trường này.
- Khoa / Bộ môn của giảng viên ICTU phần lớn **chưa có dữ liệu** (cột hiển thị "—").
- Hiện **0 danh tính được APPROVED** trong teacher DB (mọi ứng viên đang PENDING).
- Tìm kiếm tên **không phân biệt dấu và hoa/thường** (Task 17): "Luong", "luong", "Lương" đều tìm ra cả giảng viên "Lương Thị Minh Huế" lẫn tác giả Scopus "Luong, Thi Minh-Hue". Chỉ áp dụng cho tra cứu/danh sách; **không** thay đổi luật đối sánh danh tính.
- Ngày giờ ở Tổng quan, Nhật ký, Lịch sử review hiển thị `HH:mm:ss dd/MM/yyyy` (ví dụ `13:50:38 09/10/2026`, múi giờ trình duyệt). Một số màn hình khác (Nhập dữ liệu, Chuẩn hóa) có định dạng ngắn riêng.
- Nếu có lỗi hiển thị không lường trước, giao diện hiện thông báo "Đã xảy ra lỗi hiển thị" kèm nút **Tải lại trang** (Error Boundary, Task 17) thay vì màn hình trắng.

---

# Chương 2 — Khởi động và đăng nhập

## 2.1. Khởi động (không cần chạy ba cửa sổ CMD)

1. Mở thư mục `D:\DataFolder\ProjectIctu\DoAn\Scopus-Ictu`.
2. **Nhấp đúp** tệp `scopus-ictu-qhun22.bat`.
3. Cửa sổ đen hiện lần lượt các dòng `[OK]` (đợi khoảng 10–40 giây, lần đầu sau khi bật máy có thể lâu hơn vì PostgreSQL phải khởi động):
   - `PostgreSQL demo da san sang (cong 55432 ...)`
   - `Database dung: scopus_ictu_demo_teacher_20261014 ... 411 ho so giang vien`
   - `Backend san sang: http://127.0.0.1:8001/docs`
   - `Frontend san sang: http://127.0.0.1:5173`
   - `Da mo trinh duyet: http://127.0.0.1:5173`
4. Trình duyệt tự mở trang đăng nhập. Nếu không tự mở, gõ `http://127.0.0.1:5173`.
5. Cuối cửa sổ có dòng: *"Nhấn S để DỪNG phần mềm, K để giữ phần mềm chạy và thoát"*. **Đóng cửa sổ này KHÔNG dừng phần mềm.**
   Khi demo xong nên nhấn **K** (để chạy nền) hoặc **S** (dừng hẳn).

## 2.2. Đăng nhập ADMIN `[CHỈ XEM]`

1. Ở màn hình **Đăng nhập tài khoản**, nhập **Email** và **Mật khẩu** của tài khoản ADMIN demo (do nhóm cấp riêng, *không ghi trong tài liệu*).
2. Bấm **Đăng nhập**. Thành công: toast "Đăng nhập thành công", chuyển tới **Trang chủ** với lời chào "Xin chào, Quản trị viên".
3. Nhập sai email/mật khẩu: toast đỏ "Đăng nhập thất bại — Email hoặc mật khẩu không đúng." (`BROWSER_PASS`).
4. Phiên đăng nhập kéo dài **60 phút**; tải lại trang (F5) vẫn giữ phiên; hết hạn hoặc bị thu hồi thì tự về trang đăng nhập (`BROWSER_PASS` + `API_PASS`).
5. Mở địa chỉ được bảo vệ (ví dụ `/audit-logs`) khi chưa đăng nhập → tự chuyển về `/login` (`BROWSER_PASS`).

## 2.3. Đăng xuất

Bấm khung tên người dùng ở góc phải trên → **Đăng xuất** → toast "Đăng xuất thành công" và về trang đăng nhập (`BROWSER_PASS`).

## 2.4. Dừng chương trình

- Cách 1: trong cửa sổ BAT nhấn **S**.
- Cách 2 (khi cửa sổ BAT đã đóng): mở CMD tại thư mục `Scopus-Ictu`, gõ `scopus-ictu-qhun22.bat stop`.
- Chỉ dừng các tiến trình **của chính demo** (cổng 8001, 5173, và PostgreSQL demo cổng 55432); không động tới PostgreSQL cổng 5432.

## 2.5. Nhận biết lỗi khởi động

Mọi lỗi in dạng `[LOI] ...` và cửa sổ giữ nguyên để đọc. Nhật ký chi tiết: `D:\DataFolder\ProjectIctu\DoAn\_quan_ly_do_an\logs\demo\` (`launcher.log`, `backend.log`, `frontend.log`).
Xem thêm Chương 7.

---

# Chương 3 — Giao diện tổng quan

Thanh menu bên trái (ADMIN). Trạng thái: ✔ = đã có chức năng thật.

| Menu (tiếng Việt) | Địa chỉ | Chức năng | Quyền | Đọc / Ghi | Tình trạng |
|---|---|---|---|---|---|
| Trang chủ | `/home` | Lời chào, ô Tra cứu nhanh, lối tắt. Khung biểu đồ/hoạt động là giữ chỗ | Mọi vai trò | Chỉ đọc | ✔ (một phần giữ chỗ) |
| Tổng quan | `/dashboard` | Thẻ thống kê, trạng thái định danh, đợt nhập gần nhất, hoạt động gần đây | ADMIN | Chỉ đọc | ✔ |
| Nhập dữ liệu | `/imports` | Nhập CSV Scopus; nhập JSON giảng viên; lịch sử các đợt nhập; hoàn tác/xóa đợt nhập | ADMIN | **Ghi** | ✔ |
| Chuẩn hóa dữ liệu | `/normalization` | Chuẩn hóa công bố; bóc tách tác giả; danh sách tác giả Scopus | ADMIN | **Ghi** (nút chuẩn hóa) / Đọc (danh sách) | ✔ |
| Giảng viên | `/lecturers` | Danh sách, tìm kiếm, thêm, sửa, xóa hồ sơ; cấp/khóa/mở khóa tài khoản; đặt lại mật khẩu; Xuất JSON | ADMIN | **Ghi** | ✔ |
| Công bố | `/publications` | Danh sách công bố, lọc, chi tiết bài + tác giả + đơn vị theo tác giả; Xuất JSON (**chỉ ADMIN**: REVIEWER không thấy nút, API trả 403) | ADMIN, REVIEWER | Đọc (nút Xuất JSON **ghi audit**) | ✔ |
| Duyệt đối sánh | `/reviews` (cũng `/approval-queue`) | Hàng đợi ứng viên; xem bằng chứng; ACCEPT / REJECT | ADMIN, REVIEWER | Đọc; **Ghi** khi ACCEPT/REJECT | ✔ |
| Lịch sử review | `/review-history` | Danh sách quyết định đã ghi (chỉ đọc) | ADMIN, REVIEWER | Chỉ đọc | ✔ |
| Nhật ký hệ thống | `/audit-logs` | Nhật ký kiểm toán chỉ đọc, có bộ lọc | ADMIN | Chỉ đọc | ✔ |
| Tác vụ | `/tasks` | Trang "Tác vụ hệ thống — đang hoàn thiện" | ADMIN | — | **NOT_IMPLEMENTED** |
| (không có trên menu) Tra cứu | `/search` | Tìm giảng viên / công bố / tác giả Scopus; vào từ ô tìm ở Trang chủ | ADMIN, REVIEWER | Chỉ đọc | ✔ |

Menu của **LECTURER**: Trang chủ · Hồ sơ cá nhân (`/profile`) · Công bố của tôi (`/my-publications`) · Liên kết Scopus (`/identity`).
Menu của **REVIEWER**: Trang chủ · Công bố · Duyệt đối sánh · Lịch sử review.

Phần đầu trang: nút **thu gọn menu**, công tắc ngôn ngữ **VI / EN**, khung người dùng (Thông tin tài khoản, Đăng xuất).
Chân menu hiển thị phiên bản (ví dụ "M2.3").

> **Chỉ nên giới thiệu, không bấm khi trình diễn trên teacher DB:** nút **Xuất JSON** (ở Giảng viên và Công bố — ghi nhật ký), **Thêm giảng viên**, **Xóa**, **Chi tiết → Khóa tài khoản / Đặt lại mật khẩu**, **Nhập dữ liệu** (cả CSV và JSON), **Chuẩn hóa dữ liệu**, **Xác nhận đối sánh / Từ chối**.

---

# Chương 4 — Hướng dẫn chi tiết từng chức năng

Mỗi chức năng theo cùng khung: Mục đích · Khi nào dùng · Điều kiện · Các bước · Ví dụ · Kết quả mong đợi · Lỗi thường gặp · Cách xử lý · Cảnh báo database · Đã kiểm thử.

## 4.1. Trang chủ và Tổng quan (Dashboard) — **[CHỈ XEM]**

- **Mục đích:** nhìn nhanh quy mô dữ liệu và tình trạng xử lý.
- **Các bước:** menu **Tổng quan** → xem các thẻ → bấm **Làm mới** nếu cần.
- **Số liệu thật trên teacher DB** (đối chiếu API `GET /api/v1/dashboard/summary` và database):

| Thẻ | Giá trị | Ý nghĩa |
|---|---|---|
| Tổng công bố | **660** | Số bài báo (EID duy nhất) |
| Tổng giảng viên | **411** | 410 giảng viên ICTU + 1 hồ sơ demo ("Người dùng") |
| Giảng viên hoạt động | **411** | Hồ sơ đang `is_active` |
| Tác giả Scopus | **1.207** | Số Scopus Author ID duy nhất |
| Chờ duyệt | **40** | Ứng viên đối sánh trạng thái PENDING |
| Trạng thái định danh: ỨNG VIÊN / ĐÃ DUYỆT / BỊ TỪ CHỐI / BỊ THU HỒI | **0 / 0 / 0 / 0** | *Định danh* (identity) chỉ xuất hiện **sau khi** ADMIN ACCEPT. Chưa ai ACCEPT nên đều 0 |
| Đợt nhập gần nhất | `Truong_Quang_Huy_Scopus_Sep2026.csv`, APPLIED, 660/660 hợp lệ, 0 lỗi | Lần nhập CSV Scopus |

- **Lưu ý:** "Chờ duyệt = 40" (ứng viên) **khác** "ỨNG VIÊN = 0" (định danh). Đây là hai khái niệm khác nhau (xem 6.9).
- Số liệu là **thống kê tại thời điểm tải trang**, không phải thời gian thực. Nút **Làm mới** tải lại.
- **Trang chủ:** ô **Tra cứu nhanh** → gõ ≥ 2 ký tự → **Tìm kiếm** → chuyển tới `/search?q=...`.
- **Đã kiểm thử:** `BROWSER_PASS` (hiển thị, điều hướng, tải lại trang); `API_PASS` (đối chiếu số liệu với database). Dashboard không có biểu đồ — chỉ có thẻ và bảng.

## 4.2. Quản lý giảng viên — **[CÓ GHI DỮ LIỆU khi thêm/sửa/xóa — chỉ test DB]**

### Khái niệm cần nắm
- **Hồ sơ giảng viên** (bảng `lecturers`): thông tin về *một con người* trong danh mục ICTU.
- **`source_id`**: định danh của *nguồn*, với ICTU thường là **URL hồ sơ** trên kho lưu trữ (ví dụ `https://repository.ictu.edu.vn/giang-vien/hoang-ha-giang/`). Dùng để nhận ra "đây là cùng hồ sơ" khi nhập lại.
- **UUID nội bộ**: mã máy tự sinh khi tạo hồ sơ (ví dụ `5326512f-...`). **Giữ nguyên** khi cập nhật. Không bao giờ nên tự tạo UUID giả thay cho `source_id`.
- **ORCID**: mã định danh nhà nghiên cứu quốc tế (dạng `0000-0002-1825-009X`). Dùng làm *bằng chứng* (xem 4.9).
- **Scopus Author ID**: mã số tác giả do Scopus gán. Một người có thể có nhiều ID; một ID đôi khi bị gộp nhầm nhiều người.
- **Vì sao 410 + 1 = 411?** 410 hồ sơ nhập từ JSON ICTU + 1 hồ sơ demo do script `seed_demo_users` tạo cho tài khoản `user@gmail.com`.
- **Vì sao hai giảng viên trùng tên vẫn phải giữ riêng?** Ví dụ trong ứng viên đối sánh có 4 hồ sơ "ThS. Nguyễn Thị Dung" và 1 hồ sơ "PGS.TS. Nguyễn Thị Dung" — là **5 hồ sơ nguồn khác nhau**. Chỉ kho ICTU (`source_id`) mới biết họ là ai; tên giống không chứng minh cùng người.

### Xem danh sách / tìm kiếm / phân trang / chi tiết — **[CHỈ XEM]**
1. Menu **Giảng viên**. Đầu trang có 5 thẻ: *Tổng giảng viên, Đã cấp tài khoản, Chưa cấp tài khoản, Tài khoản bị khóa, Cảnh báo*.
2. Gõ vào ô tìm kiếm (họ tên, email, mã cán bộ, bộ môn, khoa hoặc UUID) rồi **Enter**. Ví dụ gõ `Nguyễn Văn` rồi Enter → bảng chỉ còn các giảng viên khớp, số trang cập nhật theo kết quả.
3. Cuối bảng chọn số dòng **10 / trang** hoặc dùng **Trang trước / Trang sau**. Nút **Đặt lại** xóa bộ lọc.
4. Bấm **Chi tiết** để xem cửa sổ hồ sơ (UUID ở đầu cửa sổ, link **Trang hồ sơ nguồn**).
   - Nếu mở bằng nút **Chi tiết** rồi **Hủy** → không có thay đổi nào.
- `BROWSER_PASS` (tìm, phân trang, chi tiết). Cột **Khoa / Bộ môn** thường "—" vì dữ liệu nguồn chưa có.

### Thêm giảng viên — **[CÓ GHI DỮ LIỆU]** (chỉ test DB)
1. **Thêm giảng viên** → điền **Họ và tên\***, **Email giảng viên\***, **Mật khẩu tài khoản\*** (≥ 8 ký tự), (tùy chọn) **Mã cán bộ**, **Vai trò** (Giảng viên / Quản trị viên / Phê duyệt viên), **Học vị / Học hàm**, **Khoa / Bộ môn** → **Tạo giảng viên**.
2. Mã cán bộ để trống được (lưu NULL). Hệ thống gợi ý từ email nhưng có thể sửa.
3. **Một lần tạo ra hai thứ:** hồ sơ giảng viên **và** tài khoản đăng nhập (liên kết với hồ sơ).
- **Kết quả:** toast "Thêm thành công"; số "Tổng giảng viên" tăng 1; **nhật ký ghi `LECTURER_CREATED`** (đã sửa trong Task 16 — trước đó thao tác này *không* được ghi nhật ký).
- **Lỗi thường gặp (đã thử):** mật khẩu < 8 ký tự → trình duyệt báo ngay; email đã có tài khoản → khung đỏ "Email đã được sử dụng." (HTTP 409); thiếu tên/email → 422.
- **Mã cán bộ trùng** → 409 `STAFF_CODE_ALREADY_EXISTS` (`API_PASS`).
- **Email trùng ở hồ sơ giảng viên:** hệ thống **cho phép** giữ hai *hồ sơ* trùng email (dữ liệu ICTU có trường hợp này) để quản trị viên đối soát; hồ sơ trùng được gắn nhãn **Cảnh báo**, thẻ "Cảnh báo" tăng, cửa sổ chi tiết nhắc "Hồ sơ cần được rà soát". Nhưng **tài khoản đăng nhập** thì email phải duy nhất.
- `BROWSER_PASS`.

### Sửa hồ sơ — **[CÓ GHI DỮ LIỆU]**
1. **Chi tiết** → sửa các ô (Họ và tên, Email đơn vị, Mã cán bộ, Học vị/Học hàm, Khoa, Bộ môn) → **Lưu thay đổi**.
2. Xóa trống **Họ và tên** → trình duyệt chặn ("Please fill out this field").
3. Kết quả: toast "Cập nhật thành công"; `version` tăng 1; nhật ký ghi `LECTURER_UPDATED` (trước/sau).
4. **Xung đột phiên bản:** nếu hồ sơ đã bị người khác sửa → HTTP 409 `VERSION_CONFLICT` "Dữ liệu ... đã thay đổi. Vui lòng tải lại." (`API_PASS`). **Cách xử lý:** tải lại trang rồi sửa lại.
5. ORCID sai định dạng (chỉ qua API): trước Task 16 báo nhầm 409 "trùng"; nay trả 422 "ORCID không hợp lệ..." (đã sửa, có test).

### Xóa hồ sơ — **[QUẢN TRỊ QUAN TRỌNG]**
- **Xóa** → hộp thoại xác nhận "Xóa giảng viên?". Hồ sơ **đang có tài khoản** hoặc **có ứng viên/công bố liên quan** sẽ bị chặn (409 `LECTURER_IN_USE`, toast "Không thể xóa giảng viên — Hồ sơ này đang được liên kết với dữ liệu khác"). Hồ sơ tự do được xóa và ghi `LECTURER_DELETED`. (`BROWSER_PASS`.)
- **Không xóa hồ sơ trên teacher DB.**

### Quản lý tài khoản (nằm trong Chi tiết giảng viên) — **[QUẢN TRỊ QUAN TRỌNG]**
Bốn khái niệm **khác nhau, không đánh đồng**:

| Khái niệm | Là gì | Lưu ở đâu |
|---|---|---|
| **Hồ sơ giảng viên** | Thông tin về con người (tên, email đơn vị, học vị…) | bảng `lecturers` |
| **Tài khoản đăng nhập** | Email + mật khẩu băm để vào phần mềm | bảng `users` (có thể *không* gắn hồ sơ — ví dụ `admin@gmail.com`) |
| **Vai trò trong phần mềm** | ADMIN / REVIEWER / LECTURER: quyền thao tác | cột `role` của `users` |
| **Danh tính tác giả Scopus** | "Giảng viên X chính là Scopus Author ID Y" — kết quả của ACCEPT | bảng `lecturer_scopus_identities` |

Một giảng viên có thể *chưa có tài khoản* nhưng vẫn *có danh tính Scopus*; một tài khoản ADMIN không cần là giảng viên.

Thao tác (khi hồ sơ **chưa** có tài khoản): **Chi tiết** → tích **Cấp tài khoản đăng nhập hệ thống cho giảng viên này** → nhập *Email đăng nhập*, *Mật khẩu khởi tạo*, *Vai trò* → **Lưu thay đổi**.
Khi hồ sơ **đã** có tài khoản: cửa sổ hiện *Email đăng nhập*, *Vai trò*, *Trạng thái tài khoản* (Đang hoạt động / Đã khóa), ô *Mật khẩu mới* và các nút:
- **Đặt lại mật khẩu**: bắt buộc ≥ 8 ký tự (báo "Mật khẩu mới phải có ít nhất 8 ký tự."), có hộp xác nhận; sau khi đặt lại, mật khẩu cũ **không dùng được** (đã thử: cũ → 401, mới → 200) và phiên đang đăng nhập của người đó bị thu hồi (tải lại trang là về đăng nhập). Ghi `USER_PASSWORD_RESET`.
- **Khóa tài khoản / Mở khóa tài khoản**: có hộp xác nhận; tài khoản khóa không đăng nhập được (HTTP 403 `ACCOUNT_LOCKED`, `API_PASS`). Ghi `USER_LOCKED` / `USER_UNLOCKED`.
- Người bị khóa/đặt lại mật khẩu nhận **thông báo** (bảng `user_notifications`, hiển thị dạng toast khi họ tải trang; không có trang "Thông báo" riêng).
- Đổi **Vai trò**: ngay trong cửa sổ **Chi tiết** của giảng viên có tài khoản, ô **Vai trò** (Giảng viên / Quản trị viên / Phê duyệt viên) → **Lưu thay đổi** (`BROWSER_PASS`, ghi `USER_ROLE_CHANGED` và gửi thông báo "Quyền tài khoản đã thay đổi" cho người đó); cũng làm được qua `PATCH /users/{id}` (`API_PASS`). **Quy tắc an toàn (Task 17):** ADMIN **không tự đổi vai trò của chính mình** (409 `CANNOT_CHANGE_OWN_ROLE`) và **không thể hạ quản trị viên cuối cùng** (409 `LAST_ADMIN_PROTECTED`); vai trò LECTURER cần có hồ sơ giảng viên (422 `LECTURER_PROFILE_REQUIRED`); ADMIN/REVIEWER thì không bắt buộc.
- **Không có** nút "Tạo user" độc lập và **không có** trang "Người dùng" riêng (`NOT_IMPLEMENTED`); tài khoản mới tạo qua *Thêm giảng viên* hoặc *Cấp tài khoản*.

## 4.3. Nhập JSON giảng viên — **[CÓ GHI DỮ LIỆU — chỉ test DB]**

- **Mục đích:** nạp/cập nhật danh mục giảng viên từ tệp JSON chuẩn của dự án.
- **Điều kiện:** tệp `.json` ≤ 20 MB, có khối `dataset` và mảng `lecturers`; mỗi bản ghi cần `source_id` và `full_name`.
- **Quy trình thật (đã thử trên test DB sạch):**
  1. Menu **Nhập dữ liệu** → khung **Tải tệp Giảng viên** → bấm/kéo thả tệp JSON.
  2. Bấm **Kiểm tra dữ liệu** (Preview — *chưa ghi gì*). Thẻ **KẾT QUẢ** hiện: *Tổng hồ sơ, Hợp lệ, Tạo mới, Cập nhật, Không thay đổi, Cảnh báo*.
  3. Bấm **Xác nhận nhập** → hộp thoại "Xác nhận nhập dữ liệu giảng viên?" → **Xác nhận nhập**.
  4. Kiểm tra tại menu **Giảng viên**.
- **Ví dụ thật (test DB sạch, tệp `ictu_lecturers_merged.json` — 410 hồ sơ):** Preview = Tạo mới 410 → Xác nhận → database có 411 hồ sơ (410 + 1 demo), 410 bản ghi nguồn, 352 hồ sơ có ORCID, 410 hồ sơ có `source_id` (link hồ sơ).
- **Cập nhật giữ ổn định:** nhập `edit_email_position.json` (cùng `source_id`, đổi email 1 người và chức vụ 1 người) → Preview "Cập nhật 2, Không thay đổi 408" → Nhập → email đổi, `version` tăng, **UUID giữ nguyên**, tổng vẫn 411.
- **Hồ sơ vắng mặt không bị xóa:** nhập tệp chỉ 50 hồ sơ → 360 hồ sơ còn lại **giữ nguyên**; tệp 50 dòng còn **khôi phục** (revert) 2 giá trị đã sửa về trạng thái cũ.
- **Hoàn tác đợt nhập (Restore):** **Nhập dữ liệu** → dòng đợt nhập → **Chi tiết** → **Xóa đợt nhập** → hộp "Cần hoàn tác trước khi xóa" → **Hoàn tác đợt nhập** → hộp "Hoàn tác đợt nhập giảng viên?" → **Hoàn tác**. Kết quả: trạng thái "Đã hoàn tác", các hồ sơ do đợt đó *tạo* bị gỡ, hồ sơ *cập nhật* được trả về giá trị trước; hồ sơ thêm thủ công giữ nguyên; ghi `LECTURER_DATASET_ROLLED_BACK`. Nếu hồ sơ trong đợt nhập đã có tài khoản → bị chặn, phải gỡ liên kết trước.
- **Lỗi thường gặp (đã thử):**

| Tình huống | Thông báo thật |
|---|---|
| JSON sai cú pháp (cắt ngang tệp) | "Không thể kiểm tra tệp — INVALID_LECTURER_DATASET: Tệp JSON không hợp lệ. Vui lòng kiểm tra định dạng tệp." |
| Thiếu trường bắt buộc | "INVALID_LECTURER_DATASET: lecturers[0].full_name là bắt buộc." |
| Hai bản ghi trùng email trong cùng tệp | "DUPLICATE_LECTURER_IDENTITY: Email '...' bị trùng giữa các bản ghi." |

- **Ba phiên bản JSON trong dữ liệu thật (đều `schema_version` 1.0):**
  1. `ictu_lecturers.json` — bản thô từ DSpace: 410 hồ sơ, **chưa có** ORCID/điện thoại.
  2. `ictu_lecturers_merged.json` — bản gộp: thêm **ORCID (352)** và điện thoại (327); dùng cho teacher DB.
  3. Bản **xuất từ chính hệ thống** (Xuất JSON): có `full_name_normalized`, ORCID, **không có `tel`** (database không lưu).
  Nhập bản (1) lên DB đang có ORCID sẽ cho Preview "Cập nhật 352" (xóa ORCID) — **cẩn thận khi nhập tệp cũ**.
- **`Xuất JSON`** (nút ở trang **Giảng viên**): tải về 410 hồ sơ giảng viên ICTU (không gồm hồ sơ demo), **không chứa mật khẩu/băm/token/secret** (đã quét: 0 từ khóa nhạy cảm). Xuất xong nhập lại → Preview "Không thay đổi 410". **Mỗi lần Xuất ghi `LECTURER_DATASET_EXPORTED` vào nhật ký** → *không bấm trên teacher DB*.
- **Đã kiểm thử:** `BROWSER_PASS` (chọn tệp, Preview, nhập, cập nhật, khôi phục, hoàn tác, các lỗi trên); nút Xuất JSON `BROWSER_PASS` (gọi server, ghi nhật ký) + nội dung tệp `API_PASS` (trình duyệt tích hợp không cho kiểm tra tệp tải về).

## 4.4. Nhập CSV Scopus — **[CÓ GHI DỮ LIỆU — chỉ test DB]**

### CSV Scopus là gì?
Tệp bảng tính mà Scopus cho phép "Export" kết quả tìm kiếm. Mỗi **dòng = một công bố**; các cột gồm tên bài, tác giả, EID, DOI, năm, nguồn… File dùng trong đồ án: `D:\DataFolder\ProjectIctu\DoAn\Truong_Quang_Huy_Scopus_Sep2026.csv` (660 dòng, SHA-256 `6a62fcf6...f75d`).
> Lưu ý: bản CSV bị Git bỏ qua trong repository có checksum khác bản gốc ở thư mục `DoAn` (nội dung giá trị khớp). Task 16 dùng **bản gốc ở `DoAn`**.

### Thuật ngữ
- **EID**: mã duy nhất của bài trong Scopus, dạng `2-s2.0-105006527625`. Hệ thống dùng EID làm "chứng minh thư" của bài (ADR-001).
- **DOI**: mã định danh tài liệu số của nhà xuất bản (`10.3390/wevj16050276`). Có thể thiếu (một số bài không có).
- **Scopus Author ID**: mã tác giả, ví dụ `57201704313`.
- **Dữ liệu thô** (`raw_scopus_records`): nguyên văn từng dòng CSV. **Dữ liệu chuẩn hóa**: bảng `publications`, `scopus_authors`, `publication_authors` đã tách và khử trùng.

### Các bước
1. **Nhập dữ liệu** → khung **Tải tệp Scopus** → chọn tệp `.csv` (≤ 20 MB) → **Bắt đầu nhập**.
2. Kết quả: thẻ **KẾT QUẢ** *Tổng bản ghi 660 · Đã nhập 660 · Lỗi 0*; đợt nhập có trạng thái chờ chuẩn hóa. Dữ liệu mới chỉ ở dạng **thô**.
3. Menu **Chuẩn hóa dữ liệu** → thẻ tab **Công bố** → mục **Cần xử lý** → **Chuẩn hóa dữ liệu** (đợi vài giây) → đợt chuyển sang **Lịch sử đã xử lý** "Hoàn thành". Kết quả: 660 công bố chuẩn.
4. Tab **Tác giả** → mục **Đợt nhập cần xử lý** → **Bóc tách tác giả** (đợi ~30 giây; có vòng quay "Đang xử lý") → bảng **Tác giả Scopus** có dữ liệu.
- **Kết quả thật (test DB sạch, qua giao diện):** 660 công bố · **1.207 tác giả Scopus** · **2.751 vị trí tác giả** · 2.768 biến thể tên — **trùng khớp từng giá trị** với teacher DB (đã so sánh mã băm nội dung cả 3 bảng, không chỉ số dòng).
- **Vì sao 1.207 tác giả tạo ra 2.751 vị trí?** *Tác giả* đếm mỗi con người một lần (theo Scopus Author ID). *Vị trí tác giả* đếm mỗi lần một người xuất hiện trong một bài. Một tác giả viết nhiều bài ⇒ nhiều vị trí. Ví dụ: tác giả `60319803200` (Luong, Thi Minh-Hue) có mặt trong 19 bài ⇒ 1 tác giả, 19 vị trí.
- **Nhập trùng:** chọn lại cùng tệp → thông báo vàng "Tệp có nội dung trùng với một đợt nhập trước…" với nút **Xem đợt trước** / **Vẫn nhập lại** (API trả 409 `DUPLICATE_IMPORT_CONFIRMATION_REQUIRED`). **Không bấm "Vẫn nhập lại"** nếu không cần.
- **Chuẩn hóa lặp lại an toàn (idempotent):** chạy lại chuẩn hóa công bố + tác giả: 0 bản ghi mới, 2.751 "đã tồn tại", số liệu không đổi (`API_PASS`).
- **Lỗi thường gặp:** tệp `.txt` → "Chỉ hỗ trợ tệp CSV." (UI) / 422 `UNSUPPORTED_IMPORT_FORMAT` (API). **CSV không phải bản xuất Scopus** (thiếu cột `EID`, ví dụ cột `cot1,cot2`) bị từ chối ngay khi nhập (Task 17): đợt nhập có trạng thái **Thất bại** (0/0), mở **Chi tiết** thấy "Chi tiết lỗi: Tệp CSV không phải bản xuất từ Scopus: thiếu cột EID…" (mã `MISSING_EID_COLUMN`); không có dữ liệu thô nào được lưu và không hiện phần "Đi tới chuẩn hóa". (Trước Task 17 tệp này được nhận như dữ liệu thô rồi báo "Hoàn thành".) Nếu một đợt vẫn chuẩn hóa xong nhưng có dòng lỗi, cột kết quả hiện **"Hoàn thành có lỗi"** (màu cam) và đợt được tính vào thẻ **Có lỗi**.
- **Xóa đợt nhập:** đợt đã chuẩn hóa/đang được dùng → 409 `IMPORT_IN_USE` (không xóa được); đợt chưa dùng xóa được; **Lưu trữ / Khôi phục lịch sử** để ẩn/hiện khỏi danh sách (`API_PASS`).
- **Đã kiểm thử:** `BROWSER_PASS` (import, chuẩn hóa công bố, bóc tách tác giả, trùng, sai định dạng); `API_PASS` (idempotency, quản lý đợt nhập).

## 4.5. Công bố khoa học — **[CHỈ XEM]** (trừ nút Xuất JSON)

1. Menu **Công bố** → danh sách có cột: *Công bố (tiêu đề), EID, Năm, Nguồn tạp chí, Loại tài liệu, Trích dẫn, Giai đoạn xuất bản, Truy cập mở, Thao tác*. (Task 16 đã sửa cột tiêu đề bị co lại 77 px nên không đọc được; nay hiển thị đủ 2–3 dòng tiêu đề.)
2. Ô tìm kiếm (tiêu đề / EID / DOI / nguồn) có độ trễ ~0,5 giây; bộ lọc **Năm / Loại tài liệu / Giai đoạn / Truy cập mở** + **Áp dụng** / **Đặt lại**. Ví dụ: gõ `UML` → các bài về UML; lọc Năm `2020` → toàn bộ dòng là năm 2020. 20 dòng/trang.
3. **Chi tiết** → trang bài: thông tin (EID, DOI, năm, volume, issue, số bài, trích dẫn, loại tài liệu, giai đoạn, truy cập mở), **Danh sách tác giả (Scopus)**, **Liên kết giảng viên ICTU** (chỉ hiện giảng viên đã được APPROVED), **Nguồn dữ liệu & truy vết** (tên tệp CSV, số dòng, SHA-256).
4. Địa chỉ không tồn tại (ví dụ `/publications/2-s2.0-000000000`) → "Không tìm thấy công bố này." + nút quay lại.
- **Nút Xuất JSON** (đầu trang Công bố): xuất toàn bộ công bố (~760 KB) **và ghi một dòng nhật ký** → *không bấm trên teacher DB*.
- **Đã kiểm thử:** `BROWSER_PASS` (danh sách, tìm, lọc, chi tiết, không tìm thấy); `API_PASS` (xuất JSON).

### Ba công bố thật để làm ví dụ (đã kiểm chứng trực tiếp bằng dữ liệu hiện tại)

| # | EID | Dùng để minh họa | Kiểm chứng |
|---|---|---|---|
| 1 | `2-s2.0-105027527591` | **Nhiều tác giả, dễ hiểu** — "MUFO: Multi-UAV flight optimization…" (2026) | 3 tác giả, 4 mục đơn vị |
| 2 | `2-s2.0-105013367684` | **Đủ thông tin đơn vị cho cả 5 tác giả** — "Quantum AMDS Negacyclic Codes of Length 2ps Over Fpm" (2026) | 5 tác giả, 9 mục đơn vị; có 1 VERIFIED; có tác giả ICTU |
| 3 | `2-s2.0-105035336993` | **Chưa xác định / thiếu đơn vị** — "A Hybrid LSTM-CNN Model for Automated Pavement Defect Detection…" (2026) | 3 tác giả, cả 3 UNRESOLVED (`NO_EXTERNAL_WORK`) |

Ví dụ bổ sung: `2-s2.0-105006527625` ("A Road-Adaptive Vibration Reduction System…", 5 tác giả → 8 mục đơn vị + 1 chưa xác định) và `2-s2.0-105036729228` (4 tác giả, **nguồn không cung cấp đơn vị**). Chi tiết từng hàng tác giả ở 4.9.

## 4.6. Tác giả Scopus (tab "Tác giả" của Chuẩn hóa dữ liệu) — **[CHỈ XEM]**
**Chuẩn hóa dữ liệu → Tác giả**: bảng *Tác giả Scopus* (tên tác giả, Scopus ID, số công bố, biến thể tên) có ô tìm theo tên hoặc Scopus ID, phân trang 10 dòng. Thẻ tóm tắt: *Chờ xử lý, Đã xử lý, Có lỗi dữ liệu, Tác giả Scopus*. (`BROWSER_PASS` hiển thị; API `/authors`, `/authors/stats`, `/authors/{id}` `API_PASS`.)

## 4.7. Tra cứu tổng hợp (`/search`) — **[CHỈ XEM]**
Gõ từ khóa ≥ 2 ký tự: hệ thống trả tối đa 5 giảng viên, 5 công bố, 5 tác giả Scopus. Ví dụ: `UML` → 5 công bố; `60319803200` → 1 tác giả; `10.1007/978-981-92-2587-3_9` (DOI) → 1 công bố; `Nguyễn` → 5 giảng viên; `a` → lỗi "Từ khóa tìm kiếm phải có ít nhất 2 ký tự."
Tìm **không phân biệt dấu** (Task 17): `Luong`, `luong`, `Lương`, `LƯƠNG` cho cùng kết quả (`BROWSER_PASS` + `API_PASS`). Mã số (EID, DOI, Scopus ID) vẫn so khớp theo đúng chuỗi gõ.

## 4.8. Hồ sơ cá nhân của giảng viên (vai trò LECTURER) — **[CHỈ XEM]**
Đăng nhập bằng tài khoản giảng viên: **Hồ sơ cá nhân** (thông tin cơ bản, học thuật, bộ môn/khoa, ORCID), **Công bố của tôi** (chỉ hiện khi đã có định danh APPROVED; hiển thị thẻ *Tổng số công bố, Tổng lượt trích dẫn, Công bố chưa có dữ liệu trích dẫn, Định danh Scopus đã duyệt*, danh sách và phân bố theo năm), **Liên kết Scopus** (danh sách định danh đã duyệt hoặc "Chưa có định danh Scopus").
Đã thử trên test DB: sau khi ADMIN ACCEPT ứng viên *ThS. Lương Thị Minh Huế ↔ 60319803200* và cấp tài khoản cho giảng viên này, đăng nhập thì **Công bố của tôi hiện 19 công bố** (17 bài năm 2026, 2 bài năm 2025). (`BROWSER_PASS`.)

## 4.9. Đơn vị công tác theo từng tác giả (Affiliation) — **PHẦN QUAN TRỌNG NHẤT**

### Cách xem trên giao diện `[CHỈ XEM]`
**Công bố → Chi tiết một bài → cuộn tới "Danh sách tác giả (Scopus)"**.
- Dòng tóm tắt "**Affiliation theo N tác giả**" đếm: VERIFIED có đơn vị · VERIFIED nguồn không có đơn vị · CORROBORATED có đơn vị · CORROBORATED nguồn không có đơn vị · UNRESOLVED chưa xác định.
- Dòng ghi chú: *"Đơn vị lấy từ nguồn metadata ngoài (OpenAlex/Crossref), không phải xác nhận trực tiếp của Scopus. CORROBORATED chỉ là đối chiếu theo số tác giả + vị trí + tên, chưa được xác minh."*
- Bảng: **STT · Tên ưu tiên · Scopus ID · Đơn vị theo tác giả (nguồn ngoài) & độ tin cậy**. Mỗi tác giả có các thẻ: nhãn trạng thái, nguồn (Crossref / OpenAlex), **nguyên văn đơn vị trên bài (raw)**, **Tổ chức (do nguồn chuẩn hóa)** kèm mã quốc gia, và dòng "Crossref: … · OpenAlex: …".

### Giải thích ba trạng thái (đúng theo mã nguồn `author_affiliation.py`)
- **VERIFIED — có bằng chứng danh tính mạnh.** Loại bằng chứng đang dùng: **cầu nối ORCID ↔ Scopus Author ID** (`ORCID_SCOPUS_ID_BRIDGE`): tác giả bên OpenAlex/Crossref có ORCID, và hồ sơ ORCID công khai đó *tự khai* đúng Scopus Author ID của vị trí này. **Mã định danh là bằng chứng; tên và vị trí không được dùng.** Không có nghĩa "Scopus xác nhận đơn vị".
- **CORROBORATED — được củng cố, chưa phải xác minh.** Không có định danh chung, nhưng: hai danh sách tác giả **cùng độ dài**, tác giả ngoài đứng **đúng vị trí đó**, **tên trùng** (các token tên bằng nhau) và không có mâu thuẫn (`POSITION_COUNT_NAME`). Hệ thống **không tự nâng** CORROBORATED thành VERIFIED.
- **UNRESOLVED — chưa đủ căn cứ.** Không gán đơn vị, không đoán. Có lý do cụ thể, dịch trên giao diện: `NO_EXTERNAL_WORK` (nguồn ngoài không có bài này), `NO_EXTERNAL_AUTHOR_LIST`, `AUTHOR_COUNT_MISMATCH` (khác số tác giả), `NAME_MISMATCH` ("Tên tác giả không khớp"), `ORDER_INCONSISTENT_WITH_VERIFIED_ID`, `POSITION_CLAIMED_BY_OTHER_ID`, `ID_CONFLICT`, `WITHHELD_SOURCE_CONFLICT` (nguồn mâu thuẫn bị giữ lại).
- **"Nguồn không cung cấp đơn vị"** (`affiliation_presence = ABSENT`): người đó đã được nối đúng (VERIFIED/CORROBORATED) nhưng nguồn **không có** chuỗi đơn vị; hệ thống để trống, **không lấy đơn vị của bài hay của người khác để điền**.

### Ví dụ thật 1 — Dễ hiểu, nhiều tác giả: `2-s2.0-105027527591`
*MUFO: Multi-UAV flight optimization for enhancing connectivity in remote driving services* — DOI 10.1016/j.adhoc.2025.104129.

| STT | Tác giả [Scopus ID] | Trạng thái | Đơn vị trên bài (OpenAlex) | Tổ chức chuẩn hóa |
|---|---|---|---|---|
| 1 | Nguyen, Van-Linh [57194062575] | **VERIFIED** (ORCID–Scopus ID) | College of Artificial Intelligence, National Yang Ming Chiao Tung University, Tainan, Taiwan **và** Department of Computer Science and Information Engineering, National Chung Cheng University, Chiayi, Taiwan | National Yang Ming Chiao Tung University (TW); National Chung Cheng University (TW) |
| 2 | Nguyen, Lan-Huong [57415807400] | **CORROBORATED** | College of Artificial Intelligence, National Yang Ming Chiao Tung University, Tainan, Taiwan | National Yang Ming Chiao Tung University (TW) |
| 3 | Hwang, Ren-Hung [7103381899] | **VERIFIED** | College of Artificial Intelligence, National Yang Ming Chiao Tung University, Tainan, Taiwan | National Yang Ming Chiao Tung University (TW) |

→ **3 tác giả nhưng 4 mục đơn vị**, vì tác giả #1 thuộc **hai** đơn vị. Crossref có đối chiếu nhưng *không có chuỗi đơn vị* (ABSENT) nên chỉ OpenAlex đóng góp đơn vị.

### Ví dụ thật 2 — Đủ thông tin đơn vị cả 5 tác giả, nhiều nguồn: `2-s2.0-105013367684`
*Quantum AMDS Negacyclic Codes of Length 2ps Over Fpm* — 5 tác giả, **9 mục đơn vị**.

| STT | Tác giả [Scopus ID] | Trạng thái | Đơn vị trên bài |
|---|---|---|---|
| 1 | Dinh, Hai Q. [7003410519] | CORROBORATED (Crossref); OpenAlex: UNRESOLVED – tên không khớp | Faculty of Data Science in Business, Ho Chi Minh University of Banking, Ho Chi Minh City, Vietnam |
| 2 | Nguyen, Bac T. [57196261528] | CORROBORATED (Crossref) | Institute of Fundamental and Applied Sciences, Duy Tan University, Ho Chi Minh City, Vietnam |
| 3 | **Nguyen, Van-Nui [57188562370]** | CORROBORATED (Crossref) | **Thai Nguyen University of Information and Communication Technology, Thai Nguyen, Vietnam** (tác giả ICTU) |
| 4 | Thi, Hiep L. [57959371300] | CORROBORATED (Crossref + OpenAlex) | Faculty of Education, Thu Dau Mot University — **3 mục**: 1 từ Crossref, 2 từ OpenAlex (hai chuỗi chỉ khác "Ho Chi Minh City"/"Binh Duong") |
| 5 | Yamaka, Woraphon [57015628300] | **VERIFIED** (OpenAlex, cầu ORCID); Crossref: CORROBORATED | Centre of Excellence in Econometrics, Chiang Mai University, Thailand — **3 mục** (2 OpenAlex + 1 Crossref) → Chiang Mai University (TH) |

→ **5 tác giả, 9 mục đơn vị**: vì 2 nguồn (Crossref, OpenAlex) cùng báo cho một số tác giả và một chuỗi đơn vị có thể xuất hiện nhiều biến thể.

### Ví dụ thật 3 — Chưa xác định: `2-s2.0-105035336993`
*A Hybrid LSTM-CNN Model for Automated Pavement Defect Detection and Classification* (không có DOI): 3 tác giả — Huong, Nguyen T. [58771687200]; Long, Nguyen T. [59708287500]; Kien, Pham V. [60565894600] — **cả 3 UNRESOLVED**, lý do `NO_EXTERNAL_WORK` (OpenAlex và Crossref đều không có bài). **Hệ thống không đoán đơn vị.**

### Ví dụ thật 4 — "5 tác giả vẫn có 8 liên kết": `2-s2.0-105006527625`
*A Road-Adaptive Vibration Reduction System with Fuzzy PI Control Approach for Electric Bicycles*, DOI 10.3390/wevj16050276, 2025.

| STT | Tác giả [Scopus ID] | Trạng thái | Đơn vị (Crossref **và** OpenAlex cùng báo) |
|---|---|---|---|
| 1 | Meng, Chao-Li [55932686700] | CORROBORATED | Department of Information Engineering and Computer Science, Feng Chia University, Taichung 40724, Taiwan → Feng Chia University (TW) |
| 2 | Bui, Van-Tung [57201704313] | CORROBORATED | Faculty of Engineering and Technology, Thai Nguyen University of Information and Communication Technology, Thai Nguyen 250000, Vietnam → Thai Nguyen University of ICT (VN) |
| 3 | Dow, Chyi-Ren [35611060200] | CORROBORATED | (như #1) Feng Chia University (TW) |
| 4 | Chang, Shun-Ming [57206903090] | CORROBORATED | (như #1) Feng Chia University (TW) |
| 5 | Lu, Yueh-E [59916144400] | **UNRESOLVED** | — "Tên tác giả không khớp" ở cả hai nguồn |

→ 4 tác giả × 2 nguồn = **8 mục**, + 1 người chưa xác định = 5 tác giả. **Không** lấy đơn vị của tác giả khác gán cho người #5.

### Ví dụ thật 5 — Nối đúng nhưng nguồn thiếu đơn vị: `2-s2.0-105036729228`
*Enhancing Student Mental Health in Vietnam via a Predictive Emotion Chatbot* — 4 tác giả: #1 Doan, Ngoc-Phuong [60598627700] **VERIFIED**; #2 Nguyen, Phuong-Nam [60598087800] CORROBORATED; #3 Nguyen, Vinh T. [57210589113] **VERIFIED**; #4 Nguyen, Lan-Oanh [60597824000] CORROBORATED — **nhưng cả 4 đều "nguồn không có đơn vị"** (không có chuỗi đơn vị nào để hiển thị).
Đây là ví dụ cho câu hỏi: *"Biết Scopus Author ID / nối đúng người có nghĩa là có đơn vị không?"* — **Không.**

### Các con số tổng hợp (teacher DB) — đừng nhầm mức đếm
| Mức đếm | Giá trị | Giải thích |
|---|---|---|
| Vị trí tác giả (`publication_authors`) | **2.751** | Mỗi tác giả trong mỗi bài |
| Bản ghi đối chiếu (`..._affiliation_resolutions`) | **5.502** = 2.751 × 2 | Mỗi vị trí được đối chiếu với **2 nguồn**: Crossref và OpenAlex |
| Vị trí xét theo mức tốt nhất (cách đếm của `affiliation_summary`, cũng là số hiển thị ở dòng tóm tắt trên trang bài) | **545 VERIFIED** (**506** có đơn vị + **39** nguồn không có đơn vị) · **2.053 CORROBORATED** (1.774 có đơn vị + 279 không) · **153 UNRESOLVED** | Tổng 2.751; "có đơn vị" nghĩa là *bản đối chiếu cùng mức tốt nhất đó* có chuỗi đơn vị |
| Dòng liên kết đơn vị (`publication_author_affiliations`) | **4.147** = 883 VERIFIED + 3.264 CORROBORATED | Mỗi dòng = một chuỗi đơn vị (hoặc một tổ chức do nguồn chuẩn hóa) của một bản ghi đối chiếu |
| Thẻ đơn vị hiển thị trên giao diện | **3.451** | Giao diện **gộp** các tổ chức cùng một chuỗi gốc thành một thẻ |
| Tổ chức duy nhất | **217** | Trong đó 3.415 dòng liên kết có tổ chức chuẩn hóa, 732 dòng chỉ có chuỗi gốc |
| Vị trí có ít nhất một đơn vị | **2.291** | |

> **Vì sao có tài liệu ghi 517/28 thay vì 506/39?** Có 2 cách đếm hợp lệ nhưng khác tiêu chí. **Cách A (chuẩn của đồ án):** vị trí VERIFIED "có đơn vị" khi chính bản đối chiếu VERIFIED có chuỗi đơn vị → **506 / 39**. **Cách B:** vị trí "có đơn vị" khi *bất kỳ* bản đối chiếu đáng tin (cả CORROBORATED) có đơn vị → 517 / 28. Chênh **11 vị trí** là những tác giả được Crossref **VERIFIED** nhưng Crossref không có đơn vị, trong khi OpenAlex chỉ **CORROBORATED** và có đơn vị (ví dụ EID `2-s2.0-105027134268` #4 và #5). Ở các vị trí này giao diện vẫn hiện đơn vị của OpenAlex **kèm nhãn CORROBORATED**, và hệ thống **không nâng** nó thành VERIFIED. Toàn bộ tài liệu dùng **Cách A (506/39)**.

> **4.147 là số dòng liên kết, không phải số tác giả, không phải số vị trí.** Số liên kết lớn hơn số tác giả vì (a) 2 nguồn, (b) một tác giả có nhiều đơn vị, (c) một chuỗi đơn vị được nguồn tách thành nhiều tổ chức.

### Đơn vị trên bài báo ≠ đơn vị hiện tại của giảng viên
Affiliation trên bài là **đơn vị người đó khai tại thời điểm công bố** (có thể là trường cũ, hợp tác, hoặc viết tắt khác nhau). "Đơn vị hiện tại của giảng viên ICTU" là dữ liệu hồ sơ ICTU (khoa/bộ môn). Hai thứ **độc lập**, không suy từ nhau. Mã đơn vị chung của cả bài **không** được copy cho từng đồng tác giả.

- **Đã kiểm thử:** `BROWSER_PASS` (xem trang chi tiết bài trên test DB giống hệt teacher: bản ghi tác giả, thẻ, ghi chú, UNRESOLVED); `API_PASS` (đọc trực tiếp bằng API trên teacher DB cho các EID trên, và quét toàn bộ 660 bài: tổng mục đơn vị, trạng thái từng tác giả).

## 4.10. Hàng đợi đối sánh (Matching) — **[CHỈ XEM]**

### Matching Engine làm gì?
Một **script dòng lệnh** (`generate_matching_candidates.py`, **không** có nút trên giao diện, **không** chạy trong web) đọc 410 giảng viên và 1.207 tác giả Scopus rồi **sinh ứng viên (candidate)** — mỗi ứng viên là *một đề xuất* "giảng viên A có thể là Scopus Author ID Y". Cách sinh **xác định (deterministic)**: so tên sau khi bỏ tiền tố chức danh (`DH.`, `GS.TS.`, `PGS.TS.`, `ThS.`, `TS.`), chuẩn hóa chữ thường/bỏ dấu, tương đương dấu phẩy (4 quy tắc `RULE_EXACT_N0`, `RULE_TITLE_STRIPPED_N0`, `RULE_TITLE_STRIPPED_N2`, `RULE_TITLE_STRIPPED_N2_FORMAT`). Sau đó bổ sung **bằng chứng công bố**: so DOI/tiêu đề trong *công bố đã biết của giảng viên* (nguồn Craw ICTU) với công bố Scopus của tác giả đó (`DOI_EXACT`, `TITLE_EXACT`). **Không chấm điểm, không xếp hạng, không tự duyệt.**

### Trên giao diện
1. **Duyệt đối sánh**. Bộ lọc: **Trạng thái** (mặc định *Chờ duyệt*), **Loại bằng chứng**, **Mức độ mơ hồ**; **Làm mới**; "Tổng số: 40". 20 dòng/trang.
2. Mỗi dòng: *Giảng viên ICTU · Tác giả Scopus (tên + ID) · Trạng thái · Bằng chứng · Ngữ cảnh mơ hồ · Thao tác*.
   - Bằng chứng: **"Chỉ bằng chứng tên"** (34 ứng viên) hoặc **"Có công bố hỗ trợ — N công bố"** (6 ứng viên).
   - Ngữ cảnh mơ hồ: "Không có ứng viên khác" · "Còn 1 ứng viên khác" (giảng viên đó có >1 ứng viên) · cảnh báo đỏ **"Tác giả Scopus dùng chung (5 giảng viên)"**.
3. **Xem chi tiết** → cửa sổ **Chi tiết ứng viên đối sánh** gồm năm phần: **A. Giảng viên ICTU** · **B. Tác giả Scopus** (tên ưu tiên, Scopus ID, biến thể tên) · **C. Bằng chứng tên** (quy tắc, tên hai phía, giá trị so sánh) · **D. Bằng chứng công bố** (danh sách bài khớp theo DOI/tiêu đề, kèm EID) · **E. Ngữ cảnh mơ hồ**; cuối cửa sổ: **Trạng thái hiện tại**, **Từ chối**, **Xác nhận đối sánh**.

### Số liệu thật (teacher DB, đã đọc bằng API chỉ-đọc)
- **40** ứng viên PENDING cho **38** giảng viên và **36** Scopus ID (có giảng viên có 2 ứng viên; có ID được 5 giảng viên chia sẻ).
- **6 ứng viên có bằng chứng công bố:**

| Giảng viên | Tác giả Scopus (ID) | Công bố hỗ trợ |
|---|---|---|
| ThS. Lương Thị Minh Huế | Luong, Thi Minh-Hue (60319803200) | 16 |
| TS. Lê Văn Chung | Van Chung, Le (57222490164) | 1 |
| TS. Vũ Đức Quang | Vu, Duc-Quang (57193082389) | 17 |
| PGS.TS. Phùng Trung Nghĩa | Phung, Trung-Nghia (55605197600) | 28 |
| TS. Nguyễn Văn Tảo | Nguyen, Van Tao (56967513900) | 4 |
| TS. Nguyễn Đức Bình | Nguyen, Duc-Binh (57075583000) | 3 |

- **5 ứng viên "dùng chung"** cùng một Scopus Author ID `59253245500` (Nguyen Thi, Dung): 4 hồ sơ "ThS. Nguyễn Thị Dung" + 1 "PGS.TS. Nguyễn Thị Dung". Chỉ có bằng chứng tên ⇒ không thể biết ai là ai.
- **0** danh tính APPROVED, **0** quyết định review.

### Câu hỏi nền
- *Vì sao hệ thống không tự ACCEPT?* Tên giống chưa đủ để kết luận người; liên kết sai làm sai công bố của người khác. Quyết định phải do con người, có lý do và dấu vết.
- *Vì sao một Scopus Author ID xuất hiện ở nhiều ứng viên là cảnh báo?* Một ID chỉ nên thuộc **một** người ICTU. Nếu nhiều giảng viên cùng được đề xuất cùng ID thì ít nhất N−1 đề xuất sai; hệ thống **chặn ACCEPT lần hai** cho cùng ID.
- *Giảng viên không có ứng viên nghĩa là không có công bố?* **Không.** Có thể tên trong Scopus quá khác (viết tắt, đảo tên) nên không qua quy tắc, hoặc người đó chưa có trong tệp CSV 660 bài.
- **Đã kiểm thử:** `BROWSER_PASS` (trên test DB giống hệt teacher: hàng đợi, chi tiết, các phần A–E, cảnh báo dùng chung); `API_PASS` (teacher DB, chỉ-đọc: tổng 40, 6, 5). **Không** chạy lại generator trên teacher.

## 4.11. Duyệt ACCEPT / REJECT — **[QUẢN TRỊ QUAN TRỌNG — chỉ test DB]**

### ADMIN dựa trên bằng chứng nào?
1. **Bằng chứng công bố (D)** mạnh hơn bằng chứng tên: nếu các bài mà tác giả Scopus đã viết *trùng DOI/tiêu đề* với danh sách công bố đã biết của chính giảng viên ICTU ⇒ rất đáng tin.
2. **Bằng chứng tên (C)** yếu: chỉ cho biết tên khớp.
3. **Ngữ cảnh mơ hồ (E)**: có ứng viên khác? ID có bị chia sẻ không?
### Khi nào ACCEPT / REJECT / giữ PENDING
- **ACCEPT**: có bằng chứng công bố rõ, không mơ hồ, không dùng chung.
- **REJECT**: có căn cứ cho thấy *không phải* cùng người (khác lĩnh vực/đơn vị, trùng tên người khác…). **Bắt buộc nhập lý do** (nút "Xác nhận REJECT" bị khóa khi để trống).
- **Giữ PENDING**: chưa đủ căn cứ — **không làm gì** là lựa chọn hợp lệ và an toàn.

### Các bước (đã thử trên test DB)
1. **Duyệt đối sánh** → **Xem chi tiết** → xem kỹ A–E.
2. **Xác nhận đối sánh** → hộp "Xác nhận quyết định ACCEPT" (nhắc kiểm tra đúng cặp) → **Xác nhận ACCEPT**. Hoặc **Từ chối** → nhập lý do → **Xác nhận REJECT**.
3. Kết quả ACCEPT: trạng thái ứng viên → `ACCEPTED`; tạo **1 danh định** `APPROVED` (kèm các dòng bằng chứng); ghi **2 sự kiện nhật ký** (`CANDIDATE_ACCEPTED`, `IDENTITY_CREATED_FROM_CANDIDATE`); xuất hiện ở **Lịch sử review**; thẻ Tổng quan *ĐÃ DUYỆT* tăng. Kết quả REJECT: `REJECTED`, 1 dòng lịch sử có lý do, **không** tạo danh định.
### Ghi vào những bảng nào?
`lecturer_scopus_candidate_reviews` (quyết định, lý do), `lecturer_scopus_candidates` (đổi trạng thái + version), `lecturer_scopus_identities` + `identity_evidence` (khi ACCEPT), `audit_events` (nhật ký). Bảng review là **append-only**.
### Lỗi / xung đột (HTTP 409 nghĩa là gì?)
**409 Conflict** = *yêu cầu hợp lệ nhưng xung đột với trạng thái hiện tại của dữ liệu*; không có gì bị ghi. Đã thử:

| Tình huống | Mã | Thông báo giao diện |
|---|---|---|
| ACCEPT ứng viên khác cùng Scopus ID đã được xác nhận cho giảng viên khác | 409 `SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER` | Toast "Không thể lưu quyết định — Tác giả Scopus này đã được xác nhận cho một giảng viên khác. Không thể tự động thử lại quyết định." (`BROWSER_PASS`) |
| Quyết định trên bản ghi đã cũ (version) | 409 `STALE_CANDIDATE_VERSION` (`API_PASS`) | Tải lại hàng đợi |
| ACCEPT ứng viên đã bị REJECT | 409 `CANDIDATE_ALREADY_DECIDED_CONFLICT` (`API_PASS`) | — |
| ACCEPT lại ứng viên đã ACCEPT cùng version | 200, `idempotent: true` — không ghi trùng (`API_PASS`) | — |
| REJECT không có lý do | 422 `INVALID_REVIEW_REASON` | Nút bị khóa trên giao diện |
| Tài khoản LECTURER gọi duyệt | 403 `FORBIDDEN` | Không thấy menu |
- Vì sao **Audit Trail** quan trọng: biết *ai*, *khi nào*, *quyết định gì*, *lý do*; không sửa/xóa được (append-only, ADR-003).
- **Không ACCEPT/REJECT trên teacher DB.**

## 4.11b. Dùng tài khoản Phê duyệt viên (REVIEWER) — **[CÓ GHI DỮ LIỆU khi ACCEPT/REJECT — chỉ test DB]**

> Trạng thái: **`BROWSER_PASS` trên DB test** (Task 17). **Teacher DB hiện chưa có tài khoản REVIEWER** (chỉ 2 ADMIN + 1 LECTURER). Khi demo cho thầy, chỉ giới thiệu vai trò này bằng lời/ảnh chụp từ DB test; không tạo tài khoản trên teacher khi chưa được người dùng duyệt.

**Cấp tài khoản (ADMIN làm).** Cách 1: **Giảng viên → Thêm giảng viên**, chọn **Vai trò = Phê duyệt viên** rồi **Tạo giảng viên** (tạo cả hồ sơ và tài khoản; ghi `LECTURER_CREATED`, không ghi mật khẩu). Cách 2: mở **Chi tiết** của giảng viên đã có tài khoản và đổi ô **Vai trò** sang *Phê duyệt viên (REVIEWER)* → **Lưu thay đổi** (người được đổi nhận thông báo "Quyền tài khoản đã thay đổi"). Mật khẩu đủ ≥ 8 ký tự; **không ghi mật khẩu vào Git/tài liệu**. Tài khoản ADMIN **không** thể tự đổi vai trò của mình.

**Đăng nhập.** Dùng màn hình đăng nhập thông thường. Lời chào hiện "Xin chào, <tên>"; `GET /auth/me` trả `role = REVIEWER`. Trang chủ có ba thẻ: *Đối sánh cần xử lý*, *Công bố khoa học*, *Lịch sử review*.

**Menu thấy được:** Trang chủ · Công bố · Duyệt đối sánh · Lịch sử review (và Tra cứu qua ô tìm). Gõ địa chỉ `/dashboard`, `/imports`, `/normalization`, `/lecturers`, `/users`, `/audit-logs`, `/tasks`, `/profile`, `/my-publications` → tự chuyển về `/home` (9/9 đã thử).

**Quyền được phép** (đều đã thử): xem danh sách và chi tiết công bố, tác giả, đơn vị theo tác giả; xem hàng đợi ứng viên, chi tiết (A–E), bằng chứng tên và công bố, cảnh báo dùng chung; xem Lịch sử review; tra cứu; **ACCEPT / REJECT** (REJECT bắt buộc lý do).

**Quyền bị cấm** (API trả **403**, đã thử 31 thao tác): quản lý giảng viên (xem/thêm/sửa/xóa/xuất), quản lý tài khoản (xem/sửa/khóa/mở khóa/đặt lại mật khẩu), nhập và chuẩn hóa dữ liệu, Tổng quan, Nhật ký hệ thống, danh sách tác giả quản trị, Xuất JSON công bố, các API `/lecturers/me/*` của giảng viên.

**Xem bằng chứng và quyết định.** Giống ADMIN (mục 4.10–4.11): **Duyệt đối sánh → Xem chi tiết → A–E → Xác nhận đối sánh / Từ chối**. Kết quả đã kiểm: trạng thái ứng viên đổi, tạo danh định `APPROVED` + bằng chứng (khi ACCEPT), **người duyệt được ghi đúng là tài khoản REVIEWER** (cột `reviewer_user_id`; nhật ký hiển thị tên người duyệt, không phải ADMIN/SYSTEM), Lịch sử review có dòng mới với cột **Người duyệt**; giảng viên được ACCEPT đăng nhập thấy **19 công bố**.

**Xử lý 409 (xung đột).** Toast "Không thể lưu quyết định — Tác giả Scopus này đã được xác nhận cho một giảng viên khác…" và khung vàng "Dữ liệu có xung đột": tải lại hàng đợi, xem mục E, chọn quyết định khác. Các mã khác: `STALE_CANDIDATE_VERSION` (tải lại), `CANDIDATE_ALREADY_DECIDED_CONFLICT` (đã có người quyết định). Gửi lại ACCEPT đã duyệt cùng phiên bản → idempotent, không ghi trùng.

## 4.12. Lịch sử review và Nhật ký hệ thống — **[CHỈ XEM]**
- **Lịch sử review:** bảng *Thời gian · Hành động (ACCEPT/REJECT) · Chuyển trạng thái (PENDING → ACCEPTED) · Giảng viên · Tác giả Scopus · Người duyệt · Lý do*; bộ lọc Hành động, Từ ngày, Đến ngày; nút **Áp dụng / Xóa bộ lọc / Làm mới**. (`BROWSER_PASS` — hiển thị 3 quyết định thử nghiệm trên test DB.)
- **Nhật ký hệ thống (Nhật ký kiểm toán):** chỉ đọc, "ghi nhận tự động và không thể sửa đổi". Bộ lọc: *Hành động, Loại thực thể, Loại tác nhân (Người dùng/Hệ thống), Từ ngày, Đến ngày*. Các hành động thật đã gặp: `SCOPUS_IMPORT_STARTED/COMPLETED`, `SCOPUS_NORMALIZATION_TRIGGERED`, `LECTURER_DATASET_IMPORTED/EXPORTED/ROLLED_BACK`, `LECTURER_CREATED/UPDATED/DELETED`, `USER_LOCKED/UNLOCKED/PASSWORD_RESET`, `CANDIDATE_ACCEPTED/REJECTED`, `IDENTITY_CREATED_FROM_CANDIDATE`, `SCOPUS_IMPORT_DELETED`, `DEMO_ADMIN_BOOTSTRAPPED`. (`BROWSER_PASS`.)
- Xem nhật ký trên teacher DB là an toàn; nhưng **mỗi lần Xuất JSON sẽ thêm một dòng mới**.

## 4.13. Thông báo — chỉ có cơ chế nền
Không có trang "Thông báo". Khi ADMIN khóa/mở khóa/đặt lại mật khẩu của một người, hệ thống lưu thông báo; lần tải trang tiếp theo của người đó nó được lấy về, hiển thị rồi đánh dấu đã đọc (`API_PASS`).

## 4.14. Tác vụ — `NOT_IMPLEMENTED`
Menu **Tác vụ** dẫn tới trang "Tác vụ hệ thống — Tính năng đang trong quá trình hoàn thiện". Chỉ giới thiệu là *dự kiến phát triển*.

## 4.15. Chức năng chỉ có ở API (Swagger tại `http://127.0.0.1:8001/docs`)
Không có nút giao diện, **không thao tác Swagger với dữ liệu teacher**: `GET /lecturers/me/*`, `GET /lecturers/{id}/scopus/{identities|profile|publications}` (`API_PASS`), `GET /auth/users` (bí danh cũ), `PUT/PATCH /lecturers/{id}`, `POST /imports/{id}/cancel`.
**Lưu ý:** `DELETE /lecturers/unlinked/cleanup` đã bị **gỡ chức năng** (từ Task 16 trả HTTP **410** `LECTURER_BULK_CLEANUP_RETIRED`, không xóa gì; trước đó trả 500 do thiếu hàm). Hồ sơ giảng viên là dữ liệu gốc; chỉ xóa bản ghi thử nghiệm bằng script `clean_orphan_lecturers --lecturer-id`.

---

## 4.16. Ma trận quyền ADMIN / REVIEWER / LECTURER (đã kiểm chứng)

| Chức năng | ADMIN | REVIEWER | LECTURER |
|---|---|---|---|
| Đăng nhập, đăng xuất, đổi phiên | ✔ | ✔ | ✔ |
| Trang chủ | ✔ | ✔ | ✔ |
| Tổng quan (Dashboard) | ✔ | ✖ 403 | ✖ 403 |
| Nhập dữ liệu (CSV Scopus / JSON giảng viên), Chuẩn hóa, Bóc tách tác giả | ✔ | ✖ 403 | ✖ 403 |
| Quản lý giảng viên (xem, thêm, sửa, xóa, Xuất JSON) | ✔ | ✖ 403 | ✖ 403 |
| Quản lý tài khoản (cấp, đổi vai trò, khóa, mở khóa, đặt lại mật khẩu) | ✔ (không tự đổi vai trò, không hạ ADMIN cuối) | ✖ 403 | ✖ 403 |
| Công bố: danh sách, chi tiết, tác giả, đơn vị theo tác giả | ✔ | ✔ | ✖ 403 |
| Xuất JSON công bố | ✔ | ✖ 403 | ✖ 403 |
| Tra cứu tổng hợp | ✔ | ✔ | ✖ 403 |
| Hàng đợi đối sánh + chi tiết + bằng chứng | ✔ | ✔ | ✖ 403 |
| ACCEPT / REJECT | ✔ | ✔ | ✖ 403 |
| Lịch sử review | ✔ | ✔ | ✖ 403 |
| Nhật ký hệ thống | ✔ | ✖ 403 | ✖ 403 |
| Hồ sơ cá nhân, Công bố của tôi, Liên kết Scopus | ✖ (route chuyển về `/home`) | ✖ (về `/home`; API `/lecturers/me/*` 403) | ✔ (chỉ của chính mình) |
| API xem hồ sơ Scopus của giảng viên khác (`/lecturers/{id}/scopus/*`) | ✔ | ✖ 403 | ✖ 403 |

Chưa đăng nhập: mọi API (trừ đăng nhập, `/health`) trả **401**. Kết quả này lấy từ 31 lệnh gọi API của REVIEWER, 8 của LECTURER và các lần mở route bằng trình duyệt (xem `BAO_CAO_KIEM_THU_CHUC_NANG.md`, chương 18).

---

# Chương 5 — Luồng xử lý dữ liệu

```
Giảng viên ICTU ──► JSON hồ sơ ──► [Nhập dữ liệu → Thêm giảng viên] ──► bảng lecturers (+ lecturer_source_snapshots)
                                                              │
                                  quản lý hồ sơ / tài khoản ◄─┘  (Giảng viên → Chi tiết)

Scopus CSV ──► [Nhập dữ liệu → Thêm tệp Scopus] ──► scopus_imports + raw_scopus_records   (DỮ LIỆU THÔ)
          ──► [Chuẩn hóa → Công bố] ──► publications (+ publication_raw_sources)
          ──► [Chuẩn hóa → Tác giả]  ──► scopus_authors, scopus_author_name_variants, publication_authors

Craw ICTU (công bố đã biết)  ──► script ──► lecturer_known_publications          ┐ BẰNG CHỨNG
OpenAlex / Crossref / ORCID  ──► script ──► organizations, ...affiliation_resolutions,  │ (không có nút UI)
                                           publication_author_affiliations      ┘

Matching Engine (script) ──► candidate_generation_runs, lecturer_scopus_candidates (PENDING) + observations + evidence

ADMIN ──► [Duyệt đối sánh] ──► kiểm tra bằng chứng ──► ACCEPT / REJECT / giữ PENDING
                      └──► lecturer_scopus_candidate_reviews, lecturer_scopus_identities (+identity_evidence), audit_events

Review History + Audit ◄── truy vết mọi quyết định
```

| Bước | Đầu vào | Đầu ra | Dữ liệu thay đổi |
|---|---|---|---|
| Nhập hồ sơ giảng viên | JSON | Hồ sơ giảng viên | `lecturers`, `lecturer_source_snapshots`, `audit_events` |
| Nhập CSV Scopus | CSV | Bản ghi thô | `scopus_imports`, `raw_scopus_records` |
| Chuẩn hóa công bố | Bản ghi thô | Công bố chuẩn | `publications`, `publication_raw_sources` |
| Bóc tách tác giả | Công bố chuẩn | Tác giả, vị trí | `scopus_authors`, `scopus_author_name_variants`, `publication_authors` |
| Nạp bằng chứng ngoài (script) | JSON/JSONL ngoài Git | Công bố đã biết; đơn vị theo tác giả | `lecturer_known_publications`; `organizations`, `publication_author_affiliation_*` |
| Sinh ứng viên (script) | Hồ sơ + tác giả + bằng chứng | Ứng viên PENDING | `candidate_generation_runs`, `lecturer_scopus_candidates`, `..._observations`, `..._evidence` |
| ADMIN duyệt | Ứng viên | Quyết định + danh tính | `..._candidate_reviews`, `lecturer_scopus_identities`, `identity_evidence`, `audit_events` |

---

# Chương 6 — Giải thích các con số và thuật ngữ

1. **Vì sao 410 ICTU + 1 seed = 411 hồ sơ?** 410 hồ sơ từ JSON ICTU + 1 hồ sơ "Người dùng" do `seed_demo_users` tạo cho tài khoản `user@gmail.com` (đã kiểm chứng: Preview nhập JSON trên DB sạch chỉ tạo 410; DB sạch đã có sẵn 1 hồ sơ seed ⇒ 411).
2. **Vì sao 1.207 tác giả khác 2.751 vị trí?** Xem 4.4: tác giả đếm theo người; vị trí đếm theo (người × bài).
3. **4.147 affiliation links là gì?** 4.147 dòng trong `publication_author_affiliations` = 883 VERIFIED + 3.264 CORROBORATED. Không phải số tác giả. Giao diện gộp còn 3.451 thẻ (xem 4.9).
4. **Vì sao VERIFIED khác CORROBORATED?** VERIFIED = chuỗi định danh ORCID↔Scopus ID; CORROBORATED = trùng số tác giả + vị trí + tên, *chưa* xác minh.
5. **Vì sao có UNRESOLVED?** Khi không đủ căn cứ (nguồn ngoài không có bài, khác số tác giả, tên không khớp, mâu thuẫn…) hệ thống chọn *không gán* thay vì đoán: 153 vị trí.
6. **Vì sao chỉ 40 ứng viên PENDING?** Chỉ những cặp có **tên khớp theo 4 quy tắc xác định** mới thành ứng viên. Giảng viên có tên Scopus khác nhiều (viết tắt, đảo họ tên) không xuất hiện.
7. **Vì sao không tự động duyệt?** (4.10) — rủi ro gán sai danh tính; cần người chịu trách nhiệm + dấu vết.
8. **Vì sao cùng tên không chắc là cùng người?** Ví dụ ID `59253245500` bị 5 hồ sơ ICTU cùng được đề xuất; ngược lại "Nguyen Thi, Dung" trên Scopus có thể là bất kỳ ai tên đó trong cả nước.
9. **Candidate (ứng viên) và Identity (danh tính) khác nhau thế nào?** Candidate = *đề xuất của máy*, nhiều trạng thái PENDING/ACCEPTED/REJECTED. Identity = *kết luận của người* sau ACCEPT, trạng thái APPROVED. Dashboard "Chờ duyệt 40" đếm candidate; "ỨNG VIÊN/ĐÃ DUYỆT…" đếm identity.
10. **Vì sao một tác giả có thể có nhiều tổ chức?** Một người có thể ghi hai cơ quan trên cùng bài (ví dụ #1 của EID `105027527591` ghi cả NYCU và NCCU; trường hợp ICTU + trường khác).
11. **Vì sao số liên kết lớn hơn số tác giả?** 2 nguồn × nhiều đơn vị × nhiều biến thể chuỗi (4.9).
12. **Vì sao có thể thiếu dữ liệu từ OpenAlex/Crossref?** Nguồn ngoài không lập chỉ mục mọi bài (`NO_EXTERNAL_WORK`: 91 vị trí tác giả ở mỗi nguồn không tìm thấy bài); Crossref nhiều khi **không** cung cấp đơn vị (`ABSENT`: 1.810 bản ghi đối chiếu Crossref ở mức CORROBORATED không có chuỗi đơn vị).
13. **Vì sao đơn vị hiện tại của giảng viên không đồng nghĩa với đơn vị trên bài?** (4.9) — khác thời điểm, khác cách ghi.
14. **Biết ORCID–Scopus ID hỗ trợ xác minh điều gì?** Nếu hồ sơ ORCID công khai *tự khai* Scopus Author ID Y và bài ở OpenAlex/Crossref có đúng ORCID đó ở vị trí tác giả, thì vị trí Scopus của Y chính là người đó (VERIFIED). Nhưng **chưa chắc có đơn vị** (nguồn có thể không ghi).
15. **Vì sao biết Scopus Author ID không có nghĩa Scopus xác nhận đơn vị?** Trong đồ án này đơn vị đến từ OpenAlex/Crossref, không từ Scopus.

---

# Chương 7 — Xử lý lỗi thường gặp

| Tình huống | Dấu hiệu | Cách xử lý |
|---|---|---|
| **BAT không chạy** | Cửa sổ đóng ngay / `[LOI] Khong tim thay Python 3.12 virtual environment` | Kiểm tra thư mục `_venv_backend_demo_py312` còn nguyên cạnh `Scopus-Ictu`; chạy lại BAT |
| **Cổng bị chiếm** | `[LOI] Cong 55432/8001/5173 dang duoc tien trinh khac ... Khong tu dong dung.` | BAT cố ý không kill tiến trình lạ. Đóng chương trình đang dùng cổng đó rồi chạy lại |
| **Backend chưa sẵn sàng** | `Backend khong tra loi /health trong 60 giay` | Xem `logs\demo\backend.log`; chờ thêm; chạy lại BAT |
| **Frontend chưa sẵn sàng** | Trang trắng / không mở được `127.0.0.1:5173` | Xem `logs\demo\frontend.log`; thử Ctrl+F5 |
| **Đăng nhập sai** | Toast "Email hoặc mật khẩu không đúng" | Kiểm tra email/mật khẩu; tài khoản bị khóa báo "Tài khoản đang bị khóa." — nhờ ADMIN mở khóa |
| **Phiên hết hạn / bị thu hồi** | Tự về trang đăng nhập | Đăng nhập lại |
| **Lỗi import (JSON)** | Toast đỏ "Không thể kiểm tra tệp" | Đọc mã lỗi (bảng 4.3): sai cú pháp / thiếu `full_name`, `source_id` / trùng email trong tệp |
| **Lỗi import (CSV)** | "Chỉ hỗ trợ tệp CSV." / cảnh báo tệp trùng | Chọn đúng `.csv`; không "Vẫn nhập lại" nếu không cần |
| **Trùng hồ sơ** | Thẻ **Cảnh báo** > 0, nhãn "Cảnh báo" | Mở **Chi tiết** cả hai hồ sơ, sửa email/đối soát; không xóa vội |
| **Không tìm thấy công bố** | "Không tìm thấy công bố này." | Kiểm tra EID; quay lại danh sách; dùng ô tìm |
| **Không có affiliation** | Tác giả ghi "Chưa xác định được đơn vị" hoặc không có thẻ đơn vị | Bình thường (UNRESOLVED / nguồn không có đơn vị). Không tự điền |
| **Ứng viên bị conflict (409)** | Toast "Không thể lưu quyết định…" | Đọc ngữ cảnh mơ hồ (E); tải lại hàng đợi; chọn quyết định khác |
| **Không đủ quyền** | Menu không hiện; API 403 | Đăng nhập tài khoản đúng vai trò |
| **Màn hình "Đã xảy ra lỗi hiển thị"** | Khung thông báo với nút **Tải lại trang** / **Về trang chủ** (Error Boundary) | Dữ liệu không bị thay đổi; tải lại trang; nếu lặp lại, báo nhóm (chi tiết lỗi ở console trình duyệt) |
| **Trang trắng khi đang sửa mã ở chế độ dev** | Console: "useI18n must be used within an I18nProvider" | Chỉ xảy ra khi sửa mã nguồn lúc phiên đang mở (hot-reload); tải lại trang |

---

# Chương 8 — An toàn dữ liệu

| Thứ | Là gì | Được phép |
|---|---|---|
| **Teacher demo DB** `scopus_ictu_demo_teacher_20261014` (PostgreSQL 127.0.0.1:**55432**) | Dữ liệu trình diễn cho giảng viên | **Chỉ đọc & trình diễn.** Dấu vân tay nội dung được giữ (xem báo cáo) |
| **Database test** (tên chứa `test`, cùng cụm 55432) | Nơi **thử mọi thao tác ghi** | Ghi thoải mái; có thể xóa làm lại. Task 16 dùng `scopus_ictu_test_e2e_t16_20261009` (bản sao teacher) và `scopus_ictu_test_empty_t16_20261009` (trống) |
| **CSV / JSON / Craw gốc** | Dữ liệu nguồn | **Không sửa, không xóa, không ghi đè** |
| **Backup** (`_quan_ly_do_an\backups`, `_postgres_demo_14_10\backups`) | Bản sao lưu | Không xóa; không tự ý ghi |
| **Git repository** | Mã nguồn | Không chứa dữ liệu, mật khẩu, ảnh chụp tài khoản |

**Không bao giờ thực hiện trên teacher DB:** nhập JSON/CSV · chuẩn hóa/nhập lại · thêm/sửa/xóa giảng viên · tạo/khóa/đặt lại mật khẩu tài khoản · **Xuất JSON** (ghi nhật ký) · ACCEPT/REJECT · sinh ứng viên mới · bất kỳ thao tác nào làm đổi audit hoặc dữ liệu nghiệp vụ.
**Không dùng** PostgreSQL cổng 5432, DB acceptance/production. **Không** ghi mật khẩu vào mã, nhật ký, ảnh chụp hay tài liệu.
Nếu cần thử thao tác ghi: khởi chạy Backend/Frontend riêng trỏ vào DB test (cổng khác, ví dụ 8002/5174), dùng cookie/hồ sơ trình duyệt riêng, và **xác nhận tên DB phía máy chủ** trước khi thao tác.
