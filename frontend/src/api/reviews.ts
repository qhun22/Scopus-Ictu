/** Reviews API client — M0 scaffold. */

import { apiGet } from "./client";

export function pingReviews() {
  return apiGet<{ status: string; milestone: string }>("/api/v1/reviews/ping");
}