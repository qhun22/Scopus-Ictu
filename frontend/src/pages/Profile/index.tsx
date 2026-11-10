import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import Avatar from "../../components/common/Avatar";
import Button, { buttonClass } from "../../components/ui/Button";
import { useAuth } from "../../contexts/AuthContext";
import { useI18n } from "../../i18n";
import type { TranslationSchema } from "../../i18n/types";
import { orcidProfileUrl, webProfileUrl } from "./profileLinks";
import useProfileData from "./useProfileData";
import ProfileEditForm from "./ProfileEditForm";

type ProfileCopy = TranslationSchema["personalProfile"];
const panelClass = "min-w-0 overflow-hidden rounded-card border border-slate-200/80 bg-white";
const badgeClass = "inline-flex h-badge shrink-0 items-center justify-center whitespace-nowrap rounded-control border bg-white px-2.5 text-sm font-bold leading-none";

function ProfileSection({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className={panelClass}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 bg-slate-50/50 px-4 py-3.5">
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>{action}
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return <div className="min-w-0"><dt className="text-sm text-slate-500">{label}</dt><dd className="mt-1 break-words text-sm font-medium text-slate-800">{value}</dd></div>;
}

function ProfileLink({ value, href, fallback }: { value: string | null | undefined; href: string | null; fallback: string }) {
  if (!value?.trim()) return <span className="text-slate-400">{fallback}</span>;
  return href ? <a href={href} target="_blank" rel="noopener noreferrer" className="break-all text-brand hover:underline">{value.trim()}</a> : <>{value.trim()}</>;
}

function ProfileSkeleton({ copy }: { copy: ProfileCopy }) {
  return <div className="space-y-4" role="status" aria-label={copy.loading}>
    <p className="text-sm text-slate-500">{copy.loading}</p>
    {[0, 1, 2].map((key) => <div key={key} className={`${panelClass} p-5`}>
      <div className="mb-5 h-4 w-40 animate-pulse rounded-control bg-slate-100" />
      <div className="grid gap-4 sm:grid-cols-2">{[0, 1, 2, 3].map((field) => <div key={field} className="h-10 animate-pulse rounded-control bg-slate-100" />)}</div>
    </div>)}
  </div>;
}

export default function ProfilePage() {
  const { user } = useAuth();
  const { t, locale, getRoleLabel } = useI18n();
  const copy = t.personalProfile;
  const { profile, loading, error, identities, identitiesLoading, identitiesError, loadProfile, loadIdentities, applyProfile } = useProfileData();
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);
  const notLinked = error instanceof ApiError && error.code === "LECTURER_NOT_LINKED";
  const name = profile?.full_name?.trim() || user?.display_name?.trim() || copy.notAvailable;
  const fieldValue = (value: string | null | undefined): ReactNode => value?.trim() || <span className="text-slate-400">{copy.notAvailable}</span>;
  const role = getRoleLabel(user?.role) || copy.notAvailable;
  const linkStatus = loading ? copy.loading : notLinked ? copy.notLinked : profile ? copy.linked : copy.unverified;
  const linkTone = loading || (!profile && !notLinked) ? "border-slate-300 text-slate-600" : notLinked ? "border-amber-400 text-amber-700" : "border-emerald-400 text-emerald-700";
  const reload = () => { setSaved(false); loadProfile(); loadIdentities(); };
  const mainIdentity = identities.find((identity) => identity.is_primary && identity.status === "APPROVED");
  const primaryIdValue = identitiesLoading ? <span role="status">{copy.identityLoading}</span> : identitiesError ? <div className="space-y-2">
    <p className="text-rose-700">{copy.identityError}</p><Button variant="secondary" size="sm" onClick={loadIdentities}>{copy.retry}</Button>
  </div> : mainIdentity ? <Link to={`/identity?q=${encodeURIComponent(mainIdentity.scopus_id)}`} className="font-mono text-brand hover:underline">{mainIdentity.scopus_id}</Link> : <span className="text-slate-400">{copy.noPrimaryScopusId}</span>;
  const genderLabel = (value: string | null) => value === "Nam" ? copy.genderMale : value === "Nữ" ? copy.genderFemale : value === "Khác" ? copy.genderOther : fieldValue(value);

  return (
    <div className="personal-profile-page app-page-container min-w-0">
      <div className="grid min-w-0 items-start gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="min-w-0 space-y-4 xl:sticky xl:top-0">
          <section className={`${panelClass} p-4 sm:p-5`} aria-label={copy.account}>
            <p className="mb-4 text-sm font-semibold text-slate-800">{copy.account}</p>
            <div className="flex min-w-0 items-center gap-3">
              <Avatar src={user?.avatar_url} name={name} className="h-16 w-16 shrink-0 rounded-control text-2xl" />
              <h1 className="min-w-0 break-words text-lg font-bold leading-6 text-slate-800">{name}</h1>
            </div>
            <dl className="mt-5 space-y-4 border-t border-slate-100 pt-4">
              <Field label={copy.accountName} value={fieldValue(user?.display_name)} />
              <Field label={copy.accountEmail} value={fieldValue(user?.email)} />
              <Field label={copy.accountRole} value={<span className={`${badgeClass} border-slate-300 text-slate-700`}>{role}</span>} />
              <Field label={copy.profileLink} value={<span className={`${badgeClass} ${linkTone}`}>{linkStatus}</span>} />
            </dl>
            <Button variant="secondary" fullWidth className="mt-5" onClick={reload} disabled={loading || identitiesLoading || editing}>{copy.refresh}</Button>
          </section>

          <section className={panelClass}>
            <h2 className="border-b border-slate-200/80 bg-slate-50/50 px-4 py-3.5 text-sm font-semibold text-slate-800">{copy.quickLinks}</h2>
            <nav aria-label={copy.quickLinks} className="divide-y divide-slate-100">
              <Link to="/my-publications" className="block px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-brand">{t.nav.myPublications}</Link>
              <Link to="/identity" className="block px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-brand">{t.nav.identity}</Link>
            </nav>
          </section>
        </aside>

        <div className="min-w-0 space-y-4">
          {loading ? <ProfileSkeleton copy={copy} /> : error || !profile ? (
            <section className={`rounded-card border p-5 ${notLinked ? "border-amber-200 bg-amber-50 text-amber-900" : "border-rose-200 bg-rose-50 text-rose-900"}`} role="alert">
              <h2 className="text-sm font-semibold">{notLinked ? copy.notLinkedTitle : copy.loadError}</h2>
              <p className="mt-2 text-sm leading-6">{notLinked ? copy.notLinkedMessage : getApiErrorMessage(error, copy.loadError)}</p>
              <Button variant="secondary" className="mt-4" onClick={loadProfile}>{copy.retry}</Button>
            </section>
          ) : <>
            <ProfileSection title={copy.basic} action={!editing && <Button variant="secondary" size="sm" onClick={() => { setSaved(false); setEditing(true); }}>{copy.edit}</Button>}>
              <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 2xl:grid-cols-3">
                <Field label={copy.fullName} value={fieldValue(profile.full_name)} />
                <Field label={copy.primaryScopusId} value={primaryIdValue} />
                <Field label={copy.email} value={fieldValue(profile.email)} />
              </dl>
            </ProfileSection>

            {saved && <p className="rounded-control border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{copy.saved}</p>}
            {editing ? <ProfileEditForm profile={profile} onCancel={() => setEditing(false)} onSaved={(updated) => { applyProfile(updated); setEditing(false); setSaved(true); }} /> : <>
                <ProfileSection title={copy.academic}>
                  <dl className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
                    <Field label={copy.academicRank} value={fieldValue(profile.academic_rank)} />
                    <Field label={copy.academicDegree} value={fieldValue(profile.academic_degree)} />
                    <Field label={copy.position} value={fieldValue(profile.position)} />
                    <Field label={copy.specialization} value={fieldValue(profile.specialization)} />
                  </dl>
                </ProfileSection>

              <ProfileSection title={copy.contact}>
                <dl className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
                  <Field label={copy.phone} value={fieldValue(profile.phone)} />
                  <Field label={copy.dateOfBirth} value={profile.date_of_birth ? new Date(`${profile.date_of_birth}T00:00:00`).toLocaleDateString(locale === "vi" ? "vi-VN" : "en-US") : fieldValue(null)} />
                  <Field label={copy.gender} value={genderLabel(profile.gender)} />
                </dl>
              </ProfileSection>

              <ProfileSection title={copy.research}>
                <dl className="grid gap-4 sm:grid-cols-2">
                  <Field label={copy.orcid} value={<ProfileLink value={profile.orcid} href={orcidProfileUrl(profile.orcid)} fallback={copy.notAvailable} />} />
                  <Field label={copy.repository} value={<ProfileLink value={profile.repository_profile_url} href={webProfileUrl(profile.repository_profile_url)} fallback={copy.notAvailable} />} />
                </dl>
              </ProfileSection>
            </>}
          </>}

          {!loading && !editing && <section className={`${panelClass} flex flex-wrap items-center justify-between gap-4 p-4 sm:p-5`}>
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-semibold text-slate-800">{copy.updateTitle}</h2>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">{copy.updateMessage}</p>
            </div>
            <Link to="/report-issue" className={buttonClass("secondary")}>{copy.requestUpdate}</Link>
          </section>}
        </div>
      </div>
    </div>
  );
}
