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

Database gate (as of A3 Commit #1):

- `prod` is refused.
- The configured and the live (`SELECT current_database()`) database must
  both be exactly `scopus_c3_eval_v1`. The name is never printed.
- A `REPEATABLE READ READ ONLY` snapshot transaction is fail-closed.
- The input fingerprint must equal the pinned value; it is UNPINNED in
  Commit #1, so evaluation is refused.
- Database errors are redacted and the engine is disposed.

## 6. Evaluation Contract

The frozen A1 path is used unchanged (`resolve_lecturers_from_db`,
`load_scopus_corpus_ids`, `generate_pairs_from_current_production`,
`evaluate_candidate_retrieval`). A1 metrics only. No ranking, scoring,
thresholds, or tuning. The safe result contains no `confirmation_source`,
notes, reviewer data, internal UUIDs, or database information.

## 7. Validation Performed

Local, Phase 1:

- `test_matching_quality_evaluation.py`: 79 passed at the initial Phase-1
  commit; 92 passed after the frozen-dataset correction
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

## Phase-1 Audit Correction — Frozen Dataset Snapshot

- Initial Phase-1 tooling SHA: `387aea002115d45a671f153f9623c9bf11b86d76`
  (historical exact-head CI run 37715869332; historical evidence only).
- Independent review classification:
  - line-ending dual representation: NON_BLOCKING
  - current worktree cohort binding: NON_BLOCKING
  - official dataset Phase-1 snapshot binding: SHOULD_FIX_BEFORE_HUMAN_REVIEW
- Reason: a later dataset revision could keep the same 50 source IDs while
  changing names or emails. An A2 package built from it would be internally
  consistent but would not represent the snapshot the cohort was fixed on.
- Final correction contract:
  - Only the exact Phase-1 dataset hashes are accepted, in two byte forms:
    LF `9428e0a2b009ecff1043b4dc796ed69a0fc64054594b0fb40ffa27bbed4ec82e` and
    CRLF `ac4ed2d3f3c5fc7e73912ac9386b5710f4e015bbd7028e5b48a656dae3d4c3d4`.
    Any third hash fails closed, in both `prepare-cohort` and `evaluate`.
  - The A2 manifest still binds the exact bytes actually used for review. An
    LF/CRLF mismatch between the dataset and the manifest is rejected.
  - Sampling algorithm, seed, size, and the committed cohort file are
    unchanged. Matching production code is unchanged.
  - No `.gitattributes`, no line-ending normalization, no Git config change.
- Status at this correction: human review has NOT started, the A2 review
  package has NOT been generated, and the official evaluation has NOT run.

Final corrected Phase-1 SHA: see Git commit containing this record and final
Phase-1 audit report.

New corrected CI: NOT_AVAILABLE_AT_COMMIT_TIME.

## A3 Commit #1 — Evaluation Database Guard and Input Fingerprint

Reason: `scopus_m12_test` turned out to be a pytest scratch database, with 1
lecturer, 1 Scopus author and 22 publications. The frozen A2 builder failed
closed: 50 of 50 cohort lecturers were unresolved. Decision (Option 3): use a
dedicated evaluation database `scopus_c3_eval_v1`, created by Alembic and
selectively copied from read-only acceptance. That is a separate operational
step, not performed here.

Verified from models and the initial Alembic migration:

- **Primary keys.** All 9 tables have a UUID PK `id`.
- **Foreign keys.** The only required parents are
  `raw_scopus_records.import_id → scopus_imports.id` and
  `scopus_author_name_variants.first_seen_raw_record_id` (NOT NULL) →
  `raw_scopus_records.id`. `scopus_imports` has no FK, and none of the 9
  tables references `users`.
- **Other constraints.**
  - Composite FK
    `lecturer_known_publications(snapshot_id, lecturer_id) →
    lecturer_source_snapshots(id, lecturer_id)`.
  - Unique constraints: `publications.eid`, `scopus_authors.scopus_id`,
    `scopus_author_name_variants(scopus_author_id, variant_type,
    variant_name)`, `publication_authors(publication_id, author_order)` and
    `(publication_id, scopus_author_id)`,
    `raw_scopus_records(import_id, row_number)`.
- **`publication_raw_sources`** is not read by the generator or enricher, so
  it is excluded.

Changes:

- The approved database is `scopus_c3_eval_v1`. `scopus_m12_test` and the
  acceptance DB are explicitly rejected.
- The live-connection `current_database()` check was added.
- The snapshot is now `REPEATABLE READ READ ONLY`.
- Input fingerprint schema_version 1: 7 content tables plus 2 primary-key
  tables, with a canonical JSON and SHA-256 contract (see
  `data/matching/evaluation/README.md`).
- New `compute-fingerprint` mode.
- `evaluate` is refused while the fingerprint is UNPINNED, and refused on any
  mismatch. The result records `input_fingerprint`.
- `EXPECTED_INPUT_FINGERPRINT_SHA256 = None` (UNPINNED) in this commit.
  Pinning is Commit #2, after the operational database build.
- Matching code, the frozen A2 builder, schema and models are unchanged.

Review-package binding, assessed:

- **Already bound:**
  - the manifest ↔ the package files
  - the manifest ↔ the dataset bytes and cohort file
  - the rule-set provenance
  - the frozen code blobs
  - the blank sheet ↔ the confirmed copy (identity columns)
  - the confirmed labels ↔ the cohort (all 50)
- **Package ↔ database snapshot, now bound by re-render.** The frozen A2
  manifest does not record a database fingerprint. So, inside the same
  `REPEATABLE READ READ ONLY` snapshot as the fingerprint check, `evaluate`
  re-runs the frozen A2 pipeline:
  1. It uses the same functions the A2 builder CLI calls, in
     `review_package.py`: `parse_official_lecturers`, `parse_source_id_file`,
     `select_lecturers`, `resolve_canonical_lecturers_from_db`,
     `generate_review_inputs` and `build_review_package`.
  2. Inputs come only from the verified dataset and cohort bytes, the database
     session, and the candidate rule-set constants. Package CSV data is never
     used to build the expected bytes.
  3. It requires byte-equality of `candidate_review.csv` and
     `reference_labeling_sheet.csv` with the re-render.
  4. It requires equality of every manifest field except `generated_at`.
  5. File hashes are recomputed from the supplied files, never trusted as
     declared.

  Any mismatch fails closed before a result is written. The result records
  `review_package_rerender`. The A2 builder is unchanged.
- **Residual gap:** labels ↔ the exact package the reviewer saw. The confirmed
  CSV follows the A1 8-column contract and carries no package identity. Two
  packages built from different database states share the same blank sheet,
  because identity columns come only from the dataset and cohort. A3 proves
  that the evaluated package matches the pinned database, but it cannot
  prove from the labels alone that the reviewer viewed that package rather
  than an earlier one. Mitigation is operational: a provenance sidecar, with
  the fingerprint checked before and after the builder and the package SHAs
  recorded at hand-off. A sidecar is not a signature, so the evaluator never
  trusts it in place of re-render.

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

1. Operational build of `scopus_c3_eval_v1`.
2. A3 Commit #2: pin the fingerprint.
3. Generate the A2 package with the fingerprint checked before and after the
   builder.
4. Human confirmation of every primary-cohort row (50/50).
