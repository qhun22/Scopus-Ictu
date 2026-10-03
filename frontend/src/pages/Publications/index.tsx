import { Card } from "antd";

export default function PublicationsPage() {
  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      <h1 className="text-2xl font-semibold">Publications</h1>
      <Card>
        <p className="text-gray-600">
          M0 skeleton. Canonical publication browser arrives in M1+.
        </p>
      </Card>
    </div>
  );
}