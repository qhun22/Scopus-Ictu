import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { getMyApprovedScopusIdentities } from "../../api/lecturerScopus";
import Button from "../../components/ui/Button";
import useDebouncedSearch from "../../hooks/useDebouncedSearch";
import { useI18n } from "../../i18n";
import type { TranslationSchema } from "../../i18n/types";
import type { ApprovedScopusIdentity } from "../../types/lecturerScopus";
import { filterIdentities } from "./identityFilters";

type IdentityCopy = TranslationSchema["scopusIdentity"];
const panelClass = "rounded-card border border-slate-200/80 bg-white";
const controlClass = "h-control min-w-0 rounded-control border border-line bg-white px-2.5 text-sm text-ink-body focus:border-line focus:outline-none";
const headerClass = "whitespace-nowrap border-r border-slate-200/80 px-2.5 py-3.5 text-center font-medium text-slate-700";
const cellClass = "border-r border-b border-slate-100 px-2.5 py-3.5 text-center align-middle";
const badgeClass = "inline-flex h-badge shrink-0 items-center justify-center whitespace-nowrap rounded-control border bg-white px-2.5 text-center text-sm font-bold leading-none";
const tableBadgeClass = `${badgeClass} w-32 border-emerald-400 text-emerald-700 hover:bg-emerald-50`;
const detailButtonClass = "inline-flex w-32 items-center justify-center whitespace-nowrap rounded-control border border-slate-300 bg-white px-2.5 py-0.5 text-sm font-bold text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50 hover:text-slate-900 cursor-pointer";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const pad = (number: number) => String(number).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())} ${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`;
}

function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 px-5 py-12 text-center" role="status">
      <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-control border border-slate-200/80 bg-slate-100/80 text-slate-400">
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12l2 2 4-4M12 3l8 4v5c0 5-8 9-8 9s-8-4-8-9V7l8-4z" />
        </svg>
      </div>
      <h2 className="text-sm font-bold text-slate-700">{title}</h2>
      <p className="max-w-lg text-sm leading-6 text-slate-400">{message}</p>
    </div>
  );
}

function IdentityDetails({ identity, copy }: { identity: ApprovedScopusIdentity; copy: IdentityCopy }) {
  return (
    <div id={`identity-details-${identity.identity_id}`} className="space-y-5 bg-slate-50/50 p-4 text-left sm:p-5">
      <section>
        <h3 className="text-sm font-semibold text-slate-800">{copy.variants}</h3>
        {identity.name_variants.length ? <div className="mt-2 flex flex-wrap gap-2">
          {[...new Set(identity.name_variants)].map((variant) => <span key={variant} title={variant} className={`${badgeClass} max-w-full border-slate-200 text-slate-700`}><span className="min-w-0 truncate">{variant}</span></span>)}
        </div> : <p className="mt-2 text-sm text-slate-500">{copy.noVariants}</p>}
      </section>
      <section>
        <h3 className="mb-3 text-sm font-semibold text-slate-800">{copy.evidence}</h3>
        <div className={`${panelClass} overflow-x-auto`}>
          <table className="w-full min-w-[560px] text-left text-sm">
            <caption className="sr-only">{copy.evidence}</caption>
            <thead className="border-b border-slate-200/80 bg-slate-50/70">
              <tr>{[copy.evidenceType, copy.direction, copy.recordedAt].map((label) => <th key={label} scope="col" className={`${headerClass} last:border-r-0`}>{label}</th>)}</tr>
            </thead>
            <tbody>{identity.evidence.length ? identity.evidence.map((item, index) => <tr key={`${item.evidence_type}-${item.created_at}-${index}`}>
              <td className="border-r border-b border-slate-100 px-2.5 py-3.5 text-slate-700">{copy.evidenceTypes[item.evidence_type as keyof IdentityCopy["evidenceTypes"]] || item.evidence_type || copy.notAvailable}</td>
              <td className={cellClass}>
                <span className={`${badgeClass} ${item.direction === "SUPPORTS" ? "border-emerald-300 text-emerald-700" : item.direction === "CONTRADICTS" ? "border-rose-300 text-rose-700" : "border-slate-300 text-slate-700"}`}>
                  {item.direction === "SUPPORTS" ? copy.supports : item.direction === "CONTRADICTS" ? copy.contradicts : item.direction || copy.notAvailable}
                </span>
              </td>
              <td className="whitespace-nowrap border-b border-slate-100 px-2.5 py-3.5 text-center text-slate-600">{formatDate(item.created_at)}</td>
            </tr>) : <tr><td colSpan={3} className="px-4 py-8 text-center text-sm text-slate-500">{copy.noEvidence}</td></tr>}</tbody>
          </table>
        </div>
      </section>
      <dl className="grid gap-3 border-t border-slate-200/80 pt-4 text-sm sm:grid-cols-2">
        <div><dt className="text-slate-500">{copy.createdAt}</dt><dd className="mt-1 text-slate-700">{formatDate(identity.created_at)}</dd></div>
        <div><dt className="text-slate-500">{copy.updatedAt}</dt><dd className="mt-1 text-slate-700">{formatDate(identity.updated_at)}</dd></div>
      </dl>
    </div>
  );
}

export default function IdentityPage() {
  const { t, locale } = useI18n();
  const copy = t.scopusIdentity;
  const [identities, setIdentities] = useState<ApprovedScopusIdentity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const [params, setParams] = useSearchParams();
  const query = params.get("q") || "";
  const kind = ["primary", "other"].includes(params.get("kind") || "") ? params.get("kind")! : "";
  const pageSize = [10, 20, 50].find((size) => size === Number(params.get("size"))) || 10;
  const number = (value: number) => new Intl.NumberFormat(locale === "vi" ? "vi-VN" : "en-US").format(value);

  const loadIdentities = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError(null);
    setExpandedId(null);
    void getMyApprovedScopusIdentities({ signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setIdentities(data); })
      .catch((requestError: unknown) => { if (!controller.signal.aborted) setError(requestError); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
  }, []);

  useEffect(() => {
    loadIdentities();
    return () => controllerRef.current?.abort();
  }, [loadIdentities]);

  const update = (key: string, value: string) => {
    setExpandedId(null);
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value); else next.delete(key);
      if (key !== "page") next.delete("page");
      return next;
    }, { replace: true });
  };
  const search = useDebouncedSearch(query, (value) => update("q", value));
  const reset = () => {
    search.clear();
    setExpandedId(null);
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      ["q", "kind", "page"].forEach((key) => next.delete(key));
      return next;
    }, { replace: true });
  };
  const filtered = useMemo(() => filterIdentities(identities, query, kind), [identities, query, kind]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const requestedPage = Number(params.get("page"));
  const page = Math.min(totalPages, Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1);
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);
  const mainIdentity = identities.find((identity) => identity.is_primary);
  const notLinked = error instanceof ApiError && error.code === "LECTURER_NOT_LINKED";

  return (
    <div className="scopus-identity-page app-page-container min-w-0 space-y-4 sm:space-y-5">
      {loading ? <div className="space-y-5" role="status" aria-label={copy.loading}>
        <p className="text-sm text-slate-500">{copy.loading}</p>
        <div className="grid gap-3 sm:grid-cols-3">{[0, 1, 2].map((key) => <div key={key} className={`${panelClass} h-28 animate-pulse`} />)}</div>
        <div className={`${panelClass} h-20 animate-pulse`} />
        <div className={`${panelClass} h-64 animate-pulse`} />
      </div> : error ? <div className="rounded-card border border-rose-200 bg-rose-50 p-5" role="alert">
        <h2 className="text-sm font-semibold text-rose-900">{notLinked ? copy.notLinkedTitle : copy.loadError}</h2>
        <p className="mt-2 text-sm text-rose-800">{notLinked ? copy.notLinked : getApiErrorMessage(error, copy.loadError)}</p>
        <Button variant="secondary" className="mt-4 !text-sm" onClick={loadIdentities}>{copy.retry}</Button>
      </div> : <>
        <section aria-label={copy.overview} className="grid gap-3 sm:grid-cols-3">
          {[
            [copy.approvedCount, number(identities.length)],
            [copy.primaryId, mainIdentity?.scopus_id || copy.notChosen],
            [copy.evidenceCount, number(identities.reduce((count, identity) => count + identity.evidence.length, 0))],
          ].map(([label, value]) => <div key={label} className={`${panelClass} flex flex-col justify-between gap-2 p-4 shadow-sm sm:p-5`}>
            <p className="text-sm font-medium leading-6 text-slate-500">{label}</p>
            <p className="break-all text-2xl font-bold tabular-nums text-slate-800">{value}</p>
          </div>)}
        </section>

        <section className={`${panelClass} flex flex-col gap-3 p-3.5 sm:flex-row sm:items-center sm:justify-between`} aria-label={copy.search}>
          <label className="min-w-0 flex-1">
            <span className="sr-only">{copy.search}</span>
            <input type="text" role="searchbox" {...search.inputProps} placeholder={copy.searchPlaceholder} className={`${controlClass} w-full bg-slate-50`} />
          </label>
          <div className="flex shrink-0 items-center gap-2">
            <label className="min-w-0 flex-1">
              <span className="sr-only">{copy.identityType}</span>
              <select className={`${controlClass} w-full bg-slate-50 font-semibold sm:w-auto`} value={kind} onChange={(event) => update("kind", event.target.value)}>
                <option value="">{copy.allIdentities}</option><option value="primary">{copy.primaryId}</option><option value="other">{copy.otherIdentities}</option>
              </select>
            </label>
            <Button variant="secondary" disabled={!query && !kind && !search.draft} onClick={reset}>{copy.reset}</Button>
          </div>
        </section>

        <section className={`${panelClass} min-w-0 overflow-hidden`} aria-label={copy.list}>
          <div className="relative overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">{copy.list}</caption>
              <thead className="border-b border-slate-200/80 bg-slate-50/70"><tr>
                <th scope="col" className={`${headerClass} w-14`}>{copy.serialNumber}</th>
                <th scope="col" className={`${headerClass} !text-left`}>{copy.author}</th>
                <th scope="col" className={headerClass}>{copy.publicationCount}</th>
                <th scope="col" className={headerClass} title={copy.scopusId}>{copy.id}</th>
                <th scope="col" className={headerClass} title={copy.updatedAt}>{copy.time}</th>
                <th scope="col" className={headerClass}>{copy.type}</th>
                <th scope="col" className={headerClass}>{copy.status}</th>
                <th scope="col" className="sticky right-0 z-[1] w-44 whitespace-nowrap border-l border-slate-200/80 bg-slate-50 px-2.5 py-3.5 text-center font-medium text-slate-700">{t.common.actions}</th>
              </tr></thead>
              <tbody>{visible.length === 0 ? <tr><td colSpan={8}>
                <EmptyState title={identities.length ? copy.noResultsTitle : copy.emptyTitle} message={identities.length ? copy.noResultsMessage : copy.emptyMessage} />
              </td></tr> : visible.map((identity, index) => {
                const expanded = expandedId === identity.identity_id;
                return <Fragment key={identity.identity_id}>
                  <tr className={expanded ? "bg-slate-50" : "transition-colors hover:bg-slate-50/50"}>
                    <td className={`${cellClass} w-14 font-medium tabular-nums text-slate-600`}>{number((page - 1) * pageSize + index + 1)}</td>
                    <td className="min-w-[240px] whitespace-nowrap border-r border-b border-slate-100 px-2.5 py-3.5 align-middle">
                      <span title={identity.preferred_name || copy.notAvailable} className="block max-w-xs truncate font-medium text-slate-800 sm:max-w-sm">{identity.preferred_name || copy.notAvailable}</span>
                    </td>
                    <td className={`${cellClass} font-medium tabular-nums text-slate-800`}>{identity.publication_count == null ? "—" : number(identity.publication_count)}</td>
                    <td className={`${cellClass} whitespace-nowrap font-mono font-medium text-slate-600`}>{identity.scopus_id || copy.notAvailable}</td>
                    <td className={`${cellClass} whitespace-nowrap font-medium text-slate-600`}>{formatDate(identity.updated_at)}</td>
                    <td className={cellClass}><span className={tableBadgeClass}>{identity.is_primary ? copy.primaryType : copy.secondaryType}</span></td>
                    <td className={cellClass}><span className={tableBadgeClass}>{copy.approved}</span></td>
                    <td className="sticky right-0 z-[1] whitespace-nowrap border-l border-b border-slate-100 bg-white px-2.5 py-3.5 text-center align-middle">
                      <button type="button" className={detailButtonClass} aria-expanded={expanded} aria-controls={`identity-details-${identity.identity_id}`} onClick={() => setExpandedId(expanded ? null : identity.identity_id)}>{expanded ? copy.hideDetails : copy.details}</button>
                    </td>
                  </tr>
                  {expanded && <tr><td colSpan={8} className="border-b border-slate-100"><IdentityDetails identity={identity} copy={copy} /></td></tr>}
                </Fragment>;
              })}</tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-sm text-slate-500">
            <div className="flex flex-wrap items-center gap-3">
              <span role="status">{copy.showing.split(/(\{shown\}|\{total\})/g).map((part, index) => part === "{shown}" ? <strong key={index}>{number(visible.length)}</strong> : part === "{total}" ? <strong key={index}>{number(filtered.length)}</strong> : part)}</span>
              <label className="flex items-center gap-1.5 border-l border-slate-200 pl-2">{t.common.showingCount}:
                <select aria-label={copy.pageSize} value={pageSize} onChange={(event) => update("size", event.target.value)} className={`${controlClass} !h-7 !px-1.5 font-semibold`}>
                  {[10, 20, 50].map((size) => <option key={size} value={size}>{copy.perPage.replace("{count}", number(size))}</option>)}
                </select>
              </label>
            </div>
            <nav className="flex items-center gap-1.5" aria-label={copy.pagination}>
              <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => update("page", String(page - 1))}>{copy.previous}</Button>
              <span className="px-0.5 text-slate-400">{copy.pageLabel}</span>
              <input key={`${page}-${totalPages}`} type="number" aria-label={copy.goToPage} min={1} max={totalPages} defaultValue={page} disabled={!filtered.length}
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
                className={`${controlClass} !h-8 w-14 text-center font-bold disabled:opacity-50 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none`} />
              <span className="whitespace-nowrap text-slate-400" aria-live="polite">/ <strong className="text-slate-600">{number(totalPages)}</strong></span>
              <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => update("page", String(page + 1))}>{copy.next}</Button>
            </nav>
          </div>
        </section>
      </>}
    </div>
  );
}
