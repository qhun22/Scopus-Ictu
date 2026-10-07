/** Global search types — Completion-1 A3. */

export interface LecturerSearchItem {
  full_name: string;
  staff_code: string | null;
  department: string | null;
  faculty: string | null;
  orcid: string | null;
}

export interface PublicationSearchItem {
  eid: string;
  title: string;
  year: number | null;
  source_title: string | null;
  cited_by_count: number | null;
  document_type: string | null;
}

export interface ScopusAuthorSearchItem {
  scopus_id: string;
  preferred_name: string;
}

export interface SearchResponse {
  q: string;
  limit: number;
  lecturers: LecturerSearchItem[];
  publications: PublicationSearchItem[];
  scopus_authors: ScopusAuthorSearchItem[];
}

export interface SearchQuery {
  q: string;
  limit?: number;
}