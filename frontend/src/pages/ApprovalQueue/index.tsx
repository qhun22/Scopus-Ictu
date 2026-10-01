import { Card } from "antd";

import DiffViewerStub from "../../components/diff/DiffViewerStub";

export default function ApprovalQueuePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Approval Queue</h1>
      <Card>
        <p className="mb-4 text-gray-600">
          M0 skeleton. Reviewer workflow, candidate ranking, and diff preview arrive in M1+.
        </p>
        <DiffViewerStub />
      </Card>
    </div>
  );
}