import { forwardRef, useCallback, useEffect, useId, useImperativeHandle, useRef, useState } from "react";
import {
  assignScopusIdentity,
  clearPrimaryScopusIdentity,
  getLecturerScopusIdentities,
  revokeScopusIdentity,
  setPrimaryScopusIdentity,
} from "../../api/lecturerScopus";
import { ApiError } from "../../api/client";
import ConfirmModal from "../../components/common/ConfirmModal";
import { getPendingScopusImportReview } from "../../api/lecturerScopusImport";
import { ApprovedScopusIdentity } from "../../types/lecturerScopus";
import Button from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";
import { useI18n } from "../../i18n";

export interface ScopusIdentitiesEditorHandle {
  validate: () => boolean;
  needsReason: () => boolean;
  save: (reason: string) => Promise<void>;
}

interface SavedIdentity {
  scopusId: string;
  identityId: string;
  preferredName: string;
  publicationCount?: number;
  isPrimary: boolean;
}

const toSavedIdentity = (identity: ApprovedScopusIdentity): SavedIdentity => ({
  scopusId: identity.scopus_id,
  identityId: identity.identity_id,
  preferredName: identity.preferred_name,
  publicationCount: identity.publication_count,
  isPrimary: Boolean(identity.is_primary),
});

/** Adding IDs and choosing the main ID only edits a draft.
 * The lecturer form explicitly saves it through the existing review APIs.
 */
const ScopusIdentitiesSummary = forwardRef<ScopusIdentitiesEditorHandle, {
  lecturerId: string;
  disabled?: boolean;
}>(function ScopusIdentitiesSummary({ lecturerId, disabled = false }, ref) {
  const { t } = useI18n();
  const toast = useToast();
  const s = t.lecturers.scopus;
  const panelId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const initializedRef = useRef(false);
  const [expanded, setExpanded] = useState(false);
  const [identities, setIdentities] = useState<SavedIdentity[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [inputId, setInputId] = useState("");
  const [pendingIds, setPendingIds] = useState<string[]>([]);
  const [importedIds, setImportedIds] = useState<string[]>([]);
  const [selectedPrimaryId, setSelectedPrimaryId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revokeTargetId, setRevokeTargetId] = useState<string | null>(null);
  const [revokeReason, setRevokeReason] = useState("");
  const [revoking, setRevoking] = useState(false);
  const busy = disabled || saving;
  const savedMain = identities?.find((identity) => identity.isPrimary);
  const primaryChanged = identities !== null && selectedPrimaryId !== (savedMain?.scopusId ?? null);
  const hasChanges = pendingIds.length > 0 || primaryChanged;
  const hasImportedDraft = pendingIds.some((id) => importedIds.includes(id));
  const list = [
    ...(identities ?? []).map((identity) => ({ scopusId: identity.scopusId, saved: identity })),
    ...pendingIds.map((scopusId) => ({ scopusId, saved: null })),
  ];

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setLoadError(null);
    try {
      const [approved, imported] = await Promise.all([
        getLecturerScopusIdentities(lecturerId, { signal }),
        getPendingScopusImportReview(lecturerId, { signal }),
      ]);
      const result = approved.map(toSavedIdentity);
      if (signal?.aborted) return;
      setIdentities(result);
      if (!initializedRef.current) {
        const source = imported.find((item) => item.lecturer_id === lecturerId);
        const draft = source?.scopus_ids.filter((id) => !result.some((row) => row.scopusId === id)) ?? [];
        setPendingIds(draft);
        setImportedIds(draft);
        setSelectedPrimaryId(result.find((identity) => identity.isPrimary)?.scopusId ?? source?.primary_scopus_id ?? null);
        if (draft.length) setExpanded(true);
        initializedRef.current = true;
      }
    } catch (e) {
      if (!signal?.aborted) setLoadError(e instanceof ApiError ? e.detail || e.message : s.loadError);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [lecturerId, s.loadError]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const addId = () => {
    const id = inputId.trim();
    if (!id || busy || loading || loadError) return;
    if (list.some((row) => row.scopusId === id)) {
      toast.warning(s.title, s.duplicateId.replace("{id}", id));
      return;
    }
    setPendingIds((previous) => [...previous, id]);
    setInputId("");
    setError(null);
    inputRef.current?.focus();
  };

  const validate = () => {
    if (inputId.trim()) {
      setExpanded(true);
      setError(s.addBeforeSave);
      requestAnimationFrame(() => inputRef.current?.focus());
      return false;
    }
    if (!hasChanges) return true;
    if (loading || loadError) {
      setExpanded(true);
      setError(loadError || s.loadError);
      return false;
    }
    setError(null);
    return true;
  };

  const save = async (reason: string) => {
    if (!validate()) throw new Error(s.assignError);
    if (!hasChanges) return;
    const why = reason.trim();
    if (!why) {
      setError(s.reasonRequired);
      throw new Error(s.reasonRequired);
    }
    const resolvedIds = new Map((identities ?? []).map((identity) => [identity.scopusId, identity.identityId]));
    const missingAuthors: string[] = [];
    let currentId: string | null = null;
    setSaving(true);
    setError(null);
    try {
      for (const scopusId of pendingIds) {
        currentId = scopusId;
        let result;
        try {
          result = await assignScopusIdentity(lecturerId, { scopus_id: scopusId, reason: why, create_author_if_missing: true });
        } catch (e) {
          if (e instanceof ApiError && e.code === "SCOPUS_AUTHOR_NOT_FOUND") {
            missingAuthors.push(s.unknownAuthor.replace("{id}", scopusId));
            currentId = null;
            continue;
          }
          throw e;
        }
        resolvedIds.set(scopusId, result.identity_id);
        // Retain each successful write immediately, so retries only save the remainder.
        setIdentities((previous) => [...(previous ?? []).filter((identity) => identity.scopusId !== scopusId), {
          scopusId: result.scopus_id,
          identityId: result.identity_id,
          preferredName: result.scopus_preferred_name,
          isPrimary: false,
        }]);
        setPendingIds((previous) => previous.filter((id) => id !== scopusId));
        currentId = null;
      }
      // An unknown author must not block a human-selected, approved main ID.
      if (primaryChanged && (selectedPrimaryId === null || resolvedIds.has(selectedPrimaryId))) {
        if (selectedPrimaryId !== null) {
          const identityId = resolvedIds.get(selectedPrimaryId);
          if (!identityId) throw new Error(s.assignError);
          await setPrimaryScopusIdentity(lecturerId, { identity_id: identityId, reason: why });
        } else {
          await clearPrimaryScopusIdentity(lecturerId, { reason: why });
        }
        setIdentities((previous) => previous?.map((identity) => ({ ...identity, isPrimary: identity.scopusId === selectedPrimaryId })) ?? null);
      }
      if (missingAuthors.length > 0) throw new Error(missingAuthors.join("\n"));
    } catch (e) {
      setExpanded(true);
      const message = e instanceof Error ? e.message : s.assignError;
      setError(e instanceof ApiError && e.status === 405
        ? s.methodUnavailable
        : currentId
          ? s.saveIdError.replace("{id}", currentId).replace("{message}", e instanceof ApiError ? e.detail || e.message : message)
          : e instanceof ApiError ? e.detail || e.message : message);
      // Reconcile a response lost after a commit without overwriting the draft main ID.
      try {
        const current = (await getLecturerScopusIdentities(lecturerId)).map(toSavedIdentity);
        setIdentities(current);
        setPendingIds((previous) => previous.filter((id) => !current.some((identity) => identity.scopusId === id)));
      } catch {
        // Successful responses above remain recorded locally if refresh is unavailable.
      }
      throw e;
    } finally {
      setSaving(false);
    }
  };

  useImperativeHandle(ref, () => ({ validate, needsReason: () => hasChanges, save }));

  const openRevoke = (identity: SavedIdentity) => {
    if (busy || loading || loadError) return;
    setRevokeTargetId(identity.identityId);
    setRevokeReason(s.revokeReasonDefault);
    setError(null);
  };

  const cancelRevoke = () => {
    setRevokeTargetId(null);
    setRevokeReason("");
  };

  const confirmRevoke = async () => {
    const target = identities?.find((identity) => identity.identityId === revokeTargetId);
    if (!target) return;
    const why = revokeReason.trim();
    if (!why) {
      setError(s.reasonRequired);
      return;
    }
    setRevoking(true);
    setError(null);
    try {
      await revokeScopusIdentity(lecturerId, target.identityId, why);
      setIdentities((previous) => previous?.filter((identity) => identity.identityId !== target.identityId) ?? null);
      setSelectedPrimaryId((previous) => (previous === target.scopusId ? null : previous));
      toast.success(s.title, s.revokeSuccess.replace("{id}", target.scopusId));
      setRevokeTargetId(null);
      setRevokeReason("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail || e.message : s.revokeError);
    } finally {
      setRevoking(false);
    }
  };

  const identityLink = (scopusId: string) => (
    <a
      href={`https://www.scopus.com/authid/detail.uri?authorId=${encodeURIComponent(scopusId)}`}
      target="_blank"
      rel="noreferrer"
      aria-label={s.openScopus.replace("{id}", scopusId)}
      className="inline-flex min-w-0 items-center gap-1 break-all font-semibold text-brand hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
    >
      {scopusId}
      <svg aria-hidden="true" className="h-3.5 w-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
        <path strokeLinecap="round" strokeLinejoin="round" d="M14 4h6v6m0-6L10 14m0-9H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-4" />
      </svg>
    </a>
  );

  const revokeTarget = identities?.find((identity) => identity.identityId === revokeTargetId) ?? null;

  return (
    <>
    <section aria-labelledby={`${panelId}-title`} aria-busy={loading || saving} className="mt-4 overflow-hidden rounded-[5px] border border-slate-200 bg-white font-['Saira',Arial,sans-serif] text-[14px] leading-5">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 sm:px-4">
        <div className="flex flex-wrap items-center gap-2">
          <h4 id={`${panelId}-title`} className="font-bold text-slate-700">{s.title}</h4>
          {list.length > 0 && !loadError && (
            <span className="rounded-[5px] bg-slate-100 px-2 py-0.5 text-slate-600">
              {s.listCount.replace("{count}", String(list.length))}
            </span>
          )}
        </div>
        <button type="button" aria-expanded={expanded} aria-controls={`${panelId}-details`} onClick={() => setExpanded((value) => !value)} className="inline-flex items-center gap-1.5 rounded-[5px] px-2 py-1 font-semibold text-brand hover:bg-brand-subtle focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand">
          {expanded ? s.collapse : s.expand}
          <svg aria-hidden="true" className={`h-4 w-4 transition-transform ${expanded ? "rotate-180" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path strokeLinecap="round" strokeLinejoin="round" d="m6 9 6 6 6-6" />
          </svg>
        </button>
      </div>
      <div className="px-3 pb-3 sm:px-4" aria-live="polite">
        {loading && identities === null ? <p className="text-slate-500">{t.common.loading}</p> : loadError ? (
          <div className="flex flex-wrap items-center gap-2">
            <p role="alert" className="text-rose-600">{loadError}</p>
            <button type="button" onClick={() => void load()} disabled={loading || busy} className="font-semibold text-brand underline disabled:opacity-50">{t.common.refresh}</button>
          </div>
        ) : savedMain ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2" data-testid="lecturer-scopus-main-id">
            {identityLink(savedMain.scopusId)}
            <span className="min-w-0 break-words text-slate-600">{savedMain.preferredName}</span>
          </div>
        ) : hasImportedDraft && selectedPrimaryId ? (
          <p className="text-slate-600">{s.importedMainLabel}: {selectedPrimaryId}</p>
        ) : <p className="text-slate-500">{list.length ? s.noMainId : s.empty}</p>}
        {hasChanges && <p className="mt-2 text-slate-500">{hasImportedDraft ? s.importedHint : s.pendingHint}</p>}
      </div>

      <div id={`${panelId}-details`} hidden={!expanded} className="border-t border-slate-200">
        <div className="grid grid-cols-1 lg:grid-cols-2">
          <div role="group" aria-labelledby={`${panelId}-input-label`} className="min-w-0 space-y-3 bg-slate-50/70 px-3 py-3 sm:px-4">
            <label id={`${panelId}-input-label`} htmlFor={`${panelId}-input`} className="block font-semibold text-slate-700">{s.idLabel}</label>
            <input
              ref={inputRef}
              id={`${panelId}-input`}
              type="text"
              inputMode="numeric"
              maxLength={50}
              value={inputId}
              onChange={(event) => setInputId(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  event.stopPropagation();
                  addId();
                }
              }}
              placeholder={s.idPlaceholder}
              disabled={busy || loading || Boolean(loadError)}
              className="h-9 w-full min-w-0 rounded-[5px] border border-slate-200 bg-white px-3 text-slate-800 focus:border-brand focus:outline-none disabled:bg-slate-100"
            />
            <Button type="button" variant="secondary" onClick={addId} disabled={busy || loading || Boolean(loadError) || !inputId.trim()} className="!text-[14px]">
              {s.addRow}
            </Button>
          </div>

          <div className="min-w-0 border-t border-slate-200 px-3 py-3 sm:px-4 lg:border-l lg:border-t-0">
            <h5 id={`${panelId}-list-title`} className="mb-3 font-semibold text-slate-700">{s.addedIds}</h5>
            {list.length === 0 ? <p className="text-slate-500">{loading ? t.common.loading : s.emptyList}</p> : (
              <ul aria-labelledby={`${panelId}-list-title`} className="space-y-2" data-testid="lecturer-scopus-identities">
                {list.map((row) => (
                  <li key={row.scopusId} className="rounded-[5px] border border-slate-200 bg-white px-3 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          {row.saved ? identityLink(row.scopusId) : <span className="break-all font-semibold text-slate-700">{row.scopusId}</span>}
                        </div>
                        {row.saved && <p className="break-words text-slate-500">{row.saved.preferredName !== row.scopusId ? row.saved.preferredName : ""}{row.saved.publicationCount !== undefined && `${row.saved.preferredName && row.saved.preferredName !== row.scopusId ? " · " : ""}${s.publications.replace("{count}", String(row.saved.publicationCount))}`}</p>}
                      </div>
                      <label className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 font-medium text-slate-600">
                        <input type="checkbox" checked={selectedPrimaryId === row.scopusId} onChange={(event) => { setSelectedPrimaryId(event.target.checked ? row.scopusId : null); setError(null); }} disabled={busy || loading || Boolean(loadError)} className="h-4 w-4 rounded border-slate-300 accent-slate-600" />
                        {s.chooseMainId}
                      </label>
                      {!row.saved && (
                        <button type="button" aria-label={s.removeRow} disabled={busy} onClick={() => { setPendingIds((previous) => previous.filter((id) => id !== row.scopusId)); setSelectedPrimaryId((previous) => previous === row.scopusId ? (savedMain?.scopusId ?? null) : previous); setError(null); }} className="inline-flex h-9 w-8 shrink-0 items-center justify-center rounded-[5px] text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-30">
                          <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" d="m6 6 12 12M6 18 18 6" /></svg>
                        </button>
                      )}
                      {row.saved && (
                        <button type="button" aria-label={s.removeSavedRow} disabled={busy || revoking} onClick={() => openRevoke(row.saved!)} className="inline-flex h-9 w-8 shrink-0 items-center justify-center rounded-[5px] text-slate-400 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-30">
                          <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m2 0-.7 11.2a2 2 0 0 1-2 1.8H9.7a2 2 0 0 1-2-1.8L7 7" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
      {error && <p role="alert" className="whitespace-pre-line border-t border-rose-100 bg-rose-50 px-3 py-2 text-rose-700 sm:px-4">{error}</p>}
    </section>
    <ConfirmModal
      open={revokeTarget !== null}
      title={revokeTarget ? s.revokeConfirmTitle.replace("{id}", revokeTarget.scopusId) : ""}
      variant="danger"
      confirmLabel={s.revokeConfirm}
      cancelLabel={s.revokeCancel}
      loading={revoking}
      confirmDisabled={!revokeReason.trim()}
      autoFocusConfirm={false}
      description={
        <div className="space-y-2 text-[14px]">
          <label htmlFor="scopus-revoke-reason" className="block font-semibold text-slate-700">
            {s.reasonLabel}
          </label>
          <input
            id="scopus-revoke-reason"
            type="text"
            autoFocus
            value={revokeReason}
            onChange={(event) => setRevokeReason(event.target.value)}
            disabled={revoking}
            className="h-9 w-full rounded-[5px] border border-slate-200 bg-white px-3 text-slate-800 focus:border-brand focus:outline-none disabled:bg-slate-100"
          />
        </div>
      }
      onCancel={cancelRevoke}
      onConfirm={() => void confirmRevoke()}
    />
    </>
  );
});

export default ScopusIdentitiesSummary;
