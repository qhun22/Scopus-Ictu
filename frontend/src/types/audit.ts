/** Audit types — M0 scaffold. */

import { MilestonePing } from "./index";

export interface AuditEvent {
  id: number;
  actor_user_id?: number;
  action: string;
  entity_type?: string;
  entity_id?: number;
}

export type AuditPing = MilestonePing;