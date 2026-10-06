import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { getMyApprovedScopusIdentities } from "../../api/lecturerScopus";
import { useI18n } from "../../i18n";
import { ApprovedScopusIdentity } from "../../types/lecturerScopus";

const viCopy = {
  title: "Liên kết Scopus",
  subtitle: "Các định danh Scopus đã được phê duyệt cho hồ sơ của bạn.",
  identity: "Định danh Scopus",
  scopusId: "Scopus Author ID",
  status: "Trạng thái",
  approved: "Đã phê duyệt",
  variants: "Biến thể tên",
  noVariants: "Không có biến thể tên được ghi nhận.",
  evidence: "Tóm tắt bằng chứng",
  evidenceType: "Loại bằng chứng",
  direction: "Chiều liên kết",
  recordedAt: "Thời điểm ghi nhận",
  createdAt: "Tạo lúc",
  updatedAt: "Cập nhật lúc",
  emptyTitle: "Chưa có định danh Scopus",
  emptyMessage: "Hồ sơ của bạn hiện chưa có liên kết Scopus được phê duyệt.",
  loadError: "Không thể tải các liên kết Scopus.",
  retry: "Thử lại",
  loading: "Đang tải liên kết Scopus…",
  notLinked: "Tài khoản chưa được liên kết với hồ sơ giảng viên.",
};

const enCopy = {
  title: "Scopus identity links",
  subtitle: "Approved Scopus identities associated with your profile.",
  identity: "Scopus identity",
  scopusId: "Scopus Author ID",
  status: "Status",
  approved: "Approved",
  variants: "Name variants",
  noVariants: "No recorded name variants.",
  evidence: "Evidence summary",
  evidenceType: "Evidence type",
  direction: "Link direction",
  recordedAt: "Recorded at",
  createdAt: "Created",
  updatedAt: "Updated",
  emptyTitle: "No Scopus identities",
  emptyMessage: "Your profile has no approved Scopus identity links yet.",
  loadError: "Unable to load your Scopus identity links.",
  retry: "Retry",
  loading: "Loading Scopus identities…",
  notLinked: "Your account is not linked to a lecturer profile.",
};

type IdentityCopy = typeof viCopy;

function formatDate(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function IdentitySkeleton({ copy }: { copy: IdentityCopy }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2" aria-label={copy.loading}>
      {[0, 1].map((item) => (
        <div key={item} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="h-5 w-48 animate-pulse rounded bg-slate-100" />
          <div className="mt-5 space-y-4">
            {[0, 1, 2, 3].map((line) => <div key={line} className="h-4 w-full animate-pulse rounded bg-slate-100" />)}
          </div>
        </div>
      ))}
    </div>
  );
}

function StateCard({ copy, message, onRetry, title }: { copy: IdentityCopy; message: string; onRetry: () => void; title: string }) {
  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-900 shadow-sm" role="alert">
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="mt-2 text-sm text-rose-800">{message}</p>
      <button type="button" onClick={onRetry} className="mt-5 rounded-lg bg-white px-4 py-2 text-sm font-semibold shadow-sm ring-1 ring-inset ring-rose-300 transition hover:bg-rose-50">
        {copy.retry}
      </button>
    </div>
  );
}

function IdentityCard({ identity, copy, locale }: { identity: ApprovedScopusIdentity; copy: IdentityCopy; locale: string }) {
  const fallback = "—";
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{copy.identity}</p>
          <h2 className="mt-1 text-lg font-bold text-slate-900">{identity.preferred_name || fallback}</h2>
        </div>
        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
          {identity.status === "APPROVED" ? copy.approved : identity.status || fallback}
        </span>
      </div>

      <dl className="mt-6 grid gap-4 sm:grid-cols-2">
        <div><dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{copy.scopusId}</dt><dd className="mt-1 break-all text-sm font-medium text-slate-800">{identity.scopus_id || fallback}</dd></div>
      </dl>

      <div className="mt-6 border-t border-slate-100 pt-5">
        <h3 className="text-sm font-semibold text-slate-900">{copy.variants}</h3>
        {identity.name_variants.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {identity.name_variants.map((variant) => <span key={variant} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{variant}</span>)}
          </div>
        ) : <p className="mt-2 text-sm text-slate-500">{copy.noVariants}</p>}
      </div>

      <div className="mt-6 border-t border-slate-100 pt-5">
        <h3 className="text-sm font-semibold text-slate-900">{copy.evidence}</h3>
        {identity.evidence.length > 0 ? (
          <div className="mt-3 space-y-3">
            {identity.evidence.map((item, index) => (
              <dl key={`${item.evidence_type}-${item.created_at}-${index}`} className="grid gap-2 rounded-xl bg-slate-50 p-3 text-sm sm:grid-cols-3">
                <div><dt className="text-xs text-slate-400">{copy.evidenceType}</dt><dd className="mt-1 font-medium text-slate-700">{item.evidence_type || fallback}</dd></div>
                <div><dt className="text-xs text-slate-400">{copy.direction}</dt><dd className="mt-1 font-medium text-slate-700">{item.direction || fallback}</dd></div>
                <div><dt className="text-xs text-slate-400">{copy.recordedAt}</dt><dd className="mt-1 font-medium text-slate-700">{formatDate(item.created_at, locale)}</dd></div>
              </dl>
            ))}
          </div>
        ) : <p className="mt-2 text-sm text-slate-500">{fallback}</p>}
      </div>

      <dl className="mt-6 grid gap-4 border-t border-slate-100 pt-5 text-sm sm:grid-cols-2">
        <div><dt className="text-xs text-slate-400">{copy.createdAt}</dt><dd className="mt-1 text-slate-700">{formatDate(identity.created_at, locale)}</dd></div>
        <div><dt className="text-xs text-slate-400">{copy.updatedAt}</dt><dd className="mt-1 text-slate-700">{formatDate(identity.updated_at, locale)}</dd></div>
      </dl>
    </article>
  );
}

export default function IdentityPage() {
  const { locale } = useI18n();
  const copy = locale === "vi" ? viCopy : enCopy;
  const [identities, setIdentities] = useState<ApprovedScopusIdentity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const loadIdentities = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError(null);

    void getMyApprovedScopusIdentities({ signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setIdentities(data);
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return;
        if (requestError instanceof ApiError && requestError.code === "LECTURER_NOT_LINKED") {
          setError(copy.notLinked);
          return;
        }
        setError(getApiErrorMessage(requestError, copy.loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
  }, [copy.loadError, copy.notLinked]);

  useEffect(() => {
    loadIdentities();
    return () => controllerRef.current?.abort();
  }, [loadIdentities]);

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{copy.title}</h1>
        <p className="mt-1 text-sm text-slate-500">{copy.subtitle}</p>
      </header>

      {loading ? <IdentitySkeleton copy={copy} /> : null}
      {!loading && error ? <StateCard copy={copy} title={copy.loadError} message={error} onRetry={loadIdentities} /> : null}
      {!loading && !error && identities.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">{copy.emptyTitle}</h2>
          <p className="mt-2 text-sm text-slate-500">{copy.emptyMessage}</p>
        </div>
      ) : null}
      {!loading && !error && identities.length > 0 ? (
        <div className="grid gap-6 lg:grid-cols-2">
          {identities.map((identity) => <IdentityCard key={identity.scopus_id} identity={identity} copy={copy} locale={locale} />)}
        </div>
      ) : null}
    </main>
  );
}
