import { useCallback, useEffect, useState } from "react";
import Button, { buttonClass } from "../../components/ui/Button";
import ConfirmModal from "../../components/common/ConfirmModal";
import FeedbackThread from "../../components/feedback/FeedbackThread";
import { useI18n } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import { useFeedbackUnread } from "../../contexts/FeedbackUnreadContext";
import {
  listFeedbackReports,
  resolveFeedbackReport,
  type FeedbackCategory,
  type FeedbackReport,
  type FeedbackStatus,
} from "../../api/feedback";
import { ApiError } from "../../api/client";

const basicBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900";
const openBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-amber-400 bg-white px-2.5 text-center text-sm font-bold leading-none text-amber-700 hover:bg-amber-50";
const resolvedBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-emerald-400 bg-white px-2.5 text-center text-sm font-bold leading-none text-emerald-700 hover:bg-emerald-50";

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
  } catch {
    return iso;
  }
}

export default function FeedbackReportsPage() {
  const { t, locale } = useI18n();
  const toast = useToast();
  const { markSeen } = useFeedbackUnread();

  const [items, setItems] = useState<FeedbackReport[]>([]);
  const [openCount, setOpenCount] = useState(0);
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | "ALL">("ALL");
  const [searchInput, setSearchInput] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [target, setTarget] = useState<{ report: FeedbackReport; status: "RESOLVED" | "DISMISSED" } | null>(null);
  const [adminNote, setAdminNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [threadFor, setThreadFor] = useState<FeedbackReport | null>(null);

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

  const filteredItems = items.filter((item) => {
    const q = searchInput.trim().toLowerCase();
    if (!q) return true;
    return (
      item.reporter_name.toLowerCase().includes(q) ||
      item.message.toLowerCase().includes(q) ||
      categoryLabel(item.category).toLowerCase().includes(q) ||
      (item.publication_eid ? item.publication_eid.toLowerCase().includes(q) : false)
    );
  });

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const paginatedItems = filteredItems.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listFeedbackReports(
        statusFilter === "ALL" ? {} : { status: statusFilter },
      );
      setItems(res.items);
      setOpenCount(res.open_count);
    } catch {
      toast.error(t.feedback.adminPageTitle, t.common.noData);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void markSeen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openResolveModal = (report: FeedbackReport, status: "RESOLVED" | "DISMISSED") => {
    setTarget({ report, status });
    setAdminNote("");
  };

  const confirmResolve = async () => {
    if (!target) return;
    setSubmitting(true);
    try {
      const updated = await resolveFeedbackReport(target.report.id, {
        status: target.status,
        admin_note: adminNote.trim() || undefined,
      });
      setTarget(null);
      setThreadFor((prev) => (prev && prev.id === updated.id ? updated : prev));
      await load();
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : undefined;
      toast.error(t.feedback.adminPageTitle, detail || t.feedback.adminPageTitle);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="app-page-container space-y-5">
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
            placeholder={t.feedback.searchPlaceholder}
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
            onClick={() => {
              setSearchInput("");
              setStatusFilter("ALL");
              setPage(1);
            }}
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
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{t.feedback.columnReporter}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{t.feedback.columnCategory}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700">{t.feedback.columnPublication}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700">{t.feedback.columnMessage}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 text-center font-medium text-slate-700 whitespace-nowrap">{t.feedback.columnStatus}</th>
                <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{t.feedback.columnCreatedAt}</th>
                <th className="sticky right-0 z-[1] w-32 whitespace-nowrap border-l border-slate-200/80 bg-slate-50 px-2.5 py-3.5 text-center font-medium text-slate-700">
                  {t.feedback.columnActions}
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-10 text-center">
                    <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                  </td>
                </tr>
              ) : filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center">
                    <div className="flex flex-col items-center gap-1">
                      <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-[5px] border border-slate-200/80 bg-slate-100/80 text-slate-400">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <span className="text-sm font-bold text-slate-700">{t.feedback.emptyTitle}</span>
                      <span className="text-sm text-slate-400">{t.feedback.emptySubtitle}</span>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedItems.map((item) => (
                  <tr key={item.id} className="transition-colors duration-300 hover:bg-slate-50/50">
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 align-middle font-medium text-slate-800 whitespace-nowrap">
                      {item.reporter_name}
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 align-middle text-slate-600 whitespace-nowrap">
                      {categoryLabel(item.category)}
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 align-middle text-slate-600 whitespace-nowrap">
                      {item.publication_eid || "—"}
                    </td>
                    <td className="max-w-xs border-r border-b border-slate-100 px-2.5 py-3.5 align-middle">
                      <p className="line-clamp-3 break-words text-slate-700">{item.message}</p>
                      {item.admin_note && (
                        <p className="mt-1 text-sm italic text-slate-400">
                          {t.feedback.adminNoteLabel}: {item.admin_note}
                        </p>
                      )}
                      {item.comment_count > 0 && (
                        <p className="mt-1 text-sm text-slate-400">
                          {item.comment_count} {t.feedback.commentsCountSuffix}
                        </p>
                      )}
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                      <span className={statusBadgeClass(item.status)}>{statusLabel(item.status)}</span>
                    </td>
                    <td className="border-r border-b border-slate-100 px-2.5 py-3.5 align-middle text-slate-600 whitespace-nowrap">
                      {formatDate(item.created_at)}
                    </td>
                    <td className="sticky right-0 z-[1] whitespace-nowrap border-l border-b border-slate-100 bg-white px-2.5 py-3.5 text-center align-middle">
                      <div className="relative inline-block">
                        <button
                          type="button"
                          onClick={() => setThreadFor(item)}
                          className="inline-flex w-32 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 py-0.5 text-sm font-bold text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50 hover:text-slate-900 cursor-pointer"
                        >
                          {t.common.viewDetails}
                        </button>
                        {item.has_unread && (
                          <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-red-500" />
                        )}
                      </div>
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
              {locale === "vi" ? "Hiển thị" : "Showing"} <strong>{paginatedItems.length}</strong> {locale === "vi" ? "trong" : "of"} <strong>{filteredItems.length}</strong> {locale === "vi" ? "báo lỗi" : "reports"}
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

      <ConfirmModal
        open={!!target}
        variant="primary"
        title={t.feedback.resolveModalTitle}
        confirmLabel={t.feedback.resolveModalConfirm}
        cancelLabel={t.feedback.resolveModalCancel}
        loading={submitting}
        onConfirm={() => void confirmResolve()}
        onCancel={() => setTarget(null)}
        description={
          target && (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">{target.report.message}</p>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  {t.feedback.resolveModalNoteLabel}
                </label>
                <textarea
                  className="min-h-24 w-full resize-y rounded-[5px] border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-1 focus:ring-[#3A5FC3]"
                  placeholder={t.feedback.resolveModalNotePlaceholder}
                  value={adminNote}
                  onChange={(e) => setAdminNote(e.target.value)}
                  maxLength={4000}
                />
              </div>
            </div>
          )
        }
      />

      {threadFor && (
        <FeedbackThread
          report={threadFor}
          onClose={() => {
            setThreadFor(null);
            void load();
          }}
          categoryLabel={categoryLabel}
          statusLabel={statusLabel}
          footer={
            threadFor.status === "OPEN" ? (
              <div className="flex items-center gap-2">
                <Button variant="secondary" onClick={() => openResolveModal(threadFor, "DISMISSED")}>
                  {t.feedback.dismissAction}
                </Button>
                <Button variant="primary" onClick={() => openResolveModal(threadFor, "RESOLVED")}>
                  {t.feedback.resolveAction}
                </Button>
              </div>
            ) : (
              <p className="text-sm text-slate-400">
                {threadFor.resolved_at ? formatDate(threadFor.resolved_at) : "—"}
              </p>
            )
          }
        />
      )}
    </div>
  );
}
