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

export interface PublicationAuthorRead {
  author_order: number;
  scopus_id: string;
  preferred_name: string;
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
}
