# Gate E.2 / G03 — Author Position Drift

Date: 2026-10-29 (Asia/Bangkok). Status: IMPLEMENTED; READY FOR OWNER REVIEW.

## Problem and resulting behavior

Previously, `_ensure_publication_author_link()` returned immediately for an
existing publication/Scopus-author pair, regardless of the newer author position.
A synthetic position 2 -> 4 replay produced zero conflicts. Gate E.1 describes
this branch as G03 (`IDENTITY_EVIDENCE_GAP_ANALYSIS.md`, G03 row;
`IMPLEMENTATION_ROADMAP.md:16,34`).

The same pair now retains its canonical link and original position and reports
`AUTHOR_POSITION_DRIFT` when both positions are known and differ. This is a
metadata discrepancy; it does not establish an identity error or change a
lecturer identity, review, affiliation resolution or recommendation.

## Exact change scope

1. `backend/app/services/normalization/scopus_author_normalizer.py` — modified.
2. `backend/tests/unit/test_author_position_drift.py` — added.

Only these four G03 artifacts were written under `docs/qa/gate_e2/`:
`G03_HANDOVER.md`, `G03_IMPLEMENTATION.diff`, `G03_TEST_RESULTS.txt`,
`G03_VALIDATION.json`. Existing G01/G02 packages, Gate D research, other dirty
files and Gate E.1 documents were preserved. No commit or push.

## Existing architecture and persistent recording

The model already has `ScopusImport.normalization_summary` as JSONB
(`backend/app/models/scopus_raw.py:74-77`). Author normalization already assigns
and commits that JSON in `AuthorNormalizer.finalize()`. No migration or new
table is needed.

The existing `authors.errors` list remains a maximum-50 diagnostic sample.
Complete G03 provenance is stored separately at:

`normalization_summary.authors.position_discrepancies`

Each entry has `code`, `publication_id`, `publication_author_id`, internal
`scopus_author_id`, external `scopus_id`, `existing_author_order`,
`observed_author_order`, and `observations`. Each observation has `import_id`,
`raw_record_id`, and `row_number`. These IDs join to the canonical publication
and immutable raw payload, including its original author list, EID and DOI
(`scopus_raw.py:123-154`; `publication.py`, PublicationRawSource). Raw metadata
is referenced rather than copied or rewritten.

Entries are grouped by `(publication_id, scopus_author_id, existing_author_order,
observed_author_order)`. Source observations are deduplicated by
`(import_id, raw_record_id, row_number)`. Both levels are sorted before storing.
Repeated observations from the same raw record produce no duplicate entry;
different raw records remain separate provenance observations on that entry.
Counters count unique drift groups encountered in the current normalizer run,
not a cumulative history count. Existing-link counters still count every replay.

The complete diagnostic is merged with the previous JSON during initial,
progress, FAILED and COMPLETED checkpoints, including an empty restart.
Ordinary run counters and the sampled errors keep their existing per-run policy.
M2.6A publication finalization already preserves the nested `authors` object;
a pure regression test verifies this with the new diagnostic present.

Recording is **per import**, not a global conflict registry. Two distinct imports
may each report the same disagreement, preserving each import's provenance.
Diagnostics are historical observations, not an ACTIVE/RESOLVED review workflow.

## Behavior contract

| Input | Result |
| --- | --- |
| New pair, known position | Existing insertion behavior and constraints retained. |
| Existing pair, same position | No new association or drift diagnostic. |
| Existing pair, known 2 -> 4 (or 4 -> 2) | Existing position retained; drift recorded with provenance. |
| Existing pair, either position null | No conflict and no automatic position replacement. |
| Existing unknown position, newer concrete position | Preserve unknown; no conflict or automatic promotion. |
| New pair, null position | Skip insertion; report `AUTHOR_ORDER_MISSING`, without incrementing conflicts. |
| Different author already occupies a slot | Existing `AUTHOR_ORDER_CONFLICT` behavior retained. |
| Seventh/later author | Same detection rules, without a position cutoff. |

`PublicationAuthor.author_order` is NOT NULL with CHECK >= 1, and the parser emits
1-based integer positions (`publication.py:270-288`; initial migration
`e5b3cf21c1d12b64_0001_initial_schema.py:634,656-665`). Null canonical positions
are therefore defensive synthetic cases, not a claim about valid current DB
contents. No nullable schema or fabricated author position was introduced.

First observation still determines the canonical position. Reversing import
order can change that first position; both directions now detect disagreement.
The patch does not choose which source is correct or reorder authors.

## Code evidence and traced path

Current source line references:

- `parse_author_occurrences():137-276`: parse the complete aligned author lists
  and retain raw/import provenance, with no six-author cutoff.
- `normalize_authors_for_import():704-810`: load raw/provenance, call the parser,
  `record_occurrences`, and existing checkpoint/finalization mechanism.
- `record_occurrences():362-405`: resolve publication via raw provenance, obtain
  the author, retain variants, and call the association check.
- `_ensure_publication_author_link():486-563`: compare the existing known
  position; leave existing associations intact; guard unknown new positions.
- `_record_position_discrepancy():565-599`: group the metadata diagnostic and
  retain newer raw observations without any identity action.
- `_merge_position_discrepancies():330-351`, `finalize():601-645`: deterministic
  merge into the existing JSON persistence mechanism, beyond the error sample.
- `backend/app/api/v1/endpoints/authors.py:88-115`: existing caller reads sampled
  summary errors. Its response schema exposes row/code/message, not the complete
  new provenance. No HTTP/UI change was included.

The final pure entry-point test exercises raw synthetic author lists -> parser
-> `record_occurrences` -> association check -> startup/progress/final checkpoints
-> same-import replay, for positions 4 and 8. Query/loading operations and commits
are fake in-memory methods; neither a real Session nor an engine is used.

## Validation

- Before application edits: **14 FAILED / 34 PASSED**, exit 1, on the initial
  21-case G03 module plus 27 existing parser cases. Known position drift failed
  at the zero-conflict assertion. The new-null-association guard also failed;
  this is a defensive case, not evidence that the parser emits null positions.
- Final: **51 PASSED**, exit 0: 24 G03 cases and 27 existing parser cases. Three
  additional cases were added after the baseline run (multiple observed positions,
  publication-summary retention, and the eighth-position entry-point variant).
- All ten requested regression categories are covered, plus occupied-slot
  compatibility, full provenance beyond 50 sampled errors, deterministic grouping,
  distinct raw observations and checkpoint/restart retention.
- Tests use synthetic data, fake sessions, `--noconftest`, disabled plugin autoload,
  no pytest cache and Python `-B`. A module-import guard rejects database/app/
  conftest initialization; socket connections are blocked. Final loaded forbidden
  modules: `[]`. Exact commands and actual output are in `G03_TEST_RESULTS.txt`.
- Scoped diff check passes. Ruff 0.16.10 reports **zero new diagnostics**:
  normalizer 10 before / 10 after, new test file 0. Full-file lint is not clean.
- AST comparison confirms `_upsert_author`, `_ensure_variant`,
  `record_occurrences`, the link IntegrityError handler and the entire service
  entry point are unchanged. G04 rollback/race recovery is not fixed or modified.
- SHA-256 inventory checks cover 1,566 pre-existing, Git-listed files (tracked
  and non-ignored untracked): only the intended normalizer changed; 1,565 remained
  identical. G01/G02 source, tests and artifacts are included in that check.
  Inventory exclusions and individual changed-file hashes are explicit in JSON.

## Limits and later verification

No DB connection/query/write, migration, real import, reviewer decision, HTTP
execution or concurrency test was performed. Fake persistence tests validate
the JSON assignments and merge behavior, not PostgreSQL durability or locking.
The existing finalize transaction boundaries and G04 integrity recovery remain.
A crash before a checkpoint can still require replay; this is not a new
transaction or append-only audit subsystem.

Historical silent drift is not backfilled. No original raw-source pointer exists
on PublicationAuthor, so the diagnostic identifies the preserved association and
position but does not invent the exact raw row that first established it. The
newer observation has an exact raw/import/row reference. Raw contents are not
cryptographically frozen again in this diagnostic.

The full diagnostic is uncapped in the existing import JSON; large-import JSON
size, checkpoint cost and concurrent normalization require later DB-backed
verification. The API's error sample may omit some drift after 50 errors; the
complete list remains in the import summary. No new UI, conflict resolution,
identity inference, G04 implementation or source-claim intake was started.

STOPPED after G03 for owner review.
