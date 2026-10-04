import { apiGet, apiPost } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuthorNameVariant {
  id: string;
  variant_type: "AUTHOR_DISPLAY" | "AUTHOR_FULL_NAME";
  variant_name: string;
  variant_name_normalized: string;
  created_at: string;
}

export interface AuthorListItem {
  id: string;
  scopus_id: string;
  preferred_name: string;
  publication_count: number;
  variant_count: number;
}

export interface AuthorListResponse {
  items: AuthorListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuthorStats {
  total_authors: number;
  publication_author_links: number;
  name_variants: number;
}

export interface AuthorDetail {
  id: string;
  scopus_id: string;
  preferred_name: string;
  created_at: string;
  updated_at: string;
  variants: AuthorNameVariant[];
  publication_count: number;
}

// ---------------------------------------------------------------------------
// API Functions
// ---------------------------------------------------------------------------

/** Global canonical aggregates for Authors tab KPIs. */
export function getAuthorStats(): Promise<AuthorStats> {
  return apiGet<AuthorStats>("/api/v1/authors/stats");
}

/** Run author normalization for an APPLIED Scopus import (M2.6B). */
export function normalizeAuthors(importId: string): Promise<unknown> {
  return apiPost<unknown>(`/api/v1/authors/normalize-import/${importId}`);
}

/** List/search Scopus authors. */
export function getAuthors(params?: {
  q?: string;
  page?: number;
  page_size?: number;
}): Promise<AuthorListResponse> {
  const sp = new URLSearchParams();
  if (params?.q) sp.set("q", params.q);
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  const qs = sp.toString();
  return apiGet<AuthorListResponse>(
    `/api/v1/authors${qs ? `?${qs}` : ""}`,
  );
}

/** Get author detail with name variants. */
export function getAuthorDetail(authorId: string): Promise<AuthorDetail> {
  return apiGet<AuthorDetail>(`/api/v1/authors/${authorId}`);
}
