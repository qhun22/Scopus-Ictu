import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

const COMPLETE_DELAY_MS = 180;

export default function PageLoadingBar() {
  const location = useLocation();
  const [progress, setProgress] = useState(8);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    setVisible(true);
    setProgress(8);

    const progressTimer = window.setTimeout(() => setProgress(72), 120);
    const completeTimer = window.setTimeout(() => setProgress(100), 280);
    const hideTimer = window.setTimeout(
      () => setVisible(false),
      280 + COMPLETE_DELAY_MS,
    );

    return () => {
      window.clearTimeout(progressTimer);
      window.clearTimeout(completeTimer);
      window.clearTimeout(hideTimer);
    };
  }, [location.pathname, location.search]);

  if (!visible) return null;

  return (
    <div
      aria-label="Đang tải trang"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 top-0 z-[100] h-1 bg-[#3A5FC3]/10"
    >
      <div
        className="h-full bg-[#3A5FC3] transition-[width] duration-300 ease-out"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
