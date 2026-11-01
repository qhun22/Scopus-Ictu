# E3-P3-B2-E — PostgreSQL validation of the B2-D hybrid persistence

Date: 2026-11-01 · **Decision: PG_VALIDATED** (PostgreSQL 17.10, one target, scope below).
SOURCE_CLAIM production workflow remains **INACTIVE**. No commit, push or production migration.

The most important limit up front: **append-only is not enforced by the database** (see §5). The
CHECK, UNIQUE and FK constraints and the service protect recorded history; the owning role can still
`UPDATE` unconstrained columns and `DELETE` leaf rows.

## 1. Safe target (no credentials)

| Item | Value |
|---|---|
| Server | PostgreSQL 17.10, Windows, started from the installed 17 binaries |
| Instance | **new throwaway cluster**, own data directory in the session scratchpad, loopback `127.0.0.1:54329` only |
| Database | `scopus_ictu_test_pytest_e3p3b2e`; role is a cluster superuser, password auth (scram-sha-256), password not recorded |
| Cluster identity | `system_identifier` 7702994310001884572 |
| Not used | the existing service on port 5432 (forbidden by the guard) was **never connected to**; no application, teacher, demo or production database was touched |
| Guard | `db_safety_guard.py` unchanged in logic; every guard layer (allowlist, blocklist, port, loopback, URL/server cross-check, cluster identity) ran on every fixture |
| After the run | server stopped; no database process left running; data directory kept in the scratchpad |

**Owner-approved guard edit (asked first, 2026-11-01).** The guard trusts a local database only by
exact name plus the recorded cluster identity, so a new cluster is refused unless a reviewed entry
exists. I added exactly two data lines and a comment in `backend/tests/db_safety_guard.py`: the new
database name in `ALLOWED_TEST_DATABASE_NAMES`, and `{name: 7702994310001884572}` in
`EXPECTED_LOCAL_CLUSTER_SYSTEM_IDENTIFIERS`. **Owner action:** keep or remove this entry. It is only
meaningful while that scratchpad data directory exists.

`psycopg` (v3) was **not** needed: the tests use `postgresql+psycopg2` (`psycopg2-binary`, already a
project dependency). Nothing was installed.

## 2. Commands and results

```text
. <scratchpad>\pgenv.ps1                 # sets TEST_DATABASE_URL for this shell only
cd backend
python -m pytest tests/integration/test_source_claim_hybrid_persistence_pg.py -v
```

| Run | Result |
|---|---|
| 1. The 14 tests as delivered | **14 errors** in fixture setup: `relation "source_capture_analyses" does not exist` |
| 2. After fixture fix F1 (below) | **14 passed** |
| 3. 12 new tests added (see §4), first run | 5 passed, **7 failed** (3 distinct causes: F2, S1, one over-narrow assertion of mine) |
| 4. After F2, S1 and the assertion fix | **26 passed, 0 failed, 0 skipped** (41.5 s) |
| 5. Stability: concurrency, lock and revoke/supersede tests, 4 further runs | 8 passed each time |

Offline checks of what changed:

| Command | Result |
|---|---|
| `pytest tests/unit/test_source_claim_hybrid_persistence.py --noconftest` | 30 passed |
| the 7 `tests/unit/test_source_claim_*` files that share these modules (excluding the matching bridge) | **323 passed** |
| `ruff check` on the three changed Python files | all checks passed |
| `pytest tests/unit/test_db_safety_guard.py` | 22 passed, **3 failed**: `ModuleNotFoundError: psycopg` when the test calls `create_engine("postgresql://…")` (SQLAlchemy 2.1.6 defaults that URL to psycopg v3, which is not installed). Environment mismatch; independent of my data-only edit; not fixed |

Not run: the 1,121-test suite, the 597-test audit, B2-B/B2-C regression (their files are unchanged),
and the staging-migration, B2 and G04 PostgreSQL tests (outside this task).

## 3. Defects found and fixed

| # | Where | Defect (demonstrated) | Fix |
|---|---|---|---|
| F1 | PG test fixture | built the staging tables with `create_all`, but the two staging views exist only in migration `a77e01c33ee1`; `SourceStagingService.activate_rule_set()` queries `source_capture_analyses`, so all 14 tests errored | the fixture now creates both views from the model SQL (a unit test already pins model == migration) |
| F2 | PG test fixture | ran the migration without `target_metadata`, unlike `alembic/env.py`; PostgreSQL then named primary keys `*_pkey` instead of the project convention `pk_*`. Found by the new catalog test | `MigrationContext.configure(conn, opts={"target_metadata": Base.metadata})`, as in `env.py` |
| S1 | **service** | idempotency was resolved before the per-stream advisory lock and never again after it. With two identical concurrent requests the loser raised `HYBRID_HISTORY_INTEGRITY_VIOLATION` instead of resolving to `ALREADY_RECORDED` (4/4 runs). No duplicate was ever written; the refusal was fail-closed, but the retry contract was not met | in `record_proposal`, `record_exception_approval` and `record_revocation`, the idempotency key is re-resolved right after the lock. In `record_revocation` the lock now precedes the replay check **and** the already-compensated check, so a concurrent *different* compensation gets the proper business refusal, not a raw constraint error |

An over-narrow constraint-name assertion in my own new cross-candidate test was also corrected; the
database had refused the update correctly (`fk_sc_hybrid_proposals_context_pair_policy`).

The existing `test_pg_concurrent_identical_proposals_record_exactly_one_event` accepts a refusal for
the loser and so could not detect S1. It is unchanged; the strict test below replaces it as the
evidence.

## 4. Changes (paths)

| File | Change |
|---|---|
| `backend/app/services/source_claim_hybrid_persistence.py` | S1: three post-lock `_recorded` re-checks; revocation lock moved earlier (about 12 lines) |
| `backend/tests/integration/test_source_claim_hybrid_persistence_pg.py` | F1, F2, the assertion fix, and 12 new tests (6 functions, parametrized) |
| `backend/tests/db_safety_guard.py` | the two approved data entries |
| `docs/qa/gate_e3/E3P3B2E_PG_VALIDATION.md` | this document |

Models, migration `c99a03e55ff3`, frozen contracts and all earlier accepted tests are unchanged. No
frozen contract needed to change.

## 5. Task 2 checklist: what PostgreSQL showed

| Item | Result | Protection is |
|---|---|---|
| 1. Fresh migration upgrade in a disposable schema | pass, every test | DB |
| 2. Constraint inventory | `test_pg_catalog_constraints_match_the_models`: live `pg_constraint` names for all 7 tables equal the models' (PK, UNIQUE, FK, CHECK), none missing, none extra | DB |
| 3. Tampering refused | 7 UPDATEs rejected by CHECKs: independently-verified flag, snapshot hash, envelope hash, `actor_type`, null principal, source tier, revoked issuance state | **DB** |
| 4. Append and idempotent retry | pass (sequential and concurrent) | service (+ UNIQUE `operation_key`) |
| 5. Two concurrent appends | strict test, 4 runs: one `APPENDED`, one `ALREADY_RECORDED`, one event stored (after S1) | service under the advisory lock; UNIQUE as backstop |
| 6. Advisory-lock serialization | a second writer is observably blocked (`pg_locks`, one ungranted advisory lock) until the first commits, then replays | service (`pg_advisory_xact_lock`) |
| 7. Rollback and SAVEPOINT ownership | a failed approval inside the caller's transaction leaves the caller's earlier `users` write intact and visible; no event or approval remains from the failed call; the caller commits afterwards | service |
| 8. Proposal/approval principal separation | an approval by the proposer's own user and principal is refused | **DB** CHECK (plus service rule) |
| 9. Cross-candidate reuse | re-pointing a proposal at another candidate is refused by the composite FK `fk_sc_hybrid_proposals_context_pair_policy`; the service also binds an approval to its proposal's branch and reviewer | **DB** FK + service |
| 10. Revoke / supersede | both append event 3 with an intact `previous_event_id`/`previous_event_hash` chain; an identical retry replays; a different second compensation gets `HYBRID_EVENT_ALREADY_REVOKED`; no identity row is written | service + UNIQUE |
| 11. SOURCE_CLAIM submit | `submit()` raises `SOURCE_CLAIM_WORKFLOW_INACTIVE`; no identity, evidence or event | service |
| Also | chain fork refused; a second approval of one proposal refused (UNIQUE); the downgrade raises and keeps recorded history | **DB** |

### Append-only is NOT database-enforced

`test_pg_append_only_is_not_enforced_by_the_database` characterizes this:
- the seven tables have **0 triggers, 0 rules and no ACL restrictions**;
- as the owning role, `UPDATE sc_hybrid_events SET action_at = …` (covered by no CHECK) and
  `DELETE FROM sc_hybrid_approvals` both **succeed** (the test then rolls back).

What the database does enforce is limited to the CHECK/UNIQUE/FK constraints above. Nothing in the
migration grants or revokes privileges, so which role may modify history depends on how the
application role is provisioned, which this task could not inspect and did not test. The test must be
inverted when `REVOKE UPDATE, DELETE` for the application role or triggers are added.

## 6. Remaining risks

1. **No DB-level append-only** (above). Hardening needs a design decision on roles and grants.
2. **Tested as a superuser.** Privilege-dependent behaviour was not exercised.
3. **PostgreSQL 17.10 only.** `compose.yaml` uses `postgres:16`; the features used (advisory locks,
   generated and identity columns, `ON CONFLICT`) exist in 16 but were not run there.
4. **READ COMMITTED assumed** for the post-lock re-check. Under REPEATABLE READ or SERIALIZABLE a
   loser would not see the winner's row and would still get the (fail-closed) constraint refusal.
5. **One cluster, one machine.** Concurrency is two threads and four short repeats, not a stress test.
6. **Chain-hash linkage** is computed by the service. The database enforces the unique successor and
   foreign key, not that `previous_event_hash` equals the predecessor's hash; the tests verify it for
   the flows exercised.
7. The staging migration, the 4 B2 service PostgreSQL tests and the G04 PostgreSQL tests were not run
   here. The same disposable target can run them once their names are accepted by the guard, which
   they already are since they use the same conftest.
8. The 3 failing guard unit tests need `psycopg` v3 or a `+psycopg2` URL in those tests.

## 7. Antigravity review items

None were supplied.

## 8. Final decision

**PG_VALIDATED** for the B2-D persistence, migration `c99a03e55ff3` and its 26 PostgreSQL tests on
PostgreSQL 17.10, with the limits in §6 and the explicit statement that append-only history is
service- and constraint-protected, **not** database-enforced. This is not a production-readiness
claim, and SOURCE_CLAIM stays INACTIVE.
