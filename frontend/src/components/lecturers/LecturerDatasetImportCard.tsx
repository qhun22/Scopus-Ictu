import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { previewLecturerDataset } from "../../api/lecturerImport";
import { useToast } from "../../contexts/ToastContext";
import { useI18n } from "../../i18n";

export interface DatasetMeta {
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

export interface PreviewSummary {
  total: number;
  valid: number;
  create: number;
  update: number;
  unchanged: number;
  conflicts: number;
}

export interface PreviewConflict {
  record_full_name: string;
  matched_by: string;
  existing_id: string;
  existing_full_name: string;
  existing_email: string | null;
}

export interface PreviewResponse {
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
  clearFile: () => void;
}

export interface LecturerDatasetImportCardProps {
  onPreviewGenerated?: (preview: PreviewResponse, file: File) => void;
  onFileCleared?: () => void;
  onFileSelected?: (file: File) => void;
  isImporting?: boolean;
}

const LecturerDatasetImportCard = forwardRef<
  LecturerDatasetImportCardHandle,
  LecturerDatasetImportCardProps
>(function LecturerDatasetImportCard(
  { onPreviewGenerated, onFileCleared, onFileSelected, isImporting = false },
  ref,
) {
  const { t, locale } = useI18n();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectionError, setSelectionError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [previewing, setPreviewing] = useState(false);

  const clearFile = () => {
    setSelectedFile(null);
    setSelectionError("");
    if (inputRef.current) inputRef.current.value = "";
    onFileCleared?.();
  };

  useImperativeHandle(ref, () => ({
    openFilePicker: () => {
      inputRef.current?.click();
    },
    clearFile: () => {
      clearFile();
    },
  }));

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
      onFileCleared?.();
      return;
    }
    if (file.size === 0) {
      setSelectedFile(null);
      setSelectionError(
        locale === "vi" ? "Tệp rỗng." : "File is empty.",
      );
      onFileCleared?.();
      return;
    }
    setSelectedFile(file);
    setSelectionError("");
    onFileSelected?.(file);
  };

  const handlePreview = async () => {
    if (!selectedFile || previewing || isImporting) return;
    setPreviewing(true);
    try {
      const response = await previewLecturerDataset(selectedFile);
      if (response.conflicts && response.conflicts.length > 0) {
        toast.warning(
          locale === "vi" ? "Cảnh báo trùng tên" : "Duplicate Name Warnings",
          locale === "vi"
            ? `Phát hiện ${response.conflicts.length} bản ghi có tên trùng với cán bộ khác. Các hồ sơ riêng biệt vẫn được lưu trữ đầy đủ.`
            : `${response.conflicts.length} duplicate name candidates detected. Separate records will be retained.`,
        );
      }
      onPreviewGenerated?.(response, selectedFile);
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

  return (
    <section className="flex flex-col h-full rounded-xl border border-slate-200/80 bg-white p-4 sm:p-5 shadow-xs">
      <div className="flex items-center gap-2.5 pb-3.5 border-b border-slate-100">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#3A5FC3]/10 text-[#3A5FC3]">
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
        disabled={isImporting || previewing}
        className="hidden"
        onChange={(event) => selectFile(event.target.files?.[0])}
      />

      {!selectedFile ? (
        <div
          onClick={() => !isImporting && !previewing && inputRef.current?.click()}
          onDragEnter={(event) => {
            event.preventDefault();
            if (!isImporting && !previewing) setDragging(true);
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
              ? "border-[#3A5FC3] bg-[#3A5FC3]/10 scale-[0.99]"
              : "border-slate-200 hover:border-[#3A5FC3]/60 bg-slate-50/40 hover:bg-[#3A5FC3]/5"
          } ${isImporting || previewing ? "cursor-not-allowed opacity-60" : ""}`}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#3A5FC3]/10 text-[#3A5FC3] mb-2.5 shadow-2xs group-hover:scale-110 transition-transform">
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                d="M12 4v16m8-8H4"
              />
            </svg>
          </div>
          <p className="text-xs font-semibold text-slate-700 sm:text-sm group-hover:text-[#3A5FC3] transition-colors">
            {locale === "vi"
              ? "Nhấp hoặc kéo thả tệp JSON vào đây để tải lên"
              : "Click or drag and drop a JSON file here to upload"}
          </p>
          <p className="mt-1 text-[11px] text-slate-400">
            {locale === "vi"
              ? "Hỗ trợ .json — tối đa 20.0 MB"
              : "Supports .json — up to 20.0 MB"}
          </p>
        </div>
      ) : (
        <div className="mt-4 flex flex-1 min-h-44 flex-col justify-center rounded-xl border border-slate-200/80 bg-slate-50/50 p-4">
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
                  <span>•</span>
                  <span>
                    {locale === "vi" ? "Định dạng:" : "Format:"}{" "}
                    <strong className="text-slate-700">JSON</strong>
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-200/60 justify-end">
              <button
                type="button"
                disabled={previewing || isImporting}
                onClick={clearFile}
                className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer shadow-2xs"
              >
                {t.imports.cancelFile}
              </button>
              <button
                type="button"
                disabled={previewing || isImporting}
                onClick={() => void handlePreview()}
                className="inline-flex min-w-28 items-center justify-center gap-1.5 rounded-lg bg-[#3A5FC3] px-3.5 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors disabled:cursor-wait disabled:opacity-70 cursor-pointer"
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
    </section>
  );
});

export default LecturerDatasetImportCard;
