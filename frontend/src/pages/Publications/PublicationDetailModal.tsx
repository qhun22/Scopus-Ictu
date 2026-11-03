import { useEffect } from "react";
import ModalPortal from "../../components/common/ModalPortal";
import { useI18n } from "../../i18n";
import { buttonClass } from "../../components/ui/Button";
import PublicationDetailBody from "./PublicationDetailBody";

export interface PublicationDetailModalProps {
  /** EID of the publication to show; the modal renders nothing when null. */
  eid: string | null;
  onClose: () => void;
}

/**
 * Large modal showing a publication's full detail (same content as the
 * standalone `/publications/:eid` page) without navigating away from the
 * list — so the list's scroll position, filters and search stay exactly as
 * they were when the modal closes.
 */
export default function PublicationDetailModal({ eid, onClose }: PublicationDetailModalProps) {
  const { locale } = useI18n();

  // Lock the page behind the modal: otherwise, since this modal's content is
  // taller than most, the page is still tall/scrollable behind it and the
  // browser shows its own native scrollbar alongside the modal's own one —
  // looks like the modal is spilling out past the screen.
  useEffect(() => {
    if (!eid) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [eid]);

  if (!eid) return null;

  const title = locale === "vi" ? "Chi tiết công bố" : "Publication detail";

  return (
    <ModalPortal>
      <div
        className="fixed inset-x-0 top-16 bottom-0 md:left-[var(--app-sidebar-w)] z-50 flex items-center justify-center overflow-y-auto bg-black/60 p-4 modal-backdrop-in transition-[left] duration-200 ease-out"
        onClick={onClose}
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="publication-detail-modal-title"
          className="h-full w-full max-w-none overflow-y-auto rounded-card border border-slate-200 bg-white shadow-2xl modal-panel-in"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="sticky top-0 z-10 flex items-center justify-between rounded-t-card border-b border-slate-100 bg-slate-50 px-5 py-4">
            <h2 id="publication-detail-modal-title" className="text-base font-bold text-slate-800">
              {title}
            </h2>
            <button type="button" onClick={onClose} className={buttonClass("secondary")}>
              {locale === "vi" ? "Đóng" : "Close"}
            </button>
          </div>

          <div className="px-5 py-4">
            <PublicationDetailBody eid={eid} onNavigateAway={onClose} />
          </div>
        </div>
      </div>
    </ModalPortal>
  );
}
