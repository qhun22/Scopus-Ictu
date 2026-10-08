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

## Human review workflow

1. Build the A2 package with the frozen builder and **this** cohort file:
   `build_matching_review_package.py --source-id-file
   data/matching/evaluation/primary_cohort_source_ids.txt`, against the
   approved runtime/test database only. Keep the output outside Git.
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
3. SHA-256 of the official dataset equals the manifest. The source-id file's
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

## Database restriction

`evaluate` refuses `environment=prod` and refuses any configured database
whose name is not `scopus_m12_test` (generic message; the name and URL are
never printed). It runs `SET TRANSACTION READ ONLY` (fail closed), redacts
database errors, disposes the engine, and performs no writes.

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
