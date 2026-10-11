# Bảng khóa chính, khóa ngoại, duy nhất và chỉ mục

> **Sinh tự động** từ snapshot lược đồ thật (`gen_database_assets.py`). Cardinality suy ra như sau: phía **cha** là `1` nếu cột FK `NOT NULL`, ngược lại `0..1`; phía **con** là `0..1` nếu cột FK là duy nhất (UNIQUE hoặc chỉ mục unique một phần), ngược lại `0..*`.

## 1. Khóa ngoại (30)

| # | Cụm | Bảng con (cột) | → | Bảng cha (cột) | Cardinality (cha : con) | ON DELETE | Tên ràng buộc |
|--:|:-:|---|:-:|---|:-:|---|---|
| 1 | A | `audit_events` (`actor_user_id`) | → | `users` (`id`) | 0..1 : 0..* | RESTRICT | `fk_audit_events_actor_user_id_users` |
| 2 | A | `user_notifications` (`user_id`) | → | `users` (`id`) | 1 : 0..* | RESTRICT | `fk_user_notifications_user_id_users` |
| 3 | A | `users` (`lecturer_id`) | → | `lecturers` (`id`) | 0..1 : 0..1 (UNIQUE một phần) | RESTRICT | `fk_users_lecturer_id_lecturers` |
| 4 | B | `lecturer_known_publications` (`snapshot_id, lecturer_id`) — FK ghép | → | `lecturer_source_snapshots` (`id, lecturer_id`) | 1 : 0..* | RESTRICT | `fk_lecturer_known_publications_snapshot_lecturer` |
| 5 | B | `lecturer_source_snapshots` (`lecturer_id`) | → | `lecturers` (`id`) | 0..1 : 0..* | RESTRICT | `fk_lecturer_source_snapshots_lecturer_id_lecturers` |
| 6 | C | `raw_scopus_records` (`import_id`) | → | `scopus_imports` (`id`) | 1 : 0..* | RESTRICT | `fk_raw_scopus_records_import_id_scopus_imports` |
| 7 | D | `publication_authors` (`publication_id`) | → | `publications` (`id`) | 1 : 0..* | CASCADE | `fk_publication_authors_publication_id_publications` |
| 8 | D | `publication_authors` (`scopus_author_id`) | → | `scopus_authors` (`id`) | 1 : 0..* | RESTRICT | `fk_publication_authors_scopus_author_id_scopus_authors` |
| 9 | D | `publication_raw_sources` (`publication_id`) | → | `publications` (`id`) | 1 : 0..* | RESTRICT | `fk_publication_raw_sources_publication_id_publications` |
| 10 | D | `publication_raw_sources` (`raw_record_id`) | → | `raw_scopus_records` (`id`) | 1 : 0..1 (UNIQUE) | RESTRICT | `fk_publication_raw_sources_raw_record_id_raw_scopus_records` |
| 11 | D | `scopus_author_name_variants` (`first_seen_raw_record_id`) | → | `raw_scopus_records` (`id`) | 1 : 0..* | RESTRICT | `fk_scopus_author_name_variants_first_seen_raw_record_id_d3c5` |
| 12 | D | `scopus_author_name_variants` (`scopus_author_id`) | → | `scopus_authors` (`id`) | 1 : 0..* | RESTRICT | `fk_scopus_author_name_variants_scopus_author_id_scopus_authors` |
| 13 | E | `publication_author_affiliation_resolutions` (`publication_author_id`) | → | `publication_authors` (`id`) | 1 : 0..* | CASCADE | `fk_paar_publication_author_id` |
| 14 | E | `publication_author_affiliations` (`organization_id`) | → | `organizations` (`id`) | 0..1 : 0..* | RESTRICT | `fk_paa_organization_id` |
| 15 | E | `publication_author_affiliations` (`resolution_id, link_status`) — FK ghép | → | `publication_author_affiliation_resolutions` (`id, link_status`) | 1 : 0..* | CASCADE | `fk_paa_resolution_link_status` |
| 16 | F | `identity_evidence` (`identity_id`) | → | `lecturer_scopus_identities` (`id`) | 1 : 0..* | RESTRICT | `fk_identity_evidence_identity_id_lecturer_scopus_identities` |
| 17 | F | `lecturer_scopus_candidate_evidence` (`observation_id`) | → | `lecturer_scopus_candidate_observations` (`id`) | 1 : 0..* | RESTRICT | `fk_lecturer_scopus_candidate_evidence_observation_id_le_d76b` |
| 18 | F | `lecturer_scopus_candidate_observations` (`candidate_id`) | → | `lecturer_scopus_candidates` (`id`) | 1 : 0..* | RESTRICT | `fk_lecturer_scopus_candidate_observations_candidate_id__26b4` |
| 19 | F | `lecturer_scopus_candidate_observations` (`generation_run_id`) | → | `candidate_generation_runs` (`id`) | 1 : 0..* | RESTRICT | `fk_lecturer_scopus_candidate_observations_generation_ru_f0a3` |
| 20 | F | `lecturer_scopus_candidate_reviews` (`candidate_id`) | → | `lecturer_scopus_candidates` (`id`) | 1 : 0..* | RESTRICT | `fk_lecturer_scopus_candidate_reviews_candidate_id_lectu_d610` |
| 21 | F | `lecturer_scopus_candidate_reviews` (`observation_id`) | → | `lecturer_scopus_candidate_observations` (`id`) | 1 : 0..* | RESTRICT | `fk_lecturer_scopus_candidate_reviews_observation_id_lec_05f7` |
| 22 | F | `lecturer_scopus_candidate_reviews` (`resulting_identity_id`) | → | `lecturer_scopus_identities` (`id`) | 0..1 : 0..* | RESTRICT | `fk_lecturer_scopus_candidate_reviews_resulting_identity_a592` |
| 23 | F | `lecturer_scopus_candidate_reviews` (`reviewer_user_id`) | → | `users` (`id`) | 1 : 0..* | RESTRICT | `fk_lecturer_scopus_candidate_reviews_reviewer_user_id_users` |
| 24 | F | `lecturer_scopus_candidates` (`lecturer_id`) | → | `lecturers` (`id`) | 1 : 0..* | RESTRICT | `fk_lecturer_scopus_candidates_lecturer_id_lecturers` |
| 25 | F | `lecturer_scopus_candidates` (`scopus_author_id`) | → | `scopus_authors` (`id`) | 1 : 0..* | RESTRICT | `fk_lecturer_scopus_candidates_scopus_author_id_scopus_authors` |
| 26 | F | `lecturer_scopus_identities` (`lecturer_id`) | → | `lecturers` (`id`) | 1 : 0..* | RESTRICT | `fk_lecturer_scopus_identities_lecturer_id_lecturers` |
| 27 | F | `lecturer_scopus_identities` (`scopus_author_id`) | → | `scopus_authors` (`id`) | 1 : 0..1 (UNIQUE một phần) | RESTRICT | `fk_lecturer_scopus_identities_scopus_author_id_scopus_authors` |
| 28 | F | `mapping_reviews` (`compensates_review_id`) | → | `mapping_reviews` (`id`) | 0..1 : 0..* | RESTRICT | `fk_mapping_reviews_compensates_review_id_mapping_reviews` |
| 29 | F | `mapping_reviews` (`identity_id`) | → | `lecturer_scopus_identities` (`id`) | 1 : 0..* | RESTRICT | `fk_mapping_reviews_identity_id_lecturer_scopus_identities` |
| 30 | F | `mapping_reviews` (`reviewer_user_id`) | → | `users` (`id`) | 1 : 0..* | RESTRICT | `fk_mapping_reviews_reviewer_user_id_users` |

- **ON DELETE CASCADE (3):** `publication_authors` → `publication_author_affiliation_resolutions`; `publication_author_affiliation_resolutions` → `publication_author_affiliations`; `publications` → `publication_authors`. Mọi khóa ngoại còn lại là `RESTRICT`: không thể xóa bản ghi đang được tham chiếu.
- **Khóa ngoại ghép (2):** `lecturer_known_publications(snapshot_id, lecturer_id)` → `lecturer_source_snapshots(id, lecturer_id)`; `publication_author_affiliations(resolution_id, link_status)` → `publication_author_affiliation_resolutions(id, link_status)`.

## 2. Khóa chính (24)

| Bảng | Khóa chính | Tên ràng buộc |
|---|---|---|
| `audit_events` | `id` | `pk_audit_events` |
| `candidate_generation_runs` | `id` | `pk_candidate_generation_runs` |
| `identity_evidence` | `id` | `pk_identity_evidence` |
| `lecturer_known_publications` | `id` | `pk_lecturer_known_publications` |
| `lecturer_scopus_candidate_evidence` | `id` | `pk_lecturer_scopus_candidate_evidence` |
| `lecturer_scopus_candidate_observations` | `id` | `pk_lecturer_scopus_candidate_observations` |
| `lecturer_scopus_candidate_reviews` | `id` | `pk_lecturer_scopus_candidate_reviews` |
| `lecturer_scopus_candidates` | `id` | `pk_lecturer_scopus_candidates` |
| `lecturer_scopus_identities` | `id` | `pk_lecturer_scopus_identities` |
| `lecturer_source_snapshots` | `id` | `pk_lecturer_source_snapshots` |
| `lecturers` | `id` | `pk_lecturers` |
| `mapping_reviews` | `id` | `pk_mapping_reviews` |
| `organizations` | `id` | `pk_organizations` |
| `publication_author_affiliation_resolutions` | `id` | `pk_publication_author_affiliation_resolutions` |
| `publication_author_affiliations` | `id` | `pk_publication_author_affiliations` |
| `publication_authors` | `id` | `pk_publication_authors` |
| `publication_raw_sources` | `id` | `pk_publication_raw_sources` |
| `publications` | `id` | `pk_publications` |
| `raw_scopus_records` | `id` | `pk_raw_scopus_records` |
| `scopus_author_name_variants` | `id` | `pk_scopus_author_name_variants` |
| `scopus_authors` | `id` | `pk_scopus_authors` |
| `scopus_imports` | `id` | `pk_scopus_imports` |
| `user_notifications` | `id` | `pk_user_notifications` |
| `users` | `id` | `pk_users` |

## 3. Ràng buộc UNIQUE (16)

| Bảng | Tên | Cột | Ý nghĩa chống trùng |
|---|---|---|---|
| `identity_evidence` | `uq_identity_evidence_dedup` | `identity_id, evidence_type, algorithm_version, evidence_fingerprint` | Không lưu trùng bằng chứng của cùng một danh tính. |
| `lecturer_scopus_candidate_evidence` | `uq_candidate_evidence_descriptor` | `observation_id, rule_id, rule_version, evidence_fingerprint` | Cùng một bằng chứng (luật, phiên bản, dấu vân tay) không lưu hai lần trong một quan sát. |
| `lecturer_scopus_candidate_observations` | `uq_candidate_observations_candidate_run` | `candidate_id, generation_run_id` | Mỗi ứng viên chỉ có một quan sát trong một lần chạy. |
| `lecturer_scopus_candidates` | `uq_lecturer_scopus_candidates_pair` | `lecturer_id, scopus_author_id` | Mỗi cặp (giảng viên, tác giả Scopus) chỉ là một ứng viên. |
| `lecturer_scopus_identities` | `uq_lecturer_scopus_identities_pair` | `lecturer_id, scopus_author_id` | Mỗi cặp (giảng viên, tác giả Scopus) chỉ có một danh tính. |
| `lecturer_source_snapshots` | `uq_lecturer_source_snapshots_id_lecturer` | `id, lecturer_id` | Khóa ứng viên ghép (id, lecturer_id) để làm đích cho FK ghép của công bố đã biết. |
| `publication_author_affiliation_resolutions` | `uq_paar_author_source_payload` | `publication_author_id, source_system, source_payload_sha256` | Cùng vị trí tác giả + nguồn + payload (SHA-256) chỉ nạp một lần (nhập lại không trùng). |
| `publication_author_affiliation_resolutions` | `uq_paar_id_link_status` | `id, link_status` | Khóa ứng viên ghép (id, link_status) làm đích cho FK ghép của dòng đơn vị. |
| `publication_author_affiliations` | `uq_paa_resolution_ord` | `resolution_id, ord` | Thứ tự đơn vị là duy nhất trong một resolution. |
| `publication_authors` | `uq_publication_authors_author` | `publication_id, scopus_author_id` | Một tác giả chỉ xuất hiện một lần trong một công bố. |
| `publication_authors` | `uq_publication_authors_order` | `publication_id, author_order` | Mỗi thứ tự tác giả trong công bố chỉ thuộc một người. |
| `publication_raw_sources` | `uq_publication_raw_sources_raw_record_id` | `raw_record_id` | Mỗi dòng thô chỉ dẫn tới tối đa một công bố (provenance 1–1 phía dòng thô). |
| `publications` | `uq_publications_eid` | `eid` | Mỗi EID chỉ một công bố chuẩn hóa — chốt chặn chống trùng công bố. |
| `raw_scopus_records` | `uq_raw_scopus_records_import_row` | `import_id, row_number` | Mỗi số dòng chỉ xuất hiện một lần trong một đợt nhập. |
| `scopus_author_name_variants` | `uq_author_name_variants` | `scopus_author_id, variant_type, variant_name` | Một dạng tên chỉ lưu một lần cho mỗi tác giả. |
| `scopus_authors` | `uq_scopus_authors_scopus_id` | `scopus_id` | Mỗi Scopus Author ID chỉ một tác giả. |

## 4. Chỉ mục UNIQUE một phần (partial) (7)

| Bảng | Tên | Biểu thức/cột | Điều kiện | Ý nghĩa |
|---|---|---|---|---|
| `lecturer_scopus_identities` | `uq_identities_scopus_author_approved` | `scopus_author_id` | `((status)::text = 'APPROVED'::text)` | **Một Scopus Author ID chỉ được APPROVED cho đúng một giảng viên** — chặn gán trùng ở mức DB. |
| `lecturers` | `uq_lecturers_orcid` | `orcid` | `(orcid IS NOT NULL)` | ORCID duy nhất khi có. |
| `lecturers` | `uq_lecturers_staff_code` | `staff_code` | `(staff_code IS NOT NULL)` | Mã cán bộ duy nhất khi có. |
| `organizations` | `uq_organizations_source_name` | `source_system, display_name` | `(source_org_id IS NULL)` | Tổ chức không có mã nguồn thì duy nhất theo (nguồn, tên). |
| `organizations` | `uq_organizations_source_org` | `source_system, source_org_id` | `(source_org_id IS NOT NULL)` | Tổ chức có mã nguồn thì duy nhất theo (nguồn, mã). |
| `users` | `uq_users_email_ci` | `lower((email)::text)` | `None` | Email tài khoản duy nhất, không phân biệt hoa/thường. |
| `users` | `uq_users_lecturer` | `lecturer_id` | `(lecturer_id IS NOT NULL)` | Mỗi hồ sơ giảng viên tối đa một tài khoản (quan hệ 0..1). |

## 5. Chỉ mục thường (45)

| Bảng | Tên | Cột/biểu thức | Điều kiện (partial) |
|---|---|---|---|
| `audit_events` | `ix_audit_events_actor` | `actor_user_id, created_at` |  |
| `audit_events` | `ix_audit_events_correlation` | `correlation_id` | `(correlation_id IS NOT NULL)` |
| `audit_events` | `ix_audit_events_created` | `created_at` |  |
| `audit_events` | `ix_audit_events_entity` | `entity_type, entity_id, created_at` |  |
| `candidate_generation_runs` | `ix_candidate_generation_runs_status_created` | `status, created_at` |  |
| `identity_evidence` | `ix_identity_evidence_created_at` | `created_at` |  |
| `lecturer_known_publications` | `ix_known_pubs_lecturer_year` | `lecturer_id, published_year` |  |
| `lecturer_known_publications` | `ix_lecturer_known_publications_doi` | `doi_normalized` | `(doi_normalized IS NOT NULL)` |
| `lecturer_known_publications` | `ix_lecturer_known_publications_lecturer_id` | `lecturer_id` |  |
| `lecturer_known_publications` | `ix_lecturer_known_publications_snapshot_id` | `snapshot_id` |  |
| `lecturer_scopus_candidate_evidence` | `ix_candidate_evidence_observation` | `observation_id, created_at` |  |
| `lecturer_scopus_candidate_observations` | `ix_candidate_observations_candidate` | `candidate_id, created_at` |  |
| `lecturer_scopus_candidate_observations` | `ix_candidate_observations_run` | `generation_run_id` |  |
| `lecturer_scopus_candidate_reviews` | `ix_candidate_reviews_candidate_created` | `candidate_id, created_at` |  |
| `lecturer_scopus_candidate_reviews` | `ix_candidate_reviews_observation` | `observation_id` |  |
| `lecturer_scopus_candidate_reviews` | `ix_candidate_reviews_reviewer` | `reviewer_user_id` |  |
| `lecturer_scopus_candidates` | `ix_lecturer_scopus_candidates_lecturer` | `lecturer_id` |  |
| `lecturer_scopus_candidates` | `ix_lecturer_scopus_candidates_scopus_author` | `scopus_author_id` |  |
| `lecturer_scopus_candidates` | `ix_lecturer_scopus_candidates_status_updated` | `status, updated_at` |  |
| `lecturer_scopus_identities` | `ix_identities_scopus_author_id` | `scopus_author_id` |  |
| `lecturer_scopus_identities` | `ix_identities_status_updated` | `status, updated_at` |  |
| `lecturer_source_snapshots` | `ix_lecturer_source_snapshots_lecturer_id` | `lecturer_id` |  |
| `lecturer_source_snapshots` | `ix_snapshots_source_lookup` | `source_system, source_url, fetched_at` |  |
| `lecturers` | `ix_lecturers_email_ci` | `lower((email)::text)` | `(email IS NOT NULL)` |
| `lecturers` | `ix_lecturers_full_name_normalized` | `full_name_normalized` |  |
| `mapping_reviews` | `ix_mapping_reviews_compensates` | `compensates_review_id` | `(compensates_review_id IS NOT NULL)` |
| `mapping_reviews` | `ix_mapping_reviews_identity_id` | `identity_id` |  |
| `mapping_reviews` | `ix_mapping_reviews_reviewer` | `reviewer_user_id` |  |
| `organizations` | `ix_organizations_ror` | `ror` |  |
| `publication_author_affiliation_resolutions` | `ix_paar_publication_author` | `publication_author_id` |  |
| `publication_author_affiliation_resolutions` | `ix_paar_source_status` | `source_system, link_status` |  |
| `publication_author_affiliations` | `ix_paa_organization_id` | `organization_id` |  |
| `publication_authors` | `ix_publication_authors_scopus_author_id` | `scopus_author_id` |  |
| `publication_raw_sources` | `ix_publication_raw_sources_publication_id` | `publication_id` |  |
| `publications` | `ix_publications_doi` | `doi` | `(doi IS NOT NULL)` |
| `publications` | `ix_publications_year` | `year` |  |
| `raw_scopus_records` | `ix_raw_scopus_records_doi_raw` | `doi_raw` | `(doi_raw IS NOT NULL)` |
| `raw_scopus_records` | `ix_raw_scopus_records_eid_raw` | `eid_raw` | `(eid_raw IS NOT NULL)` |
| `scopus_author_name_variants` | `ix_author_name_variants_normalized` | `variant_name_normalized` |  |
| `scopus_author_name_variants` | `ix_author_name_variants_raw_source` | `first_seen_raw_record_id` |  |
| `scopus_imports` | `ix_scopus_imports_file_sha256` | `file_sha256` |  |
| `scopus_imports` | `ix_scopus_imports_status` | `status` |  |
| `user_notifications` | `ix_user_notifications_created_at` | `created_at` |  |
| `user_notifications` | `ix_user_notifications_unread_lookup` | `user_id, is_read, created_at` |  |
| `user_notifications` | `ix_user_notifications_user_id` | `user_id` |  |

**Lưu ý:** các cột khóa ngoại thường có chỉ mục hỗ trợ truy vấn; một số FK không có chỉ mục riêng vì đã nằm đầu một ràng buộc UNIQUE ghép. Task 19 không đo hiệu năng nên **không khẳng định** bộ chỉ mục là tối ưu.

