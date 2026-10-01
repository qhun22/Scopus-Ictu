import { Route, Routes } from "react-router-dom";

import MainLayout from "./layouts/MainLayout";
import DashboardPage from "./pages/Dashboard";
import LecturersPage from "./pages/Lecturers";
import ImportsPage from "./pages/Imports";
import PublicationsPage from "./pages/Publications";
import ApprovalQueuePage from "./pages/ApprovalQueue";
import AuditLogsPage from "./pages/AuditLogs";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="lecturers" element={<LecturersPage />} />
        <Route path="imports" element={<ImportsPage />} />
        <Route path="publications" element={<PublicationsPage />} />
        <Route path="approval-queue" element={<ApprovalQueuePage />} />
        <Route path="audit-logs" element={<AuditLogsPage />} />
      </Route>
    </Routes>
  );
}