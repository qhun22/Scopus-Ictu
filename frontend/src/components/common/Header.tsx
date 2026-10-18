import { safeDisplayName } from "../../utils/displayName";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
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
  const { locale, setLocale, t, isLanguageSwitching } = useI18n();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const safeName = safeDisplayName(user?.display_name, user?.role, {
    locale: locale === "vi" ? "vi" : "en",
    fallback: user?.email || (locale === "vi" ? "Người dùng" : "User"),
  });

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



  const getPageTitle = () => {
    // Publication detail (/publications/:eid) belongs to the "Công bố" section, not the generic "Hệ thống" fallback.
    if (location.pathname.startsWith("/publications/")) return t.nav.publications;
    switch (location.pathname) {
      case "/home":
        return t.nav.home;
      case "/search":
        return locale === "vi" ? "Tra cứu" : "Search";
      case "/dashboard":
        return t.nav.dashboard;
      case "/imports":
        return t.nav.imports;
      case "/normalization":
        return t.nav.normalization;
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
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[5px] border border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900 md:hidden focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
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
          className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-[5px] border border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900 md:flex focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
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
          className="flex h-10 items-center gap-0.5 sm:gap-1 rounded-[5px] border border-slate-200 bg-white p-0.5 sm:p-1 shadow-2xs"
          role="group"
          aria-label="Language selector"
        >
          <button
            type="button"
            disabled={isLanguageSwitching || locale === "vi"}
            onClick={() => setLocale("vi")}
            className={`flex h-full items-center justify-center rounded-[5px] px-2.5 sm:px-3 text-xs transition-all ${
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
            className={`flex h-full items-center justify-center rounded-[5px] px-2.5 sm:px-3 text-xs transition-all ${
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
            className="flex h-10 items-center gap-1.5 sm:gap-2.5 rounded-[5px] border border-slate-200 bg-slate-50/70 py-1 pl-1.5 sm:pl-2 pr-2 sm:pr-3 text-left transition-colors hover:bg-slate-100/90 focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
            aria-expanded={dropdownOpen}
            aria-haspopup="true"
          >
            <div className="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-full bg-[#3A5FC3] text-xs font-bold text-white shadow-sm shrink-0">
              {safeName.charAt(0).toUpperCase()}
            </div>

            <div className="hidden flex-col md:flex min-w-0 max-w-[140px] lg:max-w-[180px]">
              <span className="text-xs font-semibold text-slate-800 leading-tight truncate">
                {safeName}
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
            <div className="absolute right-0 top-full mt-3 w-full min-w-[130px] md:min-w-0 md:inset-x-0 z-50 animate-in fade-in zoom-in-95 duration-100">
              <button
                type="button"
                disabled={isLoggingOut}
                onClick={handleLogout}
                className="group flex h-10 w-full cursor-pointer items-center gap-1.5 sm:gap-2.5 rounded-[5px] border border-slate-200 bg-slate-50/95 hover:bg-rose-50/90 hover:border-rose-200 py-1 pl-1.5 sm:pl-2 pr-2 sm:pr-3 text-left shadow-lg backdrop-blur-sm transition-all focus:outline-none focus:ring-2 focus:ring-rose-500/20 disabled:opacity-50"
              >
                <div className="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-full bg-rose-500 text-white shadow-sm shrink-0 transition-transform group-hover:scale-105">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                </div>

                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-semibold text-rose-600 leading-tight truncate">
                    {isLoggingOut ? t.header.loggingOut : t.header.logout}
                  </span>
                </div>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
