import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useI18n } from "../../i18n";

interface OverviewCard {
  title: string;
  statusLabel: string;
  subtext: string;
  to: string;
  iconBg: string;
  iconColor: string;
  badgeColor: string;
  icon: React.ReactNode;
}

interface QuickAction {
  title: string;
  description: string;
  to: string;
  iconBg: string;
  iconColor: string;
  icon: React.ReactNode;
}

export default function HomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { t } = useI18n();

  const [searchQuery, setSearchQuery] = useState("");
  const [searchError, setSearchError] = useState("");

  const role = user?.role?.toUpperCase() || "LECTURER";

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = searchQuery.trim();
    if (!trimmed) {
      setSearchError(t.home.searchEmptyError);
      return;
    }
    setSearchError("");
    navigate(`/search?q=${encodeURIComponent(trimmed)}`);
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    if (searchError) {
      setSearchError("");
    }
  };

  // 1. Role Overview Cards Config
  const getOverviewCards = (): OverviewCard[] => {
    if (role === "ADMIN") {
      return [
        {
          title: t.home.cardLecturersTitle,
          statusLabel: t.home.cardLecturersStatus,
          subtext: t.home.cardLecturersSubtext,
          to: "/lecturers",
          iconBg: "bg-indigo-50 border-indigo-100",
          iconColor: "text-indigo-600",
          badgeColor: "bg-indigo-50 text-indigo-700 border-indigo-200",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ),
        },
        {
          title: t.home.cardPubsTitle,
          statusLabel: t.home.cardPubsStatus,
          subtext: t.home.cardPubsSubtext,
          to: "/publications",
          iconBg: "bg-violet-50 border-violet-100",
          iconColor: "text-violet-600",
          badgeColor: "bg-violet-50 text-violet-700 border-violet-200",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          ),
        },
        {
          title: t.home.cardReviewsTitle,
          statusLabel: t.home.cardReviewsStatus,
          subtext: t.home.cardReviewsSubtext,
          to: "/reviews",
          iconBg: "bg-amber-50 border-amber-100",
          iconColor: "text-amber-600",
          badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
          ),
        },
        {
          title: t.home.cardImportsTitle,
          statusLabel: t.home.cardImportsStatus,
          subtext: t.home.cardImportsSubtext,
          to: "/imports",
          iconBg: "bg-teal-50 border-teal-100",
          iconColor: "text-teal-600",
          badgeColor: "bg-teal-50 text-teal-700 border-teal-200",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
            </svg>
          ),
        },
      ];
    }

    if (role === "REVIEWER") {
      return [
        {
          title: t.home.cardReviewsTitle,
          statusLabel: t.home.cardReviewsStatus,
          subtext: t.home.cardReviewsSubtext,
          to: "/reviews",
          iconBg: "bg-amber-50 border-amber-100",
          iconColor: "text-amber-600",
          badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
          ),
        },
        {
          title: t.home.cardPubsTitle,
          statusLabel: t.home.cardPubsStatus,
          subtext: t.home.cardPubsSubtext,
          to: "/publications",
          iconBg: "bg-blue-50 border-blue-100",
          iconColor: "text-[#3A5FC3]",
          badgeColor: "bg-blue-50 text-[#3A5FC3] border-blue-200",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          ),
        },
        {
          title: t.home.cardReviewHistoryTitle,
          statusLabel: t.home.cardReviewHistoryStatus,
          subtext: t.home.cardReviewHistorySubtext,
          to: "/review-history",
          iconBg: "bg-indigo-50 border-indigo-100",
          iconColor: "text-indigo-600",
          badgeColor: "bg-indigo-50 text-indigo-700 border-indigo-200",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ),
        },
      ];
    }

    // Default: LECTURER
    return [
      {
        title: t.home.cardProfileTitle,
        statusLabel: t.home.cardProfileStatus,
        subtext: t.home.cardProfileSubtext,
        to: "/profile",
        iconBg: "bg-emerald-50 border-emerald-100",
        iconColor: "text-emerald-600",
        badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
        icon: (
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        ),
      },
      {
        title: t.home.cardMyPubsTitle,
        statusLabel: t.home.cardMyPubsStatus,
        subtext: t.home.cardMyPubsSubtext,
        to: "/my-publications",
        iconBg: "bg-blue-50 border-blue-100",
        iconColor: "text-[#3A5FC3]",
        badgeColor: "bg-blue-50 text-[#3A5FC3] border-blue-200",
        icon: (
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
        ),
      },
      {
        title: t.home.cardIdentityTitle,
        statusLabel: t.home.cardIdentityStatus,
        subtext: t.home.cardIdentitySubtext,
        to: "/identity",
        iconBg: "bg-indigo-50 border-indigo-100",
        iconColor: "text-indigo-600",
        badgeColor: "bg-indigo-50 text-indigo-700 border-indigo-200",
        icon: (
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        ),
      },
    ];
  };

  // 2. Quick Actions Config
  const getQuickActions = (): QuickAction[] => {
    if (role === "ADMIN") {
      return [
        {
          title: t.nav.dashboard,
          description: t.home.actionDashboardDesc,
          to: "/dashboard",
          iconBg: "bg-blue-50 text-[#3A5FC3]",
          iconColor: "text-[#3A5FC3]",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
          ),
        },
        {
          title: t.nav.imports,
          description: t.home.actionImportsDesc,
          to: "/imports",
          iconBg: "bg-teal-50 text-teal-600",
          iconColor: "text-teal-600",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
            </svg>
          ),
        },
        {
          title: t.nav.lecturers,
          description: t.home.actionLecturersDesc,
          to: "/lecturers",
          iconBg: "bg-indigo-50 text-indigo-600",
          iconColor: "text-indigo-600",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ),
        },
        {
          title: t.nav.users,
          description: t.home.actionUsersDesc,
          to: "/users",
          iconBg: "bg-emerald-50 text-emerald-600",
          iconColor: "text-emerald-600",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          ),
        },
        {
          title: t.nav.auditLogs,
          description: t.home.actionAuditLogsDesc,
          to: "/audit-logs",
          iconBg: "bg-amber-50 text-amber-600",
          iconColor: "text-amber-600",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          ),
        },
        {
          title: t.nav.tasks,
          description: t.home.actionTasksDesc,
          to: "/tasks",
          iconBg: "bg-rose-50 text-rose-600",
          iconColor: "text-rose-600",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          ),
        },
      ];
    }

    if (role === "REVIEWER") {
      return [
        {
          title: t.nav.reviews,
          description: t.home.actionReviewsDesc,
          to: "/reviews",
          iconBg: "bg-amber-50 text-amber-600",
          iconColor: "text-amber-600",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
          ),
        },
        {
          title: t.nav.publications,
          description: t.home.actionPubsDesc,
          to: "/publications",
          iconBg: "bg-blue-50 text-[#3A5FC3]",
          iconColor: "text-[#3A5FC3]",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          ),
        },
        {
          title: t.nav.reviewHistory,
          description: t.home.actionReviewHistoryDesc,
          to: "/review-history",
          iconBg: "bg-indigo-50 text-indigo-600",
          iconColor: "text-indigo-600",
          icon: (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ),
        },
      ];
    }

    // Default: LECTURER
    return [
      {
        title: t.nav.profile,
        description: t.home.actionProfileDesc,
        to: "/profile",
        iconBg: "bg-emerald-50 text-emerald-600",
        iconColor: "text-emerald-600",
        icon: (
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        ),
      },
      {
        title: t.nav.myPublications,
        description: t.home.actionMyPubsDesc,
        to: "/my-publications",
        iconBg: "bg-blue-50 text-[#3A5FC3]",
        iconColor: "text-[#3A5FC3]",
        icon: (
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
        ),
      },
      {
        title: t.nav.identity,
        description: t.home.actionIdentityDesc,
        to: "/identity",
        iconBg: "bg-indigo-50 text-indigo-600",
        iconColor: "text-indigo-600",
        icon: (
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        ),
      },
    ];
  };

  const overviewCards = getOverviewCards();
  const quickActions = getQuickActions();

  // Dynamic titles per role
  const getChartTitle = () => {
    if (role === "ADMIN") return t.home.chartTitleAdmin;
    if (role === "REVIEWER") return t.home.chartTitleReviewer;
    return t.home.chartTitleLecturer;
  };

  const getRecentTitle = () => {
    if (role === "ADMIN") return t.home.recentTitleAdmin;
    if (role === "REVIEWER") return t.home.recentTitleReviewer;
    return t.home.recentTitleLecturer;
  };

  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* ====================================================================== */}
      {/* 1. WELCOME BANNER */}
      {/* ====================================================================== */}
      <section className="relative overflow-hidden rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs sm:p-6">
        <div className="relative z-10">
          <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">
            {t.home.welcome},{" "}
            <span className="text-[#3A5FC3]">
              {user?.display_name || user?.email || t.home.welcomeGuest}
            </span>
          </h1>
          <p className="mt-1 text-xs text-slate-500 sm:text-sm">
            {t.home.welcomeSubtitle}
          </p>
        </div>
      </section>

      {/* ====================================================================== */}
      {/* 2. QUICK SEARCH — hidden for LECTURER (no access to /search) */}
      {/* ====================================================================== */}
      {role !== "LECTURER" && <section className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs sm:p-5">
        <div className="mb-2.5 flex items-center gap-2">
          <svg className="h-4 w-4 text-[#3A5FC3]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <h2 className="text-sm font-bold text-slate-800 sm:text-base">
            {t.home.quickSearchTitle}
          </h2>
        </div>

        <form onSubmit={handleSearchSubmit} className="relative">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <input
                type="text"
                value={searchQuery}
                onChange={handleSearchChange}
                placeholder={t.home.quickSearchPlaceholder}
                className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50/50 pl-9 pr-9 text-xs text-slate-800 placeholder:text-slate-400 transition-all focus:border-[#3A5FC3] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 sm:text-sm"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600 focus:outline-none cursor-pointer"
                  aria-label="Clear search"
                >
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>

            <button
              type="submit"
              className="inline-flex h-10 cursor-pointer items-center justify-center gap-1.5 rounded-lg bg-[#3A5FC3] px-5 text-xs font-bold text-white shadow-xs transition-all duration-150 hover:bg-[#2f4ea6] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/30 sm:text-sm"
            >
              <span>{t.home.searchBtn}</span>
            </button>
          </div>

          {searchError && (
            <p className="mt-1 text-xs font-medium text-rose-500">{searchError}</p>
          )}
        </form>
      </section>}

      {/* ====================================================================== */}
      {/* 3. ROLE OVERVIEW */}
      {/* ====================================================================== */}
      <section className="space-y-2.5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-800 sm:text-base">
            {t.home.roleOverviewTitle}
          </h2>
        </div>

        <div className={`grid grid-cols-1 gap-3 sm:grid-cols-2 ${role === "ADMIN" ? "xl:grid-cols-4 lg:grid-cols-2" : "lg:grid-cols-3"} sm:gap-4`}>
          {overviewCards.map((card) => (
            <Link
              key={card.to + card.title}
              to={card.to}
              className="group relative flex flex-col justify-between rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs transition-all duration-150 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-sm cursor-pointer"
            >
              <div>
                <div className="flex items-center justify-between">
                  <div
                    className={`flex h-9 w-9 items-center justify-center rounded-lg border ${card.iconBg} ${card.iconColor}`}
                  >
                    {card.icon}
                  </div>
                  <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${card.badgeColor}`}>
                    {card.statusLabel}
                  </span>
                </div>

                <h3 className="mt-3 text-sm font-bold text-slate-800 transition-colors group-hover:text-[#3A5FC3] sm:text-base">
                  {card.title}
                </h3>
                <p className="mt-0.5 text-[11px] text-slate-500 leading-relaxed sm:text-xs">
                  {card.subtext}
                </p>
              </div>

              <div className="mt-3 flex items-center gap-1 text-xs font-semibold text-[#3A5FC3]">
                <span>{t.common.viewDetails}</span>
                <svg className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* ====================================================================== */}
      {/* 4 & 5. CHART / SUMMARY & RECENT INFORMATION */}
      {/* ====================================================================== */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Visual Summary / Small Chart Container */}
        <div className="flex flex-col justify-between rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs sm:p-5">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-800 sm:text-base">
                {getChartTitle()}
              </h3>
              <span className="text-[10px] font-medium text-slate-400">
                {t.home.chartPeriodicSync}
              </span>
            </div>
            <p className="mt-0.5 text-[11px] text-slate-500">
              {t.home.chartSubtitle}
            </p>
          </div>

          {/* Academic Chart Skeleton Frame & Empty State */}
          <div className="relative my-4 flex h-36 flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/50 p-4 text-center">
            {/* Background grid skeleton lines */}
            <div className="pointer-events-none absolute inset-x-4 top-4 bottom-4 flex flex-col justify-between opacity-30" aria-hidden="true">
              <div className="border-b border-slate-300 w-full" />
              <div className="border-b border-slate-300 w-full" />
              <div className="border-b border-slate-300 w-full" />
            </div>

            <div className="relative z-10 flex flex-col items-center">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-slate-400 shadow-xs border border-slate-200">
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <p className="mt-2 text-xs font-semibold text-slate-700">
                {t.home.chartEmpty}
              </p>
              <p className="mt-0.5 max-w-xs text-[10px] text-slate-400">
                {t.home.chartEmptySub}
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-100 pt-2.5">
            <span>{t.home.chartSource}</span>
            <span>{t.home.chartStatusReady}</span>
          </div>
        </div>

        {/* Recent Information Container */}
        <div className="flex flex-col justify-between rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs sm:p-5">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-800 sm:text-base">
                {getRecentTitle()}
              </h3>
              <span className="text-[10px] font-medium text-slate-400">
                {t.home.recentRealtime}
              </span>
            </div>
            <p className="mt-0.5 text-[11px] text-slate-500">
              {t.home.recentSubtitle}
            </p>
          </div>

          {/* Empty State Box */}
          <div className="my-4 flex h-36 flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/50 p-4 text-center">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-slate-400 shadow-xs border border-slate-200">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <p className="mt-2 text-xs font-semibold text-slate-700">
              {t.home.recentEmpty}
            </p>
            <p className="mt-0.5 max-w-xs text-[10px] text-slate-400">
              {t.home.recentEmptySub}
            </p>
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-100 pt-2.5">
            <span>{t.home.autoUpdate}</span>
            <Link to="/publications" className="font-medium text-[#3A5FC3] hover:underline">
              {t.home.viewAll}
            </Link>
          </div>
        </div>
      </section>

      {/* ====================================================================== */}
      {/* 6. QUICK ACTIONS */}
      {/* ====================================================================== */}
      <section className="space-y-2.5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-800 sm:text-base">
              {t.home.quickActionsTitle}
            </h2>
            <p className="text-[11px] text-slate-500">
              {t.home.quickActionsSubtitle}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {quickActions.map((action) => (
            <Link
              key={action.to}
              to={action.to}
              className="group flex items-center justify-between rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs transition-all duration-150 hover:border-slate-300 hover:bg-slate-50/60 hover:shadow-xs cursor-pointer"
            >
              <div className="flex items-center gap-3">
                <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${action.iconBg}`}>
                  {action.icon}
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-800 group-hover:text-[#3A5FC3] sm:text-sm">
                    {action.title}
                  </h4>
                  <p className="text-[11px] text-slate-500 truncate max-w-[180px] sm:max-w-[220px]">
                    {action.description}
                  </p>
                </div>
              </div>

              <div className="flex h-6 w-6 items-center justify-center rounded-md text-slate-400 transition-colors group-hover:bg-[#3A5FC3]/10 group-hover:text-[#3A5FC3]">
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* ====================================================================== */}
      {/* 7. ACADEMIC GUIDELINES NOTE */}
      {/* ====================================================================== */}
      <section className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
        <div className="flex items-start gap-3">
          <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-blue-50 text-[#3A5FC3]">
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-800 sm:text-sm">
              {t.home.guidelinesTitle}
            </h4>
            <p className="mt-0.5 text-[11px] text-slate-500 leading-relaxed sm:text-xs">
              {t.home.guidelinesContent}
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
