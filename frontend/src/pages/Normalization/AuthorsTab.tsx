import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AuthorDetail,
  AuthorListItem,
  AuthorStats,
  getAuthorDetail,
  getAuthorStats,
  getAuthors,
  normalizeAuthors,
} from "../../api/authors";
import { ApiError } from "../../api/client";
import {
  normalizeImport as normalizePublicationImport,
  ScopusImport,
} from "../../api/imports";
import { useI18n } from "../../i18n";
import { buttonClass } from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";
import ModalPortal from "../../components/common/ModalPortal";

const badgeClassName =
  "inline-flex h-badge w-28 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-[#3A5FC3] bg-white px-2.5 text-center text-xs font-bold leading-none text-[#3A5FC3] hover:bg-blue-50";
const neutralDetailButtonClassName =
  "inline-flex h-badge w-28 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-xs font-bold leading-none text-slate-700 hover:bg-slate-50";

interface AuthorsTabProps {
  scopusImports: ScopusImport[];
  locale: "vi" | "en";
  onRefresh: () => void;
  onViewDetail: (item: ScopusImport) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isAuthorPending(item: ScopusImport): boolean {
  // Only re-queue COMPLETED imports that FAILED (system exception).
  // COMPLETED with row-level errors stays completed (no retry needed).
  const summary = item.normalization_summary?.authors;
  if (item.status !== "APPLIED") return false;
  if (!summary) return true;
  if (summary.status === "FAILED") return true;
  // COMPLETED (even with row errors) — do not re-queue
  return false;
}

function isAuthorCompletedWithErrors(item: ScopusImport): boolean {
  const summary = item.normalization_summary?.authors;
  const completed = isAuthorCompleted(item);
  if (!completed) return false;
  // Has row-level errors or conflicts — flag but still COMPLETED (not FAILED)
  return Boolean(
    (summary?.errors && summary.errors.length > 0) ||
    (summary?.conflicts && summary.conflicts > 0)
  );
}

function isAuthorCompleted(item: ScopusImport): boolean {
  const summary = item.normalization_summary?.authors;
  return (
    item.status === "APPLIED" &&
    summary?.status === "COMPLETED"
  );
}

function formatDate(isoString?: string | null): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleString("vi-VN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function formatCount(n: number): string {
  return new Intl.NumberFormat("vi-VN").format(n);
}

function variantTypeLabel(vt: string, locale: string): string {
  if (vt === "AUTHOR_FULL_NAME") return locale === "vi" ? "Tên đầy đủ" : "Full Name";
  return locale === "vi" ? "Tên hiển thị" : "Display";
}

// ---------------------------------------------------------------------------
// AuthorsTab Component
// ---------------------------------------------------------------------------

export default function AuthorsTab({ scopusImports, locale, onRefresh, onViewDetail }: AuthorsTabProps) {
  const { t } = useI18n();
  // Destructure stable callbacks — avoid depending on the whole toast object
  // which changes identity when state (toast list) updates.
  const { error: toastError, success: toastSuccess } = useToast();

  // Pending imports for author extraction
  const [pendingImports, setPendingImports] = useState<ScopusImport[]>([]);
  const [normalizingId, setNormalizingId] = useState<string | null>(null);
  const [authorNormalizingId, setAuthorNormalizingId] = useState<string | null>(null);

  // Author list state
  const [authorSearchInput, setAuthorSearchInput] = useState("");
  const [appliedAuthorSearch, setAppliedAuthorSearch] = useState("");
  const [authorPage, setAuthorPage] = useState(1);
  const [authorPageSize, setAuthorPageSize] = useState(10);

  const handleApplyAuthorSearch = () => {
    setAppliedAuthorSearch(authorSearchInput.trim());
    setAuthorPage(1);
  };

  const handleResetAuthorSearch = () => {
    setAuthorSearchInput("");
    setAppliedAuthorSearch("");
    setAuthorPage(1);
  };

  const isApplyAuthorDisabled = authorSearchInput.trim() === appliedAuthorSearch.trim();
  const isResetAuthorDisabled = !authorSearchInput && !appliedAuthorSearch;
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(10);
  const [authorTotal, setAuthorTotal] = useState(0);
  const [authors, setAuthors] = useState<AuthorListItem[]>([]);
  const [authorsLoading, setAuthorsLoading] = useState(false);
  const [globalStats, setGlobalStats] = useState<AuthorStats | null>(null);

  const authorTotalPages = Math.max(1, Math.ceil(authorTotal / authorPageSize));
  const authorHistory = useMemo(
    () => scopusImports.filter(isAuthorCompleted),
    [scopusImports],
  );
  const historyTotalPages = Math.max(1, Math.ceil(authorHistory.length / historyPageSize));
  const paginatedHistory = useMemo(
    () =>
      authorHistory.slice(
        (historyPage - 1) * historyPageSize,
        historyPage * historyPageSize,
      ),
    [authorHistory, historyPage, historyPageSize],
  );

  // Author detail modal
  const [selectedAuthor, setSelectedAuthor] = useState<AuthorDetail | null>(null);

  // Computed summary
  const summaryCards = useMemo(() => {
    const pending = scopusImports.filter(isAuthorPending);
    const completed = scopusImports.filter(isAuthorCompleted);
    const completedWithErrors = scopusImports.filter(isAuthorCompletedWithErrors);
    return { pending, completed, completedWithErrors };
  }, [scopusImports]);

  // Keep pending imports in sync with scopusImports prop
  useEffect(() => {
    setPendingImports(scopusImports.filter(isAuthorPending));
  }, [scopusImports]);

  // Load author list
  const loadAuthors = useCallback(async (q: string, page: number, pageSize: number) => {
    setAuthorsLoading(true);
    try {
      const res = await getAuthors({ q: q || undefined, page, page_size: pageSize });
      setAuthors(res.items);
      setAuthorTotal(res.total);
    } catch (err: unknown) {
      toastError(
        locale === "vi" ? "Lỗi tải danh sách" : "Load error",
        err instanceof ApiError ? err.message : (locale === "vi" ? "Không thể tải danh sách tác giả." : "Unable to load author list."),
      );
    } finally {
      setAuthorsLoading(false);
    }
  }, [toastError, locale]);

  // Load global stats
  const loadStats = useCallback(async () => {
    try {
      const stats = await getAuthorStats();
      setGlobalStats(stats);
    } catch {
      // Non-fatal — stats are secondary to the workflow
    }
  }, []);

  // Reload author list AND global stats after a normalization action
  const reloadAuthorsAndStats = useCallback(async () => {
    await loadAuthors(appliedAuthorSearch, authorPage, authorPageSize);
    await loadStats();
  }, [appliedAuthorSearch, authorPage, authorPageSize, loadAuthors, loadStats]);

  useEffect(() => {
    void loadAuthors(appliedAuthorSearch, authorPage, authorPageSize);
    void loadStats();
  }, [appliedAuthorSearch, authorPage, authorPageSize, loadAuthors, loadStats]);

  // Handlers
  const handleNormalizePublication = async (item: ScopusImport) => {
    if (normalizingId) return;
    setNormalizingId(item.id);
    try {
      await normalizePublicationImport(item.id);
      onRefresh();
      await reloadAuthorsAndStats();
      toastSuccess(
        locale === "vi" ? "Chuẩn hóa công bố hoàn tất" : "Publication normalization complete",
        locale === "vi"
          ? "Đã chuẩn hóa công bố thành công."
          : "Publication normalization complete.",
      );
    } catch (err: unknown) {
      toastError(
        locale === "vi" ? "Lỗi chuẩn hóa" : "Normalization error",
        err instanceof ApiError ? err.message : (locale === "vi" ? "Không thể chuẩn hóa." : "Unable to normalize."),
      );
    } finally {
      setNormalizingId(null);
    }
  };

  const handleNormalizeAuthors = async (item: ScopusImport) => {
    if (authorNormalizingId) return;
    setAuthorNormalizingId(item.id);
    try {
      await normalizeAuthors(item.id);
      onRefresh();
      await reloadAuthorsAndStats();
      toastSuccess(
        locale === "vi" ? "Bóc tách hoàn tất" : "Extraction complete",
        locale === "vi"
          ? "Đã bóc tách tác giả thành công."
          : "Author extraction complete.",
      );
    } catch (err: unknown) {
      toastError(
        locale === "vi" ? "Lỗi bóc tách" : "Extraction error",
        err instanceof ApiError ? err.message : (locale === "vi" ? "Không thể bóc tách tác giả." : "Unable to extract authors."),
      );
    } finally {
      setAuthorNormalizingId(null);
    }
  };

  const handleViewAuthorDetail = async (author: AuthorListItem) => {
    try {
      const detail = await getAuthorDetail(author.id);
      setSelectedAuthor(detail);
    } catch (err: unknown) {
      toastError(
        locale === "vi" ? "Lỗi tải chi tiết" : "Load error",
        err instanceof ApiError ? err.message : (locale === "vi" ? "Không thể tải chi tiết." : "Unable to load detail."),
      );
    }
  };

  const authorStatusLabel = (status?: string, hasErrors?: boolean) => {
    if (status === "FAILED") return t.normalization.authorsTab.status.failed;
    if (status === "NORMALIZING") return t.normalization.authorsTab.status.normalizing;
    if (status === "COMPLETED") {
      if (hasErrors) return t.normalization.authorsTab.status.completedWithErrors;
      return t.normalization.authorsTab.status.completed;
    }
    return t.normalization.authorsTab.status.pending;
  };

  return (
    <div className="space-y-5">
      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
        <div className="rounded-[5px] border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">
            {locale === "vi" ? "Tổng đợt nhập" : "Total imports"}
          </span>
          <p className="mt-1 text-2xl font-black text-slate-800">
            {formatCount(summaryCards.pending.length + summaryCards.completed.length)}
          </p>
        </div>
        <div className="rounded-[5px] border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">
            {t.normalization.authorsTab.summary.pending}
          </span>
          <p className="mt-1 text-2xl font-black text-slate-800">
            {formatCount(summaryCards.pending.length)}
          </p>
        </div>
        <div className="rounded-[5px] border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-emerald-600">
            {t.normalization.authorsTab.summary.processed}
          </span>
          <p className="mt-1 text-2xl font-black text-emerald-600">
            {formatCount(summaryCards.completed.length)}
          </p>
        </div>
        <div className="rounded-[5px] border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-amber-600">
            {t.normalization.authorsTab.summary.completedWithErrors}
          </span>
          <p className="mt-1 text-2xl font-black text-amber-600">
            {formatCount(summaryCards.completedWithErrors.length)}
          </p>
        </div>
        <div className="rounded-[5px] border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-[#3A5FC3]">
            {t.normalization.authorsTab.summary.scopusAuthors}
          </span>
          <p className="mt-1 text-2xl font-black text-[#3A5FC3]">
            {globalStats ? formatCount(globalStats.total_authors) : "—"}
          </p>
        </div>
      </div>

      {/* SECTION 1: Chờ xử lý */}
      <section className="space-y-3">
        <div>
          <h2 className="text-base font-bold text-slate-800 sm:text-lg">
            {t.normalization.authorsTab.pendingTitle}
          </h2>
          <p className="text-xs text-slate-500">
            {t.normalization.authorsTab.pendingSubtitle}
          </p>
        </div>

        <div className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
                <tr>
                  <th className="px-3 py-3.5 font-semibold text-slate-700 whitespace-nowrap">Tên tệp</th>
                  <th className="px-3 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Loại dữ liệu</th>
                  <th className="px-3 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Thời gian</th>
                  <th className="px-3 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Bản ghi</th>
                  <th className="px-3 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Người thực hiện</th>
                  <th className="px-3 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Trạng thái</th>
                  <th className="sticky right-0 z-[1] w-44 whitespace-nowrap border-l border-slate-200/80 bg-slate-50 px-3 py-3.5 text-center font-semibold text-slate-700">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
        {pendingImports.length === 0 ? (
          <tr>
            <td colSpan={7} className="py-12 text-center text-slate-400">
              <div className="flex flex-col items-center justify-center gap-1.5">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-[5px] bg-slate-100/80 text-slate-400 mb-2.5 border border-slate-200/80">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-sm font-bold text-slate-700">
              {t.normalization.authorsTab.emptyPending}
            </h3>
            <p className="mt-1 text-xs text-slate-400">
              {t.normalization.authorsTab.emptyPendingSub}
            </p>
          </div>
            </td>
          </tr>
        ) : (
            pendingImports.map((item) => {
              const authorSummary = item.normalization_summary?.authors;
              const authorStatus = authorSummary?.status;
              const needsPublicationNormalization =
                !item.normalization || item.normalization.status !== "COMPLETED";
              const isNorm = normalizingId === item.id;
              const isAuthorNorm = authorNormalizingId === item.id;

              return (
                <tr
                  key={item.id}
                  className="transition-colors hover:bg-slate-50/70"
                >
                    {/* Info */}
                    <td className="px-3 py-3.5 align-middle whitespace-nowrap">
                      <div className="flex items-center gap-2.5">
                      <div className="flex h-10 w-10 items-center justify-center rounded-[5px] bg-slate-100 text-slate-600 border border-slate-200/80 shrink-0">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <div className="min-w-0 max-w-xs sm:max-w-sm">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className="font-bold text-slate-800 text-sm truncate max-w-xs sm:max-w-md"
                            title={item.file_name}
                          >
                            {item.file_name}
                          </span>
                        </div>
                      </div>
                      </div>
                    </td>

                    <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap"><span className={badgeClassName}>Scopus</span></td>
                    <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap font-medium text-slate-600">{formatDate(item.created_at)}</td>
                    <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap font-bold text-slate-800">{formatCount(item.total_records)}</td>
                    <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap"><span className={badgeClassName}>{item.performed_by || (locale === "vi" ? "Không xác định" : "Unknown")}</span></td>
                    <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap"><span className={badgeClassName}>{authorStatusLabel(authorStatus)}</span></td>

                    {/* Actions */}
                    <td className="sticky right-0 z-[1] whitespace-nowrap border-l border-slate-100 bg-white px-3 py-3.5 text-center align-middle">
                      <div className="flex items-center justify-center gap-2">
                      {needsPublicationNormalization ? (
                        <button
                          type="button"
                          onClick={() => void handleNormalizePublication(item)}
                          disabled={isNorm}
                          className="inline-flex h-badge w-28 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-[5px] border border-slate-200 bg-white px-2.5 text-center text-xs font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-300 hover:text-slate-900 transition-all duration-150 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-slate-300/40 cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {isNorm ? (
                            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700" />
                          ) : (
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                          )}
                          {isNorm ? t.normalization.actions.normalizing : (locale === "vi" ? "Chuẩn hóa" : "Normalize")}
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => void handleNormalizeAuthors(item)}
                          disabled={isAuthorNorm}
                          className="inline-flex h-badge w-28 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-[5px] border border-slate-200 bg-white px-2.5 text-center text-xs font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-300 hover:text-slate-900 transition-all duration-150 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-slate-300/40 cursor-pointer disabled:cursor-not-allowed disabled:opacity-60 group"
                        >
                          {isAuthorNorm ? (
                            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700" />
                          ) : (
                            <svg className="h-3.5 w-3.5 transition-transform duration-150 group-hover:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                            </svg>
                          )}
                          {isAuthorNorm
                            ? t.normalization.actions.normalizing
                            : (locale === "vi" ? "Bóc tách" : "Extract")}
                        </button>
                      )}
                      </div>
                    </td>
                </tr>
              );
            })
        )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* SECTION 2: Processed author extraction history */}
      <section className="space-y-3">
        <div>
          <h2 className="text-base font-bold text-slate-800 sm:text-lg">
            {t.normalization.authorsTab.historyTitle}
          </h2>
        </div>
        <div className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
                <tr>
                  <th className="px-3 py-3.5 font-semibold text-slate-700 whitespace-nowrap">Tên tệp</th>
                  <th className="px-3 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Loại dữ liệu</th>
                  <th className="px-3 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Thời gian</th>
                  <th className="px-3 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Bản ghi</th>
                  <th className="px-3 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Người thực hiện</th>
                  <th className="px-3 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Trạng thái</th>
                  <th className="sticky right-0 z-[1] w-44 whitespace-nowrap border-l border-slate-200/80 bg-slate-50 px-3 py-3.5 text-center font-semibold text-slate-700">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {paginatedHistory.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center justify-center gap-1.5">
                        <div className="flex h-10 w-10 items-center justify-center rounded-[5px] border border-slate-200/80 bg-slate-100/80 text-slate-400">
                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <span className="text-sm font-bold text-slate-700">
                          {locale === "vi" ? "Không tìm thấy dữ liệu" : "No data found"}
                        </span>
                        <span className="text-xs text-slate-400">
                          {locale === "vi" ? "Chưa có đợt nhập nào được bóc tách tác giả." : "No imports have had authors extracted yet."}
                        </span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  paginatedHistory.map((item) => (
                    <tr key={item.id} className="transition-colors hover:bg-slate-50/70">
                      <td className="px-3 py-3.5 align-middle whitespace-nowrap">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-8 w-8 items-center justify-center rounded-[5px] border border-slate-200/80 bg-slate-100 text-slate-600 shrink-0">
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                          </div>
                          <div className="min-w-0 max-w-xs sm:max-w-sm">
                            <span className="block font-bold text-slate-800 truncate" title={item.file_name}>
                              {item.file_name}
                            </span>
                            <span className="block text-[10px] font-mono text-slate-400 truncate">
                              ID: {item.id}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap"><span className={badgeClassName}>Scopus</span></td>
                      <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap font-medium text-slate-600">{formatDate(item.created_at)}</td>
                      <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap font-bold text-slate-800">{formatCount(item.total_records)}</td>
                      <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap"><span className={badgeClassName}>{item.performed_by || (locale === "vi" ? "Không xác định" : "Unknown")}</span></td>
                      <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap">
                        <span className={item.normalization_summary?.authors?.status === "COMPLETED" ? "inline-flex h-badge w-28 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-emerald-300 bg-white px-2.5 text-center text-xs font-bold leading-none text-emerald-700 hover:bg-emerald-50" : badgeClassName}>
                          {authorStatusLabel(item.normalization_summary?.authors?.status)}
                        </span>
                      </td>
                      <td className="sticky right-0 z-[1] border-l border-slate-100 bg-white px-3 py-3.5 text-center align-middle">
                        <button
                          type="button"
                          onClick={() => onViewDetail(item)}
                          className="inline-flex h-badge w-28 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-200 bg-white px-2.5 text-center text-xs font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-300 hover:text-slate-900 transition-colors cursor-pointer"
                        >
                          {t.normalization.authorsTab.actions.viewDetail}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-xs text-slate-500">
            <div className="flex items-center gap-3">
              <span>
                {locale === "vi" ? "Hiển thị" : "Showing"} <strong>{paginatedHistory.length}</strong> {locale === "vi" ? "trong" : "of"} {authorHistory.length} {locale === "vi" ? "đợt nhập" : "imports"}
              </span>
              <div className="flex items-center gap-1.5 border-l border-slate-200 pl-2">
                <span>{locale === "vi" ? "Hiển thị:" : "Show:"}</span>
                <select
                  value={historyPageSize}
                  onChange={(e) => {
                    setHistoryPageSize(Number(e.target.value));
                    setHistoryPage(1);
                  }}
                  className="h-6.5 cursor-pointer rounded-[5px] border border-slate-200 bg-white px-1.5 text-[11px] font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none"
                >
                  <option value={10}>10 / {locale === "vi" ? "trang" : "page"}</option>
                  <option value={30}>30 / {locale === "vi" ? "trang" : "page"}</option>
                  <option value={50}>50 / {locale === "vi" ? "trang" : "page"}</option>
                  <option value={100}>100 / {locale === "vi" ? "trang" : "page"}</option>
                </select>
              </div>
            </div>
            <nav aria-label="Pagination" className="flex items-center gap-1.5">
              <button type="button" onClick={() => setHistoryPage((page) => Math.max(1, page - 1))} disabled={historyPage <= 1} className={buttonClass("secondary", "sm")}>
                {locale === "vi" ? "Trang trước" : "Previous"}
              </button>
              <span className="px-0.5 text-slate-400">{locale === "vi" ? "Trang" : "Page"}</span>
              <input
                type="number"
                aria-label={locale === "vi" ? "Đến trang" : "Go to page"}
                min={1}
                max={historyTotalPages}
                value={historyPage}
                onChange={(e) => {
                  const value = Math.max(1, Math.min(historyTotalPages, parseInt(e.target.value, 10) || 1));
                  setHistoryPage(value);
                }}
                className="h-8 w-14 rounded-[5px] border border-slate-200 bg-white px-2 text-center text-[11px] font-bold text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
              <span className="text-slate-400">/ <strong className="text-slate-600">{historyTotalPages}</strong></span>
              <button type="button" onClick={() => setHistoryPage((page) => Math.min(historyTotalPages, page + 1))} disabled={historyPage >= historyTotalPages} className={buttonClass("secondary", "sm")}>
                {locale === "vi" ? "Trang sau" : "Next"}
              </button>
            </nav>
          </div>
        </div>
      </section>

      {/* SECTION 3: Tác giả Scopus */}
      <section className="space-y-3">
        <div>
          <h2 className="text-base font-bold text-slate-800 sm:text-lg">
            {t.normalization.authorsTab.scopusAuthorsTitle}
          </h2>
        </div>

        {/* Toolbar: Search input with Apply & Reset buttons */}
        <div className="flex flex-col gap-3 rounded-[5px] border border-slate-200/80 bg-white p-3.5 shadow-xs sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              type="text"
              aria-label={t.common.search}
              value={authorSearchInput}
              onChange={(e) => setAuthorSearchInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleApplyAuthorSearch();
                }
              }}
              placeholder={t.normalization.authorsTab.searchPlaceholder}
              className="h-control w-full rounded-control border border-line bg-slate-50 pl-9 pr-3 text-[13px] text-ink placeholder:text-ink-faint focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20"
            />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Nút Áp dụng */}
            <button
              type="button"
              disabled={isApplyAuthorDisabled}
              onClick={handleApplyAuthorSearch}
              className={buttonClass("primary")}
            >
              <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span className="truncate">{locale === "vi" ? "Áp dụng" : "Apply"}</span>
            </button>

            {/* Nút Đặt lại */}
            <button
              type="button"
              onClick={handleResetAuthorSearch}
              disabled={isResetAuthorDisabled}
              className={buttonClass("secondary")}
            >
              <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span className="truncate">{locale === "vi" ? "Đặt lại" : "Reset"}</span>
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-600">
                    {t.normalization.authorsTab.table.authorName}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-600">
                    {t.normalization.authorsTab.table.scopusId}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-center font-semibold text-slate-600">
                    {t.normalization.authorsTab.table.publicationCount}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-center font-semibold text-slate-600">
                    {t.normalization.authorsTab.table.variantCount}
                  </th>
                  <th className="w-44 whitespace-nowrap border-l border-slate-200/80 px-4 py-3 text-center font-semibold text-slate-600">
                    {t.normalization.authorsTab.table.actions}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {authorsLoading ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                      <div className="flex items-center justify-center gap-2">
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                        <span className="text-xs font-medium">
                          {locale === "vi" ? "Đang tải..." : "Loading..."}
                        </span>
                      </div>
                    </td>
                  </tr>
                ) : authors.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center justify-center gap-1.5">
                        <div className="flex h-10 w-10 items-center justify-center rounded-[5px] bg-slate-100/80 border border-slate-200/80 text-slate-400 mb-1">
                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                          </svg>
                        </div>
                        <span className="text-sm font-bold text-slate-700">
                          {locale === "vi" ? "Chưa có tác giả nào" : "No authors yet"}
                        </span>
                        <span className="text-xs text-slate-400">
                          {locale === "vi" ? "Danh sách tác giả trích xuất sẽ xuất hiện tại đây." : "Extracted author list will appear here."}
                        </span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  authors.map((author) => (
                    <tr key={author.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-4 py-3 font-medium text-slate-800 max-w-[200px] truncate" title={author.preferred_name}>
                        {author.preferred_name}
                      </td>
                      <td className="px-4 py-3 text-slate-500 font-mono text-[11px]">
                        {author.scopus_id}
                      </td>
                      <td className="px-4 py-3 text-center text-slate-700 font-semibold">
                        {formatCount(author.publication_count)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {author.variant_count > 0 ? (
                          <span className="font-semibold text-slate-700">
                            {author.variant_count}
                          </span>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="w-44 border-l border-slate-100 px-4 py-3 text-center">
                        <button
                          type="button"
                          onClick={() => void handleViewAuthorDetail(author)}
                          className={neutralDetailButtonClassName}
                        >
                          {t.normalization.authorsTab.actions.viewDetail}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Footer info & Pagination Controls (Visible even at total=0) */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-2.5 text-[11px] text-slate-500">
            <div className="flex items-center gap-3">
              <span>
                {locale === "vi" ? "Hiển thị" : "Showing"} <strong>{authors.length}</strong> {locale === "vi" ? "trong" : "of"} {authorTotal} {locale === "vi" ? "tác giả" : "authors"}
              </span>

              {/* Page Size Selector */}
              <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
                <span className="text-slate-500">{locale === "vi" ? "Hiển thị:" : "Show:"}</span>
                <select
                  value={authorPageSize}
                  onChange={(e) => {
                    const newSize = Number(e.target.value);
                    setAuthorPageSize(newSize);
                    setAuthorPage(1);
                  }}
                  className="h-6.5 rounded-[5px] border border-slate-200 bg-white px-1.5 text-[11px] font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer"
                >
                  <option value={10}>10 / {locale === "vi" ? "trang" : "page"}</option>
                  <option value={30}>30 / {locale === "vi" ? "trang" : "page"}</option>
                  <option value={50}>50 / {locale === "vi" ? "trang" : "page"}</option>
                  <option value={100}>100 / {locale === "vi" ? "trang" : "page"}</option>
                </select>
              </div>
            </div>

            <nav aria-label="Pagination" className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setAuthorPage((prev) => Math.max(1, prev - 1))}
                disabled={authorPage <= 1}
                className={buttonClass("secondary", "sm")}
              >
                {locale === "vi" ? "Trang trước" : "Previous"}
              </button>
              <span className="px-0.5 text-slate-400">{locale === "vi" ? "Trang" : "Page"}</span>
              <input
                type="number"
                aria-label={locale === "vi" ? "Đến trang" : "Go to page"}
                min={1}
                max={authorTotalPages}
                value={authorPage}
                onChange={(e) => {
                  const value = Math.max(1, Math.min(authorTotalPages, parseInt(e.target.value, 10) || 1));
                  setAuthorPage(value);
                }}
                className="h-8 w-14 rounded-[5px] border border-slate-200 bg-white px-2 text-center text-[11px] font-bold text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
              <span className="text-slate-400">/ <strong className="text-slate-600">{authorTotalPages}</strong></span>
              <button
                type="button"
                onClick={() => setAuthorPage((prev) => Math.min(authorTotalPages, prev + 1))}
                disabled={authorPage >= authorTotalPages}
                className={buttonClass("secondary", "sm")}
              >
                {locale === "vi" ? "Trang sau" : "Next"}
              </button>
            </nav>
          </div>
        </div>
      </section>

      {/* Author Detail Modal */}
      {selectedAuthor && (
        <ModalPortal>
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
            <div className="w-full max-w-lg rounded-card border border-slate-200 bg-white shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <h2 className="text-base font-bold text-slate-800">
                  {t.normalization.authorsTab.detail.title}
                </h2>
                <button
                  type="button"
                  onClick={() => setSelectedAuthor(null)}
                  className="inline-flex items-center justify-center rounded-[5px] p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4 px-5 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                      {t.normalization.authorsTab.detail.preferredName}
                    </label>
                    <p className="font-bold text-slate-800 text-sm">{selectedAuthor.preferred_name}</p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                      {t.normalization.authorsTab.detail.scopusId}
                    </label>
                    <p className="font-mono text-xs text-slate-600">{selectedAuthor.scopus_id}</p>
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                    {t.normalization.authorsTab.detail.nameVariants}
                  </label>
                  {selectedAuthor.variants.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">
                      {t.normalization.authorsTab.detail.noVariants}
                    </p>
                  ) : (
                    <div className="space-y-1.5">
                      {selectedAuthor.variants.map((v) => (
                        <div key={v.id} className="flex items-start gap-2 rounded-[5px] border border-slate-100 bg-slate-50 px-3 py-2">
                          <span className={`mt-0.5 shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${
                            v.variant_type === "AUTHOR_FULL_NAME"
                              ? "bg-blue-50 text-blue-600 border border-blue-200"
                              : "bg-slate-100 text-slate-600 border border-slate-200"
                          }`}>
                            {variantTypeLabel(v.variant_type, locale)}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold text-slate-700 truncate">{v.variant_name}</p>
                            <p className="text-[10px] text-slate-400 font-mono truncate">{v.variant_name_normalized}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                    {t.normalization.authorsTab.detail.publicationCount}
                  </label>
                  <p className="text-sm font-bold text-slate-700">
                    {formatCount(selectedAuthor.publication_count)}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-end border-t border-slate-100 px-5 py-4">
                <button
                  type="button"
                  onClick={() => setSelectedAuthor(null)}
                  className={buttonClass("secondary")}
                >
                  {t.common.close}
                </button>
              </div>
            </div>
          </div>
        </ModalPortal>
      )}
    </div>
  );
}
