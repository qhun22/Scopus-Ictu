import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { getMyLecturerPublications } from "../../api/lecturerScopus";
import { useI18n } from "../../i18n";
import { LecturerPublication, LecturerPublicationsResponse } from "../../types/lecturerScopus";

const PAGE_SIZE = 20;

const viCopy = {
  title: "Công bố Scopus của tôi",
  subtitle: "Các công bố được liên kết từ những định danh Scopus đã được phê duyệt.",
  summaryTitle: "Tổng quan công bố",
  totalPublications: "Tổng số công bố",
  knownCitations: "Tổng lượt trích dẫn đã biết",
  unknownCitations: "Công bố chưa có dữ liệu trích dẫn",
  approvedIdentities: "Định danh Scopus đã duyệt",
  yearTitle: "Phân bổ theo năm",
  unknownYear: "Chưa rõ năm",
  noYearData: "Chưa có dữ liệu phân bổ theo năm.",
  publicationsTitle: "Danh sách công bố",
  noPublicationsTitle: "Chưa có công bố Scopus",
  noPublicationsMessage: "Chưa có công bố Scopus được liên kết với các định danh đã duyệt.",
  year: "Năm",
  sourceTitle: "Nguồn xuất bản",
  documentType: "Loại tài liệu",
  stage: "Giai đoạn công bố",
  openAccess: "Truy cập mở",
  eid: "EID",
  doi: "DOI",
  citations: "Trích dẫn",
  authorPositions: "Vị trí tác giả",
  citationUnknown: "Chưa có dữ liệu",
  yearUnknown: "Chưa rõ năm",
  notAvailable: "Chưa cập nhật",
  loading: "Đang tải công bố…",
  paginationLoading: "Đang tải trang công bố…",
  loadError: "Không thể tải công bố Scopus.",
  retry: "Thử lại",
  notLinkedTitle: "Tài khoản chưa được liên kết",
  notLinkedMessage: "Tài khoản của bạn chưa được liên kết với hồ sơ giảng viên ICTU.",
  previous: "Trang trước",
  next: "Trang sau",
  pageIndicator: (page: number, totalPages: number) => `Trang ${page} / ${totalPages}`,
};

const enCopy = {
  title: "My Scopus publications",
  subtitle: "Publications linked from your approved Scopus identities.",
  summaryTitle: "Publication overview",
  totalPublications: "Total publications",
  knownCitations: "Known citation sum",
  unknownCitations: "Publications without citation data",
  approvedIdentities: "Approved Scopus identities",
  yearTitle: "Publication years",
  unknownYear: "Unknown year",
  noYearData: "No year breakdown is available.",
  publicationsTitle: "Publication list",
  noPublicationsTitle: "No Scopus publications",
  noPublicationsMessage: "No Scopus publications are linked to your approved identities.",
  year: "Year",
  sourceTitle: "Source title",
  documentType: "Document type",
  stage: "Publication stage",
  openAccess: "Open access",
  eid: "EID",
  doi: "DOI",
  citations: "Citations",
  authorPositions: "Author positions",
  citationUnknown: "No data",
  yearUnknown: "Unknown year",
  notAvailable: "Not available",
  loading: "Loading publications…",
  paginationLoading: "Loading publication page…",
  loadError: "Unable to load your Scopus publications.",
  retry: "Retry",
  notLinkedTitle: "Account not linked",
  notLinkedMessage: "Your account is not linked to an ICTU lecturer profile.",
  previous: "Previous",
  next: "Next",
  pageIndicator: (page: number, totalPages: number) => `Page ${page} / ${totalPages}`,
};

type PublicationCopy = typeof viCopy;

function formatNumber(value: number, locale: string): string {
  return new Intl.NumberFormat(locale === "vi" ? "vi-VN" : "en-US").format(value);
}

function sortedYearBuckets(buckets: Record<string, number>): Array<[string, number]> {
  return Object.entries(buckets).sort(([left], [right]) => {
    const leftYear = Number(left);
    const rightYear = Number(right);
    const leftKnown = Number.isFinite(leftYear);
    const rightKnown = Number.isFinite(rightYear);

    if (leftKnown && rightKnown) return rightYear - leftYear;
    if (leftKnown) return -1;
    if (rightKnown) return 1;
    return left.localeCompare(right);
  });
}

function LoadingState({ copy }: { copy: PublicationCopy }) {
  return (
    <div className="space-y-6" aria-label={copy.loading}>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="h-28 animate-pulse rounded-2xl border border-slate-200 bg-white shadow-sm" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="h-72 animate-pulse rounded-2xl border border-slate-200 bg-white shadow-sm" />
        <div className="h-72 animate-pulse rounded-2xl border border-slate-200 bg-white shadow-sm" />
      </div>
      <div className="space-y-4">
        {[0, 1].map((item) => <div key={item} className="h-44 animate-pulse rounded-2xl border border-slate-200 bg-white shadow-sm" />)}
      </div>
    </div>
  );
}

function StateCard({
  title,
  message,
  retryLabel,
  onRetry,
  tone,
}: {
  title: string;
  message: string;
  retryLabel: string;
  onRetry: () => void;
  tone: "error" | "info";
}) {
  const toneClass = tone === "error"
    ? "border-rose-200 bg-rose-50 text-rose-900"
    : "border-blue-200 bg-blue-50 text-blue-900";

  return (
    <div className={`rounded-2xl border p-6 shadow-sm ${toneClass}`} role="alert">
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="mt-2 text-sm opacity-80">{message}</p>
      <button type="button" onClick={onRetry} className="mt-5 rounded-lg bg-white px-4 py-2 text-sm font-semibold shadow-sm ring-1 ring-inset ring-current/20 transition hover:bg-slate-50">
        {retryLabel}
      </button>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-3 text-2xl font-bold text-slate-900">{value}</p>
    </section>
  );
}

function Detail({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-1 break-words text-sm text-slate-700">{value}</dd>
    </div>
  );
}

function PublicationCard({
  publication,
  copy,
  locale,
}: {
  publication: LecturerPublication;
  copy: PublicationCopy;
  locale: string;
}) {
  const value = (field: string | null) => field ?? copy.notAvailable;
  const year = publication.year === null ? copy.yearUnknown : String(publication.year);
  const citations = publication.cited_by_count === null
    ? copy.citationUnknown
    : formatNumber(publication.cited_by_count, locale);

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h3 className="text-base font-bold leading-6 text-slate-900">{publication.title || copy.notAvailable}</h3>
      <dl className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Detail label={copy.year} value={year} />
        <Detail label={copy.sourceTitle} value={value(publication.source_title)} />
        <Detail label={copy.documentType} value={value(publication.document_type)} />
        <Detail label={copy.stage} value={value(publication.publication_stage)} />
        <Detail label={copy.openAccess} value={value(publication.open_access_status)} />
        <Detail label={copy.citations} value={citations} />
        <Detail label={copy.eid} value={publication.eid} />
        <Detail label={copy.doi} value={value(publication.doi)} />
        {publication.linked_author_orders.length > 0 ? (
          <Detail label={copy.authorPositions} value={publication.linked_author_orders.join(", ")} />
        ) : null}
      </dl>
    </article>
  );
}

function YearBreakdown({
  aggregates,
  copy,
  locale,
}: {
  aggregates: LecturerPublicationsResponse["aggregates"];
  copy: PublicationCopy;
  locale: string;
}) {
  const buckets = sortedYearBuckets(aggregates.publication_count_by_year);
  const hasUnknownYear = aggregates.unknown_year_count > 0;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">{copy.yearTitle}</h2>
      {buckets.length === 0 && !hasUnknownYear ? (
        <p className="mt-4 text-sm text-slate-500">{copy.noYearData}</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {buckets.map(([year, count]) => (
            <li key={year} className="flex items-center justify-between gap-4 text-sm">
              <span className="text-slate-600">{year}</span>
              <span className="font-semibold text-slate-900">{formatNumber(count, locale)}</span>
            </li>
          ))}
          {hasUnknownYear ? (
            <li className="flex items-center justify-between gap-4 border-t border-slate-100 pt-3 text-sm">
              <span className="text-slate-600">{copy.unknownYear}</span>
              <span className="font-semibold text-slate-900">{formatNumber(aggregates.unknown_year_count, locale)}</span>
            </li>
          ) : null}
        </ul>
      )}
    </section>
  );
}

function PaginationControls({
  copy,
  currentPage,
  totalPages,
  total,
  disabled,
  onPrevious,
  onNext,
}: {
  copy: PublicationCopy;
  currentPage: number;
  totalPages: number;
  total: number;
  disabled: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <nav className="flex flex-wrap items-center justify-between gap-3" aria-label="Publication pagination">
      <button type="button" onClick={onPrevious} disabled={disabled || currentPage <= 1} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40">
        {copy.previous}
      </button>
      <span className="text-sm font-medium text-slate-600" aria-live="polite">{copy.pageIndicator(currentPage, totalPages)}</span>
      <button type="button" onClick={onNext} disabled={disabled || total === 0 || currentPage >= totalPages} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40">
        {copy.next}
      </button>
    </nav>
  );
}

export default function MyPublicationsPage() {
  const { locale } = useI18n();
  const copy = locale === "vi" ? viCopy : enCopy;
  const [response, setResponse] = useState<LecturerPublicationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [paginationLoading, setPaginationLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notLinked, setNotLinked] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const requestedPageRef = useRef(1);
  const hasLoadedRef = useRef(false);

  const loadPage = useCallback((requestedPage: number) => {
    const page = Math.max(1, Math.trunc(requestedPage));
    requestedPageRef.current = page;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const isPaginationRequest = hasLoadedRef.current;

    setError(null);
    setNotLinked(false);
    if (isPaginationRequest) {
      setPaginationLoading(true);
    } else {
      setLoading(true);
    }

    void getMyLecturerPublications({ page, page_size: PAGE_SIZE }, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setResponse(data);
          hasLoadedRef.current = true;
        }
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return;
        setResponse(null);
        if (requestError instanceof ApiError && requestError.code === "LECTURER_NOT_LINKED") {
          setNotLinked(true);
          return;
        }
        setError(getApiErrorMessage(requestError, copy.loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
          setPaginationLoading(false);
        }
      });
  }, [copy.loadError]);

  useEffect(() => {
    loadPage(1);
    return () => controllerRef.current?.abort();
  }, [loadPage]);

  const retry = () => loadPage(requestedPageRef.current);
  const totalPages = response
    ? Math.max(1, Math.ceil(response.total / Math.max(1, response.page_size)))
    : 1;

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{copy.title}</h1>
        <p className="mt-1 text-sm text-slate-500">{copy.subtitle}</p>
      </header>

      {loading ? <LoadingState copy={copy} /> : null}
      {!loading && notLinked ? (
        <StateCard title={copy.notLinkedTitle} message={copy.notLinkedMessage} retryLabel={copy.retry} onRetry={retry} tone="info" />
      ) : null}
      {!loading && error ? (
        <StateCard title={copy.loadError} message={error} retryLabel={copy.retry} onRetry={retry} tone="error" />
      ) : null}
      {!loading && !error && !notLinked && paginationLoading ? (
        <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5 text-sm text-blue-900" role="status" aria-live="polite">
          {copy.paginationLoading}
        </div>
      ) : null}

      {!loading && !error && !notLinked && !paginationLoading && response ? (
        <div className="space-y-6">
          <section>
            <h2 className="mb-4 text-base font-semibold text-slate-900">{copy.summaryTitle}</h2>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <SummaryCard label={copy.totalPublications} value={formatNumber(response.aggregates.total_publications, locale)} />
              <SummaryCard label={copy.knownCitations} value={formatNumber(response.aggregates.known_citation_sum, locale)} />
              <SummaryCard label={copy.unknownCitations} value={formatNumber(response.aggregates.citation_unknown_publication_count, locale)} />
              <SummaryCard label={copy.approvedIdentities} value={formatNumber(response.aggregates.approved_identity_count, locale)} />
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-base font-semibold text-slate-900">{copy.publicationsTitle}</h2>
              {response.items.length === 0 ? (
                <div className="py-12 text-center">
                  <h3 className="text-base font-semibold text-slate-900">{copy.noPublicationsTitle}</h3>
                  <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{copy.noPublicationsMessage}</p>
                </div>
              ) : (
                <div className="mt-5 space-y-4">
                  {response.items.map((publication) => (
                    <PublicationCard key={publication.eid} publication={publication} copy={copy} locale={locale} />
                  ))}
                </div>
              )}
            </section>
            <YearBreakdown aggregates={response.aggregates} copy={copy} locale={locale} />
          </div>

          <PaginationControls
            copy={copy}
            currentPage={response.page}
            totalPages={totalPages}
            total={response.total}
            disabled={paginationLoading}
            onPrevious={() => loadPage(response.page - 1)}
            onNext={() => loadPage(response.page + 1)}
          />
        </div>
      ) : null}
    </main>
  );
}
