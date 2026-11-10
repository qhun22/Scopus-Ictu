import { ApiError, apiGet, type ApiRequestOptions } from "./client";
import type { ScopusImportItem } from "./lecturerImport";
import {
  assignScopusIdentity,
  getLecturerScopusIdentities,
  setPrimaryScopusIdentity,
} from "./lecturerScopus";

export interface ScopusImportFailure {
  item: ScopusImportItem;
  message: string;
}

export function getPendingScopusImportReview(
  lecturerId?: string, options: ApiRequestOptions = {},
): Promise<ScopusImportItem[]> {
  const query = lecturerId ? `?lecturer_id=${encodeURIComponent(lecturerId)}` : "";
  return apiGet<ScopusImportItem[]>(`/api/v1/lecturers/scopus-import-review${query}`, options);
}

/** Called only after the reviewer explicitly confirms the displayed pairs and reason.
 * Each write uses the existing human-review APIs; retries retain successful work.
 */
export async function applyReviewedScopusImport(
  items: ScopusImportItem[],
  reason: string,
  fallbackMessage: string,
  onProgress: (done: number) => void,
): Promise<ScopusImportFailure[]> {
  if (!reason.trim()) throw new Error(fallbackMessage);
  const failures: ScopusImportFailure[] = [];
  for (const [index, item] of items.entries()) {
    let currentId: string | null = null;
    try {
      if (!item.lecturer_id) throw new Error(fallbackMessage);
      const saved = await getLecturerScopusIdentities(item.lecturer_id);
      const byId = new Map(saved.map((identity) => [identity.scopus_id, identity.identity_id]));
      for (const scopusId of item.scopus_ids) {
        currentId = scopusId;
        if (byId.has(scopusId)) continue;
        const assigned = await assignScopusIdentity(item.lecturer_id, {
          scopus_id: scopusId, reason, create_author_if_missing: true,
        });
        byId.set(scopusId, assigned.identity_id);
      }
      currentId = item.primary_scopus_id;
      const primary = item.primary_scopus_id ? byId.get(item.primary_scopus_id) : null;
      if (primary && !saved.some((identity) => identity.identity_id === primary && identity.is_primary)) {
        try {
          await setPrimaryScopusIdentity(item.lecturer_id, { identity_id: primary, reason });
        } catch (error) {
          if (!(error instanceof ApiError && error.code === "ALREADY_PRIMARY")) throw error;
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : fallbackMessage;
      failures.push({ item, message: `${currentId ? `${currentId}: ` : ""}${message}` });
    } finally {
      onProgress(index + 1);
    }
  }
  return failures;
}
