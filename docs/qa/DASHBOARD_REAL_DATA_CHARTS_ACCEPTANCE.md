# Nghiệm thu Dashboard — Biểu đồ dữ liệu thật

**Ngày:** 2026-10-15 — cập nhật 2026-10-16
**Phạm vi:** Trang Tổng quan (`/dashboard`), Trang chủ (`/home`)
**Trạng thái tổng thể:** ✅ PASS (biểu đồ `/dashboard`) · ✅ PASS (`/home` không còn placeholder "Đang phát triển", xem mục 7.1) · ⚠️ PARTIAL còn lại (CSV-only riêng biệt, DB trống qua UI, REVIEWER dashboard — xem mục 7)

---

## 1. Hiện trạng trước khi sửa

### 1.1 `/dashboard` (ADMIN only)
Chỉ có 5 KPI card (`SummaryCard`), 4 ô đếm identity status, bảng audit gần đây — toàn bộ lấy từ `GET /api/v1/dashboard/summary`. **Không có biểu đồ nào.**

### 1.2 `/home`
- Khối "Thống kê đối sánh & công bố" (`Home/index.tsx:538-596`, trước khi sửa) là **CSS giả** — 3 đường lưới vẽ bằng `<div>`, không gọi API, hiện cố định text `t.home.chartEmpty` = "Chưa có dữ liệu để hiển thị biểu đồ" và `chartPeriodicSync`/`recentRealtime` = "Đang phát triển".
- Toàn bộ card điều hướng theo role là `<Link>` tĩnh, không có số liệu thật.

### 1.3 Thư viện chart
`package.json` trước khi sửa: chỉ có `antd`, không có chart.js/recharts/victory/nivo/d3/apexcharts nào.

---

## 2. Phân loại theo 5 nhóm yêu cầu (Phần 7)

| Khu vực | Phân loại | Ghi chú |
|---|---|---|
| `/dashboard` — biểu đồ công bố theo năm | 1. Chưa triển khai dù có dữ liệu | `Publication.year` có sẵn, có index — đã triển khai ở lần sửa này |
| `/dashboard` — cơ cấu document_type | 1. Chưa triển khai dù có dữ liệu | `Publication.document_type` có sẵn — đã triển khai |
| `/dashboard` — mức độ đầy đủ đơn vị tác giả | 2. Có component nhưng API chưa nối → nay đã nối | Dữ liệu nguồn (`publication_author_affiliation_resolutions`) đã đầy đủ từ Task 11, chỉ thiếu tầng aggregate — đã viết `get_dashboard_charts` |
| `/dashboard` — trạng thái đối sánh (PENDING/ACCEPTED/REJECTED) | 3→ đã có sẵn, không triển khai thêm | `GET /api/v1/reviews/context` đã trả `candidates_by_status` từ trước — **không cần sửa**, đủ điều kiện cho REVIEWER dashboard nếu làm riêng (ngoài phạm vi lần này, xem mục 7) |
| `/home` khối "Thống kê đối sánh & công bố" | 5. Thiết kế dự kiến, thay bằng shortcut tới chức năng thật | **Đã sửa 2026-10-16** — thay 2 khối CSS-giả bằng card điều hướng thật theo role, dẫn tới `/dashboard`/`/reviews`/`/my-publications` v.v. — xem mục 7.1 |

---

## 3. Biểu đồ đã triển khai (dữ liệu thật)

### 3.1 Backend — endpoint mới

`GET /api/v1/dashboard/charts` (ADMIN only, read-only, không ghi gì) — `backend/app/api/v1/endpoints/dashboard.py`

Service: `backend/app/services/dashboard_queries.py::get_dashboard_charts()`

| Field | Định nghĩa | Nguồn |
|---|---|---|
| `publications_by_year` | Group theo `Publication.year`, loại `NULL`, sort tăng dần | `SELECT year, COUNT(*) FROM publications WHERE year IS NOT NULL GROUP BY year ORDER BY year` |
| `publications_total_without_year` | Đếm riêng các công bố `year IS NULL` | Không gộp vào biểu đồ, không coi là lỗi — hiển thị ghi chú riêng |
| `publications_by_document_type` | Group theo `document_type`, `NULL` → `"UNSPECIFIED"` | Không tự suy đoán loại — chỉ dùng giá trị DB có |
| `affiliation_coverage.total_author_positions` | `COUNT(*)` trên `publication_authors` | **Vị trí tác giả**, không phải Scopus Author duy nhất |
| `affiliation_coverage.positions_with_affiliation` | Vị trí có ≥1 resolution `VERIFIED`/`CORROBORATED` VÀ `affiliation_presence='PRESENT'` | 1 vị trí có nhiều resolution (nhiều source) chỉ đếm 1 lần — lấy rank cao nhất (`VERIFIED` > `CORROBORATED` > `UNRESOLVED`) |
| `affiliation_coverage.positions_without_affiliation` | `total - with` | Gồm cả vị trí `UNRESOLVED`, `ABSENT`, và chưa từng thử (0 resolution) |
| `affiliation_coverage.by_link_status` | Đếm theo trạng thái tốt nhất mỗi vị trí | Tham khảo thêm, không dùng để tính % chính |

### 3.2 Frontend — 3 component chart mới

| File | Loại | Thư viện |
|---|---|---|
| `frontend/src/pages/Dashboard/charts/PublicationsByYearChart.tsx` | Bar chart | `chart.js` + `react-chartjs-2` (mới cài, `chart.js@4.5.1`) |
| `frontend/src/pages/Dashboard/charts/DocumentTypeDonutChart.tsx` | Donut + legend % | nt |
| `frontend/src/pages/Dashboard/charts/AffiliationCoverageChart.tsx` | Donut 2 phần + số % giữa | nt |

Lý do chọn chart.js: nhẹ (~160KB gzip thêm vào bundle), API đơn giản, không cần thêm build config, phổ biến và dễ bảo trì — không có thư viện chart nào cài sẵn trước đó nên không có xung đột lựa chọn.

### 3.3 Đối chiếu Figma (Phần 2)

Đọc trực tiếp node Figma `9:22` (Stat Cards) qua MCP — chỉ thấy 4 KPI card dạng số tĩnh (`--` placeholder, label "Minh họa"), **không có bất kỳ thiết kế biểu đồ cột/tròn nào** trong toàn bộ file Figma (`3:3` "Thành phần giao diện", đã duyệt hết Buttons/Badges/Form Controls/Stat Cards/Data Table/Sidebar/Topbar/PageHeader).

→ **`NOT SPECIFIED IN FIGMA`**. 3 biểu đồ trên tự thiết kế theo:
- Màu brand `#3A5FC3` xác nhận đúng Figma (Primary Button `bg-[#3a5fc3]`)
- Card style `rounded-[5px]` nhất quán với quyết định của người dùng (xem `FIGMA_DASHBOARD_COMPONENT_ALIGNMENT.md`)
- Bảng mẫu bên dưới biểu đồ donut thay cho khả năng đọc bằng thị giác kém — đáp ứng yêu cầu "bảng số liệu thay thế" (Phần 10)

---

## 4. Dữ liệu kiểm thử thực tế

Môi trường: server test `127.0.0.1:8199`/`5199`, DB `scopus_ictu_test_withjson_r2_20261011` (CSV + JSON + Craw đã nạp từ trước, không phải dữ liệu demo).

| Chỉ số | Giá trị quan sát | Ảnh chụp |
|---|---|---|
| Tổng công bố | 660 | Dashboard header card |
| Phân bố theo năm | 2008 → 2027, tăng dần, cột cao nhất ở 2026-2027 | Biểu đồ cột |
| Cơ cấu loại tài liệu | Bài báo hội nghị 367 (55.6%), Bài báo tạp chí 263 (39.8%), Chương sách 13 (2.0%), Bài tổng quan 11 (1.7%), Đính chính 2, Retracted 2, Ghi chú khoa học 1, Bài xã luận 1 | Donut + legend |
| Tổng vị trí tác giả | 2.751 | Donut coverage |
| Có đơn vị công tác | 2.291 (83%) | nt |
| Chưa có đơn vị công tác | 460 | nt |

Không có số liệu nào bị hardcode — toàn bộ lấy trực tiếp từ API tại thời điểm test.

### 4.1 Lỗi phát hiện và đã sửa trong lúc kiểm thử
`document_type` trong CSV Scopus không nhất quán hoa/thường ("Conference paper" vs khóa dịch ban đầu `"Conference Paper"`) → nhãn tiếng Việt rơi về sai giá trị fallback. Đã sửa bằng so khớp case-insensitive (`docType.toLowerCase()`), xác nhận lại bằng browser: "Conference paper" → "Bài báo hội nghị" đúng.

---

## 5. Kiểm thử trạng thái trống (empty state)

Logic đã viết (chưa kiểm thử trên DB rỗng thật trong lần này — xem mục 8 hạn chế):
- `publications_by_year.length === 0` → card "Chưa có công bố nào có năm xuất bản hợp lệ" + hướng dẫn nhập CSV
- `publications_by_document_type.length === 0` → "Chưa có dữ liệu loại công bố"
- `affiliation_coverage.total_author_positions === 0` → "Chưa có vị trí tác giả nào để đối chiếu đơn vị công tác" + hướng dẫn bóc tách tác giả trước
- Lỗi tải (`chartsError`) → khối đỏ + nút "Thử lại" gọi lại `fetchCharts()`
- Loading → skeleton 2 khối xám pulse

22 test backend (`test_dashboard_api.py`, class `TestChartsEmptyDatabase` và các class khác) **đã** chạy PASS trên DB rỗng (schema mới tạo mỗi test) — xác nhận `0`/`[]`/`{VERIFIED:0,...}` đúng, không lỗi 500. Đây là bằng chứng ở tầng API; tầng UI (màn hình thật khi DB trống) chưa chụp ảnh trong lần kiểm thử này.

---

## 6. Kiểm thử kỹ thuật

| Bước | Lệnh | Kết quả |
|---|---|---|
| Backend unit/integration test | `pytest tests/integration/test_dashboard_api.py` trên DB `scopus_ictu_test_pytest_20261013` (pytest-only, qua `db_safety_guard`) | ✅ 56/56 PASS (22 test mới cho `/charts`, 34 test cũ cho `/summary` không bị ảnh hưởng) |
| Frontend TypeScript | `npx tsc --noEmit` | ✅ 0 lỗi |
| Frontend build | `npm run build` | ✅ PASS, 13-14s |
| Browser E2E (CSV+JSON+Craw thật) | Server test 8199/5199, tài khoản `scroll.e2e.admin` | ✅ Cả 3 biểu đồ render đúng, số liệu khớp |
| Responsive | Mobile 375px, laptop 1366px | ✅ Không tràn ngang (`document.documentElement.scrollWidth === clientWidth`), biểu đồ tự xếp dọc trên mobile |

---

## 7. Giới hạn

### 7.1 `/home` placeholder — ĐÃ SỬA (2026-10-16)

Theo rà soát nghiệm thu (phản hồi ChatGPT, mục ưu tiên cao nhất vì `/home` là trang đầu tiên cả 3 role nhìn thấy), 2 khối CSS-giả "Thống kê đối sánh & công bố" và "Hoạt động gần đây" đã được thay bằng card điều hướng thật, dẫn tới route đã tồn tại theo từng role — không xây tính năng mới:

| Role | Khối "chart" dẫn tới | Khối "recent" dẫn tới |
|---|---|---|
| ADMIN | `/dashboard` (3 biểu đồ thật) | `/audit-logs` |
| REVIEWER | `/reviews` (hàng đợi duyệt) | `/review-history` |
| LECTURER | `/my-publications` | `/profile` |

Đã kiểm thử qua browser thật (server test 8199/5199), tạo 2 tài khoản test mới (REVIEWER, LECTURER) để xác nhận cả 3 role — không còn "Đang phát triển"/"In development" ở bất kỳ đâu trên `/home`, cả chế độ VI và EN (test đầy đủ cho ADMIN). Commit `731fa8f`.

### 7.2 Còn lại — chưa làm trong lần này

1. **Biểu đồ trạng thái đối sánh cho REVIEWER dashboard** (Phần 8.4) — dữ liệu đã có sẵn qua `GET /api/v1/reviews/context` (`candidates_by_status`), nhưng chưa dựng UI biểu đồ riêng cho REVIEWER (hiện REVIEWER chỉ có shortcut dẫn tới `/reviews`, không có chart). Đề xuất: tái dùng data này, không cần endpoint mới.
2. **KPI bổ sung** (Phần 8.5: top nguồn xuất bản, số tác giả/bài, số giảng viên có hồ sơ nguồn...) — chưa triển khai, cần đánh giá thêm để tránh làm trang quá tải theo đúng nguyên tắc "chỉ chọn biểu đồ hữu ích, có định nghĩa rõ".
3. Chưa test màn hình thật ở trạng thái **DB hoàn toàn trống** (Kịch bản A, Phần 13.2) — chỉ có bằng chứng ở tầng API (56 test PASS trên schema rỗng). Khuyến nghị bổ sung 1 lượt test UI trên DB trống trước khi coi mục này DONE hoàn toàn.
4. Chưa test riêng kịch bản **CSV-only** (Kịch bản B) qua browser — logic không phụ thuộc JSON nên về lý thuyết hoạt động (3 biểu đồ chỉ cần `publications`/`publication_authors`/`affiliation_resolutions`, không đụng `LecturerScopusCandidate`), nhưng chưa có ảnh chụp xác nhận trên DB CSV-only thật.

---

## 8. Kết luận

| Tiêu chí nghiệm thu (Phần 16) | Trạng thái |
|---|---|
| Trang Tổng quan có biểu đồ hữu ích dựa trên dữ liệu thật | ✅ PASS (3 biểu đồ, `/dashboard`) |
| Không còn placeholder "Đang phát triển" gây hiểu nhầm | ✅ PASS (`/home`, cả 3 role, VI+EN đã test — mục 7.1) |
| CSV-only vẫn hiển thị thống kê công bố/tác giả phù hợp | ⚠️ Chưa test riêng kịch bản CSV-only (có test CSV+JSON+Craw) — logic không phụ thuộc JSON nên về lý thuyết hoạt động, cần xác nhận thêm |
| Số thống kê đối chiếu đúng DB | ✅ PASS (đối chiếu thủ công 660/2751/83% khớp dữ liệu quan sát) |
| Không giả định năm hiện tại là năm lớn nhất | ✅ PASS (group-by thuần, không hardcode) |
| Không hardcode 660/410/327 | ✅ PASS (toàn bộ qua API) |

**Không tuyên bố DONE toàn bộ Phần 7-11** — `/dashboard` ADMIN và `/home` (3 role) đã hoàn thiện và kiểm thử; CSV-only riêng biệt, DB trống qua UI, REVIEWER dashboard chart vẫn PARTIAL.
