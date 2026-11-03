import { Route, Routes } from "react-router-dom";

import { AuthProvider } from "./contexts/AuthContext";
import { NotificationProvider } from "./contexts/NotificationContext";
import { ToastProvider } from "./contexts/ToastContext";
import { PageVisitProvider } from "./contexts/PageVisitContext";
import { I18nProvider, useI18n } from "./i18n";
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
import PlaceholderPage from "./components/common/PlaceholderPage";

function TasksPlaceholderPage() {
  const { locale } = useI18n();
  return (
    <PlaceholderPage
      title={locale === "vi" ? "Tác vụ hệ thống" : "System tasks"}
      description={
        locale === "vi"
          ? "Chức năng đang phát triển. Trang này dành riêng cho quản lý tác vụ nền trong các phiên bản tương lai — chưa có bộ lập lịch hay công cụ thực thi nào được triển khai."
          : "This feature is under development. This page is reserved for managing background tasks in a future release — no scheduler or execution tooling has been implemented yet."
      }
      icon="tasks"
    />
  );
}

function NotFoundPage() {
  const { locale } = useI18n();
  return (
    <PlaceholderPage
      title={locale === "vi" ? "404 - Không tìm thấy trang" : "404 - Page not found"}
      description={
        locale === "vi"
          ? "Đường dẫn này không tồn tại hoặc đã được thay đổi. Hãy kiểm tra lại địa chỉ, hoặc quay về trang chủ."
          : "This page doesn't exist or has moved. Check the address, or head back to the home page."
      }
      icon="default"
    />
  );
}

export default function App() {
  return (
    <I18nProvider>
      <ToastProvider>
        <AuthProvider>
          <NotificationProvider>
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
          </Route>

          {/* Authenticated Application Shell */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
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
              </Route>

              {/* Admin Routes */}
              <Route element={<RoleRoute allowedRoles={["ADMIN"]} />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/imports" element={<ImportsPage />} />
                <Route path="/normalization" element={<NormalizationPage />} />
                <Route path="/lecturers" element={<LecturersPage />} />
                <Route path="/users" element={<UsersPage />} />
                <Route path="/audit-logs" element={<AuditLogsPage />} />
                <Route path="/tasks" element={<TasksPlaceholderPage />} />
              </Route>
            </Route>
          </Route>

          {/* Catch-all route: any unmatched path (logged in or not) gets a
              proper 404 page instead of a silent redirect. */}
          <Route element={<AppLayout />}>
            <Route path="*" element={<NotFoundPage />} />
          </Route>
            </Routes>
            <button
              type="button"
              className="fixed bottom-6 right-6 z-50 h-10 w-10 overflow-hidden rounded-full focus:outline-none"
              aria-label="Chat bot"
            >
              <img src="/assets/gatchan.png" alt="Gatchan chat bot" className="h-full w-full object-cover" />
            </button>
            </>
            </PageVisitProvider>
          </NotificationProvider>
        </AuthProvider>
      </ToastProvider>
    </I18nProvider>
  );
}
