/** Global search API client — Completion-1 A3 contract. */

import { apiGet } from "./client";
import { SearchQuery, SearchResponse } from "../types/search";

/**
 * Grouped global search across lecturers, publications, and Scopus authors.
 * Only ADMIN and REVIEWER roles are authorised by the backend.
 *
 * The query is trimmed before being sent; the caller is responsible for
 * enforcing the minimum length so no request is issued for a short term.
 */
export async function getSearch(
  query: SearchQuery,
  options: { signal?: AbortSignal } = {},
): Promise<SearchResponse> {
  const params = new URLSearchParams();
  params.set("q", query.q.trim());
  if (query.limit !== undefined) params.set("limit", String(query.limit));

  return apiGet<SearchResponse>(`/api/v1/search?${params.toString()}`, options);
}