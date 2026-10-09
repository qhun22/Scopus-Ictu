import type {
  AffiliationLinkStatus,
  AffiliationSummaryRead,
  PublicationAuthorRead,
} from "../../types/publication";

type Locale = "vi" | "en";

const STATUS_STYLE: Record<AffiliationLinkStatus, string> = {
  VERIFIED: "bg-emerald-50 text-emerald-700 border-emerald-200",
  CORROBORATED: "bg-amber-50 text-amber-700 border-amber-200",
  UNRESOLVED: "bg-slate-100 text-slate-600 border-slate-200",
  NOT_RECONCILED: "bg-slate-50 text-slate-400 border-slate-200",
};

function statusHint(status: AffiliationLinkStatus, locale: Locale): string {
  const vi: Record<AffiliationLinkStatus, string> = {
    VERIFIED: "Đã xác minh bằng chuỗi định danh ORCID → Scopus Author ID.",
    CORROBORATED: "Chỉ đối chiếu theo số tác giả + vị trí + tên. CHƯA được xác minh.",
    UNRESOLVED: "Không đủ bằng chứng; không gán đơn vị nào.",
    NOT_RECONCILED: "Chưa chạy đối chiếu affiliation cho tác giả này.",
  };
  const en: Record<AffiliationLinkStatus, string> = {
    VERIFIED: "Verified through an ORCID → Scopus Author ID identifier chain.",
    CORROBORATED: "Matched only by author count + position + name. NOT verified.",
    UNRESOLVED: "Insufficient evidence; no unit is assigned.",
    NOT_RECONCILED: "No affiliation reconciliation has been run for this author.",
  };
  return (locale === "vi" ? vi : en)[status];
}

const REASON_VI: Record<string, string> = {
  NO_EXTERNAL_WORK: "Không tìm thấy bài trên nguồn ngoài",
  NO_EXTERNAL_AUTHOR_LIST: "Nguồn ngoài không có danh sách tác giả",
  AUTHOR_COUNT_MISMATCH: "Số tác giả khác với Scopus",
  NAME_MISMATCH: "Tên tác giả không khớp",
  ORDER_INCONSISTENT_WITH_VERIFIED_ID: "Thứ tự mâu thuẫn với định danh đã xác minh",
  POSITION_CLAIMED_BY_OTHER_ID: "Vị trí đã thuộc về định danh khác",
  ID_CONFLICT: "Mâu thuẫn định danh",
  ID_AMBIGUOUS: "Định danh không rõ ràng",
  WITHHELD_SOURCE_CONFLICT: "Giữ lại do xung đột giữa các nguồn",
};
const REASON_EN: Record<string, string> = {
  NO_EXTERNAL_WORK: "Paper not found in the external source",
  NO_EXTERNAL_AUTHOR_LIST: "External source has no author list",
  AUTHOR_COUNT_MISMATCH: "Author count differs from Scopus",
  NAME_MISMATCH: "Author name does not match",
  ORDER_INCONSISTENT_WITH_VERIFIED_ID: "Order contradicts a verified identifier",
  POSITION_CLAIMED_BY_OTHER_ID: "Position already claimed by another identifier",
  ID_CONFLICT: "Identifier conflict",
  ID_AMBIGUOUS: "Ambiguous identifier",
  WITHHELD_SOURCE_CONFLICT: "Withheld because sources conflict",
};

export function reasonLabel(code: string, locale: Locale): string {
  return (locale === "vi" ? REASON_VI : REASON_EN)[code] ?? code;
}

const SOURCE_LABEL: Record<string, string> = { openalex: "OpenAlex", crossref: "Crossref" };
const sourceLabel = (s: string) => SOURCE_LABEL[s] ?? s;

export function AffiliationBadge({
  status,
  locale,
  small = false,
}: {
  status: AffiliationLinkStatus;
  locale: Locale;
  small?: boolean;
}) {
  const text = status === "NOT_RECONCILED" ? (locale === "vi" ? "Chưa đối chiếu" : "Not reconciled") : status;
  return (
    <span
      title={statusHint(status, locale)}
      data-testid={`aff-badge-${status}`}
      className={`inline-flex items-center rounded border font-bold ${small ? "px-1.5 py-0 text-[10px]" : "px-2 py-0.5 text-[11px]"} ${STATUS_STYLE[status]}`}
    >
      {text}
    </span>
  );
}

export function AffiliationSummaryBar({
  summary,
  locale,
}: {
  summary: AffiliationSummaryRead | null | undefined;
  locale: Locale;
}) {
  if (!summary) return null;
  const all: Array<{ status: AffiliationLinkStatus; label: string; value: number }> = [
    { status: "VERIFIED", label: locale === "vi" ? "có đơn vị" : "with unit", value: summary.verified_with_affiliation },
    { status: "VERIFIED", label: locale === "vi" ? "nguồn không có đơn vị" : "source lists no unit", value: summary.verified_without_affiliation },
    { status: "CORROBORATED", label: locale === "vi" ? "có đơn vị" : "with unit", value: summary.corroborated_with_affiliation },
    { status: "CORROBORATED", label: locale === "vi" ? "nguồn không có đơn vị" : "source lists no unit", value: summary.corroborated_without_affiliation },
    { status: "UNRESOLVED", label: locale === "vi" ? "chưa xác định" : "unresolved", value: summary.unresolved },
    { status: "NOT_RECONCILED", label: locale === "vi" ? "chưa đối chiếu" : "not reconciled", value: summary.not_reconciled },
  ];
  const items = all.filter((i) => i.value > 0 || i.status !== "NOT_RECONCILED");
  return (
    <div className="mb-3 space-y-2 rounded-lg border border-slate-100 bg-slate-50/60 p-3" data-testid="aff-summary">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
        <span className="font-semibold">
          {locale === "vi" ? `Affiliation theo ${summary.authors} tác giả:` : `Affiliation across ${summary.authors} authors:`}
        </span>
        {items.map((i, idx) => (
          <span key={`${i.status}-${idx}`} className="inline-flex items-center gap-1">
            <AffiliationBadge status={i.status} locale={locale} small />
            <span>
              {i.value} {i.label}
            </span>
          </span>
        ))}
      </div>
      <p className="text-[11px] leading-snug text-slate-500">
        {locale === "vi"
          ? "Đơn vị lấy từ nguồn metadata ngoài (OpenAlex/Crossref), không phải xác nhận trực tiếp của Scopus. CORROBORATED chỉ là đối chiếu theo số tác giả + vị trí + tên, chưa được xác minh."
          : "Affiliations come from external metadata sources (OpenAlex/Crossref), not asserted by Scopus. CORROBORATED is matched by author count + position + name only and is not verified."}
      </p>
    </div>
  );
}

export function AuthorAffiliationCell({
  author,
  locale,
}: {
  author: PublicationAuthorRead;
  locale: Locale;
}) {
  const status = author.affiliation_status ?? "NOT_RECONCILED";
  const affiliations = author.affiliations ?? [];
  const resolutions = author.affiliation_resolutions ?? [];
  const noUnit = locale === "vi" ? "Chưa có thông tin đơn vị" : "No unit information yet";

  const resolutionLine = resolutions.length > 0 && (
    <div className="mt-1 text-[10px] text-slate-400" data-testid="aff-resolutions">
      {resolutions
        .map((r) =>
          r.link_status === "UNRESOLVED"
            ? `${sourceLabel(r.source_system)}: UNRESOLVED${r.unresolved_reason ? ` (${reasonLabel(r.unresolved_reason, locale)})` : ""}`
            : `${sourceLabel(r.source_system)}: ${r.link_status}${r.affiliation_presence === "ABSENT" ? (locale === "vi" ? " — nguồn không có đơn vị" : " — source lists no unit") : ""}`,
        )
        .join(" · ")}
    </div>
  );

  if (status === "NOT_RECONCILED") {
    return <AffiliationBadge status={status} locale={locale} />;
  }

  if (status === "UNRESOLVED") {
    return (
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <AffiliationBadge status={status} locale={locale} />
          <span className="text-slate-500">{locale === "vi" ? "Chưa xác định được đơn vị" : "Unit could not be determined"}</span>
        </div>
        {resolutionLine}
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <AffiliationBadge status={status} locale={locale} />
        {affiliations.length === 0 && (
          <span className="font-medium text-slate-500" data-testid="aff-no-unit">
            {noUnit}
          </span>
        )}
      </div>
      {affiliations.length > 0 && (
        <ul className="mt-1.5 space-y-1.5">
          {affiliations.map((a, i) => (
            <li key={`${a.source_system}-${i}`} className="leading-snug" data-testid="aff-item">
              <div className="flex flex-wrap items-center gap-1.5">
                <AffiliationBadge status={a.link_status} locale={locale} small />
                <span className="rounded bg-slate-100 px-1.5 text-[10px] font-semibold text-slate-600">{sourceLabel(a.source_system)}</span>
                <span className="text-slate-700">{a.raw_affiliation_text ?? <em className="text-slate-400">{locale === "vi" ? "(chỉ có tổ chức chuẩn hóa)" : "(normalized organization only)"}</em>}</span>
              </div>
              {a.organizations.length > 0 && (
                <div className="ml-1 mt-0.5 flex flex-wrap gap-1 text-[10px] text-slate-500">
                  <span>{locale === "vi" ? "Tổ chức (do nguồn chuẩn hóa):" : "Organization (source-normalized):"}</span>
                  {a.organizations.map((o, k) => (
                    <span key={`${o.source_org_id ?? o.display_name}-${k}`} className="rounded bg-sky-50 px-1.5 text-sky-700">
                      {o.display_name}
                      {o.country_code ? ` (${o.country_code})` : ""}
                    </span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {resolutionLine}
    </div>
  );
}
