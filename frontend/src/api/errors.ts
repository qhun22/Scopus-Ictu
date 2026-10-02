/** Safe helpers for the backend's stable `{ detail, code }` error contract. */

import { ApiError } from "./client";

const CODE_MESSAGES: Readonly<Record<string, string>> = {
  INVALID_CREDENTIALS: "Email hoặc mật khẩu không đúng.",
  ACCOUNT_LOCKED: "Tài khoản đang bị khóa.",
  PASSWORD_RESET_BY_ADMIN: "Thông tin đăng nhập đã được quản trị viên thay đổi.",
  SESSION_REVOKED: "Phiên đăng nhập đã thay đổi. Vui lòng đăng nhập lại.",
  VERSION_CONFLICT: "Dữ liệu đã thay đổi. Vui lòng tải lại thông tin mới nhất.",
  CANNOT_LOCK_CURRENT_USER: "Không thể khóa tài khoản đang sử dụng.",
  CANNOT_RESET_CURRENT_USER:
    "Không thể đặt lại mật khẩu quản trị viên đang sử dụng từ màn hình này.",
};

export function getApiErrorCode(error: unknown): string | undefined {
  return error instanceof ApiError ? error.code : undefined;
}

export function getApiErrorDetail(error: unknown): string | undefined {
  return error instanceof ApiError ? error.detail : undefined;
}

export function hasApiErrorCode(error: unknown, code: string): boolean {
  return getApiErrorCode(error) === code;
}

export function getApiErrorMessage(
  error: unknown,
  fallbackMessage = "Có lỗi xảy ra. Vui lòng thử lại sau.",
): string {
  if (error instanceof ApiError) {
    if (error.code && CODE_MESSAGES[error.code]) {
      return CODE_MESSAGES[error.code];
    }

    if (error.status === 401) {
      return "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.";
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

    // Validation/business details from 4xx responses are intended for users;
    // server-side 5xx details are deliberately hidden above.
    if (error.status >= 400 && error.status < 500 && error.detail) {
      return error.detail;
    }
  }

  if (error instanceof Error) {
    if (error.name === "TypeError" && error.message.includes("fetch")) {
      return "Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại kết nối mạng.";
    }
  }

  return fallbackMessage;
}
