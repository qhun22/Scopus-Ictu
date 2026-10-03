import { Card } from "antd";

export default function DashboardPage() {
  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <Card>
        <p className="text-gray-600">
          M0 skeleton. The dashboard will summarize import status, mapping queue depth, and
          audit activity in M1+.
        </p>
      </Card>
    </div>
  );
}