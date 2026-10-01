/**
 * Typed fetch client — M0 scaffold.
 *
 * Base URL is sourced from `VITE_API_BASE_URL` (no secrets).
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

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { method: "GET" });
  if (!res.ok) {
    throw new ApiError(`GET ${path} → ${res.status}`, res.status, await res.json().catch(() => null));
  }
  return (await res.json()) as T;
}

export async function apiPost<T, B = unknown>(path: string, body: B): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new ApiError(`POST ${path} → ${res.status}`, res.status, await res.json().catch(() => null));
  }
  return (await res.json()) as T;
}