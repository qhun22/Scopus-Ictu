/** ADMIN workflow: candidate generation (name + Craw-assisted) and ICTU-Craw ingestion preview -> apply. */

import { apiPost, ApiRequestOptions } from "./client";

export interface GenerationRunResult {
  run_id: string;
  run_status: string;
  candidate_roots: number;
  observations: number;
  evidence: number;
  idempotent_replay: boolean;
  name_candidates: number;
  craw_assisted_candidates: number;
  craw_unattributed: number;
  publication_conflicts: number;
}

export function generateCandidates(options: ApiRequestOptions = {}): Promise<GenerationRunResult> {
  return apiPost<GenerationRunResult, Record<string, never>>("/api/v1/matching/candidates/generate", {}, options);
}

export interface CrawIngestionPreview {
  fingerprint: string;
  can_apply: boolean;
  blocked_reason: string | null;
  stats: Record<string, unknown>;
  preview: {
    source_lecturer_count: number;
    source_publication_attribution_count: number;
    mapped_lecturer_count: number;
    unmapped_lecturer_count: number;
    ambiguous_lecturer_count: number;
    snapshots_to_create: number;
    snapshots_already_present: number;
    known_publications_to_create: number;
    known_publications_already_present: number;
    source_duplicates_within_snapshot: number;
    invalid_records: number;
    conflicts: number;
    source_urls_collapsed_into_existing_record: number;
    error_codes: Record<string, number>;
  };
  blocking: string[];
}

export interface CrawIngestionApplyResult {
  run_id: string;
  fingerprint: string;
  result: {
    snapshots_created: number;
    snapshots_reused: number;
    known_publications_created: number;
    known_publications_reused: number;
    source_duplicates_collapsed: number;
    source_urls_collapsed: number;
    invalid_records: number;
    unmapped: number;
  };
}

export function previewCrawIngestion(options: ApiRequestOptions = {}): Promise<CrawIngestionPreview> {
  return apiPost<CrawIngestionPreview, Record<string, never>>("/api/v1/matching/craw/preview", {}, options);
}

export function applyCrawIngestion(
  fingerprint: string,
  options: ApiRequestOptions = {},
): Promise<CrawIngestionApplyResult> {
  return apiPost<CrawIngestionApplyResult, { fingerprint: string; confirm: boolean }>(
    "/api/v1/matching/craw/apply",
    { fingerprint, confirm: true },
    options,
  );
}
