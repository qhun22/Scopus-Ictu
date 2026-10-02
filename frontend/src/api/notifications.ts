import { apiGet, apiPost, type ApiRequestOptions } from "./client";

export type NotificationType =
  | "PROFILE_UPDATED"
  | "ROLE_CHANGED"
  | "ACCOUNT_LOCKED"
  | "ACCOUNT_UNLOCKED"
  | "PASSWORD_RESET";

export interface UserNotification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface NotificationReadResponse {
  id: string;
  is_read: true;
  read_at: string;
}

export function getUnreadNotifications(
  options: ApiRequestOptions = {},
): Promise<UserNotification[]> {
  return apiGet<UserNotification[]>("/api/v1/notifications/unread", options);
}

export function markNotificationRead(
  notificationId: string,
  options: ApiRequestOptions = {},
): Promise<NotificationReadResponse> {
  return apiPost<NotificationReadResponse>(
    `/api/v1/notifications/${encodeURIComponent(notificationId)}/read`,
    undefined,
    options,
  );
}
