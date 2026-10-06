import { ApiRequestOptions, apiGet } from "./client";
import {
  ApprovedScopusIdentity,
  LecturerScopusProfile,
  LecturerPublicationsResponse,
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
