// Human-readable labels for the matching rule / reconciliation codes shown to reviewers.
// Meanings follow backend/app/services/matching/candidate_generator.py and the known-publication enrichment rules.
// The raw code is kept for traceability (tooltip), never shown instead of the label; unknown codes fall back to the code.

type Locale = "vi" | "en";

const RULES: Record<string, Record<Locale, string>> = {
  RULE_EXACT_N0: {
    vi: "Trùng tên chính xác (chỉ chuẩn hóa khoảng trắng, chữ hoa/thường)",
    en: "Exact name match (whitespace / letter case normalised)",
  },
  RULE_TITLE_STRIPPED_N0: {
    vi: "Trùng tên sau khi bỏ học hàm, học vị",
    en: "Name match after removing academic titles",
  },
  RULE_TITLE_STRIPPED_N2: {
    vi: "Trùng tên sau khi bỏ học hàm, học vị và dấu tiếng Việt",
    en: "Name match after removing academic titles and Vietnamese diacritics",
  },
  RULE_TITLE_STRIPPED_N2_FORMAT: {
    vi: "Trùng tên sau khi bỏ học hàm, học vị, dấu tiếng Việt và dấu phẩy (dạng 'Họ, Tên')",
    en: "Name match after removing titles, Vietnamese diacritics and the comma ('Family, Given' form)",
  },
  RULE_N2: {
    vi: "Trùng tên sau khi bỏ dấu tiếng Việt",
    en: "Name match after removing Vietnamese diacritics",
  },
  RULE_N2_FORMAT: {
    vi: "Trùng tên sau khi bỏ dấu tiếng Việt và dấu phẩy (dạng 'Họ, Tên')",
    en: "Name match after removing Vietnamese diacritics and the comma ('Family, Given' form)",
  },
  RULE_N2_HYPHEN: {
    vi: "Trùng tên sau khi bỏ dấu tiếng Việt, dấu phẩy và gạch nối (dạng Scopus 'Họ, Tên-Đệm')",
    en: "Name match after removing Vietnamese diacritics, comma and hyphen (Scopus 'Family, First-Middle' form)",
  },
  RULE_KNOWN_PUBLICATION_DOI_EXACT: {
    vi: "Công bố đã biết của giảng viên trùng DOI",
    en: "Lecturer's known publication with the same DOI",
  },
  RULE_KNOWN_PUBLICATION_TITLE_EXACT: {
    vi: "Công bố đã biết của giảng viên trùng tiêu đề",
    en: "Lecturer's known publication with the same title",
  },
  RULE_CRAW_KNOWN_PUBLICATION_AUTHOR_POSITION: {
    vi: "Công bố Craw trùng ở đúng vị trí tác giả",
    en: "Crawled publication matching at the author position",
  },
};

const RECONCILIATION: Record<string, Record<Locale, string>> = {
  DOI_EXACT: { vi: "Trùng DOI", en: "DOI match" },
  TITLE_EXACT: { vi: "Trùng tiêu đề", en: "Title match" },
};

// Which Scopus name surface matched (scopus_author.preferred_name or a name variant type).
const SURFACE: Record<string, Record<Locale, string>> = {
  PREFERRED_NAME: { vi: "Tên ưu tiên trên Scopus", en: "Scopus preferred name" },
  AUTHOR_FULL_NAME: { vi: "Họ tên đầy đủ trên Scopus", en: "Scopus full author name" },
  AUTHOR_DISPLAY: { vi: "Tên hiển thị trên Scopus", en: "Scopus display name" },
};

export function surfaceLabel(code: string, locale: Locale): string {
  return SURFACE[code]?.[locale] ?? code;
}

export function ruleLabel(code: string, locale: Locale): string {
  return RULES[code]?.[locale] ?? code;
}

export function reconciliationLabel(code: string | null | undefined, locale: Locale, unknown: string): string {
  if (!code) return unknown;
  return RECONCILIATION[code]?.[locale] ?? code;
}
