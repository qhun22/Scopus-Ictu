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

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LogoutResponse {
  message: string;
}

export async function login(credentials: LoginCredentials): Promise<User> {
  return apiPost<User, LoginCredentials>("/api/v1/auth/login", credentials, {
    // Login errors are mapped by the form and must not tear down a different
    // session through the global protected-request handler.
    skipGlobalAuthHandling: true,
  });
}

export async function getCurrentUser(): Promise<User> {
  return apiGet<User>("/api/v1/auth/me");
}

export async function logout(): Promise<LogoutResponse> {
  return apiPost<LogoutResponse>("/api/v1/auth/logout", undefined, {
    skipGlobalAuthHandling: true,
  });
}
