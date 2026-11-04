import { adminLabel, isCorruptedName } from "../../utils/displayName";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  ScopusImport,
  getConfirmedImportIds,
  getImportHistory,
  isImportConfirmed,
  isSupersededByNewerConfirmedDuplicate,
  normalizeImport,
} from "../../api/imports";
import { ApiError } from "../../api/client";
import { useI18n } from "../../i18n";
import { buttonClass } from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";
import ModalPortal from "../../components/common/ModalPortal";
import ConfirmModal from "../../components/common/ConfirmModal";
import AffiliationsTab from "./AffiliationsTab";
import AuthorsTab from "./AuthorsTab";
import MatchingTab from "./MatchingTab";

const numberFormatter = new Intl.NumberFormat("vi-VN");

const badgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-[#3A5FC3] bg-white px-2.5 text-center text-sm font-bold leading-none text-[#3A5FC3] hover:bg-blue-50";
// "Basic" neutral style — same as the "Chi tiết" action button, not the blue brand badge.
const basicBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900";
const ingestionSuccessBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-emerald-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-emerald-700 hover:bg-emerald-50";
const completedStatusBadgeClassName = ingestionSuccessBadgeClassName;

// Same convention as the Imports page: the full id is a 36-char UUID, too
// long for a table cell. Show only the first 8 characters; the full value
// stays available via the `title` tooltip.
function shortId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

function formatDate(isoString?: string | null): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "—";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
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

  // Each tab is its own sidebar entry and route (/normalization/:tab); this
  // page component is shared because the four tabs' data and modals overlap.
  type TabKey = "publications" | "authors" | "affiliations" | "matching";
  const validTabs: TabKey[] = ["publications", "authors", "affiliations", "matching"];
  const { tab: tabParam } = useParams<{ tab: string }>();
  const activeTab: TabKey =
    tabParam && validTabs.includes(tabParam as TabKey) ? (tabParam as TabKey) : "publications";

  useEffect(() => {
    if (activeTab === "publications") setHistoryPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);
  const [history, setHistory] = useState<ScopusImport[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState("");
  const [historyStatusFilter, setHistoryStatusFilter] = useState<"all" | "processing" | "completed" | "failed">("all");
  const [pendingSearchInput, setPendingSearchInput] = useState("");
  const [pendingStatusFilter, setPendingStatusFilter] = useState<"ALL" | "PENDING" | "SUPERSEDED">("ALL");
  const [pendingPage, setPendingPage] = useState(1);
  const [pendingPageSize, setPendingPageSize] = useState(10);

  const handleResetSearch = () => {
    setSearchInput("");
    setHistoryStatusFilter("all");
    setHistoryPage(1);
  };

  const isResetDisabled = !searchInput && historyStatusFilter === "all";

  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(10);
  const [normalizingId, setNormalizingId] = useState<string | null>(null);
  const [detailModalItem, setDetailModalItem] = useState<ScopusImport | null>(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [reNormalizeTarget, setReNormalizeTarget] = useState<ScopusImport | null>(null);

  const [confirmedIds, setConfirmedIds] = useState<string[]>(getConfirmedImportIds());

  const highlightedRef = useRef<HTMLTableRowElement | null>(null);

  const fetchImports = async () => {
    try {
      setLoading(true);
      setConfirmedIds(getConfirmedImportIds());
      const res = await getImportHistory(true);
      setHistory(res.items || []);
    } catch (err: unknown) {
      toast.error(
        locale === "vi" ? "Lỗi tải dữ liệu" : "Data load error",
        err instanceof ApiError ? err.message : locale === "vi" ? "Không thể tải danh sách đợt nhập." : "Could not load the import batches.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchImports();
  }, []);

  useEffect(() => {
    const handleStorageChange = () => {
      setConfirmedIds(getConfirmedImportIds());
    };
    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("focus", handleStorageChange);
    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("focus", handleStorageChange);
    };
  }, []);

  // Only Scopus imports are eligible for Publication Normalization.
  // Imports cancelled before normalization ever started never belong to this page.
  // Staged imports awaiting admin confirmation ("Chờ xử lý") do not appear until admin confirms import.
  const scopusImports = useMemo(() => {
    return history.filter(
      (item) =>
        item.type !== "LECTURERS" &&
        !(item.status === "CANCELLED" && !item.normalization) &&
        isImportConfirmed(item, confirmedIds),
    );
  }, [history, confirmedIds]);

  // Lifecycle classifications
  const isPending = (item: ScopusImport): boolean => {
    return (
      item.status === "STAGED" &&
      (!item.normalization || item.normalization.status !== "COMPLETED")
    );
  };

  // A newer, already-confirmed duplicate exists: normalizing this one would
  // process stale data. Same rule as the "Thay thế" badge on the Imports page.
  const isSuperseded = (item: ScopusImport): boolean =>
    isSupersededByNewerConfirmedDuplicate(item, history, confirmedIds);

  const isProcessing = (item: ScopusImport): boolean => {
    return (
      item.normalization?.status === "NORMALIZING" ||
      ["RECEIVED", "PARSING", "VALIDATED"].includes(item.status)
    );
  };

  // Chuẩn hóa xong nhưng có dòng bị lỗi (vd. CSV không đúng định dạng Scopus) không được coi là thành công hoàn toàn.
  const hasRowErrors = (item: ScopusImport): boolean => {
    return (
      item.normalization?.status === "COMPLETED" &&
      (item.normalization.canonical_failed ?? 0) > 0
    );
  };

  const isCompleted = (item: ScopusImport): boolean => {
    return (
      !hasRowErrors(item) &&
      (item.status === "APPLIED" || item.normalization?.status === "COMPLETED")
    );
  };

  const isFailed = (item: ScopusImport): boolean => {
    return (
      item.status === "FAILED" ||
      item.normalization?.status === "FAILED" ||
      hasRowErrors(item)
    );
  };

  // Actionable queue items
  const pendingImports = useMemo(() => {
    return scopusImports.filter(isPending);
  }, [scopusImports]);

  const pendingCountAll = pendingImports.length;
  const pendingCountAwaiting = pendingImports.filter((item) => !isSuperseded(item)).length;
  const pendingCountSuperseded = pendingImports.filter(isSuperseded).length;

  const filteredPendingImports = useMemo(() => {
    let list = pendingImports;
    if (pendingStatusFilter === "PENDING") {
      list = list.filter((item) => !isSuperseded(item));
    } else if (pendingStatusFilter === "SUPERSEDED") {
      list = list.filter(isSuperseded);
    }
    const q = pendingSearchInput.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (item) =>
        item.file_name.toLowerCase().includes(q) ||
        item.id.toLowerCase().includes(q) ||
        (item.performed_by && item.performed_by.toLowerCase().includes(q)),
    );
  }, [pendingImports, pendingSearchInput, pendingStatusFilter]);

  const pendingTotalPages = Math.max(1, Math.ceil(filteredPendingImports.length / pendingPageSize));
  const currentPendingPage = Math.min(pendingPage, pendingTotalPages);
  const paginatedPendingImports = useMemo(() => {
    return filteredPendingImports.slice(
      (currentPendingPage - 1) * pendingPageSize,
      currentPendingPage * pendingPageSize,
    );
  }, [filteredPendingImports, currentPendingPage, pendingPageSize]);

  const handlePendingPageChange = (newPage: number) => {
    if (newPage === pendingPage || newPage < 1 || newPage > pendingTotalPages) return;
    setPendingPage(newPage);
  };

  const handlePendingPageSizeChange = (newSize: number) => {
    if (newSize === pendingPageSize) return;
    setPendingPageSize(newSize);
    setPendingPage(1);
  };

  // Processed history items
  const historyImports = useMemo(() => {
    return scopusImports.filter((item) => !isPending(item));
  }, [scopusImports]);

  const historyCountAll = historyImports.length;
  const historyCountProcessing = historyImports.filter(isProcessing).length;
  const historyCountCompleted = historyImports.filter(isCompleted).length;
  const historyCountFailed = historyImports.filter(isFailed).length;

  // Filtered history list
  const filteredHistory = useMemo(() => {
    let list = historyImports;
    if (historyStatusFilter === "processing") {
      list = list.filter(isProcessing);
    } else if (historyStatusFilter === "completed") {
      list = list.filter(isCompleted);
    } else if (historyStatusFilter === "failed") {
      list = list.filter(isFailed);
    }
    const q = searchInput.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (item) =>
        item.file_name.toLowerCase().includes(q) ||
        item.id.toLowerCase().includes(q) ||
        (item.performed_by && item.performed_by.toLowerCase().includes(q)),
    );
  }, [historyImports, historyStatusFilter, searchInput]);

  const historyTotalPages = Math.max(1, Math.ceil(filteredHistory.length / historyPageSize));
  const currentHistoryPage = Math.min(historyPage, historyTotalPages);
  const paginatedHistory = useMemo(() => {
    return filteredHistory.slice(
      (currentHistoryPage - 1) * historyPageSize,
      currentHistoryPage * historyPageSize,
    );
  }, [filteredHistory, currentHistoryPage, historyPageSize]);

  const formatPerformedBy = (name: string | null | undefined): string => {
    if (!name || name === "Không xác định") {
      return locale === "vi" ? "Không xác định" : "Unknown";
    }
    if (isCorruptedName(name)) {
      return adminLabel(locale === "vi" ? "vi" : "en");
    }
    return name;
  };

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
      {activeTab === "affiliations" && (
        <div className="tab-fade-in space-y-4">
          <AffiliationsTab locale={locale} />
        </div>
      )}

      {activeTab === "matching" && (
        <div className="tab-fade-in space-y-4">
          <MatchingTab locale={locale} />
        </div>
      )}

      {/* Tab Content: Authors Tab (M2.6B) */}
      {activeTab === "authors" && (
        <div className="tab-fade-in space-y-4">
          <AuthorsTab
            scopusImports={scopusImports}
            locale={locale}
            onRefresh={fetchImports}
            onViewDetail={handleOpenDetailModal}
          />
        </div>
      )}

      {/* Tab Content: Publications Normalization (M2.6A Functional) */}
      {activeTab === "publications" && (
        <div className="tab-fade-in space-y-5">
          {/* SECTION 1: CẦN XỬ LÝ (Actionable Queue Table) */}
          <section className="space-y-3">
            <div>
              <h2 className="text-base font-bold text-slate-800 sm:text-lg">
                {t.normalization.pendingTitle}
              </h2>
              <p className="text-xs text-slate-500">
                {t.normalization.pendingSubtitle}
              </p>
            </div>

            {/* Toolbar: Search + status filter (both apply live) */}
            <div className="flex flex-col gap-3 rounded-[5px] border border-slate-200/80 bg-white p-3.5 shadow-xs sm:flex-row sm:items-center sm:justify-between">
              <div className="relative flex-1">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <input
                  type="text"
                  aria-label={t.common.search}
                  value={pendingSearchInput}
                  onChange={(e) => { setPendingSearchInput(e.target.value); setPendingPage(1); }}
                  placeholder={locale === "vi" ? "Tìm theo tên tệp, người thực hiện hoặc mã phiên..." : t.normalization.searchPlaceholder}
                  className="h-control w-full rounded-control border border-line bg-slate-50 pl-9 pr-3 text-[13px] text-ink placeholder:text-ink-faint focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20"
                />
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <select
                  aria-label={locale === "vi" ? "Trạng thái" : "Status"}
                  value={pendingStatusFilter}
                  onChange={(e) => { setPendingStatusFilter(e.target.value as "ALL" | "PENDING" | "SUPERSEDED"); setPendingPage(1); }}
                  className="h-control shrink-0 rounded-control border border-line bg-slate-50 px-3 text-[13px] font-semibold text-ink focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20 cursor-pointer"
                >
                  <option value="ALL">
                    {locale === "vi" ? "Tất cả" : "All"} ({numberFormatter.format(pendingCountAll)})
                  </option>
                  <option value="PENDING">
                    {locale === "vi" ? "Chờ chuẩn hóa" : "Awaiting normalization"} ({numberFormatter.format(pendingCountAwaiting)})
                  </option>
                  <option value="SUPERSEDED">
                    {locale === "vi" ? "Lỗi / Đã hủy" : "Failed / Rolled back"} ({numberFormatter.format(pendingCountSuperseded)})
                  </option>
                </select>

                <button
                  type="button"
                  onClick={() => {
                    setPendingSearchInput("");
                    setPendingStatusFilter("ALL");
                    setPendingPage(1);
                  }}
                  disabled={!pendingSearchInput && pendingStatusFilter === "ALL"}
                  className={buttonClass("secondary")}
                >
                  <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <span className="truncate">{locale === "vi" ? "Đặt lại" : "Reset"}</span>
                </button>
              </div>
            </div>

            <div className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
                    <tr>
                      <th className="px-2.5 py-3.5 font-bold text-slate-700 whitespace-nowrap">{t.normalization.table.fileName}</th>
                      <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Loại dữ liệu" : "Data Type"}</th>
                      <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{t.normalization.table.importedAt}</th>
                      <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Bản ghi" : "Records"}</th>
                      <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Người thực hiện" : "Performed by"}</th>
                      <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Trạng thái" : "Status"}</th>
                      <th className="sticky right-0 z-[1] w-44 whitespace-nowrap border-l border-slate-200/80 bg-slate-50 px-2.5 py-3.5 text-center font-bold text-slate-700">{t.normalization.table.actions}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loading ? (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                            <span className="text-xs font-medium">{t.common.loading}</span>
                          </div>
                        </td>
                      </tr>
                    ) : filteredPendingImports.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-1.5">
                            <div className="flex h-10 w-10 items-center justify-center rounded-[5px] bg-slate-100/80 border border-slate-200/80 text-slate-400 mb-1">
                              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                            </div>
                            <span className="text-sm font-bold text-slate-700">
                              {pendingImports.length === 0
                                ? (locale === "vi" ? "Không có đợt nhập nào chờ xử lý" : "No pending imports awaiting normalization")
                                : (locale === "vi" ? "Không tìm thấy đợt nào khớp" : "No matching imports found")}
                            </span>
                            <span className="text-xs text-slate-400">
                              {pendingImports.length === 0
                                ? (locale === "vi" ? "Tất cả các đợt nhập Scopus đã được chuẩn hóa hoặc xử lý hoàn tất." : "All Scopus imports have been normalized or processed.")
                                : (locale === "vi" ? "Thử từ khóa khác." : "Try a different search term.")}
                            </span>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      paginatedPendingImports.map((item) => {
                        const isHighlighted = requestedImportId === item.id;
                        const superseded = isSuperseded(item);
                        return (
                          <tr
                            key={item.id}
                            id={`import-item-${item.id}`}
                            ref={isHighlighted ? highlightedRef : null}
                            className={`transition-colors hover:bg-slate-50/70 ${
                              isHighlighted ? "bg-blue-50/30" : ""
                            }`}
                          >
                            {/* File Name */}
                            <td className="px-2.5 py-3.5 align-middle whitespace-nowrap">
                              <div className="flex items-center gap-2.5">
                                <div className="flex h-8 w-8 items-center justify-center rounded-[5px] border border-slate-200/80 bg-slate-100 text-slate-600 shrink-0 shadow-2xs">
                                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                  </svg>
                                </div>
                                <div className="min-w-0 max-w-xs sm:max-w-sm">
                                  <span className="block font-bold text-slate-800 truncate" title={item.file_name}>
                                    {item.file_name}
                                  </span>
                                  <span className="block text-[10px] text-slate-400 truncate" title={item.id}>
                                    ID: {shortId(item.id)}
                                  </span>
                                </div>
                              </div>
                            </td>

                            {/* Data type */}
                            <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap font-medium">
                              <span className={basicBadgeClassName}>Scopus</span>
                            </td>

                            {/* Time */}
                            <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap font-medium text-slate-600">
                              {formatDate(item.created_at)}
                            </td>

                            {/* Records */}
                            <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap font-bold text-slate-800">
                              {numberFormatter.format(item.processed_records || item.imported_records || item.total_records)} / {numberFormatter.format(item.total_records)}
                            </td>

                            {/* Performed by */}
                            <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                              <span className={basicBadgeClassName}>{formatPerformedBy(item.performed_by)}</span>
                            </td>

                            {/* Status */}
                            <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                              {superseded ? (
                                <span className="inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-red-400 bg-white px-2.5 text-center text-sm font-bold leading-none text-red-700 hover:bg-red-50">
                                  {locale === "vi" ? "Thay thế" : "Superseded"}
                                </span>
                              ) : (
                                <span className={badgeClassName}>
                                  {locale === "vi" ? "Chờ chuẩn hóa" : "Awaiting normalization"}
                                </span>
                              )}
                            </td>

                            {/* Actions */}
                            <td className="sticky right-0 z-[1] whitespace-nowrap border-l border-slate-100 bg-white px-2.5 py-3.5 text-center align-middle">
                              <div className="flex items-center justify-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => void handleNormalize(item)}
                                  disabled={Boolean(normalizingId) || superseded}
                                  title={
                                    superseded
                                      ? (locale === "vi"
                                          ? "Đợt này đã được thay thế bởi một đợt nhập trùng mới hơn đã xác nhận."
                                          : "This import was superseded by a newer, confirmed duplicate.")
                                      : undefined
                                  }
                                  className="inline-flex h-badge w-32 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900 transition-all duration-150 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-slate-300/40 cursor-pointer disabled:cursor-not-allowed disabled:opacity-60 group"
                                >
                                  {normalizingId === item.id ? (
                                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700" />
                                  ) : (
                                    <svg className="h-3.5 w-3.5 transition-transform duration-150 group-hover:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                    </svg>
                                  )}
                                  <span>{normalizingId === item.id ? t.normalization.actions.normalizing : (locale === "vi" ? "Chuẩn hóa" : "Normalize")}</span>
                                </button>

                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {/* Footer info & Pagination Controls */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-xs text-slate-500">
                <div className="flex items-center gap-3">
                  <span>
                    {t.imports.showing} <strong>{paginatedPendingImports.length}</strong> {locale === "vi" ? "trong" : "of"} {filteredPendingImports.length} {locale === "vi" ? "đợt nhập" : "imports"}
                  </span>

                  <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
                    <span className="text-slate-500">{locale === "vi" ? "Hiển thị:" : "Show:"}</span>
                    <select
                      value={pendingPageSize}
                      onChange={(e) => handlePendingPageSizeChange(Number(e.target.value))}
                      className="h-7 rounded-[5px] border border-slate-200 bg-white px-1.5 text-xs font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer"
                    >
                      <option value={10}>10 / {locale === "vi" ? "trang" : "page"}</option>
                      <option value={30}>30 / {locale === "vi" ? "trang" : "page"}</option>
                      <option value={50}>50 / {locale === "vi" ? "trang" : "page"}</option>
                      <option value={100}>100 / {locale === "vi" ? "trang" : "page"}</option>
                    </select>
                  </div>
                </div>

                <nav aria-label="Pagination" className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => handlePendingPageChange(currentPendingPage - 1)}
                    disabled={currentPendingPage <= 1}
                    className={buttonClass("secondary", "sm")}
                  >
                    {t.imports.previousPage}
                  </button>
                  <span className="text-slate-400 px-0.5">{t.imports.page}</span>
                  <input
                    type="number"
                    aria-label={locale === "vi" ? "Đến trang" : "Go to page"}
                    min={1}
                    max={pendingTotalPages}
                    value={currentPendingPage}
                    onChange={(e) => {
                      const val = Math.max(1, Math.min(pendingTotalPages, parseInt(e.target.value, 10) || 1));
                      handlePendingPageChange(val);
                    }}
                    className="h-8 w-14 rounded-[5px] border border-slate-200 bg-white px-2 text-center text-[11px] font-bold text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <span className="text-slate-400">/ <strong className="text-slate-600">{pendingTotalPages}</strong></span>
                  <button
                    type="button"
                    onClick={() => handlePendingPageChange(currentPendingPage + 1)}
                    disabled={currentPendingPage >= pendingTotalPages}
                    className={buttonClass("secondary", "sm")}
                  >
                    {t.imports.nextPage}
                  </button>
                </nav>
              </div>
            </div>
          </section>

          {/* SECTION 2: LỊCH SỬ ĐÃ XỬ LÝ (Processed History) */}
          <section className="space-y-3 pt-2">
            <div>
              <h2 className="text-base font-bold text-slate-800 sm:text-lg">
                {t.normalization.historyTitle}
              </h2>
            </div>

            {/* Toolbar: Search + status filter (both apply live) */}
            <div className="flex flex-col gap-3 rounded-[5px] border border-slate-200/80 bg-white p-3.5 shadow-xs sm:flex-row sm:items-center sm:justify-between">
              <div className="relative flex-1">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <input
                  type="text"
                  aria-label={t.common.search}
                  value={searchInput}
                  onChange={(e) => { setSearchInput(e.target.value); setHistoryPage(1); }}
                  placeholder={locale === "vi" ? "Tìm theo tên tệp, người thực hiện hoặc mã phiên..." : t.normalization.searchPlaceholder}
                  className="h-control w-full rounded-control border border-line bg-slate-50 pl-9 pr-3 text-[13px] text-ink placeholder:text-ink-faint focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20"
                />
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <select
                  aria-label={locale === "vi" ? "Trạng thái" : "Status"}
                  value={historyStatusFilter}
                  onChange={(e) => { setHistoryStatusFilter(e.target.value as "all" | "processing" | "completed" | "failed"); setHistoryPage(1); }}
                  className="h-control shrink-0 rounded-control border border-line bg-slate-50 px-3 text-[13px] font-semibold text-ink focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20 cursor-pointer"
                >
                  <option value="all">
                    {locale === "vi" ? "Tất cả" : "All"} ({numberFormatter.format(historyCountAll)})
                  </option>
                  <option value="processing">
                    {t.normalization.summary.processing} ({numberFormatter.format(historyCountProcessing)})
                  </option>
                  <option value="completed">
                    {t.normalization.summary.completed} ({numberFormatter.format(historyCountCompleted)})
                  </option>
                  <option value="failed">
                    {t.normalization.summary.failed} ({numberFormatter.format(historyCountFailed)})
                  </option>
                </select>

                {/* Nút Đặt lại */}
                <button
                  type="button"
                  onClick={handleResetSearch}
                  disabled={isResetDisabled}
                  className={buttonClass("secondary")}
                >
                  <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <span className="truncate">{locale === "vi" ? "Đặt lại" : "Reset"}</span>
                </button>
              </div>
            </div>

            {/* Simple History Table */}
            <div className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
                    <tr>
                      <th className="px-2.5 py-3.5 font-bold text-slate-700 whitespace-nowrap">{t.normalization.table.fileName}</th>
                      <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Loại dữ liệu" : "Data Type"}</th>
                      <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{t.normalization.table.importedAt}</th>
                      <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Bản ghi" : "Records"}</th>
                      <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Người thực hiện" : "Performed by"}</th>
                      <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Trạng thái" : "Status"}</th>
                      <th className="sticky right-0 z-[1] w-44 whitespace-nowrap border-l border-slate-200/80 bg-slate-50 px-2.5 py-3.5 text-center font-bold text-slate-700">{t.normalization.table.actions}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loading ? (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                            <span>{t.common.loading}</span>
                          </div>
                        </td>
                      </tr>
                    ) : filteredHistory.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-1.5">
                            <div className="flex h-10 w-10 items-center justify-center rounded-[5px] bg-slate-100/80 border border-slate-200/80 text-slate-400 mb-1">
                              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                            </div>
                            <span className="text-sm font-bold text-slate-700">{t.common.noData}</span>
                            <span className="text-xs text-slate-400">
                              {locale === "vi" ? "Chưa có đợt nhập nào được chuẩn hóa." : "No normalized imports yet."}
                            </span>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      paginatedHistory.map((item) => {
                        const n = item.normalization;
                        return (
                          <tr key={item.id} className="transition-colors hover:bg-slate-50/70">
                            {/* File Name */}
                            <td className="px-2.5 py-3.5 align-middle whitespace-nowrap">
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
                                  <span className="block text-[10px] text-slate-400 truncate" title={item.id}>
                                    ID: {shortId(item.id)}
                                  </span>
                                </div>
                              </div>
                            </td>

                            {/* Data type */}
                            <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap font-medium">
                              <span className={basicBadgeClassName}>Scopus</span>
                            </td>

                            {/* Time */}
                            <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap font-medium text-slate-600">
                              {formatDate(item.created_at)}
                            </td>

                            {/* Records */}
                            <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap font-bold text-slate-800">
                              {numberFormatter.format(item.processed_records)} / {numberFormatter.format(item.total_records)}
                            </td>

                            {/* Performed by */}
                            <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                              <span className={basicBadgeClassName}>{formatPerformedBy(item.performed_by)}</span>
                            </td>

                            {/* Result */}
                            <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                              <span
                                className={
                                  n && n.status === "COMPLETED" && !hasRowErrors(item)
                                    ? completedStatusBadgeClassName
                                    : badgeClassName
                                }
                              >
                                {n && n.status === "COMPLETED" && hasRowErrors(item)
                                  ? t.normalization.status.completedWithErrors
                                  : n && n.status === "COMPLETED"
                                    ? t.normalization.status.completed
                                    : n && n.status === "NORMALIZING"
                                      ? `${t.normalization.status.normalizing} (${n.progress_percent}%)`
                                      : isFailed(item)
                                        ? t.normalization.status.failed
                                        : item.status === "CANCELLED"
                                          ? t.normalization.status.cancelled
                                          : t.normalization.status.notNormalized}
                              </span>
                            </td>

                            {/* Actions: [Chi tiết] only */}
                            <td className="sticky right-0 z-[1] whitespace-nowrap border-l border-slate-100 bg-white px-2.5 py-3.5 text-center align-middle">
                              <button
                                type="button"
                                onClick={() => handleOpenDetailModal(item)}
                                className="inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900 transition-colors cursor-pointer"
                              >
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

              {/* Footer info & Pagination Controls */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-xs text-slate-500">
                <div className="flex items-center gap-3">
                  <span>
                    {locale === "vi" ? "Hiển thị" : "Showing"} <strong>{paginatedHistory.length}</strong> {locale === "vi" ? "trong" : "of"} {filteredHistory.length} {locale === "vi" ? "đợt nhập" : "imports"}
                  </span>

                  {/* Page Size Selector */}
                  <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
                    <span className="text-slate-500">{locale === "vi" ? "Hiển thị:" : "Show:"}</span>
                    <select
                      value={historyPageSize}
                      onChange={(e) => {
                        setHistoryPageSize(Number(e.target.value));
                        setHistoryPage(1);
                      }}
                      className="h-7 rounded-[5px] border border-slate-200 bg-white px-1.5 text-xs font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer"
                    >
                      <option value={10}>10 / {locale === "vi" ? "trang" : "page"}</option>
                      <option value={30}>30 / {locale === "vi" ? "trang" : "page"}</option>
                      <option value={50}>50 / {locale === "vi" ? "trang" : "page"}</option>
                      <option value={100}>100 / {locale === "vi" ? "trang" : "page"}</option>
                    </select>
                  </div>
                </div>

                <nav aria-label="Pagination" className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setHistoryPage((prev) => Math.max(1, prev - 1))}
                    disabled={currentHistoryPage <= 1}
                    className={buttonClass("secondary", "sm")}
                  >
                    {locale === "vi" ? "Trang trước" : "Previous"}
                  </button>
                  <span className="text-slate-400 px-0.5">{locale === "vi" ? "Trang" : "Page"}</span>
                  <input
                    type="number"
                    aria-label={locale === "vi" ? "Đến trang" : "Go to page"}
                    min={1}
                    max={historyTotalPages}
                    value={currentHistoryPage}
                    onChange={(e) => {
                      const val = Math.max(1, Math.min(historyTotalPages, parseInt(e.target.value, 10) || 1));
                      setHistoryPage(val);
                    }}
                    className="h-8 w-14 rounded-[5px] border border-slate-200 bg-white px-2 text-center text-[11px] font-bold text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <span className="text-slate-400">/ <strong className="text-slate-600">{historyTotalPages}</strong></span>
                  <button
                    type="button"
                    onClick={() => setHistoryPage((prev) => Math.min(historyTotalPages, prev + 1))}
                    disabled={currentHistoryPage >= historyTotalPages}
                    className={buttonClass("secondary", "sm")}
                  >
                    {locale === "vi" ? "Trang sau" : "Next"}
                  </button>
                </nav>
              </div>
            </div>
          </section>

        </div>
      )}

      {/* NORMALIZATION DETAIL MODAL */}
      {detailModalItem && (
        <ModalPortal>
          <div
            className="fixed inset-x-0 top-16 bottom-0 md:left-[var(--app-sidebar-w)] z-50 flex items-center justify-center overflow-hidden bg-black/60 p-4 modal-backdrop-in transition-[left] duration-200 ease-out"
            onClick={(e) => { if (e.target === e.currentTarget) setDetailModalItem(null); }}
          >
            <section className="flex h-full w-full flex-col overflow-hidden rounded-card border border-blue-200 bg-white shadow-2xl modal-panel-in">
              {/* Modal Header */}
              <header className="flex items-start justify-between gap-4 border-b border-blue-100 bg-blue-50 px-5 py-4">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="min-w-0">
                    <h2 className="text-sm sm:text-base font-bold text-[#2f4ea6] truncate">
                      {locale === "vi" ? "Chi tiết chuẩn hóa dữ liệu" : "Data Normalization Details"}
                    </h2>
                    <p className="mt-0.5 text-xs text-[#3A5FC3] truncate" title={detailModalItem.file_name}>
                      {detailModalItem.file_name}
                    </p>
                  </div>
                </div>
              </header>

              {/* Modal Body */}
              <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 space-y-4 text-sm text-slate-700">
                {/* CARD 1: THÔNG TIN NGUỒN */}
                  <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                      <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                        {t.normalization.detail.rawIngestionTitle}
                      </h3>
                      <span className={ingestionSuccessBadgeClassName}>
                        {locale === "vi" ? "Đã tiếp nhận" : "Ingestion complete"}
                      </span>
                    </div>

                    {/* Stats */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center mb-3">
                      <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                        <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Tổng bản ghi" : "Total records"}</span>
                        <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detailModalItem.total_records)}</p>
                      </div>
                      <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                        <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Đã xử lý" : "Processed"}</span>
                        <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detailModalItem.processed_records ?? detailModalItem.imported_records)}</p>
                      </div>
                      <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                        <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Hợp lệ" : "Valid"}</span>
                        <p className="mt-0.5 text-base font-black text-emerald-700">{numberFormatter.format(detailModalItem.imported_records)}</p>
                      </div>
                      <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                        <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Lỗi" : "Failed"}</span>
                        <p className="mt-0.5 text-base font-black text-rose-700">{numberFormatter.format(detailModalItem.failed_records)}</p>
                      </div>
                    </div>

                    {/* Info */}
                    <dl className="space-y-3 border-t border-slate-100 pt-3 text-sm">
                      <div className="min-w-0">
                        <dt className="text-slate-400">{locale === "vi" ? "Tên tệp" : "File name"}</dt>
                        <dd className="font-semibold text-slate-800 break-all" title={detailModalItem.file_name}>{detailModalItem.file_name}</dd>
                      </div>
                      <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-3">
                        <div className="min-w-0">
                          <dt className="text-slate-400">{locale === "vi" ? "Người thực hiện" : "Performed by"}</dt>
                          <dd className="font-semibold text-slate-700">{formatPerformedBy(detailModalItem.performed_by)}</dd>
                        </div>
                        <div className="min-w-0">
                          <dt className="text-slate-400">{locale === "vi" ? "Bắt đầu lúc" : "Started at"}</dt>
                          <dd className="font-medium text-slate-700">{formatDate(detailModalItem.created_at)}</dd>
                        </div>
                        <div className="min-w-0">
                          <dt className="text-slate-400">{locale === "vi" ? "Thời lượng" : "Duration"}</dt>
                          <dd className="font-medium text-slate-700">{formatDuration(detailModalItem.duration_seconds)}</dd>
                        </div>
                      </div>
                    </dl>
                  </section>

                  {/* CARD 2: KẾT QUẢ XỬ LÝ */}
                  <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                      <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                        {t.normalization.detail.metricsTitle}
                      </h3>
                      {detailModalItem.normalization && detailModalItem.normalization.status === "COMPLETED" && hasRowErrors(detailModalItem) ? (
                        <span className={`${badgeClassName} border-amber-200 bg-amber-50 text-amber-700`}>
                          {t.normalization.status.completedWithErrors}
                        </span>
                      ) : detailModalItem.normalization && detailModalItem.normalization.status === "COMPLETED" ? (
                        <span className={completedStatusBadgeClassName}>
                          {t.normalization.status.completed}
                        </span>
                      ) : (
                        <span className={badgeClassName}>
                          {t.normalization.summary.pending}
                        </span>
                      )}
                    </div>

                    {detailModalItem.normalization ? (
                      <>
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-center">
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Đã xử lý" : "Processed"}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detailModalItem.normalization.canonical_processed ?? (detailModalItem.normalization.canonical_new + detailModalItem.normalization.canonical_existing + detailModalItem.normalization.canonical_metadata_changed))}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{t.normalization.table.newPublications}</span>
                            <p className="mt-0.5 text-base font-black text-emerald-700">{numberFormatter.format(detailModalItem.normalization.canonical_new)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{t.normalization.table.existing}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detailModalItem.normalization.canonical_existing)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{t.normalization.table.metadataChanged}</span>
                            <p className="mt-0.5 text-base font-black text-amber-700">{numberFormatter.format(detailModalItem.normalization.canonical_metadata_changed)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Trùng nội tệp" : "Intra-dup"}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detailModalItem.normalization.canonical_intra_duplicate)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{t.normalization.table.errors}</span>
                            <p className="mt-0.5 text-base font-black text-rose-700">{numberFormatter.format(detailModalItem.normalization.canonical_failed)}</p>
                          </div>
                        </div>

                        <div className="mt-auto rounded-[5px] border border-slate-200/60 bg-white/75 p-2.5 text-[11px] text-slate-500">
                          {locale === "vi"
                            ? "Dữ liệu Scopus đã được chuẩn hóa và ánh xạ vào kho công bố khoa học hợp nhất."
                            : "Scopus data has been normalized and mapped to the canonical publication store."}
                        </div>
                      </>
                    ) : (
                      <div className="flex flex-1 flex-col items-center justify-center rounded-[5px] border border-dashed border-slate-200 bg-white/60 p-5 text-center">
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
                  </section>

                {/* ROW 2: Chi tiết / Lỗi */}
                {detailModalItem.row_errors && detailModalItem.row_errors.length > 0 && (
                  <div className="rounded-[5px] border border-amber-200 bg-amber-50/60 p-3 text-xs">
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
                <div className="rounded-[5px] border border-slate-200/80 bg-slate-50/50 p-3">
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
                        <span className="font-bold text-slate-700" title={detailModalItem.id}>{shortId(detailModalItem.id)}</span>
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
              <footer className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-slate-100 bg-white px-5 py-3">
                {/* Trái: badges thông tin */}
                <div className="flex shrink-0 items-center gap-2">
                  <span className={`${basicBadgeClassName} font-mono`} title={detailModalItem.id}>
                    {shortId(detailModalItem.id)}
                  </span>
                  <span className={basicBadgeClassName}>Scopus</span>
                  <span className={
                    detailModalItem.normalization?.status === "COMPLETED" && !hasRowErrors(detailModalItem)
                      ? completedStatusBadgeClassName
                      : detailModalItem.normalization?.status === "COMPLETED"
                        ? `${badgeClassName} border-amber-200 text-amber-700 hover:bg-amber-50`
                        : isPending(detailModalItem)
                          ? badgeClassName
                          : badgeClassName
                  }>
                    {detailModalItem.normalization?.status === "COMPLETED" && !hasRowErrors(detailModalItem)
                      ? (locale === "vi" ? "Hoàn thành" : "Completed")
                      : detailModalItem.normalization?.status === "COMPLETED"
                        ? (locale === "vi" ? "Có lỗi" : "With errors")
                        : isPending(detailModalItem)
                          ? (locale === "vi" ? "Chờ xử lý" : "Pending")
                          : (locale === "vi" ? "Đang xử lý" : "Processing")}
                  </span>
                </div>
                {/* Phải: nút hành động */}
                <div className="flex items-center gap-2">
                {isPending(detailModalItem) ? (
                  <button
                    type="button"
                    disabled={Boolean(normalizingId) || isSuperseded(detailModalItem)}
                    title={
                      isSuperseded(detailModalItem)
                        ? (locale === "vi"
                            ? "Đợt này đã được thay thế bởi một đợt nhập trùng mới hơn đã xác nhận."
                            : "This import was superseded by a newer, confirmed duplicate.")
                        : undefined
                    }
                    onClick={() => void handleNormalize(detailModalItem)}
                    className={buttonClass("primary")}
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
                    className={buttonClass("secondary")}
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
                  className={buttonClass("secondary")}
                >
                  {locale === "vi" ? "Đóng" : "Close"}
                </button>
                </div>
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
