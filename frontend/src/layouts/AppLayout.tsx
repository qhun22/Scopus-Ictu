import { useState } from "react";
import { Outlet } from "react-router-dom";
import Header from "../components/common/Header";
import Sidebar from "../components/common/Sidebar";

export default function AppLayout() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#f4f6fb] text-slate-800 antialiased font-['Saira',Arial,sans-serif]">
      {/* Role-aware Sidebar */}
      <Sidebar
        isCollapsed={isSidebarCollapsed}
        isMobileOpen={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div
        className={`flex min-h-screen flex-col transition-all duration-300 ${
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
        <main className="flex-1 min-w-0 max-w-full overflow-y-auto overflow-x-hidden p-4 sm:p-5 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
