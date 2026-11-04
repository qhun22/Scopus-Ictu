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
import Button, { buttonClass } from "../../components/ui/Button";
import ModalPortal from "../../components/common/ModalPortal";
import { useSingleFlight } from "../../components/common/useSingleFlight";
import { useToast } from "../../contexts/ToastContext";
import ApplyToOtherPositions from "./ApplyToOtherPositions";

type Locale = "vi" | "en";

const REASON_KIND_LABEL: Record<string, Record<Locale, string>> = {
  UNRESOLVED: { vi: "Chưa có đơn vị", en: "No unit" },
  CONFLICTING_SOURCES: { vi: "Nguồn mâu thuẫn", en: "Conflicting sources" },
  LOW_CONFIDENCE: { vi: "Chỉ đối chiếu, chưa xác minh", en: "Corroborated only, not verified" },
};

// A status that carries two facts is shown as two stacked labels, like the source labels beside it.
const REASON_KIND_PARTS: Record<string, Record<Locale, string[]>> = {
  LOW_CONFIDENCE: {
    vi: ["Chỉ đối chiếu", "Chưa xác minh"],
    en: ["Corroborated only", "Not verified"],
  },
};

// Once an ADMIN has set an active unit the position is handled: the badge says so, while the
// source-derived status stays visible in the detail view and as a tooltip.
const ADJUSTED_LABEL: Record<Locale, string> = { vi: "Đã hiệu chỉnh", en: "Adjusted" };
const ADJUSTED_STYLE = "border-emerald-400 bg-white text-emerald-700 hover:bg-emerald-50";

const reasonParts = (kind: string, locale: Locale): string[] =>
  REASON_KIND_PARTS[kind]?.[locale] ?? [REASON_KIND_LABEL[kind]?.[locale] ?? kind];

const REASON_KIND_STYLE: Record<string, string> = {
  UNRESOLVED: "border-slate-300 bg-white text-slate-600 hover:bg-slate-50",
  CONFLICTING_SOURCES: "border-red-300 bg-white text-red-700 hover:bg-red-50",
  LOW_CONFIDENCE: "border-amber-300 bg-white text-amber-700 hover:bg-amber-50",
};

// Same fixed width for the "Trạng thái rà soát" and "Nguồn đối soát" labels, so the column reads evenly.
const STATUS_BADGE_BASE =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center truncate whitespace-nowrap rounded-[5px] border px-2 text-center text-sm font-bold leading-none";
const UNIT_BADGE_BASE =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border px-2 text-center text-sm font-bold leading-none";
const UNIT_BADGE_ICTU = "border-[#3A5FC3] bg-white text-[#3A5FC3] hover:bg-blue-50";
const UNIT_BADGE_OTHER = "border-slate-400 bg-white text-slate-700 hover:bg-slate-50";

// The university itself (name or acronym), ignoring case and Vietnamese diacritics.
const isIctuUnit = (text: string): boolean => {
  const plain = text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/gi, "d")
    .toLowerCase();
  return (plain.includes("cong nghe thong tin") && plain.includes("truyen thong")) ||
    (plain.includes("information and communication technology") && plain.includes("thai nguyen")) ||
    /ictu/.test(plain);
};
const SOURCE_BADGE_BASE =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center truncate whitespace-nowrap rounded border border-slate-200 px-2 text-center text-sm leading-none";

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

const neutralDetailButtonClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-slate-700 hover:bg-slate-50 cursor-pointer";

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
    const missing = [
      !form.affiliation_text.trim() && (vi ? "Tên đơn vị" : "Unit name"),
      !form.evidence_url.trim() && (vi ? "Nguồn chứng cứ (URL)" : "Evidence source (URL)"),
      !form.reason.trim() && (vi ? "Lý do" : "Reason"),
    ].filter(Boolean);
    if (missing.length > 0) {
      setError(vi ? `Cần nhập: ${missing.join(", ")}.` : `Required: ${missing.join(", ")}.`);
      return;
    }
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
    <div className="mt-2 space-y-2.5 rounded-[5px] border border-slate-200 bg-white p-3">
      <p className="text-sm font-bold text-slate-800">{title}</p>
      <div>
        <label className="text-sm font-semibold text-slate-600">{vi ? "Tên đơn vị *" : "Unit name *"}</label>
        <input
          className="mt-1 w-full rounded-[5px] border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
          value={form.affiliation_text}
          onChange={(e) => setForm((f) => ({ ...f, affiliation_text: e.target.value }))}
          placeholder={vi ? "VD: Trường Đại học Công nghệ Thông tin và Truyền thông" : "e.g. ICTU"}
          data-testid="override-input-text"
        />
      </div>
      <div>
        <label className="text-sm font-semibold text-slate-600">{vi ? "Mức tin cậy" : "Confidence"}</label>
        <select
          className="mt-1 w-full rounded-[5px] border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
          value={form.confidence}
          onChange={(e) => setForm((f) => ({ ...f, confidence: e.target.value as EditForm["confidence"] }))}
          data-testid="override-input-confidence"
        >
          <option value="CORROBORATED">{vi ? "Đã đối chiếu · Chưa xác minh" : "Corroborated · Not verified"}</option>
          <option value="UNRESOLVED">{vi ? "Vẫn chưa xác định" : "Still unresolved"}</option>
        </select>
      </div>
      <div>
        <label className="text-sm font-semibold text-slate-600">
          {vi ? "Nguồn chứng cứ (URL) *" : "Evidence source (URL) *"}
        </label>
        <input
          className="mt-1 w-full rounded-[5px] border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
          value={form.evidence_url}
          onChange={(e) => setForm((f) => ({ ...f, evidence_url: e.target.value }))}
          placeholder="https://..."
          data-testid="override-input-evidence"
        />
      </div>
      <div>
        <label className="text-sm font-semibold text-slate-600">{vi ? "Lý do *" : "Reason *"}</label>
        <textarea
          className="mt-1 w-full rounded-[5px] border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
          rows={2}
          value={form.reason}
          onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
          placeholder={vi ? "VD: Bổ sung theo trang đầu PDF bản in bài báo..." : "Reason..."}
          data-testid="override-input-reason"
        />
      </div>
      {error && (
        <p className="text-sm font-medium text-rose-600" role="alert">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2 pt-1">
        <Button type="button" variant="primary" onClick={submit} disabled={saving} data-testid="override-submit-btn">
          {saving ? (vi ? "Đang lưu…" : "Saving…") : submitLabel}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={saving}>
          {vi ? "Hủy" : "Cancel"}
        </Button>
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
      toast.success(
        vi ? "Đã thu hồi đơn vị" : "Unit revoked",
        vi
          ? `Đơn vị "${o.affiliation_text}" không còn hoạt động. Lịch sử vẫn được giữ lại.`
          : `"${o.affiliation_text}" is no longer active. The history is kept.`,
      );
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
      className={`rounded-[5px] border p-3 ${isRevoked ? "border-slate-200 bg-slate-50" : "border-slate-200 bg-white"}`}
      data-testid="override-row"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-800">{o.affiliation_text}</span>
            {isRevoked ? (
              <span className="inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2 text-center text-sm font-bold leading-none text-slate-600 hover:bg-slate-50">
                {vi ? "Đã thu hồi" : "Revoked"}
              </span>
            ) : null}
          </div>
          <p className="text-sm text-slate-600">
            <span className="text-slate-400">{vi ? "Mức tin cậy: " : "Confidence: "}</span>
            <span className="font-semibold text-slate-700">
              {o.confidence === "CORROBORATED"
                ? vi
                  ? "Đã đối chiếu · Chưa xác minh"
                  : "Corroborated · Not verified"
                : vi
                  ? "Vẫn chưa xác định"
                  : "Still unresolved"}
            </span>
          </p>
          <p className="text-sm text-slate-600 break-all">
            <span className="text-slate-400">{vi ? "Nguồn: " : "Evidence: "}</span>
            <a
              href={o.evidence_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#3A5FC3] hover:underline"
            >
              {o.evidence_url}
            </a>
          </p>
          <p className="text-sm text-slate-600">
            <span className="text-slate-400">{vi ? "Lý do: " : "Reason: "}</span>
            {o.reason}
          </p>
        </div>
        {!isRevoked && !editing && !revoking && (
          <div className="flex gap-1.5 shrink-0">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setEditing(true)}
              data-testid="override-edit-btn"
            >
              {vi ? "Sửa" : "Edit"}
            </Button>
            <button
              type="button"
              className="rounded-[5px] border border-rose-300 px-2.5 py-1 text-sm font-semibold text-rose-700 hover:bg-rose-50 cursor-pointer transition-colors"
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
          initial={{
            affiliation_text: o.affiliation_text,
            confidence: o.confidence,
            evidence_url: o.evidence_url,
            reason: "",
          }}
          submitLabel={vi ? "Lưu thay đổi" : "Save changes"}
          onCancel={() => setEditing(false)}
          onSubmit={async (form) => {
            await updateOverride(o.id, { ...form, expected_version: o.version });
            toast.success(
              vi ? "Đã cập nhật đơn vị" : "Unit updated",
              vi
                ? `Đã lưu thay đổi cho "${form.affiliation_text}" kèm nguồn chứng cứ và lý do.`
                : `Changes to "${form.affiliation_text}" were saved with its evidence and reason.`,
            );
            setEditing(false);
            onChanged();
          }}
        />
      )}

      {revoking && (
        <div className="mt-2 space-y-2 rounded-[5px] border border-rose-200 bg-rose-50/40 p-2.5">
          <label className="text-sm font-semibold text-slate-700">
            {vi ? "Lý do thu hồi *" : "Revoke reason *"}
          </label>
          <textarea
            className="w-full rounded-[5px] border border-slate-300 bg-white px-2.5 py-1 text-sm focus:border-rose-400 focus:outline-none"
            rows={2}
            value={revokeReason}
            onChange={(e) => setRevokeReason(e.target.value)}
            placeholder={vi ? "Nhập lý do thu hồi đơn vị này..." : "Reason to revoke..."}
            data-testid="revoke-input-reason"
          />
          {revokeError && (
            <p className="text-sm font-medium text-rose-600" role="alert">
              {revokeError}
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-[5px] border border-rose-400 bg-rose-600 px-3 py-1 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-50 cursor-pointer transition-colors"
              onClick={doRevoke}
              disabled={revokeSaving || !revokeReason.trim()}
              data-testid="revoke-confirm-btn"
            >
              {revokeSaving ? (vi ? "Đang thu hồi…" : "Revoking…") : vi ? "Xác nhận thu hồi" : "Confirm revoke"}
            </button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                setRevoking(false);
                setRevokeError(null);
              }}
              disabled={revokeSaving}
            >
              {vi ? "Hủy" : "Cancel"}
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

export default function ManualReviewCard({ locale }: { locale: Locale }) {
  const vi = locale === "vi";
  const toast = useToast();

  const [items, setItems] = useState<NeedsReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Search & Filter state
  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [reasonFilter, setReasonFilter] = useState("ALL");
  const [appliedReasonFilter, setAppliedReasonFilter] = useState("ALL");
  // Scope of the list: only Scopus authors tied to an ICTU lecturer (default), or every author.
  const [scopeFilter, setScopeFilter] = useState<"ICTU" | "ALL">("ICTU");
  const [appliedScope, setAppliedScope] = useState<"ICTU" | "ALL">("ICTU");

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Selected item for modal details
  const [selectedItem, setSelectedItem] = useState<NeedsReviewItem | null>(null);
  const [modalAdding, setModalAdding] = useState(false);
  // Revoked units stay in the history; the list shows them only when asked.
  const [showRevoked, setShowRevoked] = useState(false);

  const loadItems = useCallback(
    async (q: string, filter: string, scope: "ICTU" | "ALL", targetPage: number, targetPageSize: number) => {
      setLoading(true);
      setLoadError(null);
      try {
        const res = await getNeedsReview({
          limit: targetPageSize,
          offset: (targetPage - 1) * targetPageSize,
          query: q.trim() || undefined,
          reason_kind: filter !== "ALL" ? filter : undefined,
          ictu_only: scope === "ICTU",
        });
        setItems(res.items);
        setTotal(res.total);
        setSelectedItem((prev) => {
          if (!prev) return null;
          return res.items.find((i) => i.publication_author_id === prev.publication_author_id) ?? prev;
        });
      } catch (err) {
        setLoadError(explain(err, locale));
      } finally {
        setLoading(false);
      }
    },
    [locale],
  );

  useEffect(() => {
    void loadItems(appliedSearch, appliedReasonFilter, appliedScope, page, pageSize);
  }, [loadItems, appliedSearch, appliedReasonFilter, appliedScope, page, pageSize]);

  const refresh = useCallback(async () => {
    await loadItems(appliedSearch, appliedReasonFilter, appliedScope, page, pageSize);
  }, [loadItems, appliedSearch, appliedReasonFilter, appliedScope, page, pageSize]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handleApplySearch = () => {
    setAppliedSearch(searchInput.trim());
    setAppliedReasonFilter(reasonFilter);
    setAppliedScope(scopeFilter);
    setPage(1);
  };

  const handleResetSearch = () => {
    setSearchInput("");
    setAppliedSearch("");
    setReasonFilter("ALL");
    setAppliedReasonFilter("ALL");
    setScopeFilter("ICTU");
    setAppliedScope("ICTU");
    setPage(1);
  };

  const isApplyDisabled =
    searchInput.trim() === appliedSearch.trim() &&
    reasonFilter === appliedReasonFilter &&
    scopeFilter === appliedScope;
  const isResetDisabled =
    !searchInput.trim() &&
    !appliedSearch &&
    reasonFilter === "ALL" &&
    appliedReasonFilter === "ALL" &&
    scopeFilter === "ICTU" &&
    appliedScope === "ICTU";

  return (
    <section className="space-y-4" data-testid="aff-manual-review-card">
      {/* Title & Description */}
      <div>
        <h2 className="text-base font-bold text-slate-800 uppercase tracking-wide">
          {vi ? "5. Rà soát và hiệu chỉnh thủ công" : "5. Manual review and override"}
        </h2>
        <p className="mt-1 text-sm leading-relaxed text-slate-600 max-w-5xl">
          {vi
            ? "Các vị trí tác giả chưa có đơn vị, có nguồn mâu thuẫn, hoặc chỉ mới đối chiếu (chưa xác minh). Một vị trí có thể có nhiều đơn vị đang hoạt động cùng lúc (ví dụ kiêm nhiệm). ADMIN có thể thêm/sửa/thu hồi từng đơn vị độc lập, kèm nguồn chứng cứ và lý do; hệ thống không tự nâng mức tin cậy lên \"Đã xác minh\" chỉ vì ADMIN xác nhận."
            : "Author positions with no unit, conflicting sources, or only corroborated (not verified). A position may have several units active at once (e.g. a dual appointment). ADMIN may add/edit/revoke each unit independently, with evidence and a reason; the system never promotes confidence to \"Verified\" just because an ADMIN confirmed it."}
        </p>
      </div>

      {/* Toolbar: Search input, Reason Filter, Apply & Reset buttons */}
      <div className="flex flex-col gap-3 rounded-[5px] border border-slate-200/80 bg-white p-3.5 shadow-xs sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            aria-label={vi ? "Tìm kiếm" : "Search"}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleApplySearch();
              }
            }}
            placeholder={
              vi
                ? "Tìm theo tên tác giả, Scopus ID, EID hoặc tiêu đề bài báo..."
                : "Search by author name, Scopus ID, EID or title..."
            }
            className="h-control w-full rounded-control border border-line bg-slate-50 pl-9 pr-3 text-[13px] text-ink placeholder:text-ink-faint focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {/* Phạm vi tác giả */}
          <select
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value as "ICTU" | "ALL")}
            aria-label={vi ? "Phạm vi tác giả" : "Author scope"}
            className="h-control rounded-control border border-line bg-slate-50 px-3 text-[13px] text-ink focus:border-brand focus:bg-white focus:outline-none cursor-pointer"
          >
            <option value="ICTU">{vi ? "Tác giả liên quan ICTU" : "ICTU-related authors"}</option>
            <option value="ALL">{vi ? "Tất cả tác giả" : "All authors"}</option>
          </select>

          {/* Lọc theo lý do */}
          <select
            value={reasonFilter}
            onChange={(e) => setReasonFilter(e.target.value)}
            className="h-control rounded-control border border-line bg-slate-50 px-3 text-[13px] text-ink focus:border-brand focus:bg-white focus:outline-none cursor-pointer"
          >
            <option value="ALL">{vi ? "Tất cả trạng thái" : "All statuses"}</option>
            <option value="UNRESOLVED">{vi ? "Chưa có đơn vị" : "No unit"}</option>
            <option value="CONFLICTING_SOURCES">{vi ? "Nguồn mâu thuẫn" : "Conflicting sources"}</option>
            <option value="LOW_CONFIDENCE">{vi ? "Chỉ đối chiếu, chưa xác minh" : "Corroborated only"}</option>
            <option value="ADJUSTED">{vi ? "Đã hiệu chỉnh" : "Adjusted"}</option>
          </select>

          {/* Nút Áp dụng */}
          <button
            type="button"
            disabled={isApplyDisabled}
            onClick={handleApplySearch}
            className={buttonClass("primary")}
          >
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="truncate">{vi ? "Áp dụng" : "Apply"}</span>
          </button>

          {/* Nút Đặt lại */}
          <button
            type="button"
            onClick={handleResetSearch}
            disabled={isResetDisabled}
            className={buttonClass("secondary")}
          >
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span className="truncate">{vi ? "Đặt lại" : "Reset"}</span>
          </button>
        </div>
      </div>

      {loadError && (
        <div className="rounded-[5px] border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {loadError}
        </div>
      )}

      {/* Main Table */}
      <div className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-600">
                  {vi ? "Tác giả Scopus" : "Scopus Author"}
                </th>
                <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-600">
                  {vi ? "Bài báo / EID" : "Publication / EID"}
                </th>
                <th className="whitespace-nowrap px-4 py-3 text-center font-semibold text-slate-600">
                  {vi ? "Trạng thái rà soát" : "Review Status"}
                </th>
                <th className="whitespace-nowrap px-4 py-3 text-center font-semibold text-slate-600">
                  {vi ? "Trực thuộc" : "Affiliated Unit"}
                </th>
                <th className="w-44 whitespace-nowrap border-l border-slate-200/80 px-4 py-3 text-center font-semibold text-slate-600">
                  {vi ? "Thao tác" : "Actions"}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-slate-400">
                    <div className="flex items-center justify-center gap-2">
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                      <span className="text-sm font-medium">
                        {vi ? "Đang tải dữ liệu…" : "Loading data…"}
                      </span>
                    </div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-1.5">
                      <div className="flex h-10 w-10 items-center justify-center rounded-[5px] bg-slate-100/80 border border-slate-200/80 text-slate-400 mb-1">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <span className="text-sm font-bold text-slate-700">
                        {vi ? "Không có dữ liệu cần rà soát" : "No review items found"}
                      </span>
                      <span className="text-sm text-slate-400">
                        {vi ? "Tất cả vị trí tác giả đều đã được xác minh hoặc không khớp tiêu chí tìm kiếm." : "All author positions are either verified or do not match current filters."}
                      </span>
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const activeOverrides = item.overrides.filter((o) => o.status === "ACTIVE");
                  return (
                    <tr key={item.publication_author_id} className="hover:bg-slate-50/50 transition-colors" data-testid="review-item">
                      {/* Tác giả */}
                      <td className="px-4 py-3">
                        <p className="font-semibold text-slate-800 text-sm line-clamp-1" title={item.preferred_name}>
                          {item.preferred_name}
                        </p>
                        <p className="text-sm text-slate-500 mt-0.5 whitespace-nowrap">
                          {vi ? "Vị trí" : "Order"} <span className="font-semibold text-slate-700">{item.author_order}</span>
                        </p>
                        <p className="text-sm text-slate-500 whitespace-nowrap">
                          Scopus ID: <span className="font-semibold text-slate-600">{item.scopus_id}</span>
                        </p>
                      </td>

                      {/* Bài báo / EID */}
                      <td className="px-4 py-3 max-w-[280px]">
                        <p className="font-medium text-slate-700 text-sm line-clamp-2 leading-relaxed" title={item.title}>
                          {item.title}
                        </p>
                        <p className="text-sm text-slate-400 mt-0.5">
                          EID: {item.eid}
                        </p>
                      </td>

                      {/* Trạng thái rà soát */}
                      <td className="px-4 py-3 text-center whitespace-nowrap">
                        <div className="flex flex-col items-center gap-1">
                          {(activeOverrides.length > 0 ? [ADJUSTED_LABEL[locale]] : reasonParts(item.reason_kind, locale)).map((part) => (
                            <span
                              key={part}
                              className={`${STATUS_BADGE_BASE} ${activeOverrides.length > 0 ? ADJUSTED_STYLE : REASON_KIND_STYLE[item.reason_kind]}`}
                              title={`${vi ? "Trạng thái từ nguồn" : "Source status"}: ${REASON_KIND_LABEL[item.reason_kind]?.[locale] ?? item.reason_kind}`}
                            >
                              {part}
                            </span>
                          ))}
                        </div>
                      </td>

                      {/* Trực thuộc */}
                      <td className="px-4 py-3 text-center">
                        {activeOverrides.length > 0 ? (
                          <span
                            className={`${UNIT_BADGE_BASE} ${activeOverrides.some((o) => isIctuUnit(o.affiliation_text)) ? UNIT_BADGE_ICTU : UNIT_BADGE_OTHER}`}
                            title={activeOverrides.map((o) => o.affiliation_text).join("; ")}
                          >
                            {activeOverrides.length} {vi ? "đơn vị" : "unit(s)"}
                          </span>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>

                      {/* Thao tác */}
                      <td className="w-44 border-l border-slate-100 px-4 py-3 text-center">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedItem(item);
                            setModalAdding(false);
                          }}
                          className={neutralDetailButtonClassName}
                        >
                          {vi ? "Chi tiết" : "Details"}
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer info & Pagination Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-2.5 text-sm text-slate-500">
          <div className="flex items-center gap-3">
            <span>
              {vi ? "Hiển thị" : "Showing"} <strong>{items.length}</strong> {vi ? "trong" : "of"}{" "}
              <strong>{total}</strong> {vi ? "vị trí cần rà soát" : "positions to review"}
            </span>

            {/* Page Size Selector */}
            <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
              <span className="text-slate-500">{vi ? "Hiển thị:" : "Show:"}</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  const newSize = Number(e.target.value);
                  setPageSize(newSize);
                  setPage(1);
                }}
                className="h-6.5 rounded-[5px] border border-slate-200 bg-white px-1.5 text-sm font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer"
              >
                <option value={10}>10 / {vi ? "trang" : "page"}</option>
                <option value={20}>20 / {vi ? "trang" : "page"}</option>
                <option value={50}>50 / {vi ? "trang" : "page"}</option>
                <option value={100}>100 / {vi ? "trang" : "page"}</option>
              </select>
            </div>
          </div>

          <nav aria-label="Pagination" className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              disabled={page <= 1}
              className={buttonClass("secondary", "sm")}
            >
              {vi ? "Trang trước" : "Previous"}
            </button>
            <span className="px-0.5 text-slate-400">{vi ? "Trang" : "Page"}</span>
            <input
              type="number"
              aria-label={vi ? "Đến trang" : "Go to page"}
              min={1}
              max={totalPages}
              value={page}
              onChange={(e) => {
                const val = Math.max(1, Math.min(totalPages, parseInt(e.target.value, 10) || 1));
                setPage(val);
              }}
              className="h-8 w-14 rounded-[5px] border border-slate-200 bg-white px-2 text-center text-sm font-bold text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
            <span className="text-slate-400">
              / <strong className="text-slate-600">{totalPages}</strong>
            </span>
            <button
              type="button"
              onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
              disabled={page >= totalPages}
              className={buttonClass("secondary", "sm")}
            >
              {vi ? "Trang sau" : "Next"}
            </button>
          </nav>
        </div>
      </div>

      {/* Modal chi tiết & hiệu chỉnh đơn vị tác giả */}
      {selectedItem && (
        <ModalPortal>
          <div className="fixed inset-x-0 top-16 bottom-0 md:left-[var(--app-sidebar-w)] z-50 flex items-center justify-center bg-black/40 p-4 modal-backdrop-in transition-[left] duration-200 ease-out">
            <div className="w-full max-w-3xl max-h-[90vh] flex flex-col rounded-card border border-slate-200 bg-white shadow-2xl overflow-hidden modal-panel-in">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 shrink-0">
                <div>
                  <h2 className="text-base font-bold text-slate-800">
                    {vi ? "Chi tiết rà soát & Hiệu chỉnh đơn vị tác giả" : "Author Unit Review & Override"}
                  </h2>
                  <p className="text-sm text-slate-500 mt-0.5">
                    {selectedItem.preferred_name} · {vi ? "Vị trí" : "Position"} {selectedItem.author_order} (Scopus ID: {selectedItem.scopus_id})
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedItem(null);
                    setModalAdding(false);
                  }}
                  className="inline-flex items-center justify-center rounded-[5px] p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Scrollable Content */}
              <div className="overflow-y-auto p-5 space-y-4 flex-1">
                {/* Paper Context Card */}
                <div className="rounded-[5px] border border-slate-200/80 bg-slate-50/60 p-3.5 space-y-2">
                  <span className="block text-sm font-semibold text-slate-700">
                    EID: <span className="font-bold text-slate-900">{selectedItem.eid}</span>
                  </span>
                  <p className="text-sm font-medium text-slate-800 leading-snug">{selectedItem.title}</p>
                  <div className="flex flex-col items-start gap-1 text-sm text-slate-500 pt-1.5 border-t border-slate-200/60">
                    <span className="font-semibold">{vi ? "Trạng thái rà soát:" : "Review status:"}</span>
                    <div className="flex flex-col items-start gap-2">
                      <div className="flex flex-col items-start gap-1">
                        <span className="text-sm text-slate-500">
                          {selectedItem.overrides.some((o) => o.status === "ACTIVE")
                            ? vi ? "Trạng thái cũ" : "Previous status"
                            : vi ? "Trạng thái hiện tại" : "Current status"}
                        </span>
                        <div className="flex flex-wrap items-center gap-1">
                          {reasonParts(selectedItem.reason_kind, locale).map((part) => (
                            <span key={part} className={`${STATUS_BADGE_BASE} ${REASON_KIND_STYLE[selectedItem.reason_kind]}`}>
                              {part}
                            </span>
                          ))}
                        </div>
                      </div>
                      {selectedItem.overrides.some((o) => o.status === "ACTIVE") && (
                        <div className="flex flex-col items-start gap-1">
                          <span className="text-sm text-slate-500">{vi ? "Trạng thái mới" : "New status"}</span>
                          <span className={`${STATUS_BADGE_BASE} ${ADJUSTED_STYLE}`}>{ADJUSTED_LABEL[locale]}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  {selectedItem.resolution_summaries.some((r) => r.link_status !== "UNRESOLVED") && (
                  <div className="flex flex-col items-start gap-1 text-sm text-slate-500 pt-1.5 border-t border-slate-200/60">
                    <span className="font-semibold">{vi ? "Nguồn đối soát:" : "Reconciled sources:"}</span>
                    <div className="flex flex-col items-start gap-2">
                      {selectedItem.resolution_summaries.filter((r) => r.link_status !== "UNRESOLVED").map((r, idx) => (
                        <div key={idx} className="flex flex-col items-start gap-1">
                          <span
                            className={`${SOURCE_BADGE_BASE} bg-white text-slate-600`}
                            title={`${r.source_system}: ${r.link_status}${r.unresolved_reason ? ` (${r.unresolved_reason})` : ""}`}
                          >
                            {r.source_system}: <strong className="text-slate-800">{r.link_status}</strong>
                            {r.unresolved_reason ? ` (${r.unresolved_reason})` : ""}
                          </span>
                          {(r.raw_affiliations ?? []).length > 0 ? (
                            <ul className="ml-1 list-disc space-y-0.5 pl-4 text-sm text-slate-700">
                              {(r.raw_affiliations ?? []).map((text) => (
                                <li key={text}>{text}</li>
                              ))}
                            </ul>
                          ) : (
                            <span className="ml-1 text-sm text-slate-400">
                              {vi ? "Nguồn này không ghi đơn vị." : "This source reports no affiliation."}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                  )}
                </div>

                {/* Overrides List & Add Button */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wide">
                      {vi ? "Danh sách đơn vị đã ghi nhận" : "Recorded units list"}
                      {selectedItem.overrides.some((o) => o.status === "ACTIVE") && (
                        <span className="ml-1.5 font-normal text-slate-400">
                          ({selectedItem.overrides.filter((o) => o.status === "ACTIVE").length})
                        </span>
                      )}
                    </h3>
                    {!modalAdding && (
                      <button
                        type="button"
                        onClick={() => setModalAdding(true)}
                        className="inline-flex h-badge w-32 shrink-0 cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-[5px] border border-[#3A5FC3] bg-white px-2 text-center text-sm font-bold leading-none text-[#3A5FC3] hover:bg-blue-50"
                        data-testid="review-add-btn"
                      >
                        <span>{vi ? "Thêm đơn vị" : "Add unit"}</span>
                      </button>
                    )}
                  </div>

                  {selectedItem.overrides.filter((o) => showRevoked || o.status === "ACTIVE").length === 0 && !modalAdding ? (
                    <div className="rounded-[5px] border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">
                      {vi
                        ? "Chưa có đơn vị nào được ghi nhận thủ công cho vị trí tác giả này."
                        : "No manual units recorded for this author position yet."}
                    </div>
                  ) : (
                    <ul className="space-y-2" data-testid="override-list">
                      {selectedItem.overrides
                        .filter((o) => showRevoked || o.status === "ACTIVE")
                        .map((o) => (
                        <OverrideRow
                          key={o.id}
                          override={o}
                          locale={locale}
                          onChanged={async () => {
                            await refresh();
                          }}
                        />
                      ))}
                    </ul>
                  )}
                  {selectedItem.overrides.some((o) => o.status === "REVOKED") && (
                    <button
                      type="button"
                      onClick={() => setShowRevoked((v) => !v)}
                      className="mt-2 text-sm font-semibold text-slate-500 underline underline-offset-2 hover:text-slate-700"
                      data-testid="toggle-revoked-units"
                    >
                      {showRevoked
                        ? vi ? "Ẩn các đơn vị đã thu hồi" : "Hide revoked units"
                        : vi
                          ? `Hiện ${selectedItem.overrides.filter((o) => o.status === "REVOKED").length} đơn vị đã thu hồi`
                          : `Show ${selectedItem.overrides.filter((o) => o.status === "REVOKED").length} revoked unit(s)`}
                    </button>
                  )}
                </div>

                {selectedItem.overrides.some((o) => o.status === "ACTIVE") && (
                  <ApplyToOtherPositions item={selectedItem} locale={locale} onDone={refresh} />
                )}

                {/* Form thêm đơn vị mới */}
                {modalAdding && (
                  <OverrideForm
                    locale={locale}
                    title={vi ? "Thêm đơn vị mới cho vị trí này" : "Add a new unit for this position"}
                    initial={EMPTY_FORM}
                    submitLabel={vi ? "Thêm đơn vị" : "Add unit"}
                    onCancel={() => setModalAdding(false)}
                    onSubmit={async (form) => {
                      await addOverride({
                        publication_author_id: selectedItem.publication_author_id,
                        ...form,
                      });
                      toast.success(
                        vi ? "Đã thêm đơn vị" : "Unit added",
                        vi ? "Đơn vị đã được ghi nhận có bằng chứng." : "The unit was recorded with evidence.",
                      );
                      setModalAdding(false);
                      await refresh();
                    }}
                  />
                )}
              </div>

              {/* Modal Footer */}
              <div className="border-t border-slate-100 bg-slate-50/50 px-5 py-3 flex justify-end shrink-0">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setSelectedItem(null);
                    setModalAdding(false);
                  }}
                >
                  {vi ? "Đóng" : "Close"}
                </Button>
              </div>
            </div>
          </div>
        </ModalPortal>
      )}
    </section>
  );
}
