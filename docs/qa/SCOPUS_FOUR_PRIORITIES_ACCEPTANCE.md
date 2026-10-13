# Đối chiếu 4 Ưu tiên — Scopus-ICTU (tổng hợp, không lặp lại chi tiết từng báo cáo gốc)

**Ngày tổng hợp:** 14/10/2026
**Mục đích:** một bảng đối chiếu duy nhất cho 4 Ưu tiên đã làm, phân biệt rõ **đã hoàn thành** / **đã kiểm thử E2E thật** / **chưa có dữ liệu để kiểm thử** / **chưa triển khai**. Không tuyên bố PASS tuyệt đối cho bất kỳ mục nào còn giới hạn ghi nhận ở báo cáo gốc.

Mỗi dòng dẫn về báo cáo chi tiết gốc — đọc báo cáo gốc để biết đầy đủ bằng chứng, báo cáo này chỉ tổng hợp kết luận.

---

## Ưu tiên 1 — CSV-only + đối chiếu đơn vị trực tuyến

Báo cáo gốc: [PRIORITY_1_ONLINE_AFFILIATION_E2E.md](PRIORITY_1_ONLINE_AFFILIATION_E2E.md)

| Hạng mục | Trạng thái |
|---|---|
| Thu thập trực tuyến OpenAlex/Crossref/ORCID (job nền, poll, hủy) | **Đã kiểm thử E2E thật** (3 DOI thật, UI+API thật) |
| Preview → Apply đối chiếu đơn vị | **Đã kiểm thử E2E thật** trong phạm vi bộ mẫu 3 DOI |
| RBAC ADMIN-only | **Đã kiểm thử E2E thật** |
| CSV Scopus **xuất thật** từ Scopus (không phải CSV 3 dòng tự dựng) | **Chưa có dữ liệu để kiểm thử** — treo lại từ 12/10, chưa đổi |
| Độ chính xác affiliation theo đúng thời điểm xuất bản (so với thời điểm truy vấn) | **Giới hạn kiến trúc đã biết, chưa kiểm chứng định lượng** |

## Ưu tiên 2 — ADMIN hiệu chỉnh đơn vị tác giả thủ công

Báo cáo gốc: [PRIORITY_2_MANUAL_AFFILIATION_E2E.md](PRIORITY_2_MANUAL_AFFILIATION_E2E.md)

| Hạng mục | Trạng thái |
|---|---|
| ADMIN rà soát danh sách cần xử lý, thêm/sửa/thu hồi override | **Đã kiểm thử E2E thật** |
| Một tác giả nhiều đơn vị hiệu chỉnh độc lập | **Đã triển khai** (xác nhận qua commit `579cae5`, ngoài phạm vi báo cáo gốc 12/10 — xem lịch sử git) |
| Audit trail cho override | **Đã kiểm thử E2E thật** |

## Ưu tiên 3 — ADMIN tạo tài khoản Giảng viên/Phê duyệt viên không cần hồ sơ

Báo cáo gốc: [PRIORITY_3_ADMIN_LECTURER_E2E.md](PRIORITY_3_ADMIN_LECTURER_E2E.md)

| Hạng mục | Trạng thái |
|---|---|
| ADMIN tạo LECTURER/REVIEWER không hồ sơ, từ DB trống | **Đã kiểm thử E2E thật**, kể cả route `/users` bị lỗi được phát hiện và sửa ngay trong phiên |
| LECTURER tra cứu công bố/đơn vị không cần JSON | **Đã kiểm thử E2E thật** |
| Không thể tạo ADMIN qua endpoint này | **Đã kiểm thử E2E thật** (type-level, không chỉ runtime check) |
| Nhiều đơn vị cho 1 tác giả cùng lúc (GAP phát hiện ở Ưu tiên 2) | **GAP đã xác nhận có thật ở báo cáo Ưu tiên 3, đã đóng sau đó** (xem Ưu tiên 2, commit `579cae5`) |
| Phiên hết hạn qua UI thật | **Chưa kiểm thử trực tiếp** — chỉ xác nhận gián tiếp qua test tự động |
| Backend restart giữa tác vụ nền | **Chưa kiểm thử lại trong Ưu tiên 3**; đã đóng riêng sau đó (commit `0322f96`, "Khôi phục hiển thị tác vụ thu thập đơn vị trực tuyến sau tải lại trang và xử lý gián đoạn do khởi động lại máy chủ") |

## Ưu tiên 4 — JSON + Craw + Matching

Báo cáo gốc: [PRIORITY_4_PREIMPLEMENTATION_AUDIT.md](PRIORITY_4_PREIMPLEMENTATION_AUDIT.md) (kiểm toán trước triển khai) + [PRIORITY_4_JSON_CRAW_MATCHING_E2E.md](PRIORITY_4_JSON_CRAW_MATCHING_E2E.md) (E2E sau triển khai)

| Hạng mục | Trạng thái |
|---|---|
| ADMIN nhập/cập nhật JSON giảng viên (idempotent, không tạo User, không tự xác nhận Scopus ID) | **Đã hoàn thành từ trước** (xác nhận lại qua kiểm toán 13/10, không có thay đổi mới) |
| REVIEWER duyệt candidate từ khớp tên, giữ lịch sử quyết định | **Đã hoàn thành từ trước**, **đã kiểm thử E2E thật lại** trong phiên này (3 quyết định cũ không bị ghi đè sau khi chạy lại generation) |
| ADMIN nạp Craw qua UI (trước đây chỉ CLI) | **Mới triển khai trong phiên này, đã kiểm thử E2E thật** qua trình duyệt trên dữ liệu Craw thật (48 giảng viên, 327 công bố đã biết) |
| ADMIN sinh ứng viên qua UI (trước đây chỉ CLI) | **Mới triển khai trong phiên này, đã kiểm thử E2E thật** — 149 candidate tổng (39 tên + 110 Craw-assisted) trên dữ liệu thật |
| Craw-assisted candidate discovery (phát hiện candidate mới từ Craw, không chỉ bổ sung evidence) | **Mới triển khai trong phiên này** — thiết kế ban đầu có lỗi mass-generation, đã tự phát hiện và sửa bằng quy tắc 2 neo (vị trí tác giả + tương quan tên); đã kiểm thử E2E thật, 110/571 (19%) vị trí tác giả được neo đúng, phần còn lại bị loại đúng |
| REVIEWER phân biệt rõ nguồn gốc candidate (tên vs Craw-assisted) trên UI | **Mới triển khai trong phiên này, đã kiểm thử E2E thật** — badge + cảnh báo rõ ràng, không cần đổi schema backend |
| Precision/recall của candidate Craw-assisted | **Chưa có ground truth để kiểm chứng** — không công bố con số |
| 2 REVIEWER duyệt đồng thời candidate Craw-assisted | **Chưa kiểm thử riêng cho loại candidate mới** (logic concurrency không đổi, kế thừa từ test cũ) |
| CSV Scopus xuất thật (kế thừa giới hạn Ưu tiên 1) | **Vẫn chưa có dữ liệu để kiểm thử**, không đổi |

---

## Tổng hợp kỹ thuật xuyên suốt 4 Ưu tiên

| Hạng mục | Trạng thái hiện tại (14/10/2026) |
|---|---|
| Backend test suite đầy đủ | **1004 passed, 5 skipped, 0 failed, 0 errors** (venv `_venv_backend_demo_py312`, DB pytest `scopus_ictu_test_pytest_20261013`) |
| Frontend build | PASS, 0 lỗi TypeScript |
| Alembic | 1 head duy nhất `c7f2a9b1d3e5`, không drift |
| CI GitHub Actions | **NOT VERIFIED trên cả 4 Ưu tiên** — chưa push, không coi test suite xanh cục bộ là bằng chứng CI PASS |
| App DB (`scopus_ictu_app`, cổng 55432) | Xác nhận không bị động tới xuyên suốt 4 Ưu tiên (kiểm tra lại 14/10: `candidate_generation_runs` = 0, không đổi) |
| Teacher DB (`scopus_ictu_demo_teacher_20261014`) | Xác nhận không bị động tới (kiểm tra lại 14/10: `candidate_generation_runs` = 2, số cũ không tăng) |
| `/system/reset` | Không chạm trong cả 4 Ưu tiên |
| GitHub | Không push ở bất kỳ Ưu tiên nào; không commit JSON giảng viên thật/CSV Scopus thật/Craw thô/secrets |

## Giới hạn còn treo xuyên suốt cả 4 Ưu tiên (chưa đóng, không lặp lại chi tiết)

1. **CSV Scopus xuất thật** — treo từ Ưu tiên 1 (12/10), chưa có dữ liệu để kiểm thử ở bất kỳ Ưu tiên nào sau đó.
2. **CI GitHub Actions thật** — chưa xác nhận ở bất kỳ Ưu tiên nào (không push).
3. **Phiên hết hạn qua UI thật** — chưa test trực tiếp (chỉ gián tiếp qua test tự động), từ Ưu tiên 3.
4. **Precision/recall cho matching** — không có ground truth ở bất kỳ giai đoạn nào, kể cả candidate Craw-assisted mới.
5. **Backend restart giữa tác vụ nền Craw/matching** — chưa test riêng cho luồng mới của Ưu tiên 4 (đã test cho luồng affiliation ở commit `0322f96`, không tự động suy ra matching cũng an toàn tương tự dù cơ chế append-only giống nhau).

**Không có Ưu tiên nào trong 4 Ưu tiên được tuyên bố "hoàn thiện tuyệt đối"** — mỗi báo cáo gốc đều ghi PASS có điều kiện kèm danh sách giới hạn cụ thể, giữ nguyên trạng thái đó trong bảng tổng hợp này.
