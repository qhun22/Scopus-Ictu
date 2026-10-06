import { ApiRequestOptions, apiGet } from "./client";
import {
  ApprovedScopusIdentity,
  LecturerScopusProfile,
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
