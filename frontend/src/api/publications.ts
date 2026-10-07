/** Canonical publication read API client — A1 contract. */

import { apiDownload, apiGet } from "./client";
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
 * Only ADMIN and REVIEWER roles are authorised by the backend.
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

  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<PublicationListResponse>(`/api/v1/publications${suffix}`, options);
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

/**
 * Export the canonical publication dataset as a downloadable JSON file.
 * Uses HttpOnly-cookie auth via the shared apiDownload helper.
 * Only ADMIN role is authorised by the backend.
 */
export async function exportPublicationsJson(
  filters: PublicationExportFilters = {},
  options = {},
): Promise<{ blob: Blob; filename: string; recordCount: number }> {
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
  const suffix = params.toString() ? `?${params.toString()}` : "";

  const { blob, filename } = await apiDownload(
    `/api/v1/publications/export${suffix}`,
    options,
  );

  let recordCount = 0;
  try {
    const text = await blob.text();
    const parsed = JSON.parse(text) as { dataset?: { record_count?: number } };
    recordCount = parsed?.dataset?.record_count ?? 0;
  } catch {
    // ignore parse errors — caller receives blob regardless
  }

  return { blob, filename, recordCount };
}
