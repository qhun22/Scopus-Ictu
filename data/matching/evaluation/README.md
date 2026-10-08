# Verified Matching Quality Evaluation (C3-A3)

## Purpose

C3-A3 measures **candidate retrieval** quality of the frozen production
matching pipeline (`CandidateGenerator` + `PublicationEvidenceEnricher`)
against **human-confirmed** labels, using the frozen C3-A1 evaluator
unchanged. It does not evaluate ranking and does not tune the algorithm.

Tool: `backend/scripts/run_matching_quality_evaluation.py`
(`prepare-cohort`, `evaluate`).

## Primary cohort (fixed before candidate review)

`primary_cohort_source_ids.txt` lists the 50 lecturers whose labels produce
the headline metrics. It was generated and committed **before** any review
package or candidate output was produced or inspected.

- Algorithm `SHA256_SEED_RANK_V1`; seed `C3-A3-ICTU-PRIMARY-2026-V1`; size 50.
- For every unique trimmed `lecturer_source_id` in
  `data/lecturers/ictu_lecturers.json`, compute
  `SHA256(UTF8(seed) || 0x00 || UTF8(lecturer_source_id))`; sort by digest
  hex, then source ID; take the first 50; write them sorted ascending, one per
  line, with a trailing newline.
- Selection depends only on official source IDs: not on candidate counts,
  ambiguity, publication evidence or conflicts, difficulty, or Scopus
  knowledge. No `random`, no clock.

Selecting first prevents choosing easy or hard cases after seeing algorithm
output. n = 50 is practical for a graduation project and reproducible, but it
is **not** a high-precision estimate for the whole 410-lecturer population.
Headline metrics use only this cohort; no challenge set is mixed in.

## Frozen official dataset (Phase 1)

The official lecturer dataset used by C3-A3 is frozen at the snapshot from
which the cohort was precommitted. Because Git `core.autocrlf` yields two byte
forms of the same repository text, exactly **two** SHA-256 values of the exact
dataset bytes are accepted:

- LF (repository content):
  `9428e0a2b009ecff1043b4dc796ed69a0fc64054594b0fb40ffa27bbed4ec82e`
- CRLF (Windows checkout):
  `ac4ed2d3f3c5fc7e73912ac9386b5710f4e015bbd7028e5b48a656dae3d4c3d4`

Any other hash fails closed, both in `prepare-cohort` and before
evaluation. This holds even if the 50 source IDs are unchanged, because names
or emails may have changed. Bytes are hashed exactly as supplied, with no
newline normalization. Arbitrary normalized-equivalent content is **not**
accepted; only these two exact hashes are.

This does not weaken package provenance. The A2 manifest still records the
SHA-256 of the exact bytes actually used, and A3 still requires the supplied
dataset to match it. An LF dataset with a CRLF-built manifest (or the reverse)
is rejected.

## Human review workflow

1. Build the A2 package with the frozen builder and **this** cohort file:
   `build_matching_review_package.py --source-id-file
   data/matching/evaluation/primary_cohort_source_ids.txt`, against the
   approved evaluation database `scopus_c3_eval_v1` only, after its
   fingerprint is pinned. Keep the output outside Git.
2. **Never edit** `candidate_review.csv`, `reference_labeling_sheet.csv` or
   `review_manifest.json`.
3. Copy `reference_labeling_sheet.csv` to `reference_confirmed.csv` (in a
   protected location outside Git) and edit **only** `decision`,
   `expected_scopus_id`, `confirmation_source`, `confirmed_at`, `notes`.
4. Every one of the 50 rows must be completed. There is no partial evaluation.

Methodology:

- Candidate suggestions are review assistance only. Final labels require
  independent human/external confirmation and are never generated from
  `CandidateGenerator`.
- `candidate_count = 0`, `NO_CANDIDATE_GENERATED`, and publication conflicts
  do **not** imply `NO_MATCH`.
- The reviewer may confirm a Scopus ID that is not among the candidates, or
  that is absent from the local Scopus corpus. Such a target is reported as
  corpus-missing, never turned into `NO_MATCH`.
- **Incorporation bias:** the reviewer sees the algorithm's suggestions, which
  can bias labels toward them. A blinded independent search before seeing
  suggestions would be methodologically stronger. It was not required for this
  project workflow, so the review is **not** described as fully blinded.

## Verification gates (all fail closed, before any DB connection)

1. `review_manifest.json` parsed strictly: exact A2 field set, correct types.
2. SHA-256 of `candidate_review.csv` and `reference_labeling_sheet.csv` equal
   the manifest.
3. The official dataset is one of the two frozen Phase-1 byte forms, **and**
   its SHA-256 equals the manifest. The source-id file's
   SHA-256 equals the manifest (never null) and the committed cohort file's.
   `selected_lecturer_count == 50`. The file's lines equal the cohort
   recomputed from the dataset.
4. Frozen code: for `candidate_generator.py`,
   `publication_evidence_enricher.py`, `candidate_types.py`, the blob at
   frozen A2 commit `a1e761c2…` equals the recorded anchor, **and** the
   current working-tree blob (`git hash-object`) equals it. Any change,
   including an uncommitted one, or Git being unavailable, fails.
5. Rule provenance: the six manifest fields (`candidate_*`, `publication_*`,
   `generation_*` rule-set ID and version) equal the current
   `candidate_persistence` constants. A changed algorithm is a different
   experiment.
6. Original sheet: exact A1 8-column schema, 50 rows, unique IDs, all five
   label columns blank, IDs equal the cohort.
7. Confirmed copy: same schema and the same 50 lecturers. Source ID and full
   name are compared after trimming (name case-sensitive); email after
   trim + casefold. Row order may differ (e.g. Excel); a UTF-8 BOM is
   accepted.
8. All 50 rows must pass the frozen A1 reference parser and the official
   dataset cross-check (MATCH needs `expected_scopus_id`, NO_MATCH must not
   have one, `confirmation_source` required, `confirmed_at` UTC).

**Line endings:** with Git `core.autocrlf=true`, checked-out text files may be
CRLF, so their SHA-256 differs from the LF repository content. Build the A2
package and run `evaluate` from the same checkout so the bytes are consistent.
The cohort content check compares lines, not bytes.

## Evaluation database and input fingerprint

C3 evaluation runs only against a dedicated database named exactly
**`scopus_c3_eval_v1`**. `scopus_m12_test` is a pytest scratch database, not a
research corpus. Acceptance is never used. Every other name is refused.

Database identity is checked twice:

- **configuration:** `settings.database_url`, composed only from `DB_*`
  settings. Process environment variables take precedence over
  `backend/.env`, and there is no raw `DATABASE_URL` setting.
- **live connection:** `SELECT current_database()`.

Errors are generic: the name and URL are never printed. `prod` is refused.

Both `compute-fingerprint` and `evaluate` open one
`SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY` snapshot as the
first statement. Failure is fail-closed. Database errors are redacted, the
engine is disposed, and there are no writes.

### Input fingerprint, schema_version 1

- **Content tables (7).** Only the columns read by `CandidateGenerator`,
  `PublicationEvidenceEnricher` and lecturer resolution are hashed. Column
  names are sorted, and every table's primary key is `id`:
  - `lecturers`: `full_name, id, repository_profile_url`
  - `lecturer_source_snapshots`: `id, lecturer_id`
  - `lecturer_known_publications`:
    `doi_normalized, id, lecturer_id, snapshot_id, title_normalized`
  - `publications`: `doi, eid, id, title, title_normalized`
  - `publication_authors`: `id, publication_id, scopus_author_id`
  - `scopus_authors`: `id, preferred_name, scopus_id`
  - `scopus_author_name_variants`:
    `id, scopus_author_id, variant_name, variant_type`
- **Structural tables (2): `scopus_imports`, `raw_scopus_records`.** Only the
  row count and the sorted primary-key set are hashed. This checks structure
  and the key set only; it does not prove that raw content is unchanged.
  `raw_payload` is never selected or hashed.
- **Encoding.**
  - Canonical JSON is
    `json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`,
    encoded as UTF-8 and hashed with SHA-256.
  - UUIDs become their canonical lowercase string. `NULL` becomes `null`,
    which is distinct from `""`. Integers stay numbers. Strings are taken
    verbatim: no trim, case folding, or Unicode normalization.
  - Any other value type is rejected.
  - Rows are sorted by `id` string in Python, so the result never depends on
    the order PostgreSQL returns rows in.
  - A duplicate `id` is rejected.
- **Table hash.** Content tables hash the list of row objects. Structural
  tables hash the sorted list of key strings.
- **Final hash.** SHA-256 of
  `{"schema_version": 1, "tables": [...]}`. Each `tables` entry is
  `{"table", "hash_kind": "content"|"primary_key", "columns", "row_count",
  "sha256"}`, and entries are sorted by table name.

The same implementation serves both modes:

- **`compute-fingerprint`** needs no pinned value. It verifies identity and
  prints the digest, per-table counts and hashes. It never prints row data.
- **`evaluate`** is refused while the expected fingerprint is **UNPINNED**,
  before any database connection. After pinning, everything below happens in
  one snapshot:
  1. Require the live-snapshot fingerprint to equal the pinned value.
  2. **Re-render the review package** from that snapshot with the frozen A2
     functions (`parse_official_lecturers` → `parse_source_id_file` →
     `select_lecturers` → `resolve_canonical_lecturers_from_db` →
     `generate_review_inputs` → `build_review_package`). Inputs are only the
     verified dataset and cohort bytes plus the database. Require
     `candidate_review.csv` and `reference_labeling_sheet.csv` to be
     **byte-equal**, and every manifest field except `generated_at` to be
     equal.
  3. Run the frozen A1 evaluation.

  Any mismatch fails closed. The result records the fingerprint and the
  re-render outcome. A self-declared manifest or sidecar is never trusted in
  place of re-computation.

### Operational conditions for the next step (not performed yet)

1. Acceptance is read only.
2. Create `scopus_c3_eval_v1` with the repo's Alembic.
3. Verify FKs before copying. The only required parents are
   `raw_scopus_records.import_id → scopus_imports.id` and
   `scopus_author_name_variants.first_seen_raw_record_id →
   raw_scopus_records.id`. `scopus_imports` has no FK, and none of the 9
   tables references `users`.
4. Copy the 9 tables, preserving UUIDs.
5. Compare source and target row counts, and the contract fingerprint
   (content and key sets), each on a consistent snapshot.
6. Restrict the application role to `SELECT` on the data. Check effective
   write privileges, including ownership and inherited roles.
7. Check that all 50 cohort lecturers resolve to exactly one row each.
8. Pin the fingerprint (A3 Commit #2) before generating the review package.
9. Verify the fingerprint immediately before and after the frozen A2
   builder. Publish the package only if both match.
10. Never run pytest against this database.
11. `evaluate` re-checks the fingerprint and the package/label links.

## Outputs and data policy

- `evaluation_result.json` (safe; may be committed after a real evaluation):
  provenance hashes, cohort selection, six rule-provenance values, three code
  blob anchors, counts, frozen A1 metrics, and A1 safe cases. It contains no
  `confirmation_source`, no notes, no reviewer data, no internal UUIDs, and no
  database information.
- `reference_confirmed.csv` is **never committed** (it may identify
  reviewers). A de-identified copy needs a future explicit approval.
- A2 runtime package files are not committed.

## Metrics

The frozen A1 metrics are used unchanged: candidate-pair precision/recall/F1,
end-to-end and eligible candidate recall, TP/FP/FN, MATCH hit/miss,
single/ambiguous MATCH counts, NO_MATCH with/without candidates,
corpus-present/missing MATCH counts, and mean candidates per reference. There
are no ranking metrics (no score, top-k, MRR, NDCG, or thresholds).

A3 freezes the baseline. Any later algorithm change is a separate experiment
with a preserved baseline, an explicit hypothesis, a new rule version, and
re-evaluation against the same confirmed labels.
