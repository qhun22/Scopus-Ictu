# E3-P3-B2-C — SOURCE_CLAIM_HYBRID_V1 (offline compatibility)

Date: 2026-10-30 (Asia/Bangkok). Production workflow INACTIVE.

## Phase 0: compatibility and impact matrix

| Repository evidence inspected | Existing contract | B2-C impact |
| --- | --- | --- |
| `source_claim_decision_boundary.py`, prepare/_prepare/verify_replay/submit; B2-B five artifacts | Exact CURRENT/STAGED source replay, D-2, roles, negative/history/ownership checks, child read savepoint; inactive submit | Reuse unchanged. Six B2-B artifact/code hashes and reverse patch verified. |
| `models/identity.py`, IdentityEvidence; resolved M1.0 freeze sections 11–14; ADR-004 | Seven evidence types; one approved owner; human-governed identities | No new persistent type, enum, mapping or identity write. Institutional declaration is separate provenance. |
| `models/governance.py`, User; `api/dependencies.py`, get_current_user/require_role | ADMIN/REVIEWER/LECTURER, is_active and auth_version | No explicit exception grant, human/service classification or same-human account linkage. Production authority adapter remains unavailable and denies by default. |
| `models/source_staging.py`, SourceCapture/Artifact/Record/Claim; B1 writer and R1 read helper | Immutable digests, exact lineage, versioned current analysis | Bind provenance to actual selected rows and hashes. Byte integrity does not authenticate institutional issuance. |
| `candidate_review_service.py`, mapping/promotion/_accept/_reject; candidate model | Legacy NAME/PUBLICATION decisions, JSON snapshot, immutable review history | No changes. No operative SOURCE_CLAIM exception lifecycle or approver persistence. |
| `matching/rules/{orcid_rule,approved_id_rule,publication_overlap_rule}.py`; candidate_types/publication enricher | Exact rule scaffolds are not implemented verifiers; publication reconciliation is not a universal identity proof | Independent qualification requires an external authoritative assessment contract. No new matching engine and no automatic qualification from an enum or DOI/ORCID string. |
| ADR-003, M1.0 A08; audit_events/MappingReview/CandidateReview | Append-only decisions and compensation | Drafts only; future persistence requires separate append-only proposal/approval/transition design. |
| `candidate_evidence_read.py`, serializer/preview; existing review routes | SOURCE_CLAIM read/review not activated | No routes, feature flags, workers, frontend or application DB access. |

There is no need to change a frozen contract to implement typed offline drafts.
There are material **production capability gaps**: authenticated institutional
issuance, qualifying independent assessment, explicit permission grants, human
principal identity and durable hybrid transitions. Default behavior fails closed.
Synthetic authority fixtures exercise proposed invariants; they do not implement
these missing authorities or justify production readiness.

## Locked business policy

Identifier SOURCE_CLAIM_HYBRID_V1, version 1. Default STANDARD_INDEPENDENT requires
CURRENT qualifying independently verified identity assessment. A source statement,
name similarity, generic publication match, filename, reason or issuer label is
never an independent assessment. Supported strong evidence vocabularies are only
references to existing IdentityEvidence semantics, not a new promotion mapping.
Qualification is supplied by a trusted verifier, not computed from an evidence
type, a hash, a source ORCID or an arbitrary client flag.

INSTITUTIONAL_EXCEPTION permits an offline proposal when independent evidence is
insufficient, provided selected institutional provenance has verified authenticity.
It requires explicit reason, the exact risk acknowledgment token, a human reviewer
with an explicit proposal grant, and a different authorized human with an explicit
exception-approval grant. No ADMIN bypass. Different account IDs for the same human
do not satisfy separation of duties. Invalid/withdrawn independent assessments and
contradictions are blocking, not treated as missing evidence. B2-B source/ownership/
negative decision protections always run first and cannot be waived by an authority.

Assurance values INDEPENDENT_VERIFIED and INSTITUTIONAL_EXCEPTION are conceptual
application contract values only. Neither is a database status or new IdentityEvidence
type. An exception never becomes independent verification after approval.

## Trust and persistence boundary

The server-owned authority port must resolve current, context-bound independent
assessments, institutional authenticity and human permission attestations. It must
not deserialize these facts from request payloads. This gate supplies **no production
adapter** because existing models cannot enforce those invariants. The default port
raises HYBRID_AUTHORITY_UNAVAILABLE. Test-only adapters supply synthetic attestations.
Hashes detect substitution relative to that authority; they do not authenticate it.

Proposal preparation, approval validation and replay remain read-only, detached
draft operations. No proposal/approval is persisted or a final decision emitted.
Timestamps are explicit server-bound event-context inputs; they are retained during
replay rather than replaced with now(). Their durable origin/uniqueness cannot be
proven until the event store exists. Final submit always returns
SOURCE_CLAIM_WORKFLOW_INACTIVE, regardless of any offline draft.

Further operation details, tests, persistence proposal and release blockers are
recorded in the final handover. No frozen contract replacement or migration execution.

## Typed operations and evidence boundary

`ReviewBranch`, `AssuranceBasis`, `AssessmentState`, `Grant`,
`SourceAuthenticityState` and `DenialReason` are new transient application values.
No existing enum or database column is renamed. `IndependentAssessment`,
`HumanAuthority`, `SourceAuthenticity` and `AuthorityFacts` are immutable,
server-owned authority outputs, not request schemas. The complete facts bundle
must bind to the B2-B snapshot digest, which binds candidate/lecturer/Scopus ID,
reviewer/auth_version, reason, observation/generation, source/rule versions and
logical fingerprints. Invalid shapes, duplicate authority IDs and mismatched
bindings fail closed. A current assessment from a future verifier is required;
an unsupported stale assessment state is invalid, never an exception fallback.

`InstitutionalProvenance` binds selected active B2-A traces to actual staging
artifact/capture/record/claim rows and linkage. It retains source system, record,
lecturer, author UUID and claimed Scopus ID, capture/analysis/artifact/claim IDs,
capture timestamp, artifact digest as stable source revision/snapshot digest,
record digest, CURRENT validity, SOURCE_CLAIM/INSTITUTION_DECLARED and, if supplied,
the separately verified ICTU issuance receipt. Missing verification stays absent;
it is never inferred from a URL, source filename or a matching artifact hash.
All selected active traces must have current formal verification for an exception.
This is deliberately conservative for historical traces retained in the active
B1 descriptor. Revoked selected issuance blocks both branches. Standard may use
independent verification without authenticating institutional issuance, but the
source claim still remains explicitly unverified institutional context.

`evaluate_hybrid_policy` returns **evidence-policy eligibility only**, not an action
authorization or signature verifier. QUALIFYING independently verified assessments
must reference existing strong evidence vocabulary; NAME_SIMILARITY and
SOURCE_CLAIM cannot qualify. Missing/INSUFFICIENT assessment can allow exception
eligibility. INVALID/WITHDRAWN/CONTRADICTORY or authority-reported hard conflicts
deny both branches. The full preparation path additionally enforces principals,
grants, reason/risk acknowledgment, source context, history and all B2-B guards.

| Operation | Result and checks |
| --- | --- |
| prepare_proposal(actor, HybridCommand, proposed_at) | Fresh stored actor authorization, B2-B context, current authority facts, human/grant checks, provenance and evidence-policy checks; detached immutable JSON/hash, OFFLINE_PROPOSAL_PREPARED. No persistence. |
| verify_proposal(actor, command, original, proposed_at) | Recompute authoritative current facts using the original server-bound event context, compare the full canonical representation and digest. Rehashed substitutions fail. |
| prepare_exception_approval(reviewer, approver, command, original, proposed_at, approved_at) | Exception branch only; reauthorize both users, replay original proposal, require explicit approval grant, different user AND human IDs and valid event ordering. Return OFFLINE_APPROVAL_VALIDATED, not ACCEPTED. |
| verify_exception_approval(..., original_approval, ...) | Reprepare and fully compare the approval as well as original proposal/context. Fresh revocations, authority revisions and source changes invalidate it. |
| submit(...) | Always SOURCE_CLAIM_WORKFLOW_INACTIVE. No arguments, draft, authority or direct function enables submission. B2-B submit remains unchanged. |

Proposals and approvals include policy ID/version, branch, assurance, reviewer
attestation, optional approver attestation, event timestamps, reason/risk acknowledgment,
source context and digest, institutional provenance, independent assessment receipt
references, authority revision, conflict/eligibility evaluation, nonfinal outcome,
and a null revocation/supersession reference. Approval also binds the exact proposal
digest. All snapshots explicitly carry simulation_only=true, final_acceptance=false,
workflow_active=false and decision_enabled=false. No volatile IDs or clock reads
are generated by preparation. Equivalent input context is deterministic.

The caller owns the outer transaction. A fresh child ORM Session uses the same
connection and an owned read SAVEPOINT, with autoflush disabled. No pending parent
objects are flushed or expired; no parent commit/rollback/close or review/audit DML
is performed. Database/authority failures propagate. A SAVEPOINT does not establish
a coherent multi-query PostgreSQL READ COMMITTED snapshot; live concurrency and
atomic finalization remain blocked pending the separate persistence proposal.

No raw source rows, email addresses, passwords, token fields or storage paths are
serialized. Human reason is preserved as explicit bounded review text, never used
as evidence. It is not a secret scanner: operators must not enter secrets as reasons.
The authority adapter must return typed allowlisted receipt metadata, not arbitrary
certificate/documents or private payload dictionaries.
