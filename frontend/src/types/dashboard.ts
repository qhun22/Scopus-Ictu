// Safe read-only types for the dashboard summary API — C2-A4/A5.

import type { AuditListItem } from "./audit";

export type DashboardIdentityStatus = "CANDIDATE" | "APPROVED" | "REJECTED" | "REVOKED";

export type DashboardImportStatus =
  | "RECEIVED"
  | "PARSING"
  | "VALIDATED"
  | "STAGED"
  | "APPLIED"
  | "FAILED"
  | "CANCELLED";

export interface DashboardLatestImport {
  file_name: string;
  status: DashboardImportStatus;
  total_records: number;
  valid_records: number;
  invalid_records: number;
  created_at: string;
  updated_at: string;
}

export interface DashboardSummary {
  total_publications: number;
  total_lecturers: number;
  active_lecturers: number;
  total_scopus_authors: number;
  identity_counts: Record<DashboardIdentityStatus, number>;
  pending_review_count: number;
  latest_scopus_import: DashboardLatestImport | null;
  recent_audit_actions: AuditListItem[];
}
