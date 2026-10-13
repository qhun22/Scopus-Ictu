import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Divider,
  Empty,
  Input,
  Modal,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";

import {
  decideReviewCandidate,
  getReviewCandidate,
  getReviewCandidates,
  getReviewContext,
} from "../../api/reviews";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { useToast } from "../../contexts/ToastContext";
import type {
  AmbiguityFilter,
  ReviewContext,
  CandidateStatus,
  EvidenceCategory,
  ReviewAction,
  ReviewCandidateDetail,
  ReviewNameEvidence,
  ReviewQueueItem,
} from "../../types/review";

const { Paragraph, Text } = Typography;

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

const STATUS_BADGE_CLASS: Record<CandidateStatus, string> = {
  PENDING: "border-amber-300 bg-amber-50 text-amber-700",
  ACCEPTED: "border-emerald-200 bg-emerald-50 text-emerald-700",
  REJECTED: "border-rose-200 bg-rose-50 text-rose-700",
  SUPERSEDED: "border-slate-200 bg-slate-100 text-slate-600",
};

const badgeClassName =
  "inline-flex h-6 items-center justify-center rounded-full border px-2.5 text-[11px] font-bold whitespace-nowrap";

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

function sharedAuthorText(count: number | undefined): string {
  return `Cùng một Scopus Author ID đang được đề xuất cho ${count ?? "nhiều"} giảng viên`;
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

function emptyQueueCopy(context: ReviewContext | null): { title: string; text: string } {
  if (!context) {
    return { title: "Hàng đợi đang trống", text: "Chưa xác định được nguyên nhân. Thử tải lại trang." };
  }
  const n = (v: number) => v.toLocaleString("vi-VN");
  const purpose =
    "Màn hình này duyệt việc đối sánh giảng viên ICTU với tác giả Scopus; đây không phải màn hình phê duyệt chuẩn hóa công bố. ";
  switch (context.state) {
    case "NO_LECTURERS":
      return {
        title: "Chưa có dữ liệu giảng viên ICTU để đối sánh",
        text:
          purpose +
          `Hệ thống đang có ${n(context.publications_total)} công bố và ${n(context.scopus_authors_total)} tác giả Scopus nhưng 0 giảng viên, nên chưa có gì để đối sánh. ` +
          "Công bố và tác giả vẫn tra cứu bình thường ở mục Công bố. Khi đã nhập danh sách giảng viên (JSON) ở trang Nhập dữ liệu, quản trị viên chạy bước sinh ứng viên (hiện là công cụ dòng lệnh) để hàng đợi này có dữ liệu.",
      };
    case "NO_CANDIDATE_RUN":
      return {
        title: "Đã có giảng viên nhưng chưa sinh ứng viên đối sánh",
        text:
          purpose +
          `Hệ thống có ${n(context.lecturers_total)} giảng viên và ${n(context.scopus_authors_total)} tác giả Scopus, nhưng chưa có lượt sinh ứng viên nào hoàn tất. Quản trị viên cần chạy bước sinh ứng viên (công cụ dòng lệnh); giao diện chưa có nút chạy.`,
      };
    case "RUN_WITHOUT_CANDIDATES":
      return {
        title: "Đã sinh ứng viên nhưng không tìm thấy cặp phù hợp",
        text:
          purpose +
          `Đã có ${n(context.completed_generation_runs)} lượt sinh ứng viên hoàn tất nhưng không có cặp giảng viên – tác giả nào đủ bằng chứng tên hoặc công bố.`,
      };
    default: {
      const by = context.candidates_by_status;
      const others = Object.entries(by)
        .filter(([, count]) => count > 0)
        .map(([name, count]) => `${name}: ${n(count)}`)
        .join(" · ");
      return {
        title: "Bộ lọc hiện tại không có kết quả",
        text: `Hệ thống có ứng viên ở các trạng thái khác (${others}). Hãy đổi trạng thái hoặc đặt lại bộ lọc.`,
      };
    }
  }
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
  const [context, setContext] = useState<ReviewContext | null>(null);

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

  // Which precondition of the queue is missing (decides the empty-state text).
  useEffect(() => {
    let cancelled = false;
    getReviewContext()
      .then((value) => {
        if (!cancelled) setContext(value);
      })
      .catch(() => {
        if (!cancelled) setContext(null);
      });
    return () => {
      cancelled = true;
    };
  }, [items.length, total]);

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

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="app-page-container space-y-4 sm:space-y-5">
      {/* ── Page Header ──────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">Duyệt đối sánh</h1>
          <p className="mt-0.5 text-xs text-slate-500 sm:text-sm">
            Kiểm tra bằng chứng trước khi xác nhận hoặc từ chối liên kết giữa giảng viên ICTU và tác giả Scopus.
          </p>
        </div>
        <div className="text-xs text-slate-500 mt-1">
          Tổng số: <span className="font-semibold text-slate-800">{total}</span>
        </div>
      </div>

      {/* ── Filter Bar ──────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
        <div className="flex flex-wrap items-end gap-3">
          {/* Trạng thái */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">Trạng thái</label>
            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value as CandidateStatus); setPage(1); }}
              className="h-8 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
            >
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          {/* Loại bằng chứng */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">Loại bằng chứng</label>
            <select
              value={evidenceFilter}
              onChange={(e) => { setEvidenceFilter(e.target.value as EvidenceFilter); setPage(1); }}
              className="h-8 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
            >
              <option value="all">Tất cả</option>
              <option value="publication-supported">Có công bố hỗ trợ</option>
              <option value="name-only">Chỉ bằng chứng tên</option>
            </select>
          </div>

          {/* Mức độ mơ hồ */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600">Mức độ mơ hồ</label>
            <select
              value={ambiguityFilter}
              onChange={(e) => { setAmbiguityFilter(e.target.value as AmbiguitySelection); setPage(1); }}
              className="h-8 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-800 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
            >
              <option value="all">Tất cả</option>
              <option value="ambiguous">Có nhiều ứng viên</option>
              <option value="unique">Không có ứng viên khác</option>
            </select>
          </div>

          {/* Refresh button */}
          <button
            type="button"
            onClick={() => void loadQueue()}
            disabled={queueLoading}
            className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 shadow-2xs transition-colors hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-60 ml-auto"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Làm mới
          </button>
        </div>
      </div>

      {/* ── Queue Table ─────────────────────────────────────────────────── */}
      <section className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-xs">
        {queueError ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 m-4 p-4 text-xs text-rose-800 flex items-start gap-2.5">
            <svg className="h-5 w-5 shrink-0 text-rose-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="flex flex-col gap-1.5">
              <span className="font-semibold">Không thể tải hàng đợi</span>
              <span>{queueError}</span>
              <button
                type="button"
                onClick={() => void loadQueue()}
                className="self-start rounded-lg border border-rose-300 bg-white px-3 py-1 text-xs font-bold text-rose-700 hover:bg-rose-100 transition-colors cursor-pointer"
              >
                Thử lại
              </button>
            </div>
          </div>
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
                <tr>
                  <th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">Giảng viên ICTU</th>
                  <th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">Tác giả Scopus</th>
                  <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap">Trạng thái</th>
                  <th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">Bằng chứng</th>
                  <th className="px-4 py-3.5 font-semibold text-slate-700 whitespace-nowrap">Ngữ cảnh mơ hồ</th>
                  <th className="px-4 py-3.5 text-center font-semibold text-slate-700 whitespace-nowrap w-28">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {queueLoading ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center gap-2">
                        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                        <span>Đang tải hàng đợi...</span>
                      </div>
                    </td>
                  </tr>
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center justify-center gap-1.5">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100/80 border border-slate-200/80 text-slate-400 mb-1">
                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <span className="text-sm font-bold text-slate-700">{emptyQueueCopy(context).title}</span>
                        <span className="max-w-xl text-xs leading-relaxed text-slate-500" data-testid="review-empty-detail">
                          {emptyQueueCopy(context).text}
                        </span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  items.map((item) => (
                    <tr
                      key={item.candidate_id}
                      className="hover:bg-slate-50/50 transition-colors cursor-default"
                      onDoubleClick={() => openDetail(item.candidate_id)}
                    >
                      <td className="px-4 py-3.5 align-middle whitespace-nowrap">
                        <span className="font-bold text-slate-800">{item.lecturer.full_name}</span>
                      </td>
                      <td className="px-4 py-3.5 align-middle">
                        <div className="font-medium text-slate-900">{item.scopus_author.preferred_name}</div>
                        <div className="mt-0.5 font-mono text-[10px] text-slate-400">{item.scopus_author.scopus_id}</div>
                      </td>
                      <td className="px-4 py-3.5 text-center align-middle whitespace-nowrap">
                        <span className={`${badgeClassName} ${STATUS_BADGE_CLASS[item.candidate_status]}`}>
                          {STATUS_LABELS[item.candidate_status]}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 align-middle">
                        {item.publication_support_count > 0 && item.name_evidence_count === 0 ? (
                          <div>
                            <span
                              className="inline-flex h-5 items-center rounded-full border border-violet-200 bg-violet-50 px-2 text-[10px] font-bold text-violet-700"
                              title="Ứng viên này không khớp tên theo quy tắc chuẩn — được tìm thấy vì công bố Craw của giảng viên trùng DOI/tiêu đề với Scopus Author này ở đúng vị trí tác giả có liên quan tên. Chưa phải xác nhận danh tính."
                            >
                              Chỉ từ Craw (không khớp tên)
                            </span>
                            <div className="mt-1 text-[10px] text-slate-400">{item.publication_support_count} công bố Craw</div>
                          </div>
                        ) : item.publication_support_count > 0 ? (
                          <div>
                            <span className="inline-flex h-5 items-center rounded-full border border-cyan-200 bg-cyan-50 px-2 text-[10px] font-bold text-cyan-700">
                              Có công bố hỗ trợ
                            </span>
                            <div className="mt-1 text-[10px] text-slate-400">
                              {item.publication_support_count} công bố · {item.name_evidence_count} bằng chứng tên
                            </div>
                          </div>
                        ) : (
                          <div>
                            <span className="inline-flex h-5 items-center rounded-full border border-slate-200 bg-slate-100 px-2 text-[10px] font-bold text-slate-600">
                              Chỉ bằng chứng tên
                            </span>
                            <div className="mt-1 text-[10px] text-slate-400">{item.name_evidence_count} bằng chứng tên</div>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3.5 align-middle">
                        <div className="flex flex-col gap-1">
                          <span className={`inline-flex h-5 w-fit items-center rounded-full border px-2 text-[10px] font-bold ${item.is_ambiguous ? "border-amber-300 bg-amber-50 text-amber-700" : "border-slate-200 bg-slate-100 text-slate-600"}`}>
                            {ambiguityText(item.candidate_count_for_lecturer)}
                          </span>
                          {item.is_shared_scopus_author && (
                            <span
                              data-testid="shared-author-tag"
                              title={sharedAuthorText(item.candidate_count_for_scopus_author)}
                              className="inline-flex h-5 w-fit items-center rounded-full border border-rose-200 bg-rose-50 px-2 text-[10px] font-bold text-rose-700"
                            >
                              Dùng chung ({item.candidate_count_for_scopus_author ?? "?"} GV)
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3.5 text-center align-middle whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => openDetail(item.candidate_id)}
                          className="inline-flex h-7 items-center justify-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 text-[11px] font-semibold text-slate-700 shadow-2xs transition-all duration-150 active:scale-[0.97] hover:border-[#3A5FC3] hover:text-[#3A5FC3] cursor-pointer whitespace-nowrap"
                        >
                          <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                          <span>Xem chi tiết</span>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer: record count + page size + pagination */}
        {!queueError && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-2.5 text-[11px] text-slate-500">
            <div className="flex items-center gap-3">
              <span>
                Hiển thị <strong>{items.length}</strong> trong {total} ứng viên
              </span>
              <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
                <span className="text-slate-500">Hiển thị:</span>
                <select
                  value={pageSize}
                  disabled={queueLoading}
                  onChange={(e) => { setPage(1); setPageSize(Number(e.target.value)); }}
                  className="h-6 rounded-md border border-slate-200 bg-white px-1.5 text-[11px] font-semibold text-slate-700 focus:border-[#3A5FC3] focus:outline-none cursor-pointer disabled:opacity-50"
                >
                  <option value={10}>10 / trang</option>
                  <option value={20}>20 / trang</option>
                  <option value={50}>50 / trang</option>
                  <option value={100}>100 / trang</option>
                </select>
              </div>
            </div>
            <nav aria-label="Phân trang" className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || queueLoading}
                className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 transition-all duration-150 active:scale-[0.97] hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
              >
                Trước
              </button>
              <span aria-live="polite" className="min-w-[72px] text-center font-medium text-slate-600">
                Trang <strong>{page}</strong> / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || queueLoading}
                className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-semibold text-slate-700 transition-all duration-150 active:scale-[0.97] hover:border-[#3A5FC3] hover:text-[#3A5FC3] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
              >
                Sau
              </button>
            </nav>
          </div>
        )}
      </section>

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
            ) : detail.publication_evidence.length > 0 ? (
              <Alert
                type="warning"
                showIcon
                message="Ứng viên này KHÔNG khớp tên theo 4 quy tắc chuẩn"
                description="Được đề xuất vì công bố Craw của giảng viên trùng DOI/tiêu đề với công bố Scopus này, ở đúng vị trí tác giả có tương quan tên (xem mục D). Đây chưa phải xác nhận danh tính — hãy tự đối chiếu tên/ngữ cảnh trước khi quyết định."
              />
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
            {detail.ambiguity.is_shared_scopus_author && (
              <Alert
                className="mt-3"
                showIcon
                type="error"
                message={sharedAuthorText(detail.ambiguity.candidate_count_for_scopus_author)}
                description="Nhiều giảng viên cùng được đề xuất một tác giả Scopus. Chỉ bằng chứng tên là chưa đủ; hệ thống chặn xác nhận thứ hai cho cùng Scopus Author ID, và không có quyết định nào được tự động đưa ra."
              />
            )}
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
