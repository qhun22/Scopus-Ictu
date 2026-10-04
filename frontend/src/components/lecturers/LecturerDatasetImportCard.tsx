import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { importLecturerDataset, previewLecturerDataset } from "../../api/lecturerImport";
import ConfirmModal from "../../components/common/ConfirmModal";
import { useToast } from "../../contexts/ToastContext";
import { useI18n } from "../../i18n";

interface DatasetMeta {
  name?: string | null;
  schema_version: string;
  institution?: string | null;
  source?: string | null;
  source_url?: string | null;
  source_system?: string | null;
  generated_at?: string | null;
  parser_version?: string | null;
  record_count: number;
}

interface PreviewSummary {
  total: number;
  valid: number;
  create: number;
  update: number;
  unchanged: number;
  conflicts: number;
}

interface PreviewConflict {
  record_full_name: string;
  matched_by: string;
  existing_id: string;
  existing_full_name: string;
  existing_email: string | null;
}

interface PreviewResponse {
  dataset: DatasetMeta;
  summary: PreviewSummary;
  conflicts: PreviewConflict[];
  filename: string;
  parser_version: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export interface LecturerDatasetImportCardHandle {
  openFilePicker: () => void;
}

export interface LecturerDatasetImportCardProps {
  onSuccess?: () => void;
}

const LecturerDatasetImportCard = forwardRef<
  LecturerDatasetImportCardHandle,
  LecturerDatasetImportCardProps
>(function LecturerDatasetImportCard({ onSuccess }, ref) {
  const { t, locale } = useI18n();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({
    openFilePicker: () => {
      inputRef.current?.click();
    },
  }));

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectionError, setSelectionError] = useState("");
  const [dragging, setDragging] = useState(false);

  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const selectFile = (file: File | undefined) => {
    if (!file) return;
    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith(".json")) {
      setSelectedFile(null);
      setSelectionError(
        locale === "vi"
          ? "Chỉ hỗ trợ tệp .json. Vui lòng chọn lại."
          : "Only .json files are supported.",
      );
      return;
    }
    if (file.size === 0) {
      setSelectedFile(null);
      setSelectionError(
        locale === "vi" ? "Tệp rỗng." : "File is empty.",
      );
      return;
    }
    setSelectedFile(file);
    setSelectionError("");
    setPreview(null);
  };

  const clearFile = () => {
    setSelectedFile(null);
    setSelectionError("");
    setPreview(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const handlePreview = async () => {
    if (!selectedFile || previewing) return;
    setPreviewing(true);
    setPreview(null);
    try {
      const response = await previewLecturerDataset(selectedFile);
      setPreview(response);
      if (response.conflicts && response.conflicts.length > 0) {
        toast.warning(
          locale === "vi" ? "Cảnh báo trùng tên" : "Duplicate Name Warnings",
          locale === "vi"
            ? `Phát hiện ${response.conflicts.length} bản ghi có tên trùng với cán bộ khác. Các hồ sơ riêng biệt vẫn được lưu trữ đầy đủ.`
            : `${response.conflicts.length} duplicate name candidates detected. Separate records will be retained.`,
        );
      }
    } catch (error) {
      const code = error instanceof ApiError ? error.code : "PREVIEW_FAILED";
      const detail =
        error instanceof ApiError
          ? error.message
          : locale === "vi"
            ? "Không thể kiểm tra tệp JSON."
            : "Unable to preview the JSON file.";
      toast.error(t.lecturerImport.previewErrorTitle, `${code}: ${detail}`);
    } finally {
      setPreviewing(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!selectedFile || importing) return;
    setImporting(true);
    try {
      const result = await importLecturerDataset(selectedFile);
      setConfirmOpen(false);
      clearFile();
      toast.success(
        t.lecturerImport.importSuccessTitle,
        t.lecturerImport.importSuccessMessage.replace(
          "{count}",
          String(result.summary.total),
        ),
      );
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      const code = error instanceof ApiError ? error.code : "IMPORT_FAILED";
      const detail =
        error instanceof ApiError
          ? error.message
          : locale === "vi"
            ? "Không thể nhập dữ liệu giảng viên."
            : "Unable to import lecturer data.";
      toast.error(t.lecturerImport.importErrorTitle, `${code}: ${detail}`);
    } finally {
      setImporting(false);
    }
  };

  return (
    <section className="flex flex-col h-full rounded-xl border border-slate-200/80 bg-white p-4 sm:p-5 shadow-xs">
      <div className="flex items-center gap-2.5 pb-3.5 border-b border-slate-100">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100 text-violet-600">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M12 14l9-5-9-5-9 5 9 5zm0 0v6m0 0l3-3m-3 3l-3-3"
            />
          </svg>
        </div>
        <div>
          <h2 className="text-sm font-bold text-slate-800">
            {t.lecturerImport.cardTitle}
          </h2>
          <p className="text-xs text-slate-500">
            {t.lecturerImport.cardSubtitle}
          </p>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={(event) => selectFile(event.target.files?.[0])}
      />

      {!selectedFile ? (
        <div
          onClick={() => inputRef.current?.click()}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            event.preventDefault();
            if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            selectFile(event.dataTransfer.files[0]);
          }}
          className={`mt-4 group flex flex-1 min-h-44 flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-6 text-center cursor-pointer transition-all duration-200 ${
            dragging
              ? "border-violet-500 bg-violet-50 scale-[0.99]"
              : "border-slate-200 hover:border-violet-400 bg-slate-50/40 hover:bg-violet-50/40"
          }`}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 mb-2.5 shadow-2xs group-hover:scale-110 transition-transform">
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                d="M12 4v16m8-8H4"
              />
            </svg>
          </div>
          <p className="text-xs font-semibold text-slate-700 sm:text-sm group-hover:text-violet-600 transition-colors">
            {locale === "vi"
              ? "Kéo thả JSON hoặc chọn tệp"
              : "Drag and drop a JSON file or click to choose"}
          </p>
          <p className="mt-1 text-[11px] text-slate-400">
            {locale === "vi"
              ? "Hỗ trợ .json — tối đa 20 MB"
              : "Supports .json — up to 20 MB"}
          </p>
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-slate-200/80 bg-slate-50/50 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3 min-w-0">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-100 text-violet-600 shrink-0">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.8"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <span className="block font-bold text-slate-800 text-sm truncate max-w-[180px] sm:max-w-xs" title={selectedFile.name}>
                  {selectedFile.name}
                </span>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span>
                    {locale === "vi" ? "Dung lượng:" : "Size:"}{" "}
                    <strong className="text-slate-700">{formatBytes(selectedFile.size)}</strong>
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-200/60 justify-end">
              <button
                type="button"
                disabled={previewing || importing}
                onClick={clearFile}
                className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer shadow-2xs"
              >
                {locale === "vi" ? "Hủy tệp" : "Clear file"}
              </button>
              <button
                type="button"
                disabled={previewing || importing}
                onClick={() => void handlePreview()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-violet-700 transition-colors disabled:cursor-wait disabled:opacity-70 cursor-pointer"
              >
                {previewing ? (
                  <>
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                    <span>{t.common.loading}</span>
                  </>
                ) : (
                  <>
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    <span>{t.lecturerImport.checkData}</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedFile && previewing && (
        <div className="mt-3 overflow-hidden rounded-xl border border-violet-200 bg-violet-50/60 p-4 transition-all duration-300">
          <div className="flex items-center justify-between text-xs font-semibold text-violet-800">
            <span className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-violet-600"></span>
              </span>
              {locale === "vi" ? "Đang phân tích và kiểm tra tính toàn vẹn dữ liệu..." : "Analyzing and validating dataset structure..."}
            </span>
            <span className="text-violet-600 font-mono text-[11px] font-medium">{locale === "vi" ? "Đang tải" : "Loading"}</span>
          </div>
          <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-violet-200/80">
            <div className="h-full w-2/5 bg-violet-600 rounded-full animate-[pulse_1s_ease-in-out_infinite]" />
          </div>
        </div>
      )}

      {selectionError && (
        <div
          role="alert"
          className="mt-3 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50/80 p-3 text-xs font-semibold text-rose-700 animate-in fade-in duration-200"
        >
          <svg
            className="h-4 w-4 shrink-0 text-rose-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>{selectionError}</span>
        </div>
      )}

      {preview && (
        <div className="mt-4 rounded-xl border border-slate-200/80 bg-white p-4 shadow-2xs transition-all duration-300">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
            {t.lecturerImport.previewTitle}
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            <strong>{preview.filename}</strong> · {preview.dataset.schema_version} ·{" "}
            {preview.dataset.record_count} {locale === "vi" ? "bản ghi" : "records"}
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Stat label={t.lecturerImport.totalRecords} value={preview.summary.total} />
            <Stat label={t.lecturerImport.validRecords} value={preview.summary.valid} variant="emerald" />
            <Stat label={t.lecturerImport.createRecords} value={preview.summary.create} variant="emerald" />
            <Stat label={t.lecturerImport.updateRecords} value={preview.summary.update} variant="amber" />
            <Stat label={t.lecturerImport.unchangedRecords} value={preview.summary.unchanged} variant="slate" />
            <Stat label={locale === "vi" ? "Cảnh báo" : "Warnings"} value={preview.conflicts.length} variant="amber" />
          </dl>
          {preview.conflicts.length > 0 && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              <strong>{locale === "vi" ? "Cảnh báo trùng tên cần kiểm tra" : "Duplicate name warnings"}:</strong> {preview.conflicts.length}
            </div>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              disabled={importing}
              onClick={() => setConfirmOpen(false)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer"
            >
              {t.common.cancel}
            </button>
            <button
              type="button"
              disabled={importing}
              onClick={() => setConfirmOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-violet-700 transition-colors disabled:opacity-50 cursor-pointer"
            >
              {t.lecturerImport.confirmImport}
            </button>
          </div>
        </div>
      )}

      <ConfirmModal
        open={confirmOpen}
        variant="primary"
        loading={importing}
        title={t.lecturerImport.confirmTitle}
        description={t.lecturerImport.confirmMessage}
        confirmLabel={t.lecturerImport.confirmImport}
        cancelLabel={t.common.cancel}
        onConfirm={() => void handleConfirmImport()}
        onCancel={() => {
          if (!importing) setConfirmOpen(false);
        }}
      />
    </section>
  );
});

function Stat({
  label,
  value,
  variant = "slate",
}: {
  label: string;
  value: number;
  variant?: "slate" | "emerald" | "amber" | "rose";
}) {
  const variantClasses: Record<string, string> = {
    slate: "border-slate-200 bg-slate-50/60 text-slate-700",
    emerald: "border-emerald-200 bg-emerald-50/60 text-emerald-700",
    amber: "border-amber-200 bg-amber-50/60 text-amber-700",
    rose: "border-rose-200 bg-rose-50/60 text-rose-700",
  };
  return (
    <div className={`rounded-lg border p-2.5 text-center ${variantClasses[variant]}`}>
      <dt className="text-[10px] font-medium uppercase tracking-wider opacity-70">
        {label}
      </dt>
      <dd className="mt-0.5 text-base font-black">{value}</dd>
    </div>
  );
}

export default LecturerDatasetImportCard;
