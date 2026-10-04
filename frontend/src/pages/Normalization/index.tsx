import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ScopusImport,
  getImportHistory,
  normalizeImport,
} from "../../api/imports";
import { ApiError } from "../../api/client";
import { useI18n } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";

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
  const [normalizingId, setNormalizingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(requestedImportId);
  const [reNormalizeTarget, setReNormalizeTarget] = useState<ScopusImport | null>(null);

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

  useEffect(() => {
    if (requestedImportId) {
      setExpandedId(requestedImportId);
    }
  }, [requestedImportId]);

  // Only Scopus imports are eligible for Publication Normalization
  const scopusImports = useMemo(() => {
    return history.filter((item) => item.type !== "LECTURERS");
  }, [history]);

  const filteredImports = useMemo(() => {
    if (!search.trim()) return scopusImports;
    const q = search.toLowerCase().trim();
    return scopusImports.filter(
      (item) =>
        item.file_name.toLowerCase().includes(q) ||
        item.id.toLowerCase().includes(q) ||
        (item.performed_by && item.performed_by.toLowerCase().includes(q)),
    );
  }, [scopusImports, search]);

  const handleNormalize = async (item: ScopusImport) => {
    if (normalizingId) return;
    setNormalizingId(item.id);
    try {
      const normalized = await normalizeImport(item.id);
      setHistory((current) => current.map((i) => (i.id === normalized.id ? normalized : i)));
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
      setExpandedId(item.id);
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

  const renderStatusBadge = (item: ScopusImport) => {
    const n = item.normalization;
    if (!n) {
      return (
        <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
          {t.normalization.status.notNormalized}
        </span>
      );
    }
    if (n.status === "NORMALIZING") {
      return (
        <span className="inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-[#3A5FC3]">
          <span className="h-2 w-2 animate-spin rounded-full border-2 border-[#3A5FC3] border-t-transparent" />
          {t.normalization.status.normalizing} ({n.progress_percent}%)
        </span>
      );
    }
    if (n.status === "COMPLETED") {
      return (
        <span className="inline-flex items-center rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
          {t.normalization.status.completed}
        </span>
      );
    }
    if (n.status === "CANCELLED") {
      return (
        <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-semibold text-slate-500">
          {t.normalization.status.cancelled}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center rounded-md border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700">
        {t.normalization.status.failed}
      </span>
    );
  };

  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">
            {t.normalization.title}
          </h1>
          <p className="text-xs text-slate-500 sm:text-sm">
            {t.normalization.subtitle}
          </p>
        </div>

        <button
          type="button"
          onClick={() => void fetchImports()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 self-start sm:self-auto rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-xs hover:bg-slate-50 hover:text-[#3A5FC3] hover:border-[#3A5FC3] transition-colors cursor-pointer disabled:opacity-50"
        >
          <svg className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>{t.common.refresh}</span>
        </button>
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
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
            {t.normalization.comingSoon}
          </span>
        </button>
      </div>

      {/* Tab Content: Authors Placeholder (M2.6B) */}
      {activeTab === "authors" && (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-xs">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 mb-4 border border-amber-200">
            <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          </div>
          <h2 className="text-base font-bold text-slate-800 sm:text-lg">
            {t.normalization.authorsPlaceholder}
          </h2>
          <p className="mt-2 max-w-md mx-auto text-xs text-slate-500 sm:text-sm">
            {t.normalization.authorsPlaceholderNote}
          </p>
          <div className="mt-5 inline-flex items-center gap-2 rounded-lg bg-slate-50 px-4 py-2 border border-slate-200 text-xs font-medium text-slate-600">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            <span>M2.6B Author Normalization Workspace</span>
          </div>
        </div>
      )}

      {/* Tab Content: Publications Normalization (M2.6A Functional) */}
      {activeTab === "publications" && (
        <div className="space-y-4">
          {/* Search bar */}
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
            <div className="text-xs text-slate-500 font-medium">
              {filteredImports.length} {locale === "vi" ? "đợt nhập Scopus" : "Scopus imports"}
            </div>
          </div>

          {/* Table */}
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="border-b border-slate-200 bg-slate-50/80 text-[11px] font-bold uppercase tracking-wider text-slate-600">
                  <tr>
                    <th className="px-4 py-3">{t.normalization.table.fileName}</th>
                    <th className="px-4 py-3 text-center">{t.normalization.table.importedAt}</th>
                    <th className="px-4 py-3 text-center">{t.normalization.table.sourceRecords}</th>
                    <th className="px-4 py-3 text-center">{t.normalization.table.status}</th>
                    <th className="px-4 py-3 text-center">{t.normalization.table.newPublications}</th>
                    <th className="px-4 py-3 text-center">{t.normalization.table.existing}</th>
                    <th className="px-4 py-3 text-center">{t.normalization.table.metadataChanged}</th>
                    <th className="px-4 py-3 text-center">{t.normalization.table.errors}</th>
                    <th className="px-4 py-3 text-center">{t.normalization.table.actions}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    <tr>
                      <td colSpan={9} className="py-12 text-center text-slate-400">
                        <div className="flex flex-col items-center justify-center gap-2">
                          <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                          <span>{t.common.loading}</span>
                        </div>
                      </td>
                    </tr>
                  ) : filteredImports.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="py-12 text-center text-slate-400">
                        {t.common.noData}
                      </td>
                    </tr>
                  ) : (
                    filteredImports.map((item) => {
                      const n = item.normalization;
                      const isExpanded = expandedId === item.id;
                      const isBusy = normalizingId === item.id;
                      return (
                        <React.Fragment key={item.id}>
                          <tr className={`transition-colors hover:bg-slate-50/70 ${isExpanded ? "bg-blue-50/20" : ""}`}>
                            <td className="px-4 py-3.5">
                              <div className="flex items-center gap-2.5">
                                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-blue-100/80 bg-blue-50 text-[#3A5FC3] shrink-0">
                                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                  </svg>
                                </div>
                                <div className="min-w-0 max-w-xs">
                                  <span className="block font-bold text-slate-800 truncate" title={item.file_name}>
                                    {item.file_name}
                                  </span>
                                  <span className="block text-[10px] font-mono text-slate-400 truncate">
                                    ID: {item.id}
                                  </span>
                                </div>
                              </div>
                            </td>

                            <td className="px-4 py-3.5 text-center text-slate-600 whitespace-nowrap">
                              {formatDate(item.created_at)}
                            </td>

                            <td className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">
                              {numberFormatter.format(item.imported_records)} / {numberFormatter.format(item.total_records)}
                            </td>

                            <td className="px-4 py-3.5 text-center whitespace-nowrap">
                              {renderStatusBadge(item)}
                            </td>

                            <td className="px-4 py-3.5 text-center font-bold text-emerald-600 whitespace-nowrap">
                              {n ? numberFormatter.format(n.canonical_new) : "—"}
                            </td>

                            <td className="px-4 py-3.5 text-center font-semibold text-slate-600 whitespace-nowrap">
                              {n ? numberFormatter.format(n.canonical_existing) : "—"}
                            </td>

                            <td className="px-4 py-3.5 text-center font-semibold text-amber-600 whitespace-nowrap">
                              {n ? numberFormatter.format(n.canonical_metadata_changed) : "—"}
                            </td>

                            <td className="px-4 py-3.5 text-center font-semibold text-rose-600 whitespace-nowrap">
                              {n ? numberFormatter.format(n.canonical_failed) : "—"}
                            </td>

                            <td className="px-4 py-3.5 text-center whitespace-nowrap">
                              <div className="flex items-center justify-center gap-1.5">
                                {/* Normalize / Re-normalize Button */}
                                {!n || n.status !== "COMPLETED" ? (
                                  <button
                                    type="button"
                                    disabled={isBusy}
                                    onClick={() => void handleNormalize(item)}
                                    className="inline-flex items-center gap-1 rounded-md bg-[#3A5FC3] px-2.5 py-1 text-[11px] font-bold text-white shadow-2xs hover:bg-[#2f4ea6] transition-colors cursor-pointer disabled:opacity-50"
                                  >
                                    {isBusy ? (
                                      <>
                                        <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                                        <span>{t.normalization.actions.normalizing}</span>
                                      </>
                                    ) : (
                                      <>
                                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                        </svg>
                                        <span>{t.normalization.actions.normalize}</span>
                                      </>
                                    )}
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    disabled={isBusy}
                                    onClick={() => setReNormalizeTarget(item)}
                                    className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:border-[#3A5FC3] hover:text-[#3A5FC3] transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                                  >
                                    <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                    </svg>
                                    <span>{t.normalization.actions.reNormalize}</span>
                                  </button>
                                )}

                                {/* Expand Details Button */}
                                <button
                                  type="button"
                                  onClick={() => setExpandedId(isExpanded ? null : item.id)}
                                  className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-semibold transition-colors cursor-pointer shadow-2xs ${
                                    isExpanded
                                      ? "border-[#3A5FC3] bg-blue-50 text-[#3A5FC3]"
                                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                                  }`}
                                >
                                  <span>{isExpanded ? t.normalization.actions.hideDetail : t.normalization.actions.viewDetail}</span>
                                  <svg
                                    className={`h-3 w-3 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                                  </svg>
                                </button>
                              </div>
                            </td>
                          </tr>

                          {/* Expandable Detail Section */}
                          {isExpanded && (
                            <tr className="bg-slate-50/50">
                              <td colSpan={9} className="p-4 sm:p-5">
                                <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 sm:p-5 shadow-xs">
                                  {/* Normalization Metrics */}
                                  <div>
                                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-3 flex items-center gap-2">
                                      <div className="flex h-5 w-5 items-center justify-center rounded-md bg-[#3A5FC3]/10 text-[#3A5FC3]">
                                        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                        </svg>
                                      </div>
                                      <span>{t.normalization.detail.metricsTitle}</span>
                                    </h3>

                                    {n ? (
                                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                                        <div className="rounded-lg border border-emerald-200 bg-emerald-50/40 p-3 text-center">
                                          <span className="text-[11px] font-medium text-emerald-700">{t.normalization.table.newPublications}</span>
                                          <p className="mt-0.5 text-xl font-black text-emerald-700">{numberFormatter.format(n.canonical_new)}</p>
                                        </div>
                                        <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-3 text-center">
                                          <span className="text-[11px] font-medium text-slate-600">{t.normalization.table.existing}</span>
                                          <p className="mt-0.5 text-xl font-black text-slate-700">{numberFormatter.format(n.canonical_existing)}</p>
                                        </div>
                                        <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-3 text-center">
                                          <span className="text-[11px] font-medium text-amber-700">{t.normalization.table.metadataChanged}</span>
                                          <p className="mt-0.5 text-xl font-black text-amber-700">{numberFormatter.format(n.canonical_metadata_changed)}</p>
                                        </div>
                                        <div className="rounded-lg border border-rose-200 bg-rose-50/40 p-3 text-center">
                                          <span className="text-[11px] font-medium text-rose-700">{t.normalization.table.errors}</span>
                                          <p className="mt-0.5 text-xl font-black text-rose-700">{numberFormatter.format(n.canonical_failed)}</p>
                                        </div>
                                        <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-3 text-center col-span-2 sm:col-span-1">
                                          <span className="text-[11px] font-medium text-slate-600">{locale === "vi" ? "Trùng EID nội tệp" : "Intra-file Duplicates"}</span>
                                          <p className="mt-0.5 text-xl font-black text-slate-700">{numberFormatter.format(n.canonical_intra_duplicate)}</p>
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50/60 p-4 text-center text-slate-500 text-xs font-medium">
                                        {t.normalization.status.notNormalized}
                                      </div>
                                    )}
                                  </div>

                                  {/* 2-Column: Raw Ingestion & Usage State */}
                                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 pt-2 border-t border-slate-100">
                                    {/* Raw Ingestion Info */}
                                    <div className="rounded-lg border border-slate-100 bg-slate-50/60 p-3.5 space-y-2">
                                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
                                        {t.normalization.detail.rawIngestionTitle}
                                      </h4>
                                      <div className="grid grid-cols-2 gap-2 text-xs">
                                        <div>
                                          <span className="text-slate-500">{locale === "vi" ? "Tổng bản ghi:" : "Total records:"}</span>
                                          <p className="font-bold text-slate-800">{numberFormatter.format(item.total_records)}</p>
                                        </div>
                                        <div>
                                          <span className="text-slate-500">{locale === "vi" ? "Đã tiếp nhận:" : "Imported:"}</span>
                                          <p className="font-bold text-emerald-600">{numberFormatter.format(item.imported_records)}</p>
                                        </div>
                                        <div>
                                          <span className="text-slate-500">{locale === "vi" ? "Người thực hiện:" : "Performed by:"}</span>
                                          <p className="font-medium text-slate-700">{item.performed_by || "—"}</p>
                                        </div>
                                        <div>
                                          <span className="text-slate-500">{locale === "vi" ? "Thời lượng:" : "Duration:"}</span>
                                          <p className="font-medium text-slate-700">{formatDuration(item.duration_seconds)}</p>
                                        </div>
                                      </div>
                                    </div>

                                    {/* Provenance & Usage */}
                                    <div className="rounded-lg border border-slate-100 bg-slate-50/60 p-3.5 space-y-2">
                                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
                                        {t.normalization.detail.provenanceTitle}
                                      </h4>
                                      <div className="flex items-center gap-2">
                                        <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-bold ${
                                          item.in_use
                                            ? "border border-violet-200 bg-violet-50 text-violet-700"
                                            : "border border-slate-200 bg-slate-100 text-slate-600"
                                        }`}>
                                          {item.in_use ? t.normalization.detail.provenanceInUse : t.normalization.detail.provenanceNotInUse}
                                        </span>
                                      </div>
                                      {item.usage && (
                                        <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                                          <div>
                                            <span className="text-slate-500">{t.normalization.detail.publicationLinks}:</span>
                                            <p className="font-bold text-slate-800">{numberFormatter.format(item.usage.publication_source_links)}</p>
                                          </div>
                                          <div>
                                            <span className="text-slate-500">{t.normalization.detail.authorVariantLinks}:</span>
                                            <p className="font-bold text-slate-800">{numberFormatter.format(item.usage.author_variant_links)}</p>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  </div>

                                  {/* Error logs if any */}
                                  {item.row_errors && item.row_errors.length > 0 && (
                                    <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 text-xs">
                                      <h4 className="mb-1.5 font-bold text-amber-800">{t.imports.rowErrors}</h4>
                                      <ul className="max-h-28 space-y-1 overflow-y-auto text-amber-900">
                                        {item.row_errors.map((rowError, idx) => (
                                          <li key={idx}>
                                            {locale === "vi" ? "Dòng" : "Row"} {rowError.row_number ?? "—"}: {rowError.message ?? rowError.code ?? "Lỗi"}
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal for Re-normalization */}
      {reNormalizeTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center gap-3 text-amber-600 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 border border-amber-200 shrink-0">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  {t.normalization.actions.confirmReNormalize}
                </h3>
                <p className="text-xs text-slate-500 truncate max-w-[260px]">
                  {reNormalizeTarget.file_name}
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-600 mb-5">
              {t.normalization.actions.reNormalizePrompt}
            </p>

            <div className="flex items-center justify-end gap-2 border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={() => setReNormalizeTarget(null)}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                {t.common.cancel}
              </button>
              <button
                type="button"
                disabled={Boolean(normalizingId)}
                onClick={() => void handleNormalize(reNormalizeTarget)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#3A5FC3] px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors cursor-pointer disabled:opacity-50"
              >
                {normalizingId ? (
                  <>
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    <span>{t.normalization.actions.normalizing}</span>
                  </>
                ) : (
                  <span>{t.normalization.actions.reNormalize}</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
