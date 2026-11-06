import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../../components/ui/PageHeader";
import Button from "../../components/ui/Button";
import ModalPortal from "../../components/common/ModalPortal";
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
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-200 bg-white px-2.5 text-center text-xs font-bold leading-none text-slate-700";
const openBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-amber-400 bg-white px-2.5 text-center text-xs font-bold leading-none text-amber-700";
const resolvedBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-emerald-400 bg-white px-2.5 text-center text-xs font-bold leading-none text-emerald-700";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("vi-VN", {
      year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function FeedbackReportsPage() {
  const { t, locale } = useI18n();
  const toast = useToast();
  const { markSeen } = useFeedbackUnread();

  const [items, setItems] = useState<FeedbackReport[]>([]);
  const [total, setTotal] = useState(0);
  const [openCount, setOpenCount] = useState(0);
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | "ALL">("OPEN");
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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listFeedbackReports(
        statusFilter === "ALL" ? {} : { status: statusFilter },
      );
      setItems(res.items);
      setTotal(res.total);
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
      await resolveFeedbackReport(target.report.id, {
        status: target.status,
        admin_note: adminNote.trim() || undefined,
      });
      setTarget(null);
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
      <PageHeader title={t.feedback.adminPageTitle} subtitle={t.feedback.adminPageSubtitle} />

      <div className="flex items-center gap-2">
        <select
          className="rounded-[5px] border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as FeedbackStatus | "ALL")}
        >
          <option value="ALL">{t.feedback.statusAll}</option>
          <option value="OPEN">{`${t.feedback.statusOpen} (${openCount})`}</option>
          <option value="RESOLVED">{t.feedback.statusResolved}</option>
          <option value="DISMISSED">{t.feedback.statusDismissed}</option>
        </select>
        <span className="text-xs text-slate-500">
          {locale === "vi" ? `Hiển thị ${items.length} trong ${total} báo cáo` : `Showing ${items.length} of ${total} reports`}
        </span>
      </div>

      <section className="overflow-x-auto rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
        {loading ? (
          <div className="flex min-h-40 items-center justify-center">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
          </div>
        ) : items.length === 0 ? (
          <div className="py-14 text-center">
            <p className="text-sm font-bold text-slate-600">{t.feedback.emptyTitle}</p>
            <p className="mt-1 text-xs text-slate-400">{t.feedback.emptySubtitle}</p>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-100 bg-slate-50/60 text-xs text-slate-500">
              <tr>
                <th className="px-3 py-2.5 font-semibold">{t.feedback.columnReporter}</th>
                <th className="px-3 py-2.5 font-semibold">{t.feedback.columnCategory}</th>
                <th className="px-3 py-2.5 font-semibold">{t.feedback.columnPublication}</th>
                <th className="px-3 py-2.5 font-semibold">{t.feedback.columnMessage}</th>
                <th className="px-3 py-2.5 text-center font-semibold">{t.feedback.columnStatus}</th>
                <th className="px-3 py-2.5 font-semibold">{t.feedback.columnCreatedAt}</th>
                <th className="px-3 py-2.5 text-center font-semibold">{t.feedback.columnActions}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {items.map((item) => (
                <tr key={item.id} className="align-top hover:bg-slate-50/50">
                  <td className="px-3 py-2.5 font-medium text-slate-800">{item.reporter_name}</td>
                  <td className="px-3 py-2.5 text-slate-600">{categoryLabel(item.category)}</td>
                  <td className="px-3 py-2.5 font-mono text-xs text-slate-500">{item.publication_eid || "—"}</td>
                  <td className="max-w-xs px-3 py-2.5 text-slate-700">
                    <p className="line-clamp-3 break-words">{item.message}</p>
                    {item.admin_note && (
                      <p className="mt-1 text-xs italic text-slate-400">
                        {t.feedback.adminNoteLabel}: {item.admin_note}
                      </p>
                    )}
                    {item.comment_count > 0 && (
                      <p className="mt-1 text-[11px] text-slate-400">
                        {item.comment_count} {t.feedback.commentsCountSuffix}
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={statusBadgeClass(item.status)}>{statusLabel(item.status)}</span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-slate-500">{formatDate(item.created_at)}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-col items-center gap-2">
                      <Button variant="tonal" size="sm" onClick={() => setThreadFor(item)}>
                        {t.feedback.viewThreadAction}
                      </Button>
                      {item.status === "OPEN" ? (
                        <div className="flex items-center justify-center gap-2">
                          <Button variant="secondary" size="sm" onClick={() => openResolveModal(item, "DISMISSED")}>
                            {t.feedback.dismissAction}
                          </Button>
                          <Button variant="primary" size="sm" onClick={() => openResolveModal(item, "RESOLVED")}>
                            {t.feedback.resolveAction}
                          </Button>
                        </div>
                      ) : (
                        <p className="text-center text-xs text-slate-400">{item.resolved_at ? formatDate(item.resolved_at) : "—"}</p>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {target && (
        <ModalPortal>
          <div
            className="fixed inset-x-0 top-16 bottom-0 md:left-[var(--app-sidebar-w)] z-50 flex items-center justify-center bg-black/60 p-4 modal-backdrop-in transition-[left] duration-200 ease-out"
            onClick={() => !submitting && setTarget(null)}
          >
            <div
              className="w-full max-w-md rounded-card border border-slate-200 bg-white shadow-2xl modal-panel-in"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="border-b border-slate-100 px-5 py-4">
                <h2 className="text-base font-bold text-slate-900">{t.feedback.resolveModalTitle}</h2>
              </div>
              <div className="space-y-3 px-5 py-4">
                <p className="text-sm text-slate-600">{target.report.message}</p>
                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">
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
              <div className="flex items-center justify-end gap-2 border-t border-slate-100 px-5 py-3">
                <Button variant="secondary" onClick={() => setTarget(null)} disabled={submitting}>
                  {t.feedback.resolveModalCancel}
                </Button>
                <Button variant="primary" onClick={() => void confirmResolve()} loading={submitting}>
                  {t.feedback.resolveModalConfirm}
                </Button>
              </div>
            </div>
          </div>
        </ModalPortal>
      )}

      {threadFor && (
        <FeedbackThread
          report={threadFor}
          onClose={() => {
            setThreadFor(null);
            void load();
          }}
          categoryLabel={categoryLabel}
          statusLabel={statusLabel}
        />
      )}
    </div>
  );
}
