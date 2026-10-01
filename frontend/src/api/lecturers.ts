/** Lecturer API client — M0 scaffold. */

import { apiGet } from "./client";

export function pingLecturers() {
  return apiGet<{ status: string; milestone: string }>("/api/v1/lecturers/ping");
}