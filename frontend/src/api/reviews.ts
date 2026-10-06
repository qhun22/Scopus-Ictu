/** Typed client for the M2.7B human-review endpoints. */

import {
  AmbiguityFilter,
  CandidateStatus,
  EvidenceCategory,
  ReviewCandidateDetail,
  ReviewDecisionRequest,
  ReviewDecisionResponse,
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

export function decideReviewCandidate(
  candidateId: string,
  request: ReviewDecisionRequest,
): Promise<ReviewDecisionResponse> {
  return apiPost<ReviewDecisionResponse, ReviewDecisionRequest>(
    `/api/v1/reviews/candidates/${encodeURIComponent(candidateId)}/reviews`,
    request,
  );
}
