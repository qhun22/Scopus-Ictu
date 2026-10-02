import { Locale } from "../../i18n/types";

interface LanguageTransitionOverlayProps {
  isVisible: boolean;
  pendingLocale: Locale | null;
}

export default function LanguageTransitionOverlay({
  isVisible,
  pendingLocale,
}: LanguageTransitionOverlayProps) {
  if (!isVisible || !pendingLocale) return null;

  // Text rule:
  // When VI -> EN: "Đang chuyển sang English..."
  // When EN -> VI: "Switching to Tiếng Việt..."
  const isSwitchingToEnglish = pendingLocale === "en";
  const mainMessage = isSwitchingToEnglish
    ? "Đang chuyển sang English..."
    : "Switching to Tiếng Việt...";
  const subMessage = isSwitchingToEnglish
    ? "Vui lòng chờ trong giây lát"
    : "Please wait a moment";

  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-white/94 backdrop-blur-md select-none cursor-wait animate-in fade-in duration-200"
      tabIndex={-1}
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.stopPropagation()}
    >
      {/* Floating loading cat icon (independent, no container box) */}
      <div className="relative mb-3 flex h-20 w-20 items-center justify-center">
        <img
          src="/assets/mona-loading-default-c3c7aad1282f.gif"
          alt="Loading animation"
          className="h-full w-full object-contain pointer-events-none"
        />
      </div>

      {/* Main Transition Text */}
      <p className="text-base font-bold tracking-tight text-slate-900 sm:text-lg">
        {mainMessage}
      </p>

      {/* Subtitle */}
      <p className="mt-1 text-xs font-medium text-slate-500 sm:text-sm">
        {subMessage}
      </p>
    </div>
  );
}
