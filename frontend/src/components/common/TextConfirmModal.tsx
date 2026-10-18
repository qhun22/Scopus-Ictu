import { useEffect, useRef, useState } from "react";
import ModalPortal from "./ModalPortal";
import { useI18n } from "../../i18n";
import { buttonClass } from "../ui/Button";

export interface TextConfirmModalProps {
  open: boolean;
  title: string;
  subtitle?: string;
  description: string;
  confirmWord: string;
  confirmLabel: string;
  cancelLabel?: string;
  loading?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
}

export default function TextConfirmModal({
  open,
  title,
  subtitle,
  description,
  confirmWord,
  confirmLabel,
  cancelLabel,
  loading = false,
  onConfirm,
  onCancel,
}: TextConfirmModalProps) {
  const { t } = useI18n();
  const resolvedCancelLabel = cancelLabel ?? t.common.cancel;
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setInput("");
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) onCancel();
      if (e.key === "Enter" && input === confirmWord && !loading) void onConfirm();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, loading, input, confirmWord, onConfirm, onCancel]);

  if (!open) return null;

  return (
    <ModalPortal>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
        onClick={() => { if (!loading) onCancel(); }}
      >
        <div
          className="w-full max-w-md rounded-card border border-red-200 bg-white shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="rounded-t-card border-b border-red-100 bg-red-50 px-5 py-4">
            <h2 className="text-base font-semibold text-red-700">{title}</h2>
            {subtitle && <p className="mt-0.5 text-xs text-red-500">{subtitle}</p>}
          </div>

          {/* Body */}
          <div className="px-5 py-4 space-y-3">
            <p className="text-sm text-gray-700">{description}</p>
            <p className="text-sm font-medium text-gray-800">
              {t.common.typeToConfirmPrefix}{" "}
              <span
                className="font-mono font-bold text-red-600 cursor-pointer select-none underline decoration-dotted underline-offset-2 hover:text-red-700"
                title={t.common.clickToAutofill}
                onClick={() => setInput(confirmWord)}
              >
                {confirmWord}
              </span>{" "}
              {t.common.typeToConfirmSuffix}
            </p>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={confirmWord}
              disabled={loading}
              className="h-control w-full rounded-control border border-line px-3 text-[13px] font-mono focus:border-red-400 focus:outline-none focus:ring-2 focus:ring-red-200 disabled:opacity-60"
            />
          </div>

          {/* Footer */}
          <div className="flex flex-wrap justify-end gap-2 border-t border-gray-100 px-5 py-3">
            <button
              type="button"
              onClick={onCancel}
              disabled={loading}
              className={buttonClass("secondary")}
            >
              {resolvedCancelLabel}
            </button>
            <button
              type="button"
              onClick={() => void onConfirm()}
              disabled={input !== confirmWord || loading}
              className={buttonClass("danger")}
            >
              {loading && (
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              )}
              {confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </ModalPortal>
  );
}
