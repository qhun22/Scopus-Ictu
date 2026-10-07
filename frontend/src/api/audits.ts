/** Audits API client — C2-A1 safe read-only contract. */

import { apiGet, ApiRequestOptions } from "./client";
import { AuditListResponse, AuditLogsQueryParams } from "../types/audit";

export function getAuditLogs(
  params: AuditLogsQueryParams,
  options: ApiRequestOptions = {},
): Promise<AuditListResponse> {
  const qs = new URLSearchParams();

  qs.set("page", String(params.page));
  qs.set("page_size", String(params.page_size));

  const action = params.action?.trim();
  if (action) qs.set("action", action);

  const entityType = params.entity_type?.trim();
  if (entityType) qs.set("entity_type", entityType);

  if (params.actor_type) qs.set("actor_type", params.actor_type);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);

  return apiGet<AuditListResponse>(`/api/v1/audits?${qs.toString()}`, options);
}
