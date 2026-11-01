# E3-P3-B2-B — prospective source decision contract, INACTIVE

Date: 2026-10-30 (Asia/Bangkok). Canonical source promotion is BLOCKED.

## Why the compatibility-only branch applies

The accepted candidate kind SOURCE_CLAIM / source tier INSTITUTION_DECLARED is an
institutional declaration. It is neither verified author identity nor any of the
seven allowed IdentityEvidence types. The existing promotion function handles
NAME/PUBLICATION and refuses SOURCE_CLAIM. Reviewer approval/reason must not be
disguised as an evidence observation. Neither a new type nor a migration is added.

The owner must explicitly decide between at least these policy models before
source-only ACCEPT can be implemented:

1. Keep SOURCE_CLAIM as candidate/review context only; require independent evidence
   already representable under the approved canonical mapping before ACCEPT. Define
   how source context is retained without promoting it or relaxing D-2.
2. Explicitly authorize a human SOURCE-only association decision while retaining
   the institutional declaration solely in the CandidateReview decision snapshot,
   with no fabricated IdentityEvidence promotion. This changes the current service
   contract and requires an independently approved persistence/audit/replay policy.

This gate chooses neither policy and implements no canonical association change.
Adding an IdentityEvidence type is not an implicit third option authorized here.
Actual source REJECT/REOPEN/REVOKE behavior and decision-write idempotency likewise
need an explicit lifecycle policy; they are not inferred from an ACCEPT draft.

## Internal inputs and authorization

`ReviewerContext(user_id, auth_version)` is a SERVER-BOUND result of the existing
authentication path, not a request DTO or proof issued by this helper. A later
route must use the cookie/JWT/auth_version-aware get_current_user/require_role
dependency before constructing it. Only active stored ADMIN/REVIEWER accounts
with matching auth_version can prepare a draft; role claims from clients or
pending ORM objects are not trusted. No new HTTP endpoint exists in this delivery.

`SourceClaimAcceptContext(candidate_id, observation_id, candidate_version, reason)`
contains only a prospective ACCEPT context. It has no reviewer ID, enable flag,
evidence payload, confidence, target identity status or promotion instruction.
Invalid IDs/version/reason shapes fail closed. Server data supplies evidence and policy.

## Operations

| Operation | Behavior |
| --- | --- |
| prepare(actor, command) | Validate freshly stored permissions, source/candidate context and D-2; return immutable canonical JSON plus hash. No decision, write or authorization to execute. |
| verify_replay(actor, command, snapshot_json, snapshot_hash) | Reprepare from current trusted rows; compare canonical hash and every snapshot value. Reordered JSON keys may be equivalent; changed payload/provenance/flags/actor is not. |
| submit(actor, command, snapshot_json, snapshot_hash) | Revalidate then always refuse SOURCE_CLAIM_WORKFLOW_INACTIVE. No success or release switch. |

Failures use APIError with static messages. Role/session failures are 401/403;
invalid command/reason is 422; missing candidate 404; stale/invalid/conflicting
context, unsupported source lifecycle and inactive workflow are 409.

## Preconditions and refusal rules

1. PENDING candidate, exact version and observation membership. Terminal states
   are never reopened. Any prior CandidateReview is blocked pending source replay/
   reopen policy, even if the root has been reset to PENDING independently.
2. Exact source rule-set/version and STAGED generation. Normal legacy completed
   observations cannot be misused as source decision contexts.
3. R1 historical envelope digest/structure must validate. The B1 trusted preparation
   must equal the stored generation state, and full B1 run/observation/evidence
   verification must pass. A newer valid generation never authorizes an old requested
   observation merely because its logical fingerprint happens to match.
4. Every selected descriptor must be CURRENT, weight 1, SOURCE_CLAIM and
   INSTITUTION_DECLARED. Withdrawal, NOT_OBSERVED, ambiguity, invalidity or an
   unusable extra descriptor refuses the draft; the command cannot cherry-pick it away.
5. Within each relevant source-system/scope/projection, all captures at the latest
   instant must be COMPLETE. Earlier PARTIAL captures remain provenance. Equal-time
   captures are compared as a set; a UUID never proves chronology or completeness.
6. Existing exact identities, negative identity states, an approved other owner or
   bridge ownership/conflict reasons are blocked. A reason cannot override these.
   Multiple IDs for one lecturer remain separate candidate pairs, not a merge.
7. The unchanged D-2 reason policy sees SOURCE_CLAIM, not PUBLICATION. NAME_EVIDENCE_ONLY
   remains required; active shared-author/multiple-candidate triggers remain. Blank
   reasons are refused before returning a usable prospective context.

These rules validate a draft only. They do not imply institutional declarations
are sufficient canonical identity evidence or authorize a human decision today.

## Snapshot representation

The detached canonical JSON contains:

- schema_version, boundary, intended_action=ACCEPT;
- workflow_active=false, decision_enabled=false and
  identity_evidence_promotion=BLOCKED_OWNER_POLICY_REQUIRED;
- reviewer ID/stored role/auth_version, candidate pair/status/version;
- exact observation ID/hash and generation ID/status/rules/input_hash;
- active source activation ID/sequence/identity+normalization versions;
- all comparable capture history (IDs, system/scope/projection, times/completeness);
- selected logical fingerprints and a trusted_evidence_hash binding the full
  verified normalized descriptors and source references;
- the accepted B2-A safe source DTOs: SOURCE_CLAIM/INSTITUTION_DECLARED, CURRENT state,
  declaration weight, versioned claim/capture/analysis traces and historical labels;
- D-2 reason requirements/triggers and normalized human reason.

Raw source rows, e-mails, account secrets, arbitrary payload dictionaries and
unrelated private fields are not copied into the prospective snapshot. The trusted
descriptor hash plus staged IDs/generation hash bind the internal full provenance.
The reason is review context, never IdentityEvidence. A frozen dataclass stores
JSON strings, not mutable ORM/dictionary aliases. No clock/random IDs are added,
so unchanged context yields the same draft/replay identity.

No CandidateReview is persisted here. A future real decision must create its
decision-time snapshot atomically with review/audit/state changes after source
promotion policy, authorization and PostgreSQL release gates are approved.

## Caller transaction and caching boundary

Preparation uses the caller's connection in a fresh ORM Session joined through
an owned SAVEPOINT. It does not flush/expire pending parent objects, commit or
roll back the outer transaction. The fresh identity map reads stored roles,
versions and source records rather than stale parent ORM values. Closing the view
rolls back only its own read savepoint; no ORM objects escape it.

Tests show earlier caller writes survive validation and unexpected IntegrityError
failures, retry works and the caller can roll back its own transaction. No database
error is swallowed as an ordinary duplicate or an approved decision. SQLite coverage
does not prove PostgreSQL savepoint/isolation/concurrency behavior. SAVEPOINT is not
a transaction-wide snapshot lock; production release needs coherent-source reads
and locking/serialization in the eventual mutation transaction.

## Implemented / deferred / blocked / not executed

| Category | Status |
| --- | --- |
| Authorization-context, version/current/conflict/D-2 checks and trusted snapshots | IMPLEMENTED for offline compatibility. JWT/HTTP binding is not newly implemented. |
| Full draft replay comparison and inactive submit boundary | IMPLEMENTED; no persistence or source decision success. |
| SOURCE_CLAIM -> IdentityEvidence promotion | BLOCKED on explicit owner policy; unsupported by current vocabulary. |
| SOURCE_CLAIM ACCEPT/REJECT/REOPEN/REVOKE mutation and durable decision receipts | DEFERRED; no new handler or state transition. |
| HTTP privileged evidence access/release, frontend and queue activation | DEFERRED; accepted live paths unchanged. |
| PostgreSQL, migrations, real data, HTTP/E2E and deployment | NOT_EXECUTED. |

The four legacy NAME/PUBLICATION ACCEPT/REJECT regressions run only against
synthetic isolated SQLite fixtures. They do not execute a real reviewer decision
or promote any SOURCE_CLAIM. Existing application decision handlers and canonical
constraints remain byte-identical. Stop here for independent review; no P4.
