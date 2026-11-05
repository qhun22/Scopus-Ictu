import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import {
  exportPublicationsJson,
  getPublicationFilterOptions,
  getPublications,
  PublicationFilterOptions,
} from "../../api/publications";
import { useAuth } from "../../contexts/AuthContext";
import { PublicationListItem } from "../../types/publication";
import { useI18n } from "../../i18n";
import Button from "../../components/ui/Button";
import PublicationDetailModal from "./PublicationDetailModal";

const DEFAULT_PAGE_SIZE = 20;
const FILTER_DELAY_MS = 350;

const NULL_YEAR: Record<"vi" | "en", string> = { vi: "Chưa rõ", en: "Unknown" };
const NULL_STRING: Record<"vi" | "en", string> = { vi: "Chưa cập nhật", en: "Not available" };

interface AppliedFilters {
  year: number | undefined;
  document_type: string | undefined;
  publication_stage: string | undefined;
  open_access_status: string | undefined;
  missing_doi: boolean;
}

export default function PublicationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedEid, setSelectedEid] = useState<string | null>(null);
  const rawScopusId = searchParams.get("scopus_id") ?? "";
  const scopusIdFilter = /^\d{1,32}$/.test(rawScopusId) ? rawScopusId : undefined;
  const { locale } = useI18n();
  const { user: currentUser } = useAuth();
  const isAdmin = currentUser?.role === "ADMIN";

  // ── Data state ────────────────────────────────────────────────────────────
  const [items, setItems] = useState<PublicationListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  // ── Search state (one box: title, EID, DOI, journal, author name, Scopus ID) ───
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");

  // When the search box contains only digits (>=8), treat it as a Scopus Author ID
  // and route to the dedicated scopus_id param (exact match) instead of q (substring).
  const qIsScopusId = /^\d{8,}$/.test(qDebounced.trim());
  const qForApi = qIsScopusId ? undefined : (qDebounced || undefined);
  const effectiveScopusId = scopusIdFilter ?? (qIsScopusId ? qDebounced.trim() : undefined);

  // ── Year: free-text, debounced live filter (same pattern as the search box) ──
  const [yearInput, setYearInput] = useState("");

  // ── Applied filter state (each control writes here directly — filtering is
  //     live, no separate "Apply" step) ──────────────────────────────────

  const [appliedFilters, setAppliedFilters] = useState<AppliedFilters>({
    year: undefined,
    document_type: undefined,
    publication_stage: undefined,
    open_access_status: undefined,
    missing_doi: false,
  });

  // ── Pagination state ─────────────────────────────────────────────────────
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  // ── Error state ──────────────────────────────────────────────────────────
  const [error, setError] = useState<string | null>(null);

  // ── Filter options (distinct values, counted within the OTHER filters
  //     currently applied — re-fetched alongside the list so counts stay
  //     truthful instead of always showing the dataset-wide totals) ───────
  const [filterOptions, setFilterOptions] = useState<PublicationFilterOptions | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPublicationFilterOptions({
      q: qForApi,
      scopus_id: effectiveScopusId,
      ...appliedFilters,
    })
      .then((opts) => {
        if (!cancelled) setFilterOptions(opts);
      })
      .catch(() => {
        // Non-critical: dropdowns just keep their last-known counts if this fails.
      });
    return () => {
      cancelled = true;
    };
  }, [qForApi, effectiveScopusId, appliedFilters]);

  // ── Export state (ADMIN only) ─────────────────────────────────────────────
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // ── Stale-request defenses: AbortController + monotonic generation ─────
  const abortRef = useRef<AbortController | null>(null);
  const genRef = useRef(0);

  // ── Scroll restoration: save position before navigating to detail page,
  //     restore it after the first data load completes on return. ─────────
  const SCROLL_KEY = "pub-list-scroll-y";
  const scrollRestoredRef = useRef(false);

  const fetchPublications = useCallback(
    async (currentPage: number, currentPageSize: number, currentGen: number) => {
      // Explicitly establish the complete loading state for THIS request
      // BEFORE awaiting. This prevents a stale earlier request from leaving
      // the UI in an indeterminate loading state.
      const isFirstPage = currentPage === 1;
      if (isFirstPage) {
        setLoading(true);
        setLoadingMore(false);
      } else {
        setLoading(false);
        setLoadingMore(true);
      }
      setError(null);

      // Abort any previous in-flight request and create a new controller
      // for THIS request.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const data = await getPublications(
          {
            page: currentPage,
            page_size: currentPageSize,
            q: qForApi,
            scopus_id: effectiveScopusId,
            ...appliedFilters,
          },
          { signal: controller.signal },
        );

        // Generation guard: only commit if THIS request is still current.
        if (currentGen !== genRef.current) return;

        setItems(data.items);
        setTotal(data.total);
      } catch (err) {
        // AbortError is silent — neither error nor state is updated.
        if ((err as Error).name === "AbortError") return;
        // Generation guard also blocks state updates for stale non-aborted
        // requests (defensive even though we already aborted the previous).
        if (currentGen !== genRef.current) return;

        setError(
          err instanceof ApiError
            ? getApiErrorMessage(err)
            : "Không thể tải danh sách công bố. Vui lòng thử lại.",
        );
      } finally {
        // Only the CURRENT request clears its own loading flag. A stale
        // request's finally is a no-op, so loading can never stick.
        if (currentGen !== genRef.current) return;
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [qForApi, effectiveScopusId, appliedFilters],
  );

  // Restore scroll once, after the first successful data load on mount.
  useEffect(() => {
    if (loading || scrollRestoredRef.current) return;
    scrollRestoredRef.current = true;
    try {
      const saved = sessionStorage.getItem(SCROLL_KEY);
      if (saved !== null) {
        sessionStorage.removeItem(SCROLL_KEY);
        const y = Number(saved);
        if (Number.isFinite(y) && y > 0) {
          requestAnimationFrame(() => window.scrollTo({ top: y, behavior: "instant" }));
        }
      }
    } catch {}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  // ── Single trigger: appliedFilters + page + pageSize + qDebounced ────────
  useEffect(() => {
    genRef.current += 1;
    const currentGen = genRef.current;
    fetchPublications(page, pageSize, currentGen);
    // Cleanup: on unmount or before the next effect run, abort in-flight.
    return () => {
      abortRef.current?.abort();
    };
    // fetchPublications is stable wrt appliedFilters/qDebounced (captured in
    // closure); we list page + pageSize + appliedFilters + qDebounced to drive
    // the trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, appliedFilters, qDebounced, scopusIdFilter]);

  // ── Debounce free-text search + reset to page 1 when it changes ─────────
  useEffect(() => {
    if (q === qDebounced) return;
    const timer = window.setTimeout(() => {
      setQDebounced(q);
      setPage(1);
    }, FILTER_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [q, qDebounced]);

  // ── Debounce the year box — only filters once it's a complete 4-digit
  //     year (or empty); a partial typed year like "20" filters nothing yet.
  useEffect(() => {
    const trimmed = yearInput.trim();
    const timer = window.setTimeout(() => {
      const parsed = /^\d{4}$/.test(trimmed) ? Number(trimmed) : undefined;
      setAppliedFilters((prev) => (prev.year === parsed ? prev : { ...prev, year: parsed }));
      setPage(1);
    }, FILTER_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [yearInput]);

  // ── Filter actions: each control sets appliedFilters directly (live) ────
  const setFilter = <K extends keyof AppliedFilters>(key: K, value: AppliedFilters[K]) => {
    setAppliedFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handleClear = () => {
    if (scopusIdFilter) setSearchParams({}, { replace: true });
    setQ("");
    setQDebounced("");
    setYearInput("");
    setAppliedFilters({
      year: undefined,
      document_type: undefined,
      publication_stage: undefined,
      open_access_status: undefined,
      missing_doi: false,
    });
    setPage(1);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setPage(1);
  };

  // ── Derived ───────────────────────────────────────────────────────────
  const hasAnyInput =
    !!scopusIdFilter ||
    !!q ||
    !!qDebounced ||
    !!yearInput ||
    !!appliedFilters.year ||
    !!appliedFilters.document_type ||
    !!appliedFilters.publication_stage ||
    !!appliedFilters.open_access_status ||
    appliedFilters.missing_doi;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const isFiltering = loading || loadingMore;

  // ── Display helpers ────────────────────────────────────────────────────
  const fmtYear = (y: number | null) =>
    y === null ? NULL_YEAR[locale] : String(y);

  const fmtField = (v: string | null) =>
    v && v.trim() ? v.trim() : NULL_STRING[locale];

  // ── Labels ────────────────────────────────────────────────────────────
  const colTitle = locale === "vi" ? "Công bố" : "Publication";
  const colEid = "EID";
  const colYear = locale === "vi" ? "Năm" : "Year";
  const colSource = locale === "vi" ? "Nguồn xuất bản" : "Source title";
  const colDocType = locale === "vi" ? "Loại tài liệu" : "Document Type";
  const colStage = locale === "vi" ? "Giai đoạn" : "Stage";
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
    ? "Danh mục công bố khoa học đã được chuẩn hóa."
    : "Catalog of canonically normalized scientific publications.";

  const exportLabel = locale === "vi" ? "Xuất JSON" : "Export JSON";
  const exportingLabel = locale === "vi" ? "Đang xuất..." : "Exporting...";

  const handleExport = async () => {
    if (!isAdmin || isExporting) return;
    setIsExporting(true);
    setExportError(null);
    try {
      const { blob, filename } = await exportPublicationsJson({
        q: qDebounced || undefined,
        year: appliedFilters.year,
        document_type: appliedFilters.document_type,
        publication_stage: appliedFilters.publication_stage,
        open_access_status: appliedFilters.open_access_status,
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(
        err instanceof ApiError
          ? (err.detail ?? "Không thể xuất dữ liệu công bố.")
          : "Không thể xuất dữ liệu công bố.",
      );
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* ── Page Header ──────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">
            Công bố khoa học
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">{subtitleText}</p>
        </div>
        {isAdmin && (
          <div className="flex flex-col items-end gap-1">
            <Button
              variant="secondary"
              onClick={() => { void handleExport(); }}
              disabled={isExporting}
              icon={
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              }
            >
              {isExporting ? exportingLabel : exportLabel}
            </Button>
            {exportError && (
              <p className="text-sm font-medium text-rose-500">{exportError}</p>
            )}
          </div>
        )}
      </div>

      {scopusIdFilter && (
        <div
          className="flex flex-wrap items-center gap-2 rounded-[5px] border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900"
          data-testid="scopus-id-chip"
        >
          <span>
            {locale === "vi" ? "Đang lọc theo tác giả Scopus ID " : "Filtered by Scopus Author ID "}
            <b>{scopusIdFilter}</b>
          </span>
          <button
            type="button"
            className="rounded border border-sky-300 bg-white px-2 py-0.5 font-semibold text-sky-800 hover:bg-sky-100"
            onClick={() => {
              setSearchParams({}, { replace: true });
              setPage(1);
            }}
          >
            {locale === "vi" ? "Bỏ lọc" : "Clear"}
          </button>
        </div>
      )}

      {/* ── Filter Bar: row 1 = search + reset, row 2 = filters + apply ───── */}
      <div className="rounded-[5px] border border-slate-200/80 bg-white p-3.5 shadow-xs space-y-3">
        {/* Row 1: search + reset */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
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
                  ? "Tìm theo tiêu đề, EID, DOI, nguồn, tác giả, Scopus ID tác giả..."
                  : "Search by title, EID, DOI, journal, author, author's Scopus ID..."
              }
              className="h-control w-full rounded-[5px] border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
            />
          </div>

          <Button
            variant="secondary"
            onClick={handleClear}
            disabled={!hasAnyInput}
          >
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span className="truncate">{resetLabel}</span>
          </Button>
        </div>

        {/* Row 2: filters — equal-width columns, apply live on change */}
        <div className={`grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 sm:grid-cols-3 ${isAdmin ? "lg:grid-cols-5" : "lg:grid-cols-4"}`}>
          {/* Year — free-text, filters live once a full 4-digit year is typed */}
          <input
            type="text"
            inputMode="numeric"
            list="pub-year-options"
            aria-label={locale === "vi" ? "Năm" : "Year"}
            value={yearInput}
            onChange={(e) => setYearInput(e.target.value.replace(/[^\d]/g, "").slice(0, 4))}
            placeholder={locale === "vi" ? "Năm (vd 2024)" : "Year (e.g. 2024)"}
            className="h-control w-full rounded-[5px] border border-slate-200 bg-white px-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
          />
          <datalist id="pub-year-options">
            {filterOptions?.years.map((y) => (
              <option key={y} value={y} />
            ))}
          </datalist>

          {/* Document type */}
          <select
            aria-label={locale === "vi" ? "Loại tài liệu" : "Document type"}
            value={appliedFilters.document_type ?? ""}
            onChange={(e) => setFilter("document_type", e.target.value || undefined)}
            className="h-control w-full rounded-[5px] border border-slate-200 bg-white px-2 text-sm text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
          >
            <option value="">{locale === "vi" ? "Loại tài liệu: Tất cả" : "Doc. type: All"}</option>
            {filterOptions?.document_types.map((o) => (
              <option key={o.value} value={o.value}>{o.value} ({o.count})</option>
            ))}
          </select>

          {/* Publication stage */}
          <select
            aria-label={locale === "vi" ? "Giai đoạn" : "Stage"}
            value={appliedFilters.publication_stage ?? ""}
            onChange={(e) => setFilter("publication_stage", e.target.value || undefined)}
            className="h-control w-full rounded-[5px] border border-slate-200 bg-white px-2 text-sm text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
          >
            <option value="">{locale === "vi" ? "Giai đoạn: Tất cả" : "Stage: All"}</option>
            {filterOptions?.publication_stages.map((o) => (
              <option key={o.value} value={o.value}>{o.value} ({o.count})</option>
            ))}
          </select>

          {/* Open access status */}
          <select
            aria-label={locale === "vi" ? "Truy cập mở" : "Open Access"}
            value={appliedFilters.open_access_status ?? ""}
            onChange={(e) => setFilter("open_access_status", e.target.value || undefined)}
            className="h-control w-full rounded-[5px] border border-slate-200 bg-white px-2 text-sm text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
          >
            <option value="">{locale === "vi" ? "Truy cập mở: Tất cả" : "Open Access: All"}</option>
            {filterOptions?.open_access_statuses.map((o) => (
              <option key={o.value} value={o.value}>{o.value} ({o.count})</option>
            ))}
          </select>

          {/* Missing DOI — admin only */}
          {isAdmin && (
            <label className="flex h-control w-full cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-[5px] border border-slate-200 bg-white px-2.5 text-sm font-semibold text-slate-600">
              <input
                type="checkbox"
                checked={appliedFilters.missing_doi}
                onChange={(e) => setFilter("missing_doi", e.target.checked)}
                className="cursor-pointer"
              />
              {locale === "vi" ? "Thiếu DOI" : "Missing DOI"}
              {filterOptions && <span className="text-slate-400">({filterOptions.missing_doi_count})</span>}
            </label>
          )}
        </div>
      </div>

      {/* ── Table ───────────────────────────────────────────────────────── */}
      <div className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
        <div className="relative overflow-x-auto">
          <table className="w-full table-fixed text-left text-sm" aria-busy={isFiltering}>
            <colgroup>
              <col style={{ width: 200 }} />
              <col style={{ width: 165 }} />
              <col style={{ width: 66 }} />
              <col style={{ width: 180 }} />
              <col style={{ width: 100 }} />
              <col style={{ width: 88 }} />
              <col style={{ width: 105 }} />
              <col style={{ width: 164 }} />
            </colgroup>
            <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
              <tr>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{colTitle}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{colEid}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{colYear}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{colSource}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{colDocType}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{colStage}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{colOa}</th>
                <th className="sticky right-0 z-[1] border-l border-slate-200/80 bg-slate-50 px-2.5 py-3.5 text-center font-medium text-slate-700 whitespace-nowrap">{colAction}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {/* ── Initial loading / error — on error just keep spinning ── */}
              {(loading && items.length === 0) || error ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400">
                    <div className="flex items-center justify-center gap-2">
                      <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                      {!error && <span className="text-xs font-medium">{loadingLabel}</span>}
                    </div>
                  </td>
                </tr>
              ) : /* ── Empty state ── */
              !loading && items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-1">
                      <svg className="h-8 w-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <span className="text-sm font-bold text-slate-700">{noDataLabel}</span>
                      <span className="text-xs text-slate-400">{noDataSubLabel}</span>
                    </div>
                  </td>
                </tr>
              ) : /* ── Data rows ── */
                items.map((pub) => (
                  <tr key={pub.eid} className="transition-colors duration-300 hover:bg-slate-50/50">
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 align-middle">
                      <span
                        className="block line-clamp-2 break-words font-medium text-slate-800"
                        title={pub.title}
                      >
                        {pub.title}
                      </span>
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 break-words font-medium text-slate-500 align-middle">
                      {pub.eid}
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 whitespace-nowrap font-medium text-slate-800 align-middle">
                      {fmtYear(pub.year)}
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 align-middle">
                      <span className="block line-clamp-2 break-words font-medium text-slate-700" title={pub.source_title ?? ""}>
                        {fmtField(pub.source_title)}
                      </span>
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 break-words font-medium text-slate-700 align-middle">
                      {fmtField(pub.document_type)}
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 break-words font-medium text-slate-700 align-middle">
                      {fmtField(pub.publication_stage)}
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 break-words font-medium text-slate-700 align-middle">
                      {fmtField(pub.open_access_status)}
                    </td>
                    <td className="sticky right-0 z-[1] border-l border-b border-slate-100 bg-white px-2.5 py-3.5 text-center align-middle">
                      {isAdmin ? (
                        <button
                          type="button"
                          onClick={() => setSelectedEid(pub.eid)}
                          className="inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900 transition-colors cursor-pointer"
                        >
                          {viewDetailLabel}
                        </button>
                      ) : (
                        <Link
                          to={`/publications/${encodeURIComponent(pub.eid)}`}
                          onClick={() => {
                            try { sessionStorage.setItem(SCROLL_KEY, String(window.scrollY)); } catch {}
                          }}
                          className="inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900 transition-colors"
                        >
                          {viewDetailLabel}
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>

          {/* Loading overlay for filter/page transitions */}
          {loadingMore && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/80 backdrop-blur-[1px]">
              <div role="status" className="flex items-center gap-2 rounded-[5px] border border-slate-100 bg-white px-4 py-2.5 text-sm font-medium text-slate-600 shadow-sm">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                {loadingLabel}
              </div>
            </div>
          )}
        </div>

        {/* ── Footer: count + pagination ──────────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-sm text-slate-500">
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
                className="h-6.5 rounded-[5px] border border-slate-200 bg-white px-1.5 text-sm font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          </div>

          {/* Server-driven pagination */}
          <nav aria-label={locale === "vi" ? "Phân trang công bố" : "Publication pagination"} className="flex items-center gap-1.5">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={isFiltering || page <= 1}
            >
              {prevLabel}
            </Button>
            <span className="px-0.5 text-slate-400">{pageLabel}</span>
            <input
              type="number"
              aria-label={locale === "vi" ? "Đến trang" : "Go to page"}
              min={1}
              max={totalPages}
              value={page}
              disabled={isFiltering}
              onChange={(e) => {
                const val = Math.max(1, Math.min(totalPages, parseInt(e.target.value, 10) || 1));
                setPage(val);
              }}
              className="h-8 w-14 rounded-[5px] border border-slate-200 bg-white px-2 text-center text-sm font-bold text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 disabled:opacity-50 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
            <span className="text-slate-400">/ <strong className="text-slate-600">{totalPages}</strong></span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={isFiltering || page >= totalPages}
            >
              {nextLabel}
            </Button>
          </nav>
        </div>
      </div>

      <PublicationDetailModal eid={selectedEid} onClose={() => setSelectedEid(null)} />
    </div>
  );
}