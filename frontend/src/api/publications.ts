/** Canonical publication read API client — A1 contract. */

import { apiGet } from "./client";
import {
  PublicationDetailResponse,
  PublicationListQuery,
  PublicationListResponse,
} from "../types/publication";

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
 */
export async function getPublicationByEid(
  eid: string,
  options = {},
): Promise<PublicationDetailResponse> {
  return apiGet<PublicationDetailResponse>(`/api/v1/publications/${eid}`, options);
}
