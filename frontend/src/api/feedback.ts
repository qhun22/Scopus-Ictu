import { apiGet, apiPost, type ApiRequestOptions } from "./client";

export type FeedbackCategory = "WRONG_AFFILIATION" | "WRONG_AUTHOR_LINK" | "OTHER";
export type FeedbackStatus = "OPEN" | "RESOLVED" | "DISMISSED";

export interface FeedbackReport {
  id: string;
  reporter_user_id: string;
  reporter_name: string;
  category: FeedbackCategory;
  publication_eid: string | null;
  message: string;
  status: FeedbackStatus;
  admin_note: string | null;
  resolved_by_user_id: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedbackReportListResponse {
  items: FeedbackReport[];
  total: number;
  open_count: number;
}

export function createFeedbackReport(
  payload: { category: FeedbackCategory; publication_eid?: string; message: string },
  options: ApiRequestOptions = {},
): Promise<FeedbackReport> {
  return apiPost<FeedbackReport>("/api/v1/feedback/reports", payload, options);
}

export function listFeedbackReports(
  params: { status?: FeedbackStatus; limit?: number; offset?: number } = {},
  options: ApiRequestOptions = {},
): Promise<FeedbackReportListResponse> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  const qs = search.toString();
  return apiGet<FeedbackReportListResponse>(
    `/api/v1/feedback/reports${qs ? `?${qs}` : ""}`,
    options,
  );
}

export function resolveFeedbackReport(
  reportId: string,
  payload: { status: "RESOLVED" | "DISMISSED"; admin_note?: string },
  options: ApiRequestOptions = {},
): Promise<FeedbackReport> {
  return apiPost<FeedbackReport>(
    `/api/v1/feedback/reports/${encodeURIComponent(reportId)}/resolve`,
    payload,
    options,
  );
}
