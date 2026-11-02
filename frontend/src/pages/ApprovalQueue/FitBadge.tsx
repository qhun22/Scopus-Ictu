import { ReviewFit } from "../../types/review";

type Locale = "vi" | "en";

const LEVEL_LABEL: Record<ReviewFit["level"], Record<Locale, string>> = {
  HIGH: { vi: "Phù hợp cao", en: "High fit" },
  MEDIUM: { vi: "Phù hợp vừa", en: "Medium fit" },
  LOW: { vi: "Phù hợp thấp", en: "Low fit" },
  INSUFFICIENT: { vi: "Chưa đủ căn cứ", en: "Not enough grounds" },
};

const LEVEL_STYLE: Record<ReviewFit["level"], string> = {
  HIGH: "border-emerald-300 text-emerald-700 hover:bg-emerald-50",
  MEDIUM: "border-[#3A5FC3] text-[#3A5FC3] hover:bg-blue-50",
  LOW: "border-amber-300 text-amber-700 hover:bg-amber-50",
  INSUFFICIENT: "border-slate-300 text-slate-600 hover:bg-slate-50",
};

/** One sentence per reason code, so the reviewer reads the grounds instead of a bare label. */
export function fitReasonText(code: string, locale: Locale, ictuPapers: number): string {
  const vi = locale === "vi";
  switch (code) {
    case "PUBLICATION_SUPPORT":
      return vi ? "Có công bố trùng với công bố đã biết của giảng viên (DOI hoặc tiêu đề)." : "Shares a publication known for the lecturer (DOI or title).";
    case "ICTU_AFFILIATION":
      return vi
        ? `Có ${ictuPapers} bài của tác giả này ghi đơn vị là ICTU.`
        : `${ictuPapers} paper(s) of this author report ICTU as the affiliation.`;
    case "NAME_MATCH":
      return vi ? "Tên giảng viên khớp tên tác giả Scopus theo ít nhất một quy tắc." : "The lecturer's name matches the Scopus author's name under at least one rule.";
    case "NAME_ONLY":
      return vi ? "Chỉ có tên giống nhau, chưa có công bố hay đơn vị hỗ trợ." : "Only the names match; no publication or affiliation supports it.";
    case "SHARED_ID":
      return vi ? "ID này cũng được đề xuất cho giảng viên khác, nên không xếp mức cao." : "This ID is also proposed for another lecturer, so it is not rated high.";
    case "MULTIPLE_IDS_FOR_LECTURER":
      return vi ? "Giảng viên có nhiều ID được đề xuất; có thể là cùng một người." : "The lecturer has several proposed IDs; they may be one person.";
    default:
      return code;
  }
}

export function fitLevelLabel(level: ReviewFit["level"], locale: Locale): string {
  return LEVEL_LABEL[level][locale];
}

export default function FitBadge({ fit, locale }: { fit: ReviewFit; locale: Locale }) {
  return (
    <span
      className={`inline-flex h-badge w-32 shrink-0 items-center justify-center whitespace-nowrap rounded-[5px] border bg-white px-2 text-center text-xs font-bold leading-none ${LEVEL_STYLE[fit.level]}`}
      title={fit.reasons.map((r) => fitReasonText(r, locale, fit.ictu_affiliation_papers)).join("\n")}
      data-testid="fit-badge"
    >
      {fitLevelLabel(fit.level, locale)}
    </span>
  );
}
