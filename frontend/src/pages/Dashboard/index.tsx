import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getDashboardSummary } from "../../api/dashboard";
import { getApiErrorMessage } from "../../api/errors";
import { useI18n } from "../../i18n";
import {
  DashboardIdentityStatus,
  DashboardSummary,
} from "../../types/dashboard";
import { AuditListItem } from "../../types/audit";

function formatTimestamp(raw: string): string {
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  return d.toLocaleString();
}

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
  const { t } = useI18n();
  const copy = t.dashboard;

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

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

  return (
    <div className="app-page-container space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{copy.title}</h1>
          <p className="mt-1 text-sm text-gray-500">{copy.subtitle}</p>
        </div>
        <button
          onClick={fetchSummary}
          disabled={loading}
          className="flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? (
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
          ) : null}
          {copy.refresh}
        </button>
      </div>

      {/* Error state */}
      {error && !loading && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
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
                className="h-24 animate-pulse rounded-lg border border-gray-200 bg-gray-100"
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

          {/* Identity status counts — always all 4 statuses */}
          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-base font-semibold text-gray-800">
              {copy.identityTitle}
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {IDENTITY_STATUSES.map((status) => (
                <div
                  key={status}
                  className={`rounded-md border px-4 py-3 ${IDENTITY_COLORS[status]}`}
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

          {/* Latest Scopus import */}
          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
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
                    <ImportStatusBadge status={summary.latest_scopus_import.status} />
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
          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
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
                        <td className="py-2 pr-4 text-gray-700">{item.entity_type}</td>
                        <td className="py-2 pr-4 font-mono text-xs text-gray-700">
                          {item.action}
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
  const inner = (
    <div
      className={`rounded-lg border p-4 shadow-sm transition ${
        highlight
          ? "border-amber-300 bg-amber-50"
          : "border-gray-200 bg-white hover:border-blue-200 hover:bg-blue-50"
      }`}
    >
      <div className="text-xs font-medium text-gray-500">{label}</div>
      <div
        className={`mt-1 text-3xl font-bold ${
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

const IMPORT_STATUS_COLORS: Record<string, string> = {
  RECEIVED: "bg-blue-100 text-blue-700",
  PARSING: "bg-indigo-100 text-indigo-700",
  VALIDATED: "bg-cyan-100 text-cyan-700",
  STAGED: "bg-yellow-100 text-yellow-700",
  APPLIED: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
  CANCELLED: "bg-gray-100 text-gray-600",
};

function ImportStatusBadge({ status }: { status: string }) {
  const color = IMPORT_STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${color}`}>
      {status}
    </span>
  );
}
