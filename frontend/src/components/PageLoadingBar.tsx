import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { usePageVisit } from "../contexts/PageVisitContext";

const PROGRESS_COMPLETE_AT_MS = 450;
const HIDE_AFTER_MS = 650;

// eslint-disable-next-line @typescript-eslint/no-unused-vars
interface PageLoadingBarProps {
  isSidebarCollapsed?: boolean;
}

export default function PageLoadingBar(_props: PageLoadingBarProps) {
  const location = useLocation();
  const { hasVisited, markVisited } = usePageVisit();
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState<"idle" | "running" | "done">("idle");
  const pageKey = location.pathname;
  const isVisited = hasVisited(pageKey);

  useEffect(() => {
    if (isVisited) return;

    let isActive = true;
    setProgress(0);
    setPhase("running");

    const t1 = window.setTimeout(() => { if (isActive) setProgress(30); }, 30);
    const t2 = window.setTimeout(() => { if (isActive) setProgress(60); }, 150);
    const t3 = window.setTimeout(() => { if (isActive) setProgress(85); }, 280);
    const t4 = window.setTimeout(() => { if (isActive) setProgress(100); setPhase("done"); }, PROGRESS_COMPLETE_AT_MS);
    const t5 = window.setTimeout(() => {
      if (!isActive) return;
      setPhase("idle");
      markVisited(pageKey);
    }, HIDE_AFTER_MS);

    return () => {
      isActive = false;
      [t1, t2, t3, t4, t5].forEach(window.clearTimeout);
    };
  }, [isVisited, markVisited, pageKey]);

  if (isVisited || phase === "idle") return null;

  return (
    <div
      aria-label="Loading"
      aria-live="polite"
      data-testid="page-loading-bar"
      className="pointer-events-none fixed top-0 left-0 right-0 z-50 h-[3px]"
    >
      <div
        className="h-full bg-[#3A5FC3] shadow-[0_0_8px_rgba(58,95,195,0.6)] transition-[width] ease-out"
        style={{
          width: `${progress}%`,
          transitionDuration: phase === "done" ? "150ms" : "300ms",
        }}
      />
    </div>
  );
}
