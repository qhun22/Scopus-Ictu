import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../../components/ui/PageHeader";
import Button from "../../components/ui/Button";
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
  "inline-flex h-badge shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-amber-400 bg-white px-2.5 text-center text-xs font-bold leading-none text-amber-700";
const resolvedBadgeClassName =
  "inline-flex h-badge shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-emerald-400 bg-white px-2.5 text-center text-xs font-bold leading-none text-emerald-700";
const basicBadgeClassName =
  "inline-flex h-badge shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-200 bg-white px-2.5 text-center text-xs font-bold leading-none text-slate-700";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("vi-VN", {
      year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function ReportIssuePage() {
  const { t } = useI18n();
  const toast = useToast();
  const { markSeen } = useFeedbackUnread();

  const [category, setCategory] = useState<FeedbackCategory | "">("");
  const [publicationEid, setPublicationEid] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [myReports, setMyReports] = useState<FeedbackReport[]>([]);
  const [loadingMine, setLoadingMine] = useState(true);
  const [openThreadFor, setOpenThreadFor] = useState<FeedbackReport | null>(null);

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
      <PageHeader title={t.feedback.pageTitle} subtitle={t.feedback.pageSubtitle} />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">
                {t.feedback.categoryLabel}
              </label>
              <select
                className={basicFieldClassName}
                value={category}
                onChange={(e) => setCategory(e.target.value as FeedbackCategory)}
              >
                <option value="" disabled>
                  {t.feedback.categoryLabel}
                </option>
                {categoryOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">
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
              <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">
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

        <section className="flex flex-col rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
          <h2 className="text-sm font-bold text-slate-800">{t.feedback.myReportsTitle}</h2>
          <p className="mt-0.5 text-xs text-slate-500">{t.feedback.myReportsSubtitle}</p>

          <div className="mt-3 flex-1 space-y-2 overflow-y-auto">
            {loadingMine ? (
              <div className="flex justify-center py-8">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
              </div>
            ) : myReports.length === 0 ? (
              <p className="py-8 text-center text-xs text-slate-400">{t.feedback.myReportsEmpty}</p>
            ) : (
              myReports.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setOpenThreadFor(r)}
                  className="block w-full rounded-[5px] border border-slate-100 bg-slate-50/50 px-3 py-2.5 text-left transition-colors hover:border-slate-200 hover:bg-slate-50"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-700">{categoryLabel(r.category)}</span>
                    <span className={statusBadgeClass(r.status)}>{statusLabel(r.status)}</span>
                  </div>
                  <p className="mt-1 line-clamp-2 break-words text-xs text-slate-600">{r.message}</p>
                  <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-400">
                    <span>{formatDate(r.created_at)}</span>
                    {r.comment_count > 0 && (
                      <span>{r.comment_count} {t.feedback.commentsCountSuffix}</span>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>
        </section>
      </div>

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
