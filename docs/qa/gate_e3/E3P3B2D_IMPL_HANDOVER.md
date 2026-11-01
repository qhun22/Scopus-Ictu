# E3-P3-B2-D — Authority & persistence implementation handover

Date: 2026-11-01 (Asia/Bangkok). **Status: PARTIAL_OFFLINE.**

No commit, no push, no migration applied to any database, no HTTP/E2E run.
SOURCE_CLAIM production workflow remains **INACTIVE**. This is not a production-readiness
claim.

This handover accompanies the earlier design-only `E3P3B2D_*` artifacts, which are
unchanged. Where the implementation deviates from the design, §7 says so.

---

## 1. What was actually implemented

### 1.1 Deterministic hybrid branch precedence

`app/services/source_claim_hybrid.py` — policy revision **1 → 2**.

`evaluate_hybrid_policy` now resolves one branch instead of reporting two independently
eligible ones:

| Situation | STANDARD_INDEPENDENT | INSTITUTIONAL_EXCEPTION |
|---|---|---|
| Qualifying independent assessment | eligible | denied `STANDARD_INDEPENDENT_REVIEW_REQUIRED` |
| Independent evidence insufficient, provenance verified | denied `INDEPENDENT_EVIDENCE_INSUFFICIENT` | eligible |
| Independent evidence insufficient, provenance unverified | denied | denied `INSTITUTIONAL_PROVENANCE_UNVERIFIED` |
| Invalid / withdrawn / contradictory assessment | denied | denied (same reason) |
| Hard conflict | denied | denied |

Consequences:

- **No downgrade route.** Choosing the exception branch while qualifying independent
  evidence exists is refused, so the stricter review cannot be bypassed.
- `HybridEligibility.required_branch` names the single open branch (or `None`), and
  `_prepare` additionally requires `required_branch == command.branch`
  (`HYBRID_BRANCH_PRECEDENCE`). A reviewer may only agree with the policy, not pick.
- Denials are reported by a declared severity order (`_DENIAL_PRECEDENCE`), so a
  blocking conflict is never masked by an incidental alphabetically-earlier reason.
- **Policy version and replay.** The semantics changed, so the revision was bumped and
  `policy_document()` / `POLICY_DIGEST` now pin the exact parameters (precedence order,
  qualifying types, grants, denial order, dual-control count, `final_acceptance: False`).
  The digest is in every snapshot and every persisted row, so a v1 receipt does not
  replay against v2 and stored history cannot be reinterpreted under newer rules.

### 1.2 Authority integration foundations

`app/services/source_claim_authority.py` (new) — four typed contracts, fail-closed:

| Authority | Adapter | Wired to | Missing before production |
|---|---|---|---|
| ICTU institutional source | `StagingSourceLineageAuthority` | **real** `source_artifacts` / `source_captures` | Formally verified, revocable ICTU issuance of the staged declaration |
| " (strict default) | `UnavailableInstitutionalSourceAuthority` | — | Authenticated issuance channel, issuer delegation, revocation feed |
| Independent identity evidence | `UnavailableIndependentEvidenceAuthority` | — | Governed verifier, qualification rules, conflict resolution |
| Human principal registry | `UnavailableHumanPrincipalRegistry` | — | ICTU person registry proving account ↔ human equivalence |
| Reviewer/exception authorization | `UnavailableExceptionAuthorizationAuthority` | — | Dual-control capability grants with revocation |

- `StagingSourceLineageAuthority` is the only adapter reading a genuinely authoritative
  existing source. Staging is authoritative for *what bytes ICTU published and when*, and
  is **not** an issuance authority — so it returns an **empty** attestation set rather
  than a verification it cannot make. The effect is that `provenance_verified` stays
  false and the exception branch is blocked by `INSTITUTIONAL_PROVENANCE_UNVERIFIED`.
  It fails closed if an artifact named by the trusted context is absent from staging.
- The independent authority **raises** instead of returning an empty set: with no
  verifier, insufficiency is *unknown*, and unknown must not become an exception grant.
- `HybridAuthorityGateway` composes the four into the existing `AuthorityFacts`. It binds
  a grant only when the authorization authority and the registry agree on the *same*
  human for that account, so a transplanted or stale grant cannot carry someone else's
  capability. Revoked grants are dropped; a non-current account is refused.
- `assert_production_safe` refuses any non-authoritative adapter under
  `ENVIRONMENT=prod` (`SOURCE_CLAIM_AUTHORITY_NOT_PRODUCTION_READY`), re-checked on every
  load. Synthetic authority cannot be substituted in production.
- New port in the policy module: `AuthorityRequest` (scope derived only from the trusted
  server snapshot — pair, version, claimed IDs, artifacts, accounts) and
  `ScopedHybridAuthority`. Digest-only authorities still work unchanged.
- `integration_report()` returns the machine-readable gap list above.

### 1.3 Persistence foundation

`app/models/source_claim_hybrid.py` (new, 7 append-only relations) and
`app/services/source_claim_hybrid_persistence.py` (new, `HybridDecisionJournal`).

| Relation | Carries |
|---|---|
| `sc_hybrid_policies` | Immutable policy revision; `policy_digest` = SHA-256 of its exact bytes |
| `sc_hybrid_contexts` | Revalidated pair/observation/run/reviewer/policy context, context + source + evidence + authority digests |
| `sc_hybrid_provenance` | Institutional lineage per context, with issuance attestation or none |
| `sc_hybrid_events` | Hash-chained append-only decision log, one stream per candidate |
| `sc_hybrid_proposals` | Reviewer proposal, branch, assurance basis, reason, risk acknowledgment |
| `sc_hybrid_approvals` | Second-human exception approval |
| `sc_hybrid_revocations` | REVOKE / SUPERSEDE compensation under dual control |

Public API: `record_proposal`, `record_exception_approval`, `record_revocation`,
`submit` (always refuses). Each returns `AppendResult(outcome=APPENDED|ALREADY_RECORDED,
…, final_acceptance=False, workflow_active=False)`.

**There is deliberately no finalization relation and no identity/review column.** Grep-
guarded by a test: no `identity_id`, `finalization_id`, `candidate_review_id`,
`mapping_review_id`, `resulting_identity_id` anywhere in the new schema. Recording
history therefore cannot become an acceptance, and `submit` still raises
`SOURCE_CLAIM_WORKFLOW_INACTIVE`.

---

## 2. Files added / modified

**Added (9)**

```
backend/app/models/source_claim_hybrid.py
backend/app/services/source_claim_authority.py
backend/app/services/source_claim_hybrid_persistence.py
backend/alembic/versions/c99a03e55ff3_e3_p3b2d_source_claim_hybrid_history.py
backend/tests/unit/test_source_claim_hybrid_persistence.py
backend/tests/unit/test_source_claim_authority.py
backend/tests/unit/test_source_claim_hybrid_schema.py
backend/tests/integration/test_source_claim_hybrid_persistence_pg.py
docs/qa/gate_e3/E3P3B2D_IMPL_HANDOVER.md   (this file)
```

**Modified (4)**

| File | Change |
|---|---|
| `backend/app/services/source_claim_hybrid.py` | Policy revision 2, branch precedence, denial order, `policy_document`/`POLICY_DIGEST`, `AuthorityRequest`/`ScopedHybridAuthority` port, `authorize_principals`, `verify_receipt`, scoped load |
| `backend/app/models/__init__.py` | One registration import for the new model module |
| `backend/tests/unit/test_source_claim_hybrid.py` | 3 assertions updated for policy v2 (see §7) |
| `backend/tests/unit/test_source_staging_schema.py` | Expected single Alembic head moved to `c99a03e55ff3` |

Unrelated dirty-worktree changes were left untouched. No endpoint, router, `main.py`,
frontend file or unrelated service was modified — verified by grep: nothing under
`app/api/`, `app/main.py` or `frontend/src/` references the new modules.

---

## 3. Test results

Run offline on Windows with `python -m pytest --noconftest` (see §4 for why).

**New B2-D tests — 74 passed, 0 failed**

| File | Result |
|---|---|
| `tests/unit/test_source_claim_hybrid_persistence.py` | 30 passed |
| `tests/unit/test_source_claim_hybrid_schema.py` | 25 passed |
| `tests/unit/test_source_claim_authority.py` | 19 passed |

**B2-C / B2-B / B2-A / E3 regression — 575 passed, 0 failed, 1 error**

| File | Result |
|---|---|
| `test_source_claim_hybrid.py` | 93 passed |
| `test_source_claim_decision_boundary.py` | 52 passed |
| `test_source_claim_candidate_persistence.py` | 39 passed |
| `test_source_claim_reviewer_read.py` | 65 passed |
| `test_source_claim_matching_bridge.py` | 43 passed |
| `test_source_claims.py` | 118 passed |
| `test_source_claims_adapters.py` | 74 passed |
| `test_source_claims_provenance.py` | 32 passed |
| `test_source_staging_schema.py` | 23 passed |
| `test_source_staging_service.py` | 36 passed, 1 error (`isolated_db_engine` fixture, `--noconftest`) |

**Whole backend unit suite (one run): 1121 passed, 4 failed, 6 skipped, 34 errors.**

Every failure and error is environmental and pre-existing, none in B2-D code:

| Count | Cause |
|---|---|
| 26 errors | `PermissionError: [WinError 5]` on a Windows temp path (launcher/file tests) |
| 8 errors | `fixture 'isolated_db_engine' not found` — a direct consequence of `--noconftest` |
| 3 failed | `ModuleNotFoundError: No module named 'psycopg'` (`test_db_safety_guard.py`) |
| 1 failed | `test_demo_launcher.py::test_the_bat_is_one_entry_point…` — pre-existing, from the restored portable launcher config already in the dirty worktree |

Lint: `python -m ruff check` clean on all 12 added/modified Python files. (The repo-wide
`ruff check app/` is **not** clean today — pre-existing E501/B008/E741 in
`api/v1/endpoints/affiliations.py`, `lecturers.py` and others, untouched here.)

### Explicitly NOT_EXECUTED

| Area | Status | Why |
|---|---|---|
| PostgreSQL integration | **NOT_EXECUTED** | No reachable allowlisted test cluster. Only port 5432 is listening, which `tests/db_safety_guard.py` forbids by design, and `psycopg` is not installed. 14 PG tests are written and *import-verified* (`--collect-only`) in `tests/integration/test_source_claim_hybrid_persistence_pg.py`, never run. |
| PostgreSQL concurrency | **NOT_EXECUTED** | Same. The per-stream advisory lock and the concurrent-append test exist but are unrun. |
| DB-level CHECK / FK enforcement | **NOT_EXECUTED** | The SQLite mirror carries no CHECKs, no non-staging FKs and no composite FKs. Offline tests prove the *declared* constraints and the *service-level* enforcement; they do not prove the database rejects a direct tampering UPDATE. |
| Migration execution | **NOT_EXECUTED** | Rendered `as_sql` and compared item-by-item against the models; never applied to any database. |
| HTTP / JWT | **NOT_EXECUTED** | No endpoint was registered; there is nothing to call. |
| Web E2E | **NOT_EXECUTED** | No frontend action was activated. |

---

## 4. Note on how the tests were run

`tests/conftest.py` calls `pytest.exit()` at import when `TEST_DATABASE_URL` does not
resolve to an allowlisted, reachable PostgreSQL database — which it cannot here. That
blocks collection of *every* test, including the SQLite-only unit tests. The safety guard
was **not** modified or bypassed; `--noconftest` was used so the offline unit tests could
run at all. Its only side effect is the 8 missing-fixture errors listed above. All B2-D
unit tests build their own isolated in-memory SQLite engine and touch no server.

---

## 5. Security guarantees

Enforced and covered by an offline test unless noted.

| Invariant | How | Where enforced |
|---|---|---|
| Two distinct human principals for an institutional exception | Distinct account **and** distinct `human_principal_id` required | Service (`authorize_principals`, `prepare_exception_approval`) + CHECK `ck_sc_hybrid_approvals_distinct_human_principals` |
| No self-approval | Same checks; approver must differ from reviewer | Service + CHECK `…_distinct_accounts` |
| No same-human multi-account bypass | Distinctness is on the *principal*, not the account | Service + CHECK (covered: `test_one_human_with_two_accounts_cannot_satisfy_dual_control`) |
| Fresh authorization at decision boundaries | Stored account state (`_authorize`) and authority facts re-read inside the write transaction, for every human, on every action — including revocation | Service |
| No hard-conflict bypass | Conflict denies both branches; command must equal `required_branch` | Policy |
| Institutional claim never treated as independent evidence | `independently_verified` is CHECK-pinned to `FALSE`; `source_tier`/`evidence_kind` pinned; a `SOURCE_CLAIM` assessment type never qualifies | Schema + policy |
| No replay / snapshot tampering | Only the server-re-prepared snapshot is stored; a supplied receipt is byte-and-hash compared; `snapshot_hash`/`envelope_hash` CHECK-matched against their JSON; hash-chained predecessor | Service + schema |
| Idempotency | `operation_key` derived server-side from the trusted snapshot; `UNIQUE(operation_key)`; a retry resolves to the recorded event, a different snapshot under a recorded key is refused | Service + schema |
| No cross-candidate approval reuse | Approval carries a composite FK to the proposal's exact id/context/branch/reviewer/principal | Schema + service recheck |
| No duplicate final decisions | `UNIQUE(sc_hybrid_proposals.context_id)`, `UNIQUE(sc_hybrid_approvals.proposal_id)`, `UNIQUE(target_event_id)` for compensation, `UNIQUE(previous_event_id)` so the chain is a line not a tree | Schema |
| No hidden commit/rollback of the caller's transaction | Every write in `begin_nested()`; the only `commit`/`rollback` calls are on the SAVEPOINT object; a test asserts no `UPDATE`/`DELETE`/`COMMIT` is emitted and the caller still owns its transaction | Service |
| No automatic ACCEPT | No finalization relation, no identity/review column, no endpoint; `submit` raises `SOURCE_CLAIM_WORKFLOW_INACTIVE` on both the hybrid and the persistence boundary | Architecture |
| Append-only | Insert-only writers; revocation and supersession append; `downgrade()` refuses to drop a non-empty table | Service + migration |
| No synthetic authority in production | `assert_production_safe` refuses non-authoritative adapters under `ENVIRONMENT=prod` | Gateway |

---

## 6. Remaining authority & persistence blockers

**Authority (owner decisions, unchanged from the design gate).** All four integrations are
still missing; the code is fail-closed, so the hybrid path cannot be used in production at
all. Needed before any activation:

1. **ICTU institutional source** — nominate the source custodian, an authenticated
   issuance channel, signing keys and a revocation feed. Until then
   `StagingSourceLineageAuthority` attests nothing and the exception branch is closed.
2. **Independent identity evidence** — nominate the verifier operator, source tiers,
   qualification procedure and conflict governance. Until then the standard branch is
   closed too, because the adapter refuses rather than reporting "insufficient".
3. **Human principal registry** — select the actual ICTU system/export proving
   account ↔ person equivalence. Without it no human can be authorized at all, so no row
   can be written.
4. **Exception authorization** — nominate grant custodians and dual-control
   enrollment/revocation.

**Persistence.**

- **PostgreSQL validation is the open item**, not the schema: CHECK/FK behaviour,
  concurrency and the migration run are all NOT_EXECUTED (§3).
- **No DB-level FK from `sc_hybrid_provenance` into the staging tables.** This is the one
  design element deliberately not implemented: the accepted E3-P2-B1 contract is that
  staging is pre-identity and nothing downstream points into it, and a unit test enforces
  it. Adding those FKs would have required reopening that frozen contract, so per the
  gate's own rule that portion was stopped. Lineage is instead fully revalidated by the
  append boundary against the live staging rows and pinned by the stored artifact/record
  digests. **If the owner wants referential enforcement here, the E3-P2-B1 staging
  contract must be reopened first — that decision is not taken in this gate.**
- Not implemented from the design (intentionally out of "minimum compatible" scope):
  event signatures and signing keys, issuer/key registries, authority-event streams,
  checkpoints and checkpoint outbox, principal/binding/grant tables, assurance-state
  events, and restricted append-only database roles. These are only meaningful once a real
  authority and a signer exist; nothing implemented here conflicts with adding them.
- `recorded_at` is the database clock; `action_at` comes from the trusted boundary. There
  is no authenticated external timestamp.

---

## 7. Deliberate changes to previously accepted artifacts

Reported explicitly because these are edits to accepted tests, not new ones.

1. **Policy revision 1 → 2** is a semantic change, required by the branch-precedence
   objective. Three assertions in `tests/unit/test_source_claim_hybrid.py` were updated:
   - the expected `policy_version` is now `POLICY_VERSION`, plus new assertions on
     `policy_digest` and `required_branch`;
   - the version-mismatch parametrization moved from `[0, 2, True, "1"]` to
     `[0, 1, 3, True, "2"]` (2 is now the valid revision);
   - `test_newer_independent_facts_do_not_replace_an_old_proposal` now asserts the
     precedence denial for the branch-flipping case **and** keeps the original
     replay-invalid assertion for a fact change that leaves the branch open.
   No test was weakened or deleted. Nothing was ever persisted under v1, so there is no
   stored history to migrate.
2. **Alembic head** moved to `c99a03e55ff3`; the single-head assertion in
   `tests/unit/test_source_staging_schema.py` was updated accordingly. This is the normal
   append-only consequence of adding a revision; no published revision was rewritten.
3. **Doc drift (not fixed here, out of scope):** `CLAUDE.md` still says the head is
   `c7f2a9b1d3e5` and `AGENTS.md` says `a77e01c33ee1`. Both were already stale before this
   gate; the real head is now `c99a03e55ff3`. Worth a separate doc-sync commit.

---

## 8. Migration status

| Item | Value |
|---|---|
| Revision | `c99a03e55ff3` (`e3_p3b2d_source_claim_hybrid_history`) |
| Parent | `b88f02d44ff2` (accepted B1 revision, not rewritten) |
| Head | Single head, verified by test |
| Applied | **No.** Not applied to any database — app, demo, teacher or test |
| Verified | Rendered with `as_sql` and compared **item by item** against the models (every column, CHECK, UNIQUE, FK and index), plus name-length limits |
| Alters existing tables | **No.** `ALTER TABLE` and `DROP` are absent from the rendered upgrade; no frozen table is redefined |
| Downgrade | Structural only — raises and refuses if any of the seven tables holds a row |

---

## 9. Next actionable gate

**B2-E — PostgreSQL validation of the B2-D foundation.** Nothing more should be built on
this schema until it has been exercised on a real database.

1. Provision a disposable PostgreSQL test database, add its exact name to
   `ALLOWED_TEST_DATABASE_NAMES`, install `psycopg`, and run
   `tests/integration/test_source_claim_hybrid_persistence_pg.py` (14 tests). Expect to
   fix test-side issues on first run: the file has never executed.
2. Apply `c99a03e55ff3` in a scratch schema only, and confirm every CHECK in §5 actually
   rejects a direct tampering `UPDATE`.
3. Confirm the per-stream advisory lock serializes concurrent appends and that an
   identical concurrent proposal yields exactly one event.
4. Then, and only then, take the authority decisions in §6 to the owner. Until at least
   the human principal registry and one of the two evidence authorities exist, no further
   workflow gate is reachable: the code is fail-closed by construction.

Re-confirming the standing restrictions: SOURCE_CLAIM submit stays
`SOURCE_CLAIM_WORKFLOW_INACTIVE`, no acceptance endpoint is registered, no frontend
approval action is activated, and no migration has been applied.
