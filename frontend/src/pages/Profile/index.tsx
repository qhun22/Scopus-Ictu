import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError } from "../../api/client";
import { getMyLecturerProfile } from "../../api/lecturerScopus";
import { getApiErrorMessage } from "../../api/errors";
import { useI18n } from "../../i18n";
import { LecturerScopusProfile } from "../../types/lecturerScopus";

const viCopy = {
  title: "Hồ sơ giảng viên",
  subtitle: "Thông tin hồ sơ được liên kết với tài khoản ICTU của bạn.",
  basic: "Thông tin cơ bản",
  academic: "Thông tin học thuật",
  organization: "Đơn vị công tác",
  research: "Thông tin nghiên cứu",
  fullName: "Họ và tên",
  staffCode: "Mã cán bộ",
  email: "Email",
  academicRank: "Học hàm",
  academicDegree: "Học vị",
  position: "Chức vụ",
  department: "Bộ môn",
  faculty: "Khoa / đơn vị",
  orcid: "ORCID",
  repository: "Hồ sơ kho lưu trữ",
  notAvailable: "Chưa cập nhật",
  loading: "Đang tải hồ sơ…",
  loadError: "Không thể tải hồ sơ giảng viên.",
  retry: "Thử lại",
  notLinkedTitle: "Tài khoản chưa được liên kết",
  notLinkedMessage: "Tài khoản của bạn chưa được liên kết với hồ sơ giảng viên ICTU.",
};

const enCopy = {
  title: "Lecturer profile",
  subtitle: "Profile information linked to your ICTU account.",
  basic: "Basic information",
  academic: "Academic information",
  organization: "Organization",
  research: "Research information",
  fullName: "Full name",
  staffCode: "Staff code",
  email: "Email",
  academicRank: "Academic rank",
  academicDegree: "Academic degree",
  position: "Position",
  department: "Department",
  faculty: "Faculty / unit",
  orcid: "ORCID",
  repository: "Repository profile",
  notAvailable: "Not available",
  loading: "Loading profile…",
  loadError: "Unable to load your lecturer profile.",
  retry: "Retry",
  notLinkedTitle: "Account not linked",
  notLinkedMessage: "Your account is not linked to an ICTU lecturer profile.",
};

type ProfileCopy = typeof viCopy;

function ProfileSkeleton({ copy }: { copy: ProfileCopy }) {
  return (
    <div className="space-y-6" aria-label={copy.loading}>
      {[copy.basic, copy.academic, copy.organization].map((section) => (
        <section key={section} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-5 h-5 w-44 animate-pulse rounded bg-slate-100" />
          <div className="grid gap-5 sm:grid-cols-2">
            {[0, 1, 2, 3].map((item) => (
              <div key={item} className="space-y-2">
                <div className="h-3 w-24 animate-pulse rounded bg-slate-100" />
                <div className="h-5 w-48 animate-pulse rounded bg-slate-100" />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function StateCard({
  title,
  message,
  actionLabel,
  onAction,
  tone,
}: {
  title: string;
  message: string;
  actionLabel: string;
  onAction: () => void;
  tone: "error" | "info";
}) {
  const toneClass = tone === "error"
    ? "border-rose-200 bg-rose-50 text-rose-900"
    : "border-blue-200 bg-blue-50 text-blue-900";

  return (
    <div className={`rounded-2xl border p-6 shadow-sm ${toneClass}`} role="alert">
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="mt-2 text-sm opacity-80">{message}</p>
      <button
        type="button"
        onClick={onAction}
        className="mt-5 rounded-lg bg-white px-4 py-2 text-sm font-semibold shadow-sm ring-1 ring-inset ring-current/20 transition hover:bg-slate-50"
      >
        {actionLabel}
      </button>
    </div>
  );
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-1 break-words text-sm font-medium text-slate-800">{value}</dd>
    </div>
  );
}

export default function ProfilePage() {
  const { locale } = useI18n();
  const copy = locale === "vi" ? viCopy : enCopy;
  const [profile, setProfile] = useState<LecturerScopusProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notLinked, setNotLinked] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  const loadProfile = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError(null);
    setNotLinked(false);

    void getMyLecturerProfile({ signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setProfile(data);
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return;
        if (requestError instanceof ApiError && requestError.code === "LECTURER_NOT_LINKED") {
          setProfile(null);
          setNotLinked(true);
          return;
        }
        setError(getApiErrorMessage(requestError, copy.loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
  }, [copy.loadError]);

  useEffect(() => {
    loadProfile();
    return () => controllerRef.current?.abort();
  }, [loadProfile]);

  const value = (field: string | null | undefined) => field ?? copy.notAvailable;
  const linkValue = (field: string | null) => field
    ? <a className="text-[#3A5FC3] hover:underline" href={field} target="_blank" rel="noreferrer">{field}</a>
    : copy.notAvailable;

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{copy.title}</h1>
        <p className="mt-1 text-sm text-slate-500">{copy.subtitle}</p>
      </header>

      {loading ? <ProfileSkeleton copy={copy} /> : null}
      {!loading && notLinked ? (
        <StateCard title={copy.notLinkedTitle} message={copy.notLinkedMessage} actionLabel={copy.retry} onAction={loadProfile} tone="info" />
      ) : null}
      {!loading && error ? (
        <StateCard title={copy.loadError} message={error} actionLabel={copy.retry} onAction={loadProfile} tone="error" />
      ) : null}

      {!loading && !error && !notLinked && profile ? (
        <div className="space-y-6">
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-slate-900">{copy.basic}</h2>
            <dl className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              <Field label={copy.fullName} value={value(profile.full_name)} />
              <Field label={copy.staffCode} value={value(profile.staff_code)} />
              <Field label={copy.email} value={value(profile.email)} />
            </dl>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-slate-900">{copy.academic}</h2>
            <dl className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              <Field label={copy.academicRank} value={value(profile.academic_rank)} />
              <Field label={copy.academicDegree} value={value(profile.academic_degree)} />
              <Field label={copy.position} value={value(profile.position)} />
            </dl>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-slate-900">{copy.organization}</h2>
            <dl className="mt-5 grid gap-5 sm:grid-cols-2">
              <Field label={copy.department} value={value(profile.department)} />
              <Field label={copy.faculty} value={value(profile.faculty)} />
            </dl>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-slate-900">{copy.research}</h2>
            <dl className="mt-5 grid gap-5 sm:grid-cols-2">
              <Field label={copy.orcid} value={value(profile.orcid)} />
              <Field label={copy.repository} value={linkValue(profile.repository_profile_url)} />
            </dl>
          </section>
        </div>
      ) : null}
    </main>
  );
}
