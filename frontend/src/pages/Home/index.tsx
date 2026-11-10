import { safeDisplayName } from "../../utils/displayName";
import React, { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useI18n } from "../../i18n";
import Button, { buttonClass } from "../../components/ui/Button";
import { getMyLecturerPublications } from "../../api/lecturerScopus";
import type { LecturerPublicationsResponse } from "../../types/lecturerScopus";
import PublicationsByYearChart from "../Dashboard/charts/PublicationsByYearChart";

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
  const { t, locale } = useI18n();

  const searchRef = useRef<HTMLInputElement>(null);
  const [searchError, setSearchError] = useState("");

  const role = user?.role?.toUpperCase() || "GUEST";

  // LECTURER-only: the two summary boxes below show this lecturer's own
  // publication data instead of a bare navigation shortcut.
  const [publicationResult, setPublicationResult] = useState<{ owner: string; data: LecturerPublicationsResponse } | null>(null);
  const myPubs = publicationResult?.owner === user?.id ? publicationResult?.data : null;
  const [myPubsLoading, setMyPubsLoading] = useState(true);
  const [myPubsError, setMyPubsError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    setPublicationResult(null);
    setMyPubsError(false);
    if (role !== "LECTURER" || !user?.id) {
      setMyPubsLoading(false);
      return;
    }
    const controller = new AbortController();
    const owner = user.id;
    setMyPubsLoading(true);
    getMyLecturerPublications({ page: 1, page_size: 5 }, { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setPublicationResult({ owner, data }); })
      .catch(() => { if (!controller.signal.aborted) setMyPubsError(true); })
      .finally(() => { if (!controller.signal.aborted) setMyPubsLoading(false); });
    return () => controller.abort();
  }, [role, user?.id, retryKey]);

  const safeName = safeDisplayName(user?.display_name, user?.role, {
    locale: locale === "vi" ? "vi" : "en",
    fallback: user?.email || t.home.welcomeGuest,
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = searchRef.current?.value.trim();
    if (!trimmed) {
      setSearchError(t.home.searchEmptyError);
      searchRef.current?.focus();
      return;
    }
    setSearchError("");
    navigate(`/search?q=${encodeURIComponent(trimmed)}`);
  };

  const handleSearchChange = () => {
    if (searchError) {
      setSearchError("");
    }
  };

  // 1. Role Overview Cards Config
  const getOverviewCards = (): OverviewCard[] => {
    if (!user) {
      return [
        {
          title: t.home.cardPubsTitle, statusLabel: t.home.cardPubsStatus,
          subtext: t.home.cardPubsSubtext, to: "/publications",
          iconBg: "bg-blue-50 border-blue-100", iconColor: "text-brand",
          badgeColor: "bg-white text-brand border-blue-200",
          icon: <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 6v14M3 5c3-1 6-1 9 1 3-2 6-2 9-1v14c-3-1-6-1-9 1-3-2-6-2-9-1V5z" /></svg>,
        },
        {
          title: t.nav.search, statusLabel: t.home.searchBtn,
          subtext: t.home.publicSearchDescription, to: "/search",
          iconBg: "bg-indigo-50 border-indigo-100", iconColor: "text-indigo-600",
          badgeColor: "bg-white text-indigo-700 border-indigo-200",
          icon: <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>,
        },
        {
          title: t.nav.guide, statusLabel: t.common.viewDetails,
          subtext: t.home.publicGuideDescription, to: "/guide",
          iconBg: "bg-emerald-50 border-emerald-100", iconColor: "text-emerald-600",
          badgeColor: "bg-white text-emerald-700 border-emerald-200",
          icon: <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 9a3 3 0 016 1c0 2-3 2-3 4m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
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
          badgeColor: "bg-white text-amber-700 border-amber-200",
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
          badgeColor: "bg-white text-[#3A5FC3] border-blue-200",
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
          badgeColor: "bg-white text-indigo-700 border-indigo-200",
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
        badgeColor: "bg-white text-emerald-700 border-emerald-200",
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
        badgeColor: "bg-white text-[#3A5FC3] border-blue-200",
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
        badgeColor: "bg-white text-indigo-700 border-indigo-200",
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
    if (role === "REVIEWER") return t.home.chartTitleReviewer;
    return t.home.chartTitleLecturer;
  };

  const getRecentTitle = () => {
    if (role === "REVIEWER") return t.home.recentTitleReviewer;
    return t.home.recentTitleLecturer;
  };

  // Role-aware shortcuts replacing the old "chart coming soon" / "recent
  // activity coming soon" placeholders — each links to a real, already
  // built screen instead of faking data that doesn't exist here.
  const chartShortcut =
    role === "REVIEWER"
      ? {
          to: "/reviews",
          sectionSubtitle: t.home.chartShortcutSectionSubtitleReviewer,
          label: t.home.chartShortcutLabelReviewer,
          sublabel: t.home.chartShortcutSublabelReviewer,
        }
      : {
          to: "/my-publications",
          sectionSubtitle: t.home.chartShortcutSectionSubtitleLecturer,
          label: t.home.chartShortcutLabelLecturer,
          sublabel: t.home.chartShortcutSublabelLecturer,
        };

  const recentShortcut =
    role === "REVIEWER"
      ? {
          to: "/review-history",
          sectionSubtitle: t.home.recentShortcutSectionSubtitleReviewer,
          label: t.home.recentShortcutLabelReviewer,
          sublabel: t.home.recentShortcutSublabelReviewer,
        }
      : {
          to: "/profile",
          sectionSubtitle: t.home.recentShortcutSectionSubtitleLecturer,
          label: t.home.recentShortcutLabelLecturer,
          sublabel: t.home.recentShortcutSublabelLecturer,
        };

  // ADMIN's "Trang chủ" IS the Tổng quan/Dashboard page (sidebar links straight
  // to /dashboard) — this shared Home page has nothing left to show an admin,
  // so a stray link or bookmark to /home sends them there instead.
  if (role === "ADMIN") {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="home-page app-page-container min-w-0 space-y-4 text-sm sm:space-y-5">
      {/* ====================================================================== */}
      {/* 1. WELCOME BANNER + QUICK SEARCH — one slim row, split left/right */}
      {/* ====================================================================== */}
      <section className="rounded-card border border-slate-200/80 bg-white p-4 sm:p-5">
        <div className="grid min-w-0 grid-cols-1 items-center gap-5 xl:grid-cols-2 xl:gap-6">
          <div className="min-w-0">
            <h1 className="break-words text-xl font-bold leading-8 text-slate-800 sm:text-2xl">
              {t.home.welcome},{" "}
              <span className="text-[#3A5FC3]">{safeName}</span>
            </h1>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              {t.home.welcomeSubtitle}
            </p>
          </div>

          <form onSubmit={handleSearchSubmit} onKeyDown={(event) => {
            if (event.key === "Enter" && event.nativeEvent.isComposing) event.preventDefault();
          }} className="min-w-0" role="search" aria-label={t.home.quickSearchTitle}>
            <label htmlFor="home-search" className="sr-only">{t.home.quickSearchTitle}</label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative min-w-0 flex-1">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <input
                  ref={searchRef}
                  id="home-search"
                  name="q"
                  type="text"
                  role="searchbox"
                  onChange={handleSearchChange}
                  aria-invalid={Boolean(searchError)}
                  aria-describedby={searchError ? "home-search-error" : undefined}
                  placeholder={t.home.quickSearchPlaceholder}
                  className="h-control w-full min-w-0 rounded-control border border-line bg-white pl-9 pr-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-line focus:outline-none"
                />
              </div>

              <Button type="submit" variant="primary" className="!text-sm">
                {t.home.searchBtn}
              </Button>
            </div>

            {searchError && (
              <p id="home-search-error" className="mt-2 text-sm font-medium text-rose-600" role="alert">{searchError}</p>
            )}
          </form>
        </div>
      </section>

      {/* ====================================================================== */}
      {/* 3. ROLE OVERVIEW */}
      {/* ====================================================================== */}
      <section className="space-y-2.5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-800">
            {user ? t.home.roleOverviewTitle : t.home.publicOverviewTitle}
          </h2>
        </div>

        <div className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {overviewCards.map((card) => (
            <Link
              key={card.to + card.title}
              to={card.to}
              className="group relative flex min-w-0 flex-col justify-between rounded-card border border-slate-200/80 bg-white p-4 transition-colors hover:border-slate-300 hover:bg-slate-50/50 sm:p-5"
            >
              <div>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-card border ${card.iconBg} ${card.iconColor}`}
                  >
                    {card.icon}
                  </div>
                  <span className={`inline-flex h-badge min-w-[120px] items-center justify-center whitespace-nowrap rounded-control border px-2.5 text-sm font-bold leading-none ${card.badgeColor}`}>
                    {card.statusLabel}
                  </span>
                </div>

                <h3 className="mt-3 text-base font-semibold text-slate-800 transition-colors group-hover:text-[#3A5FC3]">
                  {card.title}
                </h3>
                <p className="mt-0.5 text-sm text-slate-500 leading-6">
                  {card.subtext}
                </p>
              </div>

              <div className="mt-3 flex items-center gap-1 text-sm font-semibold text-[#3A5FC3]">
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
      {user && <section className="grid min-w-0 grid-cols-1 items-start gap-4">
        {/* Visual Summary / Small Chart Container */}
        <div className="min-w-0 overflow-hidden rounded-card border border-slate-200/80 bg-white">
          <div className="border-b border-slate-200/80 bg-slate-50/50 px-4 py-3.5 sm:px-5">
            <h3 className="text-base font-semibold text-slate-800">
              {getChartTitle()}
            </h3>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              {chartShortcut.sectionSubtitle}
            </p>
          </div>

          <div className="min-w-0 p-4 sm:p-5">{role === "LECTURER" ? (
            myPubsLoading ? (
              <div role="status" className="my-4 flex min-h-48 items-center justify-center gap-2 text-sm font-medium text-slate-500">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                {t.common.loading}
              </div>
            ) : myPubsError || !myPubs ? (
              <div className="my-4 flex min-h-48 flex-col items-center justify-center gap-4 text-center text-sm text-slate-500" role="alert">
                <p>{t.home.myPubsLoadError}</p>
                <Button variant="secondary" className="!text-sm" onClick={() => setRetryKey((key) => key + 1)}>{t.home.retry}</Button>
              </div>
            ) : myPubs.aggregates.total_publications === 0 ? (
              <Link
                to="/identity"
                className="group my-4 flex min-h-48 flex-col items-center justify-center gap-1.5 rounded-card border border-slate-200/80 bg-[#EBEFF9]/40 p-4 text-center transition-colors hover:bg-[#EBEFF9]/70 hover:border-[#3A5FC3]/30"
              >
                <p className="max-w-xs text-sm text-slate-500">{t.home.myPubsEmpty}</p>
                <span className="mt-1 inline-flex items-center gap-1 text-sm font-semibold text-[#3A5FC3]">
                  {t.home.myPubsEmptyCta}
                  <svg className="h-3 w-3 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                  </svg>
                </span>
              </Link>
            ) : (
              <div className="my-3">
                <PublicationsByYearChart
                  locale={locale === "en" ? "en" : "vi"}
                  fontSize={14}
                  height={280}
                  data={Object.entries(myPubs.aggregates.publication_count_by_year).map(
                    ([year, count]) => ({ year: Number(year), count }),
                  )}
                />
              </div>
            )
          ) : (
            /* Role-aware shortcut to the real statistics/workflow screen */
            <Link
              to={chartShortcut.to}
              className="group relative my-4 flex min-h-48 flex-col items-center justify-center gap-1.5 rounded-card border border-slate-200/80 bg-[#EBEFF9]/40 p-4 text-center transition-colors hover:bg-[#EBEFF9]/70 hover:border-[#3A5FC3]/30"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-white text-[#3A5FC3] border border-[#3A5FC3]/20 transition-transform group-hover:scale-105">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <p className="text-sm font-semibold text-slate-800">
                {chartShortcut.label}
              </p>
              <p className="max-w-xs text-sm text-slate-500">
                {chartShortcut.sublabel}
              </p>
              <span className="mt-1 inline-flex items-center gap-1 text-sm font-semibold text-[#3A5FC3]">
                {t.common.viewDetails}
                <svg className="h-3 w-3 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                </svg>
              </span>
            </Link>
          )}</div>
        </div>

        {/* Recent Information Container */}
        <div className="min-w-0 overflow-hidden rounded-card border border-slate-200/80 bg-white">
          <div className="border-b border-slate-200/80 bg-slate-50/50 px-4 py-3.5 sm:px-5">
            <h3 className="text-base font-semibold text-slate-800">
              {getRecentTitle()}
            </h3>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              {role === "LECTURER" ? t.home.recentPubsSubtitle : recentShortcut.sectionSubtitle}
            </p>
          </div>

          <div className="min-w-0 p-4 sm:p-5">{role === "LECTURER" ? (
            myPubsLoading ? (
              <div role="status" className="my-4 flex min-h-48 items-center justify-center gap-2 text-sm font-medium text-slate-500">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                {t.common.loading}
              </div>
            ) : myPubsError || !myPubs ? (
              <div className="my-4 flex min-h-48 flex-col items-center justify-center gap-4 text-center text-sm text-slate-500" role="alert">
                <p>{t.home.myPubsLoadError}</p>
                <Button variant="secondary" className="!text-sm" onClick={() => setRetryKey((key) => key + 1)}>{t.home.retry}</Button>
              </div>
            ) : myPubs.items.length === 0 ? (
              <div className="my-4 flex min-h-48 items-center justify-center text-center text-sm leading-6 text-slate-500">
                {t.home.myPubsEmpty}
              </div>
            ) : (
              <div className="my-3 space-y-1.5">
                <ul className="divide-y divide-slate-100 overflow-hidden rounded-control border border-slate-200/80">
                  {myPubs.items.slice(0, 4).map((pub) => (
                    <li key={pub.publication_id}>
                      <Link to={`/publications/${encodeURIComponent(pub.eid)}`} state={{ from: "/home" }} className="block min-w-0 px-3 py-3 hover:bg-slate-50">
                        <p className="line-clamp-2 break-words text-sm font-semibold leading-6 text-slate-800" title={pub.title}>{pub.title}</p>
                        <p className="mt-1 break-words text-sm leading-5 text-slate-500">
                          {[pub.year, pub.source_title].filter((value) => value != null && value !== "").join(" · ") || "—"}
                        </p>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )
          ) : (
            /* Role-aware shortcut to the real history/profile screen */
            <Link
              to={recentShortcut.to}
              className="group my-4 flex min-h-48 flex-col items-center justify-center gap-1.5 rounded-card border border-slate-200/80 bg-[#EBEFF9]/40 p-4 text-center transition-colors hover:bg-[#EBEFF9]/70 hover:border-[#3A5FC3]/30"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-white text-[#3A5FC3] border border-[#3A5FC3]/20 transition-transform group-hover:scale-105">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <p className="text-sm font-semibold text-slate-800">
                {recentShortcut.label}
              </p>
              <p className="max-w-xs text-sm text-slate-500">
                {recentShortcut.sublabel}
              </p>
              <span className="mt-1 inline-flex items-center gap-1 text-sm font-semibold text-[#3A5FC3]">
                {t.common.viewDetails}
                <svg className="h-3 w-3 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                </svg>
              </span>
            </Link>
          )}</div>
        </div>
      </section>}

      {/* ====================================================================== */}
      {/* 6. QUICK ACTIONS — REVIEWER only. Dropped for LECTURER: identical */}
      {/* destinations to the "Tổng quan trạng thái" cards above (pure */}
      {/* duplication). ADMIN never reaches this component (redirected to */}
      {/* /dashboard above). */}
      {/* ====================================================================== */}
      {role === "REVIEWER" && (
        <section className="space-y-2.5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-800">
                {t.home.quickActionsTitle}
              </h2>
              <p className="text-sm text-slate-500">
                {t.home.quickActionsSubtitle}
              </p>
            </div>
          </div>

          <div className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {quickActions.map((action) => (
              <Link
                key={action.to}
                to={action.to}
                className="group flex min-w-0 items-center justify-between gap-3 rounded-card border border-slate-200/80 bg-white p-4 transition-colors hover:border-slate-300 hover:bg-slate-50/60"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-card ${action.iconBg}`}>
                    {action.icon}
                  </div>
                  <div className="min-w-0">
                    <h4 className="text-sm font-semibold text-slate-800 group-hover:text-[#3A5FC3]">
                      {action.title}
                    </h4>
                    <p className="text-sm leading-6 text-slate-500">
                      {action.description}
                    </p>
                  </div>
                </div>

                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-control text-slate-400 transition-colors group-hover:bg-[#3A5FC3]/10 group-hover:text-[#3A5FC3]">
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ====================================================================== */}
      {/* 7. GUEST SIGN-IN PROMPT */}
      {/* ====================================================================== */}
      {!user && <section className="flex min-w-0 flex-wrap items-center justify-between gap-4 rounded-card border border-slate-200/80 bg-white p-4 sm:p-5">
        <p className="min-w-0 flex-1 text-sm leading-6 text-slate-500">{t.home.signInDescription}</p>
        <Link to="/login" className={`${buttonClass("secondary")} !text-sm`}>{t.home.loginAction}</Link>
      </section>}
    </div>
  );
}
