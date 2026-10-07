/** Audit types — C2-A1 safe DTO contract. */

export type AuditActorType = "USER" | "SYSTEM";

export interface AuditListItem {
  id: string;
  entity_type: string;
  action: string;
  actor_type: AuditActorType;
  actor_display_name: string | null;
  actor_service: string | null;
  reason: string | null;
  created_at: string;
}

export interface AuditListResponse {
  items: AuditListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditLogsQueryParams {
  page: number;
  page_size: number;
  action?: string;
  entity_type?: string;
  actor_type?: AuditActorType;
  date_from?: string;
  date_to?: string;
}
