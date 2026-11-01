# Gate E.1 — System integration audit handover

**Date:** 2026-10-29, Asia/Bangkok. **Baseline:** `4bb69f6efaac945399b1c191fc12879ad1c62885`.
**Disposition:** audit complete for owner review; no implementation, real import, identity decision or merge performed. Research Gate D acceptance is inherited, not reopened. This is not permission to import into the current DB.

## Decision

The existing canonical identity and human-review foundation should be retained. **Source-claim ingestion is required to use the 410-profile roster and separate 83/69-ID inventories safely.** Extend existing Craw/snapshot/ADMIN-preview infrastructure with a distinct raw-claim boundary. Do not bypass current master contracts or manufacture canonical candidates for unowned/zero-CSV source IDs.

The 18 requirement rows classify as **12 PARTIAL, 5 MISSING, 1 DEFECT_CONFIRMED**. This grades complete research invariants, not the entire product: many narrower protections are implemented. Four conditional integrity defects G01–G04 are documented; only G02 directly classifies a whole matrix row as DEFECT_CONFIRMED. No live data corruption or privilege exploit is claimed.

## What already works in code

- Multiple approved Scopus IDs per lecturer; only one lecturer can own a given approved author ID. Explicit reviewer acceptance, role checks, reason policy, candidate locks, version/observation checks, decision snapshots and audit records exist.
- Candidate regeneration appends observations and preserves existing review status; same-run replay verifies content. It does not auto-accept or reopen decided roots.
- EID-first unique publications, nullable DOI, full CSV author-list checks, raw lineage, personal publication dedup and multiple affiliation entries exist.
- Frontend separates approved identity links from their evidence basis and exposes name/publication evidence plus stale/ownership conflicts. Affiliation reconciliation is distinct from canonical lecturer approval.

Sources: `backend/app/models/identity.py:115-128`; `backend/app/services/candidate_review_service.py:547-790`; `backend/app/services/matching/candidate_persistence.py:494-604`; `backend/app/services/normalization/scopus_author_normalizer.py:137-276`; `backend/app/services/lecturer_scopus_projection.py:305-329`; `frontend/src/pages/Publications/LinkEvidence.tsx:7-60`.

## First phase: P0 integrity corrections

| Defect | Verified trigger and effect | Priority |
|---|---|---|
| G01 | Duplicate canonical repository URL → first lecturer silently selected by `setdefault`; exact-method probe reproduced selection | P0: block ambiguity before writes |
| G02 | OpenAlex entity name/ORCID → VERIFIED external affiliation through registry external-ID bridge even when raw name differs; pure probe reproduced it | P0: source-qualified proof and separate entity signals |
| G03 | Existing publication/author pair replayed at another position → early return, no drift conflict | P0: compare order, preserve link and report drift |
| G04 | Late author/variant/link IntegrityError → whole-session rollback and continue, without a savepoint/full-batch restart | P0: bounded recovery and durable-counter consistency; DB reproduction still outstanding |

Exact functions/ranges, tests and impacts are in `IDENTITY_EVIDENCE_GAP_ANALYSIS.md`. G02 affects affiliation trust; it does not itself approve a lecturer association. Existing source data triggering G01/G04 was not queried.

## Critical integration gaps

There is no complete source-claim intake with all-profile capture, duplicated ORCID provenance/collision handling, source-primary flags, unowned IDs and withdrawal history. Candidate decision descriptors omit frozen author position/row ID. Publication conflicts are computed but not retained as complete reviewer counter-evidence. The active identity API supports ACCEPT/REJECT, not REVOKE/REOPEN. Approved ID projections include every publication of the ID; per-paper attribution/exclusion is missing. Dashboard totals are deduplicated local corpus totals, not established ICTU-only output. Publisher slot, registry DOI-work, profile and aggregator tiers are not equivalent in current runtime models.

The structured parser dropping `scopus_ids` is verified behavior under its **canonical master-data contract**, not automatically a bug. The real Craw file has no such field; the separate ICTU-WEB inventories must be handled explicitly. DOI-mismatch/title fallback is intentional and tested; its counter-evidence policy needs design review rather than being mislabeled a confirmed bug.

## What was verified locally, and what was not

The configured external Craw file was available and read without import: 410 profiles, checksum `c12252e02cbf73c58ae3add65a5b6b925f5e0fcd75273bd7e0a3cc28c8a0accb`, 10 repeated ORCID values across 20 profiles, zero duplicate source IDs. Of 410 profiles, 106 have raw publication URLs; the separate publication-link file contains 328 rows covering 48 profiles. Current Craw enrichment selects those 48, not all 410. The research tables contain 34/10/59 rows and represent the accepted 83/69 ID inventories; research claims are not reviewer decisions.

**NOT_VERIFIABLE:** whether 410 lecturer masters or 152 claimed IDs were imported in the deployed application; applied migration revision, real duplicates/ownership, transaction race outcomes, immutable DB permissions/triggers and browser UI behavior. No DB connection was made. Existing DB-backed tests are **NOT_EXECUTED**. Eight synthetic in-memory probes passed assertions about current behavior, including confirmed unsafe behavior; they are not a product regression-suite pass.

The original independent audit did not find the external raw snapshot. This continuation located it via configuration and corrected that limitation. No Gate D evidence or research files were changed; their original historical statements were preserved. Superseded R-10/E17/E18/E19 statements were not reused as current conclusions.

## Before importing real ICTU data

Resolve P0 triggers; stage all profiles and ID claims without approvals; run synthetic end-to-end replay/withdrawal/collision/slot/source-tier tests on an explicitly authorized disposable DB; verify current schema and backup/recovery; exercise concurrent ownership and author-normalization error paths; verify UI source/candidate/approved/counter-evidence/count labels. Ingested raw duplicates must survive. An absent registry DOI or unavailable profile must not cause automatic rejection, invalidation or merge.

The first bounded implementation handover is G01 URL ambiguity handling, followed by separate G02/G03/G04 fixes. Source-claim intake follows those protections. Detailed dependencies, policy choices and acceptance criteria are in `IMPLEMENTATION_ROADMAP.md`; no fix is implemented here.

## Deliverables and provenance

1. `AS_IS_ARCHITECTURE.md` — runtime models, active paths, transactions, migrations, auth and frontend.
2. `REQUIREMENT_IMPLEMENTATION_MATRIX.csv` — all R-01…R-18, accepted wording, findings, code/tests, limits, risk and remediation.
3. `IMPORT_DATA_FLOW_AUDIT.md` — complete paths, eight independent cross-checks, reimport/withdrawal behavior and ingestion design.
4. `IDENTITY_EVIDENCE_GAP_ANALYSIS.md` — confirmed defects versus missing/partial capabilities, tiers and UI implications.
5. `TEST_CASE_DESIGN.md` — 23 synthetic cases and existing-test limits.
6. `IMPLEMENTATION_ROADMAP.md` — P0–P3, dependencies, design trade-offs and first-task handover.
7. `EXECUTIVE_SUMMARY.md` — this handover.

Supporting artifacts: `SOURCE_REFERENCES.csv` (source hashes/ranges/symbols), `AUDIT_VALIDATION.json` (method, probes and documentation/source-integrity checks), `DOCUMENTATION_CHANGES.diff` (actual additions against the absent Gate E.1 baseline), `MANIFEST.sha256`, and a documentation ZIP with SHA-256 in a separate `.zip.sha256` file. Package verification is a documentation check, not runtime test execution. Stop for independent owner/ChatGPT review.
