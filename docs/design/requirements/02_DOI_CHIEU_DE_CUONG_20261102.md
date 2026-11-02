# Đối chiếu đề cương ↔ sản phẩm (cập nhật 02/11/2026)

Bổ sung cho `00_MA_TRAN_YEU_CAU_GVHD.md` (viết ngày 09/10/2026, nhiều dòng đã cũ). Chỉ ghi những thay đổi sau đó.
Nguyên tắc: không ghi "đạt" khi chưa có bằng chứng chạy được.

## 1. Đã bổ sung trong đợt này

| Yêu cầu đề cương | Trước | Nay | Bằng chứng |
|---|---|---|---|
| Gợi ý theo **mã định danh, tên, đơn vị, công bố** | Chưa dùng đơn vị | Đơn vị tác giả (ICTU) là một căn cứ của gợi ý | `services/candidate_fit.py`; `tests/unit/test_candidate_fit.py` |
| Hiển thị **căn cứ và mức độ phù hợp** | Chỉ hiện căn cứ | Nhãn 4 mức (cao / vừa / thấp / chưa đủ căn cứ) kèm lý do bằng câu chữ, ở danh sách và chi tiết | `ApprovalQueue/FitBadge.tsx`; API `fit` |
| **So sánh trước/sau chuẩn hóa** | Không có | Thẻ trong chi tiết công bố: giá trị CSV gốc ↔ giá trị lưu ↔ dạng chuẩn | `services/normalization_compare.py`; `tests/integration/test_normalization_compare.py` |
| **Sao lưu và phục hồi** | Chỉ `pg_dump` rời rạc | Sao lưu + SHA-256 + manifest, kiểm chứng khôi phục, khôi phục vào database mới | `scripts/db_backup.py`; `docs/demo/HUONG_DAN_SAO_LUU_PHUC_HOI.md`; `tests/unit/test_db_backup_safety.py` |
| **Đánh giá chất lượng gợi ý** | Chưa có | Công cụ đánh giá trên tập đối chiếu, báo cáo số liệu | `scripts/evaluate_candidates.py` |
| Quản lý liên kết nhiều Scopus ID của một giảng viên | Chưa có | Duyệt theo nhóm trong một giao dịch, ID chính (chỉ là nhãn), gợi ý theo danh sách gộp của ICTU, khóa khi ID dùng chung | `candidate_group_review.py`, `primary_scopus_identity.py`, `merge_guide.py` |
| Lọc và tìm kiếm | Thiếu ô tìm trong hàng đợi duyệt | Tìm theo tên/email giảng viên, tên/ID tác giả (bỏ qua dấu) | `GET /reviews/candidates?q=` |
| Rà soát đơn vị tác giả | Một vị trí một thao tác | Áp dụng cùng đơn vị cho các bài khác của tác giả (không chọn sẵn, mỗi bài có chứng cứ và nhật ký riêng, tất cả hoặc không gì) | `POST /affiliations/overrides/bulk` |

## 2. Số liệu đánh giá gợi ý (chạy thật 02/11/2026)

Tập đối chiếu: danh sách gộp tài khoản Scopus của ICTU (34 giảng viên, 83 cặp). **Đây là lời khai của nhà trường, chưa phải tập do GVHD xác nhận, và chỉ gồm giảng viên có từ 2 ID trở lên.**

| Chỉ số | Giá trị |
|---|---|
| Độ phủ dữ liệu: ID đối chiếu có trong dữ liệu Scopus đã nhập | 76 / 83 (91,6%) |
| Độ chính xác: cặp đề xuất được tập đối chiếu xác nhận | 18 / 20 (90,0%) |
| Độ phủ gợi ý: cặp đối chiếu mà hệ thống đã đề xuất | 18 / 76 (23,7%) |
| Độ chính xác theo mức | cao 6/6 · vừa 6/6 · thấp 6/8 |

**Điểm yếu thật:** hệ thống đề xuất ít (23,7% số cặp đối chiếu), vì đối chiếu tên chưa bắt được các ID có cách viết tên khác. Mức "cao" và "vừa" không sai trên tập này, mức "thấp" sai 2/8. Đây là số liệu cần nêu trong báo cáo cùng các trường hợp chưa giải quyết được.

## 3. Còn thiếu (không che giấu)

1. **Tập đối chiếu do GVHD xác nhận:** đề cương yêu cầu; hiện chỉ có danh sách của ICTU làm thay thế tạm.
2. **Tiêu chí nghiệm thu thống nhất với GVHD** (PI 1.2): chưa có xác nhận.
3. **Biên bản kiểm thử** gắn với bộ test hiện tại (PI 4.2): cần cập nhật `docs/demo/BAO_CAO_KIEM_THU_CHUC_NANG.md`.
4. **Kiểm thử trên điện thoại** (PI 3.2): giao diện có bố cục co giãn nhưng chưa có bằng chứng kiểm thử.
5. **Báo cáo đồ án** (4 chương): chưa thấy trong kho mã.
6. Luật **độ phủ gợi ý** thấp (mục 2) chưa được cải thiện.
