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
    vi: "Hệ thống chưa được cấu hình kho lưu trữ ICTU. Vui lòng liên hệ quản trị viên kỹ thuật.",
    en: "The server has no ICTU archive source configured. Please contact a system administrator.",
  },
  CRAW_SOURCE_DIR_MISSING: {
    vi: "Không tìm thấy thư mục kho lưu trữ ICTU đã cấu hình. Vui lòng liên hệ quản trị viên kỹ thuật.",
    en: "The configured ICTU archive directory does not exist. Please contact a system administrator.",
  },
  CRAW_SOURCE_FILES_MISSING: {
    vi: "Thiếu tệp dữ liệu trong kho lưu trữ ICTU. Vui lòng liên hệ quản trị viên kỹ thuật.",
    en: "Required ICTU archive data files are missing. Please contact a system administrator.",
  },
};
const ERROR_LABEL: Record<string, Record<Locale, string>> = {
  PREVIEW_STALE: {
    vi: "Dữ liệu đã thay đổi kể từ lần xem trước. Vui lòng bấm \"Xem trước dữ liệu\" lại.",
    en: "The data changed since the preview. Please preview again.",
  },
  CRAW_APPLY_IN_PROGRESS: {
    vi: "Hệ thống đang xử lý một yêu cầu bổ sung dữ liệu khác. Vui lòng đợi rồi thử lại.",
    en: "Another data update is already in progress. Please wait and try again.",
  },
  CRAW_APPLY_FAILED: {
    vi: "Không thể hoàn tất việc bổ sung dữ liệu. Không có thay đổi nào được lưu.",
    en: "The data update could not be completed. Nothing was saved.",
  },
};

const fmt = (n: number | null | undefined) => (n ?? 0).toLocaleString("vi-VN");

function Card({ title, children, testId }: { title: string; children: React.ReactNode; testId?: string }) {
  return (
    <section className="rounded-[5px] border border-slate-200/80 bg-white p-4 shadow-xs sm:p-5" data-testid={testId}>
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
    return vi ? "Đã xảy ra lỗi không xác định. Vui lòng thử lại." : "An unknown error occurred. Please try again.";
  };

  const runGenerate = useSingleFlight(async () => {
    setGenerating(true);
    setGenerationMessage(null);
    try {
      const result = await generateCandidates();
      setGenerationResult(result);
      const text = vi
        ? `Đã tạo/cập nhật ${fmt(result.candidate_roots)} cặp đề xuất (${fmt(result.name_candidates)} từ đối chiếu tên, ${fmt(result.craw_assisted_candidates)} từ kho lưu trữ ICTU). ${fmt(result.craw_unattributed)} công bố trong kho lưu trữ chưa xác định được thuộc giảng viên nào.`
        : `${fmt(result.candidate_roots)} proposed pairs created/updated (${fmt(result.name_candidates)} from name matching, ${fmt(result.craw_assisted_candidates)} from the ICTU archive). ${fmt(result.craw_unattributed)} archive publications could not be attributed to a lecturer.`;
      toast.success(vi ? "Đã tạo xong danh sách đề xuất" : "Proposed pairs ready", text);
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
        ? `Đã bổ sung: ${fmt(done.result.snapshots_created)} bản ghi công bố mới, ${fmt(done.result.known_publications_created)} công bố mới được ghi nhận cho giảng viên.`
        : `Added: ${fmt(done.result.snapshots_created)} new publication records, ${fmt(done.result.known_publications_created)} new publications recorded for lecturers.`;
      toast.success(vi ? "Đã bổ sung dữ liệu công bố" : "Publication data added", text);
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

  const sourceCount = preview?.preview.source_lecturer_count;
  const mappedCount = preview?.preview.mapped_lecturer_count;
  const unmappedCount = preview?.preview.unmapped_lecturer_count;

  return (
    <div className="space-y-4" data-testid="matching-tab">
      <div className="rounded-[5px] border border-sky-100 bg-sky-50/70 p-3 text-xs leading-relaxed text-sky-900">
        {vi
          ? "Trang này giúp liên kết hồ sơ giảng viên ICTU với tác giả tương ứng trên Scopus, qua hai bước độc lập: bổ sung công bố đã thu thập sẵn từ kho lưu trữ của trường, và tìm các cặp giảng viên – tác giả Scopus có khả năng tương ứng để người xét duyệt kiểm tra. Không bước nào tự động xác nhận danh tính — mọi đề xuất đều cần REVIEWER kiểm tra và quyết định trước khi có hiệu lực."
          : "This page helps link ICTU lecturer profiles to the matching Scopus author, through two independent steps: adding publications already collected from the university's archive, and proposing lecturer–Scopus author pairs for a reviewer to check. Neither step confirms an identity automatically — every proposal needs REVIEWER approval before it takes effect."}
      </div>

      <Card
        title={vi ? "1. Bổ sung công bố của giảng viên từ kho lưu trữ ICTU" : "1. Add lecturer publications from the ICTU archive"}
        testId="craw-ingest-card"
      >
        <p className="mb-3 text-xs leading-relaxed text-slate-600">
          {vi
            ? "Hệ thống sử dụng dữ liệu công bố đã thu thập sẵn từ kho lưu trữ của trường để bổ sung thông tin cho những giảng viên đã có hồ sơ (liên kết qua trang hồ sơ ICTU của từng người). Việc bổ sung này không tự xác nhận danh tính tác giả Scopus — đó là việc của bước xét duyệt ở phần sau."
            : "The system uses publication data already collected from the university's archive to add information for lecturers who already have a profile (matched through each person's ICTU profile page). This does not confirm a Scopus author identity on its own — that happens later, during review."}
        </p>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button type="button" className={BUTTON_SECONDARY} onClick={runPreview} disabled={previewing || applying} data-testid="craw-preview-btn">
            {previewing ? (vi ? "Đang tính toán…" : "Computing…") : vi ? "Xem trước dữ liệu" : "Preview data"}
          </button>
          <span className="text-xs text-slate-500">
            {vi ? "Chỉ xem trước, chưa ghi dữ liệu nào vào hệ thống." : "Preview only — nothing is saved yet."}
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
              <p className="rounded-[5px] border border-amber-200 bg-amber-50 p-2 font-medium text-amber-800" data-testid="craw-blocked">
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
            {sourceCount !== undefined && (
              <>
                <ul className="grid gap-x-6 gap-y-0.5 sm:grid-cols-2" data-testid="craw-preview-stats">
                  <li>{vi ? "Giảng viên có trong kho lưu trữ" : "Lecturers in the archive"}: <b>{fmt(sourceCount)}</b></li>
                  <li>{vi ? "Đã tìm thấy hồ sơ tương ứng" : "Matched to a profile"}: <b>{fmt(mappedCount)}</b></li>
                  <li>{vi ? "Chưa tìm thấy hồ sơ tương ứng" : "No matching profile found"}: <b>{fmt(unmappedCount)}</b></li>
                  <li>{vi ? "Bản ghi công bố mới" : "New publication records"}: <b>{fmt(preview.preview.snapshots_to_create)}</b></li>
                  <li>{vi ? "Công bố mới cho giảng viên" : "New lecturer publications"}: <b>{fmt(preview.preview.known_publications_to_create)}</b></li>
                  <li>{vi ? "Đã có sẵn trong hệ thống" : "Already recorded"}: <b>{fmt(preview.preview.known_publications_already_present)}</b></li>
                </ul>
                {unmappedCount !== undefined && unmappedCount > 0 && (
                  <p className="rounded-[5px] border border-slate-200 bg-slate-50 p-2.5 leading-relaxed text-slate-600">
                    {vi
                      ? `${fmt(unmappedCount)} giảng viên trong kho lưu trữ chưa tìm thấy hồ sơ tương ứng trong danh sách giảng viên của hệ thống. Vui lòng kiểm tra xem danh sách giảng viên ICTU đã được nhập đầy đủ hay chưa (mục Nhập dữ liệu → Thêm giảng viên).`
                      : `${fmt(unmappedCount)} lecturers in the archive have no matching profile in the system's lecturer list. Please check whether the ICTU lecturer list has been fully imported (Data import → Add lecturers).`}
                  </p>
                )}
                {sourceCount !== undefined && sourceCount > 0 && unmappedCount === 0 && (
                  <p className="rounded-[5px] border border-emerald-200 bg-emerald-50 p-2.5 leading-relaxed text-emerald-800">
                    {vi
                      ? `Trong dữ liệu công bố từ kho lưu trữ ICTU, có ${fmt(sourceCount)} giảng viên được ghi nhận có liên kết công bố. Cả ${fmt(sourceCount)} hồ sơ đã tìm thấy trong danh sách giảng viên của hệ thống.`
                      : `In the ICTU archive data, ${fmt(sourceCount)} lecturers have linked publications. All ${fmt(sourceCount)} profiles were found in the system's lecturer list.`}
                  </p>
                )}
              </>
            )}

            <label className="flex items-start gap-2 rounded-[5px] border border-slate-200 bg-slate-50 p-2.5">
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
                  ? "Tôi đã xem kết quả ở trên. Tôi hiểu rằng việc bổ sung dữ liệu này không tự tạo hay xác nhận liên kết giữa giảng viên và tác giả Scopus."
                  : "I have reviewed the result above. I understand this does not create or confirm any link between a lecturer and a Scopus author."}
              </span>
            </label>
            <button
              type="button"
              className={BUTTON_PRIMARY}
              onClick={runApply}
              disabled={!preview.can_apply || !confirmed || applying}
              data-testid="craw-apply-btn"
            >
              {applying ? (vi ? "Đang bổ sung dữ liệu…" : "Adding data…") : vi ? "Xác nhận bổ sung dữ liệu" : "Confirm and add data"}
            </button>
          </div>
        )}
      </Card>

      <Card
        title={vi ? "2. Tìm giảng viên có thể tương ứng với tác giả Scopus" : "2. Find lecturers who may match a Scopus author"}
        testId="generate-candidates-card"
      >
        <p className="mb-3 text-xs leading-relaxed text-slate-600">
          {vi
            ? "Hệ thống so sánh tên giảng viên với tên tác giả trên Scopus, kết hợp thông tin công bố đã biết (nếu có từ bước 1), để tạo ra danh sách các cặp giảng viên – tác giả Scopus cần người xét duyệt kiểm tra. Đây chỉ là đề xuất, chưa phải danh tính đã được xác nhận. Có thể chạy lại nhiều lần một cách an toàn: không ghi đè quyết định mà REVIEWER đã duyệt hoặc từ chối trước đó, không tự động nâng một đề xuất lên trạng thái đã xác nhận."
            : "The system compares lecturer names with Scopus author names, combined with known publication evidence (from step 1, if any), to produce a list of lecturer–Scopus author pairs for a reviewer to check. These are proposals only, not confirmed identities. It is safe to re-run at any time: it never overwrites a REVIEWER's prior accept/reject decision, and never auto-promotes a proposal to confirmed."}
        </p>
        <button type="button" className={BUTTON_PRIMARY} onClick={runGenerate} disabled={generating} data-testid="generate-candidates-btn">
          {generating ? (vi ? "Đang tìm kiếm…" : "Searching…") : vi ? "Tạo danh sách đề xuất" : "Create proposed pairs"}
        </button>

        {generationMessage && (
          <p className={`mt-3 text-xs font-medium ${generationMessage.kind === "ok" ? "text-emerald-700" : "text-rose-600"}`} role="status" data-testid="generate-message">
            {generationMessage.text}
          </p>
        )}

        {generationResult && (
          <>
            <ul className="mt-3 grid gap-x-6 gap-y-0.5 text-xs text-slate-700 sm:grid-cols-2" data-testid="generate-result-stats">
              <li>{vi ? "Tổng số cặp đề xuất" : "Total proposed pairs"}: <b>{fmt(generationResult.candidate_roots)}</b></li>
              <li>{vi ? "Từ đối chiếu tên" : "From name matching"}: <b>{fmt(generationResult.name_candidates)}</b></li>
              <li>{vi ? "Từ kho lưu trữ ICTU (bổ sung)" : "From the ICTU archive (added)"}: <b>{fmt(generationResult.craw_assisted_candidates)}</b></li>
              <li>{vi ? "Công bố trong kho lưu trữ chưa xác định được giảng viên" : "Archive publications not yet attributed"}: <b>{fmt(generationResult.craw_unattributed)}</b></li>
            </ul>
            {generationResult.candidate_roots > 0 ? (
              <p className="mt-3 rounded-[5px] border border-emerald-200 bg-emerald-50 p-2.5 text-xs leading-relaxed text-emerald-800">
                {vi
                  ? "Bước tiếp theo: xem và xét duyệt các cặp được đề xuất trong mục Duyệt đối sánh."
                  : "Next step: review the proposed pairs in the Review queue."}
              </p>
            ) : (
              <p className="mt-3 rounded-[5px] border border-slate-200 bg-slate-50 p-2.5 text-xs leading-relaxed text-slate-600">
                {vi
                  ? "Chưa tìm thấy cặp giảng viên – tác giả Scopus nào phù hợp để đề xuất. Điều này có thể do tên giảng viên và tên tác giả Scopus không đủ tương đồng, hoặc dữ liệu công bố liên quan còn hạn chế. Bạn vẫn có thể tra cứu công bố và đơn vị tác giả bình thường mà không cần bước này."
                  : "No matching lecturer–Scopus author pairs were found to propose. This may be because lecturer and Scopus author names are not similar enough, or because related publication data is limited. You can still browse publications and author affiliations normally without this step."}
              </p>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
