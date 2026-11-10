import type { LecturerPublication } from "../../types/lecturerScopus";

export const FILTER_KEYS = ["q", "year", "type", "source", "stage", "access", "citations", "doi", "author"] as const;
export type FilterKey = typeof FILTER_KEYS[number];
export type PublicationFilters = Record<FilterKey, string>;
export const SORT_KEYS = ["newest", "oldest", "mostCited", "leastCited", "titleAZ"] as const;
export type PublicationSort = typeof SORT_KEYS[number];

export function normalizeSearch(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[đĐ]/g, "d").toLowerCase().trim();
}

/** Filter the complete lecturer projection, never just the visible page. */
export function filterPublications(items: LecturerPublication[], filters: PublicationFilters, sort: PublicationSort, locale: string): LecturerPublication[] {
  const words = normalizeSearch(filters.q).split(/\s+/).filter(Boolean);
  const filtered = items.filter((item) => {
    const text = normalizeSearch([item.title, item.source_title, item.doi, item.eid, item.document_type, item.publication_stage, item.open_access_status].join(" "));
    if (!words.every((word) => text.includes(word))) return false;
    if (filters.year && (item.year === null ? "unknown" : String(item.year)) !== filters.year) return false;
    if (filters.type && item.document_type !== filters.type) return false;
    if (filters.source && item.source_title !== filters.source) return false;
    if (filters.stage && item.publication_stage !== filters.stage) return false;
    if (filters.access && item.open_access_status !== filters.access) return false;
    if (filters.citations === "cited" && !(item.cited_by_count !== null && item.cited_by_count > 0)) return false;
    if (filters.citations === "uncited" && item.cited_by_count !== 0) return false;
    if (filters.citations === "unknown" && item.cited_by_count !== null) return false;
    if (filters.doi === "present" && !item.doi?.trim()) return false;
    if (filters.doi === "missing" && item.doi?.trim()) return false;
    if (filters.author === "first" && !item.linked_author_orders.includes(1)) return false;
    if (filters.author === "other" && (!item.linked_author_orders.length || item.linked_author_orders.includes(1))) return false;
    return true;
  });
  const compareNullable = (left: number | null, right: number | null, ascending: boolean) => {
    if (left === null) return right === null ? 0 : 1;
    if (right === null) return -1;
    return ascending ? left - right : right - left;
  };
  return filtered.sort((left, right) => {
    let order: number;
    if (sort === "titleAZ") order = left.title.localeCompare(right.title, locale);
    else if (sort === "mostCited" || sort === "leastCited") order = compareNullable(left.cited_by_count, right.cited_by_count, sort === "leastCited");
    else order = compareNullable(left.year, right.year, sort === "oldest");
    return order || left.eid.localeCompare(right.eid);
  });
}

export function distinctValues(items: LecturerPublication[], field: "source_title" | "document_type" | "publication_stage" | "open_access_status", locale: string): string[] {
  return [...new Set(items.flatMap((item) => item[field]?.trim() ? [item[field]!] : []))]
    .sort((left, right) => left.localeCompare(right, locale));
}
