import { apiDelete, apiDownload, apiGet, apiPost, apiPut, type ApiRequestOptions } from "./client";

export interface LecturerAccount {
  user_id: string;
  email: string;
  role: string;
  is_active: boolean;
  version: number;
}

export interface LecturerStats {
  total_lecturers: number;
  account_linked: number;
  account_not_linked: number;
  account_locked: number;
  warning_count: number;
}

export interface LecturerUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
  lecturer_id: string | null;
  staff_code: string | null;
  academic_rank: string | null;
  academic_degree: string | null;
  position: string | null;
  department: string | null;
  faculty: string | null;
  orcid: string | null;
  is_active: boolean;
  version: number;
  created_at?: string;
  updated_at?: string;
  has_warning?: boolean;
  warning_reason?: string | null;
}

export interface LecturerForm {
  full_name: string;
  email: string;
  password?: string;
  // staff_code is OPTIONAL: blank/omitted -> stored as NULL on the server.
  staff_code: string | null;
  role: string;
  academic_degree: string;
  department: string;
}

export interface LecturerUpdatePayload {
  version: number;
  full_name?: string;
  email?: string;
  // staff_code update contract:
  //   * non-empty string -> trim & set
  //   * null              -> clear to NULL
  //   * undefined         -> unchanged (field omitted)
  staff_code?: string | null;
  role?: string;
  academic_degree?: string | null;
  academic_rank?: string | null;
  position?: string | null;
  faculty?: string | null;
  department?: string | null;
  orcid?: string | null;
  specialization?: string | null;
  gender?: string | null;
  date_of_birth?: string | null;
  phone?: string | null;
  grant_account?: boolean;
  password?: string;
}

export interface LecturerMasterItem {
  id: string;
  full_name: string;
  full_name_normalized: string;
  staff_code: string | null;
  institutional_email: string | null;
  academic_degree: string | null;
  academic_rank: string | null;
  position: string | null;
  faculty: string | null;
  department: string | null;
  orcid: string | null;
  specialization: string | null;
  gender: string | null;
  date_of_birth: string | null;
  phone: string | null;
  profile_url: string | null;
  is_active: boolean;
  has_user_account: boolean;
  has_warning?: boolean;
  warning_reason?: string | null;
  account: LecturerAccount | null;
  version: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface LecturerMasterResponse {
  items: LecturerMasterItem[];
  total: number;
  page: number;
  page_size: number;
  stats: LecturerStats;
}

export interface LecturerMasterQuery {
  page?: number;
  page_size?: number;
  search?: string;
  faculty?: string;
  department?: string;
}

export async function getLecturers(
  query: LecturerMasterQuery = {},
): Promise<LecturerMasterResponse> {
  const params = new URLSearchParams();
  if (query.page) params.set("page", String(query.page));
  if (query.page_size) params.set("page_size", String(query.page_size));
  if (query.search) params.set("search", query.search);
  if (query.faculty) params.set("faculty", query.faculty);
  if (query.department) params.set("department", query.department);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<LecturerMasterResponse>(`/api/v1/lecturers${suffix}`);
}

export async function getLecturerMaster(
  query: LecturerMasterQuery = {},
): Promise<LecturerMasterResponse> {
  return getLecturers(query);
}

export async function createLecturer(payload: LecturerForm): Promise<LecturerUser> {
  return apiPost<LecturerUser, LecturerForm>("/api/v1/lecturers", payload);
}

export async function updateLecturer(
  id: string,
  payload: LecturerUpdatePayload,
): Promise<LecturerUser> {
  return apiPut<LecturerUser, LecturerUpdatePayload>(`/api/v1/lecturers/${id}`, payload);
}

export async function deleteLecturer(id: string): Promise<{ message: string }> {
  return apiDelete(`/api/v1/lecturers/${id}`);
}

export async function exportLecturersJson(
  options: ApiRequestOptions = {},
): Promise<{ blob: Blob; filename: string; recordCount: number }> {
  const { blob, filename } = await apiDownload("/api/v1/lecturers/export", options);

  let recordCount = 0;
  try {
    const text = await blob.text();
    const parsed = JSON.parse(text) as {
      dataset?: { record_count?: number };
      lecturers?: unknown[];
    };
    recordCount = parsed?.dataset?.record_count ?? parsed?.lecturers?.length ?? 0;
  } catch {
    // ignore
  }

  return { blob, filename, recordCount };
}
