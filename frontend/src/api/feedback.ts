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
  comment_count: number;
}

export interface FeedbackReportListResponse {
  items: FeedbackReport[];
  total: number;
  open_count: number;
}

export interface FeedbackComment {
  id: string;
  report_id: string;
  author_user_id: string;
  author_name: string;
  is_staff_author: boolean;
  message: string;
  created_at: string;
}

export interface FeedbackCommentListResponse {
  items: FeedbackComment[];
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

export function listMyFeedbackReports(
  params: { status?: FeedbackStatus; limit?: number; offset?: number } = {},
  options: ApiRequestOptions = {},
): Promise<FeedbackReportListResponse> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  const qs = search.toString();
  return apiGet<FeedbackReportListResponse>(
    `/api/v1/feedback/reports/mine${qs ? `?${qs}` : ""}`,
    options,
  );
}

export function getFeedbackReport(
  reportId: string,
  options: ApiRequestOptions = {},
): Promise<FeedbackReport> {
  return apiGet<FeedbackReport>(`/api/v1/feedback/reports/${encodeURIComponent(reportId)}`, options);
}

export function listFeedbackComments(
  reportId: string,
  options: ApiRequestOptions = {},
): Promise<FeedbackCommentListResponse> {
  return apiGet<FeedbackCommentListResponse>(
    `/api/v1/feedback/reports/${encodeURIComponent(reportId)}/comments`,
    options,
  );
}

export function getFeedbackUnread(
  options: ApiRequestOptions = {},
): Promise<{ has_unread: boolean }> {
  return apiGet<{ has_unread: boolean }>("/api/v1/feedback/unread", options);
}

export function markFeedbackSeen(options: ApiRequestOptions = {}): Promise<void> {
  return apiPost<void>("/api/v1/feedback/mark-seen", {}, options);
}

export function addFeedbackComment(
  reportId: string,
  payload: { message: string },
  options: ApiRequestOptions = {},
): Promise<FeedbackComment> {
  return apiPost<FeedbackComment>(
    `/api/v1/feedback/reports/${encodeURIComponent(reportId)}/comments`,
    payload,
    options,
  );
}
