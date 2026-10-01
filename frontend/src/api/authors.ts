/** Authors API client — M0 scaffold. */

import { apiGet } from "./client";

export function pingAuthors() {
  return apiGet<{ status: string; milestone: string }>("/api/v1/authors/ping");
}