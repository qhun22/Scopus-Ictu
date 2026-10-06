import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Divider,
  Empty,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";

import {
  decideReviewCandidate,
  getReviewCandidate,
  getReviewCandidates,
} from "../../api/reviews";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { useToast } from "../../contexts/ToastContext";
import type {
  AmbiguityFilter,
  CandidateStatus,
  EvidenceCategory,
  ReviewAction,
  ReviewCandidateDetail,
  ReviewNameEvidence,
  ReviewQueueItem,
} from "../../types/review";

const { Paragraph, Text, Title } = Typography;

type EvidenceFilter = EvidenceCategory | "all";
type AmbiguitySelection = AmbiguityFilter | "all";

const STATUS_LABELS: Record<CandidateStatus, string> = {
  PENDING: "Chờ duyệt",
  ACCEPTED: "Đã xác nhận",
  REJECTED: "Đã từ chối",
  SUPERSEDED: "Đã thay thế",
};

const STATUS_COLORS: Record<CandidateStatus, string> = {
  PENDING: "gold",
  ACCEPTED: "green",
  REJECTED: "red",
  SUPERSEDED: "default",
};

const CONFLICT_MESSAGES: Readonly<Record<string, string>> = {
  STALE_CANDIDATE_VERSION:
    "Ứng viên đã thay đổi kể từ khi bạn mở chi tiết. Dữ liệu mới nhất đã được tải lại; vui lòng kiểm tra trước khi quyết định lại.",
  STALE_CANDIDATE_OBSERVATION:
    "Bằng chứng của ứng viên đã được cập nhật. Dữ liệu mới nhất đã được tải lại; hệ thống không tự gửi lại quyết định.",
  CANDIDATE_ALREADY_DECIDED_CONFLICT:
    "Ứng viên này đã được một người dùng khác quyết định. Hàng đợi và chi tiết đang được làm mới.",
  SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER:
    "Tác giả Scopus này đã được xác nhận cho một giảng viên khác. Không thể tự động thử lại quyết định.",
  PREEXISTING_IDENTITY_PROVENANCE_CONFLICT:
    "Liên kết định danh hiện có có nguồn gốc bằng chứng xung đột. Vui lòng kiểm tra trước khi tiếp tục.",
};

function ambiguityText(count: number): string {
  if (count <= 1) return "Không có ứng viên khác";
  if (count === 2) return "Còn 1 ứng viên khác";
  return `Có ${count} ứng viên`;
}

function displayValue(value: string | null | undefined): string {
  const normalized = value?.trim();
  return normalized ? normalized : "Chưa có dữ liệu";
}

function provenanceText(ref: unknown): string {
  if (typeof ref !== "object" || ref === null) return String(ref);
  const values = Object.entries(ref as Record<string, unknown>)
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([key, value]) => `${key}: ${String(value)}`);
  return values.length > 0 ? values.join(" · ") : "Nguồn không có mô tả";
}

function NameEvidenceCard({ evidence }: { evidence: ReviewNameEvidence }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Tag color="blue">{evidence.rule_id}</Tag>
        <Text type="secondary">Phiên bản quy tắc {evidence.rule_version}</Text>
      </div>
      <Paragraph className="!mb-3 !mt-2 !text-slate-600">
        Quy tắc trên so sánh tên từ hồ sơ giảng viên với tên hiển thị hoặc biến thể tên
        do Scopus cung cấp.
      </Paragraph>
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <Text type="secondary">Tên từ hồ sơ ICTU</Text>
          <div className="font-medium text-slate-900">
            {displayValue(evidence.lecturer_source_value)}
          </div>
          {evidence.lecturer_comparison_value && (
            <div className="mt-1 text-xs text-slate-500">
              Giá trị so sánh: {evidence.lecturer_comparison_value}
            </div>
          )}
        </div>
        <div>
          <Text type="secondary">Tên từ Scopus</Text>
          <div className="font-medium text-slate-900">
            {displayValue(evidence.scopus_surface_value)}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {evidence.scopus_surface_type && `Loại: ${evidence.scopus_surface_type}`}
            {evidence.scopus_comparison_value &&
              `${evidence.scopus_surface_type ? " · " : ""}Giá trị so sánh: ${evidence.scopus_comparison_value}`}
          </div>
        </div>
      </div>
      {evidence.source_refs.length > 0 && (
        <div className="mt-3 border-t border-slate-200 pt-3 text-xs text-slate-500">
          <span className="font-semibold text-slate-600">Nguồn: </span>
          {evidence.source_refs.map((ref, index) => (
            <span key={`${evidence.evidence_id}-source-${index}`}>
              {index > 0 && " | "}
              {provenanceText(ref)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ApprovalQueuePage() {
  const toast = useToast();
  const [status, setStatus] = useState<CandidateStatus>("PENDING");
  const [evidenceFilter, setEvidenceFilter] = useState<EvidenceFilter>("all");
  const [ambiguityFilter, setAmbiguityFilter] = useState<AmbiguitySelection>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState<string | null>(null);

  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ReviewCandidateDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [conflictMessage, setConflictMessage] = useState<string | null>(null);

  const [decisionAction, setDecisionAction] = useState<ReviewAction | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [decisionSubmitting, setDecisionSubmitting] = useState(false);

  const loadQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError(null);
    try {
      const response = await getReviewCandidates({
        status,
        evidence_category: evidenceFilter === "all" ? undefined : evidenceFilter,
        ambiguity: ambiguityFilter === "all" ? undefined : ambiguityFilter,
        page,
        page_size: pageSize,
      });
      setItems(response.items);
      setTotal(response.total);
    } catch (error) {
      setQueueError(getApiErrorMessage(error, "Không thể tải hàng đợi duyệt đối sánh."));
      setItems([]);
      setTotal(0);
    } finally {
      setQueueLoading(false);
    }
  }, [ambiguityFilter, evidenceFilter, page, pageSize, status]);

  const loadDetail = useCallback(async (candidateId: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const response = await getReviewCandidate(candidateId);
      setDetail(response);
    } catch (error) {
      setDetail(null);
      setDetailError(getApiErrorMessage(error, "Không thể tải chi tiết ứng viên đối sánh."));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (!selectedCandidateId) return;
    void loadDetail(selectedCandidateId);
  }, [loadDetail, selectedCandidateId]);

  const openDetail = (candidateId: string) => {
    setConflictMessage(null);
    setDetail(null);
    setSelectedCandidateId(candidateId);
  };

  const closeDetail = () => {
    if (decisionSubmitting) return;
    setSelectedCandidateId(null);
    setDetail(null);
    setDetailError(null);
    setConflictMessage(null);
  };

  const closeDecision = () => {
    if (decisionSubmitting) return;
    setDecisionAction(null);
    setRejectReason("");
    setReasonError(null);
  };

  const refreshQueueAndDetail = useCallback(async () => {
    const requests: Promise<unknown>[] = [loadQueue()];
    if (selectedCandidateId) requests.push(loadDetail(selectedCandidateId));
    await Promise.allSettled(requests);
  }, [loadDetail, loadQueue, selectedCandidateId]);

  const handleConflict = async (error: ApiError) => {
    const code = error.code ?? "";
    const message =
      CONFLICT_MESSAGES[code] ??
      "Dữ liệu hiện tại xung đột với quyết định. Vui lòng tải lại và kiểm tra trước khi thử lại.";
    setConflictMessage(message);
    toast.warning("Không thể lưu quyết định", message);

    if (code === "STALE_CANDIDATE_VERSION" || code === "STALE_CANDIDATE_OBSERVATION") {
      if (selectedCandidateId) await loadDetail(selectedCandidateId);
      return;
    }
    if (code === "CANDIDATE_ALREADY_DECIDED_CONFLICT") {
      await refreshQueueAndDetail();
    }
  };

  const submitDecision = async () => {
    if (!detail || !decisionAction) return;

    const trimmedReason = rejectReason.trim();
    if (decisionAction === "REJECT" && !trimmedReason) {
      setReasonError("Vui lòng nhập lý do từ chối.");
      return;
    }

    setDecisionSubmitting(true);
    setReasonError(null);
    setConflictMessage(null);
    try {
      if (decisionAction === "ACCEPT") {
        await decideReviewCandidate(detail.candidate_id, {
          observation_id: detail.current_observation.observation_id,
          candidate_version: detail.candidate_version,
          action: "ACCEPT",
        });
        toast.success("Thành công", "Đã xác nhận đối sánh.");
      } else {
        await decideReviewCandidate(detail.candidate_id, {
          observation_id: detail.current_observation.observation_id,
          candidate_version: detail.candidate_version,
          action: "REJECT",
          reason: trimmedReason,
        });
        toast.success("Thành công", "Đã từ chối ứng viên đối sánh.");
      }
      setDecisionAction(null);
      setRejectReason("");
      await refreshQueueAndDetail();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setDecisionAction(null);
        await handleConflict(error);
      } else {
        const message = getApiErrorMessage(error, "Không thể lưu quyết định duyệt.");
        toast.error("Lưu quyết định thất bại", message);
      }
    } finally {
      setDecisionSubmitting(false);
    }
  };

  const columns: ColumnsType<ReviewQueueItem> = useMemo(
    () => [
      {
        title: "Giảng viên ICTU",
        key: "lecturer",
        render: (_, item) => <Text strong>{item.lecturer.full_name}</Text>,
      },
      {
        title: "Tác giả Scopus",
        key: "author",
        render: (_, item) => (
          <div>
            <div className="font-medium text-slate-900">{item.scopus_author.preferred_name}</div>
            <div className="mt-1 font-mono text-xs text-slate-500">{item.scopus_author.scopus_id}</div>
          </div>
        ),
      },
      {
        title: "Trạng thái",
        dataIndex: "candidate_status",
        key: "status",
        render: (value: CandidateStatus) => <Tag color={STATUS_COLORS[value]}>{STATUS_LABELS[value]}</Tag>,
      },
      {
        title: "Bằng chứng",
        key: "evidence",
        render: (_, item) =>
          item.publication_support_count > 0 ? (
            <div>
              <Tag color="cyan">Có công bố hỗ trợ</Tag>
              <div className="mt-1 text-xs text-slate-500">
                {item.publication_support_count} công bố · {item.name_evidence_count} bằng chứng tên
              </div>
            </div>
          ) : (
            <div>
              <Tag>Chỉ bằng chứng tên</Tag>
              <div className="mt-1 text-xs text-slate-500">{item.name_evidence_count} bằng chứng tên</div>
            </div>
          ),
      },
      {
        title: "Ngữ cảnh mơ hồ",
        key: "ambiguity",
        render: (_, item) => (
          <Tag color={item.is_ambiguous ? "orange" : "default"}>
            {ambiguityText(item.candidate_count_for_lecturer)}
          </Tag>
        ),
      },
      {
        title: "Thao tác",
        key: "actions",
        fixed: "right",
        width: 110,
        render: (_, item) => (
          <Button type="link" onClick={() => openDetail(item.candidate_id)}>
            Xem chi tiết
          </Button>
        ),
      },
    ],
    [],
  );

  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      <div>
        <Title level={2} className="!mb-1 !text-slate-900">Duyệt đối sánh</Title>
        <Paragraph className="!mb-0 !text-slate-500">
          Kiểm tra bằng chứng trước khi xác nhận hoặc từ chối liên kết giữa giảng viên ICTU và tác giả Scopus.
        </Paragraph>
      </div>

      <Card>
        <div className="mb-5 flex flex-wrap items-end gap-3">
          <label className="min-w-44">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Trạng thái</span>
            <Select<CandidateStatus>
              className="w-full"
              value={status}
              options={Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }))}
              onChange={(value) => { setStatus(value); setPage(1); }}
            />
          </label>
          <label className="min-w-52">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Loại bằng chứng</span>
            <Select<EvidenceFilter>
              className="w-full"
              value={evidenceFilter}
              options={[
                { value: "all", label: "Tất cả" },
                { value: "publication-supported", label: "Có công bố hỗ trợ" },
                { value: "name-only", label: "Chỉ bằng chứng tên" },
              ]}
              onChange={(value) => { setEvidenceFilter(value); setPage(1); }}
            />
          </label>
          <label className="min-w-48">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Mức độ mơ hồ</span>
            <Select<AmbiguitySelection>
              className="w-full"
              value={ambiguityFilter}
              options={[
                { value: "all", label: "Tất cả" },
                { value: "ambiguous", label: "Có nhiều ứng viên" },
                { value: "unique", label: "Không có ứng viên khác" },
              ]}
              onChange={(value) => { setAmbiguityFilter(value); setPage(1); }}
            />
          </label>
          <Button onClick={() => void loadQueue()} loading={queueLoading}>Làm mới</Button>
          <div className="ml-auto text-sm text-slate-500">
            Tổng số: <span className="font-semibold text-slate-800">{total}</span>
          </div>
        </div>

        {queueError ? (
          <Alert
            showIcon
            type="error"
            message="Không thể tải hàng đợi"
            description={
              <Space direction="vertical">
                <span>{queueError}</span>
                <Button size="small" onClick={() => void loadQueue()}>Thử lại</Button>
              </Space>
            }
          />
        ) : (
          <Table<ReviewQueueItem>
            rowKey="candidate_id"
            columns={columns}
            dataSource={items}
            loading={queueLoading}
            scroll={{ x: 980 }}
            locale={{
              emptyText: queueLoading ? <div className="py-10">Đang tải hàng đợi...</div> : <Empty description="Không có ứng viên phù hợp với bộ lọc." />,
            }}
            pagination={{
              current: page,
              pageSize,
              total,
              showSizeChanger: true,
              pageSizeOptions: [10, 20, 50, 100],
              showTotal: (value) => `${value} ứng viên`,
              onChange: (nextPage, nextPageSize) => {
                setPage(nextPageSize !== pageSize ? 1 : nextPage);
                setPageSize(nextPageSize);
              },
            }}
            onRow={(item) => ({ onDoubleClick: () => openDetail(item.candidate_id) })}
          />
        )}
      </Card>

      <Modal
        open={selectedCandidateId !== null}
        title="Chi tiết ứng viên đối sánh"
        width={1040}
        footer={null}
        destroyOnClose
        maskClosable={!decisionSubmitting}
        closable={!decisionSubmitting}
        onCancel={closeDetail}
      >
        {detailLoading ? (
          <div className="flex min-h-72 flex-col items-center justify-center gap-3">
            <Spin size="large" />
            <Text type="secondary">Đang tải bằng chứng...</Text>
          </div>
        ) : detailError ? (
          <Alert
            showIcon
            type="error"
            message="Không thể tải chi tiết"
            description={
              <Space direction="vertical">
                <span>{detailError}</span>
                <Button size="small" onClick={() => selectedCandidateId && void loadDetail(selectedCandidateId)}>Thử lại</Button>
              </Space>
            }
          />
        ) : detail ? (
          <div className="max-h-[72vh] overflow-y-auto pr-1">
            {conflictMessage && (
              <Alert className="mb-4" showIcon closable type="warning" message="Dữ liệu có xung đột" description={conflictMessage} onClose={() => setConflictMessage(null)} />
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              <Card size="small" title="A. Giảng viên ICTU">
                <Descriptions size="small" column={1} colon={false}>
                  <Descriptions.Item label="Họ tên"><Text strong>{detail.lecturer.full_name}</Text></Descriptions.Item>
                  <Descriptions.Item label="Học vị">{displayValue(detail.lecturer.academic_degree)}</Descriptions.Item>
                  <Descriptions.Item label="Chức danh">{displayValue(detail.lecturer.academic_rank)}</Descriptions.Item>
                  <Descriptions.Item label="Hồ sơ nguồn">
                    {detail.lecturer.repository_profile_url ? (
                      <a href={detail.lecturer.repository_profile_url} target="_blank" rel="noreferrer">Mở hồ sơ ICTU</a>
                    ) : "Chưa có dữ liệu"}
                  </Descriptions.Item>
                </Descriptions>
              </Card>

              <Card size="small" title="B. Tác giả Scopus">
                <Descriptions size="small" column={1} colon={false}>
                  <Descriptions.Item label="Tên ưu tiên"><Text strong>{detail.scopus_author.preferred_name}</Text></Descriptions.Item>
                  <Descriptions.Item label="Scopus ID"><Text code>{detail.scopus_author.scopus_id}</Text></Descriptions.Item>
                  <Descriptions.Item label="Biến thể tên">
                    {detail.scopus_author.name_variants.length > 0 ? (
                      <Space wrap>{detail.scopus_author.name_variants.map((variant) => <Tag key={variant}>{variant}</Tag>)}</Space>
                    ) : "Chưa có biến thể tên"}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </div>

            <Divider orientation="left">C. Bằng chứng tên</Divider>
            {detail.name_evidence.length > 0 ? (
              <div className="space-y-3">{detail.name_evidence.map((evidence) => <NameEvidenceCard key={evidence.evidence_id} evidence={evidence} />)}</div>
            ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Không có bằng chứng tên." />}

            <Divider orientation="left">D. Bằng chứng công bố</Divider>
            {detail.publication_evidence.length > 0 ? (
              <div className="space-y-3">
                {detail.publication_evidence.map((evidence) => (
                  <div key={evidence.evidence_id} className="rounded-xl border border-slate-200 p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <Tag color={evidence.reconciliation === "DOI_EXACT" ? "green" : "blue"}>{evidence.reconciliation ?? "Chưa xác định kiểu đối chiếu"}</Tag>
                      <Text type="secondary">{evidence.rule_id} · phiên bản {evidence.rule_version}</Text>
                    </div>
                    <div className="text-base font-semibold text-slate-900">{displayValue(evidence.title)}</div>
                    <div className="mt-2 grid gap-2 text-sm md:grid-cols-2">
                      <div><span className="font-semibold text-slate-600">DOI: </span>{displayValue(evidence.doi)}</div>
                      <div><span className="font-semibold text-slate-600">EID: </span>{displayValue(evidence.eid)}</div>
                    </div>
                    {evidence.source_refs.length > 0 && (
                      <div className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
                        <span className="font-semibold text-slate-600">Nguồn: </span>
                        {evidence.source_refs.map((ref, index) => (
                          <span key={`${evidence.evidence_id}-source-${index}`}>{index > 0 && " | "}{provenanceText(ref)}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Ứng viên này không có bằng chứng công bố." />}

            <Divider orientation="left">E. Ngữ cảnh mơ hồ</Divider>
            <Alert
              showIcon
              type={detail.ambiguity.is_ambiguous ? "warning" : "info"}
              message={ambiguityText(detail.ambiguity.candidate_count_for_lecturer)}
              description={detail.ambiguity.other_candidates.length > 0 ? "Các ứng viên khác của cùng giảng viên được liệt kê theo thứ tự API cung cấp." : "Không có ứng viên Scopus nào khác được ghi nhận cho giảng viên này."}
            />
            {detail.ambiguity.other_candidates.length > 0 && (
              <div className="mt-3 space-y-2">
                {detail.ambiguity.other_candidates.map((candidate) => (
                  <div key={candidate.candidate_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 px-4 py-3">
                    <div>
                      <div className="font-medium text-slate-900">{candidate.scopus_author.preferred_name}</div>
                      <div className="font-mono text-xs text-slate-500">{candidate.scopus_author.scopus_id}</div>
                    </div>
                    <Tag color={STATUS_COLORS[candidate.candidate_status]}>{STATUS_LABELS[candidate.candidate_status]}</Tag>
                  </div>
                ))}
              </div>
            )}

            <Divider />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm text-slate-500">
                Trạng thái hiện tại: <Tag color={STATUS_COLORS[detail.candidate_status]}>{STATUS_LABELS[detail.candidate_status]}</Tag>
              </div>
              {detail.candidate_status === "PENDING" && (
                <Space wrap>
                  <Button danger onClick={() => setDecisionAction("REJECT")}>Từ chối</Button>
                  <Button type="primary" onClick={() => setDecisionAction("ACCEPT")}>Xác nhận đối sánh</Button>
                </Space>
              )}
            </div>
          </div>
        ) : <Empty description="Không có dữ liệu chi tiết." />}
      </Modal>

      <Modal
        open={decisionAction === "ACCEPT" && detail !== null}
        title="Xác nhận quyết định ACCEPT"
        okText="Xác nhận ACCEPT"
        cancelText="Hủy"
        confirmLoading={decisionSubmitting}
        closable={!decisionSubmitting}
        maskClosable={!decisionSubmitting}
        onOk={() => void submitDecision()}
        onCancel={closeDecision}
      >
        {detail && (
          <div className="space-y-3">
            <Alert showIcon type="info" message="Vui lòng kiểm tra đúng cặp đối sánh trước khi xác nhận." />
            <Descriptions size="small" column={1} colon={false}>
              <Descriptions.Item label="Giảng viên"><Text strong>{detail.lecturer.full_name}</Text></Descriptions.Item>
              <Descriptions.Item label="Tác giả Scopus">{detail.scopus_author.preferred_name}</Descriptions.Item>
              <Descriptions.Item label="Scopus ID"><Text code>{detail.scopus_author.scopus_id}</Text></Descriptions.Item>
              <Descriptions.Item label="Hành động"><Tag color="green">ACCEPT</Tag></Descriptions.Item>
            </Descriptions>
          </div>
        )}
      </Modal>

      <Modal
        open={decisionAction === "REJECT" && detail !== null}
        title="Từ chối ứng viên đối sánh"
        okText="Xác nhận REJECT"
        okButtonProps={{ danger: true, disabled: rejectReason.trim().length === 0 }}
        cancelText="Hủy"
        confirmLoading={decisionSubmitting}
        closable={!decisionSubmitting}
        maskClosable={!decisionSubmitting}
        onOk={() => void submitDecision()}
        onCancel={closeDecision}
      >
        {detail && (
          <div className="space-y-4">
            <Descriptions size="small" column={1} colon={false}>
              <Descriptions.Item label="Giảng viên"><Text strong>{detail.lecturer.full_name}</Text></Descriptions.Item>
              <Descriptions.Item label="Tác giả Scopus">{detail.scopus_author.preferred_name} ({detail.scopus_author.scopus_id})</Descriptions.Item>
              <Descriptions.Item label="Hành động"><Tag color="red">REJECT</Tag></Descriptions.Item>
            </Descriptions>
            <div>
              <label htmlFor="review-reject-reason" className="mb-1.5 block font-semibold text-slate-700">
                Lý do từ chối <span className="text-rose-600">*</span>
              </label>
              <Input.TextArea
                id="review-reject-reason"
                value={rejectReason}
                rows={4}
                maxLength={4000}
                showCount
                status={reasonError ? "error" : undefined}
                placeholder="Nhập lý do để lưu cùng quyết định duyệt..."
                onChange={(event) => {
                  setRejectReason(event.target.value);
                  if (event.target.value.trim()) setReasonError(null);
                }}
              />
              {reasonError && <div className="mt-1 text-sm text-rose-600">{reasonError}</div>}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
