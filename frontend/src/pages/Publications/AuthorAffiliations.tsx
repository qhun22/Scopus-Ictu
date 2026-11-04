import type {
  AffiliationLinkStatus,
  AffiliationOverrideRead,
  AuthorAffiliationRead,
  PublicationAuthorRead,
} from "../../types/publication";

type Locale = "vi" | "en";

const STATUS_TEXT_COLOR: Record<AffiliationLinkStatus, string> = {
  VERIFIED: "text-emerald-700",
  CORROBORATED: "text-amber-700",
  UNRESOLVED: "text-slate-600",
  NOT_RECONCILED: "text-slate-500",
};

// Display labels only: the enum values in the API and database are unchanged.
const STATUS_LABEL: Record<AffiliationLinkStatus, Record<Locale, string>> = {
  VERIFIED: { vi: "Đã xác minh định danh", en: "Identity verified" },
  CORROBORATED: { vi: "Đã đối chiếu, chưa xác minh", en: "Cross-checked, not verified" },
  UNRESOLVED: { vi: "Chưa xác định", en: "Unresolved" },
  NOT_RECONCILED: { vi: "Chưa đối chiếu", en: "Not reconciled" },
};

export function statusLabel(status: AffiliationLinkStatus, locale: Locale): string {
  return STATUS_LABEL[status][locale];
}

function statusHint(status: AffiliationLinkStatus, locale: Locale): string {
  const vi: Record<AffiliationLinkStatus, string> = {
    VERIFIED:
      "Định danh được xác minh bằng chuỗi ORCID → Scopus Author ID. Đơn vị là lời khai của nguồn metadata ngoài (OpenAlex/Crossref), không phải xác nhận trực tiếp của Scopus.",
    CORROBORATED:
      "Chỉ đối chiếu theo số tác giả + vị trí + tên; không có định danh chung nên CHƯA được xác minh.",
    UNRESOLVED: "Không đủ bằng chứng; không gán đơn vị nào cho tác giả này.",
    NOT_RECONCILED: "Chưa chạy đối chiếu đơn vị cho tác giả này.",
  };
  const en: Record<AffiliationLinkStatus, string> = {
    VERIFIED:
      "Identity verified through an ORCID → Scopus Author ID chain. The unit is the external metadata source's statement (OpenAlex/Crossref), not asserted by Scopus.",
    CORROBORATED:
      "Matched only by author count + position + name; no shared identifier, so NOT verified.",
    UNRESOLVED: "Insufficient evidence; no unit is assigned to this author.",
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

/** One short, honest line on WHY a unit is attached (never raises the confidence). */
function evidenceLine(a: AuthorAffiliationRead, locale: Locale): string {
  const vi = locale === "vi";
  const p = a.provenance;
  const where = p.external_position != null ? (vi ? ` · vị trí ${p.external_position} trên nguồn` : ` · position ${p.external_position} at the source`) : "";
  if (a.link_status === "VERIFIED") {
    const orcid = typeof p.evidence?.orcid === "string" ? p.evidence.orcid : null;
    const declared = Array.isArray(p.evidence?.declared_by) ? (p.evidence.declared_by as string[]).join(", ") : "";
    return vi
      ? `Bằng chứng: ORCID ${orcid ?? "?"} khai Scopus ID của tác giả${declared ? ` (${declared})` : ""}${where}`
      : `Evidence: ORCID ${orcid ?? "?"} declares this Scopus ID${declared ? ` (${declared})` : ""}${where}`;
  }
  return vi
    ? `Bằng chứng: chỉ khớp số tác giả + vị trí + tên (không có định danh chung)${where}`
    : `Evidence: matched only by author count + position + name (no shared identifier)${where}`;
}
const sourceLabel = (s: string) => SOURCE_LABEL[s] ?? s;

// Status badge, same "nhãn chuẩn" style used across Imports/Normalization/Lecturers/Công bố.
export function AffiliationBadge({ status, locale }: { status: AffiliationLinkStatus; locale: Locale }) {
  return (
    <span
      title={statusHint(status, locale)}
      data-testid={`aff-badge-${status}`}
      className={`font-bold ${STATUS_TEXT_COLOR[status]}`}
    >
      {statusLabel(status, locale)}
    </span>
  );
}

function hasAssignedUnit(author: PublicationAuthorRead): boolean {
  if ((author.affiliation_overrides ?? []).some((o) => o.confidence === "CORROBORATED")) return true;
  const status = author.affiliation_status ?? "NOT_RECONCILED";
  if (status === "NOT_RECONCILED" || status === "UNRESOLVED") return false;
  return (author.affiliations ?? []).length > 0;
}

export function AffiliationSummaryBar({
  authors,
  locale,
}: {
  authors: PublicationAuthorRead[];
  locale: Locale;
}) {
  if (authors.length === 0) return null;
  const assigned = authors.filter(hasAssignedUnit).length;
  const unassigned = authors.length - assigned;
  const vi = locale === "vi";
  return (
    <div className="mb-3 space-y-2 rounded-[5px] border border-slate-100 bg-slate-50/60 p-3" data-testid="aff-summary">
      <div className={'flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-slate-600'}>
        <span className="font-semibold">
          {vi ? `Đơn vị theo ${authors.length} tác giả:` : `Units across ${authors.length} authors:`}
        </span>
        <span>
          {vi
            ? `${assigned} tác giả đã được gán đơn vị`
            : `${assigned} ${assigned === 1 ? "author" : "authors"} with a unit assigned`}
        </span>
        <span>
          {vi
            ? `${unassigned} tác giả chưa gán được đơn vị`
            : `${unassigned} ${unassigned === 1 ? "author" : "authors"} without a unit`}
        </span>
        <span>
          {vi ? `${authors.length} tác giả, theo thứ tự trên bài báo.` : `${authors.length} authors, in publication order.`}
        </span>
      </div>
      <p className="text-sm leading-snug text-slate-500">
        {vi
          ? "Đơn vị được tra cứu từ nguồn bên ngoài (OpenAlex, Crossref), chưa được Scopus xác nhận trực tiếp."
          : "Units are looked up from external sources (OpenAlex, Crossref) and have not been directly confirmed by Scopus."}
      </p>
    </div>
  );
}

function OverrideNote({ override, locale }: { override: AffiliationOverrideRead; locale: Locale }) {
  const vi = locale === "vi";
  return (
    <div
      className="mt-1.5 rounded-[5px] border border-blue-200 bg-blue-50/60 p-2 text-sm leading-snug"
      data-testid="aff-override"
    >
      <p className="font-medium text-slate-700">{override.affiliation_text}</p>
      {override.evidence_url && (
        <p className="mt-0.5 text-slate-500">
          {vi ? "Nguồn: " : "Source: "}
          <a href={override.evidence_url} target="_blank" rel="noreferrer" className="text-sky-700 underline">
            {override.evidence_url}
          </a>
        </p>
      )}
    </div>
  );
}

export function AuthorAffiliationCell({
  author,
  locale,
  isAdmin = false,
}: {
  author: PublicationAuthorRead;
  locale: Locale;
  isAdmin?: boolean;
}) {
  const vi = locale === "vi";
  const status = author.affiliation_status ?? "NOT_RECONCILED";
  const affiliations = author.affiliations ?? [];
  const resolutions = author.affiliation_resolutions ?? [];
  const noUnit = vi ? "Chưa có thông tin đơn vị" : "No unit information yet";
  const hasUnit = vi ? "Đã có thông tin đơn vị" : "Unit information available";

  const resolutionLine = isAdmin && resolutions.length > 0 && (
    <div className="mt-1 text-sm text-slate-500" data-testid="aff-resolutions">
      {vi ? "Theo nguồn: " : "By source: "}
      {resolutions
        .map((r) =>
          r.link_status === "UNRESOLVED"
            ? `${sourceLabel(r.source_system)}: ${statusLabel("UNRESOLVED", locale)}${r.unresolved_reason ? ` (${reasonLabel(r.unresolved_reason, locale)})` : ""}`
            : `${sourceLabel(r.source_system)}: ${statusLabel(r.link_status, locale)}${r.affiliation_presence === "ABSENT" ? (vi ? " — nguồn không có đơn vị" : " — source lists no unit") : ""}`,
        )
        .join(" · ")}
    </div>
  );

  const overrides = author.affiliation_overrides ?? [];

  if (status === "NOT_RECONCILED") {
    return (
      <div>
        <AffiliationBadge status={status} locale={locale} />
        {overrides.map((o, i) => (
          <OverrideNote key={i} override={o} locale={locale} />
        ))}
      </div>
    );
  }

  if (status === "UNRESOLVED") {
    return (
      <div>
        {overrides.length === 0 && (
          <AffiliationBadge status={status} locale={locale} />
        )}
        {resolutionLine}
        {overrides.map((o, i) => (
          <OverrideNote key={i} override={o} locale={locale} />
        ))}
      </div>
    );
  }

  // Identity verified by one source while the only unit listed comes from another
  // source by cross-checking: say so, so the unit is not read as verified.
  const verifiedWithoutUnitSources = resolutions
    .filter((r) => r.link_status === "VERIFIED" && r.affiliation_presence === "ABSENT")
    .map((r) => sourceLabel(r.source_system));
  const unitOnlyCrossChecked =
    status === "VERIFIED" && affiliations.length > 0 && !affiliations.some((a) => a.link_status === "VERIFIED");

  return (
    <div>
      {affiliations.length === 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <AffiliationBadge status={status} locale={locale} />
          <span className="font-medium text-slate-500" data-testid={overrides.length > 0 ? "aff-has-unit" : "aff-no-unit"}>
            {overrides.length > 0 ? hasUnit : noUnit}
          </span>
        </div>
      )}
      {unitOnlyCrossChecked && isAdmin && (
        <p className="mb-1 text-sm leading-snug text-amber-700" data-testid="aff-cross-checked-note">
          {vi
            ? `Định danh đã xác minh${verifiedWithoutUnitSources.length ? ` qua ${verifiedWithoutUnitSources.join(", ")}` : ""} nhưng nguồn đó không có đơn vị; đơn vị bên dưới chỉ ở mức đối chiếu, chưa xác minh.`
            : `Identity verified${verifiedWithoutUnitSources.length ? ` via ${verifiedWithoutUnitSources.join(", ")}` : ""} but that source lists no unit; the unit below is only cross-checked, not verified.`}
        </p>
      )}
      {affiliations.length > 0 && (
        isAdmin ? (
          <ul className="space-y-1.5">
            {affiliations.map((a, i) => (
              <li key={`${a.source_system}-${i}`} className="leading-snug" data-testid="aff-item">
                <div className="flex flex-wrap items-center gap-1.5">
                  <AffiliationBadge status={a.link_status} locale={locale} />
                  <span className="rounded bg-slate-100 px-1.5 text-sm font-semibold text-slate-600">{sourceLabel(a.source_system)}</span>
                  <span className="min-w-0 break-words text-slate-700">{a.raw_affiliation_text ?? <em className="text-slate-400">{vi ? "(chỉ có tổ chức chuẩn hóa)" : "(normalized organization only)"}</em>}</span>
                </div>
                <div className="mt-0.5 text-sm text-slate-400" data-testid="aff-evidence">{evidenceLine(a, locale)}</div>
                {a.organizations.length > 0 && (
                  <div className="mt-0.5 flex flex-wrap gap-1 text-sm text-slate-500">
                    <span>{vi ? "Tổ chức (do nguồn chuẩn hóa):" : "Organization (source-normalized):"}</span>
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
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <AffiliationBadge status={status} locale={locale} />
            <span className="font-medium text-slate-500" data-testid="aff-has-unit">
              {hasUnit}
            </span>
          </div>
        )
      )}
      {resolutionLine}
      {overrides.map((o, i) => (
        <OverrideNote key={i} override={o} locale={locale} />
      ))}
    </div>
  );
}
