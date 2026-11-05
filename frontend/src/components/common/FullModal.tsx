import { useEffect, useId, type ReactNode } from "react";
import ModalPortal from "./ModalPortal";

export interface FullModalProps {
  open: boolean;
  title: ReactNode;
  description?: ReactNode;
  onClose: () => void;
  /** Blocks backdrop click and Escape while an action is running. */
  closeDisabled?: boolean;
  /** Left side of the fixed footer (counts, status text). */
  footerStart?: ReactNode;
  /** Right side of the fixed footer (action buttons). */
  footerActions?: ReactNode;
  children: ReactNode;
}

/**
 * The project's "full modal": covers the content area under the top bar and beside the sidebar,
 * with a blue header (title + description), one scrolling body and a fixed action footer.
 * Same frame as the Imports / Reviews detail modals.
 */
export default function FullModal({
  open,
  title,
  description,
  onClose,
  closeDisabled = false,
  footerStart,
  footerActions,
  children,
}: FullModalProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !closeDisabled) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, closeDisabled, onClose]);

  if (!open) return null;

  return (
    <ModalPortal>
      <div
        className="fixed inset-x-0 top-16 bottom-0 md:left-[var(--app-sidebar-w)] z-50 flex items-center justify-center overflow-hidden bg-black/60 p-4 modal-backdrop-in transition-[left] duration-200 ease-out"
        onClick={() => {
          if (!closeDisabled) onClose();
        }}
      >
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          className="flex h-full w-full max-w-none flex-col overflow-hidden rounded-card border border-blue-200 bg-white shadow-2xl modal-panel-in"
          onClick={(event) => event.stopPropagation()}
        >
          <header className="flex shrink-0 items-start justify-between gap-4 border-b border-blue-100 bg-blue-50 px-5 py-4">
            <div className="min-w-0">
              <h2 id={titleId} className="text-base font-bold text-[#2f4ea6] sm:text-lg">
                {title}
              </h2>
              {description && <p className="mt-0.5 text-sm text-[#3A5FC3]">{description}</p>}
            </div>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
          {(footerStart || footerActions) && (
            <footer className="shrink-0 border-t border-slate-100 bg-white px-5 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm text-slate-500">{footerStart}</div>
                <div className="flex flex-wrap items-center gap-2">{footerActions}</div>
              </div>
            </footer>
          )}
        </section>
      </div>
    </ModalPortal>
  );
}
