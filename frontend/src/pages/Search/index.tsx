import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { getSearch } from "../../api/search";
import { SearchResponse } from "../../types/search";
import { useI18n } from "../../i18n";

const MIN_QUERY_LENGTH = 2;
const GROUP_LIMIT = 5;

export default function SearchPage() {
  const { t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();

  const urlQuery = searchParams.get("q") ?? "";

  const [inputValue, setInputValue] = useState(urlQuery);
  const [activeQuery, setActiveQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [validationError, setValidationError] = useState("");

  // Only the latest request may write state. An AbortController cancels the
  // in-flight fetch, and the request id guards against a stale response that
  // resolves after a newer one has already been applied.
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  const runSearch = useCallback(async (rawQuery: string) => {
    const trimmed = rawQuery.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) {
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    setActiveQuery(trimmed);
    setIsLoading(true);
    setErrorMessage("");

    try {
      const response = await getSearch(
        { q: trimmed, limit: GROUP_LIMIT },
        { signal: controller.signal },
      );
      if (requestId !== requestIdRef.current) return;
      setResults(response);
    } catch (error) {
      if (controller.signal.aborted) return;
      if (requestId !== requestIdRef.current) return;
      if (error instanceof ApiError && error.status === 0) return;
      setResults(null);
      setErrorMessage(getApiErrorMessage(error, t.search.errorTitle));
    } finally {
      if (requestId === requestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [t.search.errorTitle]);

  // Auto-search on entry when the URL already carries a usable term.
  useEffect(() => {
    const trimmed = urlQuery.trim();
    if (trimmed.length >= MIN_QUERY_LENGTH) {
      setInputValue(trimmed);
      void runSearch(trimmed);
    }
    // Only the initial URL term should trigger the automatic search.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = inputValue.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setValidationError(t.search.tooShort);
      return;
    }

    setValidationError("");
    setSearchParams(trimmed ? { q: trimmed } : {}, { replace: false });
    void runSearch(trimmed);
  };

  const handleRetry = () => {
    if (activeQuery) {
      void runSearch(activeQuery);
    }
  };

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(event.target.value);
    if (validationError) setValidationError("");
  };

  const hasAnyResult =
    results !== null &&
    (results.lecturers.length > 0 ||
      results.publications.length > 0 ||
      results.scopus_authors.length > 0);

  return (
    <div className="app-page-container space-y-4 p-4 sm:p-6 lg:p-8">
      <section className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs sm:p-5">
        <h1 className="text-lg font-bold text-slate-800 sm:text-xl">
          {t.search.title}
        </h1>
        <p className="mt-1 text-xs text-slate-500 sm:text-sm">
          {t.search.subtitle}
        </p>

        <form onSubmit={handleSubmit} className="mt-3">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <input
                type="text"
                value={inputValue}
                onChange={handleChange}
                placeholder={t.search.placeholder}
                className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 transition-all focus:border-[#3A5FC3] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 sm:text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="inline-flex h-10 cursor-pointer items-center justify-center gap-1.5 rounded-lg bg-[#3A5FC3] px-5 text-xs font-bold text-white shadow-xs transition-all duration-150 hover:bg-[#2f4ea6] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/30 disabled:cursor-not-allowed disabled:opacity-60 sm:text-sm"
            >
              <span>{t.search.button}</span>
            </button>
          </div>
          {validationError && (
            <p className="mt-1 text-xs font-medium text-rose-500">{validationError}</p>
          )}
        </form>
      </section>

      {isLoading && (
        <div className="rounded-xl border border-slate-200/80 bg-white p-6 text-center text-sm text-slate-500">
          {t.search.loading}
        </div>
      )}

      {!isLoading && errorMessage && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center">
          <p className="text-sm font-medium text-rose-600">{errorMessage}</p>
          <button
            type="button"
            onClick={handleRetry}
            className="mt-3 inline-flex cursor-pointer items-center justify-center rounded-lg border border-rose-300 bg-white px-4 py-2 text-xs font-semibold text-rose-600 transition-all hover:bg-rose-100"
          >
            {t.search.errorRetry}
          </button>
        </div>
      )}

      {!isLoading && !errorMessage && !activeQuery && (
        <div className="rounded-xl border border-slate-200/80 bg-white p-8 text-center">
          <h2 className="text-sm font-bold text-slate-700">{t.search.promptTitle}</h2>
          <p className="mt-1 text-xs text-slate-500">{t.search.promptSubtitle}</p>
        </div>
      )}

      {!isLoading && !errorMessage && activeQuery && results && !hasAnyResult && (
        <div className="rounded-xl border border-slate-200/80 bg-white p-8 text-center">
          <h2 className="text-sm font-bold text-slate-700">{t.search.emptyTitle}</h2>
          <p className="mt-1 text-xs text-slate-500">{t.search.emptySubtitle}</p>
        </div>
      )}

      {!isLoading && !errorMessage && results && hasAnyResult && (
        <div className="space-y-4">
          <ResultSection title={t.search.lecturersTitle} empty={t.search.noLecturers} count={results.lecturers.length}>
            <ul className="divide-y divide-slate-100">
              {results.lecturers.map((item) => (
                <li key={`${item.full_name}-${item.staff_code ?? ""}`} className="py-2.5">
                  <p className="text-sm font-semibold text-slate-800">{item.full_name}</p>
                  <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-slate-500">
                    {item.staff_code && <Meta label={t.search.staffCode} value={item.staff_code} />}
                    {item.department && <Meta label={t.search.department} value={item.department} />}
                    {item.faculty && <Meta label={t.search.faculty} value={item.faculty} />}
                    {item.orcid && <Meta label={t.search.orcid} value={item.orcid} />}
                  </dl>
                </li>
              ))}
            </ul>
          </ResultSection>

          <ResultSection title={t.search.publicationsTitle} empty={t.search.noPublications} count={results.publications.length}>
            <ul className="divide-y divide-slate-100">
              {results.publications.map((item) => (
                <li key={item.eid} className="py-2.5">
                  <Link
                    to={`/publications/${encodeURIComponent(item.eid)}`}
                    className="text-sm font-semibold text-[#3A5FC3] hover:underline"
                  >
                    {item.title}
                  </Link>
                  <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-slate-500">
                    <Meta label="EID" value={item.eid} />
                    {item.year !== null && <Meta label={t.search.year} value={String(item.year)} />}
                    {item.source_title && <Meta label={t.search.source} value={item.source_title} />}
                    {item.cited_by_count !== null && (
                      <Meta label={t.search.citations} value={String(item.cited_by_count)} />
                    )}
                    {item.document_type && (
                      <Meta label={t.search.documentType} value={item.document_type} />
                    )}
                  </dl>
                </li>
              ))}
            </ul>
          </ResultSection>

          <ResultSection title={t.search.scopusAuthorsTitle} empty={t.search.noScopusAuthors} count={results.scopus_authors.length}>
            <ul className="divide-y divide-slate-100">
              {results.scopus_authors.map((item) => (
                <li key={item.scopus_id} className="py-2.5">
                  <p className="text-sm font-semibold text-slate-800">{item.preferred_name}</p>
                  <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-slate-500">
                    <Meta label={t.search.scopusId} value={item.scopus_id} />
                  </dl>
                </li>
              ))}
            </ul>
          </ResultSection>
        </div>
      )}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-1">
      <dt className="font-medium text-slate-400">{label}:</dt>
      <dd className="text-slate-600">{value}</dd>
    </div>
  );
}

function ResultSection({
  title,
  empty,
  count,
  children,
}: {
  title: string;
  empty: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs sm:p-5">
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-sm font-bold text-slate-800">{title}</h2>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
          {count}
        </span>
      </div>
      {count === 0 ? (
        <p className="py-2 text-xs text-slate-400">{empty}</p>
      ) : (
        children
      )}
    </section>
  );
}