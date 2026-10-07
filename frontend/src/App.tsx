import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { NotificationProvider } from "./contexts/NotificationContext";
import { ToastProvider } from "./contexts/ToastContext";
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
import ProfilePage from "./pages/Profile";
import IdentityPage from "./pages/Identity";
import MyPublicationsPage from "./pages/MyPublications";
import SearchPage from "./pages/Search";
import PlaceholderPage from "./components/common/PlaceholderPage";
import PageLoadingBar from "./components/PageLoadingBar";

function RootRedirect() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-[#3A5FC3]" />
      </div>
    );
  }
  return <Navigate to={isAuthenticated ? "/home" : "/login"} replace />;
}

export default function App() {
  return (
    <I18nProvider>
      <ToastProvider>
        <AuthProvider>
          <NotificationProvider>
            <PageLoadingBar />
            <Routes>
          {/* Public Routes */}
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Authenticated Application Shell */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              {/* Universal landing route */}
              <Route path="/home" element={<HomePage />} />

              {/* Admin + Reviewer Routes */}
              <Route element={<RoleRoute allowedRoles={["ADMIN", "REVIEWER"]} />}>
                <Route path="/search" element={<SearchPage />} />
                <Route path="/publications" element={<PublicationsPage />} />
                <Route path="/publications/:eid" element={<PublicationDetailPage />} />
              </Route>

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
                  element={<PlaceholderPage title="Lịch sử review" icon="history" />}
                />
              </Route>

              {/* Admin Routes */}
              <Route element={<RoleRoute allowedRoles={["ADMIN"]} />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/imports" element={<ImportsPage />} />
                <Route path="/normalization" element={<NormalizationPage />} />
                <Route path="/lecturers" element={<LecturersPage />} />
                <Route path="/users" element={<Navigate to="/lecturers" replace />} />
                <Route path="/audit-logs" element={<AuditLogsPage />} />
                <Route
                  path="/tasks"
                  element={<PlaceholderPage title="Tác vụ hệ thống" icon="tasks" />}
                />
              </Route>
            </Route>
          </Route>

          {/* Catch-all route */}
          <Route path="*" element={<RootRedirect />} />
            </Routes>
          </NotificationProvider>
        </AuthProvider>
      </ToastProvider>
    </I18nProvider>
  );
}
