import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "../../api/client";
import { getMergeGuide, getReviewCandidates, groupAcceptLecturerCandidates, MergeGuideResponse } from "../../api/reviews";
import Button from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";
import { ReviewQueueItem } from "../../types/review";

type Locale = "vi" | "en";

interface Group {
  lecturerId: string;
  lecturerName: string;
  members: ReviewQueueItem[];
}

const MAX_PAGES = 5;

/** What the ICTU merge guide says about ONE lecturer; a hint that pre-fills the form, nothing more. */
interface GuideHint {
  sourceUrl: string | null;
  retrievedAt: string | null;
  entry: { scopusIds: string[]; primaryScopusId: string | null } | null;
}

const errorText = (error: unknown, vi: boolean): string => {
  if (error instanceof ApiError) return error.detail || error.message;
  return vi ? "Đã xảy ra lỗi không xác định." : "An unknown error occurred.";
};

/** Strongest first: publication-supported, then more evidence; stable for ties. */
function suggestedMember(members: ReviewQueueItem[]): ReviewQueueItem {
  return [...members].sort(
    (a, b) =>
      b.publication_support_count - a.publication_support_count ||
      b.publication_evidence_count - a.publication_evidence_count,
  )[0];
}

function GroupCard({ group, locale, hint, onDone }: { group: Group; locale: Locale; hint: GuideHint | null; onDone: () => void }) {
  const vi = locale === "vi";
  const toast = useToast();
  const listed = (m: ReviewQueueItem) => hint?.entry?.scopusIds.includes(m.scopus_author.scopus_id) ?? false;
  // With a guide entry, tick the IDs ICTU lists (when at least two); otherwise tick everything.
  const guided = group.members.filter(listed);
  const useGuide = guided.length >= 2;
  const [included, setIncluded] = useState<Record<string, boolean>>(
    () => Object.fromEntries(group.members.map((m) => [m.candidate_id, useGuide ? listed(m) : true])),
  );
  const [primaryId, setPrimaryId] = useState<string>(() => {
    const fromGuide = useGuide
      ? group.members.find((m) => m.scopus_author.scopus_id === hint?.entry?.primaryScopusId && listed(m))
      : undefined;
    return (fromGuide ?? suggestedMember(group.members)).candidate_id;
  });
  const [reason, setReason] = useState(() =>
    useGuide
      ? vi
        ? `Theo danh sách gộp tài khoản Scopus của repository.ictu.edu.vn${hint?.retrievedAt ? ` (lấy ngày ${hint.retrievedAt})` : ""}.`
        : `Per the Scopus account merge guide of repository.ictu.edu.vn${hint?.retrievedAt ? ` (retrieved ${hint.retrievedAt})` : ""}.`
      : "",
  );
  const [submitting, setSubmitting] = useState(false);

  const chosen = group.members.filter((m) => included[m.candidate_id]);
  const primaryValid = chosen.some((m) => m.candidate_id === primaryId);
  // An ID proposed for several lecturers is ambiguous: it cannot be decided as part of a group.
  const sharedChosen = chosen.filter((m) => m.is_shared_scopus_author);
  const canSubmit = chosen.length >= 2 && sharedChosen.length === 0 && reason.trim().length > 0 && !submitting;

  const submit = async () => {
    setSubmitting(true);
    try {
      await groupAcceptLecturerCandidates(group.lecturerId, {
        items: chosen.map((m) => ({
          candidate_id: m.candidate_id,
          observation_id: m.current_observation_id,
          candidate_version: m.candidate_version,
        })),
        reason: reason.trim(),
        primary_candidate_id: primaryValid ? primaryId : null,
      });
      toast.success(
        vi ? "Đã chấp nhận cả nhóm" : "Group accepted",
        vi
          ? `${chosen.length} ID của ${group.lecturerName} đã được duyệt cùng lúc.`
          : `${chosen.length} IDs of ${group.lecturerName} were approved together.`,
      );
      onDone();
    } catch (e) {
      toast.error(vi ? "Không chấp nhận được nhóm" : "Could not accept the group", errorText(e, vi));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <article className="rounded-[5px] border border-slate-200 bg-white p-4" data-testid="review-group-card">
      <h3 className="text-sm font-bold text-slate-800">{group.lecturerName}</h3>
      <p className="mt-0.5 text-xs text-slate-500">
        {vi ? `${group.members.length} ID Scopus được đề xuất cho giảng viên này.` : `${group.members.length} Scopus IDs are proposed for this lecturer.`}
      </p>
      {hint && (
        <p
          className={`mt-1.5 inline-flex flex-wrap items-center gap-x-2 gap-y-1 rounded-[5px] border bg-white px-2.5 py-1 text-[11px] font-semibold ${
            hint.entry ? "border-emerald-300 text-emerald-700" : "border-amber-300 text-amber-700"
          }`}
          data-testid="merge-guide-hint"
        >
          {hint.entry
            ? vi ? "Có trong danh sách gộp của ICTU" : "Listed in the ICTU merge guide"
            : vi ? "Không có trong danh sách ICTU" : "Not in the ICTU list"}
          {hint.entry && (() => {
            const missing = hint.entry.scopusIds.filter((id) => !group.members.some((m) => m.scopus_author.scopus_id === id));
            return missing.length > 0 ? (
              <span className="font-normal text-slate-600">
                {vi ? "ICTU liệt kê thêm (chưa có trong đề xuất): " : "ICTU also lists (not proposed here): "}
                <span className="font-mono">{missing.join(", ")}</span>
              </span>
            ) : null;
          })()}
        </p>
      )}
      <ul className="mt-3 space-y-2">
        {group.members.map((m) => (
          <li key={m.candidate_id} className="flex flex-wrap items-center gap-3 rounded-[5px] border border-slate-100 bg-slate-50/60 px-3 py-2 text-xs">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!included[m.candidate_id]}
                onChange={(e) => setIncluded((prev) => ({ ...prev, [m.candidate_id]: e.target.checked }))}
              />
              <span className="font-mono font-semibold text-slate-800">{m.scopus_author.scopus_id}</span>
            </label>
            <span className="text-slate-600">{m.scopus_author.preferred_name}</span>
            <span className="text-slate-500">
              {m.publication_support_count} {vi ? "công bố hỗ trợ" : "supporting publications"} · {m.name_evidence_count} {vi ? "bằng chứng tên" : "name evidence"}
            </span>
            {hint?.entry && !listed(m) && (
              <span className="inline-flex h-badge items-center rounded-[5px] border border-amber-300 bg-white px-2 text-[10px] font-bold text-amber-700">
                {vi ? "Không có trong danh sách ICTU" : "Not in the ICTU list"}
              </span>
            )}
            {m.is_shared_scopus_author && (
              <span className="inline-flex h-badge items-center rounded-[5px] border border-rose-200 bg-rose-50 px-2 text-[10px] font-bold text-rose-700">
                {vi ? "ID dùng chung" : "Shared ID"}
              </span>
            )}
            <label className="ml-auto flex items-center gap-1.5 text-slate-600">
              <input
                type="radio"
                name={`primary-${group.lecturerId}`}
                checked={primaryId === m.candidate_id}
                disabled={!included[m.candidate_id]}
                onChange={() => setPrimaryId(m.candidate_id)}
              />
              {vi ? "ID chính" : "Main ID"}
            </label>
          </li>
        ))}
      </ul>
      <label htmlFor={`group-reason-${group.lecturerId}`} className="mt-3 mb-1 block text-xs font-semibold text-slate-700">
        {vi ? "Lý do chung cho cả nhóm" : "One shared reason for the group"} <span className="text-rose-600">*</span>
      </label>
      <textarea
        id={`group-reason-${group.lecturerId}`}
        value={reason}
        rows={2}
        maxLength={4000}
        onChange={(e) => setReason(e.target.value)}
        placeholder={vi ? "Ví dụ: cùng một người, đổi tên hoặc công bố ở nhiều cơ sở…" : "e.g. the same person, name change or several affiliations…"}
        className="w-full resize-none rounded-[5px] border border-slate-200 px-2.5 py-2 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
      />
      {sharedChosen.length > 0 && (
        <p className="mt-2 rounded-[5px] border border-amber-300 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-amber-700" role="alert">
          {vi
            ? "Cần duyệt riêng từng người: nhóm có ID dùng chung với giảng viên khác. Bỏ tick ID dùng chung hoặc duyệt riêng ở danh sách bên dưới."
            : "Review each person individually: the group has an ID shared with another lecturer. Untick the shared ID or review it in the list below."}
        </p>
      )}
      <div className="mt-2 flex items-center justify-between gap-3">
        <p className="text-[11px] text-slate-500">
          {vi
            ? "Tất cả ID đã chọn được chấp nhận trong một giao dịch: lỗi ở bất kỳ ID nào thì không ID nào được ghi."
            : "All selected IDs are accepted in one transaction: if any fails, none is saved."}
        </p>
        <Button size="sm" onClick={() => void submit()} disabled={!canSubmit} loading={submitting}>
          {vi ? `Chấp nhận ${chosen.length} ID` : `Accept ${chosen.length} IDs`}
        </Button>
      </div>
    </article>
  );
}

/**
 * Lecturers with two or more pending Scopus IDs, grouped so a reviewer can decide the whole
 * group at once. Each member still passes every single-decision rule on the server.
 */
export default function GroupReviewPanel({ locale, refreshKey, onChanged }: { locale: Locale; refreshKey: number; onChanged: () => void }) {
  const vi = locale === "vi";
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [guide, setGuide] = useState<MergeGuideResponse | null>(null);
  const [guideReady, setGuideReady] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const all: ReviewQueueItem[] = [];
      for (let page = 1; page <= MAX_PAGES; page += 1) {
        const response = await getReviewCandidates({ status: "PENDING", ambiguity: "ambiguous", page, page_size: 100 });
        all.push(...response.items);
        if (all.length >= response.total || response.items.length === 0) break;
      }
      setItems(all);
    } catch (e) {
      setItems([]);
      setError(errorText(e, vi));
    } finally {
      setLoading(false);
    }
  }, [vi]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const groups = useMemo<Group[]>(() => {
    const byLecturer = new Map<string, Group>();
    for (const item of items) {
      const existing = byLecturer.get(item.lecturer.id);
      if (existing) existing.members.push(item);
      else byLecturer.set(item.lecturer.id, { lecturerId: item.lecturer.id, lecturerName: item.lecturer.full_name, members: [item] });
    }
    return [...byLecturer.values()].filter((g) => g.members.length >= 2).sort((a, b) => a.lecturerName.localeCompare(b.lecturerName, "vi"));
  }, [items]);

  const lecturerKey = groups.map((g) => g.lecturerId).join(",");
  useEffect(() => {
    let cancelled = false;
    setGuideReady(false);
    if (!lecturerKey) {
      setGuide(null);
      return;
    }
    getMergeGuide(lecturerKey.split(","))
      .then((res) => !cancelled && setGuide(res))
      .catch(() => !cancelled && setGuide(null)) // the guide is optional: no hint on any failure
      .finally(() => !cancelled && setGuideReady(true));
    return () => {
      cancelled = true;
    };
  }, [lecturerKey]);

  const hintFor = (lecturerId: string): GuideHint | null => {
    if (!guide?.available) return null;
    const found = guide.items.find((i) => i.lecturer_id === lecturerId);
    return {
      sourceUrl: guide.source_url,
      retrievedAt: guide.retrieved_at,
      entry: found ? { scopusIds: found.scopus_ids, primaryScopusId: found.primary_scopus_id } : null,
    };
  };

  if (loading && items.length === 0) return null;
  if (error) return <p className="mb-3 text-xs text-rose-600">{error}</p>;
  if (groups.length === 0) return null;

  return (
    <section className="mb-4 rounded-[5px] border border-[#cfd9f3] bg-[#f6f8fe] p-4" data-testid="review-group-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-slate-800">
            {vi ? "Duyệt theo nhóm giảng viên" : "Review by lecturer group"}{" "}
            <span className="ml-1 rounded-[5px] bg-white px-2 py-0.5 text-xs font-semibold text-[#2f4ea6]">{groups.length}</span>
          </h2>
          <p className="mt-0.5 text-xs text-slate-600">
            {vi
              ? `${groups.length} giảng viên có từ 2 ID Scopus được đề xuất. Duyệt cả nhóm một lần và chọn ID chính.`
              : `${groups.length} lecturers have two or more proposed Scopus IDs. Review the whole group at once and pick the main ID.`}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => setOpen((v) => !v)} data-testid="review-group-toggle">
          {open ? (vi ? "Thu gọn" : "Collapse") : (vi ? "Xem các nhóm" : "Show groups")}
        </Button>
      </div>
      {open && (
        <div className="mt-3 max-h-[520px] space-y-3 overflow-y-auto pr-1">
          {!guideReady && <p className="text-xs text-slate-500">{vi ? "Đang tải…" : "Loading…"}</p>}
          {guideReady && groups.map((group) => (
            <GroupCard key={group.lecturerId} group={group} locale={locale} hint={hintFor(group.lecturerId)} onDone={() => { onChanged(); void load(); }} />
          ))}
        </div>
      )}
    </section>
  );
}
