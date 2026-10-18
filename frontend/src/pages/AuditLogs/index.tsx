import { useCallback, useEffect, useRef, useState } from "react";
import { getAuditLogs } from "../../api/audits";
import { getApiErrorMessage } from "../../api/errors";
import { useI18n } from "../../i18n";
import { buttonClass } from "../../components/ui/Button";
import { PageHeader } from "../../components/ui/PageHeader";
import { AuditActorType, AuditListItem, AuditListResponse } from "../../types/audit";
import { formatTimestamp } from "../../utils/dateTime";

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
    return <span className="text-slate-700">{item.actor_display_name ?? userFallback}</span>;
  }
  return <span className="italic text-slate-400">{item.actor_service ?? systemFallback}</span>;
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

  const hasAnyFormInput =
    !!form.action || !!form.entity_type || !!form.actor_type || !!form.date_from || !!form.date_to;

  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* ── Page Header — R4-A pilot (P11.5) ────────────────────────────── */}
      <PageHeader
        title={copy.title}
        subtitle={copy.subtitle}
        action={
          <button
            type="button"
            onClick={handleRefresh}
            disabled={loading}
            className={buttonClass("secondary")}
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {copy.refresh}
          </button>
        }
      />

      {/* ── Filter Bar ──────────────────────────────────────────────────── */}
      <div className="rounded-[5px] border border-slate-200/80 bg-white p-3.5 shadow-xs space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          {/* Action text filter */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">{copy.action}</label>
            <input
              type="text"
              value={form.action}
              onChange={(e) => handleFormChange("action", e.target.value)}
              placeholder={copy.actionPlaceholder}
              className="h-8 w-36 rounded-[5px] border border-slate-200 bg-white px-2.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
            />
          </div>

          {/* Entity type text filter */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">{copy.entityType}</label>
            <input
              type="text"
              value={form.entity_type}
              onChange={(e) => handleFormChange("entity_type", e.target.value)}
              placeholder={copy.entityTypePlaceholder}
              className="h-8 w-40 rounded-[5px] border border-slate-200 bg-white px-2.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
            />
          </div>

          {/* Actor type select */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">{copy.actorType}</label>
            <select
              value={form.actor_type}
              onChange={(e) => handleFormChange("actor_type", e.target.value as AuditActorType | "")}
              className="h-8 rounded-[5px] border border-slate-200 bg-white px-2.5 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
            >
              <option value="">{copy.allActors}</option>
              <option value="USER">{copy.userActor}</option>
              <option value="SYSTEM">{copy.systemActor}</option>
            </select>
          </div>

          {/* Date from */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">{copy.dateFrom}</label>
            <input
              type="datetime-local"
              value={form.date_from}
              onChange={(e) => handleFormChange("date_from", e.target.value)}
              className="h-8 rounded-[5px] border border-slate-200 bg-white px-2.5 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
            />
          </div>

          {/* Date to */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">{copy.dateTo}</label>
            <input
              type="datetime-local"
              value={form.date_to}
              onChange={(e) => handleFormChange("date_to", e.target.value)}
              className="h-8 rounded-[5px] border border-slate-200 bg-white px-2.5 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
            />
          </div>

          {/* Buttons */}
          <div className="ml-auto flex items-end gap-2">
            <button
              type="button"
              onClick={handleApply}
              className={buttonClass("primary", "sm")}
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
              {copy.applyFilters}
            </button>
            <button
              type="button"
              onClick={handleClear}
              disabled={!isFiltered && !hasAnyFormInput}
              className={buttonClass("secondary", "sm")}
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {copy.clearFilters}
            </button>
          </div>
        </div>

        {formError && (
          <p className="text-xs font-medium text-rose-600" role="alert">
            {formError}
          </p>
        )}
      </div>

      {/* ── Content ──────────────────────────────────────────────────────── */}
      {loading && !hasLoadedRef.current ? (
        <div className="flex items-center justify-center rounded-[5px] border border-slate-200/80 bg-white py-20 shadow-xs">
          <div className="flex flex-col items-center gap-2">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
            <span className="text-xs text-slate-400">{t.common.loading}</span>
          </div>
        </div>
      ) : error ? (
        <div className="rounded-[5px] border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 flex items-start gap-2.5">
          <svg className="h-5 w-5 shrink-0 text-rose-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div className="flex flex-col gap-1.5">
            <span className="font-semibold">{error}</span>
            <button
              type="button"
              onClick={handleRefresh}
              className={`${buttonClass("secondary", "sm")} self-start`}
            >
              {copy.retry}
            </button>
          </div>
        </div>
      ) : response && response.items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-[5px] border border-slate-200/80 bg-white py-20 shadow-xs">
          <svg className="h-8 w-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <p className="mt-2 text-sm font-semibold text-slate-600">
            {isFiltered ? copy.filteredEmptyTitle : copy.emptyTitle}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {isFiltered ? copy.filteredEmptySubtitle : copy.emptySubtitle}
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
          <div className="relative overflow-x-auto">
            <table className="w-full text-left text-xs" aria-busy={loading}>
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
                <tr>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold">{copy.colTime}</th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold">{copy.colEntityType}</th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold">{copy.colAction}</th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold">{copy.colActor}</th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold">{copy.colActorType}</th>
                  <th className="px-4 py-3 font-semibold">{copy.colReason}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(response?.items ?? []).map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                      {formatTimestamp(item.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="inline-block rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600 ring-1 ring-slate-200">
                        {item.entity_type}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="inline-block rounded bg-indigo-50 px-1.5 py-0.5 font-mono text-[11px] text-indigo-700 ring-1 ring-indigo-200">
                        {item.action}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs">
                      <ActorCell
                        item={item}
                        userFallback={copy.userFallback}
                        systemFallback={copy.systemFallback}
                      />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                      {item.actor_type}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600 max-w-xs truncate">
                      {item.reason ?? copy.noReason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ── Footer: count + pagination ───────────────────────────────── */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-2.5 text-[11px] text-slate-500">
            <div className="flex items-center gap-3">
              <span>
                {copy.page} <strong className="text-slate-700">{page}</strong> / {totalPages}
                <span className="mx-2 text-slate-300">·</span>
                <strong className="text-slate-700">{total}</strong> {copy.records}
              </span>
              <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
                <select
                  value={pageSize}
                  onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                  disabled={loading}
                  className="h-6 rounded-[5px] border border-slate-200 bg-white px-1.5 text-[11px] font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer"
                >
                  {PAGE_SIZES.map((ps) => (
                    <option key={ps} value={ps}>{ps}</option>
                  ))}
                </select>
              </div>
            </div>

            <nav className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handlePage(page - 1)}
                disabled={atFirstPage || loading}
                className={buttonClass("secondary", "sm")}
              >
                {copy.previousPage}
              </button>
              <button
                type="button"
                onClick={() => handlePage(page + 1)}
                disabled={atLastPage || loading}
                className={buttonClass("secondary", "sm")}
              >
                {copy.nextPage}
              </button>
            </nav>
          </div>
        </div>
      )}
    </div>
  );
}
