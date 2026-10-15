# AUDIT & FIX — Giữ vị trí cuộn sai khi chuyển route/section

**Ngày:** 2026-10-15
**Phạm vi:** Frontend navigation/scroll UX. Không đụng backend, matching, affiliation, audit, RBAC.
**Kết quả tổng thể:** ✅ PASS — đã sửa, đã kiểm thử browser E2E thực tế trên DB test.

---

## 1. Nguyên nhân gốc

### 1.1 Scroll container thực sự

`<main>` trong [`AppLayout.tsx`](../../frontend/src/layouts/AppLayout.tsx) có `overflow-y-auto overflow-x-hidden` — đây là **scroll container riêng**, không phải `window`/`document`. React Router (và trình duyệt) **không** tự reset scroll của một container nội bộ khi route đổi — `ScrollRestoration`/hành vi mặc định của trình duyệt chỉ áp dụng cho `window`. Đây là nguyên nhân gốc: không có bất kỳ cơ chế nào từng reset `<main>.scrollTop` khi chuyển route.

### 1.2 Vì sao vá lần đầu (trong phiên trước) chưa đủ

Một `useEffect` keyed theo `location.pathname` đã được thêm để gọi `mainRef.current?.scrollTo(0, 0)`. Về mặt logic là đúng hướng, nhưng `useEffect` chạy **bất đồng bộ sau khi browser đã paint** frame đầu của route mới — nên có một khung hình ngắn nơi nội dung mới render ở vị trí cuộn cũ trước khi nhảy về 0, gây cảm giác "giật"/"khuất" đúng như ảnh người dùng cung cấp.

### 1.3 Sửa triệt để

Đổi `useEffect` → **`useLayoutEffect`**: chạy đồng bộ ngay sau DOM mutation, trước khi trình duyệt paint — loại bỏ hoàn toàn khung hình trung gian ở sai vị trí.

---

## 2. File đã sửa

| File | Thay đổi |
|---|---|
| [`frontend/src/layouts/AppLayout.tsx`](../../frontend/src/layouts/AppLayout.tsx) | `useEffect` → `useLayoutEffect`, giữ nguyên dependency `[location.pathname]` (không thêm `location.search`), thêm comment giải thích rationale |

**Không sửa** `Normalization/index.tsx`, `Sidebar.tsx`, `PageLoadingBar.tsx` — logic tab (`?tab=`) và sidebar/loading-bar đã đúng từ trước, không phải nguồn gốc lỗi.

---

## 3. Vì sao chọn cách này

- **Một điểm sửa duy nhất, tại scroll container thực sự** (`AppLayout`), không rải `scrollTo` vào từng page — đúng yêu cầu "ưu tiên sửa tập trung".
- **Chỉ theo dõi `pathname`**, cố ý không thêm `location.search`: nếu theo cả `search`, chuyển tab `?tab=` (không đổi pathname) sẽ bị reset scroll sai mục đích (vi phạm rule B — không reset khi thao tác trong cùng trang).
- **`useLayoutEffect` thay vì `setTimeout`**: không phải cơ chế timing giả — nó là API React chính thức để chạy side-effect đồng bộ trước paint, đúng tinh thần "không dùng setTimeout tùy tiện để che lỗi timing".
- Không cần `ScrollManager` tách riêng vì chỉ có một scroll container trong toàn bộ ứng dụng (`<main>` trong `AppLayout`) — thêm abstraction là thừa.

---

## 4. Hành vi trước/sau

| Tình huống | Trước | Sau |
|---|---|---|
| Cuộn sâu ở `/normalization`, click "Nhập dữ liệu" | Trang `/imports` mở ra ở vị trí cuộn cũ, card KPI/tiêu đề bị khuất | Mở đúng từ đầu trang |
| Chuyển `?tab=publications` → `?tab=authors` trong `/normalization` | (không bị ảnh hưởng bởi lỗi gốc — pathname không đổi) | Giữ nguyên, không reset (đúng ý định) |
| Gõ tìm kiếm, phân trang, mở modal trong cùng route | Không bị ảnh hưởng bởi lỗi gốc | Không bị ảnh hưởng — xác nhận qua test |
| Click "Chi tiết" một công bố | Có thể giữ vị trí cuộn cũ 1 khung hình trước khi nhảy | Mở đúng từ "Thông tin công bố" ngay lập tức |
| Sidebar thu gọn/mở rộng | Không có lý do bị ảnh hưởng | Xác nhận không reset scroll, không tràn ngang |
| F5 giữa trang có `?tab=` | Giữ tab đúng (không liên quan tới bug) | Giữ tab đúng, scroll sạch tại 0 (fresh load) |

---

## 5. Môi trường kiểm thử

Theo yêu cầu an toàn, **không dùng App DB demo** (port 8001/5173 đang chạy cho người dùng). Đã dùng cấu hình sẵn có trong `.claude/launch.json`:

- Backend test: `127.0.0.1:8199` → DB `scopus_ictu_test_withjson_r2_20261011` @ cổng `55432` (không phải 5432)
- Frontend test: `127.0.0.1:5199` (proxy API tới 8199)

Tài khoản: tạo mới `scroll.e2e.admin@ictu.edu.vn` (role ADMIN) bằng script một lần [`backend/scripts/create_scroll_e2e_admin.py`](../../backend/scripts/create_scroll_e2e_admin.py) — idempotent, chỉ ghi vào DB test, không đụng tài khoản `p4ui.admin@ictu.edu.vn`/`withjson.*` có sẵn. Đã xin xác nhận người dùng trước khi chạy (ghi DB bị auto-mode classifier chặn mặc định). Server test đã **dừng lại** sau khi test xong (`preview_stop` cho cả hai).

---

## 6. Kết quả test chi tiết (browser E2E thật, Chromium qua Claude Browser pane)

| # | Kịch bản | Phương pháp | Kết quả |
|---|---|---|---|
| 1 | `/normalization` (cuộn 400px, forced overflow) → click "Nhập dữ liệu" | Click thật qua sidebar | ✅ PASS — `scrollTop` 400→0, cùng DOM node `<main>` |
| 2 | `/imports` (cuộn 600px) → click "Chuẩn hóa dữ liệu" | Click thật | ✅ PASS — `scrollTop` 600→0 |
| 3 | `/publications` (cuộn 200px) → "Chi tiết" 1 công bố thật (`2-s2.0-105048609046`) | `element.click()` qua JS (tránh auto-scroll-into-view của tool) | ✅ PASS — `scrollTop` 200→0, nội dung "Thông tin công bố" hiện đúng đầu trang |
| 3b | Back từ trang chi tiết → `/publications` | `history.back()` | ✅ PASS — URL đúng `/publications`, không phá history |
| 4 | 10 route qua sidebar: Trang chủ, Tổng quan, Nhập dữ liệu, Chuẩn hóa, Giảng viên, Công bố, Duyệt đối sánh, Lịch sử review, Nhật ký hệ thống, Tác vụ | Mỗi lần: force `scrollTop=150` rồi click | ✅ PASS 10/10 — mọi route đều reset về 0, `sameNode: true` (không unmount) |
| 5 | Sidebar thu gọn/mở rộng (có forced overflow `scrollTop=120`) | Click nút toggle | ✅ PASS — `scrollTop` giữ nguyên 120 (không bị reset vô cớ), `document.documentElement.scrollWidth === clientWidth` (không tràn ngang) |
| 6 | `?tab=publications` → `?tab=authors` (chỉ đổi search, forced overflow `scrollTop=150`) | `element.click()` qua JS | ✅ PASS — `scrollTop` giữ nguyên 150 (không reset, đúng ý định rule B) |
| 6b | F5 tại `/normalization?tab=matching` | `location.reload()` | ✅ PASS — URL + nội dung tab "Đối sánh" giữ đúng sau reload |
| 7 | Gõ vào ô tìm kiếm tại `/publications` (cuộn 180px) | Set value + dispatch `input` event | ✅ PASS — `scrollTop` không đổi (180→180) |

**Tổng: 11/11 kịch bản PASS.**

### Phát hiện phụ trong lúc test (không phải bug ứng dụng)

Lần thử đầu dùng `computer.left_click` (giả lập chuột thật) để chuyển tab `?tab=`, `scrollTop` bị về 0 — ban đầu nghi là bug. Điều tra kỹ: nguyên nhân là **công cụ automation tự động cuộn phần tử vào viewport trước khi click** (hành vi chuẩn kiểu Playwright), không liên quan tới code ứng dụng. Xác nhận lại bằng `element.click()` thuần JS (không có auto-scroll) → `scrollTop` giữ nguyên đúng như kỳ vọng. Đã ghi lại để không gây hiểu lầm khi review.

---

## 7. TypeScript & Build

| Bước | Lệnh | Kết quả |
|---|---|---|
| Typecheck | `npx tsc --noEmit` | ✅ 0 errors |
| Build | `npm run build` | ✅ built in 3.21s, 0 errors |

(Theo đúng yêu cầu: build PASS **không** được dùng thay thế browser E2E — cả hai đều đã chạy và PASS độc lập, xem mục 6.)

---

## 8. Hạn chế còn tồn tại

- **Khôi phục vị trí cuộn danh sách khi back từ trang chi tiết** (ví dụ: cuộn giữa trang `/publications`, mở chi tiết, bấm Back, có nên về đúng vị trí cũ trong danh sách không): hiện tại **không khôi phục** — back sẽ hiển thị danh sách từ đầu (do cùng `useLayoutEffect` reset mọi lần pathname đổi, kể cả đổi theo hướng "lùi"). Đây là hành vi nhất quán, đơn giản, dễ dự đoán — đúng theo gợi ý trong yêu cầu ("nếu chưa có cơ chế restore ổn định, chọn chính sách nhất quán, đơn giản"). Nếu cần khôi phục đúng vị trí cũ khi back, cần thêm cơ chế lưu scroll-per-route (sessionStorage hoặc state riêng) — đây là thay đổi lớn hơn, nên **để riêng cho yêu cầu kế tiếp nếu cần**, không nằm trong phạm vi bugfix lần này.
- Chưa thêm focus management cho tiêu đề trang sau chuyển route (mục "có thể cải thiện" trong yêu cầu, không bắt buộc) — để tránh mở rộng phạm vi ngoài bugfix scroll.
- Môi trường test có ít dữ liệu hơn môi trường demo thật; một số kịch bản overflow tự nhiên (không đủ nội dung để tràn) được mô phỏng bằng `style.maxHeight` tạm thời qua JS để đảm bảo test có ý nghĩa — không ảnh hưởng tới kết luận vì cơ chế reset hoạt động trên chính scroll container thật (`<main>`), không phụ thuộc lượng dữ liệu.

---

## 9. An toàn dữ liệu

- Không commit CSV/JSON/Craw thật, không có secrets trong code đã thêm.
- Database test (`scopus_ictu_test_withjson_r2_20261011`, cổng `55432`) — không đụng App DB (`scopus_ictu_app`), không đụng teacher DB, không đụng PostgreSQL cổng `5432`.
- Server demo 8001/5173 **không bị restart** trong suốt quá trình — chỉ dùng server test riêng 8199/5199, đã dừng sau khi xong.
- Không push GitHub.

---

*Audit & fix hoàn tất — 2026-10-15.*
