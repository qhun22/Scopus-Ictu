import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useI18n } from "../../i18n";
import PublicationDetailBody from "./PublicationDetailBody";

export default function PublicationDetailPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { eid } = useParams<{ eid: string }>();
  // Opened from "Công bố của tôi" (W-02): go back there instead of the full catalogue.
  const fromMyPublications = (location.state as { from?: string } | null)?.from === "/my-publications";
  const backTarget = fromMyPublications ? "/my-publications" : "/publications";
  // Prefer a real history "back" (POP) over push-navigating to a fixed path,
  // so the list page is however the user actually left it; `navigate(backTarget)`
  // is only a fallback for a direct load/refresh with no in-app history to pop
  // (location.key is React Router's "default" for that case).
  const handleBack = () => {
    if (location.key !== "default") {
      navigate(-1);
    } else {
      navigate(backTarget);
    }
  };
  const { locale } = useI18n();
  const backLabel = locale === "vi" ? "Quay lại" : "Back";

  if (!eid) return null;

  return (
    <div className="app-page-container space-y-5">
      {/* ── Back navigation ────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={handleBack}
        className="inline-flex items-center gap-1.5 rounded-[5px] border border-slate-300 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-xs hover:border-[#3A5FC3] hover:text-[#3A5FC3] transition-colors cursor-pointer"
      >
        <span>{backLabel}</span>
      </button>

      <PublicationDetailBody
        eid={eid}
        errorActions={
          <button
            type="button"
            onClick={handleBack}
            className="rounded-[5px] border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
          >
            {backLabel}
          </button>
        }
      />
    </div>
  );
}
