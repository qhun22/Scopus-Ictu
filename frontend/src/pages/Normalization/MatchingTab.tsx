import { useState } from "react";
import {
  applyCrawIngestion,
  CrawIngestionPreview,
  generateCandidates,
  GenerationRunResult,
  previewCrawIngestion,
} from "../../api/matching";
import { ApiError } from "../../api/client";
import { BUTTON_PRIMARY, BUTTON_SECONDARY } from "../../components/common/buttonStyles";
import { useSingleFlight } from "../../components/common/useSingleFlight";
import { useToast } from "../../contexts/ToastContext";

type Locale = "vi" | "en";

const BLOCKED_LABEL: Record<string, Record<Locale, string>> = {
  CRAW_SOURCE_NOT_CONFIGURED: {
    vi: "Máy chủ chưa được cấu hình thư mục nguồn Craw (CRAW_SOURCE_DIR).",
    en: "The server has no Craw source directory configured (CRAW_SOURCE_DIR).",
  },
  CRAW_SOURCE_DIR_MISSING: { vi: "Thư mục nguồn Craw đã cấu hình không tồn tại.", en: "The configured Craw source directory does not exist." },
  CRAW_SOURCE_FILES_MISSING: { vi: "Thiếu tệp nguồn Craw (lecturers.json / publications.json / lecturer_publication_links.json).", en: "Missing Craw source files." },
};
const ERROR_LABEL: Record<string, Record<Locale, string>> = {
  PREVIEW_STALE: {
    vi: "Dữ liệu Craw đã thay đổi kể từ lần xem trước. Hãy xem trước lại.",
    en: "Craw data changed since the preview. Preview again.",
  },
  CRAW_APPLY_IN_PROGRESS: { vi: "Một lượt nạp Craw khác đang chạy.", en: "Another Craw ingestion run is in progress." },
  CRAW_APPLY_FAILED: { vi: "Nạp Craw thất bại; không có dữ liệu nào được ghi.", en: "Craw ingestion failed; nothing was written." },
};

const fmt = (n: number | null | undefined) => (n ?? 0).toLocaleString("vi-VN");

function Card({ title, children, testId }: { title: string; children: React.ReactNode; testId?: string }) {
  return (
    <section className="rounded-lg border border-slate-200/80 bg-white p-4 shadow-xs sm:p-5" data-testid={testId}>
      <h2 className="mb-3 text-sm font-bold text-slate-800">{title}</h2>
      {children}
    </section>
  );
}

export default function MatchingTab({ locale }: { locale: Locale }) {
  const vi = locale === "vi";
  const toast = useToast();

  const [generating, setGenerating] = useState(false);
  const [generationResult, setGenerationResult] = useState<GenerationRunResult | null>(null);
  const [generationMessage, setGenerationMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const [preview, setPreview] = useState<CrawIngestionPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [crawMessage, setCrawMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const explain = (error: unknown): string => {
    if (error instanceof ApiError) {
      return (error.code && ERROR_LABEL[error.code]?.[locale]) || error.detail || error.message;
    }
    return vi ? "Có lỗi không xác định." : "Unknown error.";
  };

  const runGenerate = useSingleFlight(async () => {
    setGenerating(true);
    setGenerationMessage(null);
    try {
      const result = await generateCandidates();
      setGenerationResult(result);
      const text = vi
        ? `Đã sinh/cập nhật ${fmt(result.candidate_roots)} ứng viên (${fmt(result.name_candidates)} từ tên, ${fmt(result.craw_assisted_candidates)} từ Craw). ${fmt(result.craw_unattributed)} bằng chứng công bố Craw chưa quy thuộc về ai.`
        : `${fmt(result.candidate_roots)} candidates generated/updated (${fmt(result.name_candidates)} from name matching, ${fmt(result.craw_assisted_candidates)} Craw-assisted). ${fmt(result.craw_unattributed)} Craw publication links remain unattributed.`;
      toast.success(vi ? "Sinh ứng viên hoàn tất" : "Candidate generation complete", text);
      setGenerationMessage({ kind: "ok", text });
    } catch (error) {
      setGenerationMessage({ kind: "error", text: explain(error) });
    } finally {
      setGenerating(false);
    }
  });

  const runPreview = useSingleFlight(async () => {
    setPreviewing(true);
    setCrawMessage(null);
    setConfirmed(false);
    try {
      setPreview(await previewCrawIngestion());
    } catch (error) {
      setPreview(null);
      setCrawMessage({ kind: "error", text: explain(error) });
    } finally {
      setPreviewing(false);
    }
  });

  const runApply = useSingleFlight(async () => {
    if (!preview || !preview.can_apply || !confirmed) return;
    setApplying(true);
    setCrawMessage(null);
    try {
      const done = await applyCrawIngestion(preview.fingerprint);
      const text = vi
        ? `Đã nạp: ${fmt(done.result.snapshots_created)} bản chụp mới, ${fmt(done.result.known_publications_created)} công bố đã biết mới.`
        : `Ingested: ${fmt(done.result.snapshots_created)} new snapshots, ${fmt(done.result.known_publications_created)} new known publications.`;
      toast.success(vi ? "Nạp Craw hoàn tất" : "Craw ingestion applied", text);
      setCrawMessage({ kind: "ok", text });
      setPreview(null);
      setConfirmed(false);
    } catch (error) {
      const text = explain(error);
      setCrawMessage({ kind: "error", text });
      if (error instanceof ApiError && error.code === "PREVIEW_STALE") setPreview(null);
    } finally {
      setApplying(false);
    }
  });

  return (
    <div className="space-y-4" data-testid="matching-tab">
      <div className="rounded-lg border border-sky-100 bg-sky-50/70 p-3 text-xs leading-relaxed text-sky-900">
        {vi
          ? "Nạp Craw chỉ bổ sung bằng chứng công bố cho giảng viên đã có hồ sơ (qua URL hồ sơ ICTU). Sinh ứng viên chạy đối sánh theo tên VÀ tìm thêm ứng viên từ Craw khi công bố đã biết của giảng viên trùng DOI/tiêu đề với 1 Scopus Author ở đúng vị trí tác giả CÓ tương quan tên — không bao giờ gán hàng loạt cho mọi tác giả trên một công bố nhiều người viết. Mọi ứng viên vẫn ở trạng thái chờ REVIEWER duyệt."
          : "Craw ingestion only adds publication evidence for lecturers who already have a profile (via ICTU profile URL). Candidate generation runs name matching AND finds additional Craw-assisted candidates when a lecturer's known publication matches a Scopus publication by DOI/title at an author position that also has name correspondence — never assigning every author on a multi-author paper. Every candidate still waits for REVIEWER approval."}
      </div>

      <Card title={vi ? "1. Nạp bằng chứng công bố từ Craw ICTU" : "1. Ingest Craw ICTU publication evidence"} testId="craw-ingest-card">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button type="button" className={BUTTON_SECONDARY} onClick={runPreview} disabled={previewing || applying} data-testid="craw-preview-btn">
            {previewing ? (vi ? "Đang tính…" : "Computing…") : vi ? "Xem trước" : "Preview"}
          </button>
          <span className="text-xs text-slate-500">
            {vi ? "Xem trước chỉ đọc, không ghi dữ liệu." : "Preview is read-only and writes nothing."}
          </span>
        </div>

        {crawMessage && (
          <p className={`mb-3 text-xs font-medium ${crawMessage.kind === "ok" ? "text-emerald-700" : "text-rose-600"}`} role="status" data-testid="craw-message">
            {crawMessage.text}
          </p>
        )}

        {preview && (
          <div className="space-y-3 text-xs text-slate-700" data-testid="craw-preview">
            {preview.blocked_reason && (
              <p className="rounded-lg border border-amber-200 bg-amber-50 p-2 font-medium text-amber-800" data-testid="craw-blocked">
                {BLOCKED_LABEL[preview.blocked_reason]?.[locale] ?? preview.blocked_reason}
              </p>
            )}
            {preview.blocking.length > 0 && (
              <ul className="space-y-0.5 text-amber-700">
                {preview.blocking.map((b, i) => (
                  <li key={i}>• {b}</li>
                ))}
              </ul>
            )}
            {preview.preview.source_lecturer_count !== undefined && (
              <ul className="grid gap-x-6 gap-y-0.5 sm:grid-cols-2" data-testid="craw-preview-stats">
                <li>{vi ? "Giảng viên trong nguồn Craw" : "Lecturers in Craw source"}: <b>{fmt(preview.preview.source_lecturer_count)}</b></li>
                <li>{vi ? "Đã khớp hồ sơ" : "Mapped by profile"}: <b>{fmt(preview.preview.mapped_lecturer_count)}</b></li>
                <li>{vi ? "Chưa khớp hồ sơ" : "Unmapped"}: <b>{fmt(preview.preview.unmapped_lecturer_count)}</b></li>
                <li>{vi ? "Bản chụp mới" : "New snapshots"}: <b>{fmt(preview.preview.snapshots_to_create)}</b></li>
                <li>{vi ? "Công bố đã biết mới" : "New known publications"}: <b>{fmt(preview.preview.known_publications_to_create)}</b></li>
                <li>{vi ? "Đã có sẵn" : "Already present"}: <b>{fmt(preview.preview.known_publications_already_present)}</b></li>
              </ul>
            )}

            <label className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={confirmed}
                disabled={!preview.can_apply || applying}
                onChange={(e) => setConfirmed(e.target.checked)}
                data-testid="craw-confirm"
              />
              <span>
                {vi
                  ? "Tôi đã xem kết quả trên. Nạp Craw không tự tạo hoặc xác nhận danh tính giảng viên ↔ Scopus Author."
                  : "I reviewed the result above. Craw ingestion does not create or confirm any lecturer ↔ Scopus Author identity."}
              </span>
            </label>
            <button
              type="button"
              className={BUTTON_PRIMARY}
              onClick={runApply}
              disabled={!preview.can_apply || !confirmed || applying}
              data-testid="craw-apply-btn"
            >
              {applying ? (vi ? "Đang áp dụng…" : "Applying…") : vi ? "Xác nhận áp dụng" : "Confirm and apply"}
            </button>
          </div>
        )}
      </Card>

      <Card title={vi ? "2. Sinh ứng viên đối sánh" : "2. Generate matching candidates"} testId="generate-candidates-card">
        <p className="mb-3 text-xs leading-relaxed text-slate-600">
          {vi
            ? "Chạy lại an toàn nhiều lần: không ghi đè quyết định REVIEWER đã duyệt/từ chối, không tự nâng ứng viên lên trạng thái đã xác nhận."
            : "Safe to re-run: never overwrites a REVIEWER's accept/reject decision, never auto-promotes a candidate to confirmed."}
        </p>
        <button type="button" className={BUTTON_PRIMARY} onClick={runGenerate} disabled={generating} data-testid="generate-candidates-btn">
          {generating ? (vi ? "Đang sinh ứng viên…" : "Generating…") : vi ? "Chạy sinh ứng viên" : "Run candidate generation"}
        </button>

        {generationMessage && (
          <p className={`mt-3 text-xs font-medium ${generationMessage.kind === "ok" ? "text-emerald-700" : "text-rose-600"}`} role="status" data-testid="generate-message">
            {generationMessage.text}
          </p>
        )}

        {generationResult && (
          <ul className="mt-3 grid gap-x-6 gap-y-0.5 text-xs text-slate-700 sm:grid-cols-2" data-testid="generate-result-stats">
            <li>{vi ? "Tổng ứng viên" : "Candidate roots"}: <b>{fmt(generationResult.candidate_roots)}</b></li>
            <li>{vi ? "Từ khớp tên" : "From name matching"}: <b>{fmt(generationResult.name_candidates)}</b></li>
            <li>{vi ? "Từ Craw (chưa có trong bước tên)" : "Craw-assisted (new)"}: <b>{fmt(generationResult.craw_assisted_candidates)}</b></li>
            <li>{vi ? "Bằng chứng Craw chưa quy thuộc" : "Craw evidence unattributed"}: <b>{fmt(generationResult.craw_unattributed)}</b></li>
          </ul>
        )}
      </Card>
    </div>
  );
}
