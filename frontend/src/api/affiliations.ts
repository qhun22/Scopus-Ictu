/** ADMIN workflow: author-affiliation source status -> preview -> apply. */

import { apiGet, apiPost, apiPut, ApiRequestOptions } from "./client";

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

export type EnrichmentJobStatus = "RECEIVED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface EnrichmentJob {
  id: string;
  status: EnrichmentJobStatus;
  total_dois: number;
  processed_dois: number;
  openalex_found: number;
  crossref_found: number;
  orcid_fetched: number;
  bundle_dir: string | null;
  error_summary: { code?: string; message?: string } | null;
  created_at: string;
  updated_at: string;
}

export function getAffiliationOverview(options: ApiRequestOptions = {}): Promise<AffiliationOverview> {
  return apiGet<AffiliationOverview>("/api/v1/affiliations/overview", options);
}

export function previewAffiliations(
  jobId?: string,
  options: ApiRequestOptions = {},
): Promise<AffiliationPreview> {
  const path = jobId
    ? `/api/v1/affiliations/preview?job_id=${encodeURIComponent(jobId)}`
    : "/api/v1/affiliations/preview";
  return apiPost<AffiliationPreview, Record<string, never>>(path, {}, options);
}

export function applyAffiliations(
  fingerprint: string,
  jobId?: string,
  options: ApiRequestOptions = {},
): Promise<AffiliationApplyResult> {
  return apiPost<AffiliationApplyResult, { fingerprint: string; confirm: boolean; job_id?: string }>(
    "/api/v1/affiliations/apply",
    jobId ? { fingerprint, confirm: true, job_id: jobId } : { fingerprint, confirm: true },
    options,
  );
}

export function startOnlineEnrichment(options: ApiRequestOptions = {}): Promise<EnrichmentJob> {
  return apiPost<EnrichmentJob, Record<string, never>>("/api/v1/affiliations/enrichment/online", {}, options);
}

export function getOnlineEnrichment(jobId: string, options: ApiRequestOptions = {}): Promise<EnrichmentJob> {
  return apiGet<EnrichmentJob>(`/api/v1/affiliations/enrichment/online/${jobId}`, options);
}

export function cancelOnlineEnrichment(jobId: string, options: ApiRequestOptions = {}): Promise<EnrichmentJob> {
  return apiPost<EnrichmentJob, Record<string, never>>(
    `/api/v1/affiliations/enrichment/online/${jobId}/cancel`,
    {},
    options,
  );
}

// --------------------------------------------------------------------------- manual review (Priority 2 / NO-JSON closure)
export interface NeedsReviewItem {
  publication_author_id: string;
  eid: string;
  title: string;
  author_order: number;
  scopus_id: string;
  preferred_name: string;
  reason_kind: "UNRESOLVED" | "CONFLICTING_SOURCES" | "LOW_CONFIDENCE";
  resolution_summaries: Array<{ source_system: string; link_status: string; unresolved_reason: string | null }>;
  has_override: boolean;
  /** ALL overrides for this position — active and revoked, newest first. */
  overrides: OverrideFull[];
}

export interface NeedsReviewListResponse {
  items: NeedsReviewItem[];
  total: number;
}

export interface OverrideFull {
  id: string;
  publication_author_id: string;
  affiliation_text: string;
  confidence: "CORROBORATED" | "UNRESOLVED";
  status: "ACTIVE" | "REVOKED";
  evidence_url: string;
  reason: string;
  created_by_user_id: string;
  updated_by_user_id: string;
  revoked_by_user_id: string | null;
  revoked_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface AddOverrideBody {
  publication_author_id: string;
  affiliation_text: string;
  confidence: "CORROBORATED" | "UNRESOLVED";
  evidence_url: string;
  reason: string;
}

export interface UpdateOverrideBody {
  affiliation_text: string;
  confidence: "CORROBORATED" | "UNRESOLVED";
  evidence_url: string;
  reason: string;
  expected_version: number;
}

export interface RevokeOverrideBody {
  reason: string;
  expected_version: number;
}

export function getNeedsReview(
  params: { limit?: number; offset?: number } = {},
  options: ApiRequestOptions = {},
): Promise<NeedsReviewListResponse> {
  const query = new URLSearchParams();
  if (params.limit != null) query.set("limit", String(params.limit));
  if (params.offset != null) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiGet<NeedsReviewListResponse>(`/api/v1/affiliations/needs-review${qs ? `?${qs}` : ""}`, options);
}

/** Add a new active unit statement for a position. Does not touch any other override already on it. */
export function addOverride(body: AddOverrideBody, options: ApiRequestOptions = {}): Promise<OverrideFull> {
  return apiPost<OverrideFull, AddOverrideBody>("/api/v1/affiliations/overrides", body, options);
}

/** Edit exactly one override by its own id. */
export function updateOverride(
  overrideId: string,
  body: UpdateOverrideBody,
  options: ApiRequestOptions = {},
): Promise<OverrideFull> {
  return apiPut<OverrideFull, UpdateOverrideBody>(`/api/v1/affiliations/overrides/${overrideId}`, body, options);
}

/** Revoke one override (kept, not deleted, for audit); other overrides on the position are unaffected. */
export function revokeOverride(
  overrideId: string,
  body: RevokeOverrideBody,
  options: ApiRequestOptions = {},
): Promise<OverrideFull> {
  return apiPost<OverrideFull, RevokeOverrideBody>(
    `/api/v1/affiliations/overrides/${overrideId}/revoke`,
    body,
    options,
  );
}
