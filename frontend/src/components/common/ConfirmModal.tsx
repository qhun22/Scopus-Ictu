import React, { useEffect, useRef } from "react";
import ConfirmDialogFrame, {
  DialogSpinner,
  dialogCancelButtonClass,
  dialogConfirmButtonClass,
} from "./ConfirmDialogFrame";
import { useI18n } from "../../i18n";

export type ConfirmVariant = "danger" | "primary" | "warning";

export interface ConfirmModalProps {
  open: boolean;
  title: string;
  description: string | React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  showConfirmButton?: boolean;
  variant?: ConfirmVariant;
  confirmClassName?: string;
  loading?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
}

export default function ConfirmModal({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel,
  showConfirmButton = true,
  variant = "danger",
  confirmClassName,
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const { t } = useI18n();
  const resolvedConfirmLabel = confirmLabel ?? t.common.confirm;
  const resolvedCancelLabel = cancelLabel ?? t.common.cancel;
  const confirmBtnRef = useRef<HTMLButtonElement>(null);

  // Handle Escape key listener
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) {
        onCancel();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, loading, onCancel]);

  // Focus confirmation button on open
  useEffect(() => {
    if (open) {
      setTimeout(() => {
        confirmBtnRef.current?.focus();
      }, 50);
    }
  }, [open]);

  if (!open) return null;

  return (
    <ConfirmDialogFrame
      tone={variant}
      title={title}
      titleId="confirm-modal-title"
      descId="confirm-modal-desc"
      onBackdropClick={() => {
        if (!loading) onCancel();
      }}
      footer={
        <>
          {showConfirmButton && (
            <button
              type="button"
              disabled={loading}
              onClick={onCancel}
              className={dialogCancelButtonClass}
            >
              {resolvedCancelLabel}
            </button>
          )}

          <button
            ref={confirmBtnRef}
            type="button"
            disabled={loading}
            onClick={onConfirm}
            className={dialogConfirmButtonClass(variant, confirmClassName)}
          >
            {loading && <DialogSpinner />}
            <span>{loading ? t.common.processing : resolvedConfirmLabel}</span>
          </button>
        </>
      }
    >
      {description}
    </ConfirmDialogFrame>
  );
}
