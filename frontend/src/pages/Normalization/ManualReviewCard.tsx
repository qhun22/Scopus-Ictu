import { useCallback, useEffect, useState } from "react";
import {
  addOverride,
  getNeedsReview,
  NeedsReviewItem,
  OverrideFull,
  revokeOverride,
  updateOverride,
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
  OVERRIDE_ALREADY_REVOKED: { vi: "Hiệu chỉnh này đã bị thu hồi trước đó.", en: "This override was already revoked." },
  DUPLICATE_ACTIVE_OVERRIDE: {
    vi: "Đơn vị này đã được ghi nhận đang hoạt động cho vị trí tác giả này.",
    en: "This unit is already recorded as active for this author position.",
  },
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

function OverrideForm({
  locale,
  title,
  initial,
  onCancel,
  onSubmit,
  submitLabel,
  extraActions,
}: {
  locale: Locale;
  title: string;
  initial: EditForm;
  onCancel: () => void;
  onSubmit: (form: EditForm) => Promise<void>;
  submitLabel: string;
  extraActions?: React.ReactNode;
}) {
  const vi = locale === "vi";
  const [form, setForm] = useState<EditForm>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useSingleFlight(async () => {
    setSaving(true);
    setError(null);
    try {
      await onSubmit(form);
    } catch (err) {
      setError(explain(err, locale));
    } finally {
      setSaving(false);
    }
  });

  return (
    <div className="mt-2 space-y-2 rounded-lg border border-violet-200 bg-violet-50/40 p-2.5">
      <p className="text-[11px] font-semibold text-violet-700">{title}</p>
      <div>
        <label className="text-[10px] font-semibold text-slate-600">{vi ? "Tên đơn vị" : "Unit name"}</label>
        <input
          className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-xs"
          value={form.affiliation_text}
          onChange={(e) => setForm((f) => ({ ...f, affiliation_text: e.target.value }))}
          data-testid="override-input-text"
        />
      </div>
      <div>
        <label className="text-[10px] font-semibold text-slate-600">{vi ? "Mức tin cậy" : "Confidence"}</label>
        <select
          className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-xs"
          value={form.confidence}
          onChange={(e) => setForm((f) => ({ ...f, confidence: e.target.value as EditForm["confidence"] }))}
          data-testid="override-input-confidence"
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
          data-testid="override-input-evidence"
        />
      </div>
      <div>
        <label className="text-[10px] font-semibold text-slate-600">{vi ? "Lý do" : "Reason"}</label>
        <textarea
          className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-xs"
          rows={2}
          value={form.reason}
          onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
          data-testid="override-input-reason"
        />
      </div>
      {error && (
        <p className="text-[11px] font-medium text-rose-600" role="alert">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="button" className={BUTTON_PRIMARY} onClick={submit} disabled={saving} data-testid="override-submit-btn">
          {saving ? (vi ? "Đang lưu…" : "Saving…") : submitLabel}
        </button>
        <button type="button" className={BUTTON_SECONDARY} onClick={onCancel} disabled={saving}>
          {vi ? "Hủy" : "Cancel"}
        </button>
        {extraActions}
      </div>
    </div>
  );
}

function OverrideRow({
  override: o,
  locale,
  onChanged,
}: {
  override: OverrideFull;
  locale: Locale;
  onChanged: () => void;
}) {
  const vi = locale === "vi";
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [revokeReason, setRevokeReason] = useState("");
  const [revokeError, setRevokeError] = useState<string | null>(null);
  const [revokeSaving, setRevokeSaving] = useState(false);

  const doRevoke = useSingleFlight(async () => {
    setRevokeSaving(true);
    setRevokeError(null);
    try {
      await revokeOverride(o.id, { reason: revokeReason, expected_version: o.version });
      toast.success(vi ? "Đã thu hồi đơn vị" : "Unit revoked", "");
      setRevoking(false);
      onChanged();
    } catch (err) {
      setRevokeError(explain(err, locale));
    } finally {
      setRevokeSaving(false);
    }
  });

  const isRevoked = o.status === "REVOKED";

  return (
    <li
      className={`rounded border p-2 ${isRevoked ? "border-slate-200 bg-slate-50" : "border-violet-200 bg-violet-50/30"}`}
      data-testid="override-row"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-slate-800">
            {o.affiliation_text}{" "}
            {isRevoked ? (
              <span className="ml-1 rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-bold text-slate-600">
                {vi ? "Đã thu hồi" : "Revoked"}
              </span>
            ) : (
              <span className="ml-1 rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-bold text-violet-700">
                {vi ? "Đang hoạt động" : "Active"}
              </span>
            )}
          </p>
          <p className="text-[10px] text-slate-500">
            {vi ? "Mức tin cậy: " : "Confidence: "}
            {o.confidence === "CORROBORATED"
              ? vi
                ? "Đã đối chiếu · Chưa xác minh"
                : "Corroborated · Not verified"
              : vi
                ? "Vẫn chưa xác định"
                : "Still unresolved"}
          </p>
          <p className="text-[10px] text-slate-500">
            {vi ? "Nguồn: " : "Evidence: "}
            {o.evidence_url}
          </p>
          <p className="text-[10px] text-slate-500">
            {vi ? "Lý do: " : "Reason: "}
            {o.reason}
          </p>
        </div>
        {!isRevoked && !editing && !revoking && (
          <div className="flex gap-1.5">
            <button
              type="button"
              className={BUTTON_SECONDARY}
              onClick={() => setEditing(true)}
              data-testid="override-edit-btn"
            >
              {vi ? "Sửa" : "Edit"}
            </button>
            <button
              type="button"
              className="rounded border border-rose-300 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50"
              onClick={() => setRevoking(true)}
              data-testid="override-revoke-btn"
            >
              {vi ? "Thu hồi" : "Revoke"}
            </button>
          </div>
        )}
      </div>

      {editing && (
        <OverrideForm
          locale={locale}
          title={vi ? "Sửa đơn vị này" : "Edit this unit"}
          initial={{ affiliation_text: o.affiliation_text, confidence: o.confidence, evidence_url: o.evidence_url, reason: "" }}
          submitLabel={vi ? "Lưu thay đổi" : "Save changes"}
          onCancel={() => setEditing(false)}
          onSubmit={async (form) => {
            await updateOverride(o.id, { ...form, expected_version: o.version });
            toast.success(vi ? "Đã cập nhật đơn vị" : "Unit updated", "");
            setEditing(false);
            onChanged();
          }}
        />
      )}

      {revoking && (
        <div className="mt-2 space-y-2 rounded-lg border border-rose-200 bg-rose-50/40 p-2.5">
          <label className="text-[10px] font-semibold text-slate-600">
            {vi ? "Lý do thu hồi" : "Revoke reason"}
          </label>
          <textarea
            className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
            rows={2}
            value={revokeReason}
            onChange={(e) => setRevokeReason(e.target.value)}
            data-testid="revoke-input-reason"
          />
          {revokeError && (
            <p className="text-[11px] font-medium text-rose-600" role="alert">
              {revokeError}
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded border border-rose-300 bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-700 disabled:opacity-50"
              onClick={doRevoke}
              disabled={revokeSaving}
              data-testid="revoke-confirm-btn"
            >
              {revokeSaving ? (vi ? "Đang thu hồi…" : "Revoking…") : vi ? "Xác nhận thu hồi" : "Confirm revoke"}
            </button>
            <button
              type="button"
              className={BUTTON_SECONDARY}
              onClick={() => {
                setRevoking(false);
                setRevokeError(null);
              }}
              disabled={revokeSaving}
            >
              {vi ? "Hủy" : "Cancel"}
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

function ReviewRow({
  item,
  locale,
  onChanged,
}: {
  item: NeedsReviewItem;
  locale: Locale;
  onChanged: () => void;
}) {
  const vi = locale === "vi";
  const toast = useToast();
  const [adding, setAdding] = useState(false);

  const activeCount = item.overrides.filter((o) => o.status === "ACTIVE").length;

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
          {activeCount > 0 && (
            <span className="ml-1.5 text-[10px] font-medium text-violet-600">
              {vi ? `${activeCount} đơn vị đang hoạt động` : `${activeCount} active unit(s)`}
            </span>
          )}
        </div>
        {!adding && (
          <button
            type="button"
            className={BUTTON_SECONDARY}
            onClick={() => setAdding(true)}
            data-testid="review-add-btn"
          >
            {vi ? "Thêm đơn vị" : "Add unit"}
          </button>
        )}
      </div>

      <div className="mt-1.5 text-[10px] text-slate-500" data-testid="review-resolutions">
        {item.resolution_summaries
          .map((r) => `${r.source_system}: ${r.link_status}${r.unresolved_reason ? ` (${r.unresolved_reason})` : ""}`)
          .join(" · ")}
      </div>

      {item.overrides.length > 0 && (
        <ul className="mt-2 space-y-1.5" data-testid="override-list">
          {item.overrides.map((o) => (
            <OverrideRow key={o.id} override={o} locale={locale} onChanged={onChanged} />
          ))}
        </ul>
      )}

      {adding && (
        <OverrideForm
          locale={locale}
          title={vi ? "Thêm đơn vị mới cho vị trí này" : "Add a new unit for this position"}
          initial={EMPTY_FORM}
          submitLabel={vi ? "Thêm đơn vị" : "Add unit"}
          onCancel={() => setAdding(false)}
          onSubmit={async (form) => {
            await addOverride({ publication_author_id: item.publication_author_id, ...form });
            toast.success(
              vi ? "Đã thêm đơn vị" : "Unit added",
              vi ? "Đơn vị đã được ghi nhận có bằng chứng." : "The unit was recorded with evidence.",
            );
            setAdding(false);
            onChanged();
          }}
        />
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
    <section className="rounded-lg border border-slate-200/80 bg-white p-4 shadow-xs sm:p-5" data-testid="aff-manual-review-card">
      <h2 className="mb-3 text-sm font-bold text-slate-800">
        {vi ? "4. Rà soát và hiệu chỉnh thủ công" : "4. Manual review and override"}
      </h2>
      <p className="mb-3 text-xs leading-relaxed text-slate-600">
        {vi
          ? "Các vị trí tác giả chưa có đơn vị, có nguồn mâu thuẫn, hoặc chỉ mới đối chiếu (chưa xác minh). Một vị trí có thể có nhiều đơn vị đang hoạt động cùng lúc (ví dụ kiêm nhiệm). ADMIN có thể thêm/sửa/thu hồi từng đơn vị độc lập, kèm nguồn chứng cứ và lý do; hệ thống không tự nâng mức tin cậy lên \"Đã xác minh\" chỉ vì ADMIN xác nhận."
          : "Author positions with no unit, conflicting sources, or only corroborated (not verified). A position may have several units active at once (e.g. a dual appointment). ADMIN may add/edit/revoke each unit independently, with evidence and a reason; the system never promotes confidence to \"Verified\" just because an ADMIN confirmed it."}
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
              <ReviewRow key={item.publication_author_id} item={item} locale={locale} onChanged={refresh} />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
