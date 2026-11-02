import { ApiRequestOptions, apiGet, apiPost } from "./client";
import {
  ApprovedScopusIdentity,
  LecturerScopusProfile,
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
