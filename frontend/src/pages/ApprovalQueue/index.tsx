import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Descriptions,
  Divider,
  Empty,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Typography,
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
import { createManualCandidate, generateCandidates } from "../../api/matching";
import { getLecturers } from "../../api/lecturers";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { useToast } from "../../contexts/ToastContext";
import { useAuth } from "../../contexts/AuthContext";
import { useI18n } from "../../i18n/I18nContext";
import Badge, { type BadgeTone } from "../../components/ui/Badge";
import UiButton from "../../components/ui/Button";
import FitBadge, { fitLevelLabel, fitReasonText } from "./FitBadge";
import GroupReviewPanel from "./GroupReviewPanel";
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
  return `inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border bg-white px-2.5 text-center text-xs font-bold leading-none ${NHAN_TONE_STYLE[tone]}`;
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

const { Text } = Typography;

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

function NameEvidenceCard({ t, locale, evidence }: { t: T; locale: "vi" | "en"; evidence: ReviewNameEvidence }) {
  return (
    <div className="rounded-[5px] border border-slate-200 bg-slate-50/70 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-slate-800" title={evidence.rule_id} data-testid="name-rule-label">
          {ruleLabel(evidence.rule_id, locale)}
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <Text type="secondary">{t.lecturerProfileNameLabel}</Text>
          <div className="font-medium text-slate-900">
            {displayValue(t, evidence.lecturer_source_value)}
          </div>
          {evidence.lecturer_comparison_value && (
            <div className="mt-1 text-xs text-slate-500">
              {t.comparisonValueLabel}: {evidence.lecturer_comparison_value}
            </div>
          )}
        </div>
        <div>
          <Text type="secondary">{t.scopusNameLabel}</Text>
          <div className="font-medium text-slate-900">
            {displayValue(t, evidence.scopus_surface_value)}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {evidence.scopus_surface_type && `${t.typeLabel}: ${surfaceLabel(evidence.scopus_surface_type, locale)}`}
            {evidence.scopus_comparison_value &&
              `${evidence.scopus_surface_type ? " · " : ""}${t.comparisonValueLabel}: ${evidence.scopus_comparison_value}`}
          </div>
        </div>
      </div>
      {evidence.source_refs.length > 0 && (
        <div className="mt-3 border-t border-slate-200 pt-3 text-xs text-slate-500">
          <span className="font-semibold text-slate-600">{t.sourceLabel}: </span>
          {evidence.source_refs.map((ref, index) => (
            <span key={`${evidence.evidence_id}-source-${index}`}>
              {index > 0 && " | "}
              {provenanceText(t, ref)}
            </span>
          ))}
        </div>
      )}
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

  const [generateConfirmOpen, setGenerateConfirmOpen] = useState(false);
  const [generating, setGenerating] = useState(false);

  const [manualOpen, setManualOpen] = useState(false);
  const [manualLecturerQuery, setManualLecturerQuery] = useState("");
  const [manualLecturerOptions, setManualLecturerOptions] = useState<
    { value: string; label: string }[]
  >([]);
  const [manualLecturerSearching, setManualLecturerSearching] = useState(false);
  const [manualLecturerId, setManualLecturerId] = useState<string | null>(null);
  const [manualScopusId, setManualScopusId] = useState("");
  const [manualNote, setManualNote] = useState("");
  const [manualSubmitting, setManualSubmitting] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);

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

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setGenerateConfirmOpen(false);
    try {
      const result = await generateCandidates();
      const msg = format(t.generateSuccessMessage, { count: String(result.candidate_roots) });
      toast.success(t.generateSuccessTitle, msg);
      await loadQueue();
    } catch (error) {
      toast.error(t.generateErrorTitle, getApiErrorMessage(error, t.generateErrorTitle));
    } finally {
      setGenerating(false);
    }
  }, [loadQueue, t, toast]);

  useEffect(() => {
    if (!manualOpen) return;
    const q = manualLecturerQuery.trim();
    if (q.length < 2) {
      setManualLecturerOptions([]);
      return;
    }
    let cancelled = false;
    setManualLecturerSearching(true);
    const timer = setTimeout(() => {
      getLecturers({ search: q, page_size: 20 })
        .then((res) => {
          if (cancelled) return;
          setManualLecturerOptions(
            res.items.map((it) => ({
              value: it.id,
              label: `${it.full_name}${it.staff_code ? ` (${it.staff_code})` : ""}`,
            })),
          );
        })
        .catch(() => {
          if (!cancelled) setManualLecturerOptions([]);
        })
        .finally(() => {
          if (!cancelled) setManualLecturerSearching(false);
        });
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [manualLecturerQuery, manualOpen]);

  const closeManual = () => {
    if (manualSubmitting) return;
    setManualOpen(false);
    setManualLecturerQuery("");
    setManualLecturerOptions([]);
    setManualLecturerId(null);
    setManualScopusId("");
    setManualNote("");
    setManualError(null);
  };

  const openManualFor = (lecturer: LecturerWithoutCandidateItem) => {
    setGapsOpen(false);
    setManualLecturerOptions([
      { value: lecturer.id, label: `${lecturer.full_name}${lecturer.staff_code ? ` (${lecturer.staff_code})` : ""}` },
    ]);
    setManualLecturerId(lecturer.id);
    setManualLecturerQuery(lecturer.full_name);
    setManualScopusId("");
    setManualNote("");
    setManualError(null);
    setManualOpen(true);
  };

  const submitManualCandidate = async () => {
    if (manualSubmitting) return;
    if (!manualLecturerId) {
      setManualError(locale === "en" ? "Pick a lecturer first." : "Cần chọn giảng viên.");
      return;
    }
    const scopusId = manualScopusId.trim();
    if (!scopusId) {
      setManualError(locale === "en" ? "Enter a Scopus ID." : "Cần nhập Scopus ID.");
      return;
    }
    const note = manualNote.trim();
    if (!note) {
      setManualError(
        locale === "en" ? "Enter a reason/evidence note." : "Cần ghi lý do/căn cứ.",
      );
      return;
    }
    setManualSubmitting(true);
    setManualError(null);
    try {
      await createManualCandidate({ lecturer_id: manualLecturerId, scopus_id: scopusId, note });
      toast.success(
        locale === "en" ? "Candidate added" : "Đã thêm ứng viên",
        locale === "en"
          ? "A PENDING candidate was created. Review it like any other."
          : "Đã tạo 1 ứng viên Chờ duyệt. Duyệt như bình thường.",
      );
      closeManual();
      await loadQueue();
    } catch (error) {
      setManualError(getApiErrorMessage(error, locale === "en" ? "Could not add candidate." : "Không thêm được ứng viên."));
    } finally {
      setManualSubmitting(false);
    }
  };

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
        locale === "en" ? "Candidate reopened" : "Đã mở lại ứng viên",
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
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">{t.title}</h1>
          <p className="mt-0.5 text-xs text-slate-500 sm:text-sm">
            {t.subtitle}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs text-slate-500">
            {t.totalLabel}: <span className="font-semibold text-slate-800">{total}</span>
          </div>
          {(user?.role === "ADMIN" || user?.role === "REVIEWER") && (
            <UiButton
              variant="secondary"
              size="md"
              onClick={() => setGapsOpen(true)}
              icon={
                <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              }
            >
              <span className="truncate">{locale === "en" ? "Lecturers without candidates" : "Giảng viên chưa có ứng viên"}</span>
            </UiButton>
          )}
          {user?.role === "ADMIN" && (
            <UiButton
              variant="secondary"
              size="md"
              onClick={() => setManualOpen(true)}
              icon={
                <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              }
            >
              <span className="truncate">{locale === "en" ? "Add pair manually" : "Thêm cặp thủ công"}</span>
            </UiButton>
          )}
          {user?.role === "ADMIN" && (
            <UiButton
              variant="primary"
              size="md"
              loading={generating}
              onClick={() => setGenerateConfirmOpen(true)}
              icon={
                <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M12 4v16m8-8H4" />
                </svg>
              }
            >
              <span className="truncate">{t.generateBtn}</span>
            </UiButton>
          )}
        </div>
      </div>

      <Modal
        open={gapsOpen}
        title={locale === "en" ? "Lecturers without any matching candidate" : "Giảng viên chưa có ứng viên đối sánh nào"}
        footer={null}
        onCancel={() => setGapsOpen(false)}
        width={640}
      >
        <div className="space-y-3">
          <p className="text-sm text-slate-500">
            {locale === "en"
              ? "These lecturers have zero candidate roots in any status — the automatic name rules never proposed anything for them at all (not even a rejected one). Use \"Add pair manually\" if you find a matching Scopus ID for one."
              : "Các giảng viên này chưa có ứng viên đối sánh nào ở bất kỳ trạng thái nào — rule tự động chưa từng đề xuất gì cho họ (kể cả bị từ chối). Dùng \"Thêm cặp thủ công\" nếu cậu tìm được Scopus ID khớp."}
          </p>
          <Input
            value={gapsSearch}
            onChange={(e) => setGapsSearch(e.target.value)}
            placeholder={locale === "en" ? "Search by name, email or staff code…" : "Tìm theo tên, email hoặc mã cán bộ…"}
            allowClear
          />
          <div className="max-h-[50vh] overflow-y-auto rounded-[5px] border border-slate-200">
            {gapsLoading ? (
              <div className="flex justify-center py-8"><Spin /></div>
            ) : gapsItems.length === 0 ? (
              <Empty
                description={locale === "en" ? "No gaps found" : "Không có giảng viên nào bị bỏ sót"}
                className="py-8"
              />
            ) : (
              <ul className="divide-y divide-slate-100">
                {gapsItems.map((lec) => (
                  <li key={lec.id} className="flex items-center justify-between gap-3 px-3 py-2.5">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-slate-800">{lec.full_name}</div>
                      <div className="truncate text-xs text-slate-500">
                        {[lec.staff_code, lec.department, lec.email].filter(Boolean).join(" · ") || "—"}
                      </div>
                    </div>
                    <UiButton variant="secondary" size="sm" onClick={() => openManualFor(lec)}>
                      {locale === "en" ? "Add pair" : "Thêm cặp"}
                    </UiButton>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <p className="text-xs text-slate-400">
            {locale === "en" ? "Total" : "Tổng"}: {gapsTotal}
          </p>
        </div>
      </Modal>

      <Modal
        open={manualOpen}
        title={locale === "en" ? "Add matching pair manually" : "Thêm cặp đối sánh thủ công"}
        okText={locale === "en" ? "Add (Pending)" : "Thêm (Chờ duyệt)"}
        cancelText={t.cancel}
        onOk={() => void submitManualCandidate()}
        onCancel={closeManual}
        confirmLoading={manualSubmitting}
      >
        <div className="space-y-3">
          <p className="text-sm text-slate-500">
            {locale === "en"
              ? "Use this only when the automatic name-matching rules missed a pair that genuinely belongs together (e.g. word-order ambiguity). It only creates a PENDING candidate — it still goes through normal review."
              : "Chỉ dùng khi rule đối sánh tên tự động bỏ sót một cặp thực sự đúng (vd. lệch thứ tự từ trong tên). Chỉ tạo ứng viên Chờ duyệt — vẫn phải qua duyệt bình thường."}
          </p>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">
              {locale === "en" ? "Lecturer" : "Giảng viên ICTU"}
            </label>
            <Select
              showSearch
              allowClear
              value={manualLecturerId}
              placeholder={locale === "en" ? "Search by name…" : "Tìm theo tên…"}
              filterOption={false}
              loading={manualLecturerSearching}
              options={manualLecturerOptions}
              onSearch={setManualLecturerQuery}
              onChange={(value) => setManualLecturerId(value ?? null)}
              className="w-full"
              notFoundContent={
                manualLecturerQuery.trim().length < 2
                  ? (locale === "en" ? "Type at least 2 characters" : "Gõ ít nhất 2 ký tự")
                  : (locale === "en" ? "No lecturer found" : "Không tìm thấy giảng viên")
              }
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">Scopus ID</label>
            <Input
              value={manualScopusId}
              onChange={(e) => setManualScopusId(e.target.value)}
              placeholder={locale === "en" ? "e.g. 60024922300" : "VD: 60024922300"}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">
              {locale === "en" ? "Reason / evidence" : "Lý do / căn cứ"}
            </label>
            <Input.TextArea
              value={manualNote}
              onChange={(e) => setManualNote(e.target.value)}
              rows={3}
              placeholder={
                locale === "en"
                  ? "e.g. ORCID 0009-... lists this employment at ICTU and this exact paper"
                  : "VD: ORCID 0009-... ghi công tác tại ICTU và chính bài báo này"
              }
            />
          </div>
          {manualError && <Alert type="error" showIcon message={manualError} />}
        </div>
      </Modal>

      <Modal
        open={generateConfirmOpen}
        title={t.generateConfirmTitle}
        okText={t.generateConfirmOk}
        cancelText={t.cancel}
        onOk={() => void handleGenerate()}
        onCancel={() => setGenerateConfirmOpen(false)}
        confirmLoading={generating}
      >
        <p className="text-sm text-slate-600">{t.generateConfirmText}</p>
      </Modal>

      {/* ── Review by lecturer group (lecturers with 2+ pending Scopus IDs) ───── */}
      {status === "PENDING" && (
        <GroupReviewPanel
          locale={locale === "en" ? "en" : "vi"}
          refreshKey={total}
          onChanged={() => void loadQueue()}
        />
      )}

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

          {/* Mức độ mơ hồ */}
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
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
                <tr>
                  <th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">{t.colLecturer}</th>
                  <th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">{t.colScopusAuthor}</th>
                  <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">{t.colStatus}</th>
                  <th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">{t.colEvidence}</th>
                  <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">
                    {locale === "en" ? "Degree of fit" : "Mức phù hợp"}
                  </th>
                  <th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">{t.colAmbiguityContext}</th>
                  <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap w-28">{t.colActions}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {queueLoading ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center gap-2">
                        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                        <span>{t.loadingQueue}</span>
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
                      <td className="px-4 py-3.5 align-middle whitespace-nowrap">
                        <span className="font-bold text-slate-800">{item.lecturer.full_name}</span>
                      </td>
                      <td className="px-4 py-3.5 align-middle">
                        <div className="font-medium text-slate-900">{item.scopus_author.preferred_name}</div>
                        <div className="mt-0.5 font-mono text-[10px] text-slate-400">{item.scopus_author.scopus_id}</div>
                      </td>
                      <td className="px-4 py-3.5 text-center align-middle whitespace-nowrap">
                        <span className={nhanBadgeClass(CANDIDATE_STATUS_TONE[item.candidate_status])}>
                          {statusLabels(t)[item.candidate_status]}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 align-middle">
                        {item.publication_support_count > 0 && item.name_evidence_count === 0 ? (
                          <div>
                            <span className={nhanBadgeClass("violet")} title={t.craweOnlyBadgeTooltip}>
                              {t.craweOnlyBadge}
                            </span>
                            <div className="mt-1 text-[10px] text-slate-400">{format(t.craweOnlyCount, { count: item.publication_support_count })}</div>
                          </div>
                        ) : item.publication_support_count > 0 ? (
                          <div>
                            <span className={nhanBadgeClass("info")}>
                              {t.publicationSupportedBadge}
                            </span>
                            <div className="mt-1 text-[10px] text-slate-400">
                              {format(t.publicationSupportedCount, { publications: item.publication_support_count, names: item.name_evidence_count })}
                            </div>
                          </div>
                        ) : (
                          <div>
                            <span className={nhanBadgeClass("neutral")}>
                              {t.nameOnlyBadge}
                            </span>
                            <div className="mt-1 text-[10px] text-slate-400">{format(t.nameOnlyCount, { count: item.name_evidence_count })}</div>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-center align-middle">
                        {item.fit ? <FitBadge fit={item.fit} locale={locale === "en" ? "en" : "vi"} /> : <span className="text-slate-300">—</span>}
                      </td>
                      <td className="px-4 py-3.5 align-middle">
                        <div className="flex flex-col items-start gap-1">
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
                      <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => openDetail(item.candidate_id)}
                          className="inline-flex h-badge w-32 shrink-0 items-center justify-center gap-1 whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-xs font-bold leading-none text-slate-700 transition-colors hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900 cursor-pointer"
                        >
                          <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
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
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-2.5 text-[11px] text-slate-500">
            <div className="flex items-center gap-3">
              <span>{format(t.showingOf, { shown: items.length, total })}</span>
              <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
                <span className="text-slate-500">{t.perPageLabel}</span>
                <select
                  value={pageSize}
                  disabled={queueLoading}
                  onChange={(e) => { setPage(1); setPageSize(Number(e.target.value)); }}
                  className="h-6 rounded-[5px] border border-slate-200 bg-white px-1.5 text-[11px] font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer disabled:opacity-50"
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

      <Modal
        open={selectedCandidateId !== null}
        title={t.detailModalTitle}
        width={1040}
        footer={null}
        centered
        destroyOnHidden
        maskClosable={!decisionSubmitting}
        closable={!decisionSubmitting}
        onCancel={closeDetail}
        styles={{ body: { padding: 0 } }}
        zIndex={1000}
      >
        {detailLoading ? (
          <div className="flex min-h-72 flex-col items-center justify-center gap-3">
            <Spin size="large" />
            <Text type="secondary">{t.loadingEvidence}</Text>
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
          <div className="flex max-h-[80vh] flex-col">
          <div className="flex-1 overflow-y-auto px-6 pb-2 pt-4">
            {conflictMessage && (
              <Alert className="mb-4" showIcon closable type="warning" message={t.conflictAlertTitle} description={conflictMessage} onClose={() => setConflictMessage(null)} />
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              <Card size="small" title={t.sectionLecturer}>
                <Descriptions size="small" column={1} colon={false}>
                  <Descriptions.Item label={t.fieldFullName}><Text strong>{detail.lecturer.full_name}</Text></Descriptions.Item>
                  <Descriptions.Item label={t.fieldAcademicDegree}>{displayValue(t, detail.lecturer.academic_degree)}</Descriptions.Item>
                  <Descriptions.Item label={t.fieldAcademicRank}>{displayValue(t, detail.lecturer.academic_rank)}</Descriptions.Item>
                  <Descriptions.Item label={t.fieldSourceProfile}>
                    {detail.lecturer.repository_profile_url ? (
                      <a href={detail.lecturer.repository_profile_url} target="_blank" rel="noreferrer">{t.openIctuProfile}</a>
                    ) : t.noData}
                  </Descriptions.Item>
                </Descriptions>
              </Card>

              <Card size="small" title={t.sectionScopusAuthor}>
                <Descriptions size="small" column={1} colon={false}>
                  <Descriptions.Item label={t.fieldPreferredName}><Text strong>{detail.scopus_author.preferred_name}</Text></Descriptions.Item>
                  <Descriptions.Item label={t.fieldScopusId}><Text code>{detail.scopus_author.scopus_id}</Text></Descriptions.Item>
                  <Descriptions.Item label={t.fieldNameVariants}>
                    {detail.scopus_author.name_variants.length > 0 ? (
                      <Space wrap>{detail.scopus_author.name_variants.map((variant) => <Badge key={variant} tone="neutral" className="!rounded-[5px]">{variant}</Badge>)}</Space>
                    ) : t.noNameVariants}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </div>

            {detail.fit && (
              <section className="rounded-[5px] border border-slate-200 bg-white p-3.5" data-testid="fit-section">
                <div className="flex flex-wrap items-center gap-3">
                  <h3 className="text-sm font-bold text-slate-800">
                    {locale === "en" ? "Degree of fit and its grounds" : "Mức độ phù hợp và căn cứ"}
                  </h3>
                  <FitBadge fit={detail.fit} locale={locale === "en" ? "en" : "vi"} />
                </div>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-700">
                  {detail.fit.reasons.map((code) => (
                    <li key={code}>{fitReasonText(code, locale === "en" ? "en" : "vi", detail.fit?.ictu_affiliation_papers ?? 0)}</li>
                  ))}
                </ul>
                <p className="mt-2 text-[11px] text-slate-500">
                  {locale === "en"
                    ? `"${fitLevelLabel(detail.fit.level, "en")}" is an aid for the reviewer. It is not a probability and confirms nothing; the decision stays with the reviewer.`
                    : `"${fitLevelLabel(detail.fit.level, "vi")}" chỉ là gợi ý cho người duyệt. Đây không phải xác suất và không tự xác nhận; quyết định vẫn thuộc người duyệt.`}
                </p>
              </section>
            )}

            <Divider orientation="left">{t.sectionNameEvidence}</Divider>
            {detail.name_evidence.length > 0 ? (
              <div className="space-y-3">{detail.name_evidence.map((evidence) => <NameEvidenceCard key={evidence.evidence_id} t={t} locale={locale} evidence={evidence} />)}</div>
            ) : detail.publication_evidence.length > 0 ? (
              <Alert
                type="warning"
                showIcon
                message={t.nameMismatchWarningTitle}
                description={t.nameMismatchWarningDescription}
              />
            ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t.noNameEvidence} />}

            <Divider orientation="left">{t.sectionPublicationEvidence}</Divider>
            {detail.publication_evidence.length > 0 ? (
              <div className="space-y-3">
                {detail.publication_evidence.map((evidence) => (
                  <div key={evidence.evidence_id} className="rounded-[5px] border border-slate-200 p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <Badge tone={evidence.reconciliation === "DOI_EXACT" ? "success" : "brand"} className="!rounded-[5px]" title={evidence.reconciliation ?? undefined}>
                        {reconciliationLabel(evidence.reconciliation, locale, t.reconciliationUnknown)}
                      </Badge>
                      <Text type="secondary" title={evidence.rule_id}>{ruleLabel(evidence.rule_id, locale)}</Text>
                    </div>
                    <div className="text-base font-semibold text-slate-900">{displayValue(t, evidence.title)}</div>
                    <div className="mt-2 grid gap-2 text-sm md:grid-cols-2">
                      <div><span className="font-semibold text-slate-600">{t.doiLabel}: </span>{displayValue(t, evidence.doi)}</div>
                      <div><span className="font-semibold text-slate-600">{t.eidLabel}: </span>{displayValue(t, evidence.eid)}</div>
                    </div>
                    {evidence.source_refs.length > 0 && (
                      <div className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
                        <span className="font-semibold text-slate-600">{t.sourceLabel}: </span>
                        {evidence.source_refs.map((ref, index) => (
                          <span key={`${evidence.evidence_id}-source-${index}`}>{index > 0 && " | "}{provenanceText(t, ref)}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t.noPublicationEvidence} />}

            <Divider orientation="left">{t.sectionAmbiguityContext}</Divider>
            <Alert
              showIcon
              type={detail.ambiguity.is_ambiguous ? "warning" : "info"}
              message={ambiguityText(t, detail.ambiguity.candidate_count_for_lecturer)}
              description={detail.ambiguity.other_candidates.length > 0 ? t.ambiguityOtherListed : t.ambiguityNoOthers}
            />
            {detail.ambiguity.is_shared_scopus_author && (
              <Alert
                className="mt-3"
                showIcon
                type="error"
                message={sharedAuthorText(t, detail.ambiguity.candidate_count_for_scopus_author)}
                description={t.ambiguitySharedWarning}
              />
            )}
            {detail.ambiguity.other_candidates.length > 0 && (
              <div className="mt-3 space-y-2">
                {detail.ambiguity.other_candidates.map((candidate) => (
                  <div key={candidate.candidate_id} className="flex flex-wrap items-center justify-between gap-2 rounded-[5px] border border-slate-200 px-4 py-3">
                    <div>
                      <div className="font-medium text-slate-900">{candidate.scopus_author.preferred_name}</div>
                      <div className="font-mono text-xs text-slate-500">{candidate.scopus_author.scopus_id}</div>
                    </div>
                    <Badge tone={CANDIDATE_STATUS_TONE[candidate.candidate_status]} size="md" className="min-w-[96px] justify-center !rounded-[5px]">{statusLabels(t)[candidate.candidate_status]}</Badge>
                  </div>
                ))}
              </div>
            )}

            {detail.candidate_status === "ACCEPTED" && (
              <PrimaryIdPanel lecturerId={detail.lecturer.id} locale={locale === "en" ? "en" : "vi"} />
            )}

          </div>
          <div className="shrink-0 border-t border-slate-200 px-6 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm text-slate-500">
                {t.currentStatusLabel}: <Badge tone={CANDIDATE_STATUS_TONE[detail.candidate_status]} size="md" className="min-w-[96px] justify-center !rounded-[5px]">{statusLabels(t)[detail.candidate_status]}</Badge>
              </div>
              {detail.candidate_status === "PENDING" && (
                <Space wrap>
                  <Button danger onClick={() => setDecisionAction("REJECT")}>{t.rejectAction}</Button>
                  <Button type="primary" onClick={() => setDecisionAction("ACCEPT")}>{t.acceptAction}</Button>
                </Space>
              )}
              {user?.role === "ADMIN" && detail.candidate_status === "ACCEPTED" && (
                <Button
                  danger
                  onClick={() => {
                    setRevocationError(null);
                    setRevocationOpen(true);
                  }}
                >
                  {t.revokeAction}
                </Button>
              )}
              {detail.candidate_status === "REJECTED" && (
                <Button
                  onClick={() => {
                    setReopenError(null);
                    setReopenOpen(true);
                  }}
                >
                  {locale === "en" ? "Reopen" : "Mở lại"}
                </Button>
              )}
            </div>
          </div>
          </div>
        ) : <Empty description={t.noDetailData} className="py-10" />}
      </Modal>

      <Modal
        open={reopenOpen && detail !== null}
        title={locale === "en" ? "Reopen rejected candidate" : "Mở lại ứng viên đã từ chối"}
        zIndex={1050}
        okText={locale === "en" ? "Reopen (Pending)" : "Mở lại (Chờ duyệt)"}
        okButtonProps={{ disabled: reopenReason.trim().length === 0 }}
        cancelText={t.cancel}
        confirmLoading={reopenSubmitting}
        closable={!reopenSubmitting}
        maskClosable={!reopenSubmitting}
        onOk={() => void submitReopen()}
        onCancel={closeReopen}
      >
        {detail && (
          <div className="space-y-4">
            <Alert
              showIcon
              type="info"
              message={
                locale === "en"
                  ? "The candidate goes back to PENDING for a fresh review. Nothing is accepted automatically."
                  : "Ứng viên sẽ quay về trạng thái Chờ duyệt. Không có gì được tự động chấp nhận."
              }
            />
            <Descriptions size="small" column={1} colon={false}>
              <Descriptions.Item label={t.fieldLecturer}><Text strong>{detail.lecturer.full_name}</Text></Descriptions.Item>
              <Descriptions.Item label={t.fieldScopusAuthor}>{detail.scopus_author.preferred_name} ({detail.scopus_author.scopus_id})</Descriptions.Item>
            </Descriptions>
            <div>
              <label htmlFor="review-reopen-reason" className="mb-1.5 block font-semibold text-slate-700">
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
            {reopenError && <Alert type="error" showIcon message={reopenError} />}
          </div>
        )}
      </Modal>

      <Modal
        open={revocationOpen && detail !== null}
        title={t.revokeModalTitle}
        zIndex={1050}
        okText={t.confirmRevokeOk}
        okButtonProps={{ danger: true, disabled: revocationReason.trim().length === 0 }}
        cancelText={t.cancel}
        confirmLoading={revocationSubmitting}
        closable={!revocationSubmitting}
        maskClosable={!revocationSubmitting}
        onOk={() => void submitRevocation()}
        onCancel={closeRevocation}
      >
        {detail && (
          <div className="space-y-4">
            <Alert showIcon type="warning" message={t.revokeModalText} />
            <Descriptions size="small" column={1} colon={false}>
              <Descriptions.Item label={t.fieldLecturer}><Text strong>{detail.lecturer.full_name}</Text></Descriptions.Item>
              <Descriptions.Item label={t.fieldScopusAuthor}>{detail.scopus_author.preferred_name} ({detail.scopus_author.scopus_id})</Descriptions.Item>
            </Descriptions>
            <div>
              <label htmlFor="review-revoke-reason" className="mb-1.5 block font-semibold text-slate-700">
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
              {revocationError && <div className="mt-1 text-sm text-rose-600" role="alert">{revocationError}</div>}
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={decisionAction === "ACCEPT" && detail !== null}
        title={t.confirmAcceptTitle}
        zIndex={1050}
        okText={t.confirmAcceptOk}
        okButtonProps={{ disabled: acceptReasonRequired && decisionReason.trim().length === 0 }}
        cancelText={t.cancel}
        confirmLoading={decisionSubmitting}
        closable={!decisionSubmitting}
        maskClosable={!decisionSubmitting}
        onOk={() => void submitDecision()}
        onCancel={closeDecision}
      >
        {detail && (
          <div className="space-y-3">
            <Alert showIcon type="info" message={t.confirmAcceptHint} />
            <Descriptions size="small" column={1} colon={false}>
              <Descriptions.Item label={t.fieldLecturer}><Text strong>{detail.lecturer.full_name}</Text></Descriptions.Item>
              <Descriptions.Item label={t.fieldScopusAuthor}>{detail.scopus_author.preferred_name}</Descriptions.Item>
              <Descriptions.Item label={t.fieldScopusId}><Text code>{detail.scopus_author.scopus_id}</Text></Descriptions.Item>
              <Descriptions.Item label={t.fieldAction}><Badge tone="success" className="!rounded-[5px]">{t.decisionAccept}</Badge></Descriptions.Item>
            </Descriptions>
            {acceptReasonRequired && (
              <Alert
                showIcon
                type="warning"
                data-testid="accept-reason-required"
                message={t.acceptReasonRequiredTitle}
                description={
                  <ul className="m-0 list-disc pl-4">
                    {acceptReasonTriggers.map((trigger) => (
                      <li key={trigger}>{reasonTriggerText(t, trigger)}</li>
                    ))}
                  </ul>
                }
              />
            )}
            <div>
              <label htmlFor="review-accept-reason" className="mb-1.5 block font-semibold text-slate-700">
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
                className="mb-5"
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
              {reasonError && <div className="mt-1 text-sm text-rose-600" role="alert">{reasonError}</div>}
              <div className="mt-1 text-xs text-slate-500">{t.acceptReasonNotEvidence}</div>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={decisionAction === "REJECT" && detail !== null}
        title={t.rejectModalTitle}
        zIndex={1050}
        okText={t.confirmRejectOk}
        okButtonProps={{ danger: true, disabled: decisionReason.trim().length === 0 }}
        cancelText={t.cancel}
        confirmLoading={decisionSubmitting}
        closable={!decisionSubmitting}
        maskClosable={!decisionSubmitting}
        onOk={() => void submitDecision()}
        onCancel={closeDecision}
      >
        {detail && (
          <div className="space-y-4">
            <Descriptions size="small" column={1} colon={false}>
              <Descriptions.Item label={t.fieldLecturer}><Text strong>{detail.lecturer.full_name}</Text></Descriptions.Item>
              <Descriptions.Item label={t.fieldScopusAuthor}>{detail.scopus_author.preferred_name} ({detail.scopus_author.scopus_id})</Descriptions.Item>
              <Descriptions.Item label={t.fieldAction}><Badge tone="danger" className="!rounded-[5px]">{t.decisionReject}</Badge></Descriptions.Item>
            </Descriptions>
            <div>
              <label htmlFor="review-reject-reason" className="mb-1.5 block font-semibold text-slate-700">
                {t.rejectReasonLabel} <span className="text-rose-600">*</span>
              </label>
              <Input.TextArea
                id="review-reject-reason"
                className="mb-5"
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
              {reasonError && <div className="mt-1 text-sm text-rose-600" role="alert">{reasonError}</div>}
            </div>
          </div>
        )}
      </Modal>
    </div>
    </ConfigProvider>
  );
}
