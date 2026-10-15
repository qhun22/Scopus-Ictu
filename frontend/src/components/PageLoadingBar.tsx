import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { usePageVisit } from "../contexts/PageVisitContext";
import { useI18n } from "../i18n";

const OVERLAY_HIDE_MS = 700;
const OVERLAY_COMPLETE_MS = 500;
const TOP_BAR_COMPLETE_MS = 280;
const TOP_BAR_HIDE_MS = 460;

interface PageLoadingBarProps {
  isSidebarCollapsed?: boolean;
}

export default function PageLoadingBar({ isSidebarCollapsed = false }: PageLoadingBarProps) {
  const location = useLocation();
  const { hasVisited, markVisited } = usePageVisit();
  const { t } = useI18n();

  // ── top bar state (every route change) ──────────────────────────
  const [barProgress, setBarProgress] = useState(8);
  const [barVisible, setBarVisible] = useState(true);

  // ── overlay state (first visit only) ────────────────────────────
  const [overlayProgress, setOverlayProgress] = useState(8);
  const [overlayVisible, setOverlayVisible] = useState(true);

  const pageKey = location.pathname;
  const isFirstVisit = !hasVisited(pageKey);

  // Top bar — triggers on every route change (pathname + search)
  useEffect(() => {
    setBarVisible(true);
    setBarProgress(8);
    const t1 = window.setTimeout(() => setBarProgress(72), 120);
    const t2 = window.setTimeout(() => setBarProgress(100), TOP_BAR_COMPLETE_MS);
    const t3 = window.setTimeout(() => setBarVisible(false), TOP_BAR_HIDE_MS);
    return () => { [t1, t2, t3].forEach(window.clearTimeout); };
  }, [location.pathname, location.search]);

  // Overlay — triggers only on first visit to each route
  useEffect(() => {
    if (!isFirstVisit) {
      setOverlayVisible(false);
      return;
    }
    let isActive = true;
    setOverlayVisible(true);
    setOverlayProgress(8);
    const t1 = window.setTimeout(() => { if (isActive) setOverlayProgress(72); }, 120);
    const t2 = window.setTimeout(() => { if (isActive) setOverlayProgress(100); }, OVERLAY_COMPLETE_MS);
    const t3 = window.setTimeout(() => {
      if (!isActive) return;
      setOverlayVisible(false);
      markVisited(pageKey);
    }, OVERLAY_HIDE_MS);
    return () => { isActive = false; [t1, t2, t3].forEach(window.clearTimeout); };
  }, [isFirstVisit, markVisited, pageKey]);

  return (
    <>
      {/* ── Thin top bar — every navigation ── */}
      {barVisible && (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed inset-x-0 top-0 z-[100] h-[3px] bg-[#3A5FC3]/10"
        >
          <div
            className="h-full bg-[#3A5FC3] transition-[width] duration-300 ease-out"
            style={{ width: `${barProgress}%` }}
          />
        </div>
      )}

      {/* ── Full-page overlay — first visit only ── */}
      {overlayVisible && (
        <div
          aria-label={t.common.loading}
          aria-live="polite"
          aria-busy="true"
          data-testid="first-visit-loading"
          className={`pointer-events-none fixed top-16 bottom-0 right-0 z-30 flex items-center justify-center bg-[#f4f6fb]/80 px-4 backdrop-blur-[1px] transition-all duration-200 ease-out dark:bg-slate-950/80 ${
            isSidebarCollapsed ? "left-0 md:left-20" : "left-0 md:left-64"
          }`}
        >
          <div className="w-full max-w-sm text-center">
            <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-[#3A5FC3]" />
            <p className="mt-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
              {t.common.loading}
            </p>
            <div className="mt-4 h-1 overflow-hidden rounded-full bg-[#3A5FC3]/10">
              <div
                className="h-full bg-[#3A5FC3] transition-[width] duration-300 ease-out"
                style={{ width: `${overlayProgress}%` }}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
