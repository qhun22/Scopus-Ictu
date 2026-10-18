import React from "react";
import ModalPortal from "./ModalPortal";
import { buttonClass } from "../ui/Button";

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
    // PROPOSED: Figma 5:2 has no warning button; keep the amber colour on the shared button shape.
    button: "border border-amber-600 bg-amber-600 text-white hover:bg-amber-700 focus-visible:ring-amber-300",
  },
  primary: {
    panel: "border-blue-200",
    header: "border-blue-100 bg-blue-50",
    title: "text-[#2f4ea6]",
    subtitle: "text-[#3A5FC3]",
    button: "bg-[#3A5FC3] hover:bg-[#2f4ea6] focus-visible:ring-blue-300",
  },
};

// Dialog buttons use the shared Button classes (Figma "Buttons" 5:2): Cancel = Secondary, extra action = Ghost,
// Confirm = Primary / Danger. Warning has no Figma variant: the shared md shape with the amber colour (PROPOSED).
export const dialogCancelButtonClass = buttonClass("secondary");

export const dialogSecondaryButtonClass = buttonClass("ghost");

const WARNING_SHAPE =
  "inline-flex shrink-0 items-center justify-center whitespace-nowrap font-semibold leading-none transition-colors duration-150 cursor-pointer " +
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 " +
  "h-control min-w-action gap-1.5 rounded-control px-4 text-[13px]";

export function dialogConfirmButtonClass(tone: DialogTone, override?: string): string {
  if (override) return `${WARNING_SHAPE} ${override}`;
  if (tone === "danger") return buttonClass("danger");
  if (tone === "primary") return buttonClass("primary");
  return `${WARNING_SHAPE} ${TONES.warning.button}`;
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
          className={`max-h-[calc(100vh-2rem)] w-full max-w-md overflow-y-auto rounded-card border bg-white shadow-2xl ${styles.panel}`}
          onClick={(e) => e.stopPropagation()}
        >
          <div className={`rounded-t-card border-b px-5 py-4 ${styles.header}`}>
            <h2 id={titleId} className={`text-base font-semibold ${styles.title}`}>
              {title}
            </h2>
            {subtitle && <p className={`mt-0.5 text-xs ${styles.subtitle}`}>{subtitle}</p>}
          </div>

          <div id={descId} className="space-y-3 px-5 py-4 text-sm text-gray-700">
            {children}
          </div>

          <div className="flex flex-wrap justify-end gap-2 border-t border-gray-100 px-5 py-3">{footer}</div>
        </div>
      </div>
    </ModalPortal>
  );
}
