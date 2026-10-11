import React from "react";
import ModalPortal from "./ModalPortal";

export type DialogTone = "danger" | "warning" | "primary";

/**
 * Layout copied from the "Reset toàn hệ thống" dialog (TextConfirmModal):
 * dark backdrop, white rounded panel, tinted header with a divider,
 * body, and a right-aligned footer with a divider. Only the colours change
 * with the severity of the action.
 */
const TONES: Record<
  DialogTone,
  { panel: string; header: string; title: string; subtitle: string; button: string }
> = {
  danger: {
    panel: "border-red-200",
    header: "border-red-100 bg-red-50",
    title: "text-red-700",
    subtitle: "text-red-500",
    button: "bg-red-600 hover:bg-red-700 focus-visible:ring-red-300",
  },
  warning: {
    panel: "border-amber-200",
    header: "border-amber-100 bg-amber-50",
    title: "text-amber-800",
    subtitle: "text-amber-600",
    button: "bg-amber-600 hover:bg-amber-700 focus-visible:ring-amber-300",
  },
  primary: {
    panel: "border-blue-200",
    header: "border-blue-100 bg-blue-50",
    title: "text-[#2f4ea6]",
    subtitle: "text-[#3A5FC3]",
    button: "bg-[#3A5FC3] hover:bg-[#2f4ea6] focus-visible:ring-blue-300",
  },
};

const focusRing = "focus-visible:outline-none focus-visible:ring-2";

export const dialogCancelButtonClass = `rounded-md border border-gray-300 bg-white px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 ${focusRing} focus-visible:ring-gray-300`;

export const dialogSecondaryButtonClass = `rounded-md border border-amber-300 bg-white px-4 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-50 disabled:opacity-50 ${focusRing} focus-visible:ring-amber-300`;

export function dialogConfirmButtonClass(tone: DialogTone, override?: string): string {
  return `inline-flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40 disabled:cursor-not-allowed ${focusRing} ${override ?? TONES[tone].button}`;
}

export function DialogSpinner() {
  return (
    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
  );
}

export interface ConfirmDialogFrameProps {
  tone: DialogTone;
  title: string;
  subtitle?: string;
  titleId: string;
  descId: string;
  dialogRef?: React.Ref<HTMLDivElement>;
  onBackdropClick?: () => void;
  footer: React.ReactNode;
  children: React.ReactNode;
}

export default function ConfirmDialogFrame({
  tone,
  title,
  subtitle,
  titleId,
  descId,
  dialogRef,
  onBackdropClick,
  footer,
  children,
}: ConfirmDialogFrameProps) {
  const styles = TONES[tone];
  return (
    <ModalPortal>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 p-4"
        onClick={onBackdropClick}
      >
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          aria-describedby={descId}
          className={`max-h-[calc(100vh-2rem)] w-full max-w-md overflow-y-auto rounded-lg border bg-white shadow-2xl ${styles.panel}`}
          onClick={(e) => e.stopPropagation()}
        >
          <div className={`rounded-t-lg border-b px-5 py-4 ${styles.header}`}>
            <h2 id={titleId} className={`text-base font-semibold ${styles.title}`}>
              {title}
            </h2>
            {subtitle && <p className={`mt-0.5 text-xs ${styles.subtitle}`}>{subtitle}</p>}
          </div>

          <div id={descId} className="space-y-3 px-5 py-4 text-sm text-gray-700">
            {children}
          </div>

          <div className="flex justify-end gap-2 border-t border-gray-100 px-5 py-3">{footer}</div>
        </div>
      </div>
    </ModalPortal>
  );
}
