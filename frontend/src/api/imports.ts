/** Imports API client — M0 scaffold. */

import { apiGet } from "./client";

export function pingImports() {
  return apiGet<{ status: string; milestone: string }>("/api/v1/imports/ping");
}