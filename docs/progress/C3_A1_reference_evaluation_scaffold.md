# C3-A1 — Matching Reference Dataset and Evaluation Scaffold

## Summary

Builds the ground-truth reference contract and candidate-retrieval evaluation
framework for Completion-3.  The evaluator measures whether the
lecturer ↔ Scopus-author candidate generator *retrieves* the correct pair at
all — not whether it ranks it first.  No real supervisor-confirmed labels are
added in this slice; that is deferred to C3-A2.

## Scope

- Branch: `completion3/a1-reference-evaluation-scaffold`
- Base SHA: `f49281802fe5d46fdc4e1ef872978b0cbaf73c4c`
- Changed files: 7
- Production matching changed: false
- Frontend changed: false
- Migrations: none
- Acceptance DB mutations: none

## Changed Files

1. `backend/app/services/matching/evaluation.py` — NEW
2. `backend/scripts/validate_matching_reference.py` — NEW
3. `backend/scripts/evaluate_matching_reference.py` — NEW
4. `backend/tests/unit/test_matching_evaluation.py` — NEW
5. `data/matching/reference/README.md` — NEW
6. `data/matching/reference/reference_template.csv` — NEW (header only)
7. `docs/progress/C3_A1_reference_evaluation_scaffold.md` — NEW (this file)

## Implementation

### Reference CSV Contract (`data/matching/reference/`)

- `reference_template.csv`: header-only CSV template.  No ground-truth rows.
- `README.md`: full contract documentation for the reference dataset schema,
  decision semantics, primary-key choice, no-inference rule, and next steps.

Columns: `lecturer_source_id`, `institutional_email`, `lecturer_full_name`,
`decision`, `expected_scopus_id`, `confirmation_source`, `confirmed_at`, `notes`.

### Evaluation Service (`evaluation.py`)

Typed immutable dataclasses:
- `ReferenceDecision` / `ReferenceRecord`
- `ReferenceValidationIssue` / `ReferenceValidationError`
- `ReferenceCaseResult`
- `CandidateRetrievalMetrics`
- `CandidateRetrievalEvaluation`
- `_EvaluationLecturer` / `_GeneratedPair` (internal input types)

Functions:
- `parse_reference_csv(content)` — strict UTF-8 CSV parsing with full
  structural validation
- `validate_against_lecturer_dataset(records, path)` — cross-check against
  `data/lecturers/ictu_lecturers.json`
- `evaluate_candidate_retrieval(...)` — pure, stateless metric computation
- `resolve_lecturers_from_db(records, session)` — read-only DB lookup
- `load_scopus_corpus_ids(session)` — read-only corpus load
- `load_generated_pairs(ids, session)` — read-only candidate pair load

### CLIs

- `validate_matching_reference.py`: no DB, parses + cross-checks reference CSV,
  exits 0/1/2, emits concise JSON summary.
- `evaluate_matching_reference.py`: validates reference CSV, connects to DB
  read-only (`SET TRANSACTION READ ONLY`), runs candidate retrieval evaluation,
  emits deterministic JSON with `schema_version`, `evaluated_at`,
  `reference_dataset_sha256`, `candidate_rule_set_id`,
  `candidate_rule_set_version`, `metrics`, `cases`.

## Important Decisions

- **Evaluation measures candidate retrieval, not ranking.**  No
  `top_1_accuracy`, `MRR`, `NDCG`, rank, score, confidence, or threshold is
  computed.  Ranking requires a separate approved slice with a production
  ranking contract.

- **`lecturer_source_id` is the reference primary key.**  It corresponds to
  the DSpace profile URL (`source_id` in the official dataset,
  `repository_profile_url` in the DB).

- **`staff_code` is not required.**  The current ICTU source dataset has zero
  `staff_code` coverage; making it the reference key would make all 410
  reference rows unresolvable.

- **No ground truth is inferred automatically.**  The evaluator never uses its
  own candidate predictions to populate `expected_scopus_id`.  Reference labels
  must come from human/external confirmation.

- **Corpus-missing ground truth is separated from algorithm misses.**
  A confirmed MATCH target absent from the `scopus_authors` table is counted as
  `corpus_missing`, not as an algorithm FN for `eligible_candidate_recall`.
  `end_to_end_candidate_recall` still counts it as a miss.

- **No production matching/scoring change.**  `candidate_generator.py`,
  `candidate_types.py`, `candidate_persistence.py`, `engine.py`, `scoring.py`,
  and all matching rules are unmodified.

## Contracts / Invariants

- `decision` = `MATCH` ⟹ `expected_scopus_id` non-empty
- `decision` = `NO_MATCH` ⟹ `expected_scopus_id` empty
- `lecturer_source_id` unique per CSV
- MATCH `expected_scopus_id` unique per CSV
- TP: generated pair exactly equals the MATCH reference pair
- FP: generated pair that is not the confirmed MATCH (including extras on
  MATCH lecturers and all pairs on NO_MATCH lecturers)
- FN: confirmed MATCH pair absent from generated pairs
- `precision = TP / (TP + FP)`, `0.0` if denominator = 0
- `recall = TP / (TP + FN)`, `0.0` if denominator = 0
- `F1 = 2 * P * R / (P + R)`, `0.0` if denominator = 0
- `end_to_end_recall = hits / MATCH_count`, `0.0` if `MATCH_count = 0`
- `eligible_recall = corpus_hits / corpus_eligible`, `0.0` if denominator = 0

## Validation Performed

Focused unit tests:

```
python -m pytest -q backend/tests/unit/test_matching_evaluation.py
```

Full backend regression (results reported externally — see CI evidence below).

CLI smoke test against synthetic fixture (fixture not committed):
- Valid synthetic reference → validator exits 0
- Invalid synthetic reference → validator exits 1

## CI / Integration Evidence

NOT_AVAILABLE_AT_COMMIT_TIME

Authoritative task SHA: see Git commit containing this record and final task
report.  Final CI evidence will be reported externally in the task report.

## Safety Notes

- Acceptance DB mutation: NONE
- Migration: false
- Credentials exposed: false
- Force push: false
- Canonical WIP modified: false
- `scopus_ictu_acceptance_v2` not touched

## Known Limitations

- **No real supervisor-confirmed reference dataset is added in C3-A1.**
  The `reference_template.csv` contains the header only.
- **Therefore NO real ICTU precision/recall/F1 result is claimed yet.**
  Any numbers would be fabricated; the evaluator requires real labels.
- **Actual evaluation requires C3-A2** (reference labeling/population).
- The evaluate CLI's `SET TRANSACTION READ ONLY` is a best-effort guard;
  the application code performs no writes regardless.

## Next Recommended Step

**C3-A2** — populate the reference template with supervisor-confirmed labels,
run `validate_matching_reference.py` to confirm integrity, then run
`evaluate_matching_reference.py` against the live database to obtain real
ICTU candidate-retrieval precision/recall/F1 measurements.
