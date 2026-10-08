# C3-A2 — Human Matching Review Package

## 1. Summary

Builds a deterministic **review package** for human confirmation of
lecturer ↔ Scopus author matches: an advisory candidate review CSV, a blank
labeling sheet compatible with the C3-A1 reference contract, and a manifest.
Humans confirm labels from independent sources; **no ground truth is
generated here** and no precision/recall/F1 is computed.

## 2. Scope

- Branch: `completion3/a2-human-review-package`
- Base SHA: `e502e71fd33eeb93af1fde726b5b1cc5cf0b87f2` (frozen C3-A1 tip)
- Changed files: 5 (all new)
  1. `backend/app/services/matching/review_package.py`
  2. `backend/scripts/build_matching_review_package.py`
  3. `backend/tests/unit/test_matching_review_package.py`
  4. `data/matching/review/README.md`
  5. `docs/progress/C3_A2_human_review_package.md`
- Production matching changed: false
- Frontend / models / migrations: none

Authoritative task SHA: see Git commit containing this record and final A2
report.

## 3. Implementation

- **Review-package service** (`review_package.py`): immutable DTOs, official
  dataset parsing (duplicate `source_id` rejected), deterministic selection,
  exactly-one canonical `Lecturer` resolution, safe explicit serialization,
  CSV/manifest rendering. No DB writes.
- **Selection**: all official lecturers by default; optional
  `--source-id-file` (blank lines and `#` comments allowed; duplicates,
  unknown IDs, empty selection rejected). Ordered by `lecturer_source_id`.
- **Current candidates**: `CandidateGenerator(session).generate_all()`,
  filtered to selected lecturers, then
  `PublicationEvidenceEnricher(session).enrich(...)`. Persisted candidate
  tables, status filters, and review history are never read.
- **Full-selected-set conflict diagnostics**: known publications, snapshots
  and publications are loaded for **all selected lecturers** (including those
  with zero candidates) and passed to the production helper
  `_reconcile_known_publications`, so reconciliation rules are reused, not
  copied. No production file was modified to expose it.
- **`candidate_review.csv`**, **`reference_labeling_sheet.csv`**,
  **`review_manifest.json`**: see `data/matching/review/README.md`.
- **CLI** (`build_matching_review_package.py`): refuses `prod`, uses
  `settings.database_url` (never printed), `SET TRANSACTION READ ONLY` with
  fail-closed behavior, `SQLAlchemyError` redaction, engine disposal, and
  overwrite protection scoped to the three package files.

## 4. Important Decisions

- A2 is intentionally separate from A3; there is no auto-labeling.
- Candidate suggestions are advisory only; row order (lecturer source ID, then
  Scopus ID) is not ranking.
- Zero candidates and `NO_CANDIDATE_GENERATED` do not mean `NO_MATCH`.
- A reviewer may confirm a target absent from the candidate list or from the
  local Scopus corpus.
- Conflicts cover all selected lecturers, including zero-candidate lecturers,
  and are diagnostics, not positive evidence.
- `ambiguous_lecturer_count` means `candidate_count > 1` only.
- No production matching changes.

## 5. Contracts / Invariants

- `candidate_review.csv` columns (14, exact order) and
  `reference_labeling_sheet.csv` columns (the 8 A1 columns, exact order) are
  fixed; the sheet's label columns are empty on every row.
- Evidence output is whitelisted: name evidence
  (`rule_id, lecturer_source_value, scopus_surface_type,
  scopus_surface_value`), publication evidence
  (`rule_id, reconciliation, canonical_publication_eid,
  canonical_publication_doi, canonical_publication_title`), conflicts as
  count plus sorted reason strings. No internal UUIDs; no generic
  dataclass-to-dict serialization.
- No `rank/score/confidence/probability/threshold/best/top` fields.
- `publication_conflict_count` counts underlying descriptors once.
- Only `generated_at` varies across identical inputs.

## 6. Validation Performed

Recorded in the final A2 report (local results, then exact-head CI). At the
time of writing this record: focused A2 tests 59 passed.

## 7. CI / Integration Evidence

NOT_AVAILABLE_AT_COMMIT_TIME

## 8. Safety Notes

- Acceptance mutation: NONE
- Migration: false
- Credentials exposed: false
- Force push: false
- Canonical unrelated WIP modified: false

## 9. Known Limitations

- A2 generates no real confirmed labels and reports no precision/recall/F1.
- Human review is still required.
- A runtime package smoke against a database may be NOT_RUN.
- A3 waits for completed, confirmed labels.

## 10. Next Recommended Step

**C3-A3**: ingest the human/supervisor-confirmed labeling sheet, validate it
with the A1 validator, and run the real candidate-retrieval evaluation.
