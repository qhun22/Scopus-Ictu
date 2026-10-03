import React, { useEffect, useState } from "react";
import {
  LecturerForm,
  LecturerMasterItem,
  LecturerStats,
  LecturerUpdatePayload,
  createLecturer,
  deleteLecturer,
  exportLecturersJson,
  getLecturers,
  updateLecturer,
} from "../../api/lecturers";
import { ApiError } from "../../api/client";
import {
  getUser,
  lockUser,
  resetUserPassword,
  unlockUser,
} from "../../api/users";
import ConfirmModal from "../../components/common/ConfirmModal";
import ModalPortal from "../../components/common/ModalPortal";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import { useI18n } from "../../i18n";

const FILTER_DELAY_MS = 350;

export default function LecturersPage() {
  const toast = useToast();
  const { user: currentUser } = useAuth();
  const { t, getRoleLabel, locale } = useI18n();

  const getAccountRoleLabel = (role: string): string =>
    role.toUpperCase() === "LECTURER"
      ? (locale === "vi" ? "Cán bộ" : "Staff")
      : getRoleLabel(role);

  const [lecturers, setLecturers] = useState<LecturerMasterItem[]>([]);
  const [totalRecords, setTotalRecords] = useState<number>(0);
  const [stats, setStats] = useState<LecturerStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>("");
  const [appliedSearch, setAppliedSearch] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [isExporting, setIsExporting] = useState<boolean>(false);

  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const isFiltering = search !== appliedSearch;
  const isTableLoading = loading || isFiltering;

  // Modal states
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [selectedLecturer, setSelectedLecturer] = useState<LecturerMasterItem | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [detailAction, setDetailAction] = useState<
    "save" | "lock" | "unlock" | "reset" | null
  >(null);
  const [confirmAction, setConfirmAction] = useState<"lock" | "unlock" | "reset" | null>(null);

  // Form states for Add
  const [addForm, setAddForm] = useState<LecturerForm>({
    full_name: "",
    email: "",
    password: "",
    staff_code: "",
    role: "LECTURER",
    academic_degree: "Thạc sĩ",
    department: "Khoa CNTT",
  });
  const [addError, setAddError] = useState<string>("");

  // Form states for Edit / Detail
  const [editForm, setEditForm] = useState<{
    full_name: string;
    email: string;
    staff_code: string;
    academic_degree: string;
    academic_rank: string;
    faculty: string;
    department: string;
  }>({
    full_name: "",
    email: "",
    staff_code: "",
    academic_degree: "Thạc sĩ",
    academic_rank: "",
    faculty: "",
    department: "",
  });
  const [editError, setEditError] = useState<string>("");
  const [newPassword, setNewPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  // Grant Account states (for unlinked profile in Detail modal)
  const [grantAccount, setGrantAccount] = useState(false);
  const [grantEmail, setGrantEmail] = useState("");
  const [grantPassword, setGrantPassword] = useState("");
  const [grantRole, setGrantRole] = useState("LECTURER");

  const isDetailBusy = detailAction !== null;
  const isCurrentAccount =
    selectedLecturer?.account?.user_id === currentUser?.id;

  const fetchData = async () => {
    setLoading(true);
    try {
      const data = await getLecturers({
        page,
        page_size: pageSize,
        search: appliedSearch.trim() || undefined,
      });
      setLecturers(data.items);
      setTotalRecords(data.total);
      setStats(data.stats);
      setSelectedLecturer((current) => {
        if (!current) return current;
        return data.items.find((item) => item.id === current.id) ?? current;
      });
    } catch {
      toast.error(
        locale === "vi" ? "Lỗi kết nối" : "Connection Error",
        locale === "vi"
          ? "Không thể tải danh sách giảng viên."
          : "Unable to load lecturers list.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, pageSize, appliedSearch]);

  useEffect(() => {
    if (!isDetailModalOpen) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isDetailBusy && confirmAction === null) {
        setIsDetailModalOpen(false);
      }
    };

    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [confirmAction, isDetailBusy, isDetailModalOpen]);

  useEffect(() => {
    if (search === appliedSearch) return;

    const timer = window.setTimeout(() => {
      setAppliedSearch(search);
      setPage(1);
    }, FILTER_DELAY_MS);

    return () => window.clearTimeout(timer);
  }, [search, appliedSearch]);

  const getErrorCode = (error: unknown): string | undefined => {
    if (!(error instanceof ApiError) || typeof error.body !== "object" || error.body === null) {
      return undefined;
    }
    const code = (error.body as Record<string, unknown>).code;
    return typeof code === "string" ? code : undefined;
  };

  const handleVersionConflict = async () => {
    toast.warning(
      "Dữ liệu đã thay đổi",
      "Thông tin giảng viên vừa được cập nhật ở nơi khác. Vui lòng tải lại.",
    );
    setConfirmAction(null);
    setIsDetailModalOpen(false);
    await fetchData();
  };

  // Open Add Modal
  const handleOpenAddModal = () => {
    setAddForm({
      full_name: "",
      email: "",
      password: "",
      staff_code: "",
      role: "LECTURER",
      academic_degree: "Thạc sĩ",
      department: "Khoa CNTT",
    });
    setAddError("");
    setIsAddModalOpen(true);
  };

  // Submit Add Lecturer
  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addForm.full_name.trim() || !addForm.email.trim() || !addForm.password?.trim() || !addForm.staff_code.trim()) {
      setAddError(locale === "vi" ? "Vui lòng nhập đầy đủ các thông tin bắt buộc." : "Please fill in all required fields.");
      return;
    }
    if (addForm.password.length < 8) {
      setAddError(locale === "vi" ? "Mật khẩu phải có ít nhất 8 ký tự." : "Password must be at least 8 characters.");
      return;
    }

    setIsSubmitting(true);
    setAddError("");
    try {
      await createLecturer({
        full_name: addForm.full_name.trim(),
        email: addForm.email.trim(),
        password: addForm.password,
        staff_code: addForm.staff_code.trim(),
        role: addForm.role,
        academic_degree: addForm.academic_degree,
        department: addForm.department,
      });
      toast.success(
        locale === "vi" ? "Thêm thành công" : "Success",
        locale === "vi" ? `Đã thêm giảng viên ${addForm.full_name}` : `Lecturer ${addForm.full_name} has been added.`,
      );
      setIsAddModalOpen(false);
      fetchData();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || (locale === "vi" ? "Không thể thêm giảng viên. Vui lòng thử lại." : "Could not add lecturer.");
      setAddError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Open Detail Modal
  const handleOpenDetailModal = (lec: LecturerMasterItem) => {
    setSelectedLecturer(lec);
    setEditForm({
      full_name: lec.full_name,
      email: lec.institutional_email || "",
      staff_code: lec.staff_code || "",
      academic_degree: lec.academic_degree || "Thạc sĩ",
      academic_rank: lec.academic_rank || "",
      faculty: lec.faculty || "",
      department: lec.department || "",
    });
    setGrantAccount(false);
    setGrantEmail(lec.institutional_email || "");
    setGrantPassword("");
    setGrantRole(lec.account?.role || "LECTURER");
    setEditError("");
    setNewPassword("");
    setPasswordError("");
    setShowNewPassword(false);
    setConfirmAction(null);
    setIsDetailModalOpen(true);
  };

  // Submit Edit Lecturer (handles both linked user & unlinked master profiles)
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLecturer || isDetailBusy) return;
    if (!editForm.full_name.trim()) {
      setEditError(
        locale === "vi"
          ? "Vui lòng nhập họ và tên."
          : "Please enter full name.",
      );
      return;
    }

    if (grantAccount && (!grantPassword || grantPassword.length < 8)) {
      setEditError(
        locale === "vi"
          ? "Mật khẩu cấp mới phải có ít nhất 8 ký tự."
          : "Password must be at least 8 characters.",
      );
      return;
    }

    setDetailAction("save");
    setEditError("");
    try {
      const payload: LecturerUpdatePayload = {
        version: selectedLecturer.account?.version ?? selectedLecturer.version,
        full_name: editForm.full_name.trim(),
        email: (grantAccount ? grantEmail.trim() : editForm.email.trim()) || undefined,
        staff_code: editForm.staff_code.trim() || undefined,
        academic_degree: editForm.academic_degree.trim() || undefined,
        academic_rank: editForm.academic_rank.trim() || undefined,
        faculty: editForm.faculty.trim() || undefined,
        department: editForm.department.trim() || undefined,
        grant_account: grantAccount,
        password: grantAccount ? grantPassword : undefined,
        role: selectedLecturer.account || grantAccount ? grantRole : undefined,
      };
      const updated = await updateLecturer(selectedLecturer.id, payload);
      if (updated.has_warning) {
        toast.warning(
          locale === "vi" ? "Đã lưu, nhưng hồ sơ vẫn còn cảnh báo" : "Saved with a warning",
          updated.warning_reason || (locale === "vi"
            ? "Email đang được sử dụng cho nhiều hồ sơ giảng viên. Vui lòng kiểm tra và cập nhật thông tin nhận diện."
            : "This email is used by multiple lecturer profiles. Review and update the identifying information."),
        );
      } else {
        toast.success(
          locale === "vi" ? "Cập nhật thành công" : "Success",
          locale === "vi" ? `Đã cập nhật thông tin giảng viên ${editForm.full_name}` : `Lecturer ${editForm.full_name} updated successfully.`,
        );
      }
      setIsDetailModalOpen(false);
      await fetchData();
    } catch (error: unknown) {
      if (getErrorCode(error) === "VERSION_CONFLICT") {
        await handleVersionConflict();
      } else {
        toast.error(
          "Không thể lưu thay đổi",
          error instanceof ApiError
            ? error.message
            : "Không thể cập nhật thông tin giảng viên. Vui lòng thử lại.",
        );
      }
    } finally {
      setDetailAction(null);
    }
  };

  const requestPasswordReset = () => {
    const password = newPassword.trim();
    if (!password) {
      setPasswordError("Vui lòng nhập mật khẩu mới.");
      return;
    }
    if (password.length < 8) {
      setPasswordError("Mật khẩu mới phải có ít nhất 8 ký tự.");
      return;
    }
    if (isCurrentAccount) {
      toast.warning(
        "Không thể đặt lại mật khẩu",
        "Không thể đặt lại mật khẩu quản trị viên đang sử dụng từ màn hình quản trị người dùng.",
      );
      return;
    }
    setPasswordError("");
    setConfirmAction("reset");
  };

  const handleSecurityAction = async () => {
    if (!selectedLecturer || !selectedLecturer.account || !confirmAction || isDetailBusy) return;

    const action = confirmAction;
    const userId = selectedLecturer.account.user_id;
    setDetailAction(action);
    try {
      // The detail modal can stay open while the list or another admin updates
      // the account. Read the current User aggregate version immediately before
      // a versioned security mutation instead of submitting a stale list value.
      const currentAccount = await getUser(userId);
      if (action === "reset") {
        const result = await resetUserPassword(userId, {
          new_password: newPassword,
          version: currentAccount.version,
        });
        setSelectedLecturer((prev) =>
          prev && prev.account
            ? {
                ...prev,
                account: {
                  ...prev.account,
                  version: result.version,
                },
              }
            : prev,
        );
        setNewPassword("");
        toast.success(
          "Đã đặt lại mật khẩu",
          "Mật khẩu mới đã được cập nhật cho tài khoản.",
        );
      } else {
        const updated =
          action === "lock"
            ? await lockUser(userId, currentAccount.version)
            : await unlockUser(userId, currentAccount.version);
        setSelectedLecturer((prev) =>
          prev && prev.account
            ? {
                ...prev,
                account: {
                  ...prev.account,
                  is_active: updated.is_active,
                  version: updated.version,
                },
              }
            : prev,
        );
        if (action === "lock") {
          toast.success(
            "Đã khóa tài khoản",
            "Tài khoản không thể đăng nhập cho đến khi được mở khóa.",
          );
        } else {
          toast.success("Đã mở khóa tài khoản", "Người dùng có thể đăng nhập lại.");
        }
      }
      setConfirmAction(null);
      await fetchData();
    } catch (error: unknown) {
      if (getErrorCode(error) === "VERSION_CONFLICT") {
        await handleVersionConflict();
      } else if (getErrorCode(error) === "CANNOT_LOCK_CURRENT_USER") {
        toast.warning(
          "Không thể khóa tài khoản",
          "Không thể khóa tài khoản đang sử dụng.",
        );
        setConfirmAction(null);
      } else if (getErrorCode(error) === "CANNOT_RESET_CURRENT_USER") {
        toast.warning(
          "Không thể đặt lại mật khẩu",
          "Không thể đặt lại mật khẩu quản trị viên đang sử dụng từ màn hình này.",
        );
        setConfirmAction(null);
      } else {
        toast.error(
          "Không thể thực hiện thao tác",
          error instanceof ApiError ? error.message : "Vui lòng thử lại sau.",
        );
      }
    } finally {
      setDetailAction(null);
    }
  };

  // Open Delete Modal
  const handleOpenDeleteModal = (lec: LecturerMasterItem) => {
    setSelectedLecturer(lec);
    setIsDeleteModalOpen(true);
  };

  // Confirm Delete
  const handleDeleteConfirm = async () => {
    if (!selectedLecturer) return;
    setIsSubmitting(true);
    try {
      await deleteLecturer(selectedLecturer.id);
      toast.success(
        locale === "vi" ? "Xóa thành công" : "Success",
        locale === "vi" ? `Đã xóa giảng viên ${selectedLecturer.full_name}` : `Lecturer ${selectedLecturer.full_name} has been deleted.`,
      );
      setIsDeleteModalOpen(false);
      setSelectedLecturer(null);
      fetchData();
    } catch (err: any) {
      if (err instanceof ApiError && (err.code === "LECTURER_IN_USE" || err.status === 409)) {
        toast.error(
          locale === "vi" ? "Không thể xóa giảng viên" : "Cannot delete lecturer",
          locale === "vi"
            ? "Hồ sơ này đang được liên kết với dữ liệu khác trong hệ thống."
            : (err.message || "This record is currently in use in the system."),
        );
      } else {
        const msg = err instanceof ApiError ? err.message : (err?.response?.data?.detail || (locale === "vi" ? "Không thể xóa giảng viên." : "Could not delete lecturer."));
        toast.error(locale === "vi" ? "Không thể xóa giảng viên" : "Delete Error", typeof msg === "string" ? msg : JSON.stringify(msg));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Export JSON Handler
  const handleExportJson = async () => {
    setIsExporting(true);
    try {
      const { blob, filename, recordCount } = await exportLecturersJson();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(
        locale === "vi" ? "Xuất dữ liệu thành công" : "Export successful",
        locale === "vi"
          ? `Đã xuất ${recordCount} hồ sơ giảng viên.`
          : `Exported ${recordCount} lecturer records.`,
      );
    } catch (err: any) {
      toast.error(
        locale === "vi" ? "Lỗi xuất dữ liệu" : "Export error",
        err instanceof Error ? err.message : "Không thể xuất tệp JSON.",
      );
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* Page Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">
            {t.lecturers.title}
          </h1>
          <p className="text-xs text-slate-500 sm:text-sm">
            {t.lecturers.subtitle}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Export JSON Button */}
          <button
            type="button"
            disabled={isExporting}
            onClick={handleExportJson}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-xs hover:bg-slate-50 hover:text-[#3A5FC3] hover:border-[#3A5FC3] transition-colors cursor-pointer disabled:opacity-50"
          >
            {isExporting ? (
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-[#3A5FC3]" />
            ) : (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            )}
            <span>{isExporting ? (locale === "vi" ? "Đang xuất..." : "Exporting...") : (locale === "vi" ? "Xuất JSON" : "Export JSON")}</span>
          </button>

          {/* Add Lecturer Button */}
          <button
            type="button"
            onClick={handleOpenAddModal}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#3A5FC3] px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] transition-colors cursor-pointer"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M12 4v16m8-8H4" />
            </svg>
            <span>{locale === "vi" ? "Thêm giảng viên" : "Add Lecturer"}</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Grid - Lecturer-Centric 5 Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4">
        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">
            {locale === "vi" ? "Tổng giảng viên" : "Total Lecturers"}
          </span>
          <p className="mt-1 text-2xl font-black text-slate-800">
            {stats ? stats.total_lecturers : totalRecords}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-emerald-600">
            {locale === "vi" ? "Đã cấp tài khoản" : "Account Linked"}
          </span>
          <p className="mt-1 text-2xl font-black text-emerald-600">
            {stats ? stats.account_linked : 0}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">
            {locale === "vi" ? "Chưa cấp tài khoản" : "No Account"}
          </span>
          <p className="mt-1 text-2xl font-black text-slate-700">
            {stats ? stats.account_not_linked : 0}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-rose-600">
            {locale === "vi" ? "Tài khoản bị khóa" : "Account Locked"}
          </span>
          <p className="mt-1 text-2xl font-black text-rose-600">
            {stats ? stats.account_locked : 0}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs col-span-2 sm:col-span-1">
          <span className="text-xs font-medium text-amber-600">
            {locale === "vi" ? "Cảnh báo" : "Warnings"}
          </span>
          <p className="mt-1 text-2xl font-black text-amber-600">
            {stats ? stats.warning_count : "—"}
          </p>
        </div>
      </div>

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
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t.lecturers.searchPlaceholder}
            className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 sm:text-sm"
          />
        </div>

        {/* Reset Button */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setSearch("");
              setAppliedSearch("");
              setPage(1);
            }}
            disabled={!search && !appliedSearch}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-[#3A5FC3] hover:border-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 transition-colors cursor-pointer shadow-2xs"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>{locale === "vi" ? "Đặt lại" : "Reset"}</span>
          </button>
        </div>
      </div>

      {/* Lecturers Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-xs">
        <div className="relative overflow-x-auto">
          <table aria-busy={isTableLoading} className="w-full text-left text-xs">
            <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
              <tr>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{locale === "vi" ? "Giảng viên" : "Lecturer"}</th>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{t.lecturers.colEmail}</th>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{locale === "vi" ? "Học vị / Học hàm" : "Degree / Rank"}</th>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">{locale === "vi" ? "Khoa / Bộ môn" : "Faculty / Dept"}</th>
                <th className="px-4 py-3 text-center font-semibold whitespace-nowrap">{locale === "vi" ? "Tài khoản" : "Account"}</th>
                <th className="px-4 py-3 text-center font-semibold whitespace-nowrap">{locale === "vi" ? "Trạng thái" : "Status"}</th>
                <th className="px-4 py-3 text-center font-semibold whitespace-nowrap">{t.common.actions}</th>
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
              ) : lecturers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-1">
                      <svg className="h-8 w-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <span className="font-semibold text-slate-600">{t.lecturers.noData}</span>
                      <span className="text-[11px] text-slate-400">{t.lecturers.noDataSub}</span>
                    </div>
                  </td>
                </tr>
              ) : (
                lecturers.map((lec) => {
                  const degreeRank = [lec.academic_rank, lec.academic_degree].filter(Boolean).join(" / ") || "—";
                  const facultyDept = [lec.faculty, lec.department].filter(Boolean).join(" / ") || "—";
                  return (
                    <tr key={lec.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#3A5FC3] text-xs font-bold text-white shadow-xs">
                            {lec.full_name.charAt(0).toUpperCase()}
                          </div>
                          <div className="min-w-0 max-w-xs">
                            <span className="font-bold text-slate-800 block truncate" title={lec.full_name}>
                              {lec.full_name}
                            </span>
                            <span className="block text-[10px] text-slate-400 truncate">
                              {lec.staff_code || lec.position || "—"}
                            </span>
                          </div>
                        </div>
                      </td>

                      <td className="px-4 py-3 font-medium text-slate-700">
                        {lec.institutional_email || "—"}
                      </td>

                      <td className="px-4 py-3 font-medium text-slate-700">
                        {degreeRank}
                      </td>

                      <td className="px-4 py-3 font-medium text-slate-700">
                        {facultyDept}
                      </td>

                      <td className="px-4 py-3 text-center">
                        {lec.account ? (
                          <span
                            title={getAccountRoleLabel(lec.account.role)}
                            className="inline-flex w-28 items-center justify-center whitespace-nowrap rounded-full border border-violet-200 bg-violet-50 px-2.5 py-0.5 text-xs font-bold text-violet-700"
                          >
                            {getAccountRoleLabel(lec.account.role)}
                          </span>
                        ) : (
                          <span className="inline-flex w-28 items-center justify-center whitespace-nowrap rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-medium text-slate-400">
                            {locale === "vi" ? "Chưa cấp" : "Not Linked"}
                          </span>
                        )}
                      </td>

                      {/* Status Column: account lock takes precedence over data warnings. */}
                      <td className="px-4 py-3 text-center">
                        {lec.account && !lec.account.is_active ? (
                          <span
                            title={locale === "vi" ? "Tài khoản đang bị khóa" : "Account locked"}
                            className="inline-flex w-20 items-center justify-center whitespace-nowrap rounded-full border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-xs font-bold text-rose-700"
                          >
                            <span>{locale === "vi" ? "Đã khóa" : "Locked"}</span>
                          </span>
                        ) : lec.has_warning ? (
                          <span
                            title={lec.warning_reason || (locale === "vi" ? "Cần rà soát trùng tên" : "Review duplicate")}
                            className="inline-flex w-20 items-center justify-center whitespace-nowrap rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-xs font-bold text-amber-700"
                          >
                            <span>{locale === "vi" ? "Cảnh báo" : "Warning"}</span>
                          </span>
                        ) : (
                          <span className="inline-flex w-20 items-center justify-center whitespace-nowrap rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
                            <span>{locale === "vi" ? "Hoạt động" : "Active"}</span>
                          </span>
                        )}
                      </td>

                      {/* Actions Column: [Chi tiết] [Xóa] */}
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-1.5 whitespace-nowrap">
                          <button
                            type="button"
                            onClick={() => handleOpenDetailModal(lec)}
                            className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:border-[#3A5FC3] hover:text-[#3A5FC3] transition-colors cursor-pointer shadow-2xs"
                          >
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                            <span>{locale === "vi" ? "Chi tiết" : "Detail"}</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleOpenDeleteModal(lec)}
                            className="inline-flex items-center gap-1 rounded-md border border-rose-200 bg-rose-50/50 px-2.5 py-1 text-[11px] font-semibold text-rose-600 hover:bg-rose-100/70 transition-colors cursor-pointer shadow-2xs"
                          >
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            <span>{locale === "vi" ? "Xóa" : "Delete"}</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          {isFiltering && !loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/80 backdrop-blur-[1px]">
              <div role="status" className="flex items-center gap-2 rounded-lg border border-slate-100 bg-white px-4 py-2.5 text-xs font-medium text-slate-600 shadow-sm">
                <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3] motion-reduce:animate-none" />
                {t.common.loading}
              </div>
            </div>
          )}
        </div>

        {/* Footer info & Server-Side Pagination Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-2.5 text-[11px] text-slate-500">
          <div className="flex items-center gap-3">
            <span>
              {t.lecturers.showing} <strong>{lecturers.length}</strong> {t.lecturers.of} {totalRecords} {locale === "vi" ? "giảng viên" : "lecturers"}
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

          <nav aria-label={t.lecturers.paginationLabel} className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage(page - 1)}
              disabled={isTableLoading || page <= 1}
              className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
            >
              {t.lecturers.previousPage}
            </button>
            <span aria-live="polite" className="min-w-[72px] text-center font-medium text-slate-600">
              {t.lecturers.page} <strong>{page}</strong> / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage(page + 1)}
              disabled={isTableLoading || page >= totalPages}
              className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
            >
              {t.lecturers.nextPage}
            </button>
          </nav>
        </div>
      </div>

      {/* ====================================================================== */}
      {/* MODAL 1: THÊM GIẢNG VIÊN */}
      {/* ====================================================================== */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-3 sm:p-4 overflow-y-auto">
          <div className="relative w-full max-w-lg max-h-[calc(100vh-2rem)] overflow-y-auto rounded-2xl bg-white p-5 sm:p-6 shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900 sm:text-lg">
                {locale === "vi" ? "Thêm mới Giảng viên" : "Add New Lecturer"}
              </h3>
              <button
                type="button"
                onClick={() => setIsAddModalOpen(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleAddSubmit} className="mt-4 space-y-3.5 text-xs">
              {addError && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 p-2.5 text-rose-700 font-medium">
                  {addError}
                </div>
              )}

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    {locale === "vi" ? "Họ và tên" : "Full Name"} <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={addForm.full_name}
                    onChange={(e) => setAddForm({ ...addForm, full_name: e.target.value })}
                    placeholder="VD: Nguyễn Văn A"
                    className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    {locale === "vi" ? "Email giảng viên" : "Email"} <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="email"
                    required
                    value={addForm.email}
                    onChange={(e) => setAddForm({ ...addForm, email: e.target.value })}
                    placeholder="example@ictu.edu.vn"
                    className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    {locale === "vi" ? "Mật khẩu tài khoản" : "Password"} <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={addForm.password}
                    onChange={(e) => setAddForm({ ...addForm, password: e.target.value })}
                    placeholder="••••••••"
                    className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    {locale === "vi" ? "Mã cán bộ" : "Staff Code"} <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={addForm.staff_code}
                    onChange={(e) => setAddForm({ ...addForm, staff_code: e.target.value })}
                    placeholder="VD: CB00123"
                    className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    {locale === "vi" ? "Vai trò" : "Role"}
                  </label>
                  <select
                    value={addForm.role}
                    onChange={(e) => setAddForm({ ...addForm, role: e.target.value })}
                    className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
                  >
                    <option value="LECTURER">Giảng viên</option>
                    <option value="ADMIN">Quản trị viên</option>
                    <option value="REVIEWER">Phê duyệt viên</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    {locale === "vi" ? "Học vị / Học hàm" : "Degree"}
                  </label>
                  <select
                    value={addForm.academic_degree}
                    onChange={(e) => setAddForm({ ...addForm, academic_degree: e.target.value })}
                    className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
                  >
                    <option value="Cử nhân">Cử nhân / Kỹ sư</option>
                    <option value="Thạc sĩ">Thạc sĩ</option>
                    <option value="Tiến sĩ">Tiến sĩ</option>
                    <option value="TS. GVC">TS. GVC</option>
                    <option value="PGS.TS">PGS.TS</option>
                    <option value="GS.TS">GS.TS</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    {locale === "vi" ? "Khoa / Bộ môn" : "Department"}
                  </label>
                  <input
                    type="text"
                    value={addForm.department}
                    onChange={(e) => setAddForm({ ...addForm, department: e.target.value })}
                    placeholder="VD: Khoa CNTT"
                    className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-slate-100 pt-4">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
                >
                  {t.common.cancel}
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#3A5FC3] px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] disabled:opacity-50 cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      <span>{locale === "vi" ? "Đang lưu..." : "Saving..."}</span>
                    </>
                  ) : (
                    <span>{locale === "vi" ? "Tạo giảng viên" : "Create Lecturer"}</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ====================================================================== */}
      {/* MODAL 2: CHI TIẾT & HIỆU CHỈNH GIẢNG VIÊN */}
      {/* ====================================================================== */}
      {isDetailModalOpen && selectedLecturer && (
        <ModalPortal>
          <div className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-slate-900/50 p-3 backdrop-blur-xs sm:p-4">
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="lecturer-detail-title"
              className="flex max-h-[calc(100vh-1.5rem)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl animate-in zoom-in-95 duration-150 sm:max-h-[calc(100vh-2rem)]"
            >
              <div className="shrink-0 border-b border-slate-100 px-4 py-4 sm:px-6">
                <h3 id="lecturer-detail-title" className="text-base font-bold text-slate-900 sm:text-lg">
                  {locale === "vi" ? "Chi tiết Hồ sơ Giảng viên" : "Lecturer Profile Details"}
                </h3>
                <p className="mt-0.5 break-all text-[11px] font-mono text-slate-400">
                  ID: {selectedLecturer.id}
                </p>
              </div>

              <form onSubmit={handleEditSubmit} className="flex min-h-0 flex-1 flex-col text-xs">
                <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4 sm:px-6">
                  {/* Warning Notice Banner */}
                  {selectedLecturer.has_warning && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-900 flex items-start gap-2.5">
                      <svg className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <div>
                        <strong className="font-bold">{locale === "vi" ? "Hồ sơ cần được rà soát" : "Profile needs review"}:</strong>{" "}
                        <span>{selectedLecturer.warning_reason || (locale === "vi" ? "Tên giảng viên bị trùng và chưa có đủ thông tin để xác định hồ sơ." : "The lecturer name is duplicated and the profile lacks enough identifying information.")}</span>
                        <p className="mt-1 text-[11px] text-amber-700">
                          {locale === "vi"
                            ? "Vui lòng kiểm tra và cập nhật email hoặc thông tin nhận diện. Cảnh báo sẽ tự động được gỡ bỏ khi dữ liệu không còn trùng."
                            : "Review and update the email or identifying information. The warning will clear automatically once the data is no longer duplicated."}
                        </p>
                      </div>
                    </div>
                  )}

                  <section aria-labelledby="lecturer-information-heading">
                    <h4
                      id="lecturer-information-heading"
                      className="mb-3 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500"
                    >
                      {locale === "vi" ? "Thông tin hồ sơ giảng viên" : "Lecturer Profile"}
                    </h4>

                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div>
                        <label htmlFor="edit-full-name" className="mb-1 block font-semibold text-slate-700">
                          {locale === "vi" ? "Họ và tên" : "Full Name"} <span className="text-rose-500">*</span>
                        </label>
                        <input
                          id="edit-full-name"
                          type="text"
                          required
                          disabled={isDetailBusy}
                          value={editForm.full_name}
                          onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                          className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 disabled:bg-slate-50"
                        />
                      </div>

                      <div>
                        <label htmlFor="edit-email" className="mb-1 block font-semibold text-slate-700">
                          {locale === "vi" ? "Email đơn vị" : "Institutional Email"}
                        </label>
                        <input
                          id="edit-email"
                          type="email"
                          disabled={isDetailBusy}
                          value={editForm.email}
                          onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                          placeholder={selectedLecturer.institutional_email || "example@ictu.edu.vn"}
                          className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 disabled:bg-slate-50"
                        />
                      </div>

                      <div>
                        <label htmlFor="edit-staff-code" className="mb-1 block font-semibold text-slate-700">
                          {locale === "vi" ? "Mã cán bộ" : "Staff Code"}
                        </label>
                        <input
                          id="edit-staff-code"
                          type="text"
                          disabled={isDetailBusy}
                          value={editForm.staff_code}
                          onChange={(e) => setEditForm({ ...editForm, staff_code: e.target.value })}
                          placeholder="VD: CB00123"
                          className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 disabled:bg-slate-50"
                        />
                      </div>

                      <div>
                        <label htmlFor="edit-degree" className="mb-1 block font-semibold text-slate-700">
                          {locale === "vi" ? "Học vị / Học hàm" : "Degree / Rank"}
                        </label>
                        <input
                          id="edit-degree"
                          type="text"
                          disabled={isDetailBusy}
                          value={editForm.academic_degree}
                          onChange={(e) => setEditForm({ ...editForm, academic_degree: e.target.value })}
                          placeholder="VD: Thạc sĩ, Tiến sĩ, PGS.TS, TS. GVC, Cử nhân"
                          className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 disabled:bg-slate-50"
                        />
                      </div>

                      <div>
                        <label htmlFor="edit-faculty" className="mb-1 block font-semibold text-slate-700">
                          {locale === "vi" ? "Khoa" : "Faculty"}
                        </label>
                        <input
                          id="edit-faculty"
                          type="text"
                          disabled={isDetailBusy}
                          value={editForm.faculty}
                          onChange={(e) => setEditForm({ ...editForm, faculty: e.target.value })}
                          placeholder="VD: Khoa Công nghệ Thông tin"
                          className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 disabled:bg-slate-50"
                        />
                      </div>

                      <div>
                        <label htmlFor="edit-department" className="mb-1 block font-semibold text-slate-700">
                          {locale === "vi" ? "Bộ môn / Phòng ban" : "Department"}
                        </label>
                        <input
                          id="edit-department"
                          type="text"
                          disabled={isDetailBusy}
                          value={editForm.department}
                          onChange={(e) => setEditForm({ ...editForm, department: e.target.value })}
                          placeholder="VD: Bộ môn Kỹ thuật phần mềm"
                          className="h-9 w-full rounded-lg border border-slate-200 px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 disabled:bg-slate-50"
                        />
                      </div>
                    </div>

                    {selectedLecturer.profile_url && (
                      <div className="mt-3">
                        <span className="font-semibold text-slate-600 block mb-1">
                          {locale === "vi" ? "Trang hồ sơ nguồn:" : "Source Profile URL:"}
                        </span>
                        <a
                          href={selectedLecturer.profile_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[#3A5FC3] hover:underline break-all text-xs inline-flex items-center gap-1"
                        >
                          <span>{selectedLecturer.profile_url}</span>
                          <svg className="h-3 w-3 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      </div>
                    )}

                    {editError && <p className="mt-2 text-[11px] font-medium text-rose-600">{editError}</p>}
                  </section>

                  <section
                    aria-labelledby="system-account-heading"
                    className="border-t border-slate-200 pt-4"
                  >
                    <h4
                      id="system-account-heading"
                      className="mb-3 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500"
                    >
                      {locale === "vi" ? "Tài khoản hệ thống liên kết" : "Linked System Account"}
                    </h4>

                    {selectedLecturer.account ? (
                      <div className="space-y-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div className="rounded-lg bg-slate-50 p-3">
                            <span className="font-semibold text-slate-500 block text-[11px]">Email đăng nhập</span>
                            <span className="font-bold text-slate-800 mt-0.5 block">{selectedLecturer.account.email}</span>
                          </div>
                          <div className="rounded-lg bg-slate-50 p-3">
                            <label htmlFor="edit-account-role" className="font-semibold text-slate-500 block text-[11px]">
                              {locale === "vi" ? "Vai trò" : "Role"}
                            </label>
                            <select
                              id="edit-account-role"
                              value={grantRole}
                              disabled={isDetailBusy}
                              onChange={(event) => setGrantRole(event.target.value)}
                              className="mt-1 h-8 w-full rounded-lg border border-slate-200 bg-white px-2 text-xs font-bold text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 disabled:cursor-not-allowed disabled:bg-slate-100"
                            >
                              <option value="LECTURER">{locale === "vi" ? "Giảng viên (LECTURER)" : "Lecturer (LECTURER)"}</option>
                              <option value="ADMIN">{locale === "vi" ? "Quản trị viên (ADMIN)" : "Administrator (ADMIN)"}</option>
                              <option value="REVIEWER">{locale === "vi" ? "Phê duyệt viên (REVIEWER)" : "Reviewer (REVIEWER)"}</option>
                            </select>
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2.5">
                          <span className="font-semibold text-slate-600">Trạng thái tài khoản</span>
                          <span
                            className={`inline-flex items-center gap-1.5 font-bold ${
                              selectedLecturer.account.is_active ? "text-emerald-700" : "text-rose-700"
                            }`}
                          >
                            <span
                              className={`h-2 w-2 rounded-full ${
                                selectedLecturer.account.is_active ? "bg-emerald-500" : "bg-rose-500"
                              }`}
                            />
                            {selectedLecturer.account.is_active ? "Đang hoạt động" : "Đã khóa"}
                          </span>
                        </div>

                        <div>
                          <label htmlFor="new-password" className="mb-1 block font-semibold text-slate-700">
                            Mật khẩu mới
                          </label>
                          <div className="relative">
                            <input
                              id="new-password"
                              type={showNewPassword ? "text" : "password"}
                              minLength={8}
                              autoComplete="new-password"
                              disabled={isDetailBusy || isCurrentAccount}
                              value={newPassword}
                              onChange={(event) => {
                                setNewPassword(event.target.value);
                                if (passwordError) setPasswordError("");
                              }}
                              placeholder="Nhập mật khẩu mới"
                              className={`h-9 w-full rounded-lg border px-3 pr-10 text-slate-800 focus:outline-none focus:ring-2 disabled:bg-slate-50 ${
                                passwordError
                                  ? "border-rose-400 focus:border-rose-500 focus:ring-rose-500/20"
                                  : "border-slate-200 focus:border-[#3A5FC3] focus:ring-[#3A5FC3]/20"
                              }`}
                            />
                            <button
                              type="button"
                              disabled={isDetailBusy || isCurrentAccount}
                              onClick={() => setShowNewPassword((visible) => !visible)}
                              aria-label={showNewPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                              className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-slate-400 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
                            >
                              {showNewPassword ? (
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.9 4.2A10.7 10.7 0 0112 4c5 0 9 4 10 8a11.8 11.8 0 01-2.1 4.1M6.2 6.2A11.8 11.8 0 002 12c1 4 5 8 10 8a10.7 10.7 0 005.1-1.3" />
                                </svg>
                              ) : (
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M2.5 12S6 5 12 5s9.5 7 9.5 7S18 19 12 19s-9.5-7-9.5-7z" />
                                  <circle cx="12" cy="12" r="3" strokeWidth="1.8" />
                                </svg>
                              )}
                            </button>
                          </div>
                          {passwordError && (
                            <p className="mt-1 text-[11px] font-medium text-rose-600">{passwordError}</p>
                          )}
                        </div>

                        {isCurrentAccount && (
                          <p className="mt-2 text-[11px] font-medium text-amber-700">
                            Không thể khóa hoặc đặt lại mật khẩu tài khoản đang sử dụng.
                          </p>
                        )}

                        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                          <button
                            type="button"
                            disabled={isDetailBusy || isCurrentAccount}
                            onClick={requestPasswordReset}
                            className="inline-flex min-h-9 items-center justify-center rounded-lg border border-[#3A5FC3]/30 bg-blue-50 px-3 py-2 font-bold text-[#3A5FC3] hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
                          >
                            Đặt lại mật khẩu
                          </button>
                          <button
                            type="button"
                            disabled={isDetailBusy || isCurrentAccount}
                            onClick={() =>
                              setConfirmAction(selectedLecturer.account?.is_active ? "lock" : "unlock")
                            }
                            className={`inline-flex min-h-9 items-center justify-center rounded-lg border px-3 py-2 font-bold disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer ${
                              selectedLecturer.account.is_active
                                ? "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                                : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                            }`}
                          >
                            {selectedLecturer.account.is_active ? "Khóa tài khoản" : "Mở khóa tài khoản"}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div className="rounded-xl border border-violet-200/80 bg-violet-50/40 p-4">
                          <label className="flex items-center gap-2 cursor-pointer font-bold text-violet-900">
                            <input
                              type="checkbox"
                              checked={grantAccount}
                              onChange={(e) => setGrantAccount(e.target.checked)}
                              className="h-4 w-4 rounded border-violet-300 text-violet-600 focus:ring-violet-500 cursor-pointer"
                            />
                            <span>{locale === "vi" ? "Cấp tài khoản đăng nhập hệ thống cho giảng viên này" : "Grant System Login Account"}</span>
                          </label>

                          {grantAccount && (
                            <div className="mt-3 space-y-3 pt-3 border-t border-violet-200/60 animate-in fade-in duration-200">
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div>
                                  <label className="block font-semibold text-slate-700 mb-1">
                                    {locale === "vi" ? "Email đăng nhập" : "Login Email"} <span className="text-rose-500">*</span>
                                  </label>
                                  <input
                                    type="email"
                                    required={grantAccount}
                                    value={grantEmail}
                                    onChange={(e) => setGrantEmail(e.target.value)}
                                    placeholder="example@ictu.edu.vn"
                                    className="h-9 w-full rounded-lg border border-slate-200 bg-white px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                                  />
                                </div>
                                <div>
                                  <label className="block font-semibold text-slate-700 mb-1">
                                    {locale === "vi" ? "Mật khẩu khởi tạo" : "Initial Password"} <span className="text-rose-500">*</span>
                                  </label>
                                  <input
                                    type="password"
                                    required={grantAccount}
                                    minLength={8}
                                    value={grantPassword}
                                    onChange={(e) => setGrantPassword(e.target.value)}
                                    placeholder="Tối thiểu 8 ký tự"
                                    className="h-9 w-full rounded-lg border border-slate-200 bg-white px-3 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                                  />
                                </div>
                              </div>
                              <div>
                                <label className="block font-semibold text-slate-700 mb-1">
                                  {locale === "vi" ? "Vai trò tài khoản" : "Role"}
                                </label>
                                <select
                                  value={grantRole}
                                  onChange={(e) => setGrantRole(e.target.value)}
                                  className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
                                >
                                  <option value="LECTURER">Giảng viên (LECTURER)</option>
                                  <option value="ADMIN">Quản trị viên (ADMIN)</option>
                                  <option value="REVIEWER">Phê duyệt viên (REVIEWER)</option>
                                </select>
                              </div>
                            </div>
                          )}
                        </div>

                        {!grantAccount && (
                          <p className="text-[11px] text-slate-400">
                            {locale === "vi"
                              ? "Hồ sơ chưa có tài khoản đăng nhập. Tích chọn ô trên để tạo tài khoản mới cho cán bộ này."
                              : "This profile has no linked account. Check the box above to grant one."}
                          </p>
                        )}
                      </div>
                    )}
                  </section>
                </div>

                <div className="flex shrink-0 items-center justify-end gap-2 border-t border-slate-100 bg-white px-4 py-3 sm:px-6">
                  <button
                    type="button"
                    disabled={isDetailBusy}
                    onClick={() => setIsDetailModalOpen(false)}
                    className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {t.common.cancel}
                  </button>
                  <button
                    type="submit"
                    disabled={isDetailBusy}
                    className="inline-flex min-w-28 items-center justify-center gap-1.5 rounded-lg bg-[#3A5FC3] px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#2f4ea6] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {detailAction === "save" && (
                      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    )}
                    <span>{detailAction === "save" ? "Đang lưu..." : "Lưu thay đổi"}</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        </ModalPortal>
      )}

      <ConfirmModal
        open={confirmAction !== null}
        title={
          confirmAction === "lock"
            ? "Khóa tài khoản?"
            : confirmAction === "unlock"
              ? "Mở khóa tài khoản?"
              : "Đặt lại mật khẩu?"
        }
        description={
          confirmAction === "lock"
            ? "Người dùng sẽ không thể đăng nhập cho đến khi tài khoản được mở khóa."
            : confirmAction === "unlock"
              ? "Người dùng sẽ có thể đăng nhập lại bằng thông tin đăng nhập hiện tại."
              : "Mật khẩu đăng nhập hiện tại của người dùng sẽ không còn hiệu lực."
        }
        confirmLabel={
          confirmAction === "lock"
            ? "Khóa tài khoản"
            : confirmAction === "unlock"
              ? "Mở khóa tài khoản"
              : "Đặt lại mật khẩu"
        }
        variant={confirmAction === "unlock" ? "primary" : "danger"}
        loading={isDetailBusy && detailAction !== "save"}
        onConfirm={handleSecurityAction}
        onCancel={() => {
          if (!isDetailBusy) setConfirmAction(null);
        }}
      />

      {/* ====================================================================== */}
      {/* MODAL 3: XÁC NHẬN XÓA GIẢNG VIÊN (CONFIRM MODAL) */}
      {/* ====================================================================== */}
      <ConfirmModal
        open={isDeleteModalOpen && selectedLecturer !== null}
        title={locale === "vi" ? "Xóa giảng viên?" : "Delete lecturer?"}
        description={
          <span>
            {locale === "vi"
              ? "Hồ sơ giảng viên sẽ bị xóa khỏi dữ liệu hiện tại nếu không có liên kết phụ thuộc. Lịch sử truy vết của hệ thống vẫn được giữ."
              : "The lecturer profile will be removed from active data if no dependencies exist. Audit history will remain intact."}
            {selectedLecturer && (
              <span className="mt-2 block font-semibold text-slate-800">
                {selectedLecturer.full_name} {selectedLecturer.staff_code ? `(${selectedLecturer.staff_code})` : ""}
              </span>
            )}
          </span>
        }
        confirmLabel={locale === "vi" ? "Xóa" : "Delete"}
        cancelLabel={t.common.cancel}
        variant="danger"
        loading={isSubmitting}
        onConfirm={handleDeleteConfirm}
        onCancel={() => {
          if (!isSubmitting) {
            setIsDeleteModalOpen(false);
            setSelectedLecturer(null);
          }
        }}
      />
    </div>
  );
}
