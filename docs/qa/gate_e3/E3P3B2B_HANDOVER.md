# E3-P3-B2-B — safe SOURCE_CLAIM decision compatibility boundary

Date: 2026-10-30 (Asia/Bangkok). Status: READY FOR INDEPENDENT OFFLINE REVIEW.
Workflow remains INACTIVE. This is not a completed/released SOURCE_CLAIM decision workflow.

## Result and explicit status

| Status | Delivery |
| --- | --- |
| IMPLEMENTED | Authorized server-context checks; trusted prospective ACCEPT snapshot; current generation/eligibility/conflict/D-2 validation; full replay comparison; unconditional inactive submit boundary. |
| BLOCKED | Canonical SOURCE_CLAIM promotion: the accepted IdentityEvidence vocabulary and promotion contract cannot represent it. An explicit owner policy is required. |
| DEFERRED | SOURCE_CLAIM ACCEPT/REJECT/REOPEN/REVOKE execution, durable decision snapshot/review writes, HTTP access/release, frontend integration and production activation. |
| NOT_EXECUTED | PostgreSQL, migrations, real ICTU imports, real reviewer decisions, HTTP authentication/E2E and deployment. |

The requirements explicitly allow a compatibility-only implementation when the
existing promotion contract cannot safely represent SOURCE_CLAIM. That branch
applies here. No evidence type, verification tier or canonical approval workaround
was invented. A valid draft still cannot execute a decision.

## Exact changed files

Only two new code/test files:

1. `backend/app/services/source_claim_decision_boundary.py`
2. `backend/tests/unit/test_source_claim_decision_boundary.py`

Five new E3P3B2B artifacts are written under `docs/qa/gate_e3/`. No existing file
is modified. The baseline was the accepted dirty pre-task worktree: main, HEAD
`4bb69f6efaac945399b1c191fc12879ad1c62885` (context only). Captured status with
`-uall` and 1,662 tracked/non-ignored-untracked file hashes before edits. All 1,662
pre-existing files, including B2-A/R1 code and its five accepted artifact hashes,
are preserved. The patch is relative to this worktree, not a HEAD reset/baseline.

No commit/push/reset/clean/stash, schema/migration change, frontend change or
application/PostgreSQL database connection. Only synthetic SQLite test data was used.

## Verified existing contracts and blocker

- `CandidateReviewService._accept/_reject` authorize stored active ADMIN/REVIEWER
  accounts, check current completed observations and candidate versions. ACCEPT
  preserves existing identity/cardinality checks and D-2 before identity creation.
- `candidate_review_service.py`, `CANDIDATE_TO_IDENTITY_EVIDENCE_TYPE` and
  `_promote_candidate_evidence_to_identity` recognize NAME/PUBLICATION only and
  explicitly refuse unsupported kinds. The snapshot/promotion/decision code is unchanged.
- `models/identity.py`, `IdentityEvidence` CHECK permits APPROVED_ID, ORCID_EXACT,
  DOI_EXACT, PUBLICATION_OVERLAP, COAUTHOR_CONFIRMED, NAME_SIMILARITY and AFFILIATION_MATCH.
  It has no institutional SOURCE_CLAIM representation. Reviewer reasons are not evidence.
- `uq_identities_scopus_author_approved` protects one approved owner per Scopus
  author. Many authors for one lecturer are allowed. Existing exact identities
  cannot be silently reattributed to a new candidate decision.
- REOPEN exists in history/schema vocabulary, but no operative candidate REOPEN
  endpoint/service was found in the inspected source. This delivery adds none.
- B2-A/R1 provides an offline source read contract; STAGED runs stay outside the
  live COMPLETED-only reviewer path. Its writer/read/provenance logic is unchanged.

The exact owner policy choices and later release prerequisites are in
E3P3B2B_DECISION_CONTRACT.md. Neither choice is implemented implicitly.

## Implemented compatibility behavior

`SourceClaimDecisionBoundary.prepare(actor, command)` returns an immutable
`PreparedSourceClaimDecision(snapshot_json, snapshot_hash)`. It is a deterministic
prospective decision-context draft, not a stored CandidateReview or completed decision.

- Actor ID/auth_version must come from existing authenticated server context,
  never request-supplied reviewer/role fields. Stored active ADMIN/REVIEWER role
  and auth_version are checked freshly before candidate information is read.
- Candidate must be PENDING with the requested version and matching observation.
  Existing terminal status is refused. Any existing candidate-review history is
  conservatively blocked pending an explicit source reopen/replay policy; a
  PENDING flag alone cannot erase a previous negative human decision.
- Requested run must be the source writer's STAGED rule set/version. Historical
  envelope hash/shape is checked through the accepted R1 helper. B1's trusted
  preparation and exact run replay verification are reused to reject stale inputs,
  changed descriptors, snapshots, source refs and unrelated observations.
- Every selected source descriptor must be SOURCE_CLAIM / INSTITUTION_DECLARED,
  CURRENT with usable-declaration weight 1. WITHDRAWN/NOT_OBSERVED/AMBIGUOUS/INVALID
  is refused. A reason cannot waive a data-integrity or ownership conflict.
- All captures at the latest comparable instant for each selected source scope/
  projection must be COMPLETE. Older PARTIAL captures remain labeled history and
  do not invalidate a later complete observation. UUIDs do not establish chronology.
- Exact existing identities, negative identity states, an approved different owner
  and competing institutional ownership are blocked. Multiple Scopus IDs for the
  same lecturer remain represented independently and invoke existing D-2 reasons.
- The unchanged D-2 policy is evaluated with SOURCE_CLAIM, not PUBLICATION. Therefore
  NAME_EVIDENCE_ONLY still requires a nonblank reason; other competition triggers remain.

The snapshot contains actor ID/role/auth_version; candidate pair/status/version;
observation/run identities and hashes; active activation/rule versions; comparable
capture history; logical fingerprints; a hash binding full trusted descriptors;
and B2-A's allowlisted source provenance/history DTO. It carries the normalized
reason/triggers and explicit workflow_active=false / decision_enabled=false /
BLOCKED_OWNER_POLICY_REQUIRED markers. No raw source rows or account secrets are copied.

`verify_replay` recomputes this entire trusted snapshot, validates the supplied
canonical hash AND full representation, and rejects even self-consistently rehashed
client changes. Role revocation, new capture/rules/version, negative state and
descriptor corruption are rechecked. No volatile generated timestamp or new UUID
inflates receipt identity. This is draft replay, not decision-write idempotency.

`submit` revalidates then ALWAYS raises SOURCE_CLAIM_WORKFLOW_INACTIVE. There is
no enable flag/config/client bypass or delegation to the old review service.

## Transaction ownership

The caller retains its outer Session/transaction/connection. Preparation borrows
that exact connection into a fresh, autoflush-disabled ORM Session with
`join_transaction_mode="create_savepoint"`. This avoids stale identity-map roles,
versions and source values without expiring or autoflushing caller-owned objects.
The child closes/rolls back only its SAVEPOINT. No new engine/outer transaction,
explicit Session.begin(), outer commit/rollback, insert/update/delete or audit write
is performed. Only JSON strings escape the view, not ORM objects or mutable aliases.

Tests verify earlier caller writes survive semantic and unexpected IntegrityError
failures, retries work, pending caller objects are not flushed, and the caller can
still roll back its outer work. Unexpected database errors propagate, not ordinary
duplicate recovery or false success. SQLite verifies these scoped mechanics only;
SAVEPOINTs do not prove PostgreSQL snapshot isolation or whole-job exclusivity.

## Tests actually run

- Initial focused draft: 45 PASS; after additional history/replay/error cases:
  **52/52 focused PASS**, exit 0.
- Combined offline: **505/505 PASS**, exit 0 = 52 B2-B + 453 accepted offline/pure
  cases. No final failures/skips.
- Includes valid/stale/withdrawn/ambiguous/invalid/incomplete claims, active rules,
  competing ownership, multi-ID, candidate/identity negatives, prior review history,
  forbidden/revoked roles, receipt/storage tampering, pending/caller transactions
  and unexpected integrity propagation.
- Four regressions invoke the unchanged legacy ACCEPT/REJECT service for NAME and
  PUBLICATION on synthetic SQLite fixtures only. These are not real reviewer actions
  or SOURCE_CLAIM approvals; no application database is connected. All SOURCE_CLAIM
  submit cases are refused and no source review/identity/audit rows are created.
- Network and app.main/app.core.database/conftest initialization blocked; forbidden
  modules loaded []. Pytest plugins/cache/bytecode disabled. The combined suite's
  existing temporary SQLite-file fixture ran with approved execution because the
  Windows sandbox previously denied its pytest temp directory.
- Ruff 0.17.3 clean on both new paths. Scoped diff, added-line whitespace and
  reverse patch checks pass. Global diff check retains three pre-existing research
  Markdown whitespace findings; those files remain byte-identical.

## Limitations / next authorization required

The service-side principal context is not a JWT authenticator. A future authorized
route must bind it from get_current_user/require_role and must not accept reviewer
ID, role or auth_version from request payloads. No privileged endpoint is added.
The current live queue/read/decision flow is unchanged; existing raw-root counts
and D-2 competition semantics were not redesigned.

The boundary reuses B1 `_prepare/_verify_run` and R1 `_historical_captures` internal
interfaces without modifying them; changes to those interfaces require retesting.
PostgreSQL JSONB/CHECK/uniqueness, same-pair/reviewer races, read isolation and a
future atomic mutation/receipt persistence policy are not verified by SQLite.
Under PostgreSQL READ COMMITTED a SAVEPOINT alone is not a coherent multi-query
snapshot guarantee. Release requires an independently validated isolation/locking
design, not trusting this offline draft as write authorization. Performance is
unbenchmarked. No P4, production release or automatic next gate was started.

STOPPED after B2-B compatibility delivery for independent review.
