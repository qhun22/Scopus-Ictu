import { adminLabel, isCorruptedName } from "../../utils/displayName";
import { useEffect, useRef, useState } from "react";
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
  getImportPrerequisites,
  uploadScopusCsv,
  CONFIRMED_IMPORTS_KEY,
  getConfirmedImportIds,
  isSupersededByNewerConfirmedDuplicate,
} from "../../api/imports";
import { ApiError } from "../../api/client";
import { cancelLecturerDatasetImport, importLecturerDataset } from "../../api/lecturerImport";
import ConfirmModal from "../../components/common/ConfirmModal";
import ModalPortal from "../../components/common/ModalPortal";
import LecturerDatasetImportCard, {
  LecturerDatasetImportCardHandle,
  PreviewResponse,
} from "../../components/lecturers/LecturerDatasetImportCard";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import { useI18n } from "../../i18n";
import { buttonClass } from "../../components/ui/Button";
import {
  PENDING_SCOPUS_IMPORT_KEY,
  PENDING_LECTURER_PREVIEW_KEY,
  savePendingLecturerFile,
  loadPendingLecturerFile,
  clearPendingLecturerFile,
} from "../../utils/pendingImportCache";

const LECTURER_PREVIEW_ID = "__lecturer_preview__";

function replaceToken(template: string, token: string, value: string): string {
  return template.replace(`{${token}}`, value);
}

// A real UUID shown in place of the internal LECTURER_PREVIEW_ID placeholder
// while the file is still only a preview (no backend record yet). Sent back
// to the server on confirm (see handleConfirmLecturerImport) so the backend
// uses this exact id for the new import instead of generating its own —
// the id the admin saw while previewing never changes once confirmed. Only
// the first 8 characters are ever shown (see shortId below), so continuity
// holds visually too, not just internally.
function generateDisplayId(): string {
  return crypto.randomUUID();
}

// The full id is a 36-char UUID — too long for a compact badge/cell and
// prone to overflowing the layout. Show only its first 8 characters (still
// unique enough to tell rows apart at a glance); the full value is always
// available via the `title` tooltip for copy/paste.
function shortId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

const badgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-[#3A5FC3] bg-white px-2.5 text-center text-sm font-bold leading-none text-[#3A5FC3] hover:bg-blue-50";
const statusBadgeClassName = badgeClassName;
const cancelledStatusBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-red-400 bg-white px-2.5 text-center text-sm font-bold leading-none text-red-700 hover:bg-red-50";
const activeStatusBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-emerald-400 bg-white px-2.5 text-center text-sm font-bold leading-none text-emerald-700 hover:bg-emerald-50";
const supersededStatusBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-red-400 bg-white px-2.5 text-center text-sm font-bold leading-none text-red-700 hover:bg-red-50";
const abnormalStatusBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-amber-400 bg-white px-2.5 text-center text-sm font-bold leading-none text-amber-700 hover:bg-amber-50";
const needsProcessingBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-[#3A5FC3] bg-white px-2.5 text-center text-sm font-bold leading-none text-[#3A5FC3] hover:bg-blue-50";
// "Basic" neutral style — same as the "Chi tiết" action button, not the blue brand badge.
const basicBadgeClassName =
  "inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center text-sm font-bold leading-none text-slate-700 hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900";
const typeBadgeClassName = basicBadgeClassName;
const userBadgeClassName = basicBadgeClassName;
const ACTIVE_STATUSES: ImportStatus[] = ["RECEIVED", "PARSING", "VALIDATED"];

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
  const { user } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const lecturerCardRef = useRef<LecturerDatasetImportCardHandle>(null);

  const [config, setConfig] = useState<ImportConfig | null>(null);
  const [history, setHistory] = useState<ScopusImport[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectionError, setSelectionError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [lecturerPreview, setLecturerPreview] = useState<{
    preview: PreviewResponse;
    file: File;
    at: string;
    // A random 8-digit stand-in shown in the UI instead of the internal
    // LECTURER_PREVIEW_ID placeholder constant — generated once per preview
    // and kept stable across reloads via sessionStorage. The real
    // LECTURER_PREVIEW_ID stays the row's `id` everywhere else (the client
    // never calls the backend to confirm/cancel, so all that logic matches
    // on this fixed constant) — this field is for display only.
    displayId: string;
    duplicate?: { importId: string; filename: string; importedAt: string } | null;
  } | null>(null);
  // Scopus CSV needs the school's lecturer data first.
  const [lecturerCount, setLecturerCount] = useState<number | null>(null);
  const [lecturerImporting, setLecturerImporting] = useState(false);
  const [lecturerCancelling, setLecturerCancelling] = useState(false);
  const [activeResultPanel, setActiveResultPanel] = useState<"scopus_checked" | "lecturer_preview" | null>(null);
  const [isScopusFileExiting, setIsScopusFileExiting] = useState(false);
  const [pendingImport, setPendingImport] = useState<ScopusImport | null>(null);
  void pendingImport;
  const [confirmedImportIds, setConfirmedImportIds] = useState<string[]>(getConfirmedImportIds());
  const [confirmingImportId, setConfirmingImportId] = useState<string | null>(null);
  const [cancellingImportId, setCancellingImportId] = useState<string | null>(null);

  // Search & Filter & Pagination states
  const [searchInput, setSearchInput] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [archiveFilter, setArchiveFilter] = useState<"active" | "archived" | "all">(
    "active",
  );
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [isPageLoading] = useState(false);

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
      sessionStorage.removeItem(PENDING_SCOPUS_IMPORT_KEY);
      setPendingImport(null);
    } catch (error: unknown) {
      toast.error(
        t.imports.errorTitle,
        error instanceof ApiError ? error.message : t.imports.loadError,
      );
    } finally {
      setLoading(false);
    }
  };

  const restorePendingLecturerPreview = async () => {
    const serialized = sessionStorage.getItem(PENDING_LECTURER_PREVIEW_KEY);
    if (!serialized) return;
    try {
      const stored = JSON.parse(serialized) as {
        preview: PreviewResponse;
        at: string;
        displayId?: string;
        duplicate?: { importId: string; filename: string; importedAt: string } | null;
      };
      if (!stored.preview?.filename || !stored.at) {
        throw new Error("Invalid pending lecturer preview");
      }
      const file = await loadPendingLecturerFile();
      if (!file) {
        sessionStorage.removeItem(PENDING_LECTURER_PREVIEW_KEY);
        return;
      }
      setLecturerPreview({
        preview: stored.preview,
        file,
        at: stored.at,
        // Older sessionStorage entries predate this field — fall back to a
        // freshly generated one rather than breaking restoration.
        displayId: stored.displayId ?? generateDisplayId(),
        duplicate: stored.duplicate ?? null,
      });
    } catch (error) {
      sessionStorage.removeItem(PENDING_LECTURER_PREVIEW_KEY);
      await clearPendingLecturerFile().catch(() => undefined);
      toast.error(
        t.imports.errorTitle,
        locale === "vi"
          ? "Không thể khôi phục bản xem trước tệp JSON."
          : "Unable to restore the JSON preview.",
      );
      console.error("Failed to restore pending lecturer preview", error);
    }
  };

  useEffect(() => {
    fetchData();
    void restorePendingLecturerPreview();
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

  const formatDate = (value: string): string => {
    const d = new Date(value);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
  };

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

  const isAwaitingConfirmation = (item: ScopusImport): boolean =>
    item.id === LECTURER_PREVIEW_ID;

  const isWarningStatus = (item: ScopusImport): boolean => {
    // A pending lecturer preview flagged as a duplicate shows "Bất thường" —
    // count it as a warning instead of plain processing.
    if (isAwaitingConfirmation(item)) {
      return Boolean(item.duplicate_of);
    }
    // A Scopus CSV staged as a whole-file duplicate, not yet confirmed, also
    // shows "Bất thường" — same rule, it just has a real id instead of the
    // lecturer-preview placeholder one.
    if (item.type !== "LECTURERS" && item.status === "STAGED" && item.duplicate_of) {
      const confirmed = confirmedImportIds.includes(item.id) || Boolean(item.normalization_summary);
      if (!confirmed) return true;
    }
    if (item.status !== "STAGED" && item.status !== "APPLIED" && item.status !== "IMPORTED") {
      return false;
    }
    return getItemWarningCount(item) > 0;
  };

  const warnPendingAction = () => {
    toast.warning(
      locale === "vi" ? "Cần thao tác trước" : "Action required first",
      locale === "vi"
        ? "Vui lòng bấm \"Chi tiết\" ở danh sách để Xác nhận nhập hoặc Hủy tiến trình."
        : "Please click \"Details\" in the table to confirm import or cancel process.",
    );
  };

  const isInUse = (item: ScopusImport): boolean => {
    if (item.type === "LECTURERS") return false;
    return Boolean(item.in_use);
  };

  const cancelledLabel = (item: ScopusImport): string =>
    item.type === "LECTURERS" && !item.lecturer_summary?.cancelled_before_import
      ? (locale === "vi" ? "Đã hoàn tác" : "Rolled back")
      : t.imports.cancelled;

  const statusLabel = (item: ScopusImport): string => {
    if (confirmingImportId === item.id || cancellingImportId === item.id) {
      return t.imports.inProgress;
    }
    if (ACTIVE_STATUSES.includes(item.status)) {
      return t.imports.inProgress;
    }
    if (item.status === "FAILED") return t.imports.failed;
    if (item.status === "CANCELLED") return cancelledLabel(item);
    // A newer import of the same file now holds the data: nothing was rolled back.
    if (item.status === "SUPERSEDED") return locale === "vi" ? "Thay thế" : "Superseded";
    if (item.type === "LECTURERS") {
      if (isAwaitingConfirmation(item)) {
        if (item.duplicate_of) return locale === "vi" ? "Bất thường" : "Abnormal";
        return locale === "vi" ? "Chờ xử lý" : "Awaiting processing";
      }
      if (isWarningStatus(item)) {
        return locale === "vi" ? "Cảnh báo" : "Warning";
      }
      return item.failed_records > 0 ? t.imports.completedWithErrors : (locale === "vi" ? "Hoạt động" : "Active");
    }
    // Scopus imports
    if (isSupersededByNewerConfirmedDuplicate(item, history, confirmedImportIds)) {
      return locale === "vi" ? "Thay thế" : "Superseded";
    }
    if (item.status === "APPLIED" || isInUse(item)) {
      return locale === "vi" ? "Hoạt động" : "Active";
    }
    if (item.status === "STAGED") {
      const confirmed = confirmedImportIds.includes(item.id) || Boolean(item.normalization_summary);
      if (item.duplicate_of && !confirmed) {
        return locale === "vi" ? "Bất thường" : "Abnormal";
      }
      if (isWarningStatus(item)) {
        return locale === "vi" ? "Cảnh báo" : "Warning";
      }
      if (confirmed) {
        return locale === "vi" ? "Chờ chuẩn hóa" : "Awaiting normalization";
      }
      return locale === "vi" ? "Chờ xử lý" : "Awaiting processing";
    }
    return locale === "vi" ? "Hoạt động" : "Active";
  };

  const renderStatusBadge = (item: ScopusImport) => {
    const isBusy = confirmingImportId === item.id || cancellingImportId === item.id;
    const label = statusLabel(item);
    const isActive = label === (locale === "vi" ? "Hoạt động" : "Active");
    const isNeedsProcessing =
      label === (locale === "vi" ? "Chờ xử lý" : "Awaiting processing") ||
      label === (locale === "vi" ? "Chờ chuẩn hóa" : "Awaiting normalization");
    const isAbnormal = label === (locale === "vi" ? "Bất thường" : "Abnormal");
    const isSuperseded = label === (locale === "vi" ? "Thay thế" : "Superseded");
    const isProcessing = ACTIVE_STATUSES.includes(item.status) || isBusy;
    return (
      <span
        className={
          item.status === "CANCELLED" && !isBusy
            ? cancelledStatusBadgeClassName
            : isSuperseded
              ? supersededStatusBadgeClassName
              : isActive
              ? activeStatusBadgeClassName
              : isAbnormal && !isBusy
                ? abnormalStatusBadgeClassName
                : isNeedsProcessing || isBusy
                ? needsProcessingBadgeClassName
                : statusBadgeClassName
        }
      >
        {isProcessing && (
          <span className="mr-1.5 h-2.5 w-2.5 animate-spin [animation-duration:1.5s] rounded-full border-2 border-[#3A5FC3] border-t-transparent" />
        )}
        {label}
      </span>
    );
  };

  const renderTableStatusBadge = (item: ScopusImport) => {
    if (item.archived) {
      return (
        <span
          title={locale === "vi" ? "Đã ẩn khỏi lịch sử" : "Hidden from history"}
          className={statusBadgeClassName}
        >
          {locale === "vi" ? "Đã ẩn" : "Archived"}
        </span>
      );
    }

    return renderStatusBadge(item);
  };

  const renderIngestionBadge = (item: ScopusImport) => {
    if (ACTIVE_STATUSES.includes(item.status)) {
      return (
        <span className={`${needsProcessingBadgeClassName} gap-1`}>
          <span className="h-2.5 w-2.5 animate-spin [animation-duration:1.5s] rounded-full border-2 border-[#3A5FC3] border-t-transparent" />
          {t.imports.inProgress}
        </span>
      );
    }
    if (item.status === "FAILED") {
      return (
        <span className={cancelledStatusBadgeClassName}>
          {t.imports.failed}
        </span>
      );
    }
    if (item.status === "CANCELLED") {
      return (
        <span className={cancelledStatusBadgeClassName}>
          {cancelledLabel(item)}
        </span>
      );
    }
    // Trùng file chưa xác nhận → "Bất thường", không phải "Cảnh báo"
    if (item.status === "STAGED" && item.duplicate_of) {
      const confirmed = confirmedImportIds.includes(item.id) || Boolean(item.normalization_summary);
      if (!confirmed) {
        return (
          <span className={abnormalStatusBadgeClassName}>
            {locale === "vi" ? "Bất thường" : "Abnormal"}
          </span>
        );
      }
    }
    if (isWarningStatus(item)) {
      return (
        <span className={abnormalStatusBadgeClassName}>
          {locale === "vi" ? "Cảnh báo" : "Warning"}
        </span>
      );
    }
    if (item.failed_records > 0) {
      return (
        <span className={activeStatusBadgeClassName}>
          {locale === "vi" ? "Đã tiếp nhận (có lỗi)" : "Ingested with errors"}
        </span>
      );
    }
    return (
      <span className={activeStatusBadgeClassName}>
        {locale === "vi" ? "Đã tiếp nhận" : "Ingestion complete"}
      </span>
    );
  };

  const renderNormalizationBadge = (item: ScopusImport) => {
    const n = item.normalization;
    if (n && n.status === "COMPLETED") {
      return (
        <span className={badgeClassName}>
          {locale === "vi" ? "Đã hoàn thành" : "Completed"}
        </span>
      );
    }
    if (n && n.status === "NORMALIZING") {
      return (
        <span className={`${badgeClassName} gap-1 border-blue-300 text-[#3A5FC3]`}>
          <span className="h-2 w-2 animate-spin rounded-full border-2 border-[#3A5FC3] border-t-transparent" />
          {locale === "vi" ? "Đang xử lý..." : "Processing"} ({n.progress_percent}%)
        </span>
      );
    }
    if (n && n.status === "FAILED") {
      return (
        <span className="inline-flex items-center rounded-[5px] border border-rose-300 bg-white px-2.5 py-0.5 text-sm font-bold text-rose-700">
          {locale === "vi" ? "Lỗi chuẩn hóa" : "Normalization failed"}
        </span>
      );
    }
    return (
      <span className={activeStatusBadgeClassName}>
        {locale === "vi" ? "Chờ chuẩn hóa" : "Awaiting normalization"}
      </span>
    );
  };

  const renderTypeBadge = (type?: string) => {
    if (type === "LECTURERS") {
      return (
        <span className={typeBadgeClassName}>
          {locale === "vi" ? "Giảng viên" : "Lecturer"}
        </span>
      );
    }
    return (
      <span className={typeBadgeClassName}>
        Scopus
      </span>
    );
  };

  const formatPerformedBy = (name: string | null | undefined): string => {
    if (!name || name === "Không xác định") {
      return locale === "vi" ? "Không xác định" : "Unknown";
    }
    if (isCorruptedName(name)) {
      return adminLabel(locale === "vi" ? "vi" : "en");
    }
    return name;
  };

  const renderUserBadge = (name: string | null) => {
    const cleanName = formatPerformedBy(name);
    if (cleanName === (locale === "vi" ? "Không xác định" : "Unknown")) {
      return (
        <span className={userBadgeClassName}>
          {cleanName}
        </span>
      );
    }
    return (
      <span
        title={cleanName}
        className={userBadgeClassName}
      >
        <span className="truncate max-w-[120px]">{cleanName}</span>
      </span>
    );
  };

  const selectFile = (file: File | undefined) => {
    if (!file || uploading) return;
    if (lecturerDataMissing) {
      notifyLecturerDataRequired();
      return;
    }
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

    setSelectionError("");
    setSelectedFile(file);
  };

  const clearFile = () => {
    if (uploading) return;
    setSelectedFile(null);
    setSelectionError("");
    setIsScopusFileExiting(false);
    if (inputRef.current) inputRef.current.value = "";
  };

  const exitScopusFile = () => {
    if (uploading) return;
    setIsScopusFileExiting(true);
    setTimeout(clearFile, 180);
  };

  const refreshHistory = async () => {
    try {
      const response = await getImportHistory(archiveFilter !== "active");
      setHistory(response.items);
    } catch {
      // non-critical error
    }
    try {
      setLecturerCount((await getImportPrerequisites()).lecturer_count);
    } catch {
      // non-critical: the server still enforces the rule
    }
  };

  useEffect(() => {
    void getImportPrerequisites()
      .then((res) => setLecturerCount(res.lecturer_count))
      .catch(() => setLecturerCount(null));
  }, []);

  const lecturerDataMissing = lecturerCount === 0;
  const lecturerDataMessage =
    locale === "vi"
      ? "Cần nhập danh sách giảng viên của trường (tệp JSON) trước khi nhập tệp Scopus."
      : "Import the school's lecturer list (JSON) before importing a Scopus file.";
  const notifyLecturerDataRequired = () => {
    toast.warning(locale === "vi" ? "Cần dữ liệu giảng viên" : "Lecturer data required", lecturerDataMessage);
  };

  const startImport = async () => {
    if (!selectedFile || uploading) return;
    setUploading(true);
    setSelectionError("");
    try {
      // An identical file is not refused: it is imported and flagged "Bất thường" for the reviewer.
      let wasDuplicate = false;
      const upload = async () => {
        try {
          return await uploadScopusCsv(selectedFile, false);
        } catch (error) {
          if (error instanceof ApiError && error.code === "DUPLICATE_IMPORT_CONFIRMATION_REQUIRED") {
            wasDuplicate = true;
            return uploadScopusCsv(selectedFile, true);
          }
          throw error;
        }
      };
      await Promise.all([upload(), new Promise((resolve) => setTimeout(resolve, 1500))]);
      setSelectedFile(null);
      if (inputRef.current) inputRef.current.value = "";
      sessionStorage.removeItem(PENDING_SCOPUS_IMPORT_KEY);
      setPendingImport(null);
      if (activeResultPanel === "scopus_checked") {
        setActiveResultPanel(null);
      }
      if (wasDuplicate) {
        toast.warning(
          locale === "vi" ? "Đã nạp tệp (Bất thường)" : "File uploaded (Abnormal)",
          locale === "vi"
            ? "Nội dung tệp trùng với một đợt nhập trước nên được đánh dấu 'Bất thường'. Bấm 'Chi tiết' trong danh sách để xem rồi xác nhận nhập."
            : "The file content matches an earlier import, so it is marked 'Abnormal'. Click 'Details' in the list to review and confirm."
        );
      } else {
        toast.success(
          t.imports.successTitle,
          locale === "vi"
            ? "Đã nạp tệp thành công (Trạng thái: Chờ xử lý). Bạn có thể bấm 'Chi tiết' trong danh sách để xem và xử lý tiếp."
            : "File uploaded successfully (Status: Awaiting processing). You can click 'Details' in the list to proceed."
        );
      }
      await refreshHistory();
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "LECTURER_DATA_REQUIRED") {
        setLecturerCount(0);
        notifyLecturerDataRequired();
        return;
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



  const cancelLecturerPreview = async () => {
    if (!lecturerPreview || lecturerCancelling || lecturerImporting) return;
    // Đóng box chi tiết ngay lập tức để người dùng quan sát hiệu ứng ngoài bảng
    setDetailOpen(false);
    setCancellingImportId(LECTURER_PREVIEW_ID);
    setLecturerCancelling(true);
    try {
      await Promise.all([
        cancelLecturerDatasetImport(lecturerPreview.file),
        new Promise((resolve) => setTimeout(resolve, 2000)),
      ]);
      sessionStorage.removeItem(PENDING_LECTURER_PREVIEW_KEY);
      await clearPendingLecturerFile();
      setLecturerPreview(null);
      setActiveResultPanel(null);
      await refreshHistory();
      toast.success(
        t.imports.cancelled,
        locale === "vi" ? "Đã hủy tiến trình nhập tệp." : "Import process cancelled."
      );
    } catch (error: unknown) {
      toast.error(
        t.imports.cancelFailed,
        error instanceof ApiError ? error.message : t.imports.cancelFailed,
      );
    } finally {
      setLecturerCancelling(false);
      setCancellingImportId(null);
    }
  };

  const handleConfirmLecturerImport = async () => {
    if (!lecturerPreview?.file || lecturerImporting) return;
    // Đóng box chi tiết ngay lập tức để người dùng quan sát hiệu ứng ngoài bảng
    setDetailOpen(false);
    setConfirmingImportId(LECTURER_PREVIEW_ID);
    setLecturerImporting(true);
    try {
      const [result] = await Promise.all([
        importLecturerDataset(lecturerPreview.file, lecturerPreview.displayId),
        new Promise((resolve) => setTimeout(resolve, 2000)),
      ]);
      sessionStorage.removeItem(PENDING_LECTURER_PREVIEW_KEY);
      await clearPendingLecturerFile();
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
      if (result.summary.accounts_skipped !== undefined && result.summary.accounts_skipped > 0) {
        toast.warning(
          t.lecturerImport.accountsSkipped,
          t.lecturerImport.accountsSkippedWarning.replace("{count}", String(result.summary.accounts_skipped)),
        );
      }
      await fetchData();
      // fetchData() only refreshes config + history; lecturerCount (used to
      // gate the Scopus upload box) is a separate piece of state and goes
      // stale here otherwise — re-fetch it so the "Cần dữ liệu giảng viên"
      // warning doesn't keep firing right after a successful import.
      try {
        setLecturerCount((await getImportPrerequisites()).lecturer_count);
      } catch {
        // non-critical: the server still enforces the rule
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
      setLecturerImporting(false);
      setConfirmingImportId(null);
    }
  };

  const openDetail = async (item: ScopusImport) => {
    if (item.id === LECTURER_PREVIEW_ID) {
      if (!lecturerPreview) {
        warnPendingAction();
        return;
      }
      setDetail(item);
      setDetailOpen(true);
      return;
    }
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

  const handleConfirmImport = async (item: ScopusImport) => {
    // Đóng box chi tiết ngay lập tức để người dùng thấy nhãn loading ngoài bảng
    setDetailOpen(false);
    setConfirmingImportId(item.id);
    try {
      const next = [...confirmedImportIds, item.id];
      localStorage.setItem(CONFIRMED_IMPORTS_KEY, JSON.stringify(next));
      setConfirmedImportIds(next);
      // Hiệu ứng loading 2s trực tiếp trên nhãn ngoài bảng
      await new Promise((resolve) => setTimeout(resolve, 2000));
      toast.success(
        t.imports.successTitle,
        locale === "vi"
          ? `Đã xác nhận nhập thành công ${numberFormatter.format(item.total_records)} bản ghi.`
          : `Successfully confirmed import of ${numberFormatter.format(item.total_records)} records.`
      );
    } catch {
      // ignore
    } finally {
      setConfirmingImportId(null);
    }
  };

  const handleCancelProcess = async (item: ScopusImport) => {
    // Đóng box chi tiết ngay lập tức để người dùng thấy nhãn loading ngoài bảng
    setDetailOpen(false);
    setCancellingImportId(item.id);
    setIsCancelling(true);
    try {
      // Chạy lệnh hủy và duy trì hiệu ứng loading 2s trực tiếp trên nhãn ngoài bảng
      await Promise.all([
        cancelImport(item.id),
        new Promise((resolve) => setTimeout(resolve, 2000)),
      ]);
      await refreshHistory();
      toast.success(
        t.imports.cancelled,
        locale === "vi" ? "Đã hủy tiến trình nhập tệp." : "Import process cancelled."
      );
    } catch (error: unknown) {
      toast.error(
        t.imports.cancelFailed,
        error instanceof ApiError ? error.message : t.imports.cancelFailed,
      );
    } finally {
      setIsCancelling(false);
      setCancellingImportId(null);
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
    if (isAwaitingConfirmation(item)) {
      warnPendingAction();
      return;
    }
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

  const viewPreviousImport = async (importId: string | undefined) => {
    if (!importId) return;
    try {
      const previous = await getImportDetail(importId);
      setDetail(previous);
      setDetailOpen(true);
    } catch (error: unknown) {
      toast.error(t.imports.errorTitle, error instanceof ApiError ? error.message : t.imports.loadError);
    }
  };

  // Filter & Pagination calculations
  const lecturerPreviewRow: ScopusImport | null = lecturerPreview
    ? {
        id: LECTURER_PREVIEW_ID,
        type: "LECTURERS",
        file_name: lecturerPreview.preview.filename,
        status: "STAGED",
        total_records: lecturerPreview.preview.summary.total,
        imported_records: lecturerPreview.preview.summary.valid,
        failed_records: 0,
        processed_records: lecturerPreview.preview.summary.valid,
        progress_percent: 100,
        duplicate_candidates: lecturerPreview.preview.summary.conflicts,
        duplicate_of: lecturerPreview.duplicate
          ? {
              import_id: lecturerPreview.duplicate.importId,
              file_name: lecturerPreview.duplicate.filename,
              imported_at: lecturerPreview.duplicate.importedAt,
            }
          : null,
        row_errors: [],
        error_summary: null,
        normalization: null,
        version: 0,
        created_at: lecturerPreview.at,
        updated_at: lecturerPreview.at,
        started_at: lecturerPreview.at,
        finished_at: null,
        duration_seconds: 0,
        is_terminal: false,
        performed_by: user?.display_name ?? null,
        lecturer_summary: {
          created: lecturerPreview.preview.summary.create,
          updated: lecturerPreview.preview.summary.update,
          unchanged: lecturerPreview.preview.summary.unchanged,
          conflicts: lecturerPreview.preview.summary.conflicts,
          warnings: lecturerPreview.preview.summary.conflicts,
        },
      }
    : null;
  const tableHistory = lecturerPreviewRow
    ? [lecturerPreviewRow, ...history].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
    : history;

  // Status-filter calculations — must include the in-progress lecturer
  // preview row (tableHistory), not just confirmed server-side history,
  // otherwise the "Total" count undercounts by 1 while a JSON preview is
  // pending.
  const isCancelled = (item: ScopusImport): boolean => item.status === "CANCELLED";
  const isSuperseded = (item: ScopusImport): boolean =>
    statusLabel(item) === (locale === "vi" ? "Thay thế" : "Superseded");
  // Its Scopus rows haven't gone through normalization yet — a distinct,
  // still-in-progress state, not lumped into "Hoạt động" or "Bất thường".
  const isAwaitingNormalization = (item: ScopusImport): boolean =>
    statusLabel(item) === (locale === "vi" ? "Chờ chuẩn hóa" : "Awaiting normalization");
  // Not yet confirmed/applied at all — distinct from "Chờ chuẩn hóa" (confirmed,
  // waiting on the normalization pipeline). Previously lumped into "Hoạt động".
  const isAwaitingProcessing = (item: ScopusImport): boolean =>
    statusLabel(item) === (locale === "vi" ? "Chờ xử lý" : "Awaiting processing");
  // A real problem: failed outright, or completed with warnings. Deliberate
  // administrative states (cancelled, superseded) are their own categories,
  // not "abnormal" — nothing went wrong, an admin acted on purpose.
  const isAbnormal = (item: ScopusImport): boolean =>
    !isCancelled(item) && !isSuperseded(item) && !isAwaitingNormalization(item) &&
    (item.status === "FAILED" || isWarningStatus(item));
  // Active = everything still alive and working as intended: in progress,
  // awaiting confirmation, or finished cleanly — i.e. none of the other
  // five categories.
  const isActive = (item: ScopusImport): boolean =>
    !isAbnormal(item) && !isCancelled(item) && !isSuperseded(item) &&
    !isAwaitingNormalization(item) && !isAwaitingProcessing(item);

  const countTotal = tableHistory.length;
  const countAwaitingProcessing = tableHistory.filter(isAwaitingProcessing).length;
  const countActive = tableHistory.filter(isActive).length;
  const countAbnormal = tableHistory.filter(isAbnormal).length;
  const countCancelled = tableHistory.filter(isCancelled).length;
  const countSuperseded = tableHistory.filter(isSuperseded).length;
  const countAwaitingNormalization = tableHistory.filter(isAwaitingNormalization).length;

  const filteredHistory = tableHistory.filter((item) => {
    const q = searchInput.trim().toLowerCase();
    const matchesSearch =
      !q ||
      item.file_name.toLowerCase().includes(q) ||
      (item.performed_by && item.performed_by.toLowerCase().includes(q)) ||
      item.id.toLowerCase().includes(q) ||
      (item.type && item.type.toLowerCase().includes(q));

    let matchesStatus = true;
    if (statusFilter === "AWAITING_PROCESSING") {
      matchesStatus = isAwaitingProcessing(item);
    } else if (statusFilter === "ACTIVE") {
      matchesStatus = isActive(item);
    } else if (statusFilter === "ABNORMAL") {
      matchesStatus = isAbnormal(item);
    } else if (statusFilter === "CANCELLED") {
      matchesStatus = isCancelled(item);
    } else if (statusFilter === "SUPERSEDED") {
      matchesStatus = isSuperseded(item);
    } else if (statusFilter === "AWAITING_NORMALIZATION") {
      matchesStatus = isAwaitingNormalization(item);
    }

    return matchesSearch && matchesStatus;
  });

  const totalPages = Math.max(1, Math.ceil(filteredHistory.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const paginatedHistory = filteredHistory.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );

  const handlePageChange = (newPage: number) => {
    if (newPage === page || newPage < 1 || newPage > totalPages || isPageLoading) return;
    setPage(newPage);
  };

  const handlePageSizeChange = (newSize: number) => {
    if (newSize === pageSize || isPageLoading) return;
    setPageSize(newSize);
    setPage(1);
  };

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

      {/* Import Boxes Grid: 1 row, 2 boxes (1:1 ratio) - Left: Scopus CSV, Right: Lecturer JSON */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5 items-stretch">
        {/* Left Box: Tải tệp Scopus */}
        <section className="flex flex-col h-full rounded-[5px] border border-slate-200/80 bg-white p-4 sm:p-5 shadow-xs">
          <div className="flex items-center gap-2.5 pb-3.5 border-b border-slate-100">
            <div className="flex h-8 w-8 items-center justify-center rounded-[5px] bg-[#3A5FC3]/10 text-[#3A5FC3]">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l9-5-9-5-9 5 9 5zm0 0v6m0 0l3-3m-3 3l-3-3" />
              </svg>
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">
                {t.imports.uploadTitle}
              </h2>
              <p className="text-sm text-slate-500">
                {t.imports.uploadSubtitle}
              </p>
            </div>
          </div>

          {!selectedFile ? (
            <div
              onClick={() => {
                if (uploading) return;
                if (lecturerDataMissing) notifyLecturerDataRequired();
                else inputRef.current?.click();
              }}
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
              className={`mt-4 group flex flex-1 min-h-44 flex-col items-center justify-center rounded-[5px] border-2 border-dashed px-4 py-6 text-center cursor-pointer transition-all duration-200 ${
                dragging
                  ? "border-[#3A5FC3] bg-[#3A5FC3]/10 scale-[0.99]"
                  : "border-slate-200 hover:border-[#3A5FC3]/60 bg-slate-50/40 hover:bg-[#3A5FC3]/5"
              } ${uploading ? "cursor-not-allowed opacity-60" : ""}`}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-[5px] bg-[#3A5FC3]/10 text-[#3A5FC3] mb-2.5 shadow-2xs group-hover:scale-110 transition-transform">
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M7 19a4 4 0 01-.88-7.903A5.002 5.002 0 0116.9 9H17a4 4 0 010 8h-1m-4-6v6m0 0l-2-2m2 2l2-2" />
                </svg>
              </div>
              <p className="text-sm font-semibold text-slate-700 group-hover:text-[#3A5FC3] transition-colors">
                {dragging
                  ? t.imports.dragActivePrompt
                  : locale === "vi"
                    ? "Nhấp hoặc kéo thả tệp CSV vào đây để tải lên"
                    : "Click or drag and drop a CSV file here to upload"}
              </p>
              <p className="mt-1 text-sm text-slate-400">
                {replaceToken(t.imports.supportedHint, "size", maxSize)}
              </p>
            </div>
          ) : (
            <div className={`mt-4 flex flex-1 min-h-44 flex-col justify-center rounded-[5px] border border-slate-200/80 bg-slate-50/50 p-4 sm:p-5 transition-all duration-300 ease-out ${isScopusFileExiting ? "opacity-0 scale-[0.97] -translate-y-1" : "opacity-100 scale-100 translate-y-0 animate-in fade-in slide-in-from-top-2 duration-300"}`}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="flex h-10 w-10 items-center justify-center rounded-[5px] bg-blue-100/80 text-[#3A5FC3] shrink-0">
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div className="min-w-0 flex-1">
                    <span
                      className="block font-semibold text-slate-800 text-sm leading-snug break-all line-clamp-2"
                      title={selectedFile.name}
                    >
                      {selectedFile.name}
                    </span>
                    <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-sm text-slate-500">
                      <span>{locale === "vi" ? "Dung lượng:" : "Size:"} <strong className="text-slate-700">{formatBytes(selectedFile.size)}</strong></span>
                      <span>•</span>
                      <span>{locale === "vi" ? "Định dạng:" : "Format:"} <strong className="text-slate-700">CSV</strong></span>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col gap-2 shrink-0 w-full sm:w-40 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-200/60 justify-center">
                  <button
                    type="button"
                    disabled={uploading}
                    onClick={() => void startImport()}
                    className={`${buttonClass("primary", "md", true)} w-full`}
                  >
                    {uploading ? (
                      <>
                        <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                        <span>{locale === "vi" ? "Đang xử lý..." : "Processing..."}</span>
                      </>
                    ) : (
                      <>
                        <svg className="h-4 w-4 shrink-0 group-hover:scale-110 transition-transform duration-150" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>{locale === "vi" ? "Kiểm tra dữ liệu" : "Check data"}</span>
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    disabled={uploading}
                    onClick={exitScopusFile}
                    className={`${buttonClass("secondary", "md", true)} w-full`}
                  >
                    {t.imports.cancelFile}
                  </button>
                </div>
              </div>
            </div>
          )}

          {selectionError && (
            <div role="alert" className="mt-3 flex items-center gap-2 rounded-[5px] border border-rose-200 bg-rose-50/80 p-3 text-sm font-semibold text-rose-700">
              <svg className="h-4 w-4 shrink-0 text-rose-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{selectionError}</span>
            </div>
          )}

        </section>

        {/* Right Box: Dữ liệu giảng viên ICTU */}
        <LecturerDatasetImportCard
          ref={lecturerCardRef}
          isImporting={lecturerImporting}
          onPreviewGenerated={(preview, file, duplicateOf) => {
            const at = new Date().toISOString();
            const displayId = generateDisplayId();
            setLecturerPreview({ preview, file, at, displayId, duplicate: duplicateOf ?? null });
            setActiveResultPanel("lecturer_preview");
            sessionStorage.setItem(
              PENDING_LECTURER_PREVIEW_KEY,
              JSON.stringify({ preview, at, displayId, duplicate: duplicateOf ?? null }),
            );
            void savePendingLecturerFile(file).catch((error: unknown) => {
              sessionStorage.removeItem(PENDING_LECTURER_PREVIEW_KEY);
              toast.error(
                t.imports.errorTitle,
                locale === "vi"
                  ? "Không thể lưu tạm tệp JSON để khôi phục khi quay lại."
                  : "Unable to save the JSON file for restoration.",
              );
              console.error("Failed to persist pending lecturer file", error);
            });
          }}
          onFileCleared={() => {
            setLecturerPreview(null);
            sessionStorage.removeItem(PENDING_LECTURER_PREVIEW_KEY);
            void clearPendingLecturerFile().catch((error: unknown) => {
              console.error("Failed to clear pending lecturer file", error);
            });
            if (activeResultPanel === "lecturer_preview") {
              setActiveResultPanel(null);
            }
          }}
          onFileSelected={() => {
            setLecturerPreview(null);
            sessionStorage.removeItem(PENDING_LECTURER_PREVIEW_KEY);
            void clearPendingLecturerFile().catch((error: unknown) => {
              console.error("Failed to clear pending lecturer file", error);
            });
            if (activeResultPanel === "lecturer_preview") {
              setActiveResultPanel(null);
            }
          }}
        />
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col gap-3 rounded-[5px] border border-slate-200/80 bg-white p-3.5 shadow-xs sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            aria-label={t.common.search}
            value={searchInput}
            onChange={(e) => { setSearchInput(e.target.value); setPage(1); }}
            placeholder={t.imports.searchPlaceholder}
            className="h-control w-full rounded-control border border-line bg-slate-50 pl-9 pr-3 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20"
          />
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <select
            aria-label={t.common.status}
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="h-control shrink-0 rounded-control border border-line bg-slate-50 px-3 text-sm font-semibold text-ink focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20 cursor-pointer"
          >
            <option value="ALL">
              {t.imports.statusAll} ({numberFormatter.format(countTotal)})
            </option>
            <option value="AWAITING_PROCESSING">
              {t.imports.statusAwaitingProcessing} ({numberFormatter.format(countAwaitingProcessing)})
            </option>
            <option value="ACTIVE">
              {t.imports.statusActive} ({numberFormatter.format(countActive)})
            </option>
            <option value="ABNORMAL">
              {t.imports.statusAbnormal} ({numberFormatter.format(countAbnormal)})
            </option>
            <option value="CANCELLED">
              {t.imports.statusCancelled} ({numberFormatter.format(countCancelled)})
            </option>
            <option value="SUPERSEDED">
              {t.imports.statusSuperseded} ({numberFormatter.format(countSuperseded)})
            </option>
            <option value="AWAITING_NORMALIZATION">
              {t.imports.statusAwaitingNormalization} ({numberFormatter.format(countAwaitingNormalization)})
            </option>
          </select>

          {/* Nút Đặt lại */}
          <button
            type="button"
            onClick={() => {
              setSearchInput("");
              setStatusFilter("ALL");
              setArchiveFilter("active");
              setPage(1);
            }}
            disabled={!searchInput && statusFilter === "ALL"}
            className={buttonClass("secondary")}
          >
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span className="truncate">{locale === "vi" ? "Đặt lại" : "Reset"}</span>
          </button>
        </div>
      </div>

      {/* History Table Card */}
      <section className="overflow-hidden rounded-[5px] border border-slate-200/80 bg-white shadow-xs">
        <div className="relative overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
              <tr>
                <th className="px-2.5 py-3.5 font-bold text-slate-700 whitespace-nowrap">{t.imports.fileName}</th>
                <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Loại dữ liệu" : "Data Type"}</th>
                <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{t.imports.time}</th>
                <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{locale === "vi" ? "Đã nạp / Bản ghi" : "Imported / Total"}</th>
                <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{t.imports.performedBy}</th>
                <th className="px-2.5 py-3.5 text-center font-bold text-slate-700 whitespace-nowrap">{t.common.status}</th>
                {/* UI-10: keep the actions column visible at every width (sticky right edge) */}
                <th className="sticky right-0 z-[1] w-44 whitespace-nowrap border-l border-slate-200/80 bg-slate-50 px-2.5 py-3.5 text-center font-bold text-slate-700">{t.imports.actions}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading || isPageLoading ? (
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
                    <div className="flex flex-col items-center justify-center gap-1.5">
                      <div className="flex h-10 w-10 items-center justify-center rounded-[5px] bg-slate-100/80 border border-slate-200/80 text-slate-400 mb-1">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <span className="text-sm font-bold text-slate-700">{t.imports.noHistory}</span>
                      <span className="text-sm text-slate-400">
                        {locale === "vi" ? "Các lần nhập dữ liệu CSV và JSON sẽ xuất hiện tại đây." : "Import history will appear here."}
                      </span>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedHistory.map((item) => (
                  <tr
                    key={item.id}
                    className={`transition-colors duration-300 ${
                      confirmingImportId === item.id
                        ? "bg-blue-50/60"
                        : cancellingImportId === item.id
                          ? "bg-red-50/40"
                          : "hover:bg-slate-50/50"
                    }`}
                  >
                    <td className="px-2.5 py-3.5 align-middle whitespace-nowrap">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-[5px] border border-slate-200/80 bg-slate-100 text-slate-600 shrink-0 shadow-2xs">
                          {item.type === "LECTURERS" ? (
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
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
                          <span
                            className="block text-sm font-mono font-medium text-slate-400 truncate"
                            title={item.id === LECTURER_PREVIEW_ID ? (lecturerPreview?.displayId ?? item.id) : item.id}
                          >
                            ID: {shortId(item.id === LECTURER_PREVIEW_ID ? (lecturerPreview?.displayId ?? item.id) : item.id)}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap font-medium">
                      {renderTypeBadge(item.type)}
                    </td>

                    <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap font-medium text-slate-600">
                      {formatDate(item.created_at)}
                    </td>

                    <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap font-bold text-slate-800">
                      <span>
                        {`${numberFormatter.format(
                          item.status === "CANCELLED" ||
                            item.status === "FAILED" ||
                            statusLabel(item) === (locale === "vi" ? "Thay thế" : "Superseded")
                            ? 0
                            : item.type === "LECTURERS"
                              ? item.imported_records
                              : item.processed_records
                        )} / ${numberFormatter.format(item.total_records)}`}
                      </span>
                      {ACTIVE_STATUSES.includes(item.status) && (
                        <div className="mx-auto mt-1 h-1 w-20 overflow-hidden rounded-full bg-slate-200">
                          <div className="h-full bg-[#3A5FC3]" style={{ width: `${item.progress_percent}%` }} />
                        </div>
                      )}
                    </td>

                    <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                      {renderUserBadge(item.performed_by)}
                    </td>

                    <td className="px-2.5 py-3.5 text-center align-middle whitespace-nowrap">
                      {renderTableStatusBadge(item)}
                    </td>

                    <td className="sticky right-0 z-[1] whitespace-nowrap border-l border-slate-100 bg-white px-2.5 py-3.5 text-center align-middle">
                      <button
                        type="button"
                        onClick={() => openDetail(item)}
                        className="inline-flex w-32 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 py-0.5 text-sm font-bold text-slate-700 hover:bg-slate-50 hover:border-slate-400 hover:text-slate-900 transition-colors cursor-pointer"
                      >
                        {t.imports.detail}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer info & Pagination Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-sm text-slate-500">
          <div className="flex items-center gap-3">
            <span>
              {t.imports.showing} <strong>{paginatedHistory.length}</strong> {locale === "vi" ? "trong" : "of"} <strong>{filteredHistory.length}</strong> {locale === "vi" ? "đợt nhập" : "imports"}
            </span>

            {/* Page Size Selector */}
            <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
              <span className="text-slate-500">{locale === "vi" ? "Hiển thị:" : "Show:"}</span>
              <select
                value={pageSize}
                disabled={isPageLoading}
                onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                className="h-7 rounded-[5px] border border-slate-200 bg-white px-1.5 text-sm font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer disabled:opacity-50"
              >
                <option value={10}>10 / {locale === "vi" ? "trang" : "page"}</option>
                <option value={30}>30 / {locale === "vi" ? "trang" : "page"}</option>
                <option value={50}>50 / {locale === "vi" ? "trang" : "page"}</option>
                <option value={100}>100 / {locale === "vi" ? "trang" : "page"}</option>
              </select>
            </div>
          </div>

          <nav aria-label="Pagination" className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1 || isPageLoading}
              className={buttonClass("secondary", "sm")}
            >
              {t.imports.previousPage}
            </button>
            <span className="text-slate-400 px-0.5">{t.imports.page}</span>
            <input
              type="number"
              aria-label={locale === "vi" ? "Đến trang" : "Go to page"}
              min={1}
              max={totalPages}
              value={currentPage}
              disabled={isPageLoading}
              onChange={(e) => {
                const val = Math.max(1, Math.min(totalPages, parseInt(e.target.value, 10) || 1));
                handlePageChange(val);
              }}
              className="h-8 w-14 rounded-[5px] border border-slate-200 bg-white px-2 text-center text-sm font-bold text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 disabled:opacity-50 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
            <span className="text-slate-400">/ <strong className="text-slate-600">{totalPages}</strong></span>
            <button
              type="button"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= totalPages || isPageLoading}
              className={buttonClass("secondary", "sm")}
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
          <div className="fixed inset-x-0 top-16 bottom-0 md:left-[var(--app-sidebar-w)] z-50 flex items-center justify-center overflow-hidden bg-black/60 p-4 modal-backdrop-in transition-[left] duration-200 ease-out">
            <section
              role="dialog"
              aria-modal="true"
              aria-labelledby="import-detail-title"
              className="flex h-full w-full max-w-none flex-col overflow-hidden rounded-card border border-blue-200 bg-white shadow-2xl modal-panel-in"
            >
              <header className="flex shrink-0 items-start justify-between gap-4 border-b border-blue-100 bg-blue-50 px-5 py-4">
                <div className="min-w-0">
                  <h2 id="import-detail-title" className="text-base font-bold text-[#2f4ea6] sm:text-lg">
                    {locale === "vi" ? "Chi tiết đợt nhập" : "Import detail"}
                  </h2>
                  <p className="mt-0.5 text-sm text-[#3A5FC3]">
                    {locale === "vi"
                      ? "Thông tin tiếp nhận và tình trạng sử dụng dữ liệu."
                      : "Ingestion information and data usage status."}
                  </p>
                </div>
              </header>

              <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
                {detail?.duplicate_of &&
                  !confirmedImportIds.includes(detail.id) &&
                  !detail.normalization_summary && (
                    <div
                      className="mb-4 rounded-[5px] border border-amber-300 bg-white p-4"
                      role="alert"
                      data-testid="duplicate-import-banner"
                    >
                      <h3 className="text-sm font-bold text-amber-700">
                        {locale === "vi" ? "Tệp dữ liệu đã được nhập trước đó" : "This file was imported before"}
                      </h3>
                      <p className="mt-1 text-sm text-slate-600">
                        {locale === "vi"
                          ? "Tệp có nội dung trùng với một đợt nhập trước. Đợt này được đánh dấu \"Bất thường\"; bạn có thể \"Xem đợt trước\" để đối chiếu, hoặc xác nhận nhập/hủy tiến trình bên dưới."
                          : "The file content matches an earlier import. This one is marked \"Abnormal\"; you can view the earlier import to compare, or confirm/cancel below."}
                      </p>
                      <dl className="mt-2 space-y-0.5 text-sm text-slate-700">
                        <div>
                          <dt className="inline font-semibold">{locale === "vi" ? "Tệp đã chọn: " : "Selected file: "}</dt>
                          <dd className="inline break-all">{detail.file_name}</dd>
                        </div>
                        <div>
                          <dt className="inline font-semibold">{locale === "vi" ? "Đợt nhập trước: " : "Earlier import: "}</dt>
                          <dd className="inline break-all">
                            {detail.duplicate_of.file_name} · {formatDate(detail.duplicate_of.imported_at)}
                          </dd>
                        </div>
                      </dl>
                    </div>
                  )}
                {detailLoading || !detail ? (
                  <div className="flex min-h-40 items-center justify-center">
                    <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                  </div>
                ) : detail.type === "LECTURERS" ? (
                  <div className="space-y-4">
                    <div className="space-y-4">
                      <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
                        <div className="mb-3 border-b border-slate-100 pb-3">
                          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                            {locale === "vi" ? "Tiếp nhận dữ liệu" : "Data ingestion"}
                          </h3>
                          <span className="text-sm font-medium text-slate-500">
                            {locale === "vi" ? "Dữ liệu giảng viên" : "Lecturer dataset"}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-center">
                          <div className="flex h-16 flex-col items-center justify-center rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium uppercase text-slate-500">{t.lecturerImport.totalRecords}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.total_records)}</p>
                          </div>
                          <div className="flex h-16 flex-col items-center justify-center rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium uppercase text-slate-500">{t.lecturerImport.created}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.lecturer_summary?.created ?? detail.imported_records)}</p>
                          </div>
                          <div className="flex h-16 flex-col items-center justify-center rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium uppercase text-slate-500">{t.lecturerImport.updated}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.lecturer_summary?.updated ?? 0)}</p>
                          </div>
                          <div className="flex h-16 flex-col items-center justify-center rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium uppercase text-slate-500">{t.lecturerImport.unchanged}</span>
                            <p className="mt-0.5 text-base font-black text-slate-700">{numberFormatter.format(detail.lecturer_summary?.unchanged ?? 0)}</p>
                          </div>
                          {detail.id !== LECTURER_PREVIEW_ID && (
                            <>
                              <div className="flex h-16 flex-col items-center justify-center rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                                <span className="text-sm font-medium uppercase text-slate-500">{t.lecturerImport.accountsCreated}</span>
                                <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.lecturer_summary?.accounts_created ?? 0)}</p>
                              </div>
                              <div className={`flex h-16 flex-col items-center justify-center rounded-[5px] border p-2.5 shadow-2xs ${(detail.lecturer_summary?.accounts_skipped ?? 0) > 0 ? "border-amber-200 bg-amber-50/80" : "border-slate-200/80 bg-white"}`}>
                                <span className={`text-sm font-medium uppercase ${(detail.lecturer_summary?.accounts_skipped ?? 0) > 0 ? "text-amber-700" : "text-slate-500"}`}>{t.lecturerImport.accountsSkipped}</span>
                                <p className={`mt-0.5 text-base font-black ${(detail.lecturer_summary?.accounts_skipped ?? 0) > 0 ? "text-amber-800" : "text-slate-700"}`}>{numberFormatter.format(detail.lecturer_summary?.accounts_skipped ?? 0)}</p>
                              </div>
                            </>
                          )}
                        </div>
                      </section>

                      <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
                        <div className="mb-3 border-b border-slate-100 pb-3">
                          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                            {locale === "vi" ? "Thông tin tệp" : "File information"}
                          </h3>
                          <span className="text-sm font-medium text-slate-500">
                            {locale === "vi" ? "Thông tin đợt nhập" : "Import details"}
                          </span>
                        </div>
                        <dl className="space-y-3 text-sm">
                          <div className="min-w-0">
                            <dt className="text-slate-400">{t.imports.fileName}</dt>
                            <dd className="font-semibold text-slate-800 whitespace-nowrap" title={detail.file_name}>{detail.file_name}</dd>
                          </div>
                          <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                            <div className="min-w-0">
                              <dt className="text-slate-400">{locale === "vi" ? "Thời gian nhập" : "Imported at"}</dt>
                              <dd className="font-medium text-slate-700">{formatDate(detail.created_at)}</dd>
                            </div>
                            <div className="min-w-0">
                              <dt className="text-slate-400">{t.imports.performedBy}</dt>
                              <dd className="font-semibold text-slate-700 truncate">{formatPerformedBy(detail.performed_by)}</dd>
                            </div>
                          </div>
                        </dl>
                      </section>
                    </div>

                    {detail.id !== LECTURER_PREVIEW_ID && (detail.lecturer_summary?.accounts_skipped ?? 0) > 0 && (
                      <div className="rounded-[5px] border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800" role="alert">
                        <div className="flex items-start gap-2">
                          <svg className="h-4 w-4 shrink-0 mt-0.5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                          </svg>
                          <span>
                            <strong>{t.lecturerImport.accountsSkipped}:</strong>{" "}
                            {t.lecturerImport.accountsSkippedWarning.replace("{count}", String(detail.lecturer_summary?.accounts_skipped ?? 0))}
                          </span>
                        </div>
                        {(detail.lecturer_summary?.account_warnings ?? []).length > 0 && (
                          <ul className="mt-2 ml-6 space-y-1 text-amber-700">
                            {(detail.lecturer_summary?.account_warnings ?? []).map((w, i) => (
                              <li key={i} className="leading-relaxed">
                                <span className="font-medium">{w.record_full_name ?? "—"}</span>
                                {w.reason ? <span className="text-amber-600"> — {w.reason}</span> : null}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                    {lecturerPreview && detail.id === LECTURER_PREVIEW_ID && lecturerPreview.preview.conflicts.length > 0 ? (
                      <div className="rounded-[5px] border border-amber-200 bg-amber-50/90 p-4 text-sm text-amber-900 shadow-2xs">
                        <div className="flex items-center gap-2 font-bold text-amber-900">
                          <svg className="h-4 w-4 shrink-0 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                          </svg>
                          <span>
                            {locale === "vi"
                              ? `Phát hiện ${lecturerPreview.preview.conflicts.length} cảnh báo trùng tên cán bộ (hệ thống vẫn lưu trữ riêng biệt):`
                              : `${lecturerPreview.preview.conflicts.length} duplicate name warnings detected (retained separately):`}
                          </span>
                        </div>
                        <ul className="mt-2.5 list-disc list-inside space-y-1 text-slate-700 max-h-32 overflow-y-auto">
                          {lecturerPreview.preview.conflicts.map((c, i) => (
                            <li key={i} className="text-sm leading-relaxed">
                              <strong>{c.record_full_name}</strong> {locale === "vi" ? "trùng tên với" : "matches name of"} <strong>{c.existing_full_name}</strong> {c.existing_email ? `(${c.existing_email})` : ""}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : (detail.lecturer_summary?.warnings ?? detail.duplicate_candidates) > 0 ? (
                      <div className="rounded-[5px] border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                        <strong>{locale === "vi" ? "Cảnh báo trùng tên" : "Duplicate name warnings"}:</strong>{" "}
                        {numberFormatter.format(detail.lecturer_summary?.warnings ?? detail.duplicate_candidates)}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* SECTION 1: TIẾP NHẬN NGUỒN */}
                    <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
                      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                            {t.imports.sourceIngestion}
                          </h3>
                        </div>
                        {renderIngestionBadge(detail)}
                      </div>

                      {/* Raw stats */}
                      <div className="grid grid-cols-2 gap-2 text-center mb-3 sm:grid-cols-4">
                        <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                          <span className="text-sm font-medium text-slate-500 uppercase">{t.imports.totalRecords}</span>
                          <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.total_records)}</p>
                        </div>
                        <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                          <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Đã xử lý" : "Processed"}</span>
                          <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.processed_records)}</p>
                        </div>
                        <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                          <span className="text-sm font-medium text-slate-500 uppercase">{t.imports.importedRecords}</span>
                          <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.status === "CANCELLED" || detail.status === "FAILED" || statusLabel(detail) === (locale === "vi" ? "Thay thế" : "Superseded") ? 0 : detail.imported_records)}</p>
                        </div>
                        <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                          <span className="text-sm font-medium text-slate-500 uppercase">{t.imports.failedRecords}</span>
                          <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.failed_records)}</p>
                        </div>
                      </div>

                      {/* Metadata summary */}
                      <dl className="space-y-3 border-t border-slate-100 pt-3 text-sm">
                        <div className="min-w-0">
                          <dt className="text-slate-400">{t.imports.fileName}</dt>
                          <dd className="font-semibold text-slate-800 whitespace-nowrap" title={detail.file_name}>{detail.file_name}</dd>
                        </div>
                        <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-3">
                          <div className="min-w-0">
                            <dt className="text-slate-400">{t.imports.performedBy}</dt>
                            <dd className="font-semibold text-slate-700 truncate">{formatPerformedBy(detail.performed_by)}</dd>
                          </div>
                          <div className="min-w-0">
                            <dt className="text-slate-400">{locale === "vi" ? "Bắt đầu lúc" : "Started at"}</dt>
                            <dd className="font-medium text-slate-700">{formatDate(detail.started_at)}</dd>
                          </div>
                          {detail.finished_at && (
                            <div className="min-w-0">
                              <dt className="text-slate-400">
                                {detail.status === "CANCELLED"
                                  ? (locale === "vi" ? "Thời điểm hủy" : "Cancelled at")
                                  : (locale === "vi" ? "Kết thúc lúc" : "Finished at")}
                              </dt>
                              <dd className="font-medium text-slate-700">{formatDate(detail.finished_at)} ({formatDuration(detail.duration_seconds)})</dd>
                            </div>
                          )}
                        </div>
                      </dl>
                    </section>

                    {/* SECTION: KẾT QUẢ CHUẨN HÓA CÔNG BỐ (admin full visibility) */}
                    {detail.normalization && (
                      <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
                        <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                            {locale === "vi" ? "Kết quả chuẩn hóa công bố" : "Publication normalization result"}
                          </h3>
                          {renderNormalizationBadge(detail)}
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-center sm:grid-cols-3 lg:grid-cols-6">
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Đã xử lý" : "Processed"}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.normalization.canonical_processed)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Công bố mới" : "New"}</span>
                            <p className="mt-0.5 text-base font-black text-emerald-700">{numberFormatter.format(detail.normalization.canonical_new)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Đã tồn tại" : "Existing"}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.normalization.canonical_existing)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Đổi metadata" : "Metadata changed"}</span>
                            <p className="mt-0.5 text-base font-black text-amber-700">{numberFormatter.format(detail.normalization.canonical_metadata_changed)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Trùng lặp nội bộ" : "Intra-duplicate"}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.normalization.canonical_intra_duplicate)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{t.imports.failedRecords}</span>
                            <p className="mt-0.5 text-base font-black text-rose-700">{numberFormatter.format(detail.normalization.canonical_failed)}</p>
                          </div>
                        </div>
                      </section>
                    )}

                    {/* SECTION: KẾT QUẢ CHUẨN HÓA TÁC GIẢ (admin full visibility) */}
                    {detail.normalization_summary?.authors && (
                      <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
                        <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                            {locale === "vi" ? "Kết quả chuẩn hóa tác giả" : "Author normalization result"}
                          </h3>
                          <span className={
                            detail.normalization_summary.authors.status === "COMPLETED"
                              ? badgeClassName
                              : detail.normalization_summary.authors.status === "FAILED"
                                ? "inline-flex items-center rounded-[5px] border border-rose-300 bg-white px-2.5 py-0.5 text-sm font-bold text-rose-700"
                                : activeStatusBadgeClassName
                          }>
                            {detail.normalization_summary.authors.status === "COMPLETED"
                              ? (locale === "vi" ? "Đã hoàn thành" : "Completed")
                              : detail.normalization_summary.authors.status === "FAILED"
                                ? (locale === "vi" ? "Lỗi chuẩn hóa" : "Normalization failed")
                                : (locale === "vi" ? "Đang xử lý..." : "Processing")}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-center sm:grid-cols-3 lg:grid-cols-6">
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Tác giả duy nhất" : "Unique authors"}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.normalization_summary.authors.unique_authors_seen)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Tác giả mới" : "New authors"}</span>
                            <p className="mt-0.5 text-base font-black text-emerald-700">{numberFormatter.format(detail.normalization_summary.authors.authors_created)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Tác giả đã có" : "Existing authors"}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.normalization_summary.authors.authors_existing)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Biến thể tên mới" : "New name variants"}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.normalization_summary.authors.variants_created)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Liên kết mới" : "New links"}</span>
                            <p className="mt-0.5 text-base font-black text-slate-800">{numberFormatter.format(detail.normalization_summary.authors.publication_author_links_created)}</p>
                          </div>
                          <div className="rounded-[5px] border border-slate-200/80 bg-white p-2.5 shadow-2xs">
                            <span className="text-sm font-medium text-slate-500 uppercase">{locale === "vi" ? "Xung đột" : "Conflicts"}</span>
                            <p className="mt-0.5 text-base font-black text-rose-700">{numberFormatter.format(detail.normalization_summary.authors.conflicts)}</p>
                          </div>
                        </div>
                        {(detail.normalization_summary.authors.errors?.length ?? 0) > 0 && (
                          <div className="mt-3 rounded-[5px] border border-amber-200 bg-amber-50/60 p-3 text-sm">
                            <h4 className="mb-2 font-bold text-amber-800">{t.imports.rowErrors}</h4>
                            <ul className="max-h-36 space-y-1 overflow-y-auto text-amber-900">
                              {detail.normalization_summary.authors.errors!.map((rowError, index) => (
                                <li key={`${rowError.row_number ?? "row"}-${index}`}>
                                  {locale === "vi" ? "Dòng" : "Row"} {rowError.row_number ?? "—"}: {rowError.message ?? rowError.code ?? t.imports.failed}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </section>
                    )}

                    {/* SECTION 2: TÌNH TRẠNG SỬ DỤNG DỮ LIỆU */}
                    <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs">
                      <div className="flex items-center gap-2 mb-3">
                        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                          {locale === "vi" ? "Tình trạng sử dụng dữ liệu" : "Data Usage State"}
                        </h3>
                        {detail.archived && (
                          <span className={`${badgeClassName} ml-auto border-violet-200 bg-violet-50 text-violet-700`}>
                            {locale === "vi" ? "Đã ẩn khỏi lịch sử" : "Hidden from history"}
                          </span>
                        )}
                      </div>
                      <dl className="grid grid-cols-1 gap-2.5 text-sm sm:grid-cols-3">
                        <div className="rounded-[5px] border border-slate-200/80 bg-white p-3 text-center shadow-2xs">
                          <dt className="text-sm font-medium text-slate-500">
                            {locale === "vi" ? "Trạng thái" : "Status"}
                          </dt>
                          <dd className={`mt-0.5 text-base font-black ${
                            "text-slate-800"
                          }`}>
                            {isInUse(detail)
                              ? (locale === "vi" ? "Đang sử dụng" : "In use")
                              : (locale === "vi" ? "Chưa sử dụng" : "Not in use")}
                          </dd>
                        </div>
                        <div className="rounded-[5px] border border-slate-200/80 bg-white p-3 text-center shadow-2xs">
                          <dt className="text-sm font-medium text-slate-500">
                            {locale === "vi" ? "Liên kết nguồn" : "Publication source links"}
                          </dt>
                          <dd className="mt-0.5 text-base font-black text-slate-800">
                            {numberFormatter.format(detail.usage?.publication_source_links ?? 0)}
                          </dd>
                        </div>
                        <div className="rounded-[5px] border border-slate-200/80 bg-white p-3 text-center shadow-2xs">
                          <dt className="text-sm font-medium text-slate-500">
                            {locale === "vi" ? "Biến thể tên tác giả" : "Author name variants"}
                          </dt>
                          <dd className="mt-0.5 text-base font-black text-slate-800">
                            {numberFormatter.format(detail.usage?.author_variant_links ?? 0)}
                          </dd>
                        </div>
                      </dl>
                    </section>

                    {detail.duplicate_candidates > 0 && (
                      <div className="rounded-[5px] border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                        <strong>{t.imports.duplicateRows}:</strong> {numberFormatter.format(detail.duplicate_candidates)}
                      </div>
                    )}

                    {fatalErrorMessage(detail.error_summary) && (
                      <div className="rounded-[5px] border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                        <strong>{t.imports.errorDetail}:</strong> {fatalErrorMessage(detail.error_summary)}
                      </div>
                    )}

                    {detail.row_errors.length > 0 && (
                      <div className="rounded-[5px] border border-amber-200 bg-amber-50/60 p-3 text-sm">
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

              <footer className="flex shrink-0 items-center justify-between gap-2 border-t border-slate-100 bg-white px-5 py-3">
                {/* Left: ID / type / status badges */}
                <div className="flex shrink-0 items-center gap-2">
                  {detail && (
                    <>
                      <span
                        className="inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border border-slate-300 bg-white px-2.5 text-center font-mono text-sm font-bold leading-none text-slate-700"
                        title={detail.id === LECTURER_PREVIEW_ID ? (lecturerPreview?.displayId ?? detail.id) : detail.id}
                      >
                        ID: {shortId(detail.id === LECTURER_PREVIEW_ID ? (lecturerPreview?.displayId ?? detail.id) : detail.id)}
                      </span>
                      {renderTypeBadge(detail.type)}
                      {renderStatusBadge(detail)}
                    </>
                  )}
                </div>

                {/* Right: all actions (destructive first, then confirm/close) */}
                <div className="flex items-center gap-2">
                  {detail && !detail.archived && !ACTIVE_STATUSES.includes(detail.status) && detail.id !== LECTURER_PREVIEW_ID && (detail.status !== "STAGED" || confirmedImportIds.includes(detail.id)) && (
                    <button
                      type="button"
                      disabled={detailLoading}
                      onClick={() => handleDeleteIntent(detail)}
                      className={`${buttonClass("danger")} font-bold`}
                    >
                      {locale === "vi" ? "Xóa đợt nhập" : "Delete import"}
                    </button>
                  )}
                  {detail && detail.archived && (
                    <button
                      type="button"
                      disabled={detailLoading || isRestoring}
                      onClick={() => handleOpenRestoreModal(detail)}
                      className={`${buttonClass("secondary")} font-bold`}
                    >
                      {isRestoring ? (locale === "vi" ? "Đang khôi phục..." : "Restoring...") : (locale === "vi" ? "Khôi phục hiển thị" : "Restore visibility")}
                    </button>
                  )}
                  {detail && ACTIVE_STATUSES.includes(detail.status) && (
                    <button
                      type="button"
                      disabled={detailLoading}
                      onClick={() => handleOpenCancelModal(detail)}
                      className={"inline-flex h-control min-w-action items-center justify-center gap-1.5 rounded-control border border-amber-300 bg-amber-50 px-4 text-sm font-bold text-amber-800 hover:bg-amber-100 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-300 disabled:cursor-not-allowed disabled:opacity-50"}
                    >
                      <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 6l12 12M18 6L6 18" />
                      </svg>
                      <span>{t.imports.cancelImport}</span>
                    </button>
                  )}
                  {detail?.id === LECTURER_PREVIEW_ID ? (
                    <>
                      <button
                        type="button"
                        disabled={
                          detailLoading ||
                          lecturerImporting ||
                          lecturerCancelling ||
                          !lecturerPreview ||
                          lecturerPreview.preview.summary.valid === 0
                        }
                        onClick={() => void handleConfirmLecturerImport()}
                        className={`${buttonClass("primary")} font-bold`}
                      >
                        {lecturerImporting && (
                          <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                        )}
                        <span>{t.lecturerImport.confirmImport}</span>
                      </button>
                      {detail?.duplicate_of && (
                        <button
                          type="button"
                          disabled={detailLoading || lecturerImporting || lecturerCancelling}
                          onClick={() => void viewPreviousImport(detail.duplicate_of?.import_id)}
                          className={`${buttonClass("secondary")} font-bold`}
                        >
                          {locale === "vi" ? "Xem đợt trước" : "View earlier import"}
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={detailLoading || lecturerImporting || lecturerCancelling}
                        onClick={() => void cancelLecturerPreview()}
                        className={`${buttonClass("secondary")} font-bold`}
                      >
                        {lecturerCancelling ? (
                          <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
                        ) : null}
                        <span>{locale === "vi" ? "Hủy tiến trình" : "Cancel process"}</span>
                      </button>
                      <button
                        type="button"
                        disabled={detailLoading || lecturerImporting || lecturerCancelling}
                        onClick={() => setDetailOpen(false)}
                        className={`${buttonClass("secondary")} font-bold`}
                      >
                        {t.imports.close}
                      </button>
                    </>
                  ) : detail && detail.type !== "LECTURERS" && detail.status === "STAGED" && !confirmedImportIds.includes(detail.id) ? (
                    <>
                      <button
                        type="button"
                        disabled={detailLoading || isCancelling || confirmingImportId === detail.id}
                        onClick={() => void handleConfirmImport(detail)}
                        className={`${buttonClass("primary")} font-bold`}
                      >
                        <span>{locale === "vi" ? "Xác nhận nhập" : "Confirm import"}</span>
                      </button>
                      {detail.duplicate_of && (
                        <button
                          type="button"
                          disabled={detailLoading || isCancelling || confirmingImportId === detail.id}
                          onClick={() => void viewPreviousImport(detail.duplicate_of?.import_id)}
                          className={`${buttonClass("secondary")} font-bold`}
                        >
                          {locale === "vi" ? "Xem đợt trước" : "View earlier import"}
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={detailLoading || isCancelling || confirmingImportId === detail.id}
                        onClick={() => void handleCancelProcess(detail)}
                        className={`${buttonClass("secondary")} font-bold`}
                      >
                        <span>{locale === "vi" ? "Hủy tiến trình" : "Cancel process"}</span>
                      </button>
                      <button
                        type="button"
                        disabled={detailLoading || isCancelling || confirmingImportId === detail.id}
                        onClick={() => setDetailOpen(false)}
                        className={`${buttonClass("secondary")} font-bold`}
                      >
                        {t.imports.close}
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      disabled={detailLoading}
                      onClick={() => setDetailOpen(false)}
                      className={`${buttonClass("secondary")} font-bold`}
                    >
                      {t.imports.close}
                    </button>
                  )}
                </div>
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
                    <span className="my-2.5 block rounded-[5px] border border-amber-200/80 bg-amber-50/50 p-2.5 text-sm text-slate-700">
                      <span className="block">
                        {locale === "vi" ? "Liên kết nguồn:" : "Publication source links:"}{" "}
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

    </div>
    </>
  );
}
