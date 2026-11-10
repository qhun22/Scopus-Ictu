import { ApiRequestOptions, apiDelete, apiGet, apiPatch, apiPost } from "./client";
import {
  ApprovedScopusIdentity,
  LecturerScopusProfile,
  LecturerProfileUpdate,
  LecturerPublicationsResponse,
  PrimaryIdentityResult,
} from "../types/lecturerScopus";

export function getMyLecturerProfile(
  options: ApiRequestOptions = {},
): Promise<LecturerScopusProfile> {
  return apiGet<LecturerScopusProfile>("/api/v1/lecturers/me/profile", options);
}

export function getMyApprovedScopusIdentities(
  options: ApiRequestOptions = {},
): Promise<ApprovedScopusIdentity[]> {
  return apiGet<ApprovedScopusIdentity[]>("/api/v1/lecturers/me/identities", options);
}

export function updateMyLecturerProfile(
  payload: LecturerProfileUpdate,
  options: ApiRequestOptions = {},
): Promise<LecturerScopusProfile> {
  return apiPatch<LecturerScopusProfile>("/api/v1/lecturers/me/profile", payload, options);
}

export function getMyLecturerPublications(
  params: { page?: number; page_size?: number } = {},
  options: ApiRequestOptions = {},
): Promise<LecturerPublicationsResponse> {
  const page = Math.max(1, Math.trunc(params.page ?? 1));
  const pageSize = Math.min(100, Math.max(1, Math.trunc(params.page_size ?? 20)));
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  return apiGet<LecturerPublicationsResponse>(
    `/api/v1/lecturers/me/publications?${query.toString()}`,
    options,
  );
}

/** ADMIN/REVIEWER: approved Scopus IDs of one lecturer (with the main-ID label). */
export function getLecturerScopusIdentities(
  lecturerId: string,
  options: ApiRequestOptions = {},
): Promise<ApprovedScopusIdentity[]> {
  return apiGet<ApprovedScopusIdentity[]>(
    `/api/v1/lecturers/${encodeURIComponent(lecturerId)}/scopus/identities`,
    options,
  );
}

export function setPrimaryScopusIdentity(
  lecturerId: string,
  body: { identity_id: string; reason: string },
): Promise<PrimaryIdentityResult> {
  return apiPost<PrimaryIdentityResult, typeof body>(
    `/api/v1/lecturers/${encodeURIComponent(lecturerId)}/scopus/primary-identity`,
    body,
  );
}

export function clearPrimaryScopusIdentity(
  lecturerId: string,
  body: { reason: string },
): Promise<PrimaryIdentityResult> {
  return apiPost<PrimaryIdentityResult, typeof body>(
    `/api/v1/lecturers/${encodeURIComponent(lecturerId)}/scopus/primary-identity/clear`,
    body,
  );
}

export interface AssignScopusIdentityResult {
  identity_id: string;
  scopus_id: string;
  scopus_preferred_name: string;
  already_approved: boolean;
}

/** ADMIN/REVIEWER: assign one Scopus author ID to a lecturer directly from the
 * profile screen (still goes through the normal candidate-review boundary). */
export function assignScopusIdentity(
  lecturerId: string,
  body: { scopus_id: string; reason: string; create_author_if_missing?: boolean },
): Promise<AssignScopusIdentityResult> {
  return apiPost<AssignScopusIdentityResult, typeof body>(
    `/api/v1/lecturers/${encodeURIComponent(lecturerId)}/scopus/identities`,
    body,
  );
}

export interface RevokeScopusIdentityResult {
  identity_id: string;
  scopus_id: string;
}

/** ADMIN-only: undo a mistaken "Gán ID Scopus" (still an audited revoke, not a delete). */
export function revokeScopusIdentity(
  lecturerId: string,
  identityId: string,
  reason: string,
): Promise<RevokeScopusIdentityResult> {
  return apiDelete<RevokeScopusIdentityResult>(
    `/api/v1/lecturers/${encodeURIComponent(lecturerId)}/scopus/identities/${encodeURIComponent(identityId)}?reason=${encodeURIComponent(reason)}`,
  );
}
