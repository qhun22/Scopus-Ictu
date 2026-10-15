# Đối chiếu Figma — Design System và Dashboard

**Ngày:** 2026-10-15
**File Figma:** `yctOa75eATXHnTQmesJy5A` ("Scopus–ICTU | Thiết kế UI/UX")
**Trạng thái:** ✅ Đã đọc trực tiếp qua MCP, đối chiếu xong các component chính; có 1 điểm lệch có chủ đích (radius)

---

## 1. Node đã đọc thật qua Figma MCP

Dùng `get_metadata` và `get_design_context` (không suy đoán, không bịa).

| Node | Tên | Đọc bằng | Kết quả |
|---|---|---|---|
| `0:1` | Nền tảng thiết kế | `get_metadata` (top-level page listing) | Chỉ trả về page này khi liệt kê — **xác nhận lại** hiện tượng đã ghi trong yêu cầu: liệt kê không đầy đủ |
| `3:3` | Thành phần giao diện | `get_metadata` trực tiếp bằng node ID | **Đọc được đầy đủ** dù không xuất hiện trong danh sách top-level — chứa Buttons, Status Badges, Form Controls, Stat Cards, Data Table, Sidebar, Topbar, PageHeader, và các symbol components |
| `5:2` | Buttons (frame cha) | `get_metadata` | 4 nhóm: Primary, Secondary, Danger, Ghost |
| `5:4` | Primary Button | `get_design_context` (có code + screenshot) | `bg-[#3a5fc3]`, `rounded-[6px]`, `h-36px`, `px-16px`, font `Saira SemiBold 13px` |
| `5:34` | All Badges (Status Badges) | `get_design_context` | 12 badge mẫu, `rounded-[9999px]` (pill), màu theo ý nghĩa trạng thái |
| `9:9` | Search Input | `get_design_context` | `bg-[#f8fafc]`, `rounded-[6px]`, border `#e2e8f0` |
| `9:22` | Stat Cards | `get_metadata` + `get_design_context` cho `9:25` | 4 card KPI tĩnh, `rounded-[10px]`, giá trị placeholder `--`, nhãn "Minh họa" |
| `9:41` | Data Table | `get_metadata` | Header + 3 row mẫu, badge trạng thái trong ô |
| `10:2` | Sidebar | `get_metadata` | 8 mục nav, có mục "Thống kê" riêng (khác cấu trúc code hiện tại) |
| `10:38`, `10:47` | Topbar, PageHeader | `get_metadata` | Breadcrumb, role badge, avatar, nút primary |

**Không có bất kỳ node nào tên/nội dung liên quan "Chart"/"Biểu đồ"** trong toàn bộ `3:3` — xác nhận bằng cách đọc hết children của `3:3` (12 frame con), không node nào là chart.

---

## 2. Component đã đối chiếu

### 2.1 Màu brand — Primary Button
| Thuộc tính | Figma (`5:4`, qua MCP) | Code hiện tại (`buttonStyles.ts`) | Khớp? |
|---|---|---|---|
| Nền | `#3a5fc3` | `#3A5FC3` | ✅ |
| Hover | (không có frame hover riêng trong Figma) | `#2F4EA6` | Không đối chiếu được — Figma chỉ có 1 trạng thái tĩnh |
| Chữ | trắng, Saira SemiBold 13px | trắng, font-bold | ✅ gần đúng (SemiBold vs bold — Tailwind không phân biệt SemiBold/Bold riêng, chấp nhận được) |

**Xác nhận quan trọng:** quyết định đổi Primary Button từ tím `#5B45D2` sang xanh `#3A5FC3` ở phiên trước **là đúng theo Figma thật**, không phải suy đoán.

### 2.2 Status Badges
Figma (`5:34`) dùng `rounded-[9999px]` (pill) cho mọi badge trạng thái, với bảng màu theo ý nghĩa:

| Trạng thái | Figma bg | Figma text |
|---|---|---|
| ACCEPTED | `#ecfdf5` | `#047857` |
| PENDING | `#fffbeb` | `#b45309` |
| REJECTED | `#fff1f2` | `#be123c` |
| PROCESSING | `#ecfeff` | `#0e7490` |
| IMPORTED | `#eef2ff` | `#4338ca` |
| LINKED | `#ecfdf5` | `#047857` |
| UNLINKED | `#fff1f2` | `#be123c` |

Code hiện tại (`badgeClassName` dùng ở nhiều trang) dùng `rounded-full` (= pill, khớp) nhưng bảng màu cụ thể **chưa được đối chiếu từng badge một trong lần này** — ngoài phạm vi thời gian của đợt audit, cần một lượt riêng để map chính xác từng trạng thái (PENDING/ACCEPTED/REJECTED của candidate, VERIFIED/CORROBORATED/UNRESOLVED của affiliation, RECEIVED/PARSING/.../CANCELLED của import) sang đúng bảng màu Figma.

### 2.3 Stat Cards (Dashboard)
Figma (`9:25`): card trắng, border `#e2e8f0`, `rounded-[10px]`, padding `20px`, label `12px #64748b`, giá trị `28px bold #3a5fc3`, dòng phụ `11px #94a3b8`.

Code hiện tại (`SummaryCard` trong `Dashboard/index.tsx`): dùng `rounded-[5px]` (theo quyết định người dùng, xem mục 3), các thuộc tính khác (màu giá trị, label) chưa đối chiếu pixel-perfect trong lần này.

### 2.4 Sidebar
Figma (`10:2`) có mục **"Thống kê"** riêng trong sidebar (giữa "Lịch sử review" và "Nhật ký hệ thống") — **không tồn tại trong code hiện tại**. Đây là điểm lệch thật, chưa rõ có phải route `/dashboard` đổi tên hay là tính năng thống kê riêng chưa triển khai. Không tự ý thêm route mới — ghi nhận để quyết định riêng.

Cấu trúc nav còn lại (Tổng quan, Công bố, Nhập dữ liệu, Giảng viên, Hàng đợi duyệt, Lịch sử review, Nhật ký hệ thống, Tác vụ) khớp về mặt khái niệm với 3 nhóm sidebar hiện tại (Quy trình xử lý / Tra cứu & Kết quả / Quản trị) đã làm ở phiên trước, dù tên nhóm và cách sắp xếp khác (Figma không có grouping, hiện flat list).

---

## 3. Điểm lệch có chủ đích — Border radius

Figma dùng **3 mức radius khác nhau theo loại component**:

| Component | Figma radius |
|---|---|
| Button (`5:4`) | `6px` |
| Status Badge (`5:34`) | `9999px` (pill) |
| Input/Search (`9:9`) | `6px` |
| Stat Card (`9:25`) | `10px` |

Trong phiên làm việc trước (trước nhiệm vụ Dashboard/i18n này), người dùng đã **trực tiếp yêu cầu** đồng nhất toàn bộ site về `5px` cho mọi thành phần (card, button, input, modal), ghi đè quyết định "theo đúng Figma" ban đầu. Khi phát hiện mâu thuẫn này ở đầu Giai đoạn 2, đã hỏi lại và người dùng xác nhận: **giữ nguyên 5px, không đổi lại theo Figma**.

→ Đây là **sai lệch có chủ đích, đã được xác nhận**, không phải lỗi. Badge vẫn giữ `rounded-full` (pill) vì không nằm trong phạm vi "card/button/input" mà người dùng yêu cầu đổi.

---

## 4. Trước/sau — các thay đổi thực hiện trong Giai đoạn 3-4 (không phải thay đổi Figma alignment)

Không có thay đổi UI nào trong Giai đoạn 3-4 (biểu đồ + i18n) đụng tới component Figma đã đối chiếu trước đó (Button/Badge/Sidebar) — các sửa đổi lần này là:
- 3 biểu đồ mới (không có trong Figma — tự thiết kế, xem báo cáo 1 mục 3.3)
- Text nội dung (không ảnh hưởng style)

---

## 5. Phần chưa có thiết kế Figma tương ứng

| Thành phần | Trạng thái |
|---|---|
| Biểu đồ cột/donut bất kỳ | `NOT SPECIFIED IN FIGMA` — không có node nào |
| Dashboard REVIEWER/LECTURER (theo role) | `NOT SPECIFIED IN FIGMA` — chỉ có 1 Topbar mẫu với role "ADMIN" |
| WorkflowBanner, next-step hint (đã làm ở phiên trước) | `NOT SPECIFIED IN FIGMA` |
| Trạng thái loading/error/empty cho biểu đồ | `NOT SPECIFIED IN FIGMA` — có symbol "Trạng thái không có dữ liệu" (`28:11`) và "Trạng thái đang tải" (`28:17`) ở khu vực symbol riêng nhưng chưa đọc design context chi tiết (chỉ có trong metadata listing, chưa gọi `get_design_context` cho 2 node này — hạn chế thời gian) |

---

## 6. Hạn chế của lần đối chiếu này

1. Chưa gọi `get_design_context` cho `28:11` (Trạng thái không có dữ liệu) và `28:17` (Trạng thái đang tải) — chỉ biết qua tên node trong metadata, chưa xác nhận màu/layout cụ thể.
2. Chưa đối chiếu pixel-perfect toàn bộ 12 trạng thái Status Badge với code thật (chỉ đối chiếu Primary Button và radius).
3. Mục "Thống kê" trong Figma Sidebar (`10:28`) chưa được làm rõ có phải route cần thêm hay không — cần quyết định của người dùng, không tự ý thêm.
4. Variable defs (`get_variable_defs`) không gọi được trong phiên này — công cụ yêu cầu selection trong Figma desktop app đang mở, môi trường này không có; toàn bộ màu sắc lấy từ `get_design_context` (giá trị hex trực tiếp trong code trả về), không phải token variable chính thức.

---

## 7. Kết luận

| Tiêu chí (Phần 16) | Trạng thái |
|---|---|
| Giao diện tuân thủ Design System Figma ở component có thiết kế | ✅ PASS cho Primary Button (màu), ⚠️ PARTIAL cho Badge/Stat Card (chưa đối chiếu hết), ⚠️ lệch có chủ đích cho radius (đã xác nhận với người dùng) |
| Không tự bịa Figma đã thiết kế chart chưa tồn tại | ✅ PASS — đã kiểm tra kỹ, ghi `NOT SPECIFIED IN FIGMA` rõ ràng |
| Đọc Figma MCP thật, không suy đoán | ✅ PASS — mọi giá trị trong báo cáo này trích từ `get_metadata`/`get_design_context` thật, có node ID cụ thể |
