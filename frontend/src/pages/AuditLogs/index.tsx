import { useCallback, useEffect, useRef, useState } from "react";
import { getAuditLogs } from "../../api/audits";
import { getApiErrorMessage } from "../../api/errors";
import { useI18n } from "../../i18n";
import { AuditActorType, AuditListItem, AuditListResponse } from "../../types/audit";

const PAGE_SIZES = [20, 50, 100] as const;
const DEFAULT_PAGE_SIZE = 50;

interface FilterForm {
  action: string;
  entity_type: string;
  actor_type: AuditActorType | "";
  date_from: string;
  date_to: string;
}

interface AppliedFilters {
  action: string;
  entity_type: string;
  actor_type: AuditActorType | "";
  date_from: string;
  date_to: string;
  page: number;
  page_size: number;
}

const EMPTY_FORM: FilterForm = {
  action: "",
  entity_type: "",
  actor_type: "",
  date_from: "",
  date_to: "",
};

function datetimeLocalToIso(value: string): string | undefined {
  if (!value) return undefined;
  const d = new Date(value);
  if (isNaN(d.getTime())) return undefined;
  return d.toISOString();
}

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
  return <span className="italic text-gray-500">{item.actor_service ?? systemFallback}</span>;
}

export default function AuditLogsPage() {
  const { t } = useI18n();
  const copy = t.auditLogs;

  const [form, setForm] = useState<FilterForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [applied, setApplied] = useState<AppliedFilters>({
    ...EMPTY_FORM,
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
  });

  const [response, setResponse] = useState<AuditListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const hasLoadedRef = useRef(false);

  const fetchLogs = useCallback(
    (filters: AppliedFilters) => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      setError(null);
      setLoading(true);

      const dateFrom = datetimeLocalToIso(filters.date_from);
      const dateTo = datetimeLocalToIso(filters.date_to);

      void getAuditLogs(
        {
          page: filters.page,
          page_size: filters.page_size,
          action: filters.action || undefined,
          entity_type: filters.entity_type || undefined,
          actor_type: filters.actor_type || undefined,
          date_from: dateFrom,
          date_to: dateTo,
        },
        { signal: controller.signal },
      )
        .then((data) => {
          if (!controller.signal.aborted) {
            setResponse(data);
            hasLoadedRef.current = true;
          }
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setResponse(null);
          setError(getApiErrorMessage(err, copy.loadError));
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setLoading(false);
          }
        });
    },
    [copy.loadError],
  );

  useEffect(() => {
    fetchLogs(applied);
    return () => controllerRef.current?.abort();
  }, [applied, fetchLogs]);

  function handleFormChange(field: keyof FilterForm, value: string) {
    setFormError(null);
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleApply() {
    const dateFrom = datetimeLocalToIso(form.date_from);
    const dateTo = datetimeLocalToIso(form.date_to);
    if (dateFrom && dateTo && new Date(dateFrom) > new Date(dateTo)) {
      setFormError(copy.invalidDateRange);
      return;
    }
    setFormError(null);
    setApplied({
      action: form.action.trim(),
      entity_type: form.entity_type.trim(),
      actor_type: form.actor_type,
      date_from: form.date_from,
      date_to: form.date_to,
      page: 1,
      page_size: applied.page_size,
    });
  }

  function handleClear() {
    setForm(EMPTY_FORM);
    setFormError(null);
    setApplied({ ...EMPTY_FORM, page: 1, page_size: applied.page_size });
  }

  function handleRefresh() {
    fetchLogs(applied);
  }

  function handlePageSizeChange(ps: number) {
    setApplied((prev) => ({ ...prev, page: 1, page_size: ps }));
  }

  function handlePage(next: number) {
    setApplied((prev) => ({ ...prev, page: next }));
  }

  const total = response?.total ?? 0;
  const page = response?.page ?? applied.page;
  const pageSize = response?.page_size ?? applied.page_size;
  const totalPages = Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
  const atFirstPage = page <= 1;
  const atLastPage = page >= totalPages;
  const isFiltered =
    !!applied.action ||
    !!applied.entity_type ||
    !!applied.actor_type ||
    !!applied.date_from ||
    !!applied.date_to;

  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{copy.title}</h1>
          <p className="mt-1 text-sm text-gray-500">{copy.subtitle}</p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
        >
          {copy.refresh}
        </button>
      </div>

      {/* Filters */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-medium text-gray-700">{copy.filtersTitle}</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">{copy.action}</label>
            <input
              type="text"
              value={form.action}
              onChange={(e) => handleFormChange("action", e.target.value)}
              placeholder={copy.actionPlaceholder}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">
              {copy.entityType}
            </label>
            <input
              type="text"
              value={form.entity_type}
              onChange={(e) => handleFormChange("entity_type", e.target.value)}
              placeholder={copy.entityTypePlaceholder}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">
              {copy.actorType}
            </label>
            <select
              value={form.actor_type}
              onChange={(e) =>
                handleFormChange("actor_type", e.target.value as AuditActorType | "")
              }
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">{copy.allActors}</option>
              <option value="USER">{copy.userActor}</option>
              <option value="SYSTEM">{copy.systemActor}</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">{copy.dateFrom}</label>
            <input
              type="datetime-local"
              value={form.date_from}
              onChange={(e) => handleFormChange("date_from", e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">{copy.dateTo}</label>
            <input
              type="datetime-local"
              value={form.date_to}
              onChange={(e) => handleFormChange("date_to", e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        {formError && (
          <p className="mt-2 text-sm text-red-600" role="alert">
            {formError}
          </p>
        )}

        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={handleApply}
            className="inline-flex items-center rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {copy.applyFilters}
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {copy.clearFilters}
          </button>
        </div>
      </div>

      {/* Content */}
      {loading && !hasLoadedRef.current ? (
        <div className="flex items-center justify-center rounded-lg border border-gray-200 bg-white py-20 shadow-sm">
          <span className="text-sm text-gray-500">{t.common.loading}</span>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      ) : response && response.items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 bg-white py-20 shadow-sm">
          <p className="text-base font-medium text-gray-700">
            {isFiltered ? copy.filteredEmptyTitle : copy.emptyTitle}
          </p>
          <p className="mt-1 text-sm text-gray-500">
            {isFiltered ? copy.filteredEmptySubtitle : copy.emptySubtitle}
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          {/* Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colTime}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colEntityType}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colAction}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colActor}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colActorType}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colReason}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(response?.items ?? []).map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-4 py-3 text-gray-700">
                      {formatTimestamp(item.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-700">
                        {item.entity_type}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="rounded bg-blue-50 px-1.5 py-0.5 font-mono text-xs text-blue-700">
                        {item.action}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      <ActorCell
                        item={item}
                        userFallback={copy.userFallback}
                        systemFallback={copy.systemFallback}
                      />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-gray-500">
                      {item.actor_type}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {item.reason ?? copy.noReason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination footer */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <span>
                {copy.page} {page} / {totalPages}
              </span>
              <span className="text-gray-400">·</span>
              <span>
                {total} {copy.records}
              </span>
              <span className="text-gray-400">·</span>
              <select
                value={pageSize}
                onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                disabled={loading}
                className="rounded border border-gray-300 px-2 py-0.5 text-xs"
              >
                {PAGE_SIZES.map((ps) => (
                  <option key={ps} value={ps}>
                    {ps}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handlePage(page - 1)}
                disabled={atFirstPage || loading}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {copy.previousPage}
              </button>
              <button
                type="button"
                onClick={() => handlePage(page + 1)}
                disabled={atLastPage || loading}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {copy.nextPage}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
