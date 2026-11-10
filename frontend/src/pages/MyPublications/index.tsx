import { useMemo, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import Button from "../../components/ui/Button";
import { useI18n } from "../../i18n";
import type { TranslationSchema } from "../../i18n/types";
import type { LecturerPublication } from "../../types/lecturerScopus";
import { distinctValues, FILTER_KEYS, filterPublications, SORT_KEYS, type FilterKey, type PublicationFilters } from "./publicationFilters";
import useMyPublications from "./useMyPublications";
import usePublicationSearch from "./usePublicationSearch";

type Copy = TranslationSchema["myPublications"];
const controlClass = "h-control w-full min-w-0 rounded-control border border-line bg-white px-2.5 text-sm text-ink-body focus:border-line focus:outline-none";
const panelClass = "rounded-card border border-line bg-white shadow-sm";
const tableHeadClass = "border-r border-slate-200/80 px-2.5 py-3.5 text-center font-medium text-slate-700 whitespace-nowrap";
const tableCellClass = "border-r border-b border-slate-100 px-2.5 py-3.5 text-center align-middle";
const detailLinkClass = "inline-flex w-32 items-center justify-center whitespace-nowrap rounded-control border border-slate-300 bg-white px-2.5 py-0.5 text-sm font-bold text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50 hover:text-slate-900 cursor-pointer";
function SelectField({ label, value, onChange, options, all }: {
  label: string; value: string; onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>; all?: string;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5 text-sm font-medium text-ink-muted">
      {label}
      <select className={controlClass} value={value} onChange={(event) => onChange(event.target.value)}>
        {all && <option value="">{all}</option>}
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  );
}

function DetailLink({ publication, copy, children, className = "" }: { publication: LecturerPublication; copy: Copy; children?: ReactNode; className?: string }) {
  return (
    <Link to={`/publications/${encodeURIComponent(publication.eid)}`} state={{ from: "/my-publications" }}
      className={className} aria-label={`${copy.viewDetail}: ${publication.title || publication.eid}`} data-testid="my-publication-detail-link">
      {children || copy.viewDetail}
    </Link>
  );
}

export default function MyPublicationsPage() {
  const { t, locale } = useI18n();
  const copy = t.myPublications;
  const { response, loading, error, notLinked, reload } = useMyPublications(copy.loadError);
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => Object.fromEntries(FILTER_KEYS.map((key) => [key, params.get(key) || ""])) as PublicationFilters, [params]);
  const sort = SORT_KEYS.find((key) => key === params.get("sort")) || "newest";
  const pageSize = [10, 20, 50].find((size) => size === Number(params.get("size"))) || 10;
  const number = (value: number) => new Intl.NumberFormat(locale === "vi" ? "vi-VN" : "en-US").format(value);
  const update = (key: string, value: string) => {
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value); else next.delete(key);
      if (key !== "page") next.delete("page");
      next.delete("view");
      return next;
    }, { replace: true });
  };
  const search = usePublicationSearch(filters.q, (value) => update("q", value));
  const reset = () => {
    search.clear();
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      FILTER_KEYS.forEach((key) => next.delete(key));
      next.delete("page");
      next.delete("sort");
      next.delete("view");
      return next;
    }, { replace: true });
  };
  const activeFilters = FILTER_KEYS.filter((key) => filters[key].trim());
  const canReset = activeFilters.length > 0 || search.draft.length > 0 || sort !== "newest";
  const filtered = useMemo(() => filterPublications(response?.items || [], filters, sort, locale), [response, filters, sort, locale]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const requestedPage = Number(params.get("page"));
  const page = Math.min(totalPages, Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1);
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);
  const values = (field: Parameters<typeof distinctValues>[1]) => distinctValues(response?.items || [], field, locale).map((value) => ({ value, label: value }));
  const yearBuckets = Object.entries(response?.aggregates.publication_count_by_year || {}).sort(([a], [b]) => Number(b) - Number(a));
  const yearOptions = yearBuckets.map(([year]) => ({ value: year, label: year }));
  if (response?.aggregates.unknown_year_count) yearOptions.push({ value: "unknown", label: copy.unknownYear });
  const labels: Record<FilterKey, string> = { q: copy.search, year: copy.year, type: copy.documentType, source: copy.sourceTitle, stage: copy.stage, access: copy.openAccess, citations: copy.citationStatus, doi: copy.doiStatus, author: copy.authorRole };
  const filterField = (key: FilterKey, options: Array<{ value: string; label: string }>) => <SelectField label={labels[key]} value={filters[key]} onChange={(value) => update(key, value)} options={options} all={copy.all} />;

  return (
    <div className="my-publications-page app-page-container min-w-0 space-y-4 sm:space-y-5">
      {loading && <div role="status" aria-label={copy.loading} className="space-y-5">
        <p className="text-sm text-ink-muted">{copy.loading}</p>
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">{[0, 1, 2, 3].map((key) => <div key={key} className={`${panelClass} h-28 animate-pulse`} />)}</div>
        <div className={`${panelClass} h-44 animate-pulse`} />
        <div className={`${panelClass} h-80 animate-pulse`} />
      </div>}
      {!loading && (error || notLinked) && <div className={`${panelClass} p-6`} role="alert">
        <h2 className="font-semibold text-ink">{notLinked ? copy.notLinkedTitle : copy.loadError}</h2>
        <p className="mt-2 text-sm text-ink-muted">{notLinked ? copy.notLinkedMessage : error}</p>
        <Button variant="secondary" className="mt-4" onClick={() => void reload()}>{copy.retry}</Button>
      </div>}
      {!loading && response && <>
        <section aria-label={copy.summaryTitle} className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {([
            [copy.totalPublications, response.aggregates.total_publications],
            [copy.knownCitations, response.aggregates.known_citation_sum],
            [copy.unknownCitations, response.aggregates.citation_unknown_publication_count],
            [copy.approvedIdentities, response.aggregates.approved_identity_count],
          ] as const).map(([label, value]) => <div key={label} className={`${panelClass} flex flex-col justify-between gap-2 p-4 sm:p-5`}>
            <p className="text-sm font-medium leading-6 text-ink-muted">{label}</p>
            <p className="text-2xl font-bold tabular-nums text-ink">{number(value)}</p>
          </div>)}
        </section>

        <div className="grid min-w-0 items-start gap-4 lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[250px_minmax(0,1fr)_190px]">
          <section className={`${panelClass} min-w-0 space-y-3.5 p-3.5 lg:sticky lg:top-0 lg:max-h-[calc(100dvh-8rem)] lg:overflow-y-auto`} aria-label={copy.filterTitle}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-ink">{copy.filterTitle}</h2>
              <Button variant="secondary" className="!min-w-0" onClick={reset} disabled={!canReset}>{copy.reset}</Button>
            </div>
            <label className="flex min-w-0 flex-col gap-1.5 text-sm font-medium text-ink-muted">
              {copy.search}
              <input type="text" role="searchbox" {...search.inputProps}
                placeholder={copy.searchPlaceholder} title={copy.searchPlaceholder} className={`${controlClass} bg-slate-50/60`} />
            </label>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              {filterField("year", yearOptions)}
              {filterField("type", values("document_type"))}
              {filterField("source", values("source_title"))}
              {filterField("stage", values("publication_stage"))}
              {filterField("access", values("open_access_status"))}
              {filterField("citations", [{ value: "cited", label: copy.cited }, { value: "uncited", label: copy.uncited }, { value: "unknown", label: copy.citationUnknown }])}
              {filterField("doi", [{ value: "present", label: copy.hasDoi }, { value: "missing", label: copy.missingDoi }])}
              {filterField("author", [{ value: "first", label: copy.firstAuthor }, { value: "other", label: copy.otherAuthor }])}
              <SelectField label={copy.sort} value={sort} onChange={(value) => update("sort", value)} options={SORT_KEYS.map((value) => ({ value, label: copy[value] }))} />
            </div>
          </section>

          <section className="min-w-0 overflow-hidden rounded-card border border-slate-200/80 bg-white" aria-label={copy.publicationsTitle}>
            <div className="relative overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">{copy.publicationsTitle}</caption>
                <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
                  <tr>
                    <th scope="col" className={`${tableHeadClass} w-14`}>{copy.serialNumber}</th>
                    <th scope="col" className={`${tableHeadClass} !text-left`}>{copy.publicationsTitle}</th>
                    {[copy.year, copy.documentType, copy.citations].map((label) => <th key={label} scope="col" className={tableHeadClass}>{label}</th>)}
                    <th scope="col" className="sticky right-0 z-[1] w-44 whitespace-nowrap border-l border-slate-200/80 bg-slate-50 px-2.5 py-3.5 text-center font-medium text-slate-700">{t.common.actions}</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.length === 0 ? <tr>
                    <td colSpan={6} className="px-5 py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center justify-center gap-1.5" role="status">
                        <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-control border border-slate-200/80 bg-slate-100/80 text-slate-400">
                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <h3 className="text-sm font-bold text-slate-700">{response.items.length ? copy.noResultsTitle : copy.noPublicationsTitle}</h3>
                        <p className="max-w-lg text-sm text-slate-400">{response.items.length ? copy.noResultsMessage : copy.noPublicationsMessage}</p>
                      </div>
                    </td>
                  </tr> : visible.map((item, index) => <tr key={item.eid} className="transition-colors hover:bg-slate-50/50">
                    <td className={`${tableCellClass} w-14 font-medium tabular-nums text-slate-600`}>{number((page - 1) * pageSize + index + 1)}</td>
                    <td className="min-w-[280px] max-w-md border-r border-b border-slate-100 px-2.5 py-3.5 align-middle">
                      <DetailLink publication={item} copy={copy} className="block break-words font-medium text-slate-800 hover:text-brand">{item.title || copy.notAvailable}</DetailLink>
                      <p className="text-slate-500">{item.source_title || copy.notAvailable}</p>
                      <p className="break-all text-slate-400">{copy.doi}: {item.doi || copy.notAvailable}</p>
                      <p className="break-all font-mono text-slate-400">{copy.eid}: {item.eid}</p>
                    </td>
                    <td className={`${tableCellClass} whitespace-nowrap font-medium text-slate-600`}>{item.year ?? copy.unknownYear}</td>
                    <td className={`${tableCellClass} whitespace-nowrap font-medium text-slate-700`}>{item.document_type || copy.notAvailable}</td>
                    <td className={`${tableCellClass} font-medium tabular-nums text-slate-800`} title={item.cited_by_count === null ? copy.citationUnknown : undefined}>{item.cited_by_count === null ? "—" : number(item.cited_by_count)}</td>
                    <td className="sticky right-0 z-[1] whitespace-nowrap border-l border-b border-slate-100 bg-white px-2.5 py-3.5 text-center align-middle">
                      <DetailLink publication={item} copy={copy} className={detailLinkClass} />
                    </td>
                  </tr>)}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-sm text-slate-500">
              <div className="flex flex-wrap items-center gap-3">
                <span role="status">{copy.showing.split(/(\{shown\}|\{total\})/g).map((part, index) => part === "{shown}" ? <strong key={index}>{number(visible.length)}</strong> : part === "{total}" ? <strong key={index}>{number(filtered.length)}</strong> : part)}</span>
                <label className="flex items-center gap-1.5 border-l border-slate-200 pl-2">
                  {t.common.showingCount}:
                  <select aria-label={copy.pageSize} value={pageSize} onChange={(event) => update("size", event.target.value)} className={`${controlClass} !h-7 !w-auto !px-1.5 font-semibold`}>
                    {[10, 20, 50].map((size) => <option key={size} value={size}>{copy.perPage.replace("{count}", number(size))}</option>)}
                  </select>
                </label>
              </div>
              <nav className="flex items-center gap-1.5" aria-label={copy.pagination}>
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => update("page", String(page - 1))}>{copy.previous}</Button>
                <span className="px-0.5 text-slate-400">{copy.pageLabel}</span>
                <input key={`${page}-${totalPages}`} type="number" aria-label={copy.goToPage} min={1} max={totalPages} defaultValue={page} disabled={filtered.length === 0}
                  onBlur={(event) => {
                    const requested = Number(event.currentTarget.value);
                    const target = Number.isFinite(requested) && event.currentTarget.value.trim() ? Math.max(1, Math.min(totalPages, Math.trunc(requested))) : page;
                    event.currentTarget.value = String(target);
                    if (target !== page) update("page", String(target));
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") event.currentTarget.value = String(page);
                    if (event.key === "Enter" || event.key === "Escape") event.currentTarget.blur();
                  }}
                  className={`${controlClass} !h-8 !w-14 text-center font-bold disabled:cursor-not-allowed disabled:opacity-50 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none`} />
                <span className="whitespace-nowrap text-slate-400" aria-live="polite">/ <strong className="text-slate-600">{number(totalPages)}</strong></span>
                <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => update("page", String(page + 1))}>{copy.next}</Button>
              </nav>
            </div>
          </section>

          <aside className={`${panelClass} min-w-0 p-3 lg:col-start-2 xl:sticky xl:top-0 xl:col-start-auto`}>
            <h2 className="text-sm font-semibold text-ink">{copy.yearTitle}</h2>
            <div className="mt-2 space-y-0.5" role="group" aria-label={copy.yearTitle}>
              {[...yearBuckets, ...(response.aggregates.unknown_year_count ? [["unknown", response.aggregates.unknown_year_count] as [string, number]] : [])].map(([year, count]) => <button key={year} type="button" aria-pressed={filters.year === year}
                onClick={() => update("year", filters.year === year ? "" : year)} className={`w-full rounded-control px-1.5 py-1.5 text-left text-sm ${filters.year === year ? "bg-brand-subtle text-brand" : "text-ink-muted hover:bg-slate-50"}`}>
                <span className="mb-1.5 flex justify-between gap-2"><span>{year === "unknown" ? copy.unknownYear : year}</span><span className="font-semibold tabular-nums text-ink">{number(count)}</span></span>
                <span className="block h-1.5 overflow-hidden rounded-control bg-slate-100"><span className={`block h-full rounded-control ${filters.year === year ? "bg-brand" : "bg-brand/40"}`} style={{ width: `${count / Math.max(1, ...yearBuckets.map(([, value]) => value), response.aggregates.unknown_year_count) * 100}%` }} /></span>
              </button>)}
              {!yearOptions.length && <p className="text-sm text-ink-muted">{copy.noYearData}</p>}
            </div>
          </aside>
        </div>
      </>}
    </div>
  );
}
