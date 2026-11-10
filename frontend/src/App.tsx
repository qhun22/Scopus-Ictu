import { Link, Navigate, Route, Routes, useMatch } from "react-router-dom";
import { Bot } from "lucide-react";

import { AuthProvider } from "./contexts/AuthContext";
import { NotificationProvider } from "./contexts/NotificationContext";
import { FeedbackUnreadProvider } from "./contexts/FeedbackUnreadContext";
import { ToastProvider } from "./contexts/ToastContext";
import { PageVisitProvider } from "./contexts/PageVisitContext";
import { I18nProvider } from "./i18n";
import ProtectedRoute from "./components/ProtectedRoute";
import RoleRoute from "./components/auth/RoleRoute";
import AppLayout from "./layouts/AppLayout";
import LoginPage from "./pages/Login";
import HomePage from "./pages/Home";
import DashboardPage from "./pages/Dashboard";
import LecturersPage from "./pages/Lecturers";
import ImportsPage from "./pages/Imports";
import NormalizationPage from "./pages/Normalization";
import PublicationsPage from "./pages/Publications";
import PublicationDetailPage from "./pages/Publications/Detail";
import ApprovalQueuePage from "./pages/ApprovalQueue";
import AuditLogsPage from "./pages/AuditLogs";
import ReviewHistoryPage from "./pages/ReviewHistory";
import ProfilePage from "./pages/Profile";
import IdentityPage from "./pages/Identity";
import MyPublicationsPage from "./pages/MyPublications";
import SearchPage from "./pages/Search";
import UsersPage from "./pages/Users";
import GuidePage from "./pages/Guide";
import ReportIssuePage from "./pages/ReportIssue";
import FeedbackReportsPage from "./pages/FeedbackReports";
import NotFoundPage from "./pages/NotFound";

export default function App() {
  const isLoginPage = useMatch("/login");

  return (
    <I18nProvider>
      <ToastProvider>
        <AuthProvider>
          <NotificationProvider>
          <FeedbackUnreadProvider>
            <PageVisitProvider>
            <>
            <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route element={<AppLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/home" element={<HomePage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/publications" element={<PublicationsPage />} />
            <Route path="/publications/:eid" element={<PublicationDetailPage />} />
            <Route path="/guide" element={<GuidePage />} />
          </Route>

          {/* Authenticated Application Shell */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              {/* Any logged-in role */}
              <Route path="/report-issue" element={<ReportIssuePage />} />

              {/* Lecturer Routes */}
              <Route element={<RoleRoute allowedRoles={["LECTURER"]} />}>
                <Route
                  path="/profile"
                  element={<ProfilePage />}
                />
                <Route
                  path="/my-publications"
                  element={<MyPublicationsPage />}
                />
                <Route
                  path="/identity"
                  element={<IdentityPage />}
                />
              </Route>

              {/* Reviewer Routes */}
              <Route element={<RoleRoute allowedRoles={["REVIEWER", "ADMIN"]} />}>
                <Route path="/reviews" element={<ApprovalQueuePage />} />
                <Route path="/approval-queue" element={<ApprovalQueuePage />} />
                <Route
                  path="/review-history"
                  element={<ReviewHistoryPage />}
                />
                <Route path="/feedback-reports" element={<FeedbackReportsPage />} />
              </Route>

              {/* Admin Routes */}
              <Route element={<RoleRoute allowedRoles={["ADMIN"]} />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/imports" element={<ImportsPage />} />
                <Route path="/normalization" element={<Navigate to="/normalization/publications" replace />} />
                <Route path="/normalization/:tab" element={<NormalizationPage />} />
                <Route path="/lecturers" element={<LecturersPage />} />
                <Route path="/users" element={<UsersPage />} />
                <Route path="/audit-logs" element={<AuditLogsPage />} />
                {/* Trang tác vụ chưa phát triển: ẩn khỏi menu, link cũ chuyển về Dashboard. */}
                <Route path="/tasks" element={<Navigate to="/dashboard" replace />} />
              </Route>
            </Route>
          </Route>

          {/* Catch-all route: any unmatched path (logged in or not) gets a
              proper 404 page instead of a silent redirect. */}
          <Route element={<AppLayout />}>
            <Route path="*" element={<NotFoundPage />} />
          </Route>
            </Routes>
            {!isLoginPage && <Link
              to="/report-issue"
              className="fixed bottom-6 right-6 z-50 flex h-11 w-11 items-center justify-center rounded-full bg-[#3A5FC3] text-white shadow-lg transition-transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/40 focus:ring-offset-2"
              aria-label="Báo lỗi / hỗ trợ"
              title="Báo lỗi / hỗ trợ"
            >
              <Bot className="h-5 w-5" strokeWidth={1.8} />
            </Link>}
            </>
            </PageVisitProvider>
          </FeedbackUnreadProvider>
          </NotificationProvider>
        </AuthProvider>
      </ToastProvider>
    </I18nProvider>
  );
}
