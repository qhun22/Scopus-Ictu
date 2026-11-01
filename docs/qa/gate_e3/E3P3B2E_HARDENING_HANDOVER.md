# E3-P3-B2-E — Targeted security hardening of the hybrid history

Date: 2026-11-01 · **Final status: HARDENING_VALIDATED** (PostgreSQL 17.10: 52/52; addendum: PostgreSQL 16.11: 53/53, see §10).
SOURCE_CLAIM production workflow remains **INACTIVE**. No commit, no push, no application or
production database touched, no migration applied outside per-test disposable schemas.
This is not a production-readiness claim.

Scope: only the confirmed findings F1–F8 against the `sc_hybrid_*` relations. No authority
integration, HTTP endpoint, frontend, IdentityEvidence change or staging foreign key was added.

## 1. Finding-by-finding disposition

| # | Disposition | Where it is enforced | Evidence |
|---|---|---|---|
| F1 | **Fixed** (DB triggers) | `BEFORE UPDATE OR DELETE` row trigger and `BEFORE TRUNCATE` statement trigger on all 7 relations, one shared function, `ENABLE ALWAYS` (so `session_replication_role = replica` does not skip them) | §5 |
| F2 | **Verified present, not rewritten** | post-lock `_recorded` re-check in `record_proposal`, `record_exception_approval`, `record_revocation` | strict race tests for all three paths pass (§6) |
| F3 | **Fixed** | service refuses with `HYBRID_PROPOSAL_NOT_EFFECTIVE` after taking the stream lock; DB trigger on `sc_hybrid_approvals` refuses the same directly | offline + PG tests |
| F4/F5 | **Fixed** | new column `previous_stream_seq` (CHECK `= stream_seq - 1`), `UNIQUE(stream_candidate_id, stream_seq, event_id, envelope_hash)` and composite FK `fk_sc_hybrid_events_chain_link` from `(stream, previous_seq, previous_id, previous_hash)` | §5 |
| F6 | **Fixed** | composite FK `fk_sc_hybrid_events_context_candidate_policy` `(context_id, stream_candidate_id, policy_digest)` → `sc_hybrid_contexts(id, candidate_id, policy_digest)` (new `UNIQUE uq_sc_hybrid_contexts_candidate_policy`) | §5 |
| F7 | **Fixed** (exact table below) | service pre-checks and DB trigger on `sc_hybrid_revocations` | offline + PG tests |
| F8 | **Fixed**, no conflict with a frozen contract | service refuses with `HYBRID_ACTIVE_PROPOSAL_EXISTS`; DB trigger on `sc_hybrid_proposals` refuses a second effective proposal | §6 |

Root/stream-seq semantics are unchanged (root = `stream_seq 1`, no predecessor; successor unique).

**F7 transition table** (an event is *effective* while no REVOKE/SUPERSEDE targets it):

| Action | Allowed target | Replacement | Refused |
|---|---|---|---|
| `PROPOSE` | n/a | n/a | a second one while another proposal of the candidate is effective (F8) |
| `APPROVE_EXCEPTION` | n/a | n/a | approving a proposal that was revoked or superseded (F3) |
| `REVOKE` | an effective `PROPOSE` or `APPROVE_EXCEPTION` | none | targeting a `REVOKE`/`SUPERSEDE` event; a second compensation of one target |
| `SUPERSEDE` | same as `REVOKE` | required: an effective `PROPOSE` or `APPROVE_EXCEPTION` of the same stream, recorded after the target and before the supersession | replacement that is a `REVOKE`/`SUPERSEDE`, already compensated, older than the target, or in another stream |

Consequence of F8 worth knowing: a replacement proposal cannot exist while the old one is effective,
so a `SUPERSEDE` of a `PROPOSE` is reachable only with its `APPROVE_EXCEPTION` as replacement (the
accepted offline test already does exactly that and is unchanged). The way to replace a proposal is
`REVOKE` it, then `PROPOSE` again; both stay in history.

## 2. Exact changed files

| File | Change |
|---|---|
| `backend/alembic/versions/d0b14a77c8e2_e3_p3b2e_hybrid_history_hardening.py` | **new** additive migration (revises `c99a03e55ff3`) |
| `backend/app/models/source_claim_hybrid.py` | `previous_stream_seq` column, its CHECK, chain-link UNIQUE + FK, event→context FK, contexts UNIQUE |
| `backend/app/services/source_claim_hybrid_persistence.py` | lock key via `hashtext(uuid text)`; F3, F7, F8 checks; writes `previous_stream_seq` |
| `backend/tests/integration/test_source_claim_hybrid_persistence_pg.py` | fixture also runs the hardening; 26 new PG tests; 4 existing tests adjusted (below) |
| `backend/tests/unit/test_source_claim_hybrid_persistence.py` | +6 offline lifecycle tests (30 accepted tests untouched) |
| `backend/tests/unit/test_source_claim_hybrid_schema.py` | head pin moved to the new head; item-by-item test now compares c99a03e55ff3 **plus exactly the named hardening items** to the models |
| `backend/tests/unit/test_source_staging_schema.py` | head pin moved (its comment already says the head moves with each accepted revision) |
| `backend/tests/db_safety_guard.py` | net zero change (temporary entries removed, §8) |
| `docs/qa/gate_e3/E3P3B2E_HARDENING_HANDOVER.md` | this report |

Existing PG tests I had to adjust, because a BEFORE trigger now fires ahead of CHECK/FK evaluation.
Each still asserts its original constraint; the append-only triggers are switched off in the test's
own rolled-back transaction (an owner-level bypass) so the constraint itself must refuse:
the 7-case CHECK tamper test; the cross-candidate UPDATE (composite FK name still asserted); the
own-human approval insert (now also asserts a `distinct_*` CHECK name); the chain-fork insert (now
supplies a valid `previous_stream_seq`). The old "append-only is NOT database-enforced"
characterization test was replaced by a trigger inventory test, as its own docstring required.

## 3. Migration strategy and status

`c99a03e55ff3` is an **untracked, never committed** file and says it was applied to no database, but
nothing proves no developer database ran it. So the hardening is a **new additive revision**; the
published one is not edited. Head is now `d0b14a77c8e2`.

- Upgrade order: add column → backfill (`stream_seq - 1`, before any trigger exists) → CHECK/UNIQUE/FK
  (these validate existing rows and fail closed if history is inconsistent) → lifecycle triggers →
  append-only triggers last.
- Tested on a schema that already held a proposal, an approval and a revocation: the hardening was
  downgraded and re-upgraded, backfill gave `[(1, None), (2, 1), (3, 2)]`, and the guards were active
  again afterwards.
- Downgrade removes the hardening (privileged, structural) and keeps all history; c99a03e55ff3's own
  downgrade still refuses to drop recorded history.
- **Not applied** to any application, demo or production database.

## 4. PostgreSQL tests executed

Target: the disposable cluster (own data directory, loopback port 54329, database
`scopus_ictu_test_pytest_e3p3b2e`); the service on 5432 was never used. The guard ran unmodified.

| Run | Result |
|---|---|
| Offline: hybrid, persistence, schema, decision-boundary, candidate-persistence unit files | 246 passed |
| Offline: `test_source_staging_schema.py` | 23 passed |
| PG, targeted new tests first | 20 passed |
| PG, whole B2-E file, once | **52 passed, 0 failed, 0 skipped** (36.7 s; was 26) |
| Mutation probes, 6 mutants of the migration | all 6 caught (below) |
| `ruff check` on the changed Python files | all checks passed |

Mutants caught: F8 check removed, F3 check removed, F7 target-kind rule removed, F1 `ENABLE ALWAYS`
dropped, F4 chain-link FK dropped, F6 context FK dropped. The migration was restored afterwards.
Not run: whole unit suite, `test_db_safety_guard.py` (its 3 `psycopg` failures are the known
environment mismatch from the previous report, unrelated), the staging/G04 PG tests.

## 5. Direct SQL tampering results (PostgreSQL)

| Attempt | Result |
|---|---|
| `UPDATE` / `DELETE` / `TRUNCATE ... CASCADE` on each of the 7 relations as the owning superuser | all refused: `sc_hybrid history is append-only` |
| same with `session_replication_role = replica` (superuser) | still refused (`ENABLE ALWAYS`) |
| same as a **non-superuser, non-owner role holding every table privilege** (`SET ROLE`) | all refused; the role could not `ALTER TABLE ... DISABLE TRIGGER` (`must be owner`) nor set `session_replication_role` (`permission denied`); history unchanged |
| owner/superuser `ALTER TABLE ... DISABLE TRIGGER` then `DELETE` | **succeeds** — documented residual bypass (§7) |
| predecessor with wrong hash / unknown id / skipped position / lied position | refused (`fk_sc_hybrid_events_chain_link`, `ck_..._previous_stream_seq`) |
| graft onto another candidate's stream, both directions | refused (`fk_sc_hybrid_events_chain_link`) |
| honest seq-2 link (positive control) | accepted |
| event for another candidate than its context, event with another policy than its context | refused (`fk_sc_hybrid_events_context_candidate_policy`) |
| approval row for a revoked proposal | refused by trigger |
| revoke a REVOKE; superseding with a REVOKE / revoked event as replacement; kind mismatch | refused by trigger |
| second proposal row while one is effective | refused by trigger |

## 6. Transaction and concurrency evidence

- **One lock, two writers.** The service now takes `pg_advisory_xact_lock(1835032549, hashtext(<uuid text>))`;
  the triggers take the same lock through `sc_hybrid_lock_stream`. A test pins the two constants,
  shows `pg_try_advisory_xact_lock` with that key returns false while the service holds it, and that a
  trigger-side lock request is observably blocked (`pg_locks`, one ungranted) until the service commits.
- **F2 strict races** (two threads, barrier): identical proposals 4 runs, identical approvals 2 runs,
  identical revocations 2 runs — each time exactly one `APPENDED` and one `ALREADY_RECORDED`, one row stored.
- **F8 race**: two distinct proposals for one candidate, 3 runs — exactly one `APPENDED`, the other
  `HYBRID_ACTIVE_PROPOSAL_EXISTS`, one proposal stored.
- The triggers refuse to run outside READ COMMITTED (tested with REPEATABLE READ), because the checks rely
  on a fresh snapshot per statement after the lock is granted.
- SAVEPOINT ownership and the caller's transaction are unchanged; the earlier test still passes.
- Append-only is preserved: nothing in the service updates or deletes.

## 7. Remaining blockers and limits

1. **No immutability claim against privileged roles.** A table owner or superuser can disable the triggers.
   Deployment must run the application as a role that is neither owner nor superuser; this repository does
   not provision roles and I did not inspect any real one.
2. ~~PostgreSQL 17.10 only~~ Superseded by §10: also run on PostgreSQL 16.11 (the `compose.yaml` major version).
3. The lifecycle rules need READ COMMITTED (enforced by refusal, not adaptation).
4. Trigger functions reference the `sc_hybrid_*` tables unqualified, so they depend on the session `search_path`.
5. `hashtext` can collide across candidates; that only serializes two unrelated streams, never lets one through.
6. The SQLite mirror tests cover the service rules only; DB rules are proven solely by the PG tests.
7. Chain-hash content (that `previous_event_hash` is what the service computed) is still service-computed;
   the database now guarantees the hash, id, stream and position name one real event.
8. Not production-ready; SOURCE_CLAIM stays inactive and there is no finalization relation.

## 8. Temporary guard entry cleanup

Both entries added for this cluster (database-name allowlist line + comment, and the
`system_identifier` mapping) are **removed**; `git diff` of `db_safety_guard.py` against HEAD is empty and
no `e3p3b2e` string remains. The server is stopped (`pg_isready`: no response). The data directory stays in
the session scratchpad and was not deleted; to rerun these tests it needs a new owner-approved guard entry.
No shared cluster was touched.

## 9. SOURCE_CLAIM activation guard

`HybridDecisionJournal.submit()` still raises `SOURCE_CLAIM_WORKFLOW_INACTIVE`; the offline and PG
tests for it pass, and the PG test confirms no identity, no IdentityEvidence and no event is written. The
migration adds no finalization relation and no code path accepts a candidate.

## 10. Addendum — PostgreSQL 16 and least-privilege role (2026-11-01)

| Item | Result |
|---|---|
| Runtime | PostgreSQL **16.11** (EnterpriseDB portable zip, 324,093,756 bytes, SHA-256 `3761aee1252a2083679020b5dc79c75df2d567eea708a2cbb9f6ff5402e27101` computed locally; no vendor checksum was available to compare). Only `bin`, `lib`, `share` extracted into the session scratchpad; nothing installed. |
| Target | New throwaway cluster, loopback port 54316, database `scopus_ictu_test_pytest_pg16verify`. The PG 17 service and port 5432 were not used. |
| Result | B2-E PG file: **53 passed, 0 failed, 0 skipped** (57 s). The 52 tests above plus one new test. |
| New test | `test_pg_service_runs_as_a_non_owner_role_that_cannot_rewrite_history`: a non-superuser, non-owner role holding only SELECT/INSERT/UPDATE/DELETE runs proposal, approval and revocation through the service (seq 1–3); its UPDATE and DELETE on history are refused by the triggers; no role left behind. Run on PG 16 only. |
| Guard | Two temporary allowlist lines added for this database and removed afterwards; `db_safety_guard.py` matches HEAD. Cluster stopped; data directory left in the scratchpad. |

Still **NOT_VERIFIED**: the real production application DB role. The test uses a representative role
only; real roles are provisioned outside this repository. Production-readiness is not claimed and
SOURCE_CLAIM stays INACTIVE.
