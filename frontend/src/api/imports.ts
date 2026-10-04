import { apiDelete, apiGet, apiPost, apiPostForm } from "./client";

export type ImportStatus =
  | "RECEIVED"
  | "PARSING"
  | "VALIDATED"
  | "STAGED"
  | "APPLIED"
  | "FAILED"
  | "CANCELLED"
  | "IMPORTED";

export interface NormalizationData {
  status: "NORMALIZING" | "COMPLETED" | "CANCELLED" | "FAILED";
  total_records: number;
  progress_percent: number;
  canonical_new: number;
  canonical_existing: number;
  canonical_metadata_changed: number;
  canonical_failed: number;
  canonical_processed: number;
  canonical_intra_duplicate: number;
}

export interface LecturerImportSummaryData {
  created?: number;
  updated?: number;
  unchanged?: number;
  conflicts?: number;
  warnings?: number;
  dataset_name?: string;
  schema_version?: string;
}

export interface AuthorNormalizationSummary {
  status: "NORMALIZING" | "COMPLETED" | "FAILED";
  raw_records_processed: number;
  raw_records_failed: number;
  author_occurrences: number;
  unique_authors_seen: number;
  authors_created: number;
  authors_existing: number;
  publication_author_links_created: number;
  publication_author_links_existing: number;
  variants_created: number;
  variants_existing: number;
  conflicts: number;
  errors?: Array<{
    row_number?: number;
    code?: string;
    message?: string;
    [key: string]: unknown;
  }>;
}

export interface ImportNormalizationSummary {
  status?: NormalizationData["status"];
  authors?: AuthorNormalizationSummary | null;
  [key: string]: unknown;
}

export interface ScopusImport {
  id: string;
  type?: "SCOPUS" | "LECTURERS";
  file_name: string;
  status: ImportStatus;
  total_records: number;
  imported_records: number;
  failed_records: number;
  processed_records: number;
  progress_percent: number;
  duplicate_candidates: number;
  row_errors: Array<{ row_number?: number; code?: string; message?: string }>;
  error_summary: Record<string, unknown> | null;
  normalization: NormalizationData | null;
  version: number;
  created_at: string;
  updated_at: string;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number;
  is_terminal: boolean;
  performed_by: string | null;
  can_delete?: boolean;
  // M2.6A follow-up: truthful import usage state.
  in_use?: boolean;
  archived?: boolean;
  usage?: {
    publication_source_links: number;
    author_variant_links: number;
  };
  scopus_summary?: Record<string, unknown> | null;
  lecturer_summary?: LecturerImportSummaryData | null;
  // M2.6B: nested author normalization counters
  normalization_summary?: ImportNormalizationSummary | null;
}

export interface UnifiedImportStats {
  total_imports: number;
  success_count: number;
  processing_count: number;
  failed_count: number;
}

export interface ImportHistoryResponse {
  items: ScopusImport[];
  stats?: UnifiedImportStats | null;
}

export interface ImportConfig {
  supported_extensions: string[];
  max_bytes: number;
}

export function getImportConfig(): Promise<ImportConfig> {
  return apiGet<ImportConfig>("/api/v1/imports/config");
}

export function getImportHistory(
  includeArchived = false,
): Promise<ImportHistoryResponse> {
  const query = includeArchived ? "?include_archived=true" : "";
  return apiGet<ImportHistoryResponse>(`/api/v1/imports${query}`);
}

export function getImportDetail(id: string): Promise<ScopusImport> {
  return apiGet<ScopusImport>(`/api/v1/imports/${id}`);
}

export function uploadScopusCsv(file: File, allowDuplicate = false): Promise<ScopusImport> {
  const form = new FormData();
  form.append("file", file, file.name);
  const suffix = allowDuplicate ? "?allow_duplicate=true" : "";
  return apiPostForm<ScopusImport>(`/api/v1/imports/scopus${suffix}`, form);
}

export function cancelImport(id: string): Promise<ScopusImport> {
  return apiPost<ScopusImport>(`/api/v1/imports/${id}/cancel`);
}

export function deleteImport(id: string): Promise<{ message: string; id: string }> {
  return apiDelete<{ message: string; id: string }>(`/api/v1/imports/${id}`);
}

export function rollbackLecturerImport(id: string): Promise<{ message: string; id: string }> {
  return apiPost<{ message: string; id: string }>(`/api/v1/imports/${id}/rollback`);
}

export function normalizeImport(id: string): Promise<ScopusImport> {
  return apiPost<ScopusImport>(`/api/v1/imports/${id}/normalize`);
}

export function archiveImport(id: string): Promise<ScopusImport> {
  return apiPost<ScopusImport>(`/api/v1/imports/${id}/archive`);
}

export function restoreImportHistory(id: string): Promise<ScopusImport> {
  return apiPost<ScopusImport>(`/api/v1/imports/${id}/restore-history`);
}
