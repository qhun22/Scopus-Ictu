# Gate E.2 / P0-B — G02 OpenAlex evidence trust boundary

Date: 2026-10-29 (Asia/Bangkok). Baseline HEAD: `4bb69f6efaac945399b1c191fc12879ad1c62885`; the already accepted, uncommitted G01 changes were preserved. Scope is G02 only. No database query/write, migration, real import, lecturer identity decision or commit/push occurred.

## Result and provenance semantics

The production OpenAlex parser now uses the publication authorship's `raw_author_name` for alignment. Entity ID, entity display name and entity ORCID occupy separate fields; an entity ORCID is not put into the publisher-identifier field. `align_paper()` independently requires both a Crossref context and a Crossref authorship before using the existing publisher ORCID → registry external Scopus ID bridge. Relabeling the context on an OpenAlex object cannot enable that bridge.

| Observation / decision | Before | After |
|---|---|---|
| OpenAlex author name | Entity display name preferred over raw authorship name | Raw authorship name only; missing raw name never falls back to entity |
| OpenAlex ORCID | Entity ORCID could enter identifier proof | Stored only as entity metadata; never independently produces VERIFIED |
| Raw/entity name disagreement | Entity could silently substitute for the publication author | UNRESOLVED / `OPENALEX_ENTITY_NAME_CONFLICT`; raw and entity observations retained separately |
| Missing raw name / missing list | Entity could fill missing raw name | `NO_RAW_AUTHOR_NAME` / `NO_EXTERNAL_AUTHOR_LIST`, distinct from the entity mismatch diagnostic |
| Compatible raw authorship | Name/position/count or entity bridge | At most CORROBORATED from count + position + raw name; multiple raw affiliations retained |
| Valid publisher identifier chain | Allowed independently of name variant | Preserved for Crossref + registry external-ID proof; publisher name variant alone does not defeat it |
| Provenance on withheld assignment | Could be empty or replaced by withholding metadata | JSON evidence retains source observations and withholding metadata together, without assigning affiliations |
| Resolution replay identity | Raw payload version only | `author-affiliation/2` is included in payload fingerprint and evidence; same-policy replay stays deterministic, changed policy creates a distinct version |

`OPENALEX_ENTITY_NAME_CONFLICT` reports a metadata name discrepancy, not a decision that two real people are different. An untrusted entity discrepancy does not veto an independent Crossref identifier chain. No matching tier or human identity is automatically approved. Registry external identifiers are **not** registry DOI-work claims; this patch does not implement T1–T6 or assert target-slot proof merely because a registry lists a DOI.

## Exact changed files and rationale

| File | Change |
|---|---|
| `backend/app/services/author_affiliation.py` | `ExternalAuthorship` lines 86–97 separates raw/entity fields; parser lines 204–253; `_link()` lines 272–305 retains observations even on unresolved links; `align_paper()` lines 308–388 qualifies publisher proof and distinguishes absent raw name from entity name mismatch. |
| `backend/app/services/affiliation_sources.py` | `build_inputs()` lines 185–384 carries policy version, target Scopus ID/order, external position, raw name/affiliations, entity metadata, publisher ORCID, work/DOI/time and complete source-authorship observations into existing JSON evidence. Unassigned observations survive count/identifier mismatch without being treated as assigned authorships. |
| `backend/app/services/affiliation_import.py` | `apply_cross_source_policy()` lines 150–181 preserves the original evidence dictionary when adding withholding metadata. Existing ORM JSON persistence is reused; no schema/migration change. |
| `backend/tests/unit/test_author_affiliation.py` | Adds 14 parametrized trust-boundary cases using production parsers/alignment. Existing intended identifier-positive fixtures now explicitly use Crossref, rather than relying on unsafe OpenAlex entity proof. Raw OpenAlex fixture names are explicit. |
| `backend/tests/unit/test_affiliation_provenance.py` | New: 8 cases covering builder provenance, independent publisher support beside entity conflict, unassigned observations, withholding preservation, deterministic policy-version fingerprints and real importer planning/apply against a fake session. |
| `backend/tests/integration/test_import_author_affiliations_cli.py` | Synthetic raw names added; an entity-derived VERIFIED expectation corrected to raw-authorship CORROBORATED. Four proven file-only helper tests executed individually; CLI main/DB paths not executed. |
| `backend/tests/integration/test_affiliation_workflow_api.py` | Synthetic raw names and expected CORROBORATED status adjusted. This DB/HTTP module was inspected and updated, **NOT_EXECUTED**. |

## Actual validation

- Pre-change regression class: **9 FAIL / 5 PASS** (14 cases). Besides missing new provenance fields, failures directly reproduced VERIFIED from an OpenAlex object and VERIFIED despite missing raw authorship name. The captured output is in `G02_TEST_RESULTS.txt`.
- Final: **39 PASS**, exit code 0: 35 unit cases (13 existing + 22 new) and four selected file-only CLI helper cases. This is a different suite from G01's 39 cases; G01 tests were not re-run.
- Final runner disabled conftest/plugin autoload, bytecode/cache writes and socket connections, and confirmed no `app.main`, `app.core.database` or conftest module loaded. All importer sessions were fakes; fixture bundles contained synthetic records only.
- Initial sandbox runs hit Windows permission errors while creating/cleaning synthetic temporary fixtures, not application assertion failures. The successful final run used approved execution outside the sandbox, a fresh workspace-contained temporary path, the same network/module restrictions and no DB fixtures. Exact command/output is preserved in the log.
- Scoped `git diff --check`: **PASS**. Ruff comparison: **zero new diagnostics**. Whole-file lint remains non-clean: 123 baseline diagnostics across the touched existing files (127 before); the new test module is Ruff-clean. No unrelated bulk lint cleanup was performed.

The fake persistence test runs the real builder, alignment, cross-source policy, importer planner and importer apply, then checks produced ORM evidence and JSON round-trip. It proves the application boundary, not actual PostgreSQL transactions or persisted production state.

## Limits and later verification

Existing stored OpenAlex VERIFIED resolutions are **not rewritten or revoked**. New policy fingerprints distinguish future recomputation from old results; owner approval is required before any real enrichment/apply. Existing cached survey JSONL that asserts unsafe VERIFIED results can intentionally fail the current raw-metadata cross-check and require regeneration. No real bundle was altered here.

Database-backed HTTP/CLI workflows, SQL constraints/concurrency, live data impact and browser rendering remain unexecuted. Existing API evidence fields are reused, and new reason codes may use frontend fallback labels; frontend source was not changed. Complete source-authorship observations increase evidence payload size; production storage volume was not benchmarked. Generic typed importer inputs remain an internal trusted-producer interface; source qualification is enforced in the production parser/alignment path, not a new public authorization mechanism.

G03 author-position replay, G04 rollback behavior and raw source-claim intake remain untouched. No automatic lecturer association or publication deletion was introduced.

## G01 documentation clarification and preservation

`G01_DOCUMENTATION_CLARIFICATION.md` and `G01_CLARIFICATION_VALIDATION.json` explain that the original unchanged backend tree hashes excluded the two modified G01 paths and `__pycache__`. Both subset hashes were reproduced before G02 edits. They are not complete-tree hashes. All five original G01 artifacts, their manifest and the two G01 source/test files remain byte-identical to the accepted version.

G02 validation explicitly records protected-subset exclusions **and separate before/after hashes of all seven changed files**. `G02_IMPLEMENTATION.diff` contains only those seven application/test files, including the new unit module. `G02_MANIFEST.sha256` is separate from the accepted G01 manifest. G02 is ready for independent owner review; stop without starting G03/G04 or real ingestion.
