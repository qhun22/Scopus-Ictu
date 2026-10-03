import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export type ToastLevel = "success" | "error" | "warning" | "info";

export interface ToastItemData {
  id: string;
  level: ToastLevel;
  title: string;
  message: string;
  ttl: number; // in ms, 0 = persistent
  createdAt: number;
}

export interface ToastOptions {
  level: ToastLevel;
  title: string;
  message: string;
  ttl?: number;
}

interface ToastContextType {
  toasts: ToastItemData[];
  showToast: (options: ToastOptions) => void;
  removeToast: (id: string) => void;
  success: (title: string, message: string, ttl?: number) => void;
  error: (title: string, message: string, ttl?: number) => void;
  warning: (title: string, message: string, ttl?: number) => void;
  info: (title: string, message: string, ttl?: number) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

const MAX_TOASTS = 5;
const DEFAULT_TTL = 5000;

interface ToastComponentProps {
  toast: ToastItemData;
  onClose: (id: string) => void;
}

function ToastCard({ toast, onClose }: ToastComponentProps) {
  const [remainingTime, setRemainingTime] = useState(toast.ttl);
  const isPausedRef = useRef(false);
  const lastTickRef = useRef(Date.now());

  // Reset remaining time when toast ID/instance updates
  useEffect(() => {
    setRemainingTime(toast.ttl);
    lastTickRef.current = Date.now();
  }, [toast.id, toast.ttl]);

  // Interval timer updating remaining time
  useEffect(() => {
    if (toast.ttl <= 0) return;

    const interval = setInterval(() => {
      if (!isPausedRef.current) {
        const now = Date.now();
        const delta = now - lastTickRef.current;
        lastTickRef.current = now;

        setRemainingTime((prev) => Math.max(0, prev - delta));
      } else {
        lastTickRef.current = Date.now();
      }
    }, 40);

    return () => clearInterval(interval);
  }, [toast.id, toast.ttl]);

  // Safe effect-based trigger to close toast when countdown completes
  useEffect(() => {
    if (toast.ttl > 0 && remainingTime <= 0) {
      onClose(toast.id);
    }
  }, [remainingTime, toast.ttl, toast.id, onClose]);

  const handleMouseEnter = () => {
    isPausedRef.current = true;
  };

  const handleMouseLeave = () => {
    isPausedRef.current = false;
    lastTickRef.current = Date.now();
  };

  // Standard library-style solid / filled icons
  const getLevelStyles = (level: ToastLevel) => {
    switch (level) {
      case "success":
        return {
          progressBar: "bg-emerald-500",
          icon: (
            <svg className="h-4.5 w-4.5 text-emerald-500" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
                clipRule="evenodd"
              />
            </svg>
          ),
        };
      case "error":
        return {
          progressBar: "bg-rose-500",
          icon: (
            <svg className="h-4.5 w-4.5 text-rose-500" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
                clipRule="evenodd"
              />
            </svg>
          ),
        };
      case "warning":
        return {
          progressBar: "bg-amber-500",
          icon: (
            <svg className="h-4.5 w-4.5 text-amber-500" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
                clipRule="evenodd"
              />
            </svg>
          ),
        };
      case "info":
      default:
        return {
          progressBar: "bg-[#3A5FC3]",
          icon: (
            <svg className="h-4.5 w-4.5 text-[#3A5FC3]" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
                clipRule="evenodd"
              />
            </svg>
          ),
        };
    }
  };

  const styles = getLevelStyles(toast.level);
  const progressPercent =
    toast.ttl > 0 ? Math.max(0, Math.min(100, (remainingTime / toast.ttl) * 100)) : 100;

  return (
    <div
      role="status"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className="pointer-events-auto relative flex w-full max-w-[290px] flex-col overflow-hidden rounded-lg border border-slate-200 bg-white p-3 shadow-sm transition-all duration-200 animate-in fade-in slide-in-from-top-2"
    >
      {/* Header hàng ngang: [Icon Thư Viện] - Tiêu đề - [X] hoàn toàn thẳng hàng */}
      <div className="flex items-center gap-2">
        <div className="flex h-5 w-5 shrink-0 items-center justify-center">
          {styles.icon}
        </div>

        <h4 className="min-w-0 flex-1 text-sm font-bold text-slate-800 leading-snug truncate">
          {toast.title}
        </h4>

        <button
          type="button"
          onClick={() => onClose(toast.id)}
          aria-label="Đóng thông báo"
          className="-mr-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Nội dung thông báo: Thụt lề theo tiêu đề, chữ nhiều tự động xuống dòng gọn gàng */}
      {toast.message && (
        <p className="mt-1 pl-[28px] text-xs leading-relaxed text-slate-600 break-words">
          {toast.message}
        </p>
      )}

      {/* Thanh tiến trình thời gian giảm dần (Progress Countdown Bar) */}
      {toast.ttl > 0 && (
        <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-slate-100">
          <div
            className={`h-full transition-all duration-75 ease-linear ${styles.progressBar}`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      )}
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItemData[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((options: ToastOptions) => {
    const ttl = options.ttl ?? DEFAULT_TTL;

    setToasts((prev) => {
      // Nếu đã có thông báo cùng level + title -> đè lên box cũ và reset lại time về 100% (không sinh thêm box mới)
      const existingIndex = prev.findIndex(
        (t) => t.level === options.level && t.title === options.title
      );

      if (existingIndex !== -1) {
        const updated = [...prev];
        updated[existingIndex] = {
          id: `toast-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
          level: options.level,
          title: options.title,
          message: options.message,
          ttl,
          createdAt: Date.now(),
        };
        return updated;
      }

      const newToast: ToastItemData = {
        id: `toast-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        level: options.level,
        title: options.title,
        message: options.message,
        ttl,
        createdAt: Date.now(),
      };

      const nextList = [...prev, newToast];
      if (nextList.length > MAX_TOASTS) {
        return nextList.slice(nextList.length - MAX_TOASTS);
      }
      return nextList;
    });
  }, []);

  const success = useCallback(
    (title: string, message: string, ttl?: number) => {
      showToast({ level: "success", title, message, ttl });
    },
    [showToast]
  );

  const error = useCallback(
    (title: string, message: string, ttl?: number) => {
      showToast({ level: "error", title, message, ttl });
    },
    [showToast]
  );

  const warning = useCallback(
    (title: string, message: string, ttl?: number) => {
      showToast({ level: "warning", title, message, ttl });
    },
    [showToast]
  );

  const info = useCallback(
    (title: string, message: string, ttl?: number) => {
      showToast({ level: "info", title, message, ttl });
    },
    [showToast]
  );

  const contextValue = useMemo(
    () => ({
      toasts,
      showToast,
      removeToast,
      success,
      error,
      warning,
      info,
    }),
    [toasts, showToast, removeToast, success, error, warning, info]
  );

  return (
    <ToastContext.Provider value={contextValue}>
      {children}

      {/* Top-Right Toast Viewport Container */}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed right-3 top-3 z-[1000] flex max-h-screen w-auto max-w-sm flex-col items-end gap-2 sm:right-5 sm:top-5"
      >
        {toasts.map((toast) => (
          <ToastCard key={toast.id} toast={toast} onClose={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextType {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
