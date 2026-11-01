# Gate E.1 — Import and source-to-canonical identity flow

Read-only continuation, 2026-10-29. Code references are repository-relative paths with inclusive line ranges. Tests mentioned below were inspected, NOT_EXECUTED. In-memory probes are recorded separately in `AUDIT_VALIDATION.json`.

## Source reality versus application state

Read-only inspection found the configured Craw snapshot outside the repository at `D:/DataFolder/ProjectIctu/DoAn/Craw/output/full/lecturers.json`. Its 410 records and SHA-256 match FINDING-001. There are no duplicated source IDs, but 10 ORCIDs occur on 20 profiles. This is permissible source data. The snapshot has no source-listed Scopus-ID field. The separate accepted ICTU-WEB tables contain 34 multi-ID rows (83 IDs), 10 ambiguous rows and 59 unassigned rows. Their availability does not prove any application ingestion occurred.

**Has the system already imported 410 lecturers? NOT_VERIFIABLE.** No DB was queried. A file count, source inventory, mocked test or UI counter is not evidence of deployed import state.

**Can existing workflows safely ingest all source material? Not end-to-end.** The canonical upload requires a different envelope and rejects duplicate ORCIDs. Craw known-publication ingestion is an additive enrichment for existing lecturers, not a roster importer. The 152-ID source inventory lacks a typed ingestion/reconciliation path, especially IDs with no canonical CSV author row and IDs with no lecturer owner.

## Traced route A — structured master data

1. ADMIN uploads to `import_lecturer_dataset()` (`backend/app/api/v1/endpoints/lecturers.py:1110-1143`). It bounds/reads the upload and invokes `LecturerImportService.import_dataset()`.
2. `parse_and_validate()` expects a `{dataset, lecturers}` envelope, validates count/schema, normalizes identity fields, rejects duplicate ORCID claims and constructs a normalized field allowlist (`backend/app/services/lecturer_dataset/parser.py:127-181`, `243-259`, `325-375`). Synthetic `scopus_ids` disappears from that output.
3. `_build_index()` reads canonical lecturer rows and historical source identifiers; `_resolve()` uses source ID, staff code and email, reporting conflicts and avoiding name-only merge (`backend/app/services/lecturer_dataset/importer.py:219-261`, `296-377`). This is lecturer master resolution, not publisher-email identity matching.
4. `import_dataset()` refuses blocking conflicts before writes, creates/updates master data, appends a reconstructed snapshot for every record, deduplicates known publications by title/DOI/year, writes audit and commits (`importer.py:558-760` under the same path).

The upload contract is internally coherent for canonical master data. Dropping unsupported `scopus_ids` is **VERIFIED behavior / integration functionality MISSING**, not automatically a defective implementation of its current contract. In particular the real Craw file does not contain that field. The business problem is the absent separate source-claim path; changing the canonical importer to auto-approve IDs would be unsafe.

The canonical `Lecturer.orcid` is unique, but upload writes it directly without a reviewed ORCID state. Do not describe it as “reviewer-verified” merely because it occupies a canonical column (`backend/app/models/master_lecturer.py:64-65`, `108-113`; importer `614`, `643`). Retain canonical uniqueness; capture raw claims before resolving them.

## Traced route B — actual Craw JSON through review

1. `build_sources()` reads all three local Craw artifacts. It indexes source records and follows `lecturer_publication_links.json`, rejecting unresolved links at the wrapper level. Only lecturers present in those links become service inputs. Their full record and source/link hashes enter raw payload (`backend/scripts/ingest_craw_known_publications.py:81-141`, `174-185`). On the inspected source this selects 48 of 410 profiles, not all 106 with raw publication URLs.
2. `KnownPublicationIngestionService._build_lecturer_index()` maps profile URL to canonical lecturer; `apply()` hashes raw payload and reuses snapshots by hash/lecturer, creates known-publication rows and commits (`backend/app/services/lecturer_dataset/known_publication_ingestion.py:335-378`, `537-687`). Duplicate source ORCID values are not checked here, but no complete 410-profile source staging exists. Duplicate canonical URL mapping is defect G01.
3. Separately, Scopus CSV ingestion preserves row payload/EID/DOI (`backend/app/services/scopus_import_service.py:172-190`, `1365-1392`), normalizes unique EID publications and external authors/positions (`backend/app/services/normalization/scopus_normalizer.py:517-606`; `backend/app/services/normalization/scopus_author_normalizer.py:137-276`, `330-373`). This establishes a canonical publication-author pair, not its lecturer ownership.
4. `build_candidates()` generates names, enriches existing pairs with known publications and discovers additional publication/name-anchored pairs (`backend/app/services/matching/generation_workflow.py:113-149`). `enrich_candidates()` requires the candidate author on the reconciled publication; Craw discovery additionally checks name correspondence (`backend/app/services/matching/publication_evidence_enricher.py:196-246`; `backend/app/services/matching/craw_assisted_discovery.py:307-351`). A shared DOI alone does not automatically create a lecturer identity.
5. `persist_generation()` stores observations/descriptors under a stable pair root. `_get_or_create_root()` does not change existing review status (`backend/app/services/matching/candidate_persistence.py:494-604`). A same-run replay verifies content; a new run appends history.
6. `decide_review_candidate()` delegates ACCEPT/REJECT to `CandidateReviewService`. ACCEPT checks actor, lock, candidate version, current completed observation and ownership; creates APPROVED identity plus promoted evidence, candidate review and audit; commits once (`backend/app/api/v1/endpoints/reviews.py:578-633`; `backend/app/services/candidate_review_service.py:547-790`). REJECT creates no identity (`candidate_review_service.py:900-947`).
7. `LecturerScopusProjectionService._publication_set()` derives distinct publications from approved IDs; there is no per-publication lecturer exclusion (`backend/app/services/lecturer_scopus_projection.py:305-329`). This is the unresolved R-01 concern.

## Eight independent cross-checks

| Hypothesis | Verdict | Test and limitation | Risk / smallest appropriate response |
|---|---|---|---|
| Structured parser ignores `scopus_ids` | VERIFIED behavior; MISSING integration | `backend/tests/unit/test_lecturer_dataset_parser.py:32-51` covers normalization, not claim ingestion; synthetic probe reproduced omission | Add an explicit source-claim contract. Do not reinterpret unsupported fields as reviewer approval. |
| Craw excludes profiles without publication links | VERIFIED; contract-specific | `build_sources()` above; `backend/tests/integration/test_ingest_craw_known_publications_cli.py:138-170` covers publication ingestion replay, not complete roster staging | Preserve every source profile independently; keep linked-publication enrichment. |
| URL `setdefault` can select wrong lecturer | VERIFIED / DEFECT_CONFIRMED G01 | Exact extracted method probe: two canonical rows → first wins. Model has no URL uniqueness (`master_lecturer.py:82-115`); no duplicate-URL regression found | URL→set index, report ambiguity and block affected writes; do not merge records or impose raw URL uniqueness blindly. |
| Regeneration preserves decisions/history, including withdrawal | PARTIAL | `backend/tests/unit/test_candidate_persistence.py:213-233` checks REJECTED root survives a new run; accepted/revoked + source-withdrawal combinations not covered | Preserve decisions; add source-presence observations. Latest completed observation is per candidate, not proof the pair exists in the latest global run (`backend/app/services/candidate_review_queries.py:22-83`). |
| PublicationEvidence freezes position/row ID | REFUTED | Descriptor lacks both (`backend/app/services/matching/candidate_types.py:67-87`); persistence refs use pair (`candidate_persistence.py:317-355`). Existing provenance tests do not assert a frozen slot | Add row ID/order/raw row/name/algorithm to immutable descriptors and reviewer snapshot. |
| ORCID raw claims separated from verified canonical identities | PARTIAL | Raw JSONB can preserve included collisions; structured rejection test `backend/tests/integration/test_lecturer_json_roundtrip.py:238-246` confirms canonical contract | Add all-profile claim capture/collision flags; do not relax canonical uniqueness or choose an ORCID owner automatically. |
| Review API implements REVOKE/REOPEN | REFUTED for canonical identity writes | API action Literal is only ACCEPT/REJECT (`backend/app/schemas/review_api.py:11-25`), legacy service stub (`backend/app/services/review_service.py:6-17`) | Add compensating transitions if required; affiliation-override revocation is a different feature. |
| DOI mismatch/title fallback is intentional and safe | VERIFIED intentional behavior; safety PARTIAL | `backend/tests/unit/test_publication_evidence_enricher.py:95-108` expects differing DOI + same title → TITLE_EXACT; `133-150` blocks DOI/title pointing at two known publications | Preserve title fallback for absent DOI; explicitly retain observed DOI disagreement and show it to reviewer. Policy approval required before making it a hard rejection. |

## Reimport and disappearance semantics

| Route | Same input replay | New snapshot removes claim/publication |
|---|---|---|
| Structured master upload | Reuses master identity and known-publication keys, appends new snapshots/audit even when unchanged (`importer.py:625-675`, `696-760`) | Absent lecturer not deleted/deactivated; known publications remain. Missing canonical ORCID can clear the master field on an included updated record. This is not an ORCID withdrawal history. |
| Craw enrichment | Same content/lecturer snapshot and publication keys reused (`known_publication_ingestion.py:597-609`, `619-689`) | New payload is additive; all historical known publications remain inputs. Full-file hashes embedded in each payload may cause unrelated source changes to create many snapshots. No source-claim tombstones. |
| Candidate generation | Same run ID/content replay checked; new run creates observations without resetting statuses | Missing pair is untouched; prior completed observation remains reviewable. Does not remove/revoke identities or record an explicit withdrawal. |
| CSV normalization | Unique EID/author/links reused; metadata drift reported rather than silently replacing canonical publication | No snapshot-based publication deletion. Author replay has position-drift and integrity-recovery defects G03/G04. |

Thus “idempotent” must state which rows it means. Neither new-run history nor repeated canonical snapshots is a duplicate canonical identity. Source absence must never automatically erase a human decision, but reviewers need to see that support has become historical.

## Decision: extend ingestion infrastructure, add a separate source-claim boundary

Reuse `LecturerSourceSnapshot`, source URL/hash conventions, the existing Craw loader and ADMIN preview/apply pattern. Extend the source loader to preserve the entire roster and parse the separate ICTU-WEB tables into snapshot-linked claim observations. Represent an ID as a string even when no local Scopus-author row or lecturer owner exists. Preserve source group, primary flag, count/source timestamp, raw value, collision and withdrawal observations.

Keep this operationally distinct from canonical master upload and candidate approval. Existing candidates require canonical lecturer/author FKs and only NAME/PUBLICATION descriptors; they cannot safely substitute for raw claims. Materialize candidates only after an explicit, non-approving resolution to existing canonical rows. Avoid an unrelated parallel import framework or a wholesale staging redesign. Proposed schema/API details require design review, not implementation during this gate.
