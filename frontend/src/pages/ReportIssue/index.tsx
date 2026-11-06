import { useCallback, useEffect, useState } from "react";
import Button, { buttonClass } from "../../components/ui/Button";
import FeedbackThread from "../../components/feedback/FeedbackThread";
import { useI18n } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import { useFeedbackUnread } from "../../contexts/FeedbackUnreadContext";
import {
  createFeedbackReport,
  listMyFeedbackReports,
  type FeedbackCategory,
  type FeedbackReport,
  type FeedbackStatus,
} from "../../api/feedback";
import { ApiError } from "../../api/client";

const basicFieldClassName =
  "w-full rounded-[5px] border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-1 focus:ring-[#3A5FC3]";

const openBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-amber-400 bg-white px-2.5 text-center text-sm font-bold leading-none text-amber-700 hover:bg-amber-50";
const resolvedBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-emerald-400 bg-white px-2.5 text-center text-sm font-bold leading-none text-emerald-700 hover:bg-emerald-50";
const basicBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900";

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
  } catch {
    return iso;
  }
}

export default function ReportIssuePage() {
  const { t, locale } = useI18n();
  const toast = useToast();
  const { markSeen } = useFeedbackUnread();

  const [category, setCategory] = useState<FeedbackCategory | "">("");
  const [publicationEid, setPublicationEid] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [myReports, setMyReports] = useState<FeedbackReport[]>([]);
  const [loadingMine, setLoadingMine] = useState(true);
  const [openThreadFor, setOpenThreadFor] = useState<FeedbackReport | null>(null);
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | "ALL">("ALL");
  const [searchInput, setSearchInput] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const categoryOptions: { value: FeedbackCategory; label: string }[] = [
    { value: "WRONG_AFFILIATION", label: t.feedback.categoryWrongAffiliation },
    { value: "WRONG_AUTHOR_LINK", label: t.feedback.categoryWrongAuthorLink },
    { value: "OTHER", label: t.feedback.categoryOther },
  ];

  const categoryLabel = (c: FeedbackCategory): string =>
    c === "WRONG_AFFILIATION"
      ? t.feedback.categoryWrongAffiliation
      : c === "WRONG_AUTHOR_LINK"
        ? t.feedback.categoryWrongAuthorLink
        : t.feedback.categoryOther;

  const statusBadgeClass = (s: FeedbackStatus): string =>
    s === "OPEN" ? openBadgeClassName : s === "RESOLVED" ? resolvedBadgeClassName : basicBadgeClassName;

  const statusLabel = (s: FeedbackStatus): string =>
    s === "OPEN" ? t.feedback.statusOpen : s === "RESOLVED" ? t.feedback.statusResolved : t.feedback.statusDismissed;

  const openCount = myReports.filter((r) => r.status === "OPEN").length;

  const filteredReports = myReports.filter((r) => {
    if (statusFilter !== "ALL" && r.status !== statusFilter) return false;
    const q = searchInput.trim().toLowerCase();
    if (!q) return true;
    return categoryLabel(r.category).toLowerCase().includes(q) || r.message.toLowerCase().includes(q);
  });

  const totalPages = Math.max(1, Math.ceil(filteredReports.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const paginatedReports = filteredReports.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const loadMine = useCallback(async () => {
    setLoadingMine(true);
    try {
      const res = await listMyFeedbackReports();
      setMyReports(res.items);
    } catch {
      // the list is a convenience panel; a transient failure here shouldn't block the form
    } finally {
      setLoadingMine(false);
    }
  }, []);

  useEffect(() => {
    void loadMine();
    void markSeen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadMine]);

  const reset = () => {
    setCategory("");
    setPublicationEid("");
    setMessage("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!category) {
      toast.error(t.feedback.pageTitle, t.feedback.categoryRequired);
      return;
    }
    if (!message.trim()) {
      toast.error(t.feedback.pageTitle, t.feedback.messageRequired);
      return;
    }
    setSubmitting(true);
    try {
      await createFeedbackReport({
        category,
        publication_eid: publicationEid.trim() || undefined,
        message: message.trim(),
      });
      toast.success(t.feedback.pageTitle, t.feedback.submitSuccess);
      reset();
      await loadMine();
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : undefined;
      toast.error(t.feedback.pageTitle, detail || t.feedback.pageTitle);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="app-page-container space-y-5">
      <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">
                {t.feedback.categoryLabel}
              </label>
              <select
                className={basicFieldClassName}
                value={category}
                onChange={(e) => setCategory(e.target.value as FeedbackCategory)}
              >
                <option value="" disabled>
                  {t.feedback.categoryAll}
                </option>
                {categoryOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">
                {t.feedback.publicationEidLabel}
              </label>
              <input
                type="text"
                className={basicFieldClassName}
                placeholder={t.feedback.publicationEidPlaceholder}
                value={publicationEid}
                onChange={(e) => setPublicationEid(e.target.value)}
                maxLength={200}
              />
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">
                {t.feedback.messageLabel}
              </label>
              <textarea
                className={`${basicFieldClassName} min-h-32 resize-y`}
                placeholder={t.feedback.messagePlaceholder}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={4000}
              />
            </div>

            <div className="flex justify-end">
              <Button type="submit" variant="primary" loading={submitting} disabled={submitting}>
                {submitting ? t.feedback.submitting : t.feedback.submit}
              </Button>
            </div>
          </form>
        </section>

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
            onChange={(e) => { setSearchInput(e.target.value); setPage(1); }}
            placeholder={t.feedback.myReportsSearchPlaceholder}
            className="h-control w-full rounded-control border border-line bg-slate-50 pl-9 pr-3 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20"
          />
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <select
            aria-label={t.common.status}
            className="h-control shrink-0 rounded-control border border-line bg-slate-50 px-3 text-sm font-semibold text-ink cursor-pointer focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value as FeedbackStatus | "ALL"); setPage(1); }}
          >
            <option value="ALL">{t.feedback.statusAll}</option>
            <option value="OPEN">{`${t.feedback.statusOpen} (${openCount})`}</option>
            <option value="RESOLVED">{t.feedback.statusResolved}</option>
            <option value="DISMISSED">{t.feedback.statusDismissed}</option>
          </select>

          <button
            type="button"
            onClick={() => { setSearchInput(""); setStatusFilter("ALL"); setPage(1); }}
            disabled={!searchInput && statusFilter === "ALL"}
            className={buttonClass("secondary")}
          >
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span className="truncate">{locale === "vi" ? "Đặt lại" : "Reset"}</span>
          </button>
        </div>
      </div>

      <section className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
        <div className="relative overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
              <tr>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{t.feedback.categoryLabel}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700">{t.feedback.messageLabel}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 text-center font-medium text-slate-700 whitespace-nowrap">{t.imports.time}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 text-center font-medium text-slate-700 whitespace-nowrap">{t.common.status}</th>
                <th className="sticky right-0 z-[1] w-44 whitespace-nowrap border-l border-slate-200/80 bg-slate-50 px-2.5 py-3.5 text-center font-medium text-slate-700">
                  {t.common.actions}
                </th>
              </tr>
            </thead>
            <tbody>
              {loadingMine ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center">
                    <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                  </td>
                </tr>
              ) : filteredReports.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center">
                    <div className="flex flex-col items-center gap-1">
                      <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-[5px] border border-slate-200/80 bg-slate-100/80 text-slate-400">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <span className="text-sm font-bold text-slate-700">{t.feedback.myReportsEmpty}</span>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedReports.map((r) => (
                  <tr key={r.id} className="transition-colors duration-300 hover:bg-slate-50/50">
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 align-middle whitespace-nowrap">
                      <span className="font-medium text-slate-800">{categoryLabel(r.category)}</span>
                    </td>
                    <td className="max-w-xs border-r border-b border-slate-100 px-2.5 py-3.5 align-middle">
                      <p className="line-clamp-2 break-words text-slate-600">{r.message}</p>
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 text-center align-middle whitespace-nowrap font-medium text-slate-600">
                      <div>{formatDate(r.created_at)}</div>
                      {r.comment_count > 0 && (
                        <div className="text-slate-400">{r.comment_count} {t.feedback.commentsCountSuffix}</div>
                      )}
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                      <span className={statusBadgeClass(r.status)}>{statusLabel(r.status)}</span>
                    </td>
                    <td className="sticky right-0 z-[1] whitespace-nowrap border-l border-b border-slate-100 bg-white px-2.5 py-3.5 text-center align-middle">
                      <button
                        type="button"
                        onClick={() => setOpenThreadFor(r)}
                        className="relative inline-flex w-32 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 py-0.5 text-sm font-bold text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50 hover:text-slate-900 cursor-pointer"
                      >
                        {r.has_unread && (
                          <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-red-500" />
                        )}
                        {t.common.viewDetails}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-sm text-slate-500">
          <div className="flex items-center gap-3">
            <span>
              {locale === "vi" ? "Hiển thị" : "Showing"} <strong>{paginatedReports.length}</strong> {locale === "vi" ? "trong" : "of"} <strong>{filteredReports.length}</strong> {locale === "vi" ? "báo lỗi" : "reports"}
            </span>
            <div className="flex items-center gap-1.5 border-l border-slate-200 pl-2">
              <span className="text-slate-500">{locale === "vi" ? "Hiển thị:" : "Show:"}</span>
              <select
                value={pageSize}
                onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                className="h-7 rounded-[5px] border border-slate-200 bg-white px-1.5 text-sm font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer"
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
              onClick={() => setPage(currentPage - 1)}
              disabled={currentPage <= 1}
              className={buttonClass("secondary", "sm")}
            >
              {locale === "vi" ? "Trước" : "Previous"}
            </button>
            <span className="px-0.5 text-slate-400">{locale === "vi" ? "Trang" : "Page"}</span>
            <input
              type="number"
              aria-label={locale === "vi" ? "Đến trang" : "Go to page"}
              min={1}
              max={totalPages}
              value={currentPage}
              onChange={(e) => {
                const val = Math.max(1, Math.min(totalPages, parseInt(e.target.value, 10) || 1));
                setPage(val);
              }}
              className="h-8 w-14 rounded-[5px] border border-slate-200 bg-white px-2 text-center text-sm font-bold text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 [appearance:textfield]"
            />
            <span className="text-slate-400">/ <strong className="text-slate-600">{totalPages}</strong></span>
            <button
              type="button"
              onClick={() => setPage(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className={buttonClass("secondary", "sm")}
            >
              {locale === "vi" ? "Sau" : "Next"}
            </button>
          </nav>
        </div>
      </section>

      {openThreadFor && (
        <FeedbackThread
          report={openThreadFor}
          onClose={() => {
            setOpenThreadFor(null);
            void loadMine();
          }}
          categoryLabel={categoryLabel}
          statusLabel={statusLabel}
        />
      )}
    </div>
  );
}
