import { apiDelete, apiGet, apiPost, apiPut } from "./client";

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
  academic_degree?: string;
  academic_rank?: string;
  position?: string;
  faculty?: string;
  department?: string;
  orcid?: string;
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

export async function exportLecturersJson(): Promise<{ blob: Blob; filename: string; recordCount: number }> {
  const token = localStorage.getItem("token");
  const response = await fetch("/api/v1/lecturers/export", {
    method: "GET",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    let errorDetail = "Không thể xuất dữ liệu giảng viên.";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  const contentDisposition = response.headers.get("Content-Disposition");
  let filename = "ictu_lecturers.json";
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?([^";]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const text = await response.text();
  let recordCount = 0;
  try {
    const parsed = JSON.parse(text);
    recordCount = parsed?.dataset?.record_count ?? parsed?.lecturers?.length ?? 0;
  } catch {
    // ignore
  }

  const blob = new Blob([text], { type: "application/json;charset=utf-8" });
  return { blob, filename, recordCount };
}
