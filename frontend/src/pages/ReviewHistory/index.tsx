import { useCallback, useEffect, useRef, useState } from "react";
import { getReviewHistory } from "../../api/reviews";
import { getApiErrorMessage } from "../../api/errors";
import { useI18n } from "../../i18n";
import { ReviewHistoryAction, ReviewHistoryItem, ReviewHistoryResponse } from "../../types/review";

const PAGE_SIZES = [20, 50, 100] as const;
const DEFAULT_PAGE_SIZE = 20;

interface FilterForm {
  action: ReviewHistoryAction | "";
  date_from: string;
  date_to: string;
}

interface AppliedFilters {
  action: ReviewHistoryAction | "";
  date_from: string;
  date_to: string;
  page: number;
  page_size: number;
}

const EMPTY_FORM: FilterForm = {
  action: "",
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

function ActionBadge({ action }: { action: ReviewHistoryAction }) {
  const colors: Record<ReviewHistoryAction, string> = {
    ACCEPT: "bg-green-50 text-green-700",
    REJECT: "bg-red-50 text-red-700",
    REOPEN: "bg-yellow-50 text-yellow-700",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 font-mono text-xs ${colors[action]}`}>
      {action}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-700">
      {status}
    </span>
  );
}

function ReviewHistoryRow({ item, copy }: { item: ReviewHistoryItem; copy: Record<string, string> }) {
  return (
    <tr className="hover:bg-gray-50">
      <td className="whitespace-nowrap px-4 py-3 text-gray-700">
        {formatTimestamp(item.created_at)}
      </td>
      <td className="whitespace-nowrap px-4 py-3">
        <ActionBadge action={item.action} />
      </td>
      <td className="whitespace-nowrap px-4 py-3">
        <div className="flex items-center gap-1">
          <StatusBadge status={item.from_status} />
          <span className="text-gray-400">→</span>
          <StatusBadge status={item.to_status} />
        </div>
      </td>
      <td className="px-4 py-3 text-gray-700">
        {item.lecturer_full_name ?? copy.unknown}
        {item.lecturer_staff_code && (
          <span className="ml-1.5 text-xs text-gray-400">({item.lecturer_staff_code})</span>
        )}
      </td>
      <td className="px-4 py-3 text-gray-700">
        {item.scopus_author_preferred_name ?? copy.unknown}
        {item.scopus_author_scopus_id && (
          <span className="ml-1.5 text-xs text-gray-400">{item.scopus_author_scopus_id}</span>
        )}
      </td>
      <td className="px-4 py-3 text-gray-700">
        {item.reviewer_display_name ?? copy.unknownReviewer}
      </td>
      <td className="px-4 py-3 text-gray-600 max-w-xs truncate">
        {item.reason ?? copy.noReason}
      </td>
    </tr>
  );
}

export default function ReviewHistoryPage() {
  const { t } = useI18n();
  const copy = t.reviewHistory;

  const [form, setForm] = useState<FilterForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [applied, setApplied] = useState<AppliedFilters>({
    ...EMPTY_FORM,
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
  });

  const [response, setResponse] = useState<ReviewHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const hasLoadedRef = useRef(false);

  const fetchHistory = useCallback(
    (filters: AppliedFilters) => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      setError(null);
      setLoading(true);

      const dateFrom = datetimeLocalToIso(filters.date_from);
      const dateTo = datetimeLocalToIso(filters.date_to);

      void getReviewHistory(
        {
          page: filters.page,
          page_size: filters.page_size,
          action: filters.action || undefined,
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
    fetchHistory(applied);
    return () => controllerRef.current?.abort();
  }, [applied, fetchHistory]);

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
      action: form.action,
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
    fetchHistory(applied);
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
  const isFiltered = !!applied.action || !!applied.date_from || !!applied.date_to;

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
            <select
              value={form.action}
              onChange={(e) => handleFormChange("action", e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">{copy.allActions}</option>
              <option value="ACCEPT">{copy.actionAccept}</option>
              <option value="REJECT">{copy.actionReject}</option>
              <option value="REOPEN">{copy.actionReopen}</option>
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
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colTime}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colAction}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colTransition}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colLecturer}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colScopusAuthor}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colReviewer}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">
                    {copy.colReason}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {response?.items.map((item: ReviewHistoryItem) => (
                  <ReviewHistoryRow
                    key={item.id}
                    item={item}
                    copy={copy as unknown as Record<string, string>}
                  />
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
