import { Component, ErrorInfo, ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * Bắt lỗi render không lường trước để người dùng không gặp màn hình trắng.
 * Cố ý KHÔNG hiển thị stack trace hay nội dung lỗi (tránh lộ thông tin); chi tiết chỉ ghi vào console.
 * Dùng chuỗi cố định (không dùng hook i18n) để vẫn hoạt động khi chính I18nProvider bị lỗi.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Lỗi giao diện không lường trước:", error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    return (
      <div
        role="alert"
        className="flex min-h-screen items-center justify-center bg-slate-50 p-6"
      >
        <div className="max-w-md rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-sm">
          <h1 className="text-lg font-bold text-slate-800">Đã xảy ra lỗi hiển thị</h1>
          <p className="mt-2 text-sm text-slate-600">
            Trang không thể hiển thị đúng. Dữ liệu của bạn không bị thay đổi. Vui lòng tải lại trang;
            nếu lỗi lặp lại, hãy báo cho quản trị viên.
          </p>
          <div className="mt-5 flex justify-center gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-lg bg-[#3A5FC3] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
            >
              Tải lại trang
            </button>
            <a
              href="/"
              className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Về trang chủ
            </a>
          </div>
        </div>
      </div>
    );
  }
}
