/** Matching API client — M0 scaffold. */

import { apiGet } from "./client";

export function pingMatching() {
  return apiGet<{ status: string; milestone: string }>("/api/v1/matching/ping");
}