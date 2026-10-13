import type {
  AffiliationLinkStatus,
  AffiliationOverrideRead,
  AuthorAffiliationRead,
  PublicationAuthorRead,
} from "../../types/publication";

type Locale = "vi" | "en";

const STATUS_STYLE: Record<AffiliationLinkStatus, string> = {
  VERIFIED: "bg-emerald-50 text-emerald-700 border-emerald-200",
  CORROBORATED: "bg-amber-50 text-amber-700 border-amber-200",
  UNRESOLVED: "bg-slate-100 text-slate-600 border-slate-200",
  NOT_RECONCILED: "bg-slate-50 text-slate-400 border-slate-200",
};

// Display labels only: the enum values in the API and database are unchanged.
const STATUS_LABEL: Record<AffiliationLinkStatus, Record<Locale, string>> = {
  VERIFIED: { vi: "Đã xác minh định danh", en: "Identity verified" },
  CORROBORATED: { vi: "Đã đối chiếu · Chưa xác minh", en: "Cross-checked · Not verified" },
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

export function AffiliationBadge({
  status,
  locale,
  small = false,
}: {
  status: AffiliationLinkStatus;
  locale: Locale;
  small?: boolean;
}) {
  return (
    <span
      title={statusHint(status, locale)}
      data-testid={`aff-badge-${status}`}
      className={`inline-flex items-center whitespace-nowrap rounded border font-bold ${small ? "px-1.5 py-0 text-[10px]" : "px-2 py-0.5 text-[11px]"} ${STATUS_STYLE[status]}`}
    >
      {statusLabel(status, locale)}
    </span>
  );
}

/**
 * Trust level of the UNIT shown for an author (not of the identity link).
 * An author whose identity is verified by a source that lists no unit, while
 * another source lists a unit only by cross-checking, has a cross-checked unit.
 */
type UnitLevel = "VERIFIED" | "CORROBORATED" | "NO_UNIT_VERIFIED" | "NO_UNIT_CORROBORATED" | "UNRESOLVED" | "NOT_RECONCILED";

function unitLevel(author: PublicationAuthorRead): UnitLevel {
  const status = author.affiliation_status ?? "NOT_RECONCILED";
  if (status === "NOT_RECONCILED") return "NOT_RECONCILED";
  if (status === "UNRESOLVED") return "UNRESOLVED";
  const items = author.affiliations ?? [];
  if (items.some((a) => a.link_status === "VERIFIED")) return "VERIFIED";
  if (items.length > 0) return "CORROBORATED";
  return status === "VERIFIED" ? "NO_UNIT_VERIFIED" : "NO_UNIT_CORROBORATED";
}

export function AffiliationSummaryBar({
  authors,
  locale,
}: {
  authors: PublicationAuthorRead[];
  locale: Locale;
}) {
  if (authors.length === 0) return null;
  const counts: Record<UnitLevel, number> = {
    VERIFIED: 0,
    CORROBORATED: 0,
    NO_UNIT_VERIFIED: 0,
    NO_UNIT_CORROBORATED: 0,
    UNRESOLVED: 0,
    NOT_RECONCILED: 0,
  };
  for (const a of authors) counts[unitLevel(a)] += 1;

  const vi = locale === "vi";
  const all: Array<{ key: UnitLevel; status: AffiliationLinkStatus; label: string }> = [
    { key: "VERIFIED", status: "VERIFIED", label: vi ? "có đơn vị" : "with unit" },
    { key: "CORROBORATED", status: "CORROBORATED", label: vi ? "có đơn vị" : "with unit" },
    {
      key: "NO_UNIT_VERIFIED",
      status: "VERIFIED",
      label: vi ? "nguồn xác minh không có đơn vị" : "verifying source lists no unit",
    },
    { key: "NO_UNIT_CORROBORATED", status: "CORROBORATED", label: vi ? "nguồn không có đơn vị" : "source lists no unit" },
    { key: "UNRESOLVED", status: "UNRESOLVED", label: vi ? "không gán được đơn vị" : "no unit assigned" },
    { key: "NOT_RECONCILED", status: "NOT_RECONCILED", label: vi ? "chưa đối chiếu" : "not reconciled" },
  ];
  const items = all.filter((i) => counts[i.key] > 0);
  return (
    <div className="mb-3 space-y-2 rounded-lg border border-slate-100 bg-slate-50/60 p-3" data-testid="aff-summary">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-slate-600">
        <span className="font-semibold">
          {vi ? `Đơn vị theo ${authors.length} tác giả:` : `Units across ${authors.length} authors:`}
        </span>
        {items.map((i) => (
          <span key={i.key} className="inline-flex items-center gap-1">
            <AffiliationBadge status={i.status} locale={locale} small />
            <span>
              {counts[i.key]} {vi ? "tác giả" : counts[i.key] === 1 ? "author" : "authors"} {i.label}
            </span>
          </span>
        ))}
      </div>
      <p className="text-[11px] leading-snug text-slate-500">
        {vi
          ? "Đơn vị lấy từ nguồn metadata ngoài (OpenAlex, Crossref), không phải xác nhận trực tiếp của Scopus. “Đã xác minh định danh” nghĩa là có chuỗi ORCID → Scopus Author ID; “Đã đối chiếu · Chưa xác minh” chỉ khớp theo số tác giả, vị trí và tên."
          : "Units come from external metadata sources (OpenAlex, Crossref), not asserted by Scopus. “Identity verified” means an ORCID → Scopus Author ID chain exists; “Cross-checked · Not verified” is matched only by author count, position and name."}
      </p>
    </div>
  );
}

function OverrideNote({ override, locale }: { override: AffiliationOverrideRead; locale: Locale }) {
  const vi = locale === "vi";
  return (
    <div
      className="mt-1.5 rounded-lg border border-violet-200 bg-violet-50/60 p-2 text-[11px] leading-snug"
      data-testid="aff-override"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-bold text-violet-700">
          {vi ? "ADMIN rà soát thủ công" : "ADMIN manual review"}
        </span>
        <AffiliationBadge status={override.confidence} locale={locale} small />
      </div>
      <p className="mt-1 font-medium text-slate-700">{override.affiliation_text}</p>
      <p className="mt-0.5 text-slate-500">
        {vi ? "Nguồn: " : "Source: "}
        <a href={override.evidence_url} target="_blank" rel="noreferrer" className="text-sky-700 underline">
          {override.evidence_url}
        </a>
      </p>
      <p className="mt-0.5 text-slate-500">
        {vi ? "Lý do: " : "Reason: "}
        {override.reason}
      </p>
      <p className="mt-1 text-[10px] text-violet-600">{override.note}</p>
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
  const vi = locale === "vi";
  const status = author.affiliation_status ?? "NOT_RECONCILED";
  const affiliations = author.affiliations ?? [];
  const resolutions = author.affiliation_resolutions ?? [];
  const noUnit = vi ? "Chưa có thông tin đơn vị" : "No unit information yet";

  const resolutionLine = resolutions.length > 0 && (
    <div className="mt-1 text-[10px] text-slate-500" data-testid="aff-resolutions">
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
        <div className="flex flex-wrap items-center gap-2">
          <AffiliationBadge status={status} locale={locale} />
          <span className="text-slate-500">{vi ? "Chưa xác định được đơn vị" : "Unit could not be determined"}</span>
        </div>
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
          <span className="font-medium text-slate-500" data-testid="aff-no-unit">
            {noUnit}
          </span>
        </div>
      )}
      {unitOnlyCrossChecked && (
        <p className="mb-1 text-[11px] leading-snug text-amber-700" data-testid="aff-cross-checked-note">
          {vi
            ? `Định danh đã xác minh${verifiedWithoutUnitSources.length ? ` qua ${verifiedWithoutUnitSources.join(", ")}` : ""} nhưng nguồn đó không có đơn vị; đơn vị bên dưới chỉ ở mức đối chiếu, chưa xác minh.`
            : `Identity verified${verifiedWithoutUnitSources.length ? ` via ${verifiedWithoutUnitSources.join(", ")}` : ""} but that source lists no unit; the unit below is only cross-checked, not verified.`}
        </p>
      )}
      {affiliations.length > 0 && (
        <ul className="space-y-1.5">
          {affiliations.map((a, i) => (
            <li key={`${a.source_system}-${i}`} className="leading-snug" data-testid="aff-item">
              <div className="flex flex-wrap items-center gap-1.5">
                <AffiliationBadge status={a.link_status} locale={locale} small />
                <span className="rounded bg-slate-100 px-1.5 text-[10px] font-semibold text-slate-600">{sourceLabel(a.source_system)}</span>
                <span className="min-w-0 break-words text-slate-700">{a.raw_affiliation_text ?? <em className="text-slate-400">{vi ? "(chỉ có tổ chức chuẩn hóa)" : "(normalized organization only)"}</em>}</span>
              </div>
              <div className="ml-1 mt-0.5 text-[10px] text-slate-400" data-testid="aff-evidence">{evidenceLine(a, locale)}</div>
              {a.organizations.length > 0 && (
                <div className="ml-1 mt-0.5 flex flex-wrap gap-1 text-[10px] text-slate-500">
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
      )}
      {resolutionLine}
      {overrides.map((o, i) => (
        <OverrideNote key={i} override={o} locale={locale} />
      ))}
    </div>
  );
}
