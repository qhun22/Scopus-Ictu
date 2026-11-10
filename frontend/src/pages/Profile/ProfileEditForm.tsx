import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { updateMyLecturerProfile } from "../../api/lecturerScopus";
import Button from "../../components/ui/Button";
import { useI18n } from "../../i18n";
import type { LecturerProfileUpdate, LecturerScopusProfile } from "../../types/lecturerScopus";

export const EDITABLE_PROFILE_FIELDS = ["academic_rank", "academic_degree", "position", "specialization", "phone", "date_of_birth", "gender", "orcid", "repository_profile_url"] as const;
type EditableField = typeof EDITABLE_PROFILE_FIELDS[number];
type Draft = Record<EditableField, string>;
const inputClass = "h-control w-full min-w-0 rounded-control border border-line bg-white px-2.5 text-sm text-slate-800 focus:border-line focus:outline-none disabled:opacity-60";

export default function ProfileEditForm({ profile, onSaved, onCancel }: {
  profile: LecturerScopusProfile;
  onSaved: (profile: LecturerScopusProfile) => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const copy = t.personalProfile;
  const [initial] = useState(() => Object.fromEntries(EDITABLE_PROFILE_FIELDS.map((key) => [key, profile[key] || ""])) as Draft);
  const [draft, setDraft] = useState<Draft>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => () => controllerRef.current?.abort(), []);
  const changed = EDITABLE_PROFILE_FIELDS.filter((key) => draft[key].trim() !== initial[key].trim());
  const setField = (key: EditableField, value: string) => setDraft((previous) => ({ ...previous, [key]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (saving || !changed.length) return;
    setSaving(true);
    setError(null);
    const controller = new AbortController();
    controllerRef.current = controller;
    const payload: LecturerProfileUpdate = {
      version: profile.version,
      ...Object.fromEntries(changed.map((key) => [key, draft[key].trim() || null])),
    };
    try {
      const updated = await updateMyLecturerProfile(payload, { signal: controller.signal });
      if (!controller.signal.aborted) onSaved(updated);
    } catch (requestError) {
      if (controller.signal.aborted) return;
      const messages: Record<string, string> = {
        VERSION_CONFLICT: copy.conflict,
        INVALID_ORCID: copy.invalidOrcid,
        ORCID_ALREADY_EXISTS: copy.orcidExists,
        INVALID_PROFILE_URL: copy.invalidUrl,
        PROFILE_URL_ALREADY_EXISTS: copy.urlExists,
        INVALID_BIRTH_DATE: copy.invalidBirthDate,
      };
      setError(requestError instanceof ApiError && requestError.code && messages[requestError.code]
        ? messages[requestError.code] : getApiErrorMessage(requestError, copy.saveError));
    } finally {
      if (!controller.signal.aborted) setSaving(false);
    }
  };

  const field = (key: EditableField, label: string, maxLength: number, type = "text") => (
    <label className="flex min-w-0 flex-col gap-1.5 text-sm text-slate-500">
      {label}
      <input name={key} type={type} defaultValue={initial[key]} maxLength={maxLength} disabled={saving}
        className={inputClass} onChange={(event) => setField(key, event.target.value)} />
      {key === "orcid" && <span className="text-sm text-slate-400">{copy.orcidHint}</span>}
    </label>
  );

  return (
    <form onSubmit={(event) => void submit(event)} onKeyDown={(event) => {
      if (event.key === "Enter" && event.nativeEvent.isComposing) event.preventDefault();
    }} className="overflow-hidden rounded-card border border-slate-200/80 bg-white">
      <div className="border-b border-slate-200/80 bg-slate-50/50 px-4 py-3.5">
        <h2 className="text-sm font-semibold text-slate-800">{copy.editTitle}</h2>
        <p className="mt-1 text-sm leading-6 text-slate-500">{copy.editHint}</p>
      </div>
      <div className="space-y-5 p-4 sm:p-5">
        <fieldset>
          <legend className="mb-3 text-sm font-semibold text-slate-800">{copy.academic}</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            {field("academic_rank", copy.academicRank, 50)}
            {field("academic_degree", copy.academicDegree, 50)}
            {field("position", copy.position, 100)}
            {field("specialization", copy.specialization, 200)}
          </div>
        </fieldset>
        <fieldset className="border-t border-slate-100 pt-4">
          <legend className="mb-3 text-sm font-semibold text-slate-800">{copy.contact}</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            {field("phone", copy.phone, 20, "tel")}
            <label className="flex flex-col gap-1.5 text-sm text-slate-500">{copy.dateOfBirth}
              <input name="date_of_birth" type="date" defaultValue={initial.date_of_birth} max={new Date().toISOString().slice(0, 10)} disabled={saving}
                className={inputClass} onChange={(event) => setField("date_of_birth", event.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5 text-sm text-slate-500">{copy.gender}
              <select name="gender" value={draft.gender} disabled={saving} className={inputClass} onChange={(event) => setField("gender", event.target.value)}>
                <option value="">{copy.notSpecified}</option><option value="Nam">{copy.genderMale}</option><option value="Nữ">{copy.genderFemale}</option><option value="Khác">{copy.genderOther}</option>
              </select>
            </label>
          </div>
        </fieldset>
        <fieldset className="border-t border-slate-100 pt-4">
          <legend className="mb-3 text-sm font-semibold text-slate-800">{copy.research}</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            {field("orcid", copy.orcid, 100)}
            {field("repository_profile_url", copy.repository, 2048, "url")}
          </div>
        </fieldset>
        {error && <p className="rounded-control border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">{error}</p>}
      </div>
      <div className="flex justify-end gap-2 border-t border-slate-100 bg-slate-50/50 px-4 py-3">
        <Button variant="secondary" disabled={saving} onClick={onCancel}>{copy.cancel}</Button>
        <Button type="submit" loading={saving} disabled={!changed.length}>{saving ? copy.saving : copy.save}</Button>
      </div>
    </form>
  );
}
