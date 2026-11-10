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

export interface ScopusImportItem {
  lecturer_id: string | null;
  full_name: string;
  institutional_email: string | null;
  scopus_ids: string[];
  primary_scopus_id: string | null;
}

export interface LecturerPreviewResponse {
  scopus_review_items?: ScopusImportItem[];
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

export interface AccountWarningItem {
  record_full_name: string | null;
  matched_by?: string;
  existing_id?: string | null;
  existing_full_name?: string | null;
  existing_email?: string | null;
  blocking?: boolean;
  reason: string;
}

export interface LecturerImportResponse {
  scopus_review_items?: ScopusImportItem[];
  dataset: LecturerDatasetMeta;
  summary: {
    total: number;
    created: number;
    updated: number;
    unchanged: number;
    conflicts: number;
    blocking_conflicts?: number;
    absent_from_file?: number;
    deleted?: number;
    accounts_created?: number;
    accounts_skipped?: number;
    account_warnings?: AccountWarningItem[];
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
  extraFields?: Record<string, string>,
): Promise<T> {
  const form = new FormData();
  form.append("file", file, file.name);
  if (extraFields) {
    for (const [key, value] of Object.entries(extraFields)) {
      form.append(key, value);
    }
  }
  return apiPostForm<T>(path, form);
}

export function previewLecturerDataset(
  file: File,
  allowDuplicate = false,
): Promise<LecturerPreviewResponse> {
  const suffix = allowDuplicate ? "?allow_duplicate=true" : "";
  return postForm<LecturerPreviewResponse>(
    `/api/v1/lecturers/import/preview${suffix}`,
    file,
  );
}

export function importLecturerDataset(
  file: File,
  // When given, the backend uses this exact UUID as the new import's id
  // instead of generating its own — so the id shown during preview doesn't
  // change once the import is confirmed. Best-effort: an invalid or already
  // taken id is silently ignored server-side (a fresh one gets generated).
  clientImportId?: string,
): Promise<LecturerImportResponse> {
  return postForm<LecturerImportResponse>(
    "/api/v1/lecturers/import",
    file,
    clientImportId ? { client_import_id: clientImportId } : undefined,
  );
}

export function cancelLecturerDatasetImport(
  file: File,
): Promise<{ id: string; status: "CANCELLED" }> {
  return postForm<{ id: string; status: "CANCELLED" }>(
    "/api/v1/lecturers/import/cancel",
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
