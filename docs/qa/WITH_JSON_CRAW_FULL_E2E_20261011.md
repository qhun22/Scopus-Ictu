# E2E luồng CÓ JSON giảng viên + Craw — 12/10/2026

Giai đoạn này chỉ bắt đầu sau Gate 1 (xem `NO_JSON_FULL_E2E_20261011.md`). Mọi thao tác ghi chạy trên DB test mới; App DB và teacher DB chỉ đọc.

**Kết luận Gate 2: PASS** (có giới hạn ghi ở mục 8). Mức bằng chứng: **[TN]** thực nghiệm · **[T]** đọc code · **[CK]** chưa kiểm được.

---

## 1. Môi trường [TN]

| DB | Vai trò | Alembic | Ghi chú |
|---|---|---|---|
| `scopus_ictu_test_withjson_r2_20261011` | **E2E WITH-JSON chính** | `f6a1b2c3d4e5` | dựng từ đầu bằng pipeline hợp lệ |
| `scopus_ictu_test_jsononly_20261011` | trạng thái "CSV + JSON, chưa Craw" để chạy dry-run so sánh | `f6a1b2c3d4e5` | khôi phục từ bản sao lưu trước Craw (`pg_restore`), không ghi gì thêm |
| `scopus_ictu_test_withjson_20261011` | **bỏ** | `f6a1b2c3d4e5` | tôi dùng nhầm CSV tổng hợp 30 dòng của kịch bản "CSV mới" (script bỏ qua tham số đường dẫn). Không xóa DB (theo quy tắc), không dùng, không có JSON/Craw/matching trong đó |
| `scopus_ictu_test_nojson_20261011` | đối chứng NO-JSON | — | **không đổi**: 5 băm nội dung (công bố, tác giả, liên kết, đơn vị, đợt nhập) trùng Gate 1 sau toàn bộ giai đoạn này |

- Tiến trình riêng: backend **8031**, frontend **5194** (`localhost`), helper nạp tệp **5192** — đã tắt sau kiểm thử. Chứng minh kết nối: kết nối PostgreSQL của backend 8031 thuộc đúng DB `…withjson_r2…`. Demo 8001 (PID 3948) / 5173 (PID 8000) không đổi; 5432 không chạm.
- Backup trước từng bước ghi (ngoài Git, `_postgres_demo_14_10/backups/`): `withjson_pre_craw_20261012.dump` (SHA-256 `eb4786e0…278a`, 25 bảng dữ liệu), `withjson_pre_matching_20261012.dump` (`0174a852…93ab3`). Manifest: `_postgres_demo_14_10/manifests/withjson_craw_known_pubs_20261012.json`, `withjson_matching_20261012.json`.
- Nguồn:

| Nguồn | Đường dẫn | SHA-256 | Cấu trúc |
|---|---|---|---|
| CSV | `D:\DataFolder\ProjectIctu\DoAn\Truong_Quang_Huy_Scopus_Sep2026.csv` | `6a62fcf6…bf75d` | 660 dòng (đã kiểm ở NO-JSON) |
| JSON giảng viên | `D:\DataFolder\ProjectIctu\DoAn\ictu_lecturers_20261010_090704.json` | `3bce6750034a9597ce2b3a47dda1c05b5877994a1fc7854a0cd3f56e84727828` (tính lại trong trình duyệt = bằng) | `dataset` + 410 `lecturers`, schema 1.0, 352 có ORCID, **0 mã cán bộ, 0 khối `account`** |
| Craw | `D:\DataFolder\ProjectIctu\DoAn\Craw\output\full\` (`lecturers.json` c12252e0…, `publications.json` 40104734…, `lecturer_publication_links.json` fde1895e…) | — | 410 giảng viên, 1.907 công bố, 328 liên kết, 48 giảng viên có liên kết, 155 công bố phân biệt, 235 liên kết có DOI |

## 2. Dựng nền CSV-only trong DB mới [TN]
CSV → chuẩn hóa → bóc tách tác giả → áp dụng đơn vị (bộ nguồn offline), qua đúng API mà giao diện dùng. Kết quả: 660 / 1.207 / 2.751 / 217 tổ chức / 5.502 resolution / 4.147 dòng đơn vị, và **4 băm nội dung (công bố, tác giả, liên kết, đơn vị) bằng đúng DB NO-JSON** → pipeline xác định, không phụ thuộc DB.

## 3. Nhập JSON giảng viên (giao diện thật) [TN]
| Bước | Kết quả |
|---|---|
| Chọn `ictu_lecturers_20261010_090704.json` → "Kiểm tra dữ liệu" | Tổng 410 · Hợp lệ 410 · **Tạo mới 410** · Cập nhật 0 · Không đổi 0 · **Cảnh báo 0** |
| "Xác nhận nhập" | HTTP 201; đợt "Giảng viên ICTU" `410/410 Hoàn thành`; audit `LECTURER_DATASET_IMPORTED` |
| Danh sách giảng viên (UI + API) | **410** (410 hoạt động, 352 có ORCID, 0 tài khoản, 410 chưa cấp tài khoản, 0 cảnh báo) |
| 410 bản ghi snapshot nguồn | 410 |
| Dữ liệu Scopus sau nhập JSON | công bố / tác giả / liên kết / đơn vị: **băm không đổi** |
| Ứng viên / định danh sau nhập JSON | 0 / 0 — JSON **không** tự khẳng định danh tính Scopus |
| Trùng bất thường | 0 trùng mã (không có mã cán bộ); **16 hồ sơ thuộc 7 nhóm trùng tên chuẩn hóa** (410 hồ sơ nhưng 401 tên chuẩn hóa khác nhau; đồng tên thật, ví dụ nhiều "Nguyễn Thị Dung") — chưa gộp, sẽ xuất hiện thành cảnh báo ở khâu đối sánh |

## 4. Craw làm nguồn tham chiếu [TN]
`ingest_craw_known_publications` (importer có sẵn; chạy trên DB test sau `--dry-run` + sao lưu):

| | Dry-run | Apply |
|---|---|---|
| Giảng viên được ánh xạ | 48 / 0 chưa ánh xạ | 48 snapshot tạo |
| Công bố đã biết | 327 sẽ tạo, 0 xung đột, 1 URL gộp vào bản ghi có sẵn | **327 tạo**, 1 tái dùng, 0 lỗi |
| Bảng thay đổi | — | `lecturer_known_publications` +327, `lecturer_source_snapshots` +48 |

Khớp mốc tham chiếu (48 / 327). **Mức bao phủ thực tế của Craw đối với CSV Scopus** (đếm trực tiếp trong DB):
- Công bố đã biết có DOI trùng một công bố Scopus: 148 bản ghi (26 giảng viên, 62 công bố Scopus); trùng tiêu đề chuẩn hóa: 173 bản ghi (77 công bố Scopus).
- **82 / 660 công bố Scopus (12,4%)** có liên hệ DOI hoặc tiêu đề với Craw; **30 / 410 giảng viên (7,3%)** có ít nhất một công bố như vậy (30/48 trong số giảng viên có dữ liệu Craw).

## 5. Đối sánh và gợi ý [TN]
Dry-run ở **hai trạng thái** (cùng 660 công bố):

| Trạng thái | Ứng viên | Giảng viên | Tác giả Scopus | Bằng chứng tên | Bằng chứng công bố | `pairs_sha256` |
|---|---|---|---|---|---|---|
| CSV + JSON (chưa Craw; DB khôi phục từ sao lưu) | **39** | 37 | 35 | 66 | **0** | `5d45d1a7…511e9` |
| CSV + JSON + Craw | **39** | 37 | 35 | 66 | **41** (32 DOI chính xác + 9 tiêu đề chính xác) | `5d45d1a7…511e9` |

**Hai trạng thái có cùng tập cặp (`pairs_sha256` bằng nhau): Craw không sinh thêm ứng viên nào; nó chỉ thêm bằng chứng công bố cho các cặp đã có** — 5 ứng viên "Có công bố hỗ trợ" và 34 "Chỉ bằng chứng tên". Khớp mốc cũ (39 / 5 / 34), nhưng đó chỉ là số liệu lịch sử, không phải mục tiêu.

Apply (`--apply --expected-candidates 39`, sau sao lưu): run `cff7910d…` `COMPLETED`; 39 gốc ứng viên, 39 quan sát, 107 bằng chứng (66 tên + 41 công bố), `inputs_unchanged_after_apply = true`; trạng thái `PENDING` 39.

**Giới hạn thuật toán (đã đo, không sửa):** 30 giảng viên có công bố Craw trùng một công bố Scopus, nhưng **24 trong số đó không có ứng viên nào** (chỉ 6 có ứng viên). Bằng chứng DOI/tiêu đề hiện **chỉ làm giàu** ứng viên do quy tắc tên sinh ra (một quy tắc duy nhất kích hoạt: `RULE_TITLE_STRIPPED_N2_FORMAT`), **không chủ động đề xuất** tác giả của công bố trùng DOI. Hướng phát triển đề xuất: sinh ứng viên ngược từ DOI → tác giả của công bố Scopus tương ứng, xếp hạng bằng tương thích tên + vị trí + (nếu có) đơn vị ICTU từ bước đơn vị, vẫn bắt buộc duyệt tay. Chưa có gold labels nên **không công bố precision/recall**.

## 6. Hàng đợi `/reviews` và duyệt (DB test) [TN]
- `/reviews/context`: `HAS_CANDIDATES` (410 giảng viên, 660 công bố, 1.207 tác giả, 1 lượt sinh hoàn tất). Lọc: có công bố hỗ trợ 5, chỉ tên 34, mơ hồ 4, **tác giả Scopus dùng chung 5**.
- Chi tiết ứng viên (REVIEWER, giao diện): phần A giảng viên, B tác giả + biến thể tên, C bằng chứng tên (quy tắc + giá trị so sánh), D bằng chứng công bố (`DOI_EXACT`, tiêu đề, DOI, EID, nguồn). **Phân biệt trung thực:** DOI khớp chứng minh *hai công bố là một*, không tự chứng minh Scopus Author ID của giảng viên; tên tương đồng không đủ. Hộp thoại xác nhận bắt buộc kiểm đúng cặp.
- Hành động thử (chỉ DB test): **ACCEPT** `TS. Vũ Đức Quang ↔ 57193082389` (17 bằng chứng công bố) bằng giao diện; **ACCEPT** `PGS.TS. Nguyễn Thị Dung ↔ 59253245500`; **REJECT** `ThS. Đỗ Thị Mai` (chỉ có tên) kèm lý do; chấp nhận **lần hai** cùng Scopus ID cho giảng viên khác → **409 `SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER`** (hệ thống chặn đúng); gửi lại quyết định đã xử lý → 200 **idempotent**, không tạo thêm dòng (tối đa 1 review/ứng viên).
- Kết quả DB: `ACCEPTED 2 · REJECTED 1 · PENDING 36`; 2 định danh `APPROVED`; 20 `identity_evidence`; audit `CANDIDATE_ACCEPTED ×2`, `CANDIDATE_REJECTED ×1`, `IDENTITY_CREATED_FROM_CANDIDATE ×2`.
- REVIEWER quyền (đã kiểm ở DB NO-JSON): đọc công bố 200, hàng đợi 200, export/imports/authors/affiliations 403.
- Ví dụ đồng tên: cặp `Nguyễn Thị Dung` có **5 giảng viên** cùng đề xuất một Scopus ID — chính là ca cần người duyệt.

## 7. Công bố, giảng viên, tài khoản [TN]
- Chi tiết công bố `2-s2.0-105023491380` (REVIEWER): mục "Liên kết giảng viên ICTU" hiện `TS. Vũ Đức Quang`, vị trí 6, Scopus ID `57193082389`, ORCID; 6 tác giả với đơn vị (5 VERIFIED, 1 CORROBORATED) vẫn đúng như trước khi có giảng viên.
- Cấp tài khoản LECTURER cho đúng giảng viên đó bằng endpoint mà form "Sửa giảng viên" dùng (`PUT /lecturers/{id}`, `grant_account`; mức API, mật khẩu ngẫu nhiên không in): đăng nhập → "Công bố của tôi" **27 công bố**, "Định danh Scopus đã duyệt 1"; tra cứu theo `scopus_id=57193082389` → cũng **27**. Chỉ thấy dữ liệu của chính mình ở `/lecturers/me/*`; vẫn 403 ở export, reviews, imports, lecturers, affiliations.

## 8. So sánh ba kịch bản (số liệu thực nghiệm)

| Tiêu chí | CSV-only (DB NO-JSON) | CSV + JSON (DB khôi phục) | CSV + JSON + Craw (DB WITH-JSON) |
|---|---|---|---|
| Công bố chuẩn hóa | 660 | 660 | 660 |
| Tác giả Scopus / vị trí / biến thể | 1.207 / 2.751 / 2.768 | giống hệt | giống hệt |
| Đơn vị tác giả | 5.502 resolution, 4.147 dòng, 217 tổ chức; 2.291 vị trí có ≥1 đơn vị (545 VERIFIED · 2.053 CORROBORATED · 153 UNRESOLVED) | giống hệt | giống hệt (băm không đổi) |
| Giảng viên ICTU | **0** | **410** | 410 (48 có dữ liệu Craw) |
| Ứng viên đối sánh | 0 (`/reviews` giải thích vì sao) | 39 (dry-run) | 39 đã ghi; sau thử duyệt: 36 PENDING · 2 ACCEPTED · 1 REJECTED |
| Bằng chứng tên | 0 | 66 | 66 |
| Bằng chứng DOI/tiêu đề | 0 | 0 | **41** (32 DOI + 9 tiêu đề) trên 5 ứng viên |
| Khả năng ADMIN thao tác | nhập CSV, chuẩn hóa, bóc tách, xem trước/áp dụng đơn vị, tra cứu | + nhập/xem giảng viên; sinh ứng viên **chỉ qua CLI** | + nạp Craw (**CLI**), sinh ứng viên (**CLI**), duyệt trên UI, cấp tài khoản giảng viên |
| Khả năng LECTURER tra cứu | có (tài khoản chưa liên kết, chỉ đọc) | có; "Công bố của tôi" cần tài khoản liên kết **và** định danh được duyệt | có; sau duyệt thấy "Công bố của tôi" (27) |

## 9. Kiểm tra không phá kết quả no-JSON [TN]
Sau toàn bộ nhập JSON, Craw, matching, duyệt: băm nội dung `publications`, `scopus_authors`, `publication_authors` và `publication_author_affiliation_resolutions` của DB WITH-JSON **bằng đúng** DB NO-JSON (và App DB về công bố/tác giả/liên kết). Số dòng bảng nghiệp vụ Scopus không đổi.

## 10. Giới hạn chưa giải quyết
1. **Sinh ứng viên và nạp Craw là CLI**, không có nút trên giao diện (chủ ý: chưa có API kích hoạt an toàn). `/reviews` nói rõ điều này.
2. Craw bao phủ 12,4% công bố / 7,3% giảng viên; DOI/tiêu đề không sinh ứng viên mới (mục 5).
3. JSON không có mã cán bộ và không có khối tài khoản → không có tài khoản nào được tạo từ JSON; muốn giảng viên đăng nhập phải cấp tài khoản từng người.
4. 16 hồ sơ đồng tên (7 nhóm) chưa được phân biệt; cảnh báo "dùng chung Scopus ID" chỉ hiện ở hàng đợi.
5. Chưa chạy matching/duyệt trên App DB hay teacher DB (đúng yêu cầu); định danh `APPROVED` ở trên chỉ tồn tại trong DB test.
6. Ảnh QA ≤ 800 px (xem báo cáo NO-JSON mục 8); cần tự chụp: `/reviews` có ứng viên, hộp thoại chi tiết ứng viên, "Công bố của tôi".
7. Giao diện chưa có test tự động; kiểm bằng trình duyệt tích hợp.

## 11. Gate 2
| Điều kiện | Kết quả |
|---|---|
| JSON + Craw hoạt động, không phá kết quả no-JSON | **PASS** (băm nội dung bằng nhau) |
| Mọi hành động đối sánh thử nghiệm ở DB test | **PASS** |
| Có bằng chứng API/UI, phân quyền phù hợp | **PASS** (ADMIN / REVIEWER / LECTURER chưa liên kết / LECTURER đã liên kết) |
| Không tự chấp nhận ứng viên thật | **PASS** (chỉ thử trên DB test) |
| Không công bố precision/recall khi chưa có gold labels | **PASS** |
