/**
 * Typed fetch client shared by all frontend API modules.
 *
 * Requests use the HttpOnly authentication cookie and API failures retain the
 * backend's stable `{ detail, code }` contract without coupling pages to the
 * raw response shape.
 */

const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export const SESSION_AUTH_ERROR_CODES = [
  "ACCOUNT_LOCKED",
  "PASSWORD_RESET_BY_ADMIN",
  "SESSION_REVOKED",
] as const;

export type SessionAuthErrorCode = (typeof SESSION_AUTH_ERROR_CODES)[number];

export interface ApiErrorPayload {
  detail?: string;
  code?: string;
  [key: string]: unknown;
}

export interface ApiRequestOptions {
  signal?: AbortSignal;
  /** Login/logout handle their own outcome and must not trigger session teardown. */
  skipGlobalAuthHandling?: boolean;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly body: unknown;
  public readonly code?: string;
  public readonly detail?: string;

  constructor(message: string, status: number, body: unknown, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.code = code;
    this.detail = getStringField(body, "detail");

    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

type ApiErrorListener = (error: ApiError) => void;

const authErrorListeners = new Set<ApiErrorListener>();
const sessionAuthErrorCodes = new Set<string>(SESSION_AUTH_ERROR_CODES);

function getStringField(value: unknown, field: string): string | undefined {
  if (typeof value !== "object" || value === null) return undefined;

  const candidate = (value as Record<string, unknown>)[field];
  if (typeof candidate !== "string") return undefined;

  const normalized = candidate.trim();
  return normalized.length > 0 ? normalized : undefined;
}

function isSessionAuthError(error: ApiError): error is ApiError & { code: SessionAuthErrorCode } {
  return typeof error.code === "string" && sessionAuthErrorCodes.has(error.code);
}

function publishSessionAuthError(error: ApiError): void {
  if (!isSessionAuthError(error)) return;

  authErrorListeners.forEach((listener) => {
    try {
      listener(error);
    } catch {
      // A UI listener must never prevent the original API rejection.
    }
  });
}

export function subscribeToSessionAuthErrors(listener: ApiErrorListener): () => void {
  authErrorListeners.add(listener);
  return () => authErrorListeners.delete(listener);
}

async function readJsonBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text.trim()) return null;

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

async function createApiError(method: string, response: Response): Promise<ApiError> {
  const body = await readJsonBody(response);
  const detail = getStringField(body, "detail");
  const code = getStringField(body, "code");
  const fallback = `Yêu cầu ${method} không thành công (${response.status}).`;

  return new ApiError(detail ?? fallback, response.status, body, code);
}

async function parseSuccessBody<T>(response: Response): Promise<T> {
  if (response.status === 204 || response.status === 205) {
    return undefined as T;
  }

  const body = await readJsonBody(response);
  return body as T;
}

async function request<T>(
  method: string,
  path: string,
  body: unknown,
  options: ApiRequestOptions,
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let bodyContent: string | undefined;

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    bodyContent = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    credentials: "include",
    body: bodyContent,
    signal: options.signal,
  });

  if (!response.ok) {
    const error = await createApiError(method, response);
    if (!options.skipGlobalAuthHandling) {
      publishSessionAuthError(error);
    }
    throw error;
  }

  return parseSuccessBody<T>(response);
}

async function requestForm<T>(
  method: string,
  path: string,
  body: FormData,
  options: ApiRequestOptions,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { Accept: "application/json" },
    credentials: "include",
    body,
    signal: options.signal,
  });

  if (!response.ok) {
    const error = await createApiError(method, response);
    if (!options.skipGlobalAuthHandling) {
      publishSessionAuthError(error);
    }
    throw error;
  }

  return parseSuccessBody<T>(response);
}

export function apiGet<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  return request<T>("GET", path, undefined, options);
}

export function apiPost<T, B = unknown>(
  path: string,
  body?: B,
  options: ApiRequestOptions = {},
): Promise<T> {
  return request<T>("POST", path, body, options);
}

export function apiPostForm<T>(
  path: string,
  body: FormData,
  options: ApiRequestOptions = {},
): Promise<T> {
  return requestForm<T>("POST", path, body, options);
}

export function apiPut<T, B = unknown>(
  path: string,
  body: B,
  options: ApiRequestOptions = {},
): Promise<T> {
  return request<T>("PUT", path, body, options);
}

export function apiPatch<T, B = unknown>(
  path: string,
  body: B,
  options: ApiRequestOptions = {},
): Promise<T> {
  return request<T>("PATCH", path, body, options);
}

export function apiDelete<T = { message: string }>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  return request<T>("DELETE", path, undefined, options);
}

export interface DownloadResult {
  blob: Blob;
  filename: string;
}

/**
 * Fetch a file download using HttpOnly-cookie auth (credentials:"include").
 * Honors VITE_API_BASE_URL. Extracts the filename from Content-Disposition.
 * Throws ApiError on non-2xx, propagating the backend { detail, code } contract.
 */
export async function apiDownload(
  path: string,
  options: ApiRequestOptions = {},
): Promise<DownloadResult> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: { Accept: "application/json, application/octet-stream" },
    credentials: "include",
    signal: options.signal,
  });

  if (!response.ok) {
    const error = await createApiError("GET", response);
    if (!options.skipGlobalAuthHandling) {
      publishSessionAuthError(error);
    }
    throw error;
  }

  const cd = response.headers.get("Content-Disposition") ?? "";
  const match = cd.match(/filename[^;=\n]*=\s*(?:['"]?)([^'"\n;]+)(?:['"]?)/i);
  const filename = match?.[1]?.trim() ?? path.split("/").pop() ?? "download";

  const blob = await response.blob();
  return { blob, filename };
}
