import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ScopusImport,
  getImportHistory,
  normalizeImport,
} from "../../api/imports";
import { ApiError } from "../../api/client";
import { useI18n } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import ModalPortal from "../../components/common/ModalPortal";
import ConfirmModal from "../../components/common/ConfirmModal";

const numberFormatter = new Intl.NumberFormat("vi-VN");

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

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

export default function NormalizationPage() {
  const { t, locale } = useI18n();
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const requestedImportId = searchParams.get("import");

  const [activeTab, setActiveTab] = useState<"publications" | "authors">("publications");
  const [history, setHistory] = useState<ScopusImport[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [historyStatusFilter, setHistoryStatusFilter] = useState<"all" | "completed" | "failed">("all");

  const [normalizingId, setNormalizingId] = useState<string | null>(null);
  const [detailModalItem, setDetailModalItem] = useState<ScopusImport | null>(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [reNormalizeTarget, setReNormalizeTarget] = useState<ScopusImport | null>(null);

  const highlightedRef = useRef<HTMLDivElement | null>(null);

  const fetchImports = async () => {
    try {
      setLoading(true);
      const res = await getImportHistory(true);
      setHistory(res.items || []);
    } catch (err: unknown) {
      toast.error(
        locale === "vi" ? "Lỗi tải dữ liệu" : "Data load error",
        err instanceof ApiError ? err.message : "Không thể tải danh sách đợt nhập.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchImports();
  }, []);

  // Only Scopus imports are eligible for Publication Normalization
  const scopusImports = useMemo(() => {
    return history.filter((item) => item.type !== "LECTURERS");
  }, [history]);

  // Lifecycle classifications
  const isPending = (item: ScopusImport): boolean => {
    return (
      item.status === "STAGED" &&
      (!item.normalization || item.normalization.status !== "COMPLETED")
    );
  };

  const isProcessing = (item: ScopusImport): boolean => {
    return (
      item.normalization?.status === "NORMALIZING" ||
      ["RECEIVED", "PARSING", "VALIDATED"].includes(item.status)
    );
  };

  const isCompleted = (item: ScopusImport): boolean => {
    return (
      item.status === "APPLIED" ||
      item.normalization?.status === "COMPLETED"
    );
  };

  const isFailed = (item: ScopusImport): boolean => {
    return (
      item.status === "FAILED" ||
      item.normalization?.status === "FAILED"
    );
  };

  // 4 Summary KPI counters
  const countPending = scopusImports.filter(isPending).length;
  const countProcessing = scopusImports.filter(isProcessing).length;
  const countCompleted = scopusImports.filter(isCompleted).length;
  const countFailed = scopusImports.filter(isFailed).length;

  // Actionable queue items
  const pendingImports = useMemo(() => {
    return scopusImports.filter(isPending);
  }, [scopusImports]);

  // Processed history items
  const historyImports = useMemo(() => {
    return scopusImports.filter((item) => !isPending(item));
  }, [scopusImports]);

  // Filtered history list
  const filteredHistory = useMemo(() => {
    let list = historyImports;
    if (historyStatusFilter === "completed") {
      list = list.filter(isCompleted);
    } else if (historyStatusFilter === "failed") {
      list = list.filter(isFailed);
    }
    if (!search.trim()) return list;
    const q = search.toLowerCase().trim();
    return list.filter(
      (item) =>
        item.file_name.toLowerCase().includes(q) ||
        item.id.toLowerCase().includes(q) ||
        (item.performed_by && item.performed_by.toLowerCase().includes(q)),
    );
  }, [historyImports, historyStatusFilter, search]);

  // Deep-link scroll into view
  useEffect(() => {
    if (requestedImportId && !loading) {
      const el = document.getElementById(`import-item-${requestedImportId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [requestedImportId, loading]);

  const handleNormalize = async (item: ScopusImport) => {
    if (normalizingId) return;
    setNormalizingId(item.id);
    try {
      const normalized = await normalizeImport(item.id);
      // Auto-update history list without manual refresh
      setHistory((current) => current.map((i) => (i.id === normalized.id ? normalized : i)));

      // If modal is currently open for this item, update modal state
      if (detailModalItem && detailModalItem.id === normalized.id) {
        setDetailModalItem(normalized);
      }

      const n = normalized.normalization;
      const total = n?.canonical_processed ?? 0;
      const newCount = n?.canonical_new ?? 0;
      const existingCount = n?.canonical_existing ?? 0;
      const changedCount = n?.canonical_metadata_changed ?? 0;
      const msg =
        total === 0
          ? locale === "vi"
            ? "Không có bản ghi nào để chuẩn hóa."
            : "No records to normalize."
          : newCount === 0
            ? locale === "vi"
              ? `Tất cả ${total} bản ghi đã tồn tại trong hệ thống.`
              : `${total} records already exist in the system.`
            : locale === "vi"
              ? `Đã chuẩn hóa ${total} bản ghi: ${newCount} bài mới, ${existingCount + changedCount} đã tồn tại.`
              : `Normalized ${total} records: ${newCount} new, ${existingCount + changedCount} existing.`;
      toast.success(locale === "vi" ? "Chuẩn hóa hoàn tất" : "Normalization complete", msg);
    } catch (error: unknown) {
      toast.error(
        locale === "vi" ? "Lỗi chuẩn hóa" : "Normalization error",
        error instanceof ApiError ? error.message : (locale === "vi" ? "Không thể chuẩn hóa." : "Unable to normalize."),
      );
    } finally {
      setNormalizingId(null);
      setReNormalizeTarget(null);
    }
  };

  const handleOpenDetailModal = (item: ScopusImport) => {
    setDetailModalItem(item);
    setShowTechnicalDetails(false);
  };

  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-800 sm:text-2xl">
            {t.normalization.title}
          </h1>
          <p className="text-xs text-slate-500 sm:text-sm">
            {t.normalization.subtitle}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("publications")}
          className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs sm:text-sm font-bold transition-colors cursor-pointer ${
            activeTab === "publications"
              ? "bg-[#3A5FC3] text-white shadow-xs"
              : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
          }`}
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
          <span>{t.normalization.tabs.publications}</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("authors")}
          className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs sm:text-sm font-bold transition-colors cursor-pointer ${
            activeTab === "authors"
              ? "bg-[#3A5FC3] text-white shadow-xs"
              : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
          }`}
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
          <span>{t.normalization.tabs.authors}</span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600 border border-slate-200">
            {t.normalization.comingSoon}
          </span>
        </button>
      </div>

      {/* Tab Content: Authors Placeholder (M2.6B) */}
      {activeTab === "authors" && (
        <div className="rounded-xl border border-slate-200/80 bg-white p-8 text-center shadow-xs">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-[#3A5FC3] mb-3.5 border border-blue-100">
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          </div>
          <h2 className="text-base font-bold text-slate-800 sm:text-lg">
            {t.normalization.authorsPlaceholder}
          </h2>
          <p className="mt-2 max-w-md mx-auto text-xs text-slate-500 sm:text-sm">
            {t.normalization.authorsPlaceholderNote}
          </p>
          <div className="mt-4 inline-flex items-center gap-2 rounded-lg bg-slate-50 px-3.5 py-1.5 border border-slate-200 text-xs font-semibold text-slate-600">
            <span className="h-2 w-2 rounded-full bg-slate-400" />
            <span>M2.6B — {locale === "vi" ? "Chưa triển khai" : "Not implemented"}</span>
          </div>
        </div>
      )}

      {/* Tab Content: Publications Normalization (M2.6A Functional) */}
      {activeTab === "publications" && (
        <div className="space-y-5">
          {/* Summary KPI Cards — Matching /imports & /lecturers visual rhythm */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
              <span className="text-xs font-medium text-slate-500">
                {t.normalization.summary.pending}
              </span>
              <p className="mt-1 text-2xl font-black text-slate-800">
                {countPending}
              </p>
            </div>

            <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
              <span className="text-xs font-medium text-[#3A5FC3]">
                {t.normalization.summary.processing}
              </span>
              <p className="mt-1 text-2xl font-black text-[#3A5FC3]">
                {countProcessing}
              </p>
            </div>

            <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
              <span className="text-xs font-medium text-emerald-600">
                {t.normalization.summary.completed}
              </span>
              <p className="mt-1 text-2xl font-black text-emerald-600">
                {countCompleted}
              </p>
            </div>

            <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
              <span className="text-xs font-medium text-rose-600">
                {t.normalization.summary.failed}
              </span>
              <p className="mt-1 text-2xl font-black text-rose-600">
                {countFailed}
              </p>
            </div>
          </div>

          {/* SECTION 1: CẦN XỬ LÝ (Actionable Queue) */}
          <section className="space-y-3">
            <div>
              <h2 className="text-base font-bold text-slate-800 sm:text-lg">
                {t.normalization.pendingTitle}
              </h2>
              <p className="text-xs text-slate-500">
                {t.normalization.pendingSubtitle}
              </p>
            </div>

            {loading ? (
              <div className="rounded-xl border border-slate-200/80 bg-white p-8 text-center text-slate-400">
                <div className="flex flex-col items-center justify-center gap-2">
                  <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                  <span className="text-xs font-medium">{t.common.loading}</span>
                </div>
              </div>
            ) : pendingImports.length === 0 ? (
              <div className="rounded-xl border border-slate-200/80 bg-white p-8 text-center shadow-xs">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 mb-2.5 border border-emerald-100">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-sm font-bold text-slate-700">
                  {t.normalization.emptyPending}
                </h3>
                <p className="mt-1 text-xs text-slate-400">
                  {t.normalization.emptyPendingSub}
                </p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {pendingImports.map((item) => {
                  const isHighlighted = requestedImportId === item.id;
                  const isBusy = normalizingId === item.id;
                  return (
                    <div
                      key={item.id}
                      id={`import-item-${item.id}`}
                      ref={isHighlighted ? highlightedRef : null}
                      className={`rounded-xl border bg-white p-4 transition-all shadow-xs ${
                        isHighlighted
                          ? "border-[#3A5FC3] ring-2 ring-[#3A5FC3]/20 bg-blue-50/20"
                          : "border-slate-200/80 hover:border-slate-300"
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        {/* Left: Info */}
                        <div className="flex items-start gap-3 min-w-0">
                          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-[#3A5FC3] border border-blue-100/80 shrink-0">
                            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-bold text-slate-800 text-sm truncate max-w-xs sm:max-w-md" title={item.file_name}>
                                {item.file_name}
                              </span>
                              <span className="inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-[#3A5FC3]">
                                Scopus
                              </span>
                            </div>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                              <span>
                                <strong className="text-slate-700">{numberFormatter.format(item.total_records)}</strong> {locale === "vi" ? "bản ghi" : "records"}
                              </span>
                              <span>•</span>
                              <span>{formatDate(item.created_at)}</span>
                              <span>•</span>
                              <span className="inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-[#3A5FC3]">
                                {t.normalization.summary.pending}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Right: Actions */}
                        <div className="flex items-center gap-2 shrink-0 justify-end pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                          <button
                            type="button"
                            onClick={() => handleOpenDetailModal(item)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition-colors cursor-pointer"
                          >
                            <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                            <span>{t.normalization.actions.viewDetail}</span>
                          </button>

                          <button
                            type="button"
                            disabled={isBusy}
                            onClick={() => void handleNormalize(item)}
                            className="inline-flex min-w-36 items-center justify-center gap-1.5 rounded-lg bg-[#3A5FC3] px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors cursor-pointer disabled:opacity-50"
                          >
                            {isBusy ? (
                              <>
                                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                                <span>{t.normalization.actions.normalizing}</span>
                              </>
                            ) : (
                              <>
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                </svg>
                                <span>{t.normalization.actions.normalize}</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* SECTION 2: LỊCH SỬ ĐÃ XỬ LÝ (Processed History) */}
          <section className="space-y-3 pt-2">
            <div>
              <h2 className="text-base font-bold text-slate-800 sm:text-lg">
                {t.normalization.historyTitle}
              </h2>
            </div>

            {/* Toolbar: Search input + Status dropdown */}
            <div className="flex flex-col gap-3 rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs sm:flex-row sm:items-center sm:justify-between">
              <div className="relative flex-1">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={t.normalization.searchPlaceholder}
                  className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 sm:text-sm"
                />
              </div>

              <div className="flex items-center gap-2">
                <label htmlFor="norm-history-status-filter" className="text-xs font-medium text-slate-500 whitespace-nowrap">
                  {locale === "vi" ? "Trạng thái:" : "Status:"}
                </label>
                <select
                  id="norm-history-status-filter"
                  value={historyStatusFilter}
                  onChange={(e) => setHistoryStatusFilter(e.target.value as "all" | "completed" | "failed")}
                  className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
                >
                  <option value="all">{locale === "vi" ? "Tất cả" : "All"}</option>
                  <option value="completed">{t.normalization.summary.completed}</option>
                  <option value="failed">{t.normalization.summary.failed}</option>
                </select>
              </div>
            </div>

            {/* Simple History Table */}
            <div className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="border-b border-slate-200 bg-slate-50/80 text-[11px] font-bold uppercase tracking-wider text-slate-600">
                    <tr>
                      <th className="px-4 py-3">{t.normalization.table.fileName}</th>
                      <th className="px-4 py-3 text-center">{t.normalization.table.importedAt}</th>
                      <th className="px-4 py-3 text-center">{t.normalization.table.sourceRecords}</th>
                      <th className="px-4 py-3 text-center">{t.normalization.table.status}</th>
                      <th className="w-28 px-3 py-3 text-center">{t.normalization.table.actions}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loading ? (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                            <span>{t.common.loading}</span>
                          </div>
                        </td>
                      </tr>
                    ) : filteredHistory.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-slate-400">
                          {t.common.noData}
                        </td>
                      </tr>
                    ) : (
                      filteredHistory.map((item) => {
                        const n = item.normalization;
                        return (
                          <tr key={item.id} className="transition-colors hover:bg-slate-50/70">
                            {/* File Name */}
                            <td className="px-4 py-3.5">
                              <div className="flex items-center gap-2.5">
                                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-blue-100/80 bg-blue-50 text-[#3A5FC3] shrink-0">
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

                            {/* Time */}
                            <td className="px-4 py-3.5 text-center text-slate-600 whitespace-nowrap">
                              {formatDate(item.created_at)}
                            </td>

                            {/* Records */}
                            <td className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">
                              {numberFormatter.format(item.processed_records)} / {numberFormatter.format(item.total_records)}
                            </td>

                            {/* Result */}
                            <td className="px-4 py-3.5 text-center whitespace-nowrap">
                              {n && n.status === "COMPLETED" ? (
                                <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
                                  {t.normalization.status.completed}
                                </span>
                              ) : n && n.status === "NORMALIZING" ? (
                                <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-[#3A5FC3]">
                                  <span className="h-2 w-2 animate-spin rounded-full border-2 border-[#3A5FC3] border-t-transparent" />
                                  {t.normalization.status.normalizing} ({n.progress_percent}%)
                                </span>
                              ) : isFailed(item) ? (
                                <span className="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-xs font-bold text-rose-700">
                                  {t.normalization.status.failed}
                                </span>
                              ) : (
                                <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                                  {item.status === "CANCELLED" ? t.normalization.status.cancelled : t.normalization.status.notNormalized}
                                </span>
                              )}
                            </td>

                            {/* Actions: [Chi tiết] only */}
                            <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap">
                              <button
                                type="button"
                                onClick={() => handleOpenDetailModal(item)}
                                className="inline-flex h-7 w-20 items-center justify-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-[11px] font-semibold text-slate-700 shadow-2xs transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] cursor-pointer whitespace-nowrap"
                              >
                                <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                </svg>
                                <span>{t.normalization.actions.viewDetail}</span>
                              </button>
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
        </div>
      )}

      {/* NORMALIZATION DETAIL MODAL */}
      {detailModalItem && (
        <ModalPortal>
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
            <div
              className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
              onClick={() => setDetailModalItem(null)}
            />

            <section className="relative flex flex-col w-full max-w-4xl max-h-[90vh] rounded-2xl bg-white shadow-2xl overflow-hidden z-10 animate-in zoom-in-95 duration-150">
              {/* Modal Header */}
              <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4 bg-slate-50/50">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-[#3A5FC3] border border-blue-100 shrink-0">
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-sm sm:text-base font-bold text-slate-800 truncate">
                      {locale === "vi" ? "Chi tiết chuẩn hóa dữ liệu" : "Data Normalization Details"}
                    </h2>
                    <p className="text-xs text-slate-500 truncate" title={detailModalItem.file_name}>
                      {detailModalItem.file_name}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setDetailModalItem(null)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
                  aria-label={t.common.close}
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </header>

              {/* Modal Body */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs text-slate-700">
                {/* ROW 1: 2 Equal Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-stretch">
                  {/* CARD 1: THÔNG TIN NGUỒN */}
                  <div className="flex flex-col rounded-xl border border-blue-100 bg-blue-50/20 p-4 shadow-2xs">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-blue-100/70">
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#3A5FC3]/10 text-[#3A5FC3]">
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                          </svg>
                        </div>
                        <div>
                          <h3 className="text-xs font-bold uppercase tracking-wider text-blue-800">
                            {t.normalization.detail.rawIngestionTitle}
                          </h3>
                        </div>
                      </div>
                      <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
                        {locale === "vi" ? "Đã tiếp nhận" : "Ingestion complete"}
                      </span>
                    </div>

                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-2 text-center mb-3">
                      <div className="rounded-lg border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                        <span className="text-[10px] font-medium text-slate-500 uppercase">{locale === "vi" ? "Tổng bản ghi" : "Total records"}</span>
                        <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detailModalItem.total_records)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-200/80 bg-white p-2.5 shadow-2xs">
                        <span className="text-[10px] font-medium text-emerald-600 uppercase">{locale === "vi" ? "Hợp lệ" : "Valid"}</span>
                        <p className="mt-0.5 text-base font-black text-emerald-600">{numberFormatter.format(detailModalItem.imported_records)}</p>
                      </div>
                      <div className="rounded-lg border border-rose-200/80 bg-white p-2.5 shadow-2xs">
                        <span className="text-[10px] font-medium text-rose-600 uppercase">{locale === "vi" ? "Lỗi" : "Failed"}</span>
                        <p className="mt-0.5 text-base font-black text-rose-600">{numberFormatter.format(detailModalItem.failed_records)}</p>
                      </div>
                    </div>

                    {/* Info */}
                    <div className="mt-auto space-y-1.5 rounded-lg border border-blue-100/80 bg-white/75 p-3 text-xs text-slate-600">
                      <div className="flex justify-between gap-2">
                        <span className="text-slate-400 shrink-0">{locale === "vi" ? "Tên tệp:" : "File name:"}</span>
                        <span className="font-semibold text-slate-800 truncate text-right" title={detailModalItem.file_name}>{detailModalItem.file_name}</span>
                      </div>
                      <div className="flex justify-between gap-2">
                        <span className="text-slate-400 shrink-0">{locale === "vi" ? "Người thực hiện:" : "Performed by:"}</span>
                        <span className="font-semibold text-slate-700">{detailModalItem.performed_by || (locale === "vi" ? "Không xác định" : "Unknown")}</span>
                      </div>
                      <div className="flex justify-between gap-2">
                        <span className="text-slate-400 shrink-0">{locale === "vi" ? "Thời gian tiếp nhận:" : "Imported at:"}</span>
                        <span className="font-medium text-slate-700">{formatDate(detailModalItem.created_at)}</span>
                      </div>
                    </div>
                  </div>

                  {/* CARD 2: KẾT QUẢ XỬ LÝ */}
                  <div className="flex flex-col rounded-xl border border-slate-200/80 bg-slate-50/40 p-4 shadow-2xs">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-200/70">
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                          </svg>
                        </div>
                        <div>
                          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                            {t.normalization.detail.metricsTitle}
                          </h3>
                        </div>
                      </div>
                      {detailModalItem.normalization && detailModalItem.normalization.status === "COMPLETED" ? (
                        <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
                          {t.normalization.status.completed}
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-[#3A5FC3]">
                          {t.normalization.summary.pending}
                        </span>
                      )}
                    </div>

                    {detailModalItem.normalization ? (
                      <>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center mb-3">
                          <div className="rounded-lg border border-emerald-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-emerald-700 uppercase">{t.normalization.table.newPublications}</span>
                            <p className="mt-0.5 text-base font-black text-emerald-700">{numberFormatter.format(detailModalItem.normalization.canonical_new)}</p>
                          </div>
                          <div className="rounded-lg border border-slate-200 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-slate-600 uppercase">{t.normalization.table.existing}</span>
                            <p className="mt-0.5 text-base font-black text-slate-700">{numberFormatter.format(detailModalItem.normalization.canonical_existing)}</p>
                          </div>
                          <div className="rounded-lg border border-amber-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-amber-700 uppercase">{t.normalization.table.metadataChanged}</span>
                            <p className="mt-0.5 text-base font-black text-amber-700">{numberFormatter.format(detailModalItem.normalization.canonical_metadata_changed)}</p>
                          </div>
                          <div className="rounded-lg border border-rose-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-rose-700 uppercase">{t.normalization.table.errors}</span>
                            <p className="mt-0.5 text-base font-black text-rose-700">{numberFormatter.format(detailModalItem.normalization.canonical_failed)}</p>
                          </div>
                        </div>

                        {detailModalItem.normalization.canonical_intra_duplicate > 0 && (
                          <div className="mb-2 rounded-lg border border-slate-200 bg-white p-2 text-center">
                            <span className="text-[10px] font-medium text-slate-600">{locale === "vi" ? "Trùng EID nội tệp:" : "Intra-file Duplicates:"} </span>
                            <strong className="text-slate-800 font-bold">{numberFormatter.format(detailModalItem.normalization.canonical_intra_duplicate)}</strong>
                          </div>
                        )}

                        <div className="mt-auto rounded-lg border border-slate-200/60 bg-white/75 p-2.5 text-[11px] text-slate-500">
                          {locale === "vi"
                            ? "Dữ liệu Scopus đã được chuẩn hóa và ánh xạ vào kho công bố khoa học hợp nhất."
                            : "Scopus data has been normalized and mapped to the canonical publication store."}
                        </div>
                      </>
                    ) : (
                      <div className="flex flex-1 flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white/60 p-5 text-center">
                        <svg className="h-7 w-7 text-slate-300 mb-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                        </svg>
                        <p className="text-xs font-semibold text-slate-600">{t.normalization.summary.pending}</p>
                        <p className="mt-1 text-[11px] text-slate-400">
                          {locale === "vi"
                            ? "Đợt nhập này đã tiếp nhận nguồn thành công và đang chờ thực hiện chuẩn hóa dữ liệu."
                            : "This import batch is waiting for publication normalization."}
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* ROW 2: Chi tiết / Lỗi */}
                {detailModalItem.row_errors && detailModalItem.row_errors.length > 0 && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 text-xs">
                    <h4 className="mb-1.5 font-bold text-amber-800">{locale === "vi" ? "Chi tiết lỗi dòng" : "Row Errors"}</h4>
                    <ul className="max-h-28 space-y-1 overflow-y-auto text-amber-900">
                      {detailModalItem.row_errors.map((rowError, idx) => (
                        <li key={idx}>
                          {locale === "vi" ? "Dòng" : "Row"} {rowError.row_number ?? "—"}: {rowError.message ?? rowError.code ?? "Lỗi"}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Collapsible: Technical info & Provenance */}
                <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3">
                  <button
                    type="button"
                    onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                    className="flex w-full items-center justify-between text-xs font-bold text-slate-700 hover:text-[#3A5FC3] cursor-pointer"
                  >
                    <span>{t.normalization.detail.provenanceTitle}</span>
                    <svg
                      className={`h-4 w-4 transition-transform ${showTechnicalDetails ? "rotate-180" : ""}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {showTechnicalDetails && (
                    <div className="mt-3 pt-3 border-t border-slate-200/60 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-slate-400 block">{locale === "vi" ? "Mã đợt nhập (ID):" : "Import ID:"}</span>
                        <span className="font-mono text-slate-700 font-semibold">{detailModalItem.id}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">{locale === "vi" ? "Thời lượng xử lý:" : "Duration:"}</span>
                        <span className="font-semibold text-slate-700">{formatDuration(detailModalItem.duration_seconds)}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">{t.normalization.detail.publicationLinks}:</span>
                        <span className="font-semibold text-slate-700">{numberFormatter.format(detailModalItem.usage?.publication_source_links ?? 0)}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">{t.normalization.detail.authorVariantLinks}:</span>
                        <span className="font-semibold text-slate-700">{numberFormatter.format(detailModalItem.usage?.author_variant_links ?? 0)}</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Modal Footer */}
              <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-100 px-5 py-3 bg-slate-50/50">
                {isPending(detailModalItem) ? (
                  <button
                    type="button"
                    disabled={Boolean(normalizingId)}
                    onClick={() => void handleNormalize(detailModalItem)}
                    className="inline-flex min-w-36 items-center justify-center gap-1.5 rounded-lg bg-[#3A5FC3] px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors cursor-pointer disabled:opacity-50"
                  >
                    {normalizingId === detailModalItem.id ? (
                      <>
                        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                        <span>{t.normalization.actions.normalizing}</span>
                      </>
                    ) : (
                      <>
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                        </svg>
                        <span>{t.normalization.actions.normalize}</span>
                      </>
                    )}
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={Boolean(normalizingId)}
                    onClick={() => setReNormalizeTarget(detailModalItem)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <span>{t.normalization.actions.reNormalize}</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => setDetailModalItem(null)}
                  className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer shadow-2xs"
                >
                  {t.common.close}
                </button>
              </footer>
            </section>
          </div>
        </ModalPortal>
      )}

      {/* Confirmation Modal for Re-normalization */}
      {reNormalizeTarget && (
        <ConfirmModal
          open={Boolean(reNormalizeTarget)}
          variant="warning"
          loading={Boolean(normalizingId)}
          title={t.normalization.actions.confirmReNormalize}
          description={
            <span>
              {t.normalization.actions.reNormalizePrompt}
              <br />
              <strong className="text-slate-800 mt-1 block">{reNormalizeTarget.file_name}</strong>
            </span>
          }
          confirmLabel={t.normalization.actions.reNormalize}
          cancelLabel={t.common.cancel}
          onConfirm={() => void handleNormalize(reNormalizeTarget)}
          onCancel={() => {
            if (!normalizingId) {
              setReNormalizeTarget(null);
            }
          }}
        />
      )}
    </div>
  );
}
