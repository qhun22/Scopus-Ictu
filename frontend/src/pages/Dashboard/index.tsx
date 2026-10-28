import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getDashboardCharts, getDashboardSummary } from "../../api/dashboard";
import { getApiErrorMessage } from "../../api/errors";
import { resetSystem } from "../../api/system";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import TextConfirmModal from "../../components/common/TextConfirmModal";
import Badge, { type BadgeTone } from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useI18n } from "../../i18n";
import {
  DashboardCharts,
  DashboardIdentityStatus,
  DashboardSummary,
} from "../../types/dashboard";
import { AuditListItem } from "../../types/audit";
import { formatTimestamp } from "../../utils/dateTime";
import PublicationsByYearChart from "./charts/PublicationsByYearChart";
import DocumentTypeDonutChart from "./charts/DocumentTypeDonutChart";
import AffiliationCoverageChart from "./charts/AffiliationCoverageChart";


function ActorCell({
  item,
  userFallback,
  systemFallback,
}: {
  item: AuditListItem;
  userFallback: string;
  systemFallback: string;
}) {
  if (item.actor_type === "USER") {
    return <span>{item.actor_display_name ?? userFallback}</span>;
  }
  return (
    <span className="italic text-gray-500">{item.actor_service ?? systemFallback}</span>
  );
}

const IDENTITY_STATUSES: DashboardIdentityStatus[] = [
  "CANDIDATE",
  "APPROVED",
  "REJECTED",
  "REVOKED",
];

const IDENTITY_COLORS: Record<DashboardIdentityStatus, string> = {
  CANDIDATE: "bg-blue-50 border-blue-200 text-blue-700",
  APPROVED: "bg-green-50 border-green-200 text-green-700",
  REJECTED: "bg-red-50 border-red-200 text-red-700",
  REVOKED: "bg-gray-50 border-gray-200 text-gray-600",
};

const IDENTITY_LABEL_KEYS: Record<DashboardIdentityStatus, "identityCandidate" | "identityApproved" | "identityRejected" | "identityRevoked"> = {
  CANDIDATE: "identityCandidate",
  APPROVED: "identityApproved",
  REJECTED: "identityRejected",
  REVOKED: "identityRevoked",
};

export default function DashboardPage() {
  const { t, locale } = useI18n();
  const copy = t.dashboard;
  const toast = useToast();
  const { user: currentUser } = useAuth();

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const [charts, setCharts] = useState<DashboardCharts | null>(null);
  const [chartsLoading, setChartsLoading] = useState(true);
  const [chartsError, setChartsError] = useState<string | null>(null);
  const chartsControllerRef = useRef<AbortController | null>(null);

  // Reset modal state
  const [showResetModal, setShowResetModal] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const handleReset = async () => {
    setIsResetting(true);
    try {
      await resetSystem("ICTU");
      toast.success(copy.resetSuccessTitle, copy.resetSuccessMessage);
      setShowResetModal(false);
      fetchSummary();
    } catch (err) {
      toast.error(copy.resetErrorTitle, getApiErrorMessage(err, copy.resetErrorMessage));
    } finally {
      setIsResetting(false);
    }
  };

  const fetchSummary = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setError(null);

    getDashboardSummary({ signal: controller.signal })
      .then((data) => {
        setSummary(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setError(getApiErrorMessage(err, copy.loadError));
        setLoading(false);
      });
  }, [copy.loadError]);

  useEffect(() => {
    fetchSummary();
    return () => {
      controllerRef.current?.abort();
    };
  }, [fetchSummary]);

  const fetchCharts = useCallback(() => {
    if (chartsControllerRef.current) {
      chartsControllerRef.current.abort();
    }
    const controller = new AbortController();
    chartsControllerRef.current = controller;

    setChartsLoading(true);
    setChartsError(null);

    getDashboardCharts({ signal: controller.signal })
      .then((data) => {
        setCharts(data);
        setChartsLoading(false);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setChartsError(getApiErrorMessage(err, copy.loadError));
        setChartsLoading(false);
      });
  }, [copy.loadError]);

  useEffect(() => {
    fetchCharts();
    return () => {
      chartsControllerRef.current?.abort();
    };
  }, [fetchCharts]);

  return (
    <div className="app-page-container space-y-6">
      {/* Reset Confirmation Modal */}
      <TextConfirmModal
        open={showResetModal}
        title={copy.resetModalTitle}
        subtitle={copy.resetModalSubtitle}
        description={copy.resetModalDescription}
        confirmWord="ICTU"
        confirmLabel={copy.resetModalConfirmLabel}
        cancelLabel={copy.resetModalCancelLabel}
        loading={isResetting}
        onConfirm={handleReset}
        onCancel={() => setShowResetModal(false)}
      />

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{copy.title}</h1>
          <p className="mt-1 text-sm text-gray-500">{copy.subtitle}</p>
        </div>
        <div className="page-action-group">
          <Button
            variant="secondary"
            fullWidth
            onClick={fetchSummary}
            loading={loading}
            icon={
              <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            }
          >
            {copy.refresh}
          </Button>
          {currentUser?.role === "ADMIN" ? (
            <Button
              variant="danger"
              fullWidth
              onClick={() => setShowResetModal(true)}
              icon={
                <svg className="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              }
            >
              {copy.resetSystem}
            </Button>
          ) : (
            <div />
          )}
        </div>
      </div>

      {/* Error state */}
      {error && !loading && (
        <div className="rounded-[5px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !summary && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-24 animate-pulse rounded-[5px] border border-gray-200 bg-gray-100"
              />
            ))}
          </div>
        </div>
      )}

      {summary && (
        <>
          {/* Summary cards — 5 main metrics */}
          <section>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              <SummaryCard
                label={copy.totalPublications}
                value={summary.total_publications}
                href="/publications"
              />
              <SummaryCard
                label={copy.totalLecturers}
                value={summary.total_lecturers}
                href="/lecturers"
              />
              <SummaryCard
                label={copy.activeLecturers}
                value={summary.active_lecturers}
              />
              <SummaryCard
                label={copy.totalScopusAuthors}
                value={summary.total_scopus_authors}
              />
              <SummaryCard
                label={copy.pendingReviews}
                value={summary.pending_review_count}
                href="/reviews"
                highlight={summary.pending_review_count > 0}
              />
            </div>
          </section>

          {/* Identity link counts (lecturer_scopus_identities.status) — not the candidate review queue */}
          <section className="rounded-[5px] border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800">
              {copy.identityTitle}
            </h2>
            <p className="mb-4 mt-1 text-xs text-gray-500">{copy.identityHint}</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {IDENTITY_STATUSES.map((status) => (
                <div
                  key={status}
                  className={`rounded-[5px] border px-4 py-3 ${IDENTITY_COLORS[status]}`}
                >
                  <div className="text-xs font-medium uppercase tracking-wide opacity-75">
                    {copy[IDENTITY_LABEL_KEYS[status]]}
                  </div>
                  <div className="mt-1 text-2xl font-bold">
                    {summary.identity_counts[status] ?? 0}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Charts — publications by year, document type mix, affiliation coverage */}
          <section className="rounded-[5px] border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-base font-semibold text-gray-800">
              {copy.chartsTitle}
            </h2>

            {chartsLoading && !charts && (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <div className="h-64 animate-pulse rounded-[5px] bg-gray-100" />
                <div className="h-64 animate-pulse rounded-[5px] bg-gray-100" />
              </div>
            )}

            {chartsError && !chartsLoading && (
              <div className="flex flex-wrap items-center gap-3 rounded-[5px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <span>{chartsError}</span>
                <Button variant="secondary" size="sm" onClick={fetchCharts}>
                  {copy.chartsRetry}
                </Button>
              </div>
            )}

            {charts && !chartsLoading && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  {/* Publications by year */}
                  <div>
                    <h3 className="mb-1 text-sm font-semibold text-slate-700">
                      {copy.publicationsByYearTitle}
                    </h3>
                    {charts.publications_by_year.length === 0 ? (
                      <div className="flex h-64 flex-col items-center justify-center gap-1.5 rounded-[5px] border border-dashed border-slate-200 text-center">
                        <p className="text-sm font-medium text-slate-500">
                          {copy.publicationsByYearEmptyTitle}
                        </p>
                        <p className="text-xs text-slate-400">
                          {copy.publicationsByYearEmptySubtitle}
                        </p>
                      </div>
                    ) : (
                      <>
                        <PublicationsByYearChart data={charts.publications_by_year} locale={locale} />
                        {charts.publications_total_without_year > 0 && (
                          <p className="mt-2 text-[11px] text-slate-400">
                            {charts.publications_total_without_year.toLocaleString(
                              locale === "vi" ? "vi-VN" : "en-US",
                            )}{" "}
                            {copy.publicationsWithoutYearNote}
                          </p>
                        )}
                      </>
                    )}
                  </div>

                  {/* Document type breakdown */}
                  <div>
                    <h3 className="mb-1 text-sm font-semibold text-slate-700">
                      {copy.documentTypeTitle}
                    </h3>
                    {charts.publications_by_document_type.length === 0 ? (
                      <div className="flex h-64 flex-col items-center justify-center gap-1.5 rounded-[5px] border border-dashed border-slate-200 text-center">
                        <p className="text-sm font-medium text-slate-500">
                          {copy.documentTypeEmptyTitle}
                        </p>
                      </div>
                    ) : (
                      <DocumentTypeDonutChart data={charts.publications_by_document_type} locale={locale} />
                    )}
                  </div>
                </div>

                {/* Affiliation coverage */}
                <div className="border-t border-gray-100 pt-5">
                  <h3 className="mb-1 text-sm font-semibold text-slate-700">
                    {copy.affiliationCoverageTitle}
                  </h3>
                  {charts.affiliation_coverage.total_author_positions === 0 ? (
                    <div className="flex h-40 flex-col items-center justify-center gap-1.5 rounded-[5px] border border-dashed border-slate-200 text-center">
                      <p className="text-sm font-medium text-slate-500">
                        {copy.affiliationCoverageEmptyTitle}
                      </p>
                      <p className="text-xs text-slate-400">
                        {copy.affiliationCoverageEmptySubtitle}
                      </p>
                    </div>
                  ) : (
                    <AffiliationCoverageChart data={charts.affiliation_coverage} locale={locale} />
                  )}
                </div>
              </div>
            )}
          </section>

          {/* Latest Scopus import */}
          <section className="rounded-[5px] border border-gray-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-800">
                {copy.latestImportTitle}
              </h2>
              <Link
                to="/imports"
                className="text-sm text-blue-600 hover:underline"
              >
                {t.nav.imports}
              </Link>
            </div>
            {summary.latest_scopus_import === null ? (
              <div className="py-6 text-center">
                <p className="text-sm font-medium text-gray-600">{copy.noImportTitle}</p>
                <p className="mt-1 text-xs text-gray-400">{copy.noImportSubtitle}</p>
              </div>
            ) : (
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-4">
                <div>
                  <dt className="font-medium text-gray-500">{copy.fileName}</dt>
                  <dd className="mt-0.5 break-all text-gray-900">
                    {summary.latest_scopus_import.file_name}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-500">{copy.status}</dt>
                  <dd className="mt-0.5">
                    <ImportStatusBadge status={summary.latest_scopus_import.status} locale={locale} />
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-500">{copy.totalRecords}</dt>
                  <dd className="mt-0.5 text-gray-900">
                    {summary.latest_scopus_import.total_records}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-500">{copy.validRecords}</dt>
                  <dd className="mt-0.5 text-green-700">
                    {summary.latest_scopus_import.valid_records}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-500">{copy.invalidRecords}</dt>
                  <dd className="mt-0.5 text-red-600">
                    {summary.latest_scopus_import.invalid_records}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-500">{copy.createdAt}</dt>
                  <dd className="mt-0.5 text-gray-900">
                    {formatTimestamp(summary.latest_scopus_import.created_at)}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-500">{copy.updatedAt}</dt>
                  <dd className="mt-0.5 text-gray-900">
                    {formatTimestamp(summary.latest_scopus_import.updated_at)}
                  </dd>
                </div>
              </dl>
            )}
          </section>

          {/* Recent audit actions */}
          <section className="rounded-[5px] border border-gray-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-800">
                {copy.recentAuditTitle}
              </h2>
              <Link
                to="/audit-logs"
                className="text-sm text-blue-600 hover:underline"
              >
                {copy.viewAuditLogs}
              </Link>
            </div>
            {summary.recent_audit_actions.length === 0 ? (
              <div className="py-6 text-center">
                <p className="text-sm font-medium text-gray-600">{copy.noRecentAudit}</p>
                <p className="mt-1 text-xs text-gray-400">{copy.noRecentAuditSubtitle}</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                      <th className="pb-2 pr-4">{copy.time}</th>
                      <th className="pb-2 pr-4">{copy.entityType}</th>
                      <th className="pb-2 pr-4">{copy.action}</th>
                      <th className="pb-2 pr-4">{copy.actor}</th>
                      <th className="pb-2">{copy.reason}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {summary.recent_audit_actions.map((item) => (
                      <tr key={item.id} className="align-top">
                        <td className="py-2 pr-4 whitespace-nowrap text-gray-500">
                          {formatTimestamp(item.created_at)}
                        </td>
                        <td className="py-2 pr-4 text-gray-700">
                          {copy.entityLabels[item.entity_type] ?? item.entity_type}
                        </td>
                        <td className="py-2 pr-4 text-gray-700">
                          {copy.actionLabels[item.action] ?? item.action}
                        </td>
                        <td className="py-2 pr-4">
                          <ActorCell
                            item={item}
                            userFallback={copy.userFallback}
                            systemFallback={copy.systemFallback}
                          />
                        </td>
                        <td className="py-2 text-gray-500">
                          {item.reason ?? copy.noReason}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  href,
  highlight,
}: {
  label: string;
  value: number;
  href?: string;
  highlight?: boolean;
}) {
  /* Figma 9:25 Stat Card: r10 (rounded-card), p20 (p-5), value 28px */
  const inner = (
    <div
      className={`rounded-card border p-5 shadow-sm transition ${
        highlight
          ? "border-amber-300 bg-amber-50"
          : "border-gray-200 bg-white hover:border-blue-200 hover:bg-blue-50"
      }`}
    >
      <div className="text-xs font-medium text-gray-500">{label}</div>
      <div
        className={`mt-1 text-[28px] font-bold leading-none ${
          highlight ? "text-amber-700" : "text-gray-900"
        }`}
      >
        {value}
      </div>
    </div>
  );

  if (href) {
    return (
      <Link to={href} className="block">
        {inner}
      </Link>
    );
  }
  return inner;
}

const IMPORT_STATUS_TONE: Record<string, BadgeTone> = {
  RECEIVED: "brand",
  PARSING: "indigo",
  VALIDATED: "info",
  STAGED: "warning",
  APPLIED: "success",
  FAILED: "danger",
  CANCELLED: "neutral",
};

const IMPORT_STATUS_LABEL: Record<string, Record<"vi" | "en", string>> = {
  RECEIVED: { vi: "Đã tiếp nhận", en: "Received" },
  PARSING: { vi: "Đang phân tích", en: "Parsing" },
  VALIDATED: { vi: "Đã kiểm tra", en: "Validated" },
  STAGED: { vi: "Chờ áp dụng", en: "Awaiting apply" },
  APPLIED: { vi: "Đã áp dụng", en: "Applied" },
  FAILED: { vi: "Thất bại", en: "Failed" },
  CANCELLED: { vi: "Đã hủy", en: "Cancelled" },
};

function ImportStatusBadge({ status, locale }: { status: string; locale: "vi" | "en" }) {
  const label = IMPORT_STATUS_LABEL[status]?.[locale] ?? status;
  return <Badge tone={IMPORT_STATUS_TONE[status] ?? "neutral"} className="!rounded-[5px]">{label}</Badge>;
}
