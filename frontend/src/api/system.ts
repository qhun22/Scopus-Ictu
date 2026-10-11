import { apiPost, ApiRequestOptions } from "./client";

export interface SystemResetResponse {
  status: string;
  message: string;
}

export function resetSystem(
  confirmation: string,
  options: ApiRequestOptions = {},
): Promise<SystemResetResponse> {
  return apiPost<SystemResetResponse, { confirmation: string }>(
    "/api/v1/system/reset",
    { confirmation },
    options,
  );
}
