import { useEffect, useId, useRef } from "react";
import ConfirmDialogFrame, {
  DialogSpinner,
  dialogCancelButtonClass,
  dialogConfirmButtonClass,
  dialogSecondaryButtonClass,
} from "./ConfirmDialogFrame";
import { useSingleFlight } from "./useSingleFlight";
import { useI18n } from "../../i18n";

export interface DuplicateImportDialogProps {
  open: boolean;
  fileName: string;
  previousFileName?: string;
  previousImportedAt?: string;
  loading?: boolean;
  onCancel: () => void;
  onViewPrevious: () => void;
  onConfirm: () => void | Promise<void>;
}

const FOCUSABLE = "button:not([disabled])";

export default function DuplicateImportDialog({
  open,
  fileName,
  previousFileName,
  previousImportedAt,
  loading = false,
  onCancel,
  onViewPrevious,
  onConfirm,
}: DuplicateImportDialogProps) {
  const { t, locale } = useI18n();
  const copy = t.imports;
  const uid = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const handleConfirm = useSingleFlight(onConfirm);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) {
        onCancel();
        return;
      }
      if (e.key !== "Tab" || !dialogRef.current) return;
      const items = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      const outside = !dialogRef.current.contains(active);
      if (e.shiftKey && (active === first || outside)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || outside)) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, loading, onCancel]);

  // Safe default: focus "Hủy" so a stray Enter never re-imports.
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const timer = window.setTimeout(() => cancelRef.current?.focus(), 50);
    return () => {
      window.clearTimeout(timer);
      previouslyFocused?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  const previousTime = previousImportedAt
    ? new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-US", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(previousImportedAt))
    : null;

  return (
    <ConfirmDialogFrame
      tone="warning"
      title={copy.duplicateDialogTitle}
      subtitle={copy.duplicateDialogDescription}
      titleId={`${uid}-title`}
      descId={`${uid}-desc`}
      dialogRef={dialogRef}
      footer={
        <>
          <button
            ref={cancelRef}
            type="button"
            disabled={loading}
            onClick={onCancel}
            className={dialogCancelButtonClass}
          >
            {t.common.cancel}
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={onViewPrevious}
            className={dialogSecondaryButtonClass}
          >
            {copy.viewPrevious}
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={handleConfirm}
            className={dialogConfirmButtonClass("warning")}
          >
            {loading && <DialogSpinner />}
            <span>{loading ? t.common.processing : copy.importAnyway}</span>
          </button>
        </>
      }
    >
      <p>
        {copy.duplicateDialogFileLabel}:{" "}
        <strong className="break-all text-gray-900">{fileName}</strong>
      </p>
      {(previousFileName || previousTime) && (
        <p>
          {copy.duplicateDialogPreviousLabel}:{" "}
          {previousFileName && <strong className="break-all text-gray-900">{previousFileName}</strong>}
          {previousTime && <span className="block whitespace-nowrap text-gray-600">{previousTime}</span>}
        </p>
      )}
      <p className="font-medium text-gray-800">{copy.duplicateDialogQuestion}</p>
    </ConfirmDialogFrame>
  );
}
