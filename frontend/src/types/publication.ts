/** Typed publication API types — mirrors backend PublicationDetailResponse. */

export interface PublicationListItem {
  publication_id: string;
  eid: string;
  doi: string | null;
  title: string;
  source_title: string | null;
  year: number | null;
  cited_by_count: number | null;
  document_type: string | null;
  publication_stage: string | null;
  open_access_status: string | null;
}

export interface PublicationListResponse {
  items: PublicationListItem[];
  total: number;
  page: number;
  page_size: number;
}

/** Confidence of the link between the Scopus author and an external-source authorship. */
export type AffiliationLinkStatus = "VERIFIED" | "CORROBORATED" | "UNRESOLVED" | "NOT_RECONCILED";

export interface AffiliationOrganizationRead {
  source_system: string;
  source_org_id: string | null;
  ror: string | null;
  display_name: string;
  country_code: string | null;
}

export interface AuthorAffiliationRead {
  link_status: "VERIFIED" | "CORROBORATED";
  source_system: string;
  raw_affiliation_text: string | null;
  organizations: AffiliationOrganizationRead[];
  retrieved_at: string;
  /** Always the author's affiliation on THIS paper per an external metadata source (not Scopus). */
  scope: "AUTHOR_ON_PUBLICATION_EXTERNAL_SOURCE";
  provenance: {
    link_method: string;
    source_work_id: string | null;
    source_doi: string | null;
    external_position: number | null;
    external_author_name: string | null;
    evidence: Record<string, unknown>;
  };
}

export interface AffiliationResolutionRead {
  source_system: string;
  link_status: "VERIFIED" | "CORROBORATED" | "UNRESOLVED";
  link_method: string | null;
  unresolved_reason: string | null;
  affiliation_presence: "PRESENT" | "ABSENT" | null;
  retrieved_at: string | null;
  source_work_id: string | null;
}

/** ADMIN-entered statement, layered on top of the automated resolutions.
 * Never independently verified by this alone — confidence is always
 * CORROBORATED or UNRESOLVED, never VERIFIED. */
export interface AffiliationOverrideRead {
  affiliation_text: string;
  confidence: "CORROBORATED" | "UNRESOLVED";
  evidence_url: string;
  reason: string;
  updated_at: string;
  note: string;
}

export interface PublicationAuthorRead {
  author_order: number;
  scopus_id: string;
  preferred_name: string;
  affiliation_status?: AffiliationLinkStatus;
  /** true: a trusted source lists a unit; false: it lists none; null: unknown. */
  source_has_affiliation?: boolean | null;
  affiliations?: AuthorAffiliationRead[];
  affiliation_resolutions?: AffiliationResolutionRead[];
  /** All currently-active ADMIN overrides for this position (0, 1, or many). */
  affiliation_overrides?: AffiliationOverrideRead[];
}

export interface AffiliationSummaryRead {
  authors: number;
  verified_with_affiliation: number;
  verified_without_affiliation: number;
  corroborated_with_affiliation: number;
  corroborated_without_affiliation: number;
  unresolved: number;
  not_reconciled: number;
  all_authors_verified_with_affiliation: boolean;
  all_authors_verified_or_corroborated_with_affiliation: boolean;
  note?: string;
}

export interface PublicationLecturerLinkRead {
  author_order: number;
  scopus_id: string;
  full_name: string;
  staff_code: string | null;
  department: string | null;
  faculty: string | null;
  orcid: string | null;
}

export interface PublicationProvenanceRead {
  file_name: string;
  file_sha256: string;
  row_number: number;
  imported_at: string;
}

export interface PublicationDetailResponse {
  publication_id: string;
  eid: string;
  doi: string | null;
  title: string;
  source_title: string | null;
  year: number | null;
  volume: string | null;
  issue: string | null;
  art_no: string | null;
  page_start: string | null;
  page_end: string | null;
  cited_by_count: number | null;
  document_type: string | null;
  publication_stage: string | null;
  open_access_status: string | null;
  authors: PublicationAuthorRead[];
  affiliation_summary?: AffiliationSummaryRead | null;
  approved_lecturer_links: PublicationLecturerLinkRead[];
  provenance: PublicationProvenanceRead[];
}

export interface PublicationListQuery {
  page?: number;
  page_size?: number;
  q?: string;
  year?: number;
  document_type?: string;
  publication_stage?: string;
  open_access_status?: string;
  /** Only publications in which this Scopus Author ID appears. */
  scopus_id?: string;
  /** Only publications with an author whose Scopus preferred name matches (substring, diacritic-insensitive). */
  author_name?: string;
}
