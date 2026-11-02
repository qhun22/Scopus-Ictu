/** Typed client for the M2.7B human-review endpoints. */

import {
  AmbiguityFilter,
  CandidateStatus,
  EvidenceCategory,
  ReviewCandidateDetail,
  ReviewContext,
  ReviewDecisionRequest,
  ReviewGroupAcceptRequest,
  ReviewGroupAcceptResponse,
  ReviewDecisionResponse,
  ReviewRevocationRequest,
  ReviewRevocationResponse,
  ReviewHistoryQueryParams,
  ReviewHistoryResponse,
  ReviewQueueResponse,
} from "../types/review";
import { apiGet, apiPost, ApiRequestOptions } from "./client";

export interface MergeGuideResponse {
  available: boolean;
  source_url: string | null;
  retrieved_at: string | null;
  items: Array<{ lecturer_id: string; scopus_ids: string[]; primary_scopus_id: string | null }>;
}

/** ICTU merge-guide hint for the listed lecturers (matched by e-mail on the server). Decides nothing. */
export function getMergeGuide(lecturerIds: string[], options: ApiRequestOptions = {}): Promise<MergeGuideResponse> {
  const query = new URLSearchParams();
  lecturerIds.forEach((id) => query.append("lecturer_ids", id));
  return apiGet<MergeGuideResponse>(`/api/v1/reviews/merge-guide?${query.toString()}`, options);
}

export interface ReviewQueueParams {
  status?: CandidateStatus;
  evidence_category?: EvidenceCategory;
  ambiguity?: AmbiguityFilter;
  /** Free text: lecturer name / e-mail, Scopus name / ID (diacritics ignored). */
  q?: string;
  page?: number;
  page_size?: number;
}

export function getReviewCandidates(
  params: ReviewQueueParams,
  options: ApiRequestOptions = {},
): Promise<ReviewQueueResponse> {
  const query = new URLSearchParams();
  query.set("status", params.status ?? "PENDING");
  query.set("page", String(params.page ?? 1));
  query.set("page_size", String(params.page_size ?? 20));
  if (params.evidence_category) query.set("evidence_category", params.evidence_category);
  if (params.ambiguity) query.set("ambiguity", params.ambiguity);
  if (params.q) query.set("q", params.q);

  return apiGet<ReviewQueueResponse>(`/api/v1/reviews/candidates?${query.toString()}`, options);
}

export function getReviewCandidate(
  candidateId: string,
  options: ApiRequestOptions = {},
): Promise<ReviewCandidateDetail> {
  return apiGet<ReviewCandidateDetail>(
    `/api/v1/reviews/candidates/${encodeURIComponent(candidateId)}`,
    options,
  );
}

export function getReviewHistory(
  params: ReviewHistoryQueryParams,
  options: ApiRequestOptions = {},
): Promise<ReviewHistoryResponse> {
  const qs = new URLSearchParams();
  qs.set("page", String(params.page));
  qs.set("page_size", String(params.page_size));
  if (params.action) qs.set("action", params.action);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  return apiGet<ReviewHistoryResponse>(`/api/v1/reviews/history?${qs.toString()}`, options);
}

export function decideReviewCandidate(
  candidateId: string,
  request: ReviewDecisionRequest,
): Promise<ReviewDecisionResponse> {
  return apiPost<ReviewDecisionResponse, ReviewDecisionRequest>(
    `/api/v1/reviews/candidates/${encodeURIComponent(candidateId)}/reviews`,
    request,
  );
}

export function revokeReviewCandidate(
  candidateId: string,
  request: ReviewRevocationRequest,
): Promise<ReviewRevocationResponse> {
  return apiPost<ReviewRevocationResponse, ReviewRevocationRequest>(
    `/api/v1/reviews/candidates/${encodeURIComponent(candidateId)}/revocation`,
    request,
  );
}

export function getReviewContext(options: ApiRequestOptions = {}): Promise<ReviewContext> {
  return apiGet<ReviewContext>("/api/v1/reviews/context", options);
}

/** Accept every proposed Scopus ID of one lecturer in one transaction (all or none). */
export function groupAcceptLecturerCandidates(
  lecturerId: string,
  request: ReviewGroupAcceptRequest,
): Promise<ReviewGroupAcceptResponse> {
  return apiPost<ReviewGroupAcceptResponse, ReviewGroupAcceptRequest>(
    `/api/v1/reviews/lecturers/${encodeURIComponent(lecturerId)}/group-accept`,
    request,
  );
}
