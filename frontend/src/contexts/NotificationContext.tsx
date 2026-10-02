import React, { useCallback, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import {
  getUnreadNotifications,
  markNotificationRead,
  NotificationType,
  UserNotification,
} from "../api/notifications";
import { useAuth } from "./AuthContext";
import { useToast } from "./ToastContext";

const POLL_INTERVAL_MS = 5_000;
const SEEN_STORAGE_PREFIX = "scopus-ictu:seen-notifications:";
const MAX_STORED_NOTIFICATION_IDS = 500;

function compareNotifications(left: UserNotification, right: UserNotification): number {
  const timeOrder = left.created_at.localeCompare(right.created_at);
  return timeOrder !== 0 ? timeOrder : left.id.localeCompare(right.id);
}

function loadSeenNotificationIds(userId: string): Set<string> {
  try {
    const stored = window.sessionStorage.getItem(`${SEEN_STORAGE_PREFIX}${userId}`);
    const parsed: unknown = stored ? JSON.parse(stored) : [];
    if (Array.isArray(parsed)) {
      return new Set(parsed.filter((id): id is string => typeof id === "string"));
    }
  } catch {
    // Polling still works when sessionStorage is unavailable.
  }

  return new Set<string>();
}

function persistSeenNotificationIds(userId: string, ids: Set<string>): void {
  try {
    const recentIds = Array.from(ids).slice(-MAX_STORED_NOTIFICATION_IDS);
    window.sessionStorage.setItem(`${SEEN_STORAGE_PREFIX}${userId}`, JSON.stringify(recentIds));
  } catch {
    // Notification delivery must not depend on browser storage availability.
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { user, isAuthenticated, refreshUser } = useAuth();
  const { info, success } = useToast();
  const seenIdsByUserRef = useRef<Map<string, Set<string>>>(new Map());

  const getSeenIds = useCallback((userId: string): Set<string> => {
    const existing = seenIdsByUserRef.current.get(userId);
    if (existing) return existing;

    const loaded = loadSeenNotificationIds(userId);
    seenIdsByUserRef.current.set(userId, loaded);
    return loaded;
  }, []);

  const dispatchNotification = useCallback(
    (type: NotificationType, notification: UserNotification): boolean => {
      switch (type) {
        case "PROFILE_UPDATED":
          info(
            "Thông tin tài khoản đã được cập nhật",
            "Quản trị viên vừa cập nhật thông tin của bạn.",
          );
          return true;

        case "ROLE_CHANGED":
          info(
            "Quyền tài khoản đã thay đổi",
            "Vai trò tài khoản của bạn vừa được quản trị viên cập nhật.",
          );
          return true;

        case "ACCOUNT_UNLOCKED":
          success(
            "Tài khoản đã được mở khóa",
            "Tài khoản của bạn hiện đã hoạt động trở lại.",
          );
          return false;

        case "PASSWORD_RESET":
          info(
            "Mật khẩu tài khoản đã được cập nhật",
            "Quản trị viên đã thay đổi mật khẩu đăng nhập của bạn.",
          );
          return false;

        case "ACCOUNT_LOCKED":
          // An online lock is surfaced by the protected-request auth handler.
          // Showing this persisted event after a later unlock would be stale.
          return false;

        default:
          info(notification.title || "Thông báo", notification.message);
          return false;
      }
    },
    [info, success],
  );

  const processNotifications = useCallback(
    async (notifications: UserNotification[], userId: string, signal: AbortSignal) => {
      const seenIds = getSeenIds(userId);
      let shouldRefreshUser = false;

      // Backend ordering is not assumed; chronological processing makes role
      // and profile transitions deterministic across browsers.
      const orderedNotifications = [...notifications].sort(compareNotifications);

      for (const notification of orderedNotifications) {
        if (signal.aborted) return;

        if (!seenIds.has(notification.id)) {
          shouldRefreshUser =
            dispatchNotification(notification.type, notification) || shouldRefreshUser;
          seenIds.add(notification.id);
          persistSeenNotificationIds(userId, seenIds);
        }

        // A failed mark is intentionally retried on the next poll. The seen-ID
        // set prevents the retry from dispatching a duplicate Toast.
        try {
          await markNotificationRead(notification.id, { signal });
        } catch (error: unknown) {
          if (isAbortError(error)) return;
        }
      }

      if (shouldRefreshUser && !signal.aborted) {
        try {
          await refreshUser();
        } catch {
          // Session errors are centralized; transient errors preserve the
          // current user and will be retried by a future notification/update.
        }
      }
    },
    [dispatchNotification, getSeenIds, refreshUser],
  );

  const pollingEnabled = isAuthenticated && location.pathname !== "/login";
  const userId = user?.id;

  useEffect(() => {
    if (!pollingEnabled || !userId) return;

    let disposed = false;
    let inFlight = false;
    let immediatePollQueued = false;
    let timerId: number | null = null;
    let activeController: AbortController | null = null;

    const clearTimer = () => {
      if (timerId !== null) {
        window.clearTimeout(timerId);
        timerId = null;
      }
    };

    const schedulePoll = (delay: number) => {
      if (disposed || document.visibilityState !== "visible") return;

      clearTimer();
      timerId = window.setTimeout(() => {
        timerId = null;
        void poll();
      }, delay);
    };

    const poll = async () => {
      if (disposed || inFlight || document.visibilityState !== "visible") return;

      inFlight = true;
      immediatePollQueued = false;
      const controller = new AbortController();
      activeController = controller;

      try {
        const notifications = await getUnreadNotifications({ signal: controller.signal });
        if (!disposed && !controller.signal.aborted && Array.isArray(notifications)) {
          await processNotifications(notifications, userId, controller.signal);
        }
      } catch (error: unknown) {
        if (!isAbortError(error)) {
          // Poll failures stay silent; stable auth failures are already handled
          // globally and transient failures are retried after five seconds.
        }
      } finally {
        if (activeController === controller) {
          activeController = null;
        }
        inFlight = false;

        if (!disposed && document.visibilityState === "visible") {
          schedulePoll(immediatePollQueued ? 0 : POLL_INTERVAL_MS);
        }
      }
    };

    const requestImmediatePoll = () => {
      if (disposed || document.visibilityState !== "visible") return;

      if (inFlight) {
        immediatePollQueued = true;
        return;
      }

      schedulePoll(0);
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        requestImmediatePoll();
      } else {
        clearTimer();
        activeController?.abort();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("focus", requestImmediatePoll);

    // Deferring the initial request lets React StrictMode complete its
    // setup/cleanup/setup cycle without issuing two network requests.
    schedulePoll(0);

    return () => {
      disposed = true;
      clearTimer();
      activeController?.abort();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("focus", requestImmediatePoll);
    };
  }, [pollingEnabled, processNotifications, userId]);

  return <>{children}</>;
}
