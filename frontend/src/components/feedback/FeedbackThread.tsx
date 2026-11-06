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
  type FeedbackCategory,
  type FeedbackComment,
  type FeedbackReport,
  type FeedbackStatus,
} from "../../api/feedback";
import { ApiError } from "../../api/client";

const POLL_INTERVAL_MS = 3000;

const openBadgeClassName =
  "inline-flex h-badge shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-amber-400 bg-white px-2.5 text-center text-xs font-bold leading-none text-amber-700";
const resolvedBadgeClassName =
  "inline-flex h-badge shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-emerald-400 bg-white px-2.5 text-center text-xs font-bold leading-none text-emerald-700";
const basicBadgeClassName =
  "inline-flex h-badge shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-200 bg-white px-2.5 text-center text-xs font-bold leading-none text-slate-700";

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("vi-VN", {
      year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    });
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
  report, onClose, categoryLabel, statusLabel, footer,
}: FeedbackThreadProps) {
  const { t } = useI18n();
  const { user } = useAuth();
  const toast = useToast();

  const [comments, setComments] = useState<FeedbackComment[]>([]);
  const [liveStatus, setLiveStatus] = useState<FeedbackStatus>(report.status);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [commentsRes, reportRes] = await Promise.all([
        listFeedbackComments(report.id),
        getFeedbackReport(report.id),
      ]);
      setComments(commentsRes.items);
      setLiveStatus(reportRes.status);
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

  const statusBadgeClass =
    liveStatus === "OPEN" ? openBadgeClassName
      : liveStatus === "RESOLVED" ? resolvedBadgeClassName
        : basicBadgeClassName;

  return (
    <ModalPortal>
      <div
        className="fixed inset-x-0 top-16 bottom-0 md:left-[var(--app-sidebar-w)] z-50 flex items-center justify-center bg-black/60 p-4 modal-backdrop-in transition-[left] duration-200 ease-out"
        onClick={onClose}
      >
        <div
          className="flex max-h-[85vh] w-full max-w-lg flex-col rounded-card border border-slate-200 bg-white shadow-2xl modal-panel-in"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">{t.feedback.threadTitle}</h2>
              <p className="mt-0.5 text-xs text-slate-500">{categoryLabel(report.category)}</p>
            </div>
            <span className={statusBadgeClass}>{statusLabel(liveStatus)}</span>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
            <div className="rounded-[5px] border border-slate-100 bg-slate-50/70 px-3 py-2.5 text-sm text-slate-700">
              <p className="mb-1 text-xs font-bold text-slate-500">
                {report.reporter_name} · {formatDateTime(report.created_at)}
              </p>
              <p className="whitespace-pre-wrap break-words">{report.message}</p>
              {report.publication_eid && (
                <p className="mt-1.5 font-mono text-xs text-slate-400">{report.publication_eid}</p>
              )}
            </div>

            {loading ? (
              <div className="flex justify-center py-6">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
              </div>
            ) : comments.length === 0 ? (
              <p className="py-4 text-center text-xs text-slate-400">{t.feedback.threadEmpty}</p>
            ) : (
              comments.map((c) => {
                const mine = user?.id === c.author_user_id;
                return (
                  <div key={c.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[85%] rounded-[5px] px-3 py-2 text-sm shadow-sm ${
                        mine
                          ? "bg-[#3A5FC3] text-white"
                          : c.is_staff_author
                            ? "border border-emerald-200 bg-emerald-50 text-slate-800"
                            : "border border-slate-300 bg-slate-100 text-slate-800"
                      }`}
                    >
                      <p className={`mb-0.5 text-[11px] font-bold ${mine ? "text-white/80" : "text-slate-500"}`}>
                        {mine ? t.feedback.youLabel : c.is_staff_author ? t.feedback.staffReplyLabel : c.author_name}
                      </p>
                      <p className="whitespace-pre-wrap break-words">{c.message}</p>
                      <p className={`mt-1 text-[10px] ${mine ? "text-white/70" : "text-slate-400"}`}>
                        {formatDateTime(c.created_at)}
                      </p>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="space-y-2 border-t border-slate-100 px-5 py-3">
            <div className="flex items-end gap-2">
              <textarea
                className="min-h-16 flex-1 resize-y rounded-[5px] border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-1 focus:ring-[#3A5FC3]"
                placeholder={t.feedback.commentPlaceholder}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
                maxLength={4000}
              />
              <Button variant="primary" onClick={() => void send()} loading={sending}>
                {sending ? t.feedback.commentSending : t.feedback.commentSend}
              </Button>
            </div>
            <div className="flex items-center justify-between gap-2">
              <div>{footer}</div>
              <Button variant="secondary" size="sm" onClick={onClose}>
                {t.common.close}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </ModalPortal>
  );
}
