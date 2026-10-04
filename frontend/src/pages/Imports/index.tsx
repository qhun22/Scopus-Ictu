import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ImportConfig,
  ImportStatus,
  ScopusImport,
  archiveImport,
  cancelImport,
  deleteImport,
  restoreImportHistory,
  rollbackLecturerImport,
  getImportConfig,
  getImportDetail,
  getImportHistory,
  uploadScopusCsv,
} from "../../api/imports";
import { ApiError } from "../../api/client";
import { importLecturerDataset } from "../../api/lecturerImport";
import ConfirmModal from "../../components/common/ConfirmModal";
import ModalPortal from "../../components/common/ModalPortal";
import LecturerDatasetImportCard, {
  LecturerDatasetImportCardHandle,
  PreviewResponse,
} from "../../components/lecturers/LecturerDatasetImportCard";
import { useToast } from "../../contexts/ToastContext";
import { useI18n } from "../../i18n";

function replaceToken(template: string, token: string, value: string): string {
  return template.replace(`{${token}}`, value);
}

const badgeClassName =
  "inline-flex h-6 w-32 items-center justify-center rounded-full border px-2.5 text-xs font-bold whitespace-nowrap";
const ACTIVE_STATUSES: ImportStatus[] = ["RECEIVED", "PARSING", "VALIDATED"];

interface DuplicateWarning {
  importId: string;
  filename: string;
  importedAt: string;
}

function errorField(error: ApiError, field: string): string | undefined {
  if (typeof error.body !== "object" || error.body === null) return undefined;
  const value = (error.body as Record<string, unknown>)[field];
  return typeof value === "string" ? value : undefined;
}

function errorNumberField(error: ApiError, field: string): number | undefined {
  if (typeof error.body !== "object" || error.body === null) return undefined;
  const value = (error.body as Record<string, unknown>)[field];
  return typeof value === "number" ? value : undefined;
}

function fatalErrorMessage(summary: Record<string, unknown> | null): string | undefined {
  if (!summary || typeof summary.fatal_error !== "object" || summary.fatal_error === null) return undefined;
  const message = (summary.fatal_error as Record<string, unknown>).message;
  return typeof message === "string" ? message : undefined;
}

export default function ImportsPage() {
  const { t, locale } = useI18n();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const lecturerCardRef = useRef<LecturerDatasetImportCardHandle>(null);

  const [config, setConfig] = useState<ImportConfig | null>(null);
  const [history, setHistory] = useState<ScopusImport[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectionError, setSelectionError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [latestResult, setLatestResult] = useState<ScopusImport | null>(null);
  const [lecturerPreview, setLecturerPreview] = useState<{
    preview: PreviewResponse;
    file: File;
  } | null>(null);
  const [lecturerImporting, setLecturerImporting] = useState(false);
  const [lecturerConfirmOpen, setLecturerConfirmOpen] = useState(false);
  const [activeResultPanel, setActiveResultPanel] = useState<"scopus" | "lecturer_preview" | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState<DuplicateWarning | null>(null);

  // Search & Filter & Pagination states
  const [search, setSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [archiveFilter, setArchiveFilter] = useState<"active" | "archived" | "all">(
    "active",
  );
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(10);

  // Detail Modal states
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<ScopusImport | null>(null);

  // Cancellation
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [itemToCancel, setItemToCancel] = useState<ScopusImport | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  // Safe Delete
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<ScopusImport | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Archive (hide from history)
  const [archiveModalOpen, setArchiveModalOpen] = useState(false);
  const [itemToArchive, setItemToArchive] = useState<ScopusImport | null>(null);
  const [isArchiving, setIsArchiving] = useState(false);

  // Restore archived
  const [restoreModalOpen, setRestoreModalOpen] = useState(false);
  const [itemToRestore, setItemToRestore] = useState<ScopusImport | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);

  // Rollback Lecturer Import
  const [rollbackModalOpen, setRollbackModalOpen] = useState(false);
  const [itemToRollback, setItemToRollback] = useState<ScopusImport | null>(null);
  const [isRollingBack, setIsRollingBack] = useState(false);

  // Blocked Delete Explanation Modal (Scopus in use or Lecturer rollback prerequisite)
  const [blockedDeleteState, setBlockedDeleteState] = useState<{
    item: ScopusImport;
    reason: "SCOPUS_IN_USE" | "LECTURER_NEED_ROLLBACK" | "LECTURER_BLOCKED";
  } | null>(null);

  const numberFormatter = new Intl.NumberFormat(locale === "vi" ? "vi-VN" : "en-US");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [nextConfig, response] = await Promise.all([
        getImportConfig(),
        getImportHistory(archiveFilter !== "active"),
      ]);
      setConfig(nextConfig);
      setHistory(response.items);
    } catch (error: unknown) {
      toast.error(
        t.imports.errorTitle,
        error instanceof ApiError ? error.message : t.imports.loadError,
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [archiveFilter]);

  const hasActiveImports = history.some((item) => ACTIVE_STATUSES.includes(item.status));

  useEffect(() => {
    if (!hasActiveImports) return;
    const poll = () => {
      if (document.visibilityState === "visible") void refreshHistory();
    };
    const timer = window.setInterval(poll, 2000);
    window.addEventListener("focus", poll);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", poll);
    };
  }, [hasActiveImports]);

  useEffect(() => {
    if (!detailOpen || !detail || !ACTIVE_STATUSES.includes(detail.status)) return;
    const pollDetail = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const next = await getImportDetail(detail.id);
        setDetail(next);
        setHistory((current) => current.map((item) => (item.id === next.id ? next : item)));
        setLatestResult((current) => (current?.id === next.id ? next : current));
      } catch {
        // A transient polling failure must not close the detail modal.
      }
    };
    const timer = window.setInterval(() => void pollDetail(), 2000);
    return () => window.clearInterval(timer);
  }, [detail?.id, detail?.status, detailOpen]);

  useEffect(() => {
    if (!detailOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !detailLoading) setDetailOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [detailLoading, detailOpen]);

  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (value: string): string =>
    new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-US", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainder = Math.round(seconds % 60);
    return `${minutes}m ${remainder}s`;
  };

  const getItemWarningCount = (item: ScopusImport): number => {
    if (item.type === "LECTURERS") {
      return (item.lecturer_summary?.warnings ?? item.duplicate_candidates) || 0;
    }
    return item.duplicate_candidates || 0;
  };

  const isWarningStatus = (item: ScopusImport): boolean => {
    if (item.status !== "STAGED" && item.status !== "APPLIED" && item.status !== "IMPORTED") {
      return false;
    }
    return getItemWarningCount(item) > 0;
  };

  const isInUse = (item: ScopusImport): boolean => {
    if (item.type === "LECTURERS") return false;
    return Boolean(item.in_use);
  };

  const statusLabel = (item: ScopusImport): string => {
    if (ACTIVE_STATUSES.includes(item.status)) {
      return `${t.imports.inProgress} · ${item.progress_percent}%`;
    }
    if (item.status === "FAILED") return t.imports.failed;
    if (item.status === "CANCELLED") {
      return item.type === "LECTURERS"
        ? (locale === "vi" ? "Đã hoàn tác" : "Rolled back")
        : t.imports.cancelled;
    }
    if (item.type === "LECTURERS") {
      if (isWarningStatus(item)) {
        return locale === "vi" ? "Cảnh báo" : "Warning";
      }
      return item.failed_records > 0 ? t.imports.completedWithErrors : t.imports.completed;
    }
    // Scopus imports
    if (item.status === "APPLIED" || isInUse(item)) {
      return locale === "vi" ? "Được sử dụng" : "In Use";
    }
    if (item.status === "STAGED") {
      if (isWarningStatus(item)) {
        return locale === "vi" ? "Cảnh báo" : "Warning";
      }
      return locale === "vi" ? "Chờ chuẩn hóa" : "Awaiting normalization";
    }
    return t.imports.completed;
  };

  const renderStatusBadge = (item: ScopusImport) => {
    const status = item.status;
    let colorClass = "border-slate-200 bg-slate-50 text-slate-600";
    if (item.type !== "LECTURERS") {
      if (status === "APPLIED" || isInUse(item)) {
        colorClass = "border-violet-200 bg-violet-50 text-violet-700";
      } else if (status === "STAGED") {
        if (isWarningStatus(item)) {
          colorClass = "border-amber-300 bg-amber-50 text-amber-700";
        } else {
          colorClass = "border-blue-200 bg-blue-50 text-[#3A5FC3]";
        }
      } else if (status === "FAILED") {
        colorClass = "border-rose-200 bg-rose-50 text-rose-700";
      } else if (status === "CANCELLED") {
        colorClass = "border-slate-200 bg-slate-100 text-slate-600";
      } else {
        colorClass = "border-blue-200 bg-blue-50 text-[#3A5FC3]";
      }
    } else {
      if (status === "IMPORTED" || status === "STAGED" || status === "APPLIED") {
        if (isWarningStatus(item)) {
          colorClass = "border-amber-300 bg-amber-50 text-amber-700";
        } else {
          colorClass = "border-emerald-200 bg-emerald-50 text-emerald-700";
        }
      } else if (status === "FAILED") {
        colorClass = "border-rose-200 bg-rose-50 text-rose-700";
      } else if (status === "CANCELLED") {
        colorClass = "border-slate-200 bg-slate-100 text-slate-600";
      } else {
        colorClass = "border-blue-200 bg-blue-50 text-[#3A5FC3]";
      }
    }

    return (
      <span className={`${badgeClassName} ${colorClass}`}>
        {statusLabel(item)}
      </span>
    );
  };

  const renderTableStatusBadge = (item: ScopusImport) => {
    if (item.archived) {
      return (
        <span
          title={locale === "vi" ? "Đã ẩn khỏi lịch sử" : "Hidden from history"}
          className={`${badgeClassName} border-slate-200 bg-slate-100 text-slate-600`}
        >
          {locale === "vi" ? "Đã ẩn" : "Archived"}
        </span>
      );
    }

    return renderStatusBadge(item);
  };

  const ingestionStatusLabel = (item: ScopusImport): string => {
    if (ACTIVE_STATUSES.includes(item.status)) {
      return `${t.imports.inProgress} · ${item.progress_percent}%`;
    }
    if (item.status === "FAILED") return t.imports.failed;
    if (item.status === "CANCELLED") {
      return item.type === "LECTURERS"
        ? (locale === "vi" ? "Đã hoàn tác" : "Rolled back")
        : t.imports.cancelled;
    }
    if (item.failed_records > 0) {
      return locale === "vi" ? "Tiếp nhận hoàn tất (có lỗi)" : "Ingestion complete with errors";
    }
    return locale === "vi" ? "Tiếp nhận hoàn tất" : "Ingestion complete";
  };

  const renderIngestionBadge = (item: ScopusImport) => {
    if (ACTIVE_STATUSES.includes(item.status)) {
      return (
        <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-[#3A5FC3]">
          {t.imports.inProgress} · {item.progress_percent}%
        </span>
      );
    }
    if (item.status === "FAILED") {
      return (
        <span className="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-xs font-bold text-rose-700">
          {t.imports.failed}
        </span>
      );
    }
    if (item.status === "CANCELLED") {
      return (
        <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-600">
          {item.type === "LECTURERS" ? (locale === "vi" ? "Đã hoàn tác" : "Rolled back") : t.imports.cancelled}
        </span>
      );
    }
    if (isWarningStatus(item)) {
      return (
        <span className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-xs font-bold text-amber-700">
          {locale === "vi" ? "Cảnh báo" : "Warning"}
        </span>
      );
    }
    if (item.failed_records > 0) {
      return (
        <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
          {locale === "vi" ? "Đã tiếp nhận (có lỗi)" : "Ingested with errors"}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
        {locale === "vi" ? "Đã tiếp nhận" : "Ingestion complete"}
      </span>
    );
  };

  const renderNormalizationBadge = (item: ScopusImport) => {
    const n = item.normalization;
    if (n && n.status === "COMPLETED") {
      return (
        <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
          {locale === "vi" ? "Hoàn thành" : "Completed"}
        </span>
      );
    }
    if (n && n.status === "NORMALIZING") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-[#3A5FC3]">
          <span className="h-2 w-2 animate-spin rounded-full border-2 border-[#3A5FC3] border-t-transparent" />
          {locale === "vi" ? "Đang xử lý" : "Processing"} ({n.progress_percent}%)
        </span>
      );
    }
    if (n && n.status === "FAILED") {
      return (
        <span className="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-xs font-bold text-rose-700">
          {locale === "vi" ? "Lỗi chuẩn hóa" : "Normalization failed"}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-[#3A5FC3]">
        {locale === "vi" ? "Chờ chuẩn hóa" : "Awaiting normalization"}
      </span>
    );
  };

  const renderTypeBadge = (type?: string) => {
    if (type === "LECTURERS") {
      return (
        <span className={`${badgeClassName} border-violet-200 bg-violet-50 text-violet-700`}>
          {locale === "vi" ? "Giảng viên ICTU" : "ICTU Lecturers"}
        </span>
      );
    }
    return (
      <span className={`${badgeClassName} border-blue-200 bg-blue-50 text-[#3A5FC3]`}>
        Scopus
      </span>
    );
  };

  const renderUserBadge = (name: string | null) => {
    if (!name || name === "Không xác định") {
      return (
        <span className={`${badgeClassName} border-slate-200 bg-slate-50 font-normal text-slate-400`}>
          {locale === "vi" ? "Không xác định" : "Unknown"}
        </span>
      );
    }
    return (
      <span
        title={name}
        className={`${badgeClassName} border-slate-200 bg-slate-50/90 font-medium text-slate-700`}
      >
        <span className="truncate max-w-[120px]">{name}</span>
      </span>
    );
  };

  const selectFile = (file: File | undefined) => {
    if (!file || uploading) return;
    const extension = file.name.includes(".")
      ? `.${file.name.split(".").pop()?.toLowerCase()}`
      : "";
    const supported = config?.supported_extensions.map((item) => item.toLowerCase()) ?? [".csv"];
    if (!supported.includes(extension)) {
      setSelectedFile(null);
      setSelectionError(t.imports.invalidExtension);
      return;
    }
    if (file.size === 0) {
      setSelectedFile(null);
      setSelectionError(t.imports.emptyFile);
      return;
    }
    if (config && file.size > config.max_bytes) {
      setSelectedFile(null);
      setSelectionError(t.imports.tooLarge);
      return;
    }
    setSelectedFile(file);
    setSelectionError("");
    setDuplicateWarning(null);
  };

  const clearFile = () => {
    if (uploading) return;
    setSelectedFile(null);
    setSelectionError("");
    setDuplicateWarning(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const refreshHistory = async () => {
    try {
      const response = await getImportHistory(archiveFilter !== "active");
      setHistory(response.items);
      setLatestResult((current) => {
        if (!current) return current;
        return response.items.find((item) => item.id === current.id) ?? current;
      });
    } catch {
      // non-critical error
    }
  };

  const startImport = async (allowDuplicate = false) => {
    if (!selectedFile || uploading) return;
    setUploading(true);
    setSelectionError("");
    try {
      const result = await uploadScopusCsv(selectedFile, allowDuplicate);
      setLatestResult(result);
      setActiveResultPanel("scopus");
      setDuplicateWarning(null);
      setSelectedFile(null);
      if (inputRef.current) inputRef.current.value = "";
      await refreshHistory();
      toast.success(
        t.imports.successTitle,
        replaceToken(
          t.imports.successMessage,
          "count",
          numberFormatter.format(result.total_records),
        ),
      );
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "DUPLICATE_IMPORT_CONFIRMATION_REQUIRED") {
        const importId = errorField(error, "duplicate_of_import_id");
        const importedAt = errorField(error, "duplicate_imported_at");
        const filename = errorField(error, "duplicate_filename");
        if (importId && importedAt && filename) {
          setDuplicateWarning({ importId, importedAt, filename });
          return;
        }
      }
      if (error instanceof ApiError && error.code === "IMPORT_ALREADY_PROCESSING") {
        const existingId = errorField(error, "existing_import_id");
        if (existingId) {
          try {
            const existing = await getImportDetail(existingId);
            setDetail(existing);
            setDetailOpen(true);
          } catch {
            // The conflict itself remains the actionable message.
          }
        }
      }
      const message =
        error instanceof ApiError
          ? error.code === "IMPORT_FILE_TOO_LARGE"
            ? t.imports.tooLarge
            : error.code === "UNSUPPORTED_IMPORT_FORMAT"
              ? t.imports.invalidExtension
              : error.code === "EMPTY_IMPORT_FILE"
                ? t.imports.emptyFile
                : error.message
          : t.imports.loadError;
      toast.error(t.imports.errorTitle, message);
    } finally {
      setUploading(false);
    }
  };

  const handleConfirmLecturerImport = async () => {
    if (!lecturerPreview?.file || lecturerImporting) return;
    setLecturerImporting(true);
    try {
      const result = await importLecturerDataset(lecturerPreview.file);
      setLecturerConfirmOpen(false);
      setLecturerPreview(null);
      if (activeResultPanel === "lecturer_preview") {
        setActiveResultPanel(null);
      }
      lecturerCardRef.current?.clearFile();
      toast.success(
        t.lecturerImport.importSuccessTitle,
        t.lecturerImport.importSuccessMessage.replace(
          "{count}",
          String(result.summary.total),
        ),
      );
      await fetchData();
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
      setLecturerImporting(false);
    }
  };

  const openDetail = async (item: ScopusImport) => {
    setDetail(item);
    setDetailOpen(true);
    setDetailLoading(true);
    try {
      const freshDetail = await getImportDetail(item.id);
      setDetail(freshDetail);
    } catch (error: unknown) {
      toast.error(
        t.imports.errorTitle,
        error instanceof ApiError ? error.message : t.imports.loadError,
      );
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleOpenCancelModal = (item: ScopusImport) => {
    if (!ACTIVE_STATUSES.includes(item.status)) return;
    setItemToCancel(item);
    setCancelModalOpen(true);
  };

  const handleConfirmCancel = async () => {
    if (!itemToCancel) return;
    setIsCancelling(true);
    try {
      const cancelled = await cancelImport(itemToCancel.id);
      toast.success(
        t.imports.cancelled,
        t.imports.cancelSuccess,
      );
      setCancelModalOpen(false);
      setItemToCancel(null);
      setDetail((current) => (current?.id === cancelled.id ? cancelled : current));
      setLatestResult((current) => (current?.id === cancelled.id ? cancelled : current));
      await refreshHistory();
    } catch (error: unknown) {
      toast.error(
        t.imports.cancelFailed,
        error instanceof ApiError ? error.message : t.imports.cancelFailed,
      );
    } finally {
      setIsCancelling(false);
    }
  };

  const handleDeleteIntent = (item: ScopusImport) => {
    if (ACTIVE_STATUSES.includes(item.status) || item.archived) return;

    if (item.type === "LECTURERS") {
      if (item.status !== "CANCELLED") {
        setBlockedDeleteState({ item, reason: "LECTURER_NEED_ROLLBACK" });
        return;
      }
      if (item.can_delete === false) {
        setBlockedDeleteState({ item, reason: "LECTURER_BLOCKED" });
        return;
      }
      setItemToDelete(item);
      setDeleteModalOpen(true);
      return;
    }

    // Scopus / default import
    if (isInUse(item) || item.can_delete === false) {
      setBlockedDeleteState({ item, reason: "SCOPUS_IN_USE" });
      return;
    }

    setItemToDelete(item);
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!itemToDelete) return;
    setIsDeleting(true);
    try {
      await deleteImport(itemToDelete.id);
      toast.success(
        itemToDelete.type === "LECTURERS"
          ? (locale === "vi" ? "Đã xóa lịch sử nhập dữ liệu" : "Import history deleted")
          : (locale === "vi" ? "Đã xóa đợt nhập" : "Import deleted"),
        itemToDelete.type === "LECTURERS"
          ? (locale === "vi"
              ? `Đã xóa ${itemToDelete.file_name} khỏi lịch sử nhập dữ liệu.`
              : `Removed ${itemToDelete.file_name} from import history.`)
          : (locale === "vi"
              ? `Đã xóa đợt nhập ${itemToDelete.file_name}`
              : `Import ${itemToDelete.file_name} has been deleted.`),
      );
      setDeleteModalOpen(false);
      setItemToDelete(null);
      if (detail && detail.id === itemToDelete.id) {
        setDetailOpen(false);
        setDetail(null);
      }
      await refreshHistory();
    } catch (error: unknown) {
      if (
        error instanceof ApiError &&
        (error.code === "LECTURER_IMPORT_IN_USE" ||
          error.code === "IMPORT_IN_USE" ||
          error.status === 409)
      ) {
        const linkedCount = errorNumberField(error, "linked_accounts");
        const pubLinks = errorNumberField(error, "publication_source_links");
        const authLinks = errorNumberField(error, "author_variant_links");
        const totalLinks = (pubLinks ?? 0) + (authLinks ?? 0);
        const msg = linkedCount
          ? (locale === "vi"
              ? `Có ${linkedCount} hồ sơ trong đợt nhập đang được liên kết với tài khoản hệ thống. Vui lòng xử lý các liên kết trước.`
              : `There are ${linkedCount} profiles in this import linked to system accounts. Please resolve linkages first.`)
          : totalLinks > 0
            ? (locale === "vi"
                ? `Dữ liệu nguồn được sử dụng ở bước xử lý tiếp theo (${pubLinks ?? 0} liên kết công bố, ${authLinks ?? 0} biến thể tên). Vui lòng chọn "Ẩn khỏi lịch sử" thay vì xóa.`
                : `Source data is referenced downstream (${pubLinks ?? 0} publication links, ${authLinks ?? 0} author variants). Use "Hide from history" instead of deleting.`)
            : (error.message ||
              (locale === "vi"
                ? "Dữ liệu từ đợt nhập này được hệ thống sử dụng."
                : "Data from this import is currently in use by the system."));
        toast.error(
          locale === "vi" ? "Không thể xóa đợt nhập" : "Cannot delete import",
          msg,
        );
      } else {
        toast.error(
          locale === "vi" ? "Lỗi xóa" : "Delete error",
          error instanceof ApiError ? error.message : "Unable to complete action.",
        );
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const handleOpenRollbackModal = (item: ScopusImport) => {
    setItemToRollback(item);
    setRollbackModalOpen(true);
  };

  const handleConfirmRollback = async () => {
    if (!itemToRollback) return;
    setIsRollingBack(true);
    try {
      await rollbackLecturerImport(itemToRollback.id);
      toast.success(
        locale === "vi" ? "Hoàn tác thành công" : "Rollback successful",
        locale === "vi"
          ? `Đã hoàn tác và gỡ các giảng viên được tạo bởi đợt nhập ${itemToRollback.file_name}`
          : `Rolled back lecturers created by ${itemToRollback.file_name}.`,
      );
      setRollbackModalOpen(false);
      setItemToRollback(null);
      if (detail && detail.id === itemToRollback.id) {
        try {
          const updatedDetail = await getImportDetail(itemToRollback.id);
          setDetail(updatedDetail);
        } catch {
          // ignore
        }
      }
      await refreshHistory();
    } catch (error: unknown) {
      if (
        error instanceof ApiError &&
        (error.code === "LECTURER_IMPORT_IN_USE" ||
          error.code === "IMPORT_IN_USE" ||
          error.status === 409)
      ) {
        const linkedCount = errorNumberField(error, "linked_accounts");
        const msg = linkedCount
          ? (locale === "vi"
              ? `Có ${linkedCount} hồ sơ trong đợt nhập đang được liên kết với tài khoản hệ thống. Vui lòng gỡ liên kết trước khi hoàn tác.`
              : `There are ${linkedCount} profiles in this import linked to system accounts. Please unlink before rollback.`)
          : (error.message ||
            (locale === "vi"
              ? "Dữ liệu từ đợt nhập này đang được hệ thống sử dụng."
              : "Data from this import is currently in use by the system."));
        toast.error(
          locale === "vi" ? "Không thể hoàn tác đợt nhập" : "Cannot rollback import",
          msg,
        );
      } else {
        toast.error(
          locale === "vi" ? "Lỗi hoàn tác" : "Rollback error",
          error instanceof ApiError ? error.message : "Unable to rollback.",
        );
      }
    } finally {
      setIsRollingBack(false);
    }
  };

  const handleOpenArchiveModal = (item: ScopusImport) => {
    if (item.archived) return;
    setItemToArchive(item);
    setArchiveModalOpen(true);
  };

  const handleConfirmArchive = async () => {
    if (!itemToArchive) return;
    setIsArchiving(true);
    try {
      const updated = await archiveImport(itemToArchive.id);
      toast.success(
        locale === "vi" ? "Đã ẩn khỏi lịch sử" : "Hidden from history",
        locale === "vi"
          ? `Đã ẩn ${updated.file_name} khỏi danh sách lịch sử.`
          : `${updated.file_name} is no longer visible in the default history list.`,
      );
      setArchiveModalOpen(false);
      setItemToArchive(null);
      if (detail && detail.id === updated.id) {
        setDetail(updated);
      }
      // Refresh using the current filter (the item may be gone from "active" view).
      await refreshHistory();
    } catch (error: unknown) {
      toast.error(
        locale === "vi" ? "Không thể ẩn đợt nhập" : "Cannot hide import",
        error instanceof ApiError ? error.message : (locale === "vi" ? "Lỗi không xác định." : "Unknown error."),
      );
    } finally {
      setIsArchiving(false);
    }
  };

  const handleOpenRestoreModal = (item: ScopusImport) => {
    if (!item.archived) return;
    setItemToRestore(item);
    setRestoreModalOpen(true);
  };

  const handleConfirmRestore = async () => {
    if (!itemToRestore) return;
    setIsRestoring(true);
    try {
      const updated = await restoreImportHistory(itemToRestore.id);
      toast.success(
        locale === "vi" ? "Đã khôi phục hiển thị" : "Visibility restored",
        locale === "vi"
          ? `${updated.file_name} đã xuất hiện trở lại trong lịch sử.`
          : `${updated.file_name} is visible in history again.`,
      );
      setRestoreModalOpen(false);
      setItemToRestore(null);
      if (detail && detail.id === updated.id) {
        setDetail(updated);
      }
      await refreshHistory();
    } catch (error: unknown) {
      toast.error(
        locale === "vi" ? "Không thể khôi phục" : "Cannot restore",
        error instanceof ApiError ? error.message : (locale === "vi" ? "Lỗi không xác định." : "Unknown error."),
      );
    } finally {
      setIsRestoring(false);
    }
  };

  const viewDuplicateImport = async () => {
    if (!duplicateWarning) return;
    try {
      const previous = await getImportDetail(duplicateWarning.importId);
      setDetail(previous);
      setDetailOpen(true);
    } catch (error: unknown) {
      toast.error(t.imports.errorTitle, error instanceof ApiError ? error.message : t.imports.loadError);
    }
  };

  const handleHeaderAddClick = () => {
    if (uploading) return;
    inputRef.current?.click();
  };

  // KPI Calculations
  const countTotal = history.length;
  const countWarning = history.filter((item) => isWarningStatus(item)).length;
  const countSuccess = history.filter(
    (item) =>
      (item.status === "STAGED" || item.status === "APPLIED" || item.status === "IMPORTED") &&
      !isWarningStatus(item),
  ).length;
  const countProcessing = history.filter((item) =>
    ["RECEIVED", "PARSING", "VALIDATED"].includes(item.status),
  ).length;
  const countFailed = history.filter(
    (item) => item.status === "FAILED" || item.status === "CANCELLED",
  ).length;

  // Filter & Pagination calculations
  const filteredHistory = history.filter((item) => {
    const q = search.trim().toLowerCase();
    const matchesSearch =
      !q ||
      item.file_name.toLowerCase().includes(q) ||
      (item.performed_by && item.performed_by.toLowerCase().includes(q)) ||
      item.id.toLowerCase().includes(q) ||
      (item.type && item.type.toLowerCase().includes(q));

    let matchesStatus = true;
    if (statusFilter === "COMPLETED") {
      matchesStatus =
        (item.status === "STAGED" || item.status === "APPLIED" || item.status === "IMPORTED") &&
        !isWarningStatus(item);
    } else if (statusFilter === "WARNING") {
      matchesStatus = isWarningStatus(item);
    } else if (statusFilter === "PROCESSING") {
      matchesStatus = ["RECEIVED", "PARSING", "VALIDATED"].includes(item.status);
    } else if (statusFilter === "FAILED") {
      matchesStatus = item.status === "FAILED" || item.status === "CANCELLED";
    }

    return matchesSearch && matchesStatus;
  });

  const totalPages = Math.max(1, Math.ceil(filteredHistory.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const paginatedHistory = filteredHistory.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );

  const maxSize = config ? formatBytes(config.max_bytes) : "20.0 MB";

  return (
    <>
      {/* Hidden File Input — kept outside app-page-container so its
          space-y children start at the correct vertical position. */}
      <input
        ref={inputRef}
        type="file"
        accept={(config?.supported_extensions ?? [".csv"]).join(",")}
        disabled={uploading}
        className="hidden"
        onChange={(event) => selectFile(event.target.files?.[0])}
      />

      <div className="app-page-container space-y-4 sm:space-y-5">

      {/* Header Title Section with '+ Thêm tệp Scopus' Button */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-800 sm:text-2xl">
            {t.imports.title}
          </h1>
          <p className="text-xs text-slate-500 sm:text-sm">
            {t.imports.subtitle}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={uploading}
            onClick={handleHeaderAddClick}
            className="inline-flex min-w-36 items-center justify-center gap-1.5 rounded-lg bg-[#3A5FC3] px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors cursor-pointer disabled:opacity-50"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M12 4v16m8-8H4" />
            </svg>
            <span>{t.imports.addImport}</span>
          </button>

          <button
            type="button"
            disabled={uploading}
            onClick={() => lecturerCardRef.current?.openFilePicker()}
            className="inline-flex min-w-36 items-center justify-center gap-1.5 rounded-lg bg-[#3A5FC3] px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors cursor-pointer disabled:opacity-50"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M12 4v16m8-8H4" />
            </svg>
            <span>{t.imports.addLecturers}</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4">
        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">
            {locale === "vi" ? "Tổng đợt nhập" : "Total Imports"}
          </span>
          <p className="mt-1 text-2xl font-black text-slate-800">
            {numberFormatter.format(countTotal)}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-emerald-600">
            {locale === "vi" ? "Thành công" : "Completed"}
          </span>
          <p className="mt-1 text-2xl font-black text-emerald-600">
            {numberFormatter.format(countSuccess)}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-amber-600">
            {locale === "vi" ? "Cảnh báo" : "Warnings"}
          </span>
          <p className="mt-1 text-2xl font-black text-amber-600">
            {numberFormatter.format(countWarning)}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-blue-600">
            {locale === "vi" ? "Đang xử lý" : "Processing"}
          </span>
          <p className="mt-1 text-2xl font-black text-[#3A5FC3]">
            {numberFormatter.format(countProcessing)}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs col-span-2 sm:col-span-1">
          <span className="text-xs font-medium text-rose-600">
            {locale === "vi" ? "Lỗi / Đã hủy" : "Failed / Rolled back"}
          </span>
          <p className="mt-1 text-2xl font-black text-rose-600">
            {numberFormatter.format(countFailed)}
          </p>
        </div>
      </div>

      {/* Import Boxes Grid: 1 row, 2 boxes (1:1 ratio) - Left: Scopus CSV, Right: Lecturer JSON */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5 items-stretch">
        {/* Left Box: Tải tệp Scopus */}
        <section className="flex flex-col h-full rounded-xl border border-slate-200/80 bg-white p-4 sm:p-5 shadow-xs">
          <div className="flex items-center gap-2.5 pb-3.5 border-b border-slate-100">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#3A5FC3]/10 text-[#3A5FC3]">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">
                {t.imports.uploadTitle}
              </h2>
              <p className="text-xs text-slate-500">
                {t.imports.uploadSubtitle}
              </p>
            </div>
          </div>

          {!selectedFile ? (
            <div
              onClick={() => !uploading && inputRef.current?.click()}
              onDragEnter={(event) => {
                event.preventDefault();
                if (!uploading) setDragging(true);
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
              } ${uploading ? "cursor-not-allowed opacity-60" : ""}`}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#3A5FC3]/10 text-[#3A5FC3] mb-2.5 shadow-2xs group-hover:scale-110 transition-transform">
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6H16a5 5 0 011 9.9M12 12v9m0-9l-3 3m3-3l3 3" />
                </svg>
              </div>
              <p className="text-xs font-semibold text-slate-700 sm:text-sm group-hover:text-[#3A5FC3] transition-colors">
                {dragging
                  ? t.imports.dragActivePrompt
                  : locale === "vi"
                    ? "Nhấp hoặc kéo thả tệp CSV vào đây để tải lên"
                    : "Click or drag and drop a CSV file here to upload"}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                {replaceToken(t.imports.supportedHint, "size", maxSize)}
              </p>
            </div>
          ) : (
            <div className="mt-4 flex flex-1 min-h-44 flex-col justify-center rounded-xl border border-slate-200/80 bg-slate-50/50 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100/80 text-[#3A5FC3] shrink-0">
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div className="min-w-0 flex-1">
                    <span className="block font-bold text-slate-800 text-sm truncate max-w-[180px] sm:max-w-xs" title={selectedFile.name}>
                      {selectedFile.name}
                    </span>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span>{locale === "vi" ? "Dung lượng:" : "Size:"} <strong className="text-slate-700">{formatBytes(selectedFile.size)}</strong></span>
                      <span>•</span>
                      <span>{locale === "vi" ? "Định dạng:" : "Format:"} <strong className="text-slate-700">CSV</strong></span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-200/60 justify-end">
                  <button
                    type="button"
                    disabled={uploading}
                    onClick={clearFile}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer shadow-2xs"
                  >
                    {t.imports.cancelFile}
                  </button>
                  <button
                    type="button"
                    disabled={uploading}
                    onClick={() => void startImport()}
                    className="inline-flex min-w-28 items-center justify-center gap-1.5 rounded-lg bg-[#3A5FC3] px-3.5 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors disabled:cursor-wait disabled:opacity-70 cursor-pointer"
                  >
                    {uploading ? (
                      <>
                        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                        <span>{t.imports.processing}</span>
                      </>
                    ) : (
                      <>
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                        </svg>
                        <span>{t.imports.startImport}</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {selectionError && (
            <div role="alert" className="mt-3 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50/80 p-3 text-xs font-semibold text-rose-700">
              <svg className="h-4 w-4 shrink-0 text-rose-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{selectionError}</span>
            </div>
          )}

          {duplicateWarning && selectedFile && (
            <div role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-900">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 flex-1">
                  <p className="font-bold text-amber-900">{t.imports.duplicateTitle}</p>
                  <p className="mt-0.5 text-amber-800">
                    {t.imports.duplicateMessage} <strong className="text-amber-950">{duplicateWarning.filename}</strong> · {formatDate(duplicateWarning.importedAt)}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-amber-200/60 justify-end">
                  <button
                    type="button"
                    disabled={uploading}
                    onClick={() => void viewDuplicateImport()}
                    className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-800 hover:bg-amber-100 transition-colors disabled:opacity-50 cursor-pointer shadow-2xs"
                  >
                    {t.imports.viewPrevious}
                  </button>
                  <button
                    type="button"
                    disabled={uploading}
                    onClick={() => void startImport(true)}
                    className="inline-flex items-center justify-center rounded-lg bg-amber-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-amber-700 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {t.imports.importAnyway}
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Right Box: Dữ liệu giảng viên ICTU */}
        <LecturerDatasetImportCard
          ref={lecturerCardRef}
          isImporting={lecturerImporting}
          onPreviewGenerated={(preview, file) => {
            setLecturerPreview({ preview, file });
            setActiveResultPanel("lecturer_preview");
          }}
          onFileCleared={() => {
            setLecturerPreview(null);
            if (activeResultPanel === "lecturer_preview") {
              setActiveResultPanel(null);
            }
          }}
          onFileSelected={() => {
            setLecturerPreview(null);
            if (activeResultPanel === "lecturer_preview") {
              setActiveResultPanel(null);
            }
          }}
        />
      </div>

      {/* Unified Result Panel: Shows most recently produced result (Lecturer JSON validation or Scopus CSV latest result) */}
      {activeResultPanel === "lecturer_preview" && lecturerPreview ? (
        <section className="rounded-xl border border-blue-200 bg-blue-50/40 p-4 sm:p-5 shadow-xs animate-in fade-in duration-200">
          <div className="flex items-center justify-between pb-2.5 border-b border-blue-100">
            <div className="flex items-center gap-2 min-w-0">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-violet-100 text-violet-700 shrink-0">
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-blue-800 shrink-0">
                {t.lecturerImport.previewTitle}
              </h2>
              <span className="inline-flex items-center rounded-md border border-violet-200 bg-violet-100/60 px-2 py-0.5 text-[10px] font-semibold text-violet-700 shrink-0">
                {locale === "vi" ? "Dữ liệu giảng viên ICTU" : "ICTU Lecturer JSON"}
              </span>
              <span className="text-xs text-slate-500 font-medium truncate hidden sm:inline" title={lecturerPreview.preview.filename}>
                {lecturerPreview.preview.filename}
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                setLecturerPreview(null);
                setActiveResultPanel(null);
              }}
              className="text-blue-600 hover:text-blue-800 text-xs font-medium cursor-pointer p-1"
              aria-label={t.imports.close}
            >
              ✕
            </button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
            <div className="rounded-lg bg-white/80 border border-blue-100 p-3 shadow-2xs">
              <p className="text-xs font-medium text-slate-500">{t.lecturerImport.totalRecords}</p>
              <p className="mt-0.5 text-xl font-black text-slate-800">
                {numberFormatter.format(lecturerPreview.preview.summary.total)}
              </p>
            </div>
            <div className="rounded-lg bg-white/80 border border-blue-100 p-3 shadow-2xs">
              <p className="text-xs font-medium text-emerald-600">{t.lecturerImport.validRecords}</p>
              <p className="mt-0.5 text-xl font-black text-emerald-600">
                {numberFormatter.format(lecturerPreview.preview.summary.valid)}
              </p>
            </div>
            <div className="rounded-lg bg-white/80 border border-blue-100 p-3 shadow-2xs">
              <p className="text-xs font-medium text-blue-600">{t.lecturerImport.createRecords}</p>
              <p className="mt-0.5 text-xl font-black text-blue-600">
                {numberFormatter.format(lecturerPreview.preview.summary.create)}
              </p>
            </div>
            <div className="rounded-lg bg-white/80 border border-blue-100 p-3 shadow-2xs">
              <p className="text-xs font-medium text-amber-600">{t.lecturerImport.updateRecords}</p>
              <p className="mt-0.5 text-xl font-black text-amber-600">
                {numberFormatter.format(lecturerPreview.preview.summary.update)}
              </p>
            </div>
            <div className="rounded-lg bg-white/80 border border-blue-100 p-3 shadow-2xs">
              <p className="text-xs font-medium text-slate-500">{t.lecturerImport.unchangedRecords}</p>
              <p className="mt-0.5 text-xl font-black text-slate-600">
                {numberFormatter.format(lecturerPreview.preview.summary.unchanged)}
              </p>
            </div>
            <div className="rounded-lg bg-white/80 border border-blue-100 p-3 shadow-2xs">
              <p className="text-xs font-medium text-rose-600">{locale === "vi" ? "Cảnh báo" : "Warnings"}</p>
              <p className="mt-0.5 text-xl font-black text-rose-600">
                {numberFormatter.format(lecturerPreview.preview.summary.conflicts)}
              </p>
            </div>
          </div>

          {lecturerPreview.preview.conflicts.length > 0 && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50/80 p-3 text-xs text-amber-900">
              <div className="flex items-center gap-2 font-bold">
                <svg className="h-4 w-4 shrink-0 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>
                  {locale === "vi"
                    ? `Phát hiện ${lecturerPreview.preview.conflicts.length} cảnh báo trùng tên cán bộ (hệ thống vẫn lưu trữ riêng biệt):`
                    : `${lecturerPreview.preview.conflicts.length} duplicate name warnings detected (retained separately):`}
                </span>
              </div>
              <ul className="mt-2 list-disc list-inside space-y-0.5 text-slate-700 max-h-28 overflow-y-auto">
                {lecturerPreview.preview.conflicts.map((c, i) => (
                  <li key={i}>
                    <strong>{c.record_full_name}</strong> {locale === "vi" ? "trùng tên với" : "matches name of"} <strong>{c.existing_full_name}</strong> {c.existing_email ? `(${c.existing_email})` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-3.5 flex flex-wrap items-center justify-end gap-2 pt-3 border-t border-blue-100">
            <button
              type="button"
              disabled={lecturerImporting}
              onClick={() => {
                setLecturerPreview(null);
                setActiveResultPanel(null);
              }}
              className="rounded-lg border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer shadow-2xs"
            >
              {t.common.cancel}
            </button>
            <button
              type="button"
              disabled={lecturerImporting || lecturerPreview.preview.summary.valid === 0}
              onClick={() => setLecturerConfirmOpen(true)}
              className="inline-flex min-w-28 items-center justify-center gap-1.5 rounded-lg bg-[#3A5FC3] px-4 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors disabled:cursor-wait disabled:opacity-70 cursor-pointer"
            >
              {lecturerImporting ? (
                <>
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  <span>{t.imports.processing}</span>
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                  <span>{t.lecturerImport.confirmImport}</span>
                </>
              )}
            </button>
          </div>
        </section>
      ) : (activeResultPanel === "scopus" || (!activeResultPanel && latestResult)) && latestResult ? (
        <section className="rounded-xl border border-blue-200 bg-blue-50/40 p-4 sm:p-5 shadow-xs animate-in fade-in duration-200">
          <div className="flex items-center justify-between pb-2.5 border-b border-blue-100">
            <div className="flex items-center gap-2 min-w-0">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-[#3A5FC3] shrink-0">
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-blue-800 shrink-0">
                {t.imports.latestResult}
              </h2>
              <span className="inline-flex items-center rounded-md border border-blue-200 bg-blue-100/60 px-2 py-0.5 text-[10px] font-semibold text-[#3A5FC3] shrink-0">
                Scopus CSV
              </span>
              <span className="text-xs text-slate-500 font-medium truncate hidden sm:inline" title={latestResult.file_name}>
                {latestResult.file_name}
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                setLatestResult(null);
                if (activeResultPanel === "scopus") setActiveResultPanel(null);
              }}
              className="text-blue-600 hover:text-blue-800 text-xs font-medium cursor-pointer p-1"
              aria-label={t.imports.close}
            >
              ✕
            </button>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-white/80 border border-blue-100 p-3 shadow-2xs">
              <p className="text-xs font-medium text-slate-500">{t.imports.totalRecords}</p>
              <p className="mt-0.5 text-xl font-black text-slate-800">{numberFormatter.format(latestResult.total_records)}</p>
            </div>
            <div className="rounded-lg bg-white/80 border border-blue-100 p-3 shadow-2xs">
              <p className="text-xs font-medium text-emerald-600">{t.imports.importedRecords}</p>
              <p className="mt-0.5 text-xl font-black text-emerald-600">{numberFormatter.format(latestResult.imported_records)}</p>
            </div>
            <div className="rounded-lg bg-white/80 border border-blue-100 p-3 shadow-2xs">
              <p className="text-xs font-medium text-rose-600">{t.imports.failedRecords}</p>
              <p className="mt-0.5 text-xl font-black text-rose-600">{numberFormatter.format(latestResult.failed_records)}</p>
            </div>
          </div>
          <div className="mt-3">
            <div className="mb-1 flex justify-between text-[11px] font-semibold text-slate-600">
              <span>{ingestionStatusLabel(latestResult)}</span>
              <span>{latestResult.processed_records} / {latestResult.total_records} ({latestResult.progress_percent}%)</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-blue-100">
              <div className="h-full bg-[#3A5FC3] transition-all" style={{ width: `${latestResult.progress_percent}%` }} />
            </div>
          </div>
        </section>
      ) : null}

      {/* Filter & Search Bar */}
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            aria-label={t.common.search}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder={t.imports.searchPlaceholder}
            className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 sm:text-sm"
          />
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="import-archive-filter" className="text-xs font-medium text-slate-500 whitespace-nowrap">
            {locale === "vi" ? "Hiển thị" : "Visibility"}:
          </label>
          <select
            id="import-archive-filter"
            value={archiveFilter}
            onChange={(e) => {
              setArchiveFilter(e.target.value as "active" | "archived" | "all");
              setPage(1);
            }}
            className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
          >
            <option value="active">{locale === "vi" ? "Đang hiển thị" : "Visible"}</option>
            <option value="archived">{locale === "vi" ? "Đã ẩn" : "Hidden"}</option>
            <option value="all">{locale === "vi" ? "Tất cả" : "All"}</option>
          </select>

          <label htmlFor="import-status-filter" className="text-xs font-medium text-slate-500 whitespace-nowrap">
            {t.common.status}:
          </label>
          <select
            id="import-status-filter"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
          >
            <option value="ALL">{t.imports.filterAll}</option>
            <option value="COMPLETED">{t.imports.completed}</option>
            <option value="WARNING">{locale === "vi" ? "Cảnh báo" : "Warnings"}</option>
            <option value="PROCESSING">{t.imports.inProgress}</option>
            <option value="FAILED">{t.imports.failed}</option>
          </select>

          {/* Reset Button */}
          <button
            type="button"
            onClick={() => {
              setSearch("");
              setStatusFilter("ALL");
              setArchiveFilter("active");
              setPage(1);
            }}
            disabled={!search && statusFilter === "ALL" && archiveFilter === "active"}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-[#3A5FC3] hover:border-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 transition-colors cursor-pointer shadow-2xs"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>{locale === "vi" ? "Đặt lại" : "Reset"}</span>
          </button>
        </div>
      </div>

      {/* History Table Card */}
      <section className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-xs">
        <div className="relative overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
              <tr>
                <th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">{t.imports.fileName}</th>
                <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Loại dữ liệu" : "Data Type"}</th>
                <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">{t.imports.time}</th>
                <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Đã nạp / Bản ghi" : "Imported / Total"}</th>
                <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">{t.imports.performedBy}</th>
                <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">{t.common.status}</th>
                <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap w-56">{t.imports.actions}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-2">
                      <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                      <span>{t.common.loading}</span>
                    </div>
                  </td>
                </tr>
              ) : filteredHistory.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-1">
                      <svg className="h-8 w-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <span className="font-semibold text-slate-600">{t.imports.noHistory}</span>
                      <span className="text-[11px] text-slate-400">
                        {locale === "vi" ? "Các lần nhập dữ liệu CSV và JSON sẽ xuất hiện tại đây." : "Import history will appear here."}
                      </span>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedHistory.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3.5 align-middle whitespace-nowrap">
                      <div className="flex items-center gap-2.5">
                        <div className={`flex h-8 w-8 items-center justify-center rounded-lg border shrink-0 shadow-2xs ${
                          item.type === "LECTURERS"
                            ? "bg-violet-50 text-violet-600 border-violet-100/80"
                            : "bg-blue-50 text-[#3A5FC3] border-blue-100/80"
                        }`}>
                          {item.type === "LECTURERS" ? (
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 14l9-5-9-5-9 5 9 5zm0 0v6m0 0l3-3m-3 3l-3-3" />
                            </svg>
                          ) : (
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                          )}
                        </div>
                        <div className="min-w-0 max-w-xs sm:max-w-sm">
                          <span className="block font-bold text-slate-800 truncate" title={item.file_name}>
                            {item.file_name}
                          </span>
                          <span className="block text-[10px] font-mono text-slate-400 truncate">
                            ID: {item.id}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="px-4 py-3.5 text-center align-middle whitespace-nowrap font-medium">
                      {renderTypeBadge(item.type)}
                    </td>

                    <td className="px-4 py-3.5 text-center align-middle whitespace-nowrap font-medium text-slate-600">
                      {formatDate(item.created_at)}
                    </td>

                    <td className="px-4 py-3.5 text-center align-middle whitespace-nowrap font-bold text-emerald-600">
                      <span>
                        {`${numberFormatter.format(item.type === "LECTURERS" ? item.imported_records : item.processed_records)} / ${numberFormatter.format(item.total_records)}`}
                      </span>
                      {ACTIVE_STATUSES.includes(item.status) && (
                        <div className="mx-auto mt-1 h-1 w-20 overflow-hidden rounded-full bg-slate-200">
                          <div className="h-full bg-[#3A5FC3]" style={{ width: `${item.progress_percent}%` }} />
                        </div>
                      )}
                    </td>

                    <td className="px-4 py-3.5 text-center align-middle whitespace-nowrap">
                      {renderUserBadge(item.performed_by)}
                    </td>

                    <td className="px-4 py-3.5 text-center align-middle whitespace-nowrap">
                      {renderTableStatusBadge(item)}
                    </td>

                    <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap">
                      <div className="mx-auto grid w-52 grid-cols-2 gap-1.5">
                        <button
                          type="button"
                          onClick={() => openDetail(item)}
                          className="inline-flex h-7 w-full items-center justify-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-[11px] font-semibold text-slate-700 shadow-2xs transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] cursor-pointer whitespace-nowrap"
                        >
                          <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                          <span>{t.imports.detail}</span>
                        </button>

                        {ACTIVE_STATUSES.includes(item.status) ? (
                          <button
                            type="button"
                            onClick={() => handleOpenCancelModal(item)}
                            className="inline-flex h-7 w-full items-center justify-center gap-1 rounded-md border border-amber-200 bg-amber-50/80 px-2 text-[11px] font-semibold text-amber-700 shadow-2xs transition-colors hover:bg-amber-100 cursor-pointer whitespace-nowrap"
                          >
                            <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 6l12 12M18 6L6 18" />
                            </svg>
                            <span>{t.imports.cancelImport}</span>
                          </button>
                        ) : item.archived ? (
                          <button
                            type="button"
                            onClick={() => handleOpenRestoreModal(item)}
                            title={locale === "vi" ? "Khôi phục hiển thị" : "Restore visibility"}
                            className="inline-flex h-7 w-full items-center justify-center gap-1 rounded-md border border-blue-200 bg-blue-50/80 px-2 text-[11px] font-semibold text-[#3A5FC3] shadow-2xs transition-colors hover:bg-blue-100 cursor-pointer whitespace-nowrap"
                          >
                            <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            <span>{locale === "vi" ? "Khôi phục" : "Restore"}</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleDeleteIntent(item)}
                            title={locale === "vi" ? "Xóa đợt nhập" : "Delete import"}
                            className="inline-flex h-7 w-full items-center justify-center gap-1 rounded-md border border-rose-200 bg-rose-50/80 px-2 text-[11px] font-semibold text-rose-600 shadow-2xs transition-colors hover:bg-rose-100 cursor-pointer whitespace-nowrap"
                          >
                            <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            <span>{locale === "vi" ? "Xóa" : "Delete"}</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer info & Pagination Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-2.5 text-[11px] text-slate-500">
          <div className="flex items-center gap-3">
            <span>
              {t.imports.showing} <strong>{paginatedHistory.length}</strong> {locale === "vi" ? "trong" : "of"} {filteredHistory.length} {locale === "vi" ? "đợt nhập" : "imports"}
            </span>

            {/* Page Size Selector */}
            <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
              <span className="text-slate-500">{locale === "vi" ? "Hiển thị:" : "Show:"}</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                className="h-6.5 rounded-md border border-slate-200 bg-white px-1.5 text-[11px] font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer"
              >
                <option value={10}>10 / {locale === "vi" ? "trang" : "page"}</option>
                <option value={30}>30 / {locale === "vi" ? "trang" : "page"}</option>
                <option value={50}>50 / {locale === "vi" ? "trang" : "page"}</option>
                <option value={100}>100 / {locale === "vi" ? "trang" : "page"}</option>
              </select>
            </div>
          </div>

          <nav aria-label="Pagination" className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              disabled={currentPage <= 1}
              className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
            >
              {t.imports.previousPage}
            </button>
            <span aria-live="polite" className="min-w-[72px] text-center font-medium text-slate-600">
              {t.imports.page} <strong>{currentPage}</strong> / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
              disabled={currentPage >= totalPages}
              className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
            >
              {t.imports.nextPage}
            </button>
          </nav>
        </div>
      </section>

      {/* ====================================================================== */}
      {/* MODAL: CHI TIẾT ĐỢT NHẬP (DETAIL MODAL) */}
      {/* ====================================================================== */}
      {detailOpen && (
        <ModalPortal>
          <div className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-slate-900/50 p-3 backdrop-blur-xs sm:p-4">
            <section
              role="dialog"
              aria-modal="true"
              aria-labelledby="import-detail-title"
              className="flex max-h-[calc(100vh-1.5rem)] w-[calc(100vw-1.5rem)] sm:w-full max-w-4xl lg:max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl animate-in zoom-in-95 duration-150 sm:max-h-[calc(100vh-2rem)]"
            >
              <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <div className="flex items-center gap-2.5">
                  <div>
                    <h2 id="import-detail-title" className="text-base font-bold text-slate-900 sm:text-lg">
                      {t.imports.detail}
                    </h2>
                    {detail && (
                      <p className="mt-0.5 break-all text-[11px] font-mono text-slate-400">
                        ID: {detail.id}
                      </p>
                    )}
                  </div>
                  {detail && renderTypeBadge(detail.type)}
                </div>
                <button
                  type="button"
                  onClick={() => setDetailOpen(false)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </header>

              <div className="min-h-48 overflow-y-auto p-4 sm:p-5">
                {detailLoading || !detail ? (
                  <div className="flex min-h-40 items-center justify-center">
                    <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                  </div>
                ) : detail.type === "LECTURERS" ? (
                  <div className="space-y-4">
                    {/* Summary Stats for Lecturer JSON Import */}
                    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                      <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3 text-center shadow-2xs">
                        <span className="text-[11px] font-medium text-slate-500">{t.lecturerImport.totalRecords}</span>
                        <p className="mt-0.5 text-lg font-black text-slate-800">{numberFormatter.format(detail.total_records)}</p>
                      </div>
                      <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/40 p-3 text-center shadow-2xs">
                        <span className="text-[11px] font-medium text-emerald-600">{t.lecturerImport.created}</span>
                        <p className="mt-0.5 text-lg font-black text-emerald-600">
                          {numberFormatter.format(detail.lecturer_summary?.created ?? detail.imported_records)}
                        </p>
                      </div>
                      <div className="rounded-xl border border-amber-200/80 bg-amber-50/40 p-3 text-center shadow-2xs">
                        <span className="text-[11px] font-medium text-amber-600">{t.lecturerImport.updated}</span>
                        <p className="mt-0.5 text-lg font-black text-amber-600">
                          {numberFormatter.format(detail.lecturer_summary?.updated ?? 0)}
                        </p>
                      </div>
                      <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3 text-center shadow-2xs">
                        <span className="text-[11px] font-medium text-slate-500">{t.lecturerImport.unchanged}</span>
                        <p className="mt-0.5 text-lg font-black text-slate-700">
                          {numberFormatter.format(detail.lecturer_summary?.unchanged ?? 0)}
                        </p>
                      </div>
                    </div>

                    {(detail.lecturer_summary?.warnings ?? detail.duplicate_candidates) > 0 && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                        <strong>{locale === "vi" ? "Cảnh báo trùng tên" : "Duplicate name warnings"}:</strong>{" "}
                        {numberFormatter.format(detail.lecturer_summary?.warnings ?? detail.duplicate_candidates)}
                      </div>
                    )}

                    {/* Metadata details */}
                    <dl className="grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
                      <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3 sm:col-span-2">
                        <dt className="font-semibold text-slate-500">{t.imports.fileName}</dt>
                        <dd className="mt-1 break-all font-bold text-slate-800">{detail.file_name}</dd>
                      </div>

                      <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                        <dt className="font-semibold text-slate-500">{locale === "vi" ? "Thời gian nhập" : "Imported at"}</dt>
                        <dd className="mt-1 font-semibold text-slate-700">{formatDate(detail.created_at)}</dd>
                      </div>

                      <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                        <dt className="font-semibold text-slate-500">{t.imports.performedBy}</dt>
                        <dd className="mt-1 font-semibold text-slate-700">{detail.performed_by ?? (locale === "vi" ? "Không xác định" : "Unknown")}</dd>
                      </div>

                      <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3 sm:col-span-2">
                        <dt className="font-semibold text-slate-500">{t.common.status}</dt>
                        <dd className="mt-1.5">{renderStatusBadge(detail)}</dd>
                      </div>
                    </dl>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* ROW 1: Two equal cards side-by-side on desktop, stacked on mobile */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-stretch">
                      {/* CARD 1: TIẾP NHẬN NGUỒN */}
                      <div className="flex flex-col rounded-xl border border-blue-100 bg-blue-50/20 p-4 shadow-2xs">
                        <div className="flex items-center justify-between pb-3 mb-3 border-b border-blue-100/70">
                          <div className="flex items-center gap-2">
                            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#3A5FC3]/10 text-[#3A5FC3]">
                              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                              </svg>
                            </div>
                            <div>
                              <h3 className="text-xs font-bold uppercase tracking-wider text-blue-800">
                                {t.imports.sourceIngestion}
                              </h3>
                              <span className="text-[11px] font-medium text-blue-600">
                                {locale === "vi" ? "Đã tiếp nhận nguồn" : "Source received"}
                              </span>
                            </div>
                          </div>
                          {renderIngestionBadge(detail)}
                        </div>

                        {/* Raw stats */}
                        <div className="grid grid-cols-3 gap-2 text-center mb-3">
                          <div className="rounded-lg border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-slate-500 uppercase">{t.imports.totalRecords}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.total_records)}</p>
                          </div>
                          <div className="rounded-lg border border-emerald-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-emerald-600 uppercase">{t.imports.importedRecords}</span>
                            <p className="mt-0.5 text-base font-black text-emerald-600">{numberFormatter.format(detail.imported_records)}</p>
                          </div>
                          <div className="rounded-lg border border-rose-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-[10px] font-medium text-rose-600 uppercase">{t.imports.failedRecords}</span>
                            <p className="mt-0.5 text-base font-black text-rose-600">{numberFormatter.format(detail.failed_records)}</p>
                          </div>
                        </div>

                        {/* Metadata summary */}
                        <div className="mt-auto space-y-1.5 rounded-lg border border-blue-100/80 bg-white/75 p-3 text-xs text-slate-600">
                          <div className="flex justify-between gap-2">
                            <span className="text-slate-400 shrink-0">{t.imports.fileName}:</span>
                            <span className="font-semibold text-slate-800 truncate text-right" title={detail.file_name}>{detail.file_name}</span>
                          </div>
                          <div className="flex justify-between gap-2">
                            <span className="text-slate-400 shrink-0">{t.imports.performedBy}:</span>
                            <span className="font-semibold text-slate-700">{detail.performed_by || (locale === "vi" ? "Không xác định" : "Unknown")}</span>
                          </div>
                          <div className="flex justify-between gap-2">
                            <span className="text-slate-400 shrink-0">{locale === "vi" ? "Bắt đầu lúc" : "Started at"}:</span>
                            <span className="font-medium text-slate-700">{formatDate(detail.started_at)}</span>
                          </div>
                          {detail.finished_at && (
                            <div className="flex justify-between gap-2">
                              <span className="text-slate-400 shrink-0">
                                {detail.status === "CANCELLED"
                                  ? (locale === "vi" ? "Thời điểm hủy" : "Cancelled at")
                                  : (locale === "vi" ? "Kết thúc lúc" : "Finished at")}:
                              </span>
                              <span className="font-medium text-slate-700">{formatDate(detail.finished_at)} ({formatDuration(detail.duration_seconds)})</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* CARD 2: CHUẨN HÓA DỮ LIỆU */}
                      <div className="flex flex-col rounded-xl border border-slate-200/80 bg-slate-50/40 p-4 shadow-2xs">
                        <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-200/70">
                          <div className="flex items-center gap-2">
                            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
                              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                              </svg>
                            </div>
                            <div>
                              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                                {t.normalization.title}
                              </h3>
                              <span className="text-[11px] font-medium text-slate-500">
                                {detail.normalization
                                  ? (detail.normalization.status === "COMPLETED"
                                      ? (locale === "vi" ? "Đã chuẩn hóa công bố" : "Publications normalized")
                                      : (locale === "vi" ? "Đang xử lý" : "Processing"))
                                  : (locale === "vi" ? "Chờ chuẩn hóa" : "Awaiting normalization")}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {renderNormalizationBadge(detail)}
                            <Link
                              to={`/normalization?import=${detail.id}`}
                              className="inline-flex items-center gap-1 rounded-lg border border-[#3A5FC3] bg-white px-2.5 py-1 text-[11px] font-bold text-[#3A5FC3] shadow-2xs hover:bg-blue-50 transition-colors cursor-pointer"
                            >
                              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                              </svg>
                              <span>{t.normalization.goToNormalization}</span>
                            </Link>
                          </div>
                        </div>

                        {detail.normalization ? (
                          <>
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-center mb-3">
                              <div className="rounded-lg border border-emerald-200/80 bg-white p-2.5 shadow-2xs">
                                <span className="text-[10px] font-medium text-emerald-700 uppercase">{t.normalization.table.newPublications}</span>
                                <p className="mt-0.5 text-base font-black text-emerald-700">{numberFormatter.format(detail.normalization.canonical_new)}</p>
                              </div>
                              <div className="rounded-lg border border-slate-200 bg-white p-2.5 shadow-2xs">
                                <span className="text-[10px] font-medium text-slate-600 uppercase">{t.normalization.table.existing}</span>
                                <p className="mt-0.5 text-base font-black text-slate-700">{numberFormatter.format(detail.normalization.canonical_existing)}</p>
                              </div>
                              <div className="rounded-lg border border-amber-200/80 bg-white p-2.5 shadow-2xs">
                                <span className="text-[10px] font-medium text-amber-700 uppercase">{t.normalization.table.metadataChanged}</span>
                                <p className="mt-0.5 text-base font-black text-amber-700">{numberFormatter.format(detail.normalization.canonical_metadata_changed)}</p>
                              </div>
                              <div className="rounded-lg border border-rose-200/80 bg-white p-2.5 shadow-2xs">
                                <span className="text-[10px] font-medium text-rose-700 uppercase">{t.normalization.table.errors}</span>
                                <p className="mt-0.5 text-base font-black text-rose-700">{numberFormatter.format(detail.normalization.canonical_failed)}</p>
                              </div>
                              <div className="rounded-lg border border-slate-200 bg-white p-2.5 shadow-2xs col-span-2 sm:col-span-2">
                                <span className="text-[10px] font-medium text-slate-600 uppercase">{locale === "vi" ? "Trùng EID nội tệp" : "Intra-file Duplicates"}</span>
                                <p className="mt-0.5 text-base font-black text-slate-700">{numberFormatter.format(detail.normalization.canonical_intra_duplicate)}</p>
                              </div>
                            </div>
                            <div className="mt-auto rounded-lg border border-slate-200/60 bg-white/75 p-2.5 text-[11px] text-slate-500">
                              {locale === "vi"
                                ? "Dữ liệu Scopus đã được chuẩn hóa và ánh xạ vào kho công bố khoa học hợp nhất."
                                : "Scopus data has been normalized and mapped to the canonical publication store."}
                            </div>
                          </>
                        ) : (
                          <div className="flex flex-1 flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white/60 p-5 text-center">
                            <svg className="h-7 w-7 text-slate-300 mb-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                            </svg>
                            <p className="text-xs font-semibold text-slate-600">{t.normalization.status.notNormalized}</p>
                            <p className="mt-1 text-[11px] text-slate-400">
                              {locale === "vi"
                                ? "Đã hoàn thành tiếp nhận nguồn. Vui lòng chuyển sang không gian Chuẩn hóa để xử lý và ánh xạ vào kho công bố khoa học."
                                : "Source ingestion complete. Please visit the Normalization workspace to process and map to canonical publications."}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* ROW 2: TÌNH TRẠNG SỬ DỤNG DỮ LIỆU SPANS FULL WIDTH */}
                    <div className="rounded-xl border border-violet-200/80 bg-violet-50/20 p-4 shadow-2xs">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
                          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 015.656 0l1.415 1.415a4 4 0 010 5.656l-3 3a4 4 0 01-5.656 0M10.172 13.828a4 4 0 01-5.656 0l-1.415-1.415a4 4 0 010-5.656l3-3a4 4 0 015.656 0" />
                          </svg>
                        </div>
                        <h3 className="text-xs font-bold uppercase tracking-wider text-violet-800">
                          {locale === "vi" ? "Tình trạng sử dụng dữ liệu" : "Data Usage State"}
                        </h3>
                        {detail.archived && (
                          <span className={`${badgeClassName} ml-auto border-violet-200 bg-violet-50 text-violet-700`}>
                            {locale === "vi" ? "Đã ẩn khỏi lịch sử" : "Hidden from history"}
                          </span>
                        )}
                      </div>
                      <dl className="grid grid-cols-1 gap-2.5 text-xs sm:grid-cols-3">
                        <div className="rounded-xl border border-slate-200/80 bg-white p-3 text-center shadow-2xs">
                          <dt className="text-[11px] font-medium text-slate-500">
                            {locale === "vi" ? "Được sử dụng" : "In use"}
                          </dt>
                          <dd className={`mt-0.5 text-lg font-black ${
                            isInUse(detail) ? "text-violet-700" : "text-slate-700"
                          }`}>
                            {isInUse(detail)
                              ? (locale === "vi" ? "Có" : "Yes")
                              : (locale === "vi" ? "Không" : "No")}
                          </dd>
                        </div>
                        <div className="rounded-xl border border-slate-200/80 bg-white p-3 text-center shadow-2xs">
                          <dt className="text-[11px] font-medium text-slate-500">
                            {locale === "vi" ? "Liên kết nguồn công bố" : "Publication source links"}
                          </dt>
                          <dd className="mt-0.5 text-lg font-black text-slate-800">
                            {numberFormatter.format(detail.usage?.publication_source_links ?? 0)}
                          </dd>
                        </div>
                        <div className="rounded-xl border border-slate-200/80 bg-white p-3 text-center shadow-2xs">
                          <dt className="text-[11px] font-medium text-slate-500">
                            {locale === "vi" ? "Biến thể tên tác giả" : "Author name variants"}
                          </dt>
                          <dd className="mt-0.5 text-lg font-black text-slate-800">
                            {numberFormatter.format(detail.usage?.author_variant_links ?? 0)}
                          </dd>
                        </div>
                      </dl>
                      {isInUse(detail) && (
                        <p className="mt-3 text-[11px] text-violet-900">
                          {locale === "vi"
                            ? "Dữ liệu nguồn của đợt nhập đã được sử dụng ở bước xử lý tiếp theo nên không thể xóa vật lý mà không làm mất provenance."
                            : "Source data has been consumed by downstream processing, so it cannot be physically deleted without losing provenance."}
                        </p>
                      )}
                    </div>

                    {detail.duplicate_candidates > 0 && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                        <strong>{t.imports.duplicateRows}:</strong> {numberFormatter.format(detail.duplicate_candidates)}
                      </div>
                    )}

                    {fatalErrorMessage(detail.error_summary) && (
                      <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                        <strong>{t.imports.errorDetail}:</strong> {fatalErrorMessage(detail.error_summary)}
                      </div>
                    )}

                    {detail.row_errors.length > 0 && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 text-xs">
                        <h4 className="mb-2 font-bold text-amber-800">{t.imports.rowErrors}</h4>
                        <ul className="max-h-36 space-y-1 overflow-y-auto text-amber-900">
                          {detail.row_errors.map((rowError, index) => (
                            <li key={`${rowError.row_number ?? "row"}-${index}`}>
                              {locale === "vi" ? "Dòng" : "Row"} {rowError.row_number ?? "—"}: {rowError.message ?? rowError.code ?? t.imports.failed}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-100 px-5 py-3 bg-slate-50/50">
                {detail && ACTIVE_STATUSES.includes(detail.status) ? (
                  <button
                    type="button"
                    disabled={detailLoading}
                    onClick={() => handleOpenCancelModal(detail)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-xs font-semibold text-amber-800 hover:bg-amber-100 disabled:opacity-50 cursor-pointer shadow-2xs"
                  >
                    <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 6l12 12M18 6L6 18" />
                    </svg>
                    <span>{t.imports.cancelImport}</span>
                  </button>
                ) : detail && detail.archived ? (
                  <button
                    type="button"
                    disabled={detailLoading || isRestoring}
                    onClick={() => handleOpenRestoreModal(detail)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-blue-300 bg-blue-50 px-4 py-2 text-xs font-semibold text-[#3A5FC3] hover:bg-blue-100 transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                  >
                    <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <span>{isRestoring ? (locale === "vi" ? "Đang khôi phục..." : "Restoring...") : (locale === "vi" ? "Khôi phục hiển thị" : "Restore visibility")}</span>
                  </button>
                ) : detail ? (
                  <button
                    type="button"
                    disabled={detailLoading}
                    onClick={() => handleDeleteIntent(detail)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-100 transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                  >
                    <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    <span>{locale === "vi" ? "Xóa đợt nhập" : "Delete import"}</span>
                  </button>
                ) : null}

                <button
                  type="button"
                  disabled={detailLoading}
                  onClick={() => setDetailOpen(false)}
                  className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                >
                  {t.imports.close}
                </button>
              </footer>
            </section>
          </div>
        </ModalPortal>
      )}

      {/* BLOCKED DELETE WARNING / EXPLANATORY MODAL */}
      {blockedDeleteState && (
        <ConfirmModal
          open={Boolean(blockedDeleteState)}
          variant="warning"
          title={
            blockedDeleteState.reason === "LECTURER_NEED_ROLLBACK"
              ? (locale === "vi" ? "Cần hoàn tác trước khi xóa" : "Rollback required before deletion")
              : (locale === "vi" ? "Không thể xóa đợt nhập" : "Cannot delete import")
          }
          description={
            <span>
              {blockedDeleteState.reason === "LECTURER_NEED_ROLLBACK" ? (
                <>
                  {locale === "vi"
                    ? "Đợt nhập này đã tạo hoặc cập nhật dữ liệu giảng viên. Hãy hoàn tác các thay đổi của đợt nhập trước khi xóa bản ghi lịch sử."
                    : "This import created or updated lecturer master records. Please rollback changes before deleting history."}
                  <br />
                  <strong className="text-slate-800 mt-1 block">{blockedDeleteState.item.file_name}</strong>
                </>
              ) : blockedDeleteState.reason === "SCOPUS_IN_USE" ? (
                <>
                  {locale === "vi"
                    ? "Dữ liệu của đợt nhập này đang được sử dụng ở các bước xử lý tiếp theo nên không thể xóa vật lý mà không làm mất provenance."
                    : "This import's data is consumed by downstream processing and cannot be physically deleted without losing provenance."}
                  {blockedDeleteState.item.usage && (
                    <span className="my-2.5 block rounded-lg border border-amber-200/80 bg-amber-50/50 p-2.5 text-xs text-slate-700">
                      <span className="block">
                        {locale === "vi" ? "Liên kết nguồn công bố:" : "Publication source links:"}{" "}
                        <strong className="text-slate-800 font-bold">
                          {numberFormatter.format(blockedDeleteState.item.usage.publication_source_links ?? 0)}
                        </strong>
                      </span>
                      <span className="block mt-1">
                        {locale === "vi" ? "Biến thể tên tác giả:" : "Author name variants:"}{" "}
                        <strong className="text-slate-800 font-bold">
                          {numberFormatter.format(blockedDeleteState.item.usage.author_variant_links ?? 0)}
                        </strong>
                      </span>
                    </span>
                  )}
                  <span className="block text-slate-600">
                    {locale === "vi"
                      ? "Bạn có thể Ẩn khỏi lịch sử. Thao tác này không xóa dữ liệu và không làm mất thông tin truy vết."
                      : "You can Hide from history. This will not delete data or lose provenance tracking."}
                  </span>
                  <strong className="text-slate-800 mt-1 block">{blockedDeleteState.item.file_name}</strong>
                </>
              ) : (
                <>
                  {locale === "vi"
                    ? "Đợt nhập giảng viên này đang có hồ sơ liên kết với tài khoản hệ thống nên không thể xóa."
                    : "This lecturer import has accounts linked to system users and cannot be deleted."}
                  <br />
                  <strong className="text-slate-800 mt-1 block">{blockedDeleteState.item.file_name}</strong>
                </>
              )}
            </span>
          }
          confirmLabel={
            blockedDeleteState.reason === "LECTURER_NEED_ROLLBACK"
              ? (locale === "vi" ? "Hoàn tác đợt nhập" : "Rollback import")
              : blockedDeleteState.reason === "SCOPUS_IN_USE"
                ? (locale === "vi" ? "Ẩn khỏi lịch sử" : "Hide from history")
                : undefined
          }
          showConfirmButton={blockedDeleteState.reason !== "LECTURER_BLOCKED"}
          cancelLabel={t.imports.close}
          onConfirm={() => {
            const item = blockedDeleteState.item;
            const reason = blockedDeleteState.reason;
            setBlockedDeleteState(null);
            if (reason === "LECTURER_NEED_ROLLBACK") {
              handleOpenRollbackModal(item);
            } else if (reason === "SCOPUS_IN_USE") {
              handleOpenArchiveModal(item);
            }
          }}
          onCancel={() => {
            setBlockedDeleteState(null);
          }}
        />
      )}

      {/* CANCEL MODAL */}
      {cancelModalOpen && itemToCancel && (
        <ConfirmModal
          open={cancelModalOpen}
          variant="warning"
          loading={isCancelling}
          title={t.imports.cancelConfirmTitle}
          description={
            <span>
              {t.imports.cancelConfirmMessage}{" "}
              <strong className="text-slate-800">{itemToCancel.file_name}</strong>?
              <br />
              {t.imports.cancelKeepsData}
            </span>
          }
          confirmLabel={t.imports.confirmCancel}
          cancelLabel={t.common.cancel}
          onConfirm={handleConfirmCancel}
          onCancel={() => {
            if (!isCancelling) {
              setCancelModalOpen(false);
              setItemToCancel(null);
            }
          }}
        />
      )}

      {/* ROLLBACK MODAL */}
      {rollbackModalOpen && itemToRollback && (
        <ConfirmModal
          open={rollbackModalOpen}
          variant="warning"
          loading={isRollingBack}
          title={locale === "vi" ? "Hoàn tác đợt nhập giảng viên?" : "Rollback lecturer import?"}
          description={
            <span>
              {locale === "vi"
                ? "Hệ thống sẽ gỡ các hồ sơ giảng viên được tạo bởi đợt nhập này và khôi phục trạng thái ban đầu của hồ sơ đã tồn tại trước đó. Giảng viên được thêm thủ công sẽ được giữ nguyên."
                : "The system will remove master records created by this import and restore pre-existing records when history exists. Manually added lecturers will remain unchanged."}
              <br />
              <strong className="text-slate-800 mt-1 block">{itemToRollback.file_name}</strong>
            </span>
          }
          confirmLabel={locale === "vi" ? "Hoàn tác" : "Rollback"}
          cancelLabel={t.common.cancel}
          onConfirm={handleConfirmRollback}
          onCancel={() => {
            if (!isRollingBack) {
              setRollbackModalOpen(false);
              setItemToRollback(null);
            }
          }}
        />
      )}

      {/* DELETE MODAL */}
      {deleteModalOpen && itemToDelete && (
        <ConfirmModal
          open={deleteModalOpen}
          variant="danger"
          loading={isDeleting}
          title={
            itemToDelete.type === "LECTURERS"
              ? (locale === "vi" ? "Xóa lịch sử nhập dữ liệu?" : "Delete import history?")
              : (locale === "vi" ? "Xóa đợt nhập dữ liệu?" : "Delete import dataset?")
          }
          description={
            <span>
              {itemToDelete.type === "LECTURERS" ? (
                locale === "vi"
                  ? "Bạn có chắc chắn muốn xóa bản ghi này khỏi lịch sử nhập dữ liệu? Dữ liệu giảng viên đã được gỡ khi hoàn tác."
                  : "Are you sure you want to remove this entry from import history? Its lecturer data was already removed during rollback."
              ) : (
                locale === "vi"
                  ? "Đợt nhập và dữ liệu nguồn chưa được sử dụng ở các bước xử lý tiếp theo sẽ bị xóa vĩnh viễn khỏi hệ thống."
                  : "The import and unlinked raw source data will be permanently deleted."
              )}
              <br />
              <strong className="text-slate-800 mt-1 block">{itemToDelete.file_name}</strong>
            </span>
          }
          confirmLabel={
            itemToDelete.type === "LECTURERS"
              ? (locale === "vi" ? "Xóa lịch sử" : "Delete history")
              : (locale === "vi" ? "Xóa đợt nhập" : "Delete import")
          }
          cancelLabel={t.common.cancel}
          onConfirm={handleConfirmDelete}
          onCancel={() => {
            if (!isDeleting) {
              setDeleteModalOpen(false);
              setItemToDelete(null);
            }
          }}
        />
      )}

      {/* ARCHIVE MODAL */}
      {archiveModalOpen && itemToArchive && (
        <ConfirmModal
          open={archiveModalOpen}
          variant="warning"
          loading={isArchiving}
          title={locale === "vi" ? "Ẩn đợt nhập khỏi lịch sử?" : "Hide import from history?"}
          description={
            <span>
              {locale === "vi"
                ? "Đợt nhập sẽ không còn xuất hiện trong danh sách mặc định. Dữ liệu nguồn, dữ liệu chuẩn hóa, liên kết provenance và nhật ký hệ thống vẫn được giữ nguyên."
                : "This import will no longer appear in the default history list. Source data, canonical publications, provenance links and audit logs remain intact."}
              <br />
              <strong className="text-slate-800 mt-1 block">{itemToArchive.file_name}</strong>
            </span>
          }
          confirmLabel={locale === "vi" ? "Ẩn khỏi lịch sử" : "Hide from history"}
          cancelLabel={t.common.cancel}
          onConfirm={handleConfirmArchive}
          onCancel={() => {
            if (!isArchiving) {
              setArchiveModalOpen(false);
              setItemToArchive(null);
            }
          }}
        />
      )}

      {/* RESTORE MODAL */}
      {restoreModalOpen && itemToRestore && (
        <ConfirmModal
          open={restoreModalOpen}
          variant="primary"
          loading={isRestoring}
          title={locale === "vi" ? "Khôi phục hiển thị đợt nhập?" : "Restore import visibility?"}
          description={
            <span>
              {locale === "vi"
                ? "Đợt nhập sẽ xuất hiện trở lại trong danh sách lịch sử mặc định. Chỉ thay đổi khả năng hiển thị trong lịch sử, không ảnh hưởng tới dữ liệu."
                : "This import will appear again in the default history list. Only the history visibility changes — no data is affected."}
              <br />
              <strong className="text-slate-800 mt-1 block">{itemToRestore.file_name}</strong>
            </span>
          }
          confirmLabel={locale === "vi" ? "Khôi phục hiển thị" : "Restore visibility"}
          cancelLabel={t.common.cancel}
          onConfirm={handleConfirmRestore}
          onCancel={() => {
            if (!isRestoring) {
              setRestoreModalOpen(false);
              setItemToRestore(null);
            }
          }}
        />
      )}

      {/* LECTURER IMPORT CONFIRM MODAL */}
      {lecturerConfirmOpen && lecturerPreview && (
        <ConfirmModal
          open={lecturerConfirmOpen}
          variant="primary"
          loading={lecturerImporting}
          title={t.lecturerImport.confirmTitle}
          description={
            <span>
              {t.lecturerImport.confirmMessage}
              <br />
              <strong className="text-slate-800 mt-1 block">
                {lecturerPreview.preview.filename} ({numberFormatter.format(lecturerPreview.preview.summary.valid)} {locale === "vi" ? "hồ sơ hợp lệ" : "valid records"})
              </strong>
            </span>
          }
          confirmLabel={t.lecturerImport.confirmImport}
          cancelLabel={t.common.cancel}
          onConfirm={handleConfirmLecturerImport}
          onCancel={() => {
            if (!lecturerImporting) {
              setLecturerConfirmOpen(false);
            }
          }}
        />
      )}
    </div>
    </>
  );
}
