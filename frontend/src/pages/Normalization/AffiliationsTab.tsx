import { useCallback, useEffect, useRef, useState } from "react";
import {
  AffiliationOverview,
  AffiliationPreview,
  applyAffiliations,
  cancelOnlineEnrichment,
  EnrichmentJob,
  getAffiliationOverview,
  getOnlineEnrichment,
  previewAffiliations,
  startOnlineEnrichment,
} from "../../api/affiliations";
import { ApiError } from "../../api/client";
import { BUTTON_PRIMARY, BUTTON_SECONDARY } from "../../components/common/buttonStyles";
import { useSingleFlight } from "../../components/common/useSingleFlight";
import { useToast } from "../../contexts/ToastContext";
import ManualReviewCard from "./ManualReviewCard";

type Locale = "vi" | "en";

const SOURCE_LABEL: Record<string, string> = { openalex: "OpenAlex", crossref: "Crossref" };
const STATUS_LABEL: Record<string, Record<Locale, string>> = {
  VERIFIED: { vi: "Đã xác minh định danh", en: "Identity verified" },
  CORROBORATED: { vi: "Đã đối chiếu · Chưa xác minh", en: "Cross-checked · Not verified" },
  UNRESOLVED: { vi: "Chưa xác định", en: "Unresolved" },
};
const OUTCOME_LABEL: Record<string, Record<Locale, string>> = {
  inserted: { vi: "sẽ ghi mới", en: "to insert" },
  reused: { vi: "đã có sẵn", en: "already stored" },
  skipped: { vi: "bỏ qua", en: "skipped" },
  conflicted: { vi: "xung đột (giữ lại)", en: "conflicted (withheld)" },
};
const BLOCKED_LABEL: Record<string, Record<Locale, string>> = {
  SOURCE_DIR_NOT_CONFIGURED: {
    vi: "Máy chủ chưa được cấu hình thư mục nguồn đơn vị (AFFILIATION_SOURCE_DIR).",
    en: "The server has no affiliation source directory configured (AFFILIATION_SOURCE_DIR).",
  },
  SOURCE_DIR_NOT_FOUND: { vi: "Thư mục nguồn đã cấu hình không tồn tại.", en: "The configured source directory does not exist." },
  BUNDLE_UNREADABLE: { vi: "Không đọc được bộ nguồn (tệp hỏng).", en: "The source bundle could not be read." },
  NO_PUBLICATIONS: {
    vi: "Chưa có công bố nào. Hãy nhập CSV Scopus và chuẩn hóa trước.",
    en: "No publications yet. Import and normalize a Scopus CSV first.",
  },
  NOTHING_TO_APPLY: {
    vi: "Không có gì mới để ghi: kết quả này đã được áp dụng trước đó.",
    en: "Nothing new to write: this result has already been applied.",
  },
  SOURCE_MISMATCH: {
    vi: "Bộ nguồn mâu thuẫn với dữ liệu tính lại từ metadata gốc (có thể cũ hoặc bị sửa). Không được áp dụng.",
    en: "The source bundle disagrees with the recomputation from raw metadata (stale or tampered). Cannot be applied.",
  },
};
const ERROR_LABEL: Record<string, Record<Locale, string>> = {
  PREVIEW_STALE: {
    vi: "Dữ liệu hoặc nguồn đã thay đổi kể từ lần xem trước. Hãy xem trước lại.",
    en: "Data or source changed since the preview. Preview again.",
  },
  AFFILIATION_APPLY_IN_PROGRESS: {
    vi: "Một lượt áp dụng khác đang chạy. Thử lại sau.",
    en: "Another apply run is in progress. Try again later.",
  },
  AFFILIATION_APPLY_FAILED: {
    vi: "Áp dụng thất bại; không có dữ liệu nào được ghi.",
    en: "Apply failed; nothing was written.",
  },
  ONLINE_CACHE_NOT_CONFIGURED: {
    vi: "Máy chủ chưa cấu hình thư mục lưu kết quả thu thập trực tuyến.",
    en: "The server has no online-enrichment cache directory configured.",
  },
  NO_PUBLICATIONS: {
    vi: "Chưa có công bố nào. Hãy nhập CSV Scopus trước.",
    en: "No publications yet. Import a Scopus CSV first.",
  },
  ENRICHMENT_ALREADY_RUNNING: {
    vi: "Một lượt thu thập trực tuyến khác đang chạy.",
    en: "Another online enrichment run is already in progress.",
  },
};
const ENRICHMENT_STATUS_LABEL: Record<string, Record<Locale, string>> = {
  RECEIVED: { vi: "Đã nhận, chuẩn bị chạy", en: "Received, about to start" },
  RUNNING: { vi: "Đang thu thập…", en: "Collecting…" },
  COMPLETED: { vi: "Hoàn tất", en: "Completed" },
  FAILED: { vi: "Thất bại", en: "Failed" },
  CANCELLED: { vi: "Đã hủy", en: "Cancelled" },
};
const ENRICHMENT_ACTIVE: EnrichmentJob["status"][] = ["RECEIVED", "RUNNING"];

const fmt = (n: number | null | undefined) => (n ?? 0).toLocaleString("vi-VN");
const sourceOf = (key: string) => SOURCE_LABEL[key.split("/")[0]] ?? key.split("/")[0];
const statusOf = (key: string, locale: Locale) => STATUS_LABEL[key.split("/")[1]]?.[locale] ?? key.split("/")[1];

function Card({ title, children, testId }: { title: string; children: React.ReactNode; testId?: string }) {
  return (
    <section className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs sm:p-5" data-testid={testId}>
      <h2 className="mb-3 text-sm font-bold text-slate-800">{title}</h2>
      {children}
    </section>
  );
}

export default function AffiliationsTab({ locale }: { locale: Locale }) {
  const vi = locale === "vi";
  const toast = useToast();
  const [overview, setOverview] = useState<AffiliationOverview | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [preview, setPreview] = useState<AffiliationPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [job, setJob] = useState<EnrichmentJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [sourceMode, setSourceMode] = useState<"offline" | "online">("offline");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      setOverview(await getAffiliationOverview());
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof ApiError ? error.detail ?? error.message : vi ? "Không tải được dữ liệu." : "Could not load data.");
    }
  }, [vi]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Poll the active online enrichment job every 2s, same pattern as the
  // Scopus import history page: only while active, pause when the tab is hidden.
  useEffect(() => {
    if (!job || !ENRICHMENT_ACTIVE.includes(job.status)) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    const poll = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const updated = await getOnlineEnrichment(job.id);
        setJob(updated);
        if (updated.status === "COMPLETED") {
          setSourceMode("online");
          setPreview(null);
          setConfirmed(false);
          toast.success(
            vi ? "Thu thập trực tuyến hoàn tất" : "Online collection completed",
            vi
              ? `Đã xử lý ${updated.processed_dois}/${updated.total_dois} DOI.`
              : `Processed ${updated.processed_dois}/${updated.total_dois} DOIs.`,
          );
        }
      } catch {
        // transient poll failure; try again on the next tick
      }
    };
    pollRef.current = setInterval(poll, 2000);
    window.addEventListener("focus", poll);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      window.removeEventListener("focus", poll);
    };
  }, [job, toast, vi]);

  const explain = (error: unknown): string => {
    if (error instanceof ApiError) {
      return (error.code && ERROR_LABEL[error.code]?.[locale]) || error.detail || error.message;
    }
    return vi ? "Có lỗi không xác định." : "Unknown error.";
  };

  const runStartEnrichment = useSingleFlight(async () => {
    setStarting(true);
    setMessage(null);
    try {
      setJob(await startOnlineEnrichment());
    } catch (error) {
      setMessage({ kind: "error", text: explain(error) });
    } finally {
      setStarting(false);
    }
  });

  const runCancelEnrichment = useSingleFlight(async () => {
    if (!job) return;
    try {
      setJob(await cancelOnlineEnrichment(job.id));
    } catch (error) {
      setMessage({ kind: "error", text: explain(error) });
    }
  });

  const runPreview = useSingleFlight(async () => {
    setPreviewing(true);
    setMessage(null);
    setConfirmed(false);
    try {
      const jobId = sourceMode === "online" && job?.status === "COMPLETED" ? job.id : undefined;
      setPreview(await previewAffiliations(jobId));
    } catch (error) {
      setPreview(null);
      setMessage({ kind: "error", text: explain(error) });
    } finally {
      setPreviewing(false);
    }
  });

  const runApply = useSingleFlight(async () => {
    if (!preview || !preview.can_apply || !confirmed) return;
    setApplying(true);
    setMessage(null);
    try {
      const jobId = sourceMode === "online" && job?.status === "COMPLETED" ? job.id : undefined;
      const done = await applyAffiliations(preview.fingerprint, jobId);
      const inserted = done.result.resolutions_to_insert ?? 0;
      const text = vi
        ? `Đã áp dụng: ${fmt(inserted)} kết quả đối chiếu đơn vị được ghi.`
        : `Applied: ${fmt(inserted)} affiliation resolutions written.`;
      toast.success(vi ? "Áp dụng đơn vị hoàn tất" : "Affiliations applied", text);
      setMessage({ kind: "ok", text });
      setPreview(null);
      setConfirmed(false);
      await refresh();
    } catch (error) {
      const text = explain(error);
      setMessage({ kind: "error", text });
      if (error instanceof ApiError && error.code === "PREVIEW_STALE") setPreview(null);
    } finally {
      setApplying(false);
    }
  });

  const source = overview?.source;
  const db = overview?.database;

  return (
    <div className="space-y-4" data-testid="affiliations-tab">
      <div className="rounded-lg border border-sky-100 bg-sky-50/70 p-3 text-xs leading-relaxed text-sky-900">
        {vi
          ? "File CSV Scopus không có cột đơn vị theo từng tác giả. Bước này bổ sung đơn vị từ metadata công khai đã tải sẵn (OpenAlex, Crossref, ORCID). Hệ thống không tự kết nối mạng. Đơn vị là lời khai của nguồn ngoài, không phải xác nhận của Scopus; tác giả không đủ bằng chứng sẽ hiển thị “Chưa xác định” và không bị gán đơn vị."
          : "The Scopus CSV carries no per-author affiliation. This step adds affiliations from pre-downloaded public metadata (OpenAlex, Crossref, ORCID). The system never goes online by itself. Units are statements of external sources, not asserted by Scopus; authors without enough evidence stay “Unresolved” and get no unit."}
      </div>

      {loadError && <p className="text-xs font-medium text-rose-600" role="alert">{loadError}</p>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={vi ? "1. Nguồn dữ liệu đơn vị" : "1. Affiliation source"} testId="aff-source-card">
          {!source ? (
            <p className="text-xs text-slate-500">{vi ? "Đang tải…" : "Loading…"}</p>
          ) : !source.configured ? (
            <p className="text-xs font-medium text-amber-700" data-testid="aff-source-missing">
              {BLOCKED_LABEL.SOURCE_DIR_NOT_CONFIGURED[locale]}
              <br />
              <span className="font-normal text-slate-500">
                {vi
                  ? "Người vận hành cần đặt biến môi trường và chép bộ metadata vào thư mục đó. Thu thập trực tuyến chưa được bật."
                  : "The operator must set the variable and place the metadata bundle there. Online collection is not enabled."}
              </span>
            </p>
          ) : (
            <div className="space-y-2 text-xs text-slate-700">
              <p>
                <span className="font-semibold">{vi ? "Thư mục: " : "Directory: "}</span>
                <code className="rounded bg-slate-100 px-1">{source.directory_label}</code>{" "}
                <span className={source.ready ? "font-bold text-emerald-700" : "font-bold text-rose-600"} data-testid="aff-source-state">
                  {source.ready ? (vi ? "Sẵn sàng" : "Ready") : vi ? "Chưa sẵn sàng" : "Not ready"}
                </span>
              </p>
              {source.problems.length > 0 && (
                <p className="text-rose-600">
                  {source.problems.map((p) => BLOCKED_LABEL[p]?.[locale] ?? p).join(" · ")}
                </p>
              )}
              <ul className="space-y-0.5">
                {source.files.map((f) => (
                  <li key={f.name} className="flex flex-wrap items-center gap-1.5">
                    <span className={f.present ? "text-emerald-600" : f.required ? "text-rose-600" : "text-slate-400"}>
                      {f.present ? "✓" : f.required ? "✗" : "–"}
                    </span>
                    <code>{f.name}</code>
                    {!f.required && <span className="text-slate-400">({vi ? "tùy chọn: đối chiếu chéo" : "optional: cross-check"})</span>}
                    {f.sha256 && <span className="text-slate-400">SHA-256 {f.sha256.slice(0, 10)}…</span>}
                  </li>
                ))}
              </ul>
              {source.ready && (
                <p className="text-slate-600" data-testid="aff-source-counts">
                  {vi ? "Có " : "Contains "}
                  <b>{fmt(source.openalex_works)}</b> {vi ? "bài trên OpenAlex" : "OpenAlex works"}, <b>{fmt(source.crossref_works)}</b>{" "}
                  {vi ? "bài trên Crossref" : "Crossref works"}, <b>{fmt(source.orcid_records)}</b> ORCID (
                  <b>{fmt(source.orcid_with_scopus_id)}</b> {vi ? "có khai Scopus ID" : "declare a Scopus ID"}).
                  {source.retrieved_from && (
                    <>
                      {" "}
                      {vi ? "Tải ngày " : "Retrieved "}
                      {source.retrieved_from.slice(0, 10)}
                      {source.retrieved_to && source.retrieved_to.slice(0, 10) !== source.retrieved_from.slice(0, 10)
                        ? ` – ${source.retrieved_to.slice(0, 10)}`
                        : ""}
                      .
                    </>
                  )}
                </p>
              )}
            </div>
          )}
        </Card>

        <Card title={vi ? "2. Hiện trạng trong hệ thống" : "2. Current state"} testId="aff-state-card">
          {!db ? (
            <p className="text-xs text-slate-500">{vi ? "Đang tải…" : "Loading…"}</p>
          ) : (
            <div className="space-y-1.5 text-xs text-slate-700">
              <p>
                {fmt(db.publications)} {vi ? "công bố" : "publications"} · {fmt(db.author_positions)} {vi ? "vị trí tác giả" : "author positions"} ·{" "}
                {fmt(db.organizations)} {vi ? "tổ chức" : "organizations"} · {fmt(db.affiliation_entries)} {vi ? "dòng đơn vị" : "affiliation lines"}
              </p>
              {Object.keys(db.resolutions_by_source_and_status).length === 0 ? (
                <p className="font-medium text-slate-500" data-testid="aff-none-applied">
                  {vi ? "Chưa áp dụng đối chiếu đơn vị nào. Mọi tác giả đang hiển thị “Chưa đối chiếu”." : "No affiliation reconciliation applied yet. Every author shows “Not reconciled”."}
                </p>
              ) : (
                <ul className="space-y-0.5" data-testid="aff-state-list">
                  {Object.entries(db.resolutions_by_source_and_status)
                    .sort()
                    .map(([key, n]) => (
                      <li key={key}>
                        {sourceOf(key)} · {statusOf(key, locale)}: <b>{fmt(n)}</b>
                      </li>
                    ))}
                </ul>
              )}
              {db.last_run && (
                <p className="text-slate-500">
                  {vi ? "Lần gần nhất: " : "Last run: "}
                  {new Date(db.last_run.at).toLocaleString(vi ? "vi-VN" : "en-GB")}
                  {db.last_run.action.endsWith("FAILED") ? (vi ? " (thất bại)" : " (failed)") : ""}
                </p>
              )}
            </div>
          )}
        </Card>
      </div>

      <Card title={vi ? "2. Thu thập đơn vị trực tuyến (tùy chọn)" : "2. Online affiliation collection (optional)"} testId="aff-online-card">
        <p className="mb-3 text-xs leading-relaxed text-slate-600">
          {vi
            ? "ADMIN có thể chủ động tra cứu OpenAlex, Crossref và ORCID công khai cho DOI của các công bố hiện có, thay vì cần chuẩn bị bộ nguồn offline thủ công. Chạy nền; có thể hủy giữa chừng."
            : "ADMIN may actively query public OpenAlex, Crossref and ORCID for the DOIs of existing publications, instead of preparing an offline bundle by hand. Runs in the background; can be cancelled mid-way."}
        </p>
        {!job || !ENRICHMENT_ACTIVE.includes(job.status) ? (
          <button
            type="button"
            className={BUTTON_SECONDARY}
            onClick={runStartEnrichment}
            disabled={starting}
            data-testid="aff-online-start-btn"
          >
            {starting ? (vi ? "Đang khởi tạo…" : "Starting…") : vi ? "Bắt đầu thu thập trực tuyến" : "Start online collection"}
          </button>
        ) : (
          <div className="flex items-center gap-2" data-testid="aff-online-running">
            <span className="text-xs font-medium text-sky-700">
              {ENRICHMENT_STATUS_LABEL[job.status]?.[locale] ?? job.status} ({fmt(job.processed_dois)}/{fmt(job.total_dois)})
            </span>
            <button type="button" className={BUTTON_SECONDARY} onClick={runCancelEnrichment} data-testid="aff-online-cancel-btn">
              {vi ? "Hủy" : "Cancel"}
            </button>
          </div>
        )}
        {job && !ENRICHMENT_ACTIVE.includes(job.status) && (
          <div className="mt-3 text-xs text-slate-700" data-testid="aff-online-result">
            <p>
              <span className={job.status === "COMPLETED" ? "font-bold text-emerald-700" : "font-bold text-rose-600"}>
                {ENRICHMENT_STATUS_LABEL[job.status]?.[locale] ?? job.status}
              </span>
              {job.status === "COMPLETED" && (
                <>
                  {" · "}
                  {fmt(job.openalex_found)} {vi ? "bài OpenAlex" : "OpenAlex works"}
                  {" · "}
                  {fmt(job.crossref_found)} {vi ? "bài Crossref" : "Crossref works"}
                  {" · "}
                  {fmt(job.orcid_fetched)} ORCID
                </>
              )}
              {job.status === "FAILED" && job.error_summary?.message && <> · {job.error_summary.message}</>}
            </p>
            {job.status === "COMPLETED" && (
              <p className="mt-1 text-slate-500">
                {vi
                  ? 'Kết quả đã sẵn sàng. Nhấn "Xem trước" bên dưới để dùng kết quả này thay cho bộ nguồn offline.'
                  : 'Result is ready. Click "Preview" below to use this result instead of the offline bundle.'}
              </p>
            )}
          </div>
        )}
      </Card>

      <Card title={vi ? "3. Xem trước và áp dụng" : "3. Preview and apply"} testId="aff-preview-card">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button type="button" className={BUTTON_SECONDARY} onClick={runPreview} disabled={previewing || applying} data-testid="aff-preview-btn">
            {previewing ? (vi ? "Đang tính…" : "Computing…") : vi ? "Xem trước" : "Preview"}
          </button>
          <span className="text-xs text-slate-500" data-testid="aff-preview-source-mode">
            {sourceMode === "online" && job?.status === "COMPLETED"
              ? vi
                ? "Dùng kết quả thu thập trực tuyến vừa chạy."
                : "Using the result of the online run just completed."
              : vi
                ? "Xem trước chỉ đọc, không ghi dữ liệu."
                : "Preview is read-only and writes nothing."}
          </span>
          {job?.status === "COMPLETED" && (
            <button
              type="button"
              className="text-xs font-medium text-sky-700 underline"
              onClick={() => setSourceMode((m) => (m === "online" ? "offline" : "online"))}
              data-testid="aff-source-mode-toggle"
            >
              {sourceMode === "online"
                ? vi
                  ? "Chuyển sang bộ nguồn offline"
                  : "Switch to offline bundle"
                : vi
                  ? "Chuyển sang kết quả trực tuyến"
                  : "Switch to online result"}
            </button>
          )}
        </div>

        {message && (
          <p className={`mb-3 text-xs font-medium ${message.kind === "ok" ? "text-emerald-700" : "text-rose-600"}`} role="status" data-testid="aff-message">
            {message.text}
          </p>
        )}

        {preview && (
          <div className="space-y-3 text-xs text-slate-700" data-testid="aff-preview">
            {preview.blocked_reason && (
              <p className="rounded-lg border border-amber-200 bg-amber-50 p-2 font-medium text-amber-800" data-testid="aff-blocked">
                {BLOCKED_LABEL[preview.blocked_reason]?.[locale] ?? preview.blocked_reason}
              </p>
            )}
            {preview.input.papers !== undefined && (
              <div data-testid="aff-coverage">
                <p className="mb-1 font-semibold">{vi ? "Mức bao phủ của nguồn" : "Source coverage"}</p>
                <ul className="grid gap-x-6 gap-y-0.5 sm:grid-cols-2">
                  <li>{vi ? "Công bố cần đối chiếu" : "Publications"}: <b>{fmt(preview.input.papers)}</b></li>
                  <li>{vi ? "Vị trí tác giả" : "Author positions"}: <b>{fmt(preview.input.author_slots)}</b></li>
                  <li>{vi ? "Có bài trong OpenAlex" : "Found in OpenAlex"}: <b>{fmt(preview.input.papers_with_openalex_work)}</b></li>
                  <li>{vi ? "Có bài trong Crossref" : "Found in Crossref"}: <b>{fmt(preview.input.papers_with_crossref_work)}</b></li>
                  <li>{vi ? "Không có bài ở nguồn nào" : "In no source"}: <b>{fmt(preview.input.papers_without_any_work)}</b></li>
                  <li>{vi ? "Không có DOI" : "Without DOI"}: <b>{fmt(preview.input.papers_without_doi)}</b></li>
                  <li>{vi ? "DOI trùng (không dùng)" : "Duplicate DOI (unused)"}: <b>{fmt(preview.input.papers_with_duplicate_doi)}</b></li>
                  <li data-testid="aff-cross-check">
                    {vi ? "Đối chiếu chéo với tệp khảo sát" : "Cross-check with survey file"}:{" "}
                    {preview.input.cross_check_against_survey_jsonl ? (
                      <>
                        <b>{fmt(preview.input.cross_check_links_matched)}</b> {vi ? "khớp" : "agree"}
                        {(preview.input.cross_check_links_not_covered ?? 0) > 0 && (
                          <>
                            , <b>{fmt(preview.input.cross_check_links_not_covered)}</b> {vi ? "không có trong tệp (chỉ tính lại từ metadata gốc)" : "not in the file (recomputed from raw metadata only)"}
                          </>
                        )}
                        {preview.source_mismatches > 0 && <b className="text-rose-600"> · {fmt(preview.source_mismatches)} {vi ? "lệch" : "mismatches"}</b>}
                      </>
                    ) : (
                      <b>{vi ? "Không có tệp (tùy chọn)" : "No file (optional)"}</b>
                    )}
                  </li>
                </ul>
              </div>
            )}

            {preview.report.by_source_and_confidence && (
              <div>
                <p className="mb-1 font-semibold">{vi ? "Kết quả theo nguồn và mức tin cậy" : "Result by source and confidence"}</p>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[32rem] border-collapse text-left" data-testid="aff-preview-table">
                    <thead>
                      <tr className="border-b border-slate-200 text-[11px] uppercase text-slate-500">
                        <th className="py-1 pr-3">{vi ? "Nguồn" : "Source"}</th>
                        <th className="py-1 pr-3">{vi ? "Mức" : "Level"}</th>
                        {Object.keys(OUTCOME_LABEL).map((k) => (
                          <th key={k} className="py-1 pr-3 text-right">{OUTCOME_LABEL[k][locale]}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(preview.report.by_source_and_confidence)
                        .sort()
                        .map(([key, counts]) => (
                          <tr key={key} className="border-b border-slate-100">
                            <td className="py-1 pr-3">{sourceOf(key)}</td>
                            <td className="py-1 pr-3">{statusOf(key, locale)}</td>
                            {Object.keys(OUTCOME_LABEL).map((k) => (
                              <td key={k} className="py-1 pr-3 text-right tabular-nums">{fmt((counts as Record<string, number>)[k])}</td>
                            ))}
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-1.5" data-testid="aff-preview-totals">
                  {vi ? "Sẽ ghi: " : "Will write: "}
                  <b>{fmt(preview.report.resolutions_to_insert)}</b> {vi ? "kết quả đối chiếu" : "resolutions"},{" "}
                  <b>{fmt(preview.report.affiliations_to_insert)}</b> {vi ? "dòng đơn vị" : "affiliation lines"},{" "}
                  <b>{fmt(preview.report.organizations_to_insert)}</b> {vi ? "tổ chức mới" : "new organizations"}.
                </p>
                {preview.report.conflict_reasons && Object.keys(preview.report.conflict_reasons).length > 0 && (
                  <p className="text-slate-500">
                    {vi ? "Xung đột được giữ lại an toàn: " : "Conflicts safely withheld: "}
                    {Object.entries(preview.report.conflict_reasons).map(([k, n]) => `${k} (${fmt(n)})`).join(" · ")}
                  </p>
                )}
              </div>
            )}

            <label className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={confirmed}
                disabled={!preview.can_apply || applying}
                onChange={(e) => setConfirmed(e.target.checked)}
                data-testid="aff-confirm"
              />
              <span>
                {vi
                  ? "Tôi đã xem kết quả trên. Đơn vị đến từ nguồn ngoài, “Đã đối chiếu” chưa phải “Đã xác minh”, và tác giả không đủ bằng chứng sẽ giữ “Chưa xác định”."
                  : "I reviewed the result above. Units come from external sources, “Cross-checked” is not “Verified”, and authors without enough evidence stay “Unresolved”."}
              </span>
            </label>
            <button
              type="button"
              className={BUTTON_PRIMARY}
              onClick={runApply}
              disabled={!preview.can_apply || !confirmed || applying}
              data-testid="aff-apply-btn"
            >
              {applying ? (vi ? "Đang áp dụng…" : "Applying…") : vi ? "Xác nhận áp dụng" : "Confirm and apply"}
            </button>
          </div>
        )}
      </Card>

      <ManualReviewCard locale={locale} />
    </div>
  );
}
