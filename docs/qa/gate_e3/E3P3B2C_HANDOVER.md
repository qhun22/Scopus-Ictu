# E3-P3-B2-C — HYBRID policy and offline compatibility handover

Date: 2026-10-30 (Asia/Bangkok). **DECISION: PARTIAL — OFFLINE.**

The requested HYBRID V1 contracts and read-only validators are implemented and
tested. Existing repository authorities cannot yet establish institutional source
authenticity, independent identity qualification, explicit exception grants or
human/service and same-human account linkage. These are required security
invariants, so the default authority fails closed. Tests exercise synthetic authority
outputs only. This delivery does not claim an operative, fully integrated hybrid
review workflow against the current repository data model.

**SOURCE_CLAIM production workflow remains INACTIVE.**

## Baseline and B2-B compatibility

- Branch main; HEAD `4bb69f6efaac945399b1c191fc12879ad1c62885`. Last commit is the
  prior Gate D.2/matching/affiliation documentation change, not a committed E3 baseline.
- Dirty status captured before edits: 20 modified tracked and 721 untracked entries.
  1,669 existing tracked/nonignored-untracked files hashed. No existing file changed.
- B2-B four nonself artifact hashes plus its two source/test hashes match the
  recorded validation (6/6); reverse patch application check exit 0. Its accepted
  module, tests, five QA artifacts and accepted P1/P2/P3-A/B1/B2-A/R1 remain unchanged.
- Inventory excludes ignored/private datasets, secrets, .git, .venv, node_modules,
  __pycache__, .pytest_cache and .tmp. Equal protected hashes apply only to
  preexisting files; they are not complete before/after hashes including additions.
- No application database connection, migration, real import/reviewer decision,
  commit/push/reset/clean/stash, frontend activation or P4. Tests use synthetic SQLite.

The audit-first impact matrix and exact trust contracts are in
E3P3B2C_HYBRID_CONTRACT.md. The separate persistence proposal is design only.

## Exact implementation scope

Two new files, no modified existing code/tests:

1. `backend/app/services/source_claim_hybrid.py` — transient dataclasses/enums,
   pure evidence-policy evaluator, typed authority port, provenance binding,
   reviewer proposal, distinct-human approval preparation, replay and inactive submit.
2. `backend/tests/unit/test_source_claim_hybrid.py` — synthetic authority fixtures
   and 92 parametrized offline cases. Reuses existing E3 SQLite fixtures/B2-B helpers.

Seven E3P3B2C QA artifacts: this handover, HYBRID_CONTRACT, PERSISTENCE_PROPOSAL,
IMPLEMENTATION.diff, TEST_RESULTS.txt, VALIDATION.json and MANIFEST.sha256.
The patch contains exactly the two new code/test files, relative to the captured
dirty worktree. Prior uncommitted work is not folded into this patch.

## Contract and enforced behavior

Policy SOURCE_CLAIM_HYBRID_V1, version 1. STANDARD_INDEPENDENT is the default.
It needs a current separately qualified independent assessment from the trusted
authority contract. A source claim, type literal, DOI/ORCID string, institution
label, hash or reviewer reason cannot independently qualify. D-2 still sees
SOURCE_CLAIM and retains its reason requirements even when an independent receipt
supports a prospective standard branch.

INSTITUTIONAL_EXCEPTION requires current formal ICTU issuance receipts bound to
every selected active source artifact, human reviewer with explicit proposal grant,
reason and exact risk acknowledgment, then a separate human approver with explicit
approval grant. Different account IDs belonging to the same human fail. ADMIN has
no grant bypass. Stored role/is_active/auth_version and both human/grant attestations
are revalidated at approval/replay. Missing human classification denies the action.

Immutable provenance contains actual source record, capture/analysis/artifact/claim,
lecturer/author UUID and claimed Scopus ID, time/revision/digests and authenticity
metadata if available. Source kind/tier remain SOURCE_CLAIM/INSTITUTION_DECLARED.
No canonical evidence enum, promotion mapping or approved identity is changed.
INDEPENDENT_VERIFIED and INSTITUTIONAL_EXCEPTION are distinct conceptual assurance
values; an offline exception approval retains INSTITUTIONAL_EXCEPTION.

B2-B exact current generation, source envelope replay, historical provenance,
candidate version/history, ownership/negative identity checks, capture completeness,
active rules and D-2 are reused unchanged. Authority-reported contradictions and
invalid/withdrawn assessments block both branches rather than falling back to an
exception. Missing/INSUFFICIENT independent evidence is separately classified.
Revoked institutional issuance blocks even a supported standard proposal.

Proposals and approval results are detached immutable JSON/digest drafts labeled
OFFLINE_PROPOSAL_PREPARED or OFFLINE_APPROVAL_VALIDATED, simulation_only=true,
final_acceptance=false. Full current authority/source replay is required; client
rehashing cannot substitute reviewer, pair, revision, time, assurance or approval.
Cross-candidate and cross-lecturer reuse fails. Original event-context timestamps
are retained during replay, not replaced by the clock. There is no durable event
store proving those timestamps; the separate proposal specifies that release gap.

Default HybridAuthority raises HYBRID_AUTHORITY_UNAVAILABLE. No production adapter,
endpoint, flag, worker or alternate acceptance service is registered. New submit
unconditionally raises SOURCE_CLAIM_WORKFLOW_INACTIVE; B2-B submit remains unchanged.
No new function writes a decision or canonical association.

## Caller transaction and security evidence

Preparation/approval borrow the caller's connection in a fresh autoflush-disabled
ORM Session using an owned read SAVEPOINT. Its rollback/close affect only the child
savepoint, not caller-owned outer work. Pending parent objects are neither flushed
nor expired. Tests observe no INSERT/UPDATE/DELETE/COMMIT from hybrid operations;
earlier caller writes survive semantic failures, unexpected IntegrityError and retry.
Only the test owner explicitly rolls back its outer work. No ORM objects or mutable
authority dictionaries escape snapshots. A SAVEPOINT is not a PostgreSQL coherent
snapshot/concurrency guarantee.

| Security invariant | Evidence/status |
| --- | --- |
| Institutional declaration never independent evidence | Typed separate provenance; standard missing/type-laundering tests; no IdentityEvidence writes. |
| Explicit exception permissions, no generic ADMIN override | Default deny authority; grant checks on both actions; synthetic ADMIN-without-grant denied. Actual grant authority BLOCKED. |
| Two authorized HUMAN principals | Both account and human IDs differ; missing/revoked/service classifications denied; actual registry BLOCKED. |
| Fresh source/role/replay binding | Stored B2-B revalidation + current authority context digest/full canonical replay; role/session/grant/source/tamper tests. |
| Conflicts cannot be waived | B2-B hard ownership/history/negative checks plus contradictory assessment denials; source duplicate-owner test. |
| No final/duplicate acceptance | All draft results nonfinal; both submit guards inactive; repeated drafts deterministic and zero identity/review writes. Durable finalization NOT_IMPLEMENTED. |
| Protected data minimized | B2-A safe DTOs, allowlisted authority metadata, no raw source/account secrets/storage refs; snapshot privacy test. Reason is bounded text, not a secret scanner. |
| Append-only historical semantics | No historical or review writes. Future correction/compensation and atomic audit specified separately, not implemented. |
| Privileged HTTP access | No new route. Future authenticated binding, HTTP security and E2E NOT_EXECUTED. |

## Actual tests and checks

- Initial focused draft: 6 FAIL / 78 PASS. The regressions caught incorrect denial
  classification of invalid/withdrawn/contradictory standard evidence as insufficiency.
  These cases were denied already; the correction preserves the specific blocker.
- Intermediate focused: 84 PASS. Final additional authority/revocation/pair cases:
  **92/92 focused PASS**, exit 0, 15.97s.
- **597/597 combined PASS**, exit 0, 52.71s = 92 new + 505 relevant accepted cases,
  including all 52 B2-B tests. No final failures/skips.
- The first combined sandbox run failed on Windows WinError 5 in an existing pytest
  temp fixture/cleanup. The same guarded command passed with approved execution.
  No test was skipped or guard weakened. Temporary synthetic files are ignored .tmp.
- Four accepted combined legacy NAME/PUBLICATION ACCEPT/REJECT regressions invoke
  real unchanged service methods on synthetic SQLite only. No real or SOURCE_CLAIM
  decision is executed. app.main/app.core.database/conftest modules loaded: [].
- Ruff 0.17.3: zero diagnostics on both new paths. Scoped diff check, generated patch
  added-line whitespace and reverse-apply checks pass. Global diff check still fails
  only on three preexisting research Markdown trailing spaces, with existing LF/CRLF
  warnings; these files remain byte-identical.

Exact commands, captured outputs, environment safeguards and failed attempts are in
TEST_RESULTS.txt. Hashes and baseline preservation are in VALIDATION.json/MANIFEST.

## Remaining blockers and unexecuted checks

IMPLEMENTED: transient hybrid contracts, pure policy, binding to staging provenance,
read-only proposal/approval/replay, two-human/grant validation over authoritative
contract outputs, immutable assurance distinction and inactive submission guard.

BLOCKED: production authority adapters for formal issuance, independently qualifying
identity verification, human registry and explicit exception permissions. Current
models cannot enforce these facts, so no permissive substitute is implemented.

DEFERRED: durable proposal/approval/finalization/assurance/compensation storage,
canonical promotion policy execution, actual negative reopen lifecycle, auth-bound
HTTP integration and release. The business HYBRID choice is not reopened.

NOT_EXECUTED: application DB/PostgreSQL, schema migration, PG constraints/JSONB/
partial uniqueness/savepoints/isolation/concurrency, actual HTTP/JWT dependencies,
web E2E, frontend build, real decisions, imports and deployment. SQLite mirrors
omit PG CHECKs/partial indexes/external FKs and cannot establish these guarantees.
The independent verifier port is not an implemented ORCID/DOI matching engine.

## Rollback and next recommended gate

No runtime route/config/schema registration exists. For a reviewed rollback, archive
the seven hashed artifacts, verify current hashes still match, then remove only
the two listed new code/test files and these seven B2-C artifacts if explicitly
authorized. Preserve every preexisting dirty file. Do not reset, clean, stash,
reverse unrelated patches or run database rollback. No rollback was executed.

Next: independent B2-C offline review, followed by separate approval of the
authority/persistence design and qualification rules, then an authorized disposable
PostgreSQL + authenticated HTTP/E2E gate. No automatic next gate or activation.

STOPPED after B2-C for independent review. No commit, no push, no application DB connection.
