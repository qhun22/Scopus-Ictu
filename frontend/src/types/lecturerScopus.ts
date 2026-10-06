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
