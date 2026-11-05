/** Canonical publication read API client — A1 contract. */

import { ApiRequestOptions, apiDownload, apiGet } from "./client";
import {
  PublicationDetailResponse,
  PublicationListQuery,
  PublicationListResponse,
} from "../types/publication";

export interface PublicationExportFilters {
  q?: string;
  year?: number;
  document_type?: string;
  publication_stage?: string;
  open_access_status?: string;
}

/**
 * List canonical publications with server-side filtering and pagination.
 * ADMIN, REVIEWER and LECTURER (read-only) are authorised by the backend.
 */
export async function getPublications(
  query: PublicationListQuery = {},
  options = {},
): Promise<PublicationListResponse> {
  const params = new URLSearchParams();

  if (query.page !== undefined) params.set("page", String(query.page));
  if (query.page_size !== undefined) params.set("page_size", String(query.page_size));
  if (query.q !== undefined && query.q.trim()) params.set("q", query.q.trim());
  if (query.year !== undefined) params.set("year", String(query.year));
  if (query.document_type !== undefined && query.document_type.trim()) {
    params.set("document_type", query.document_type.trim());
  }
  if (query.publication_stage !== undefined && query.publication_stage.trim()) {
    params.set("publication_stage", query.publication_stage.trim());
  }
  if (query.open_access_status !== undefined && query.open_access_status.trim()) {
    params.set("open_access_status", query.open_access_status.trim());
  }

  if (query.scopus_id !== undefined && /^\d+$/.test(query.scopus_id.trim())) {
    params.set("scopus_id", query.scopus_id.trim());
  }

  if (query.author_name !== undefined && query.author_name.trim()) {
    params.set("author_name", query.author_name.trim());
  }

  if (query.missing_doi) params.set("missing_doi", "true");

  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<PublicationListResponse>(`/api/v1/publications${suffix}`, options);
}

export interface PublicationFilterOption {
  value: string;
  count: number;
}

export interface PublicationFilterOptions {
  years: number[];
  document_types: PublicationFilterOption[];
  publication_stages: PublicationFilterOption[];
  open_access_statuses: PublicationFilterOption[];
  missing_doi_count: number;
}

/**
 * Year/document-type/stage/open-access values for the list filter dropdowns,
 * each counted within the scope of whatever OTHER filters are passed here
 * (same shape as `getPublications`'s query) — not that dropdown's own filter.
 * Re-fetch this whenever the applied filters change so the counts stay
 * truthful instead of always showing the dataset-wide totals.
 */
export async function getPublicationFilterOptions(
  query: PublicationListQuery = {},
  options: ApiRequestOptions = {},
): Promise<PublicationFilterOptions> {
  const params = new URLSearchParams();

  if (query.q !== undefined && query.q.trim()) params.set("q", query.q.trim());
  if (query.year !== undefined) params.set("year", String(query.year));
  if (query.document_type !== undefined && query.document_type.trim()) {
    params.set("document_type", query.document_type.trim());
  }
  if (query.publication_stage !== undefined && query.publication_stage.trim()) {
    params.set("publication_stage", query.publication_stage.trim());
  }
  if (query.open_access_status !== undefined && query.open_access_status.trim()) {
    params.set("open_access_status", query.open_access_status.trim());
  }
  if (query.scopus_id !== undefined && /^\d+$/.test(query.scopus_id.trim())) {
    params.set("scopus_id", query.scopus_id.trim());
  }
  if (query.author_name !== undefined && query.author_name.trim()) {
    params.set("author_name", query.author_name.trim());
  }
  if (query.missing_doi) params.set("missing_doi", "true");

  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<PublicationFilterOptions>(`/api/v1/publications/filters${suffix}`, options);
}

/**
 * Fetch a single canonical publication by its EID.
 * Returns 404 PUBLICATION_NOT_FOUND when the EID is not in the canonical DB.
 *
 * The dynamic EID path segment is URL-encoded so that any reserved
 * characters in the EID do not corrupt the request path. The rest of the
 * URL is left untouched.
 */
export async function getPublicationByEid(
  eid: string,
  options = {},
): Promise<PublicationDetailResponse> {
  const encodedEid = encodeURIComponent(eid);
  return apiGet<PublicationDetailResponse>(`/api/v1/publications/${encodedEid}`, options);
}

function exportQuery(filters: PublicationExportFilters, format?: "csv"): string {
  const params = new URLSearchParams();
  if (filters.q !== undefined && filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.year !== undefined) params.set("year", String(filters.year));
  if (filters.document_type !== undefined && filters.document_type.trim()) {
    params.set("document_type", filters.document_type.trim());
  }
  if (filters.publication_stage !== undefined && filters.publication_stage.trim()) {
    params.set("publication_stage", filters.publication_stage.trim());
  }
  if (filters.open_access_status !== undefined && filters.open_access_status.trim()) {
    params.set("open_access_status", filters.open_access_status.trim());
  }
  if (format) params.set("format", format);
  return params.toString() ? `?${params.toString()}` : "";
}

/**
 * Export the canonical publication dataset as a downloadable JSON file (schema 1.1).
 * Uses HttpOnly-cookie auth via the shared apiDownload helper.
 * Only ADMIN role is authorised by the backend.
 */
export async function exportPublicationsJson(
  filters: PublicationExportFilters = {},
  options = {},
): Promise<{ blob: Blob; filename: string }> {
  return apiDownload(`/api/v1/publications/export${exportQuery(filters)}`, options);
}

/**
 * Export the same dataset as a CSV file Excel can open: one row per author position,
 * with each author's affiliation, confidence and source. The row count is not read from
 * the response (the backend exposes no custom header and the file is not parsed here).
 */
export async function exportPublicationsCsv(
  filters: PublicationExportFilters = {},
  options = {},
): Promise<{ blob: Blob; filename: string }> {
  return apiDownload(`/api/v1/publications/export${exportQuery(filters, "csv")}`, options);
}

export interface NormalizationCompare {
  eid: string;
  sources: Array<{ file_name: string; row_number: number; row_hash: string }>;
  fields: Array<{
    field: string;
    raw: string | null;
    stored: string | null;
    canonical: string | null;
    status: "SAME" | "CLEANED" | "CHANGED" | "MISSING";
  }>;
}

/** ADMIN/REVIEWER: raw CSV value vs stored value vs canonical form (read-only). */
export function getNormalizationCompare(eid: string, options: ApiRequestOptions = {}): Promise<NormalizationCompare> {
  return apiGet<NormalizationCompare>(
    `/api/v1/publications/${encodeURIComponent(eid)}/normalization-compare`,
    options,
  );
}
