import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Header from "../components/common/Header";
import Sidebar from "../components/common/Sidebar";
import PageLoadingBar from "../components/PageLoadingBar";

export default function AppLayout() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  // Reset scroll position of the content area on every pathname change
  // (useLayoutEffect runs synchronously before paint, so the new route
  // never flashes at the old scroll offset). Deliberately keyed on
  // pathname only — changing just `?tab=`/search params must not
  // reset scroll, since that would jump the user while switching tabs.
  useLayoutEffect(() => {
    mainRef.current?.scrollTo(0, 0);
  }, [location.pathname]);

  // Exposes the current (desktop) sidebar width as a CSS var on <body> so
  // content-area overlays (modal backdrops, loading overlays) rendered via
  // a portal to document.body can size themselves to the content region
  // only — below the header, right of the sidebar — instead of the full
  // viewport, without prop-drilling this state through every page.
  useEffect(() => {
    document.body.style.setProperty("--app-sidebar-w", isSidebarCollapsed ? "5rem" : "16rem");
  }, [isSidebarCollapsed]);

  return (
    <div className="h-screen overflow-x-hidden bg-[#f4f6fb] text-slate-800 antialiased font-['Saira',Arial,sans-serif]">
      {/* Role-aware Sidebar */}
      <Sidebar
        isCollapsed={isSidebarCollapsed}
        isMobileOpen={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div
        className={`flex h-screen min-w-0 min-h-0 flex-1 flex-col transition-all duration-200 ease-out ${
          isSidebarCollapsed ? "md:pl-20" : "md:pl-64"
        }`}
      >
        {/* Top Header */}
        <Header
          onToggleMobileMenu={() => setIsMobileMenuOpen((prev) => !prev)}
          isSidebarCollapsed={isSidebarCollapsed}
          onToggleSidebarCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
        />

        {/* Dynamic Page Content */}
        <main
          ref={mainRef}
          className={`relative flex-1 min-h-0 min-w-0 w-full overflow-y-auto overflow-x-hidden p-3.5 sm:p-5 lg:p-6 ${
            location.pathname === "/normalization/publications" ? "app-main-publications" : ""
          }`}
        >
          <PageLoadingBar isSidebarCollapsed={isSidebarCollapsed} />
          <div key={location.pathname} className="page-fade-in w-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
