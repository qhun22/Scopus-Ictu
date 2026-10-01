/**
 * Typed fetch client — M2.2 runtime implementation.
 *
 * Base URL is sourced from `VITE_API_BASE_URL` (defaults to empty string for Vite proxy or relative API).
 * Always includes `credentials: "include"` for HttpOnly cookie exchange.
 */

const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export class ApiError extends Error {
  public readonly status: number;
  public readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function throwApiError(method: string, path: string, res: Response): Promise<never> {
  const errorBody = await res.json().catch(() => null);
  const detail =
    typeof errorBody === "object" &&
    errorBody !== null &&
    "detail" in errorBody &&
    typeof errorBody.detail === "string"
      ? errorBody.detail
      : `${method} ${path} → ${res.status}`;
  throw new ApiError(detail, res.status, errorBody);
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    credentials: "include",
  });
  if (!res.ok) {
    await throwApiError("GET", path, res);
  }
  return (await res.json()) as T;
}

export async function apiPost<T, B = unknown>(path: string, body?: B): Promise<T> {
  const headers: Record<string, string> = {};
  let bodyContent: string | undefined;

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    bodyContent = JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    credentials: "include",
    body: bodyContent,
  });
  if (!res.ok) {
    await throwApiError("POST", path, res);
  }
  return (await res.json()) as T;
}