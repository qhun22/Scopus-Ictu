/** Typed client for the dashboard summary endpoint — C2-A4/A5. */

import { DashboardCharts, DashboardSummary } from "../types/dashboard";
import { apiGet, ApiRequestOptions } from "./client";

export function getDashboardSummary(
  options: ApiRequestOptions = {},
): Promise<DashboardSummary> {
  return apiGet<DashboardSummary>("/api/v1/dashboard/summary", options);
}

export function getDashboardCharts(
  options: ApiRequestOptions = {},
): Promise<DashboardCharts> {
  return apiGet<DashboardCharts>("/api/v1/dashboard/charts", options);
}
