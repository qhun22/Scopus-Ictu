import { apiPost, apiPostForm } from "./client";

export interface LecturerDatasetMeta {
  name?: string | null;
  schema_version: string;
  institution?: string | null;
  source?: string | null;
  source_url?: string | null;
  source_system?: string | null;
  generated_at?: string | null;
  parser_version?: string | null;
  record_count: number;
}

export interface LecturerDatasetConflict {
  record_full_name: string;
  matched_by: string;
  existing_id: string;
  existing_full_name: string;
  existing_email: string | null;
}

export interface LecturerPreviewResponse {
  dataset: LecturerDatasetMeta;
  summary: {
    total: number;
    valid: number;
    create: number;
    update: number;
    unchanged: number;
    conflicts: number;
  };
  conflicts: LecturerDatasetConflict[];
  filename: string;
  parser_version: string;
}

export interface LecturerImportResponse {
  dataset: LecturerDatasetMeta;
  summary: {
    total: number;
    created: number;
    updated: number;
    unchanged: number;
    conflicts: number;
  };
  conflicts: LecturerDatasetConflict[];
  snapshot_ids: string[];
  filename: string;
  parser_version: string;
}

export class LecturerDatasetError extends Error {
  public readonly code?: string;
  public readonly status?: number;

  constructor(message: string, status?: number, code?: string) {
    super(message);
    this.name = "LecturerDatasetError";
    this.status = status;
    this.code = code;
  }
}

async function postForm<T>(
  path: string,
  file: File,
): Promise<T> {
  const form = new FormData();
  form.append("file", file, file.name);
  return apiPostForm<T>(path, form);
}

export function previewLecturerDataset(
  file: File,
): Promise<LecturerPreviewResponse> {
  return postForm<LecturerPreviewResponse>(
    "/api/v1/lecturers/import/preview",
    file,
  );
}

export function importLecturerDataset(
  file: File,
): Promise<LecturerImportResponse> {
  return postForm<LecturerImportResponse>(
    "/api/v1/lecturers/import",
    file,
  );
}

export function rollbackLecturerDataset(
  importId: string,
): Promise<{
  message: string;
  import_id: string;
  created_records_removed: number;
  updated_records_restored: number;
  manual_records_preserved: number;
  multi_source_records_preserved: number;
  rolled_back_at: string;
}> {
  return apiPost<{
    message: string;
    import_id: string;
    created_records_removed: number;
    updated_records_restored: number;
    manual_records_preserved: number;
    multi_source_records_preserved: number;
    rolled_back_at: string;
  }>(`/api/v1/lecturers/import/${importId}/rollback`);
}
