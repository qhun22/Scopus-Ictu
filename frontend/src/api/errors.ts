/**
 * Shared API Error helper — M2.2
 *
 * Provides safe, user-friendly error message extraction without exposing
 * internal stack traces, database details, or authentication secrets.
 */

import { ApiError } from "./client";

export function getApiErrorMessage(
  error: unknown,
  fallbackMessage = "Có lỗi xảy ra. Vui lòng thử lại sau."
): string {
  if (error instanceof ApiError) {
    if (typeof error.body === "object" && error.body !== null) {
      const detail = (error.body as Record<string, unknown>).detail;
      if (typeof detail === "string" && detail.trim().length > 0) {
        return detail;
      }
    }

    if (error.status === 401) {
      return "Phiên làm việc đã hết hạn hoặc thông tin đăng nhập không đúng.";
    }
    if (error.status === 403) {
      return "Bạn không có quyền thực hiện thao tác này.";
    }
    if (error.status === 404) {
      return "Không tìm thấy dữ liệu yêu cầu.";
    }
    if (error.status >= 500) {
      return "Máy chủ đang gặp sự cố. Vui lòng thử lại sau.";
    }
  }

  if (error instanceof Error) {
    if (error.name === "TypeError" && error.message.includes("fetch")) {
      return "Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại kết nối mạng.";
    }
  }

  return fallbackMessage;
}
