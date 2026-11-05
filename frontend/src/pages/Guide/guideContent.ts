// Nội dung trang Hướng dẫn. Soạn theo giao diện thật; tên menu/nút phải khớp `src/i18n/locales/*`.
// Chỉnh nội dung ở đây, không sửa trang hiển thị.

export type GuideRole = "GUEST" | "LECTURER" | "REVIEWER" | "ADMIN";

export type GuideBlock =
  | { kind: "p"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "steps"; items: string[] }
  | { kind: "table"; head: string[]; rows: string[][] }
  | { kind: "code"; text: string }
  | { kind: "note"; tone: "info" | "warn"; text: string };

export interface GuideSection {
  id: string;
  title: string;
  /** Vai trò nhìn thấy mục này. */
  roles: GuideRole[];
  blocks: GuideBlock[];
}

const ALL: GuideRole[] = ["GUEST", "LECTURER", "REVIEWER", "ADMIN"];

const vi: GuideSection[] = [
  {
    id: "overview",
    title: "Hệ thống làm gì",
    roles: ALL,
    blocks: [
      {
        kind: "p",
        text:
          "Scopus ICTU quản lý hồ sơ tác giả và công bố khoa học từ Scopus phục vụ Trường ĐH Công nghệ thông tin và Truyền thông. " +
          "Hệ thống nhập tệp CSV xuất từ Scopus, chuẩn hoá công bố, tìm đơn vị công tác của từng tác giả, " +
          "rồi gợi ý tác giả Scopus nào tương ứng với giảng viên nào để người có thẩm quyền duyệt.",
      },
      {
        kind: "note",
        tone: "info",
        text:
          "Hệ thống không bao giờ tự khẳng định một tác giả là giảng viên chỉ vì tên giống nhau. " +
          "Mọi liên kết đều cần người duyệt xem căn cứ và quyết định; thiếu căn cứ thì nằm trong danh sách chờ xác minh.",
      },
    ],
  },
  {
    id: "roles",
    title: "Vai trò và quyền",
    roles: ALL,
    blocks: [
      {
        kind: "table",
        head: ["Vai trò", "Làm được gì", "Trang"],
        rows: [
          ["Khách (chưa đăng nhập)", "Xem công bố công khai, chi tiết công bố, tra cứu tác giả", "Trang chủ, Công bố, Tra cứu tác giả"],
          ["Giảng viên", "Xem công bố và định danh Scopus đã được duyệt của chính mình (chỉ đọc)", "Công bố của tôi, Liên kết Scopus, Hồ sơ cá nhân"],
          ["Người duyệt", "Duyệt các cặp giảng viên – tác giả Scopus", "Duyệt đối sánh, Lịch sử duyệt"],
          ["Quản trị (ADMIN)", "Toàn bộ: nhập dữ liệu, chuẩn hoá, thu thập đơn vị, người dùng, nhật ký, xuất dữ liệu", "Tất cả các mục trong menu"],
        ],
      },
      {
        kind: "p",
        text:
          "Ghi chú nội bộ của quản trị, nguồn dữ liệu gốc và danh sách liên kết nội bộ chỉ ADMIN nhìn thấy. " +
          "Tài khoản do ADMIN tạo; hệ thống không có đăng ký công khai.",
      },
    ],
  },
  {
    id: "lecturer",
    title: "Dành cho giảng viên",
    roles: ["LECTURER"],
    blocks: [
      {
        kind: "list",
        items: [
          "Công bố của tôi: các công bố đã được gắn với bạn. Bấm một dòng để xem số tác giả và đơn vị từng tác giả.",
          "Liên kết Scopus: các mã Scopus Author ID đã được phê duyệt cho hồ sơ của bạn, cùng bằng chứng.",
          "Hồ sơ cá nhân: thông tin hồ sơ giảng viên được liên kết với tài khoản của bạn.",
        ],
      },
      {
        kind: "note",
        tone: "info",
        text:
          "Nếu thấy \"Tài khoản chưa được liên kết với hồ sơ giảng viên\" hoặc thiếu công bố, hãy liên hệ quản trị viên. " +
          "Giảng viên không tự sửa được liên kết.",
      },
    ],
  },
  {
    id: "reviewer",
    title: "Dành cho người duyệt",
    roles: ["REVIEWER", "ADMIN"],
    blocks: [
      {
        kind: "steps",
        items: [
          "Vào Duyệt đối sánh. Mỗi dòng là một cặp \"giảng viên – tác giả Scopus\" do hệ thống đề xuất.",
          "Mở chi tiết cặp để xem căn cứ (tên, công bố chung, đơn vị ICTU) và mức phù hợp (Cao, Vừa, Thấp, Chưa đủ căn cứ).",
          "Bấm Chấp nhận hoặc Từ chối. Khi chỉ có bằng chứng tên, tác giả dùng chung, hoặc nhiều đề xuất cho một giảng viên, hệ thống bắt buộc nhập lý do.",
          "Quyết định được ghi vào Lịch sử duyệt. Cặp đã từ chối có thể Mở lại để xét lại; việc Thu hồi một cặp đã chấp nhận do quản trị viên thực hiện.",
        ],
      },
      {
        kind: "note",
        tone: "warn",
        text: "Hai tên giống nhau chưa đủ để chấp nhận. Chỉ chấp nhận khi có thêm căn cứ, ví dụ công bố có đơn vị ICTU hoặc trùng mã định danh.",
      },
    ],
  },
  {
    id: "workflow",
    title: "Quy trình xử lý dữ liệu (ADMIN)",
    roles: ["ADMIN"],
    blocks: [
      { kind: "p", text: "Làm đúng thứ tự; bước sau cần kết quả của bước trước." },
      {
        kind: "steps",
        items: [
          "Nhập dữ liệu → ô Tải tệp Giảng viên: chọn tệp .json, xem kết quả kiểm tra rồi Xác nhận nhập.",
          "Nhập dữ liệu → ô Tải tệp Scopus: kéo thả tệp .csv (tối đa 20 MB). Hệ thống báo lỗi theo từng dòng và từ chối tệp trùng nội dung. Có thể Hủy tiến trình; dữ liệu đã ghi được giữ để truy vết.",
          "Chuẩn hóa công bố: chuyển dòng thô thành công bố chuẩn, gộp trùng theo mã EID, không ghi đè dữ liệu gốc.",
          "Đơn vị tác giả → mục 3 Bắt đầu thu thập trực tuyến (tra OpenAlex, Crossref, ORCID theo DOI; chạy nền, tạm dừng và tiếp tục được) → mục 4 Xem trước (chỉ tính thử) → Xác nhận áp dụng.",
          "Đơn vị tác giả → mục 5 Rà soát và hiệu chỉnh thủ công: lọc Chưa có đơn vị, Nguồn mâu thuẫn, Chỉ đối chiếu chưa xác minh; thêm, sửa, thu hồi đơn vị kèm nguồn và lý do.",
          "Đối sánh dữ liệu → Tạo danh sách đề xuất. Chạy lại an toàn, không ghi đè quyết định đã duyệt.",
          "Duyệt đối sánh (xem mục dành cho người duyệt).",
        ],
      },
      {
        kind: "note",
        tone: "warn",
        text:
          "Làm bước thu thập đơn vị (4) trước bước tạo đề xuất (6). Quy tắc \"cùng từ, khác thứ tự\" chỉ giữ cặp khi tác giả có ít nhất một bài ghi đơn vị ICTU; " +
          "nếu chưa thu thập đơn vị, các cặp đó bị loại mà không báo.",
      },
    ],
  },
  {
    id: "export",
    title: "Xem, thống kê và xuất dữ liệu",
    roles: ["ADMIN"],
    blocks: [
      {
        kind: "list",
        items: [
          "Tổng quan: số công bố, giảng viên, tác giả, độ phủ đơn vị, các cặp chờ duyệt.",
          "Công bố: lọc theo năm, loại, giai đoạn, mở truy cập, thiếu DOI, Scopus ID. Mở một bài để xem có mấy tác giả và từng tác giả thuộc đơn vị nào.",
          "Nút Xuất JSON và Xuất CSV ở trang Công bố: mỗi tác giả một dòng kèm đơn vị, mức tin cậy và nguồn. CSV có 16 cột, mã hoá UTF-8 có BOM, mở được bằng Excel.",
          "Đơn vị tác giả → lọc Chưa có đơn vị: danh sách vị trí chưa tìm được đơn vị kèm lý do; cũng xuất được CSV.",
        ],
      },
    ],
  },
  {
    id: "recover",
    title: "Sửa nhầm và phục hồi trong ứng dụng",
    roles: ["REVIEWER", "ADMIN"],
    blocks: [
      {
        kind: "table",
        head: ["Tình huống", "Cách xử lý"],
        rows: [
          ["Chấp nhận nhầm một cặp", "Quản trị viên: Duyệt đối sánh → Thu hồi (kèm lý do)"],
          ["Từ chối nhầm một cặp", "Người duyệt hoặc quản trị: Mở lại để xét lại"],
          ["Nhập nhầm danh sách giảng viên", "Nhập dữ liệu → Chi tiết đợt nhập → hoàn tác (rollback)"],
          ["Nhập nhầm tệp Scopus", "Hủy tiến trình khi đang chạy; đợt đã ẩn khỏi lịch sử có thể khôi phục lại"],
          ["Cần xem ai đã làm gì", "Nhật ký hệ thống (ADMIN) hoặc Lịch sử duyệt"],
        ],
      },
      {
        kind: "p",
        text:
          "Dữ liệu gốc từ Scopus luôn được giữ nguyên ở bảng riêng, không bị ghi đè khi chuẩn hoá. " +
          "Hiện chưa có nút hoàn tác chuẩn hoá công bố; muốn quay về trạng thái trước chuẩn hoá phải khôi phục từ bản sao lưu.",
      },
    ],
  },
  {
    id: "backup",
    title: "Sao lưu và phục hồi cơ sở dữ liệu (ADMIN)",
    roles: ["ADMIN"],
    blocks: [
      {
        kind: "p",
        text: "Công cụ có sẵn: backend/scripts/db_backup.py. Chạy từ thư mục backend/ của máy chủ, không chạy từ trình duyệt.",
      },
      { kind: "code", text: "python -m scripts.db_backup backup\npython -m scripts.db_backup verify  --dump <tệp .dump>\npython -m scripts.db_backup restore --dump <tệp .dump> --into <TEN_DATABASE_MOI>" },
      {
        kind: "list",
        items: [
          "backup: tạo tệp .dump, tệp băm .sha256 và .manifest.json; rồi khôi phục thử vào database tạm để chứng minh dùng được, và xoá database tạm. Thêm --no-verify để bỏ bước thử.",
          "verify: kiểm tra băm và khôi phục thử một bản sao lưu có sẵn.",
          "restore: luôn đi vào một database MỚI; không bao giờ ghi đè database đang chạy. Muốn thay thế, khôi phục sang database mới, kiểm tra, rồi đổi DB_NAME trong cấu hình và khởi động lại backend.",
        ],
      },
      {
        kind: "note",
        tone: "warn",
        text:
          "Sao lưu trước mỗi lần nâng cấp cấu trúc dữ liệu, cất bản sao lưu ngoài thư mục mã nguồn, không đưa lên Git (có dữ liệu giảng viên). " +
          "Bản sao lưu chưa chạy verify chưa được coi là đã chứng minh khôi phục được.",
      },
    ],
  },
  {
    id: "trouble",
    title: "Sự cố thường gặp (ADMIN)",
    roles: ["ADMIN"],
    blocks: [
      {
        kind: "table",
        head: ["Hiện tượng", "Nguyên nhân và cách xử lý"],
        rows: [
          ["Tải CSV bị từ chối vì trùng", "Cùng nội dung tệp đã nhập (so SHA-256). Đúng thiết kế; xem đợt nhập cũ."],
          ["Báo lỗi ở một số dòng", "Dòng thiếu trường hoặc sai định dạng. Xem bảng lỗi theo dòng, sửa tệp nguồn, tải lại."],
          ["Đề xuất ghép ít hơn mong đợi", "Chưa thu thập đơn vị trước khi tạo đề xuất. Làm bước thu thập đơn vị rồi tạo lại."],
          ["Bị đăng xuất đột ngột", "Tài khoản bị khoá, bị đặt lại mật khẩu hoặc hệ thống vừa được Reset. Đăng nhập lại."],
          ["Mở CSV bằng Excel bị vỡ chữ", "Dùng Dữ liệu → Từ văn bản/CSV và chọn UTF-8 (tệp đã có BOM)."],
          ["Nút Reset hệ thống", "Chỉ có tác dụng khi môi trường là local hoặc dev; gõ ICTU để xác nhận; xoá dữ liệu, giữ tài khoản ADMIN. Không dùng trên bản thật."],
        ],
      },
    ],
  },
];

const en: GuideSection[] = [
  {
    id: "overview",
    title: "What the system does",
    roles: ALL,
    blocks: [
      {
        kind: "p",
        text:
          "Scopus ICTU manages Scopus author profiles and publications for the University of Information and Communication Technology. " +
          "It imports Scopus CSV exports, normalizes publications, finds each author's affiliations, " +
          "and suggests which Scopus author matches which lecturer for an authorized person to review.",
      },
      {
        kind: "note",
        tone: "info",
        text:
          "The system never concludes that an author is a lecturer just because the names look alike. " +
          "Every link needs a reviewer to check the evidence and decide; anything without enough evidence waits in the pending list.",
      },
    ],
  },
  {
    id: "roles",
    title: "Roles and permissions",
    roles: ALL,
    blocks: [
      {
        kind: "table",
        head: ["Role", "What it can do", "Pages"],
        rows: [
          ["Guest (not signed in)", "View public publications, publication details, author lookup", "Home, Publications, Author Lookup"],
          ["Lecturer", "View own publications and approved Scopus identities (read-only)", "My Publications, Scopus Identity, My Profile"],
          ["Reviewer", "Review lecturer – Scopus author pairs", "Review Matches, Review Log"],
          ["Administrator (ADMIN)", "Everything: import, normalization, affiliation collection, users, audit log, export", "All menu items"],
        ],
      },
      {
        kind: "p",
        text:
          "Internal admin notes, raw source data and the internal link list are visible to ADMIN only. " +
          "Accounts are created by ADMIN; there is no public sign-up.",
      },
    ],
  },
  {
    id: "lecturer",
    title: "For lecturers",
    roles: ["LECTURER"],
    blocks: [
      {
        kind: "list",
        items: [
          "My Publications: publications linked to you. Open a row to see the number of authors and each author's affiliation.",
          "Scopus Identity: Scopus Author IDs approved for your profile, with the evidence.",
          "My Profile: the lecturer profile information linked to your account.",
        ],
      },
      {
        kind: "note",
        tone: "info",
        text:
          "If you see \"Your account is not linked to a lecturer profile\" or publications are missing, contact an administrator. " +
          "Lecturers cannot edit links themselves.",
      },
    ],
  },
  {
    id: "reviewer",
    title: "For reviewers",
    roles: ["REVIEWER", "ADMIN"],
    blocks: [
      {
        kind: "steps",
        items: [
          "Open Review Matches. Each row is a \"lecturer – Scopus author\" pair suggested by the system.",
          "Open the pair's details to see the evidence (name, shared publications, ICTU affiliation) and the fit level (High, Medium, Low, Not enough evidence).",
          "Click Accept or Reject. When the evidence is name-only, the Scopus author is shared, or several suggestions exist for one lecturer, a reason is required.",
          "Decisions are recorded in the Review Log. A rejected pair can be Reopened for another look; revoking an accepted pair is done by an administrator.",
        ],
      },
      {
        kind: "note",
        tone: "warn",
        text: "Two identical names are not enough to accept. Accept only with additional evidence, such as a paper with an ICTU affiliation or a matching identifier.",
      },
    ],
  },
  {
    id: "workflow",
    title: "Data processing workflow (ADMIN)",
    roles: ["ADMIN"],
    blocks: [
      { kind: "p", text: "Follow the order; each step needs the result of the previous one." },
      {
        kind: "steps",
        items: [
          "Data Import → Lecturer file box: choose a .json file, review the check result, then Confirm import.",
          "Data Import → Scopus file box: drop a .csv (max 20 MB). The system reports errors per row and rejects files with duplicate content. You can cancel the run; data already written is kept for traceability.",
          "Normalize publications: turns raw rows into canonical publications, merges duplicates by EID, never overwrites raw data.",
          "Author Affiliations → section 3 Start online collection (looks up OpenAlex, Crossref, ORCID by DOI; runs in the background, can pause and resume) → section 4 Preview (dry run) → Confirm apply.",
          "Author Affiliations → section 5 Manual review: filter No affiliation, Conflicting sources, Matched only (unverified); add, edit or revoke affiliations with source and reason.",
          "Data Matching → Generate suggestion list. Safe to re-run; it never overwrites decisions already made.",
          "Review Matches (see the reviewer section).",
        ],
      },
      {
        kind: "note",
        tone: "warn",
        text:
          "Collect affiliations (step 4) before generating suggestions (step 6). The \"same words, different order\" rule keeps a pair only when the author has at least one paper with an ICTU affiliation; " +
          "without affiliations those pairs are dropped silently.",
      },
    ],
  },
  {
    id: "export",
    title: "Browse, statistics and export",
    roles: ["ADMIN"],
    blocks: [
      {
        kind: "list",
        items: [
          "Dashboard: counts of publications, lecturers, authors, affiliation coverage, pending pairs.",
          "Publications: filter by year, type, period, open access, missing DOI, Scopus ID. Open one to see how many authors it has and each author's affiliation.",
          "Export JSON and Export CSV on the Publications page: one row per author with affiliation, confidence level and source. The CSV has 16 columns, UTF-8 with BOM, and opens in Excel.",
          "Author Affiliations → filter No affiliation: positions without a found affiliation, with the reason; also exportable as CSV.",
        ],
      },
    ],
  },
  {
    id: "recover",
    title: "Fixing mistakes inside the app",
    roles: ["REVIEWER", "ADMIN"],
    blocks: [
      {
        kind: "table",
        head: ["Situation", "What to do"],
        rows: [
          ["A pair was accepted by mistake", "Administrator: Review Matches → Revoke (with a reason)"],
          ["A pair was rejected by mistake", "Reviewer or administrator: Reopen to look again"],
          ["Wrong lecturer list imported", "Data Import → import Details → roll back"],
          ["Wrong Scopus file imported", "Cancel while running; an import hidden from history can be restored"],
          ["Who did what", "Audit Log (ADMIN) or Review Log"],
        ],
      },
      {
        kind: "p",
        text:
          "Raw Scopus data is always kept in separate tables and never overwritten by normalization. " +
          "There is no one-click undo for publication normalization yet; to return to the pre-normalization state, restore from a backup.",
      },
    ],
  },
  {
    id: "backup",
    title: "Database backup and restore (ADMIN)",
    roles: ["ADMIN"],
    blocks: [
      {
        kind: "p",
        text: "Built-in tool: backend/scripts/db_backup.py. Run it from the server's backend/ folder, not from the browser.",
      },
      { kind: "code", text: "python -m scripts.db_backup backup\npython -m scripts.db_backup verify  --dump <file .dump>\npython -m scripts.db_backup restore --dump <file .dump> --into <NEW_DATABASE>" },
      {
        kind: "list",
        items: [
          "backup: writes the .dump, a .sha256 checksum and a .manifest.json; then test-restores into a temporary database to prove it works, and drops that database. Add --no-verify to skip the test.",
          "verify: checks the hash and test-restores an existing backup.",
          "restore: always goes into a NEW database; the running database is never overwritten. To replace it, restore into a new database, check it, then change DB_NAME in the configuration and restart the backend.",
        ],
      },
      {
        kind: "note",
        tone: "warn",
        text:
          "Back up before every schema upgrade, keep backups outside the source folder, and never commit them to Git (they contain lecturer data). " +
          "A backup that has not been verified is not proven restorable.",
      },
    ],
  },
  {
    id: "trouble",
    title: "Common problems (ADMIN)",
    roles: ["ADMIN"],
    blocks: [
      {
        kind: "table",
        head: ["Symptom", "Cause and fix"],
        rows: [
          ["CSV rejected as duplicate", "Same file content was already imported (SHA-256). By design; check earlier imports."],
          ["Errors on some rows", "A row is missing a field or has a bad format. Check the per-row error table, fix the source file, upload again."],
          ["Fewer suggestions than expected", "Affiliations were not collected before generating suggestions. Collect affiliations, then generate again."],
          ["Suddenly signed out", "Account locked, password reset, or the system was just reset. Sign in again."],
          ["CSV looks garbled in Excel", "Use Data → From Text/CSV and choose UTF-8 (the file already has a BOM)."],
          ["System Reset button", "Works only when the environment is local or dev; type ICTU to confirm; wipes data, keeps ADMIN accounts. Never use on a real deployment."],
        ],
      },
    ],
  },
];

export const GUIDE_CONTENT: Record<"vi" | "en", GuideSection[]> = { vi, en };
