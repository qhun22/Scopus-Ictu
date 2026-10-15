# Báo cáo xác minh: Dữ liệu giảng viên thật trên GitHub (Scopus-Ictu)

**Ngày:** 2026-10-12
**Phạm vi:** Chỉ xác minh và lập kế hoạch. Chưa thực hiện bất kỳ thay đổi nào lên remote.
**Trạng thái:** DỪNG theo mục 8 của yêu cầu — chờ phê duyệt trước khi hành động.

---

## 1. Repository công khai hay riêng tư

- Remote: `https://github.com/qhun22/Scopus-Ictu.git`
- **Visibility: PUBLIC**
- Default branch: `main`

## 2. File thực tế có mặt trên remote không

Đã xác minh bằng `git ls-remote` (không dựa vào tracking ref cục bộ cũ) — remote HEAD thực tế là `f49281802fe5d46fdc4e1ef872978b0cbaf73c4c`, trùng khớp với `origin/main` cục bộ (không bị lệch).

File `data/lecturers/ictu_lecturers.json` **có mặt** trong cây file của remote HEAD (kích thước ~437 KB, ~410 bản ghi theo cấu trúc JSON).

### Phát hiện bổ sung quan trọng — vượt phạm vi file được nêu ban đầu

Quét toàn bộ cây file remote HEAD phát hiện **thêm 2 file khác chứa dữ liệu thật** liên quan đến giảng viên, ngoài file người dùng đã chỉ định:

| File | Kích thước | Ghi nhận |
|---|---|---|
| `data/lecturers/ictu_lecturers.json` | ~437 KB | Dataset thật, ~410 bản ghi (đúng như báo cáo ban đầu) |
| `data/lecturers/ictu_lecturers.example.json` | ~5.8 KB | 5 bản ghi, dùng domain email **thật** `@ictu.edu.vn` → **không phải dữ liệu giả**, là trích đoạn từ dữ liệu thật |
| `data/lecturers/raw/ictu_lecturers_archive_snapshot.html` | ~1.13 MB | HTML crawl gốc, chứa 1693 lần xuất hiện domain `ictu.edu.vn` → rất có thể là snapshot thô chứa PII thật |

File khác đã kiểm tra và **xác nhận an toàn** (không cần xử lý):
- `backend/tests/fixtures/ictu_lecturers_fixture.json` — dùng domain `example.invalid`, là dữ liệu giả hợp lệ.
- `data/lecturers/reports/lecturer_dataset_report.json` — chỉ chứa số liệu tổng hợp (counts, field_coverage, privacy_check flags), trường `privacy_check` tự báo cáo không có password/token/CCCD/địa chỉ. Khuyến nghị vẫn nên bỏ tracking vì đây là báo cáo phái sinh trực tiếp từ dataset thật, nhưng mức độ rủi ro thấp hơn 3 file trên.

## 3. Commit đưa file vào lịch sử

Cả 3 file rủi ro chính (`ictu_lecturers.json`, `ictu_lecturers.example.json`, `archive_snapshot.html`) được đưa vào **cùng một commit**:

- **SHA:** `b6842d11351771f178725a42f12ddeaadeb9e963`
- **Ngày:** 2026-10-03 13:40:51 +0700
- **Author/Committer (theo Git):** Quang Huy Truong (trùng với Git user cấu hình máy hiện tại — không suy luận thêm ai thực hiện hành động push, vì không có bằng chứng độc lập về việc push)

## 4. Phạm vi rủi ro thực tế — QUAN TRỌNG, VƯỢT PHẠM VI BAN ĐẦU

Yêu cầu ban đầu giả định cần "gỡ khỏi phiên bản GitHub hiện tại" (HEAD của `main`). Khi quét toàn bộ remote, phát hiện:

- Repo có **27 remote branch khác** ngoài `main`.
- File `data/lecturers/ictu_lecturers.json` **có mặt ở TẤT CẢ 27 branch đó cộng với `main`** — tức là **toàn bộ 28 nhánh remote hiện có đều chứa dữ liệu thật**.
- Có **29 Pull Request** (26 closed, 2 merged, nhiều draft/CI-carrier) liên kết tới các nhánh này trên GitHub — nghĩa là nội dung file cũng tồn tại trong diff/cache của các PR đó, độc lập với trạng thái branch.

**Hệ quả:** một commit xoá file duy nhất trên `main` — đúng như mục 4 yêu cầu — sẽ **không** loại được dữ liệu khỏi GitHub công khai, vì 27 branch khác và các PR liên quan vẫn phân phối nguyên vẹn dữ liệu thật. Đây không phải vấn đề "xoá khỏi HEAD" đơn giản mà là vấn đề **toàn bộ lịch sử + toàn bộ ref namespace** của một repo public.

## 5. Các thao tác đã thực hiện (chỉ đọc, không ghi)

1. `git remote -v`, `git status`, `git rev-parse` — xác minh trạng thái local (46 commit ahead, khớp báo cáo trước).
2. `git for-each-ref refs/agents` → đếm được đúng 84 ref (khớp báo cáo trước).
3. `git stash list` → đúng 2 stash còn nguyên (khớp báo cáo trước).
4. `git fetch origin --prune` → đồng bộ thông tin remote, không thay đổi working tree.
5. `git ls-remote origin HEAD refs/heads/main` → xác nhận remote HEAD thật = `f492818...`, khớp tracking ref cục bộ.
6. `gh repo view` → xác nhận PUBLIC, default branch `main`.
7. `git ls-tree -r <remote HEAD>` → xác nhận file có mặt, tìm các file dữ liệu khác.
8. `git log --follow --diff-filter=A` → tìm commit đầu tiên thêm từng file.
9. `git ls-remote --heads origin` + quét từng branch tip bằng `git ls-tree` → phát hiện phạm vi 28/28 branch.
10. Kiểm tra cấu trúc JSON (chỉ keys, không in giá trị) để phân loại file thật vs. giả.
11. Kiểm tra `D:\DataFolder\ProjectIctu\DoAn\ictu_lecturers_20261010_090704.json` — **xác nhận tồn tại**, 560,352 bytes, sha256 đã ghi nhận nội bộ, không bị động tới.
12. `grep` tìm các chỗ code tham chiếu đường dẫn các file này — xác nhận chúng chỉ là **default output path** của script import/build (`backend/scripts/build_ictu_lecturer_dataset.py`, `validate_ictu_lecturer_dataset.py`), không phải import-time dependency. Gỡ khỏi Git tracking (giữ trên đĩa) sẽ không phá chức năng.
13. `gh pr list --state all` và `gh api .../actions/runs` → xác nhận có PR và CI run liên kết tới các nhánh chứa dữ liệu.
14. So sánh `git log origin/main..main -- data/lecturers/` → **trống**, xác nhận 46 commit cục bộ chưa push **không** chứa thay đổi nào tới các file dữ liệu này (an toàn, không có nguy cơ mang thêm dữ liệu nhạy cảm nếu các commit đó được xử lý sau).

**Không có thao tác ghi, push, rewrite, hay xoá nào được thực hiện trong phiên này.**

## 6. Đã gỡ khỏi HEAD remote hay chưa

**CHƯA.** Theo đúng mục 8 của yêu cầu, dừng lại ngay sau khi xác minh để trình phương án, vì phạm vi thực tế (28 branch + 29 PR) lớn hơn nhiều so với giả định ban đầu (chỉ HEAD của `main`) và cần quyết định của người dùng về trình tự xử lý trước khi push bất kỳ commit gỡ dữ liệu nào.

## 7. Dữ liệu còn truy xuất qua lịch sử

Có, chắc chắn còn, ở nhiều lớp:
- Qua chính các branch chứa file (28/28 nhánh hiện tại).
- Qua lịch sử commit của mỗi branch (commit `b6842d1` và mọi commit sau đó cho tới khi bị gỡ).
- Qua diff/cache của 29 Pull Request trên GitHub (tồn tại độc lập với trạng thái branch — xoá branch không tự xoá PR đã đóng khỏi giao diện GitHub).
- Qua bất kỳ fork hoặc clone bên ngoài — **không có khả năng kiểm tra từ phía Git/GitHub API thông thường**; không có thông tin cho thấy có fork, nhưng không thể loại trừ.

## 8. Các nhánh/tag/ref còn rủi ro

- **Tag:** không có tag nào trên remote (`git ls-remote --tags` trống) → không rủi ro từ tag.
- **Branch:** toàn bộ 28 branch hiện có trên remote đều chứa file dữ liệu thật (danh sách đầy đủ đã liệt kê ở mục 4, gồm các nhóm `completion1/*`, `completion2/*`, `completion3/*`, `m27*/*`, `m28/*`, `ci/*`).
- **Pull Request:** 29 PR liên kết tới các nhánh trên, bất kể trạng thái (closed/merged/draft) đều có thể còn hiển thị diff chứa dữ liệu trên giao diện GitHub.

## 9. Bảo toàn 46 commit, stash, database

Đã xác minh **không bị ảnh hưởng** và **không bị động tới** trong phiên này:
- 46 commit cục bộ chưa push trên `main` — còn nguyên, không rebase/reset/amend. Xác nhận các commit này không đụng tới `data/lecturers/`.
- 84 `refs/agents/*` — còn nguyên (đếm lại = 84).
- 2 stash — còn nguyên (`stash@{0}`, `stash@{1}`), không bị drop/pop.
- App DB (`scopus_ictu_app`), teacher DB, PostgreSQL — không có thao tác nào chạm tới, toàn bộ phiên này chỉ gọi `git`/`gh` read-only.
- File nguồn dữ liệu gốc bên ngoài repo (`ictu_lecturers_20261010_090704.json`) — còn nguyên, đã xác minh tồn tại và hash.

## 10. Kế hoạch loại dữ liệu khỏi lịch sử — CẦN PHÊ DUYỆT RIÊNG

Đây chỉ là đề xuất phương án, **chưa thực hiện**. Đề xuất gồm 2 giai đoạn tách biệt, mỗi giai đoạn cần phê duyệt riêng:

### Giai đoạn A — Gỡ khỏi HEAD hiện tại của từng nhánh đang hoạt động (nhanh, ít rủi ro)
- Phạm vi: chỉ các nhánh thực sự cần giữ sống (ví dụ `main`, và bất kỳ nhánh completion/milestone nào còn đang dùng cho công việc đang mở). Các nhánh CI-carrier/do-not-merge đã đóng PR có thể cân nhắc xoá hẳn khỏi remote (nếu người dùng xác nhận không còn cần) thay vì sửa.
- Với mỗi nhánh cần giữ: tạo bản clone/worktree cách ly từ đúng HEAD remote của nhánh đó, `git rm` 3 file rủi ro (+ tuỳ chọn file report), thêm rule `.gitignore`, commit tiếng Việt mô tả rõ, push fast-forward riêng nhánh đó.
- **Hạn chế đã biết:** Giai đoạn A chỉ ẩn dữ liệu khỏi cây file *hiện tại*; dữ liệu vẫn truy xuất được qua lịch sử commit cũ của mỗi nhánh. Đây là bước giảm thiểu tức thời, không phải khắc phục triệt để.

### Giai đoạn B — Loại khỏi lịch sử Git triệt để (rủi ro cao, cần kế hoạch riêng)
- Công cụ phù hợp: `git filter-repo` (theo khuyến nghị chính thức của GitHub, thay cho `filter-branch` đã lỗi thời) hoặc GitHub's "remove sensitive data" guide.
- **Vì đây sẽ viết lại lịch sử (thay đổi SHA mọi commit bị ảnh hưởng) trên một repo có 28 branch, 29 PR, và ít nhất 46 commit cục bộ chưa đồng bộ**, phạm vi ảnh hưởng gồm:
  - Mọi clone/fork hiện có sẽ lệch lịch sử với remote sau khi rewrite → cần force-push, cần mọi người cộng tác (nếu có) fetch lại từ đầu.
  - 46 commit cục bộ trên `main` đang xây trên các SHA cũ → sau rewrite sẽ cần rebase lại 46 commit đó lên lịch sử mới (rủi ro conflict, cần làm thủ công/có kiểm soát, không tự động).
  - 84 `refs/agents/*` và 2 stash tham chiếu tới các SHA hiện có — cần kiểm tra từng ref có trỏ tới commit bị rewrite không trước khi coi là an toàn.
  - GitHub có thể còn giữ cache nội bộ của các commit cũ trong một khoảng thời gian sau rewrite (ngoài khả năng kiểm soát của người dùng/Claude).
  - Không có khả năng xác minh hoặc kiểm soát fork/clone bên ngoài — **không thể khẳng định dữ liệu đã bị loại hoàn toàn khỏi Internet** chỉ bằng rewrite lịch sử trên remote chính.
- **Khuyến nghị thứ tự:** vì repo là PUBLIC, cách xử lý triệt để và chắc chắn nhất — nên được người dùng cân nhắc — là liên hệ GitHub Support để xoá cache/purge nội dung nhạy cảm theo quy trình chính thức của họ, *song song* với filter-repo + force-push có kiểm soát. Đây là quyết định của người dùng, không tự thực hiện.
- **KHÔNG tự thực hiện rewrite hoặc force-push trong bất kỳ trường hợp nào** cho tới khi có phê duyệt riêng, kèm xác nhận đã backup đầy đủ (clone bare, export refs/agents, export stash) trước khi bắt đầu.

## 11. Cảnh báo còn lại trước khi push công việc phát triển

1. **Tuyệt đối không push nhánh `main` cục bộ (46 commit ahead) trước khi hoàn tất xử lý dữ liệu** — nếu push trước, sẽ fast-forward remote `main` nhưng remote vẫn chứa file cũ trong lịch sử cho tới khi xử lý; không làm tăng rủi ro hiện tại nhưng cũng không giảm, và có thể làm phức tạp việc filter-repo sau này (phạm vi rewrite sẽ phải bao gồm cả 46 commit mới).
2. Việc gỡ file ở Giai đoạn A phải làm trên môi trường cách ly (worktree/clone riêng dựng từ remote HEAD), **không đụng vào `main` cục bộ** đang giữ 46 commit.
3. Trước khi push bất kỳ commit gỡ dữ liệu nào, cần xác nhận lại: remote HEAD chưa đổi so với `f49281802fe5d46fdc4e1ef872978b0cbaf73c4c` (người khác có thể đã push trong lúc chờ phê duyệt).
4. Sau khi xử lý Giai đoạn A, *không* merge/sync các nhánh đã xử lý trở lại worktree chính chứa 46 commit cục bộ trước khi có đối chiếu lịch sử rõ ràng, để tránh tái đưa dữ liệu lên qua merge.
5. `.gitignore` hiện tại **không có rule nào** cho `data/lecturers/*` — đây là nguyên nhân gốc của việc rò rỉ. Cần bổ sung rule chính xác (giữ `.example` nếu thay bằng dữ liệu giả thật sự, ignore `ictu_lecturers.json`, `ictu_lecturers.example.json`, `raw/*`, `reports/lecturer_dataset_report.json`) trước khi làm bất kỳ commit mới nào trong khu vực này.
6. Chưa xác minh được có fork/clone bên ngoài nào không — không có công cụ nào trong phiên này có thể trả lời chắc chắn câu hỏi đó.

---

**Việc tiếp theo cần người dùng quyết định (không tự triển khai):**
- (a) Phê duyệt Giai đoạn A — gỡ khỏi HEAD — và xác nhận phạm vi nhánh cần xử lý (chỉ `main`? hay toàn bộ 28 nhánh? hay xoá hẳn các nhánh CI-carrier đã đóng?).
- (b) Quyết định có tiến hành Giai đoạn B (filter-repo + force-push) hay không, và thời điểm.
- (c) Quyết định về 46 commit cục bộ: giữ chờ tiếp hay rebase sau khi lịch sử được viết lại.
- (d) Quyết định có liên hệ GitHub Support để purge cache không.

Dừng nhiệm vụ tại đây theo mục 8 của yêu cầu.
