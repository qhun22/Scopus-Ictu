# Gate E.2 / G04 — Transaction Rollback Safety in Author Normalization

Date: 2026-10-29. Status: **IMPLEMENTED; READY FOR OWNER REVIEW.**
PostgreSQL verification: **NOT_EXECUTED** (no authorized disposable DB was available; see §8).
No commit, push, migration, DB connection, real import or identity decision.

## 1. Takeover findings (before any edit)

- `git status --short -uall`: the accepted G01/G02/G03 changes are uncommitted in the
  working tree, as stated in the handover. Git HEAD (`4bb69f6`) does not contain them.
- `scopus_author_normalizer.py` = HEAD + the G03 diff, **identical** to
  `G03_IMPLEMENTATION.diff` (107/107 changed lines). `test_author_position_drift.py` is
  identical to the file in that diff (393/393 lines).
- **No partial G04 work by Codex.** All three helper-level `db.rollback()` calls and the
  docstring claim "upsert-safe via savepoint" were still present, with no `begin_nested()`.
- A copy of the pre-G04 normalizer was saved outside the repository and used as the diff
  baseline and for the behavioral baseline run. Files were not restored from HEAD, and no
  unrelated dirty file was touched.

## 2. Root cause

Each of `_upsert_author`, `_ensure_variant` and `_ensure_publication_author_link` handled
`IntegrityError` with `db.rollback(); db.flush()` and then kept going. `Session.rollback()`
ends the **whole** outer transaction. Every author, variant and link flushed earlier in the
batch (up to 500 raw rows) was silently discarded. The batch then committed only the rows
written after the error, the counters still included the lost rows, and the run reported
`COMPLETED` with HTTP success.

In addition:
- the variant and link handlers counted **any** `IntegrityError` as "existing", including
  FK and CHECK violations;
- on a failed batch, the in-memory counters (and G03 observations) of the rolled-back
  batch were written into the `FAILED` summary.

## 3. Changes — exact scope

| File | Change |
|---|---|
| `backend/app/services/normalization/scopus_author_normalizer.py` | Constants and `integrity_violation()` (l.62–82); `_insert_in_savepoint()` (l.85–114); `AuthorNormalizer.batch_checkpoint()` and `restore_batch_checkpoint()` (l.422–434); handlers in `_upsert_author` (l.480), `_ensure_variant` (l.519), `_ensure_publication_author_link` (l.563; keyword-only `_after_conflict` plus a 4-line guard); batch loop in `normalize_authors_for_import` (l.848 checkpoint; l.878–892 failure path); docstring invariant 1. **+115 / −30 lines.** |
| `backend/tests/unit/test_author_position_drift.py` (G03) | Test double only: `FakeSession.begin_nested()` returns `contextlib.nullcontext()`, plus the import. **No G03 assertion changed.** Required because G03's fake session had no savepoint API. |
| `backend/tests/unit/test_author_normalizer_transactions.py` | New: 24 pure tests. |
| `backend/tests/integration/test_author_normalizer_transactions_pg.py` | New: 11 PostgreSQL tests (P1–P10), not executed. |

The G03 logic (existing-link drift check, `AUTHOR_ORDER_MISSING`, slot conflict,
`_record_position_discrepancy`, `_merge_position_discrepancies`, `finalize`) is unchanged.
The endpoint, models, migrations, eligibility rules and checkpoint cadence are also unchanged.

## 4. Transaction design

**Transaction owner:** `normalize_authors_for_import`. The unit of work is one batch: it
commits whole (`db.commit()` per batch) or rolls back whole. Helpers never end a transaction.

**Insert sequence** (`_insert_in_savepoint`):

```
db.flush()                       # 1. boundary: flush earlier pending state OUTSIDE recovery
try:
    with db.begin_nested():      # 2. its own unconditional pre-SAVEPOINT flush is now a no-op
        db.add(obj)              # 3. the object enters the session INSIDE the savepoint
        db.flush()               # 4. the only INSERT inside the savepoint
except IntegrityError as exc:    # 5. try is OUTSIDE the with: savepoint already rolled back
    recognized unique?  -> return exc (caller re-queries the exact key)
    anything else       -> raise      (batch owner rolls back everything, FAILED)
```

- **Why step 1 exists.** SQLAlchemy 2.0.41 `SessionTransaction._take_snapshot` calls
  `session.flush()` for any non-BEGIN transaction, regardless of `autoflush=False`. Without
  step 1, a failure from earlier pending state would be raised under a `try` that recovers
  unique violations, and it could be mistaken for this row's conflict.
- **Savepoint rollback leaves earlier rows alone.** `_restore_snapshot(dirty_only=True)`
  expunges only the object added inside the savepoint and expires only state modified
  there. Earlier flushed rows of the batch stay in the outer transaction. No error is
  caught inside the `with` block, so the transaction is never left half-failed.

**Before/after timeline** (concurrent runs; T2 has already flushed N rows in its batch):

| step | before G04 | after G04 |
|---|---|---|
| T1 inserts author S and commits | — | — |
| T2 INSERT S → `UniqueViolation` | `db.rollback()`: **N rows lost**, transaction ended | `ROLLBACK TO SAVEPOINT`: only the S insert is undone |
| T2 recovery | re-query S, continue in a new transaction | re-query S by exact key; if absent, raise |
| T2 batch commit | commits only post-error rows; counters include lost rows; `COMPLETED` | commits all N rows plus the rest; counters match |
| T2 FK/CHECK error on a link | counted as `links_existing`, run `COMPLETED` | raised; batch rolled back whole; `FAILED`; exception re-raised (endpoint returns error) |

## 5. Constraint handling

Names come from `alembic/versions/e5b3cf21c1d12b64_0001_initial_schema.py` (l.562, 603,
657, 661, 665) and the frozen naming convention (`models/base.py`). No later migration
references them; a unit test checks this statically, and P5 checks the live catalog.
Identification uses `orig.pgcode`/`sqlstate` plus `orig.diag.constraint_name`. There is
deliberately **no message parsing**, so an unidentifiable violation is never recovered.

| Helper | Recovered (SQLSTATE 23505 only) | Proof after recovery | Everything else |
|---|---|---|---|
| author | `uq_scopus_authors_scopus_id` | re-query `scopus_id` → `authors_existing` | raise |
| variant | `uq_author_name_variants` | re-query `(author, type, name)` → `variants_existing` | raise |
| link | `uq_publication_authors_author`, `uq_publication_authors_order` | re-enter the replay path once: pair → `links_existing` plus G03 drift; slot → `AUTHOR_ORDER_CONFLICT` | raise; also raise if neither row is visible |

FK (23503), CHECK (23514), other or future unique constraints, and a recognized name in the
wrong helper (e.g. the order constraint on a variant) all fail closed.

## 6. Counter behavior

- **During a batch:** `*_created` increments only after the savepoint succeeds. `*_existing`
  and `conflicts` increment only after a re-query proves the row.
- **On batch failure:** `batch_checkpoint()` (deep copy of counters, errors and G03
  `position_discrepancies`, taken before each batch) is restored after `db.rollback()`. The
  `FAILED` summary then describes committed state only, and one `AUTHOR_BATCH_ROLLED_BACK`
  error records the row range and exception type. Earlier committed batches are kept, and a
  replay re-derives the failed batch from the unchanged raw rows.

## 7. G03 compatibility

All 24 G03 tests pass unchanged (test double extended only).
- **Drift found through a race** is reported exactly as on replay: canonical position kept,
  `AUTHOR_POSITION_DRIFT` with provenance.
- **Drift observed in a rolled-back batch** is dropped with that batch. It is not presented
  as recorded, and a replay re-observes it.
- **Drift from committed batches** stays in the `FAILED` summary through G03's merge.
- No canonical author position is overwritten. No identity, review, candidate or decision
  model is read or written: the fake session rejects any unknown model.

## 8. Tests

| Suite | Result |
|---|---|
| G04 pure unit (24) + G03 (24) + parser (27) | **75 passed**, exit 0, no DB/app/conftest module loaded, network blocked |
| Same 24 G04 tests on the **pre-G04** normalizer | **16 failed / 8 passed** (shows the tests detect the old behavior) |
| PostgreSQL P1–P10 (11 tests) | **NOT_EXECUTED** — collected only |
| Ruff (normalizer, G03 test, existing integration test) | 46 → 46, identical set, **0 new**; new files clean |

**Unit coverage:**
- constraint classification;
- static migration-name check;
- savepoint ordering;
- pending-duplicate boundary (a recognized name still fails closed);
- author, variant, link-pair and link-slot races;
- FK and CHECK violations;
- unrecognized unique constraint;
- recognized conflict without a provable row (×3);
- wrong-helper constraint;
- failed batch atomicity and counters;
- G03 observations kept or dropped by batch outcome;
- replay idempotency;
- reviewer identity untouched.

**PostgreSQL tests (written, not executed):**
- P5: catalog names, and the real SQLSTATE and constraint for each violation;
- P1: hook-driven race keeps earlier writes;
- P2: real two-connection race (blocked insert detected via `pg_stat_activity`, bounded
  waits, `lock_timeout` and `statement_timeout`, guaranteed holder rollback and thread join);
- P3/P4: FK/CHECK batch rollback and `FAILED` counters;
- P6: slot race and pair race with drift;
- P7: pending duplicate gives `PendingRollbackError` (not recovered);
- P8: replay;
- P10: G03 observations kept vs dropped.

Each test uses its own schema in the database behind `TEST_DATABASE_URL`, re-verified by
`db_safety_guard` before cleanup.

**Not proven:** the fake session models savepoint semantics; it is not PostgreSQL.
PostgreSQL transaction safety is **claimed only after P1–P10 pass** on an allowlisted
disposable database (e.g. `scopus_ictu_test_pytest_20261013` on 55432, which was not
running).

## 9. Concurrency assessment

- **Cross-import race** (two imports sharing a Scopus author, variant or link): handled by
  savepoint recovery. A deadlock (40P01) is not an `IntegrityError`, so it fails the batch
  closed and the run can be replayed.
- **Same-import double run:** still possible. Eligibility only requires `APPLIED`. After
  G04 both runs converge without data loss, but they interleave summary writes: the last
  `finalize` wins on `normalization_summary.authors`.
- **No lock was added**, on purpose:
  - a transaction-scoped advisory lock would cover one batch, not the job;
  - a session-level lock is unreliable because the pooled connection may change after each
  commit;
  - a correct guard needs a job-state compare-and-set with stale-run recovery, which is new
  job-state architecture and is left for an owner decision (§10).

## 10. Remaining risks and decisions for the owner

1. **PostgreSQL verification pending.** P1–P10 must pass before G04 is called proven.
   This needs an authorized disposable DB.
2. **Same-import concurrent runs:** summary last-writer-wins. Proposal: a CAS guard on
   `authors.status = NORMALIZING` with a staleness timeout (later task, no migration needed).
3. Deadlocks between concurrent imports surface as `FAILED`. Replay is the recovery path.
4. Pre-existing: the old integration fixture `test_scopus_author_normalization.py::db_session`
   creates schemas in `settings.database_url` (backend `.env`), not `TEST_DATABASE_URL`.
   This was not changed by G04 (out of scope). The new G04 tests use only the guarded engine.
5. Historical data written before G04 is not re-audited. A one-off read-only consistency
   check (summary counters vs rows per import) could be a follow-up.

STOPPED after G04 for independent review. Gate E.3 not started.
