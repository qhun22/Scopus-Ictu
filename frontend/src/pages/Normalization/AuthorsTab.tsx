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
  AuthorNormalizationSummary,
  normalizeImport as normalizePublicationImport,
  ScopusImport,
} from "../../api/imports";
import { useI18n } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import ModalPortal from "../../components/common/ModalPortal";

interface AuthorsTabProps {
  scopusImports: ScopusImport[];
  locale: "vi" | "en";
  onRefresh: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isAuthorPending(item: ScopusImport): boolean {
  // Only re-queue COMPLETED imports that FAILED (system exception).
  // COMPLETED with row-level errors stays completed (no retry needed).
  const summary = item.normalization_summary as AuthorNormalizationSummary | undefined | null;
  if (item.status !== "APPLIED") return false;
  if (!summary) return true;
  if (summary.status === "FAILED") return true;
  // COMPLETED (even with row errors) — do not re-queue
  return false;
}

function isAuthorCompletedWithErrors(item: ScopusImport): boolean {
  const summary = item.normalization_summary as AuthorNormalizationSummary | undefined | null;
  const completed = isAuthorCompleted(item);
  if (!completed) return false;
  // Has row-level errors or conflicts — flag but still COMPLETED (not FAILED)
  return Boolean(
    (summary?.errors && summary.errors.length > 0) ||
    (summary?.conflicts && summary.conflicts > 0)
  );
}

function isAuthorCompleted(item: ScopusImport): boolean {
  const summary = item.normalization_summary as AuthorNormalizationSummary | undefined | null;
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

export default function AuthorsTab({ scopusImports, locale, onRefresh }: AuthorsTabProps) {
  const { t } = useI18n();
  const toast = useToast();

  // Pending imports for author extraction
  const [pendingImports, setPendingImports] = useState<ScopusImport[]>([]);
  const [normalizingId, setNormalizingId] = useState<string | null>(null);
  const [authorNormalizingId, setAuthorNormalizingId] = useState<string | null>(null);

  // Author list state
  const [authorSearch, setAuthorSearch] = useState("");
  const [authorPage, setAuthorPage] = useState(1);
  const [authorTotal, setAuthorTotal] = useState(0);
  const [authors, setAuthors] = useState<AuthorListItem[]>([]);
  const [authorsLoading, setAuthorsLoading] = useState(false);
  const [globalStats, setGlobalStats] = useState<AuthorStats | null>(null);

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
  const loadAuthors = useCallback(async (q: string, page: number) => {
    setAuthorsLoading(true);
    try {
      const res = await getAuthors({ q: q || undefined, page, page_size: 20 });
      setAuthors(res.items);
      setAuthorTotal(res.total);
    } catch (err: unknown) {
      toast.error(
        locale === "vi" ? "Lỗi tải danh sách" : "Load error",
        err instanceof ApiError ? err.message : (locale === "vi" ? "Không thể tải danh sách tác giả." : "Unable to load author list."),
      );
    } finally {
      setAuthorsLoading(false);
    }
  }, [toast, locale]);

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
    await loadAuthors(authorSearch, authorPage);
    await loadStats();
  }, [authorSearch, authorPage, loadAuthors, loadStats]);

  useEffect(() => {
    void loadAuthors(authorSearch, authorPage);
    void loadStats();
  }, [authorSearch, authorPage, loadAuthors, loadStats]);

  // Handlers
  const handleNormalizePublication = async (item: ScopusImport) => {
    if (normalizingId) return;
    setNormalizingId(item.id);
    try {
      await normalizePublicationImport(item.id);
      onRefresh();
      await reloadAuthorsAndStats();
      toast.success(
        locale === "vi" ? "Chuẩn hóa công bố hoàn tất" : "Publication normalization complete",
        locale === "vi"
          ? "Đã chuẩn hóa công bố thành công."
          : "Publication normalization complete.",
      );
    } catch (err: unknown) {
      toast.error(
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
      toast.success(
        locale === "vi" ? "Bóc tách hoàn tất" : "Extraction complete",
        locale === "vi"
          ? "Đã bóc tách tác giả thành công."
          : "Author extraction complete.",
      );
    } catch (err: unknown) {
      toast.error(
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
      toast.error(
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

  const authorStatusColor = (status?: string, hasErrors?: boolean) => {
    if (status === "COMPLETED") {
      if (hasErrors) return "bg-amber-50 text-amber-700 border-amber-200";
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    }
    if (status === "FAILED") return "bg-rose-50 text-rose-700 border-rose-200";
    if (status === "NORMALIZING") return "bg-blue-50 text-blue-700 border-blue-200";
    return "bg-slate-50 text-slate-600 border-slate-200";
  };

  return (
    <div className="space-y-5">
      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">
            {t.normalization.authorsTab.summary.pending}
          </span>
          <p className="mt-1 text-2xl font-black text-slate-800">
            {formatCount(summaryCards.pending.length)}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-emerald-600">
            {t.normalization.authorsTab.summary.processed}
          </span>
          <p className="mt-1 text-2xl font-black text-emerald-600">
            {formatCount(summaryCards.completed.length)}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-amber-600">
            {t.normalization.authorsTab.summary.completedWithErrors}
          </span>
          <p className="mt-1 text-2xl font-black text-amber-600">
            {formatCount(summaryCards.completedWithErrors.length)}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-[#3A5FC3]">
            {t.normalization.authorsTab.summary.scopusAuthors}
          </span>
          <p className="mt-1 text-2xl font-black text-[#3A5FC3]">
            {globalStats ? formatCount(globalStats.total_authors) : "—"}
          </p>
        </div>
      </div>

      {/* SECTION 1: Cần xử lý */}
      <section className="space-y-3">
        <div>
          <h2 className="text-base font-bold text-slate-800 sm:text-lg">
            {t.normalization.authorsTab.pendingTitle}
          </h2>
          <p className="text-xs text-slate-500">
            {t.normalization.authorsTab.pendingSubtitle}
          </p>
        </div>

        {pendingImports.length === 0 ? (
          <div className="rounded-xl border border-slate-200/80 bg-white p-8 text-center shadow-xs">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 mb-2.5 border border-emerald-100">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="text-sm font-bold text-slate-700">
              {t.normalization.authorsTab.emptyPending}
            </h3>
            <p className="mt-1 text-xs text-slate-400">
              {t.normalization.authorsTab.emptyPendingSub}
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {pendingImports.map((item) => {
              const authorSummary = item.normalization_summary as AuthorNormalizationSummary | undefined;
              const authorStatus = authorSummary?.status;
              const needsPublicationNormalization =
                !item.normalization || item.normalization.status !== "COMPLETED";
              const isNorm = normalizingId === item.id;
              const isAuthorNorm = authorNormalizingId === item.id;

              return (
                <div
                  key={item.id}
                  className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    {/* Info */}
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-[#3A5FC3] border border-purple-100/80 shrink-0">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                        </svg>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className="font-bold text-slate-800 text-sm truncate max-w-xs sm:max-w-md"
                            title={item.file_name}
                          >
                            {item.file_name}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                          <span>
                            <strong className="text-slate-700">{formatCount(item.total_records)}</strong>{" "}
                            {locale === "vi" ? "công bố" : "publications"}
                          </span>
                          <span>•</span>
                          <span>{formatDate(item.created_at)}</span>
                          {authorStatus && authorStatus !== "NORMALIZING" && (
                            <>
                              <span>•</span>
                              <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-bold ${authorStatusColor(authorStatus)}`}>
                                {authorStatusLabel(authorStatus)}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 shrink-0">
                      {needsPublicationNormalization ? (
                        <button
                          type="button"
                          onClick={() => void handleNormalizePublication(item)}
                          disabled={isNorm}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 shadow-xs hover:border-[#3A5FC3] hover:text-[#3A5FC3] transition-colors cursor-pointer disabled:opacity-50"
                        >
                          {isNorm ? (
                            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-[#3A5FC3]" />
                          ) : (
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                          )}
                          {t.normalization.actions.normalize}
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => void handleNormalizeAuthors(item)}
                          disabled={isAuthorNorm}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-[#3A5FC3] px-3 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors cursor-pointer disabled:opacity-50"
                        >
                          {isAuthorNorm ? (
                            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                          ) : (
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                            </svg>
                          )}
                          {t.normalization.authorsTab.actions.normalizeAuthors}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* SECTION 2: Tác giả Scopus */}
      <section className="space-y-3">
        <div>
          <h2 className="text-base font-bold text-slate-800 sm:text-lg">
            {t.normalization.authorsTab.scopusAuthorsTitle}
          </h2>
        </div>

        {/* Search */}
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={authorSearch}
            onChange={(e) => {
              setAuthorSearch(e.target.value);
              setAuthorPage(1);
            }}
            placeholder={t.normalization.authorsTab.searchPlaceholder}
            className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm text-slate-700 shadow-xs placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
          />
        </div>

        {/* Table */}
        <div className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-xs">
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
                  <th className="whitespace-nowrap px-4 py-3 text-center font-semibold text-slate-600">
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
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                      <div className="flex flex-col items-center gap-1">
                        <svg className="h-6 w-6 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                        </svg>
                        <span className="text-xs">
                          {locale === "vi" ? "Chưa có tác giả nào" : "No authors yet"}
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
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                            {author.variant_count}
                          </span>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <button
                          type="button"
                          onClick={() => void handleViewAuthorDetail(author)}
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:border-[#3A5FC3] hover:text-[#3A5FC3] transition-colors cursor-pointer shadow-2xs"
                        >
                          <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                          {t.normalization.authorsTab.actions.viewDetail}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {authorTotal > 20 && (
            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 bg-slate-50/50">
              <span className="text-xs text-slate-500">
                {locale === "vi"
                  ? `Hiển thị ${(authorPage - 1) * 20 + 1}–${Math.min(authorPage * 20, authorTotal)} trong ${formatCount(authorTotal)}`
                  : `Showing ${(authorPage - 1) * 20 + 1}–${Math.min(authorPage * 20, authorTotal)} of ${formatCount(authorTotal)}`}
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setAuthorPage((p) => Math.max(1, p - 1))}
                  disabled={authorPage <= 1}
                  className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
                >
                  ‹
                </button>
                <span className="px-2 text-xs font-semibold text-slate-700">{authorPage}</span>
                <button
                  type="button"
                  onClick={() => setAuthorPage((p) => p + 1)}
                  disabled={authorPage * 20 >= authorTotal}
                  className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
                >
                  ›
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Author Detail Modal */}
      {selectedAuthor && (
        <ModalPortal>
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
            <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <h2 className="text-base font-bold text-slate-800">
                  {t.normalization.authorsTab.detail.title}
                </h2>
                <button
                  type="button"
                  onClick={() => setSelectedAuthor(null)}
                  className="inline-flex items-center justify-center rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
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
                        <div key={v.id} className="flex items-start gap-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
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
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#3A5FC3] px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors cursor-pointer"
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
