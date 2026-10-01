/** Audits API client — M0 scaffold. */

import { apiGet } from "./client";

export function pingAudits() {
  return apiGet<{ status: string; milestone: string }>("/api/v1/audits/ping");
}