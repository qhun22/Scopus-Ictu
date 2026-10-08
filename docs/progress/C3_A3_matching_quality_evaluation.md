# C3-A3 — Matching Quality Evaluation

## 1. Summary

Verified evaluation tooling for candidate-retrieval quality against
human-confirmed labels on a primary cohort that was fixed in advance. Phase 1
(this record) delivers the tooling and the committed cohort. No labels exist
yet, so **no metric is reported**. The official evaluation (Phase 2) waits for
human confirmation of all 50 cohort rows.

Authoritative task SHA: see Git commit containing this record and final task
report.

## 2. Frozen Inputs

- A1 SHA: `e502e71fd33eeb93af1fde726b5b1cc5cf0b87f2`
- A2 SHA: `a1e761c21622280845fd9f4958493d4acfe86dde`
- Frozen blobs (verified at A2 SHA and in the working tree at task start):
  - `backend/app/services/matching/candidate_generator.py`:
    `2e98f87d9d2f6b2709c4fd0aa061c7da8046d556`
  - `backend/app/services/matching/publication_evidence_enricher.py`:
    `0c855f9834e271b765ceac57f6c7578ab89ab475`
  - `backend/app/services/matching/candidate_types.py`:
    `57f1a5a7e74fdcbe063fb111b19fd609ccab629a`

Branch `completion3/a3-matching-quality-evaluation`, parent = A2 SHA. Phase-1
files (6, all new): `backend/app/services/matching/verified_evaluation.py`,
`backend/scripts/run_matching_quality_evaluation.py`,
`backend/tests/unit/test_matching_quality_evaluation.py`,
`data/matching/evaluation/README.md`,
`data/matching/evaluation/primary_cohort_source_ids.txt`, and this document.
Production matching changed: false.

## 3. Primary Cohort Protocol

- Algorithm: `SHA256_SEED_RANK_V1`
- Seed: `C3-A3-ICTU-PRIMARY-2026-V1`
- Requested size: 50; selected: 50 (from 410 official lecturers)
- Official lecturer dataset SHA-256:
  - repository content (LF):
    `9428e0a2b009ecff1043b4dc796ed69a0fc64054594b0fb40ffa27bbed4ec82e`
  - Windows `core.autocrlf=true` working tree (CRLF), as hashed at
    generation: `ac4ed2d3f3c5fc7e73912ac9386b5710f4e015bbd7028e5b48a656dae3d4c3d4`
- Primary cohort source-id file SHA-256:
  - as generated and committed (LF):
    `e91babc67ade4413f0378c199a5821f10cba73da73dbbe22bdbec452fc357878`
  - CRLF checkout equivalent:
    `1bd333cf2089ea2ab8dab01b19bd5dfb0fe2cd0a6794bc13de393fcbe531b662`

The cohort was generated with `prepare-cohort` from the official dataset only,
**before any review package was built or any candidate output was generated
or inspected**. 50 lines, 50 unique IDs, all present in the official dataset,
sorted ascending. Its reproducibility from the dataset is unit-tested.

## 4. Human Review Protocol

The A2 package (`candidate_review.csv`, `reference_labeling_sheet.csv`,
`review_manifest.json`) is built from this cohort file with the frozen A2
builder and is never edited. The reviewer copies the blank sheet to
`reference_confirmed.csv` and edits only `decision`, `expected_scopus_id`,
`confirmation_source`, `confirmed_at`, `notes` for all 50 rows.

Suggestions are assistance only. Labels need independent human/external
confirmation. Zero candidates, `NO_CANDIDATE_GENERATED`, and publication
conflicts do not imply `NO_MATCH`. The reviewer may confirm a Scopus ID outside
the candidate list or outside the local corpus (reported as corpus-missing).
The review is assisted, not fully blinded; a blinded independent search
would be stronger. See `data/matching/evaluation/README.md`.

## 5. Provenance Gates

All gates fail closed and run before any database connection:

- strict manifest parse
- package file hashes
- dataset hash
- source-id hash, which must equal both the manifest value (never null) and
  the committed cohort
- `selected_lecturer_count == 50`
- cohort lines equal the recomputed selection
- frozen code blobs at the A2 SHA and in the working tree (`git`, no shell)
- six rule-set ID/version values equal the current `candidate_persistence`
  constants
- the original blank sheet is untouched
- confirmed identity columns are unchanged
- all 50 labels are complete and valid under the frozen A1 parser and the
  dataset cross-check

Database gate: `prod` refused; the database must be named `scopus_m12_test`
(never printed); `SET TRANSACTION READ ONLY` fail-closed; database errors
redacted; engine disposed.

## 6. Evaluation Contract

The frozen A1 path is used unchanged (`resolve_lecturers_from_db`,
`load_scopus_corpus_ids`, `generate_pairs_from_current_production`,
`evaluate_candidate_retrieval`). A1 metrics only. No ranking, scoring,
thresholds, or tuning. The safe result contains no `confirmation_source`,
notes, reviewer data, internal UUIDs, or database information.

## 7. Validation Performed

Local, Phase 1:

- `test_matching_quality_evaluation.py`: 79 passed
- Further regression results are recorded in the final task report.

## 8. CI Evidence

NOT_AVAILABLE_AT_COMMIT_TIME

## 9. Human/Data Gate

- A2 review package: NOT_GENERATED_OR_NOT_VERIFIED
- Human-confirmed reference: NOT_AVAILABLE
- Official evaluation: NOT_RUN

No results are reported.

## 10. Safety

- Acceptance mutation: NONE
- Raw confirmed reference committed: false
- Production matching changed: false
- Migration: false
- Frontend: false

## 11. Limitations

- Assisted human review may introduce incorporation bias.
- Independent confirmation is required for every label.
- The primary n = 50 sample is reproducible but is not a high-precision
  estimate for the entire 410-lecturer population.
- No ranking evaluation.
- No algorithm tuning in this slice.
- File SHA-256 values depend on line endings (Git `autocrlf`). Build and
  evaluate from the same checkout.

## 12. Next Gate

Human confirmation of every primary-cohort row (50/50), from an A2 package
built against the approved `scopus_m12_test` database with this cohort file.
