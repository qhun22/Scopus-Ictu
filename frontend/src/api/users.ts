import { apiGet, apiPatch, apiPost } from "./client";
import { User } from "./auth";
import type { LecturerUser } from "./lecturers";
import { safeDisplayName } from "../utils/displayName";

export async function getUsers(): Promise<User[]> {
  const users = await apiGet<User[]>("/api/v1/users");
  return users.map((u) => ({ ...u, display_name: safeDisplayName(u.display_name, u.role) }));
}

export function getUser(id: string): Promise<LecturerUser> {
  return apiGet<LecturerUser>(`/api/v1/users/${id}`);
}

export interface UpdateUserPayload {
  version: number;
  display_name?: string;
  email?: string;
  role?: string;
  staff_code?: string | null;
  academic_rank?: string | null;
  academic_degree?: string | null;
  position?: string | null;
  department?: string | null;
  faculty?: string | null;
  orcid?: string | null;
}

export interface VersionedUserAction {
  version: number;
}

export interface ResetPasswordPayload extends VersionedUserAction {
  new_password: string;
}

export interface ResetPasswordResponse {
  message: string;
  user_id: string;
  version: number;
}

export function updateUser(id: string, payload: UpdateUserPayload): Promise<LecturerUser> {
  return apiPatch<LecturerUser, UpdateUserPayload>(`/api/v1/users/${id}`, payload);
}

export function lockUser(id: string, version: number): Promise<LecturerUser> {
  return apiPost<LecturerUser, VersionedUserAction>(`/api/v1/users/${id}/lock`, { version });
}

export function unlockUser(id: string, version: number): Promise<LecturerUser> {
  return apiPost<LecturerUser, VersionedUserAction>(`/api/v1/users/${id}/unlock`, { version });
}

export function resetUserPassword(
  id: string,
  payload: ResetPasswordPayload,
): Promise<ResetPasswordResponse> {
  return apiPost<ResetPasswordResponse, ResetPasswordPayload>(
    `/api/v1/users/${id}/reset-password`,
    payload,
  );
}
