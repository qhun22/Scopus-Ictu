/** Types exposed by the M2.7B human-review API. */

export type CandidateStatus = "PENDING" | "ACCEPTED" | "REJECTED" | "SUPERSEDED";
export type ReviewAction = "ACCEPT" | "REJECT";
export type EvidenceCategory = "publication-supported" | "name-only";
export type AmbiguityFilter = "ambiguous" | "unique";

export interface ReviewLecturerSummary {
  id: string;
  full_name: string;
}

export interface ReviewAuthorSummary {
  id: string;
  scopus_id: string;
  preferred_name: string;
}

export interface ReviewQueueItem {
  candidate_id: string;
  candidate_status: CandidateStatus;
  candidate_version: number;
  current_observation_id: string;
  lecturer: ReviewLecturerSummary;
  scopus_author: ReviewAuthorSummary;
  name_evidence_count: number;
  publication_evidence_count: number;
  publication_support_count: number;
  candidate_count_for_lecturer: number;
  is_ambiguous: boolean;
  created_at: string;
  updated_at: string;
  last_seen_at: string;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReviewObservation {
  observation_id: string;
  generation_run_id: string;
  generation_run_rule_set_version: string;
  observed_at: string;
  observation_hash: string;
}

export interface ReviewNameEvidence {
  evidence_id: string;
  evidence_kind: "NAME";
  rule_id: string;
  rule_version: string;
  lecturer_source_value: string | null;
  lecturer_comparison_value: string | null;
  scopus_surface_type: string | null;
  scopus_surface_value: string | null;
  scopus_comparison_value: string | null;
  source_refs: unknown[];
  evidence_fingerprint: string;
}

export interface ReviewPublicationEvidence {
  evidence_id: string;
  evidence_kind: "PUBLICATION";
  rule_id: string;
  rule_version: string;
  reconciliation: "DOI_EXACT" | "TITLE_EXACT" | null;
  known_publication_id: string | null;
  lecturer_source_snapshot_id: string | null;
  canonical_publication_id: string | null;
  title: string | null;
  doi: string | null;
  eid: string | null;
  candidate_scopus_author_id: string | null;
  source_refs: unknown[];
  evidence_fingerprint: string;
}

export interface ReviewOtherCandidate {
  candidate_id: string;
  candidate_status: CandidateStatus;
  candidate_version: number;
  scopus_author: ReviewAuthorSummary;
}

export interface ReviewCandidateDetail {
  candidate_id: string;
  candidate_status: CandidateStatus;
  candidate_version: number;
  created_at: string;
  updated_at: string;
  last_seen_at: string;
  lecturer: ReviewLecturerSummary & {
    repository_profile_url: string | null;
    academic_degree: string | null;
    academic_rank: string | null;
  };
  scopus_author: ReviewAuthorSummary & { name_variants: string[] };
  current_observation: ReviewObservation;
  name_evidence: ReviewNameEvidence[];
  publication_evidence: ReviewPublicationEvidence[];
  ambiguity: {
    candidate_count_for_lecturer: number;
    is_ambiguous: boolean;
    other_candidates: ReviewOtherCandidate[];
  };
}

export type ReviewDecisionRequest =
  | {
      observation_id: string;
      candidate_version: number;
      action: "ACCEPT";
      reason?: string;
    }
  | {
      observation_id: string;
      candidate_version: number;
      action: "REJECT";
      reason: string;
    };

export interface ReviewDecisionResponse {
  review_id: string;
  candidate_id: string;
  observation_id: string;
  action: ReviewAction;
  candidate_status: "ACCEPTED" | "REJECTED";
  candidate_version: number;
  resulting_identity_id: string | null;
  idempotent: boolean;
}
