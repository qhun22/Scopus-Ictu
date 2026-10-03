import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import { useI18n } from "../../i18n";

interface HeaderProps {
  onToggleMobileMenu: () => void;
  isSidebarCollapsed: boolean;
  onToggleSidebarCollapse: () => void;
}

export default function Header({
  onToggleMobileMenu,
  isSidebarCollapsed,
  onToggleSidebarCollapse,
}: HeaderProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const { locale, setLocale, t, getRoleLabel, isLanguageSwitching } = useI18n();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Close dropdown on route change
  useEffect(() => {
    setDropdownOpen(false);
  }, [location.pathname]);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
      toast.info(
        locale === "vi" ? "Đăng xuất thành công" : "Logout successful",
        locale === "vi"
          ? "Bạn đã đăng xuất khỏi hệ thống."
          : "You have been logged out of the system.",
      );
      navigate("/login", { replace: true });
    } catch {
      toast.error(
        locale === "vi" ? "Lỗi đăng xuất" : "Logout error",
        locale === "vi"
          ? "Không thể hoàn tất đăng xuất trên máy chủ."
          : "Could not complete logout on the server.",
      );
      navigate("/login", { replace: true });
    } finally {
      setIsLoggingOut(false);
    }
  };

  const renderRoleBadge = (role?: string) => {
    const r = role?.toUpperCase();
    if (r === "ADMIN") {
      return (
        <span className="inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs font-bold text-[#3A5FC3]">
          {getRoleLabel(role)}
        </span>
      );
    }
    if (r === "REVIEWER") {
      return (
        <span className="inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-bold text-amber-700">
          {getRoleLabel(role)}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700">
        {getRoleLabel(role)}
      </span>
    );
  };

  const getPageTitle = () => {
    switch (location.pathname) {
      case "/home":
        return t.nav.home;
      case "/search":
        return locale === "vi" ? "Tra cứu" : "Search";
      case "/dashboard":
        return t.nav.dashboard;
      case "/imports":
        return t.nav.imports;
      case "/lecturers":
        return t.nav.lecturers;
      case "/publications":
        return t.nav.publications;
      case "/my-publications":
        return t.nav.myPublications;
      case "/profile":
        return t.nav.profile;
      case "/identity":
        return t.nav.identity;
      case "/reviews":
      case "/approval-queue":
        return t.nav.reviews;
      case "/review-history":
        return t.nav.reviewHistory;
      case "/users":
        return t.nav.users;
      case "/audit-logs":
        return t.nav.auditLogs;
      case "/tasks":
        return t.nav.tasks;
      default:
        return t.header.system;
    }
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200/80 bg-white/95 px-3 sm:px-6 backdrop-blur transition-all">
      {/* Left side: Mobile Hamburger, Desktop Sidebar Collapse, Current Title */}
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        {/* Mobile menu toggle */}
        <button
          type="button"
          onClick={onToggleMobileMenu}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900 md:hidden focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
          aria-label={t.header.openMenu}
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Desktop Sidebar Collapse Toggle */}
        <button
          type="button"
          onClick={onToggleSidebarCollapse}
          className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900 md:flex focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
          title={isSidebarCollapsed ? t.header.expandSidebar : t.header.collapseSidebar}
          aria-label={isSidebarCollapsed ? t.header.expandSidebar : t.header.collapseSidebar}
        >
          {isSidebarCollapsed ? (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          ) : (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          )}
        </button>

        {/* Current Page Title */}
        <div className="min-w-0">
          <h2 className="truncate text-sm font-bold text-slate-800 sm:text-base md:text-lg">
            {getPageTitle()}
          </h2>
        </div>
      </div>

      {/* Right side: Language Switcher & User Profile Dropdown */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Language Switcher: VI | EN */}
        <div
          className="flex h-10 items-center gap-0.5 sm:gap-1 rounded-lg border border-slate-200 bg-white p-0.5 sm:p-1 shadow-2xs"
          role="group"
          aria-label="Language selector"
        >
          <button
            type="button"
            disabled={isLanguageSwitching || locale === "vi"}
            onClick={() => setLocale("vi")}
            className={`flex h-full items-center justify-center rounded-md px-2.5 sm:px-3 text-xs transition-all ${
              locale === "vi"
                ? "bg-[#3A5FC3] text-white font-bold shadow-xs cursor-default"
                : "text-slate-600 hover:text-slate-900 font-semibold hover:bg-slate-50 cursor-pointer"
            } ${isLanguageSwitching ? "opacity-60 cursor-not-allowed" : ""}`}
            title="Tiếng Việt"
            aria-label={locale === "vi" ? "Tiếng Việt (đang chọn)" : "Switch to Vietnamese"}
          >
            VI
          </button>
          <span className="text-slate-300 select-none text-xs">|</span>
          <button
            type="button"
            disabled={isLanguageSwitching || locale === "en"}
            onClick={() => setLocale("en")}
            className={`flex h-full items-center justify-center rounded-md px-2.5 sm:px-3 text-xs transition-all ${
              locale === "en"
                ? "bg-[#3A5FC3] text-white font-bold shadow-xs cursor-default"
                : "text-slate-600 hover:text-slate-900 font-semibold hover:bg-slate-50 cursor-pointer"
            } ${isLanguageSwitching ? "opacity-60 cursor-not-allowed" : ""}`}
            title="English"
            aria-label={locale === "en" ? "English (selected)" : "Chuyển sang tiếng Anh"}
          >
            EN
          </button>
        </div>

        {/* User profile dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setDropdownOpen((prev) => !prev)}
            className="flex h-10 items-center gap-1.5 sm:gap-2.5 rounded-lg border border-slate-200 bg-slate-50/70 py-1 pl-1.5 sm:pl-2 pr-2 sm:pr-3 text-left transition-colors hover:bg-slate-100/90 focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
            aria-expanded={dropdownOpen}
            aria-haspopup="true"
          >
            <div className="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-full bg-[#3A5FC3] text-xs font-bold text-white shadow-sm shrink-0">
              {user?.display_name
                ? user.display_name.charAt(0).toUpperCase()
                : user?.email?.charAt(0).toUpperCase() || "U"}
            </div>

            <div className="hidden flex-col md:flex min-w-0 max-w-[140px] lg:max-w-[180px]">
              <span className="text-xs font-semibold text-slate-800 leading-tight truncate">
                {user?.display_name || user?.email || (locale === "vi" ? "Người dùng" : "User")}
              </span>
              <span className="text-[10px] text-slate-500 leading-tight truncate">
                {user?.email}
              </span>
            </div>

            <svg
              className={`h-4 w-4 text-slate-400 shrink-0 transition-transform duration-200 ${
                dropdownOpen ? "rotate-180" : ""
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Dropdown Menu */}
          {dropdownOpen && (
            <div className="absolute right-0 top-full mt-2 w-60 sm:w-64 max-w-[calc(100vw-2rem)] origin-top-right rounded-xl border border-slate-200 bg-white p-2 shadow-xl ring-1 ring-black/5 focus:outline-none animate-in fade-in zoom-in-95 duration-100 z-50">
              <div className="border-b border-slate-100 px-3 py-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900">
                    {user?.display_name || (locale === "vi" ? "Tài khoản" : "Account")}
                  </span>
                  <div className="sm:hidden">{renderRoleBadge(user?.role)}</div>
                </div>
                <p className="mt-0.5 truncate text-xs text-slate-500">
                  {user?.email}
                </p>
              </div>

              <div className="py-1">
                <Link
                  to={user?.role?.toUpperCase() === "LECTURER" ? "/profile" : "/home"}
                  onClick={() => setDropdownOpen(false)}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900"
                >
                  <svg className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  <span>{t.header.accountInfo}</span>
                </Link>
              </div>

              <div className="border-t border-slate-100 pt-1">
                <button
                  type="button"
                  disabled={isLoggingOut}
                  onClick={handleLogout}
                  className="flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 hover:text-rose-700 disabled:opacity-50"
                >
                  <svg className="h-4 w-4 text-rose-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  <span>{isLoggingOut ? t.header.loggingOut : t.header.logout}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
