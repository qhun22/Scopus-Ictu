import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Divider,
  Empty,
  Input,
  Modal,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";

import {
  decideReviewCandidate,
  getReviewCandidate,
  getReviewCandidates,
  getReviewContext,
} from "../../api/reviews";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { useToast } from "../../contexts/ToastContext";
import { useI18n } from "../../i18n/I18nContext";
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
} from "../../types/review";

const { Paragraph, Text } = Typography;

type EvidenceFilter = EvidenceCategory | "all";
type AmbiguitySelection = AmbiguityFilter | "all";
type T = TranslationSchema["approvalQueue"];

const STATUS_COLORS: Record<CandidateStatus, string> = {
  PENDING: "gold",
  ACCEPTED: "green",
  REJECTED: "red",
  SUPERSEDED: "default",
};

const STATUS_BADGE_CLASS: Record<CandidateStatus, string> = {
  PENDING: "border-amber-300 bg-amber-50 text-amber-700",
  ACCEPTED: "border-emerald-200 bg-emerald-50 text-emerald-700",
  REJECTED: "border-rose-200 bg-rose-50 text-rose-700",
  SUPERSEDED: "border-slate-200 bg-slate-100 text-slate-600",
};

const badgeClassName =
  "inline-flex h-6 items-center justify-center rounded-full border px-2.5 text-[11px] font-bold whitespace-nowrap";

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

function NameEvidenceCard({ t, evidence }: { t: T; evidence: ReviewNameEvidence }) {
  return (
    <div className="rounded-[5px] border border-slate-200 bg-slate-50/70 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Tag color="blue">{evidence.rule_id}</Tag>
        <Text type="secondary">{format(t.ruleVersionLabel, { version: evidence.rule_version })}</Text>
      </div>
      <Paragraph className="!mb-3 !mt-2 !text-slate-600">
        {t.nameRuleExplanation}
      </Paragraph>
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
            {evidence.scopus_surface_type && `${t.typeLabel}: ${evidence.scopus_surface_type}`}
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
        .map(([name, count]) => `${name}: ${n(count)}`)
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
  const { t: fullT, locale } = useI18n();
  const t = fullT.approvalQueue;
  const [status, setStatus] = useState<CandidateStatus>("PENDING");
  const [evidenceFilter, setEvidenceFilter] = useState<EvidenceFilter>("all");
  const [ambiguityFilter, setAmbiguityFilter] = useState<AmbiguitySelection>("all");
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
  const [rejectReason, setRejectReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [decisionSubmitting, setDecisionSubmitting] = useState(false);

  const loadQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError(null);
    try {
      const response = await getReviewCandidates({
        status,
        evidence_category: evidenceFilter === "all" ? undefined : evidenceFilter,
        ambiguity: ambiguityFilter === "all" ? undefined : ambiguityFilter,
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
  }, [ambiguityFilter, evidenceFilter, page, pageSize, status, t.loadQueueError]);

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
    setRejectReason("");
    setReasonError(null);
  };

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

  const submitDecision = async () => {
    if (!detail || !decisionAction) return;

    const trimmedReason = rejectReason.trim();
    if (decisionAction === "REJECT" && !trimmedReason) {
      setReasonError(t.rejectReasonRequired);
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
      setRejectReason("");
      await refreshQueueAndDetail();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
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
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* ── Page Header ──────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">{t.title}</h1>
          <p className="mt-0.5 text-xs text-slate-500 sm:text-sm">
            {t.subtitle}
          </p>
        </div>
        <div className="text-xs text-slate-500 mt-1">
          {t.totalLabel}: <span className="font-semibold text-slate-800">{total}</span>
        </div>
      </div>

      {/* ── Filter Bar ──────────────────────────────────────────────────── */}
      <div className="rounded-[5px] border border-slate-200/80 bg-white p-3.5 shadow-xs">
        <div className="flex flex-wrap items-end gap-3">
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
                  <th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">{t.colAmbiguityContext}</th>
                  <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap w-28">{t.colActions}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {queueLoading ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center gap-2">
                        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                        <span>{t.loadingQueue}</span>
                      </div>
                    </td>
                  </tr>
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
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
                        <span className={`${badgeClassName} ${STATUS_BADGE_CLASS[item.candidate_status]}`}>
                          {statusLabels(t)[item.candidate_status]}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 align-middle">
                        {item.publication_support_count > 0 && item.name_evidence_count === 0 ? (
                          <div>
                            <span
                              className="inline-flex h-5 items-center rounded-full border border-violet-200 bg-violet-50 px-2 text-[10px] font-bold text-violet-700"
                              title={t.craweOnlyBadgeTooltip}
                            >
                              {t.craweOnlyBadge}
                            </span>
                            <div className="mt-1 text-[10px] text-slate-400">{format(t.craweOnlyCount, { count: item.publication_support_count })}</div>
                          </div>
                        ) : item.publication_support_count > 0 ? (
                          <div>
                            <span className="inline-flex h-5 items-center rounded-full border border-cyan-200 bg-cyan-50 px-2 text-[10px] font-bold text-cyan-700">
                              {t.publicationSupportedBadge}
                            </span>
                            <div className="mt-1 text-[10px] text-slate-400">
                              {format(t.publicationSupportedCount, { publications: item.publication_support_count, names: item.name_evidence_count })}
                            </div>
                          </div>
                        ) : (
                          <div>
                            <span className="inline-flex h-5 items-center rounded-full border border-slate-200 bg-slate-100 px-2 text-[10px] font-bold text-slate-600">
                              {t.nameOnlyBadge}
                            </span>
                            <div className="mt-1 text-[10px] text-slate-400">{format(t.nameOnlyCount, { count: item.name_evidence_count })}</div>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3.5 align-middle">
                        <div className="flex flex-col gap-1">
                          <span className={`inline-flex h-5 w-fit items-center rounded-full border px-2 text-[10px] font-bold ${item.is_ambiguous ? "border-amber-300 bg-amber-50 text-amber-700" : "border-slate-200 bg-slate-100 text-slate-600"}`}>
                            {ambiguityText(t, item.candidate_count_for_lecturer)}
                          </span>
                          {item.is_shared_scopus_author && (
                            <span
                              data-testid="shared-author-tag"
                              title={sharedAuthorText(t, item.candidate_count_for_scopus_author)}
                              className="inline-flex h-5 w-fit items-center rounded-full border border-rose-200 bg-rose-50 px-2 text-[10px] font-bold text-rose-700"
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
                          className="inline-flex h-7 items-center justify-center gap-1 rounded-[5px] border border-slate-200 bg-white px-2.5 text-[11px] font-semibold text-slate-700 shadow-2xs transition-all duration-150 active:scale-[0.97] hover:border-[#3A5FC3] hover:text-[#3A5FC3] cursor-pointer whitespace-nowrap"
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
        destroyOnClose
        maskClosable={!decisionSubmitting}
        closable={!decisionSubmitting}
        onCancel={closeDetail}
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
          <div className="max-h-[72vh] overflow-y-auto pr-1">
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
                      <Space wrap>{detail.scopus_author.name_variants.map((variant) => <Tag key={variant}>{variant}</Tag>)}</Space>
                    ) : t.noNameVariants}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </div>

            <Divider orientation="left">{t.sectionNameEvidence}</Divider>
            {detail.name_evidence.length > 0 ? (
              <div className="space-y-3">{detail.name_evidence.map((evidence) => <NameEvidenceCard key={evidence.evidence_id} t={t} evidence={evidence} />)}</div>
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
                      <Tag color={evidence.reconciliation === "DOI_EXACT" ? "green" : "blue"}>{evidence.reconciliation ?? t.reconciliationUnknown}</Tag>
                      <Text type="secondary">{evidence.rule_id} · {format(t.ruleVersionLabel, { version: evidence.rule_version })}</Text>
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
                    <Tag color={STATUS_COLORS[candidate.candidate_status]}>{statusLabels(t)[candidate.candidate_status]}</Tag>
                  </div>
                ))}
              </div>
            )}

            <Divider />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm text-slate-500">
                {t.currentStatusLabel}: <Tag color={STATUS_COLORS[detail.candidate_status]}>{statusLabels(t)[detail.candidate_status]}</Tag>
              </div>
              {detail.candidate_status === "PENDING" && (
                <Space wrap>
                  <Button danger onClick={() => setDecisionAction("REJECT")}>{t.rejectAction}</Button>
                  <Button type="primary" onClick={() => setDecisionAction("ACCEPT")}>{t.acceptAction}</Button>
                </Space>
              )}
            </div>
          </div>
        ) : <Empty description={t.noDetailData} />}
      </Modal>

      <Modal
        open={decisionAction === "ACCEPT" && detail !== null}
        title={t.confirmAcceptTitle}
        okText={t.confirmAcceptOk}
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
              <Descriptions.Item label={t.fieldAction}><Tag color="green">ACCEPT</Tag></Descriptions.Item>
            </Descriptions>
          </div>
        )}
      </Modal>

      <Modal
        open={decisionAction === "REJECT" && detail !== null}
        title={t.rejectModalTitle}
        okText={t.confirmRejectOk}
        okButtonProps={{ danger: true, disabled: rejectReason.trim().length === 0 }}
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
              <Descriptions.Item label={t.fieldAction}><Tag color="red">REJECT</Tag></Descriptions.Item>
            </Descriptions>
            <div>
              <label htmlFor="review-reject-reason" className="mb-1.5 block font-semibold text-slate-700">
                {t.rejectReasonLabel} <span className="text-rose-600">*</span>
              </label>
              <Input.TextArea
                id="review-reject-reason"
                value={rejectReason}
                rows={4}
                maxLength={4000}
                showCount
                status={reasonError ? "error" : undefined}
                placeholder={t.rejectReasonPlaceholder}
                onChange={(event) => {
                  setRejectReason(event.target.value);
                  if (event.target.value.trim()) setReasonError(null);
                }}
              />
              {reasonError && <div className="mt-1 text-sm text-rose-600">{reasonError}</div>}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
