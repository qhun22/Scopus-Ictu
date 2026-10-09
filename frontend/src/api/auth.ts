/**
 * Auth API service — M2.2 contract.
 */

import { apiGet, apiPost } from "./client";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: "ADMIN" | "REVIEWER" | "LECTURER" | string;
  lecturer_id: string | null;
}

import { safeDisplayName } from "../utils/displayName";

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LogoutResponse {
  message: string;
}

function sanitizeUser(u: User): User {
  if (!u) return u;
  return { ...u, display_name: safeDisplayName(u.display_name, u.role) };
}

export async function login(credentials: LoginCredentials): Promise<User> {
  const user = await apiPost<User, LoginCredentials>("/api/v1/auth/login", credentials, {
    // Login errors are mapped by the form and must not tear down a different
    // session through the global protected-request handler.
    skipGlobalAuthHandling: true,
  });
  return sanitizeUser(user);
}

export async function getCurrentUser(): Promise<User> {
  const user = await apiGet<User>("/api/v1/auth/me");
  return sanitizeUser(user);
}

export async function logout(): Promise<LogoutResponse> {
  return apiPost<LogoutResponse>("/api/v1/auth/logout", undefined, {
    skipGlobalAuthHandling: true,
  });
}
