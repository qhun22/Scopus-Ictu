import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ToastProvider } from "./contexts/ToastContext";
import ProtectedRoute from "./components/ProtectedRoute";
import MainLayout from "./layouts/MainLayout";
import LoginPage from "./pages/Login";
import HomePage from "./pages/Home";
import DashboardPage from "./pages/Dashboard";
import LecturersPage from "./pages/Lecturers";
import ImportsPage from "./pages/Imports";
import PublicationsPage from "./pages/Publications";
import ApprovalQueuePage from "./pages/ApprovalQueue";
import AuditLogsPage from "./pages/AuditLogs";
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
    <ToastProvider>
      <AuthProvider>
        <PageLoadingBar />
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Protected Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/home" element={<HomePage />} />

            <Route element={<MainLayout />}>
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="lecturers" element={<LecturersPage />} />
              <Route path="imports" element={<ImportsPage />} />
              <Route path="publications" element={<PublicationsPage />} />
              <Route path="approval-queue" element={<ApprovalQueuePage />} />
              <Route path="audit-logs" element={<AuditLogsPage />} />
            </Route>
          </Route>

          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </AuthProvider>
    </ToastProvider>
  );
}
