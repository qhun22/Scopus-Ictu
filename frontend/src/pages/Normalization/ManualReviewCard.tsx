import { useCallback, useEffect, useState } from "react";
import {
  deleteOverride,
  getNeedsReview,
  NeedsReviewItem,
  OverrideFull,
  putOverride,
} from "../../api/affiliations";
import { ApiError } from "../../api/client";
import { BUTTON_PRIMARY, BUTTON_SECONDARY } from "../../components/common/buttonStyles";
import { useSingleFlight } from "../../components/common/useSingleFlight";
import { useToast } from "../../contexts/ToastContext";

type Locale = "vi" | "en";

const REASON_KIND_LABEL: Record<string, Record<Locale, string>> = {
  UNRESOLVED: { vi: "Chưa có đơn vị", en: "No unit" },
  CONFLICTING_SOURCES: { vi: "Nguồn mâu thuẫn", en: "Conflicting sources" },
  LOW_CONFIDENCE: { vi: "Chỉ đối chiếu, chưa xác minh", en: "Corroborated only, not verified" },
};
const REASON_KIND_STYLE: Record<string, string> = {
  UNRESOLVED: "bg-slate-100 text-slate-600 border-slate-200",
  CONFLICTING_SOURCES: "bg-rose-50 text-rose-700 border-rose-200",
  LOW_CONFIDENCE: "bg-amber-50 text-amber-700 border-amber-200",
};

const ERROR_LABEL: Record<string, Record<Locale, string>> = {
  STALE_OVERRIDE_VERSION: {
    vi: "Dữ liệu đã bị người khác thay đổi. Danh sách sẽ được tải lại.",
    en: "Someone else changed this already. The list will reload.",
  },
  PUBLICATION_AUTHOR_NOT_FOUND: { vi: "Không tìm thấy vị trí tác giả này.", en: "Author position not found." },
  OVERRIDE_NOT_FOUND: { vi: "Không tìm thấy hiệu chỉnh này.", en: "Override not found." },
  MISSING_EVIDENCE: { vi: "Cần dẫn nguồn chứng cứ.", en: "Evidence source is required." },
  MISSING_REASON: { vi: "Cần ghi lý do thao tác.", en: "A reason is required." },
  MISSING_AFFILIATION_TEXT: { vi: "Cần nhập tên đơn vị.", en: "Unit name is required." },
};

function explain(error: unknown, locale: Locale): string {
  if (error instanceof ApiError) {
    return (error.code && ERROR_LABEL[error.code]?.[locale]) || error.detail || error.message;
  }
  return locale === "vi" ? "Có lỗi không xác định." : "Unknown error.";
}

interface EditForm {
  affiliation_text: string;
  confidence: "CORROBORATED" | "UNRESOLVED";
  evidence_url: string;
  reason: string;
}

const EMPTY_FORM: EditForm = { affiliation_text: "", confidence: "CORROBORATED", evidence_url: "", reason: "" };

function ReviewRow({
  item,
  locale,
  onSaved,
  onDeleted,
}: {
  item: NeedsReviewItem;
  locale: Locale;
  onSaved: () => void;
  onDeleted: () => void;
}) {
  const vi = locale === "vi";
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<EditForm>(EMPTY_FORM);
  const [current, setCurrent] = useState<OverrideFull | null>(item.override);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setForm(
      current
        ? {
            affiliation_text: current.affiliation_text,
            confidence: current.confidence,
            evidence_url: current.evidence_url,
            reason: "",
          }
        : EMPTY_FORM,
    );
    setError(null);
    setEditing(true);
  };

  const save = useSingleFlight(async () => {
    setSaving(true);
    setError(null);
    try {
      const saved = await putOverride(item.publication_author_id, {
        ...form,
        expected_version: current?.version ?? null,
      });
      setCurrent(saved);
      setEditing(false);
      toast.success(vi ? "Đã lưu hiệu chỉnh" : "Override saved", vi ? "Đơn vị đã được ghi nhận có bằng chứng." : "The unit was recorded with evidence.");
      onSaved();
    } catch (err) {
      setError(explain(err, locale));
      if (err instanceof ApiError && err.code === "STALE_OVERRIDE_VERSION") onSaved();
    } finally {
      setSaving(false);
    }
  });

  const remove = useSingleFlight(async () => {
    if (!current) return;
    setSaving(true);
    setError(null);
    try {
      await deleteOverride(item.publication_author_id, current.version);
      setCurrent(null);
      toast.success(vi ? "Đã xóa hiệu chỉnh" : "Override removed", "");
      onDeleted();
    } catch (err) {
      setError(explain(err, locale));
    } finally {
      setSaving(false);
    }
  });

  return (
    <li className="rounded-lg border border-slate-200 p-3" data-testid="review-item">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-slate-800">
            {item.eid} · {vi ? "vị trí" : "position"} {item.author_order} · {item.preferred_name} ({item.scopus_id})
          </p>
          <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-500">{item.title}</p>
          <span
            className={`mt-1 inline-flex rounded border px-1.5 py-0.5 text-[10px] font-bold ${REASON_KIND_STYLE[item.reason_kind]}`}
          >
            {REASON_KIND_LABEL[item.reason_kind]?.[locale] ?? item.reason_kind}
          </span>
          {current && (
            <span className="ml-1.5 text-[10px] font-medium text-violet-600">
              {vi ? "Đã có hiệu chỉnh" : "Has an override"}
            </span>
          )}
        </div>
        {!editing && (
          <button type="button" className={BUTTON_SECONDARY} onClick={startEdit} data-testid="review-edit-btn">
            {vi ? "Hiệu chỉnh" : "Review"}
          </button>
        )}
      </div>

      <div className="mt-1.5 text-[10px] text-slate-500" data-testid="review-resolutions">
        {item.resolution_summaries
          .map((r) => `${r.source_system}: ${r.link_status}${r.unresolved_reason ? ` (${r.unresolved_reason})` : ""}`)
          .join(" · ")}
      </div>

      {editing && (
        <div className="mt-2.5 space-y-2 rounded-lg border border-violet-200 bg-violet-50/40 p-2.5">
          <div>
            <label className="text-[10px] font-semibold text-slate-600">{vi ? "Tên đơn vị" : "Unit name"}</label>
            <input
              className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-xs"
              value={form.affiliation_text}
              onChange={(e) => setForm((f) => ({ ...f, affiliation_text: e.target.value }))}
              data-testid="review-input-text"
            />
          </div>
          <div>
            <label className="text-[10px] font-semibold text-slate-600">
              {vi ? "Mức tin cậy" : "Confidence"}
            </label>
            <select
              className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-xs"
              value={form.confidence}
              onChange={(e) => setForm((f) => ({ ...f, confidence: e.target.value as EditForm["confidence"] }))}
              data-testid="review-input-confidence"
            >
              <option value="CORROBORATED">{vi ? "Đã đối chiếu · Chưa xác minh" : "Corroborated · Not verified"}</option>
              <option value="UNRESOLVED">{vi ? "Vẫn chưa xác định" : "Still unresolved"}</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] font-semibold text-slate-600">
              {vi ? "Nguồn chứng cứ (URL)" : "Evidence source (URL)"}
            </label>
            <input
              className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-xs"
              value={form.evidence_url}
              onChange={(e) => setForm((f) => ({ ...f, evidence_url: e.target.value }))}
              placeholder="https://..."
              data-testid="review-input-evidence"
            />
          </div>
          <div>
            <label className="text-[10px] font-semibold text-slate-600">{vi ? "Lý do" : "Reason"}</label>
            <textarea
              className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-xs"
              rows={2}
              value={form.reason}
              onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
              data-testid="review-input-reason"
            />
          </div>
          {error && (
            <p className="text-[11px] font-medium text-rose-600" role="alert">
              {error}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <button type="button" className={BUTTON_PRIMARY} onClick={save} disabled={saving} data-testid="review-save-btn">
              {saving ? (vi ? "Đang lưu…" : "Saving…") : vi ? "Lưu hiệu chỉnh" : "Save override"}
            </button>
            <button
              type="button"
              className={BUTTON_SECONDARY}
              onClick={() => setEditing(false)}
              disabled={saving}
            >
              {vi ? "Hủy" : "Cancel"}
            </button>
            {current && (
              <button
                type="button"
                className="rounded border border-rose-300 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50"
                onClick={remove}
                disabled={saving}
                data-testid="review-delete-btn"
              >
                {vi ? "Xóa hiệu chỉnh" : "Delete override"}
              </button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

export default function ManualReviewCard({ locale }: { locale: Locale }) {
  const vi = locale === "vi";
  const [items, setItems] = useState<NeedsReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await getNeedsReview({ limit: 50 });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setLoadError(explain(err, locale));
    } finally {
      setLoading(false);
    }
  }, [locale]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs sm:p-5" data-testid="aff-manual-review-card">
      <h2 className="mb-3 text-sm font-bold text-slate-800">
        {vi ? "4. Rà soát và hiệu chỉnh thủ công" : "4. Manual review and override"}
      </h2>
      <p className="mb-3 text-xs leading-relaxed text-slate-600">
        {vi
          ? "Các vị trí tác giả chưa có đơn vị, có nguồn mâu thuẫn, hoặc chỉ mới đối chiếu (chưa xác minh). ADMIN có thể bổ sung đơn vị kèm nguồn chứng cứ và lý do; hệ thống không tự nâng mức tin cậy lên \"Đã xác minh\" chỉ vì ADMIN xác nhận."
          : "Author positions with no unit, conflicting sources, or only corroborated (not verified). ADMIN may add a unit with evidence and a reason; the system never promotes confidence to \"Verified\" just because an ADMIN confirmed it."}
      </p>
      {loadError && (
        <p className="mb-2 text-xs font-medium text-rose-600" role="alert">
          {loadError}
        </p>
      )}
      {loading && items.length === 0 ? (
        <p className="text-xs text-slate-500">{vi ? "Đang tải…" : "Loading…"}</p>
      ) : items.length === 0 ? (
        <p className="text-xs font-medium text-emerald-700" data-testid="aff-no-review-needed">
          {vi ? "Không có vị trí tác giả nào cần rà soát." : "No author positions need review."}
        </p>
      ) : (
        <>
          <p className="mb-2 text-[11px] text-slate-500">
            {vi ? `Hiển thị ${items.length}/${total}` : `Showing ${items.length} of ${total}`}
          </p>
          <ul className="space-y-2" data-testid="aff-review-list">
            {items.map((item) => (
              <ReviewRow
                key={item.publication_author_id}
                item={item}
                locale={locale}
                onSaved={refresh}
                onDeleted={refresh}
              />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
