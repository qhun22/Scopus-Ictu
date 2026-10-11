/** ADMIN workflow: author-affiliation source status -> preview -> apply. */

import { apiGet, apiPost, ApiRequestOptions } from "./client";

export interface AffiliationBundleFile {
  name: string;
  required: boolean;
  present: boolean;
  size_bytes: number | null;
  sha256: string | null;
}

export interface AffiliationBundleStatus {
  configured: boolean;
  ready: boolean;
  directory_label: string | null;
  files: AffiliationBundleFile[];
  problems: string[];
  openalex_works: number | null;
  crossref_works: number | null;
  orcid_records: number | null;
  orcid_with_scopus_id: number | null;
  retrieved_from: string | null;
  retrieved_to: string | null;
  cross_check_available: boolean;
}

export interface AffiliationDatabaseSummary {
  publications: number;
  author_positions: number;
  organizations: number;
  resolutions_by_source_and_status: Record<string, number>;
  affiliation_entries: number;
  last_run: { action: string; at: string; fingerprint: string | null } | null;
}

export interface AffiliationOverview {
  source: AffiliationBundleStatus;
  database: AffiliationDatabaseSummary;
}

export type OutcomeCounts = Partial<Record<"inserted" | "reused" | "skipped" | "conflicted", number>>;

export interface AffiliationReport {
  by_source_and_confidence: Record<string, OutcomeCounts>;
  conflict_reasons: Record<string, number>;
  skipped_reasons: Record<string, number>;
  resolutions_to_insert: number;
  affiliations_to_insert: number;
  organizations_to_insert: number;
  organizations_reused: number;
  organization_attribute_drift: number;
}

export interface AffiliationInputStats {
  papers: number;
  author_slots: number;
  inputs: number;
  papers_without_doi: number;
  papers_with_duplicate_doi: number;
  papers_with_openalex_work: number;
  papers_with_crossref_work: number;
  papers_with_any_work: number;
  papers_without_any_work: number;
  cross_check_against_survey_jsonl: boolean;
  cross_check_links_matched: number;
  cross_check_links_not_covered: number;
}

export interface AffiliationPreview {
  fingerprint: string;
  can_apply: boolean;
  blocked_reason: string | null;
  publications: number;
  source: AffiliationBundleStatus;
  input: Partial<AffiliationInputStats>;
  report: Partial<AffiliationReport>;
  source_mismatches: number;
  resolutions_to_insert: number;
}

export interface AffiliationApplyResult {
  run_id: string;
  fingerprint: string;
  result: Partial<AffiliationReport>;
}

export function getAffiliationOverview(options: ApiRequestOptions = {}): Promise<AffiliationOverview> {
  return apiGet<AffiliationOverview>("/api/v1/affiliations/overview", options);
}

export function previewAffiliations(options: ApiRequestOptions = {}): Promise<AffiliationPreview> {
  return apiPost<AffiliationPreview, Record<string, never>>("/api/v1/affiliations/preview", {}, options);
}

export function applyAffiliations(
  fingerprint: string,
  options: ApiRequestOptions = {},
): Promise<AffiliationApplyResult> {
  return apiPost<AffiliationApplyResult, { fingerprint: string; confirm: boolean }>(
    "/api/v1/affiliations/apply",
    { fingerprint, confirm: true },
    options,
  );
}
