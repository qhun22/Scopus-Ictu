import { useCallback, useEffect, useMemo, useState } from "react";
import { addOverridesBulk, getNeedsReview, NeedsReviewItem, OverrideFull } from "../../api/affiliations";
import { ApiError } from "../../api/client";
import { useToast } from "../../contexts/ToastContext";

type Locale = "vi" | "en";

const BUTTON =
  "inline-flex h-badge w-32 shrink-0 cursor-pointer items-center justify-center whitespace-nowrap rounded-[5px] border border-[#3A5FC3] bg-white px-2 text-center text-xs font-bold leading-none text-[#3A5FC3] hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50";

const errorText = (error: unknown, vi: boolean): string => {
  if (error instanceof ApiError) return error.detail || error.message;
  return vi ? "Có lỗi không xác định." : "Unknown error.";
};

const evidenceFor = (item: NeedsReviewItem, fallback: string): string =>
  item.doi ? `https://doi.org/${item.doi}` : fallback;

const sourceTexts = (item: NeedsReviewItem): string[] => [
  ...new Set(item.resolution_summaries.flatMap((r) => r.raw_affiliations ?? [])),
];

/**
 * Lists the OTHER positions of the same Scopus author so an ADMIN who has checked each paper can
 * give them the same unit in one step. Nothing is pre-selected and nothing is inferred: every
 * position keeps its own row, evidence and audit event, and the whole batch is all-or-nothing.
 */
export default function ApplyToOtherPositions({
  item,
  locale,
  onDone,
}: {
  item: NeedsReviewItem;
  locale: Locale;
  onDone: () => Promise<void> | void;
}) {
  const vi = locale === "vi";
  const toast = useToast();
  const sources: OverrideFull[] = item.overrides.filter((o) => o.status === "ACTIVE");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [others, setOthers] = useState<NeedsReviewItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [unitId, setUnitId] = useState<string>(sources[0]?.id ?? "");
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  const unit = sources.find((o) => o.id === unitId) ?? sources[0];

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getNeedsReview({ query: item.scopus_id, limit: 100 });
      setOthers(
        res.items.filter((i) => i.scopus_id === item.scopus_id && i.publication_author_id !== item.publication_author_id),
      );
    } catch (e) {
      setError(errorText(e, vi));
    } finally {
      setLoading(false);
    }
  }, [item.scopus_id, item.publication_author_id, vi]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  const candidates = useMemo(
    () =>
      others.filter(
        (o) => !o.overrides.some((x) => x.status === "ACTIVE" && x.affiliation_text === unit?.affiliation_text),
      ),
    [others, unit],
  );
  const chosen = candidates.filter((c) => selected[c.publication_author_id]);

  if (!unit) return null;

  const submit = async () => {
    if (chosen.length === 0 || !reason.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await addOverridesBulk({
        items: chosen.map((c) => ({
          publication_author_id: c.publication_author_id,
          evidence_url: evidenceFor(c, unit.evidence_url),
        })),
        affiliation_text: unit.affiliation_text,
        confidence: unit.confidence,
        reason: reason.trim(),
      });
      toast.success(
        vi ? "Đã áp dụng cho các bài khác" : "Applied to the other papers",
        vi
          ? `Đã thêm "${unit.affiliation_text}" cho ${chosen.length} vị trí, mỗi vị trí có chứng cứ và nhật ký riêng.`
          : `Added "${unit.affiliation_text}" to ${chosen.length} positions, each with its own evidence and audit entry.`,
      );
      setSelected({});
      setReason("");
      await onDone();
      await load();
    } catch (e) {
      setError(errorText(e, vi));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-[5px] border border-slate-200 bg-white p-3" data-testid="apply-to-others">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-bold text-slate-700">
            {vi ? "Áp dụng cho các bài khác của tác giả này" : "Apply to this author's other papers"}
          </p>
          <p className="mt-0.5 text-[11px] text-slate-500">
            {vi
              ? "Không chọn sẵn bài nào. Mỗi bài vẫn có chứng cứ và nhật ký riêng."
              : "Nothing is pre-selected. Each paper keeps its own evidence and audit entry."}
          </p>
        </div>
        <button type="button" className={BUTTON} onClick={() => setOpen((v) => !v)}>
          {open ? (vi ? "Thu gọn" : "Collapse") : vi ? "Xem các bài khác" : "Show other papers"}
        </button>
      </div>

      {open && (
        <div className="mt-3 space-y-3">
          {sources.length > 1 && (
            <label className="block text-[11px] font-semibold text-slate-600">
              {vi ? "Đơn vị sẽ áp dụng" : "Unit to apply"}
              <select
                className="mt-1 w-full rounded-[5px] border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-800"
                value={unit.id}
                onChange={(e) => setUnitId(e.target.value)}
              >
                {sources.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.affiliation_text}
                  </option>
                ))}
              </select>
            </label>
          )}
          <p className="text-[11px] text-slate-600">
            {vi ? "Đơn vị áp dụng:" : "Unit to apply:"}{" "}
            <span className="font-semibold text-slate-800">{unit.affiliation_text}</span>
          </p>

          {loading ? (
            <p className="text-xs text-slate-400">{vi ? "Đang tải dữ liệu..." : "Loading…"}</p>
          ) : candidates.length === 0 ? (
            <p className="text-xs text-slate-400">
              {vi ? "Không còn bài nào khác cần áp dụng đơn vị này." : "No other paper needs this unit."}
            </p>
          ) : (
            <ul className="space-y-2">
              {candidates.map((c) => {
                const texts = sourceTexts(c);
                return (
                  <li key={c.publication_author_id} className="rounded-[5px] border border-slate-200 p-2.5 text-[11px]">
                    <label className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        className="mt-0.5"
                        checked={!!selected[c.publication_author_id]}
                        onChange={(e) =>
                          setSelected((prev) => ({ ...prev, [c.publication_author_id]: e.target.checked }))
                        }
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block font-semibold text-slate-800">{c.title}</span>
                        <span className="block text-slate-500">{c.eid}</span>
                        <span className="mt-1 block text-slate-500">
                          {vi ? "Nguồn ghi: " : "Sources report: "}
                          {texts.length > 0 ? (
                            <span className="text-slate-700">{texts.join(" · ")}</span>
                          ) : (
                            <span className="text-slate-400">{vi ? "không có đơn vị" : "no affiliation"}</span>
                          )}
                        </span>
                        <span className="block text-slate-500">
                          {vi ? "Chứng cứ: " : "Evidence: "}
                          <span className="text-slate-700">{evidenceFor(c, unit.evidence_url)}</span>
                        </span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}

          {candidates.length > 0 && (
            <>
              <div>
                <label className="text-[11px] font-semibold text-slate-600" htmlFor="apply-others-reason">
                  {vi ? "Lý do chung *" : "Shared reason *"}
                </label>
                <textarea
                  id="apply-others-reason"
                  rows={2}
                  className="mt-1 w-full rounded-[5px] border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder={
                    vi
                      ? "VD: Đã kiểm tra từng bài, nguồn ghi cùng đơn vị."
                      : "e.g. Checked each paper; sources report the same unit."
                  }
                />
              </div>
              <button
                type="button"
                disabled={saving || chosen.length === 0 || !reason.trim()}
                onClick={() => void submit()}
                className={BUTTON}
              >
                {saving
                  ? vi
                    ? "Đang lưu…"
                    : "Saving…"
                  : vi
                    ? `Áp dụng cho ${chosen.length} bài`
                    : `Apply to ${chosen.length}`}
              </button>
            </>
          )}
          {error && (
            <p className="text-[11px] font-medium text-rose-600" role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
