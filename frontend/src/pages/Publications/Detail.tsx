import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { getPublicationByEid } from "../../api/publications";
import { PublicationDetailResponse } from "../../types/publication";
import { useI18n } from "../../i18n";

const NULL_YEAR = "Chưa rõ";
const NULL_CITATION = "Chưa có dữ liệu";
const NULL_STRING = "Chưa cập nhật";

export default function PublicationDetailPage() {
  const navigate = useNavigate();
  const { eid } = useParams<{ eid: string }>();
  const { locale } = useI18n();

  const [publication, setPublication] = useState<PublicationDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAllProvenance, setShowAllProvenance] = useState(false);

  // ── Generation counter for stale-request guard ──────────────────────────
  const genRef = useRef(0);

  const fetchDetail = useCallback(async () => {
    if (!eid) return;

    const currentGen = ++genRef.current;

    setLoading(true);
    setError(null);

    try {
      const data = await getPublicationByEid(eid);
      // Guard: only commit state if this request is still the latest
      if (currentGen !== genRef.current) return;
      setPublication(data);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      if (currentGen !== genRef.current) return;

      if (err instanceof ApiError && err.status === 404) {
        setError(
          locale === "vi"
            ? "Không tìm thấy công bố này."
            : "Publication not found.",
        );
      } else {
        setError(
          err instanceof ApiError
            ? getApiErrorMessage(err)
            : (locale === "vi"
              ? "Không thể tải thông tin công bố. Vui lòng thử lại."
              : "Unable to load publication details. Please try again."),
        );
      }
    } finally {
      if (currentGen !== genRef.current) return;
      setLoading(false);
    }
  }, [eid, locale]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  // ── Display helpers ──────────────────────────────────────────────────────
  const fmtField = (v: string | null | undefined): string =>
    (v === null || v === undefined || v === "") ? NULL_STRING : v;

  const fmtYear = (y: number | null | undefined): string =>
    (y === null || y === undefined) ? NULL_YEAR : String(y);

  const fmtCitations = (c: number | null | undefined): string => {
    if (c === null || c === undefined) return NULL_CITATION;
    return String(c);
  };

  const fmtProvenanceDate = (iso: string): string => {
    try {
      return new Date(iso).toLocaleString("vi-VN", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  // ── Labels ────────────────────────────────────────────────────────────────
  const backLabel = locale === "vi" ? "← Quay lại danh sách công bố" : "← Back to publications list";
  const sectionMeta = locale === "vi" ? "Thông tin công bố" : "Publication Metadata";
  const sectionAuthors = locale === "vi" ? "Danh sách tác giả (Scopus)" : "Scopus Authors";
  const sectionLinks = locale === "vi" ? "Liên kết giảng viên ICTU" : "Approved ICTU Lecturer Links";
  const sectionProvenance = locale === "vi" ? "Nguồn dữ liệu & truy vết" : "Data Provenance";
  const loadingLabel = locale === "vi" ? "Đang tải thông tin công bố..." : "Loading publication details...";
  const retryLabel = locale === "vi" ? "Thử lại" : "Retry";
  const colAuthorOrder = locale === "vi" ? "STT" : "#";
  const colScopusId = "Scopus ID";
  const colName = locale === "vi" ? "Tên ưu tiên" : "Preferred Name";
  const colStaffCode = locale === "vi" ? "Mã cán bộ" : "Staff Code";
  const colDepartment = locale === "vi" ? "Khoa / Bộ môn" : "Faculty / Dept";
  const colFaculty = locale === "vi" ? "Khoa" : "Faculty";
  const colOrcid = "ORCID";
  const colFileName = locale === "vi" ? "Tên tệp" : "File Name";
  const colRowNum = locale === "vi" ? "Dòng" : "Row";
  const colImportedAt = locale === "vi" ? "Thời gian nhập" : "Imported At";
  const colSha256 = "SHA-256";

  const emptyAuthorsLabel = locale === "vi"
    ? "Không có dữ liệu tác giả."
    : "No author data available.";
  const emptyLinksLabel = locale === "vi"
    ? "Chưa có liên kết giảng viên được phê duyệt."
    : "No approved lecturer links yet.";
  const emptyProvenanceLabel = locale === "vi"
    ? "Không có dữ liệu truy vết."
    : "No provenance data available.";

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-slate-400">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-[#3A5FC3]" />
          <span className="text-sm">{loadingLabel}</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <div className="rounded-full bg-rose-50 p-4">
          <svg className="h-10 w-10 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-700">{error}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate("/publications")}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
          >
            {backLabel}
          </button>
          <button
            type="button"
            onClick={fetchDetail}
            className="rounded-lg bg-[#3A5FC3] px-4 py-2 text-sm font-bold text-white hover:bg-[#2f4ea6] transition-colors cursor-pointer"
          >
            {retryLabel}
          </button>
        </div>
      </div>
    );
  }

  if (!publication) return null;

  const {
    title, eid: pubEid, doi, year, source_title,
    volume, issue, art_no, page_start, page_end,
    cited_by_count, document_type, publication_stage, open_access_status,
    authors, approved_lecturer_links, provenance,
  } = publication;

  const provenanceToShow = showAllProvenance ? provenance : provenance.slice(0, 3);
  const hasMoreProvenance = provenance.length > 3;

  return (
    <div className="app-page-container space-y-5">
      {/* ── Back navigation ────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => navigate("/publications")}
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-xs hover:border-[#3A5FC3] hover:text-[#3A5FC3] transition-colors cursor-pointer"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
        </svg>
        <span>{backLabel}</span>
      </button>

      {/* ── Section A: Canonical Metadata ─────────────────────────────── */}
      <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
        <h2 className="mb-4 text-base font-bold text-slate-800 border-b border-slate-100 pb-3">
          {sectionMeta}
        </h2>

        <h3 className="mb-3 text-sm font-bold text-[#3A5FC3]">{fmtField(title)}</h3>

        <div className="grid grid-cols-1 gap-x-6 gap-y-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
          <MetaItem label="EID" value={pubEid} mono />
          <MetaItem label="DOI" value={fmtField(doi)} mono={false} />
          <MetaItem label={locale === "vi" ? "Năm xuất bản" : "Year"} value={fmtYear(year)} />
          <MetaItem label={locale === "vi" ? "Nguồn tạp chí" : "Source"} value={fmtField(source_title)} />
          <MetaItem label="Volume" value={fmtField(volume)} />
          <MetaItem label="Issue" value={fmtField(issue)} />
          <MetaItem label={locale === "vi" ? "Số bài (Art. No.)" : "Article No."} value={fmtField(art_no)} />
          <MetaItem label={locale === "vi" ? "Trang đầu" : "Page Start"} value={fmtField(page_start)} />
          <MetaItem label={locale === "vi" ? "Trang cuối" : "Page End"} value={fmtField(page_end)} />
          <MetaItem
            label={locale === "vi" ? "Số lượt trích dẫn" : "Citation Count"}
            value={fmtCitations(cited_by_count)}
            highlight={cited_by_count !== null && cited_by_count !== undefined}
          />
          <MetaItem label={locale === "vi" ? "Loại tài liệu" : "Document Type"} value={fmtField(document_type)} />
          <MetaItem label={locale === "vi" ? "Giai đoạn xuất bản" : "Publication Stage"} value={fmtField(publication_stage)} />
          <MetaItem label={locale === "vi" ? "Tình trạng truy cập mở" : "Open Access Status"} value={fmtField(open_access_status)} />
        </div>
      </section>

      {/* ── Section B: Ordered Scopus Authors (always visible) ─────────── */}
      <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
        <h2 className="mb-4 text-base font-bold text-slate-800 border-b border-slate-100 pb-3">
          {sectionAuthors}
        </h2>

        {authors.length === 0 ? (
          <p className="py-6 text-center text-xs text-slate-400">{emptyAuthorsLabel}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-100 bg-slate-50/60 text-slate-500">
                <tr>
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colAuthorOrder}</th>
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colName}</th>
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colScopusId}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {authors.map((a) => (
                  <tr key={`${a.scopus_id}-${a.author_order}`} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-3 py-2.5 text-center text-slate-500">{a.author_order}</td>
                    <td className="px-3 py-2.5 font-medium text-slate-800">{a.preferred_name}</td>
                    <td className="px-3 py-2.5 font-mono text-slate-500">{a.scopus_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Section C: Approved Lecturer Links (always visible) ─────────── */}
      <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
        <h2 className="mb-4 text-base font-bold text-slate-800 border-b border-slate-100 pb-3">
          {sectionLinks}
        </h2>

        {approved_lecturer_links.length === 0 ? (
          <p className="py-6 text-center text-xs text-slate-400">{emptyLinksLabel}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-100 bg-slate-50/60 text-slate-500">
                <tr>
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colAuthorOrder}</th>
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{locale === "vi" ? "Họ tên giảng viên" : "Lecturer Name"}</th>
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colStaffCode}</th>
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colDepartment}</th>
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colFaculty}</th>
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colOrcid}</th>
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colScopusId}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {approved_lecturer_links.map((link, idx) => (
                  <tr key={`link-${idx}-${link.author_order}-${link.scopus_id}`} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-3 py-2.5 text-center text-slate-500">{link.author_order}</td>
                    <td className="px-3 py-2.5 font-medium text-slate-800">{link.full_name}</td>
                    <td className="px-3 py-2.5 font-mono text-slate-600">{fmtField(link.staff_code)}</td>
                    <td className="px-3 py-2.5 text-slate-700">{fmtField(link.department)}</td>
                    <td className="px-3 py-2.5 text-slate-700">{fmtField(link.faculty)}</td>
                    <td className="px-3 py-2.5 font-mono text-slate-500 text-[10px]">{fmtField(link.orcid)}</td>
                    <td className="px-3 py-2.5 font-mono text-slate-500">{link.scopus_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Section D: Safe Provenance (always visible) ────────────────── */}
      <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
        <h2 className="mb-4 text-base font-bold text-slate-800 border-b border-slate-100 pb-3">
          {sectionProvenance}
        </h2>

        {provenance.length === 0 ? (
          <p className="py-6 text-center text-xs text-slate-400">{emptyProvenanceLabel}</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-100 bg-slate-50/60 text-slate-500">
                  <tr>
                    <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colFileName}</th>
                    <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colRowNum}</th>
                    <th className="px-3 py-2.5 font-semibold whitespace-nowrap">{colImportedAt}</th>
                    <th className="px-3 py-2.5 font-semibold whitespace-nowrap hidden lg:table-cell">{colSha256}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {provenanceToShow.map((p, idx) => (
                    <tr key={`${p.file_name}-${p.row_number}-${idx}`} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-3 py-2.5 font-medium text-slate-800 max-w-0">
                        <span className="block max-w-[200px] truncate" title={p.file_name}>{p.file_name}</span>
                      </td>
                      <td className="px-3 py-2.5 text-center text-slate-600">{p.row_number}</td>
                      <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{fmtProvenanceDate(p.imported_at)}</td>
                      <td className="px-3 py-2.5 font-mono text-[10px] text-slate-400 hidden lg:table-cell">
                        <span className="block max-w-[120px] truncate" title={p.file_sha256}>{p.file_sha256}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {hasMoreProvenance && (
              <div className="mt-3 text-center">
                <button
                  type="button"
                  onClick={() => setShowAllProvenance((v) => !v)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-4 py-1.5 text-xs font-semibold text-slate-600 hover:border-[#3A5FC3] hover:text-[#3A5FC3] transition-colors cursor-pointer shadow-2xs"
                >
                  {showAllProvenance
                    ? (locale === "vi" ? "Thu gọn" : "Show less")
                    : `${locale === "vi" ? "Xem thêm" : "Show all"} (${provenance.length})`}
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

// ── Small helper component ──────────────────────────────────────────────────
interface MetaItemProps {
  label: string;
  value: string;
  mono?: boolean;
  highlight?: boolean;
}

function MetaItem({ label, value, mono, highlight }: MetaItemProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</span>
      <span
        className={[
          "text-sm text-slate-800",
          mono ? "font-mono" : "font-medium",
          highlight ? "font-bold text-emerald-700" : "",
        ].join(" ")}
      >
        {value}
      </span>
    </div>
  );
}