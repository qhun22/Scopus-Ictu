/** Publications API client — M0 scaffold. */

import { apiGet } from "./client";

export function pingPublications() {
  return apiGet<{ status: string; milestone: string }>("/api/v1/publications/ping");
}