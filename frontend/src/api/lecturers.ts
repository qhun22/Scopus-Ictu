import { apiDelete, apiGet, apiPost } from "./client";

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
}

export interface LecturerForm {
  full_name: string;
  email: string;
  password?: string;
  staff_code: string;
  role: string;
  academic_degree: string;
  department: string;
}

export async function getLecturers(): Promise<LecturerUser[]> {
  return apiGet<LecturerUser[]>("/api/v1/users");
}

export async function createLecturer(payload: LecturerForm): Promise<LecturerUser> {
  return apiPost<LecturerUser, LecturerForm>("/api/v1/lecturers", payload);
}

export async function deleteLecturer(id: string): Promise<{ message: string }> {
  return apiDelete(`/api/v1/lecturers/${id}`);
}
