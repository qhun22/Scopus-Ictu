/** Typed client for the M2.7B human-review endpoints. */

import {
  AmbiguityFilter,
  CandidateStatus,
  EvidenceCategory,
  ReviewCandidateDetail,
  ReviewDecisionRequest,
  ReviewDecisionResponse,
  ReviewHistoryQueryParams,
  ReviewHistoryResponse,
  ReviewQueueResponse,
} from "../types/review";
import { apiGet, apiPost, ApiRequestOptions } from "./client";

export interface ReviewQueueParams {
  status?: CandidateStatus;
  evidence_category?: EvidenceCategory;
  ambiguity?: AmbiguityFilter;
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
