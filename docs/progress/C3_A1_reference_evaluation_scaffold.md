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
- Changed files: the A1 branch contains the original 7 task artifacts
  (initial task: 7 new files). The first audit correction modified 4 of them
  and the final polish modified the same 4; these are subsets of the original
  7, not contradictory totals.
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
- `generate_pairs_from_current_production(resolved_lecturers, session)` —
  runs `CandidateGenerator(session).generate_all()`, filters to resolved
  reference lecturers, enriches with `PublicationEvidenceEnricher(session).enrich()`,
  converts to `_GeneratedPair` (no persisted candidate reads)

### CLIs

- `validate_matching_reference.py`: no DB, parses + cross-checks reference CSV,
  exits 0/1/2, emits concise JSON summary.
- `evaluate_matching_reference.py`: validates reference CSV, connects with
  `settings.database_url` (never printed), refuses to run when
  `settings.environment` is `prod`, explicitly issues
  `SET TRANSACTION READ ONLY` before any SELECT (failure to establish it
  stops the run, fail-closed), runs candidate retrieval evaluation, redacts
  raw database exception details at the CLI boundary (generic messages
  only), disposes the engine in `finally`,
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

## Audit Correction

An independent audit of the initial A1 commit
(`6c060c8aae00f7a2e1857f594541367716562bd5`, CI run 37655663788,
Backend SUCCESS / Frontend SUCCESS) identified the following defects and
applied a corrective commit on the same branch:

- **Prediction source corrected**: the initial implementation read persisted
  `LecturerScopusCandidate` rows filtered by `status == PENDING`.  This
  couples evaluation results to workflow state (ACCEPTED/REJECTED decisions,
  older generation runs) and does not measure the *current* production
  retrieval algorithm.  Correction changed the prediction source to
  `CandidateGenerator(session).generate_all()` (transient, read-only),
  enriched by `PublicationEvidenceEnricher(session).enrich()`.
- **Historical observation evidence removed**: `LecturerScopusCandidateObservation`
  and `LecturerScopusCandidateEvidence` are no longer read for evaluation
  predictions.
- **Real ISO-8601 datetime validation**: `confirmed_at` was previously
  validated by regex only, which accepted impossible dates such as
  `2026-13-01` or `2026-02-30`.  Replaced with `datetime.fromisoformat()`
  after Z→+00:00 normalisation.  UTC timezone is now enforced.
- **Official dataset exactly-one invariant**: the cross-check previously
  used a `dict` keyed by `source_id`, silently collapsing duplicates.
  Changed to a list-based index; zero or >1 matches now raise a validation
  error.
- **Evaluation fails closed on unresolved lecturer**: `evaluate_candidate_retrieval`
  previously inserted a dummy case and excluded the row from metrics when a
  reference record had no resolved canonical lecturer.  It now raises
  `EvaluationInputError` instead.
- **Read-only DB transaction guard hardened**: `evaluate_matching_reference.py`
  now uses `settings.database_url` (not a nonexistent `get_db_url()` helper
  or manual env-var fallback), refuses to run when
  `settings.environment == "prod"`, and fails closed if
  `SET TRANSACTION READ ONLY` is rejected by the database.
- **Production matching algorithms unchanged**: `candidate_generator.py`,
  `candidate_types.py`, `publication_evidence_enricher.py`,
  `candidate_persistence.py` are unmodified.
- **DB exception messages redacted at CLI boundary**: the evaluate CLI catches
  `SQLAlchemyError` and emits a generic safe message; no raw exception text,
  host, port, database name, or username is written to output.  The read-only
  transaction failure path also emits only a generic safe message.
- **Institutional email cross-check tightened**: when a reference row provides
  `institutional_email` and the official dataset row has no corresponding email,
  a validation error is now raised (previously silently accepted).
- **No production matching algorithm changed** across all audit corrections.

Final authoritative A1 SHA: see Git commit containing this record and final
A1 audit report.

Final corrected CI evidence: NOT_AVAILABLE_AT_COMMIT_TIME.  Final CI evidence
will be reported externally in the audit report.

## Known Limitations

- **No real supervisor-confirmed reference dataset is added in C3-A1.**
  The `reference_template.csv` contains the header only.
- **Therefore NO real ICTU precision/recall/F1 result is claimed yet.**
  Any numbers would be fabricated; the evaluator requires real labels.
- **Actual evaluation requires C3-A2** (reference labeling/population).

## Next Recommended Step

**C3-A2** — populate the reference template with supervisor-confirmed labels,
run `validate_matching_reference.py` to confirm integrity, then run
`evaluate_matching_reference.py` against the live database to obtain real
ICTU candidate-retrieval precision/recall/F1 measurements.
