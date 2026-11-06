import { useCallback, useEffect, useRef, useState } from "react";
import ModalPortal from "../common/ModalPortal";
import Button from "../ui/Button";
import { useI18n } from "../../i18n";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import {
  addFeedbackComment,
  getFeedbackReport,
  listFeedbackComments,
  markFeedbackReportSeen,
  type FeedbackCategory,
  type FeedbackComment,
  type FeedbackReport,
  type FeedbackStatus,
} from "../../api/feedback";
import { ApiError } from "../../api/client";

const POLL_INTERVAL_MS = 3000;

function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
  } catch {
    return iso;
  }
}

export interface FeedbackThreadProps {
  report: FeedbackReport;
  onClose: () => void;
  categoryLabel: (c: FeedbackCategory) => string;
  statusLabel: (s: FeedbackStatus) => string;
  footer?: React.ReactNode;
}

export default function FeedbackThread({
  report, onClose, categoryLabel, footer,
}: FeedbackThreadProps) {
  const { t } = useI18n();
  const { user } = useAuth();
  const toast = useToast();

  const [comments, setComments] = useState<FeedbackComment[]>([]);
  const [currentStatus, setCurrentStatus] = useState<FeedbackStatus>(report.status);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const isClosed = currentStatus === "RESOLVED" || currentStatus === "DISMISSED";

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [commentsRes, reportRes] = await Promise.all([
        listFeedbackComments(report.id),
        getFeedbackReport(report.id),
      ]);
      setComments(commentsRes.items);
      setCurrentStatus(reportRes.status);
    } catch {
      if (!silent) toast.error(t.feedback.threadTitle, t.common.noData);
    } finally {
      if (!silent) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report.id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Clears this report's own unread dot in the list — separate from the
  // global "has new feedback somewhere" marker, which the list page clears
  // just by being visited.
  useEffect(() => {
    void markFeedbackReportSeen(report.id);
  }, [report.id]);

  // Poll while the thread is open so a reply from the other side (admin and
  // reporter are typically two different logged-in sessions) shows up without
  // the viewer having to close and reopen the modal.
  useEffect(() => {
    const id = window.setInterval(() => void load(true), POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [load]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [comments]);

  const send = async () => {
    if (isClosed) return;
    if (!draft.trim()) {
      toast.error(t.feedback.threadTitle, t.feedback.commentRequired);
      return;
    }
    setSending(true);
    try {
      const comment = await addFeedbackComment(report.id, { message: draft.trim() });
      setComments((prev) => [...prev, comment]);
      setDraft("");
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : undefined;
      toast.error(t.feedback.threadTitle, detail || t.feedback.threadTitle);
    } finally {
      setSending(false);
    }
  };

  return (
    <ModalPortal>
      <div
        className="fixed inset-x-0 top-16 bottom-0 md:left-[var(--app-sidebar-w)] z-50 flex items-center justify-center overflow-hidden bg-black/60 p-4 modal-backdrop-in transition-[left] duration-200 ease-out"
        onClick={onClose}
      >
        <div
          className="flex h-full w-full max-w-none flex-col overflow-hidden rounded-card border border-blue-200 bg-white shadow-2xl modal-panel-in"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex shrink-0 items-start justify-between gap-4 border-b border-blue-100 bg-blue-50 px-5 py-4">
            <div>
              <h2 className="text-base font-bold text-[#2f4ea6] sm:text-lg">{t.feedback.threadTitle}</h2>
              <p className="mt-0.5 text-sm text-[#3A5FC3]">{categoryLabel(report.category)}</p>
            </div>
          </div>

          <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
            <div className="rounded-[5px] border border-slate-100 bg-slate-50/70 px-3 py-2.5 text-sm text-slate-700">
              <p className="mb-1 text-sm font-bold text-slate-500">
                {report.reporter_name} · {formatDateTime(report.created_at)}
              </p>
              <p className="whitespace-pre-wrap break-words">{report.message}</p>
              {report.publication_eid && (
                <p className="mt-1.5 font-mono text-sm text-slate-400">{report.publication_eid}</p>
              )}
            </div>

            {loading ? (
              <div className="flex justify-center py-6">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
              </div>
            ) : comments.length === 0 ? (
              <p className="py-4 text-center text-sm text-slate-400">{t.feedback.threadEmpty}</p>
            ) : (
              comments.map((c) => {
                const mine = user?.id === c.author_user_id;
                return (
                  <div key={c.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[85%] rounded-[5px] px-3 py-2 text-sm shadow-sm ${
                        mine
                          ? "bg-[#3A5FC3] text-white"
                          : "border border-blue-200 bg-blue-50 text-slate-800"
                      }`}
                    >
                      <p className="whitespace-pre-wrap break-words">{c.message}</p>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="shrink-0 space-y-2 border-t border-slate-100 px-5 py-3">
            <textarea
              className="min-h-16 w-full resize-y rounded-[5px] border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-1 focus:ring-[#3A5FC3] disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
              placeholder={
                currentStatus === "RESOLVED"
                  ? t.feedback.commentClosedResolved
                  : currentStatus === "DISMISSED"
                    ? t.feedback.commentClosedDismissed
                    : t.feedback.commentPlaceholder
              }
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              maxLength={4000}
              disabled={isClosed}
            />
            <div className="flex items-center justify-between gap-2">
              <div>{footer}</div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" className="font-bold" onClick={onClose}>
                  {t.common.close}
                </Button>
                <Button variant="primary" onClick={() => void send()} loading={sending} disabled={isClosed}>
                  {sending ? t.feedback.commentSending : t.feedback.commentSend}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ModalPortal>
  );
}
