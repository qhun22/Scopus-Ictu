# Danh mục ràng buộc CHECK (99)

> **Sinh tự động** từ `pg_get_constraintdef` của DB thật. Nhóm phân loại do `gen_database_assets.py` suy từ tên/biểu thức; giải thích nghiệp vụ của các ràng buộc quan trọng nằm ở `CONSTRAINTS_BUSINESS_RULES.md`.

## Tổng hợp theo nhóm

| Nhóm | Số CHECK |
|---|--:|
| Từ vựng giá trị (enumeration) | 23 |
| Kiểu JSONB (object/array) | 19 |
| Miền giá trị số | 18 |
| Không rỗng | 17 |
| Nhất quán nghiệp vụ giữa các cột | 8 |
| Định dạng SHA-256 | 7 |
| Định dạng chuỗi | 5 |
| Bảng chuyển trạng thái | 2 |
| **Tổng** | **99** |

## Từ vựng giá trị (enumeration) (23)

| Bảng | Tên | Biểu thức (PostgreSQL) |
|---|---|---|
| `audit_events` | `ck_audit_events_actor_type` | `CHECK (((actor_type)::text = ANY ((ARRAY['USER'::character varying, 'SYSTEM'::character varying])::text[])))` |
| `candidate_generation_runs` | `ck_candidate_generation_runs_completion_consistency` | `CHECK (((((status)::text = 'RUNNING'::text) AND (completed_at IS NULL)) OR (((status)::text = ANY ((ARRAY['COMPLETED'::character varying, 'FAILED'::character varying])::text[])) AND (completed_at IS NOT NULL))))` |
| `candidate_generation_runs` | `ck_candidate_generation_runs_status` | `CHECK (((status)::text = ANY ((ARRAY['RUNNING'::character varying, 'COMPLETED'::character varying, 'FAILED'::character varying])::text[])))` |
| `identity_evidence` | `ck_identity_evidence_direction` | `CHECK (((direction)::text = ANY ((ARRAY['SUPPORTS'::character varying, 'CONTRADICTS'::character varying])::text[])))` |
| `identity_evidence` | `ck_identity_evidence_evidence_type` | `CHECK (((evidence_type)::text = ANY ((ARRAY['APPROVED_ID'::character varying, 'ORCID_EXACT'::character varying, 'DOI_EXACT'::character varying, 'PUBLICATION_OVERLAP'::character varying, 'COAUTHOR_CONFIRMED'::character varying, 'NAME_SIMILARITY'::character varying, 'AFFILIATION_MATCH'::character varying])::text[])))` |
| `lecturer_scopus_candidate_evidence` | `ck_lecturer_scopus_candidate_evidence_evidence_kind` | `CHECK (((evidence_kind)::text = ANY ((ARRAY['NAME'::character varying, 'PUBLICATION'::character varying])::text[])))` |
| `lecturer_scopus_candidate_reviews` | `ck_lecturer_scopus_candidate_reviews_action` | `CHECK (((action)::text = ANY ((ARRAY['ACCEPT'::character varying, 'REJECT'::character varying, 'REOPEN'::character varying])::text[])))` |
| `lecturer_scopus_candidate_reviews` | `ck_lecturer_scopus_candidate_reviews_from_status` | `CHECK (((from_status)::text = ANY ((ARRAY['PENDING'::character varying, 'ACCEPTED'::character varying, 'REJECTED'::character varying, 'SUPERSEDED'::character varying])::text[])))` |
| `lecturer_scopus_candidate_reviews` | `ck_lecturer_scopus_candidate_reviews_to_status` | `CHECK (((to_status)::text = ANY ((ARRAY['PENDING'::character varying, 'ACCEPTED'::character varying, 'REJECTED'::character varying, 'SUPERSEDED'::character varying])::text[])))` |
| `lecturer_scopus_candidates` | `ck_lecturer_scopus_candidates_status` | `CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'ACCEPTED'::character varying, 'REJECTED'::character varying, 'SUPERSEDED'::character varying])::text[])))` |
| `lecturer_scopus_identities` | `ck_lecturer_scopus_identities_recommendation` | `CHECK (((recommendation IS NULL) OR ((recommendation)::text = ANY ((ARRAY['MATCH'::character varying, 'NO_MATCH'::character varying, 'MANUAL_VERIFY'::character varying])::text[]))))` |
| `lecturer_scopus_identities` | `ck_lecturer_scopus_identities_status` | `CHECK (((status)::text = ANY ((ARRAY['CANDIDATE'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'REVOKED'::character varying])::text[])))` |
| `lecturer_source_snapshots` | `ck_lecturer_source_snapshots_validation_status` | `CHECK (((validation_status)::text = ANY ((ARRAY['VALID'::character varying, 'INVALID'::character varying])::text[])))` |
| `mapping_reviews` | `ck_mapping_reviews_action` | `CHECK (((action)::text = ANY ((ARRAY['APPROVE'::character varying, 'REJECT'::character varying, 'REVOKE'::character varying, 'REOPEN'::character varying])::text[])))` |
| `mapping_reviews` | `ck_mapping_reviews_compensates` | `CHECK (((((action)::text = ANY ((ARRAY['APPROVE'::character varying, 'REJECT'::character varying])::text[])) AND (compensates_review_id IS NULL)) OR (((action)::text = ANY ((ARRAY['REVOKE'::character varying, 'REOPEN'::character varying])::text[])) AND (compensates_review_id IS NOT NULL))))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_link_status` | `CHECK (((link_status)::text = ANY ((ARRAY['VERIFIED'::character varying, 'CORROBORATED'::character varying, 'UNRESOLVED'::character varying])::text[])))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_presence` | `CHECK (((((link_status)::text = 'UNRESOLVED'::text) AND (affiliation_presence IS NULL)) OR (((link_status)::text <> 'UNRESOLVED'::text) AND (affiliation_presence IS NOT NULL) AND ((affiliation_presence)::text = ANY ((ARRAY['PRESENT'::character varying, 'ABSENT'::character varying])::text[])))))` |
| `publication_author_affiliations` | `ck_publication_author_affiliations_link_status` | `CHECK (((link_status)::text = ANY ((ARRAY['VERIFIED'::character varying, 'CORROBORATED'::character varying])::text[])))` |
| `raw_scopus_records` | `ck_raw_scopus_records_validation_status` | `CHECK (((validation_status)::text = ANY ((ARRAY['VALID'::character varying, 'INVALID'::character varying])::text[])))` |
| `scopus_author_name_variants` | `ck_scopus_author_name_variants_variant_type` | `CHECK (((variant_type)::text = ANY ((ARRAY['AUTHOR_DISPLAY'::character varying, 'AUTHOR_FULL_NAME'::character varying])::text[])))` |
| `scopus_imports` | `ck_scopus_imports_status` | `CHECK (((status)::text = ANY ((ARRAY['RECEIVED'::character varying, 'PARSING'::character varying, 'VALIDATED'::character varying, 'STAGED'::character varying, 'APPLIED'::character varying, 'FAILED'::character varying, 'CANCELLED'::character varying])::text[])))` |
| `user_notifications` | `ck_user_notifications_notification_type` | `CHECK (((notification_type)::text = ANY ((ARRAY['PROFILE_UPDATED'::character varying, 'ROLE_CHANGED'::character varying, 'ACCOUNT_LOCKED'::character varying, 'ACCOUNT_UNLOCKED'::character varying, 'PASSWORD_RESET'::character varying])::text[])))` |
| `users` | `ck_users_role` | `CHECK (((role)::text = ANY ((ARRAY['ADMIN'::character varying, 'REVIEWER'::character varying, 'LECTURER'::character varying])::text[])))` |

## Kiểu JSONB (object/array) (19)

| Bảng | Tên | Biểu thức (PostgreSQL) |
|---|---|---|
| `audit_events` | `ck_audit_events_after_state_object` | `CHECK (((after_state IS NULL) OR (jsonb_typeof(after_state) = 'object'::text)))` |
| `audit_events` | `ck_audit_events_before_state_object` | `CHECK (((before_state IS NULL) OR (jsonb_typeof(before_state) = 'object'::text)))` |
| `audit_events` | `ck_audit_events_metadata_object` | `CHECK (((metadata IS NULL) OR (jsonb_typeof(metadata) = 'object'::text)))` |
| `candidate_generation_runs` | `ck_candidate_generation_runs_source_state_object` | `CHECK ((jsonb_typeof(source_state) = 'object'::text))` |
| `identity_evidence` | `ck_identity_evidence_features_object` | `CHECK ((jsonb_typeof(features) = 'object'::text))` |
| `identity_evidence` | `ck_identity_evidence_source_refs_array` | `CHECK ((jsonb_typeof(source_refs) = 'array'::text))` |
| `lecturer_scopus_candidate_evidence` | `ck_lecturer_scopus_candidate_evidence_payload_object` | `CHECK ((jsonb_typeof(payload) = 'object'::text))` |
| `lecturer_scopus_candidate_evidence` | `ck_lecturer_scopus_candidate_evidence_source_refs_array` | `CHECK ((jsonb_typeof(source_refs) = 'array'::text))` |
| `lecturer_scopus_candidate_observations` | `ck_lecturer_scopus_candidate_observations_candidate_sna_25cc` | `CHECK ((jsonb_typeof(candidate_snapshot) = 'object'::text))` |
| `lecturer_scopus_candidate_reviews` | `ck_lecturer_scopus_candidate_reviews_evidence_snapshot_object` | `CHECK ((jsonb_typeof(evidence_snapshot) = 'object'::text))` |
| `lecturer_source_snapshots` | `ck_lecturer_source_snapshots_raw_payload_object` | `CHECK ((jsonb_typeof(raw_payload) = 'object'::text))` |
| `lecturer_source_snapshots` | `ck_lecturer_source_snapshots_validation_errors_array` | `CHECK (((validation_errors IS NULL) OR (jsonb_typeof(validation_errors) = 'array'::text)))` |
| `mapping_reviews` | `ck_mapping_reviews_evidence_snapshot_object` | `CHECK ((jsonb_typeof(evidence_snapshot) = 'object'::text))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_evidence_object` | `CHECK ((jsonb_typeof(evidence) = 'object'::text))` |
| `raw_scopus_records` | `ck_raw_scopus_records_raw_payload_object` | `CHECK ((jsonb_typeof(raw_payload) = 'object'::text))` |
| `raw_scopus_records` | `ck_raw_scopus_records_validation_errors_array` | `CHECK (((validation_errors IS NULL) OR (jsonb_typeof(validation_errors) = 'array'::text)))` |
| `scopus_imports` | `ck_scopus_imports_ck_scopus_imports_normalization_summa_5872` | `CHECK (((normalization_summary IS NULL) OR (jsonb_typeof(normalization_summary) = 'object'::text)))` |
| `scopus_imports` | `ck_scopus_imports_error_summary_object` | `CHECK (((error_summary IS NULL) OR (jsonb_typeof(error_summary) = 'object'::text)))` |
| `user_notifications` | `ck_user_notifications_metadata_object` | `CHECK ((jsonb_typeof(metadata) = 'object'::text))` |

## Miền giá trị số (18)

| Bảng | Tên | Biểu thức (PostgreSQL) |
|---|---|---|
| `candidate_generation_runs` | `ck_candidate_generation_runs_version` | `CHECK ((version >= 1))` |
| `identity_evidence` | `ck_identity_evidence_confidence_score` | `CHECK (((confidence_score >= 0.0) AND (confidence_score <= 1.0)))` |
| `lecturer_known_publications` | `ck_lecturer_known_publications_published_year` | `CHECK (((published_year IS NULL) OR ((published_year >= 1000) AND (published_year <= 9999))))` |
| `lecturer_scopus_candidate_reviews` | `ck_lecturer_scopus_candidate_reviews_candidate_version` | `CHECK ((candidate_version >= 1))` |
| `lecturer_scopus_candidates` | `ck_lecturer_scopus_candidates_version` | `CHECK ((version >= 1))` |
| `lecturer_scopus_identities` | `ck_lecturer_scopus_identities_version` | `CHECK ((version >= 1))` |
| `lecturers` | `ck_lecturers_version` | `CHECK ((version >= 1))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_ext_position` | `CHECK (((external_position IS NULL) OR (external_position >= 1)))` |
| `publication_author_affiliations` | `ck_publication_author_affiliations_ord` | `CHECK ((ord >= 1))` |
| `publication_authors` | `ck_publication_authors_author_order` | `CHECK ((author_order >= 1))` |
| `publications` | `ck_publications_cited_by_count` | `CHECK (((cited_by_count IS NULL) OR (cited_by_count >= 0)))` |
| `publications` | `ck_publications_version` | `CHECK ((version >= 1))` |
| `publications` | `ck_publications_year_range` | `CHECK (((year IS NULL) OR ((year >= 1000) AND (year <= 9999))))` |
| `raw_scopus_records` | `ck_raw_scopus_records_row_number` | `CHECK ((row_number >= 1))` |
| `scopus_imports` | `ck_scopus_imports_record_counts` | `CHECK (((total_records >= 0) AND (valid_records >= 0) AND (invalid_records >= 0)))` |
| `scopus_imports` | `ck_scopus_imports_version` | `CHECK ((version >= 1))` |
| `users` | `ck_users_auth_version` | `CHECK ((auth_version >= 1))` |
| `users` | `ck_users_version` | `CHECK ((version >= 1))` |

## Không rỗng (17)

| Bảng | Tên | Biểu thức (PostgreSQL) |
|---|---|---|
| `audit_events` | `ck_audit_events_actor_invariant` | `CHECK (((((actor_type)::text = 'USER'::text) AND (actor_user_id IS NOT NULL) AND (actor_service IS NULL)) OR (((actor_type)::text = 'SYSTEM'::text) AND (actor_user_id IS NULL) AND (actor_service IS NOT NULL) AND (btrim((actor_service)::text) <> ''::text))))` |
| `candidate_generation_runs` | `ck_candidate_generation_runs_rule_set_id_not_empty` | `CHECK ((btrim(rule_set_id) <> ''::text))` |
| `candidate_generation_runs` | `ck_candidate_generation_runs_rule_set_version_not_empty` | `CHECK ((btrim(rule_set_version) <> ''::text))` |
| `lecturer_scopus_candidate_evidence` | `ck_lecturer_scopus_candidate_evidence_rule_id_not_empty` | `CHECK ((btrim(rule_id) <> ''::text))` |
| `lecturer_scopus_candidate_evidence` | `ck_lecturer_scopus_candidate_evidence_rule_version_not_empty` | `CHECK ((btrim(rule_version) <> ''::text))` |
| `lecturer_scopus_candidate_reviews` | `ck_lecturer_scopus_candidate_reviews_reason_required` | `CHECK ((((action)::text = 'ACCEPT'::text) OR ((reason IS NOT NULL) AND (btrim(reason) <> ''::text))))` |
| `mapping_reviews` | `ck_mapping_reviews_reason_required` | `CHECK ((((action)::text = 'APPROVE'::text) OR ((reason IS NOT NULL) AND (btrim(reason) <> ''::text))))` |
| `organizations` | `ck_organizations_display_name` | `CHECK ((btrim(display_name) <> ''::text))` |
| `organizations` | `ck_organizations_source_org_id` | `CHECK (((source_org_id IS NULL) OR (btrim(source_org_id) <> ''::text)))` |
| `organizations` | `ck_organizations_source_system` | `CHECK ((btrim((source_system)::text) <> ''::text))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_reason` | `CHECK (((((link_status)::text = 'UNRESOLVED'::text) = (unresolved_reason IS NOT NULL)) AND ((unresolved_reason IS NULL) OR (btrim((unresolved_reason)::text) <> ''::text))))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_source_system` | `CHECK ((btrim((source_system)::text) <> ''::text))` |
| `publication_author_affiliations` | `ck_publication_author_affiliations_raw_text` | `CHECK ((((raw_index IS NULL) = (raw_affiliation_text IS NULL)) AND ((raw_index IS NULL) OR (raw_index >= 1)) AND ((raw_affiliation_text IS NULL) OR (btrim(raw_affiliation_text) <> ''::text))))` |
| `publications` | `ck_publications_eid_not_empty` | `CHECK ((btrim(eid) <> ''::text))` |
| `scopus_authors` | `ck_scopus_authors_scopus_id_not_empty` | `CHECK ((btrim(scopus_id) <> ''::text))` |
| `users` | `ck_users_display_name_not_empty` | `CHECK ((btrim((display_name)::text) <> ''::text))` |
| `users` | `ck_users_email_not_empty` | `CHECK ((btrim((email)::text) <> ''::text))` |

## Nhất quán nghiệp vụ giữa các cột (8)

| Bảng | Tên | Biểu thức (PostgreSQL) |
|---|---|---|
| `lecturer_scopus_identities` | `ck_lecturer_scopus_identities_recommendation_consistency` | `CHECK ((((recommendation IS NULL) AND (recommendation_algorithm_version IS NULL) AND (recommended_at IS NULL)) OR ((recommendation IS NOT NULL) AND (recommendation_algorithm_version IS NOT NULL) AND (recommended_at IS NOT NULL))))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_link_method` | `CHECK (((((link_status)::text = 'VERIFIED'::text) AND (link_method IS NOT NULL) AND ((link_method)::text = 'ORCID_SCOPUS_ID_BRIDGE'::text)) OR (((link_status)::text = 'CORROBORATED'::text) AND (link_method IS NOT NULL) AND ((link_method)::text = 'POSITION_COUNT_NAME'::text)) OR (((link_status)::text = 'UNRESOLVED'::text) AND (link_method IS NULL))))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_retrieved_at` | `CHECK ((((link_status)::text = 'UNRESOLVED'::text) OR (retrieved_at IS NOT NULL)))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_trusted_position` | `CHECK ((((link_status)::text = 'UNRESOLVED'::text) OR (external_position IS NOT NULL)))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_verified_orcid` | `CHECK ((((link_status)::text <> 'VERIFIED'::text) OR (external_author_orcid IS NOT NULL)))` |
| `publication_author_affiliations` | `ck_publication_author_affiliations_content` | `CHECK (((raw_affiliation_text IS NOT NULL) OR (organization_id IS NOT NULL)))` |
| `user_notifications` | `ck_user_notifications_read_consistency` | `CHECK ((((is_read = false) AND (read_at IS NULL)) OR ((is_read = true) AND (read_at IS NOT NULL))))` |
| `users` | `ck_users_lecturer_account_required` | `CHECK ((((role)::text <> 'LECTURER'::text) OR (lecturer_id IS NOT NULL)))` |

## Định dạng SHA-256 (7)

| Bảng | Tên | Biểu thức (PostgreSQL) |
|---|---|---|
| `identity_evidence` | `ck_identity_evidence_fingerprint` | `CHECK (((evidence_fingerprint)::text ~ '^[0-9a-f]{64}$'::text))` |
| `lecturer_scopus_candidate_evidence` | `ck_lecturer_scopus_candidate_evidence_evidence_fingerprint` | `CHECK (((evidence_fingerprint)::text ~ '^[0-9a-f]{64}$'::text))` |
| `lecturer_scopus_candidate_observations` | `ck_lecturer_scopus_candidate_observations_observation_hash` | `CHECK (((observation_hash)::text ~ '^[0-9a-f]{64}$'::text))` |
| `lecturer_source_snapshots` | `ck_lecturer_source_snapshots_snapshot_hash` | `CHECK (((snapshot_hash)::text ~ '^[0-9a-f]{64}$'::text))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_payload_hash` | `CHECK (((source_payload_sha256)::text ~ '^[0-9a-f]{64}$'::text))` |
| `raw_scopus_records` | `ck_raw_scopus_records_row_hash` | `CHECK (((row_hash)::text ~ '^[0-9a-f]{64}$'::text))` |
| `scopus_imports` | `ck_scopus_imports_file_sha256` | `CHECK (((file_sha256)::text ~ '^[0-9a-f]{64}$'::text))` |

## Định dạng chuỗi (5)

| Bảng | Tên | Biểu thức (PostgreSQL) |
|---|---|---|
| `audit_events` | `ck_audit_events_action_format` | `CHECK (((action)::text ~ '^[A-Z][A-Z0-9_]*$'::text))` |
| `audit_events` | `ck_audit_events_entity_type_format` | `CHECK (((entity_type)::text ~ '^[a-z][a-z0-9_]*$'::text))` |
| `lecturers` | `ck_lecturers_orcid_format` | `CHECK (((orcid IS NULL) OR ((orcid)::text ~ '^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$'::text)))` |
| `organizations` | `ck_organizations_country_code` | `CHECK (((country_code IS NULL) OR ((country_code)::text ~ '^[A-Z]{2}$'::text)))` |
| `publication_author_affiliation_resolutions` | `ck_publication_author_affiliation_resolutions_orcid_format` | `CHECK (((external_author_orcid IS NULL) OR ((external_author_orcid)::text ~ '^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$'::text)))` |

## Bảng chuyển trạng thái (2)

| Bảng | Tên | Biểu thức (PostgreSQL) |
|---|---|---|
| `lecturer_scopus_candidate_reviews` | `ck_lecturer_scopus_candidate_reviews_transitions` | `CHECK (((((action)::text = 'ACCEPT'::text) AND ((from_status)::text = 'PENDING'::text) AND ((to_status)::text = 'ACCEPTED'::text)) OR (((action)::text = 'REJECT'::text) AND ((from_status)::text = 'PENDING'::text) AND ((to_status)::text = 'REJECTED'::text)) OR (((action)::text = 'REOPEN'::text) AND ((from_status)::text = ANY ((ARRAY['ACCEPTED'::character varying, 'REJECTED'::character varying, 'SUPERSEDED'::character varying])::text[])) AND ((to_status)::text = 'PENDING'::text))))` |
| `mapping_reviews` | `ck_mapping_reviews_transitions` | `CHECK (((((action)::text = 'APPROVE'::text) AND ((from_status)::text = 'CANDIDATE'::text) AND ((to_status)::text = 'APPROVED'::text)) OR (((action)::text = 'REJECT'::text) AND ((from_status)::text = 'CANDIDATE'::text) AND ((to_status)::text = 'REJECTED'::text)) OR (((action)::text = 'REVOKE'::text) AND ((from_status)::text = 'APPROVED'::text) AND ((to_status)::text = 'REVOKED'::text)) OR (((action)::text = 'REOPEN'::text) AND ((from_status)::text = ANY ((ARRAY['REJECTED'::character varying, 'REVOKED'::character varying])::text[])) AND ((to_status)::text = 'CANDIDATE'::text))))` |

