# Human Matching Review Package (C3-A2)

## Purpose

`backend/scripts/build_matching_review_package.py` builds deterministic
material for a **human reviewer** who will confirm, from independent
human/external sources, which Scopus author (if any) belongs to each ICTU
lecturer.

**A2 creates no ground truth.** It never fills `decision`,
`expected_scopus_id`, `confirmation_source`, `confirmed_at`, or `notes`, and
it computes no precision/recall/F1. Completed, confirmed labels are consumed
later by C3-A3.

```
python backend/scripts/build_matching_review_package.py \
  --lecturer-dataset data/lecturers/ictu_lecturers.json \
  --output-dir <directory> [--source-id-file <path>] [--overwrite]
```

Three files are written (and only these three; nothing else in the directory
is touched or deleted):

| File | Purpose |
|------|---------|
| `candidate_review.csv` | Advisory suggestions and diagnostics for the reviewer |
| `reference_labeling_sheet.csv` | Blank sheet the human fills in (A1 contract) |
| `review_manifest.json` | Counts and SHA-256 hashes |

Existing package files are never overwritten unless `--overwrite` is given.

## Selection

Default: **all** official lecturers (not only those with candidates, which
would bias the review set). `--source-id-file` restricts to a subset: UTF-8,
one `lecturer_source_id` per line, blank lines and lines starting with `#`
allowed; duplicates, unknown IDs, and an empty effective selection are
rejected. Every selected ID must match exactly one official row and exactly
one canonical `Lecturer.repository_profile_url`. Output is ordered by
`lecturer_source_id` ascending. No sampling.

## `candidate_review.csv`

Exact columns, in order:

`lecturer_source_id, institutional_email, lecturer_full_name,
suggestion_status, candidate_count, candidate_scopus_id,
candidate_preferred_name, name_rule_ids, name_evidence_json,
publication_evidence_count, publication_rule_ids, publication_evidence_json,
lecturer_publication_conflict_count, lecturer_publication_conflict_reasons`

- `suggestion_status`: `CANDIDATE` (>= 1 generated candidate) or
  `NO_CANDIDATE_GENERATED` (0). Presentation metadata only.
- A lecturer with N > 0 candidates has N rows (`candidate_count=N` repeated).
  A lecturer with 0 candidates has exactly one row with `candidate_count=0`
  and empty candidate/evidence cells.
- Rows are ordered by `lecturer_source_id` ascending, then
  `candidate_scopus_id` ascending. **This is not a ranking.**
- `name_evidence_json` items contain only `rule_id`,
  `lecturer_source_value`, `scopus_surface_type`, `scopus_surface_value`.
- `publication_evidence_json` items contain only `rule_id`,
  `reconciliation`, `canonical_publication_eid`, `canonical_publication_doi`,
  `canonical_publication_title`.
- JSON cells are compact, sorted, deterministic. No internal UUIDs are ever
  written.

### Publication conflicts

`lecturer_publication_conflict_count` / `_reasons` are lecturer-level
diagnostics computed over the **entire selected set**, including lecturers
with zero candidates, using the same reconciliation logic as the production
`PublicationEvidenceEnricher`. Reasons are a sorted unique JSON array drawn
from `DOI_AMBIGUOUS`, `DOI_TITLE_CONFLICT`, `TITLE_AMBIGUOUS`,
`SNAPSHOT_LECTURER_MISMATCH`.

A conflict is a diagnostic, **not** positive evidence: it creates no
candidate, removes no candidate, and implies neither MATCH nor NO_MATCH.
`publication_evidence_count = 0` does not necessarily mean there was no
publication-related source information: if
`lecturer_publication_conflict_count > 0`, one or more reconciliation cases
failed closed and were not converted into positive publication evidence.

## `reference_labeling_sheet.csv`

Header is exactly the C3-A1 reference contract:

`lecturer_source_id, institutional_email, lecturer_full_name, decision,
expected_scopus_id, confirmation_source, confirmed_at, notes`

One row per selected lecturer. Only the first three columns are prefilled;
the other five are empty on every row. No suggestion, count, conflict, or
evidence is copied here. Once a human fills it, it validates with
`backend/scripts/validate_matching_reference.py` (C3-A1).

## `review_manifest.json`

Fields: `schema_version`, `generated_at`, `official_lecturer_dataset_sha256`,
`source_id_file_sha256` (null without `--source-id-file`),
`candidate_rule_set_id`, `candidate_rule_set_version`,
`publication_rule_set_id`, `publication_rule_set_version`,
`generation_rule_set_id`, `generation_rule_set_version`,
`selected_lecturer_count`, `lecturers_with_candidates`,
`lecturers_without_candidates`, `candidate_pair_count`,
`ambiguous_lecturer_count`, `publication_conflict_count`,
`candidate_review_sha256`, `reference_labeling_sheet_sha256`.

- **Rule provenance** (taken from the `CANDIDATE_*`, `PUBLICATION_*` and
  `GENERATION_*` rule-set constants in `candidate_persistence.py`; never
  duplicated or invented here):
  - `candidate_rule_set_*` identifies the candidate **retrieval** rules that
    produced the suggestions.
  - `publication_rule_set_*` identifies the publication evidence /
    reconciliation rules that produced `publication_evidence_json`,
    `publication_evidence_count` and the conflict diagnostics shown to the
    reviewer.
  - `generation_rule_set_*` identifies the combined evidence-generation
    contract (candidate + publication evidence).

  This lets C3-A3 demonstrate exactly which review context the human reviewer
  saw: retrieval rules can stay the same while publication rules change the
  evidence shown. These fields are provenance only; they are not a score,
  rank, confidence, or quality estimate.
- `ambiguous_lecturer_count` is exactly the number of selected lecturers with
  `candidate_count > 1`. It is descriptive only, not "uncertain" or "wrong".
- `publication_conflict_count` counts the underlying conflict descriptors
  once (not the repeated per-row cells).
- The manifest contains no database information and no internal UUIDs.

Only `generated_at` varies between runs on identical inputs.

## Anti-bias contract (read before labeling)

- `candidate_review.csv` is advisory only; suggestions are **not** ground truth.
- Row ordering is not ranking; the first candidate is not "best".
- Matching rules and evidence are not confirmation.
- `candidate_count = 0` / `NO_CANDIDATE_GENERATED` does **not** mean `NO_MATCH`.
- Publication conflicts do not mean `NO_MATCH`; publication evidence count is
  not a score.
- A reviewer may confirm a Scopus ID that is **not** in `candidate_review.csv`.
- A reviewer may confirm a Scopus ID that is absent from the local Scopus
  corpus; A3 will classify such a target as corpus-missing.
- `NO_MATCH` requires independent human/external confirmation. The absence of
  a generated candidate is insufficient evidence.
- A2 does not generate ground truth.

## Safety

The builder refuses to run when the configured environment is `prod`, uses
the application settings (the database URL is never printed), runs
`SET TRANSACTION READ ONLY` and fails closed if that cannot be established,
redacts database errors, and performs no writes. Candidates come from the
current production `CandidateGenerator`, never from persisted candidate
tables or review history.

Generated bundles must not be committed to the repository without a later
explicit policy.
