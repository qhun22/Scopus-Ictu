# E3-P2-B2 audit closeout (B2-R1): handover for review

Date: 2026-10-29 · Status: **CORRECTION DELIVERED — STOPPED FOR REVIEW** (E3-P3 not started)

## Defect and fix

`activate_rule_set()` inserted the `source_rule_sets` row with one `uuid.uuid4()`, but audited
`SOURCE_RULE_SET_ACTIVATED` with a second, unrelated `uuid.uuid4()`.

**Fix** (`backend/app/services/source_staging/service.py`, +3/−2): generate `rule_set_id` once, use
it for the inserted row, and pass the same id to `_audit(...)`. The following are unchanged:
- the savepoint and transaction boundaries;
- the activation order and the `ALREADY_ACTIVE` path;
- the ingest audit, which already used the real `artifact_id`, now pinned by a test.

## Regressions (`backend/tests/unit/test_source_staging_service.py`, +69)

| Test | Proves |
|---|---|
| `test_b2_r1_activation_audit_references_the_persisted_rule_set_row` | 2 activations give 2 rows and 2 audits; every audit `entity_id` is a persisted rule-set id, and the metadata versions and reason equal that row; the ingest audit references the real `artifact_id` |
| `test_b2_r1_failure_after_the_rule_set_insert_leaves_no_row_and_no_audit` | an injected failure **after** the rule-set row was inserted (asserted inside the hook) rolls back the row and leaves no success audit; old rules stay active |
| `test_b2_r1_failed_reanalysis_leaves_no_activation_audit` | a corrupt stored artifact means no activation audit |
| `test_b2_r1_already_active_writes_no_row_and_no_audit` | `ALREADY_ACTIVE` is unchanged: no row and no audit |

**Old defect re-injected** (a pytest plugin gives rule-set audits an unrelated UUID, as in the accepted
B2): the first regression fails and the other 36 tests pass. The test detects exactly this defect.

## Verification

| Check | Result |
|---|---|
| B2 focused | **37 passed** (33 + 4) |
| Full offline suite (P1 + P2-A + B1 schema + provenance + B2) | **284 passed** (280 + 4) |
| Ruff (source_staging, source_claims, staging model, fixtures, all test files) | exit 0 |
| `E3P2B2_CORRECTION.diff` against the accepted B2 | 2 files; whitespace clean |
| Nine-diff replay (P1 → … → B2 → B2 correction), `--whitespace=error` | all OK; both files reproduce the workspace; reverse check OK |
| Other B2 files (`__init__`, fixtures, PostgreSQL test) | 3/3 unchanged |
| Accepted E3 files (P1, P2-A, B1, B1 correction, `pyproject.toml`) | 16/16 unchanged |
| G01–G04 | 31/31 MATCH |
| `git status` | the same 17 tracked modifications |

**Not changed:** the models, migration, views, adapters, provenance and identity code.

**Not done:** no PostgreSQL connection or migration, no real data, no reviewer decision, no commit or
push.

**Still pending:**
- PostgreSQL execution of the staging migration, the 4 B2 tests and the G04 tests, on an authorized
  disposable database, before any real import;
- formal confirmation of O-2 and O-7.

STOPPED after B2-R1.
