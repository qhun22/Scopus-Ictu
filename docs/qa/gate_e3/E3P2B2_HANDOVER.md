# E3-P2-B2 — Safe staging persistence: handover for independent review

Date: 2026-10-29 · Status: **B2 DELIVERED — STOPPED FOR INDEPENDENT REVIEW** (E3-P3 not started)

**PostgreSQL: NOT_EXECUTED.**
- No authorized disposable test database is configured (no `TEST_DATABASE_URL`).
- No migration was run, and no application or PostgreSQL database was connected.
- No real ICTU data was imported.
- No identity, candidate or review row was created or changed.

## 1. Files (all new; no existing file modified)

| File | Purpose |
|---|---|
| `backend/app/services/source_staging/__init__.py` | new package, kept outside the pure `source_claims` package |
| `backend/app/services/source_staging/service.py` | `SourceStagingService`, `Actor`, `IngestResult`, `ActivationResult`, `ingest_outcome` |
| `backend/tests/source_staging_fixtures.py` | synthetic harvest and snapshot builders; SQLite mirror of the schema |
| `backend/tests/unit/test_source_staging_service.py` | 33 tests on the SQLite mirror |
| `backend/tests/integration/test_source_staging_service_pg.py` | 4 PostgreSQL tests, gated on `isolated_db_engine` (not run) |

The following are unchanged, hash-verified (16/16):
- the accepted P1, P2-A and B1 code and tests;
- the models, migration `a77e01c33ee1`, the views and `pyproject.toml`.

G01–G04 are unchanged (31/31). There are no API endpoints and no frontend changes.

## 2. Public surface (no HTTP yet)

| Method | Trust boundary |
|---|---|
| `ingest_harvest(lecturers_bytes, lecturers_sha256, manifest_bytes, replay_bytes, crawl_report_bytes?, upstream_storage_ref?)` | **only** through `provenance.bind_and_build_profiles_artifact`. The direct adapter path is never used. |
| `ingest_guide_snapshot(snapshot_bytes, snapshot_sha256, layout=TABLES\|MULTI_ID, completeness, declared_counts?, …)` | bound to its exact bytes and SHA-256. These snapshots have no manifest or replay, so none is invented: completeness is the caller's explicit statement, and it is recorded in the capture. |
| `activate_rule_set(reason?)` | activates the **running code's** rule versions (§5) |
| `active_rule_set()` / `compare_captures(previous, current)` | read-only |

There is no public method that accepts arbitrary artifact bytes.

## 3. Lifecycle and idempotency

`VERIFIED ARTIFACT → CONTENT → CAPTURE → ARTIFACT → ANALYSIS → RECORDS → CLAIMS`.

- **Layer checks:** each layer is `INSERT … ON CONFLICT DO NOTHING` (dialect insert), then re-selected by its natural key. "Exactly one row" is required, otherwise `UNEXPECTED_CONFLICT`. A stored row that disagrees with the artifact gives `STORED_*_MISMATCH`.
- **Outcome:** the first new layer decides it: `CREATED`, `REUSED`, `ARTIFACT_ADDED`, `REANALYSED` or `ALREADY_INGESTED`.
- **Records and claims:** they are inserted only when the analysis row is new.
- **Counter verification, always:** the stored `record_count`/`claim_count` and the actual child counts must equal the snapshot's. Otherwise the result is `ANALYSIS_INCOMPLETE` (fail closed). This also catches an analysis created by a crashed or concurrent writer without its children.
- **Duplicates:**
  - nothing is unique on `claim_key` alone, so different records that claim the same Scopus ID, and duplicate ORCIDs, all stay as separate claim rows;
  - invalid rows are kept as `INVALID` records, with `value_normalized = NULL` claims.
- **Audit:** one `audit_events` row per write operation:
  - `SOURCE_ARTIFACT_INGESTED`, with the outcome, the layers, the hashes, the versions and the counts;
  - `SOURCE_RULE_SET_ACTIVATED`.

  The actor follows the existing invariant (USER with an id, or SYSTEM with a service name).

| Required behaviour | Result (test) |
|---|---|
| First ingest | `CREATED`, all 4 layers new (`test_first_import…`) |
| Identical replay | `ALREADY_INGESTED`; no staging rows, one audit row (`test_identical_replay…`) |
| Reordered JSON keys | same content, new capture: `REUSED` (`test_reordered_json_keys…`) |
| Reordered rows | new content (source order is part of the assertion) with identical record hashes (`test_reordered_rows…`) |
| Same content, new capture | `REUSED`; one analysis, observed per capture (`test_same_content_new_capture…`) |
| Same artifact, new rule version | analysed by activation; artifact rows byte-identical; old analysis kept (`test_new_rule_version…`) |
| Two artifact versions, one capture | 1 capture, 2 artifacts, observed once (`test_two_contract_versions…`) |
| Shared Scopus ID / duplicate ORCID / invalid row | all preserved (three tests) |

## 4. Withdrawal and source changes

`compare_captures` is **read-only**. It rebuilds each capture's stored artifact (the highest contract
minor, as the view selects), checks it against its stored hash, re-parses it and runs the accepted
P1 `presence_diff`.

- **Comparability:** it requires COMPLETE + COMPLETE, the same scope, the same contract major and rule
  versions, and chronological order (the P1 rules). It adds one capture-level condition: the **same
  `projection_version`**. Otherwise the reason is `PROJECTION_DIFFERS`, and every WITHDRAWN or
  KEY_UNSTABLE entry becomes NOT_OBSERVED.
- **PARTIAL:** never withdraws (tested for a PARTIAL guide capture, and for a harvest with a
  `lecturer` failure).
- **BLOCKED:** a replay that did not pass is refused at binding (`SOURCE_REJECTED_REPLAY_NOT_PASSED`),
  so it is never stored.
- **Distinctions kept:** WITHDRAWN, RECLASSIFIED, NOT_OBSERVED, KEY_UNSTABLE and OWNER_UNVERIFIABLE
  stay distinct (P1 statuses).
- **Identities untouched:** a withdrawal is a report only. It never writes, and never revokes or
  touches a reviewer-approved identity.
  - `test_reviewer_approved_identities…` inserts an APPROVED identity, then runs ingest, a withdrawal
    comparison and a rule-set activation. Every non-staging, non-audit table, all 25 of them, is
    byte-identical afterwards.
  - `test_the_service_only_inserts…` records every SQL statement. All writes are `INSERT`, there is
    no UPDATE or DELETE, and they target only staging tables and `audit_events`.

## 5. Rule-set activation: explicit order, no incomplete exposure

1. **Ingest gate:** ingest runs only when the active rule set **equals** the running code's
   `(IDENTITY_RULES_VERSION, NORMALIZATION_VERSION)`. Otherwise it returns `NO_ACTIVE_RULE_SET` or
   `RULE_SET_MISMATCH` before any write. Stale code cannot add analyses that would be invisible, and
   new code cannot write before activation.
2. **`activate_rule_set()`**, inside one SAVEPOINT:
   1. take the exclusive lock;
   2. for **every** stored artifact: rebuild its bytes from the rows, verify them against
      `artifact_bytes_sha256` (`STORED_ARTIFACT_CORRUPT`), re-parse, and ensure the analysis under
      the target rules (counters verified);
   3. insert the `source_rule_sets` row;
   4. prove coverage: every artifact has a target-rule analysis, and every capture has exactly one
      active rank-1 row in `source_capture_analyses` (`ACTIVATION_INCOMPLETE` otherwise);
   5. write the audit event.

   Any failure rolls back the whole activation. Old rules stay active, and old analyses are never
   modified.
3. **Visibility:** readers see the old rules until the caller commits, then the new ones atomically.
   The view is never empty or duplicated mid-reanalysis (tested: a corrupt artifact and a pre-existing
   childless analysis both keep the view on the old rules).
4. **Serialization (PostgreSQL only):** transaction-scoped advisory locks. Activation takes the lock
   exclusively and ingests take it shared, so an activation waits for open ingests and vice versa.
   SQLite serializes writers itself. Execution of this on PostgreSQL is NOT_EXECUTED (see the PG test).

No schema change was needed.

## 6. Transaction safety

- **The caller owns the transaction.** The service never commits or rolls back the outer
  transaction. Each write operation runs in its own SAVEPOINT, after a `flush()` (the G04 lesson: a
  pending earlier failure is not absorbed). A failure rolls back only that operation, and earlier
  work in the caller's transaction survives (`test_failure_rolls_back_only_the_failing_ingest`).
  There is no helper-level full rollback.
- **No counters outside the database.** Results are built only after the database verification
  succeeds.
- **Unexpected `IntegrityError`** gives `StagingError("INTEGRITY_VIOLATION")` after the savepoint
  rollback (fail closed). Expected key conflicts are absorbed by `ON CONFLICT DO NOTHING` and then
  proven by re-selecting.
- **Races:**

  | Case | Status |
  |---|---|
  | rows committed by another transaction are reused, not duplicated | tested on two SQLite sessions |
  | a concurrently created but childless analysis is refused | tested |
  | true two-connection race | PostgreSQL test written, **not executed** |
  | activation waiting on an open ingest | PostgreSQL test written, **not executed** |

- **Mutation probes** (each safeguard disabled in memory):

  | Safeguard removed | Result |
  |---|---|
  | count verification | 2 tests fail |
  | savepoint | 3 fail |
  | rule-set gate | 1 fails, 26 errors |
  | coverage check | 1 fails (it is a second layer behind per-artifact analysis) |

## 7. Verification

| Check | Result |
|---|---|
| Pure/offline suites: P1 + P2-A + B1 schema + provenance + **B2 service** (`--noconftest`) | **280 passed** (247 + 33) |
| B2 focused | 33 passed |
| PostgreSQL tests (4) | **NOT_EXECUTED**; the module imports without a database. With the project conftest, the run stops at the isolation guard (exit 4) |
| Ruff (source_staging, source_claims, staging model, fixtures, all test files) | exit 0 |
| Eight-diff replay (P1 → errata → closeout → P2-A → correction → B1 → B1 correction → B2), `--whitespace=error` | all OK; 5/5 files reproduce the workspace; reverse check OK |
| Accepted E3 files | 16/16 unchanged |
| G01–G04 | 31/31 MATCH |
| `git status` | the same 17 tracked modifications as after B1; B2 adds only untracked files |

## 8. Remaining risks

1. **No PostgreSQL run.** Not exercised on PostgreSQL:
   - the CHECKs, generated and identity columns, `ON CONFLICT` and advisory locks;
   - the view SQL and real concurrency.

   The SQLite mirror exercises the unique constraints, the staging FKs, savepoints and the view logic,
   but not the CHECKs or locks. Run `test_source_staging_service_pg.py` and the G04 tests on an
   authorized disposable database before any real import.
2. **Long transactions:** the shared advisory lock is held until the caller commits, so a long ingest
   transaction delays activation. That is by design, but callers should commit per ingest.
3. **Failure audit is the caller's job.** The success audit lives inside the savepoint; when an
   operation fails nothing is audited by the service, so the caller (a future API or job) should
   record the failure.
4. **Comparisons use the current code.** `compare_captures` re-parses stored artifacts with the
   running code, which equals the active rule set (enforced at ingest).
5. **Mutation-probe coverage:** the coverage check is only exercised indirectly, as the second safety
   layer.
6. **Owner decisions O-2 and O-7.** These are still recorded as pending. The user indicated the
   intended answers: raw files outside Git with checksums and restricted access; no birth date,
   gender or phone in staging. The adapter already implements O-7.
7. **CLAUDE.md** still states an outdated migration head.

STOPPED after B2. E3-P3 (candidate/reviewer integration) not started.
