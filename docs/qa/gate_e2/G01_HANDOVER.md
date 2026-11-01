# Gate E.2 / P0-A — G01 duplicate lecturer URL mapping

Date: 2026-10-29 (Asia/Bangkok). Baseline HEAD: `4bb69f6efaac945399b1c191fc12879ad1c62885`.
Scope: G01 only, authorized after Gate E.1 acceptance for implementation planning. No G02/G03/G04 fixes, source-claim ingestion, migrations, real imports, identity decisions or commits/pushes.

## Result

Canonical repository URLs now map to sets of distinct lecturer UUIDs. Exactly one UUID is eligible, even if the query repeats that row. Multiple UUIDs produce `AMBIGUOUS_LECTURER`; the service's preview error includes the source URL and deterministically sorted canonical UUIDs with an instruction to resolve the duplicate `repository_profile_url`.

Both preview and direct apply check ambiguity before planning snapshots/publication attributions. Preview reports `ambiguous_lecturer_count` and `invalid_records`; it proposes zero writes for affected records. Direct service apply returns the ambiguous URL/error and skips that record entirely, including any existing snapshot/publication reuse. Unrelated unique URLs remain eligible. Direct apply keeps the existing per-record skip policy; it does not raise a new all-batch exception.

Existing CLI/web wrappers use `blocking_problems()` and refuse the whole apply when preview reports ambiguity. The shared summary exposes `AMBIGUOUS_LECTURER` counts; the detailed actionable URL/UUID diagnostic is in `IngestionPreview.errors`. Existing frontend presentation and wrapper response shapes were not changed.

URL comparison remains exact, as in this service before the fix. No trimming, case folding, trailing-slash rewriting, new normalizer, unique constraint or lecturer merge was introduced. Other importers' normalization rules were not transplanted into this path.

## Exact changed application/test files

| File | Change / rationale |
|---|---|
| `backend/app/services/lecturer_dataset/known_publication_ingestion.py` | `_ambiguous_lecturer_error()` lines 254–263 provides stable remediation details; `_build_lecturer_index()` lines 347–364 retains distinct IDs; `preview()` lines 394–524 and `apply()` lines 554–816 skip ambiguous records. Corrected the stale comment claiming duplicated canonical URLs were impossible. No other application file changed. |
| `backend/tests/unit/test_known_publication_ingestion.py` | Fake session accepts repeated query rows and records statements. `TestLecturerUrlMapping` lines 179–409 adds 15 parametrized cases covering unique/repeated IDs, repeated source rows, ambiguity in both row orders, preview/apply safety, valid mixed input, unchanged exact URL semantics, shared wrapper blocking, existing evidence preservation and no identity/review table access. |

The existing evidence test compares pre-existing snapshot/KP field values, verifies no additions on ambiguous input, and checks no identity/review SQL is issued. It is a fake-session boundary test, not proof of persisted real reviewer decisions. The repeated-source-row test intentionally exercises mapping/snapshot reuse with no publications; it does not claim to fix unrelated same-batch publication dedup behavior.

## Actual validation

- Before backend change, the initial 14-case regression class produced **7 FAIL / 7 PASS**, demonstrating the missing ambiguity behavior. The complete output is in `TEST_RESULTS.txt`.
- Final complete ingestion unit module: **39 PASS** (24 existing cases plus 15 new parametrized cases), exit code 0.
- The final run disabled plugin autoload and conftest discovery, disabled pytest cache and bytecode writes, blocked socket connections, and asserted that `app.main`, `app.core.database` and conftest modules were not loaded. All sessions were in-memory fakes; no engine/DB fixture was invoked.
- Scoped `git diff --check` for the two changed files: **PASS**.
- Ruff on those files is **not clean**: 12 remaining baseline diagnostics (6 service, 6 test). Comparing code/message/source-line signatures to HEAD found **zero new diagnostics**; the previously unused pytest import is now used, reducing total diagnostics from 13 to 12. Unrelated lint cleanup was not performed.

Reproduce the pure module run from `backend/` in PowerShell with the existing project environment:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '..\.venv\Scripts\python.exe' -B -m pytest --noconftest -p no:cacheprovider tests/unit/test_known_publication_ingestion.py -q
```

The exact additional socket/module guard command and captured final output are in `TEST_RESULTS.txt`. `--noconftest` isolates this inspected fake-only module from the existing DB-oriented root conftest; it is not authorization to run other modules without their safety fixtures. No test configuration or DB guard was changed.

## Preview/apply safety evidence

| Case | Preview assertion | Apply assertion |
|---|---|---|
| Shared URL, two distinct lecturers; both query orders | ambiguity=1, invalid=1, mapped=0, new snapshots/KPs=0; actionable error | ambiguous URL returned; new/reused snapshots/KPs=0; no added object |
| Same lecturer row repeated | mapped=1, ambiguity=0 | snapshot/KP belongs to that one UUID |
| Duplicate source rows, same lecturer | no false ambiguity | one snapshot plus reuse; no arbitrary choice |
| Ambiguous plus unrelated unique URL | only unique record planned | only unique lecturer UUID appears in added rows |
| Existing ambiguous evidence | preview makes no writes | existing snapshot/KP fields unchanged; no identity/review table access |
| Shared CLI/web guard | ambiguity and error code survive preview summary | `blocking_problems()` returns an ambiguity blocker; existing wrapper source checks this before calling apply |

Wrapper source inspected: `backend/scripts/ingest_craw_known_publications.py:174-203`; `backend/app/services/lecturer_dataset/craw_ingestion_workflow.py:81-97`, `116-134`. The shared blocking function is exercised by a pure test; HTTP/CLI database integration was NOT_EXECUTED.

## Preservation, limitations and handover

Initial unrelated research edits and untracked Gate D/E.1 files were preserved. `VALIDATION.json` records before/after protected-tree hashes, changed-file hashes and test/lint results. Gate D, research, Gate E.1, frontend, migrations and other backend/test files remain unchanged by this task. `G01_IMPLEMENTATION.diff` is the real Git unified diff of the two implementation/test files; handover artifacts are new files under `docs/qa/gate_e2/`.

No live DB duplicate count, actual imported lecturer count, DB-backed decision-preservation/concurrency test or browser check was performed. Concurrent canonical URL edits after the lookup are not serialized by a new lock/constraint in this patch. Existing transaction/dedup policies are retained. These limits do not reduce the tested guarantee that a lookup returning two distinct canonical IDs never selects one for the affected source record.

G01 is ready for owner review. Stop here; G02–G04 and raw source-claim intake require the next separately scoped authorization.
