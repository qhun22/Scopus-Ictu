export interface LecturerScopusProfile {
  lecturer_id: string;
  full_name: string;
  staff_code: string | null;
  email: string | null;
  academic_rank: string | null;
  academic_degree: string | null;
  position: string | null;
  department: string | null;
  faculty: string | null;
  repository_profile_url: string | null;
  orcid: string | null;
}

export interface IdentityEvidenceSummary {
  evidence_type: string;
  direction: string;
  created_at: string;
}

export interface ApprovedScopusIdentity {
  identity_id: string;
  status: string;
  scopus_author_id: string;
  scopus_id: string;
  preferred_name: string;
  name_variants: string[];
  evidence: IdentityEvidenceSummary[];
  created_at: string;
  updated_at: string;
}

export interface LecturerPublication {
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
  linked_author_orders: number[];
}

export interface LecturerPublicationAggregates {
  total_publications: number;
  publication_count_by_year: Record<string, number>;
  unknown_year_count: number;
  known_citation_sum: number;
  citation_unknown_publication_count: number;
  approved_identity_count: number;
}

export interface LecturerPublicationsResponse {
  items: LecturerPublication[];
  total: number;
  page: number;
  page_size: number;
  aggregates: LecturerPublicationAggregates;
}
