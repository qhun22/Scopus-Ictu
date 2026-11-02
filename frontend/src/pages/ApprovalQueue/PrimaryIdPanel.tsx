import { useCallback, useEffect, useState } from "react";
import {
  clearPrimaryScopusIdentity,
  getLecturerScopusIdentities,
  setPrimaryScopusIdentity,
} from "../../api/lecturerScopus";
import { ApiError } from "../../api/client";
import Button from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";
import { ApprovedScopusIdentity } from "../../types/lecturerScopus";

type Locale = "vi" | "en";

const errorText = (error: unknown, vi: boolean): string => {
  if (error instanceof ApiError) return error.detail || error.message;
  return vi ? "Đã xảy ra lỗi không xác định." : "An unknown error occurred.";
};

/**
 * Shows a lecturer's approved Scopus IDs side by side and lets a reviewer mark ONE as the
 * main ID. It is a display label only: it never merges IDs or changes any publication list.
 * Rendered only when the lecturer holds two or more approved IDs.
 */
export default function PrimaryIdPanel({ lecturerId, locale }: { lecturerId: string; locale: Locale }) {
  const vi = locale === "vi";
  const toast = useToast();
  const [identities, setIdentities] = useState<ApprovedScopusIdentity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | "clear" | null>(null);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      setIdentities(await getLecturerScopusIdentities(lecturerId));
      setError(null);
    } catch (e) {
      setIdentities(null);
      setError(errorText(e, vi));
    }
  }, [lecturerId, vi]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <p className="text-xs text-rose-600">{error}</p>;
  if (!identities || identities.length < 2) return null;

  const hasPrimary = identities.some((i) => i.is_primary);

  const submit = async () => {
    if (!pendingId || !reason.trim()) return;
    setSubmitting(true);
    try {
      if (pendingId === "clear") await clearPrimaryScopusIdentity(lecturerId, { reason: reason.trim() });
      else await setPrimaryScopusIdentity(lecturerId, { identity_id: pendingId, reason: reason.trim() });
      toast.success(
        vi ? "Đã cập nhật ID chính" : "Main ID updated",
        vi ? "Nhãn ID chính chỉ để hiển thị, không gộp dữ liệu." : "The main ID is a display label only; nothing is merged.",
      );
      setPendingId(null);
      setReason("");
      await load();
    } catch (e) {
      toast.error(vi ? "Không cập nhật được ID chính" : "Could not update the main ID", errorText(e, vi));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="rounded-[5px] border border-slate-200 bg-slate-50/60 p-4" data-testid="primary-id-panel">
      <h3 className="text-sm font-semibold text-slate-800">
        {vi ? "ID Scopus chính của giảng viên" : "Lecturer's main Scopus ID"}
      </h3>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">
        {vi
          ? "Giảng viên có nhiều ID đã duyệt. Nhãn \"ID chính\" chỉ để hiển thị và không gộp hay thay đổi danh sách công bố."
          : "This lecturer has several approved IDs. The \"main ID\" label is for display only and never merges IDs or changes publication lists."}
      </p>
      <ul className="mt-3 space-y-2">
        {identities.map((identity) => (
          <li key={identity.identity_id} className="flex flex-wrap items-center gap-2 rounded-[5px] border border-slate-200 bg-white px-3 py-2">
            <span className="font-mono text-xs font-semibold text-slate-800">{identity.scopus_id}</span>
            <span className="text-xs text-slate-600">{identity.preferred_name}</span>
            <span className="text-[11px] text-slate-500">
              {identity.publication_count ?? 0} {vi ? "công bố" : "publications"}
            </span>
            {identity.is_primary && (
              <span className="inline-flex h-badge items-center rounded-[5px] border border-emerald-200 bg-emerald-50 px-2 text-[10px] font-bold text-emerald-700">
                {vi ? "ID chính" : "Main ID"}
              </span>
            )}
            {!hasPrimary && identity.is_suggested_primary && (
              <span className="inline-flex h-badge items-center rounded-[5px] border border-amber-200 bg-amber-50 px-2 text-[10px] font-bold text-amber-700">
                {vi ? "Gợi ý: nhiều công bố nhất" : "Suggested: most publications"}
              </span>
            )}
            {!identity.is_primary && (
              <Button
                variant="secondary"
                size="sm"
                className="ml-auto"
                onClick={() => { setPendingId(identity.identity_id); setReason(""); }}
              >
                {vi ? "Đặt làm ID chính" : "Set as main ID"}
              </Button>
            )}
          </li>
        ))}
      </ul>
      {hasPrimary && pendingId !== "clear" && (
        <button
          type="button"
          className="mt-2 text-xs font-semibold text-slate-500 underline underline-offset-2 hover:text-slate-700"
          onClick={() => { setPendingId("clear"); setReason(""); }}
        >
          {vi ? "Bỏ chọn ID chính" : "Remove the main ID label"}
        </button>
      )}
      {pendingId && (
        <div className="mt-3 rounded-[5px] border border-slate-200 bg-white p-3">
          <label htmlFor="primary-id-reason" className="mb-1 block text-xs font-semibold text-slate-700">
            {vi ? "Lý do" : "Reason"} <span className="text-rose-600">*</span>
          </label>
          <textarea
            id="primary-id-reason"
            value={reason}
            maxLength={4000}
            rows={2}
            onChange={(e) => setReason(e.target.value)}
            placeholder={vi ? "Nhập lý do (bắt buộc)…" : "Enter a reason (required)…"}
            className="w-full resize-none rounded-[5px] border border-slate-200 px-2.5 py-2 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
          />
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => { setPendingId(null); setReason(""); }} disabled={submitting}>
              {vi ? "Hủy" : "Cancel"}
            </Button>
            <Button size="sm" onClick={() => void submit()} disabled={!reason.trim() || submitting}>
              {pendingId === "clear"
                ? (vi ? "Xác nhận bỏ chọn" : "Confirm removal")
                : (vi ? "Xác nhận ID chính" : "Confirm main ID")}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
