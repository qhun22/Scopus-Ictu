# Gate E.1 — As-is architecture

Audit date: 2026-10-29 (Asia/Bangkok). Baseline HEAD: `4bb69f6efaac945399b1c191fc12879ad1c62885`.
Scope: static code audit, test inspection, read-only local source inventory and synthetic in-memory probes. No application/database writes, migrations, imports, reviews or commits were performed. Only this Gate E.1 documentation package was written.

## Handover and evidence policy

`git status --short` showed pre-existing edits in three research files and Gate D.2 evidence, and untracked Gate D.3/D.4 artifacts. `docs/qa/gate_e1/` did not exist: there was no Claude draft to overwrite. The research files and evidence were preserved. The prior independent import audit was reused, then challenged against the remaining code.

Authority order: the current R-01…R-12 matrix in `docs/qa/gate_d3/mission/cumulative/research_to_system_traceability.csv`, corrected by E12–E16; current R-13…R-18 in `docs/qa/gate_d4/cumulative/research_to_system_traceability.csv`, corrected by E17–E19; current `docs/research/01_RESEARCH_KNOWLEDGE.md`, `02_ICTU_DATA_FINDINGS.md`, `03_THESIS_DEFENSE_NOTES.md`. Historical prose in those files is not automatically current. In particular R-10's phrase “stronger evidence” is constrained by R-13: registry DOI membership alone never verifies the target slot. Research acceptance is supplied by the owner; this audit does not re-adjudicate Gate D.

Classifications mean: IMPLEMENTED = the entire stated invariant exists in inspected code; PARTIAL = some clauses exist; MISSING = the required application capability was not found in the traced paths; DEFECT_CONFIRMED = a concrete unsafe code path is identified, not proof that live data is corrupt; NOT_VERIFIABLE = requires unavailable runtime evidence. Existing tests are NOT_EXECUTED unless explicitly called an in-memory probe.

## Actual application boundaries

| Boundary | Actual implementation and evidence | What it does not establish |
|---|---|---|
| Lecturer JSON upload | `backend/app/api/v1/endpoints/lecturers.py:1110-1143`, `import_lecturer_dataset()` → `LecturerImportService.import_dataset()` in `backend/app/services/lecturer_dataset/importer.py:558-760` | Not a generic Craw/raw source-claim importer |
| Structured validation | `backend/app/services/lecturer_dataset/parser.py:127-375`, `parse_and_validate()` | Allowlisted normalized output, not lossless raw capture |
| Craw publications | `backend/scripts/ingest_craw_known_publications.py:81-141`, `build_sources()`; `backend/app/services/lecturer_dataset/known_publication_ingestion.py:537-687`, `apply()` | Requires existing lecturers; only profiles referenced by publication links are selected |
| Web Craw orchestration | `backend/app/services/lecturer_dataset/craw_ingestion_workflow.py:81-177`, preview fingerprint, advisory lock and apply | Does not create a 410-profile roster or typed Scopus claims |
| Scopus CSV | `backend/app/api/v1/endpoints/imports.py:54-129`, upload → `backend/app/services/scopus_import_service.py:119-190`, job creation and batch parsing | Raw ingestion and normalization are separate durable phases, not one all-file atomic transaction |
| Publications | `backend/app/services/normalization/scopus_normalizer.py:517-606`, `normalize_single_raw()` | EID reuse does not prove correct person attribution |
| Scopus authors | `backend/app/services/normalization/scopus_author_normalizer.py:137-276`, `parse_author_occurrences()`; `330-373`, `record_occurrences()` | Creating a Scopus author does not approve a lecturer association |
| Candidate retrieval | `backend/app/services/matching/candidate_generator.py:207-324`, `generate_candidates()` / `generate_all()` | String retrieval rules, not a working weighted identity scorer |
| Publication-assisted retrieval | `backend/app/services/matching/generation_workflow.py:113-149`, `build_candidates()` → enrichment and Craw discovery | Does not consume the Gate D identity evidence tiers or source-ID inventories |
| Candidate persistence | `backend/app/services/matching/candidate_persistence.py:494-604`, observations, descriptors and pair roots | New observations do not reopen accepted/rejected roots |
| Human acceptance | `backend/app/api/v1/endpoints/reviews.py:578-633`; `backend/app/services/candidate_review_service.py:547-790` | ACCEPT creates APPROVED identity; no automatic canonical linking |
| Affiliation | `backend/app/services/author_affiliation.py:194-344`; `backend/app/services/affiliation_sources.py:184-344`; `backend/app/services/affiliation_import.py:248-319` | Separate author-slot reconciliation, not lecturer identity acceptance or registry DOI-work verification |
| Read projections | `backend/app/services/lecturer_scopus_projection.py:305-329`; `backend/app/services/publication_queries.py:263-292`; `backend/app/services/dashboard_queries.py:30-83` | Lecturer association currently propagates to every publication of an approved ID; dashboard counts the local corpus, not a proven ICTU-only universe |

The `import_pipeline` orchestrator/apply classes and `matching/engine.py`, `matching/scoring.py`, `matching/rules/orcid_rule.py`, `review_service.py` contain scaffolds. They are not the active implementations just because architecture prose names them: `backend/app/services/import_pipeline/orchestrator.py:18-23`, `backend/app/services/import_pipeline/apply_service.py:12-17`, `backend/app/services/matching/engine.py:22-26`, `backend/app/services/matching/scoring.py:36-40`, `backend/app/services/matching/rules/orcid_rule.py:4-8`, `backend/app/services/review_service.py:6-17`.

## Model, constraint and migration inventory

| Data | Declared protections | Limit |
|---|---|---|
| Lecturer | versioning; staff-code and canonical ORCID partial unique indexes | Email is nonunique; repository URL has no unique constraint. Canonical ORCID has no reviewer-verification field. `backend/app/models/master_lecturer.py:39-117` |
| Source snapshot / known publication | JSON payload/hash, validation fields; publication's composite FK binds snapshot and lecturer | Generic snapshot storage can hold duplicate raw ORCID claims, but there is no normalized raw claim/withdrawal lifecycle. `backend/app/models/master_lecturer.py:123-204`, `210-276` |
| Publication / provenance | unique EID; nullable nonunique DOI; raw-to-publication provenance | No reviewed per-lecturer publication exclusion relation in inspected models/queries. `backend/app/models/publication.py:39-150` |
| Author / authorship | unique external Scopus ID; `(publication, author)` and `(publication, author_order)` unique | Position drift on an existing pair is ignored in normalization. `backend/app/models/publication.py:157-182`, `245-293` |
| Candidate | pair uniqueness, version, statuses PENDING/ACCEPTED/REJECTED/SUPERSEDED; observations per run; evidence fingerprint | No typed source claims or persistent conflict observations. `backend/app/models/candidate.py:83-240` |
| Canonical identity | unique lecturer/author pair; partial unique approved author ownership | One lecturer may own many approved IDs. `backend/app/models/identity.py:40-133` |
| Evidence / reviews | JSON evidence, fingerprints, decision snapshot; MappingReview transition checks and CandidateReview action checks | A check on a review row is not a DB trigger enforcing aggregate transitions. Enum existence does not implement REVOKE/REOPEN. `backend/app/models/identity.py:139-312`, `backend/app/models/candidate.py:243-317` |
| Affiliation | per-author-row/source/payload resolution versions and separate multiple affiliation entries | VERIFIED here describes an external author bridge, not a canonical lecturer approval. `backend/app/models/affiliation.py:104-178`, `190-236` |
| Audit | actor type/user/service consistency and structured snapshots | Application append conventions are not proof of database-enforced immutability. `backend/app/models/governance.py:200-295` |

Migration declarations were inspected, not executed: initial schema `backend/alembic/versions/e5b3cf21c1d12b64_0001_initial_schema.py:119-136` (ORCID), `462-480` (EID), `650-664` (authorship), `748-760` (approved ownership); candidate tables `backend/alembic/versions/b27c9d1e4f60_m2_7b2_candidate_persistence.py:80-140`, `245-312`; duplicate lecturer email change `backend/alembic/versions/c3f0b9a18d42_allow_duplicate_lecturer_emails.py:1-40`. Applied revision, external triggers, DB privileges and actual data are NOT_VERIFIABLE without a separate runtime audit.

## Transactions and governance

- Structured lecturer import commits master changes, snapshots, publications and audit together, rolling back SQLAlchemy errors (`importer.py:589-766` under the full path above).
- CSV ingestion commits lifecycle and batches independently. Publication creation uses a nested savepoint for EID races (`scopus_normalizer.py:560-597`). Author normalization instead calls whole-session rollback inside integrity-error recovery; see defect G04.
- Candidate persistence uses pair insert-or-ignore and row locks; human review locks the candidate, validates version/current completed observation, enforces one approved owner and commits decision/identity/evidence/audit once (`candidate_review_service.py:547-790`). Database-backed concurrency tests exist but were not run.
- Affiliation web apply includes its audit in the import transaction: `backend/app/services/affiliation_workflow.py:138-199`. Craw web apply commits data before its success audit: `craw_ingestion_workflow.py:133-176`; a success-audit failure can leave applied data without that event. Treat this as a known transaction-boundary gap, not proof of observed audit loss.
- Authorization checks the persisted active user and session version, then server-side role: `backend/app/api/dependencies.py:87-138`, `170-187`. Import/matching are ADMIN-only; reviews allow ADMIN/REVIEWER; lecturer self-service resolves the account-linked lecturer. `backend/app/api/v1/endpoints/lecturer_scopus.py:28-55`. No privilege bypass was confirmed in inspected routes; this is not a penetration test.

## Frontend integration

`frontend/src/App.tsx:74-115` gates academic lookup, lecturer, review and ADMIN routes. `frontend/src/pages/ApprovalQueue/index.tsx:378-439` submits only ACCEPT/REJECT with observation/version/reason and handles stale-state conflicts. `frontend/src/types/review.ts:3-4`, `71-128` has name/publication evidence, not typed research counter-evidence or T1–T6. REOPEN appears in history vocabulary, not a functioning write action.

The UI already separates approved identity from evidence basis (`frontend/src/pages/Publications/LinkEvidence.tsx:7-60`), lists approved identities (`frontend/src/pages/Identity/index.tsx:92-110`) and labels personal publications as derived from approved identities (`frontend/src/pages/MyPublications/index.tsx:48-64`). It cannot display source-listed IDs that never entered a claim store. Affiliation UI distinguishes VERIFIED/CORROBORATED/UNRESOLVED, includes sources and reasons, but its “Identity verified” label inherits the unsafe aggregator bridge (`frontend/src/pages/Publications/AuthorAffiliations.tsx:10-92`). No browser session or frontend build/test was run; `frontend/package.json` defines no test runner.

## Limits and corrections to the earlier audit

The earlier audit did not locate the local Craw file. This continuation found it through `CRAW_SOURCE_DIR`, read it without importing, and confirmed 410 records and SHA-256 `c12252e02cbf73c58ae3add65a5b6b925f5e0fcd75273bd7e0a3cc28c8a0accb`. It contains 10 duplicated ORCID values on 20 profiles, 106 profiles with raw publication URLs, and a separate link file with 328 rows covering 48 lecturer profiles. This establishes source availability, not DB population. The source contains no Scopus-ID field: the 83/69 inventories are separate ICTU-WEB artifacts.

Research prose saying candidate generation never writes, or listing a weighted matcher/revision service as implemented, is narrower or older than current runtime code. Pure retrieval is read-only; generation persistence writes candidate observations; canonical changes still require a reviewer. Research files were not edited.
