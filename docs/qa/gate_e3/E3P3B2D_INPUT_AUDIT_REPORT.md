# E3-P3-B2-C ? Independent offline acceptance audit

Date: 2026-10-30 (Asia/Bangkok). Final decision: **PARTIAL_OFFLINE**.

**SOURCE_CLAIM production workflow remains INACTIVE in the audited repository.** No activation, source modification, commit, push, application/PostgreSQL DB connection, real reviewer decision, or migration execution occurred. No B2-D work was started. Existing dirty worktree preserved byte for byte.

The implementation is suitable for retaining as an inactive offline compatibility prototype. It is not accepted as an operational independent-verification or institutional-exception approval workflow. The main production blockers are correctly disclosed by its own handover. No critical/high exploitable production bypass was established in the inactive code paths inspected.

## Baseline, method and preservation

Repository: `D:/DataFolder/ProjectIctu/DoAn/Scopus-Ictu`. Branch `main`, HEAD `4bb69f6efaac945399b1c191fc12879ad1c62885`.

Independent baseline: **20 modified tracked files, 730 untracked file entries**, 750 status entries using `git status --porcelain=v1 --untracked-files=all`; **1,678 existing tracked/nonignored-untracked files** hashed. The complete baseline is `baseline-status.txt`, with per-file hashes in `baseline-inventory.json` beside this report. Do not confuse this audit baseline with the implementer's earlier 20/721 baseline: the nine B2-C additions account exactly for the difference.

All seven `docs/qa/gate_e3/E3P3B2C*` artifacts were read, including the JSON validation and two-file implementation patch. Both requested Python files were inspected in full. B2-B decision code/contract, B2-A reviewer contract, source fixtures, identity/governance models, live review selection/serialization/promotion, D-2 reason policy, M1.0/M2.7/M2.8 freeze records and ADR-003/004 were inspected for the applicable boundaries. This was a local code/evidence audit; no internet or connected-service data was needed.

Testing used a new temporary workspace outside the repository. Copied app/test/Alembic files and the public schema were byte-compared with the baseline: **268 inventoried copied files, zero mismatches**. `.env`, private data, credentials and Git metadata were not copied. SQLite engines only; network connection calls, application DB initialization and PostgreSQL drivers were blocked. Settings used synthetic process-only values. No application configuration file was changed.

The selected offline tests run with `--noconftest`, following their standalone SQLite contract. The repository-wide conftest initializes application/DB fixtures and requires a verified PostgreSQL target; it was not imported. No destructive/integration test was run, no guard code or allowlist was changed, no test-DB bypass flag was used, and these runs provide no PostgreSQL evidence. This distinction is essential to the PASS claims below.

Final worktree comparison: **PASS ? all 1,678 baseline hashes and the complete Git status identical; zero changed/added/removed repository files**. Ignored/private/runtime files are outside the inventory; the audit neither ran the application nor intentionally accessed or wrote them. `worktree-preservation.json` records the comparison.

## Artifact integrity and permitted scope

Manifest verification: **6/6 PASS**. Actual SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| `E3P3B2C_HANDOVER.md` | `afed49d92409f433e1c9aa84e92d26f62e368716f6777d66eb5f95cd40f0ec3e` |
| `E3P3B2C_HYBRID_CONTRACT.md` | `b86bc5be9d73e9df08bddd89412eee743ea8bd47e3f854e661262c44201c3cf0` |
| `E3P3B2C_PERSISTENCE_PROPOSAL.md` | `c722d2bd7ce99eed2fff06295f385a75db10ede0dda5860a128ec01aa72abecc` |
| `E3P3B2C_IMPLEMENTATION.diff` | `f1d24eeaec0e80d7ab53416634b0700f4a15c25078dd99261ff16cdcf90f3a70` |
| `E3P3B2C_TEST_RESULTS.txt` | `fc61084b7135dda172447abc2b79a8ea95802f0cf2a03fb6d3030eaa58a7f222` |
| `E3P3B2C_VALIDATION.json` | `a3388b941b31972a04cc929a292d19acb4cf5a01e24d85968130f1623f9efd3f` |

The manifest itself is not self-hashed. Its independent hash is recorded in `audit-evidence.json`. Matching an unsigned manifest proves consistency with that manifest, not independent authenticity of its author or institutional issuance.

The manifest-covered VALIDATION binds the actual code/test hashes, both independently matched:

- `backend/app/services/source_claim_hybrid.py`: `88f282b81fa6347dbf4c8872e1562e0b7d8c0996849cc99a011afb017590f57d`.
- `backend/tests/unit/test_source_claim_hybrid.py`: `3e336d04a4b3b03fcb978894ccee519c8798e5e5598fab13660bf779b28621e4`.

B2-B preservation: **7/7 recorded hashes matched**: two Python files and five QA artifacts. Its validation independently supplies four nonself QA hashes; these match too. B2-B and B2-C reverse-application checks both exited 0; no patch was applied. B2-C patch contains exactly the two new Python paths and no existing-file edit.

Recomputed protected-set digests match all seven declared subsets: all preexisting **1,669**, backend app **154**, backend tests **94**, frontend **103**, whole Alembic directory **18**, Gate D/research **634**, accepted E3 QA **62**. The Alembic subset includes the whole directory, not only its 16 revision files. Complete digest values are in `audit-evidence.json`; the all-preexisting digest is `c5e36a4539bda3a4ac5d4455b6358b5b2e3f51894ece23eb95152f4a7fb3eb4c`.

Consequently, the current tree is consistent with exactly nine B2-C additions and no other B2-C edits. The earlier historical baseline is implementer-supplied evidence, not an independently witnessed prior checkout; this audit independently verified its reproducibility against the present tree and independently preserved its own baseline.

## Actual tests executed

Interpreter: Python **3.12.10**, pytest **9.2.0**, SQLAlchemy **2.1.6**, SQLite **3.49.1**.

Commands executed from the repository root, with the runner selecting the isolated backend as its working directory:

```powershell
python -B C:\Users\QuangHuy\AppData\Local\Temp\E3P3B2C-independent-audit-20261030-xb2ck63r\audit_runner.py focused
python -B C:\Users\QuangHuy\AppData\Local\Temp\E3P3B2C-independent-audit-20261030-xb2ck63r\audit_runner.py combined
python -B C:\Users\QuangHuy\AppData\Local\Temp\E3P3B2C-independent-audit-20261030-xb2ck63r\audit_runner.py independent
```

Each `*-output.txt` records the exact `pytest.main` arguments, temp paths and selected node IDs. JUnit XML and per-phase/node results JSON are retained. Plugin autoload, bytecode and pytest caching were disabled. All successful runs ended with forbidden modules loaded `[]` and SQLite as the only engine backend.

| Run | Passed | Failed | Skipped | Exit | Pytest time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Focused existing hybrid tests | 92 | 0 | 0 | 0 | 20.06s |
| Combined existing relevant regressions, including focused tests | 597 | 0 | 0 | 0 | 36.50s |
| Independent adversarial probes outside repository | 14 | 0 | 0 | 0 | 1.84s |

**611 distinct final passing cases**; 703 successful test executions because the 92 focused cases were run again in the combined suite. The combined run is 92 hybrid + 505 existing regressions, including all 52 B2-B cases. Do not add 92 to 597 as distinct coverage.

Combined selection and actual per-file counts:

| Selection under `backend/tests/unit/` | Passed |
| --- | ---: |
| `test_source_claims.py` | 118 |
| `test_source_claims_adapters.py` | 74 |
| `test_source_staging_schema.py` | 23 |
| `test_source_claims_provenance.py` | 32 |
| `test_source_staging_service.py` | 37 |
| `test_source_claim_matching_bridge.py` | 43 |
| `test_source_claim_candidate_persistence.py` | 39 |
| `test_source_claim_reviewer_read.py` | 65 |
| `test_source_claim_decision_boundary.py` | 52 |
| `test_source_claim_hybrid.py` | 92 |
| `test_candidate_generator.py` | 20 |
| `test_candidate_persistence.py (only test_canonical_json_and_hash_ignore_mapping_order; test_source_state_has_compact_rule_and_input_contract)` | 2 |

The 14 additional probes cover four qualified strong types, mixed valid/invalid receipts on both branches, both authority auth-version mismatches, standard with explicitly unverified source context, authority revision replay, stored-record tampering before authority loading, a real SQLite SQL failure during approval with prior/pending caller work and retry, rebased timestamp limitations, and overlapping branch eligibility. Their exact source is `test_independent_audit.py` outside the repository.

Two nonpassing preliminary executions are retained, not silently counted as PASS:

1. Initial focused collection: **1 collection error, 0 test bodies** because Settings requires DB/CORS/secret/environment values when imported through `app.core`. Fixed in the audit harness using fake process-only values, with no source/config edit.
2. Initial independent probes: **13 passed / 1 failed** due to the auditor comparing a noncanonical JSON string to the canonical return. The verification itself succeeded. Corrected the audit-only assertion to compare digest and decoded JSON; final 14/14 passed. This was not an implementation fix. Original output/JUnit/results retained under `initial-probe-*`.

The initial sandbox could create a temporary directory but denied writing inside it. Temporary-copy creation/testing/report writes subsequently ran with approved execution outside that sandbox, retaining all network/database guards. The denied attempt changed no repository file.

Static checks independently executed: `git apply --check --reverse` for B2-B/B2-C, both exit 0; `python -B -m ruff check --no-cache app/services/source_claim_hybrid.py tests/unit/test_source_claim_hybrid.py --output-format json` on the copy, exit 0, output `[]`. No broad integration/full-repository test success is claimed.

## What these tests establish

These are real executions of the actual Python validators, source projection/staging code, SQLAlchemy queries and SQLite transactions. They are **not real authority integrations**. `test_source_claim_hybrid.py:54-97` invents all verifier receipts, formal ICTU issuance receipts, human principal linkage and exception grants. Typed DTOs plus known strings/digests do not establish those facts in the real world.

The combined suite also executes the unchanged NAME/PUBLICATION ACCEPT and REJECT service methods in four parametrized synthetic SQLite cases (`test_source_claim_decision_boundary.py:439-469`). This performs real writes/commits against disposable SQLite fixtures only. It does not exercise SOURCE_CLAIM final acceptance, a real lecturer decision, PostgreSQL, JWT middleware or web E2E.

The reviewer-read suite extracts and calls a real endpoint function body (`test_source_claim_reviewer_read.py:219-232`), bypassing HTTP dependencies for a unit assertion. That is not authenticated HTTP or browser validation. Migration tests render DDL or record fake Alembic operations; they do not execute migrations on PostgreSQL.

## Findings and production risks

**F1 ? HIGH production blocker; acknowledged capability gap: no authoritative trust integration.** `source_claim_hybrid.py:115-128,189-220,328-330,345-348` defines a trusted port, structurally validates returned metadata, and defaults to HYBRID_AUTHORITY_UNAVAILABLE. `models/governance.py:51-94` has account roles/active/auth_version but no human-principal registry or explicit exception grant model. A separately qualified assessment, verified ICTU issuance and true same-human linkage are not established by this gate. Current inactive/default-deny behavior is safe; successful fixture results must never authorize release. Standard independence, actual issuer authenticity and real separation of duties remain unexecuted integration requirements.

**F2 ? MEDIUM production blocker; reproduced documented limit: original event time and approval history are not authenticated.** `source_claim_hybrid.py:183-186,375,396-397,399-430` takes event times as trusted caller inputs and compares a rederived receipt. `HybridAuthority.load` binds only the B2-B context digest (`:344-345`), not a persisted event. An independent probe changed both proposal/approval timestamps, their digests/proposal reference, and the supplied event-time arguments together: verification returned the corresponding nonfinal receipt. With the original trusted event arguments, timestamp-only substitutions are correctly refused by the existing tests. There is no demonstrated client exploit because no HTTP path exists and caller inputs are expressly server-bound; nevertheless these methods cannot independently prove a prior proposal/approval occurred, or provide durable approval uniqueness. The persistence proposal already identifies this gap (`E3P3B2C_PERSISTENCE_PROPOSAL.md:32-85`). All submit attempts remained INACTIVE.

**F3 ? MEDIUM production blocker: live revocation/ownership atomicity and PostgreSQL transaction semantics unproven.** `source_claim_hybrid.py:389-418` uses a fresh Session and owned SAVEPOINT. Both stored accounts and current authority facts are reread at approval/replay, but multiple reads plus a callback do not ensure a coherent READ COMMITTED snapshot or atomic revocation boundary. No finalization lock, durable event uniqueness or cross-process idempotency exists. SQLite caller-safety tests pass, including the additional actual SQL-error probe; PostgreSQL error-abort/savepoint/locking/concurrency behavior remains NOT_EXECUTED. The authority is trusted code and receives a writable ORM Session (`:115-123,345`); read-only behavior is contractual, not enforced by a read-only DB role/transaction. A future adapter must not write/commit or finalize through that session. No such production adapter or write was found today.

**F4 ? LOW policy ambiguity; independently reproduced: branch eligibility overlaps.** `source_claim_hybrid.py:250-256` does not disqualify an exception when `qualifies=True`; `:359-364` accepts a selected exception branch and keeps INSTITUTIONAL_EXCEPTION assurance. A qualified independent receipt therefore makes both branches eligible, and an explicitly requested exception draft succeeds. The contract says exception is permitted ?when independent evidence is insufficient? (`E3P3B2C_HYBRID_CONTRACT.md:35-36`) but does not explicitly say ?only when.? This is not treated as a proven hard-contract breach or stronger-assurance laundering: the exception still requires grants, verified provenance, risk acknowledgment and distinct humans, and remains an exception. Clarify whether insufficiency is a mandatory prerequisite or merely the motivating case before implementing production routing. No source was changed to decide that policy during this audit.

No new decision DML, activation flag, endpoint, worker registration, canonical evidence promotion or migration was found in the B2-C addition. Searches across app/scripts/frontend found the hybrid module used only by its tests; it is not wired into production routes. B1 STAGED generations are excluded by `candidate_review_queries.py:63,125`; the live serializer refuses SOURCE_CLAIM (`candidate_evidence_read.py:82-86`), and promotion handles only NAME/PUBLICATION (`candidate_review_service.py:220-223,479-493`). These observations concern the audited tree, not a remotely inspected deployment.

## Invariant-by-invariant verdicts

PASS here applies only to the stated offline scope. NOT_EXECUTED is not PASS. FAIL denotes an explicitly named stronger guarantee absent from this prototype, not evidence of a live exploit.

| Invariant | Offline status | File/line evidence and practical limit |
| --- | --- | --- |
| STANDARD_INDEPENDENT requires separately qualifying verified receipt; source/type/name alone cannot qualify | PASS | `source_claim_hybrid.py:223-256,357-369`; missing/invalid/withdrawn/contradictory and false qualification tested. Real verifier: NOT_EXECUTED (F1). |
| INSTITUTIONAL_EXCEPTION enforces current verified selected source provenance, reason, exact risk token and proposal grant | PASS | `:259-306,339-364`; absent/unverified/revoked/substituted receipts denied. Actual institutional issuance: NOT_EXECUTED (F1); overlap ambiguity F4. |
| Reviewer and approver accounts must differ | PASS | `:409-416`; same-account approval denied. |
| Same-human multi-account approval must fail | PASS | `:259-265,414-416`; same synthetic human ID denied. Real account-to-human resolution: NOT_EXECUTED. |
| Both accounts/attestations/grants reauthorized; ADMIN has no grant bypass | PASS | `source_claim_decision_boundary.py:74-86`; hybrid `:259-265,343-348,409-413`; inactive/role/session/grant/service/current and both attestation-version failures tested. Live JWT/grant revocation: NOT_EXECUTED. |
| Institutional provenance binds actual selected rows/digests/pair and stays SOURCE_CLAIM/INSTITUTION_DECLARED | PASS | Hybrid `:269-306`; B2-B `:161-184,206-229`; tampering rejected before authority. Hashes are not issuer authentication. |
| Rehashed snapshot substitutions and stale source/authority rejected with original trusted context | PASS | Hybrid `:313-322,396-430`; current reprepare and full canonical comparison. Not durable historical authenticity. |
| Durable original-event authenticity / approval uniqueness | FAIL | No event store/signature/unique finalization; F2 reproduced. Explicitly deferred and final submit blocked. |
| Cross-candidate/cross-lecturer approval reuse refused | PASS | B2-B `:154-178,218-229`; hybrid `:412,422,425-430`; existing two-case pair test `test_source_claim_hybrid.py:534-569`. |
| Hard conflicts/negative or terminal history cannot be waived | PASS | B2-B `:144-153,185-196`; hybrid `:239-249,350-363`; mixed qualifying+invalid and actual competing source ownership blocked. |
| Exception never classified as INDEPENDENT_VERIFIED or promoted to canonical evidence | PASS | Hybrid `:364-385,419-423`; approval preserves exception assurance; no persistent enum/mapping change. Durable downstream assurance integration: NOT_EXECUTED. |
| Default authority fails closed | PASS | Hybrid `:126-128,328-330`; tested as ADMIN with no fallback. |
| Production submit remains inactive regardless of draft/arguments | PASS | Hybrid `:432-434`; B2-B `:249-252`; both submit guards tested, no activation path added. |
| Caller pending state and earlier writes survive success/denial/error/retry, with no outer transaction ownership transfer | PASS | Hybrid `:389-394,405-423`; focused transaction tests `test_source_claim_hybrid.py:406-465` plus independent actual SQLite SQL-error approval probe. SQLite only. |
| Hybrid operation emits no INSERT/UPDATE/DELETE/COMMIT with supplied read-only authority | PASS | `test_source_claim_hybrid.py:444-465` observes statements during proposal/approval/submit. Callback read-only trust caveat F3. |
| No unauthorized real/application DB writes or reviewer-data changes by audit | PASS | Isolated synthetic fixtures only; application DB/driver/network initialization blocked; no application launch/import/migration. |
| Frozen-contract/B2-B compatibility and permitted addition scope | PASS | Matched protected hashes; unchanged live selection/promotion/evidence vocabulary; patch limited to two additions. |
| Worktree/source/contracts/config/migrations preserved by audit | PASS | All 1,678 baseline hashes and full final status identical. |
| PostgreSQL constraints/JSONB/indexes/isolation/locking/concurrency and live revocation races | NOT_EXECUTED | No PostgreSQL connection; SQLite mirror omits PG CHECKs/partial indexes/external FKs (`tests/source_staging_fixtures.py:59-85`). |
| Authenticated HTTP/JWT/role dependencies, browser E2E, frontend build, deployment | NOT_EXECUTED | Unit endpoint extraction and mocked authority results do not exercise these boundaries. |

## Frozen contracts and final disposition

B2-B compatibility: existing code/tests and QA hashes preserved; exact current generation/version/history/ownership checks and D-2 policy are reused via B2-B `_prepare` (`source_claim_hybrid.py:343-345`). All 52 B2-B tests passed independently, including the four unchanged legacy decision regressions. No source promotion/lifecycle behavior was silently added.

M1.0 freeze ?11-13 (`M1.0-AUTHORITATIVE-FREEZE-PACK-RESOLVED.md:439-538`) retains human-governed identity states, single approved author ownership, seven IdentityEvidence types and immutable review/evidence contracts. ADR-003 requires append-only audit and ADR-004 separates evidence from decisions. M2.7 review and M2.8 approved-identity consumption remain unchanged; transient assurance labels are not persistent identity/evidence status. No exception assurance is sent through existing approved-identity APIs. The existing M2.7 nullable-confidence amendment remains intact. A future operative exception association would require separately approved durable assurance/audit/promotion representation; this gate cannot grant that approval.

**Final decision: PARTIAL_OFFLINE.** Offline policy, provenance binding, replay under trusted server context, synthetic separation/grant checks, inactive guards and SQLite caller safety are independently supported. The successful tests do not close the missing real authorities, historical event authenticity or production transaction/integration gates.

Remaining blockers:

1. Approve and implement governed independent-verification, ICTU issuance/revocation, human-principal linkage and explicit exception-grant authorities; authenticate their context-bound receipts.
2. Define whether a qualified standard assessment excludes exception routing (F4).
3. Approve durable append-only proposal/authorization/finalization/revocation and assurance representation, original trusted timestamps and uniqueness/idempotency. Do not reinterpret institutional declarations as canonical independent evidence.
4. Define and verify a coherent atomic source/ownership/authorization/revocation transaction boundary, including constraints and races on an explicitly authorized disposable PostgreSQL target.
5. Separately validate authenticated HTTP/JWT/grant isolation, safe downstream assurance/UI behavior and actual browser E2E before any activation.

No implementation or activation is authorized by this audit. Stop after audit; **no B2-D**.

Evidence files beside this report: `artifact-integrity.json`, `audit-evidence.json`, `baseline-inventory.json`, `baseline-status.txt`, `final-status.txt`, `worktree-preservation.json`, `audit_runner.py`, `test_independent_audit.py`, successful and preliminary logs/results/JUnit XML, `INDEPENDENT_AUDIT_VALIDATION.json`, `INDEPENDENT_AUDIT_TEST_RESULTS.txt`, and `AUDIT_MANIFEST.sha256`.
