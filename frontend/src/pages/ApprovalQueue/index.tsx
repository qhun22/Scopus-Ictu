import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  Alert,
  Button,
  ConfigProvider,
  Empty,
  Input,
  Space,
} from "antd";
// Design system tokens scoped to this page's AntD usage.
const ANTD_THEME = {
  token: {
    colorPrimary: "#3A5FC3",
    colorError: "#E11D48",
    borderRadius: 5,
    fontFamily: "Saira, Arial, sans-serif",
  },
  components: {
    Button: { borderRadius: 5 },
    Modal: { borderRadiusLG: 5, titleFontSize: 15 },
    Card: { borderRadiusLG: 5 },
  },
};

import {
  decideReviewCandidate,
  getLecturersWithoutCandidates,
  getReviewCandidate,
  getReviewCandidates,
  getReviewContext,
  reopenRejectedCandidate,
  revokeReviewCandidate,
} from "../../api/reviews";
import type { LecturerWithoutCandidateItem } from "../../types/review";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { useToast } from "../../contexts/ToastContext";
import { useAuth } from "../../contexts/AuthContext";
import { useI18n } from "../../i18n/I18nContext";
import Badge, { type BadgeTone } from "../../components/ui/Badge";
import UiButton from "../../components/ui/Button";
import ModalPortal from "../../components/common/ModalPortal";
import FullModal from "../../components/common/FullModal";
import ConfirmModal from "../../components/common/ConfirmModal";
import FitBadge, { fitLevelLabel, fitReasonText } from "./FitBadge";
import PrimaryIdPanel from "./PrimaryIdPanel";
import { CANDIDATE_STATUS_TONE } from "../../components/ui/reviewTones";

// "Nhãn chuẩn" style used across Imports/Normalization/Lecturers/Công bố:
// h-badge, w-32, rounded-[5px], white bg, bold xs text — not the rounded-full Badge component.
const NHAN_TONE_STYLE: Record<BadgeTone, string> = {
  success: "border-emerald-400 text-emerald-700 hover:bg-emerald-50",
  warning: "border-amber-400 text-amber-700 hover:bg-amber-50",
  danger: "border-red-400 text-red-700 hover:bg-red-50",
  info: "border-sky-400 text-sky-700 hover:bg-sky-50",
  indigo: "border-indigo-400 text-indigo-700 hover:bg-indigo-50",
  neutral: "border-slate-300 text-slate-500 hover:bg-slate-50",
  violet: "border-violet-400 text-violet-700 hover:bg-violet-50",
  brand: "border-[#3A5FC3] text-[#3A5FC3] hover:bg-blue-50",
};

function nhanBadgeClass(tone: BadgeTone): string {
  // Fixed w-32 keeps rows aligned; labels must fit in ~106px of text (text-sm bold) — shorten the wording, never widen the badge.
  return `inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border bg-white px-2.5 text-center text-sm font-bold leading-none ${NHAN_TONE_STYLE[tone]}`;
}
import { reconciliationLabel, ruleLabel, surfaceLabel } from "./ruleLabels";
import type { TranslationSchema } from "../../i18n/types";
import type {
  AmbiguityFilter,
  ReviewContext,
  CandidateStatus,
  EvidenceCategory,
  ReviewAction,
  ReviewCandidateDetail,
  ReviewNameEvidence,
  ReviewQueueItem,
  ReviewReasonTrigger,
} from "../../types/review";


type EvidenceFilter = EvidenceCategory | "all";
type AmbiguitySelection = AmbiguityFilter | "all";
type T = TranslationSchema["approvalQueue"];


function reasonTriggerText(t: T, trigger: ReviewReasonTrigger): string {
  switch (trigger) {
    case "NAME_EVIDENCE_ONLY":
      return t.reasonTriggerNameOnly;
    case "SHARED_SCOPUS_AUTHOR":
      return t.reasonTriggerSharedAuthor;
    case "MULTIPLE_CANDIDATES_FOR_LECTURER":
      return t.reasonTriggerMultipleCandidates;
    default:
      return trigger;
  }
}

function statusLabels(t: T): Record<CandidateStatus, string> {
  return {
    PENDING: t.statusPending,
    ACCEPTED: t.statusAccepted,
    REJECTED: t.statusRejected,
    SUPERSEDED: t.statusSuperseded,
  };
}

function conflictMessages(t: T): Readonly<Record<string, string>> {
  return {
    STALE_CANDIDATE_VERSION: t.conflictStaleVersion,
    STALE_CANDIDATE_OBSERVATION: t.conflictStaleObservation,
    CANDIDATE_ALREADY_DECIDED_CONFLICT: t.conflictAlreadyDecided,
    SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER: t.conflictScopusAuthorApprovedElsewhere,
    PREEXISTING_IDENTITY_PROVENANCE_CONFLICT: t.conflictPreexistingProvenance,
  };
}

function format(template: string, values: Record<string, string | number>): string {
  return Object.entries(values).reduce(
    (acc, [key, value]) => acc.replace(`{${key}}`, String(value)),
    template,
  );
}

function ambiguityText(t: T, count: number): string {
  if (count <= 1) return t.noOtherCandidates;
  if (count === 2) return t.oneOtherCandidate;
  return format(t.multipleCandidates, { count });
}

function sharedAuthorText(t: T, count: number | undefined): string {
  return format(t.sharedAuthorText, { count: count ?? t.sharedAuthorMany });
}

function displayValue(t: T, value: string | null | undefined): string {
  const normalized = value?.trim();
  return normalized ? normalized : t.noData;
}

function provenanceText(t: T, ref: unknown): string {
  if (typeof ref !== "object" || ref === null) return String(ref);
  const values = Object.entries(ref as Record<string, unknown>)
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([key, value]) => `${key}: ${String(value)}`);
  return values.length > 0 ? values.join(" · ") : t.sourceNoDescription;
}

/** One titled card per section of the review detail, so every block reads the same way. */
function DetailSection({ title, count, extra, children, testId }: {
  title: string;
  count?: number;
  extra?: ReactNode;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <section className="rounded-[5px] border border-slate-200 bg-white p-4" data-testid={testId}>
      <div className="mb-3 flex flex-wrap items-center gap-3 border-b border-slate-100 pb-2.5">
        <h3 className="text-sm font-bold text-slate-800">
          {title}
          {count !== undefined && <span className="ml-1 font-medium text-slate-500">({count})</span>}
        </h3>
        {extra}
      </div>
      {children}
    </section>
  );
}

const NOTICE_TONE = {
  warning: "border-amber-300 bg-amber-50/60 text-amber-800",
  danger: "border-red-300 bg-red-50/60 text-red-800",
  info: "border-slate-200 bg-slate-50 text-slate-700",
} as const;

function Notice({ tone, title, children }: { tone: keyof typeof NOTICE_TONE; title: string; children?: ReactNode }) {
  return (
    <div className={`rounded-[5px] border px-4 py-3 text-sm ${NOTICE_TONE[tone]}`} role={tone === "info" ? undefined : "alert"}>
      <p className="font-semibold">{title}</p>
      {children && <div className="mt-1 leading-relaxed">{children}</div>}
    </div>
  );
}

/** Which pair a confirm dialog acts on — same block in accept / reject / revoke / reopen. */
function PairSummary({ t, detail }: { t: T; detail: ReviewCandidateDetail }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 rounded-[5px] border border-slate-200 bg-slate-50/60 px-4 py-3 text-sm">
      <dt className="text-slate-500">{t.fieldLecturer}</dt>
      <dd className="font-semibold text-slate-900">{detail.lecturer.full_name}</dd>
      <dt className="text-slate-500">{t.fieldScopusAuthor}</dt>
      <dd className="text-slate-800">{detail.scopus_author.preferred_name}</dd>
      <dt className="text-slate-500">{t.fieldScopusId}</dt>
      <dd className="font-mono font-medium text-slate-700">{detail.scopus_author.scopus_id}</dd>
    </dl>
  );
}

/** Raw provenance (ids, kinds) is for audit, not for deciding: keep it folded away. */
function TechnicalSources({ t, locale, refs, keyPrefix }: { t: T; locale: "vi" | "en"; refs: unknown[]; keyPrefix: string }) {
  if (refs.length === 0) return null;
  return (
    <details className="mt-3 border-t border-slate-100 pt-2">
      <summary className="cursor-pointer select-none text-sm font-medium text-slate-500 hover:text-slate-700">
        {locale === "en" ? "Technical source data" : "Dữ liệu nguồn (kỹ thuật)"}
      </summary>
      <div className="mt-2 break-all text-xs leading-relaxed text-slate-500">
        {refs.map((ref, index) => (
          <span key={`${keyPrefix}-source-${index}`}>
            {index > 0 && " | "}
            {provenanceText(t, ref)}
          </span>
        ))}
      </div>
    </details>
  );
}

function NameEvidenceCard({ t, locale, evidence }: { t: T; locale: "vi" | "en"; evidence: ReviewNameEvidence }) {
  return (
    <div className="rounded-[5px] border border-slate-200 bg-slate-50/60 p-4">
      <div className="mb-3 text-sm font-semibold text-slate-800" title={evidence.rule_id} data-testid="name-rule-label">
        {ruleLabel(evidence.rule_id, locale)}
      </div>
      <div className="grid gap-4 text-sm md:grid-cols-2">
        <div>
          <div className="text-slate-500">{t.lecturerProfileNameLabel}</div>
          <div className="mt-0.5 font-semibold text-slate-900">
            {displayValue(t, evidence.lecturer_source_value)}
          </div>
          {evidence.lecturer_comparison_value && (
            <div className="mt-1 text-slate-500">
              {t.comparisonValueLabel}: <span className="font-mono">{evidence.lecturer_comparison_value}</span>
            </div>
          )}
        </div>
        <div>
          <div className="text-slate-500">{t.scopusNameLabel}</div>
          <div className="mt-0.5 font-semibold text-slate-900">
            {displayValue(t, evidence.scopus_surface_value)}
          </div>
          <div className="mt-1 text-slate-500">
            {evidence.scopus_surface_type && `${t.typeLabel}: ${surfaceLabel(evidence.scopus_surface_type, locale)}`}
            {evidence.scopus_comparison_value && (
              <>
                {evidence.scopus_surface_type ? " · " : ""}
                {t.comparisonValueLabel}: <span className="font-mono">{evidence.scopus_comparison_value}</span>
              </>
            )}
          </div>
        </div>
      </div>
      <TechnicalSources t={t} locale={locale} refs={evidence.source_refs} keyPrefix={evidence.evidence_id} />
    </div>
  );
}

function emptyQueueCopy(
  t: T,
  locale: string,
  context: ReviewContext | null,
): { title: string; text: string } {
  if (!context) {
    return { title: t.emptyDefaultTitle, text: t.emptyDefaultText };
  }
  const n = (v: number) => v.toLocaleString(locale === "vi" ? "vi-VN" : "en-US");
  const purpose = t.emptyPurposeNote;
  switch (context.state) {
    case "NO_LECTURERS":
      return {
        title: t.emptyNoLecturersTitle,
        text:
          purpose +
          format(t.emptyNoLecturersText, {
            publications: n(context.publications_total),
            scopusAuthors: n(context.scopus_authors_total),
          }),
      };
    case "NO_CANDIDATE_RUN":
      return {
        title: t.emptyNoCandidateRunTitle,
        text:
          purpose +
          format(t.emptyNoCandidateRunText, {
            lecturers: n(context.lecturers_total),
            scopusAuthors: n(context.scopus_authors_total),
          }),
      };
    case "RUN_WITHOUT_CANDIDATES":
      return {
        title: t.emptyRunWithoutCandidatesTitle,
        text:
          purpose +
          format(t.emptyRunWithoutCandidatesText, {
            runs: n(context.completed_generation_runs),
          }),
      };
    default: {
      const by = context.candidates_by_status;
      const others = Object.entries(by)
        .filter(([, count]) => count > 0)
        .map(([name, count]) => `${statusLabels(t)[name as CandidateStatus] ?? name}: ${n(count)}`)
        .join(" · ");
      return {
        title: t.emptyFilteredTitle,
        text: format(t.emptyFilteredText, { others }),
      };
    }
  }
}

export default function ApprovalQueuePage() {
  const toast = useToast();
  const { user } = useAuth();
  const { t: fullT, locale } = useI18n();
  const t = fullT.approvalQueue;
  const [status, setStatus] = useState<CandidateStatus>("PENDING");
  const [evidenceFilter, setEvidenceFilter] = useState<EvidenceFilter>("all");
  const [ambiguityFilter, setAmbiguityFilter] = useState<AmbiguitySelection>("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [context, setContext] = useState<ReviewContext | null>(null);

  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ReviewCandidateDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [conflictMessage, setConflictMessage] = useState<string | null>(null);

  const [decisionAction, setDecisionAction] = useState<ReviewAction | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  // Triggers returned by the server on a 422; the server is the final authority even if the detail policy was stale.
  const [serverReasonTriggers, setServerReasonTriggers] = useState<ReviewReasonTrigger[]>([]);
  const [decisionSubmitting, setDecisionSubmitting] = useState(false);
  const [revocationOpen, setRevocationOpen] = useState(false);
  const [revocationReason, setRevocationReason] = useState("");
  const [revocationSubmitting, setRevocationSubmitting] = useState(false);
  const [revocationError, setRevocationError] = useState<string | null>(null);

  const [reopenOpen, setReopenOpen] = useState(false);
  const [reopenReason, setReopenReason] = useState("");
  const [reopenSubmitting, setReopenSubmitting] = useState(false);
  const [reopenError, setReopenError] = useState<string | null>(null);

  const [gapsOpen, setGapsOpen] = useState(false);
  const [gapsSearch, setGapsSearch] = useState("");
  const [gapsLoading, setGapsLoading] = useState(false);
  const [gapsItems, setGapsItems] = useState<LecturerWithoutCandidateItem[]>([]);
  const [gapsTotal, setGapsTotal] = useState(0);


  const loadQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError(null);
    try {
      const response = await getReviewCandidates({
        status,
        evidence_category: evidenceFilter === "all" ? undefined : evidenceFilter,
        ambiguity: ambiguityFilter === "all" ? undefined : ambiguityFilter,
        q: search || undefined,
        page,
        page_size: pageSize,
      });
      setItems(response.items);
      setTotal(response.total);
    } catch (error) {
      setQueueError(getApiErrorMessage(error, t.loadQueueError));
      setItems([]);
      setTotal(0);
    } finally {
      setQueueLoading(false);
    }
  }, [ambiguityFilter, evidenceFilter, page, pageSize, search, status, t.loadQueueError]);

  // Apply the search text shortly after typing stops, always from the first page.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const loadDetail = useCallback(async (candidateId: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const response = await getReviewCandidate(candidateId);
      setDetail(response);
    } catch (error) {
      setDetail(null);
      setDetailError(getApiErrorMessage(error, t.loadDetailError));
    } finally {
      setDetailLoading(false);
    }
  }, [t.loadDetailError]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  // Which precondition of the queue is missing (decides the empty-state text).
  useEffect(() => {
    let cancelled = false;
    getReviewContext()
      .then((value) => {
        if (!cancelled) setContext(value);
      })
      .catch(() => {
        if (!cancelled) setContext(null);
      });
    return () => {
      cancelled = true;
    };
  }, [items.length, total]);

  useEffect(() => {
    if (!selectedCandidateId) return;
    void loadDetail(selectedCandidateId);
  }, [loadDetail, selectedCandidateId]);

  const openDetail = (candidateId: string) => {
    setConflictMessage(null);
    setDetail(null);
    setSelectedCandidateId(candidateId);
  };

  const closeDetail = () => {
    if (decisionSubmitting) return;
    setSelectedCandidateId(null);
    setDetail(null);
    setDetailError(null);
    setConflictMessage(null);
  };

  const closeDecision = () => {
    if (decisionSubmitting) return;
    setDecisionAction(null);
    setDecisionReason("");
    setReasonError(null);
    setServerReasonTriggers([]);
  };

  const closeRevocation = () => {
    if (revocationSubmitting) return;
    setRevocationOpen(false);
    setRevocationReason("");
    setRevocationError(null);
  };

  const submitRevocation = async () => {
    if (!detail || revocationSubmitting) return;
    const reason = revocationReason.trim();
    if (!reason) {
      setRevocationError(t.revokeReasonRequired);
      return;
    }

    setRevocationSubmitting(true);
    setRevocationError(null);
    try {
      await revokeReviewCandidate(detail.candidate_id, {
        candidate_version: detail.candidate_version,
        reason,
      });
      toast.success(t.revokeSuccessTitle, t.revokeSuccessMessage);
      setRevocationOpen(false);
      setRevocationReason("");
      await refreshQueueAndDetail();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setRevocationError(getApiErrorMessage(error, t.conflictDefault));
        if (selectedCandidateId) await loadDetail(selectedCandidateId);
      } else {
        setRevocationError(getApiErrorMessage(error, t.revokeFailedTitle));
      }
    } finally {
      setRevocationSubmitting(false);
    }
  };

  const closeReopen = () => {
    if (reopenSubmitting) return;
    setReopenOpen(false);
    setReopenReason("");
    setReopenError(null);
  };

  const submitReopen = async () => {
    if (!detail || reopenSubmitting) return;
    const reason = reopenReason.trim();
    if (!reason) {
      setReopenError(locale === "en" ? "A reason is required." : "Cần nhập lý do.");
      return;
    }
    setReopenSubmitting(true);
    setReopenError(null);
    try {
      await reopenRejectedCandidate(detail.candidate_id, {
        candidate_version: detail.candidate_version,
        reason,
      });
      toast.success(
        locale === "en" ? "Pair reopened" : "Đã mở lại cặp đề xuất",
        locale === "en" ? "Back to PENDING for a fresh review." : "Đã quay về Chờ duyệt.",
      );
      setReopenOpen(false);
      setReopenReason("");
      await refreshQueueAndDetail();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setReopenError(getApiErrorMessage(error, t.conflictDefault));
        if (selectedCandidateId) await loadDetail(selectedCandidateId);
      } else {
        setReopenError(getApiErrorMessage(error, locale === "en" ? "Could not reopen." : "Không mở lại được."));
      }
    } finally {
      setReopenSubmitting(false);
    }
  };

  const loadGaps = useCallback(async (search: string) => {
    setGapsLoading(true);
    try {
      const res = await getLecturersWithoutCandidates({ search: search || undefined, page_size: 20 });
      setGapsItems(res.items);
      setGapsTotal(res.total);
    } catch {
      setGapsItems([]);
      setGapsTotal(0);
    } finally {
      setGapsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!gapsOpen) return;
    const timer = setTimeout(() => void loadGaps(gapsSearch), 300);
    return () => clearTimeout(timer);
  }, [gapsOpen, gapsSearch, loadGaps]);

  const refreshQueueAndDetail = useCallback(async () => {
    const requests: Promise<unknown>[] = [loadQueue()];
    if (selectedCandidateId) requests.push(loadDetail(selectedCandidateId));
    await Promise.allSettled(requests);
  }, [loadDetail, loadQueue, selectedCandidateId]);

  const handleConflict = async (error: ApiError) => {
    const code = error.code ?? "";
    const message = conflictMessages(t)[code] ?? t.conflictDefault;
    setConflictMessage(message);
    toast.warning(t.conflictToastTitle, message);

    if (code === "STALE_CANDIDATE_VERSION" || code === "STALE_CANDIDATE_OBSERVATION") {
      if (selectedCandidateId) await loadDetail(selectedCandidateId);
      return;
    }
    if (code === "CANDIDATE_ALREADY_DECIDED_CONFLICT") {
      await refreshQueueAndDetail();
    }
  };

  const acceptReasonTriggers: ReviewReasonTrigger[] = Array.from(
    new Set([...(detail?.review_policy?.accept_reason_triggers ?? []), ...serverReasonTriggers]),
  );
  const acceptReasonRequired = Boolean(detail?.review_policy?.accept_reason_required) || serverReasonTriggers.length > 0;

  const submitDecision = async () => {
    if (!detail || !decisionAction || decisionSubmitting) return;

    const trimmedReason = decisionReason.trim();
    if (decisionAction === "REJECT" && !trimmedReason) {
      setReasonError(t.rejectReasonRequired);
      return;
    }
    if (decisionAction === "ACCEPT" && acceptReasonRequired && !trimmedReason) {
      setReasonError(t.acceptReasonRequired);
      return;
    }

    setDecisionSubmitting(true);
    setReasonError(null);
    setConflictMessage(null);
    try {
      if (decisionAction === "ACCEPT") {
        await decideReviewCandidate(detail.candidate_id, {
          observation_id: detail.current_observation.observation_id,
          candidate_version: detail.candidate_version,
          action: "ACCEPT",
          ...(trimmedReason ? { reason: trimmedReason } : {}),
        });
        toast.success(t.acceptSuccessTitle, t.acceptSuccessMessage);
      } else {
        await decideReviewCandidate(detail.candidate_id, {
          observation_id: detail.current_observation.observation_id,
          candidate_version: detail.candidate_version,
          action: "REJECT",
          reason: trimmedReason,
        });
        toast.success(t.rejectSuccessTitle, t.rejectSuccessMessage);
      }
      setDecisionAction(null);
      setDecisionReason("");
      setServerReasonTriggers([]);
      await refreshQueueAndDetail();
    } catch (error) {
      if (error instanceof ApiError && error.status === 422 && error.code === "REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE") {
        // Keep the modal open with the reviewer's input and show which conditions the server applied.
        const body = error.body as { reason_triggers?: ReviewReasonTrigger[] } | null;
        setServerReasonTriggers(Array.isArray(body?.reason_triggers) ? body.reason_triggers : []);
        setReasonError(t.acceptReasonRequired);
      } else if (error instanceof ApiError && error.status === 422 && error.code === "INVALID_REVIEW_REASON") {
        setReasonError(decisionAction === "REJECT" ? t.rejectReasonRequired : t.acceptReasonRequired);
      } else if (error instanceof ApiError && error.status === 409) {
        setDecisionAction(null);
        await handleConflict(error);
      } else {
        const message = getApiErrorMessage(error, t.saveDecisionError);
        toast.error(t.saveDecisionFailedTitle, message);
      }
    } finally {
      setDecisionSubmitting(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <ConfigProvider theme={ANTD_THEME}>
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* ── Page Header ──────────────────────────────────────────────────── */}
      <div className="space-y-3">
        <div>
          <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">{t.title}</h1>
          <p className="mt-0.5 text-xs text-slate-500 sm:text-sm">
            {t.subtitle}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-3">
          {/* No "Tổng số" here: the table footer already reads "Hiển thị X trong Y cặp đề xuất". */}
          <div className="flex flex-wrap items-center justify-end gap-3">
          {(user?.role === "ADMIN" || user?.role === "REVIEWER") && (
            <UiButton
              variant="secondary"
              size="md"
              onClick={() => setGapsOpen(true)}
            >
              <span className="truncate">{locale === "en" ? "Lecturers the system missed" : "Giảng viên bị hệ thống bỏ sót"}</span>
            </UiButton>
          )}
          </div>
        </div>
      </div>

      <FullModal
        open={gapsOpen}
        title={locale === "en" ? "Lecturers the system missed" : "Giảng viên bị hệ thống bỏ sót"}
        description={
          locale === "en"
            ? "The system has never proposed a Scopus account for these lecturers (not even one that was later rejected). If you find their Scopus ID yourself, add it from their profile in \"Hồ sơ giảng viên\"."
            : "Hệ thống chưa từng đề xuất tài khoản Scopus nào cho các giảng viên này (kể cả đề xuất đã bị từ chối). Nếu bạn tự tìm được Scopus ID của họ, vào \"Hồ sơ giảng viên\" của người đó để gán trực tiếp."
        }
        onClose={() => setGapsOpen(false)}
        footerStart={
          <>
            {locale === "en" ? "Total" : "Tổng"}: <strong className="text-slate-700">{gapsTotal}</strong>
          </>
        }
        footerActions={
          <UiButton variant="secondary" onClick={() => setGapsOpen(false)}>
            {locale === "en" ? "Close" : "Đóng"}
          </UiButton>
        }
      >
        <div className="space-y-3">
          <Input
            value={gapsSearch}
            onChange={(e) => setGapsSearch(e.target.value)}
            placeholder={locale === "en" ? "Search by name, email or staff code…" : "Tìm theo tên, email hoặc mã cán bộ…"}
            allowClear
          />
          <div className="rounded-[5px] border border-slate-200">
            {gapsLoading ? (
              <div className="flex items-center justify-center gap-2 py-12 text-sm font-medium text-slate-400">
                <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                <span>{locale === "en" ? "Loading data..." : "Đang tải dữ liệu..."}</span>
              </div>
            ) : gapsItems.length === 0 ? (
              <Empty
                description={locale === "en" ? "No gaps found" : "Không có giảng viên nào bị bỏ sót"}
                className="py-8"
              />
            ) : (
              <ul className="divide-y divide-slate-100">
                {gapsItems.map((lec) => (
                  <li key={lec.id} className="px-3 py-2.5">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-slate-800">{lec.full_name}</div>
                      <div className="truncate text-sm text-slate-500">
                        {[lec.staff_code, lec.department, lec.email].filter(Boolean).join(" · ") || "—"}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </FullModal>

      {/* ── Filter Bar ──────────────────────────────────────────────────── */}
      <div className="rounded-[5px] border border-slate-200/80 bg-white p-3.5 shadow-xs">
        <div className="flex flex-wrap items-end gap-3">
          {/* Tìm kiếm */}
          <div className="flex min-w-[220px] flex-1 flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600" htmlFor="review-queue-search">
              {locale === "en" ? "Search" : "Tìm kiếm"}
            </label>
            <div className="relative">
              <svg className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                id="review-queue-search"
                type="text"
                value={searchInput}
                maxLength={120}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder={
                  locale === "en"
                    ? "Lecturer name or e-mail, Scopus name or ID…"
                    : "Tên hoặc email giảng viên, tên hoặc ID tác giả Scopus…"
                }
                className="h-8 w-full rounded-[5px] border border-slate-200 bg-white pl-8 pr-2.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                data-testid="review-queue-search"
              />
            </div>
          </div>

          {/* Trạng thái */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">{t.statusLabel}</label>
            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value as CandidateStatus); setPage(1); }}
              className="h-8 rounded-[5px] border border-slate-200 bg-white px-2.5 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
            >
              {Object.entries(statusLabels(t)).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          {/* Loại bằng chứng */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">{t.evidenceTypeLabel}</label>
            <select
              value={evidenceFilter}
              onChange={(e) => { setEvidenceFilter(e.target.value as EvidenceFilter); setPage(1); }}
              className="h-8 rounded-[5px] border border-slate-200 bg-white px-2.5 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
            >
              <option value="all">{t.evidenceTypeAll}</option>
              <option value="publication-supported">{t.evidenceTypePublicationSupported}</option>
              <option value="name-only">{t.evidenceTypeNameOnly}</option>
            </select>
          </div>

          {/* Đề xuất khác */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">{t.ambiguityLabel}</label>
            <select
              value={ambiguityFilter}
              onChange={(e) => { setAmbiguityFilter(e.target.value as AmbiguitySelection); setPage(1); }}
              className="h-8 rounded-[5px] border border-slate-200 bg-white px-2.5 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
            >
              <option value="all">{t.ambiguityAll}</option>
              <option value="ambiguous">{t.ambiguityAmbiguous}</option>
              <option value="unique">{t.ambiguityUnique}</option>
            </select>
          </div>

          {/* Refresh button */}
          <button
            type="button"
            onClick={() => void loadQueue()}
            disabled={queueLoading}
            className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-[5px] border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 shadow-2xs transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-60 ml-auto"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {t.refresh}
          </button>
        </div>
      </div>

      {/* ── Queue Table ─────────────────────────────────────────────────── */}
      <section className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
        {queueError ? (
          <div className="rounded-[5px] border border-rose-200 bg-rose-50 m-4 p-4 text-xs text-rose-800 flex items-start gap-2.5">
            <svg className="h-5 w-5 shrink-0 text-rose-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="flex flex-col gap-1.5">
              <span className="font-semibold">{t.cannotLoadQueueTitle}</span>
              <span>{queueError}</span>
              <button
                type="button"
                onClick={() => void loadQueue()}
                className="self-start rounded-[5px] border border-rose-300 bg-white px-3 py-1 text-xs font-bold text-rose-700 hover:bg-rose-100 transition-colors cursor-pointer"
              >
                {t.retry}
              </button>
            </div>
          </div>
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
                <tr>
                  <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{t.colLecturer}</th>
                  <th className="border-r border-slate-200/80 px-2.5 py-3.5 font-medium text-slate-700 whitespace-nowrap">{t.colScopusAuthor}</th>
                  <th className="border-r border-slate-200/80 px-2.5 py-3.5 text-center font-medium text-slate-700 whitespace-nowrap">{t.colStatus}</th>
                  <th className="border-r border-slate-200/80 px-2.5 py-3.5 text-center font-medium text-slate-700 whitespace-nowrap">{t.colEvidence}</th>
                  <th className="border-r border-slate-200/80 px-2.5 py-3.5 text-center font-medium text-slate-700 whitespace-nowrap">
                    {locale === "en" ? "Degree of fit" : "Mức phù hợp"}
                  </th>
                  <th className="border-r border-slate-200/80 px-2.5 py-3.5 text-center font-medium text-slate-700 whitespace-nowrap">{t.colAmbiguityContext}</th>
                  <th className="sticky right-0 z-[1] w-44 whitespace-nowrap border-l border-slate-200/80 bg-slate-50 px-2.5 py-3.5 text-center font-medium text-slate-700">{t.colActions}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {queueLoading ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      <div className="flex items-center justify-center gap-2">
                        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                        <span className="text-xs font-medium">{t.loadingQueue}</span>
                      </div>
                    </td>
                  </tr>
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center justify-center gap-1.5">
                        <div className="flex h-10 w-10 items-center justify-center rounded-[5px] bg-slate-100/80 border border-slate-200/80 text-slate-400 mb-1">
                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <span className="text-sm font-bold text-slate-700">{emptyQueueCopy(t, locale, context).title}</span>
                        <span className="max-w-xl text-xs leading-relaxed text-slate-500" data-testid="review-empty-detail">
                          {emptyQueueCopy(t, locale, context).text}
                        </span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  items.map((item) => (
                    <tr
                      key={item.candidate_id}
                      className="hover:bg-slate-50/50 transition-colors cursor-default"
                      onDoubleClick={() => openDetail(item.candidate_id)}
                    >
                      <td className="border-r border-b border-slate-100 px-2.5 py-3.5 align-middle whitespace-nowrap">
                        <span className="font-medium text-slate-800">{item.lecturer.full_name}</span>
                      </td>
                      <td className="border-r border-b border-slate-100 px-2.5 py-3.5 align-middle">
                        <div className="font-medium text-slate-900">{item.scopus_author.preferred_name}</div>
                        <div className="mt-0.5 font-mono text-sm font-medium text-slate-400">{item.scopus_author.scopus_id}</div>
                      </td>
                      <td className="border-r border-b border-slate-100 px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                        <span className={nhanBadgeClass(CANDIDATE_STATUS_TONE[item.candidate_status])}>
                          {statusLabels(t)[item.candidate_status]}
                        </span>
                      </td>
                      <td className="border-r border-b border-slate-100 px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                        {item.publication_support_count > 0 && item.name_evidence_count === 0 ? (
                          <span className={nhanBadgeClass("violet")} title={t.craweOnlyBadgeTooltip}>
                            {t.craweOnlyBadge}
                          </span>
                        ) : item.publication_support_count > 0 ? (
                          <span className={nhanBadgeClass("info")}>
                            {t.publicationSupportedBadge}
                          </span>
                        ) : (
                          <span className={nhanBadgeClass("neutral")}>
                            {t.nameOnlyBadge}
                          </span>
                        )}
                      </td>
                      <td className="border-r border-b border-slate-100 px-2.5 py-3.5 text-center align-middle">
                        {item.fit ? <FitBadge fit={item.fit} locale={locale === "en" ? "en" : "vi"} /> : <span className="text-slate-300">—</span>}
                      </td>
                      <td className="border-r border-b border-slate-100 px-2.5 py-3.5 align-middle">
                        <div className="flex flex-col items-center gap-1">
                          <span className={nhanBadgeClass(item.is_ambiguous ? "warning" : "neutral")}>
                            {ambiguityText(t, item.candidate_count_for_lecturer)}
                          </span>
                          {item.is_shared_scopus_author && (
                            <span
                              className={nhanBadgeClass("danger")}
                              data-testid="shared-author-tag"
                              title={sharedAuthorText(t, item.candidate_count_for_scopus_author)}
                            >
                              {format(t.sharedBadge, { count: item.candidate_count_for_scopus_author ?? "?" })}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="sticky right-0 z-[1] border-l border-b border-slate-100 bg-white px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => openDetail(item.candidate_id)}
                          className="inline-flex h-badge w-32 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-slate-700 transition-colors hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900 cursor-pointer"
                        >
                          <span>{t.viewDetail}</span>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer: record count + page size + pagination */}
        {!queueError && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-sm text-slate-500">
            <div className="flex items-center gap-3">
              <span>{format(t.showingOf, { shown: items.length, total })}</span>
              <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
                <span className="text-slate-500">{t.perPageLabel}</span>
                <select
                  value={pageSize}
                  disabled={queueLoading}
                  onChange={(e) => { setPage(1); setPageSize(Number(e.target.value)); }}
                  className="h-7 rounded-[5px] border border-slate-200 bg-white px-1.5 text-sm font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer disabled:opacity-50"
                >
                  <option value={10}>{t.perPageOption(10)}</option>
                  <option value={20}>{t.perPageOption(20)}</option>
                  <option value={50}>{t.perPageOption(50)}</option>
                  <option value={100}>{t.perPageOption(100)}</option>
                </select>
              </div>
            </div>
            <nav aria-label={t.paginationLabel} className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || queueLoading}
                className="rounded-[5px] border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 transition-all duration-150 active:scale-[0.97] hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
              >
                {t.previousPage}
              </button>
              <span aria-live="polite" className="min-w-[72px] text-center font-medium text-slate-600">
                {format(t.pageOf, { page, total: totalPages })}
              </span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || queueLoading}
                className="rounded-[5px] border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 transition-all duration-150 active:scale-[0.97] hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
              >
                {t.nextPage}
              </button>
            </nav>
          </div>
        )}
      </section>

      {selectedCandidateId !== null && (
        <ModalPortal>
          <div
            className="fixed inset-x-0 top-16 bottom-0 md:left-[var(--app-sidebar-w)] z-50 flex items-center justify-center overflow-hidden bg-black/60 p-4 modal-backdrop-in transition-[left] duration-200 ease-out"
            onClick={() => {
              if (!decisionSubmitting) closeDetail();
            }}
          >
            <section
              role="dialog"
              aria-modal="true"
              aria-labelledby="review-detail-modal-title"
              className="flex h-full w-full max-w-none flex-col overflow-hidden rounded-card border border-blue-200 bg-white shadow-2xl modal-panel-in"
              onClick={(event) => event.stopPropagation()}
            >
              <header className="flex shrink-0 items-center justify-between border-b border-blue-100 bg-blue-50 px-5 py-4">
                <div className="min-w-0">
                  <h2 id="review-detail-modal-title" className="text-base font-bold text-[#2f4ea6] sm:text-lg">
                    {t.detailModalTitle}
                  </h2>
                  <p className="mt-0.5 text-sm text-[#3A5FC3]">
                    {locale === "en"
                      ? "Compare the lecturer with the Scopus account, then accept or reject the pair."
                      : "Đối chiếu thông tin giảng viên với tài khoản Scopus, rồi chấp nhận hoặc từ chối cặp này."}
                  </p>
                </div>
              </header>
              <div className="min-h-0 flex-1 overflow-hidden px-5 py-4">
        {detailLoading ? (
          <div className="flex min-h-40 items-center justify-center py-12">
            <div className="flex items-center justify-center gap-2 text-sm font-medium text-slate-400">
              <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
              <span>{locale === "en" ? "Loading data..." : "Đang tải dữ liệu..."}</span>
            </div>
          </div>
        ) : detailError ? (
          <Alert
            showIcon
            type="error"
            message={t.cannotLoadDetailTitle}
            description={
              <Space direction="vertical">
                <span>{detailError}</span>
                <Button size="small" onClick={() => selectedCandidateId && void loadDetail(selectedCandidateId)}>{t.detailRetry}</Button>
              </Space>
            }
          />
        ) : detail ? (
          <div className="flex h-full min-h-0 flex-col">
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-1 pb-2 pt-1">
            {conflictMessage && (
              <Alert showIcon closable type="warning" message={t.conflictAlertTitle} description={conflictMessage} onClose={() => setConflictMessage(null)} />
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              <DetailSection title={t.sectionLecturer}>
                <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2.5 text-sm">
                  <dt className="text-slate-500">{t.fieldFullName}</dt>
                  <dd className="font-semibold text-slate-900">{detail.lecturer.full_name}</dd>
                  <dt className="text-slate-500">{t.fieldAcademicDegree}</dt>
                  <dd className="text-slate-800">{displayValue(t, detail.lecturer.academic_degree)}</dd>
                  <dt className="text-slate-500">{t.fieldAcademicRank}</dt>
                  <dd className="text-slate-800">{displayValue(t, detail.lecturer.academic_rank)}</dd>
                  <dt className="text-slate-500">{t.fieldSourceProfile}</dt>
                  <dd>
                    {detail.lecturer.repository_profile_url ? (
                      <a href={detail.lecturer.repository_profile_url} target="_blank" rel="noreferrer" className="font-medium text-[#3A5FC3] hover:underline">
                        {t.openIctuProfile}
                      </a>
                    ) : <span className="text-slate-800">{t.noData}</span>}
                  </dd>
                </dl>
              </DetailSection>

              <DetailSection title={t.sectionScopusAuthor}>
                <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2.5 text-sm">
                  <dt className="text-slate-500">{t.fieldPreferredName}</dt>
                  <dd className="font-semibold text-slate-900">{detail.scopus_author.preferred_name}</dd>
                  <dt className="text-slate-500">{t.fieldScopusId}</dt>
                  <dd className="font-mono font-medium text-slate-700">{detail.scopus_author.scopus_id}</dd>
                  <dt className="text-slate-500">{t.fieldNameVariants}</dt>
                  <dd>
                    {detail.scopus_author.name_variants.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {detail.scopus_author.name_variants.map((variant) => (
                          <Badge key={variant} tone="neutral" className="!rounded-[5px]">{variant}</Badge>
                        ))}
                      </div>
                    ) : <span className="text-slate-800">{t.noNameVariants}</span>}
                  </dd>
                </dl>
              </DetailSection>
            </div>

            {detail.fit && (
              <DetailSection
                testId="fit-section"
                title={locale === "en" ? "Degree of fit and its grounds" : "Mức độ phù hợp và căn cứ"}
                extra={<FitBadge fit={detail.fit} locale={locale === "en" ? "en" : "vi"} />}
              >
                <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-700">
                  {detail.fit.reasons.map((code) => (
                    <li key={code}>{fitReasonText(code, locale === "en" ? "en" : "vi", detail.fit?.ictu_affiliation_papers ?? 0)}</li>
                  ))}
                </ul>
                <p className="mt-3 text-sm text-slate-500">
                  {locale === "en"
                    ? `"${fitLevelLabel(detail.fit.level, "en")}" is only a hint for the reviewer — not a probability, and it confirms nothing. The decision stays with you.`
                    : `"${fitLevelLabel(detail.fit.level, "vi")}" chỉ là gợi ý cho người duyệt — không phải xác suất và không tự xác nhận. Quyết định vẫn thuộc về bạn.`}
                </p>
              </DetailSection>
            )}

            <DetailSection title={t.sectionNameEvidence} count={detail.name_evidence.length}>
              {detail.name_evidence.length > 0 ? (
                <div className="space-y-3">{detail.name_evidence.map((evidence) => <NameEvidenceCard key={evidence.evidence_id} t={t} locale={locale} evidence={evidence} />)}</div>
              ) : detail.publication_evidence.length > 0 ? (
                <Notice tone="warning" title={t.nameMismatchWarningTitle}>{t.nameMismatchWarningDescription}</Notice>
              ) : (
                <p className="py-2 text-sm text-slate-500">{t.noNameEvidence}</p>
              )}
            </DetailSection>

            <DetailSection title={t.sectionPublicationEvidence} count={detail.publication_evidence.length}>
              {detail.publication_evidence.length > 0 ? (
                <div className="space-y-3">
                  {detail.publication_evidence.map((evidence) => (
                    <div key={evidence.evidence_id} className="rounded-[5px] border border-slate-200 bg-slate-50/60 p-4">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <Badge tone={evidence.reconciliation === "DOI_EXACT" ? "success" : "brand"} className="!rounded-[5px]" title={evidence.reconciliation ?? undefined}>
                          {reconciliationLabel(evidence.reconciliation, locale, t.reconciliationUnknown)}
                        </Badge>
                        <span className="text-sm text-slate-500" title={evidence.rule_id}>{ruleLabel(evidence.rule_id, locale)}</span>
                      </div>
                      <div className="text-[15px] font-semibold leading-snug text-slate-900">{displayValue(t, evidence.title)}</div>
                      <div className="mt-2 grid gap-2 text-sm md:grid-cols-2">
                        <div>
                          <span className="text-slate-500">{t.doiLabel}: </span>
                          {evidence.doi ? (
                            <a href={`https://doi.org/${evidence.doi}`} target="_blank" rel="noopener noreferrer" className="font-medium text-[#3A5FC3] hover:underline">
                              {evidence.doi}
                            </a>
                          ) : <span className="text-slate-800">{t.noData}</span>}
                        </div>
                        <div>
                          <span className="text-slate-500">{t.eidLabel}: </span>
                          <span className="font-medium text-slate-800">{displayValue(t, evidence.eid)}</span>
                        </div>
                      </div>
                      <TechnicalSources t={t} locale={locale} refs={evidence.source_refs} keyPrefix={evidence.evidence_id} />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-2 text-sm text-slate-500">{t.noPublicationEvidence}</p>
              )}
            </DetailSection>

            <DetailSection title={t.sectionAmbiguityContext}>
              <div className="space-y-3">
                <Notice tone={detail.ambiguity.is_ambiguous ? "warning" : "info"} title={ambiguityText(t, detail.ambiguity.candidate_count_for_lecturer)}>
                  {detail.ambiguity.other_candidates.length > 0 ? t.ambiguityOtherListed : t.ambiguityNoOthers}
                </Notice>
                {detail.ambiguity.is_shared_scopus_author && (
                  <Notice tone="danger" title={sharedAuthorText(t, detail.ambiguity.candidate_count_for_scopus_author)}>
                    {t.ambiguitySharedWarning}
                  </Notice>
                )}
                {detail.ambiguity.other_candidates.map((candidate) => (
                  <div key={candidate.candidate_id} className="flex flex-wrap items-center justify-between gap-2 rounded-[5px] border border-slate-200 px-4 py-3">
                    <div className="text-sm">
                      <div className="font-semibold text-slate-900">{candidate.scopus_author.preferred_name}</div>
                      <div className="font-mono text-slate-500">{candidate.scopus_author.scopus_id}</div>
                    </div>
                    <span className={nhanBadgeClass(CANDIDATE_STATUS_TONE[candidate.candidate_status])}>
                      {statusLabels(t)[candidate.candidate_status]}
                    </span>
                  </div>
                ))}
              </div>
            </DetailSection>

            {detail.candidate_status === "ACCEPTED" && (
              <PrimaryIdPanel lecturerId={detail.lecturer.id} locale={locale === "en" ? "en" : "vi"} />
            )}

          </div>
          <footer className="shrink-0 border-t border-slate-100 bg-white px-5 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm text-slate-500">
                {t.currentStatusLabel}: <span className="font-medium text-slate-700">{statusLabels(t)[detail.candidate_status]}</span>
              </div>
              {/* One right-aligned group: main action(s) first, "Đóng" always last. */}
              <div className="flex flex-wrap items-center justify-end gap-2">
                {detail.candidate_status === "PENDING" && (
                  <>
                    <UiButton variant="primary" onClick={() => setDecisionAction("ACCEPT")}>
                      {t.acceptAction}
                    </UiButton>
                    <UiButton variant="danger" onClick={() => setDecisionAction("REJECT")}>
                      {t.rejectAction}
                    </UiButton>
                  </>
                )}
                {user?.role === "ADMIN" && detail.candidate_status === "ACCEPTED" && (
                  <UiButton
                    variant="danger"
                    onClick={() => {
                      setRevocationError(null);
                      setRevocationOpen(true);
                    }}
                  >
                    {t.revokeAction}
                  </UiButton>
                )}
                {detail.candidate_status === "REJECTED" && (
                  <UiButton
                    variant="primary"
                    onClick={() => {
                      setReopenError(null);
                      setReopenOpen(true);
                    }}
                  >
                    {locale === "en" ? "Reopen" : "Mở lại"}
                  </UiButton>
                )}
                <UiButton variant="secondary" onClick={closeDetail} disabled={decisionSubmitting}>
                  {locale === "en" ? "Close" : "Đóng"}
                </UiButton>
              </div>
          </div>
          </footer>
          </div>
        ) : <Empty description={t.noDetailData} className="py-10" />}
              </div>
            </section>
          </div>
        </ModalPortal>
      )}

      <ConfirmModal
        open={reopenOpen && detail !== null}
        variant="primary"
        title={locale === "en" ? "Reopen rejected pair" : "Mở lại cặp đề xuất đã từ chối"}
        confirmLabel={locale === "en" ? "Reopen (Pending)" : "Mở lại (Chờ duyệt)"}
        cancelLabel={t.cancel}
        loading={reopenSubmitting}
        confirmDisabled={reopenReason.trim().length === 0}
        onConfirm={() => void submitReopen()}
        onCancel={closeReopen}
        description={
          detail && (
            <div className="space-y-3">
              <Notice
                tone="info"
                title={
                  locale === "en"
                    ? "The pair goes back to pending for a fresh review. Nothing is accepted automatically."
                    : "Cặp đề xuất sẽ quay về trạng thái Chờ duyệt. Không có gì được tự động chấp nhận."
                }
              />
              <PairSummary t={t} detail={detail} />
              <div>
                <label htmlFor="review-reopen-reason" className="mb-1.5 block text-sm font-medium text-slate-700">
                  {locale === "en" ? "Reason" : "Lý do"} <span className="text-rose-600">*</span>
                </label>
                <Input.TextArea
                  id="review-reopen-reason"
                  value={reopenReason}
                  onChange={(e) => setReopenReason(e.target.value)}
                  rows={3}
                  placeholder={locale === "en" ? "e.g. rejected by mistake" : "VD: từ chối nhầm"}
                />
              </div>
              {reopenError && <Notice tone="danger" title={reopenError} />}
            </div>
          )
        }
      />

      <ConfirmModal
        open={revocationOpen && detail !== null}
        variant="danger"
        title={t.revokeModalTitle}
        confirmLabel={t.confirmRevokeOk}
        cancelLabel={t.cancel}
        loading={revocationSubmitting}
        confirmDisabled={revocationReason.trim().length === 0}
        onConfirm={() => void submitRevocation()}
        onCancel={closeRevocation}
        description={
          detail && (
            <div className="space-y-3">
              <Notice tone="warning" title={t.revokeModalText} />
              <PairSummary t={t} detail={detail} />
              <div>
                <label htmlFor="review-revoke-reason" className="mb-1.5 block text-sm font-medium text-slate-700">
                  {t.revokeReasonLabel} <span className="text-rose-600">*</span>
                </label>
                <Input.TextArea
                  id="review-revoke-reason"
                  value={revocationReason}
                  rows={4}
                  maxLength={4000}
                  showCount
                  status={revocationError ? "error" : undefined}
                  placeholder={t.revokeReasonPlaceholder}
                  onChange={(event) => {
                    setRevocationReason(event.target.value);
                    if (event.target.value.trim()) setRevocationError(null);
                  }}
                />
                {revocationError && <div className="mt-6 text-sm text-rose-600" role="alert">{revocationError}</div>}
              </div>
            </div>
          )
        }
      />

      <ConfirmModal
        open={decisionAction === "ACCEPT" && detail !== null}
        variant="primary"
        title={t.confirmAcceptTitle}
        confirmLabel={t.confirmAcceptOk}
        cancelLabel={t.cancel}
        loading={decisionSubmitting}
        confirmDisabled={acceptReasonRequired && decisionReason.trim().length === 0}
        onConfirm={() => void submitDecision()}
        onCancel={closeDecision}
        description={
          detail && (
            <div className="space-y-3">
              <PairSummary t={t} detail={detail} />
              {acceptReasonRequired && (
                <div data-testid="accept-reason-required">
                  <Notice tone="warning" title={t.acceptReasonRequiredTitle}>
                    <ul className="m-0 list-disc space-y-0.5 pl-4">
                      {acceptReasonTriggers.map((trigger) => (
                        <li key={trigger}>{reasonTriggerText(t, trigger)}</li>
                      ))}
                    </ul>
                  </Notice>
                </div>
              )}
              <div>
                <label htmlFor="review-accept-reason" className="mb-1.5 block text-sm font-medium text-slate-700">
                  {acceptReasonRequired ? (
                    <>
                      {t.acceptReasonLabel} <span className="text-rose-600">*</span>
                    </>
                  ) : (
                    t.acceptReasonOptionalLabel
                  )}
                </label>
                <Input.TextArea
                  id="review-accept-reason"
                  value={decisionReason}
                  rows={3}
                  maxLength={4000}
                  showCount
                  aria-required={acceptReasonRequired}
                  aria-invalid={Boolean(reasonError)}
                  status={reasonError ? "error" : undefined}
                  placeholder={t.acceptReasonPlaceholder}
                  onChange={(event) => {
                    setDecisionReason(event.target.value);
                    if (event.target.value.trim()) setReasonError(null);
                  }}
                />
                {reasonError && <div className="mt-6 text-sm text-rose-600" role="alert">{reasonError}</div>}
                <p className="mt-6 text-xs leading-relaxed text-slate-500">{t.acceptReasonNotEvidence}</p>
              </div>
            </div>
          )
        }
      />

      <ConfirmModal
        open={decisionAction === "REJECT" && detail !== null}
        variant="danger"
        title={t.rejectModalTitle}
        confirmLabel={t.confirmRejectOk}
        cancelLabel={t.cancel}
        loading={decisionSubmitting}
        confirmDisabled={decisionReason.trim().length === 0}
        onConfirm={() => void submitDecision()}
        onCancel={closeDecision}
        description={
          detail && (
            <div className="space-y-3">
              <PairSummary t={t} detail={detail} />
              <div>
                <label htmlFor="review-reject-reason" className="mb-1.5 block text-sm font-medium text-slate-700">
                  {t.rejectReasonLabel} <span className="text-rose-600">*</span>
                </label>
                <Input.TextArea
                  id="review-reject-reason"
                  value={decisionReason}
                  rows={4}
                  maxLength={4000}
                  showCount
                  status={reasonError ? "error" : undefined}
                  placeholder={t.rejectReasonPlaceholder}
                  onChange={(event) => {
                    setDecisionReason(event.target.value);
                    if (event.target.value.trim()) setReasonError(null);
                  }}
                />
                {reasonError && <div className="mt-6 text-sm text-rose-600" role="alert">{reasonError}</div>}
              </div>
            </div>
          )
        }
      />
    </div>
    </ConfigProvider>
  );
}
