import { adminLabel, isCorruptedName } from "../../utils/displayName";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
import AffiliationsTab from "./AffiliationsTab";
import AuthorsTab from "./AuthorsTab";
import MatchingTab from "./MatchingTab";

const numberFormatter = new Intl.NumberFormat("vi-VN");

const badgeClassName =
  "inline-flex h-6 w-32 items-center justify-center rounded-full border px-2.5 text-xs font-bold whitespace-nowrap";

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
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedImportId = searchParams.get("import");

  type TabKey = "publications" | "authors" | "affiliations" | "matching";
  const tabFromUrl = searchParams.get("tab") as TabKey | null;
  const validTabs: TabKey[] = ["publications", "authors", "affiliations", "matching"];
  const [activeTab, setActiveTab] = useState<TabKey>(
    tabFromUrl && validTabs.includes(tabFromUrl) ? tabFromUrl : "publications"
  );

  const switchTab = (tab: TabKey) => {
    setActiveTab(tab);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("tab", tab);
      return next;
    }, { replace: true });
  };
  const [history, setHistory] = useState<ScopusImport[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [historyStatusFilter, setHistoryStatusFilter] = useState<"all" | "pending" | "processing" | "completed" | "failed">("all");

  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(10);
  const [normalizingId, setNormalizingId] = useState<string | null>(null);
  const [detailModalItem, setDetailModalItem] = useState<ScopusImport | null>(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [reNormalizeTarget, setReNormalizeTarget] = useState<ScopusImport | null>(null);

  const highlightedRef = useRef<HTMLTableRowElement | null>(null);

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

  // Only Scopus imports are eligible for Publication Normalization.
  // Imports cancelled before normalization ever started never belong to this page.
  const scopusImports = useMemo(() => {
    return history.filter(
      (item) =>
        item.type !== "LECTURERS" && !(item.status === "CANCELLED" && !item.normalization),
    );
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
    if (historyStatusFilter === "pending") {
      list = list.filter(isPending);
    } else if (historyStatusFilter === "processing") {
      list = list.filter(isProcessing);
    } else if (historyStatusFilter === "completed") {
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
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-800 sm:text-2xl">
            {t.normalization.title}
          </h1>
          <p className="text-xs text-slate-500 sm:text-sm">
            {t.normalization.subtitle}
          </p>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto pb-1 sm:pb-0 shrink-0">
          <button
            type="button"
            onClick={() => {
              switchTab("publications");
              setHistoryPage(1);
            }}
            data-testid="tab-publications"
            className={`h-10 w-36 inline-flex items-center justify-center gap-1.5 rounded-[5px] px-2.5 py-2 text-xs font-bold transition-colors cursor-pointer shrink-0 ${
              activeTab === "publications"
                ? "bg-[#3A5FC3] text-white shadow-xs hover:bg-[#2f4ea6]"
                : "bg-white text-slate-700 border border-slate-200 shadow-xs hover:bg-slate-50 hover:text-[#3A5FC3] hover:border-[#3A5FC3]"
            }`}
          >
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <span className="truncate">{t.normalization.tabs.publications}</span>
          </button>

          <button
            type="button"
            onClick={() => switchTab("authors")}
            data-testid="tab-authors"
            className={`h-10 w-36 inline-flex items-center justify-center gap-1.5 rounded-[5px] px-2.5 py-2 text-xs font-bold transition-colors cursor-pointer shrink-0 ${
              activeTab === "authors"
                ? "bg-[#3A5FC3] text-white shadow-xs hover:bg-[#2f4ea6]"
                : "bg-white text-slate-700 border border-slate-200 shadow-xs hover:bg-slate-50 hover:text-[#3A5FC3] hover:border-[#3A5FC3]"
            }`}
          >
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <span className="truncate">{t.normalization.tabs.authors}</span>
          </button>

          <button
            type="button"
            onClick={() => switchTab("affiliations")}
            data-testid="tab-affiliations"
            className={`h-10 w-36 inline-flex items-center justify-center gap-1.5 rounded-[5px] px-2.5 py-2 text-xs font-bold transition-colors cursor-pointer shrink-0 ${
              activeTab === "affiliations"
                ? "bg-[#3A5FC3] text-white shadow-xs hover:bg-[#2f4ea6]"
                : "bg-white text-slate-700 border border-slate-200 shadow-xs hover:bg-slate-50 hover:text-[#3A5FC3] hover:border-[#3A5FC3]"
            }`}
          >
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            <span className="truncate">{locale === "vi" ? "Đơn vị tác giả" : "Author affiliations"}</span>
          </button>

          <button
            type="button"
            onClick={() => switchTab("matching")}
            data-testid="tab-matching"
            className={`h-10 w-36 inline-flex items-center justify-center gap-1.5 rounded-[5px] px-2.5 py-2 text-xs font-bold transition-colors cursor-pointer shrink-0 ${
              activeTab === "matching"
                ? "bg-[#3A5FC3] text-white shadow-xs hover:bg-[#2f4ea6]"
                : "bg-white text-slate-700 border border-slate-200 shadow-xs hover:bg-slate-50 hover:text-[#3A5FC3] hover:border-[#3A5FC3]"
            }`}
          >
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7h12m0 0l-4-4m4 4l-4 4M16 17H4m0 0l4 4m-4-4l4-4" />
            </svg>
            <span className="truncate">{locale === "vi" ? "Đối sánh" : "Matching"}</span>
          </button>
        </div>
      </div>

      {activeTab === "affiliations" && (
        <div className="tab-fade-in space-y-4">
          <AffiliationsTab locale={locale} />
          {/* Workflow next-step hint */}
          <div className="flex items-center gap-3 rounded-[5px] border border-[#3A5FC3]/20 bg-[#EBEFF9] px-4 py-3 text-sm">
            <svg className="h-4 w-4 shrink-0 text-[#3A5FC3]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7l5 5-5 5M6 12h12" />
            </svg>
            <span className="text-[#3A5FC3] font-medium">
              {locale === "vi"
                ? "Bạn có thể tra cứu công bố. Nếu có JSON Craw, tiếp tục đối sánh — "
                : "You can browse publications. If you have Craw JSON, continue matching — "}
            </span>
            <button
              type="button"
              onClick={() => switchTab("matching")}
              className="underline underline-offset-2 text-[#2F4EA6] font-semibold hover:text-[#3A5FC3] transition-colors cursor-pointer"
            >
              {locale === "vi" ? "Chuyển sang tab Đối sánh →" : "Go to Matching tab →"}
            </button>
          </div>
        </div>
      )}

      {activeTab === "matching" && (
        <div className="tab-fade-in space-y-4">
          <MatchingTab locale={locale} />
          {/* Workflow next-step hint */}
          <div className="flex items-center gap-3 rounded-[5px] border border-emerald-200 bg-[#ECFDF5] px-4 py-3 text-sm">
            <svg className="h-4 w-4 shrink-0 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-emerald-700 font-medium">
              {locale === "vi"
                ? "Ứng viên nhận dạng cần REVIEWER kiểm tra — "
                : "Identity candidates need REVIEWER verification — "}
            </span>
            <Link
              to="/reviews"
              className="underline underline-offset-2 text-emerald-700 font-semibold hover:text-emerald-800 transition-colors"
            >
              {locale === "vi" ? "Tới trang Kiểm duyệt →" : "Go to Reviews page →"}
            </Link>
          </div>
        </div>
      )}

      {/* Tab Content: Authors Tab (M2.6B) */}
      {activeTab === "authors" && (
        <div className="tab-fade-in space-y-4">
          <AuthorsTab
            scopusImports={scopusImports}
            locale={locale}
            onRefresh={fetchImports}
          />
          {/* Workflow next-step hint */}
          <div className="flex items-center gap-3 rounded-[5px] border border-[#3A5FC3]/20 bg-[#EBEFF9] px-4 py-3 text-sm">
            <svg className="h-4 w-4 shrink-0 text-[#3A5FC3]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7l5 5-5 5M6 12h12" />
            </svg>
            <span className="text-[#3A5FC3] font-medium">
              {locale === "vi"
                ? "Bước tiếp theo: Đối chiếu đơn vị tác giả — "
                : "Next step: Normalize affiliations — "}
            </span>
            <button
              type="button"
              onClick={() => switchTab("affiliations")}
              className="underline underline-offset-2 text-[#2F4EA6] font-semibold hover:text-[#3A5FC3] transition-colors cursor-pointer"
            >
              {locale === "vi" ? "Chuyển sang tab Đơn vị →" : "Go to Affiliations tab →"}
            </button>
          </div>
        </div>
      )}

      {/* Tab Content: Publications Normalization (M2.6A Functional) */}
      {activeTab === "publications" && (
        <div className="tab-fade-in space-y-5">
          {/* Summary KPI Cards — Matching /imports & /lecturers visual rhythm */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
            <button
              type="button"
              onClick={() => { setHistoryStatusFilter("all"); setHistoryPage(1); }}
              className={`rounded-[5px] border p-4 shadow-xs text-left transition-all duration-150 cursor-pointer ${historyStatusFilter === "all" ? "border-slate-400 bg-slate-100 ring-2 ring-slate-300" : "border-slate-200/80 bg-white hover:border-slate-300 hover:bg-slate-50"}`}
            >
              <span className="text-xs font-medium text-slate-500">
                {locale === "vi" ? "Tổng đợt nhập" : "Total imports"}
              </span>
              <p className="mt-1 text-2xl font-black text-slate-800">
                {scopusImports.length}
              </p>
            </button>

            <button
              type="button"
              onClick={() => { setHistoryStatusFilter(historyStatusFilter === "pending" ? "all" : "pending"); setHistoryPage(1); }}
              className={`rounded-[5px] border p-4 shadow-xs text-left transition-all duration-150 cursor-pointer ${historyStatusFilter === "pending" ? "border-slate-400 bg-slate-100 ring-2 ring-slate-300" : "border-slate-200/80 bg-white hover:border-slate-300 hover:bg-slate-50"}`}
            >
              <span className="text-xs font-medium text-slate-500">
                {t.normalization.summary.pending}
              </span>
              <p className="mt-1 text-2xl font-black text-slate-800">
                {countPending}
              </p>
            </button>

            <button
              type="button"
              onClick={() => { setHistoryStatusFilter(historyStatusFilter === "processing" ? "all" : "processing"); setHistoryPage(1); }}
              className={`rounded-[5px] border p-4 shadow-xs text-left transition-all duration-150 cursor-pointer ${historyStatusFilter === "processing" ? "border-blue-300 bg-blue-50 ring-2 ring-blue-200" : "border-slate-200/80 bg-white hover:border-blue-200 hover:bg-blue-50/40"}`}
            >
              <span className="text-xs font-medium text-[#3A5FC3]">
                {t.normalization.summary.processing}
              </span>
              <p className="mt-1 text-2xl font-black text-[#3A5FC3]">
                {countProcessing}
              </p>
            </button>

            <button
              type="button"
              onClick={() => { setHistoryStatusFilter(historyStatusFilter === "completed" ? "all" : "completed"); setHistoryPage(1); }}
              className={`rounded-[5px] border p-4 shadow-xs text-left transition-all duration-150 cursor-pointer ${historyStatusFilter === "completed" ? "border-emerald-300 bg-emerald-50 ring-2 ring-emerald-200" : "border-slate-200/80 bg-white hover:border-emerald-200 hover:bg-emerald-50/40"}`}
            >
              <span className="text-xs font-medium text-emerald-600">
                {t.normalization.summary.completed}
              </span>
              <p className="mt-1 text-2xl font-black text-emerald-600">
                {countCompleted}
              </p>
            </button>

            <button
              type="button"
              onClick={() => { setHistoryStatusFilter(historyStatusFilter === "failed" ? "all" : "failed"); setHistoryPage(1); }}
              className={`rounded-[5px] border p-4 shadow-xs text-left transition-all duration-150 cursor-pointer ${historyStatusFilter === "failed" ? "border-rose-300 bg-rose-50 ring-2 ring-rose-200" : "border-slate-200/80 bg-white hover:border-rose-200 hover:bg-rose-50/40"}`}
            >
              <span className="text-xs font-medium text-rose-600">
                {t.normalization.summary.failed}
              </span>
              <p className="mt-1 text-2xl font-black text-rose-600">
                {countFailed}
              </p>
            </button>
          </div>

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

            <div className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="border-b border-slate-200 bg-slate-50/80 text-[11px] font-bold uppercase tracking-wider text-slate-600">
                    <tr>
                      <th className="px-4 py-3">{t.normalization.table.fileName}</th>
                      <th className="px-4 py-3 text-center">{t.normalization.table.importedAt}</th>
                      <th className="px-4 py-3 text-center">{t.normalization.table.sourceRecords}</th>
                      <th className="px-4 py-3 text-center">{t.normalization.table.status}</th>
                      <th className="w-64 px-4 py-3 text-center">{t.normalization.table.actions}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loading ? (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                            <span className="text-xs font-medium">{t.common.loading}</span>
                          </div>
                        </td>
                      </tr>
                    ) : pendingImports.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center gap-1.5">
                            <div className="flex h-10 w-10 items-center justify-center rounded-[5px] bg-slate-100/80 border border-slate-200/80 text-slate-400 mb-1">
                              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                            </div>
                            <span className="text-sm font-bold text-slate-700">
                              {locale === "vi" ? "Không có đợt nhập nào chờ xử lý" : "No pending imports awaiting normalization"}
                            </span>
                            <span className="text-xs text-slate-400">
                              {locale === "vi" ? "Tất cả các đợt nhập Scopus đã được chuẩn hóa hoặc xử lý hoàn tất." : "All Scopus imports have been normalized or processed."}
                            </span>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      pendingImports.map((item) => {
                        const isHighlighted = requestedImportId === item.id;
                        const isBusy = normalizingId === item.id;
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
                            <td className="px-4 py-3.5">
                              <div className="flex items-center gap-2.5">
                                <div className="flex h-8 w-8 items-center justify-center rounded-[5px] border border-blue-100/80 bg-blue-50 text-[#3A5FC3] shrink-0 shadow-2xs">
                                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                  </svg>
                                </div>
                                <div className="min-w-0 max-w-xs sm:max-w-sm">
                                  <span className="block font-bold text-slate-800 truncate" title={item.file_name}>
                                    {item.file_name}
                                  </span>
                                  <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
                                    <span className="font-semibold text-slate-600">Scopus</span>
                                    <span>•</span>
                                    <span className="font-mono text-[10px] text-slate-400 truncate">ID: {item.id}</span>
                                  </div>
                                </div>
                              </div>
                            </td>

                            {/* Time */}
                            <td className="px-4 py-3.5 text-center text-slate-600 whitespace-nowrap">
                              {formatDate(item.created_at)}
                            </td>

                            {/* Records */}
                            <td className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">
                              {numberFormatter.format(item.processed_records || item.imported_records || item.total_records)} / {numberFormatter.format(item.total_records)}
                            </td>

                            {/* Status */}
                            <td className="px-4 py-3.5 text-center whitespace-nowrap">
                              <span className={`${badgeClassName} border-blue-200 bg-blue-50 text-[#3A5FC3]`}>
                                {locale === "vi" ? "Chờ xử lý" : "Pending"}
                              </span>
                            </td>

                            {/* Actions */}
                            <td className="px-4 py-3.5 text-center align-middle whitespace-nowrap">
                              <div className="flex items-center justify-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleOpenDetailModal(item)}
                                  className="inline-flex h-7 items-center justify-center gap-1 rounded-[5px] border border-slate-200 bg-white px-2.5 text-[11px] font-semibold text-slate-700 shadow-2xs transition-all duration-150 active:scale-[0.97] hover:border-[#3A5FC3] hover:text-[#3A5FC3] cursor-pointer whitespace-nowrap"
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
                                  className="inline-flex h-7 min-w-32 items-center justify-center gap-1.5 rounded-[5px] bg-[#3A5FC3] px-3 text-[11px] font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-all duration-150 active:scale-[0.97] cursor-pointer disabled:opacity-50 whitespace-nowrap"
                                >
                                  {isBusy ? (
                                    <>
                                      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                                      <span>{t.normalization.actions.normalizing}</span>
                                    </>
                                  ) : (
                                    <>
                                      <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                      </svg>
                                      <span>{t.normalization.actions.normalize}</span>
                                    </>
                                  )}
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
            </div>
          </section>

          {/* SECTION 2: LỊCH SỬ ĐÃ XỬ LÝ (Processed History) */}
          <section className="space-y-3 pt-2">
            <div>
              <h2 className="text-base font-bold text-slate-800 sm:text-lg">
                {t.normalization.historyTitle}
              </h2>
            </div>

            {/* Toolbar: Search input only (status filter via KPI cards) */}
            <div className="flex flex-col gap-3 rounded-[5px] border border-slate-200/80 bg-white p-3.5 shadow-xs sm:flex-row sm:items-center">
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
                  className="h-9 w-full rounded-[5px] border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 sm:text-sm"
                />
              </div>
            </div>

            {/* Simple History Table */}
            <div className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
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
                            <td className="px-4 py-3.5">
                              <div className="flex items-center gap-2.5">
                                <div className="flex h-8 w-8 items-center justify-center rounded-[5px] border border-blue-100/80 bg-blue-50 text-[#3A5FC3] shrink-0">
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
                              {n && n.status === "COMPLETED" && hasRowErrors(item) ? (
                                <span className={`${badgeClassName} border-amber-200 bg-amber-50 text-amber-700`}>
                                  {t.normalization.status.completedWithErrors}
                                </span>
                              ) : n && n.status === "COMPLETED" ? (
                                <span className={`${badgeClassName} border-emerald-200 bg-emerald-50 text-emerald-700`}>
                                  {t.normalization.status.completed}
                                </span>
                              ) : n && n.status === "NORMALIZING" ? (
                                <span className={`${badgeClassName} gap-1 border-blue-200 bg-blue-50 text-[#3A5FC3]`}>
                                  <span className="h-2 w-2 animate-spin rounded-full border-2 border-[#3A5FC3] border-t-transparent" />
                                  {t.normalization.status.normalizing} ({n.progress_percent}%)
                                </span>
                              ) : isFailed(item) ? (
                                <span className={`${badgeClassName} border-rose-200 bg-rose-50 text-rose-700`}>
                                  {t.normalization.status.failed}
                                </span>
                              ) : (
                                <span className={`${badgeClassName} border-slate-200 bg-slate-100 text-slate-600`}>
                                  {item.status === "CANCELLED" ? t.normalization.status.cancelled : t.normalization.status.notNormalized}
                                </span>
                              )}
                            </td>

                            {/* Actions: [Chi tiết] only */}
                            <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap">
                              <button
                                type="button"
                                onClick={() => handleOpenDetailModal(item)}
                                className="inline-flex h-7 w-20 items-center justify-center gap-1 rounded-[5px] border border-slate-200 bg-white px-2 text-[11px] font-semibold text-slate-700 shadow-2xs transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] cursor-pointer whitespace-nowrap"
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
                    className="inline-flex h-8 items-center rounded-[5px] border border-slate-200 bg-white px-2.5 font-semibold text-slate-700 transition-all duration-150 active:scale-[0.97] hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
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
                    className="inline-flex h-8 items-center rounded-[5px] border border-slate-200 bg-white px-2.5 font-semibold text-slate-700 transition-all duration-150 active:scale-[0.97] hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
                  >
                    {locale === "vi" ? "Trang sau" : "Next"}
                  </button>
                </nav>
              </div>
            </div>
          </section>

          {/* Workflow next-step hint */}
          <div className="flex items-center gap-3 rounded-[5px] border border-[#3A5FC3]/20 bg-[#EBEFF9] px-4 py-3 text-sm">
            <svg className="h-4 w-4 shrink-0 text-[#3A5FC3]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7l5 5-5 5M6 12h12" />
            </svg>
            <span className="text-[#3A5FC3] font-medium">
              {locale === "vi"
                ? "Bước tiếp theo: Bóc tách tác giả — "
                : "Next step: Extract authors — "}
            </span>
            <button
              type="button"
              onClick={() => switchTab("authors")}
              className="underline underline-offset-2 text-[#2F4EA6] font-semibold hover:text-[#3A5FC3] transition-colors cursor-pointer"
            >
              {locale === "vi" ? "Chuyển sang tab Tác giả →" : "Go to Authors tab →"}
            </button>
          </div>
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

            <section className="relative flex flex-col w-full max-w-4xl max-h-[90vh] rounded-[5px] bg-white shadow-2xl overflow-hidden z-10 animate-in zoom-in-95 duration-150">
              {/* Modal Header */}
              <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4 bg-slate-50/50">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex h-9 w-9 items-center justify-center rounded-[5px] bg-blue-50 text-[#3A5FC3] border border-blue-100 shrink-0">
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
                  className="rounded-[5px] p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
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
                  <div className="flex flex-col rounded-[5px] border border-blue-100 bg-blue-50/20 p-4 shadow-2xs">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-blue-100/70">
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-[5px] bg-[#3A5FC3]/10 text-[#3A5FC3]">
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
                      <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                        <span className="text-[10px] font-medium text-slate-500 uppercase">{locale === "vi" ? "Tổng bản ghi" : "Total records"}</span>
                        <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detailModalItem.total_records)}</p>
                      </div>
                      <div className="rounded-[5px] border border-emerald-200/80 bg-white p-2.5 shadow-2xs">
                        <span className="text-[10px] font-medium text-emerald-600 uppercase">{locale === "vi" ? "Hợp lệ" : "Valid"}</span>
                        <p className="mt-0.5 text-base font-black text-emerald-600">{numberFormatter.format(detailModalItem.imported_records)}</p>
                      </div>
                      <div className="rounded-[5px] border border-rose-200/80 bg-white p-2.5 shadow-2xs">
                        <span className="text-[10px] font-medium text-rose-600 uppercase">{locale === "vi" ? "Lỗi" : "Failed"}</span>
                        <p className="mt-0.5 text-base font-black text-rose-600">{numberFormatter.format(detailModalItem.failed_records)}</p>
                      </div>
                    </div>

                    {/* Info */}
                    <div className="mt-auto space-y-1.5 rounded-[5px] border border-blue-100/80 bg-white/75 p-3 text-xs text-slate-600">
                      <div className="flex justify-between gap-2">
                        <span className="text-slate-400 shrink-0">{locale === "vi" ? "Tên tệp:" : "File name:"}</span>
                        <span className="font-semibold text-slate-800 truncate text-right" title={detailModalItem.file_name}>{detailModalItem.file_name}</span>
                      </div>
                      <div className="flex justify-between gap-2">
                        <span className="text-slate-400 shrink-0">{locale === "vi" ? "Người thực hiện:" : "Performed by:"}</span>
                        <span className="font-semibold text-slate-700">{formatPerformedBy(detailModalItem.performed_by)}</span>
                      </div>
                      <div className="flex justify-between gap-2">
                        <span className="text-slate-400 shrink-0">{locale === "vi" ? "Thời gian tiếp nhận:" : "Imported at:"}</span>
                        <span className="font-medium text-slate-700">{formatDate(detailModalItem.created_at)}</span>
                      </div>
                    </div>
                  </div>

                  {/* CARD 2: KẾT QUẢ XỬ LÝ */}
                  <div className="flex flex-col rounded-[5px] border border-slate-200/80 bg-slate-50/40 p-4 shadow-2xs">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-200/70">
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-[5px] bg-indigo-100 text-indigo-700">
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
                      {detailModalItem.normalization && detailModalItem.normalization.status === "COMPLETED" && hasRowErrors(detailModalItem) ? (
                        <span className={`${badgeClassName} border-amber-200 bg-amber-50 text-amber-700`}>
                          {t.normalization.status.completedWithErrors}
                        </span>
                      ) : detailModalItem.normalization && detailModalItem.normalization.status === "COMPLETED" ? (
                        <span className={`${badgeClassName} border-emerald-200 bg-emerald-50 text-emerald-700`}>
                          {t.normalization.status.completed}
                        </span>
                      ) : (
                        <span className={`${badgeClassName} border-blue-200 bg-blue-50 text-[#3A5FC3]`}>
                          {t.normalization.summary.pending}
                        </span>
                      )}
                    </div>

                    {detailModalItem.normalization ? (
                      <>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center mb-3">
                          <div className="rounded-[5px] border border-emerald-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-emerald-700 uppercase">{t.normalization.table.newPublications}</span>
                            <p className="mt-0.5 text-base font-black text-emerald-700">{numberFormatter.format(detailModalItem.normalization.canonical_new)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-slate-600 uppercase">{t.normalization.table.existing}</span>
                            <p className="mt-0.5 text-base font-black text-slate-700">{numberFormatter.format(detailModalItem.normalization.canonical_existing)}</p>
                          </div>
                          <div className="rounded-[5px] border border-amber-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-amber-700 uppercase">{t.normalization.table.metadataChanged}</span>
                            <p className="mt-0.5 text-base font-black text-amber-700">{numberFormatter.format(detailModalItem.normalization.canonical_metadata_changed)}</p>
                          </div>
                          <div className="rounded-[5px] border border-rose-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-rose-700 uppercase">{t.normalization.table.errors}</span>
                            <p className="mt-0.5 text-base font-black text-rose-700">{numberFormatter.format(detailModalItem.normalization.canonical_failed)}</p>
                          </div>
                        </div>

                        {detailModalItem.normalization.canonical_intra_duplicate > 0 && (
                          <div className="mb-2 rounded-[5px] border border-slate-200 bg-white p-2 text-center">
                            <span className="text-[10px] font-medium text-slate-600">{locale === "vi" ? "Trùng EID nội tệp:" : "Intra-file Duplicates:"} </span>
                            <strong className="text-slate-800 font-bold">{numberFormatter.format(detailModalItem.normalization.canonical_intra_duplicate)}</strong>
                          </div>
                        )}

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
                  </div>
                </div>

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
                    className="inline-flex min-w-36 items-center justify-center gap-1.5 rounded-[5px] bg-[#3A5FC3] px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors cursor-pointer disabled:opacity-50"
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
                    className="inline-flex items-center gap-1.5 rounded-[5px] border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
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
                  className="rounded-[5px] border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer shadow-2xs"
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
