# Báo cáo Giai đoạn 2: Hạn chế công khai & chuẩn bị làm sạch lịch sử

**Ngày:** 2026-10-12
**Tiếp nối:** [GITHUB_LECTURER_DATA_REMOVAL_20261012.md](./GITHUB_LECTURER_DATA_REMOVAL_20261012.md)
**Trạng thái:** DỪNG theo yêu cầu — chưa thực hiện rewrite hoặc force-push lên GitHub. Chỉ mô phỏng trên bản sao cách ly.

---

## 1. GitHub đã PRIVATE thành công chưa

**Có.** Đã xác minh hai lần qua `gh api repos/qhun22/Scopus-Ictu`:
- Trước: `"private": false, "visibility": "public"`
- Sau khi chuyển: `"private": true, "visibility": "private"`
- Xác minh lại độc lập (API call riêng, sau mọi thao tác khác trong phiên): `{"private":true,"visibility":"private"}`

Trước khi đổi, đã kiểm tra:
- Tài khoản `qhun22` có quyền `admin: true` trên repo.
- **0 fork**, **0 GitHub Pages**, **0 webhook**, **0 deploy key**.
- 1 workflow Actions (`CI`, state: active) — không bị chặn bởi private, chỉ bị tính vào giới hạn phút/tháng của GitHub Free cho repo private (không phải lỗi, chỉ là giới hạn sử dụng, không cần xử lý ngay).
- `main` không có branch protection — không có ràng buộc nào bị ảnh hưởng.

Không xoá repository, không xoá nhánh, không force-push trong bước này.

## 2. Các tác động do đổi visibility

- Repo có **1 stargazer, 1 watcher** ghi nhận tại thời điểm còn public — không có cách xác minh danh tính qua API thông thường (GitHub không công khai ai star/watch một repo đã chuyển private cho chủ sở hữu theo cách chi tiết hơn). Không suy luận thêm.
- 29 Pull Request (26 closed, 2 merged, một số draft) hiện vẫn tồn tại trên GitHub nhưng giờ chỉ xem được bởi chủ sở hữu/người có quyền truy cập repo private.
- Không phát hiện tác động nghiêm trọng nào khác (không Pages, không webhook, không tích hợp ngoài bị gãy).

## 3. Bản sao bảo toàn Git đã được xác minh chưa

**Có, đã tạo và xác minh toàn vẹn.** Vị trí (ngoài mọi thư mục Git-tracked):

```
D:\DataFolder\ProjectIctu\DoAn\_git_backup_lecturer_data_cleanup_20261012\
├── git_dir_full_backup\          ← bản sao nguyên trạng thư mục .git (copy trực tiếp, không qua clone)
└── sandbox_mirror_for_filter_repo\   ← bare mirror clone dùng để MÔ PHỔNG filter-repo (đã bị biến đổi có chủ đích)
```

**`git_dir_full_backup`** — xác minh khớp 100% với repo làm việc chính tại thời điểm sao lưu:
| Chỉ số | Giá trị |
|---|---|
| Tổng số ref | 220 (khớp) |
| Số `refs/agents/*` | 84 (khớp) |
| Số stash | 2 (khớp, đúng nội dung) |
| `main` HEAD | `a25737d3b4176e3321753288389d154acc500235` (khớp) |
| `origin/main` | `f49281802fe5d46fdc4e1ef872978b0cbaf73c4c` (khớp) |

**CẢNH BÁO BẢO MẬT:** `git_dir_full_backup` chứa đầy đủ chính dữ liệu giảng viên thật đang cần gỡ (vì nó là bản sao toàn bộ lịch sử trước xử lý). **Tuyệt đối không upload, không đẩy lên bất kỳ dịch vụ nào, không đưa vào thư mục có đồng bộ cloud, không chia sẻ.** Thư mục này chỉ nên tồn tại cục bộ, có kiểm soát truy cập như ổ đĩa hiện tại.

`sandbox_mirror_for_filter_repo` được clone từ `git_dir_full_backup` (không phải từ repo chính) để dùng riêng cho việc mô phỏng ở mục 4 — thư mục này **đã bị biến đổi có chủ đích** (đã chạy filter-repo thật trên đó để kiểm tra hiệu quả), không đại diện trạng thái gốc, cũng chứa dữ liệu thật ở các object chưa được xoá hẳn — áp dụng cảnh báo bảo mật tương tự.

Repo làm việc chính (`D:\...\Scopus-Ictu`) **không bị động tới**: đã xác minh lại `main` HEAD, stash list, agent ref count sau toàn bộ quá trình — tất cả khớp với trạng thái ban đầu.

## 4. Phạm vi thực tế của việc làm sạch lịch sử

Đã **thực sự chạy** `git filter-repo --invert-paths` (không phải chỉ đọc tài liệu) trên `sandbox_mirror_for_filter_repo` để đo lường chính xác tác động, với 4 file:
- `data/lecturers/ictu_lecturers.json`
- `data/lecturers/ictu_lecturers.example.json`
- `data/lecturers/raw/ictu_lecturers_archive_snapshot.html`
- `data/lecturers/reports/lecturer_dataset_report.json`

**Kết quả đo được:**

| Chỉ số | Trước | Sau |
|---|---|---|
| Tổng số ref (toàn bộ `.git`, gồm cả ref nội bộ công cụ) | 220 | 188 (giảm 32 — xem giải thích dưới) |
| `refs/agents/*` | 84 | **84 (bảo toàn 100%)** |
| `refs/heads/*` (28 nhánh remote) | — | **Bảo toàn 100%, sạch dữ liệu 100%** (đã quét từng branch bằng rev-list, xác nhận 0 rò rỉ) |
| Commit nào còn chứa file qua `git log --all` | 22 commit (trước) | 0 commit |
| Số nhánh remote có SHA tip bị đổi | — | 28/28 (toàn bộ, vì mọi nhánh đều chứa file ở đâu đó trong lịch sử của nó → rewrite domino tới toàn bộ commit con) |

**Phát hiện kỹ thuật quan trọng — rò rỉ còn sót, nhưng KHÔNG ảnh hưởng GitHub:**
Sau khi chạy `git gc --prune=now --aggressive`, kiểm tra bằng `git rev-list --objects` + quét thủ công từng ref, phát hiện blob/tree dữ liệu thật **vẫn reachable từ 24 ref thuộc namespace `refs/codex/turn-diffs/checkpoints/*`**. Đây là ref checkpoint nội bộ của một công cụ agent chạy cục bộ trên máy (có cấu trúc trỏ trực tiếp tới `tree` object thay vì `commit`, khiến filter-repo bỏ qua — log có ghi "unexpected object of type tree, skipping").

**Đã xác minh bằng `git ls-remote origin | grep codex`** → **0 kết quả**. Namespace `refs/codex/*` **không tồn tại và chưa từng được push lên GitHub remote** (tổng remote chỉ có 69 ref, toàn bộ là `refs/heads/*` và `refs/pull/*` thông thường). Do đó rò rỉ này là **cục bộ, không ảnh hưởng tới mục tiêu làm sạch GitHub**, nhưng cần xử lý riêng (xoá các ref checkpoint đó hoặc dùng tùy chọn filter-repo phù hợp hơn) nếu muốn máy cục bộ hoàn toàn sạch — việc này **chưa làm** và cần quyết định riêng vì các ref này có thể là checkpoint công việc của một agent khác, không nên xoá tuỳ tiện.

### Những nhánh nào bị thay đổi lịch sử
Toàn bộ 28/28 remote branch hiện có (`main`, `completion1/*`, `completion2/*`, `completion3/*`, `m27*/*`, `m28/*`, `ci/*`) — vì mỗi nhánh đều chứa file dữ liệu ở một thời điểm nào đó trong lịch sử của nó, filter-repo phải viết lại từ commit gốc chứa file (`b6842d1`, 2026-10-03) cho tới tip của mỗi nhánh.

### Những commit nào đổi SHA
22 commit gốc từng chạm trực tiếp vào 4 file, cộng với **mọi commit con sau đó trên mỗi nhánh** (hiệu ứng domino bắt buộc của Git — đổi một commit tổ tiên luôn đổi SHA toàn bộ commit con). Đo cụ thể trên nhánh `main` phía remote: tổng 74 commit nằm trong chuỗi tổ tiên của `origin/main`, tất cả nằm trong vùng ảnh hưởng kể từ `b6842d1`.

### Số Pull Request thực sự bị ảnh hưởng
Cả 29 PR đã liệt kê ở báo cáo Giai đoạn 1 đều có head branch nằm trong 28 nhánh bị rewrite → **toàn bộ 29 PR bị ảnh hưởng** (SHA trong diff/commit list của PR sẽ không còn khớp sau khi force-push nhánh đã rewrite; một số PR closed/merged có thể hiển thị cảnh báo "commit not found" hoặc giữ nguyên nội dung cache cũ trên GitHub — xem mục 6).

## 5. Kế hoạch chính xác để gỡ dữ liệu khỏi tất cả nhánh cần thiết

**Đề xuất, CHƯA THỰC HIỆN trên repo chính hoặc remote:**

### Bước 1 — Chuẩn bị (đã hoàn tất trong phiên này)
- ✅ Backup `.git` đầy đủ, đã xác minh toàn vẹn.
- ✅ Mô phỏng filter-repo trên sandbox, đã đo chính xác phạm vi.
- ✅ Xác nhận repo chính và 46 commit cục bộ không bị động.

### Bước 2 — Quyết định phạm vi nhánh (CẦN BẠN CHỌN)
- Phương án 2a: Chỉ làm sạch `main` + các nhánh completion/milestone còn cần giữ, **xoá hẳn** các nhánh CI-carrier/do-not-merge đã đóng PR (nếu xác nhận không còn cần) để giảm phạm vi rewrite.
- Phương án 2b: Làm sạch toàn bộ 28 nhánh hiện có, không xoá nhánh nào.

### Bước 3 — Thực hiện trên bản sao cách ly mới (không phải sandbox đã dùng, vì sandbox đã bị biến đổi và còn sót ref `refs/codex/*`)
1. Tạo mirror clone mới từ remote GitHub (private) hiện tại — **không dùng lại sandbox cũ**.
2. Chạy `git filter-repo --invert-paths` với đúng 4 đường dẫn, **loại trừ việc xử lý `refs/codex/*`** (mirror clone mới từ remote sẽ không có namespace này vì nó không tồn tại trên remote — đã xác minh ở mục 4).
3. Xác minh lại bằng đúng quy trình đã dùng trong phiên này (`git rev-list --objects` quét từng `refs/heads/*`) — đảm bảo 0 rò rỉ trên mọi nhánh trước khi push.
4. Review diff/log một lần nữa, xác nhận không có thay đổi ngoài ý muốn.

### Bước 4 — Push có kiểm soát (CẦN PHÊ DUYỆT RIÊNG TRƯỚC KHI CHẠY)
- `git push --force` cho từng nhánh đã làm sạch — đây **là force-push bắt buộc** vì SHA đã đổi toàn bộ; không có cách tránh force-push ở bước này.
- Phải thực hiện **sau khi** xác nhận không ai khác đang có PR mở dựa trên nhánh đó (hoặc đã thông báo), vì force-push làm lệch lịch sử với bất kỳ clone/fork khác.

### Bước 5 — Đồng bộ 46 commit cục bộ (CẦN PHÊ DUYỆT RIÊNG)
Sau khi `main` trên remote được force-push với lịch sử mới (SHA đổi từ `b6842d1` trở đi), `main` cục bộ (đang có 46 commit xây trên lịch sử cũ `a25737d`) sẽ **không còn là fast-forward** của remote mới. Cần:
- `git rebase --onto <new-remote-main> <old-b6842d1-parent> main` để chuyển 46 commit cục bộ sang nền lịch sử mới, **có khả năng xảy ra conflict** nếu bất kỳ commit nào trong 46 commit đó từng sửa cùng vùng `data/lecturers/` (đã xác minh ở báo cáo Giai đoạn 1: **0 commit cục bộ đụng tới `data/lecturers/`** → rủi ro conflict trên chính các file dữ liệu là không có, nhưng vẫn cần rebase thủ công có kiểm soát, không tự động).
- Việc rebase này **chưa thực hiện** và cần lệnh riêng, có xác nhận từng bước.

## 6. Các vấn đề cần GitHub Support

- GitHub có thể lưu cache nội bộ (CDN, search index, PR diff snapshot) của các commit cũ trong một khoảng thời gian sau force-push, ngoài khả năng xoá trực tiếp qua API/git thông thường.
- Khuyến nghị: sau khi hoàn tất force-push làm sạch, liên hệ GitHub Support (qua https://support.github.com, mục "remove sensitive data") để yêu cầu purge cache/index cho các SHA cũ đã liệt kê, đặc biệt vì repo từng ở trạng thái PUBLIC và có 1 star/watch ghi nhận.
- Đây là quyết định và hành động của người dùng (cần tài khoản GitHub xác thực chủ sở hữu) — Claude không có khả năng tự liên hệ GitHub Support.

## 7. Cách giữ nguyên thành quả 46 commit

Trong suốt phiên này: **46 commit cục bộ hoàn toàn không bị động tới** — chỉ có repo chính được đọc (`git rev-parse`, `git log`), không có `reset`/`rebase`/`amend` nào chạy trên `D:\...\Scopus-Ictu\.git`. Mọi thao tác biến đổi (filter-repo, gc, reflog expire) chỉ chạy trên `sandbox_mirror_for_filter_repo` — một bare clone tách biệt hoàn toàn.

Kế hoạch dài hạn để giữ 46 commit sau khi rewrite lịch sử remote: xem Bước 5 ở mục 5 (rebase có kiểm soát, cần phê duyệt riêng, rủi ro conflict thấp vì các commit này không đụng `data/lecturers/`).

## 8. Những quyết định còn cần bạn duyệt trước khi thực sự viết lại lịch sử

1. **Phạm vi nhánh**: làm sạch toàn bộ 28 nhánh (phương án 2b), hay xoá trước một số nhánh CI-carrier đã đóng để giảm phạm vi (phương án 2a)?
2. **Thời điểm force-push**: ngay sau khi có phê duyệt, hay sau khi hoàn tất các việc đang chờ khác (thu thập affiliation, LECTURER account, v.v. — các việc này vẫn đang dừng theo đúng yêu cầu)?
3. **Có liên hệ GitHub Support để purge cache không**, và ai sẽ thực hiện (cần xác thực chủ sở hữu, Claude không thể tự làm)?
4. **Xử lý 24 ref cục bộ `refs/codex/turn-diffs/*`** còn sót dữ liệu sau filter-repo trên sandbox — có cần dọn sạch máy cục bộ luôn không, hay để nguyên vì không ảnh hưởng GitHub và có thể là checkpoint của agent khác đang cần?
5. **Thứ tự rebase 46 commit cục bộ** — thực hiện ngay sau force-push, hay để sau?
6. **`.gitignore`** — bổ sung rule cho `data/lecturers/*` ở nhánh nào trước: chỉ `main` sau khi rewrite, hay cả các nhánh completion/milestone đang mở?

---

**Tổng kết trạng thái cuối phiên (đã xác minh lại ngay trước khi kết thúc):**
- Repository: PRIVATE ✅
- Repo chính (`D:\...\Scopus-Ictu`): `main` = `a25737d`, 46 ahead, 2 stash, 84 agent refs — **không đổi** ✅
- Backup Git đầy đủ: đã tạo, đã xác minh toàn vẹn, nằm ngoài vùng Git-tracked ✅
- Rewrite/force-push lên GitHub: **chưa thực hiện, đúng theo yêu cầu dừng** ✅
