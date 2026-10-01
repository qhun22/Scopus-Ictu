import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";

export default function HomePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
      toast.info("Đăng xuất", "Bạn đã đăng xuất khỏi hệ thống.");
      navigate("/login", { replace: true });
    } catch {
      toast.error("Lỗi đăng xuất", "Không thể hoàn tất đăng xuất trên máy chủ.");
      navigate("/login", { replace: true });
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-8 sm:px-6">
      <section className="w-full max-w-xl rounded-2xl border border-slate-100 bg-white p-8 text-center shadow-lg shadow-slate-200/70 sm:p-10">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-slate-50 p-2 shadow-sm ring-4 ring-slate-100">
          <img
            src="/assets/ictu.png"
            alt="Logo ICTU"
            className="h-full w-full rounded-full object-contain"
          />
        </div>

        <h1 className="mt-5 text-2xl font-bold text-slate-900 sm:text-3xl">
          Cổng thông tin Scopus ICTU
        </h1>

        <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50/60 p-4 text-center">
          <p className="text-base font-semibold text-slate-800">
            Xin chào, <span className="text-[#3A5FC3]">{user?.display_name ?? "Người dùng"}</span>
          </p>
          <div className="mt-2 flex items-center justify-center gap-2 text-xs font-medium text-slate-600">
            <span>Email: <strong className="text-slate-800">{user?.email}</strong></span>
            <span>•</span>
            <span>
              Vai trò:{" "}
              <span className="inline-block rounded bg-[#3A5FC3] px-2 py-0.5 text-xs font-bold text-white uppercase">
                {user?.role}
              </span>
            </span>
          </div>
        </div>

        <p className="mt-6 text-sm text-slate-500">
          Hệ thống định danh và đối sánh hồ sơ giảng viên — Phiên bản M2.2
        </p>

        <div className="mt-8 flex items-center justify-center gap-4">
          <button
            type="button"
            disabled={isLoggingOut}
            onClick={handleLogout}
            className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-400 disabled:opacity-60"
          >
            {isLoggingOut ? "Đang đăng xuất..." : "Đăng xuất"}
          </button>
        </div>
      </section>
    </main>
  );
}
