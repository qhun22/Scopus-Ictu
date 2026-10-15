import React, { useState } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useI18n } from "../../i18n";

interface SidebarProps {
  isCollapsed: boolean;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

interface NavItem {
  to: string;
  label: string;
  badge?: string;
  icon: (active: boolean) => React.ReactNode;
}

interface NavGroup {
  heading?: string;
  items: NavItem[];
}

// ─── Icon helpers ──────────────────────────────────────────────
const ic = (active: boolean, path: string) => (
  <svg
    className={`h-5 w-5 flex-shrink-0 ${active ? "text-[#3A5FC3]" : "text-slate-400"}`}
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d={path} />
  </svg>
);

const ICONS = {
  home: (a: boolean) => ic(a, "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"),
  dashboard: (a: boolean) => ic(a, "M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"),
  imports: (a: boolean) => ic(a, "M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"),
  normalization: (a: boolean) => ic(a, "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"),
  lecturers: (a: boolean) => ic(a, "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"),
  publications: (a: boolean) => ic(a, "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"),
  reviews: (a: boolean) => ic(a, "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"),
  reviewHistory: (a: boolean) => ic(a, "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"),
  auditLogs: (a: boolean) => ic(a, "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"),
  tasks: (a: boolean) => ic(a, "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"),
  profile: (a: boolean) => ic(a, "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"),
  myPublications: (a: boolean) => ic(a, "M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"),
  identity: (a: boolean) => ic(a, "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"),
  search: (a: boolean) => ic(a, "M21 21l-4.35-4.35M17 10a7 7 0 11-14 0 7 7 0 0114 0z"),
};


// ─── Group heading ──────────────────────────────────────────────
function GroupHeading({ label, collapsed }: { label: string; collapsed: boolean }) {
  if (collapsed) {
    return <div className="mx-3 my-2 border-t border-slate-100" />;
  }
  return (
    <div className="mx-3 mb-1 mt-4 first:mt-2">
      <p className="px-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
        {label}
      </p>
    </div>
  );
}

export default function Sidebar({ isCollapsed, isMobileOpen, onCloseMobile }: SidebarProps) {
  const { user } = useAuth();
  const { t } = useI18n();
  const [logoSrc, setLogoSrc] = useState("/assets/ictu.png");

  const role = user?.role?.toUpperCase() || "LECTURER";

  // ── ADMIN nav groups ──────────────────────────────────────────
  const adminGroups: NavGroup[] = [
    {
      items: [{ to: "/home", label: t.nav.home, icon: ICONS.home }],
    },
    {
      heading: t.nav.groupWorkflow,
      items: [
        { to: "/imports",       label: t.nav.imports,       icon: ICONS.imports },
        { to: "/normalization", label: t.nav.normalization,  icon: ICONS.normalization },
        { to: "/lecturers",     label: t.nav.lecturers,      icon: ICONS.lecturers },
        { to: "/reviews",       label: t.nav.reviews,        icon: ICONS.reviews },
        { to: "/review-history",label: t.nav.reviewHistory,  icon: ICONS.reviewHistory },
      ],
    },
    {
      heading: t.nav.groupLookup,
      items: [
        { to: "/publications",  label: t.nav.publications,   icon: ICONS.publications },
        { to: "/search",        label: t.nav.search,         icon: ICONS.search },
      ],
    },
    {
      heading: t.nav.groupAdmin,
      items: [
        { to: "/dashboard",     label: t.nav.dashboard,      icon: ICONS.dashboard },
        { to: "/audit-logs",    label: t.nav.auditLogs,      icon: ICONS.auditLogs },
        { to: "/tasks",         label: t.nav.tasks,          icon: ICONS.tasks },
      ],
    },
  ];

  // ── REVIEWER nav groups ────────────────────────────────────────
  const reviewerGroups: NavGroup[] = [
    {
      items: [{ to: "/home", label: t.nav.home, icon: ICONS.home }],
    },
    {
      heading: t.nav.groupWorkflow,
      items: [
        { to: "/reviews",        label: t.nav.reviews,       icon: ICONS.reviews },
        { to: "/review-history", label: t.nav.reviewHistory, icon: ICONS.reviewHistory },
      ],
    },
    {
      heading: t.nav.groupLookup,
      items: [
        { to: "/publications", label: t.nav.publications, icon: ICONS.publications },
        { to: "/search",       label: t.nav.search,        icon: ICONS.search },
      ],
    },
  ];

  // ── LECTURER nav groups ────────────────────────────────────────
  const lecturerGroups: NavGroup[] = [
    {
      items: [{ to: "/home", label: t.nav.home, icon: ICONS.home }],
    },
    {
      heading: t.nav.groupLookup,
      items: [
        { to: "/publications",     label: t.nav.publications,    icon: ICONS.publications },
        { to: "/search",           label: t.nav.search,          icon: ICONS.search },
      ],
    },
    {
      items: [
        { to: "/my-publications",  label: t.nav.myPublications,  icon: ICONS.myPublications },
        { to: "/identity",         label: t.nav.identity,        icon: ICONS.identity },
        { to: "/profile",          label: t.nav.profile,         icon: ICONS.profile },
      ],
    },
  ];

  const groups =
    role === "ADMIN" ? adminGroups : role === "REVIEWER" ? reviewerGroups : lecturerGroups;

  // ── Render a single NavLink ────────────────────────────────────
  const renderLink = (item: NavItem, isMobile = false) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.to === "/home"}
      onClick={isMobile ? onCloseMobile : undefined}
      title={isCollapsed && !isMobile ? item.label : undefined}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all ${
          isActive
            ? "bg-[#3A5FC3]/10 text-[#3A5FC3] font-semibold shadow-xs"
            : "text-slate-600 hover:bg-slate-100/80 hover:text-slate-900"
        } ${isCollapsed && !isMobile ? "justify-center px-2" : ""}`
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r bg-[#3A5FC3]" />
          )}
          {item.icon(isActive)}
          {(!isCollapsed || isMobile) && (
            <span className="flex-1 truncate">{item.label}</span>
          )}
        </>
      )}
    </NavLink>
  );

  // ── Render all groups ─────────────────────────────────────────
  const renderGroups = (isMobile = false) => (
    <nav className="flex-1 overflow-y-auto py-2">
      {groups.map((group, gi) => (
        <div key={gi}>
          {group.heading && (
            <GroupHeading label={group.heading} collapsed={isCollapsed && !isMobile} />
          )}
          <div className="space-y-0.5 px-3">
            {group.items.map((item) => renderLink(item, isMobile))}
          </div>
        </div>
      ))}
    </nav>
  );

  return (
    <>
      {/* ── Desktop / Tablet sidebar ─────────────────────────────── */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 hidden flex-col border-r border-slate-200/80 bg-white transition-all duration-200 ease-out md:flex ${
          isCollapsed ? "w-20" : "w-64"
        }`}
      >
        {/* Brand */}
        <div className="flex h-16 items-center border-b border-slate-200/80 px-4">
          <div className="flex items-center gap-3 overflow-hidden">
            <img
              src={logoSrc}
              alt="Logo ICTU"
              onError={() => {
                if (logoSrc === "/assets/ictu.png") setLogoSrc("/logoictu.png");
              }}
              className="h-9 w-9 flex-shrink-0 object-contain"
            />
            {!isCollapsed && (
              <div className="flex flex-col truncate">
                <span className="text-sm font-bold tracking-tight text-[#3A5FC3] uppercase">
                  SCOPUS ICTU
                </span>
                <span className="text-[10px] font-medium text-slate-400 truncate">
                  Cổng thông tin Scopus
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Nav groups */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {renderGroups(false)}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200/80 p-3">
          <div
            className={`flex items-center rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500 ${
              isCollapsed ? "justify-center" : "justify-between"
            }`}
          >
            {!isCollapsed && <span className="font-semibold text-slate-600">Phiên bản</span>}
            <span className="rounded bg-slate-200/70 px-1.5 py-0.5 text-[10px] font-bold text-slate-700">
              M2.7
            </span>
          </div>
        </div>
      </aside>

      {/* ── Mobile drawer ────────────────────────────────────────── */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            onClick={onCloseMobile}
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
            aria-hidden="true"
          />
          <div className="fixed inset-y-0 left-0 flex w-72 flex-col bg-white shadow-2xl transition-transform animate-in slide-in-from-left duration-200">
            {/* Drawer header */}
            <div className="flex h-16 items-center justify-between border-b border-slate-200/80 px-4">
              <div className="flex items-center gap-3">
                <img src={logoSrc} alt="Logo ICTU" className="h-9 w-9 object-contain" />
                <div className="flex flex-col">
                  <span className="text-sm font-bold tracking-tight text-[#3A5FC3] uppercase">
                    SCOPUS ICTU
                  </span>
                  <span className="text-[10px] font-medium text-slate-400">
                    Cổng thông tin Scopus
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={onCloseMobile}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus:outline-none"
                aria-label="Đóng menu"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Mobile nav groups */}
            <div className="flex flex-1 flex-col overflow-hidden">
              {renderGroups(true)}
            </div>

            <div className="border-t border-slate-200/80 p-4">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="font-semibold text-slate-600">Hệ thống Scopus ICTU</span>
                <span className="rounded bg-slate-200/70 px-1.5 py-0.5 text-[10px] font-bold text-slate-700">
                  M2.7
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
