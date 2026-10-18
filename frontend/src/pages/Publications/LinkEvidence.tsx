import { Link } from "react-router-dom";
import Badge, { type BadgeTone } from "../../components/ui/Badge";
import type { LinkEvidenceBasisRead, LinkReviewDecisionRead } from "../../types/publication";

type Locale = "vi" | "en";

// D-3: an approved link is a reviewer decision. It is called "verified" only when the evidence rows contain an
// independent identifier match (evidence_basis.independently_verified), never because a reviewer accepted it.

const LEVEL: Record<LinkEvidenceBasisRead["level"], { tone: BadgeTone; vi: string; en: string }> = {
  IDENTIFIER_SUPPORT: { tone: "success", vi: "Có định danh độc lập", en: "Independent identifier" },
  PUBLICATION_SUPPORT: { tone: "info", vi: "Có công bố hỗ trợ", en: "Publication-supported" },
  NAME_ONLY: { tone: "warning", vi: "Chỉ trùng tên", en: "Name match only" },
  NO_RECORDED_EVIDENCE: { tone: "neutral", vi: "Chưa ghi nhận chứng cứ", en: "No recorded evidence" },
};

const SOURCE: Record<string, { vi: string; en: string }> = {
  ORCID_EXACT: { vi: "Trùng ORCID", en: "Matching ORCID" },
  DOI_EXACT: { vi: "Trùng DOI công bố", en: "Matching publication DOI" },
  PUBLICATION_OVERLAP: { vi: "Trùng công bố (tiêu đề)", en: "Matching publication (title)" },
  COAUTHOR_CONFIRMED: { vi: "Đồng tác giả xác nhận", en: "Confirmed co-author" },
  NAME_SIMILARITY: { vi: "Trùng tên", en: "Name match" },
  AFFILIATION_MATCH: { vi: "Trùng đơn vị (không phải chứng cứ định danh)", en: "Matching affiliation (not identity evidence)" },
  APPROVED_ID: { vi: "Mã định danh khác (chưa phân loại)", en: "Other identifier (unclassified)" },
};

const sourceText = (types: string[], locale: Locale) =>
  types.map((t) => SOURCE[t]?.[locale] ?? (locale === "vi" ? "Loại chứng cứ khác" : "Other evidence type")).join(" · ");

export function LinkStatusBadge({ locale }: { locale: Locale }) {
  return <Badge tone="success">{locale === "vi" ? "Liên kết định danh đã duyệt" : "Approved identity link"}</Badge>;
}

export function EvidenceBasisCell({ basis, locale }: { basis?: LinkEvidenceBasisRead | null; locale: Locale }) {
  if (!basis) return <span className="text-slate-400">—</span>;
  const level = LEVEL[basis.level];
  const verifiedLabel = locale === "vi" ? "Định danh đã xác minh độc lập" : "Independently verified identity";
  return (
    <div className="flex flex-col items-start gap-1" data-testid="link-evidence-basis" data-level={basis.level}>
      <Badge tone={level.tone} appearance="outline">
        {basis.independently_verified ? verifiedLabel : level[locale]}
      </Badge>
      {basis.supporting_evidence_types.length > 0 ? (
        <span className="text-[11px] text-slate-500">
          {locale === "vi" ? "Nguồn: " : "Source: "}
          {sourceText(basis.supporting_evidence_types, locale)}
        </span>
      ) : (
        <span className="text-[11px] text-slate-500">
          {locale === "vi"
            ? "Liên kết không có bản ghi chứng cứ (có thể tạo trước khi hệ thống lưu chứng cứ)."
            : "The link has no evidence record (it may predate evidence recording)."}
        </span>
      )}
      {basis.contradicting_evidence_types.length > 0 && (
        <span className="text-[11px] font-semibold text-rose-700">
          {locale === "vi" ? "Có chứng cứ mâu thuẫn: " : "Contradicting evidence: "}
          {sourceText(basis.contradicting_evidence_types, locale)}
        </span>
      )}
    </div>
  );
}

export function ReviewDecisionCell({
  decision,
  locale,
  formatDate,
}: {
  decision?: LinkReviewDecisionRead | null;
  locale: Locale;
  formatDate: (iso: string) => string;
}) {
  if (decision === undefined) return <span className="text-slate-400">—</span>;
  if (decision === null) {
    return <span className="text-[11px] text-slate-500">{locale === "vi" ? "Không có bản ghi quyết định duyệt" : "No review decision on record"}</span>;
  }
  return (
    <div className="flex max-w-[240px] flex-col items-start gap-1">
      <span className="text-[11px] text-slate-700">
        {locale === "vi" ? "Đã chấp nhận" : "Accepted"} · {formatDate(decision.decided_at)}
      </span>
      <span className="line-clamp-2 text-[11px] text-slate-500" title={decision.reason ?? undefined}>
        {decision.reason ?? (locale === "vi" ? "Không ghi lý do" : "No reason recorded")}
      </span>
      <Link to="/review-history" className="text-[11px] font-semibold text-brand hover:underline">
        {locale === "vi" ? "Xem lịch sử duyệt" : "View review history"}
      </Link>
    </div>
  );
}
