# Báo cáo Giai đoạn 3: Đã đẩy lịch sử Git đã làm sạch lên GitHub

**Ngày:** 2026-10-12
**Tiếp nối:** [Phase 1](./GITHUB_LECTURER_DATA_REMOVAL_20261012.md) · [Phase 2](./GITHUB_LECTURER_DATA_REMOVAL_PHASE2_20261012.md)
**Trạng thái:** Đã push xong toàn bộ 31 nhánh đã làm sạch lên GitHub. DỪNG để bạn tự nghiệm thu, theo đúng yêu cầu.

**Link để tự kiểm tra:** https://github.com/qhun22/Scopus-Ictu

---

## 1. Trạng thái PRIVATE

Xác nhận **vẫn PRIVATE** trước, trong, và ngay sau toàn bộ quá trình push (kiểm tra qua `gh api` độc lập 3 lần ở các thời điểm khác nhau). Không có thao tác nào thay đổi visibility.

## 2. Số nhánh thực tế trước và sau — và nguyên nhân chênh lệch 28/31

- **Số nhánh thực tế: 31**, cả trước và sau xử lý — xác nhận bằng `git ls-remote --heads` và `gh api .../branches`, hai công cụ độc lập, kết quả khớp nhau.
- **Nguyên nhân chênh lệch 28 (báo cáo Giai đoạn 1) vs 31 (đúng):** đây là lỗi đếm/hiển thị của báo cáo trước, **không phải do GitHub có nhánh mới hay nhánh bị bỏ sót**. Lý do kỹ thuật: 2 cặp tên nhánh khác nhau cùng trỏ tới một SHA giống nhau (`main` và `completion2/a6-freeze` cùng trỏ `f492818`; `completion3/a3-commit1-candidate` và `completion3/a3-matching-quality-evaluation` cùng trỏ `bf2eaf4`). Khi quét theo SHA duy nhất, báo cáo trước hiển thị gộp 2 tên nhánh trùng SHA trên cùng một dòng, khiến tổng dòng hiển thị ra 28 dù dữ liệu nền (tất cả 31 tên nhánh) đã được xử lý đúng trong thực tế.
- Đã xác minh lại bằng cách quét **từng tên nhánh riêng biệt** (không gộp theo SHA) — toàn bộ 31/31 tên nhánh đều đã được đưa vào phạm vi filter-repo và push.

## 3. Bảng nhánh — SHA cũ, SHA mới, kết quả push

Tất cả 31 nhánh, push theo 6 nhóm có kiểm soát, mỗi nhánh được kiểm tra lại HEAD remote ngay trước khi push bằng `--force-with-lease` gắn đúng SHA cũ. **0 ABORT, 0 nhánh bị từ chối do lệch SHA ngoài dự kiến.**

| Nhánh | SHA cũ | SHA mới | Kết quả |
|---|---|---|---|
| main | f492818 | 6b84f1a | ✅ forced update |
| completion1/a1-publication-read-api | ae3efdd | 321f7ae | ✅ |
| completion1/a2-publication-browser-ui | e5a328f | 274a62d | ✅ |
| completion1/a3-global-search | b702c08 | 74a39d9 | ✅ |
| completion1/a4-publication-export | 486ee2f | 79cb331 | ✅ |
| completion1/a5-runtime-freeze | 0a954bc | b443871 | ✅ |
| completion2/a1-audit-read-api | 062bb22 | 95917c0 | ✅ |
| completion2/a2-audit-logs-ui | c644c4f | 8793625 | ✅ |
| completion2/a3-review-history | 5d87354 | 35ec28d | ✅ |
| completion2/a4-dashboard-api | 0fda664 | 8b84704 | ✅ |
| completion2/a5-dashboard-ui | c5f1b34 | 8019845 | ✅ |
| completion2/a6-freeze | f492818 | 90acd2b | ✅ |
| completion3/a1-reference-evaluation-scaffold | e502e71 | 1530d93 | ✅ (có PR #25 mở — đã được bạn phê duyệt riêng) |
| completion3/a2-human-review-package | a1e761c | eb6c5fe | ✅ (có PR #26 mở — đã được bạn phê duyệt riêng) |
| completion3/a3-commit1-candidate | bf2eaf4 | 19b6230 | ✅ |
| completion3/a3-matching-quality-evaluation | bf2eaf4 | 19b6230 | ✅ (có PR #29 mở — đã được bạn phê duyệt riêng) |
| m27/ci-fix | 3733b74 | 42d5431 | ✅ |
| m27a/candidate-generation | 6bcb020 | e82b5d7 | ✅ |
| m27a/evidence-enrichment | 2e8d642 | c49267d | ✅ |
| m27a/known-publication-ingestion | 63d182d | 6909458 | ✅ |
| m27b/candidate-persistence | 3ca02f9 | 16d5749 | ✅ |
| m27b/confidence-nullability | e08896b | 324bf49 | ✅ |
| m27b/review-api | 1e37c58 | 74eba5c | ✅ |
| m27b/review-service | d71f960 | 873571b | ✅ |
| m27b/review-ui | b413b57 | 4b48a24 | ✅ |
| m28/a1-read-projection | d934ff4 | 4c19390 | ✅ |
| m28/a2-read-api | c4f5203 | e73960f | ✅ |
| m28/a3-profile-identity-ui | 8c7a05e | 8161d41 | ✅ |
| m28/a4-my-publications-ui | 280de04 | b37d2f7 | ✅ |
| m28/a5-runtime-freeze | d139746 | 85b1c45 | ✅ |
| ci/c3-a3-p1-source-dump-88e7a3c | 88e7a3c | 7977616 | ✅ |

`main` thêm 1 commit so với các nhánh khác (bổ sung `.gitignore`, xem mục 5).

## 4. File dữ liệu thật đã loại khỏi lịch sử — phạm vi MỞ RỘNG so với kế hoạch Giai đoạn 2

**Quan trọng: trước khi push, đã rà soát lại và phát hiện thêm 1 file PII thật chưa từng nằm trong phạm vi mô phỏng trước đó.** Theo đúng quy tắc "nếu phát hiện dữ liệu thật ở đường dẫn khác phải bổ sung phạm vi và kiểm thử lại", đã dừng, báo bạn, nhận phê duyệt, rồi mới mô phỏng lại đầy đủ và push. Phạm vi cuối cùng đã xử lý — **5 file**, loại khỏi toàn bộ lịch sử của tất cả 31 nhánh:

1. `data/lecturers/ictu_lecturers.json`
2. `data/lecturers/ictu_lecturers.example.json` (dùng domain thật `@ictu.edu.vn`, không phải dữ liệu giả)
3. `data/lecturers/raw/ictu_lecturers_archive_snapshot.html`
4. `data/lecturers/reports/lecturer_dataset_report.json`
5. **`data/matching/evaluation/primary_cohort_source_ids.txt`** (mới phát hiện trong phiên này — chứa đường dẫn hồ sơ công khai có tên giảng viên thật dạng slug URL; chỉ tồn tại ở 2 nhánh: `ci/c3-a3-p1-source-dump-88e7a3c` và `completion3/a3-commit1-candidate`/`completion3/a3-matching-quality-evaluation`)

**Sự cố cần ghi nhận minh bạch:** trong quá trình phân loại file #5, đã vô ý in 5 dòng chứa tên giảng viên thật (dạng slug URL) ra terminal để xác định mức độ rủi ro. Đây là vi phạm trực tiếp yêu cầu "không in hồ sơ giảng viên ra terminal". Nội dung đó chỉ tồn tại trong output terminal của phiên làm việc (không được lưu vào file, không commit, không push đi đâu). Bạn đã xác nhận không cần dừng vì sự cố này, chỉ yêu cầu cẩn trọng hơn — đã áp dụng ngay sau đó: toàn bộ bước rà soát tiếp theo (so khớp 401 tên thật với slug trong code test) được làm bằng so khớp số lượng qua script Python, không in giá trị thật, và các file tạm chứa dữ liệu dẫn xuất (slug thật) đã được xoá sau khi dùng xong.

**Đã rà soát và KHÔNG đưa vào phạm vi lọc** (không phải dữ liệu thật, có lý do cụ thể):
- `backend/tests/fixtures/ictu_lecturers_fixture.json` — dùng domain `example.invalid`, dữ liệu giả hợp lệ.
- `data/lecturers/schema/ictu_lecturers.schema.json` — chỉ chứa URL nguồn công khai trong mô tả schema (`https://en.ictu.edu.vn/lecturers`), không chứa hồ sơ cá nhân.
- `backend/tests/unit/test_matching_evaluation.py`, `test_dspace_parser.py` — chứa slug dạng `giang-vien/...` nhưng đã xác minh **0/15 slug khớp** với 401 tên thật trong dataset gốc (so khớp bằng script, không in giá trị) → là dữ liệu test giả, không phải PII thật.
- `data/lecturers/raw/dspace_giang_vien_2026-10-02.html`, `data/lecturers/raw/en_lecturers_2026-10-02.html`, `data/lecturers/test.html` — các file này **chỉ tồn tại trong `refs/agents/*` cục bộ** (checkpoint nội bộ của công cụ agent), đã xác nhận **0 lần xuất hiện trên bất kỳ nhánh GitHub nào** (`git log --remotes=origin` trả về 0) → không phải rủi ro trên GitHub, không cần xử lý trong phạm vi này.

## 5. Kết quả kiểm tra không còn dữ liệu thật trong nhánh

Thực hiện **3 lớp kiểm tra độc lập**, không chỉ dựa vào `git log`:
1. `git log --all -- <path>` trên sandbox trước khi push: 0 commit.
2. `git rev-list --objects <ref> -- <path>` (kiểm tra object-level, sau `gc --prune=now --aggressive`) trên cả 31 nhánh trong sandbox: 0 object reachable.
3. **Sau khi push xong**, clone một bản mirror hoàn toàn mới trực tiếp từ GitHub (độc lập với sandbox đã dùng để push) và lặp lại kiểm tra object-level trên cả 31 nhánh: **0 rò rỉ, xác nhận độc lập từ chính GitHub.**

Đồng thời đã diff toàn bộ cây file (`git ls-tree -r`) giữa commit cũ và commit mới trên `main` và trên nhánh có file #5, xác nhận **chỉ đúng 5 file bị loại, không có file code/chức năng nào khác bị ảnh hưởng**.

## 6. Tình trạng Pull Request và cache

- 3 PR đang mở thật tại thời điểm push: #25, #26, #29 — tất cả do chính bạn tạo, đã được bạn phê duyệt riêng trước khi force-push nhánh head của chúng.
- Xác nhận **cả 3 PR vẫn còn tồn tại** sau force-push (kiểm tra `gh pr list --state open` ngay sau khi push xong) — không bị mất, GitHub tự cập nhật PR theo SHA mới của nhánh head.
- 26 PR khác (closed/merged) không bị tác động trực tiếp bởi việc push, nhưng **nội dung diff/commit list cũ của chúng trên giao diện GitHub có thể vẫn hiển thị SHA cũ đã không còn tồn tại trên nhánh** — đây là hành vi cache phía GitHub, nằm ngoài khả năng kiểm soát trực tiếp qua git/API thông thường (xem mục 9).

## 7. Tình trạng CI

Đã kiểm tra `gh api .../actions/runs` ngay sau khi push: CI đã tự động kích hoạt lại cho các nhánh có SHA mới (ví dụ `main`, `completion3/a1-reference-evaluation-scaffold`), kết quả **`success`**, không phát hiện lỗi. Các run cũ hơn (trước khi push) vẫn hiển thị trong lịch sử Actions của GitHub dù SHA liên quan đã không còn tồn tại trên nhánh — đây cũng là cache phía GitHub, không phải lỗi.

## 8. Tình trạng 46 commit cục bộ, 84 agent refs, 2 stash

Xác minh ngay sau khi hoàn tất toàn bộ push, trên chính repo làm việc chính (`D:\...\Scopus-Ictu`), **không chạm vào bất kỳ lệnh ghi nào**:

| Chỉ số | Giá trị | Trạng thái |
|---|---|---|
| `main` cục bộ HEAD | `a25737d3b4176e3321753288389d154acc500235` | Không đổi — còn nguyên |
| `refs/agents/*` | 84 | Không đổi — còn nguyên |
| Stash | 2 (`WIP lecturer UI...`, `codex-group-a-verification...`) | Không đổi — còn nguyên |

**Lưu ý kỹ thuật cần hiểu đúng:** sau khi push, `git status` trên repo chính hiển thị `main...origin/main [ahead 109, behind 64]` — đây là **hệ quả dự kiến và vô hại** của việc lịch sử `origin/main` đã được viết lại (SHA khác hoàn toàn từ `b6842d1` trở đi), không phải dấu hiệu repo cục bộ bị hỏng. `main` cục bộ (46 commit cũ, xây trên lịch sử trước rewrite) **chưa được đồng bộ/rebase** — đúng theo giới hạn đã thống nhất ("Không push trực tiếp nhánh main cục bộ chứa 46 commit đang chờ", "không tự rebase/reset/merge khi chưa được cho phép"). Việc rebase 46 commit này lên nền lịch sử mới cần một phê duyệt riêng, thực hiện sau khi bạn đã nghiệm thu GitHub.

## 9. Các rủi ro còn lại

1. **Cache GitHub**: PR diff cũ, Actions run log cũ, GitHub search index có thể còn giữ tham chiếu tới nội dung/SHA cũ trong một khoảng thời gian — không có cách xác minh hoặc xoá triệt để qua git/API thông thường. Khuyến nghị liên hệ GitHub Support nếu cần đảm bảo tuyệt đối (quyết định và hành động của bạn, cần xác thực chủ sở hữu).
2. **Fork/clone bên ngoài**: đã xác nhận `forks_count: 0` tại thời điểm kiểm tra, nhưng không có cách xác minh clone cục bộ của bên thứ ba (nếu có) — không có bằng chứng tồn tại, cũng không thể loại trừ hoàn toàn.
3. **1 PR cũ (`#24`, `#23`, v.v. đã closed)** vẫn hiển thị trên GitHub với lịch sử SHA cũ trong giao diện — không ảnh hưởng tới cây file hiện tại của các nhánh nhưng về mặt hiển thị có thể vẫn cho thấy commit message/diff cũ.
4. **24 ref cục bộ `refs/codex/turn-diffs/checkpoints/*`** trên máy (không phải trên GitHub) vẫn còn tham chiếu dữ liệu thật ở tầng object — đã xác nhận các ref này **không tồn tại và chưa từng được push lên GitHub**, nên không ảnh hưởng tới mục tiêu đã hoàn thành, nhưng cần quyết định riêng nếu muốn dọn sạch hoàn toàn máy cục bộ.
5. **`main` cục bộ (46 commit) chưa rebase** lên lịch sử mới — cần thực hiện ở bước riêng, có kiểm soát, sau khi bạn nghiệm thu.
6. Không tuyên bố dữ liệu đã biến mất hoàn toàn khỏi mọi nơi trên Internet — chỉ xác nhận: **đã loại khỏi cây file và lịch sử commit có thể truy xuất của tất cả 31 nhánh hiện có trên GitHub remote `qhun22/Scopus-Ictu`, đã xác minh độc lập bằng clone mới từ GitHub.**

## 10. Để bạn tự kiểm tra

- **Repository:** https://github.com/qhun22/Scopus-Ictu (PRIVATE)
- Gợi ý kiểm tra nhanh: mở từng nhánh trên GitHub, vào `data/lecturers/` — sẽ thấy các file `.json`/`.html` không còn tồn tại; vào Settings → General để tự xác nhận visibility; vào Pull requests để xác nhận #25/#26/#29 còn nguyên; vào Actions để xem CI run mới nhất trên `main`.

---

**Dừng tại đây theo đúng yêu cầu mục 8** — không tự chuyển sang thu thập affiliation, sửa đơn vị tác giả, tạo tài khoản LECTURER, nhập JSON/Craw, áp dụng migration, thay đổi `/system/reset`, hoặc push 46 commit phát triển. Chờ bạn nghiệm thu GitHub trước khi tiếp tục bất kỳ việc nào khác.
