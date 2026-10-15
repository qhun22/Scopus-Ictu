# Kiểm toán ngôn ngữ toàn website — VI/EN

**Ngày:** 2026-10-15
**Trạng thái tổng thể:** ⚠️ PARTIAL — các route chính và thành phần dùng chung đã sửa và kiểm thử; chưa quét lại 100% mọi trạng thái/modal ở mọi route (xem mục 6)

---

## 1. Route inventory thực tế

Từ `frontend/src/App.tsx`, 15 route:

| Route | Trang | Vai trò | Trạng thái i18n |
|---|---|---|---|
| `/login` | Đăng nhập | công khai | Không có công tắc VI/EN (xem mục 2) — giữ nguyên |
| `/home` | Trang chủ | ADMIN/REVIEWER/LECTURER | Đã dùng `useI18n` từ trước, không sửa thêm lần này |
| `/search` | Tra cứu tác giả | 3 role | Đã bilingual (literal rẽ nhánh), không sửa |
| `/publications`, `/publications/:eid` | Danh mục/chi tiết công bố | 3 role | **Đã sửa** NULL_YEAR/CITATION/STRING |
| `/profile` | Hồ sơ cá nhân | LECTURER | Đã dùng pattern `viCopy`/`enCopy`, không sửa |
| `/my-publications` | Công bố của tôi | LECTURER | Đã dùng pattern `viCopy`/`enCopy`, không sửa |
| `/identity` | Liên kết Scopus | LECTURER | **Đã sửa** fallback status thô |
| `/reviews`, `/approval-queue` | Duyệt đối sánh | ADMIN/REVIEWER | **Đã Việt hóa hoàn toàn** (848 dòng → namespace mới `approvalQueue`, 127 key) |
| `/review-history` | Lịch sử xét duyệt | ADMIN/REVIEWER | **Đã sửa** ActionBadge/StatusBadge enum thô |
| `/dashboard` | Tổng quan | ADMIN | **Đã sửa** reset modal, import badge, charts section |
| `/imports` | Nhập dữ liệu | ADMIN | Đã bilingual đầy đủ từ trước (kiểm tra lại, không cần sửa) |
| `/normalization` (+ tab `?tab=matching`) | Chuẩn hóa dữ liệu | ADMIN | **Đã Việt hóa hoàn toàn tab Đối sánh** (`MatchingTab.tsx`) |
| `/lecturers` | Danh mục giảng viên | ADMIN | **Đã sửa** 12 placeholder + khu vực "Tài khoản hệ thống liên kết" (~20 chuỗi) |
| `/users` | Quản lý tài khoản | ADMIN | Đã bilingual (literal rẽ nhánh), kiểm tra lại không cần sửa |
| `/audit-logs` | Nhật ký hệ thống | ADMIN | **Đã sửa** nút "Thử lại" |
| `/tasks` | Tác vụ (placeholder) | ADMIN | **Đã sửa** — tách `TasksPlaceholderPage`, theo locale |

**Component dùng chung đã sửa:**
- `ConfirmModal.tsx` — default props + text "Đang xử lý..." nội bộ
- `TextConfirmModal.tsx` — "Nhập...để xác nhận:", "Click để điền tự động"
- `PlaceholderPage.tsx` — default description, nút "Về Trang chủ"

---

## 2. Trường hợp cố ý không sửa — Login

`pages/Login/index.tsx` (410 dòng) 100% tiếng Việt hardcode, **không dùng `useI18n` ở đâu**. Xác nhận: trang này **không có công tắc VI/EN** hiển thị — người dùng chưa đăng nhập nên chưa thấy Header có nút chuyển ngôn ngữ. Đây không phải vi phạm rule "chọn EN vẫn thấy tiếng Việt" vì không có cách nào chọn EN tại màn hình này. Quyết định: **giữ nguyên**, không nằm trong phạm vi sửa lỗi hiển thị sai ngôn ngữ.

---

## 3. Từ điển thuật ngữ đã áp dụng

| Thuật ngữ kỹ thuật | Trước | Sau (áp dụng tại MatchingTab.tsx) |
|---|---|---|
| Craw / Craw ICTU | "Nạp bằng chứng công bố từ Craw ICTU" | "Bổ sung công bố của giảng viên từ kho lưu trữ ICTU" |
| Ingest Craw | — | "Bổ sung công bố của giảng viên..." (nút "Xem trước dữ liệu") |
| Candidate / Generate candidates | "Sinh ứng viên đối sánh" | "Tìm giảng viên có thể tương ứng với tác giả Scopus" (nút "Tạo danh sách đề xuất") |
| Preview | "Xem trước" | "Xem trước dữ liệu" (rõ đối tượng) |
| Apply | "Xác nhận áp dụng" | "Xác nhận bổ sung dữ liệu" |
| Reviewer | REVIEWER | "người xét duyệt" trong văn bản mô tả, giữ "REVIEWER" khi là tên vai trò hệ thống |
| Unmapped | "Chưa khớp hồ sơ: 48" (chỉ số, không giải thích) | "Chưa tìm thấy hồ sơ tương ứng trong danh sách giảng viên của hệ thống. Vui lòng kiểm tra xem danh sách giảng viên ICTU đã được nhập hay chưa." (điều kiện: chỉ hiện khi `unmappedCount > 0`, lấy từ API thật) |
| (đã khớp đủ) | — | "Trong dữ liệu công bố từ kho lưu trữ ICTU, có N giảng viên được ghi nhận có liên kết công bố. Cả N hồ sơ đã tìm thấy..." — **không** gọi là "đã xác minh Scopus" |

### Trạng thái đối sánh (`approvalQueue` namespace, 127 key)
| Backend enum | Nhãn VI | Nhãn EN |
|---|---|---|
| `LecturerScopusCandidate.status = PENDING` | Chờ duyệt | Pending review |
| `... = ACCEPTED` | Đã xác nhận | **Accepted** (không dùng "Verified" — tránh nhầm với affiliation VERIFIED) |
| `... = REJECTED` | Đã từ chối | Rejected |
| `... = SUPERSEDED` | Đã thay thế | Superseded |

### Trạng thái xét duyệt (`reviewHistory` namespace, key mới thêm lần này)
| Backend enum | Nhãn VI | Nhãn EN |
|---|---|---|
| `statusPending` | Chờ xét duyệt | Pending review |
| `statusAccepted` | Đã chấp thuận | Accepted |
| `statusRejected` | Đã từ chối | Rejected |
| `statusSuperseded` | Đã bị thay thế | Superseded |
| Action `ACCEPT`/`REJECT`/`REOPEN` | tái dùng `actionAccept`/`actionReject`/`actionReopen` đã có, bỏ hậu tố `(ACCEPT)` khi hiện trên badge | nt |

### Affiliation (không đổi — đã đúng từ trước, chỉ xác nhận)
`AffiliationsTab.tsx` đã có map `VERIFIED`/`CORROBORATED`/`UNRESOLVED` → nhãn dịch riêng biệt, đúng nghĩa:
- `VERIFIED` = cầu nối ORCID↔Scopus Author ID — **không** dịch "đã xác minh Scopus trực tiếp xác nhận"
- `CORROBORATED` = đối chiếu vị trí+số lượng+tên — **không** dịch "đã xác minh"

**Xác nhận trong lần audit này:** hai khái niệm (identity `APPROVED`, candidate `ACCEPTED`, affiliation `VERIFIED`) không bị gộp lẫn ở bất kỳ chỗ nào đã sửa.

---

## 4. i18n keys bổ sung (tổng hợp theo file)

| Namespace | Key mới | Số lượng |
|---|---|---|
| `approvalQueue` (mới hoàn toàn) | title, statusPending/Accepted/Rejected/Superseded, evidenceType*, ambiguity*, conflict*, empty*Title/Text, col*, v.v. | 127 |
| `reviewHistory` | statusPending/Accepted/Rejected/Superseded | 4 |
| `dashboard` | resetSystem, resetSuccess/Error*, resetModal*, chartsTitle, chartsRetry, publicationsByYear*, documentType*, affiliationCoverage* | 15 |
| `auditLogs` | retry | 1 |
| `nav` | version | 1 |
| `common` | processing, typeToConfirmPrefix/Suffix, clickToAutofill | 4 |

Tổng: **152 key mới**, tất cả đã có đủ cả `vi.ts` và `en.ts`, xác nhận qua TypeScript (`TranslationSchema` interface bắt buộc khớp key ở cả 2 file hoặc build fail).

---

## 5. Hardcoded strings đã xử lý (theo file)

| File | Số chỗ sửa | Loại lỗi |
|---|---|---|
| `MatchingTab.tsx` | Toàn bộ nội dung UI viết lại | Thuật ngữ kỹ thuật khó hiểu (không phải thiếu bản dịch — đã bilingual nhưng dịch sát nghĩa kỹ thuật) |
| `ApprovalQueue/index.tsx` | 74 chuỗi | Hardcode tiếng Việt thuần, không đổi theo locale dù có công tắc VI/EN |
| `Lecturers/index.tsx` | 12 placeholder + ~20 chuỗi khu vực tài khoản | nt |
| `ReviewHistory/index.tsx` | 2 component (ActionBadge, StatusBadge) | Hiện thẳng enum backend không qua nhãn dịch |
| `Identity/index.tsx` | 1 fallback | Hiện thẳng status thô (dead code nhánh else, nhưng fallback không an toàn) |
| `Dashboard/index.tsx` | Reset modal + IMPORT_STATUS_VI (chỉ VI) | Thiếu bản EN hoàn toàn cho nhánh badge trạng thái import |
| `Publications/index.tsx` | 3 hằng số NULL_* | Thiếu bản EN hoàn toàn |
| `Sidebar.tsx` | "Phiên bản" | Thiếu bản EN hoàn toàn |
| `ConfirmModal.tsx` | default props + "Đang xử lý..." | Thiếu bản EN hoàn toàn khi caller không truyền props |
| `TextConfirmModal.tsx` | "Nhập...để xác nhận:", "Click để điền tự động" | Thiếu bản EN hoàn toàn |
| `PlaceholderPage.tsx` + `App.tsx` (`/tasks`) | default description, nút "Về Trang chủ", title/description route `/tasks` | Thiếu bản EN hoàn toàn |
| `AuditLogs/index.tsx` | nút "Thử lại" | Thiếu bản EN hoàn toàn |

**Tổng cộng ước tính: ~230+ vị trí hardcode/enum-thô đã xử lý**, qua 9 commit riêng biệt (xem `git log`).

---

## 6. Kiểm thử VI/EN thực hiện

Theo Kịch bản D (Phần 13.2), môi trường server test 8199/5199, dữ liệu CSV+JSON+Craw thật:

| Bước | Thực hiện | Kết quả |
|---|---|---|
| 1. Chọn VI, vào `/reviews` | ✅ | Hiển thị đúng tiếng Việt |
| 2. Chuyển EN tại `/reviews` | ✅ | "Match Review", "Pending review", "Review Matches", "Review History", "Browse & Results", "Administration" — tự nhiên, nhất quán |
| 3. Sidebar đồng bộ theo locale | ✅ | Chuyển cùng lúc với nội dung trang |
| 4. Deep-link `?tab=matching` tại `/normalization` | ✅ | Nội dung Việt hóa hiển thị đúng khi tải trực tiếp URL có query |
| 5. Chuyển lại VI | ✅ | Khôi phục đúng |
| 6. Dashboard charts VI | ✅ | "Số công bố theo năm", "Cơ cấu loại công bố", "Mức độ đầy đủ đơn vị tác giả" |
| 7-10. Modal, search/filter, empty/loading/error, refresh ở **mọi** route | ⚠️ **Chưa làm đủ** — chỉ test trực tiếp `/reviews` và `/normalization?tab=matching`; chưa lặp lại quy trình 10 bước đầy đủ cho cả 15 route | Xem mục 7 |

**Không đánh dấu Kịch bản D là PASS toàn phần** — chỉ 2/15 route được test đầy đủ quy trình VI→EN→VI qua browser thật; các route còn lại chỉ qua audit code tĩnh (grep + đọc thủ công), không phải browser E2E.

---

## 7. Route còn lỗi hoặc chưa kiểm thử đầy đủ — và lý do

| Route | Trạng thái | Lý do |
|---|---|---|
| `/home` | Còn 2 cụm "Đang phát triển" | Phạm vi Giai đoạn 4 ưu tiên các route có chức năng thật (Dashboard, Reviews, Matching); `/home` cần thiết kế lại theo 3 role riêng biệt (Phần 11), ngoài phạm vi 1 lượt sửa string |
| `/imports`, `/search`, `/users`, `/my-publications`, `/profile` | Đã audit code tĩnh, xác nhận bilingual đúng — **chưa` test qua browser thật** | Giới hạn thời gian; độ tin cậy dựa vào static analysis (grep pattern `locale === "vi" ? ... : ...`), không phải quan sát trực tiếp |
| `/users`, `/lecturers` form tạo tài khoản | Literal rẽ nhánh đã có đủ — nhưng **chưa thử nhập liệu thật qua UI ở chế độ EN** | Chỉ xác nhận qua đọc code |

---

## 8. Kết luận

| Tiêu chí (Phần 16) | Trạng thái |
|---|---|
| Chọn VI → giao diện tiếng Việt nhất quán | ✅ PASS cho các route đã sửa; ⚠️ chưa xác nhận lại `/home` |
| Chọn EN → giao diện tiếng Anh nhất quán, có bản dịch | ✅ PASS cho `/reviews`, `/normalization?tab=matching` (test browser thật); PARTIAL cho các route khác (chỉ audit tĩnh) |
| Không yêu cầu hiểu Craw/candidate/apply | ✅ PASS tại tab Đối sánh — đã viết lại hoàn toàn |
| Không đổi nghĩa khoa học VERIFIED/CORROBORATED | ✅ PASS — xác nhận không gộp nhầm ở bất kỳ chỗ nào sửa |
| Giữ tên riêng, DOI, Scopus ID, metadata gốc | ✅ PASS — không chỗ nào động vào dữ liệu nguồn |

**Không tuyên bố Giai đoạn 4 DONE hoàn toàn** — route chính (Dashboard, Reviews, Matching, Lecturers) đã hoàn thiện và một phần đã kiểm thử browser thật; `/home` và một số route thứ yếu còn cần công việc tiếp theo.
