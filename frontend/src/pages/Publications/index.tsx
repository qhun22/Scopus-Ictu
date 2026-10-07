import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { getPublications } from "../../api/publications";
import { PublicationListItem } from "../../types/publication";
import { useI18n } from "../../i18n";

const DEFAULT_PAGE_SIZE = 20;
const FILTER_DELAY_MS = 350;

const NULL_YEAR = "Chưa rõ";
const NULL_CITATION = "Chưa có dữ liệu";

export default function PublicationsPage() {
  const navigate = useNavigate();
  const { locale } = useI18n();

  // ── Data state ────────────────────────────────────────────────────────────
  const [items, setItems] = useState<PublicationListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  // ── Filter state ──────────────────────────────────────────────────────────
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  const [year, setYear] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [publicationStage, setPublicationStage] = useState("");
  const [openAccessStatus, setOpenAccessStatus] = useState("");

  // ── Pagination state ─────────────────────────────────────────────────────
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  // ── Error state ──────────────────────────────────────────────────────────
  const [error, setError] = useState<string | null>(null);

  // ── Abort controller for race condition prevention ───────────────────────
  const abortRef = useRef<AbortController | null>(null);

  const fetchPublications = useCallback(
    async (currentPage: number, currentPageSize: number) => {
      // Cancel any in-flight request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const isFirstPage = currentPage === 1;
      if (isFirstPage) setLoading(true);
      else setLoadingMore(true);

      setError(null);

      try {
        const data = await getPublications(
          {
            page: currentPage,
            page_size: currentPageSize,
            q: qDebounced || undefined,
            year: year ? Number(year) : undefined,
            document_type: documentType || undefined,
            publication_stage: publicationStage || undefined,
            open_access_status: openAccessStatus || undefined,
          },
          { signal: controller.signal },
        );

        setItems(data.items);
        setTotal(data.total);
        setPage(currentPage);
        setPageSize(currentPageSize);
      } catch (err) {
        if ((err as Error).name === "AbortError") return; // silently ignore cancellations
        setError(
          err instanceof ApiError
            ? getApiErrorMessage(err)
            : "Không thể tải danh sách công bố. Vui lòng thử lại.",
        );
      } finally {
        if (isFirstPage) setLoading(false);
        else setLoadingMore(false);
      }
    },
    [qDebounced, year, documentType, publicationStage, openAccessStatus],
  );

  // Reset to page 1 whenever filters change
  useEffect(() => {
    fetchPublications(1, pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qDebounced, year, documentType, publicationStage, openAccessStatus, pageSize]);

  // Re-fetch when page changes (without re-triggering filter effect)
  const prevPageRef = useRef(1);
  useEffect(() => {
    if (page === prevPageRef.current) return;
    prevPageRef.current = page;
    fetchPublications(page, pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize]);

  // Debounce free-text search
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (q !== qDebounced) {
        setQDebounced(q);
        setPage(1);
      }
    }, FILTER_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [q, qDebounced]);

  // ── Filter helpers ───────────────────────────────────────────────────────
  const hasActiveFilters =
    !!qDebounced || !!year || !!documentType || !!publicationStage || !!openAccessStatus;

  const handleClearFilters = () => {
    setQ("");
    setQDebounced("");
    setYear("");
    setDocumentType("");
    setPublicationStage("");
    setOpenAccessStatus("");
    setPage(1);
  };

  const handleApplyYear = () => {
    setPage(1);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const isFiltering = loading || loadingMore;

  // ── Display helpers ──────────────────────────────────────────────────────
  const fmtYear = (y: number | null) =>
    y === null ? NULL_YEAR : String(y);

  const fmtCitations = (c: number | null) => {
    if (c === null) return NULL_CITATION;
    if (c === 0) return "0";
    return String(c);
  };

  const fmtField = (v: string | null) => v || "—";

  // ── Column headers ───────────────────────────────────────────────────────
  const colTitle = locale === "vi" ? "Công bố" : "Publication";
  const colEid = "EID";
  const colYear = locale === "vi" ? "Năm" : "Year";
  const colSource = locale === "vi" ? "Nguồn tạp chí" : "Source";
  const colDocType = locale === "vi" ? "Loại tài liệu" : "Document Type";
  const colCitations = locale === "vi" ? "Trích dẫn" : "Citations";
  const colStage = locale === "vi" ? "Giai đoạn xuất bản" : "Publication Stage";
  const colOa = locale === "vi" ? "Truy cập mở" : "Open Access";
  const colAction = locale === "vi" ? "Thao tác" : "Actions";
  const pageLabel = locale === "vi" ? "Trang" : "Page";
  const prevLabel = locale === "vi" ? "Trang trước" : "Previous";
  const nextLabel = locale === "vi" ? "Trang sau" : "Next";
  const showLabel = locale === "vi" ? "Hiển thị:" : "Show:";
  const loadingLabel = locale === "vi" ? "Đang tải dữ liệu..." : "Loading...";
  const noDataLabel = locale === "vi" ? "Không tìm thấy công bố nào." : "No publications found.";
  const noDataSubLabel = locale === "vi"
    ? "Hãy thử từ khóa hoặc bộ lọc khác."
    : "Try a different keyword or filter.";
  const resetLabel = locale === "vi" ? "Đặt lại" : "Reset";
  const viewDetailLabel = locale === "vi" ? "Chi tiết" : "Details";
  const subtitleText = locale === "vi"
    ? "Danh mục công bố khoa học chuẩn hóa toàn trường ICTU."
    : "Canonical normalized scientific publication catalog for ICTU.";

  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* ── Page Header ──────────────────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">
          Công bố khoa học
        </h1>
        <p className="mt-0.5 text-xs text-slate-500 sm:text-sm">{subtitleText}</p>
      </div>

      {/* ── Filter Bar ──────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs space-y-3">
        {/* Free-text search */}
        <div className="relative">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            aria-label={locale === "vi" ? "Tìm kiếm công bố" : "Search publications"}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={
              locale === "vi"
                ? "Tìm theo tiêu đề, EID, DOI, nguồn tạp chí..."
                : "Search by title, EID, DOI, journal..."
            }
            className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 sm:text-sm"
          />
        </div>

        {/* Filter row */}
        <div className="flex flex-wrap items-end gap-2">
          {/* Year */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="pub-filter-year" className="whitespace-nowrap text-xs font-semibold text-slate-600">
              {locale === "vi" ? "Năm:" : "Year:"}
            </label>
            <input
              id="pub-filter-year"
              type="number"
              min="1900"
              max="2100"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (setPage(1), handleApplyYear())}
              placeholder="VD: 2023"
              className="h-8 w-24 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
            />
          </div>

          {/* Document type */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="pub-filter-doc-type" className="whitespace-nowrap text-xs font-semibold text-slate-600">
              {locale === "vi" ? "Loại tài liệu:" : "Doc. type:"}
            </label>
            <input
              id="pub-filter-doc-type"
              type="text"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              placeholder={locale === "vi" ? "VD: Article" : "e.g. Article"}
              className="h-8 w-28 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
            />
          </div>

          {/* Publication stage */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="pub-filter-stage" className="whitespace-nowrap text-xs font-semibold text-slate-600">
              {locale === "vi" ? "Giai đoạn:" : "Stage:"}
            </label>
            <input
              id="pub-filter-stage"
              type="text"
              value={publicationStage}
              onChange={(e) => setPublicationStage(e.target.value)}
              placeholder={locale === "vi" ? "VD: Published" : "e.g. Published"}
              className="h-8 w-28 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
            />
          </div>

          {/* Open access status */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="pub-filter-oa" className="whitespace-nowrap text-xs font-semibold text-slate-600">
              {locale === "vi" ? "Truy cập mở:" : "Open Access:"}
            </label>
            <input
              id="pub-filter-oa"
              type="text"
              value={openAccessStatus}
              onChange={(e) => setOpenAccessStatus(e.target.value)}
              placeholder={locale === "vi" ? "VD: Open Access" : "e.g. Open Access"}
              className="h-8 w-28 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
            />
          </div>

          {/* Apply / Clear buttons */}
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={() => { setPage(1); }}
              disabled={!hasActiveFilters}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 transition-colors cursor-pointer shadow-2xs"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
              <span>{locale === "vi" ? "Áp dụng" : "Apply"}</span>
            </button>

            <button
              type="button"
              onClick={handleClearFilters}
              disabled={!hasActiveFilters}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:border-rose-300 hover:text-rose-600 hover:bg-rose-50/50 disabled:cursor-not-allowed disabled:opacity-40 transition-colors cursor-pointer shadow-2xs"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>{resetLabel}</span>
            </button>
          </div>
        </div>
      </div>

      {/* ── Error state ─────────────────────────────────────────────────── */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 flex items-start gap-2.5">
          <svg className="h-5 w-5 shrink-0 text-rose-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div className="flex flex-col gap-1.5">
            <span className="font-semibold">{error}</span>
            <button
              type="button"
              onClick={() => fetchPublications(page, pageSize)}
              className="self-start rounded-lg border border-rose-300 bg-white px-3 py-1 text-xs font-bold text-rose-700 hover:bg-rose-100 transition-colors cursor-pointer"
            >
              {locale === "vi" ? "Thử lại" : "Retry"}
            </button>
          </div>
        </div>
      )}

      {/* ── Table ───────────────────────────────────────────────────────── */}
      <div className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-xs">
        <div className="relative overflow-x-auto">
          <table className="w-full text-left text-xs" aria-busy={isFiltering}>
            <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
              <tr>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{colTitle}</th>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{colEid}</th>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{colYear}</th>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{colSource}</th>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{colDocType}</th>
                <th className="px-4 py-3 text-center font-semibold whitespace-nowrap">{colCitations}</th>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{colStage}</th>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{colOa}</th>
                <th className="px-4 py-3 text-center font-semibold whitespace-nowrap">{colAction}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {/* ── Initial loading ── */}
              {loading && items.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-2">
                      <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                      <span>{loadingLabel}</span>
                    </div>
                  </td>
                </tr>
              ) : /* ── Empty state ── */
              !loading && items.length === 0 && !error ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-1">
                      <svg className="h-8 w-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <span className="font-semibold text-slate-600">{noDataLabel}</span>
                      <span className="text-[11px]">{noDataSubLabel}</span>
                    </div>
                  </td>
                </tr>
              ) : /* ── Data rows ── */
                items.map((pub) => (
                  <tr key={pub.eid} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3 max-w-0">
                      <span
                        className="block max-w-xs truncate font-semibold text-slate-800"
                        title={pub.title}
                      >
                        {pub.title}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap font-mono text-[11px] text-slate-500">
                      {pub.eid}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-slate-700">
                      {fmtYear(pub.year)}
                    </td>
                    <td className="px-4 py-3 max-w-0">
                      <span className="block max-w-[140px] truncate text-slate-700" title={pub.source_title ?? ""}>
                        {fmtField(pub.source_title)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {fmtField(pub.document_type)}
                    </td>
                    <td className="px-4 py-3 text-center text-slate-700">
                      {fmtCitations(pub.cited_by_count)}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {fmtField(pub.publication_stage)}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {fmtField(pub.open_access_status)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        type="button"
                        onClick={() => navigate(`/publications/${pub.eid}`)}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:border-[#3A5FC3] hover:text-[#3A5FC3] transition-colors cursor-pointer shadow-2xs"
                      >
                        {viewDetailLabel}
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>

          {/* Loading overlay for filter/page transitions */}
          {loadingMore && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/80 backdrop-blur-[1px]">
              <div role="status" className="flex items-center gap-2 rounded-lg border border-slate-100 bg-white px-4 py-2.5 text-xs font-medium text-slate-600 shadow-sm">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                {loadingLabel}
              </div>
            </div>
          )}
        </div>

        {/* ── Footer: count + pagination ──────────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-2.5 text-[11px] text-slate-500">
          {/* Record count */}
          <div className="flex items-center gap-3">
            <span>
              {locale === "vi" ? "Hiển thị" : "Showing"}{" "}
              <strong>{items.length}</strong>{" "}
              {locale === "vi" ? "của" : "of"} <strong>{total}</strong>{" "}
              {locale === "vi" ? "công bố" : "publications"}
            </span>

            {/* Page size selector */}
            <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
              <span className="text-slate-500">{showLabel}</span>
              <select
                value={pageSize}
                onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                className="h-6.5 rounded-md border border-slate-200 bg-white px-1.5 text-[11px] font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          </div>

          {/* Server-driven pagination */}
          <nav aria-label={locale === "vi" ? "Phân trang công bố" : "Publication pagination"} className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={isFiltering || page <= 1}
              className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
            >
              {prevLabel}
            </button>
            <span aria-live="polite" className="min-w-[72px] text-center font-medium text-slate-600">
              {pageLabel} <strong>{page}</strong> / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => p + 1)}
              disabled={isFiltering || page >= totalPages}
              className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
            >
              {nextLabel}
            </button>
          </nav>
        </div>
      </div>
    </div>
  );
}
