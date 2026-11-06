import { useState } from "react";
import { PageHeader } from "../../components/ui/PageHeader";
import Button from "../../components/ui/Button";
import { useI18n } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import { createFeedbackReport, type FeedbackCategory } from "../../api/feedback";
import { ApiError } from "../../api/client";

const basicFieldClassName =
  "w-full rounded-[5px] border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-1 focus:ring-[#3A5FC3]";

export default function ReportIssuePage() {
  const { t } = useI18n();
  const toast = useToast();

  const [category, setCategory] = useState<FeedbackCategory | "">("");
  const [publicationEid, setPublicationEid] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [justSubmitted, setJustSubmitted] = useState(false);

  const categoryOptions: { value: FeedbackCategory; label: string }[] = [
    { value: "WRONG_AFFILIATION", label: t.feedback.categoryWrongAffiliation },
    { value: "WRONG_AUTHOR_LINK", label: t.feedback.categoryWrongAuthorLink },
    { value: "OTHER", label: t.feedback.categoryOther },
  ];

  const reset = () => {
    setCategory("");
    setPublicationEid("");
    setMessage("");
    setJustSubmitted(false);
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
      setJustSubmitted(true);
      toast.success(t.feedback.pageTitle, t.feedback.submitSuccess);
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

      <section className="max-w-2xl rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
        {justSubmitted ? (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
              <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
              </svg>
            </span>
            <p className="max-w-sm text-sm text-slate-600">{t.feedback.submitSuccess}</p>
            <Button type="button" variant="secondary" onClick={reset}>
              {t.feedback.submitAnother}
            </Button>
          </div>
        ) : (
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
        )}
      </section>
    </div>
  );
}
